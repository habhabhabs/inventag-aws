"""The result of a run carries its run notes (``results["run_notes"]``).

The console prints the run notes of the result once after the summary
(WO-4, ``inventag/cli/main.py``). The list must be the one the default report
shows, and it must be there on every return path of a run: success, a report
format that could not be written, and the template runner (a subclass).
"""

import logging
from unittest.mock import patch

import pytest

from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
from inventag.templating.runner import TemplatedCloudBOMGenerator
from tests.unit.test_checkpoint_only_complete_accounts import (  # noqa: F401
    FakeLedger,
    _entry,
    moto_env,
)
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD,
    Expiry,
    accounts_file,
    aws,
    empty_aws,
    reports,
    run_cli,
)
from tests.unit.test_snapshot_not_poisoned import result_spy, run_notes


def test_the_result_holds_the_run_notes_the_report_shows(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)
    Expiry(monkeypatch, allow=20)
    path = accounts_file(tmp_path, [GOOD])
    assert run_cli("--accounts-file", path, *BASE, "--output-directory", "out") == 0
    shown = run_notes(reports(tmp_path / "out")[0])
    assert shown  # the expired session gives a note
    assert results[-1]["run_notes"] == shown


class ExpiredInventory:
    def __init__(self, session, regions, **kwargs):
        self.coverage = FakeLedger(
            [_entry("ok", count=1), _entry("error", "ExpiredToken", service="sqs")]
        )

    def discover_all_resources(self):
        return [{"id": "b1", "arn": "arn:aws:s3:::b1", "service": "S3"}]


def _generator(tmp_path):
    import boto3

    from inventag.core.cloud_bom_generator import AccountContext, AccountCredentials

    generator = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[object()],
            output_directory=str(tmp_path),
            enable_state_management=False,
        ),
    )
    context = AccountContext(
        credentials=AccountCredentials(account_id="111111111111"),
        session=boto3.Session(),
        caller_identity={"Account": "111111111111"},
        accessible_regions=["us-east-1"],
    )
    generator._establish_account_contexts = lambda: generator.account_contexts
    generator.account_contexts = {"111111111111": context}
    return generator


def test_a_failed_report_format_still_returns_the_run_notes(
    moto_env, tmp_path  # noqa: F811
):
    generator = _generator(tmp_path)
    with (
        patch(
            "inventag.core.cloud_bom_generator.AWSResourceInventory", ExpiredInventory
        ),
        patch.object(
            CloudBOMGenerator,
            "_generate_bom_documents",
            return_value={"success": False, "error": "Could not write: excel: disk"},
        ),
    ):
        result = generator.generate_multi_account_bom(output_formats=["excel"])
    assert result["success"] is False
    assert result["run_notes"] == generator._run_notes()
    assert any("111111111111" in n and "expired" in n for n in result["run_notes"])


@pytest.mark.parametrize("cls", [CloudBOMGenerator, TemplatedCloudBOMGenerator])
def test_every_generator_returns_the_run_notes(cls):
    """The template runner inherits the run, so it returns the key too."""
    assert "generate_multi_account_bom" not in vars(cls) or cls is CloudBOMGenerator
