"""State folder safety: atomic writes, permissions, secrets, retention, recovery."""

import json
import os
import stat
import sys
import threading
from pathlib import Path

import pytest

from inventag.state import StateManager
from inventag.state.state_manager import REDACTED, StateLoadError

ACCOUNT = "123456789012"


def _resource(n=1, **extra):
    r = {
        "service": "S3",
        "type": "Bucket",
        "id": f"bucket-{n}",
        "arn": f"arn:aws:s3:::bucket-{n}",
        "region": "us-east-1",
        "tags": {"Owner": "team"},
        "source_account_id": ACCOUNT,
    }
    r.update(extra)
    return r


def _write_snapshot(state_dir: Path, state_id: str, resources=None, **meta):
    """A snapshot file as InvenTag writes it (for old timestamps)."""
    resources = resources if resources is not None else [_resource()]
    metadata = {
        "timestamp": state_id,
        "version": "1.0",
        "account_id": ACCOUNT,
        "regions": ["us-east-1"],
        "resource_count": len(resources),
        "checksum": "x",
        "discovery_method": "test",
    }
    metadata.update(meta)
    path = state_dir / f"state_{state_id}.json"
    path.write_text(json.dumps({"metadata": metadata, "resources": resources}))
    return path


def _save(manager, resources=None, **kwargs):
    return manager.save_state(
        resources if resources is not None else [_resource()],
        ACCOUNT,
        ["us-east-1"],
        **kwargs,
    )


def _snapshot_files(state_dir: Path):
    return sorted(p.name for p in state_dir.glob("state_*.json"))


# ------------------------------------------------------------------ retention
def test_retention_defaults_are_30_days_and_100_snapshots(tmp_path):
    manager = StateManager(str(tmp_path / "s"))
    assert manager.retention_days == 30
    assert manager.max_snapshots == 100


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "30"])
def test_retention_values_are_validated(tmp_path, bad):
    with pytest.raises(ValueError):
        StateManager(str(tmp_path / "s"), retention_days=bad)
    with pytest.raises(ValueError):
        StateManager(str(tmp_path / "s"), max_snapshots=bad)


def test_none_keeps_everything(tmp_path):
    state_dir = tmp_path / "s"
    state_dir.mkdir()
    for i in range(5):
        _write_snapshot(state_dir, f"2020010{i + 1}_000000")
    manager = StateManager(str(state_dir), retention_days=None, max_snapshots=None)
    _save(manager)
    assert len(_snapshot_files(state_dir)) == 6


def test_age_limit_is_configurable(tmp_path):
    state_dir = tmp_path / "s"
    state_dir.mkdir()
    _write_snapshot(state_dir, "20200101_000000")
    _write_snapshot(state_dir, "20200102_000000")
    _write_snapshot(state_dir, "20200103_000000")
    manager = StateManager(str(state_dir), retention_days=30, max_snapshots=None)
    new_id = _save(manager)
    # Old ones go, except the one the new snapshot is compared with.
    assert _snapshot_files(state_dir) == [
        "state_20200103_000000.json",
        f"state_{new_id}.json",
    ]


def test_count_limit_is_configurable(tmp_path):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir), retention_days=None, max_snapshots=3)
    ids = [_save(manager) for _ in range(6)]
    assert _snapshot_files(state_dir) == [f"state_{i}.json" for i in ids[-3:]]
    assert set(manager.metadata_index) == set(ids[-3:])


def test_snapshot_just_written_and_its_baseline_are_never_removed(tmp_path):
    state_dir = tmp_path / "s"
    state_dir.mkdir()
    _write_snapshot(state_dir, "20200101_000000")
    manager = StateManager(str(state_dir), retention_days=1, max_snapshots=1)
    new_id = _save(manager)
    # Both are far past the limits, but one is the baseline for the new one.
    assert _snapshot_files(state_dir) == [
        "state_20200101_000000.json",
        f"state_{new_id}.json",
    ]
    # The next save no longer needs the old baseline.
    newer = _save(manager)
    assert _snapshot_files(state_dir) == [f"state_{new_id}.json", f"state_{newer}.json"]


def test_files_inventag_did_not_create_are_never_deleted(tmp_path):
    state_dir = tmp_path / "s"
    state_dir.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    mine = [
        state_dir / "notes.txt",
        state_dir / "state_backup.json",
        state_dir / "state_20200101.json",
        state_dir / "state_20200101_000000.json.bak",
    ]
    for path in mine:
        path.write_text("user file")
    (state_dir / "subdir").mkdir()
    (state_dir / "subdir" / "state_20200101_000000.json").write_text("user file")
    _write_snapshot(state_dir, "20200101_000000")
    _write_snapshot(state_dir, "20200102_000000")

    manager = StateManager(str(state_dir), retention_days=1, max_snapshots=1)
    # An edited index must not point deletes outside the state folder.
    manager.metadata_index["20190101_000000"] = {
        "file": str(victim),
        "metadata": {},
        "size_bytes": 1,
    }
    manager.metadata_index["20190102_000000"] = {
        "file": "../victim.txt",
        "metadata": {},
        "size_bytes": 1,
    }
    _save(manager)

    assert victim.read_text() == "keep me"
    for path in mine:
        assert path.read_text() == "user file"
    assert (state_dir / "subdir" / "state_20200101_000000.json").exists()
    assert not (state_dir / "state_20200101_000000.json").exists()


