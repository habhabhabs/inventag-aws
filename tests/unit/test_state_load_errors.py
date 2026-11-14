"""Bad and old snapshots are named, and save failures can be read by the caller.

Register rows A-18 and A-19 (plan section 4.1, order 13, state part):

* A snapshot whose ``resources`` holds entries that are not objects is not an
  InvenTag snapshot: it is skipped with the file named, instead of ending the
  comparison with "'str' object has no attribute 'get'" (S3 J1h).
* A previous snapshot written in an older snapshot format gives one warning
  that the change report may list format differences (S3 J1d, J1e).
* A metadata index that cannot be saved is recorded on the state manager
  (``last_index_error``), so the generator can tell the user (S3 J2c). A
  snapshot that cannot be saved already raises (S3 J2a, J2d).
"""

import json
import logging

import pytest

from inventag.state import DeltaDetector, StateManager
from inventag.state import state_manager as sm_module
from inventag.state.state_manager import StateLoadError

ACC = "111111111111"


def _row(rid):
    return {
        "service": "SQS",
        "type": "Queue",
        "id": rid,
        "arn": f"arn:aws:sqs:us-east-1:{ACC}:{rid}",
        "region": "us-east-1",
        "source_account_id": ACC,
        "tags": {},
    }


def _save(sm, rows, **kw):
    return sm.save_state(rows, account_id=ACC, regions=["us-east-1"], **kw)


def _rewrite(sm, state_id, change):
    path = sm._state_path(state_id)
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))
    return path


def test_entries_that_are_not_objects_name_the_file(tmp_path):
    sm = StateManager(state_dir=str(tmp_path))
    good = _save(sm, [_row("q1")])
    bad = _save(sm, [_row("q1")])
    path = _rewrite(sm, bad, lambda d: d.update(resources=["q1", "q2"]))
    with pytest.raises(StateLoadError) as err:
        sm.load_state(bad, strict=True)
    assert str(path) in str(err.value)
    assert "entry 1 of 'resources' is a str, not an object" in str(err.value)
    assert sm.load_state(bad) is None


def test_comparison_skips_a_snapshot_with_bad_entries(tmp_path):
    sm = StateManager(state_dir=str(tmp_path))
    good = _save(sm, [_row("q1")])
    bad = _save(sm, [_row("q1")])
    current = _save(sm, [_row("q1"), _row("q2")])
    path = _rewrite(sm, bad, lambda d: d.update(resources=[1, 2]))
    previous, problems = sm.find_previous_state(current)
    assert previous == good
    assert len(problems) == 1 and str(path) in problems[0]
    report = DeltaDetector().detect_changes_by_state_id(sm, previous, current)
    assert [c.resource_id for c in report.added_resources] == ["q2"]


def test_comparing_with_a_bad_snapshot_directly_names_it(tmp_path):
    sm = StateManager(state_dir=str(tmp_path))
    bad = _save(sm, [_row("q1")])
    current = _save(sm, [_row("q1")])
    path = _rewrite(sm, bad, lambda d: d.update(resources=["q1"]))
    with pytest.raises(StateLoadError, match=str(path)):
        DeltaDetector().detect_changes_by_state_id(sm, bad, current)


def test_older_snapshot_format_gives_one_warning(tmp_path, caplog):
    sm = StateManager(state_dir=str(tmp_path))
    old = _save(sm, [_row("q1")])
    current = _save(sm, [_row("q1")])
    _rewrite(sm, old, lambda d: d["metadata"].update(version="1.0"))
    with caplog.at_level(logging.WARNING, logger="inventag.state.delta_detector"):
        DeltaDetector().detect_changes_by_state_id(sm, old, current)
    warnings = [
        r.getMessage() for r in caplog.records if "snapshot format" in r.getMessage()
    ]
    assert warnings == [
        f"Snapshot {old} was written in snapshot format 1.0 (this release writes "
        "1.1); the change report may list differences that come from the format, "
        "not from your resources."
    ]


def test_same_snapshot_format_gives_no_warning(tmp_path, caplog):
    sm = StateManager(state_dir=str(tmp_path))
    old = _save(sm, [_row("q1")])
    current = _save(sm, [_row("q1")])
    with caplog.at_level(logging.WARNING, logger="inventag.state.delta_detector"):
        DeltaDetector().detect_changes_by_state_id(sm, old, current)
    assert not [r for r in caplog.records if "snapshot format" in r.getMessage()]


def test_index_save_failure_is_recorded(tmp_path, monkeypatch):
    sm = StateManager(state_dir=str(tmp_path))
    assert sm.last_index_error is None

    def disk_full(path, data, **kw):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(sm_module, "_atomic_write_json", disk_full)
    state_id = _save(sm, [_row("q1")])
    assert state_id
    assert "No space left on device" in sm.last_index_error
    monkeypatch.undo()
    _save(sm, [_row("q2")])
    assert sm.last_index_error is None


def test_snapshot_save_failure_raises(tmp_path, monkeypatch):
    """Present behaviour, pinned: the caller sees the failure as an exception."""
    sm = StateManager(state_dir=str(tmp_path))

    def disk_full(*a, **kw):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(sm_module, "open_private", disk_full)
    with pytest.raises(OSError, match="No space left on device"):
        _save(sm, [_row("q1")])
