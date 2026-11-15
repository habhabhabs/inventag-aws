"""The cross-track pairs of the second v1.2.x patch, each run with both sides
on the branch (debt register section 9.3).

Each track tested its half alone, with a double or a plain-string stand-in for
the other half. These tests run the real generator (lead A) with the real
discovery (senior D), console (senior C), template runner (senior E),
converter and analyzers (senior F) and uploader (senior G), under moto. The
CLI runs take 5 to 15 s each.
"""

import logging
import re

import botocore.client
import pytest
from botocore.exceptions import ClientError
from openpyxl import load_workbook

from inventag.core import cloud_bom_generator as cbg
from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.state import StateManager
from tests.unit.test_converter_uses_account_session import (  # noqa: F401
    _AccountSession,
    two_accounts,
)
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    accounts_file,
    aws,
    empty_aws,
    reports,
    run_cli,
    workbook_text,
)
from tests.unit.test_slow_cost_explorer_keeps_the_account import (
    FakeClock,
    short_limit,
    slow_cost_explorer,
)
from tests.unit.test_slow_cost_explorer_keeps_the_account import args as ce_args
from tests.unit.test_snapshot_not_poisoned import (
    DenyEverything,
    result_spy,
    run_notes,
)

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
GOOD = {"account_id": GOOD_ID, "regions": ["us-east-1"]}


def console(capsys):
    out = capsys.readouterr()
    return (out.out + out.err).splitlines()


def lines_with(lines, text):
    return [line for line in lines if text in line]


def deny(monkeypatch, *pairs, code="AccessDenied"):
    """Every (service, operation) in ``pairs`` answers ``code``."""
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if (client.meta.service_model.service_name, operation_name) in pairs:
            raise ClientError(
                {"Error": {"Code": code, "Message": "no"}}, operation_name
            )
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)


# ------------------------------------------------- A-58: the account's session
def test_each_per_account_workbook_is_read_with_its_own_accounts_session(
    two_accounts, tmp_path  # noqa: F811
):
    """The generator hands each per-account converter its account's session
    (lead A); the converter's analyzers read with it (senior F). Two stub
    sessions on one moto estate, each showing only its own VPC."""
    ids = {"A": "111111111111", "B": "222222222222"}
    contexts, rows = {}, []
    for name, account_id in ids.items():
        data = two_accounts[name]
        contexts[account_id] = AccountContext(
            credentials=AccountCredentials(account_id=account_id),
            session=data["session"],
            caller_identity={"Account": account_id},
            accessible_regions=["us-east-1"],
        )
        for row in data["rows"]:
            rows.append({**row, "source_account_id": account_id})
    generator = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[],
            output_directory=str(tmp_path),
            enable_state_management=False,
            generate_per_account_reports=True,
        )
    )
    generator.config.bom_processing_config.enable_network_analysis = True
    generator.config.bom_processing_config.enable_security_analysis = True
    generator.account_contexts = contexts
    result = generator._generate_bom_documents(rows, {}, ["excel"])
    assert result["success"] is True, result
    for name, account_id in ids.items():
        other = two_accounts["B" if name == "A" else "A"]
        own = two_accounts[name]
        path = next(tmp_path.glob(f"{account_id}_bom_*.xlsx"))
        book = load_workbook(path)
        network = {r[0] for r in book["Network Analysis"].iter_rows(values_only=True)}
        security = {r[0] for r in book["Security Analysis"].iter_rows(values_only=True)}
        assert own["vpc"] in network and other["vpc"] not in network, network
        assert own["group"] in security and other["group"] not in security
    assert two_accounts["B"]["session"].calls > 0