def test_stale_temp_files_of_crashed_runs_are_cleaned_but_others_are_not(tmp_path):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir))
    stale = state_dir / ".state_20200101_000000.123.abcd1234.tmp"
    stale.write_text("{")
    old = 1_000_000_000
    os.utime(stale, (old, old))
    fresh = state_dir / ".state_20990101_000000.123.abcd1234.tmp"
    fresh.write_text("{")
    foreign = state_dir / "other.tmp"
    foreign.write_text("x")
    os.utime(foreign, (old, old))
    _save(manager)
    assert not stale.exists()
    assert fresh.exists() and foreign.exists()


# --------------------------------------------------------------------- atomic
def test_failed_write_leaves_no_partial_snapshot_and_keeps_history(
    tmp_path, monkeypatch
):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir))
    first = _save(manager)
    before = (state_dir / f"state_{first}.json").read_bytes()

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("inventag.state.state_manager.json.dump", boom)
    with pytest.raises(OSError):
        _save(manager)
    monkeypatch.undo()

    assert _snapshot_files(state_dir) == [f"state_{first}.json"]
    assert (state_dir / f"state_{first}.json").read_bytes() == before
    assert not list(state_dir.glob(".*.tmp"))
    assert list(manager.metadata_index) == [first]


def test_new_ids_always_sort_after_existing_ones(tmp_path):
    """Retention frees the oldest same-second ID; it must not be reused."""
    manager = StateManager(str(tmp_path / "s"), retention_days=None, max_snapshots=2)
    ids = [_save(manager) for _ in range(5)]
    assert ids == sorted(ids) and len(set(ids)) == 5
    assert manager.load_state().metadata.timestamp == ids[-1]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_files_are_private_and_new_folder_is_owner_only(tmp_path):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir))
    _save(manager)
    assert stat.S_IMODE(state_dir.stat().st_mode) == 0o700
    for path in state_dir.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path.name


# ----------------------------------------------------------------- concurrency
def test_two_managers_in_one_folder_do_not_overwrite_each_other(tmp_path):
    state_dir = str(tmp_path / "s")
    a = StateManager(state_dir)
    b = StateManager(state_dir)
    id_a = _save(a, [_resource(1)])
    id_b = _save(b, [_resource(2)])
    assert id_a != id_b
    assert len(_snapshot_files(Path(state_dir))) == 2
    # The index of a fresh manager lists both, even if the index file lost one.
    fresh = StateManager(state_dir)
    assert set(fresh.metadata_index) == {id_a, id_b}
    assert fresh.load_state(id_a).resources[0]["id"] == "bucket-1"
    assert fresh.load_state(id_b).resources[0]["id"] == "bucket-2"


def test_threads_saving_at_once_keep_every_snapshot_readable(tmp_path):
    state_dir = str(tmp_path / "s")
    StateManager(state_dir)  # create the folder
    ids, errors = [], []

    def work(n):
        try:
            ids.append(_save(StateManager(state_dir), [_resource(n)]))
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(set(ids)) == 8
    fresh = StateManager(state_dir, retention_days=None, max_snapshots=None)
    assert len(fresh.metadata_index) == 8
    for state_id in ids:
        assert fresh.load_state(state_id, strict=True).resources


# ------------------------------------------------------------------- recovery
def test_lost_or_corrupt_index_is_rebuilt_from_snapshot_files(tmp_path):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir))
    ids = [_save(manager) for _ in range(3)]
    (state_dir / "metadata.json").write_text("{ not json")
    rebuilt = StateManager(str(state_dir))
    assert set(rebuilt.metadata_index) == set(ids)
    (state_dir / "metadata.json").unlink()
    assert set(StateManager(str(state_dir)).metadata_index) == set(ids)


def test_snapshots_load_after_the_folder_moved(tmp_path):
    """A CI cache restored to another path: the index holds old absolute paths."""
    old_dir = tmp_path / "old"
    manager = StateManager(str(old_dir))
    state_id = _save(manager)
    new_dir = tmp_path / "new"
    old_dir.rename(new_dir)
    moved = StateManager(str(new_dir))
    assert moved.load_state(state_id, strict=True).resources


