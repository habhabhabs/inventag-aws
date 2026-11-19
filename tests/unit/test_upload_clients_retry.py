"""Clients created by the S3 upload, the compliance package and the legacy
scripts get the shared retry settings (standard mode, 10 tries in total, the
user's AWS_RETRY_MODE and AWS_MAX_ATTEMPTS win). No own retry loop. Moto only."""

import ast
from pathlib import Path

import boto3
import pytest
from botocore.awsrequest import AWSResponse
from moto import mock_aws

REPO = Path(__file__).resolve().parents[2]
FILES = sorted(
    [REPO / "inventag" / "core" / "s3_upload.py"]
    + list((REPO / "inventag" / "compliance").glob("*.py"))
    + list((REPO / "scripts" / "legacy").glob("*.py"))
)


def client_creations(path):
    """Lines that create a boto3 client directly (``x.client(...)``)."""
    tree = ast.parse(path.read_text())
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "client"
    ]


def test_no_client_is_created_without_the_shared_retry_settings():
    found = {
        str(p.relative_to(REPO)): client_creations(p)
        for p in FILES
        if client_creations(p)
    }
    assert found == {}, found


class Sends:
    """Answers every PutObject with one status and counts the sends."""

    def __init__(self, status, code):
        self.status, self.code, self.count = status, code, 0

    def __call__(self, request, **kwargs):
        if request.method != "PUT":
            return None
        self.count += 1
        body = (
            f"<?xml version='1.0'?><Error><Code>{self.code}</Code>"
            f"<Message>injected</Message></Error>"
        ).encode()

        class Raw:
            def __init__(self):
                self._b = body

            def stream(self, *a, **k):
                yield self._b

            def read(self, *a, **k):
                return self._b

        return AWSResponse(
            request.url, self.status, {"Content-Type": "application/xml"}, Raw()
        )


@pytest.fixture
def upload_env(monkeypatch, tmp_path):
    for key, value in {
        "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
        "AWS_SECRET_ACCESS_KEY": "fake-secret-for-moto-only",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(key, value)
    for key in ("AWS_RETRY_MODE", "AWS_MAX_ATTEMPTS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    report = tmp_path / "r.xlsx"
    report.write_bytes(b"1")
    with mock_aws():
        yield report


def attempts_for(report, status, code):
    from inventag.core.s3_upload import create_upload_client, upload_files

    client = create_upload_client(boto3.Session())
    sends = Sends(status, code)
    client.meta.events.register("before-send.s3.PutObject", sends)
    result = upload_files(client, [str(report)], "reports", "p", timestamp="t")
    return sends.count, result


def test_a_throttled_put_is_tried_up_to_the_shared_limit(upload_env):
    count, result = attempts_for(upload_env, 503, "SlowDown")
    assert count == 10
    assert len(result["errors"]) == 1 and "SlowDown" in result["errors"][0]["error"]


def test_a_denied_put_is_not_retried(upload_env):
    count, result = attempts_for(upload_env, 403, "AccessDenied")
    assert count == 1
    assert "AccessDenied" in result["errors"][0]["error"]


def test_the_users_max_attempts_wins(upload_env, monkeypatch):
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "2")
    count, _ = attempts_for(upload_env, 503, "SlowDown")
    assert count == 2


def test_the_guard_and_the_bucket_grant_work_on_the_new_client(upload_env):
    from inventag.core.s3_upload import create_upload_client, upload_files
    from inventag.security.read_only_guard import (
        ReadOnlyGuard,
        ReadOnlyViolationError,
        install_global_guard,
        uninstall_global_guard,
    )

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="named")
    s3.create_bucket(Bucket="other")
    install_global_guard(ReadOnlyGuard())
    try:
        client = create_upload_client(boto3.Session())
        result = upload_files(client, [str(upload_env)], "named", "p", timestamp="t")
        assert result["errors"] == []
        with pytest.raises(ReadOnlyViolationError):
            client.put_object(Bucket="other", Key="k", Body=b"x")
    finally:
        uninstall_global_guard()


# --------------------- the generator's and the CI/CD integration's upload clients
def test_the_generators_report_upload_uses_the_shared_retry_settings(upload_env):
    """``CloudBOMGenerator.upload_reports_to_s3`` (the CLI's --s3-bucket path):
    a throttled PutObject is tried 10 times, as discovery's calls are (the SDK
    default was 3)."""
    from types import SimpleNamespace

    from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig

    seen = []
    real_session = boto3.Session

    class CountingSession(real_session):
        def client(self, *args, **kwargs):
            client = super().client(*args, **kwargs)
            if (args and args[0] == "s3") or kwargs.get("service_name") == "s3":
                sends = Sends(503, "SlowDown")
                client.meta.events.register("before-send.s3.PutObject", sends)
                seen.append(sends)
            return client

    import inventag.core.cloud_bom_generator as cbg

    original = cbg.boto3.Session
    cbg.boto3.Session = CountingSession
    try:
        generator = CloudBOMGenerator(
            MultiAccountConfig(accounts=[], output_directory=str(upload_env.parent))
        )
        config = SimpleNamespace(
            bucket_name="reports", key_prefix="p", region=None, encryption="AES256"
        )
        result = generator.upload_reports_to_s3([str(upload_env)], config)
    finally:
        cbg.boto3.Session = original
    assert len(result["errors"]) == 1
    assert [s.count for s in seen] == [10]


def test_the_cicd_integration_upload_client_uses_the_shared_retry_settings(
    upload_env, monkeypatch
):
    from inventag.core import cicd_integration
    from inventag.core import s3_upload

    made = []
    real = s3_upload.create_upload_client

    def spy(session, region_name=None):
        made.append(region_name)
        return real(session, region_name)

    monkeypatch.setattr(s3_upload, "create_upload_client", spy)
    integration = cicd_integration.CICDIntegration(
        s3_config=cicd_integration.S3UploadConfig(
            bucket_name="reports", region="eu-west-1"
        ),
        artifacts_dir=str(upload_env.parent),
    )
    client = integration._get_s3_client()
    assert made == ["eu-west-1"]
    assert client.meta.config.retries["total_max_attempts"] == 10
