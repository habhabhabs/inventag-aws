"""D5 (A-08a): an EKS cluster row carries ``resourcesVpcConfig``.

The list call gives names only. One ``eks:DescribeCluster`` per listed cluster
(allowed by the shipped IAM policy and by the read-only guard) adds the
cluster's subnets, in the AWS shape the network analysis reads:
``raw_data["resourcesVpcConfig"] = {"subnetIds": [...], "vpcId": ...}``.
A failed call keeps the row, writes a ``service-api-detail`` record and does
not fail the listing; "not found" (a cluster deleted since the listing) is not
a failure. An estate without EKS makes no EKS call.

The pair test at the end needs lead B's rule for fields new after an upgrade; it
is skipped, with the reason, where that rule is absent. The Network sheet check
(senior F reads the field) is run by the assembly.
"""

import inspect
import logging
from unittest import mock

import pytest
from botocore.exceptions import ClientError

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

R = "us-east-1"
ACCOUNT = "111122223333"
CONFIG = {
    "subnetIds": ["subnet-a", "subnet-b"],
    "vpcId": "vpc-1",
    "securityGroupIds": ["sg-1"],
}


def _row(name):
    return {
        "service": "EKS",
        "resource_type": "Cluster",
        "resource_id": name,
        "region": R,
        "arn": f"arn:aws:eks:{R}:{ACCOUNT}:cluster/{name}",
        "raw_data": {"name": name},
    }


class Eks:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def describe_cluster(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers[kwargs["name"]]
        if isinstance(answer, Exception):
            raise answer
        return {"cluster": {"name": kwargs["name"], "resourcesVpcConfig": answer}}


def _disc(rows, eks):
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=False
    )
    disc.coverage.account_id = ACCOUNT
    disc.resources = rows
    disc._client = lambda *a, **k: eks
    return disc


def _error(code):
    return ClientError({"Error": {"Code": code, "Message": "secret-detail"}}, "Op")


def test_a_cluster_row_gets_its_subnets():
    eks = Eks({"c1": CONFIG})
    disc = _disc([_row("c1")], eks)
    disc._enhance_eks_clusters()
    assert eks.calls == [{"name": "c1"}]
    assert disc.resources[0]["raw_data"]["resourcesVpcConfig"] == CONFIG
    assert disc.resources[0]["raw_data"]["name"] == "c1"
    assert disc.coverage.entries == []


def test_one_call_per_cluster():
    eks = Eks({"c1": CONFIG, "c2": CONFIG})
    _disc([_row("c1"), _row("c2")], eks)._enhance_eks_clusters()
    assert sorted(c["name"] for c in eks.calls) == ["c1", "c2"]


def test_a_denied_describe_keeps_the_row_and_records_it_once(caplog):
    eks = Eks(
        {"c1": _error("AccessDeniedException"), "c2": _error("AccessDeniedException")}
    )
    disc = _disc([_row("c1"), _row("c2")], eks)
    with caplog.at_level(logging.WARNING):
        disc._enhance_eks_clusters()
    assert [r["raw_data"] for r in disc.resources] == [{"name": "c1"}, {"name": "c2"}]
    (entry,) = disc.coverage.to_dict()
    assert (entry["source"], entry["service"], entry["operation"]) == (
        "service-api-detail",
        "eks",
        "DescribeCluster",
    )
    assert (entry["outcome"], entry["count"]) == ("denied", 2)
    assert [r.getMessage() for r in caplog.records if r.levelno >= 30] == [
        "Details of 2 eks resource(s) in us-east-1 could not be read "
        "(DescribeCluster: AccessDeniedException); their rows have some fields "
        "missing. Add the read permission to see them."
    ]
    assert "secret-detail" not in caplog.text


def test_a_cluster_deleted_since_the_listing_is_not_a_failure():
    eks = Eks({"c1": _error("ResourceNotFoundException")})
    disc = _disc([_row("c1")], eks)
    disc._enhance_eks_clusters()
    assert disc.coverage.entries == []
    assert disc.resources[0]["raw_data"] == {"name": "c1"}


