"""website/scripts/assemble-locales.mjs (L-04): the assembled build has the real
/<locale>/ paths, and a build made without its base path is refused. Runs node on
small fixture folders; no site build."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "website" / "scripts" / "assemble-locales.mjs"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")


def _site(path, lang, prefix, extra=""):
    path.mkdir(parents=True)
    (path / "index.html").write_text(
        f'<html lang="{lang}"><head><link href="{prefix}assets/a.css"></head>'
        f"<body>{extra}</body></html>"
    )
    (path / "docs").mkdir()
    (path / "docs" / "x.html").write_text("x")
    return path


def _run(*args):
    return subprocess.run(
        ["node", str(SCRIPT), *map(str, args)], capture_output=True, text=True
    )


def test_assembles_english_at_the_root_and_the_locale_under_its_name(tmp_path):
    en = _site(tmp_path / "en", "en", "/inventag-aws/")
    fr = _site(tmp_path / "fr", "fr", "/inventag-aws/fr/")
    out = tmp_path / "out"
    done = _run("--en", en, "--locale", f"fr={fr}", "--out", out)
    assert done.returncode == 0, done.stderr
    assert (out / "index.html").read_text().count('lang="en"') == 1
    assert 'lang="fr"' in (out / "fr" / "index.html").read_text()
    assert (out / "fr" / "docs" / "x.html").is_file()
    assert (out / "docs" / "x.html").is_file()


def test_refuses_a_locale_built_without_its_base_path(tmp_path):
    en = _site(tmp_path / "en", "en", "/inventag-aws/")
    fr = _site(tmp_path / "fr", "fr", "/inventag-aws/")
    done = _run("--en", en, "--locale", f"fr={fr}", "--out", tmp_path / "out")
    assert done.returncode == 1
    assert "under /inventag-aws/fr/" in done.stderr
    assert not (tmp_path / "out").exists()


def test_refuses_a_wrong_language_and_an_unknown_locale(tmp_path):
    en = _site(tmp_path / "en", "en", "/inventag-aws/")
    es = _site(tmp_path / "es", "fr", "/inventag-aws/es/")
    done = _run("--en", en, "--locale", f"es={es}", "--out", tmp_path / "o")
    assert done.returncode == 1 and 'lang="fr"' in done.stderr
    de = _site(tmp_path / "de", "de", "/inventag-aws/de/")
    done = _run("--en", en, "--locale", f"de={de}", "--out", tmp_path / "o")
    assert done.returncode == 1 and "unknown locale de" in done.stderr


def test_refuses_an_english_folder_that_already_holds_a_locale(tmp_path):
    en = _site(tmp_path / "en", "en", "/inventag-aws/")
    _site(en / "fr", "fr", "/inventag-aws/fr/")
    fr = _site(tmp_path / "fr", "fr", "/inventag-aws/fr/")
    done = _run("--en", en, "--locale", f"fr={fr}", "--out", tmp_path / "o")
    assert done.returncode == 1 and "already holds /fr/" in done.stderr


def test_usage_error_exits_2(tmp_path):
    assert _run("--en", tmp_path).returncode == 2