# --------------------------------------------- A-22: failed detail calls
def test_a_failed_detail_call_is_a_run_note_and_not_a_gap_in_the_change_report(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    """Good run, then a run where S3 GetBucketLocation (a detail call) is
    denied: discovery records it (senior D), the generator names it in the
    run notes (lead A), and the change report compares every bucket as
    before (no "not compared", nothing removed). The clean run has no note."""
    results = result_spy(monkeypatch)
    assert run_cli(*ARGS) == 0
    assert not [n for n in results[-1]["run_notes"] if "Details of" in n]
    deny(monkeypatch, ("s3", "GetBucketLocation"))
    assert run_cli(*ARGS) == 0
    notes = results[-1]["run_notes"]
    detail = [n for n in notes if n.startswith("Details of")]
    assert len(detail) == 1 and "s3 GetBucketLocation" in detail[0], notes
    assert not [n for n in notes if "partial" in n], notes
    report = results[-1]["state_management"]["delta_detection"]["summary"]
    assert "not_compared_count" not in report.summary, report.summary
    assert report.summary["removed_count"] == 0, report.summary


# ----------------------------------------------- A-18: a state problem
def test_an_unsaved_snapshot_is_a_run_note_and_the_console_does_not_say_successful(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    def no_space(self, *args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(StateManager, "save_state", no_space)
    assert run_cli(*ARGS, "--verbose") == 0  # as in v1.2.1 (INFO lines shown)
    lines = console(capsys)
    assert not lines_with(lines, "BOM generation successful"), lines
    assert len(lines_with(lines, "the state snapshot or the change report")) == 1
    assert len(lines_with(lines, "The state snapshot was not saved")) == 1


# ---------------------------------- A-13 with the run notes of the generator
def test_a_failed_template_format_is_named_beside_the_generators_notes(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """Every service listing denied (lead A's note) and the Word renderer
    failing (senior E): the Excel report is written and its run notes carry
    both; the exit code stays 1 for the failed format."""
    from inventag.templating import runner

    def broken_word(*args, **kwargs):
        raise RuntimeError("word renderer broke")

    monkeypatch.setattr(runner, "render_word", broken_word)
    denied = DenyEverything(monkeypatch)
    denied.on = True
    code = run_cli(*ARGS, "--create-word", "--template", "standard-bom")
    assert code == 1
    files = reports(tmp_path / "out")
    assert len(files) == 1 and files[0].suffix == ".xlsx", files
    text = workbook_text(files[0])
    assert f"Every service listing of account {GOOD_ID}" in text
    assert "The Word report was not written (RuntimeError)" in text


# ---------------------- A-29 message with the uploader's outcome lines
def test_an_empty_result_with_an_upload_gives_one_line_about_the_upload(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    import boto3

    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="reports-x")
    monkeypatch.setattr(
        cbg.CloudBOMGenerator,
        "_discover_account_resources_inner",
        lambda self, account_id, context: [],
    )
    assert run_cli(*ARGS, "--s3-bucket", "reports-x") == 1  # as in v1.2.1
    lines = console(capsys)
    nothing = lines_with(lines, "Nothing to upload to s3://reports-x/")
    assert nothing, lines
    for other in (
        "S3 upload failed",
        "S3 upload is incomplete",
        "No file was uploaded",
        "Nothing was uploaded",
    ):
        assert not lines_with(lines, other), (other, lines)


# ------------------ A-24 note with discovery's one Cost Explorer warning
def test_a_slow_cost_explorer_tells_one_story_about_billing(
    aws, tmp_path, monkeypatch, capsys  # noqa: F811
):
    """Cost Explorer does not answer within lead A's bound: discovery prints
    ONE Cost Explorer warning (senior D), and it tells the same story as lead
    A's run note (it did not answer in time), not a network problem, a denial
    or a missing opt-in."""
    clock = FakeClock()
    short_limit(monkeypatch, clock)
    slow_cost_explorer(monkeypatch, clock)
    assert run_cli(*ce_args(accounts_file(tmp_path, [GOOD]))) == 0
    out = capsys.readouterr()
    text = out.out + out.err
    warnings = re.findall(r"WARNING - (Cost Explorer[^\n]*)", text)
    assert len(warnings) == 1, warnings
    assert "did not answer in time" in warnings[0], warnings
    notes = run_notes(reports(tmp_path / "out")[0])
    assert any("Cost Explorer did not answer in time" in n for n in notes), notes


@pytest.fixture(autouse=True)
def _info(caplog):
    caplog.set_level(logging.INFO)
