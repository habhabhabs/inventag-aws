"""A template Name column shows a name for Lambda, IAM Role and KMS Alias."""

import pytest

from inventag.templating.columns import get_field

CASES = [
    ({"service": "LAMBDA", "resource_type": "Function", "resource_id": "fn-a"}, "fn-a"),
    (
        {
            "service": "IAM",
            "resource_type": "Role",
            "resource_id": "role-a",
            "resource_name": None,
        },
        "role-a",
    ),
    (
        {"service": "KMS", "type": "Alias", "id": "alias/a", "resource_name": ""},
        "alias/a",
    ),
    (
        {
            "service": "S3",
            "resource_type": "Bucket",
            "resource_id": "bkt",
            "name": "bkt",
            "resource_name": "bkt",
        },
        "bkt",
    ),
]


@pytest.mark.parametrize("resource,expected", CASES)
@pytest.mark.parametrize("field", ["resource_name", "name"])
def test_name_field(resource, expected, field):
    assert get_field(resource, field) == expected


def test_other_types_without_name_stay_empty():
    ec2 = {"service": "EC2", "resource_type": "Instance", "resource_id": "i-1"}
    assert get_field(ec2, "resource_name") is None
    assert get_field({**ec2, "resource_name": None}, "resource_name") is None


def test_real_name_is_not_replaced():
    fn = {
        "service": "LAMBDA",
        "resource_type": "Function",
        "resource_id": "id",
        "resource_name": "real",
    }
    assert get_field(fn, "resource_name") == "real"
