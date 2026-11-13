"""Hide secret values in resource data before any report or file is written.

InvenTag lists resources; it must not copy secrets into reports. Some AWS
describe calls return secret values next to the settings (a Lambda function's
environment variable values, an EC2 instance's user data, a CloudFormation
parameter value...). :func:`mask_resources` replaces those values with
``[MASKED]`` and keeps the names, so a report still shows that a variable
``DB_PASSWORD`` exists without showing what it holds.

This is a second line of defence. The discovery code should not collect these
values in the first place; this function makes sure that what it did collect
never reaches Excel, Word, CSV, JSON or Google output.

The rules go by field name, not by value: InvenTag cannot recognise a secret
by looking at it. A secret kept in a field that is not on the list below (a
description, a tag, a free-text field) is not found.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

MASK = "[MASKED]"

# Fields whose whole value is secret. Names are compared in lower case with
# every character other than letters and digits removed ("DB_Password" and
# "dbpassword" are the same name).
SECRET_VALUE_FIELDS = frozenset(
    {
        "userdata",  # EC2 instance and launch template user data
        "clientsecret",  # Cognito app client
        "secretaccesskey",
        "sessiontoken",
        "password",
        "masteruserpassword",  # RDS, Redshift, DocumentDB
        "adminpassword",
        "secretstring",
        "secretbinary",
        "privatekey",
        "authtoken",
        "parametervalue",  # CloudFormation stack parameter
        "resolvedvalue",  # CloudFormation parameter, resolved
    }
)
# Fields holding a mapping of name -> value; the names stay, the values go.
SECRET_MAPPING_FIELDS = frozenset(
    {
        "connectionproperties",  # Glue connection (PASSWORD, JDBC URL...)
        "environmentvariables",  # flattened Lambda / ECS / CodeBuild forms
    }
)
# Fields holding a list of {name, value} items.
NAME_VALUE_LIST_FIELDS = frozenset(
    {
        "environment",  # ECS container, CodeBuild environment
        "environmentvariables",  # CodeBuild environmentVariables
    }
)
# Never look inside tags: users choose their keys, and tag policies read them.
SKIPPED_FIELDS = frozenset({"tags"})

_NON_ALNUM = re.compile(r"[^a-z0-9]")
_MAX_DEPTH = 40


def _norm(key: Any) -> str:
    return _NON_ALNUM.sub("", str(key).lower())


def _secret(value: Any) -> bool:
    """True if there is a value to hide (empty values and booleans are kept)."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (str, list, dict, tuple)):
        return bool(value) and value != MASK
    return True


def _mask_mapping_values(value: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    count = 0
    out = {}
    for key, item in value.items():
        if _secret(item):
            out[key] = MASK
            count += 1
        else:
            out[key] = item
    return out, count


def _mask_name_value_list(value: List[Any]) -> Tuple[List[Any], int]:
    count = 0
    out: List[Any] = []
    for item in value:
        if isinstance(item, dict):
            new = dict(item)
            for key in item:
                if _norm(key) == "value" and _secret(item[key]):
                    new[key] = MASK
                    count += 1
            out.append(new)
        else:
            out.append(item)
    return out, count


def _mask(value: Any, key: str, parent: str, depth: int) -> Tuple[Any, int]:
    """Return ``(new_value, masked_count)``; unchanged containers are reused."""
    if depth > _MAX_DEPTH:
        return value, 0
    norm = _norm(key) if key else ""
    if norm in SKIPPED_FIELDS:
        return value, 0

    if norm in SECRET_VALUE_FIELDS:
        return (MASK, 1) if _secret(value) else (value, 0)

    # Lambda: Environment -> Variables -> {NAME: value}
    if norm == "variables" and parent == "environment" and isinstance(value, dict):
        return _mask_mapping_values(value)
    if norm in SECRET_MAPPING_FIELDS and isinstance(value, dict):
        return _mask_mapping_values(value)
    if norm in NAME_VALUE_LIST_FIELDS and isinstance(value, list):
        masked, count = _mask_name_value_list(value)
        if count:
            return masked, count

    if isinstance(value, dict):
        changed = False
        total = 0
        out = {}
        for child_key, child in value.items():
            new, count = _mask(child, child_key, norm, depth + 1)
            if count:
                changed = True
                total += count
            out[child_key] = new
        return (out, total) if changed else (value, 0)
    if isinstance(value, list):
        changed = False
        total = 0
        items = []
        for child in value:
            new, count = _mask(child, key, parent, depth + 1)
            if count:
                changed = True
                total += count
            items.append(new)
        return (items, total) if changed else (value, 0)
    return value, 0


def mask_resource(resource: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Return a copy of ``resource`` with secret values hidden, and how many.

    The input is not changed. A resource with nothing to hide is returned as
    it is (not copied).
    """
    if not isinstance(resource, dict):
        return resource, 0
    return _mask(resource, "", "", 0)


def mask_resources(resources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mask every resource of a list. See :func:`mask_resource`."""
    return [mask_resource(r)[0] for r in resources]


def count_masked(resources: Iterable[Dict[str, Any]]) -> int:
    """How many values :func:`mask_resources` would hide in ``resources``."""
    return sum(mask_resource(r)[1] for r in resources)
