"""Hide secret values in data copied from AWS responses. The one deny-list.

Some read-only AWS calls return secret values next to the settings InvenTag
lists: a Lambda function's environment variable values, an EC2 instance's
user data, a CloudFormation parameter value, a Glue connection password. The
read-only guard can block a call, but not a field inside an allowed response.

This module is the only place that decides which fields are secret. It is
applied in two places, with the same function:

1. at the source, in discovery, before a resource is stored
   (``inventag/discovery``), and
2. as a second line before anything is written: core scrubs every discovered
   resource before reports, snapshots, checkpoints and logs see it; the report
   writers, the state snapshot and the resume checkpoints call it again.

Values are replaced by :data:`MASK`; key names are kept, so a report still
shows that a function has a variable ``DB_PASSWORD``, but not what it holds.
Empty values, ``None`` and booleans are left as they are (``AuthTokenEnabled:
true`` is a setting, not a secret). Tags are never changed: users choose
their keys and tag policies read them.

The rules go by field name, not by value. InvenTag cannot recognise a secret
by looking at it, so a secret kept in a field that is not on this list (a
description, a tag, a free-text field) is not found.

Field names are compared in lower case with everything except letters and
digits removed (``DB_Password``, ``db-password`` and ``dbpassword`` are the
same name).

========================================  ==========================================
Field                                     Where it comes from
========================================  ==========================================
``Environment.Variables.*`` and any       Lambda, App Runner
``Variables`` / ``EnvironmentVariables``
/ ``RuntimeEnvironmentVariables`` map
``environment[].value``                   ECS container definitions
``environmentVariables[].value``          CodeBuild projects (only PLAINTEXT or no
                                          type; PARAMETER_STORE and SECRETS_MANAGER
                                          entries hold a reference, kept)
``UserData`` (and ``UserData.Value``)     EC2 instances and launch templates
``ParameterValue``, ``ResolvedValue``     CloudFormation stack parameters
``DefaultArguments.*``,                   Glue jobs
``NonOverridableArguments.*``
``ConnectionProperties.*``                Glue connections
``definition`` (text)                     Step Functions state machines
``Code.Location``                         Lambda GetFunction (presigned code URL)
``value`` of an API key (``id`` +         API Gateway GetApiKeys
``enabled`` + ``value``)
names ending in password, passwd,         RDS/Redshift/DocumentDB master passwords,
secret string/binary, secret access key,  Cognito client secrets, FSx, MSK, Storage
client/shared secret, private key,        Gateway CHAP secrets, Amplify basic auth,
api key, auth/session/security/bearer     ElastiCache auth tokens, credentials
token, credential(s); and the fixed       blocks
names in :data:`SECRET_VALUE_KEYS`
========================================  ==========================================
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

#: The text that replaces a secret value (the same text the log redaction uses).
MASK = "***REDACTED***"

# Exact (normalised) names whose value is secret wherever they appear.
SECRET_VALUE_KEYS = frozenset(
    {
        "userdata",
        "passworddata",
        "masteruserpassword",
        "adminpassword",
        "fsxadminpassword",
        "saslpassword",
        "sslclientkeypassword",
        "accountpassword",
        "secretaccesskey",
        "sessiontoken",
        "clientsecret",
        "sharedsecret",
        "secretstring",
        "secretbinary",
        "secrettoauthenticateinitiator",
        "secrettoauthenticatetarget",
        "basicauthcredentials",
        "authtoken",
        "privatekey",
        "parametervalue",
        "resolvedvalue",
    }
)
# Normalised names that END like this are secret too (DbPassword, api_key...).
_SECRET_SUFFIX = re.compile(
    r"(password|passwd|secretstring|secretbinary|secretaccesskey|clientsecret|"
    r"sharedsecret|privatekey|apikey|authtoken|sessiontoken|securitytoken|"
    r"bearertoken|credentials?)$"
)
# Mappings of name -> value whose names stay and whose values go.
SECRET_MAPPING_KEYS = frozenset(
    {
        "variables",
        "environmentvariables",
        "runtimeenvironmentvariables",
        "defaultarguments",
        "nonoverridablearguments",
        "connectionproperties",
    }
)
# Lists of {"name": ..., "value": ...} items.
NAME_VALUE_LIST_KEYS = frozenset({"environment", "environmentvariables"})
# Never looked into.
SKIPPED_KEYS = frozenset({"tags", "tagset", "taglist"})

_NON_ALNUM = re.compile(r"[^a-z0-9]")
_MAX_DEPTH = 200
_REFERENCE_TYPES = frozenset({"PARAMETER_STORE", "SECRETS_MANAGER"})


def _norm(key: Any) -> str:
    return _NON_ALNUM.sub("", str(key).lower())


def _has_value(value: Any) -> bool:
    """True if there is something to hide (empty values and booleans stay)."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (str, bytes, list, dict, tuple)):
        return bool(value) and value != MASK
    return True


