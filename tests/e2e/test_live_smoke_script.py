"""scripts/live_smoke_test.py, tested against moto.

The script is meant for a real AWS account. Here it runs in-process
(``--in-process``) against the e2e estate, and the tests break one thing at a
time to show that each check can fail.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from .conftest import restored_process_state
from .estate import seed_compute, seed_estate

pytestmark = pytest.mark.e2e

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "live_smoke_test.py"


@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location("live_smoke_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["live_smoke_test"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("live_smoke_test", None)


@pytest.fixture
def aws():
    with mock_aws():
        seed_estate()
        seed_compute()
        yield


@pytest.fixture
def run_smoke(smoke, capsys):
    def _run(*argv):
        lines = []
        with restored_process_state():
            code = smoke.main(
                ["--region", "us-east-1", "--in-process", *argv], out=lines.append
            )
        return code, "\n".join(lines)

    return _run


def result_lines(output):
    """Map check name -> (status, detail) from the printed table."""
    table = {}
    for line in output.splitlines():
        match = re.match(r"^(\S.*?)\s{2,}(PASS|FAIL|SKIP)\s+(.*)$", line)
        if match:
            table[match.group(1)] = (match.group(2), match.group(3))
    return table


class TestAgainstMoto:
    def test_everything_passes_and_the_table_is_complete(self, aws, run_smoke):
        code, output = run_smoke()

        table = result_lines(output)
        assert code == 0, output
        assert "RESULT: PASS" in output
        for name in (
            "scan exit code",
            "report opens",
            "state snapshot",
            "no write calls",
            "count S3 buckets",
            "count EC2 instances",
            "count VPCs",
            "count Security groups",
            "count Lambda functions",
            "count DynamoDB tables",
            "count SQS queues",
            "count SNS topics",
        ):
            assert table[name][0] == "PASS", (name, table.get(name), output)
        # Counts are real numbers, not placeholders.
        assert table["count S3 buckets"][1] == "report 1, direct 1"
        assert table["count EC2 instances"][1] == "report 1, direct 1"
        assert table["tags S3 buckets"][0] == "PASS"
        assert table["tags Lambda functions"][0] == "PASS"
        assert table["no write calls"][1].startswith("blocked 0 of ")

    def test_output_hides_account_ids_and_arns_by_default(self, aws, run_smoke):
        code, output = run_smoke()
        assert code == 0, output
        assert "123456789012" not in output
        assert "arn:aws" not in output
        assert "****9012" in output
        assert "AKIAIOSFODNN7EXAMPLE" not in output

    def test_show_ids_prints_the_account_id(self, aws, run_smoke):
        code, output = run_smoke("--show-ids")
        assert code == 0, output
        assert "Account 123456789012" in output

    def test_empty_account_is_skip_not_pass(self, run_smoke):
        with mock_aws():
            code, output = run_smoke()
        table = result_lines(output)
        assert table["count Lambda functions"][0] == "SKIP"
        assert table["tags S3 buckets"][0] == "SKIP"

    def test_report_is_removed_unless_a_directory_is_given(
        self, aws, run_smoke, tmp_path, monkeypatch
    ):
        import tempfile

        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        code, _ = run_smoke()
        assert code == 0
        assert list(tmp_path.glob("inventag-smoke-*")) == []

        keep = tmp_path / "kept"
        code, output = run_smoke("--output-directory", str(keep))
        assert code == 0
        assert list(keep.glob("*.xlsx"))
        assert f"Report kept in {keep}" in output

    def test_word_report_is_opened_when_asked(self, aws, run_smoke):
        code, output = run_smoke("--create-word")
        assert code == 0, output
        assert result_lines(output)["word report opens"][0] == "PASS"


def unguarded_client(service):
    """A client without the read-only guard, to change the world after the scan."""
    from inventag.security.read_only_guard import uninstall_global_guard

    uninstall_global_guard()
    return boto3.client(service, region_name="us-east-1")


class TestEachCheckCanFail:
    def _after_scan(self, smoke, monkeypatch, change):
        original = smoke.run_scan

        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            change()
            return result

        monkeypatch.setattr(smoke, "run_scan", wrapped)

    def test_a_resource_the_report_missed_fails_the_count(
        self, aws, smoke, run_smoke, monkeypatch
    ):
        self._after_scan(
            smoke,
            monkeypatch,
            lambda: unguarded_client("sqs").create_queue(
                QueueName="created-after-the-scan"
            ),
        )
        code, output = run_smoke()
        status, detail = result_lines(output)["count SQS queues"]
        assert code == 1
        assert status == "FAIL"
        assert "report 1, direct 2" in detail
        assert "RESULT: FAIL" in output
        assert "created-after-the-scan" not in output  # ids are masked

    def test_changed_tags_fail_the_tag_check(self, aws, smoke, run_smoke, monkeypatch):
        self._after_scan(
            smoke,
            monkeypatch,
            lambda: unguarded_client("s3").put_bucket_tagging(
                Bucket="e2e-bucket-one",
                Tagging={"TagSet": [{"Key": "Owner", "Value": "someone-else"}]},
            ),
        )
        code, output = run_smoke()
        assert code == 1
        assert result_lines(output)["tags S3 buckets"][0] == "FAIL"

    def test_a_blocked_write_attempt_fails_the_guard_check(
        self, aws, smoke, run_smoke, monkeypatch
    ):
        from inventag.security.read_only_guard import ReadOnlyViolationError

        def attempt_a_write():
            with pytest.raises(ReadOnlyViolationError):
                boto3.client("sqs", region_name="us-east-1").create_queue(
                    QueueName="blocked-write"
                )

        self._after_scan(smoke, monkeypatch, attempt_a_write)
        code, output = run_smoke()
        status, detail = result_lines(output)["no write calls"]
        assert code == 1
        assert status == "FAIL"
        assert "blocked=1" in detail

    def test_a_failed_scan_fails_and_prints_a_masked_log(
        self, aws, smoke, run_smoke, monkeypatch
    ):
        def failing_scan(args, output_dir, audit_path):
            return 1, "boom for account 123456789012 key AKIAABCDEFGHIJKLMNOP", 0.1

        monkeypatch.setattr(smoke, "run_scan", failing_scan)
        code, output = run_smoke()
        assert code == 1
        assert result_lines(output)["scan exit code"][0] == "FAIL"
        assert "123456789012" not in output
        assert "AKIAABCDEFGHIJKLMNOP" not in output
        assert "boom for account ****9012" in output

    def test_no_credentials_exits_2(self, smoke, run_smoke, monkeypatch):
        from botocore.exceptions import NoCredentialsError

        def no_creds(*args, **kwargs):
            raise NoCredentialsError()

        monkeypatch.setattr(smoke, "read_client", no_creds)
        code, output = run_smoke()
        assert code == 2
        assert "no usable AWS credentials" in output


class TestSafetyByConstruction:
    @pytest.mark.parametrize(
        "method",
        [
            "create_bucket",
            "put_bucket_tagging",
            "delete_queue",
            "terminate_instances",
            "run_instances",
            "invoke",
            "put_object",
        ],
    )
    def test_write_methods_are_refused_before_any_request(self, smoke, method):
        class Spy:
            called = False

            def __getattr__(self, name):
                Spy.called = True
                return lambda *a, **k: {}

        client = smoke.ReadOnlyClient(Spy())
        with pytest.raises(PermissionError):
            getattr(client, method)
        assert Spy.called is False

    @pytest.mark.parametrize(
        "method",
        ["list_buckets", "describe_vpcs", "get_bucket_tagging", "get_paginator"],
    )
    def test_read_methods_pass_through(self, smoke, method):
        class Spy:
            def __getattr__(self, name):
                return name

        assert getattr(smoke.ReadOnlyClient(Spy()), method) == method

    def test_only_read_operations_are_called_during_the_whole_run(
        self, aws, run_smoke, tmp_path
    ):
        keep = tmp_path / "kept"
        code, output = run_smoke("--output-directory", str(keep))
        assert code == 0, output
        audit = json.loads((keep / "audit" / "aws_calls.json").read_text())
        assert audit["blocked_calls"] == 0
        for op in audit["operations"]:
            assert op["operation"].startswith(
                ("List", "Describe", "Get", "Head", "Lookup", "Search", "BatchGet")
            ), op

    def test_billing_validation_is_off_unless_asked(self, smoke):
        parser = smoke.build_parser()
        default = smoke.scan_command(
            parser.parse_args(["--region", "eu-west-1"]), Path("/o"), Path("/a")
        )
        assert "--no-billing-validation" in default
        assert "--billing-validation" not in default
        assert default[default.index("--account-regions") + 1] == "eu-west-1"
        asked = smoke.scan_command(
            parser.parse_args(["--billing-validation"]), Path("/o"), Path("/a")
        )
        assert "--billing-validation" in asked
        assert "--no-billing-validation" not in asked

    def test_script_source_calls_no_write_methods(self):
        """Every ``<client>.<method>(`` call in the script is a read method."""
        import ast

        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        client_methods = {
            name
            for name in called
            if name.startswith(
                (
                    "create_",
                    "put_",
                    "delete_",
                    "update_",
                    "terminate_",
                    "start_",
                    "stop_",
                )
            )
            or name == "run_instances"
        }
        assert client_methods == set()


class TestMasking:
    def test_scrub_masks_ids_arns_and_keys(self, smoke):
        text = (
            "arn:aws:iam::123456789012:role/Admin and 210987654321 "
            "AKIAIOSFODNN7EXAMPLE ASIAIOSFODNN7EXAMPLE"
        )
        cleaned = smoke.scrub(text)
        assert "123456789012" not in cleaned
        assert "210987654321" not in cleaned
        assert "AKIAIOSFODNN7EXAMPLE" not in cleaned
        assert "ASIAIOSFODNN7EXAMPLE" not in cleaned
        assert "****9012" in cleaned and "****4321" in cleaned

    def test_show_ids_leaves_text_alone(self, smoke):
        assert smoke.scrub("123456789012", show_ids=True) == "123456789012"

    def test_mask_arn_keeps_service_and_region(self, smoke):
        masked = smoke.mask_arn("arn:aws:sqs:us-east-1:123456789012:my-queue", False)
        assert masked == "arn:aws:sqs:us-east-1:****9012:...ueue"
