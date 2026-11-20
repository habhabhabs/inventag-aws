"""InvenTag run as an identity that holds only the AWS managed policy ReadOnlyAccess.

W1 of reports/v14-plan-readonlyaccess.md (tests only). Scenarios R1 to R7 run the whole
CLI against moto while ``tests/policy_sim.py`` answers AccessDenied to every call that the
allow-list does not cover.

PROVISIONAL: the allow-list of ``ReadOnlyAccess`` is ``tests/data/aws-managed/ReadOnlyAccess.json``,
which is a list written by hand from the plan's table, not a copy of the AWS policy (see
``SOURCE.json`` next to it, which says what must replace it). Until the raw copy exists,
every result here is a result against that provisional list. The tests prove what InvenTag
does when the calls AWS would refuse are refused; they do not prove that AWS refuses
exactly these calls. Not verified against real AWS.

Faults are by action name (an allow-list), never by call count.
"""

import io
import json
import logging
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from openpyxl import load_workbook

from tests.e2e.conftest import restored_process_state
from tests.e2e.estate import seed_compute, seed_estate
from tests.policy_sim import (
    DATA_DIR,
    allow_only,
    iam_action_for,
    load_policy_actions,
    matches_any,
    read_only_access_actions,
)
from tests.regression.runner import _logging_state

REGION = "us-east-1"

# Everything the e2e estate creates, as it appears in a report.
ESTATE_NAMES = (
    "e2e-vpc",
    "e2e-open-ssh",
    "e2e-bucket-one",
    "e2e-queue",
    "e2e-topic",
    "e2e-table",
    "e2e-box",
    "e2e-fn",
)

PROVISIONAL = "PROVISIONAL list of ReadOnlyAccess (tests/data/aws-managed/SOURCE.json)"


@dataclass
class Run:
    """What one run of the CLI left behind, and what the simulated identity saw."""

    code: int
    stdout: str
    stderr: str
    out_dir: Path
    sim: object
    ledger: List[object] = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.stdout + "\n" + self.stderr

    @property
    def denied_ledger(self):
        return [e for e in self.ledger if e.outcome == "denied"]

    def workbook_text(self) -> str:
        """Every string of the newest workbook, one per line."""
        books = sorted(self.out_dir.glob("*.xlsx"), key=lambda p: p.stat().st_mtime)
        if not books:
            return ""
        wb = load_workbook(books[-1], read_only=True)
        try:
            return "\n".join(
                str(v)
                for name in wb.sheetnames
                for row in wb[name].iter_rows(values_only=True)
                for v in row
                if isinstance(v, str)
            )
        finally:
            wb.close()

    def snapshots(self) -> List[Path]:
        return sorted((self.out_dir / "state").glob("state_*.json"))


@pytest.fixture
def aws():
    """moto with the e2e estate, a tagged instance, a function and its role."""
    with mock_aws():
        boto3.client("lambda", region_name=REGION).list_functions()
        estate = seed_estate()
        estate.update(seed_compute())
        yield estate


@pytest.fixture
def run_as(monkeypatch, tmp_path):
    """``run_as(allow, *args, deny=(), accounts=None)`` runs the CLI as that identity.

    Call it inside the ``aws`` fixture. Every run uses ``tmp_path/out`` unless ``out`` is
    given, so a second call is a second run into the same folder. The read-only guard the
    CLI installs sits before the simulator, as it does in a real run.
    """
    from inventag.cli.main import main
    from inventag.discovery.coverage import CoverageLedger

    entries: List[object] = []
    original_record = CoverageLedger.record

    def spy(self, **fields):
        entry = original_record(self, **fields)
        entries.append(entry)
        return entry

    monkeypatch.setattr(CoverageLedger, "record", spy)

    def run(allow, *args, deny=(), accounts=None, out=None, billing=False, scope=True):
        out_dir = out or (tmp_path / "out")
        out_dir.mkdir(exist_ok=True)
        argv = ["--output-directory", str(out_dir)]
        if scope:
            argv += ["--account-regions", REGION]
        if not billing:
            argv.append("--no-billing-validation")
        if accounts is not None:
            path = tmp_path / "accounts.json"
            path.write_text(json.dumps({"version": "1.0", "accounts": accounts}))
            path.chmod(0o600)
            argv += ["--accounts-file", str(path)]
        argv += list(args)
        del entries[:]
        buf_out, buf_err = io.StringIO(), io.StringIO()
        code = 0
        root = logging.getLogger()
        saved_handlers = root.handlers[:]
        root.handlers[:] = []
        monkeypatch.setattr(sys, "argv", ["inventag", *argv])
        with allow_only(allow, deny) as sim:
            with (
                restored_process_state(),
                _logging_state(),
                redirect_stdout(buf_out),
                redirect_stderr(buf_err),
            ):
                try:
                    main()
                except SystemExit as exc:
                    code = 0 if exc.code is None else exc.code
                finally:
                    root.handlers[:] = saved_handlers
        return Run(
            code, buf_out.getvalue(), buf_err.getvalue(), out_dir, sim, list(entries)
        )

    return run


# ------------------------------------------------------------------ the harness itself
# These are the checks that the simulator does what the scenarios rely on it to do.


