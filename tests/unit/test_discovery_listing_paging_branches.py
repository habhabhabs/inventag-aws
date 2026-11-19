"""Branches of the listing and paging code of comprehensive_discovery.py.

T-09: branch coverage of ``inventag/discovery`` showed these branches never ran
in a test: the page-size and token lookup of ``_pages`` for an operation that
botocore cannot paginate and whose model lacks an input or an output shape, a
listing cut off by the stop flag, an answer whose path is missing or holds one
item, a failing extraction, a failing listing future, a failing client
creation, the endpoint lookup, and the CloudFront certificate lookup. No AWS
call is made: every client is a stub.
"""

import logging
import types
from unittest import mock

import pytest
from botocore.exceptions import ClientError

from inventag.discovery import comprehensive_discovery as cd
from inventag.discovery import coverage as coverage_mod

R = "us-east-1"
ARN = "arn:aws:acm:us-east-1:111122223333:certificate/abc"


def _disc(**kwargs):
    return cd.ComprehensiveAWSDiscovery(
        session=mock.MagicMock(),
        regions=[R],
        enable_billing_validation=False,
        **kwargs,
    )


def _error(code):
    return ClientError({"Error": {"Code": code, "Message": "m"}}, "Op")


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


# --- _pages: an operation botocore cannot paginate ---------------------------


class _Shape:
    def __init__(self, *members):
        self.members = {name: None for name in members}


class _NoPaginatorClient:
    """A client with one list call, no paginator and a hand-made model."""

    def __init__(self, pages, input_shape, output_shape):
        self.calls = []
        self._pages = list(pages)
        operation = types.SimpleNamespace(
            input_shape=input_shape, output_shape=output_shape
        )
        self.meta = types.SimpleNamespace(
            method_to_api_mapping={"list_things": "ListThings"},
            service_model=types.SimpleNamespace(
                service_name="things", operation_model=lambda name: operation
            ),
        )

    def can_paginate(self, name):
        return False

    def list_things(self, **kwargs):
        self.calls.append(kwargs)
        return self._pages.pop(0)


def test_a_model_without_an_input_shape_returns_the_first_page_only():
    client = _NoPaginatorClient(
        [{"Things": [1], "NextToken": "t"}], None, _Shape("Things", "NextToken")
    )
    pages = list(_disc()._pages(client, "list_things", {}))
    assert pages == [{"Things": [1], "NextToken": "t"}]
    assert client.calls == [{}]


def test_a_model_without_an_output_shape_returns_the_first_page_only():
    client = _NoPaginatorClient(
        [{"Things": [1], "NextToken": "t"}], _Shape("NextToken"), None
    )
    pages = list(_disc()._pages(client, "list_things", {}))
    assert pages == [{"Things": [1], "NextToken": "t"}]
    assert client.calls == [{}]


def test_the_token_of_the_model_is_followed_to_the_last_page():
    client = _NoPaginatorClient(
        [{"Things": [1], "NextToken": "t"}, {"Things": [2]}],
        _Shape("NextToken"),
        _Shape("Things", "NextToken"),
    )
    pages = list(_disc()._pages(client, "list_things", {}))
    assert [p["Things"] for p in pages] == [[1], [2]]
    assert client.calls == [{}, {"NextToken": "t"}]


def test_a_repeated_token_stops_the_loop():
    client = _NoPaginatorClient(
        [
            {"Things": [1], "NextToken": "t"},
            {"Things": [2], "NextToken": "t"},
            {"Things": [3]},
        ],
        _Shape("NextToken"),
        _Shape("Things", "NextToken"),
    )
    pages = list(_disc()._pages(client, "list_things", {}))
    assert [p["Things"] for p in pages] == [[1], [2]]


# --- _execute_discovery_operation --------------------------------------------


class _OnePageClient:
    def __init__(self, page):
        self.page = page
        self.meta = types.SimpleNamespace(method_to_api_mapping={})

    def can_paginate(self, name):
        return False

    def __getattr__(self, name):
        return lambda **kwargs: self.page


def _run(service, page, index=0, disc=None):
    disc = disc or _disc()
    operation = disc.service_discovery_patterns[service]["operations"][index]
    found = disc._execute_discovery_operation(
        _OnePageClient(page), service, R, operation
    )
    return disc, found


def test_a_listing_cut_off_by_the_stop_flag_is_recorded_as_a_timeout():
    disc = _disc()
    disc._stop.set()
    disc, found = _run("sqs", {"QueueUrls": ["https://x/1"]}, disc=disc)
    assert found == 0
    assert disc.resources == []
    assert [e.outcome for e in disc.coverage.entries] == [coverage_mod.TIMEOUT]


def test_an_answer_with_a_none_in_the_path_is_an_empty_listing():
    disc = _disc()
    spec = {"op": "list_x", "key": "A.B", "type": "X"}
    found = disc._extract_resources_from_response(
        {"A": None}, "A.B", "sqs", R, "X", "list_x", spec
    )
    assert found == 0
    assert disc.resources == []


