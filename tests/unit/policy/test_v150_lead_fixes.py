"""v1.5.0 integration fixes, unstubbed (the real lock, loader, testing and
output modules): ``policy lock --check`` and ``policy check --locked`` (spec
10.3), a waivers file inside the policy folder, ``policy test`` on every
shipped set (spec 11.6), and owner-only findings files (lead decision 4)."""

import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

import inventag.policy
from inventag.policy import lock

from .cli_helpers import GOLDEN, NOW, policies_dir, run, snapshot_file

BUILTIN = Path(inventag.policy.__file__).resolve().parent / "builtin"
SHIPPED_SETS = sorted(
    p.name for p in BUILTIN.iterdir() if p.is_dir() and (p / "tests").is_dir()
)


@pytest.fixture
def folder(tmp_path):
    """A policy folder with ex01 (RDS-001) and a waivers file for R5."""
    target = policies_dir(tmp_path, "ex01.yaml")
    shutil.copy(GOLDEN / "waivers" / "w16.yaml", target / "waivers.yaml")
    return target


# ------------------------------------------------------------ lock --check
def test_lock_check_says_current_after_lock(folder):
    assert run(["lock", folder])[0] == 0
    code, out, err = run(["lock", folder, "--check"])
    assert (code, out, err) == (0, "policy.lock is current.\n", "")


def test_lock_check_names_a_changed_file_and_exits_1(folder):
    run(["lock", folder])
    policy = folder / "ex01.yaml"
    policy.write_text(policy.read_text().replace("high", "low"))
    code, out, err = run(["lock", folder, "--check"])
    assert code == 1 and out == ""
    assert (
        "error: ex01.yaml: changed since policy.lock was written; run 'inventag "
        "policy lock' to record the change, or restore the file.\n"
    ) == err


def test_lock_check_without_a_lock_is_exit_1_with_no_traceback(folder):
    code, out, err = run(["lock", folder, "--check"])
    assert code == 1 and out == ""
    assert err.startswith("error: policy.lock: file not found")
    assert "Traceback" not in err


# ------------------------------------------------------------ check --locked
def _check(folder, tmp_path, *extra):
    snap = snapshot_file(tmp_path)
    return run(
        ["check", "--snapshot", snap, "--policies", folder, "--now", NOW, "--locked"]
        + list(extra)
    )


def test_locked_check_runs_when_the_lock_holds(folder, tmp_path):
    run(["lock", folder])
    code, out, err = _check(folder, tmp_path, "--waivers", folder / "waivers.yaml")
    assert code == 0, err
    assert "waived" in out


def test_locked_check_refuses_a_changed_file(folder, tmp_path):
    run(["lock", folder])
    (folder / "waivers.yaml").write_text(
        (folder / "waivers.yaml").read_text().replace("2026-12-31", "2026-12-30")
    )
    code, out, err = _check(folder, tmp_path)
    assert (code, out) == (1, "")
    assert "error: waivers.yaml: changed since policy.lock was written" in err


def test_locked_check_refuses_a_missing_lock(folder, tmp_path):
    code, out, err = _check(folder, tmp_path)
    assert (code, out) == (1, "")
    assert err.startswith("error: policy.lock: file not found")


def test_locked_check_refuses_waivers_outside_the_policy_folder(folder, tmp_path):
    run(["lock", folder])
    outside = tmp_path / "w.yaml"
    shutil.copy(folder / "waivers.yaml", outside)
    code, out, err = _check(folder, tmp_path, "--waivers", outside)
    assert (code, out) == (1, "")
    assert "outside the policy directory" in err


def test_locked_check_refuses_waivers_not_in_the_lock(folder, tmp_path):
    """A file under tests/ is inside the folder but never in the lock."""
    run(["lock", folder])
    sub = folder / "tests"
    sub.mkdir()
    late = sub / "late.yaml"
    shutil.copy(folder / "waivers.yaml", late)
    code, out, err = _check(folder, tmp_path, "--waivers", late)
    assert (code, out) == (1, "")
    assert "tests/late.yaml: not listed in policy.lock" in err


