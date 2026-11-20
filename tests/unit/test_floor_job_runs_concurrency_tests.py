"""A2 (architect ruling 1, wave 2): the CI job at the boto3/botocore floor
(ci.yml, boto-floor-tests) runs the concurrency tests, so the limiter and its
wiring are checked at the oldest supported botocore."""

from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


def test_the_floor_job_runs_tests_unit_concurrency():
    job = yaml.safe_load(CI.read_text())["jobs"]["boto-floor-tests"]
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    pytest_lines = runs[runs.index("python -m pytest") :]
    assert "tests/unit/concurrency" in pytest_lines.split()