def test_a_single_object_where_a_list_belongs_is_one_item():
    disc = _disc()
    spec = {"op": "list_x", "key": "Item", "type": "X", "id": "Id"}
    found = disc._extract_resources_from_response(
        {"Item": {"Id": "only-one", "Name": "n"}}, "Item", "sqs", R, "X", "list_x", spec
    )
    assert found == 1
    assert [r["resource_id"] for r in disc.resources] == ["only-one"]


def test_a_failing_extraction_is_reported_as_unreadable(monkeypatch, caplog):
    disc = _disc()
    problems = []

    def boom(*args, **kwargs):
        raise ValueError("secret-detail")

    monkeypatch.setattr(disc, "_normalize_resource", boom)
    with caplog.at_level(logging.WARNING):
        found = disc._extract_resources_from_response(
            {"Things": [{"Id": "a"}]},
            "Things",
            "sqs",
            R,
            "Queue",
            "list_queues",
            None,
            problems,
        )
    assert found == 0
    assert problems == [1]
    assert disc.resources == []
    assert "secret-detail" not in caplog.text


def test_add_source_on_a_resource_that_has_no_source_yet():
    resource = {"id": "r"}
    cd._add_source(resource, "tagging-api")
    assert resource["sources"] == "tagging-api"


# --- the endpoint lookup ------------------------------------------------------


def test_a_failing_endpoint_lookup_means_every_region_is_tried():
    disc = _disc()
    disc.session.get_available_regions.side_effect = RuntimeError("no data")
    assert disc._service_regions("ec2", "aws") == set()


def test_an_endpoint_lookup_that_is_not_a_list_means_every_region_is_tried():
    disc = _disc()
    disc.session.get_available_regions.return_value = None
    assert disc._service_regions("ec2", "aws") == set()


def test_an_endpoint_lookup_list_is_returned_as_a_set():
    disc = _disc()
    disc.session.get_available_regions.return_value = ["us-east-1", "eu-west-1"]
    assert disc._service_regions("ec2", "aws") == {"us-east-1", "eu-west-1"}


# --- a listing task that fails as a whole ------------------------------------


def test_a_failing_listing_future_is_a_warning_and_the_others_go_on(
    monkeypatch, caplog
):
    disc = _disc()
    seen = []

    def one_fails(task):
        seen.append(task["service"])
        if len(seen) == 1:
            raise RuntimeError("listing exploded")
        return 0

    monkeypatch.setattr(disc, "_discover_service_in_region", one_fails)
    with caplog.at_level(logging.WARNING):
        disc._discover_all_service_resources(1)
    assert len(seen) > 1
    assert any("failed: listing exploded" in w for w in _warnings(caplog))


@pytest.mark.parametrize(
    "error,code",
    [
        (_error("InvalidClientTokenId"), "InvalidClientTokenId"),
        (RuntimeError("no client"), "RuntimeError"),
    ],
)
def test_a_client_that_cannot_be_made_is_recorded_and_named(
    monkeypatch, caplog, error, code
):
    disc = _disc()

    def no_client(service, region=None):
        raise error

    monkeypatch.setattr(disc, "_client", no_client)
    task = {
        "service": "sqs",
        "region": R,
        "config": disc.service_discovery_patterns["sqs"],
    }
    with caplog.at_level(logging.WARNING):
        assert disc._discover_service_in_region(task) == 0
    (entry,) = disc.coverage.entries
    assert (entry.service, entry.region, entry.error_code) == ("sqs", R, code)
    assert entry.outcome == coverage_mod.ERROR
    assert any(
        f"client creation failed for sqs: {code}" in w for w in _warnings(caplog)
    )


def test_a_global_service_that_cannot_start_is_recorded_as_global(monkeypatch):
    disc = _disc()
    monkeypatch.setattr(disc, "_client", mock.Mock(side_effect=_error("AccessDenied")))
    task = {
        "service": "iam",
        "region": R,
        "config": {"regional": False, "operations": []},
    }
    disc._discover_service_in_region(task)
    (entry,) = disc.coverage.entries
    assert entry.region == cd.GLOBAL_REGION_LABEL
    assert entry.outcome == coverage_mod.DENIED


# --- the CloudFront certificate lookup ----------------------------------------


class _Acm:
    def __init__(self, summaries, in_use):
        self.summaries = summaries
        self.in_use = in_use

    def get_paginator(self, name):
        assert name == "list_certificates"
        return types.SimpleNamespace(
            paginate=lambda: [{"CertificateSummaryList": self.summaries}]
        )

    def describe_certificate(self, CertificateArn):
        return {"Certificate": {"InUseBy": self.in_use[CertificateArn]}}


def test_only_a_certificate_a_distribution_uses_is_listed(monkeypatch):
    disc = _disc()
    other = ARN + "-other"
    acm = _Acm(
        [
            {"CertificateArn": ARN, "DomainName": "a.example.com"},
            {"CertificateArn": other, "DomainName": "b.example.com"},
        ],
        {
            ARN: ["arn:aws:cloudfront::111122223333:distribution/E1"],
            other: ["arn:aws:elasticloadbalancing:us-east-1:1:loadbalancer/x"],
        },
    )
    monkeypatch.setattr(disc, "_client", lambda service, region=None: acm)
    assert disc._discover_cloudfront_certificates() == 1
    assert [r["arn"] for r in disc.resources] == [ARN]
    assert "acm" in disc.services_with_primary_resources


