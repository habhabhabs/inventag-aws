"""The clients of the analyzers and of the reporting package use the shared retry settings (A-73).

They got the SDK default (3 tries) while discovery's clients get the shared
settings of ``inventag/discovery/aws_clients.py`` (standard mode, 10 tries; the
user's AWS_RETRY_MODE and AWS_MAX_ATTEMPTS win). The first test reads the code;
the second throttles one analyzer call and counts the tries.
"""

import ast
from pathlib import Path

import boto3
import pytest

from inventag.discovery.network_analyzer import NetworkAnalyzer
from inventag.discovery.security_analyzer import SecurityAnalyzer

ROOT = Path(__file__).resolve().parents[2] / "inventag"
FILES = sorted(
    [
        p
        for p in (ROOT / "reporting").glob("*.py")
        if p.name not in ("google_output.py",)
    ]
    + [ROOT / "discovery" / "network_analyzer.py"]
    + [ROOT / "discovery" / "security_analyzer.py"]
)


def _direct_client_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "client"
    ]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_client_is_created_outside_the_shared_factory(path):
    assert _direct_client_calls(path) == []


class _Throttled:
    status_code = 400
    headers = {}

    def __init__(self):
        self.content = (
            b'<?xml version="1.0"?><Response><Errors><Error><Code>'
            b"RequestLimitExceeded</Code><Message>slow down</Message></Error>"
            b"</Errors><RequestID>x</RequestID></Response>"
        )
        self.text = self.content.decode()
        self.raw = self


def _throttle_describe_vpcs(session):
    tries = []

    def before_send(request, **kwargs):
        tries.append(1)
        return _Throttled()

    session.events.register("before-send.ec2.DescribeVpcs", before_send)
    session.events.register("before-send.ec2.DescribeSecurityGroups", before_send)
    return tries


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    monkeypatch.delenv("AWS_RETRY_MODE", raising=False)
    monkeypatch.delenv("AWS_MAX_ATTEMPTS", raising=False)


ROW = [{"service": "VPC", "type": "VPC", "id": "vpc-1", "region": "us-east-1"}]


def test_a_throttled_network_analysis_call_is_tried_ten_times(no_sleep):
    session = boto3.Session(region_name="us-east-1")
    tries = _throttle_describe_vpcs(session)
    NetworkAnalyzer(session).analyze_vpc_resources(ROW)
    assert len(tries) == 10


def test_a_throttled_security_analysis_call_is_tried_ten_times(no_sleep):
    session = boto3.Session(region_name="us-east-1")
    tries = _throttle_describe_vpcs(session)
    SecurityAnalyzer(session).analyze_security_groups(ROW)
    assert len(tries) == 10


def test_the_users_max_attempts_wins(no_sleep, monkeypatch):
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "2")
    session = boto3.Session(region_name="us-east-1")
    tries = _throttle_describe_vpcs(session)
    NetworkAnalyzer(session).analyze_vpc_resources(ROW)
    assert len(tries) == 2