def test_provisional_policy_sim_denies_with_the_service_own_code():
    """ec2 answers UnauthorizedOperation, s3 AccessDenied, a json service AccessDeniedException."""
    with mock_aws():
        with allow_only(["sts:GetCallerIdentity"]) as sim:
            codes = {}
            for name, call in (
                (
                    "ec2",
                    lambda: boto3.client("ec2", region_name=REGION).describe_vpcs(),
                ),
                ("s3", lambda: boto3.client("s3", region_name=REGION).list_buckets()),
                (
                    "dynamodb",
                    lambda: boto3.client("dynamodb", region_name=REGION).list_tables(),
                ),
            ):
                with pytest.raises(ClientError) as caught:
                    call()
                codes[name] = caught.value.response["Error"]["Code"]
                assert (
                    caught.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
                )
            # an allowed call goes through
            boto3.client("sts", region_name=REGION).get_caller_identity()
    assert codes == {
        "ec2": "UnauthorizedOperation",
        "s3": "AccessDenied",
        "dynamodb": "AccessDeniedException",
    }
    assert sim.denied_set == {
        "ec2:DescribeVpcs",
        "s3:ListAllMyBuckets",
        "dynamodb:ListTables",
    }
    assert "sts:GetCallerIdentity" in sim.seen_set
    sim.assert_all_mapped()


def test_provisional_policy_sim_records_a_call_with_no_action_and_names_it():
    with mock_aws():
        with allow_only(["*:*"]) as sim:
            boto3.client("iam", region_name=REGION).get_account_summary()
    assert sim.unmapped == [("iam", "GetAccountSummary")]
    with pytest.raises(AssertionError, match=r"iam\.GetAccountSummary"):
        sim.assert_all_mapped()


def test_provisional_policy_sim_explicit_deny_wins_and_wildcards_match():
    with mock_aws():
        with allow_only(
            ["ec2:Describe*", "s3:*"], deny=["ec2:DescribeVpcs", "S3:Get*"]
        ) as sim:
            ec2 = boto3.client("ec2", region_name=REGION)
            ec2.describe_subnets()
            with pytest.raises(ClientError):
                ec2.describe_vpcs()
            boto3.client("s3", region_name=REGION).list_buckets()
    assert sim.denied == ["ec2:DescribeVpcs"]
    assert "ec2:DescribeSubnets" in sim.seen_set


def test_provisional_policy_sim_runs_after_the_read_only_guard():
    """A write call is stopped by the guard, which the simulator never sees."""
    from inventag.security.read_only_guard import (
        ReadOnlyViolationError,
        install_global_guard,
        uninstall_global_guard,
    )

    with mock_aws():
        install_global_guard()
        try:
            with allow_only(["*:*"]) as sim:
                with pytest.raises(ReadOnlyViolationError):
                    boto3.client("ec2", region_name=REGION).create_vpc(
                        CidrBlock="10.0.0.0/16"
                    )
        finally:
            uninstall_global_guard()
    assert sim.seen == [] and sim.unmapped == []


def test_provisional_policy_sim_maps_every_action_of_the_policy_file_back_to_itself():
    from inventag.security.iam_policy import READ_ONLY_ACTIONS

    for action, (service, operation) in READ_ONLY_ACTIONS.items():
        assert iam_action_for(service, operation) == action
    assert iam_action_for("apigateway", "GetRestApis") == "apigateway:GET"
    assert iam_action_for("s3", "PutObject") == "s3:PutObject"
    assert iam_action_for("iam", "GetAccountSummary") is None


def test_provisional_policy_sim_reads_a_policy_document_and_refuses_what_it_cannot_read(
    tmp_path,
):
    doc = tmp_path / "p.json"
    doc.write_text(
        json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": "ec2:Describe*", "Resource": "*"}
                ],
            }
        )
    )
    assert load_policy_actions(doc) == ["ec2:Describe*"]
    for bad in (
        {"Effect": "Deny", "Action": "ec2:*", "Resource": "*"},
        {"Effect": "Allow", "NotAction": "ec2:*", "Resource": "*"},
        {"Effect": "Allow", "Action": "ec2:*", "Resource": "arn:aws:ec2:*"},
        {"Effect": "Allow", "Action": "ec2:*", "Resource": "*", "Condition": {}},
    ):
        doc.write_text(json.dumps({"Version": "2012-10-17", "Statement": [bad]}))
        with pytest.raises(ValueError):
            load_policy_actions(doc)


def test_provisional_fixture_says_it_is_provisional_and_matches_its_record():
    import hashlib

    source = json.loads((DATA_DIR / "SOURCE.json").read_text())
    assert source["status"] == "PROVISIONAL"
    assert "NOT a copy" in source["what_this_file_is"]
    digest = hashlib.sha256((DATA_DIR / "ReadOnlyAccess.json").read_bytes()).hexdigest()
    assert source["file_sha256"] == digest
    # the three actions the plan says ReadOnlyAccess does not include
    allow = read_only_access_actions()
    for action in ("sts:AssumeRole", "s3:PutObject", "kms:GenerateDataKey"):
        assert not matches_any(action, allow)