def test_an_estate_without_eks_makes_no_eks_call():
    made = []
    disc = _disc([{"service": "SQS", "resource_type": "Queue", "region": R}], None)
    disc._client = lambda *a, **k: made.append(a) or None
    disc._enhance_eks_clusters()
    assert made == []


def test_the_post_processing_step_runs_it():
    eks = Eks({"c1": CONFIG})
    disc = _disc([_row("c1")], eks)
    for name in (
        "_enhance_lambda_functions",
        "_enhance_rds_resources",
        "_enhance_cloudformation_stacks",
        "_remove_duplicates_with_priority",
    ):
        setattr(disc, name, lambda: None)
    disc.billing_services = set()
    disc._post_process_resources()
    assert eks.calls == [{"name": "c1"}]


# ------------------------------------------------------------------ pair tests
def _rule_present():
    from inventag.state.delta_detector import DeltaDetector

    return (
        "previous_inventag_version"
        in inspect.signature(DeltaDetector.detect_changes).parameters
    )


@pytest.mark.skipif(
    not _rule_present(),
    reason="lead B's rule for fields new after an upgrade (previous_inventag_version) "
    "is not on this branch; the assembly runs this test with it",
)
def test_the_new_field_is_not_a_modification_after_the_upgrade():
    from inventag.state.delta_detector import DeltaDetector

    def row(raw):
        return {
            "service": "EKS",
            "resource_type": "Cluster",
            "resource_id": "c1",
            "resource_name": "c1",
            "arn": f"arn:aws:eks:{R}:{ACCOUNT}:cluster/c1",
            "region": R,
            "account_id": ACCOUNT,
            "tags": {},
            "raw_data": raw,
            "source": "service-api",
        }

    disc = _disc([row({"name": "c1"})], Eks({"c1": CONFIG}))
    disc._enhance_eks_clusters()
    new = disc.resources
    assert new[0]["raw_data"]["resourcesVpcConfig"] == CONFIG
    report = DeltaDetector().detect_changes(
        [row({"name": "c1"})], new, "a", "b", previous_inventag_version=None
    )
    assert len(report.modified_resources) == 0
    assert len(report.unchanged_resources) == 1


# ---------------------------------------------------- no new report columns
def _flatteners():
    from inventag.reporting.converter import BOMConverter
    from inventag.reporting.csv_builder import CSVBuilder
    from inventag.reporting.excel_builder import ExcelWorkbookBuilder
    from inventag.templating.columns import flatten

    return {
        "excel": ExcelWorkbookBuilder._flatten_dict.__get__(
            object.__new__(ExcelWorkbookBuilder)
        ),
        "csv": CSVBuilder._flatten_dict.__get__(object.__new__(CSVBuilder)),
        "converter (word, google)": BOMConverter._flatten_dict.__get__(
            object.__new__(BOMConverter)
        ),
        "template reports": flatten,
    }


@pytest.mark.xfail(
    reason="the report writers (excel_builder, csv_builder, converter, "
    "templating/columns, not track D files) must skip raw_data.resourcesVpcConfig; "
    "see the patch under 'Needs from another track' in p3-track-d.md. The "
    "assembly applies it with D5 and removes this marker.",
    strict=False,
)
@pytest.mark.parametrize("writer", list(_flatteners()))
def test_the_field_adds_no_column_to_any_report(writer):
    """Sheet and column names are a published interface: the EKS header row is
    the same with and without the field. The row keeps the field for the
    network analysis (``raw_data["resourcesVpcConfig"]``) and the snapshot."""
    flat = _flatteners()[writer]
    without = _row("c1")
    with_field = _row("c1")
    with_field["raw_data"]["resourcesVpcConfig"] = dict(CONFIG)
    assert sorted(flat(with_field)) == sorted(flat(without))


def test_the_row_keeps_the_field_for_the_analysis():
    eks = Eks({"c1": CONFIG})
    disc = _disc([_row("c1")], eks)
    disc._enhance_eks_clusters()
    raw = disc.resources[0]["raw_data"]
    assert raw["resourcesVpcConfig"]["subnetIds"] == ["subnet-a", "subnet-b"]
