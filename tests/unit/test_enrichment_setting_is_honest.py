"""The service-enrichment setting says what it does: nothing, and says so once.

Until now the BOM processor called ``ServiceAttributeEnricher.enrich_resource``,
a method that does not exist. The ``AttributeError`` was caught and logged at
DEBUG once per resource, so a scan raised hidden errors and the setting
``enable_service_enrichment`` did nothing without a word. Making enrichment run
or removing the key is the owner's decision (it changes reports or a config
key); this file pins only the honest part.
"""

import logging
from unittest.mock import Mock

import boto3

from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig
from inventag.reporting.settings_loader import apply_bom_settings

LOGGER = "inventag.reporting.bom_processor"

RESOURCES = [
    {
        "id": f"i-0{n}",
        "service": "EC2",
        "type": "Instance",
        "region": "us-east-1",
        "arn": f"arn:aws:ec2:us-east-1:123456789012:instance/i-0{n}",
        "tags": [{"Key": "Name", "Value": f"web-{n}"}],
    }
    for n in range(3)
]


def _config(**overrides):
    values = dict(
        enable_network_analysis=False,
        enable_security_analysis=False,
        enable_parallel_processing=False,
    )
    values.update(overrides)
    return BOMProcessingConfig(**values)


def _process(config, caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    processor = BOMDataProcessor(config, Mock(spec=boto3.Session))
    data = processor.process_inventory_data([dict(r) for r in RESOURCES])
    return data, caplog.records


def test_a_scan_raises_no_hidden_enrichment_error(caplog):
    _, records = _process(_config(), caplog)
    failed = [r.getMessage() for r in records if "enrichment failed" in r.getMessage()]
    assert failed == []


def test_key_set_by_the_user_logs_one_warning_that_it_has_no_effect(caplog):
    config = _config()
    apply_bom_settings(config, {"enable_service_enrichment": True}, "--bom-config x")
    _, records = _process(config, caplog)
    warnings = [
        r.getMessage()
        for r in records
        if r.levelno == logging.WARNING
        and "enable_service_enrichment" in r.getMessage()
    ]
    assert len(warnings) == 1
    assert "no effect" in warnings[0]


def test_default_settings_log_nothing_about_enrichment(caplog):
    _, records = _process(_config(), caplog)
    mentions = [r.getMessage() for r in records if "nrichment" in r.getMessage()]
    # Only the debug line that names the enricher component may remain.
    assert [m for m in mentions if "failed" in m or "no effect" in m] == []


def test_rows_are_the_same_whatever_the_enrichment_setting_says(caplog):
    on, _ = _process(_config(enable_service_enrichment=True), caplog)
    off, _ = _process(_config(enable_service_enrichment=False), caplog)
    assert on.resources == off.resources
    assert on.processing_statistics["service_enriched"] == 0
