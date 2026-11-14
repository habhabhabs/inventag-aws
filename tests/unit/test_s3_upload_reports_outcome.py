"""After an S3 upload the run says which files were uploaded and which failed,
says when nothing was uploaded because a report format failed, and hints at the
bucket region on PermanentRedirect. A clean run prints nothing new and uploads
exactly what it uploaded before. Every exit code is the one of v1.2.0.

Moto only; the fast CLI runs scan an empty moto account (about 1 s each).
"""

import logging
from unittest.mock import MagicMock

import boto3
import botocore.client
import pytest
from botocore.exceptions import ClientError

from inventag.core import s3_upload
from inventag.core.s3_upload import upload_files

from tests.unit.test_cli_exit_codes_and_flags import aws, run_cli  # noqa: F401

LOGGER = "inventag.core.s3_upload"


def failing_client(failing, code="AccessDenied", message="Access Denied", extra=None):
    client = MagicMock()
    client.meta.region_name = "us-east-1"

    def put_object(**kwargs):
        if failing(kwargs["Key"]):
            error = {"Code": code, "Message": message}
            error.update(extra or {})
            raise ClientError({"Error": error}, "PutObject")
        return {}

    client.put_object.side_effect = put_object
    return client


def two_files(tmp_path):
    good, bad = tmp_path / "good.xlsx", tmp_path / "bad.docx"
    good.write_bytes(b"1")
    bad.write_bytes(b"2")
    return good, bad


# ------------------------------------------------------------- I2: partial upload
def test_partial_upload_names_the_uploaded_and_the_failed_file(tmp_path, caplog):
    good, bad = two_files(tmp_path)
    client = failing_client(lambda key: key.endswith("bad.docx"))
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        upload_files(client, [str(bad), str(good)], "reports", "p", timestamp="t")
    summary = [
        r.getMessage() for r in caplog.records if "uploaded" in r.getMessage().lower()
    ]
    assert len(summary) == 1, caplog.text
    text = summary[0]
    assert "s3://reports/p/t/good.xlsx" in text
    assert "bad.docx" in text
    assert "1 of 2" in text


def test_nothing_uploaded_says_so(tmp_path, caplog):
    good, bad = two_files(tmp_path)
    client = failing_client(lambda key: True)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        upload_files(client, [str(good), str(bad)], "reports", "p", timestamp="t")
    assert "No file was uploaded to s3://reports" in caplog.text


# ------------------------------------------------------------- I1d: wrong region
def test_permanent_redirect_hints_at_the_bucket_region(tmp_path):
    good, _ = two_files(tmp_path)
    client = failing_client(
        lambda key: True,
        code="PermanentRedirect",
        message="The bucket you are attempting to access must be addressed "
        "using the specified endpoint.",
        extra={"Endpoint": "reports.s3.eu-west-1.amazonaws.com"},
    )
    result = upload_files(client, [str(good)], "reports", "p", timestamp="t")
    message = result["errors"][0]["error"]
    assert "PermanentRedirect" in message  # the AWS text is kept
    assert "different region" in message
    assert "AWS_DEFAULT_REGION" in message
    assert "reports.s3.eu-west-1.amazonaws.com" in message


def test_other_errors_get_no_region_hint(tmp_path):
    good, _ = two_files(tmp_path)
    client = failing_client(lambda key: True)
    result = upload_files(client, [str(good)], "reports", "p", timestamp="t")
    assert "region" not in result["errors"][0]["error"].lower()


# ----------------------------------------------- I7: a failed format skips the upload
def test_skipped_upload_message_names_the_bucket_and_the_reason():
    text = s3_upload.skipped_upload_message("reports", "bom-reports/")
    assert "Nothing was uploaded to s3://reports/bom-reports/" in text
    assert "report format failed" in text


def generator_returning(monkeypatch, results):
    from inventag.core.cloud_bom_generator import CloudBOMGenerator

    gen = CloudBOMGenerator.__new__(CloudBOMGenerator)
    gen.logger = logging.getLogger("inventag.core.cloud_bom_generator")
    monkeypatch.setattr(gen, "generate_multi_account_bom", lambda **kw: results)
    return gen


CONFIG = dict(bucket_name="reports", key_prefix="bom-reports/")


def test_upload_skipped_after_a_failed_format_is_logged(monkeypatch, caplog):
    """The generator logs the uploader's message (lead A's call in
    cloud_bom_generator.generate_comprehensive_bom); v1.2.0 stayed silent."""
    from inventag.core.cicd_integration import S3UploadConfig

    # A failed format: the failure result carries bom_generation (what was written).
    gen = generator_returning(
        monkeypatch,
        {
            "success": False,
            "error": "google format failed",
            "bom_generation": {"generated_files": ["a.xlsx"]},
        },
    )
    with caplog.at_level(logging.WARNING):
        results = gen.generate_comprehensive_bom(
            ["excel"], s3_upload_config=S3UploadConfig(**CONFIG)
        )
    assert results["success"] is False
    assert "Nothing was uploaded to s3://reports/bom-reports/" in caplog.text


