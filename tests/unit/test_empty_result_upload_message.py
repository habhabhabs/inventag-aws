"""An empty result with ``--s3-bucket`` says there is nothing to upload (A-29,
message part only).

v1.2.1: "Error: S3 upload failed for 1 file(s)" and "S3 upload of reports
failed: no files", although nothing failed: the run wrote no report. The
exit code stays 1 (changing it is owner decision O3, accepted for v1.3.0).
"""

import logging

import boto3

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    empty_aws,
    logged,
    run_cli,
)

ARGS = [
    "--create-excel",
    "--no-billing-validation",
    "--account-regions",
    "us-east-1",
    "--account-services",
    "SQS",
    "--s3-bucket",
    "regression-upload",
    "--s3-key-prefix",
    "nightly/",
    "--output-directory",
    "out",
]


def test_an_empty_result_says_there_is_nothing_to_upload(
    empty_aws, tmp_path, caplog, capsys  # noqa: F811
):
    caplog.set_level(logging.INFO)
    boto3.client("s3", region_name="us-east-1").create_bucket(
        Bucket="regression-upload"
    )
    assert run_cli(*ARGS) == 1  # exit code as in v1.2.1 (O3: owner)
    text = capsys.readouterr().out + "\n".join(logged(caplog))
    assert (
        "Nothing to upload to s3://regression-upload/nightly/: the run wrote no "
        "report file because there are no resources to report."
    ) in text
    assert "upload failed" not in text
    assert "S3 upload of reports failed" not in text
    objects = boto3.client("s3", region_name="us-east-1").list_objects_v2(
        Bucket="regression-upload"
    )
    assert objects.get("KeyCount", 0) == 0
