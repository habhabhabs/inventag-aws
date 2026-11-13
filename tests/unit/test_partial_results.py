"""Per-account partial results (state-layer part of resume support)."""

import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone

import pytest

from inventag.state import StateManager
from inventag.state.partial_results import (
    PartialResultStore,
    make_run_key,
)

KEY = make_run_key({"accounts": ["111", "222"], "regions": ["us-east-1"]})


def _res(n, account="111"):
    return {"id": f"r{n}", "arn": f"arn:aws:s3:::r{n}", "source_account_id": account}


def _backdate(path, hours):
    when = datetime.now(timezone.utc) - timedelta(hours=hours)
    data = json.loads(path.read_text())
    data["completed_at"] = when.isoformat()
    path.write_text(json.dumps(data))
    os.utime(path, (when.timestamp(), when.timestamp()))


def test_run_key_depends_on_scope_only():
    assert make_run_key({"a": 1, "b": 2}) == make_run_key({"b": 2, "a": 1})
    assert make_run_key({"a": 1}) != make_run_key({"a": 2})


def test_save_and_load_round_trip(tmp_path):
    store = PartialResultStore(str(tmp_path), KEY)
    store.save_account("111", [_res(1), _res(2)], regions=["us-east-1"])
    loaded = store.load_account("111")
    assert [r["id"] for r in loaded.resources] == ["r1", "r2"]
    assert loaded.regions == ["us-east-1"]
    assert loaded.age() < timedelta(minutes=1)
    assert store.load_account("222") is None
    assert set(store.completed_accounts()) == {"111"}


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_files_are_private_and_secrets_are_redacted(tmp_path):
    store = PartialResultStore(str(tmp_path), KEY)
    path = store.save_account(
        "111",
        [{"id": "fn", "raw_data": {"Environment": {"Variables": {"K": "s3cr3t"}}}}],
    )
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert "s3cr3t" not in path.read_text()


def test_another_scope_never_reuses_results(tmp_path):
    PartialResultStore(str(tmp_path), KEY).save_account("111", [_res(1)])
    other = PartialResultStore(str(tmp_path), make_run_key({"regions": ["eu-west-1"]}))
    assert other.load_account("111") is None


def test_stale_results_are_not_reused(tmp_path):
    store = PartialResultStore(str(tmp_path), KEY, max_age_hours=24)
    path = store.save_account("111", [_res(1)])
    _backdate(path, 30)
    assert store.load_account("111") is None
    keep = PartialResultStore(str(tmp_path), KEY, max_age_hours=None)
    assert keep.load_account("111") is not None


@pytest.mark.parametrize("content", ["", "{", "[]", '{"schema": 99}', '{"schema": 1}'])
def test_corrupt_or_foreign_files_are_ignored_and_left_in_place(tmp_path, content):
    store = PartialResultStore(str(tmp_path), KEY)
    path = store.save_account("111", [_res(1)])
    path.write_text(content)
    assert store.load_account("111") is None
    assert path.read_text() == content


def test_failed_write_keeps_the_previous_result(tmp_path, monkeypatch):
    store = PartialResultStore(str(tmp_path), KEY)
    path = store.save_account("111", [_res(1)])
    before = path.read_bytes()
    monkeypatch.setattr(
        "inventag.state.state_manager.json.dump",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError):
        store.save_account("111", [_res(1), _res(2)])
    monkeypatch.undo()
    assert path.read_bytes() == before
    assert not list(path.parent.glob(".*.tmp"))


def test_account_id_cannot_escape_the_folder(tmp_path):
    store = PartialResultStore(str(tmp_path), KEY)
    path = store.save_account("../../evil", [_res(1)])
    assert path.parent == store.directory


def test_clear_removes_own_results_old_foreign_scope_results_and_empty_folders(
    tmp_path,
):
    own = PartialResultStore(str(tmp_path), KEY)
    own.save_account("111", [_res(1)])
    own.save_account("222", [_res(2)])
    other_key = make_run_key({"x": 1})
    other = PartialResultStore(str(tmp_path), other_key)
    fresh = other.save_account("111", [_res(1)])
    third = PartialResultStore(str(tmp_path), make_run_key({"x": 2}))
    stale = third.save_account("111", [_res(1)])
    _backdate(stale, 48)
    user_file = tmp_path / "partial" / KEY / "notes.txt"
    user_file.write_text("mine")

    assert own.clear() == 3
    assert fresh.exists()  # another scope, recent: left alone
    assert not stale.exists() and not third.directory.exists()
    assert user_file.read_text() == "mine"  # not ours: kept, so the folder stays
    user_file.unlink()
    other.clear()
    assert not (tmp_path / "partial").exists()  # no empty folder left behind


def test_snapshot_retention_and_listing_ignore_the_partial_folder(tmp_path):
    manager = StateManager(str(tmp_path), retention_days=1, max_snapshots=1)
    PartialResultStore(str(tmp_path), KEY).save_account("111", [_res(1)])
    for _ in range(3):
        manager.save_state([_res(1)], "111", ["us-east-1"])
    assert (tmp_path / "partial" / KEY / "111.json").exists()
    assert len(StateManager(str(tmp_path)).metadata_index) == 2


def test_run_key_must_come_from_make_run_key(tmp_path):
    with pytest.raises(ValueError):
        PartialResultStore(str(tmp_path), "../x")
    with pytest.raises(ValueError):
        PartialResultStore(str(tmp_path), KEY, max_age_hours=0)
