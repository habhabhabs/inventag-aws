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
    results: dict = field(
        default_factory=dict
    )  # what generate_comprehensive_bom returned

    @property
    def text(self) -> str:
        return self.stdout + "\n" + self.stderr

    @property
    def permission_lines(self) -> List[str]:
        """The "Permissions:" lines of the run notes on the console (log prefix removed)."""
        lines = [t for t in self.text.splitlines() if "Permissions:" in t]
        return ["Permissions:" + t.split("Permissions:", 1)[1].rstrip() for t in lines]

    @property
    def permission_actions(self) -> set:
        """The IAM actions of the result's ``permissions_denied`` key."""
        return {e["action"] for e in self.results.get("permissions_denied", [])}

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
    from inventag.core.cloud_bom_generator import CloudBOMGenerator
    from inventag.discovery.coverage import CoverageLedger

    entries: List[object] = []
    returned: List[dict] = []
    original_generate = CloudBOMGenerator.generate_comprehensive_bom

    def spy_generate(self, *args, **kwargs):
        result = original_generate(self, *args, **kwargs)
        returned.append(result)
        return result

    monkeypatch.setattr(CloudBOMGenerator, "generate_comprehensive_bom", spy_generate)
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
        del returned[:]
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
            code,
            buf_out.getvalue(),
            buf_err.getvalue(),
            out_dir,
            sim,
            list(entries),
            returned[-1] if returned else {},
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


# ------------------------------------------------------------------------ scenarios
def _assert_in_report(run: Run, estate: dict) -> None:
    text = run.workbook_text()
    assert text, "no workbook was written"
    missing = [
        name
        for name in (*ESTATE_NAMES, estate["vpc_id"], estate["instance_id"])
        if name not in text
    ]
    assert not missing, f"not in the report: {missing}"


def test_R1_provisional_readonlyaccess_runs_a_default_scan_without_a_denied_call(
    aws, run_as
):
    """R1: one account, default flags, Excel and Word, state on, as ReadOnlyAccess."""
    run = run_as(read_only_access_actions(), "--create-excel", "--create-word")
    run.sim.assert_all_mapped()
    assert run.code == 0, run.text
    assert run.sim.denied == []
    assert run.denied_ledger == []
    assert "No permission for" not in run.text
    assert "Not read in account" not in run.workbook_text() + run.text
    # W2: a clean run says nothing new and has no new key
    assert "Permissions:" not in run.text + run.workbook_text()
    assert "permissions_denied" not in run.results
    assert list(run.out_dir.glob("*.docx")), "no Word report"
    _assert_in_report(run, aws)
    assert len(run.snapshots()) == 1, "state is on: one snapshot"
    # the proof is not hollow: the run really used the actions the plan names
    assert {
        "sts:GetCallerIdentity",
        "ec2:DescribeRegions",
        "tag:GetResources",
        "s3:ListAllMyBuckets",
        "lambda:ListFunctions",
        "ec2:DescribeVpcs",
    } <= run.sim.seen_set


def test_R2_provisional_readonlyaccess_with_every_optional_read_is_denied_nothing(
    aws, run_as
):
    """R2: R1 plus network, security and cost analysis and billing validation."""
    run = run_as(
        read_only_access_actions(),
        "--create-excel",
        "--create-word",
        "--enable-network-analysis",
        "--enable-security-analysis",
        "--enable-cost-analysis",
        billing=True,
    )
    run.sim.assert_all_mapped()
    assert run.code == 0, run.text
    # none of the 122 actions of the policy file (nor the others the run uses) is denied
    assert run.sim.denied == []
    assert run.denied_ledger == []
    assert "No permission for" not in run.text
    assert "Permissions:" not in run.text + run.workbook_text()
    assert "permissions_denied" not in run.results
    _assert_in_report(run, aws)
    # the optional reads were really made (a run that skipped them proves nothing)
    assert {
        "ce:GetCostAndUsage",
        "pricing:GetProducts",
        "cloudwatch:GetMetricStatistics",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeSecurityGroups",
        "tag:GetResources",
        "apigateway:GET",
    } <= run.sim.seen_set


DEFAULT_ACCOUNT = "123456789012"  # the account moto's default credentials belong to
ROLE_ACCOUNT = "222222222222"
ROLE_ARN = f"arn:aws:iam::{ROLE_ACCOUNT}:role/InvenTagScan"


