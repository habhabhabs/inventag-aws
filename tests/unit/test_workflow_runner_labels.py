"""Every GitHub Actions job names its runner image (rule P-15, row C-10).

A floating label such as ``ubuntu-latest`` moved to a new image on its own and
broke the docs deployment of a release. A job names the image version
(``ubuntu-24.04``). A floating label is allowed only with a dated note in the
comment block directly above the ``runs-on:`` line::

    # floating runner label, decided 2026-11-15: <reason>
"""

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = sorted(
    (Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml")
)

NAMED_IMAGE = re.compile(r"^(ubuntu|windows|macos)-\d+(\.\d+)?(-(arm|xlarge|intel))?$")
RUNS_ON = re.compile(r"^\s*runs-on:\s*(?P<value>\S.*?)\s*$")
DATED_NOTE = re.compile(r"^\s*#\s*floating runner label, decided \d{4}-\d{2}-\d{2}\b")


def floating_labels_without_note(text):
    """Return (line number, line) of each ``runs-on:`` that floats and has no dated note."""
    lines = text.splitlines()
    found = []
    for index, line in enumerate(lines):
        match = RUNS_ON.match(line)
        if not match:
            continue
        label = match.group("value").strip("'\"")
        if NAMED_IMAGE.match(label):
            continue
        # The comment lines directly above the runs-on line.
        above = []
        position = index - 1
        while position >= 0 and lines[position].lstrip().startswith("#"):
            above.append(lines[position])
            position -= 1
        floating = label.endswith("-latest")
        if floating and any(DATED_NOTE.match(item) for item in above):
            continue
        found.append((index + 1, line.strip()))
    return found


def test_the_checker_flags_a_floating_label():
    text = "jobs:\n  a:\n    runs-on: ubuntu-latest\n"
    assert floating_labels_without_note(text) == [(3, "runs-on: ubuntu-latest")]


def test_the_checker_accepts_a_named_image():
    assert (
        floating_labels_without_note("jobs:\n  a:\n    runs-on: ubuntu-24.04\n") == []
    )


def test_the_checker_accepts_a_floating_label_only_with_a_dated_note():
    noted = (
        "jobs:\n  a:\n"
        "    # floating runner label, decided 2026-11-15: reason\n"
        "    runs-on: ubuntu-latest\n"
    )
    undated = "jobs:\n  a:\n    # floating runner label, because\n    runs-on: ubuntu-latest\n"
    assert floating_labels_without_note(noted) == []
    assert floating_labels_without_note(undated) == [(4, "runs-on: ubuntu-latest")]


def test_the_checker_flags_a_label_it_cannot_read():
    text = "jobs:\n  a:\n    runs-on: ${{ matrix.os }}\n"
    assert floating_labels_without_note(text) == [(3, "runs-on: ${{ matrix.os }}")]


def test_workflows_were_found():
    assert len(WORKFLOWS) >= 10


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_every_job_names_its_runner_image(path):
    text = path.read_text(encoding="utf-8")
    assert floating_labels_without_note(text) == [], (
        f"{path.name}: name the runner image (for example ubuntu-24.04); a floating "
        "label needs a dated note directly above it"
    )
    jobs = yaml.safe_load(text)["jobs"]
    for name, job in jobs.items():
        if "uses" in job:  # a reusable workflow call has no runner of its own
            continue
        assert "runs-on" in job, f"{path.name}: job {name} has no runs-on"
