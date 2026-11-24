"""v1.5.0 lead decisions (reports/v150-p6.md, "Needs a decision" 1 to 5): the
pages say what the code does, in five languages where the page is translated.

1. Exit code 8 only from ``inventag policy check``; a scan never exits with 8.
2. ``--finops-checks --template --policy --policy-fail-on S``: a FIN finding
   that fails at S or higher gives exit code 7 (behaviour:
   test_docs_claims_v150.test_finops_findings_count_for_policy_fail_on_with_template).
3. Both thresholds: the two sentences joined (behaviour: test_exit_sentence).
4. ``policy check`` files are owner-only, as the scan's.
5. ``Policy findings: <path>`` at INFO; the text summary always (behaviour:
   policy/test_v150_lead_fixes).
"""

import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LANGS = ("es", "fr", "zh-Hans", "zh-Hant")
GUIDE = ROOT / "docs/guides/governance-as-code.md"


def page(rel, lang=None):
    if lang is None:
        return (ROOT / "docs" / rel).read_text(encoding="utf-8")
    return (ROOT / "website/translations" / lang / "docs" / rel).read_text(
        encoding="utf-8"
    )


def flat(text):
    return " ".join(text.split())


def row(text, flag):
    (line,) = [x for x in text.splitlines() if x.startswith(f"| `{flag}`")]
    return line


def section(text, heading):
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start : end if end != -1 else None]


ALL = (None,) + LANGS
# first words of the "Terminal output" section of outputs.md
TERMINAL = {
    None: "Without `--verbose`, a run prints",
    "es": "Sin `--verbose`, una ejecución",
    "fr": "Sans `--verbose`, une exécution",
    "zh-Hans": "不使用 `--verbose` 时",
    "zh-Hant": "不使用 `--verbose` 時",
}


# ---------------------------------------------------------------- decision 1
def test_the_exit_code_list_says_a_scan_never_exits_with_8():
    from inventag import exit_codes

    doc = flat(exit_codes.__doc__)
    assert "A scan never exits with 8" in doc
    assert "On a scan, 8 and 7" not in doc


def test_the_guide_says_a_scan_never_exits_with_8():
    assert "A scan never exits with code 8" in flat(GUIDE.read_text())


@pytest.mark.parametrize("lang", ALL)
def test_the_cli_page_says_8_only_from_policy_check(lang):
    exits = row(page("reference/cli.md", lang), "--policy-fail-on SEVERITY")
    assert "8" in exits


# ---------------------------------------------------------------- decision 2
def test_the_cli_page_says_a_fin_fail_gives_7_with_policy_fail_on():
    text = flat(row(page("reference/cli.md"), "--finops-checks"))
    assert (
        "with `--template`, `--policy` and `--policy-fail-on SEVERITY`, the "
        "FinOps checks are checked together with your policies, so a `FIN-` "
        "finding that fails at that severity or higher gives exit code 7."
    ) in text


@pytest.mark.parametrize("lang", LANGS)
def test_the_translated_cli_pages_say_a_fin_fail_gives_7(lang):
    text = row(page("reference/cli.md", lang), "--finops-checks")
    assert "`--policy-fail-on SEVERITY`" in text
    assert "`FIN-`" in text and " 7" in text


# ---------------------------------------------------------------- decision 3
def test_the_guide_states_the_joined_sentences():
    assert (
        "| 0, both | The two sentences above, in that order, joined by one space. |"
        in (GUIDE.read_text())
    )


# ---------------------------------------------------------------- decision 4
@pytest.mark.parametrize("lang", ALL)
def test_the_outputs_page_says_the_findings_files_are_owner_only(lang):
    text = page("reference/outputs.md", lang)
    start = text.index("policy_findings_<timestamp>.<extension>")
    part = text[start : text.index("\n## ", start)]
    assert "0600" in part and "0700" in part, lang


def test_the_guide_says_the_findings_files_are_owner_only():
    text = flat(section(GUIDE.read_text(), "## Output files"))
    assert (
        "On Linux and macOS the files are readable and writable by their owner "
        "only (mode 0600)" in text
    )


@pytest.mark.e2e
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_a_scan_writes_owner_only_findings_files(tmp_path):
    from tests.unit.finops.conftest import run_scan

    from .policy.cli_helpers import policies_dir

    folder = policies_dir(tmp_path, "ex01.yaml")
    scan = run_scan(tmp_path, "--policy", str(folder), "--policy-format", "json,sarif")
    assert scan.code == 0, scan.stdout + scan.stderr
    files = sorted(scan.out.glob("policy_findings_*"))
    assert len(files) == 2
    for path in files:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path


# ---------------------------------------------------------------- decision 5
@pytest.mark.parametrize("lang", ALL)
def test_the_cli_page_says_the_path_line_needs_verbose(lang):
    text = row(page("reference/cli.md", lang), "--policy PATH")
    assert "`Policy findings: <path>`" in text and "`--verbose`" in text, lang


@pytest.mark.parametrize("lang", ALL)
def test_the_terminal_output_section_names_the_policy_lines(lang):
    text = page("reference/outputs.md", lang)
    start = text.index(TERMINAL[lang])
    part = text[start : text.index("\n## ", start)]
    assert "`Policy findings: <path>`" in part, lang


def test_the_guide_says_the_summary_is_always_printed():
    text = flat(section(GUIDE.read_text(), "## Check on a scan"))
    assert (
        "The summary is always printed. The line `Policy findings: <path>` is "
        "logged at INFO level, so it shows only with `--verbose`."
    ) in text
