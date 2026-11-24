"""`--finops-checks` through the CLI: opt-in, additive, no AWS call, no exit code."""

import json
import re
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from inventag.cli.main import create_parser
from inventag.finops import checks
from tests.unit.finops.conftest import run_scan, run_scans

pytestmark = pytest.mark.e2e

REPO = Path(__file__).resolve().parents[3]

SCHEMA = {
    "type": "object",
    "required": ["schema_version", "summary", "findings"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"const": 1},
        "summary": {
            "type": "array",
            "minItems": 6,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["policy", "check", "fail", "not_evaluated", "pass"],
                "properties": {
                    "policy": {"type": "string", "pattern": "^FIN-00[1-6]$"},
                    "check": {"type": "string"},
                    "fail": {"type": "integer", "minimum": 0},
                    "not_evaluated": {"type": "integer", "minimum": 0},
                    "pass": {"type": "integer", "minimum": 0},
                },
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "policy",
                    "result",
                    "reason",
                    "account",
                    "region",
                    "service",
                    "resource_type",
                    "resource",
                    "name",
                    "message",
                ],
                "properties": {
                    "policy": {"type": "string", "pattern": "^FIN-00[1-6]$"},
                    "result": {"enum": ["fail", "not_evaluated"]},
                    "reason": {
                        "enum": [
                            "",
                            "identity_only",
                            "field_missing",
                            "tags_not_read",
                            "listing_not_read",
                        ]
                    },
                    "account": {"type": "string"},
                    "region": {"type": "string"},
                    "service": {"type": "string"},
                    "resource_type": {"type": "string"},
                    "resource": {"type": "string"},
                    "name": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
    },
}


def sheet_cells(scan):
    return scan.sheet("FinOps")


# ------------------------------------------------------------ the flag
def test_help_names_the_flag_and_says_it_makes_no_aws_call():
    text = " ".join(create_parser().format_help().split())
    assert "--finops-checks" in text
    assert "no further AWS call" in text
    assert "their findings do not change the exit code" in text
    assert "permission and do not change the exit code" not in text


def test_the_flag_is_off_by_default():
    args = create_parser().parse_args([])
    assert args.finops_checks is False


# ------------------------------------------------------------ with the flag
def test_with_the_flag_the_workbook_ends_with_the_finops_sheet(finops_scan):
    assert finops_scan.code == 0, finops_scan.text
    names = finops_scan.sheet_names()
    assert names[-1] == "FinOps"
    assert names.count("FinOps") == 1


def test_the_result_key_matches_the_schema(finops_scan):
    jsonschema.validate(finops_scan.results["finops_checks"], SCHEMA)


def test_the_json_report_metadata_has_the_same_key(finops_scan):
    report = finops_scan.json_report()
    assert report["metadata"]["finops_checks"] == finops_scan.results["finops_checks"]


def test_the_sheet_rows_are_the_findings(finops_scan):
    rows = sheet_cells(finops_scan)
    header = rows.index(
        tuple(
            [
                "Check ID",
                "Check",
                "Result",
                "Reason",
                "Account",
                "Region",
                "Service",
                "Resource Type",
                "Resource ID",
                "Name",
                "Observed",
            ]
        )
    )
    findings = finops_scan.results["finops_checks"]["findings"]
    body = rows[header + 1 : header + 1 + len(findings)]
    assert [(r[0], r[8], r[10]) for r in body] == [
        (f["policy"], f["resource"] or None, f["message"]) for f in findings
    ]


# ------------------------------------------------------------ without it
def test_without_the_flag_nothing_is_added(plain_scan):
    assert plain_scan.code == 0, plain_scan.text
    assert "FinOps" not in plain_scan.sheet_names()
    assert "finops_checks" not in plain_scan.results
    assert "finops_checks" not in plain_scan.json_report()["metadata"]
    assert "FinOps" not in plain_scan.text
    assert "FIN-00" not in plain_scan.text


