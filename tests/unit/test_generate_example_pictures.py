"""The example generator's picture hashes (L-03): no drawing, no AWS, no PIL."""

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import PatternFill

_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "docs"
    / "generate_example_outputs.py"
)
_spec = importlib.util.spec_from_file_location("generate_example_outputs", _PATH)
gen = importlib.util.module_from_spec(_spec)
sys.modules["generate_example_outputs"] = gen
_spec.loader.exec_module(gen)


def _xlsx(path, value="a", fill="FF1F3A5F"):
    wb = Workbook()
    ws = wb.active
    ws.title = "S3"
    ws["A1"] = "Name"
    ws["A1"].fill = PatternFill("solid", fgColor=fill)
    ws["A2"] = value
    wb.save(path)
    return path


def _docx(path, text="hello", created="2026-01-01T00:00:00Z"):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", f"<w:t>{text}</w:t>")
        zf.writestr("docProps/core.xml", f"<created>{created}</created>")
    return path


def test_excel_hash_follows_values_fill_and_settings(tmp_path):
    base = gen.picture_inputs_hash(_xlsx(tmp_path / "a.xlsx"), sheet="S3")
    assert base == gen.picture_inputs_hash(_xlsx(tmp_path / "b.xlsx"), sheet="S3")
    changed_value = _xlsx(tmp_path / "c.xlsx", value="b")
    assert gen.picture_inputs_hash(changed_value, sheet="S3") != base
    changed_fill = _xlsx(tmp_path / "d.xlsx", fill="FF000000")
    assert gen.picture_inputs_hash(changed_fill, sheet="S3") != base
    same = tmp_path / "a.xlsx"
    assert gen.picture_inputs_hash(same, sheet="S3", crop_height=900) != base


def test_word_hash_follows_the_document_not_the_properties(tmp_path):
    base = gen.picture_inputs_hash(_docx(tmp_path / "a.docx"))
    other_props = _docx(tmp_path / "b.docx", created="2027-02-02T00:00:00Z")
    assert gen.picture_inputs_hash(other_props) == base
    other_text = _docx(tmp_path / "c.docx", text="changed")
    assert gen.picture_inputs_hash(other_text) != base
    assert gen.picture_inputs_hash(tmp_path / "a.docx", page=2) != base


def test_picture_records_the_hash_and_draws_only_on_request(tmp_path, monkeypatch):
    drawn = []
    monkeypatch.setattr(gen, "render_png", lambda *a, **k: drawn.append(a) or a[1])
    monkeypatch.setattr(gen, "PICTURE_INPUTS", {})
    src = _docx(tmp_path / "a.docx")
    assert gen.picture(src, tmp_path / "x.png", draw=False) is None
    assert drawn == [] and "x.png" in gen.PICTURE_INPUTS
    assert gen.picture(src, tmp_path / "y.png", draw=True) == tmp_path / "y.png"
    assert len(drawn) == 1


def _setup(tmp_path):
    png = tmp_path / "p.png"
    png.write_bytes(b"png")
    recorded = {"p.png": {"inputs": "h1", "png": gen.file_sha256(png)}}
    return recorded, {"p.png": "h1"}


def test_compare_pictures_clean(tmp_path):
    recorded, inputs = _setup(tmp_path)
    assert gen.compare_pictures(recorded, inputs, tmp_path) == []


def test_compare_pictures_finds_a_changed_source(tmp_path):
    recorded, _ = _setup(tmp_path)
    (problem,) = gen.compare_pictures(recorded, {"p.png": "h2"}, tmp_path)
    assert "p.png" in problem and "source changed" in problem


def test_compare_pictures_finds_missing_changed_and_unrecorded_files(tmp_path):
    recorded, inputs = _setup(tmp_path)
    (tmp_path / "p.png").write_bytes(b"other")
    assert "differs" in gen.compare_pictures(recorded, inputs, tmp_path)[0]
    (tmp_path / "p.png").unlink()
    assert "missing" in gen.compare_pictures(recorded, inputs, tmp_path)[0]
    assert "not in pictures.json" in gen.compare_pictures({}, inputs, tmp_path)[0]
    assert "no scenario" in gen.compare_pictures(recorded, {}, tmp_path)[0]


def test_write_pictures_round_trips(tmp_path, monkeypatch):
    png = tmp_path / "p.png"
    png.write_bytes(b"png")
    monkeypatch.setattr(gen, "PICTURES_FILE", tmp_path / "pictures.json")
    monkeypatch.setattr(gen, "PICTURE_INPUTS", {"p.png": "h1"})
    gen.write_pictures(tmp_path)
    assert gen.load_pictures() == {
        "p.png": {"inputs": "h1", "png": gen.file_sha256(png)}
    }
    assert gen.compare_pictures(gen.load_pictures(), {"p.png": "h1"}, tmp_path) == []


def test_shipped_pictures_json_matches_the_files_on_disk():
    recorded = json.loads(gen.PICTURES_FILE.read_text("utf-8"))
    img_dir = gen.ASSETS / "img"
    assert sorted(recorded) == sorted(p.name for p in img_dir.glob("*.png"))
    for name, entry in recorded.items():
        assert entry["png"] == gen.file_sha256(img_dir / name), name
        assert len(entry["inputs"]) == 64
