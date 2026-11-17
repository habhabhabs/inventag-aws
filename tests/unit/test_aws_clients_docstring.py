"""D4 (D-09): the module text names the retry mode botocore really defaults to."""

import boto3

from inventag.discovery import aws_clients


def test_docstring_does_not_name_the_wrong_default_mode():
    default = boto3.Session(
        aws_access_key_id="a", aws_secret_access_key="b", region_name="us-east-1"
    ).client("sqs")
    assert default.meta.config.retries["mode"] == "standard"
    assert "legacy" not in aws_clients.__doc__
    assert "botocore's default is" in aws_clients.__doc__
    assert "standard" in aws_clients.__doc__
