"""Docs claim check for v1.2.0: behaviours the docs state, run for real.

Each test runs the real CLI entry point (``inventag.cli.main.main``) under moto
and asserts what the code does. Where a claim in the docs is false, the test
asserts the real behaviour and says so in its docstring (claim marked FALSE).

C1  exit code 5 (--fail-on-account-error)
C2  exit code 6 (--fail-if-empty), with and without the flag
C3  source, sources, detail_level as template columns
C4  a session that expires during the scan
C5  --resume scans only the failed account
C6  order of the opt-in exit codes
"""

import importlib
import json
import logging
import sys
from pathlib import Path

import boto3
import botocore.client
import docx
import openpyxl
import pytest
import yaml
from botocore.exceptions import ClientError
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard
from tests.e2e.estate import seed_estate

cli_main = importlib.import_module("inventag.cli.main")
cbg = importlib.import_module("inventag.core.cloud_bom_generator")

GOOD_ID = "123456789012"  # the account of the default (moto) credentials
OTHER_ID = "222222222222"
GOOD = {"account_id": GOOD_ID, "regions": ["us-east-1"]}
OTHER = {
    "account_id": OTHER_ID,
    "role_arn": f"arn:aws:iam::{OTHER_ID}:role/InvenTagRole",
    "regions": ["us-east-1"],
}
THIRD = {
    "account_id": "333333333333",
    "role_arn": "arn:aws:iam::333333333333:role/InvenTagRole",
    "regions": ["us-east-1"],
}
THIRD_ID = "333333333333"
BASE = ["--create-excel", "--no-billing-validation"]


