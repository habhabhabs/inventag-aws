"""The weekly performance workflow: two jobs in one file.

Job `performance` (T-05) is scheduled and least-privilege. It also runs the
slow regression tests (`-m slow`), which no other workflow runs.

Job `benchmark` follows the rules of plan v14 section 2.9.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "performance.yml"
PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
TEXT = WORKFLOW.read_text(encoding="utf-8")
DATA = yaml.safe_load(TEXT)
TRIGGERS = DATA.get("on", DATA.get(True))
STEPS = DATA["jobs"]["benchmark"]["steps"]


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


def test_it_runs_the_slow_regression_tests():
    commands = _commands()
    assert any("-m slow" in c and "tests/regression" in c for c in commands)
    assert (ROOT / "tests/regression/test_failure_matrix.py").exists()


def test_the_marker_it_selects_is_the_one_pytest_ini_excludes():
    ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "not performance" in ini
    assert "not slow" in ini


def test_it_has_least_privilege_and_pinned_actions():
    config = _config()
    assert config["permissions"] == {"contents": "read"}
    for job in config["jobs"].values():
        assert "permissions" not in job
        assert "timeout-minutes" in job
        for step in job["steps"]:
            if "uses" in step:
                assert PINNED.match(step["uses"]), step["uses"]


def test_it_runs_weekly_and_on_demand_but_never_on_a_pull_request_or_push():
    assert set(TRIGGERS) == {"schedule", "workflow_dispatch"}
    assert len(TRIGGERS["schedule"]) == 1
    assert re.fullmatch(r"\d+ \d+ \* \* \d", TRIGGERS["schedule"][0]["cron"])


def test_it_can_only_read_the_repository_and_keeps_no_credentials():
    assert DATA["permissions"] == {"contents": "read"}
    checkouts = [s for s in STEPS if s.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 2
    assert all(s["with"]["persist-credentials"] is False for s in checkouts)


def test_every_action_is_pinned_by_commit():
    for step in STEPS:
        uses = step.get("uses")
        if uses:
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", uses), uses


def test_the_pinned_commits_are_the_ones_the_other_workflows_use():
    others = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / ".github" / "workflows").glob("*.yml")
        if p != WORKFLOW
    )
    for step in STEPS:
        uses = step.get("uses")
        if uses:
            assert uses in others, f"{uses} is not used by another workflow"


def test_the_baseline_is_a_checkout_of_the_tag_beside_the_candidate():
    baseline = [s for s in STEPS if s.get("with", {}).get("path") == "baseline"]
    assert len(baseline) == 1
    assert "'v1.3.0'" in baseline[0]["with"]["ref"]


def test_every_case_measures_baseline_then_candidate_in_one_job_then_compares():
    runs = [re.sub(r"\\\n\s*", " ", s["run"]) for s in STEPS if "run" in s]
    scan_steps = [r for r in runs if "scripts/benchmark_scan.py" in r]
    assert len(scan_steps) == 3
    assert "--inventag-root baseline" in scan_steps[0]
    assert "--inventag-root" not in scan_steps[1]
    assert "--check-case" in scan_steps[2]
    assert "--baseline" in scan_steps[2] and "--candidate" in scan_steps[2]


def test_the_cases_are_those_that_need_a_baseline():
    cases = DATA["jobs"]["benchmark"]["strategy"]["matrix"]["case"]
    assert cases == ["B1", "B2", "B3", "B4", "B7", "B8"]
    assert DATA["jobs"]["benchmark"]["strategy"]["fail-fast"] is False


def test_the_cases_exist_in_the_script():
    script = (ROOT / "scripts" / "benchmark_scan.py").read_text(encoding="utf-8")
    for case in DATA["jobs"]["benchmark"]["strategy"]["matrix"]["case"]:
        assert re.search(rf'"{case}":\s*dict\(', script), case


def test_the_workflow_states_the_real_aws_caveat():
    assert "Not verified against real AWS: any speed-up" in TEXT


def test_untrusted_values_reach_the_shell_only_through_env():
    for step in STEPS:
        run = step.get("run", "")
        assert "${{" not in run, f"expression inside a run script: {step.get('name')}"


def test_one_run_at_a_time_and_a_time_limit():
    assert DATA["concurrency"]["cancel-in-progress"] is False
    assert DATA["jobs"]["benchmark"]["timeout-minutes"] <= 60


@pytest.mark.parametrize("name", ["B5", "B6"])
def test_the_deterministic_cases_are_left_to_the_normal_suite(name):
    assert name not in DATA["jobs"]["benchmark"]["strategy"]["matrix"]["case"]