def test_without_the_flag_the_checks_never_run(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the FinOps checks ran without --finops-checks")

    monkeypatch.setattr(checks, "run_checks", refuse)
    scan = run_scan(tmp_path)
    assert scan.code == 0, scan.text
    assert "FinOps" not in scan.sheet_names()


def test_the_other_sheets_are_the_same_with_and_without_the_flag(
    finops_scan, plain_scan
):
    names = finops_scan.sheet_names()
    assert names[:-1] == plain_scan.sheet_names()
    volatile = ("discovered_at", "discovery_timestamp", "consolidation_timestamp")
    for name in names[:-1]:
        with_flag, without = finops_scan.sheet(name), plain_scan.sheet(name)
        assert len(with_flag) == len(without), name
        header = with_flag[0]
        keep = [i for i, h in enumerate(header) if h not in volatile]
        if name == "Summary":
            continue  # it holds the generation time
        assert [[r[i] for i in keep] for r in with_flag] == [
            [r[i] for i in keep] for r in without
        ], name


def test_the_guard_sees_the_same_aws_calls_with_and_without_the_flag(
    finops_scan, plain_scan
):
    assert finops_scan.audit["operations"] == plain_scan.audit["operations"]
    assert finops_scan.audit["blocked_calls"] == 0


def test_the_flag_does_not_change_the_exit_code_when_checks_fail(finops_scan):
    fails = [
        f
        for f in finops_scan.results["finops_checks"]["findings"]
        if f["result"] == "fail"
    ]
    assert fails
    assert finops_scan.code == 0


def test_with_template_the_flag_warns_and_adds_nothing(tmp_path):
    scan = run_scan(tmp_path, "--finops-checks", "--template", "standard-bom")
    assert scan.code == 0, scan.text
    assert "--finops-checks: with --template" in scan.text
    assert "FinOps" not in scan.sheet_names()
    assert "finops_checks" not in scan.results


# ------------------------------------------------------- per-account reports
def test_per_account_reports_hold_only_their_account(monkeypatch):
    import datetime as dt

    from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
    from inventag.reporting.bom_processor import BOMData
    from tests.unit.finops.test_checks_rules import unit, volume

    rows = [
        volume("vol-a", account="111111111111"),
        volume("vol-b", account="222222222222"),
    ]
    units = [dict(unit("s3"), account="222222222222")]
    started = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)
    generator = CloudBOMGenerator.__new__(CloudBOMGenerator)
    generator.config = MultiAccountConfig(
        generate_per_account_reports=True, finops_checks=True
    )
    generator._processing_stats = {"processing_start_time": started}
    generator._finops_by_account = {}
    monkeypatch.setattr(generator, "_units_not_read", lambda: units, raising=False)

    whole = generator._run_finops_checks(rows)
    data = BOMData(resources=rows, generation_metadata={"finops_checks": whole})
    scopes = generator._report_scopes(data)

    assert whole == checks.run_checks(rows, units, started)
    assert [label for _, label, _ in scopes] == ["111111111111", "222222222222"]
    for _, label, scope in scopes:
        mine = scope.generation_metadata["finops_checks"]
        assert {f["account"] for f in mine["findings"]} == {label}
        assert mine == checks.run_checks(
            [r for r in rows if r["source_account_id"] == label],
            [u for u in units if u["account"] == label],
            started,
        )
    assert data.generation_metadata["finops_checks"] == whole


# ------------------------------------------------------- determinism
def test_the_same_findings_with_concurrency_1_and_64(tmp_path):
    one, many = run_scans(
        tmp_path,
        ["--finops-checks", "--concurrency", "1"],
        ["--finops-checks", "--concurrency", "64"],
    )
    assert one.code == many.code == 0
    assert one.results["finops_checks"] == many.results["finops_checks"]
    assert one.sheet("FinOps") == many.sheet("FinOps")


SEED_SCRIPT = """
import datetime as dt, hashlib, io, json, sys
from openpyxl import Workbook
from inventag.finops import checks
from inventag.reporting import finops_sheet
rows = json.loads(sys.stdin.read())
started = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)
units = [{"account": "111122223333", "service": s, "region": r,
          "source": "service-api", "outcome": "denied"}
         for s in ("elb", "ec2", "s3") for r in ("eu-west-1", "ap-southeast-1")]
result = checks.run_checks(rows, units, started)
wb = Workbook(); wb.remove(wb["Sheet"]); finops_sheet.add_finops_sheet(wb, result)
cells = [[c for c in r] for r in wb["FinOps"].iter_rows(values_only=True)]
blob = json.dumps(result, sort_keys=False) + json.dumps(cells, default=str)
print(hashlib.sha256(blob.encode()).hexdigest())
"""


