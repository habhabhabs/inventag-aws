"""v1.5.0 architect sign-off conditions 5 and 7 and security re-check R2: the
pages and the changelog say what the code does (spec Amendment 4, 12.1).
Proof: tests/unit/policy/test_v150_behaviour_fixes.py (scan sentences) and
tests/unit/policy/test_v150_signoff_fixes.py (patterns)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LANGS = (None, "es", "fr", "zh-Hans", "zh-Hant")
SCAN_LINES = [
    "`Exit code 3: the template's tag policy found violations (fail_on_tag_violations); this code comes before the policy check's code.`",
    "`Exit code 4: a security group rule is at or above --risk-threshold; this code comes before the policy check's code.`",
    "`Exit code 5: an account could not be scanned (--fail-on-account-error); this code comes before the policy check's code.`",
    "`Exit code 6: no resources were found (--fail-if-empty); this code comes before the policy check's code.`",
]
OUT_SCAN = {
    None: "On a scan with `--policy`, the last line gives the code the scan exits with: 7 when a finding failed at or above `--policy-fail-on` (a scan never exits with 8; only `inventag policy check` gives 8). 3, 4, 5 and 6 keep their meaning and win when they apply; the line is then one of these:",
    "es": "En un escaneo con `--policy`, la última línea da el código con el que termina el escaneo: 7 cuando un hallazgo falló con la gravedad de `--policy-fail-on` o más alta (un escaneo nunca termina con 8; solo `inventag policy check` da 8). 3, 4, 5 y 6 conservan su significado y ganan cuando se aplican; la línea es entonces una de estas:",
    "fr": "Lors d’une analyse avec `--policy`, la dernière ligne donne le code de sortie de l’analyse : 7 quand un constat a échoué à la gravité de `--policy-fail-on` ou au-dessus (une analyse ne sort jamais avec 8 ; seul `inventag policy check` donne 8). 3, 4, 5 et 6 gardent leur sens et l’emportent quand ils s’appliquent ; la ligne est alors l’une de celles-ci :",
    "zh-Hans": "在使用 `--policy` 的扫描中，最后一行给出扫描的退出码：当某个发现项在 `--policy-fail-on` 或更高的严重程度上失败时为 7（扫描从不以 8 退出；只有 `inventag policy check` 会给出 8）。3、4、5 和 6 保持其含义，并在适用时优先；此时最后一行是以下之一：",
    "zh-Hant": "在使用 `--policy` 的掃描中，最後一行給出掃描的結束代碼：當某個發現項在 `--policy-fail-on` 或更高的嚴重程度上失敗時為 7（掃描從不以 8 退出；只有 `inventag policy check` 會給出 8）。3、4、5 和 6 保持其含義，並在適用時優先；此時最後一行是以下之一：",
}
TPL_PATTERN = {
    None: "A regular expression that can take very long to match (a repeated group whose length varies, or two repeats with nothing fixed between them) is a problem; see [Policy files](./policy-files.md).",
    "es": "Una expresión regular que puede tardar mucho en coincidir (un grupo repetido cuya longitud varía, o dos repeticiones sin nada fijo entre ellas) es un problema; consulta [Archivos de políticas](./policy-files.md).",
    "fr": "Une expression régulière qui peut mettre très longtemps à correspondre (un groupe répété dont la longueur varie, ou deux répétitions sans rien de fixe entre elles) est un problème ; voir [Fichiers de politiques](./policy-files.md).",
    "zh-Hans": "可能需要很长时间才能匹配的正则表达式（长度可变的重复组，或两个重复之间没有固定内容）算作问题；见[策略文件](./policy-files.md)。",
    "zh-Hant": "可能需要很長時間才能匹配的正規表示式（長度可變的重複組，或兩個重複之間沒有固定內容）算作問題；見[策略檔案](./policy-files.md)。",
}


def page(rel, lang):
    base = (
        ROOT / "docs" if lang is None else ROOT / "website/translations" / lang / "docs"
    )
    return (base / rel).read_text(encoding="utf-8")


def flat(text):
    text = re.sub(r"\n\s*", "\n", text)
    text = re.sub(r"(?<=[\u3000-\u9fff\uff00-\uffef])\n", "", text)
    return " ".join(text.split())


@pytest.mark.parametrize("lang", LANGS)
def test_outputs_page_lists_the_scan_sentences(lang):
    text = flat(page("reference/outputs.md", lang))
    assert OUT_SCAN[lang] in text
    for line in SCAN_LINES:
        assert f"- {line}" in text, line


def test_the_scan_sentences_are_the_code():
    from inventag.policy.outputs import _common

    for line in SCAN_LINES:
        code = int(line[11])
        sentence = _common.exit_sentence(
            {"summary": {"exit_code": code}}, ("low", False)
        )
        assert f"`{sentence}`" == line


def test_governance_guide_has_the_scan_rows():
    text = flat(page("guides/governance-as-code.md", None))
    assert (
        "On a scan with `--policy`, a finding that failed at or above "
        "`--policy-fail-on` gives exit code 7, never 8 (only `inventag policy "
        "check` gives 8). Exit codes 3, 4, 5 and 6 keep their meaning and win when "
        "they apply; the last line then reads:" in text
    )
    for line in SCAN_LINES:
        assert f"| {line[11]} | {line} |" in text, line


@pytest.mark.parametrize("lang", LANGS)
def test_cli_page_states_the_pattern_check(lang):
    assert TPL_PATTERN[lang] in flat(page("reference/cli.md", lang))


def test_policy_files_states_the_pattern_limit():
    text = flat(page("reference/policy-files.md", None))
    assert (
        "Two repeats with nothing fixed between them (`a*a*`, `.*.*`) and a repeat "
        "of a group whose length varies (`(a{1,50}){1,50}`, `(a?){30}`) are refused "
        "too. The check is not complete: repeats with a fixed character between "
        "them (`.*x.*x.*x.*=`) or many optional characters in a row are accepted "
        "and can still be slow, so keep patterns short and anchored." in text
    )
    assert "| Depth of `include` between policy sets | 10 |" in page(
        "reference/policy-files.md", None
    )


def test_the_changelog_names_run_checks_and_trend_note():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index("## [v1.5.0]")
    unreleased = " ".join(text[start : text.index("\n## [", start + 1)].split())
    changed = unreleased[
        unreleased.index("### Changed") : unreleased.index("### Removed")
    ]
    removed = unreleased[
        unreleased.index("### Removed") : unreleased.index("### Security")
    ]
    assert (
        "`inventag.finops.checks.run_checks()` still accepts its `policy` argument "
        "and ignores it" in changed
    )
    assert "`inventag.core.cost_requests.trend_note()`" in removed
