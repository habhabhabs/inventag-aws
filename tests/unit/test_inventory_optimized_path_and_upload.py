"""D3: the optimized engine is not run, and the S3 upload is an opt-in write.

The optimized engine ran on every scan and made no API call (D-02): each of
its operations failed on an attribute error that only the debug log saw. Its
result was never used. ``AWSResourceInventory.upload_to_s3`` wrote an object
with no opt-in and no encryption.
"""

import json
from unittest import mock

import boto3
import pytest
from moto import mock_aws

from inventag.discovery.inventory import AWSResourceInventory


def _inventory(**kwargs):
    return AWSResourceInventory(
        regions=["us-east-1"],
        session=mock.MagicMock(),
        enable_billing_validation=False,
        **kwargs,
    )


def test_a_scan_does_not_run_the_optimized_engine():
    inv = _inventory()
    assert inv.use_optimized_discovery is True  # the default configuration
    with (
        mock.patch.object(inv, "_perform_optimized_discovery") as optimized,
        mock.patch.object(
            inv.comprehensive_discovery, "discover_all_resources", return_value=[]
        ),
        mock.patch.object(inv.optimized_discovery, "discover_all_services") as engine,
    ):
        inv.discover_resources()
    optimized.assert_not_called()
    engine.assert_not_called()


@mock_aws
def test_upload_without_the_opt_in_raises_and_writes_nothing():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="out-bucket")
    inv = AWSResourceInventory(regions=["us-east-1"], enable_billing_validation=False)
    inv.resources = [{"id": "x"}]
    with pytest.raises(PermissionError) as err:
        inv.upload_to_s3("out-bucket", "r.json")
    assert "allow_write=True" in str(err.value)
    assert "Contents" not in s3.list_objects_v2(Bucket="out-bucket")


@mock_aws
def test_upload_with_the_opt_in_is_encrypted_with_sse_s3():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="out-bucket")
    inv = AWSResourceInventory(regions=["us-east-1"], enable_billing_validation=False)
    inv.resources = [{"id": "x"}]
    inv.upload_to_s3("out-bucket", "r.json", allow_write=True)
    obj = s3.get_object(Bucket="out-bucket", Key="r.json")
    assert json.loads(obj["Body"].read()) == [{"id": "x"}]
    assert obj["ServerSideEncryption"] == "AES256"
