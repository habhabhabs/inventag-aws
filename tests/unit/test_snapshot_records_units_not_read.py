"""The snapshot names the units this run did not read (A-05, A-68; writer
side of lead B's WO-B1).

Additive key ``metadata.tags.units_not_read`` (decision 6; schema stays 1.1):
one entry ``{account, service, region, source, outcome}`` per unit whose
service or Tagging API listing failed. Billing, detail calls and moto's
``404`` are not units. A clean run has no key, so its snapshot is as before.
"""

import json

from tests.regression.faults import Fault, FaultInjector
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    aws,
    empty_aws,
    run_cli,
)

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]


def snapshot_tags(tmp_path):
    files = sorted((tmp_path / "out" / "state").glob("state_*.json"))
    return json.loads(files[-1].read_text())["metadata"]["tags"]


def run(faults=()):
    with FaultInjector(list(faults)) as injector:
        injector.arm()
        return run_cli(*ARGS)


def test_a_throttled_listing_is_a_unit_not_read(aws, tmp_path):  # noqa: F811
    throttled = Fault(service="sqs", op="ListQueues", error="Throttling")
    assert run([throttled]) == 0  # as before
    assert snapshot_tags(tmp_path)["units_not_read"] == [
        {
            "account": GOOD_ID,
            "service": "sqs",
            "region": "us-east-1",
            "source": "service-api",
            "outcome": "throttled",
        }
    ]


def test_a_denied_tagging_api_is_a_unit_not_read(aws, tmp_path):  # noqa: F811
    denied = Fault(service="resourcegroupstaggingapi", error="AccessDenied")
    assert run([denied]) == 0
    units = snapshot_tags(tmp_path)["units_not_read"]
    assert [u for u in units if u["source"] == "tagging-api"] == [
        {
            "account": GOOD_ID,
            "service": units[0]["service"],
            "region": "us-east-1",
            "source": "tagging-api",
            "outcome": "denied",
        }
    ]


def test_a_clean_run_has_no_key(aws, tmp_path):  # noqa: F811
    assert run() == 0
    assert "units_not_read" not in snapshot_tags(tmp_path)
