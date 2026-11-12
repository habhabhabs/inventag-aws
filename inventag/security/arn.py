"""
Validation helpers for AWS account IDs, IAM role names and role ARNs.

``sts:AssumeRole`` needs a full role ARN. These helpers turn a role *name*
into an ARN for a given account (and partition), and reject malformed input
before it reaches AWS.
"""

import re
from typing import Optional

# IAM role names: 1-64 chars of [\w+=,.@-]; optional path "/a/b/" (max 512).
_ROLE_NAME_RE = re.compile(r"^[\w+=,.@-]{1,64}$")
_ROLE_PATH_RE = re.compile(r"^/(?:[\x21-\x7e]+/)?$")
_ACCOUNT_ID_RE = re.compile(r"^\d{12}$")
_PARTITIONS = (
    "aws",
    "aws-cn",
    "aws-us-gov",
    "aws-iso",
    "aws-iso-b",
    "aws-iso-e",
    "aws-iso-f",
    "aws-eusc",
)
_ROLE_ARN_RE = re.compile(
    r"^arn:(?P<partition>aws(?:-[a-z]+(?:-[a-z]+)?)?):iam::(?P<account>\d{12}):"
    r"role(?P<path>/(?:[\x21-\x7e]+/)?)(?P<name>[\w+=,.@-]{1,64})$"
)


class InvalidRoleError(ValueError):
    """Raised when a role name, ARN or account ID is malformed."""


def is_valid_account_id(account_id: Optional[str]) -> bool:
    return bool(account_id) and bool(_ACCOUNT_ID_RE.match(str(account_id)))


def is_role_arn(value: str) -> bool:
    return isinstance(value, str) and value.startswith("arn:")


def validate_role_arn(role_arn: str) -> str:
    """Return ``role_arn`` if it is a well-formed IAM role ARN, else raise."""
    if not isinstance(role_arn, str):
        raise InvalidRoleError("Role ARN must be a string")
    match = _ROLE_ARN_RE.match(role_arn)
    if not match or match.group("partition") not in _PARTITIONS:
        raise InvalidRoleError(
            f"Invalid IAM role ARN {role_arn!r}: expected "
            "arn:<partition>:iam::<12-digit account id>:role/<name>"
        )
    if len(match.group("path")) > 512:
        raise InvalidRoleError("IAM role path is longer than 512 characters")
    return role_arn


def account_id_from_role_arn(role_arn: str) -> str:
    validate_role_arn(role_arn)
    return _ROLE_ARN_RE.match(role_arn).group("account")


def validate_role_name(role_name: str) -> str:
    """Validate a role name, optionally with a path (``path/to/RoleName``)."""
    if not isinstance(role_name, str) or not role_name:
        raise InvalidRoleError("Role name must be a non-empty string")
    path, _, name = role_name.rpartition("/")
    if not _ROLE_NAME_RE.match(name):
        raise InvalidRoleError(
            f"Invalid IAM role name {name!r}: use 1-64 letters, digits or +=,.@_-"
        )
    if path:
        full_path = "/" + path.strip("/") + "/"
        if not _ROLE_PATH_RE.match(full_path) or len(full_path) > 512:
            raise InvalidRoleError(f"Invalid IAM role path {path!r}")
    return role_name


def partition_from_arn(arn: Optional[str], default: str = "aws") -> str:
    """Return the partition of any ARN (``arn:<partition>:...``)."""
    if isinstance(arn, str) and arn.startswith("arn:"):
        parts = arn.split(":")
        if len(parts) > 1 and parts[1] in _PARTITIONS:
            return parts[1]
    return default


def build_role_arn(account_id: str, role_name: str, partition: str = "aws") -> str:
    """
    Build ``arn:<partition>:iam::<account_id>:role/<role_name>``.

    ``role_name`` may already be a full role ARN; it is then validated and
    returned unchanged (its account must match ``account_id``).
    """
    if is_role_arn(role_name):
        validate_role_arn(role_name)
        arn_account = account_id_from_role_arn(role_name)
        if account_id and is_valid_account_id(account_id) and arn_account != account_id:
            raise InvalidRoleError(
                f"Role ARN account {arn_account} does not match account {account_id}"
            )
        return role_name
    if not is_valid_account_id(account_id):
        raise InvalidRoleError(
            f"Cannot build a role ARN for account {account_id!r}: "
            "a 12-digit AWS account ID is required"
        )
    if partition not in _PARTITIONS:
        raise InvalidRoleError(f"Unknown AWS partition {partition!r}")
    validate_role_name(role_name)
    path, _, name = role_name.rpartition("/")
    path_part = "/" + path.strip("/") + "/" if path else "/"
    return validate_role_arn(f"arn:{partition}:iam::{account_id}:role{path_part}{name}")
