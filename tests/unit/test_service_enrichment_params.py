"""Parameter guesses for the dynamic handler must not carry empty values."""

from unittest.mock import MagicMock

from inventag.discovery.service_enrichment import DynamicServiceHandler


def test_no_empty_arn_parameter_when_id_is_not_an_arn():
    handler = DynamicServiceHandler(MagicMock())
    patterns = handler._generate_parameter_patterns("Widget", "w-1", "")
    assert patterns
    assert all(value for pattern in patterns for value in pattern.values())
    assert {"WidgetArn": ""} not in patterns


def test_arn_parameters_are_used_when_an_arn_is_known():
    handler = DynamicServiceHandler(MagicMock())
    arn = "arn:aws:svc:us-east-1:123456789012:widget/w-1"
    patterns = handler._generate_parameter_patterns("Widget", "w-1", arn)
    assert {"ResourceArn": arn} in patterns
    assert {"WidgetArn": arn} in patterns
