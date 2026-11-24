"""`--finops-cost-allocation` through the CLI, in moto, with Cost Explorer
answered by a botocore Stubber (moto has no ListCostAllocationTags).

The Stubber sits on the run's own client (created through
``create_client``), so the read-only guard and the limiter see every request.
"""

import datetime as dt
import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest
from moto import mock_aws

from inventag.finops import cost_allocation as ca
from tests.unit.finops import cost_stubs as cs
from tests.unit.finops import estate
from tests.unit.finops.conftest import _run_main

pytestmark = pytest.mark.e2e

SHEET_COLUMNS = (
    "Account",
    "Grouping",
    "Value",
    "Amount",
    "Currency",
    "Metric",
    "Period start",
    "Period end",
    "Status",
)


def _period_of_today():
    start, end = ca.last_full_month(dt.datetime.now(dt.timezone.utc))
    return {"Start": start, "End": end}


@pytest.fixture
def stubbed_ce(monkeypatch):
    """Every Cost Explorer client of the feature answers from a Stubber."""
    made = []
    original = ca.create_client

    def create(session, service, region=None):
        client = original(session, service, region)
        stub = cs.full_stub(
            client,
            active=("CostCenter", "Owner"),
            inactive=("Project",),
            period=_period_of_today(),
        )
        cs.activate_after_the_guard(stub)
        made.append({"session": session, "region": region, "stub": stub})
        return client

    monkeypatch.setattr(ca, "create_client", create)
    return made


def scan(tmp_path, *extra, out=None, json_report=False):
    with mock_aws():
        ids = estate.seed()
        return _run_main(
            out or tmp_path / "out",
            tmp_path / "audit.json",
            list(extra),
            json_report,
            ids,
        )


def scans_in_one_folder(tmp_path, *runs):
    """Several runs into one output folder (for the change report)."""
    out = tmp_path / "out"
    found = []
    with mock_aws():
        ids = estate.seed()
        for n, extra in enumerate(runs):
            found.append(
                _run_main(out, tmp_path / f"audit{n}.json", list(extra), False, ids)
            )
    return found


def ce_ops(audit):
    return {
        (op["operation"], op["allowed"]): op["count"]
        for op in audit["operations"]
        if op["service"] == "ce"
    }


def snapshot(out):
    files = sorted((out / "state").glob("state_*.json"))
    return files[-1], json.loads(files[-1].read_text())


def changelogs(out):
    return sorted(out.glob("changelog_*.md"))


# ------------------------------------------------------------ the flag
def test_help_names_both_flags():
    from inventag.cli.main import create_parser

    text = " ".join(create_parser().format_help().split())
    assert "--finops-cost-allocation" in text
    assert "--no-cost-in-snapshot" in text
    assert "at most 7 Cost Explorer requests per account" in text
    parsed = create_parser().parse_args([])
    assert parsed.finops_cost_allocation is False
    assert parsed.cost_in_snapshot is True


# ------------------------------------------------------------ with the flag
def test_a_run_with_the_flag_adds_the_sheet_and_the_key(tmp_path, stubbed_ce):
    s = scan(tmp_path, "--finops-cost-allocation", json_report=True)
    assert s.code == 0, s.text
    names = s.sheet_names()
    assert names[-1] == "FinOps costs"
    rows = s.sheet("FinOps costs")
    assert rows[3][: len(SHEET_COLUMNS)] == SHEET_COLUMNS
    costs = s.results["finops_costs"]
    assert costs["schema_version"] == 1 and costs["metric"] == "UnblendedCost"
    (account,) = costs["accounts"]
    assert account["account"] == "123456789012"
    assert account["requests"] == 5  # list, SERVICE, LINKED_ACCOUNT, 2 active keys
    assert s.json_report()["metadata"]["finops_costs"] == costs
    for entry in stubbed_ce:
        entry["stub"].assert_no_pending_responses()