# ----------------------------------------------------------------- fixtures
@pytest.fixture
def empty_aws(monkeypatch, tmp_path):
    """moto AWS with nothing in it; the working directory is ``tmp_path``."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        yield
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


@pytest.fixture
def aws(empty_aws):
    """moto AWS with the standard e2e estate (VPC, buckets, queue, topic, ...)."""
    seed_estate()
    yield


def run_cli(*args):
    old_argv = sys.argv
    sys.argv = ["inventag", *args]
    try:
        cli_main.main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv


def accounts_file(tmp_path, accounts):
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps({"accounts": accounts}))
    return str(path)


def reports(out, suffix=".xlsx"):
    return sorted(Path(out).glob(f"*{suffix}"))


def workbook(path):
    """{sheet name: list of row tuples} of an Excel report."""
    wb = openpyxl.load_workbook(path)
    return {ws.title: list(ws.iter_rows(values_only=True)) for ws in wb}


def workbook_text(path):
    return "\n".join(
        str(cell)
        for rows in workbook(path).values()
        for row in rows
        for cell in row
        if cell is not None
    )


def total_resources(path):
    """The TOTAL row of the Summary sheet."""
    for row in workbook(path)["Summary"]:
        if row and str(row[0]).upper() == "TOTAL":
            return row[1]
    raise AssertionError("no TOTAL row in the Summary sheet")


def logged(caplog, level=logging.WARNING):
    return [r.getMessage() for r in caplog.records if r.levelno >= level]


def seed_account(account_id, role_arn):
    """Create two buckets and a queue inside ``account_id`` (via an assumed role)."""
    c = boto3.client("sts", region_name="us-east-1").assume_role(
        RoleArn=role_arn, RoleSessionName="seed"
    )["Credentials"]
    kw = dict(
        region_name="us-east-1",
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
    )
    for i in range(2):
        boto3.client("s3", **kw).create_bucket(Bucket=f"acct-{account_id}-b{i}")
    boto3.client("sqs", **kw).create_queue(QueueName=f"acct-{account_id}-q")


class RoleControl:
    """Makes ``sts:AssumeRole`` fail (AccessDenied) for chosen account IDs and
    remembers the temporary access key each account got."""

    def __init__(self, monkeypatch, failing=()):
        self.failing = set(failing)
        self.keys = {}
        original = cbg.CloudBOMGenerator._assume_role_session
        control = self

        def assume(self, role_arn, account_id, external_id=None):
            if str(account_id) in control.failing:
                raise ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "not authorized to assume the role",
                        }
                    },
                    "AssumeRole",
                )
            session = original(self, role_arn, account_id, external_id)
            control.keys[str(account_id)] = session.get_credentials().access_key
            return session

        monkeypatch.setattr(cbg.CloudBOMGenerator, "_assume_role_session", assume)


class Expiry:
    """After ``allow`` successful non-STS calls (of the chosen credentials, or of
    all calls when ``access_key`` is None) every call raises ``code``."""

    def __init__(self, monkeypatch, allow, code="ExpiredToken", key_of=None):
        self.allow = allow
        self.code = code
        self.key_of = key_of  # callable returning the access key to expire
        self.seen = 0
        self.raised = 0
        original = botocore.client.BaseClient._make_api_call
        expiry = self

        def call(client, operation_name, api_params):
            if client.meta.service_model.service_name == "sts":
                return original(client, operation_name, api_params)
            if expiry.key_of is not None:
                creds = client._request_signer._credentials
                if not (creds and creds.access_key == expiry.key_of()):
                    return original(client, operation_name, api_params)
            expiry.seen += 1
            if expiry.seen > expiry.allow:
                expiry.raised += 1
                raise ClientError(
                    {"Error": {"Code": expiry.code, "Message": "The token expired"}},
                    operation_name,
                )
            return original(client, operation_name, api_params)

        monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)


# ============================================================ C1: exit code 5
def test_c1_exit_5_with_flag_exit_0_without_report_of_good_account(
    aws, tmp_path, monkeypatch, caplog
):
    """One account of two cannot be reached (assume-role fails)."""
    RoleControl(monkeypatch, failing={OTHER_ID})
    caplog.set_level(logging.INFO)
    path = accounts_file(tmp_path, [GOOD, OTHER])
    flag = run_cli(
        "--accounts-file",
        path,
        *BASE,
        "--fail-on-account-error",
        "--output-directory",
        "out_flag",
    )
    assert flag == 5
    assert any(
        "--fail-on-account-error is set (exit code 5)" in m for m in logged(caplog)
    )
    plain = run_cli("--accounts-file", path, *BASE, "--output-directory", "out_plain")
    assert plain == 0
    for out in ("out_flag", "out_plain"):
        files = reports(tmp_path / out)
        assert len(files) == 1, out
        sheets = workbook(files[0])
        cells = {
            str(c)
            for name, rows in sheets.items()
            if name not in ("Summary", "Notes")
            for row in rows
            for c in row
        }
        assert GOOD_ID in cells and total_resources(files[0]) > 0
        assert OTHER_ID not in cells
        # The failed account is named in the notes of the report.
        assert OTHER_ID in workbook_text(files[0])
        assert "not scanned" in workbook_text(files[0])
    assert any(
        "were not scanned" in m and "does not include" in m for m in logged(caplog)
    )


@pytest.mark.parametrize("flag", [[], ["--fail-on-account-error"]])
def test_c1_every_account_failing_is_exit_1_and_no_report(
    aws, tmp_path, monkeypatch, flag
):
    RoleControl(monkeypatch, failing={OTHER_ID, THIRD_ID})
    path = accounts_file(tmp_path, [OTHER, THIRD])
    code = run_cli("--accounts-file", path, *BASE, *flag, "--output-directory", "out")
    assert code == 1
    assert reports(tmp_path / "out") == []


# ============================================================ C2: exit code 6
# moto's account always holds default resources (default VPC, security group,
# KMS keys), so "nothing found" is made by discovery returning no resource; one
# test uses a service filter that matches nothing ("the filters removed all").
@pytest.fixture
def none_found(aws, monkeypatch):
    monkeypatch.setattr(
        cbg.CloudBOMGenerator,
        "_discover_account_resources_inner",
        lambda self, account_id, context: [],
    )
    return ["--account-regions", "us-east-1"]


def test_c2_default_path_none_found(none_found, tmp_path, caplog):
    """No flag: exit 0, no report file, one warning. With the flag: exit 6 and
    still no report file."""
    caplog.set_level(logging.INFO)
    assert run_cli(*BASE, *none_found, "--output-directory", "plain") == 0
    assert reports(tmp_path / "plain") == []
    assert any("No resources to report" in m for m in logged(caplog))
    flagged = run_cli(*BASE, *none_found, "--fail-if-empty", "--output-directory", "f")
    assert flagged == 6
    assert reports(tmp_path / "f") == []


def test_c2_template_path_none_found(none_found, tmp_path):
    """--template: exit 0 without the flag and a report file IS written (it lists
    no resources); with the flag exit 6 and the report is still written."""
    common = [*BASE, *none_found, "--template", "standard-bom"]
    assert run_cli(*common, "--output-directory", "plain") == 0
    plain = reports(tmp_path / "plain")
    assert len(plain) == 1 and total_resources(plain[0]) == 0
    assert run_cli(*common, "--fail-if-empty", "--output-directory", "f") == 6
    flagged = reports(tmp_path / "f")
    assert len(flagged) == 1 and total_resources(flagged[0]) == 0


def test_c2_filter_removing_everything_default_path(aws, tmp_path):
    code = run_cli(
        *BASE,
        "--account-regions",
        "us-east-1",
        "--account-services",
        "NOSUCHSERVICE",
        "--fail-if-empty",
        "--output-directory",
        "out",
    )
    assert code == 6
    assert reports(tmp_path / "out") == []


# =========================================== C3: source, sources, detail_level
PROVENANCE = ["source", "sources", "detail_level"]
SOURCE_VALUES = {"service-api", "tagging-api", "billing"}
DETAIL_VALUES = {"full", "identity"}

REPORT_TEMPLATE = {
    "format_version": 1,
    "kind": "report",
    "name": "provenance",
    "spec": {
        "columns": [
            {"field": "resource_id", "header": "ID"},
            {"field": "source", "header": "Source"},
            {"field": "sources", "header": "Sources"},
            {"field": "detail_level", "header": "Detail"},
        ],
        "tag_columns": "none",
        "word": {
            "sections": ["service-tables"],
            "columns": [
                {"field": "resource_id", "header": "ID"},
                {"field": "source", "header": "Source"},
                {"field": "sources", "header": "Sources"},
                {"field": "detail_level", "header": "Detail"},
            ],
        },
    },
}
EXCEL_LAYOUT = {
    "template_version": "2.0",
    "format_type": "excel",
    "extra_fields": PROVENANCE,
    "sections": [
        {
            "id": "all",
            "content_type": "resources",
            "group_by_service": False,
            "sheet_name": "All",
            "columns": [
                {"field": "id", "heading": "ID"},
                {"field": "source", "heading": "Source"},
                {"field": "sources", "heading": "Sources"},
                {"field": "detail_level", "heading": "Detail"},
            ],
        }
    ],
}
WORD_LAYOUT = {
    "template_version": "2.0",
    "format_type": "word",
    "extra_fields": PROVENANCE,
    "sections": [
        {
            "id": "inventory",
            "content_type": "resources",
            "columns": [
                {"field": "id", "heading": "ID"},
                {"field": "source", "heading": "Source"},
                {"field": "sources", "heading": "Sources"},
                {"field": "detail_level", "heading": "Detail"},
            ],
        }
    ],
}


def excel_records(path):
    """Rows of every sheet that has an ID, Source, Sources and Detail header."""
    out = []
    for rows in workbook(path).values():
        header = next((r for r in rows if r and "Detail" in r), None)
        if header is None:
            continue
        idx = {h: header.index(h) for h in ("ID", "Source", "Sources", "Detail")}
        for row in rows[rows.index(header) + 1 :]:
            if row and row[idx["ID"]]:
                out.append({h: row[i] for h, i in idx.items()})
    return out


def word_records(path):
    out = []
    for table in docx.Document(str(path)).tables:
        header = [c.text for c in table.rows[0].cells]
        if "Detail" not in header:
            continue
        for row in table.rows[1:]:
            out.append(dict(zip(header, [c.text for c in row.cells])))
    return out


def check_provenance(records):
    assert records, "no resource rows with the provenance columns"
    for rec in records:
        assert rec["Source"] in SOURCE_VALUES, rec
        assert rec["Detail"] in DETAIL_VALUES, rec
        assert rec["Sources"], rec
        assert set(str(rec["Sources"]).split("+")) <= SOURCE_VALUES, rec
    assert any(r["Detail"] == "full" for r in records)


def test_c3_report_template_fills_source_sources_detail_level(aws, tmp_path):
    path = tmp_path / "provenance.yaml"
    path.write_text(yaml.safe_dump(REPORT_TEMPLATE))
    code = run_cli(
        *BASE,
        "--create-word",
        "--account-regions",
        "us-east-1",
        "--template",
        str(path),
        "--output-directory",
        "out",
    )
    assert code == 0
    check_provenance(excel_records(reports(tmp_path / "out")[0]))
    check_provenance(word_records(reports(tmp_path / "out", ".docx")[0]))


def test_c3_layout_files_with_extra_fields(aws, tmp_path):
    xl = tmp_path / "layout.json"
    xl.write_text(json.dumps(EXCEL_LAYOUT))
    wd = tmp_path / "layout.yaml"
    wd.write_text(yaml.safe_dump(WORD_LAYOUT))
    code = run_cli(
        *BASE,
        "--create-word",
        "--account-regions",
        "us-east-1",
        "--excel-template",
        str(xl),
        "--word-template",
        str(wd),
        "--output-directory",
        "out",
    )
    assert code == 0
    check_provenance(excel_records(reports(tmp_path / "out")[0]))
    check_provenance(word_records(reports(tmp_path / "out", ".docx")[0]))


def test_c3_layout_file_needs_extra_fields(aws, tmp_path, capsys):
    """layout-flags.md: the three fields are only usable when listed in
    extra_fields. Without it the file is refused."""
    layout = dict(EXCEL_LAYOUT)
    layout.pop("extra_fields")
    xl = tmp_path / "layout.json"
    xl.write_text(json.dumps(layout))
    code = run_cli(
        *BASE,
        "--account-regions",
        "us-east-1",
        "--excel-template",
        str(xl),
        "--output-directory",
        "out",
    )
    assert code != 0
    assert "unknown column 'source'" in capsys.readouterr().err
    assert reports(tmp_path / "out") == []


# ================================================ C4: session expires mid-scan
# status.md says: "A session that expires during the scan: the run exits with
# code 0 and the report looks complete." A reviewer says such a scan fails.
# Observed: the exit code is 0 (also with --fail-on-account-error), the account
# does not count as failed, the report holds what was read before the expiry
# with no note inside it, and each listing that failed is a console warning
# ("... failed (ExpiredToken); its resources there may be incomplete").
EXPIRED_WARNING = "may be incomplete"


def notes_say_incomplete(path):
    text = workbook_text(path).lower()
    return any(w in text for w in ("expire", "incomplete", "not scanned", "partly"))


def test_c4_single_account_expiry_exit_0_partial_report_no_note(
    aws, tmp_path, monkeypatch, caplog, capsys
):
    caplog.set_level(logging.INFO)
    expiry = Expiry(monkeypatch, allow=20, code="ExpiredToken")
    path = accounts_file(tmp_path, [GOOD])
    code = run_cli(
        "--accounts-file",
        path,
        *BASE,
        "--fail-on-account-error",
        "--output-directory",
        "out",
    )
    assert expiry.raised > 0
    assert code == 0  # not 1, and not 5 although --fail-on-account-error is set
    files = reports(tmp_path / "out")
    assert len(files) == 1
    assert total_resources(files[0]) > 0  # what was read before the expiry
    assert not notes_say_incomplete(files[0])  # the report itself looks complete
    # The console warns, once per listing that failed.
    console = capsys.readouterr().err + "\n".join(logged(caplog))
    assert f"(ExpiredToken); its resources there {EXPIRED_WARNING}" in console
    assert not any("were not scanned" in m for m in logged(caplog))


def test_c4_expired_before_the_first_call_exit_0_and_no_report(
    aws, tmp_path, monkeypatch, caplog
):
    """The session is already expired when the scan starts: exit 0, no report
    file, a warning that the region check failed."""
    caplog.set_level(logging.INFO)
    expiry = Expiry(monkeypatch, allow=0, code="ExpiredTokenException")
    code = run_cli(*BASE, "--account-regions", "us-east-1", "--output-directory", "o")
    assert expiry.raised > 0
    assert code == 0
    assert reports(tmp_path / "o") == []
    assert any("ExpiredTokenException" in m for m in logged(caplog))
    assert any("No resources to report" in m for m in logged(caplog))


def test_c4_one_account_of_two_expires(aws, tmp_path, monkeypatch, caplog, capsys):
    """Account OTHER's session expires after 30 calls; GOOD is fine. Exit 0 even
    with --fail-on-account-error; the report has GOOD and no note."""
    seed_account(OTHER_ID, OTHER["role_arn"])
    caplog.set_level(logging.INFO)
    roles = RoleControl(monkeypatch)
    expiry = Expiry(
        monkeypatch,
        allow=30,
        code="ExpiredTokenException",
        key_of=lambda: roles.keys[OTHER_ID],
    )
    path = accounts_file(tmp_path, [GOOD, OTHER])
    code = run_cli(
        "--accounts-file",
        path,
        *BASE,
        "--fail-on-account-error",
        "--output-directory",
        "out",
    )
    assert expiry.raised > 0
    assert code == 0
    files = reports(tmp_path / "out")
    assert len(files) == 1
    cells = {str(c) for rows in workbook(files[0]).values() for r in rows for c in r}
    assert GOOD_ID in cells
    assert not notes_say_incomplete(files[0])
    assert not any("were not scanned" in m for m in logged(caplog))
    console = capsys.readouterr().err + "\n".join(logged(caplog))
    assert f"(ExpiredTokenException); its resources there {EXPIRED_WARNING}" in console


def test_c4_resume_reuses_a_partly_read_account_as_if_complete(
    aws, tmp_path, monkeypatch, caplog
):
    """Side effect of the expiry behaviour: GOOD expires part-way (exit 0, no
    failure), OTHER fails to assume its role. The run saves GOOD as finished and
    --resume then reuses that partial result without a scan."""
    seed_account(OTHER_ID, OTHER["role_arn"])
    caplog.set_level(logging.INFO)
    roles = RoleControl(monkeypatch, failing={OTHER_ID})
    Expiry(monkeypatch, allow=20, key_of=lambda: "AKIAIOSFODNN7EXAMPLE")
    path = accounts_file(tmp_path, [GOOD, OTHER])
    assert run_cli("--accounts-file", path, *BASE, "--output-directory", "out") == 0
    roles.failing.clear()
    scanned = scan_spy(monkeypatch)
    caplog.clear()
    args = ["--accounts-file", path, *BASE, "--resume", "--output-directory", "out"]
    assert run_cli(*args) == 0
    assert scanned == [OTHER_ID]
    assert any("reusing results" in m and GOOD_ID in m for m in logged(caplog))


# ============================================================== C5: --resume
def scan_spy(monkeypatch):
    """List of the account IDs that discovery really scans."""
    scanned = []
    original = cbg.CloudBOMGenerator._discover_account_resources_inner

    def spy(self, account_id, context):
        scanned.append(str(account_id))
        return original(self, account_id, context)

    monkeypatch.setattr(cbg.CloudBOMGenerator, "_discover_account_resources_inner", spy)
    return scanned


def test_c5_resume_scans_only_the_failed_account(aws, tmp_path, monkeypatch, caplog):
    seed_account(OTHER_ID, OTHER["role_arn"])
    caplog.set_level(logging.INFO)
    roles = RoleControl(monkeypatch, failing={OTHER_ID})
    path = accounts_file(tmp_path, [GOOD, OTHER])
    args = ["--accounts-file", path, *BASE, "--output-directory", "out"]

    # Run 1: OTHER fails; GOOD is saved under <output>/state/partial/.
    assert run_cli(*args) == 0
    first = reports(tmp_path / "out")
    assert len(first) == 1
    first_total = total_resources(first[0])
    assert list((tmp_path / "out" / "state" / "partial").iterdir())
    assert any("Run the same command with --resume" in m for m in logged(caplog))

    # Run 2: the cause is fixed; --resume scans only OTHER.
    roles.failing.clear()
    scanned = scan_spy(monkeypatch)
    caplog.clear()
    assert run_cli(*args, "--resume") == 0
    assert scanned == [OTHER_ID]
    assert any(f"{GOOD_ID}: reusing results scanned" in m for m in logged(caplog))
    second = [p for p in reports(tmp_path / "out") if p not in first]
    assert len(second) == 1
    text = workbook_text(second[0])
    assert total_resources(second[0]) > first_total  # OTHER's resources are in
    assert f"acct-{OTHER_ID}-b0" in text
    # The notes list the reused account with its scan time.
    assert "(--resume)" in text and f"{GOOD_ID}:" in text
    # The saved results are deleted after a run in which every account finishes.
    partial = tmp_path / "out" / "state" / "partial"
    assert not partial.exists() or not list(partial.iterdir())


# ============================================ C6: order of the opt-in codes
def test_c6_5_before_4(aws, tmp_path, monkeypatch, caplog):
    """An account fails and a security group rule reaches the threshold: the
    estate has a rule open to 0.0.0.0/0 on port 22. Exit code 5, not 4; the
    risk finding is still logged."""
    RoleControl(monkeypatch, failing={OTHER_ID})
    caplog.set_level(logging.INFO)
    path = accounts_file(tmp_path, [GOOD, OTHER])
    code = run_cli(
        "--accounts-file",
        path,
        *BASE,
        "--enable-security-analysis",
        "--risk-threshold",
        "LOW",
        "--fail-on-account-error",
        "--output-directory",
        "both",
    )
    assert code == 5
    assert any("at or above risk level LOW" in m for m in logged(caplog))
    assert reports(tmp_path / "both")  # reports are written in all cases
    # Without the account flag the same run exits 4: the finding is real.
    code = run_cli(
        "--accounts-file",
        path,
        *BASE,
        "--enable-security-analysis",
        "--risk-threshold",
        "LOW",
        "--output-directory",
        "risk_only",
    )
    assert code == 4


def test_c6_5_before_6(aws, monkeypatch, tmp_path):
    """An account fails and the other finds nothing: both conditions hold. Exit
    code 5; with only --fail-if-empty the same run exits 6."""
    RoleControl(monkeypatch, failing={OTHER_ID})
    monkeypatch.setattr(
        cbg.CloudBOMGenerator,
        "_discover_account_resources_inner",
        lambda self, account_id, context: [],
    )
    path = accounts_file(tmp_path, [GOOD, OTHER])
    common = ["--accounts-file", path, *BASE, "--output-directory", "out"]
    assert run_cli(*common, "--fail-on-account-error", "--fail-if-empty") == 5
    assert run_cli(*common, "--fail-if-empty") == 6
    assert run_cli(*common, "--fail-on-account-error") == 5
    assert run_cli(*common) == 0


def test_c6_opt_in_exit_code_function_ranks_5_6_over_everything():
    from types import SimpleNamespace

    log = logging.getLogger("test")
    args = SimpleNamespace(fail_on_account_error=True, fail_if_empty=True)
    both = {
        "success": True,
        "failed_accounts": [{"account_id": "1"}],
        "bom_generation": {"total_resources": 0},
    }
    assert cli_main._opt_in_exit_code(args, both, log) == 5
    no_failure = {"success": True, "bom_generation": {"total_resources": 0}}
    assert cli_main._opt_in_exit_code(args, no_failure, log) == 6


def test_c6_5_before_3_and_3_before_4(aws, tmp_path, monkeypatch, caplog):
    """ci-pipeline sets fail_on_tag_violations (exit 3); the estate has resources
    without the required tags, and an open security group rule (risk, exit 4).
    With a failed account and the flag: 5. Without the flag: 3, not 4."""
    RoleControl(monkeypatch, failing={OTHER_ID})
    caplog.set_level(logging.INFO)
    path = accounts_file(tmp_path, [GOOD, OTHER])
    common = [
        "--accounts-file",
        path,
        "--no-billing-validation",
        "--template",
        "ci-pipeline",
        "--enable-security-analysis",
        "--risk-threshold",
        "LOW",
    ]
    code = run_cli(*common, "--fail-on-account-error", "--output-directory", "a")
    assert code == 5
    assert reports(tmp_path / "a")  # reports are written in all cases
    code = run_cli(*common, "--output-directory", "b")
    assert code == 3
