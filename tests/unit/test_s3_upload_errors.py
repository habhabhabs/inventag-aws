"""S3 upload failures are reported per file and never leave a partial object or file."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from inventag.core.s3_upload import S3UploadError, upload_files


def client_failing_for(name_fragment):
    client = MagicMock()
    client.meta.region_name = "eu-west-1"

    def put_object(**kwargs):
        if name_fragment in kwargs["Key"]:
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                "PutObject",
            )
        return {}

    client.put_object.side_effect = put_object
    return client


def test_one_failed_file_does_not_stop_the_others_and_is_reported(tmp_path):
    good = tmp_path / "good.xlsx"
    bad = tmp_path / "bad.docx"
    good.write_bytes(b"1")
    bad.write_bytes(b"2")
    client = client_failing_for("bad.docx")
    result = upload_files(client, [str(bad), str(good)], "reports", "p", timestamp="t")
    assert [u["key"] for u in result["uploaded"]] == ["p/t/good.xlsx"]
    assert result["uploaded"][0]["url"] == (
        "https://reports.s3.eu-west-1.amazonaws.com/p/t/good.xlsx"
    )
    assert len(result["errors"]) == 1
    assert result["errors"][0]["file"] == str(bad)
    assert "AccessDenied" in result["errors"][0]["error"]
    # the local report is untouched by the failed upload
    assert bad.read_bytes() == b"2"


def test_every_object_asks_for_encryption_and_no_acl(tmp_path):
    report = tmp_path / "r.xlsx"
    report.write_bytes(b"1")
    client = client_failing_for("none")
    upload_files(client, [str(report)], "reports", timestamp="t")
    kwargs = client.put_object.call_args.kwargs
    assert kwargs["ServerSideEncryption"] == "AES256"
    assert "ACL" not in kwargs


@pytest.mark.parametrize(
    "bucket,kwargs",
    [
        ("Bad_Bucket", {}),
        ("reports", {"encryption": "none"}),
        ("reports", {"public_read": True}),
    ],
)
def test_bad_settings_raise_before_any_upload(tmp_path, bucket, kwargs):
    report = tmp_path / "r.xlsx"
    report.write_bytes(b"1")
    client = client_failing_for("none")
    with pytest.raises(S3UploadError):
        upload_files(client, [str(report)], bucket, **kwargs)
    client.put_object.assert_not_called()
