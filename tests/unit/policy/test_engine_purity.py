"""The engine is pure: no AWS call, no socket, no clock, same bytes every time."""

import datetime as dt
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from inventag.policy import engine, loader

GOLDEN = Path(__file__).resolve().parent / "golden"
REPO = Path(__file__).resolve().parents[3]
NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
ALL = sorted(
    p.name for p in (GOLDEN / "policies").glob("*.yaml") if p.name.startswith("ex")
)


def evaluate_all(snapshot="s1.json"):
    loaded = loader.load([GOLDEN / "policies" / f for f in ALL], root=GOLDEN)
    data = json.loads((GOLDEN / snapshot).read_text())
    return engine.evaluate(data, loaded.policies, now=NOW, include_pass=True)


def test_no_aws_call_and_no_socket(monkeypatch):
    from inventag.security.read_only_guard import (
        get_installed_guard,
        install_global_guard,
        uninstall_global_guard,
    )

    def refuse(*a, **k):
        raise AssertionError("the policy engine opened a socket")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    had = get_installed_guard() is not None
    guard = install_global_guard()
    try:
        before = guard.audit_report()["total_calls"]
        evaluate_all()
        assert guard.audit_report()["total_calls"] == before
    finally:
        if not had:
            uninstall_global_guard()


def test_no_clock(monkeypatch):
    class Frozen(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            raise AssertionError("the policy engine read the clock")

        @classmethod
        def utcnow(cls):
            raise AssertionError("the policy engine read the clock")

    monkeypatch.setattr(engine, "datetime", Frozen, raising=False)
    evaluate_all()


SCRIPT = """
import datetime as dt, hashlib, json, sys
from pathlib import Path
from inventag.policy import engine, loader
golden = Path(sys.argv[1])
files = sorted(p for p in (golden / "policies").glob("ex*.yaml"))
loaded = loader.load(files, root=golden)
data = json.loads((golden / "s1.json").read_text())
now = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
result = engine.evaluate(data, loaded.policies, now=now, include_pass=True)
print(hashlib.sha256(engine.dumps(result).encode()).hexdigest())
"""


def test_byte_equal_under_three_hash_seeds():
    digests = set()
    for seed in ("0", "1", "4242"):
        proc = subprocess.run(
            [sys.executable, "-c", SCRIPT, str(GOLDEN)],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env={"PYTHONHASHSEED": seed, "PATH": os.environ.get("PATH", "")},
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        digests.add(proc.stdout.strip())
    assert len(digests) == 1


def test_dumps_is_sorted_two_space_indented_with_a_final_newline():
    text = engine.dumps({"b": 1, "a": [1, {"d": 2, "c": "é"}]})
    assert (
        text
        == '{\n  "a": [\n    1,\n    {\n      "c": "é",\n      "d": 2\n    }\n  ],\n  "b": 1\n}\n'
    )


def test_the_result_holds_no_host_user_or_clock():
    text = engine.dumps(evaluate_all())
    for word in (os.uname().nodename, str(Path.home()), str(REPO)):
        assert word not in text
    assert json.loads(text)["now"] == "2026-11-20"


def test_findings_are_sorted():
    result = evaluate_all()
    keys = [
        (f["policy"], f["account"], f["region"], f["resource"], f.get("from", ""))
        for f in result["findings"]
    ]
    assert keys == sorted(keys)
    assert [p["id"] for p in result["policies"]] == sorted(
        p["id"] for p in result["policies"]
    )
