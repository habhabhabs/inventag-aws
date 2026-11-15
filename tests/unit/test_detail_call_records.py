"""A-22: a failed detail call or client creation leaves a record in the coverage ledger.

Detail records have their own source (``service-api-detail``). The change
report reads only ``service-api`` and ``tagging-api`` records as listings, so a
detail record never makes it treat a resource as "not compared". The answers
AWS gives for "nothing configured" are not failures and leave no record.
"""

import logging
from unittest import mock

import pytest
from botocore.exceptions import ClientError

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery
from inventag.state.delta_detector import _RunScope

R = "eu-west-1"
ACCOUNT = "111122223333"


def _error(code):
    return ClientError({"Error": {"Code": code, "Message": "secret-detail"}}, "Op")


def _disc(resources, client_for):
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=False
    )
    disc.coverage.account_id = ACCOUNT
    disc.resources = resources
    disc._client = client_for
    return disc


def _row(service, rtype, rid):
    return {
        "service": service,
        "resource_type": rtype,
        "resource_id": rid,
        "region": R,
        "arn": f"arn:aws:{service.lower()}:{R}:{ACCOUNT}:x/{rid}",
        "raw_data": {},
    }


class Raising:
    """A client whose detail operations all raise ``error``."""

    def __init__(self, error):
        self._error = error

    def __getattr__(self, name):
        def call(**kwargs):
            raise self._error

        return call


def _entries(disc):
    return [e for e in disc.coverage.to_dict() if e["source"] == "service-api-detail"]


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


CASES = [
    (
        "LAMBDA",
        "Function",
        "_enhance_lambda_functions",
        "lambda",
        "GetFunctionConfiguration",
    ),
    ("RDS", "DBInstance", "_enhance_rds_resources", "rds", "DescribeDBInstances"),
    (
        "CLOUDFORMATION",
        "Stack",
        "_enhance_cloudformation_stacks",
        "cloudformation",
        "DescribeStacks",
    ),
]


@pytest.mark.parametrize("service, rtype, method, key, operation", CASES)
def test_failed_detail_call_is_recorded_once_per_operation(
    service, rtype, method, key, operation, caplog
):
    rows = [_row(service, rtype, name) for name in ("a", "b", "c")]
    disc = _disc(rows, lambda *a, **k: Raising(_error("AccessDeniedException")))
    with caplog.at_level(logging.WARNING):
        getattr(disc, method)()
    entries = _entries(disc)
    assert len(entries) == 1
    entry = entries[0]
    assert (entry["service"], entry["region"], entry["operation"]) == (
        key,
        R,
        operation,
    )
    assert (entry["outcome"], entry["error_code"], entry["count"]) == (
        "denied",
        "AccessDeniedException",
        3,
    )
    assert entry["account_id"] == ACCOUNT
    assert len(rows) == 3  # the rows stay in the report
    assert _warnings(caplog) == [
        f"Details of 3 {key} resource(s) in {R} could not be read "
        f"({operation}: AccessDeniedException); their rows have some fields "
        "missing. Add the read permission to see them."
    ]
    assert "secret-detail" not in caplog.text


def test_throttled_and_other_detail_failures_use_their_outcome_word():
    disc = _disc(
        [_row("LAMBDA", "Function", "a")],
        lambda *a, **k: Raising(_error("ThrottlingException")),
    )
    disc._enhance_lambda_functions()
    assert [e["outcome"] for e in _entries(disc)] == ["throttled"]
    disc = _disc(
        [_row("LAMBDA", "Function", "a")],
        lambda *a, **k: Raising(RuntimeError("boom")),
    )
    disc._enhance_lambda_functions()
    entry = _entries(disc)[0]
    assert (entry["outcome"], entry["error_code"]) == ("error", "RuntimeError")


def test_bucket_location_failure_is_recorded(caplog):
    rows = [_row("S3", "Bucket", "b1")]
    disc = _disc(rows, lambda *a, **k: Raising(_error("AccessDenied")))
    with caplog.at_level(logging.WARNING):
        disc._enhance_s3_buckets()
    (entry,) = _entries(disc)
    assert (entry["service"], entry["operation"], entry["outcome"]) == (
        "s3",
        "GetBucketLocation",
        "denied",
    )