def is_secret_key(key: Any) -> bool:
    """True if a value stored under ``key`` is always treated as secret."""
    norm = _norm(key)
    return norm in SECRET_VALUE_KEYS or bool(_SECRET_SUFFIX.search(norm))


def _mask_mapping(value: Dict[Any, Any]) -> Tuple[Dict[Any, Any], int]:
    count = 0
    out = {}
    for k, v in value.items():
        if _has_value(v):
            out[k] = MASK
            count += 1
        else:
            out[k] = v
    return (out, count) if count else (value, 0)


def _mask_name_value_list(value: List[Any]) -> Tuple[List[Any], int]:
    count = 0
    out: List[Any] = []
    for item in value:
        if isinstance(item, dict):
            kind = str(item.get("type", item.get("Type", "PLAINTEXT"))).upper()
            new = item
            if kind not in _REFERENCE_TYPES:
                for k, v in item.items():
                    if _norm(k) == "value" and _has_value(v):
                        if new is item:
                            new = dict(item)
                        new[k] = MASK
                        count += 1
            if new is item:
                new, sub = _walk(item, 1)
                count += sub
            out.append(new)
        else:
            new, sub = _walk(item, 1)
            count += sub
            out.append(new)
    return (out, count) if count else (value, 0)


def _mask_field(key: Any, value: Any, depth: int) -> Tuple[Any, int]:
    """Value stored under ``key`` after masking, and how many values were hidden."""
    norm = _norm(key)
    if norm in SKIPPED_KEYS:
        return value, 0
    if norm == "userdata" and isinstance(value, dict) and "Value" in value:
        if _has_value(value["Value"]):
            return {**value, "Value": MASK}, 1
        return value, 0
    if norm in SECRET_VALUE_KEYS or _SECRET_SUFFIX.search(norm):
        return (MASK, 1) if _has_value(value) else (value, 0)
    if norm in SECRET_MAPPING_KEYS and isinstance(value, dict):
        return _mask_mapping(value)
    if norm in NAME_VALUE_LIST_KEYS and isinstance(value, list):
        return _mask_name_value_list(value)
    if norm == "definition" and isinstance(value, str) and value:
        return MASK, 1
    if norm == "code" and isinstance(value, dict) and _has_value(value.get("Location")):
        return {**value, "Location": MASK}, 1
    return _walk(value, depth + 1)


def _walk(value: Any, depth: int) -> Tuple[Any, int]:
    """Return ``(new_value, hidden_count)``; unchanged containers are reused."""
    if depth > _MAX_DEPTH:
        # Deeper than any AWS response: hide the whole subtree (fail closed).
        return (MASK, 1) if _has_value(value) else (value, 0)
    if isinstance(value, dict):
        is_api_key = {"id", "value", "enabled"} <= set(value)
        total = 0
        out = {}
        for k, v in value.items():
            if is_api_key and k == "value" and _has_value(v):
                new, count = MASK, 1
            else:
                new, count = _mask_field(k, v, depth)
            total += count
            out[k] = new
        return (out, total) if total else (value, 0)
    if isinstance(value, (list, tuple)):
        total = 0
        items = []
        for item in value:
            new, count = _walk(item, depth + 1)
            total += count
            items.append(new)
        if not total:
            return value, 0
        return (tuple(items) if isinstance(value, tuple) else items), total
    return value, 0


def mask_resource(resource: Any) -> Tuple[Any, int]:
    """Return a copy of ``resource`` with secret values hidden, and how many.

    The input is never changed. Data with nothing to hide is returned as it
    is (not copied), so calling this twice costs little.
    """
    return _walk(resource, 0)


def mask_secret_values(data: Any) -> Any:
    """``data`` with secret values replaced by :data:`MASK` (input unchanged)."""
    return _walk(data, 0)[0]


def mask_resources(resources: Iterable[Any]) -> List[Any]:
    """Mask every item of a list. See :func:`mask_resource`."""
    return [_walk(r, 0)[0] for r in resources]


def count_masked(resources: Iterable[Any]) -> int:
    """How many values :func:`mask_resources` would hide."""
    return sum(_walk(r, 0)[1] for r in resources)
