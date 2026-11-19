"""The docs examples check runs when a CLI parser changes, and deploys nothing (C-04)."""

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(config):
    # PyYAML (YAML 1.1) reads a bare `on:` key as True; the workflow quotes it.
    return config.get("on", config.get(True))


def test_runs_on_a_change_to_either_parser_in_a_push_and_a_pull_request():
    triggers = _triggers(_load("docs-examples-check.yml"))
    for event in ("push", "pull_request"):
        paths = triggers[event]["paths"]
        assert "inventag/cli/**" in paths
        assert "inventag/templating/cli.py" in paths


def test_runs_the_ci_examples_checker():
    job = _load("docs-examples-check.yml")["jobs"]["check-ci-examples"]
    commands = [step.get("run", "") for step in job["steps"]]
    assert any("scripts/docs/check_ci_examples.py" in c for c in commands)


def test_deploys_and_publishes_nothing():
    config = _load("docs-examples-check.yml")
    assert config["permissions"] == {"contents": "read"}
    for job in config["jobs"].values():
        assert "environment" not in job
        assert "permissions" not in job
        for step in job["steps"]:
            uses = step.get("uses", "")
            assert "deploy-pages" not in uses
            assert "upload-pages-artifact" not in uses
            assert "npm run build" not in step.get("run", "")


def test_the_docs_deployment_still_does_not_run_on_parser_changes():
    triggers = _triggers(_load("docs-deploy.yml"))
    for event in ("push", "pull_request"):
        assert not any(
            path.startswith("inventag/") for path in triggers[event]["paths"]
        )
