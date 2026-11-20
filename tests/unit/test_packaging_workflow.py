"""The packaging workflow (.github/workflows/package.yml) and the job of
release.yml that calls it (plan v14 sections 3.5, 5.2 B3 and 5.6; architect
reviews of wave 1, items B3 and F2).

Nothing here runs a runner: the tests read the workflow as data and check the
rules of the repository (pinned actions, named runner images, least
privilege) and the rules of this workflow (build image pinned, no release
trigger, the notices addresses fetched, nothing published in a dry run).
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "package.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
DATA = yaml.safe_load(TEXT)
JOBS = DATA["jobs"]
PINNED = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")
NAMED_IMAGE = re.compile(r"^(ubuntu|macos)-\d+(\.\d+)?(-(arm|intel))?$")


def _triggers():
    # PyYAML (YAML 1.1) reads a bare `on:` key as True.
    return DATA.get("on", DATA.get(True))


def _steps(job):
    return JOBS[job]["steps"]


def _run_text(job):
    return "\n".join(step.get("run", "") for step in _steps(job))


def _all_steps():
    for name, job in JOBS.items():
        for step in job.get("steps", []):
            yield name, step


# ---- stage 1: triggers, permissions, the plan job -------------------------


def test_it_is_a_reusable_workflow_and_can_be_started_by_hand_only():
    # No release, push or schedule trigger: a release created with the
    # workflow's own token starts no workflow, and a second trigger would
    # package a tag twice (plan 3.5).
    assert set(_triggers()) == {"workflow_call", "workflow_dispatch"}


def test_both_triggers_take_a_tag_and_a_dry_run_flag_that_defaults_to_true():
    for name in ("workflow_call", "workflow_dispatch"):
        inputs = _triggers()[name]["inputs"]
        assert inputs["tag"]["required"] is True
        assert inputs["tag"]["type"] == "string"
        assert inputs["dry_run"]["type"] == "boolean"
        assert inputs["dry_run"]["default"] is True


def test_the_workflow_reads_no_secret_of_the_repository():
    assert "secrets." not in TEXT
    assert "secrets:" not in TEXT


def test_the_default_permission_is_read_only_contents():
    assert DATA["permissions"] == {"contents": "read"}


def test_every_job_states_its_permissions_and_only_two_jobs_hold_more_than_read():
    for name, job in JOBS.items():
        assert "permissions" in job, name
    holders = {
        name: job["permissions"]
        for name, job in JOBS.items()
        if set(job["permissions"].items()) - {("contents", "read")}
    }
    assert set(holders) <= {"provenance", "publish"}
    if "provenance" in holders:
        assert holders["provenance"] == {
            "contents": "read",
            "id-token": "write",
            "attestations": "write",
        }
    if "publish" in holders:
        assert holders["publish"] == {"contents": "write"}


def test_every_action_is_pinned_by_commit_with_its_version_in_a_comment():
    uses = [
        line
        for line in TEXT.splitlines()
        if re.match(r"^\s*-?\s*uses:", line) and not line.lstrip().startswith("#")
    ]
    assert uses
    for line in uses:
        ref = line.split("uses:", 1)[1].split("#")[0].strip()
        assert PINNED.match(ref), line
        assert re.search(r"#\s*v\d", line), line


def test_every_runner_image_is_named_and_literal():
    for name, job in JOBS.items():
        assert NAMED_IMAGE.match(job["runs-on"]), (name, job["runs-on"])


def test_every_checkout_drops_the_token_after_use():
    for name, step in _all_steps():
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] is False, name


def test_no_expression_of_the_inputs_is_pasted_into_a_script():
    # Inputs reach shell code through env: only (script injection).
    for name, step in _all_steps():
        assert "${{ inputs." not in step.get("run", ""), name
        assert "${{ github.event" not in step.get("run", ""), name


def test_one_run_per_tag_and_a_running_package_is_never_cancelled():
    group = DATA["concurrency"]
    assert "inputs.tag" in group["group"]
    assert group["cancel-in-progress"] is False


def test_the_plan_job_checks_the_tag_against_the_version_file():
    plan = JOBS["plan"]
    assert plan["outputs"].keys() >= {"tag", "version", "dry_run"}
    text = _run_text("plan")
    assert "inventag/_version.py" in text
    assert "^v[0-9]+\\.[0-9]+\\.[0-9]+$" in text
    for needed in ("requirements-lock.txt", "requirements-lock-build.txt"):
        assert needed in text
    checkout = [s for s in _steps("plan") if "checkout" in s.get("uses", "")][0]
    assert checkout["with"]["ref"] == "refs/tags/${{ inputs.tag }}"


def test_every_other_job_waits_for_the_plan():
    for name, job in JOBS.items():
        if name != "plan":
            assert "plan" in job["needs"], name
