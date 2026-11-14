"""Change detection must grow linearly with the snapshot size.

Before v1.2.0 was fixed, ``_find_related_resources`` walked the whole new
snapshot twice for every changed EC2, RDS, S3 or VPC resource: the work grew
with (changes x resources), so a run against a different estate (every ID
changed) took 4 times as long each time the estate doubled.

The test counts work instead of timing it, so it is not flaky on a slow
machine: every resource row is a dict that counts the ``get`` calls made on
it. The estates are built so that the OUTPUT grows linearly (each resource is
related to a fixed number of others), so linear work is possible; quadratic
work shows as a count ratio near 16 when the estate grows 4 times, linear
work as a ratio near 4.
"""

import pytest

from inventag.state.delta_detector import DeltaDetector

ACC = "123456789012"
REG = "us-east-1"


class CountingRow(dict):
    """A resource row that counts ``get`` calls in a shared counter."""

    counter = [0]

    def get(self, *args, **kwargs):
        CountingRow.counter[0] += 1
        return super().get(*args, **kwargs)


def _estate(groups, offset, linked):
    """``groups`` groups of 5 rows: VPC, 2 instances, a load balancer, a queue.

    With ``linked`` each group shares its own vpc_id (so each instance is
    related to its VPC and load balancer only); without it the rows carry no
    relationship field, as the v1.2.0 scanner saves them.
    """
    rows = []
    for g in range(offset, offset + groups):
        vpc = {"vpc_id": f"vpc-{g}"} if linked else {}
        sgs = {"security_groups": [f"sg-{g}"]} if linked else {}
        rows += [
            {
                "arn": f"arn:aws:ec2:{REG}:{ACC}:vpc/vpc-{g}",
                "id": f"vpc-{g}",
                "service": "VPC",
                "type": "VPC",
                **vpc,
            },
            *[
                {
                    "arn": f"arn:aws:ec2:{REG}:{ACC}:instance/i-{g}-{k}",
                    "id": f"i-{g}-{k}",
                    "service": "EC2",
                    "type": "Instance",
                    **vpc,
                    **sgs,
                }
                for k in range(2)
            ],
            {
                "arn": f"arn:aws:elasticloadbalancing:{REG}:{ACC}:loadbalancer/app/lb-{g}/1",
                "id": f"lb-{g}",
                "service": "ELB",
                "type": "LoadBalancer",
                **vpc,
                **sgs,
            },
            {
                "arn": f"arn:aws:sqs:{REG}:{ACC}:q-{g}",
                "id": f"q-{g}",
                "service": "SQS",
                "type": "Queue",
            },
        ]
    for r in rows:
        r["region"] = REG
        r["tags"] = {"Name": r["id"]}
    return rows


def _work(groups, linked):
    """``get`` calls made by one detect_changes of a fresh estate (all IDs differ)."""
    old = [CountingRow(r) for r in _estate(groups, 0, linked)]
    new = [CountingRow(r) for r in _estate(groups, groups, linked)]
    CountingRow.counter[0] = 0
    report = DeltaDetector().detect_changes(old, new, "s1", "s2")
    assert report.summary["added_count"] == len(new)
    assert report.summary["removed_count"] == len(old)
    links = sum(len(c.related_resources) for c in report.added_resources)
    return CountingRow.counter[0], links


@pytest.mark.parametrize("linked", [False, True], ids=["scanner-rows", "linked-rows"])
def test_change_detection_work_grows_linearly(linked):
    small, small_links = _work(20, linked)
    large, large_links = _work(80, linked)
    # The output itself grows linearly (4 times the groups, 4 times the links).
    assert large_links == 4 * small_links
    # So must the work: about 4 times, never near 16 times.
    assert large / small < 6, (small, large)


_VALUES = [
    "a",
    "b",
    "",
    None,
    0,
    1,
    1.0,
    True,
    ("a",),
    ["a"],
    ["b", "a"],
    ["", "c"],
    [],
    [1],
    {"k": 1},
    [{"k": 1}],
]
_SERVICES = ["EC2", "ec2", "RDS", "S3", "VPC", "ELB", "EBS", "NAT", "Lambda", "SQS"]
_FIELDS = ["vpc_id", "subnet_id", "security_groups", "iam_role", "kms_key_id"]


def _random_rows(rng, count, prefix, mode):
    """mode 0: hashable values only; 1: plus a dict value; 2: plus a list of dicts."""
    values = [
        v
        for v in _VALUES
        if (mode >= 1 or not isinstance(v, dict)) and (mode >= 2 or v != [{"k": 1}])
    ]
    rows = []
    for i in range(count):
        row = {
            "arn": f"arn:aws:x:{REG}:{ACC}:r/{prefix}{i}",
            "id": f"{prefix}{i}",
            "service": rng.choice(_SERVICES),
            "type": "T",
            "region": REG,
            "tags": {"n": str(rng.randint(0, 2))},
        }
        for name in _FIELDS:
            if rng.random() < 0.5:
                row[name] = rng.choice(values)
        rows.append(row)
    return rows


def _outcome(old, new, monkeypatch, scan_all):
    import copy
    import json

    from inventag.state import delta_detector

    if scan_all:
        monkeypatch.setattr(
            delta_detector._RelatedIndex, "candidates", lambda self, resource: None
        )
    try:
        report = DeltaDetector().detect_changes(
            copy.deepcopy(old), copy.deepcopy(new), "s1", "s2"
        )
    except Exception as exc:  # the present code raises on some shapes
        return ("raised", type(exc).__name__, str(exc))
    finally:
        monkeypatch.undo()
    changes = report.added_resources + report.removed_resources
    changes += report.modified_resources
    return json.dumps(
        [
            [[c.resource_arn, c.related_resources] for c in changes],
            report.impact_analysis,
        ],
        default=repr,
    )


@pytest.mark.parametrize("seed", range(40))
def test_index_gives_the_same_result_as_scanning_every_row(seed, monkeypatch):
    """Random rows with every value shape the rules treat differently.

    The related lists, their order and the impact analysis must be the same
    with the index as with a scan of every row (the v1.2.0 way), including
    the error raised when the rows hold lists of dicts.
    """
    import random

    rng = random.Random(seed)
    mode = seed % 3
    old = _random_rows(rng, 30, "o", mode)
    new = [dict(r) for r in old[:20]] + _random_rows(rng, 15, "n", mode)
    for r in new[:10]:
        r["tags"] = {"n": "changed"}
    indexed = _outcome(old, new, monkeypatch, scan_all=False)
    scanned = _outcome(old, new, monkeypatch, scan_all=True)
    assert indexed == scanned
    if mode < 2:
        assert indexed[0] != "raised"
