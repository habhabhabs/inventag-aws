"""All built-in templates: load, validate and run offline against moto."""

import glob
import json
import os

import pytest

from inventag.templating import cli as templates_cli
from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
from inventag.templating.runner import load_templates

from tests.integration.templating.test_report_templates import (  # noqa: F401
    aws,
    run_inventag,
)

ALL = {
    "standard-bom": "report",
    "executive-summary": "report",
    "finops-cost-report": "report",
    "finops-cost-allocation": "tag-policy",
    "security-baseline": "tag-policy",
    "evidence-soc2": "tag-policy",
    "evidence-hipaa": "tag-policy",
    "evidence-pci-dss": "tag-policy",
    "evidence-gdpr": "tag-policy",
    "evidence-pdpa": "tag-policy",
    "ci-pipeline": "config",
    "single-account": "config",
    "org-multi-account": "config",
}


def test_every_builtin_file_is_covered():
    on_disk = {p.stem for p in BUILTIN_DIR.glob("*.yaml")}
    assert on_disk == set(ALL)


@pytest.mark.parametrize("name,kind", sorted(ALL.items()))
def test_builtin_loads_and_validates(name, kind, capsys):
    registry = TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])
    resolved = registry.resolve(name)
    assert resolved.kind == kind and resolved.name == name
    load_templates([name], registry)
    assert templates_cli.main(["validate", name]) == 0
    assert capsys.readouterr().out.startswith(("OK", "WARNING"))


# name -> (exit code, report files, tag compliance JSON written)
RUNS = {
    "standard-bom": (0, ("xlsx",), False),
    "executive-summary": (0, ("xlsx",), False),
    "finops-cost-report": (0, ("xlsx",), True),
    "finops-cost-allocation": (0, ("xlsx",), True),
    "security-baseline": (0, ("xlsx",), True),
    "evidence-soc2": (0, ("xlsx",), True),
    "evidence-hipaa": (0, ("xlsx",), True),
    "evidence-pci-dss": (0, ("xlsx",), True),
    "evidence-gdpr": (0, ("xlsx",), True),
    "evidence-pdpa": (0, ("xlsx",), True),
    "ci-pipeline": (3, ("xlsx",), True),
    "single-account": (0, ("xlsx", "docx"), False),
    "org-multi-account": (0, ("xlsx", "docx"), True),
}


def test_run_table_covers_every_template():
    assert set(RUNS) == set(ALL)


@pytest.mark.parametrize("name", sorted(RUNS))
def test_builtin_runs_against_moto(aws, monkeypatch, tmp_path, name):  # noqa: F811
    code, formats, has_json = RUNS[name]
    argv = ["--template", name, "--account-regions", "us-east-1"]
    if ALL[name] != "config":
        argv += ["--create-excel"]
    assert run_inventag(monkeypatch, tmp_path, *argv) == code
    out = tmp_path / "bom_output"
    for ext in ("xlsx", "docx"):
        found = glob.glob(str(out / f"multi_account_bom_*.{ext}"))
        assert bool(found) == (ext in formats), (name, ext)
    found = glob.glob(str(out / "tag_compliance_*.json"))
    assert bool(found) == has_json
    if found:
        assert json.load(open(found[0]))["summary"]["checked"] >= 2
