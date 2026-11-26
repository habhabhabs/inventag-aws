"""UX plan U2/U3 (reports/architect-v150-ux-plan.md) and Alex's request of
24 Nov 2026 21:57 SGT ("Recommend -vv for CICD executions"): the pages state
the bare run and the levels, in five languages, and every page that
recommends ``-vv`` for CI/CD also says what debug output holds and to restrict
who can read the job log. The behaviour is proven by test_cli_bare_invocation
and test_cli_verbosity. The caveat's wording follows the v1.5.0 security review
(finding 2): what debug output holds, use ``-v`` in a public repository, and no
debug log as an artifact (test_docs_claims_v150_security)."""

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
    None: "For CI/CD runs, use `-vv`. Debug output holds account IDs, ARNs, IP addresses, tag values and the AWS SDK's full request and response bodies. Secrets are masked; the known gaps are listed under [Feature status](../getting-started/status.md#security-notes). In a public repository the job log is public, so use `-v` there. Elsewhere, restrict who can read the job log, and do not upload the debug log as an artifact.",
    "es": "Para las ejecuciones de CI/CD, usa `-vv`. La salida de depuración contiene los ID de cuenta, los ARN, las direcciones IP, los valores de las etiquetas y los cuerpos completos de las solicitudes y respuestas del SDK de AWS. Los secretos se enmascaran; los fallos conocidos se indican en [Estado de las funciones](../getting-started/status.md#security-notes). En un repositorio público, el registro del trabajo es público, así que usa `-v` allí. En los demás casos, restringe quién puede leer el registro del trabajo y no subas el registro de depuración como artefacto.",
    "fr": "Pour les exécutions CI/CD, utilisez `-vv`. La sortie de débogage contient les ID de compte, les ARN, les adresses IP, les valeurs des étiquettes et les corps complets des requêtes et des réponses du SDK AWS. Les secrets sont masqués ; les lacunes connues figurent dans [État des fonctionnalités](../getting-started/status.md#security-notes). Dans un dépôt public, le journal du job est public : utilisez donc `-v` dans ce cas. Ailleurs, limitez qui peut lire le journal du job et ne téléversez pas le journal de débogage comme artefact.",
    "zh-Hans": "在 CI/CD 运行中，请使用 `-vv`。调试输出包含账户 ID、ARN、IP 地址、标签值，以及 AWS SDK 完整的请求和响应正文。机密会被遮盖；已知的缺口列在[功能状态](../getting-started/status.md#security-notes)中。在公开仓库中，作业日志是公开的，因此请在那里使用 `-v`。在其他情况下，请限制谁可以读取作业日志，并且不要把调试日志作为产物上传。",
    "zh-Hant": "在 CI/CD 執行中，請使用 `-vv`。除錯輸出包含帳戶 ID、ARN、IP 地址、標籤值，以及 AWS SDK 完整的請求和回應正文。機密會被遮蓋；已知的缺口列在[功能狀態](../getting-started/status.md#security-notes)中。在公開儲存庫中，作業日誌是公開的，因此請在那裡使用 `-v`。在其他情況下，請限制誰可以讀取作業日誌，並且不要把除錯日誌作為產物上傳。",
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