def _two_accounts():
    return [
        {
            "account_id": DEFAULT_ACCOUNT,
            "account_name": "Default account",
            "regions": [REGION],
        },
        {
            "account_id": ROLE_ACCOUNT,
            "account_name": "Account through a role",
            "role_arn": ROLE_ARN,
            "regions": [REGION],
        },
    ]


ROLE_LINE = (
    "Permissions: 1 action(s) were not allowed for account 222222222222: "
    "sts:AssumeRole. Effect: the account was not scanned. "
    "sts:AssumeRole is not in ReadOnlyAccess; it is needed only for "
    "scanning other accounts through a role."
)


def _assert_no_aws_text(lines) -> None:
    """The block is InvenTag's own words: nothing of AWS's error text reaches it."""
    for text in lines:
        for forbidden in ("User:", "not authorized", "An error occurred", "arn:aws"):
            assert forbidden not in text, text


def test_R3_provisional_readonlyaccess_cannot_assume_a_role_and_the_default_account_is_still_scanned(
    aws, run_as
):
    """R3: sts:AssumeRole is not in ReadOnlyAccess; the account that needs it fails alone."""
    run = run_as(
        read_only_access_actions(),
        "--create-excel",
        accounts=_two_accounts(),
        scope=False,
    )
    run.sim.assert_all_mapped()
    assert run.code == 0, run.text
    # the only action refused is the one ReadOnlyAccess does not include
    assert run.sim.denied_set == {"sts:AssumeRole"}
    # the default account is scanned and is in the report
    _assert_in_report(run, aws)
    assert run.denied_ledger == []
    # the other account is named, with the reason AWS gave, and a way to continue
    assert f"{ROLE_ACCOUNT} (Account through a role)" in run.text
    assert "Role assumption failed" in run.text
    assert "(AccessDenied)" in run.text
    assert "--resume" in run.text
    # the report itself says the account is missing and why
    assert f"{ROLE_ACCOUNT} (Account through a role)" in run.workbook_text()
    # W2: the Permissions block names the action, in InvenTag's words, and the key holds it
    assert run.permission_lines == [ROLE_LINE]
    assert ROLE_LINE in run.workbook_text()
    assert run.results["permissions_denied"] == [
        {
            "account": ROLE_ACCOUNT,
            "action": "sts:AssumeRole",
            "service": "sts",
            "operation": "AssumeRole",
            "regions": [],
            "kind": "role",
        }
    ]
    assert run.permission_actions == run.sim.denied_set
    _assert_no_aws_text(run.permission_lines)

    # with the opt-in flag the same run ends with the account-failed code
    again = run_as(
        read_only_access_actions(),
        "--create-excel",
        "--fail-on-account-error",
        accounts=_two_accounts(),
        scope=False,
        out=run.out_dir.parent / "out-strict",
    )
    again.sim.assert_all_mapped()
    assert again.code == 5, again.text
    assert again.sim.denied_set == {"sts:AssumeRole"}
    assert again.permission_lines == [ROLE_LINE]
    _assert_in_report(again, aws)


def test_R3_provisional_the_audit_file_holds_the_same_permissions_list(
    aws, run_as, tmp_path
):
    """--audit-output: the key is in the audit file when something was denied, else absent.

    Needs the patch v14-w2-audit-output.patch (inventag/cli/main.py and safety.py).
    """
    audit = tmp_path / "audit" / "audit.json"
    run = run_as(
        read_only_access_actions(),
        "--create-excel",
        "--audit-output",
        str(audit),
        accounts=_two_accounts(),
        scope=False,
    )
    assert run.code == 0, run.text
    written = json.loads(audit.read_text())
    assert written["permissions_denied"] == run.results["permissions_denied"]
    assert written["permissions_denied"][0]["action"] == "sts:AssumeRole"
    # what the audit file held before is still there
    assert written["read_only_enforced"] is True and written["operations"]

    clean_audit = tmp_path / "audit" / "clean.json"
    clean = run_as(
        read_only_access_actions(),
        "--create-excel",
        "--audit-output",
        str(clean_audit),
        out=tmp_path / "out-clean",
    )
    assert clean.code == 0, clean.text
    assert "permissions_denied" not in json.loads(clean_audit.read_text())


UPLOAD_LINE = (
    "Permissions: 1 action(s) were not allowed for account 123456789012: "
    "s3:PutObject. Effect: the reports were not uploaded. "
    "s3:PutObject is not in ReadOnlyAccess; it is needed only for "
    "uploading the reports (--s3-bucket)."
)


