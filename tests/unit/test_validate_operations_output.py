"""``--validate-operations``: the answer is honest for an operation whose
permission depends on its parameters (A-46), and unchanged for all others."""

import importlib
import sys

from inventag.cli import safety
from inventag.security.read_only_guard import DENIED_PARAMETERS

cli_main = importlib.import_module("inventag.cli.main")

# The full output of v1.2.0 for these entries (golden). Order and spelling of
# the entries matter; none of them depends on a parameter.
GOLDEN_OPERATIONS = [
    "ec2:DescribeInstances",
    "s3:ListBuckets",
    "ec2:RunInstances",
    "s3:GetObject",
    "secretsmanager:GetSecretValue",
    "bad",
    "iam:ListRoles",
    "ssm:GetDocument",
    "lambda:GetFunction",
]
GOLDEN_LINES = [
    "ALLOWED  ec2:DescribeInstances (read-only prefix)",
    "ALLOWED  s3:ListBuckets (read-only prefix)",
    "BLOCKED  ec2:RunInstances (operation is not on the read-only allowlist)",
    "BLOCKED  s3:GetObject (operation returns secrets, signed URLs or customer data)",
    "BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)",
    "INVALID  bad: expected service:Operation",
    "ALLOWED  iam:ListRoles (read-only prefix)",
    "BLOCKED  ssm:GetDocument (operation returns secrets, signed URLs or customer data)",
    "BLOCKED  lambda:GetFunction (operation returns secrets, signed URLs or customer data)",
]


def test_output_for_operations_without_parameter_rules_is_unchanged():
    ok, lines = safety.validate_operations(GOLDEN_OPERATIONS)
    assert ok is False  # exit code 1 in the CLI, as before
    assert lines == GOLDEN_LINES


def test_parameter_dependent_operations_name_the_blocked_parameter():
    ok, lines = safety.validate_operations(
        [
            "apigateway:GetApiKeys",
            "apigateway:GetApiKey",
            "ec2:DescribeInstanceAttribute",
            "ec2:describe_instance_attribute",
        ]
    )
    assert ok is True  # still allowed by name: the exit code does not change
    assert lines == [
        "ALLOWED  apigateway:GetApiKeys (read-only prefix); "
        "BLOCKED when includeValues=true",
        "ALLOWED  apigateway:GetApiKey (read-only prefix); "
        "BLOCKED when includeValue=true",
        "ALLOWED  ec2:DescribeInstanceAttribute (read-only prefix); "
        "BLOCKED when Attribute=userdata",
        "ALLOWED  ec2:DescribeInstanceAttribute (read-only prefix); "
        "BLOCKED when Attribute=userdata",
    ]


def test_every_parameter_rule_of_the_guard_is_shown():
    """The text comes from the guard's own table, so a new rule appears."""
    for (service, operation), rules in DENIED_PARAMETERS.items():
        _, lines = safety.validate_operations([f"{service}:{operation}"])
        for parameter, values in rules.items():
            for value in values:
                assert f"BLOCKED when {parameter}={value}" in lines[0]


def run_cli(*args):
    old = sys.argv
    sys.argv = ["inventag", *args]
    try:
        cli_main.main()
        return 0
    except SystemExit as e:
        return e.code
    finally:
        sys.argv = old


def test_exit_codes_of_validate_operations_are_unchanged(capsys):
    assert run_cli("--validate-operations", "ec2:DescribeInstances") == 0
    assert run_cli("--validate-operations", "apigateway:GetApiKeys") == 0
    assert run_cli("--validate-operations", "ec2:RunInstances") == 1
    out = capsys.readouterr().out
    assert "BLOCKED when includeValues=true" in out