@pytest.mark.parametrize(
    "code",
    [
        "NoSuchBucketPolicy",
        "NoSuchTagSet",
        "NoSuchLifecycleConfiguration",
        "NoSuchPublicAccessBlockConfiguration",
        "NoSuchCORSConfiguration",
        "ServerSideEncryptionConfigurationNotFoundError",
        "ObjectLockConfigurationNotFoundError",
        "404",
        "NotFound",
    ],
)
def test_nothing_configured_answers_are_not_failures(code, caplog):
    disc = _disc(
        [_row("S3", "Bucket", "b1"), _row("LAMBDA", "Function", "f1")],
        lambda *a, **k: Raising(_error(code)),
    )
    with caplog.at_level(logging.WARNING):
        disc._enhance_s3_buckets()
        disc._enhance_lambda_functions()
    assert _entries(disc) == []
    assert disc.coverage.entries == []
    assert _warnings(caplog) == []


@pytest.mark.parametrize(
    "code", ["NoSuchBucket", "ResourceNotFoundException", "DBInstanceNotFound"]
)
def test_a_resource_deleted_during_the_scan_is_not_a_failure(code):
    disc = _disc(
        [_row("LAMBDA", "Function", "f1")], lambda *a, **k: Raising(_error(code))
    )
    disc._enhance_lambda_functions()
    assert disc.coverage.entries == []


def test_failed_client_creation_for_a_detail_call_is_recorded():
    def no_client(*a, **k):
        raise _error("UnrecognizedClientException")

    disc = _disc([_row("RDS", "DBInstance", "db1")], no_client)
    disc._enhance_rds_resources()
    (entry,) = _entries(disc)
    assert (entry["service"], entry["region"], entry["outcome"]) == (
        "rds",
        R,
        "error",
    )
    assert entry["error_code"] == "UnrecognizedClientException"


def test_failed_client_creation_for_a_listing_is_a_listing_record(caplog):
    def no_client(*a, **k):
        raise _error("UnrecognizedClientException")

    disc = _disc([], no_client)
    task = {
        "service": "sqs",
        "region": R,
        "config": disc.service_discovery_patterns["sqs"],
    }
    with caplog.at_level(logging.WARNING):
        assert disc._discover_service_in_region(task) == 0
    (entry,) = disc.coverage.to_dict()
    assert (entry["source"], entry["service"], entry["region"]) == (
        "service-api",
        "sqs",
        R,
    )
    assert (entry["outcome"], entry["error_code"]) == (
        "error",
        "UnrecognizedClientException",
    )
    assert "secret-detail" not in caplog.text


def test_cloudfront_certificate_failure_is_recorded_as_detail():
    disc = _disc([], lambda *a, **k: Raising(_error("AccessDenied")))
    disc.home_region = "us-east-1"
    assert disc._discover_cloudfront_certificates() == 0
    (entry,) = _entries(disc)
    assert (entry["service"], entry["region"], entry["outcome"]) == (
        "acm",
        "us-east-1",
        "denied",
    )


def test_a_detail_record_does_not_make_the_change_report_skip_the_resource():
    disc = _disc(
        [_row("LAMBDA", "Function", "f1")],
        lambda *a, **k: Raising(_error("AccessDeniedException")),
    )
    disc.coverage.record(
        region=R,
        source="service-api",
        service="lambda",
        resource_type="Function",
        operation="ListFunctions",
        outcome="ok",
        count=1,
    )
    disc._enhance_lambda_functions()
    assert len(_entries(disc)) == 1
    scope = _RunScope({"coverage": disc.coverage.to_dict()})
    resource = {"service": "LAMBDA", "region": R, "arn": "x", "account_id": ACCOUNT}
    assert scope.failed == {}
    assert scope.failed_listing(resource, "x") is None
