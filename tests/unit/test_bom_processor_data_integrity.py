"""Deduplication, ordering and ID parsing in BOMDataProcessor."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig


def make_processor(**overrides):
    config = BOMProcessingConfig(
        enable_network_analysis=False,
        enable_security_analysis=False,
        enable_service_enrichment=False,
        enable_service_descriptions=False,
        enable_tag_mapping=False,
        **overrides,
    )
    return BOMDataProcessor(config, session=MagicMock())


def test_same_id_in_two_accounts_without_arn_is_two_resources():
    p = make_processor()
    rows = [
        {"service": "IAM", "type": "Role", "id": "admin", "source_account_id": "111"},
        {"service": "IAM", "type": "Role", "id": "admin", "source_account_id": "222"},
    ]
    assert len(p.process_inventory_data(rows).resources) == 2


def test_resources_without_arn_and_id_are_not_collapsed():
    p = make_processor()
    rows = [
        {"service": "EC2", "type": "Instance", "region": "us-east-1", "name": "a"},
        {"service": "EC2", "type": "Instance", "region": "us-east-1", "name": "b"},
    ]
    assert len(p.process_inventory_data(rows).resources) == 2


def test_different_types_with_same_id_are_kept():
    p = make_processor()
    rows = [
        {"service": "IAM", "type": "User", "id": "bob", "region": "global"},
        {"service": "IAM", "type": "Role", "id": "bob", "region": "global"},
    ]
    assert len(p.process_inventory_data(rows).resources) == 2


def test_duplicate_keeps_richer_copy_and_fills_gaps_from_the_other():
    p = make_processor()
    arn = "arn:aws:s3:::bucket"
    rows = [
        {"service": "S3", "type": "Bucket", "arn": arn, "tags": {"Owner": "a"}},
        {
            "service": "S3",
            "type": "Bucket",
            "arn": arn,
            "tags": {},
            "region": "us-east-1",
            "extra": 1,
        },
    ]
    out = p.process_inventory_data(rows).resources
    assert len(out) == 1
    assert out[0]["tags"] == {"Owner": "a"}  # blank tags filled from the other copy
    assert out[0]["extra"] == 1 and out[0]["region"] == "us-east-1"
    assert rows[0].get("extra") is None  # inputs are not changed by the merge


def test_first_seen_order_is_kept_after_dedup():
    p = make_processor()
    rows = [
        {"service": "S3", "arn": "arn:aws:s3:::b", "id": "b"},
        {"service": "S3", "arn": "arn:aws:s3:::a", "id": "a"},
        {"service": "S3", "arn": "arn:aws:s3:::b", "id": "b", "x": 1},
    ]
    out = p.process_inventory_data(rows).resources
    assert [r["id"] for r in out] == ["b", "a"]


def test_lambda_arn_gives_function_name_as_id():
    p = make_processor()
    rows = [
        {
            "service": "LAMBDA",
            "arn": "arn:aws:lambda:us-east-1:111111111111:function:my-fn",
        }
    ]
    out = p.process_inventory_data(rows).resources
    assert out[0]["id"] == "my-fn"
    assert out[0]["account_id"] == "111111111111"


def test_parallel_enrichment_keeps_input_order():
    p = make_processor(max_worker_threads=4)
    delays = {i: (0.05 if i % 2 == 0 else 0.0) for i in range(12)}

    def slow(resource):
        time.sleep(delays[resource["n"]])
        return dict(resource, done=True)

    p._enrich_single_resource = slow
    rows = [{"n": i, "id": str(i)} for i in range(12)]
    out = p._parallel_enrichment_processing(rows)
    assert [r["n"] for r in out] == list(range(12))
    assert all(r["done"] for r in out)


def test_parallel_enrichment_timeout_keeps_unfinished_resources():
    p = make_processor(max_worker_threads=1, processing_timeout=0.2)
    release = threading.Event()

    def blocked(resource):
        release.wait(5)
        return dict(resource, done=True)

    p._enrich_single_resource = blocked
    rows = [{"n": i, "id": str(i)} for i in range(3)]
    try:
        out = p._parallel_enrichment_processing(rows)
    finally:
        release.set()
    assert [r["n"] for r in out] == [0, 1, 2]
    assert not any(r.get("done") for r in out)
    assert any("did not finish" in w for w in p.statistics.warnings)


def test_statistics_counter_is_thread_safe():
    p = make_processor()

    def work():
        for _ in range(2000):
            p._count("tag_mapped")

    threads = [threading.Thread(target=work) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert p.statistics.tag_mapped == 8000
