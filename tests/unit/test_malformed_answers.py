"""A-23: an answer in the wrong form makes no false rows and no silent drops.

A bad item is skipped with one WARNING that names the service, the operation
and the region (never the payload); the good items are kept; the listing is
recorded as an error so the notes and the change report know it may be partial.
An answer that has no list at all (the key is missing) is an ordinary empty
answer and says nothing.
"""

import logging
import types
from unittest import mock

import pytest

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

R = "us-east-1"
URL = "https://sqs.us-east-1.amazonaws.com/111122223333/q1"


class Client:
    """A client whose one list call answers ``page`` (no paginator)."""

    def __init__(self, page):
        self.page = page
        self.meta = types.SimpleNamespace(method_to_api_mapping={})

    def can_paginate(self, name):
        return False

    def __getattr__(self, name):
        return lambda **kwargs: self.page


def _run(service, page, index=0):
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=False
    )
    operation = disc.service_discovery_patterns[service]["operations"][index]
    disc._execute_discovery_operation(Client(page), service, R, operation)
    return disc


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


NEXT = "Run the scan again; if it repeats, report it with the --debug log."


def test_a_string_where_a_list_belongs_makes_no_row(caplog):
    with caplog.at_level(logging.WARNING):
        disc = _run("sqs", {"QueueUrls": "oops"})
    assert disc.resources == []
    assert _warnings(caplog) == [
        "sqs list_queues in us-east-1 returned an answer InvenTag could not "
        "read, so none of its items are listed. " + NEXT
    ]
    assert "oops" not in caplog.text
    (entry,) = disc.coverage.to_dict()
    assert (entry["outcome"], entry["error_code"]) == ("error", "MalformedResponse")


def test_bad_items_are_skipped_and_good_items_kept(caplog):
    with caplog.at_level(logging.WARNING):
        disc = _run("sqs", {"QueueUrls": [URL, None, 5, URL + "2", URL + "3"]})
    assert [r["resource_id"] for r in disc.resources] == [URL, URL + "2", URL + "3"]
    assert _warnings(caplog) == [
        "sqs list_queues in us-east-1 returned 2 item(s) InvenTag could not "
        "read; they are skipped and the other items are kept. " + NEXT
    ]
    (entry,) = disc.coverage.to_dict()
    assert (entry["outcome"], entry["count"]) == ("error", 3)  # 3 rows found


def test_a_list_of_wrong_items_makes_no_row(caplog):
    with caplog.at_level(logging.WARNING):
        disc = _run("dynamodb", {"TableNames": [None, 5]})
    assert disc.resources == []
    assert len(_warnings(caplog)) == 1
    assert "dynamodb list_tables in us-east-1" in _warnings(caplog)[0]


def test_a_nested_key_on_something_that_is_not_a_dict_is_reported(caplog):
    with caplog.at_level(logging.WARNING):
        disc = _run("cloudfront", {"DistributionList": "oops"})
    assert disc.resources == []
    assert len(_warnings(caplog)) == 1
    assert "cloudfront" in _warnings(caplog)[0]


@pytest.mark.parametrize(
    "service, page",
    [
        ("vpc", {}),
        ("sqs", {}),
        ("sqs", {"QueueUrls": []}),
        ("dynamodb", {"TableNames": None}),
    ],
)
def test_a_missing_or_empty_list_is_an_ordinary_empty_answer(service, page, caplog):
    with caplog.at_level(logging.WARNING):
        disc = _run(service, page)
    assert disc.resources == []
    assert _warnings(caplog) == []
    (entry,) = disc.coverage.to_dict()
    assert entry["outcome"] == "empty"


def test_a_good_answer_is_unchanged(caplog):
    with caplog.at_level(logging.WARNING):
        disc = _run("sqs", {"QueueUrls": [URL]})
    assert [r["resource_id"] for r in disc.resources] == [URL]
    assert _warnings(caplog) == []
    (entry,) = disc.coverage.to_dict()
    assert (entry["outcome"], entry["count"], entry["error_code"]) == ("ok", 1, "")


def test_an_item_that_cannot_be_turned_into_a_row_is_reported(caplog):
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R], enable_billing_validation=False
    )
    with (
        mock.patch.object(
            disc, "_normalize_resource", side_effect=RuntimeError("secret-payload")
        ),
        caplog.at_level(logging.WARNING),
    ):
        found = disc._extract_resources_from_response(
            {"Topics": [{"TopicArn": "arn:aws:sns:us-east-1:1:t"}]},
            "Topics",
            "sns",
            R,
            "Topic",
            "list_topics",
        )
    assert found == 0
    assert len(_warnings(caplog)) == 1
    assert "secret-payload" not in caplog.text
