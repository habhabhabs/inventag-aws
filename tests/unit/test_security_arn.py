"""Role ARN validation and per-account ARN building."""

import pytest

from inventag.security.arn import (
    InvalidRoleError,
    account_id_from_role_arn,
    build_role_arn,
    partition_from_arn,
    validate_role_arn,
    validate_role_name,
)


@pytest.mark.parametrize(
    "account, name, partition, expected",
    [
        (
            "123456789012",
            "InvenTagReadOnly",
            "aws",
            "arn:aws:iam::123456789012:role/InvenTagReadOnly",
        ),
        (
            "123456789012",
            "team/ops/Reader",
            "aws",
            "arn:aws:iam::123456789012:role/team/ops/Reader",
        ),
        (
            "123456789012",
            "Reader",
            "aws-us-gov",
            "arn:aws-us-gov:iam::123456789012:role/Reader",
        ),
        (
            "123456789012",
            "Reader",
            "aws-cn",
            "arn:aws-cn:iam::123456789012:role/Reader",
        ),
        (
            "123456789012",
            "arn:aws:iam::123456789012:role/Reader",
            "aws",
            "arn:aws:iam::123456789012:role/Reader",
        ),
    ],
)
def test_build_role_arn(account, name, partition, expected):
    assert build_role_arn(account, name, partition) == expected


@pytest.mark.parametrize(
    "account, name",
    [
        ("cross-account", "Reader"),  # the old CLI's placeholder account id
        ("12345", "Reader"),
        ("123456789012", "bad name"),
        ("123456789012", "a" * 65),
        ("123456789012", "Reader;rm -rf"),
        ("123456789012", ""),
        ("123456789012", "arn:aws:iam::999999999999:role/Reader"),  # account mismatch
    ],
)
def test_build_role_arn_rejects(account, name):
    with pytest.raises(InvalidRoleError):
        build_role_arn(account, name)


@pytest.mark.parametrize(
    "arn",
    [
        "InvenTagReadOnly",  # a bare name is not an ARN (old --cross-account-role bug)
        "arn:aws:iam::cross-account:role/X",
        "arn:aws:iam::123456789012:user/X",
        "arn:aws:sts::123456789012:assumed-role/X/y",
        "arn:evil:iam::123456789012:role/X",
    ],
)
def test_validate_role_arn_rejects(arn):
    with pytest.raises(InvalidRoleError):
        validate_role_arn(arn)


def test_account_and_partition_helpers():
    arn = "arn:aws-us-gov:iam::123456789012:role/path/Reader"
    assert validate_role_arn(arn) == arn
    assert account_id_from_role_arn(arn) == "123456789012"
    assert (
        partition_from_arn("arn:aws-cn:sts::123456789012:assumed-role/a/b") == "aws-cn"
    )
    assert partition_from_arn(None) == "aws"
    assert validate_role_name("path/Reader") == "path/Reader"
