"""A snapshot, an index or a change report that could not be made is in the
run notes (A-18).

v1.2.1: one ERROR line, then "BOM generation successful"; the next change
report silently compared with an older snapshot. Now each case gets one run
note (printed by the CLI after the summary, in ``results["run_notes"]``).
The exit code stays 0.
"""

import logging
from pathlib import Path

from inventag.state import DeltaDetector, StateManager
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    aws,
    empty_aws,
    run_cli,
)
from tests.unit.test_snapshot_not_poisoned import result_spy

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]


def notes_of(results):
    return results[-1]["run_notes"]


def test_a_snapshot_that_cannot_be_saved_is_in_the_run_notes(
    aws, tmp_path, monkeypatch, caplog  # noqa: F811
):
    caplog.set_level(logging.INFO)
    results = result_spy(monkeypatch)

    def save_state(self, *args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(StateManager, "save_state", save_state)
    assert run_cli(*ARGS) == 0  # as in v1.2.1
    state_dir = Path("out") / "state"  # as the user gave it
    assert (
        "The state snapshot was not saved ([Errno 28] No space left on device), "
        "so the next change report will compare with an older snapshot; check "
        f"that {state_dir} is writable."
    ) in notes_of(results), notes_of(results)


def test_an_index_that_cannot_be_saved_is_in_the_run_notes(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    results = result_spy(monkeypatch)
    original = StateManager.save_state

    def save_state(self, *args, **kwargs):
        state_id = original(self, *args, **kwargs)
        self.last_index_error = "Could not save metadata index: disk full"
        return state_id

    monkeypatch.setattr(StateManager, "save_state", save_state)
    assert run_cli(*ARGS) == 0
    state_dir = Path("out") / "state"  # as the user gave it
    assert (
        "The state snapshot was saved, but the list of snapshots could not be "
        "updated (Could not save metadata index: disk full), so the next change "
        f"report may compare with an older snapshot; check that {state_dir} is "
        "writable."
    ) in notes_of(results), notes_of(results)


def test_a_change_report_that_failed_is_in_the_run_notes(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    results = result_spy(monkeypatch)
    assert run_cli(*ARGS) == 0

    def broken(self, *args, **kwargs):
        raise ValueError("snapshot 20261115_000000 has no resources list")

    monkeypatch.setattr(DeltaDetector, "detect_changes_by_state_id", broken)
    assert run_cli(*ARGS) == 0
    assert (
        "The change report could not be made (snapshot 20261115_000000 has no "
        "resources list); the snapshot of this run was saved."
    ) in notes_of(results), notes_of(results)


def test_a_run_with_a_saved_snapshot_has_no_state_note(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    results = result_spy(monkeypatch)
    assert run_cli(*ARGS) == 0
    assert run_cli(*ARGS) == 0
    assert notes_of(results) == []
