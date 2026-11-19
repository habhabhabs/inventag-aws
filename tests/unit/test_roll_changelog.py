"""Rolling the Unreleased section of CHANGELOG.md at release time.

``.github/scripts/roll-changelog.sh`` is called by release.yml in the same
commit as the version bump. Each test runs the script on a small changelog in
a temporary folder. The tests need ``bash`` and ``awk``.
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "roll-changelog.sh"

HEAD = "# Changelog\n\nIntro text.\n\n"
OLD = "## [v1.2.0] - 2026-11-14\n\n### Added\n\n- Old entry.\n\n"
LINKS = (
    "[Unreleased]: https://github.com/o/r/compare/v1.2.0...HEAD\n"
    "[v1.2.0]: https://github.com/o/r/compare/v1.1.4...v1.2.0\n"
)
FILLED = HEAD + "## [Unreleased]\n\n### Fixed\n\n- New fix.\n\n" + OLD + LINKS
EMPTY = HEAD + "## [Unreleased]\n\n" + OLD + LINKS


def run(tmp_path, text, version="1.2.1", date="2026-11-15"):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text, encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), version, date, str(path)],
        capture_output=True,
        text=True,
    )
    return result, path.read_text(encoding="utf-8")


def test_filled_section_is_rolled_with_a_new_empty_unreleased(tmp_path):
    result, text = run(tmp_path, FILLED)
    assert result.returncode == 0, result.stderr
    assert text.startswith(
        HEAD + "## [Unreleased]\n\n## [v1.2.1] - 2026-11-15\n\n### Fixed\n"
    )
    assert "- New fix.\n\n## [v1.2.0] - 2026-11-14" in text
    assert "rolled into v1.2.1" in result.stdout


def test_link_references_follow(tmp_path):
    _, text = run(tmp_path, FILLED)
    assert (
        "[Unreleased]: https://github.com/o/r/compare/v1.2.1...HEAD\n"
        "[v1.2.1]: https://github.com/o/r/compare/v1.2.0...v1.2.1\n"
        "[v1.2.0]: https://github.com/o/r/compare/v1.1.4...v1.2.0\n"
    ) in text


def test_file_without_link_references_gets_none(tmp_path):
    _, text = run(tmp_path, FILLED.replace(LINKS, ""))
    assert "[v1.2.1]:" not in text
    assert "## [v1.2.1] - 2026-11-15" in text


def test_version_with_v_prefix_gives_the_same_result(tmp_path):
    _, plain = run(tmp_path, FILLED, version="1.2.1")
    _, prefixed = run(tmp_path, FILLED, version="v1.2.1")
    assert plain == prefixed


def test_empty_unreleased_changes_nothing(tmp_path):
    result, text = run(tmp_path, EMPTY)
    assert result.returncode == 0
    assert text == EMPTY
    assert "empty: nothing to do" in result.stdout


def test_running_twice_changes_nothing_the_second_time(tmp_path):
    _, once = run(tmp_path, FILLED)
    result, twice = run(tmp_path, once)
    assert result.returncode == 0
    assert twice == once


def test_already_rolled_version_changes_nothing_even_if_unreleased_has_notes(
    tmp_path,
):
    text = FILLED.replace(OLD, "## [v1.2.1] - 2026-11-15\n\n- Done.\n\n" + OLD)
    result, after = run(tmp_path, text)
    assert result.returncode == 0
    assert after == text
    assert "already has a section for v1.2.1" in result.stdout


def test_missing_unreleased_heading_is_an_error(tmp_path):
    text = FILLED.replace("## [Unreleased]", "## [Next]")
    result, after = run(tmp_path, text)
    assert result.returncode != 0
    assert "no '## [Unreleased]' heading" in result.stderr
    assert after == text


def test_missing_file_is_an_error(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT), "1.2.1", "2026-11-15", str(tmp_path / "none.md")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "not found" in result.stderr


@pytest.mark.parametrize(
    "version,date",
    [("1.2", "2026-11-15"), ("v1.2.x", "2026-11-15"), ("1.2.1", "15-11-2026")],
)
def test_bad_arguments_are_an_error(tmp_path, version, date):
    result, text = run(tmp_path, FILLED, version=version, date=date)
    assert result.returncode != 0
    assert text == FILLED


def test_the_real_changelog_rolls_and_keeps_every_older_section(tmp_path):
    real = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if "## [v99.0.0]" in real:
        pytest.skip("not applicable")
    result, text = run(tmp_path, real, version="99.0.0")
    assert result.returncode == 0
    older = [ln for ln in real.splitlines() if ln.startswith("## [v1.")]
    assert all(ln in text.splitlines() for ln in older)
    assert text.count("## [Unreleased]") == 1


# ------------------------- the check after a bump commit (C-09, P-16, WO-CI3)
CHECK = ROOT / ".github" / "scripts" / "check-unreleased-empty.sh"


def run_check(tmp_path, text):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text, encoding="utf-8")
    return subprocess.run(
        ["bash", str(CHECK), str(path)], capture_output=True, text=True
    )


def test_check_passes_on_an_empty_unreleased(tmp_path):
    result = run_check(tmp_path, EMPTY)
    assert result.returncode == 0
    assert "is empty" in result.stdout


def test_check_fails_on_notes_left_under_unreleased(tmp_path):
    result = run_check(tmp_path, FILLED)
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[0].startswith("::error::The Unreleased section of ")
    assert "(2 lines)" in lines[0]
    assert "7: ### Fixed" in lines and "9: - New fix." in lines


def test_check_passes_on_what_the_roll_leaves(tmp_path):
    _, rolled = run(tmp_path, FILLED)
    assert run_check(tmp_path, rolled).returncode == 0


def test_check_passes_on_the_v1_2_2_bump_commit_text(tmp_path):
    # The shape the real v1.2.2 bump commit (1f582a2) left: an empty
    # Unreleased directly above the new version heading.
    text = HEAD + "## [Unreleased]\n\n## [v1.2.2] - 2026-11-19\n\n- Fix.\n\n" + OLD
    assert run_check(tmp_path, text).returncode == 0


def test_check_without_heading_or_file_is_exit_2(tmp_path):
    assert run_check(tmp_path, FILLED.replace("## [Unreleased]", "## [Next]")).returncode == 2
    result = subprocess.run(
        ["bash", str(CHECK), str(tmp_path / "none.md")], capture_output=True, text=True
    )
    assert result.returncode == 2


def test_release_workflow_runs_the_check_on_the_bump_commit_push_only():
    import yaml

    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["changelog-after-bump"]
    condition = " ".join(job["if"].split())
    assert condition == (
        "github.event_name == 'push' && "
        "startsWith(github.event.head_commit.message, 'chore: bump version to ')"
    )
    assert "needs" not in job  # independent: it never holds back the publish job
    assert job["permissions"] == {"contents": "read"}
    runs = [step.get("run", "") for step in job["steps"]]
    assert "bash .github/scripts/check-unreleased-empty.sh CHANGELOG.md" in runs
    # No other job waits for it.
    for name, other in workflow["jobs"].items():
        assert "changelog-after-bump" not in str(other.get("needs", "")), name


def test_release_workflow_rolls_the_changelog_into_the_bump_commit():
    import yaml

    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )
    step = next(
        s
        for s in workflow["jobs"]["release"]["steps"]
        if s["name"] == "Commit and push version.json changes"
    )
    run_text = step["run"]
    roll = run_text.index(".github/scripts/roll-changelog.sh")
    add = run_text.index("git add version.json inventag/_version.py CHANGELOG.md")
    commit = run_text.index('git commit -m "chore: bump version to v')
    assert roll < add < commit
