"""A3 (plan 2.4, rule 3): the inventory sort has a last key, a digest of the row.

Rows with the same ARN, service, type, id and region (for example rows with no
ARN) must come out in one fixed order, whatever order they were found in.
"""

import itertools
from unittest import mock

from inventag.discovery.inventory import AWSResourceInventory


def _inventory(rows):
    inv = AWSResourceInventory(
        session=mock.MagicMock(),
        regions=["us-east-1"],
        enable_billing_validation=False,
    )
    inv.ensure_consistent_results = True
    inv.resources = [dict(r) for r in rows]
    return inv


def _rows():
    # Same sort key (no arn, same service/type/id/region), different content.
    return [
        {
            "service": "EC2",
            "type": "Instance",
            "id": "i-1",
            "region": "us-east-1",
            "tags": {"Name": name},
        }
        for name in ("c", "a", "b", "d")
    ] + [
        {
            "service": "EC2",
            "type": "Instance",
            "id": "i-0",
            "region": "us-east-1",
            "tags": {},
        },
        {
            "service": "S3",
            "type": "Bucket",
            "id": "b",
            "region": "us-east-1",
            "tags": {},
            "arn": "arn:aws:s3:::b",
        },
    ]


def _order(rows):
    inv = _inventory(rows)
    inv._ensure_consistent_results()
    return [r.get("tags", {}).get("Name", r["id"]) for r in inv.resources]


def test_rows_with_equal_keys_come_out_in_one_order_for_every_input_order():
    results = set()
    for perm in itertools.permutations(_rows()):
        inv = _inventory(perm)
        inv._ensure_consistent_results()
        results.add(tuple(repr(r) for r in inv.resources))
    assert len(results) == 1


def test_the_existing_keys_still_come_first():
    order = _order(_rows())
    # arn "" sorts before "arn:aws:s3:::b"; the S3 row is last
    assert order[-1] == "b"
    assert order[0] == "i-0"


def test_the_digest_does_not_change_the_rows():
    rows = _rows()
    inv = _inventory(rows)
    inv._ensure_consistent_results()
    assert sorted(map(repr, inv.resources)) == sorted(map(repr, rows))
