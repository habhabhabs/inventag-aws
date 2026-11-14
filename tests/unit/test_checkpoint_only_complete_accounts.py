"""Checkpoints (``--resume``) hold only accounts that were read completely (A-03).

An account whose session expired part-way through the scan has only part of
its resources. It must not be saved under ``<output>/state/partial/``, so a
later ``--resume`` scans it again instead of reusing the partial result. A
listing that was only denied (normal with a narrow read policy) still allows
the checkpoint.
"""

import logging
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD,
    GOOD_ID,
    OTHER,
    OTHER_ID,
    Expiry,
    RoleControl,
    accounts_file,
    aws,
    empty_aws,
    logged,
    run_cli,
    scan_spy,
    seed_account,
)


# ------------------------------------------------- end to end (CLI, moto)
def test_resume_scans_again_an_account_whose_session_expired_part_way(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """GOOD's session expires after 20 calls, OTHER cannot assume its role.
    The second run with ``--resume`` must scan GOOD again."""
    seed_account(OTHER_ID, OTHER["role_arn"])
    caplog.set_level(logging.INFO)
    roles = RoleControl(monkeypatch, failing={OTHER_ID})
    # moto replaces the access key of the environment, so ask boto3 for it.
    default_key = boto3.Session().get_credentials().access_key
    expiry = Expiry(monkeypatch, allow=20, key_of=lambda: default_key)
    path = accounts_file(tmp_path, [GOOD, OTHER])
    assert run_cli("--accounts-file", path, *BASE, "--output-directory", "out") == 0
    assert expiry.raised > 0
    first_run_log = logged(caplog)

    roles.failing.clear()
    expiry.allow = 10**9  # the session works again
    scanned = scan_spy(monkeypatch)
    caplog.clear()
    args = ["--accounts-file", path, *BASE, "--resume", "--output-directory", "out"]
    assert run_cli(*args) == 0
    assert sorted(scanned) == sorted([GOOD_ID, OTHER_ID])
    assert not any("reusing results" in m and GOOD_ID in m for m in logged(caplog))
    # The resume hint of the first run did not count GOOD as saved.
    assert any("0 of 2 account(s) finished and were saved" in m for m in first_run_log)


# ---------------------------------------------------- unit (fake discovery)
EXPIRED_CODES = ["ExpiredToken", "ExpiredTokenException", "RequestExpired"]


@pytest.fixture
def moto_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


class FakeLedger:
    def __init__(self, entries):
        self._entries = entries

    def to_dict(self):
        return [dict(e) for e in self._entries]


def _entry(outcome, error_code="", service="s3", count=0):
    return {
        "account_id": "",
        "region": "us-east-1",
        "source": "service-api",
        "service": service,
        "resource_type": "Bucket",
        "operation": "ListBuckets",
        "outcome": outcome,
        "count": count,
        "error_code": error_code,
        "seconds": 0.0,
    }


class LedgerInventory:
    """Fake discovery: one bucket, and the ledger entries set by the test."""

    entries = []

    def __init__(self, session, regions, **kwargs):
        self.coverage = FakeLedger(LedgerInventory.entries)

    def discover_all_resources(self):
        return [{"id": "b1", "arn": "arn:aws:s3:::b1", "service": "S3"}]


class SpyStore:
    saved = []

    def save_account(self, account_id, resources, regions=None):
        SpyStore.saved.append(account_id)


def _scan_one(tmp_path, entries):
    LedgerInventory.entries = entries
    SpyStore.saved = []
    generator = CloudBOMGenerator(
        MultiAccountConfig(accounts=[], output_directory=str(tmp_path))
    )
    context = AccountContext(
        credentials=AccountCredentials(account_id="111111111111"),
        session=boto3.Session(),
        caller_identity={"Account": "111111111111"},
        accessible_regions=["us-east-1"],
    )
    generator.account_contexts = {"111111111111": context}
    generator._checkpoints = SpyStore()
    with patch(
        "inventag.core.cloud_bom_generator.AWSResourceInventory", LedgerInventory
    ):
        generator._sequential_account_discovery(generator.account_contexts)
    return SpyStore.saved


@pytest.mark.parametrize("code", EXPIRED_CODES)
def test_an_account_with_an_expired_session_listing_is_not_checkpointed(
    moto_env, tmp_path, code
):
    saved = _scan_one(
        tmp_path, [_entry("ok", count=1), _entry("error", code, service="sqs")]
    )
    assert saved == []


def test_a_denied_listing_alone_still_allows_a_checkpoint(moto_env, tmp_path):
    saved = _scan_one(
        tmp_path,
        [_entry("ok", count=1), _entry("denied", "AccessDenied", service="sqs")],
    )
    assert saved == ["111111111111"]


def test_other_listing_errors_still_allow_a_checkpoint(moto_env, tmp_path):
    """Only an expired session (or a timeout) blocks the checkpoint."""
    saved = _scan_one(
        tmp_path,
        [_entry("ok", count=1), _entry("throttled", "Throttling", service="sqs")],
    )
    assert saved == ["111111111111"]