def test_R4_provisional_readonlyaccess_cannot_upload_reports_and_the_run_ends_with_exit_1(
    aws, run_as
):
    """R4: --s3-bucket needs s3:PutObject, which ReadOnlyAccess does not include."""
    boto3.client("s3", region_name=REGION).create_bucket(Bucket="w1-report-bucket")
    run = run_as(
        read_only_access_actions(),
        "--create-excel",
        "--create-word",
        "--s3-bucket",
        "w1-report-bucket",
    )
    run.sim.assert_all_mapped()
    # an upload that was asked for and did not happen is a failed run (published code 1)
    assert run.code == 1, run.text
    # the reads are all allowed; the one action refused is the upload
    assert run.sim.denied_set == {"s3:PutObject"}
    assert run.denied_ledger == []
    # the local files are kept and the run says so
    names = sorted(
        p.name for p in [*run.out_dir.glob("*.xlsx"), *run.out_dir.glob("*.docx")]
    )
    assert len(names) == 2, names
    assert "The local report files are kept." in run.text
    assert "No file was uploaded to s3://w1-report-bucket" in run.text
    # each file is named with the reason AWS gave
    for name in names:
        line = [t for t in run.text.splitlines() if "S3 upload of" in t and name in t]
        assert line, f"no per-file failure for {name}"
        assert "AccessDenied" in line[0] and "PutObject" in line[0]
    # and nothing is in the bucket
    objects = boto3.client("s3", region_name=REGION).list_objects_v2(
        Bucket="w1-report-bucket"
    )
    assert objects.get("KeyCount", 0) == 0
    # W2: the block names s3:PutObject once, for the account that uploads, and the key holds it
    assert run.permission_lines == [UPLOAD_LINE]
    assert run.results["permissions_denied"] == [
        {
            "account": DEFAULT_ACCOUNT,
            "action": "s3:PutObject",
            "service": "s3",
            "operation": "PutObject",
            "regions": [],
            "kind": "upload",
        }
    ]
    assert run.permission_actions == run.sim.denied_set
    _assert_no_aws_text(run.permission_lines)


# R5 and R7: ReadOnlyAccess minus five patterns. Written as an explicit Deny, which wins.
R5_DENY = (
    "tag:Get*",
    "ce:GetCostAndUsage",
    "pricing:GetProducts",
    "s3:Get*",
    "lambda:Get*",
)
R5_ARGS = (
    "--create-excel",
    "--create-word",
    "--enable-network-analysis",
    "--enable-security-analysis",
    "--enable-cost-analysis",
)


R5_LINE = (
    "Permissions: 5 action(s) were not allowed for account 123456789012: "
    "ce:GetCostAndUsage, lambda:GetFunctionConfiguration, pricing:GetProducts, "
    "s3:GetBucketLocation, tag:GetResources. "
    "Effect: some rows lack details; tags from the Tagging API are missing; "
    "billing checks are skipped; cost estimates are missing. "
    "All of them are in the AWS managed policy ReadOnlyAccess."
)


def _ledger_actions(run: Run) -> set:
    """The IAM actions of the ledger's denied entries (each entry names service and operation)."""
    actions = set()
    for entry in run.denied_ledger:
        action = iam_action_for(entry.service, entry.operation)
        assert action, f"a denied ledger entry has no IAM action: {entry}"
        actions.add(action)
    return actions


