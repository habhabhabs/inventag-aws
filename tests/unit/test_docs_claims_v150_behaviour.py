"""v1.5.0 behaviour review (reports/v150-behaviour-review.md) F2, F4 and F6:
the pages say what the code does. Proof: tests/unit/policy/test_v150_behaviour_fixes.py.
"""

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LANGS = (None, "es", "fr", "zh-Hans", "zh-Hant")
cli_main = importlib.import_module("inventag.cli.main")

OUT_EXIT = {
    None: "- `summary.exit_code` is 0, 7 or 8 from `inventag policy check`. On a scan it is the code the scan exits with: 0, 3, 4, 5, 6 or 7 (5, 6, 3 and 4 come before 7), and the last line of the text says the same.",
    "es": "- `summary.exit_code` es 0, 7 u 8 con `inventag policy check`. En un escaneo es el código con el que termina el escaneo: 0, 3, 4, 5, 6 o 7 (5, 6, 3 y 4 van antes que 7), y la última línea del texto dice lo mismo.",
    "fr": "- `summary.exit_code` vaut 0, 7 ou 8 avec `inventag policy check`. Lors d’une analyse, c’est le code de sortie de l’analyse : 0, 3, 4, 5, 6 ou 7 (5, 6, 3 et 4 passent avant 7), et la dernière ligne du texte dit la même chose.",
    "zh-Hans": "- 使用 `inventag policy check` 时，`summary.exit_code` 是 0、7 或 8。在扫描中，它是扫描的退出码：0、3、4、5、6 或 7（5、6、3 和 4 优先于 7），文本的最后一行也给出同一个退出码。",
    "zh-Hant": "- 使用 `inventag policy check` 時，`summary.exit_code` 是 0、7 或 8。在掃描中，它是掃描的結束代碼：0、3、4、5、6 或 7（5、6、3 和 4 優先於 7），文字的最後一行也給出同一個結束代碼。",
}
CLI_SUMMARY_OLD = {
    None: "a text summary is printed",
    "es": "se imprime un resumen de texto",
    "fr": "un résumé en texte est affiché",
    "zh-Hans": "打印文字摘要",
    "zh-Hant": "列印文字摘要",
}
CLI_SUMMARY = {
    None: "a summary is printed (the counts of each policy, the fails by severity and the first 10 findings; `-v` prints every finding, and the files always hold all of them)",
    "es": "se imprime un resumen (los recuentos de cada política, los fallos por gravedad y los 10 primeros hallazgos; `-v` imprime todos los hallazgos, y los archivos siempre los contienen todos)",
    "fr": "un résumé est affiché (les comptes de chaque politique, les échecs par gravité et les 10 premiers constats ; `-v` affiche tous les constats, et les fichiers les contiennent toujours tous)",
    "zh-Hans": "打印摘要（每个策略的计数、按严重程度统计的失败数以及前 10 条发现项；`-v` 会打印全部发现项，文件中总是包含全部发现项）",
    "zh-Hant": "列印摘要（每個策略的計數、按嚴重程度統計的失敗數以及前 10 條發現項；`-v` 會列印全部發現項，檔案中總是包含全部發現項）",
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
def test_outputs_page_gives_the_scan_exit_code(lang):
    text = flat(page("reference/outputs.md", lang))
    assert OUT_EXIT[lang] in text


@pytest.mark.parametrize("lang", LANGS)
def test_cli_page_describes_the_scan_summary(lang):
    text = flat(page("reference/cli.md", lang))
    assert CLI_SUMMARY[lang] in text
    assert CLI_SUMMARY_OLD[lang] not in text


def test_the_summary_size_on_the_page_is_the_code():
    assert cli_main.SCAN_FINDINGS_SHOWN == 10


def test_the_editor_schema_section_names_four_kinds():
    text = flat(page("reference/policy-files.md", None))
    assert (
        "the fields of the four kinds `policy`, `policy-set`, `waivers` and "
        "`policy-test`." in text
    )


def test_the_changelog_names_the_summary_and_the_scan_code():
    text = " ".join((ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split())
    assert "a summary is printed (the counts of each policy" in text
    assert (
        "On a scan, the last line of the summary and `summary.exit_code` give the "
        "code the scan exits with" in text
    )
