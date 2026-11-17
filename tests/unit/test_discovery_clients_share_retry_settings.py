"""A-73 (discovery part): every client discovery creates has the shared retry settings.

``inventag/discovery/aws_clients.py`` sets standard mode with 10 tries, and the
user's ``AWS_RETRY_MODE`` and ``AWS_MAX_ATTEMPTS`` win. A client made with a
bare ``session.client(...)`` gets the SDK default instead, so a throttled
call in that code path loses its resources after fewer tries than the docs say.

An AST scan of ``inventag/discovery`` (not the network, security and cost
analyzers, which belong to other owners): a ``session.client(`` or
``boto3.client(`` call must go through ``create_client``, or carry
``# retry-ok: <reason>`` on its line.
"""

import ast
import re
from pathlib import Path
from unittest import mock

import pytest

DISCOVERY = Path(__file__).resolve().parents[2] / "inventag" / "discovery"
NOT_SCANNED = {
    "aws_clients.py",  # the factory itself
    "network_analyzer.py",
    "security_analyzer.py",
    "cost_analyzer.py",
}
MARK = re.compile(r"#\s*retry-ok:\s*\S.{8,}")


def bare_client_calls(source: str):
    lines = source.splitlines()
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "client"
        ):
            continue
        owner = ast.unparse(node.func.value)
        if owner.split(".")[-1] not in {"session", "boto3", "_session"}:
            continue
        span = lines[node.lineno - 1 : node.end_lineno]
        if not any(MARK.search(line) for line in span):
            found.append(node.lineno)
    return found


def test_the_scan_sees_a_bare_client_and_accepts_the_factory_and_a_marked_one():
    assert bare_client_calls("c = self.session.client('s3')\n") == [1]
    assert bare_client_calls("c = boto3.client('s3')\n") == [1]
    assert bare_client_calls("c = create_client(self.session, 's3')\n") == []
    marked = "c = session.client('sts')  # retry-ok: a credential check, one call\n"
    assert bare_client_calls(marked) == []


@pytest.mark.parametrize(
    "path",
    sorted(p for p in DISCOVERY.glob("*.py") if p.name not in NOT_SCANNED),
    ids=lambda p: p.name,
)
def test_discovery_clients_go_through_the_shared_factory(path):
    assert bare_client_calls(path.read_text()) == []


def test_the_factory_gives_standard_mode_and_ten_tries(monkeypatch):
    monkeypatch.delenv("AWS_RETRY_MODE", raising=False)
    monkeypatch.delenv("AWS_MAX_ATTEMPTS", raising=False)
    from inventag.discovery.aws_clients import create_client

    session = mock.MagicMock()
    create_client(session, "eks", "us-east-1")
    config = session.client.call_args.kwargs["config"]
    assert config.retries == {"mode": "standard", "total_max_attempts": 10}