def test_R5_provisional_readonlyaccess_minus_five_patterns_keeps_the_allowed_rows_and_names_the_rest(
    aws, run_as
):
    """R5: R2 with tag, Cost Explorer, pricing, s3 Get* and lambda Get* taken away."""
    run = run_as(read_only_access_actions(), *R5_ARGS, deny=R5_DENY, billing=True)
    run.sim.assert_all_mapped()
    assert run.code == 0, run.text
    # the denied set, by action name (a pin: a new call under a denied pattern shows here)
    assert run.sim.denied_set == {
        "ce:GetCostAndUsage",
        "lambda:GetFunctionConfiguration",
        "pricing:GetProducts",
        "s3:GetBucketLocation",
        "tag:GetResources",
    }
    assert all(matches_any(a, R5_DENY) for a in run.sim.denied_set)
    # the report has the rows of the allowed listings (the details of two are thinner)
    _assert_in_report(run, aws)
    assert not any(
        e.source == "service-api" for e in run.denied_ledger
    ), "a listing was denied that the policy allows"
    # what the run reports equals what the simulator denied, except pricing:
    # the cost analysis keeps no ledger entry (see the next assertions)
    assert _ledger_actions(run) == run.sim.denied_set - {"pricing:GetProducts"}
    assert "Cost analysis: access to the pricing API was denied" in run.text
    # the notes of the run, as the report carries them today
    assert "Allow ce:GetCostAndUsage for this role." in run.text
    assert "resourcegroupstaggingapi in us-east-1 (denied)" in run.text
    assert "s3 GetBucketLocation in us-east-1 (denied, 1)" in run.text
    assert "lambda GetFunctionConfiguration in us-east-1 (denied, 1)" in run.text
    assert "Not read in account" in run.workbook_text()
    assert len(run.snapshots()) == 1
    # W2: the summary equals what the simulator denied, pricing included
    assert run.permission_actions == run.sim.denied_set
    assert run.permission_lines == [R5_LINE]
    assert R5_LINE in run.workbook_text()
    assert {(e["action"], e["kind"]) for e in run.results["permissions_denied"]} == {
        ("ce:GetCostAndUsage", "billing"),
        ("lambda:GetFunctionConfiguration", "detail"),
        ("pricing:GetProducts", "pricing"),
        ("s3:GetBucketLocation", "detail"),
        ("tag:GetResources", "tagging"),
    }
    _assert_no_aws_text(run.permission_lines)


ONLY_IDENTITY = ["sts:GetCallerIdentity"]


def _assert_read_nothing(run: Run) -> None:
    """The run finished, said that nothing could be read, and left no empty estate behind."""
    run.sim.assert_all_mapped()
    assert run.sim.seen_set > {
        "sts:GetCallerIdentity"
    }, "the run made no listing at all"
    # every call but the identity check was refused, and each refusal is in the ledger
    assert run.sim.denied_set == run.sim.seen_set - {"sts:GetCallerIdentity"}
    assert run.ledger and {e.outcome for e in run.ledger} == {"denied"}
    assert "No permission for" in run.text
    assert (
        "Every service listing of account 123456789012 was denied or failed" in run.text
    )
    assert "left out of change tracking" in run.text
    assert "No resources to report: nothing could be read" in run.text
    # no report that looks like an empty estate, and no snapshot to compare against
    assert not list(run.out_dir.glob("*.xlsx")) and not list(run.out_dir.glob("*.docx"))
    assert run.snapshots() == []
    assert "No state snapshot was saved: nothing was read in this run." in run.text
    # W2: every refused action is in the summary, once, in one line for the account.
    # Except the two region-list calls: discover_regions (inventag/discovery/regions.py)
    # keeps no record of why a list failed, so the summary cannot say "not allowed" for
    # them (reported to the architect; see the W2 report).
    expected = run.sim.denied_set - {"ec2:DescribeRegions", "account:ListRegions"}
    assert run.permission_actions == expected
    assert len(run.permission_lines) == 1
    line = run.permission_lines[0]
    count = len(expected)
    assert line.startswith(
        f"Permissions: {count} action(s) were not allowed for account 123456789012: "
    )
    assert line.endswith(
        "Effect: resources of some services are missing; tags from the Tagging API "
        "are missing. All of them are in the AWS managed policy ReadOnlyAccess."
    )
    assert all(
        e["kind"] in ("listing", "tagging") for e in run.results["permissions_denied"]
    )
    _assert_no_aws_text(run.permission_lines)


def test_R6_provisional_only_the_identity_call_reads_nothing_and_ends_with_exit_0(
    aws, run_as
):
    """R6: an identity that may only call sts:GetCallerIdentity."""
    run = run_as(ONLY_IDENTITY, "--create-excel", "--create-word")
    assert run.code == 0, run.text
    _assert_read_nothing(run)


def test_R6_provisional_only_the_identity_call_with_fail_if_empty_exits_6(aws, run_as):
    run = run_as(ONLY_IDENTITY, "--create-excel", "--fail-if-empty")
    assert run.code == 6, run.text
    _assert_read_nothing(run)
    assert "--fail-if-empty is set (exit code 6)" in run.text


