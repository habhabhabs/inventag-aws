"""A shipped rule reads only fields that a moto scan shows (brief rule).

One scan of a moto estate; for every shipped policy every ``raw_data`` key it
reads is found, with a value, on a row that the policy's ``resource`` block
selects. Fields that the scan does not produce are listed here as not shipped.
"""

import copy
import json

import pytest
from moto import mock_aws

from inventag.policy import builtin, engine, filters
from tests.unit.finops import conftest as scan_conftest
from tests.unit.policy_builtin import moto_estate

pytestmark = pytest.mark.e2e

# What a moto scan does NOT show, so no shipped rule reads it. Each entry is
# (row label, key, why). A test below fails if the scan starts to show one.
NOT_ON_THE_ROW = [
    ("S3/Bucket", "raw_data.ServerSideEncryptionConfiguration"),
    ("S3/Bucket", "raw_data.PublicAccessBlockConfiguration"),
    ("SQS/Queue", "raw_data.Attributes"),
    ("SNS/Topic", "raw_data.KmsMasterKeyId"),
    ("DYNAMODB/Table", "raw_data.SSEDescription"),
]


@pytest.fixture(scope="module")
def estate_rows(tmp_path_factory):
    scan_conftest.SERVICES = moto_estate.SERVICES
    out = tmp_path_factory.mktemp("builtin-fields")
    with mock_aws():
        moto_estate.seed()
        scan = scan_conftest._run_main(out / "out", out / "audit.json", [], False, {})
    assert scan.code == 0, scan.text
    return scan.rows


def keys_read(policy):
    """``{(key, rows block or None)}``: every raw_data key a policy reads, with
    the block that selects the rows it is read on (None: the policy's own)."""
    found = {(k, None) for k in policy.require}

    def walk(entries):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for field in ("key", "my_key", "field"):
                if isinstance(entry.get(field), str):
                    found.add((entry[field], None))
            if isinstance(entry.get("their_key"), str):
                found.add(
                    (entry["their_key"], json.dumps(entry["rows"], sort_keys=True))
                )
            found.update(
                (k, None) for k in entry.get("keys") or [] if isinstance(k, str)
            )
            for group in ("and", "or", "not"):
                if group in entry:
                    walk(entry[group])

    walk(policy.check)
    walk(policy.resource.get("filters") or [])
    return {(k, b) for k, b in found if k.startswith("raw_data")}


def selected(rows, block):
    return [r for r in rows if engine._plain(r, block)]


def all_policies():
    return [p for n in builtin.SET_NAMES for p in builtin.load_set(n)]


def test_every_raw_data_key_of_every_shipped_policy_is_on_a_scanned_row(estate_rows):
    problems = []
    for policy in all_policies():
        if not selected(estate_rows, policy.resource):
            problems.append(f"{policy.id}: the scan has no row it selects")
            continue
        for key, block in sorted(keys_read(policy), key=str):
            rows = selected(
                estate_rows, json.loads(block) if block else policy.resource
            )
            compiled = filters.compile_key(key)
            if not any(compiled.get(r) is not None for r in rows):
                problems.append(f"{policy.id}: {key} is on no scanned row")
    assert problems == []


def test_the_fields_that_are_not_shipped_are_not_on_the_scanned_rows(estate_rows):
    for label, key in NOT_ON_THE_ROW:
        service, rtype = label.split("/")
        rows = [
            r
            for r in estate_rows
            if r["service"] == service and r["resource_type"] == rtype
        ]
        assert rows, f"the estate has no {label}"
        compiled = filters.compile_key(key)
        assert all(compiled.get(r) is None for r in rows), (label, key)


def test_no_shipped_policy_reads_a_field_of_the_not_shipped_list():
    listed = {key for _, key in NOT_ON_THE_ROW}
    for policy in all_policies():
        assert not ({k for k, _ in keys_read(policy)} & listed), policy.id


def test_the_scanned_rows_give_each_encryption_and_exposure_policy_a_fail_and_a_pass(
    estate_rows,
):
    policies = [
        p
        for n in ("encryption-at-rest", "public-exposure")
        for p in builtin.load_set(n)
    ]
    snapshot = {
        "metadata": {"tags": {"units_not_read": []}},
        "resources": copy.deepcopy(estate_rows),
    }
    now = "2026-11-24T12:00:00+00:00"
    result = engine.evaluate(snapshot, policies, now=now, include_pass=True)
    by_policy = {}
    for f in result["findings"]:
        by_policy.setdefault(f["policy"], set()).add(f["result"])
    for policy in policies:
        assert {"pass", "fail"} <= by_policy.get(policy.id, set()), policy.id
    assert not [f for f in result["findings"] if f["result"] == "not_evaluated"]
