"""The two legacy upload paths grant PutObject only for the bucket the user
named: the named bucket still works, any other bucket on the same client is
blocked. Moto only."""

import importlib.util
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from inventag.compliance.checker import ComprehensiveTagComplianceChecker
from inventag.security.read_only_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    install_global_guard,
    uninstall_global_guard,
)

LEGACY = Path(__file__).resolve().parents[2] / "scripts" / "legacy"


@pytest.fixture
def guarded(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="named")
        s3.create_bucket(Bucket="other")
        install_global_guard(ReadOnlyGuard())
        try:
            yield s3
        finally:
            uninstall_global_guard()


def objects(s3, bucket):
    return [o["Key"] for o in s3.list_objects_v2(Bucket=bucket).get("Contents", [])]


class SpyClientSession:
    """A session whose S3 client is kept, so the test can try a second bucket
    on the very client the code under test granted."""

    def __init__(self):
        self.session = boto3.Session()
        self.clients = []

    def client(self, *args, **kwargs):
        client = self.session.client(*args, **kwargs)
        self.clients.append(client)
        return client


def make_checker(session):
    checker = ComprehensiveTagComplianceChecker(session=session)
    checker.compliance_results = {"summary": {"ok": True}}
    return checker


def test_checker_upload_to_the_named_bucket_works_and_is_encrypted(guarded):
    session = SpyClientSession()
    make_checker(session).upload_to_s3("named", "r.json", "json", allow_write=True)
    assert objects(guarded, "named") == ["r.json"]
    head = guarded.head_object(Bucket="named", Key="r.json")
    assert head["ServerSideEncryption"] == "AES256"


def test_checker_client_cannot_write_to_another_bucket(guarded):
    session = SpyClientSession()
    make_checker(session).upload_to_s3("named", "r.json", "json", allow_write=True)
    granted = session.clients[-1]
    with pytest.raises(ReadOnlyViolationError):
        granted.put_object(Bucket="other", Key="k", Body=b"x")
    assert objects(guarded, "other") == []


def load_inventory_script():
    spec = importlib.util.spec_from_file_location(
        "legacy_aws_resource_inventory", LEGACY / "aws_resource_inventory.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_script_upload_to_the_named_bucket_works(guarded, tmp_path):
    report = tmp_path / "r.json"
    report.write_text("{}")
    load_inventory_script()._upload_report(
        SpyClientSession(), str(report), "named", "k"
    )
    assert objects(guarded, "named") == ["k"]
    assert guarded.head_object(Bucket="named", Key="k")["ServerSideEncryption"] == (
        "AES256"
    )


def test_inventory_script_client_cannot_write_to_another_bucket(guarded, tmp_path):
    report = tmp_path / "r.json"
    report.write_text("{}")
    session = SpyClientSession()
    load_inventory_script()._upload_report(session, str(report), "named", "k")
    with pytest.raises(ReadOnlyViolationError):
        session.clients[-1].put_object(Bucket="other", Key="k", Body=b"x")
    assert objects(guarded, "other") == []