def test_corrupt_snapshot_gives_a_clear_error_and_is_left_alone(tmp_path):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir))
    state_id = _save(manager)
    path = state_dir / f"state_{state_id}.json"
    path.write_text(path.read_text()[:50])  # truncated
    truncated = path.read_bytes()

    fresh = StateManager(str(state_dir))
    with pytest.raises(StateLoadError, match="corrupt or truncated"):
        fresh.load_state(state_id, strict=True)
    assert fresh.load_state(state_id) is None  # old behaviour: None, no crash
    assert path.read_bytes() == truncated  # never modified


def test_snapshot_from_a_newer_release_is_refused_with_a_message(tmp_path):
    state_dir = tmp_path / "s"
    state_dir.mkdir()
    _write_snapshot(state_dir, "20260101_000000", version="2.0", new_field=1)
    manager = StateManager(str(state_dir))
    with pytest.raises(StateLoadError, match="newer InvenTag"):
        manager.load_state("20260101_000000", strict=True)


def test_old_1_0_snapshots_and_unknown_metadata_fields_still_load(tmp_path):
    state_dir = tmp_path / "s"
    state_dir.mkdir()
    _write_snapshot(state_dir, "20260101_000000")
    _write_snapshot(state_dir, "20260102_000000", version="1.7", future_field="x")
    manager = StateManager(str(state_dir))
    old = manager.load_state("20260101_000000", strict=True)
    assert old.metadata.accounts_scanned is None
    assert manager.load_state("20260102_000000", strict=True).resources


def test_not_a_snapshot_json_is_reported(tmp_path):
    state_dir = tmp_path / "s"
    state_dir.mkdir()
    (state_dir / "state_20260101_000000.json").write_text("[1, 2, 3]")
    manager = StateManager(str(state_dir))
    assert manager.metadata_index == {}  # not listed: it is not a snapshot


def test_find_previous_state_skips_unreadable_snapshots_and_says_why(tmp_path):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir), retention_days=None, max_snapshots=None)
    good = _save(manager)
    bad = _save(manager)
    (state_dir / f"state_{bad}.json").write_text("{")
    current = _save(manager)
    found, problems = manager.find_previous_state(current)
    assert found == good
    assert len(problems) == 1 and bad in problems[0] and "corrupt" in problems[0]
    assert manager.find_previous_state(good) == (None, [])


# -------------------------------------------------------------------- secrets
def test_secrets_are_not_written_to_snapshots(tmp_path):
    state_dir = tmp_path / "s"
    manager = StateManager(str(state_dir))
    resources = [
        _resource(
            1,
            service="Lambda",
            raw_data={
                "FunctionName": "fn",
                "Environment": {"Variables": {"DB_PASSWORD": "hunter2-SECRET"}},
                "Handler": "a.h",
            },
        ),
        _resource(
            2,
            raw_data={
                "environment": [{"name": "TOKEN", "value": "tok-123456"}],
                "DbPassword": "pw-abcdef",
                "SecretString": "ss-abcdef",
                "private_key": "-----BEGIN KEY-----",
                "NextToken": None,
            },
        ),
    ]
    state_id = _save(manager, resources, security_analysis={"api_key": "ak-987654"})
    text = (state_dir / f"state_{state_id}.json").read_text()
    for secret in ["hunter2", "tok-123456", "pw-abcdef", "ss-abcdef", "BEGIN KEY"]:
        assert secret not in text
    assert "ak-987654" not in text
    loaded = manager.load_state(state_id)
    env = loaded.resources[0]["raw_data"]["Environment"]["Variables"]
    assert env == {"DB_PASSWORD": REDACTED}  # key kept, value gone
    assert loaded.resources[0]["raw_data"]["Handler"] == "a.h"
    # The caller's own list is not modified.
    assert resources[0]["raw_data"]["Environment"]["Variables"]["DB_PASSWORD"] == (
        "hunter2-SECRET"
    )


def test_tags_and_ordinary_fields_are_not_redacted(tmp_path):
    manager = StateManager(str(tmp_path / "s"))
    res = _resource(1, tags={"Password": "tag-value", "Owner": "x"}, state="running")
    state_id = _save(manager, [res])
    assert manager.load_state(state_id).resources[0] == res


# ---------------------------------------------------------------- account scope
def test_scope_is_recorded_and_derived(tmp_path):
    manager = StateManager(str(tmp_path / "s"), retention_days=None, max_snapshots=None)
    explicit = _save(manager, accounts_scanned=["111", "222"], accounts_failed=["333"])
    meta = manager.load_state(explicit).metadata
    assert meta.accounts_scanned == ["111", "222"]
    assert meta.accounts_failed == ["333"]
    derived = _save(
        manager,
        [_resource(1, source_account_id="111"), _resource(2, source_account_id="222")],
    )
    assert manager.load_state(derived).metadata.accounts_scanned == ["111", "222"]
    assert manager.load_state(derived).metadata.accounts_failed is None
