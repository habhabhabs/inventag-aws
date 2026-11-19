"""No workflow runs the docs-migration JavaScript of scripts/*.js (row D-06).

The transformation, migration validation and health monitoring steps of
docs-deploy.yml were removed: the transformation changed no page of the site
(its one edit was in a page the site excludes), and the other two only read
files and checked what the build checks again.
"""

import re
from pathlib import Path

import pytest

WORKFLOWS = sorted(
    (Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml")
)
ROOT_JS = re.compile(r"(?<![\w./-])(\./)?scripts/[\w.-]+\.(c|m)?js\b")


def test_the_pattern_finds_a_call_of_a_root_script():
    assert ROOT_JS.search("          node scripts/transform-docs.js")
    assert not ROOT_JS.search("          node website/scripts/check-ci-examples.mjs")


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_no_workflow_runs_a_root_javascript_script(path):
    hits = [
        (number, line.strip())
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if ROOT_JS.search(line)
    ]
    assert hits == []
