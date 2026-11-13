"""Mask values that can hold secrets in data copied from AWS responses.

Discovery keeps the raw list/describe response of each resource (``raw_data``)
and some enrichment fields. Several AWS fields carry free-form values that
users often fill with passwords or tokens. Those values must not reach state
snapshots, Excel, Word or JSON reports.

:func:`mask_secret_values` returns a copy of the data in which the VALUES of
the fields below are replaced by :data:`MASK`. Key names are kept, so a
report can still show that a function has an environment variable ``DB_URL``,
but not its value.

Masked fields (``*`` = every value inside):

========================================  ==========================================
Field                                     Where it comes from
========================================  ==========================================
``Environment.Variables.*``               Lambda ListFunctions/GetFunctionConfiguration
``environment[].value``                   ECS task definition containers
``environmentVariables[].value``          CodeBuild projects (type PLAINTEXT or unset)
``UserData`` (and ``UserData.Value``)     EC2 instances and launch templates
``Parameters[].ParameterValue``           CloudFormation stacks (NoEcho is ``****``)
``DefaultArguments.*``,                   Glue jobs
``NonOverridableArguments.*``
``ConnectionProperties.*``                Glue connections
``definition``                            Step Functions state machines
``Code.Location``                         Lambda GetFunction (presigned code URL)
``value`` of an API key (``id`` +         API Gateway GetApiKeys
``enabled`` + ``value``)
any key in ``SECRET_KEYS``                passwords, tokens, client secrets
========================================  ==========================================
"""

import copy
from typing import Any

MASK = "***MASKED***"

# Keys whose value is secret wherever they appear.
SECRET_KEYS = frozenset(
    {
        "MasterUserPassword",
        "Password",
        "PasswordData",
        "SecretString",
        "SecretBinary",
        "ClientSecret",
        "AuthToken",
        "SecretAccessKey",
        "SessionToken",
        "secretAccessKey",
        "sessionToken",
        "clientSecret",
        "password",
    }
)

# Keys whose dict values are all masked (keys kept).
_MASK_ALL_VALUES = frozenset(
    {"DefaultArguments", "NonOverridableArguments", "ConnectionProperties"}
)


def _mask_mapping_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: MASK for k in value}
    return MASK if value not in (None, "") else value


def _mask_name_value_list(items: Any, value_key: str, only_plaintext=False) -> Any:
    if not isinstance(items, list):
        return items
    out = []
    for item in items:
        if isinstance(item, dict) and value_key in item:
            item = dict(item)
            kind = str(item.get("type", "PLAINTEXT")).upper()
            if not only_plaintext or kind == "PLAINTEXT":
                item[value_key] = MASK
        out.append(item)
    return out


def _mask(data: Any) -> Any:
    if isinstance(data, list):
        return [_mask(item) for item in data]
    if not isinstance(data, dict):
        return data

    is_api_key = {"id", "value", "enabled"} <= set(data)
    result = {}
    for key, value in data.items():
        if key in SECRET_KEYS and value not in (None, ""):
            result[key] = MASK
        elif key in _MASK_ALL_VALUES:
            result[key] = _mask_mapping_values(value)
        elif key in ("Environment", "environment") and isinstance(value, dict):
            env = dict(value)
            if isinstance(env.get("Variables"), dict):
                env["Variables"] = {k: MASK for k in env["Variables"]}
            result[key] = _mask(env)
        elif key == "environment" and isinstance(value, list):
            result[key] = _mask_name_value_list(value, "value")
        elif key == "environmentVariables":
            result[key] = _mask_name_value_list(value, "value", only_plaintext=True)
        elif key == "UserData":
            if isinstance(value, dict) and "Value" in value:
                result[key] = {**value, "Value": MASK}
            else:
                result[key] = _mask_mapping_values(value)
        elif key == "Parameters" and isinstance(value, list):
            result[key] = [
                (
                    {**p, "ParameterValue": MASK}
                    if isinstance(p, dict) and "ParameterValue" in p
                    else _mask(p)
                )
                for p in value
            ]
        elif key == "definition" and isinstance(value, str):
            result[key] = MASK
        elif key == "Code" and isinstance(value, dict) and "Location" in value:
            result[key] = {**value, "Location": MASK}
        elif key == "value" and is_api_key:
            result[key] = MASK
        else:
            result[key] = _mask(value)
    return result


def mask_secret_values(data: Any) -> Any:
    """A copy of ``data`` with secret-bearing values replaced by ``MASK``."""
    return _mask(copy.deepcopy(data))
