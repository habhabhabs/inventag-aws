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
