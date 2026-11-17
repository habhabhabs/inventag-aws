"""A slow Cost Explorer call must not cost the whole account (A-24).

Cost Explorer is the first call of an account's discovery and it is
optional. In v1.2.1 its client had botocore's limits (60 s to connect, 60 s
to read, up to 10 attempts), so with a short ``--account-processing-timeout``
one slow answer used the whole limit: the account was abandoned before any
listing ran, and the report had none of its resources (S1 E9: limit 15 s,
Cost Explorer sleeping 30 s, exit 1).

Now, when the limit is short, Cost Explorer gets at most a tenth of it; the
listings run, their resources are in the report, and the run notes say that
the billing data of that account is missing.

Deterministic: no real sleep. The account clock is a fake one, and the slow
endpoint is emulated from the client's own settings: a call whose read
timeout is shorter than the endpoint's delay ends with ``ReadTimeoutError``
after (attempts x timeouts) of fake time; otherwise it takes the full delay.
"""

import logging
import time

import botocore.client
import botocore.exceptions as bex
import pytest

from inventag.core import cloud_bom_generator as cbg
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    GOOD_ID,
    OTHER,
    OTHER_ID,
    RoleControl,
    accounts_file,
    aws,
    empty_aws,
    logged,
    reports,
    run_cli,
    seed_account,
    workbook,
)
from tests.unit.test_snapshot_not_poisoned import result_spy, run_notes

LIMIT = 60  # --account-processing-timeout (seconds)
DELAY = 10_000.0  # how long the slow Cost Explorer endpoint takes (fake seconds)
GOOD = {"account_id": GOOD_ID, "regions": ["us-east-1"]}


class FakeClock:
    def __init__(self):
        self.offset = 0.0

    def __call__(self):
        return time.monotonic() + self.offset


def slow_cost_explorer(monkeypatch, clock, slow_key=None):
    """Cost Explorer of the account with ``slow_key`` (all accounts if None)
    answers after DELAY fake seconds; the call obeys the client's timeouts."""
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if client.meta.service_model.service_name == "ce":
            creds = client._request_signer._credentials
            key = getattr(creds, "access_key", None)
            if slow_key is None or key == slow_key():
                config = client.meta.config
                read = config.read_timeout or 60
                connect = config.connect_timeout or 60
                retries = config.retries or {}
                attempts = retries.get("total_max_attempts") or (
                    (retries.get("max_attempts") or 9) + 1
                )
                if read < DELAY:
                    clock.offset += attempts * (connect + read)
                    raise bex.ReadTimeoutError(
                        endpoint_url="https://ce.us-east-1.amazonaws.com/"
                    )
                clock.offset += DELAY
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)


def short_limit(monkeypatch, clock):
    original = cbg.CloudBOMGenerator.__init__

    def init(self, config, *args, **kwargs):
        original(self, config, *args, **kwargs)
        self._clock = clock
        self._abandon_grace_seconds = 0.5
        self._poll_seconds = 0.05

    monkeypatch.setattr(cbg.CloudBOMGenerator, "__init__", init)


def args(path, *extra):
    return [
        "--accounts-file",
        path,
        "--create-excel",
        "--account-processing-timeout",
        str(LIMIT),
        "--output-directory",
        "out",
        *extra,
    ]


@pytest.mark.parametrize("flag", [[], ["--fail-on-account-error"]])
def test_a_slow_cost_explorer_call_keeps_the_listed_resources(
    aws, tmp_path, monkeypatch, caplog, flag  # noqa: F811
):
    caplog.set_level(logging.INFO)
    clock = FakeClock()
    short_limit(monkeypatch, clock)
    slow_cost_explorer(monkeypatch, clock)
    results = result_spy(monkeypatch)
    code = run_cli(*args(accounts_file(tmp_path, [GOOD]), *flag))
    # The account finished, so exit 0 with and without the flag (v1.2.1's
    # code for a run whose accounts all finished; v1.2.1 lost the account and
    # gave 1, the code for "every account failed").
    assert code == 0
    assert results[-1]["failed_accounts"] == []
    files = reports(tmp_path / "out")
    assert len(files) == 1
    sheets = workbook(files[0])
    assert "VPC" in sheets and len(sheets["VPC"]) > 1  # listed resources
    notes = run_notes(files[0])
    assert (
        f"Cost Explorer did not answer in time for account {GOOD_ID}, so its "
        "billing checks were skipped and services that only billing shows are "
        "not listed for it."
    ) in notes, notes


