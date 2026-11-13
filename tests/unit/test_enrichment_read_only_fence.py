"""Enrichment picks operations by name; the read-only policy refuses a value
read (ssm:GetParameter) even without the global guard. Needs
check_client_call() from the security review (inventag/security)."""

from unittest import mock

import boto3

from inventag.discovery.service_enrichment import ServiceAttributeEnricher


def test_get_parameter_is_refused_without_any_aws_call(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    handler = ServiceAttributeEnricher(boto3.Session()).handler_factory.get_handler(
        "ssm", "Parameter"
    )
    client = boto3.client("ssm", region_name="us-east-1")
    with mock.patch(
        "botocore.client.BaseClient._make_api_call",
        side_effect=AssertionError("no AWS call expected"),
    ):
        assert handler._safe_api_call(client, "get_parameter", Name="p") is None