def test_byte_equal_output_under_three_hash_seeds(finops_scan):
    rows = json.dumps(finops_scan.rows, default=str)
    digests = set()
    for seed in ("0", "1", "4242"):
        env = {"PYTHONHASHSEED": seed, "PATH": os.environ.get("PATH", "")}
        proc = subprocess.run(
            [sys.executable, "-c", SEED_SCRIPT],
            input=rows,
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=env,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        digests.add(proc.stdout.strip())
    assert len(digests) == 1


def test_the_generator_never_reads_the_clock_for_the_checks(monkeypatch):
    from inventag.core import cloud_bom_generator as cbg
    from tests.unit.finops.test_checks_rules import snapshot

    class NoClock:
        @staticmethod
        def now(*a, **k):
            raise AssertionError("the FinOps checks read the clock")

    generator = cbg.CloudBOMGenerator.__new__(cbg.CloudBOMGenerator)
    generator.config = cbg.MultiAccountConfig(finops_checks=True)
    generator._processing_stats = {"processing_start_time": None}
    generator._finops_by_account = {}
    monkeypatch.setattr(generator, "_units_not_read", lambda: [], raising=False)
    monkeypatch.setattr(cbg, "datetime", NoClock)

    result = generator._run_finops_checks([snapshot("snap-1", "2000-01-01T00:00:00")])

    (finding,) = result["findings"]
    assert (finding["policy"], finding["reason"]) == ("FIN-003", "field_missing")


def console(scan):
    """The run's console text without what changes from run to run: time
    stamps, the run's folder, the report's time stamp, spinner frames and
    blank lines."""
    text = scan.stdout + "\n---\n" + scan.stderr
    text = text.replace(str(scan.out.parent), "<run>")
    text = re.sub(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+", "<time>", text)
    text = re.sub(r"_\d{8}_\d{6}\.", "_<stamp>.", text)
    # Spinner frames and blank lines depend on timing: left out.
    text = re.sub(r"🔍 [^\n]*?[⣾⣽⣻⢿⡿⣟⣯⣷] *", "", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def test_the_flag_adds_no_console_line_to_a_run(finops_scan, plain_scan):
    # The default run's text is the release's text: the flag's code adds no
    # line to it, so with and without the flag the console is the same.
    assert console(finops_scan) == console(plain_scan)
    assert "Data exported to <run>/out/multi_account_bom_<stamp>.xlsx" in console(
        plain_scan
    )


# The fields of MultiAccountConfig in v1.4.1, in order (positional callers).
V141_FIELDS = [
    "accounts",
    "cross_account_role_name",
    "parallel_account_processing",
    "max_concurrent_accounts",
    "concurrency",
    "account_processing_timeout",
    "consolidate_accounts",
    "generate_per_account_reports",
    "enable_state_management",
    "enable_delta_detection",
    "enable_changelog_generation",
    "enable_billing_validation",
    "bom_processing_config",
    "output_directory",
    "credential_validation_timeout",
    "hide_fallback_resources",
    "fallback_display_mode",
    "word_template",
    "excel_template",
    "google_options",
    "resume",
    "resume_max_age_hours",
    "state_retention_days",
    "state_max_snapshots",
]


def test_multi_account_config_keeps_the_v141_positional_order():
    import dataclasses

    from inventag.core.cloud_bom_generator import MultiAccountConfig
    from inventag.reporting import BOMProcessingConfig

    names = [f.name for f in dataclasses.fields(MultiAccountConfig)]
    assert names[: len(V141_FIELDS)] == V141_FIELDS
    assert names[len(V141_FIELDS)] == "finops_checks"  # first field after v1.4.1

    bom = BOMProcessingConfig()
    values = [
        [],
        "Role",
        False,
        2,
        8,
        60,
        True,
        False,
        True,
        True,
        True,
        False,
        bom,
        "out",
        10,
        False,
        "never",
        None,
        None,
        None,
        False,
        1.0,
        7,
        9,
    ]
    config = MultiAccountConfig(*values)
    for name, value in zip(V141_FIELDS, values):
        assert getattr(config, name) == value, name
    assert config.finops_checks is False
