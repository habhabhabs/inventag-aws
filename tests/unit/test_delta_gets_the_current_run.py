"""The change report gets what this run read (A-05 wiring, lead B's patch).

The generator passes the current run's coverage ledger, regions and services
to ``DeltaDetector.detect_changes_by_state_id(..., current_run=...)`` (lead B).
The first test replaces the detector method by a spy that records the
argument; test_patch_tracks_together.py runs the real detector. A state
manager that could not save its index (``last_index_error``) is reported in
the result.
"""

from inventag.state import DeltaDetector, StateManager
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    GOOD_ID,
    aws,
    empty_aws,
    run_cli,
)
from tests.unit.test_snapshot_not_poisoned import result_spy

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]


def test_the_change_report_gets_the_current_run_when_it_accepts_it(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    seen = []
    original = DeltaDetector.detect_changes_by_state_id

    def spy(self, state_manager, old_id, new_id, current_run=None):
        seen.append(current_run)
        return original(self, state_manager, old_id, new_id)

    monkeypatch.setattr(DeltaDetector, "detect_changes_by_state_id", spy)
    assert run_cli(*ARGS) == 0
    assert run_cli(*ARGS) == 0
    assert len(seen) == 1 and seen[0] is not None
    scope = seen[0]
    assert scope["regions"] == {GOOD_ID: ["us-east-1"]}
    assert scope["services"] == {GOOD_ID: []}
    assert scope["coverage"] and all(
        e.get("account_id") == GOOD_ID for e in scope["coverage"]
    )


def test_an_unsaved_snapshot_index_is_in_the_result(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    original = StateManager.save_state

    def save_state(self, *args, **kwargs):
        state_id = original(self, *args, **kwargs)
        self.last_index_error = "Could not save metadata index: disk full"
        return state_id

    monkeypatch.setattr(StateManager, "save_state", save_state)
    results = result_spy(monkeypatch)
    assert run_cli(*ARGS) == 0
    assert (
        results[-1]["state_management"]["state_index_error"]
        == "Could not save metadata index: disk full"
    )