def test_no_skip_message_when_the_run_failed_before_any_report(monkeypatch, caplog):
    """A run that failed in discovery has no report formats: the format message
    would be false, so it must not appear. Passes with and without the patch."""
    from inventag.core.cicd_integration import S3UploadConfig

    gen = generator_returning(monkeypatch, {"success": False, "error": "no accounts"})
    with caplog.at_level(logging.WARNING):
        results = gen.generate_comprehensive_bom(
            ["excel"], s3_upload_config=S3UploadConfig(**CONFIG)
        )
    assert results["success"] is False
    assert "Nothing was uploaded" not in caplog.text


# ---------------------------------------------- the whole run: messages and exit codes
def keys_in(bucket="a-bucket"):
    s3 = boto3.client("s3", region_name="us-east-1")
    listing = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
    return sorted(item["Key"] for item in listing), s3


def break_put_object(monkeypatch, failing):
    real = botocore.client.BaseClient._make_api_call

    def make_api_call(self, operation_name, api_params):
        if operation_name == "PutObject" and failing(api_params):
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                operation_name,
            )
        return real(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", make_api_call)


RUN = [
    "--account-regions",
    "us-east-1",
    "--account-services",
    "s3",
    "--no-billing-validation",
]
FORMATS = ["--create-excel", "--create-word"]


def test_i2_partial_upload_run_lists_both_files_and_still_exits_1(
    aws, monkeypatch, capsys  # noqa: F811
):
    break_put_object(monkeypatch, lambda p: p["Key"].endswith(".docx"))
    code = run_cli(*RUN, *FORMATS, "--s3-bucket", "a-bucket")
    captured = capsys.readouterr()
    err = captured.err + captured.out
    assert code == 1
    keys, _ = keys_in()
    assert len(keys) == 1 and keys[0].endswith(".xlsx")
    assert "1 of 2" in err
    assert keys[0].rsplit("/", 1)[1] in err
    assert ".docx" in err


def test_i1d_permanent_redirect_run_hints_and_still_exits_1(
    aws, monkeypatch, capsys  # noqa: F811
):
    real = botocore.client.BaseClient._make_api_call

    def make_api_call(self, operation_name, api_params):
        if operation_name == "PutObject":
            raise ClientError(
                {"Error": {"Code": "PermanentRedirect", "Message": "use endpoint"}},
                operation_name,
            )
        return real(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", make_api_call)
    code = run_cli(*RUN, "--create-excel", "--s3-bucket", "a-bucket")
    captured = capsys.readouterr()
    err = captured.err + captured.out
    assert code == 1
    assert "different region" in err
    assert "No file was uploaded" in err


def test_clean_upload_run_prints_no_upload_warning_and_exits_0(
    aws, capsys, tmp_path  # noqa: F811
):
    code = run_cli(*RUN, *FORMATS, "--s3-bucket", "a-bucket", "--s3-key-prefix", "p")
    captured = capsys.readouterr()
    err = captured.err + captured.out
    assert code == 0
    assert "No file was uploaded" not in err
    assert "Nothing was uploaded" not in err
    assert "of 2" not in err
    keys, s3 = keys_in()
    assert len(keys) == 2 and all(k.startswith("p/") for k in keys)
    for key in keys:
        assert s3.head_object(Bucket="a-bucket", Key=key)["ServerSideEncryption"] == (
            "AES256"
        )


def test_clean_upload_is_silent_and_identical_for_the_uploader(tmp_path, caplog, aws):
    """Characterisation: same keys, same server-side encryption, same object
    count, no log record above INFO, and the same result shape as v1.2.0."""
    good, bad = two_files(tmp_path)
    s3 = boto3.client("s3", region_name="us-east-1")
    with caplog.at_level(logging.INFO, logger=LOGGER):
        result = upload_files(s3, [str(good), str(bad)], "a-bucket", "p", timestamp="t")
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert sorted(result) == ["errors", "uploaded"]
    assert result["errors"] == []
    assert [u["key"] for u in result["uploaded"]] == ["p/t/good.xlsx", "p/t/bad.docx"]
    assert sorted(result["uploaded"][0]) == ["file", "key", "url"]
    keys, _ = keys_in()
    assert keys == ["p/t/bad.docx", "p/t/good.xlsx"]
    for key in keys:
        head = s3.head_object(Bucket="a-bucket", Key=key)
        assert head["ServerSideEncryption"] == "AES256"


def test_exit_code_for_a_missing_bucket_stays_1(aws, capsys):  # noqa: F811
    assert run_cli(*RUN, "--create-excel", "--s3-bucket", "no-such-bucket-xyz") == 1


@pytest.mark.parametrize("flag", [[], ["--s3-key-prefix", "x"]])
def test_exit_code_without_upload_problems_stays_0(aws, flag):  # noqa: F811
    assert run_cli(*RUN, "--create-excel", "--s3-bucket", "a-bucket", *flag) == 0
