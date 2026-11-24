"""UX plan U2/U3 (reports/architect-v150-ux-plan.md) and Alex's request of
24 Nov 2026 21:57 SGT ("Recommend -vv for CICD executions"): the pages state
the bare run and the levels, in five languages, and every page that
recommends ``-vv`` for CI/CD also says what debug output holds and to restrict
who can read the job log. The behaviour is proven by test_cli_bare_invocation
and test_cli_verbosity."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LANGS = (None, "es", "fr", "zh-Hans", "zh-Hant")

BARE_LINE = (
    "inventag: error: no option was given, so no scan was started. For the scan "
    "that a bare 'inventag' ran before v1.5.0, run: inventag --create-excel"
)
CAVEAT = {
    None: "For CI/CD runs, use `-vv`. Debug output holds the AWS SDK's request "
    "and response bodies, and one masking gap is known: a secret that AWS returns "
    "as a list under a masked field name can appear. CI logs are often kept and "
    "shared, so restrict who can read the job log.",
    "es": "Para las ejecuciones de CI/CD, usa `-vv`. La salida de depuración "
    "contiene los cuerpos de las solicitudes y respuestas del SDK de AWS, y se "
    "conoce un fallo del enmascaramiento: puede aparecer un secreto que AWS "
    "devuelve como lista bajo el nombre de un campo enmascarado. Los registros "
    "de CI a menudo se conservan y se comparten, así que restringe quién puede "
    "leer el registro del trabajo.",
    "fr": "Pour les exécutions CI/CD, utilisez `-vv`. La sortie de débogage "
    "contient les corps des requêtes et des réponses du SDK AWS, et une lacune "
    "du masquage est connue : un secret qu’AWS renvoie sous forme de liste sous "
    "le nom d’un champ masqué peut apparaître. Les journaux de CI sont souvent "
    "conservés et partagés, donc limitez qui peut lire le journal du job.",
    "zh-Hans": "在 CI/CD 运行中，请使用 `-vv`。调试输出包含 AWS SDK 的请求和响应正文，"
    "并且已知有一处遮蔽缺口：AWS 以列表形式返回、且字段名会被遮盖的机密可能会出现。"
    "CI 日志常被保留和共享，因此请限制谁可以读取作业日志。",
    "zh-Hant": "在 CI/CD 執行中，請使用 `-vv`。除錯輸出包含 AWS SDK 的請求和回應本文，"
    "並且已知有一處遮蔽缺口：AWS 以列表形式返回、且欄位名會被遮蓋的機密可能會出現。"
    "CI 日誌常被保留和共享，因此請限制誰可以讀取作業日誌。",
}
RECOMMENDING = ("reference/cli.md", "guides/run-a-scan.md", "guides/run-in-ci.md")
CI_PAGES = (
    "guides/run-in-ci.md",
    "examples/tag-policy-in-ci.md",
    "examples/scheduled-s3-upload.md",
    "guides/scan-multiple-accounts.md",
)


def page(rel, lang):
    base = (
        ROOT / "docs" if lang is None else ROOT / "website/translations" / lang / "docs"
    )
    return (base / rel).read_text(encoding="utf-8")


def flat(text):
    """Whitespace folded; CJK text has no spaces at line breaks."""
    text = re.sub(r"\n\s*", "\n", text)
    text = re.sub(r"(?<=[　-鿿＀-￯])\n", "", text)
    return " ".join(text.split())


def row(text, flag):
    (line,) = [x for x in text.splitlines() if x.startswith(f"| `{flag}`")]
    return line


# ---------------------------------------------------------------- the bare run
@pytest.mark.parametrize("lang", LANGS)
def test_the_cli_page_has_run_without_options(lang):
    text = page("reference/cli.md", lang)
    heading = "## Run without options" if lang is None else "{#run-without-options}"
    assert heading in text
    start = text.index(heading)
    part = text[start : text.index("\n## ", start + 1)]
    assert "`inventag --help`" in part and "`inventag --create-excel`" in part
    assert " 2" in part and "v1.5.0" in part


@pytest.mark.parametrize("lang", LANGS)
def test_exit_code_2_names_the_bare_run(lang):
    text = page("reference/cli.md", lang)
    (line,) = [x for x in text.splitlines() if x.startswith("| 2 |")]
    assert "`inventag`" in line


def test_the_english_cli_page_sentence():
    text = flat(page("reference/cli.md", None))
    assert (
        "`inventag` with no option prints the help page (the same text as "
        "`inventag --help`) and one error line, and exits with code 2. It starts "
        "no scan and makes no AWS call. Add `--create-excel`: `inventag "
        "--create-excel` runs the scan that `inventag` ran before v1.5.0."
    ) in text


@pytest.mark.parametrize("lang", LANGS)
def test_troubleshooting_shows_the_bare_run_line(lang):
    text = page("guides/troubleshooting.md", lang)
    assert BARE_LINE in text
    if lang is not None:
        assert "{#inventag-alone-prints-the-help-page}" in text


@pytest.mark.parametrize("lang", LANGS)
def test_quick_start_and_outputs_name_the_bare_run(lang):
    for rel in ("getting-started/quick-start.md", "reference/outputs.md"):
        text = flat(page(rel, lang))
        assert "`inventag`" in text and " 2" in text, (rel, lang)
    assert (
        "`inventag` with no option at all prints the help page and exits with code 2."
        in flat(page("getting-started/quick-start.md", None))
    )


# ---------------------------------------------------------------- the levels
@pytest.mark.parametrize("lang", LANGS)
def test_the_logging_table_has_vv(lang):
    text = page("reference/cli.md", lang)
    assert "`-vv`" in row(text, "--verbose")
    assert "`-vv`" in row(text, "--debug")
    assert "`-vv`" in row(text, "--log-file FILE")
    assert "INFO" in row(text, "--verbose")


@pytest.mark.parametrize("lang", LANGS)
def test_run_a_scan_has_a_vv_row(lang):
    text = page("guides/run-a-scan.md", lang)
    assert any(x.startswith("| `-vv` |") for x in text.splitlines())


@pytest.mark.parametrize("lang", LANGS)
def test_security_and_status_name_vv_beside_debug(lang):
    for rel in ("security/index.md", "getting-started/status.md"):
        text = page(rel, lang)
        assert text.count("`--debug`") == text.count("`-vv`"), (rel, lang)


# ------------------------------------------------- -vv for CI/CD, with caveat
@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("rel", RECOMMENDING)
def test_the_vv_recommendation_comes_with_its_caveat(rel, lang):
    text = flat(page(rel, lang))
    assert CAVEAT[lang] in text, (rel, lang)


@pytest.mark.parametrize("lang", LANGS)
def test_no_page_says_debug_is_safe_in_ci(lang):
    text = flat(page("guides/run-in-ci.md", lang))
    assert "Avoid `--debug` in CI" not in text
    assert "`-v` is safe" not in text


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("rel", CI_PAGES)
def test_the_example_workflows_use_vv(rel, lang):
    text = page(rel, lang)
    blocks = re.findall(r"```ya?ml[^\n]*\n(.*?)```", text, re.S)
    commands = [
        line
        for block in blocks
        for line in block.splitlines()
        if re.search(r"(^|[\s:-])inventag\s+-", line)
    ]
    assert commands, (rel, lang)
    for line in commands:
        assert " -vv " in line + " ", (rel, lang, line)


def test_the_changelog_has_the_three_changed_lines_and_the_ci_line():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index("## [Unreleased]")
    unreleased = text[start : text.index("\n## [", start + 1)]
    changed = unreleased[unreleased.index("### Changed") :]
    flat_changed = " ".join(changed.split())
    for line in (
        "`inventag` with no option now prints the help page and exits with code 2. "
        "It starts no scan and makes no AWS call. Before, it scanned with your "
        "current credentials and wrote an Excel report. Add `--create-excel` to get "
        "that run: `inventag --create-excel`.",
        "`-vv` (or `--verbose` twice) now gives debug output, the same as `--debug`. "
        "Before, `-vv` equalled `-v`. `-v`, `--verbose`, `-d` and `--debug` are "
        "unchanged.",
        "The meaning of exit code 2 now includes a run with no option.",
        "The CI/CD guide and its example workflows now use `-vv`",
    ):
        assert line in flat_changed, line