def test_one_slow_account_of_two_keeps_its_resources(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """Only OTHER's Cost Explorer is slow. v1.2.1: OTHER failed (exit 5 with
    the flag). Now both accounts finish: exit 0 with the flag."""
    seed_account(OTHER_ID, OTHER["role_arn"])
    caplog.set_level(logging.INFO)
    clock = FakeClock()
    short_limit(monkeypatch, clock)
    roles = RoleControl(monkeypatch)
    slow_cost_explorer(monkeypatch, clock, slow_key=lambda: roles.keys[OTHER_ID])
    results = result_spy(monkeypatch)
    path = accounts_file(tmp_path, [GOOD, dict(OTHER)])
    assert run_cli(*args(path, "--fail-on-account-error")) == 0
    assert results[-1]["failed_accounts"] == []
    cells = {
        str(c)
        for rows in workbook(reports(tmp_path / "out")[0]).values()
        for r in rows
        for c in r
    }
    assert f"acct-{OTHER_ID}-b0" in cells  # OTHER's bucket is in the report
    assert not any("no results of this account" in m for m in logged(caplog))


def test_with_the_default_limit_cost_explorer_keeps_botocores_settings(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """Clean runs are unchanged: with the default limit (1800 s) the Cost
    Explorer client gets no special timeouts."""
    seen = []
    original = botocore.client.BaseClient._make_api_call

    def call(client, operation_name, api_params):
        if client.meta.service_model.service_name == "ce":
            config = client.meta.config
            seen.append((config.read_timeout, config.connect_timeout))
        return original(client, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", call)
    path = accounts_file(tmp_path, [GOOD])
    assert (
        run_cli("--accounts-file", path, "--create-excel", "--output-directory", "out")
        == 0
    )
    assert seen and all(s == (60, 60) for s in seen), seen


def test_a_cost_explorer_answer_of_three_seconds_is_read_under_a_60_second_limit(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    """Review M3: under the shortest allowed limit (60 s) a Cost Explorer that
    answers in 3 s is slow but working, as in v1.2.1: its answer is read, no
    timeout warning or note, exit 0. (A tenth of the limit gave 1.5 s per step,
    so the answer was lost.)"""
    import tests.unit.test_slow_cost_explorer_keeps_the_account as this

    monkeypatch.setattr(this, "DELAY", 3.0)
    caplog.set_level(logging.INFO)
    clock = FakeClock()
    short_limit(monkeypatch, clock)
    slow_cost_explorer(monkeypatch, clock)
    assert run_cli(*args(accounts_file(tmp_path, [GOOD]))) == 0
    assert not [m for m in logged(caplog) if "did not answer in time" in m]
    notes = run_notes(reports(tmp_path / "out")[0])
    assert not [n for n in notes if "Cost Explorer" in n], notes


def test_the_cost_explorer_bound_has_a_floor_and_stays_a_third_of_the_limit():
    """The bound per step is at least 5 s; two reads of two attempts stay
    within a third of the shortest allowed limit (60 s)."""
    config = cbg._cost_explorer_config(60)
    assert config.read_timeout == 5.0 and config.connect_timeout == 5.0
    assert 2 * 2 * config.read_timeout <= 60 / 3
    assert cbg._cost_explorer_config(1000).read_timeout == 25.0  # limit / 40
    assert cbg._cost_explorer_config(1800) is None  # default limit: botocore's
