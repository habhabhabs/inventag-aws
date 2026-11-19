"""``--validate-credentials`` resolves an accounts-file entry the way the scan
does (A-39, code-tests-coverage F14).

An entry with no credentials: the scan uses the default credentials when
they belong to the account, else assumes the cross-account role in it.
v1.2.1's validation always checked the default credentials, so for another
account it said "Account ID mismatch" although the scan of the same file
worked. Now both give the same verdict. Exit codes: 0 when every account is
valid, 1 otherwise (as before).
"""

import logging

from tests.regression.faults import Fault, FaultInjector

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    accounts_file,
    aws,
    empty_aws,
    logged,
    reports,
    run_cli,
)

OTHER_ID = "210987654321"


def validate(path):
    return run_cli("--accounts-file", path, "--validate-credentials")


def scan(path):
    return run_cli("--accounts-file", path, *BASE, "--output-directory", "out")


def console(caplog, capsys):
    return capsys.readouterr().out + "\n" + "\n".join(logged(caplog, logging.INFO))


def test_an_entry_for_another_account_is_valid_when_the_scan_works(
    aws, tmp_path, caplog, capsys  # noqa: F811
):
    caplog.set_level(logging.INFO)
    path = accounts_file(tmp_path, [{"account_id": OTHER_ID, "regions": ["us-east-1"]}])
    assert scan(path) == 0
    assert reports(tmp_path / "out")
    caplog.clear()
    capsys.readouterr()
    assert validate(path) == 0
    assert "Account ID mismatch" not in console(caplog, capsys)


def test_an_entry_for_the_default_account_stays_valid(
    aws, tmp_path, caplog, capsys  # noqa: F811
):
    caplog.set_level(logging.INFO)
    path = accounts_file(tmp_path, [{"account_id": GOOD_ID, "regions": ["us-east-1"]}])
    assert validate(path) == 0
    assert "Account ID mismatch" not in console(caplog, capsys)


def test_a_role_that_cannot_be_assumed_fails_both(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """sts:AssumeRole denied (injected by operation): the scan cannot use the
    account (exit 1: every account failed); the validation says it is not
    valid (exit 1), as before for this case."""
    path = accounts_file(tmp_path, [{"account_id": OTHER_ID, "regions": ["us-east-1"]}])
    deny = Fault(service="sts", op="AssumeRole", error="AccessDenied")
    with FaultInjector([deny]) as injector:
        injector.arm()
        assert scan(path) == 1
        assert validate(path) == 1


def test_validation_assumes_the_role_named_with_cross_account_role(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """``--cross-account-role X`` changes the role the scan assumes in another
    account; ``--validate-credentials`` must check the same role (pair of
    lead A's A-39 with the CLI). Exit 0 as for the default role."""
    import botocore.client

    roles = []
    original = botocore.client.BaseClient._make_api_call

    def spy(client, operation_name, api_params):
        if operation_name == "AssumeRole":
            roles.append(api_params.get("RoleArn"))
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", spy)
    path = accounts_file(tmp_path, [{"account_id": OTHER_ID, "regions": ["us-east-1"]}])
    code = run_cli(
        "--accounts-file",
        path,
        "--cross-account-role",
        "AuditReader",
        "--validate-credentials",
    )
    assert code == 0
    assert roles and all(r.endswith(":role/AuditReader") for r in roles), roles
