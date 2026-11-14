"""An account that read nothing must not become the baseline (A-01).

When every service-API listing of an account is denied (or fails), v1.2.0
saved a snapshot with the account marked as scanned and with only the rows
the Tagging API returned (or none). The next change report then listed every
other resource of the account as removed, and the run after it as added.

Now such an account goes into the snapshot's existing ``accounts_failed``
list (left out of the comparison), the report's Run notes name it, and a run
in which nothing at all was read saves no snapshot. Exit codes and the
``failed_accounts`` of the result (which drives exit code 5) are unchanged.
"""

import json
import logging

import botocore.client
from botocore.exceptions import ClientError

from inventag.state import StateManager
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    aws,
    cbg,
    empty_aws,
    logged,
    reports,
    run_cli,
    workbook,
)

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]

# The snapshot format of v1.2.0 (schema 1.1). No key may be added.
V120_TOP_KEYS = {
    "metadata",
    "resources",
    "compliance_data",
    "network_analysis",
    "security_analysis",
}
V120_METADATA_KEYS = {
    "timestamp",
    "version",
    "account_id",
    "regions",
    "resource_count",
    "checksum",
    "discovery_method",
    "compliance_status",
    "tags",
    "accounts_scanned",
    "accounts_failed",
}
V120_TAG_KEYS = {
    "multi_account",
    "total_accounts",
    "generation_type",
    "reused_accounts",
    "coverage_summary",
}


class DenyEverything:
    """While ``on``: every AWS call is AccessDenied except STS, EC2
    DescribeRegions (the region check) and, if ``allow_tagging``, the
    Resource Groups Tagging API."""

    def __init__(self, monkeypatch, allow_tagging=True):
        self.on = False
        self.allow_tagging = allow_tagging
        self.raised = 0
        original = botocore.client.BaseClient._make_api_call
        deny = self

        def call(client, operation_name, api_params):
            service = client.meta.service_model.service_name
            allowed = (
                not deny.on
                or service == "sts"
                or (service == "ec2" and operation_name == "DescribeRegions")
                or (deny.allow_tagging and service == "resourcegroupstaggingapi")
            )
            if allowed:
                return original(client, operation_name, api_params)
            deny.raised += 1
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "not allowed"}},
                operation_name,
            )

        monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)


def result_spy(monkeypatch):
    """The result dicts of ``generate_multi_account_bom``, one per run."""
    results = []
    original = cbg.CloudBOMGenerator.generate_multi_account_bom

    def spy(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(cbg.CloudBOMGenerator, "generate_multi_account_bom", spy)
    return results


def changes(result):
    """(added, removed) of the run's change report; (0, 0) if none was made."""
    delta = (result.get("state_management") or {}).get("delta_detection") or {}
    summary = getattr(delta.get("summary"), "summary", None) or {}
    return (
        int(summary.get("added_count", 0) or 0),
        int(summary.get("removed_count", 0) or 0),
    )


def snapshot_files(tmp_path):
    return sorted((tmp_path / "out" / "state").glob("state_*.json"))


def run_notes(path):
    """The lines under "Run notes" in the Summary sheet."""
    rows = [r[0] for r in workbook(path)["Summary"] if r and r[0] is not None]
    if "Run notes" not in rows:
        return []
    return [str(r) for r in rows[rows.index("Run notes") + 1 :]]


def test_an_all_denied_run_does_not_poison_the_next_change_report(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """Good run, all-denied run (Tagging API allowed), good run: neither the
    second nor the third run reports anything added or removed."""
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    deny = DenyEverything(monkeypatch, allow_tagging=True)

    assert run_cli(*ARGS) == 0
    assert len(snapshot_files(tmp_path)) == 1

    deny.on = True
    caplog.clear()
    before = set(reports(tmp_path / "out"))
    assert run_cli(*ARGS) == 0  # exit code as in v1.2.0
    assert deny.raised > 0
    second = results[-1]
    assert second["success"] is True
    assert second["failed_accounts"] == []  # unchanged: drives exit code 5
    assert changes(second) == (0, 0)

    # The account is in the existing accounts_failed list; no new key.
    files = snapshot_files(tmp_path)
    assert len(files) == 2
    data = json.loads(files[-1].read_text())
    assert set(data) == V120_TOP_KEYS
    assert set(data["metadata"]) == V120_METADATA_KEYS
    assert set(data["metadata"]["tags"]) <= V120_TAG_KEYS
    assert data["metadata"]["version"] == "1.1"
    assert data["metadata"]["accounts_failed"] == [GOOD_ID]
    assert data["metadata"]["accounts_scanned"] == []
    state_id = files[-1].stem[len("state_") :]
    loaded = StateManager(state_dir=str(tmp_path / "out" / "state")).load_state(
        state_id
    )
    assert loaded is not None and loaded.metadata.accounts_failed == [GOOD_ID]

    # The report's Run notes name the account; one warning says the same.
    new_reports = [p for p in reports(tmp_path / "out") if p not in before]
    assert len(new_reports) == 1
    notes = run_notes(new_reports[0])
    assert any(
        GOOD_ID in n and "left out of change tracking" in n for n in notes
    ), notes
    warnings = [
        m for m in logged(caplog) if GOOD_ID in m and "left out of change tracking" in m
    ]
    assert len(warnings) == 1, warnings

    deny.on = False
    assert run_cli(*ARGS) == 0
    assert changes(results[-1]) == (0, 0)


def test_a_run_that_read_nothing_saves_no_snapshot(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """Every call denied, the Tagging API too (S1 F3e): no snapshot is
    written, so the next good run compares with the last good one."""
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    deny = DenyEverything(monkeypatch, allow_tagging=False)

    assert run_cli(*ARGS) == 0
    first_snapshots = snapshot_files(tmp_path)
    assert len(first_snapshots) == 1

    deny.on = True
    assert run_cli(*ARGS) == 0  # exit code as in v1.2.0
    assert results[-1]["failed_accounts"] == []
    assert snapshot_files(tmp_path) == first_snapshots
    assert changes(results[-1]) == (0, 0)

    deny.on = False
    assert run_cli(*ARGS) == 0
    assert changes(results[-1]) == (0, 0)


def test_a_good_run_still_saves_a_complete_snapshot(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """Guard: a normal run lists the account under accounts_scanned."""
    assert run_cli(*ARGS) == 0
    data = json.loads(snapshot_files(tmp_path)[-1].read_text())
    assert data["metadata"]["accounts_scanned"] == [GOOD_ID]
    assert not data["metadata"]["accounts_failed"]