def test_a_denied_certificate_lookup_is_one_warning_and_a_detail_record(
    monkeypatch, caplog
):
    disc = _disc()
    monkeypatch.setattr(
        disc, "_client", mock.Mock(side_effect=_error("AccessDeniedException"))
    )
    with caplog.at_level(logging.WARNING):
        assert disc._discover_cloudfront_certificates() == 0
    assert len(_warnings(caplog)) == 1
    assert "No permission for acm" in _warnings(caplog)[0]
    (entry,) = disc.coverage.entries
    assert entry.outcome == coverage_mod.DENIED
    assert entry.source == coverage_mod.DETAIL_SOURCE


@pytest.mark.parametrize(
    "error", [_error("ThrottlingException"), RuntimeError("socket gone")]
)
def test_another_certificate_failure_is_one_warning_that_names_the_operation(
    monkeypatch, caplog, error
):
    disc = _disc()
    monkeypatch.setattr(disc, "_client", mock.Mock(side_effect=error))
    with caplog.at_level(logging.WARNING):
        assert disc._discover_cloudfront_certificates() == 0
    (warning,) = _warnings(caplog)
    assert "CloudFront certificates could not be read (ListCertificates" in warning
    (entry,) = disc.coverage.entries
    assert entry.operation == "ListCertificates"
    assert entry.outcome in (coverage_mod.THROTTLED, coverage_mod.ERROR)


# --- an operation that fails outside its own error handling ------------------


def _task(disc, service="sqs"):
    return {
        "service": service,
        "region": R,
        "config": disc.service_discovery_patterns[service],
    }


@pytest.mark.parametrize("code", ["AccessDenied", "UnauthorizedOperation"])
@pytest.mark.parametrize("graceful", [True, False])
def test_an_access_denied_operation_does_not_stop_the_next_one(
    monkeypatch, caplog, code, graceful
):
    disc = _disc()
    task = _task(disc, "ecs")
    task["config"] = {**task["config"], "graceful_degradation": graceful}
    calls = []

    def execute(client, service, region, operation):
        calls.append(operation)
        raise _error(code)

    monkeypatch.setattr(disc, "_client", mock.Mock())
    monkeypatch.setattr(disc, "_execute_discovery_operation", execute)
    with caplog.at_level(logging.WARNING):
        assert disc._discover_service_in_region(task) == 0
    assert len(calls) == len(task["config"]["operations"]) > 1
    assert _warnings(caplog) == []
    assert disc.coverage.entries == []


def test_another_client_error_of_an_operation_does_not_stop_the_next_one(
    monkeypatch,
):
    disc = _disc()
    task = _task(disc, "ecs")
    calls = []

    def execute(client, service, region, operation):
        calls.append(operation)
        raise _error("InternalFailure")

    monkeypatch.setattr(disc, "_client", mock.Mock())
    monkeypatch.setattr(disc, "_execute_discovery_operation", execute)
    assert disc._discover_service_in_region(task) == 0
    assert len(calls) == len(task["config"]["operations"]) > 1


def test_an_unexpected_error_of_an_operation_is_one_warning_per_operation(
    monkeypatch, caplog
):
    disc = _disc()
    task = _task(disc, "ecs")

    def execute(client, service, region, operation):
        raise KeyError("detail-not-in-the-warning")

    monkeypatch.setattr(disc, "_client", mock.Mock())
    monkeypatch.setattr(disc, "_execute_discovery_operation", execute)
    with caplog.at_level(logging.WARNING):
        disc._discover_service_in_region(task)
    warnings = _warnings(caplog)
    assert len(warnings) == len(task["config"]["operations"]) > 1
    assert all(w.startswith("Operation error for ecs: KeyError") for w in warnings)
    assert all("detail-not-in-the-warning" not in w for w in warnings)


def test_an_answer_that_breaks_the_reader_is_unreadable_not_a_crash(caplog):
    class Broken(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("payload-detail")

    disc = _disc()
    problems = []
    with caplog.at_level(logging.WARNING):
        found = disc._extract_resources_from_response(
            Broken(), "Things", "sqs", R, "Queue", "list_queues", None, problems
        )
    assert found == 0
    assert problems == [1]
    assert "payload-detail" not in caplog.text


def test_a_certificate_that_cannot_be_normalized_is_not_listed(monkeypatch):
    disc = _disc()
    acm = _Acm(
        [{"CertificateArn": ARN}],
        {ARN: ["arn:aws:cloudfront::111122223333:distribution/E1"]},
    )
    monkeypatch.setattr(disc, "_client", lambda service, region=None: acm)
    monkeypatch.setattr(disc, "_normalize_resource", lambda *a, **k: None)
    assert disc._discover_cloudfront_certificates() == 0
    assert disc.resources == []
    assert "acm" not in disc.services_with_primary_resources
