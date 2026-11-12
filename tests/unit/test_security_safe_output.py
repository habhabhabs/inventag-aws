"""Private file permissions, safe file names and formula neutralisation."""

import csv
import os
import stat
import zipfile

import pytest
from openpyxl import Workbook, load_workbook

from inventag.security.safe_output import (
    ensure_private_dir,
    neutralize_csv_value,
    neutralize_workbook_formulas,
    open_private,
    precreate_private,
    safe_filename_component,
    safe_join,
    write_safe_csv,
)

PAYLOADS = [
    '=HYPERLINK("http://evil.example","x")',
    "+cmd|' /C calc'!A0",
    "-2+3+cmd|' /C calc'!A0",
    "@SUM(1+1)*cmd|' /C calc'!A0",
    "\t=1+1",
    "\r=1+1",
    "＝1+1",
]

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@posix_only
def test_open_private_creates_0600_even_with_permissive_umask(tmp_path):
    old = os.umask(0)
    try:
        target = tmp_path / "secret.json"
        with open_private(target) as f:
            f.write("{}")
        assert _mode(target) == 0o600
        # An existing world-readable file is tightened on rewrite.
        os.chmod(target, 0o644)
        with open_private(target) as f:
            f.write("{}")
        assert _mode(target) == 0o600
    finally:
        os.umask(old)


@posix_only
def test_open_private_does_not_follow_symlinks(tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("original")
    link = tmp_path / "report.json"
    link.symlink_to(victim)
    with pytest.raises(OSError):
        with open_private(link) as f:
            f.write("attacker controlled")
    assert victim.read_text() == "original"


@posix_only
def test_ensure_private_dir_only_tightens_dirs_it_creates(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir(mode=0o755)
    os.chmod(existing, 0o755)
    created = ensure_private_dir(existing / "a" / "b")
    assert _mode(existing) == 0o755
    assert _mode(existing / "a") == 0o700
    assert _mode(created) == 0o700


@posix_only
def test_precreate_private_survives_library_save(tmp_path):
    target = tmp_path / "book.xlsx"
    precreate_private(target)
    Workbook().save(target)
    assert _mode(target) == 0o600


def test_open_private_refuses_read_mode(tmp_path):
    with pytest.raises(ValueError):
        open_private(tmp_path / "x", "r")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("../../etc/passwd", "etc_passwd"),
        ("..", "unnamed"),
        ("a/b\\c", "a_b_c"),
        ("name\x00with\nnull", "name_with_null"),
        (".hidden", "hidden"),
        ("prod-db.v1", "prod-db.v1"),
        (None, "unnamed"),
    ],
)
def test_safe_filename_component(value, expected):
    assert safe_filename_component(value) == expected


def test_safe_join_blocks_escape(tmp_path):
    assert safe_join(tmp_path, "ok.txt") == (tmp_path / "ok.txt").resolve()
    with pytest.raises(ValueError):
        safe_join(tmp_path, "../outside.txt")


@pytest.mark.parametrize("payload", PAYLOADS)
def test_csv_values_are_neutralised(payload):
    assert neutralize_csv_value(payload) == "'" + payload


@pytest.mark.parametrize("value", ["prod", "10.0.0.0/16", 42, -5, 3.5, None, True, ""])
def test_csv_harmless_values_unchanged(value):
    assert neutralize_csv_value(value) == value


def test_write_safe_csv_neutralises_headers_and_values(tmp_path):
    target = tmp_path / "out.csv"
    with open(target, "w", newline="", encoding="utf-8") as f:
        write_safe_csv(
            f,
            ["name", "=tagkey"],
            [{"name": PAYLOADS[0], "=tagkey": "ok"}, {"name": "x"}],
        )
    rows = list(csv.reader(target.open(encoding="utf-8")))
    assert rows[0] == ["name", "'=tagkey"]
    assert rows[1] == ["'" + PAYLOADS[0], "ok"]
    assert rows[2] == ["x", ""]


def test_workbook_formulas_become_literal_strings(tmp_path):
    wb = Workbook()
    ws = wb.active
    for i, payload in enumerate(PAYLOADS, start=1):
        ws.cell(row=i, column=1, value=payload)
    assert ws["A1"].data_type == "f"  # openpyxl would write a live formula
    changed = neutralize_workbook_formulas(wb)
    assert changed >= 1
    target = tmp_path / "x.xlsx"
    wb.save(target)
    with zipfile.ZipFile(target) as z:
        sheet_xml = z.read("xl/worksheets/sheet1.xml").decode()
    assert "<f>" not in sheet_xml and "<f " not in sheet_xml
    reloaded = load_workbook(target)
    assert reloaded.active["A1"].value == PAYLOADS[0]  # text preserved exactly
    assert reloaded.active["A1"].data_type == "s"