# ------------------------------------------- waivers file in the policy folder
def test_list_accepts_a_waivers_file_in_the_policy_folder(folder):
    code, out, err = run(["list", "--policies", folder])
    assert code == 0, err
    assert "RDS-001" in out


def test_check_accepts_a_waivers_file_in_the_policy_folder(folder, tmp_path):
    snap = snapshot_file(tmp_path)
    code, out, err = run(
        ["check", "--snapshot", snap, "--policies", folder, "--now", NOW]
    )
    assert code == 0, err


def test_explain_accepts_a_waivers_file_in_the_policy_folder(folder, tmp_path):
    snap = snapshot_file(tmp_path)
    code, out, err = run(
        ["explain", "RDS-001", "--snapshot", snap, "--policies", folder, "--now", NOW]
    )
    assert code == 0, err
    assert out.startswith("RDS-001 (rds-001, high")


def test_the_waivers_file_in_the_folder_is_not_applied_without_waivers(
    folder, tmp_path
):
    """Waivers apply only through --waivers (spec 10.1); the file in the
    folder is skipped by the loader, not read as waivers."""
    snap = snapshot_file(tmp_path)
    code, out, err = run(
        [
            "check",
            "--snapshot",
            snap,
            "--policies",
            folder,
            "--now",
            NOW,
            "--fail-on",
            "high",
        ]
    )
    assert code == 7, err


# ------------------------------------------------------- policy test, shipped
def test_every_set_with_fixtures_is_found():
    assert SHIPPED_SETS == [
        "encryption-at-rest",
        "finops-checks",
        "naming",
        "public-exposure",
        "region-allowlist",
        "tagging-standard",
    ]


@pytest.mark.parametrize("name", SHIPPED_SETS)
def test_policy_test_passes_on_every_shipped_set(name, tmp_path):
    copy = tmp_path / name
    shutil.copytree(BUILTIN / name, copy)
    code, out, err = run(["test", copy])
    assert code == 0, out + err
    assert out.rstrip().endswith(", 0 failed.")


# -------------------------------------------------- owner-only findings files
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_policy_check_writes_owner_only_files(tmp_path):
    folder = policies_dir(tmp_path, "ex01.yaml")
    snap = snapshot_file(tmp_path)
    target = tmp_path / "out" / "new"
    old = os.umask(0o022)
    try:
        code, out, err = run(
            [
                "check",
                "--snapshot",
                snap,
                "--policies",
                folder,
                "--now",
                NOW,
                "--format",
                "json,sarif,junit,markdown",
                "--output-directory",
                target,
            ]
        )
    finally:
        os.umask(old)
    assert code == 0, err
    files = sorted(target.iterdir())
    assert [f.suffix for f in files] == [".json", ".md", ".sarif", ".xml"]
    for path in files:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    assert sorted(err.splitlines()) == sorted(f"Wrote {f}" for f in files)


# ------------------------------------------- lead decision 5 (v150-p6.md)
@pytest.mark.e2e
@pytest.mark.parametrize("verbose", [False, True])
def test_a_scan_prints_the_summary_always_and_logs_the_path_at_info(tmp_path, verbose):
    from tests.unit.finops.conftest import run_scan

    folder = policies_dir(tmp_path, "ex01.yaml")
    extra = ["--policy", str(folder)] + (["--verbose"] if verbose else [])
    scan = run_scan(tmp_path, *extra)
    assert scan.code == 0, scan.stdout + scan.stderr
    assert "Exit code 0: findings are reported; no threshold was set." in scan.stdout
    (path,) = sorted(scan.out.glob("policy_findings_*.json"))
    shown = f"Policy findings: {path}" in scan.stdout + scan.stderr
    assert shown is verbose
