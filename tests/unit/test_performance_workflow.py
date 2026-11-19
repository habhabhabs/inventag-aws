"""The weekly performance job exists, is scheduled, and is least-privilege (T-05)."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "performance.yml"
PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def _config():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _commands():
    jobs = _config()["jobs"].values()
    return [s.get("run", "") for j in jobs for s in j["steps"]]


def test_it_runs_weekly_and_by_hand_but_not_on_push_or_pull_request():
    triggers = _config().get("on", _config().get(True))
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    cron = triggers["schedule"][0]["cron"].split()
    assert len(cron) == 5 and cron[2] == "*" and cron[3] == "*" and cron[4] != "*"


def test_it_runs_the_performance_marker_and_the_delta_scaling_test():
    commands = _commands()
    assert any(
        "-m performance" in c and "test_performance_benchmarks.py" in c
        for c in commands
    )
    assert any("tests/unit/test_delta_detector_scaling.py" in c for c in commands)
    assert (ROOT / "tests/unit/test_delta_detector_scaling.py").exists()


def test_the_marker_it_selects_is_the_one_pytest_ini_excludes():
    ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "not performance" in ini


def test_it_has_least_privilege_and_pinned_actions():
    config = _config()
    assert config["permissions"] == {"contents": "read"}
    for job in config["jobs"].values():
        assert "permissions" not in job
        assert "timeout-minutes" in job
        for step in job["steps"]:
            if "uses" in step:
                assert PINNED.match(step["uses"]), step["uses"]
