"""Run the CLI against the FinOps moto estate and keep what the run produced."""

import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from moto import mock_aws
from openpyxl import load_workbook

from tests.e2e.conftest import restored_process_state
from tests.unit.finops import estate

SERVICES = "ec2,vpc,elb,elbv2"


@dataclass
class Scan:
    code: int
    stdout: str
    stderr: str
    out: Path
    ids: Dict[str, str]
    rows: List[Dict[str, Any]] = field(default_factory=list)
    results: Optional[Dict[str, Any]] = None
    audit: Optional[Dict[str, Any]] = None

    @property
    def text(self) -> str:
        return self.stdout + self.stderr

    def workbook(self) -> Path:
        files = sorted(self.out.glob("*.xlsx"))
        assert len(files) == 1, files
        return files[0]

    def sheet_names(self) -> List[str]:
        wb = load_workbook(self.workbook(), read_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()

    def sheet(self, name: str) -> List[tuple]:
        wb = load_workbook(self.workbook(), read_only=True)
        try:
            return [tuple(r) for r in wb[name].iter_rows(values_only=True)]
        finally:
            wb.close()

    def json_report(self) -> Dict[str, Any]:
        files = sorted(self.out.glob("*.json"))
        assert len(files) == 1, files
        return json.loads(files[0].read_text())


def _run_main(out: Path, audit: Path, extra, json_report: bool, ids):
    """One in-process CLI run in the moto estate that is open now."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from inventag.cli.main import main
    from inventag.core import cloud_bom_generator as cbg

    argv = [
        "inventag",
        "--account-regions",
        "us-east-1",
        "--no-billing-validation",
        "--account-services",
        SERVICES,
        "--output-directory",
        str(out),
        "--audit-output",
        str(audit),
        *extra,
    ]
    captured: Dict[str, Any] = {}
    original_consolidate = cbg.CloudBOMGenerator._consolidate_account_resources
    original_generate = cbg.CloudBOMGenerator.generate_comprehensive_bom

    def consolidate(self, rows):
        found = original_consolidate(self, rows)
        captured["rows"] = copy.deepcopy(found)
        return found

    def generate(self, output_formats=None, **kwargs):
        if json_report:
            output_formats = list(output_formats or []) + ["json"]
        captured["results"] = original_generate(
            self, output_formats=output_formats, **kwargs
        )
        return captured["results"]

    code = 0
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cbg.CloudBOMGenerator, "_consolidate_account_resources", consolidate)
        mp.setattr(cbg.CloudBOMGenerator, "generate_comprehensive_bom", generate)
        mp.setattr(sys, "argv", argv)
        with (
            restored_process_state(),
            redirect_stdout(buf_out),
            redirect_stderr(buf_err),
        ):
            try:
                main()
            except SystemExit as exc:
                code = 0 if exc.code is None else exc.code
    return Scan(
        code=code,
        stdout=buf_out.getvalue(),
        stderr=buf_err.getvalue(),
        out=out,
        ids=ids,
        rows=captured.get("rows", []),
        results=captured.get("results"),
        audit=json.loads(audit.read_text()) if audit.exists() else None,
    )


def run_scans(tmp_path: Path, *runs, json_report: bool = False) -> List[Scan]:
    """Seed the estate once, then run the CLI once per argument list."""
    scans = []
    with mock_aws():
        ids = estate.seed()
        for number, extra in enumerate(runs):
            where = tmp_path / f"run{number}"
            where.mkdir(parents=True, exist_ok=True)
            scans.append(
                _run_main(where / "out", where / "audit.json", extra, json_report, ids)
            )
    return scans


def run_scan(tmp_path: Path, *extra: str, json_report: bool = False) -> Scan:
    """One CLI run in a new moto estate."""
    return run_scans(tmp_path, list(extra), json_report=json_report)[0]


@pytest.fixture(scope="module")
def scan_pair(tmp_path_factory):
    """The same estate scanned with --finops-checks and without it."""
    return run_scans(
        tmp_path_factory.mktemp("pair"), ["--finops-checks"], [], json_report=True
    )


@pytest.fixture(scope="module")
def finops_scan(scan_pair):
    return scan_pair[0]


@pytest.fixture(scope="module")
def plain_scan(scan_pair):
    return scan_pair[1]
