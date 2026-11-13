"""Duplicate resolution keeps the service-API record and merges tags from all sources.

Added after a mutation check: flipping the sort order so that fallback
(Resource Groups Tagging API) records win was not caught by any existing test.
"""

from unittest.mock import MagicMock

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

ARN = "arn:aws:s3:::my-bucket"


def make_discovery(resources):
    discovery = ComprehensiveAWSDiscovery(
        session=MagicMock(), regions=["us-east-1"], enable_billing_validation=False
    )
    discovery.resources = resources
    return discovery


def test_primary_record_wins_over_fallback_whatever_the_order():
    primary = {
        "arn": ARN,
        "priority": "primary",
        "discovered_via": "ServiceAPI:list_buckets",
        "tags": {"Owner": "a"},
    }
    fallback = {
        "arn": ARN,
        "priority": "fallback",
        "discovered_via": "ResourceGroupsTaggingAPI",
        "tags": {"Env": "prod"},
    }
    for order in ([primary, fallback], [fallback, primary]):
        discovery = make_discovery([dict(r) for r in order])
        discovery._remove_duplicates_with_priority()

        assert len(discovery.resources) == 1
        kept = discovery.resources[0]
        assert kept["discovered_via"] == "ServiceAPI:list_buckets"
        assert kept["tags"] == {"Owner": "a", "Env": "prod"}
        assert kept["duplicate_sources"] == 2
        assert kept["tagged"] is True


def test_resources_without_an_arn_are_never_merged():
    discovery = make_discovery(
        [{"id": "a", "priority": "primary"}, {"id": "b", "priority": "primary"}]
    )
    discovery._remove_duplicates_with_priority()
    assert sorted(r["id"] for r in discovery.resources) == ["a", "b"]
