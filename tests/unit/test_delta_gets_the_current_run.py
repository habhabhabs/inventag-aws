"""The change report gets what this run read (A-05 wiring, lead B's patch).

``DeltaDetector.detect_changes_by_state_id(..., current_run=...)`` exists on
lead B's branch (fix/delta-detector-performance), not on v1.2.0. The
generator passes the current run's coverage ledger, regions and services
only when the detector accepts the argument, so these tests pass with and
without that branch: they replace the detector method by a spy that accepts
it. A state manager that could not save its index (``last_index_error``,
lead B's branch) is reported in the result.
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


def test_a_detector_without_the_argument_still_compares(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    """v1.2.0's signature: no current_run; the comparison still runs."""
    calls = []
    original = DeltaDetector.detect_changes_by_state_id

    def old_signature(self, state_manager, old_id, new_id):
        calls.append(old_id)
        return original(self, state_manager, old_id, new_id)

    monkeypatch.setattr(DeltaDetector, "detect_changes_by_state_id", old_signature)
    results = result_spy(monkeypatch)
    assert run_cli(*ARGS) == 0
    assert run_cli(*ARGS) == 0
    assert len(calls) == 1
    assert "error" not in results[-1]["state_management"]["delta_detection"]


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