def test_R6_provisional_only_the_identity_call_with_fail_on_account_error_exits_0_today(
    aws, run_as
):
    """What v1.3.1 does: the account's session worked, so no account failed (see the finding)."""
    run = run_as(ONLY_IDENTITY, "--create-excel", "--fail-on-account-error")
    assert run.code == 0, run.text
    _assert_read_nothing(run)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Register row A-02, planned for v2.0.0 with the other exit-code changes: an account "
        "whose every listing was refused still counts as scanned, so --fail-on-account-error "
        "exits 0 in v1.x (use --fail-if-empty to fail a CI job; it exits 6). The code looks only "
        "at accounts whose session failed (inventag/cli/main.py:1205, "
        "inventag/core/cloud_bom_generator.py:784), not at _accounts_that_read_nothing "
        "(cloud_bom_generator.py:840). This test is the target for v2.0.0."
    ),
)
def test_R6_FINDING_account_that_read_nothing_exits_5_with_fail_on_account_error(
    aws, run_as
):
    run = run_as(ONLY_IDENTITY, "--create-excel", "--fail-on-account-error")
    assert run.code == 5, run.text


def test_R6_provisional_without_region_list_permission_every_region_is_scanned(
    aws, run_as
):
    """ec2:DescribeRegions and account:ListRegions are both refused: all regions are tried."""
    run = run_as(ONLY_IDENTITY, "--create-excel", scope=False)
    assert run.code == 0, run.text
    _assert_read_nothing(run)
    assert {"ec2:DescribeRegions", "account:ListRegions"} <= run.sim.denied_set
    regions = {e.region for e in run.ledger} - {"global"}
    assert len(regions) > 10, sorted(regions)
    assert REGION in regions


def _two_runs(aws, run_as, first_deny, second_deny):
    """Two runs into one folder, a second apart (state files are named by the second)."""
    import time

    args = R5_ARGS[:2]  # reports only: the change report is what is under test
    first = run_as(read_only_access_actions(), *args, deny=first_deny)
    time.sleep(1.1)
    second = run_as(read_only_access_actions(), *args, deny=second_deny)
    for run in (first, second):
        run.sim.assert_all_mapped()
        assert run.code == 0, run.text
    return first, second


def _changes(run: Run) -> dict:
    """The change report of a run: {title: type} of each "### ... was <type> in <SERVICE>" line."""
    import re

    reports = sorted(run.out_dir.glob("changelog_*.md"))
    assert reports, "the second run wrote no change report"
    text = reports[-1].read_text()
    found = {}
    for title, kind in re.findall(
        r"^### (.+) was (added|removed|modified) in ", text, re.M
    ):
        found[title] = kind
    return {"text": text, "changes": found}


# moto's default Athena work group "primary" carries a creation time that moto sets from
# the clock on every run, so it differs between two runs of an unchanged estate. It has
# nothing to do with a denied unit, and it is the only change two identical runs show.
MOTO_CLOCK_CHANGE = {"WorkGroup 'primary'": "modified"}


def test_R7_provisional_second_run_as_in_R5_adds_and_removes_nothing_for_the_denied_units(
    aws, run_as
):
    """R7: run R5 twice; the second change report is not made of what was not read."""
    _, second = _two_runs(aws, run_as, R5_DENY, R5_DENY)
    report = _changes(second)
    assert report["changes"] == MOTO_CLOCK_CHANGE, report["text"]
    # the report says what it could not compare, in its own words
    assert (
        "The previous run did not read tagging API in us-east-1 of account 123456789012 (denied)"
        in report["text"]
    )


def test_R7_provisional_a_full_run_then_R5_adds_and_removes_nothing(aws, run_as):
    """Units that become unreadable are not "removed", and what is no longer seen is not "added"."""
    _, second = _two_runs(aws, run_as, (), R5_DENY)
    kinds = set(_changes(second)["changes"].values())
    assert not kinds & {"added", "removed"}, _changes(second)["text"]


def test_R7_provisional_R5_then_a_full_run_adds_and_removes_nothing(aws, run_as):
    _, second = _two_runs(aws, run_as, R5_DENY, ())
    report = _changes(second)
    assert not set(report["changes"].values()) & {"added", "removed"}, report["text"]
    assert "The previous run did not read tagging API in us-east-1" in report["text"]


def test_R7_FINDING_provisional_a_denied_detail_call_does_not_make_a_resource_modified(
    aws, run_as
):
    _, second = _two_runs(aws, run_as, (), R5_DENY)
    modified = {t for t, k in _changes(second)["changes"].items() if k == "modified"}
    assert modified <= set(MOTO_CLOCK_CHANGE), modified
