"""A2 (architect ruling, wave 2 section 5; A1 finding 4): Cost Explorer
clients are never cached.

During an account's scan, ``cloud_bom_generator._bound_cost_explorer`` gives
the account's ``ce`` clients short timeouts under a short account limit, by
replacing ``session.client`` for that window. A cached ``ce`` client would
cross that window: one made before it would be used inside it without the
short timeouts, one made inside it would keep them afterwards. So
``create_client(session, "ce")`` always makes a new client, also on a session
whose cache is on. Other services stay cached.
"""

import boto3
from botocore.config import Config

from inventag.core.cloud_bom_generator import (
    _bound_cost_explorer,
    _cost_explorer_config,
)
from inventag.discovery.aws_clients import create_client, enable_client_cache


def _session():
    return boto3.Session(
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="fake-secret-for-tests-only",
        region_name="us-east-1",
    )


def test_cost_explorer_clients_are_not_cached():
    session = _session()
    enable_client_cache(session)
    first = create_client(session, "ce", "us-east-1")
    second = create_client(session, "ce", "us-east-1")
    assert first is not second


def test_other_services_stay_cached_next_to_cost_explorer():
    session = _session()
    enable_client_cache(session)
    create_client(session, "ce", "us-east-1")
    assert create_client(session, "s3", "us-east-1") is create_client(
        session, "s3", "us-east-1"
    )


def test_the_short_cost_explorer_settings_hold_only_inside_the_window():
    session = _session()
    enable_client_cache(session)
    before = create_client(session, "ce", "us-east-1")
    restore = _bound_cost_explorer(session, _cost_explorer_config(60))
    try:
        inside = create_client(session, "ce", "us-east-1")
    finally:
        restore()
    after = create_client(session, "ce", "us-east-1")

    default_read = Config().read_timeout
    assert before.meta.config.read_timeout == default_read
    assert inside.meta.config.read_timeout == 5.0
    assert after.meta.config.read_timeout == default_read