def test_one_warning_line_says_the_most_requests_first(tmp_path, stubbed_ce):
    s = scan(tmp_path, "--finops-cost-allocation")
    lines = [l for l in s.text.splitlines() if "Cost Explorer: up to" in l]
    assert len(lines) == 1, lines
    assert " - WARNING - " in lines[0]
    assert (
        "Cost Explorer: up to 7 request(s) in this run (billing validation: 0; "
        "cost trend: 0; cost allocation: 7). AWS charges for each." in lines[0]
    )


def test_the_guard_counts_no_more_requests_than_announced(tmp_path, stubbed_ce):
    s = scan(tmp_path, "--finops-cost-allocation")
    counted = ce_ops(s.audit)
    assert counted == {
        ("GetCostAndUsage", True): 4,
        ("ListCostAllocationTags", True): 1,
    }
    assert sum(counted.values()) <= ca.planned_requests(1)
    assert s.audit["blocked_calls"] == 0


def test_the_guard_allows_list_cost_allocation_tags():
    from inventag.security.read_only_guard import ReadOnlyGuard

    assert ReadOnlyGuard().evaluate("ce", "ListCostAllocationTags")[0] is True


def test_snapshot_holds_totals_only_and_stays_owner_only(tmp_path, stubbed_ce):
    s = scan(tmp_path, "--finops-cost-allocation")
    path, data = snapshot(s.out)
    totals = data["metadata"]["tags"]["cost_allocation"]
    assert totals == ca.snapshot_totals(s.results["finops_costs"])
    text = json.dumps(totals)
    for resource in s.ids.values():
        assert resource not in text
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("umask", [0o022, 0o077])
def test_snapshot_is_0600_under_either_umask(tmp_path, stubbed_ce, umask):
    previous = os.umask(umask)
    try:
        s = scan(tmp_path, "--finops-cost-allocation")
    finally:
        os.umask(previous)
    path, data = snapshot(s.out)
    assert "cost_allocation" in data["metadata"]["tags"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_no_cost_in_snapshot_keeps_the_sheet_and_leaves_the_snapshot_without_it(
    tmp_path, stubbed_ce
):
    s = scan(tmp_path, "--finops-cost-allocation", "--no-cost-in-snapshot")
    assert s.code == 0, s.text
    assert s.sheet_names()[-1] == "FinOps costs"
    _, data = snapshot(s.out)
    assert "cost_allocation" not in data["metadata"]["tags"]
    assert "UnblendedCost" not in json.dumps(data)


def test_no_cost_in_snapshot_without_the_flag_warns_and_changes_nothing(tmp_path):
    s = scan(tmp_path, "--no-cost-in-snapshot")
    assert s.code == 0, s.text
    assert (
        "--no-cost-in-snapshot has no effect without --finops-cost-allocation" in s.text
    )
    assert "FinOps costs" not in s.sheet_names()


def test_with_template_the_flag_warns_and_makes_no_request(tmp_path, stubbed_ce):
    s = scan(tmp_path, "--finops-cost-allocation", "--template", "standard-bom")
    assert s.code == 0, s.text
    assert "--finops-cost-allocation: with --template" in s.text
    assert stubbed_ce == []
    assert "finops_costs" not in s.results


def test_a_denied_request_is_a_note_and_a_permissions_line_and_exits_0(
    tmp_path, monkeypatch
):
    from botocore.stub import Stubber

    original = ca.create_client

    def create(session, service, region=None):
        client = original(session, service, region)
        stub = Stubber(client)
        stub.add_client_error(
            "list_cost_allocation_tags", "AccessDeniedException", http_status_code=400
        )
        for _ in range(6):
            stub.add_client_error(
                "get_cost_and_usage", "AccessDeniedException", http_status_code=400
            )
        cs.activate_after_the_guard(stub)
        return client

    monkeypatch.setattr(ca, "create_client", create)
    s = scan(tmp_path, "--finops-cost-allocation")
    assert s.code == 0, s.text
    assert (
        "Cost allocation in account 123456789012: Service (not read: access denied)"
        in s.text
    )
    perms = [l for l in s.text.splitlines() if "Permissions:" in l]
    assert perms and "ce:ListCostAllocationTags" in perms[0]
    assert "ce:GetCostAndUsage" in perms[0]
    assert "cost allocation figures are missing" in perms[0]
    assert s.sheet_names()[-1] == "FinOps costs"


# ------------------------------------------------------------ change report
def test_change_report_block_needs_both_snapshots(tmp_path, stubbed_ce):
    first, second = scans_in_one_folder(tmp_path, [], ["--finops-cost-allocation"])
    assert first.code == second.code == 0
    (log,) = changelogs(second.out)
    text = log.read_text()
    assert "## Cost, previous run to this run" in text
    assert (
        "Not compared: the previous snapshot holds no cost allocation figures." in text
    )


def test_change_report_says_same_month_when_both_runs_read_one_month(
    tmp_path, stubbed_ce
):
    runs = scans_in_one_folder(
        tmp_path, ["--finops-cost-allocation"], ["--finops-cost-allocation"]
    )
    assert [r.code for r in runs] == [0, 0]
    text = changelogs(runs[1].out)[-1].read_text()
    assert "Account 123456789012: not compared, both runs read the same month" in text


def test_change_lines_compare_two_months():
    def costs(start, end, amount):
        return {
            "metric": "UnblendedCost",
            "accounts": [
                {
                    "account": "1",
                    "period": {"start": start, "end": end},
                    "tables": {
                        "service": {
                            "status": "read",
                            "currency": "USD",
                            "rows": [
                                {"name": "AmazonS3", "amount": amount, "unit": "USD"}
                            ],
                        }
                    },
                }
            ],
        }

    lines = ca.change_lines(
        costs("2026-09-01", "2026-10-01", "1.5"),
        costs("2026-10-01", "2026-11-01", "2.25"),
    )
    assert lines == [
        "## Cost, previous run to this run",
        "",
        "Account 1, UnblendedCost: 2026-09-01 to 2026-10-01 (previous run), "
        "2026-10-01 to 2026-11-01 (this run).",
        "",
        "| Grouping | Value | Previous run | This run | Currency |",
        "|---|---|---|---|---|",
        "| Service | AmazonS3 | 1.5 | 2.25 | USD |",
        "",
    ]
    assert ca.change_lines(None, None) == []
    assert ca.change_lines(None, None, opted_out=True)[2].startswith("Not compared")


def test_without_the_flag_the_change_report_has_no_cost_block(tmp_path):
    runs = scans_in_one_folder(tmp_path, [], [])
    text = changelogs(runs[1].out)[-1].read_text()
    assert "Cost, previous run" not in text


# ------------------------------------------------------------ without it
def test_without_the_flag_nothing_is_read_and_nothing_is_added(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("cost allocation ran without the flag")

    monkeypatch.setattr(ca, "read_for_session", refuse)
    monkeypatch.setattr(ca, "read_account", refuse)
    s = scan(tmp_path, json_report=True)
    assert s.code == 0, s.text
    assert "FinOps costs" not in s.sheet_names()
    assert "finops_costs" not in s.results
    assert "finops_costs" not in s.json_report()["metadata"]
    _, data = snapshot(s.out)
    assert "cost_allocation" not in data["metadata"]["tags"]
    assert ("ListCostAllocationTags", True) not in ce_ops(s.audit)
    assert "cost allocation" not in s.text.lower()


def console(s):
    text = s.stdout + "\n---\n" + s.stderr
    text = text.replace(str(s.out.parent), "<run>")
    text = re.sub(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+", "<time>", text)
    text = re.sub(r"_\d{8}_\d{6}\.", "_<stamp>.", text)
    text = re.sub(r"🔍 [^\n]*?[⣾⣽⣻⢿⡿⣟⣯⣷] *", "", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def test_no_cost_in_snapshot_alone_is_the_only_new_line_without_the_flag(tmp_path):
    # A run without either flag and a run with only the opt-out differ by the
    # opt-out's warning line only.
    with mock_aws():
        ids = estate.seed()
        plain = _run_main(tmp_path / "a" / "out", tmp_path / "a.json", [], False, ids)
        opt = _run_main(
            tmp_path / "b" / "out",
            tmp_path / "b.json",
            ["--no-cost-in-snapshot"],
            False,
            ids,
        )
    extra = [
        l for l in console(opt).splitlines() if l not in console(plain).splitlines()
    ]
    assert len(extra) == 1 and "--no-cost-in-snapshot has no effect" in extra[0]


# ------------------------------------------------------------ several accounts
def test_each_account_is_read_with_its_own_session(monkeypatch):
    from types import SimpleNamespace

    from inventag.core import cloud_bom_generator as cbg

    seen = []

    def fake_read(session, account_id, regions, run_started):
        seen.append((session, account_id, tuple(regions)))
        return {
            "account": account_id,
            "period": {"start": "2026-10-01", "end": "2026-11-01"},
            "metric": "UnblendedCost",
            "requests": 3,
            "tag_keys": [],
            "tables": {},
            "failed": [],
        }

    monkeypatch.setattr(ca, "read_for_session", fake_read)
    generator = cbg.CloudBOMGenerator.__new__(cbg.CloudBOMGenerator)
    generator.config = cbg.MultiAccountConfig(finops_cost_allocation=True)
    generator.logger = __import__("logging").getLogger("test")
    generator._processing_stats = {
        "processing_start_time": dt.datetime(2026, 11, 24, tzinfo=dt.timezone.utc)
    }
    sessions = {"222222222222": object(), "111111111111": object()}
    generator.account_contexts = {
        acc: SimpleNamespace(session=sess, accessible_regions=["eu-west-1"])
        for acc, sess in sessions.items()
    }
    generator._failed_accounts = lambda: []
    costs = generator._read_cost_allocation()
    assert [(a, r) for _, a, r in seen] == [
        ("111111111111", ("eu-west-1",)),
        ("222222222222", ("eu-west-1",)),
    ]
    for session, account, _ in seen:
        assert session is sessions[account]
    assert [a["account"] for a in costs["accounts"]] == ["111111111111", "222222222222"]


def test_per_account_reports_hold_only_their_account():
    from inventag.core import cloud_bom_generator as cbg
    from inventag.reporting.bom_processor import BOMData

    costs = ca.result(
        [
            {
                "account": a,
                "period": {},
                "metric": "UnblendedCost",
                "requests": 0,
                "tag_keys": [],
                "tables": {},
                "failed": [],
            }
            for a in ("111111111111", "222222222222")
        ]
    )
    generator = cbg.CloudBOMGenerator.__new__(cbg.CloudBOMGenerator)
    generator.config = cbg.MultiAccountConfig(generate_per_account_reports=True)
    generator._finops_costs = costs
    rows = [
        {"source_account_id": "111111111111", "resource_id": "a"},
        {"source_account_id": "222222222222", "resource_id": "b"},
    ]
    data = BOMData(resources=rows, generation_metadata={"finops_costs": costs})
    for _, label, scope in generator._report_scopes(data):
        mine = scope.generation_metadata["finops_costs"]["accounts"]
        assert [a["account"] for a in mine] == [label]


def test_multi_account_config_keeps_the_v142_positional_order():
    import dataclasses

    from inventag.core.cloud_bom_generator import MultiAccountConfig

    names = [f.name for f in dataclasses.fields(MultiAccountConfig)]
    assert names[-3:] == ["finops_checks", "finops_cost_allocation", "cost_in_snapshot"]
