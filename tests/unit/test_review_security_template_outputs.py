"""Docs claim check: --template reports hide secret values like the standard ones.

A moto Lambda function has secret-looking environment variables. The CLI runs
with built-in templates and with a JSON report template loaded by path that
asks for every field (``include_all_fields``) and lists the raw environment
fields as explicit Excel and Word columns. No output file (Excel, Word, the
tag-compliance JSON, the snapshot) may contain a clear value; the mask text
must be where the value would be.
"""

import importlib
import io
import json
import logging
import sys
import zipfile

import boto3
import pytest
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard
from inventag.security.secret_values import MASK

cli_main = importlib.import_module("inventag.cli.main")

SECRETS = {
    "DB_PASSWORD": "planted-template-db-pw-41c7",
    "API_URL": "https://user:planted-template-url-pw-93ad@example.com",
}

RAW = "raw_data.Environment.Variables"
JSON_TEMPLATE = {
    "format_version": 1,
    "kind": "report",
    "name": "audit-all-fields",
    "spec": {
        "title": "Audit",
        "columns": [
            {"field": "resource_name", "header": "Name"},
            {"field": f"{RAW}.DB_PASSWORD", "header": "DB password"},
            {"field": f"{RAW}.API_URL", "header": "API URL"},
        ],
        "excel": {"include_all_fields": True, "layout": "single-sheet"},
        "word": {
            "columns": [
                {"field": "resource_name", "header": "Name"},
                {"field": f"{RAW}.DB_PASSWORD", "header": "DB password"},
                {"field": f"{RAW}.API_URL", "header": "API URL"},
            ]
        },
    },
}


@pytest.fixture
def estate(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        role = boto3.client("iam").create_role(
            RoleName="r", AssumeRolePolicyDocument="{}"
        )["Role"]["Arn"]
        code = io.BytesIO()
        with zipfile.ZipFile(code, "w") as z:
            z.writestr("h.py", "def h(e, c):\n    return 1\n")
        boto3.client("lambda").create_function(
            FunctionName="fn-template",
            Runtime="python3.12",
            Role=role,
            Handler="h.h",
            Code={"ZipFile": code.getvalue()},
            Environment={"Variables": dict(SECRETS)},
        )
        yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    redaction.clear_registered_secrets()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["inventag", *argv])
    try:
        cli_main.main()
    except SystemExit as e:
        return e.code or 0
    return 0


def _blob(path):
    data = path.read_bytes()
    if path.suffix in (".xlsx", ".docx"):
        with zipfile.ZipFile(path) as z:
            data = b"".join(z.read(n) for n in z.namelist())
    return data


@pytest.mark.parametrize(
    "template",
    ["standard-bom", "finops-cost-allocation", "security-baseline", "BY_PATH"],
)
def test_template_outputs_hide_secret_values(estate, tmp_path, monkeypatch, template):
    if template == "BY_PATH":
        path = tmp_path / "audit-all-fields.json"
        path.write_text(json.dumps(JSON_TEMPLATE))
        template = str(path)
    code = _run(
        monkeypatch,
        [
            "--account-regions",
            "us-east-1",
            "--no-billing-validation",
            "--template",
            template,
            "--create-excel",
            "--create-word",
            "--output-directory",
            "out",
        ],
    )
    assert code in (0, 3), code
    written = [p for p in (tmp_path / "out").rglob("*") if p.is_file()]
    suffixes = {p.suffix for p in written}
    assert {".xlsx", ".docx"} <= suffixes, written
    if template == "finops-cost-allocation":  # has a tag policy: JSON output
        assert any(p.name.startswith("tag_compliance_") for p in written), written
    leaks = [
        f"{name} in {p.relative_to(tmp_path)}"
        for p in written
        for name, value in SECRETS.items()
        if value.encode() in _blob(p)
    ]
    assert not leaks, leaks
    if template.endswith(".json"):
        excel = next(p for p in written if p.suffix == ".xlsx")
        word = next(p for p in written if p.suffix == ".docx")
        for report in (excel, word):
            data = _blob(report)
            assert MASK.encode() in data, report.name
            assert b"LAMBDA" in data.upper(), report.name
