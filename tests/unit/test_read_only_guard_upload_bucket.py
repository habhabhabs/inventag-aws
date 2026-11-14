"""The guard's upload exception is bound to the bucket the user named, not only
to the client. It may only get stricter: nothing blocked before is allowed now.
Moto only."""

import boto3
import pytest
from moto import mock_aws

from inventag.core.s3_upload import upload_files
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    check_client_call,
    install_global_guard,
    uninstall_global_guard,
)


@pytest.fixture
def guarded_s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="named")
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="other")
        guard = install_global_guard(ReadOnlyGuard())
        try:
            yield boto3.client("s3", region_name="us-east-1"), guard
        finally:
            uninstall_global_guard()


def put(client, bucket, key="k"):
    return client.put_object(Bucket=bucket, Key=key, Body=b"x")


# ---------------------------------------------------- G4a: stricter (new blocks)
def test_upload_to_another_bucket_is_blocked_on_the_uploader_client(
    guarded_s3, tmp_path
):
    client, guard = guarded_s3
    report = tmp_path / "r.xlsx"
    report.write_bytes(b"1")
    upload_files(client, [str(report)], "named", "p", timestamp="t")  # opens named
    with pytest.raises(ReadOnlyViolationError) as caught:
        put(client, "other")
    assert "named" in str(caught.value) and "other" in str(caught.value)
    assert client.list_objects_v2(Bucket="other").get("KeyCount", 0) == 0
    blocked = guard.audit_report()["blocked"]
    assert [(b["service"], b["operation"]) for b in blocked] == [("s3", "PutObject")]


def test_upload_to_the_named_bucket_still_works(guarded_s3, tmp_path):
    client, _ = guarded_s3
    report = tmp_path / "r.xlsx"
    report.write_bytes(b"1")
    result = upload_files(client, [str(report)], "named", "p", timestamp="t")
    assert result["errors"] == []
    assert client.head_object(Bucket="named", Key="p/t/r.xlsx")[
        "ServerSideEncryption"
    ] == ("AES256")


def test_bucket_bound_permission_never_covers_other_write_operations(guarded_s3):
    client, _ = guarded_s3
    ReadOnlyGuard.allow_on_client(client, {"PutObject"}, bucket="named")
    for call in (
        lambda: client.delete_object(Bucket="named", Key="k"),
        lambda: client.put_bucket_tagging(
            Bucket="named", Tagging={"TagSet": [{"Key": "a", "Value": "b"}]}
        ),
        lambda: client.get_object(Bucket="named", Key="k"),
    ):
        with pytest.raises(ReadOnlyViolationError):
            call()


def test_bucket_bound_permission_blocks_when_the_bucket_cannot_be_told(guarded_s3):
    client, guard = guarded_s3
    ReadOnlyGuard.allow_on_client(client, {"PutObject"}, bucket="named")
    allowed, _ = guard.evaluate("s3", "PutObject", frozenset())
    assert allowed is False
    allowed, _ = check_client_call(client, "put_object")
    assert allowed is False  # no bucket given: not allowed on a bound client


# ------------------------------------------ before and after: nothing newly allowed
def test_unbound_permission_behaves_as_before(guarded_s3):
    """Callers that give no bucket (the legacy checker) keep v1.2.0 behaviour."""
    client, _ = guarded_s3
    ReadOnlyGuard.allow_on_client(client, {"PutObject"})
    put(client, "named")
    put(client, "other")
    with pytest.raises(ReadOnlyViolationError):
        client.delete_object(Bucket="named", Key="k")


def test_a_client_without_permission_still_cannot_put(guarded_s3):
    client, _ = guarded_s3
    with pytest.raises(ReadOnlyViolationError):
        put(client, "named")


def test_read_operations_are_unchanged(guarded_s3):
    client, _ = guarded_s3
    ReadOnlyGuard.allow_on_client(client, {"PutObject"}, bucket="named")
    assert "Buckets" in client.list_buckets()
    assert client.list_objects_v2(Bucket="other")["KeyCount"] == 0
