"""v1.5.0 security review (reports/v150-security-review.md), findings 2 and 8,
and architect rulings 5 and 6 of reports/architect-v150-p9-rulings.md: what
the pages, the examples and the changelog say is what the code does.

Proof of each sentence:
- debug output holds account IDs, ARNs, IP addresses and tag values:
  ``test_vv_output_holds_tag_values_and_account_ids`` (moto run);
- the list-shaped secret is masked, the two gaps remain:
  ``test_the_masking_gaps_the_pages_name``;
- the denied names give BLOCKED: ``test_validate_operations_blocks_the_v150_names``.
"""

import re
from pathlib import Path

import pytest

from inventag.cli import safety
from inventag.security.redaction import redact

ROOT = Path(__file__).resolve().parents[2]
LANGS = (None, "es", "fr", "zh-Hans", "zh-Hant")

SEC_GAP = {
    None: "Two exceptions are known: with `--debug` or `-vv`, a secret that AWS returns inside a mapping under a masked field name, or as an XML list (`<member>` items), can appear in the log file.",
    "es": "Se conocen dos excepciones: con `--debug` o `-vv`, un secreto que AWS devuelve dentro de un mapa bajo el nombre de un campo enmascarado, o como lista XML (elementos `<member>`), puede aparecer en el archivo de registro.",
    "fr": "Deux exceptions sont connues : avec `--debug` ou `-vv`, un secret qu’AWS renvoie dans un dictionnaire sous le nom d’un champ masqué, ou sous forme de liste XML (éléments `<member>`), peut apparaître dans le fichier journal.",
    "zh-Hans": "已知有两个例外：使用 `--debug` 或 `-vv` 时，AWS 在会被遮盖的字段名下以映射形式返回的机密，或以 XML 列表（`<member>` 项）形式返回的机密，可能出现在日志文件中。",
    "zh-Hant": "已知有兩個例外：使用 `--debug` 或 `-vv` 時，AWS 在會被遮蓋的欄位名下以對應形式返回的機密，或以 XML 列表（`<member>` 項）形式返回的機密，可能出現在日誌檔案中。",
}
STATUS_GAP = {
    None: "With `--debug` or `-vv`, a secret that AWS returns inside a mapping under a masked field name, or as an XML list (`<member>` items), can appear in the log file.",
    "es": "Con `--debug` o `-vv`, un secreto que AWS devuelve dentro de un mapa bajo el nombre de un campo enmascarado, o como lista XML (elementos `<member>`), puede aparecer en el archivo de registro.",
    "fr": "Avec `--debug` ou `-vv`, un secret qu’AWS renvoie dans un dictionnaire sous le nom d’un champ masqué, ou sous forme de liste XML (éléments `<member>`), peut apparaître dans le fichier journal.",
    "zh-Hans": "使用 `--debug` 或 `-vv` 时，AWS 在会被遮盖的字段名下以映射形式返回的机密，或以 XML 列表（`<member>` 项）形式返回的机密，可能出现在日志文件中。",
    "zh-Hant": "使用 `--debug` 或 `-vv` 時，AWS 在會被遮蓋的欄位名下以對應形式返回的機密，或以 XML 列表（`<member>` 項）形式返回的機密，可能出現在日誌檔案中。",
}
STATUS_URL = {
    None: "A few AWS answers hold a URL in a field named only `Url`; InvenTag does not call those operations and does not mask that field name.",
    "es": "Algunas respuestas de AWS contienen una URL en un campo que se llama solo `Url`; InvenTag no llama a esas operaciones y no enmascara ese nombre de campo.",
    "fr": "Quelques réponses d’AWS contiennent une URL dans un champ nommé seulement `Url` ; InvenTag n’appelle pas ces opérations et ne masque pas ce nom de champ.",
    "zh-Hans": "少数 AWS 响应会在仅名为 `Url` 的字段中包含 URL；InvenTag 不调用这些操作，也不遮盖该字段名。",
    "zh-Hant": "少數 AWS 回應會在僅名為 `Url` 的欄位中包含 URL；InvenTag 不呼叫這些操作，也不遮蓋該欄位名。",
}
SEC_CLASS = {
    None: "It also blocks, by name, operations that issue a token, credentials, a signed URL or a session, and operations that return customer content, such as `quicksight:GetSessionEmbedUrl`, `gameliftstreams:GetStreamUrl`, `polly:GetVoice` and `opensearchmemory:GetMemory`.",
    "es": "También bloquea, por su nombre, las operaciones que emiten un token, credenciales, una URL firmada o una sesión, y las operaciones que devuelven contenido de los clientes, como `quicksight:GetSessionEmbedUrl`, `gameliftstreams:GetStreamUrl`, `polly:GetVoice` y `opensearchmemory:GetMemory`.",
    "fr": "Elle bloque aussi, par leur nom, les opérations qui émettent un jeton, des identifiants, une URL signée ou une session, et les opérations qui renvoient du contenu des clients, comme `quicksight:GetSessionEmbedUrl`, `gameliftstreams:GetStreamUrl`, `polly:GetVoice` et `opensearchmemory:GetMemory`.",
    "zh-Hans": "它还按名称阻止签发令牌、凭证、签名 URL 或会话的操作，以及返回客户内容的操作，例如 `quicksight:GetSessionEmbedUrl`、`gameliftstreams:GetStreamUrl`、`polly:GetVoice` 和 `opensearchmemory:GetMemory`。",
    "zh-Hant": "它還按名稱阻止簽發權杖、憑證、簽名 URL 或會話的操作，以及返回客戶內容的操作，例如 `quicksight:GetSessionEmbedUrl`、`gameliftstreams:GetStreamUrl`、`polly:GetVoice` 和 `opensearchmemory:GetMemory`。",
}

OLD_GAP = {
    None: "a secret that AWS returns as a list under a masked field name",
    "es": "un secreto que AWS devuelve como lista bajo el nombre de un campo",
    "fr": "un secret qu’AWS renvoie sous forme de liste sous le nom",
    "zh-Hans": "AWS 以列表形式返回、且字段名会被遮盖的机密",
    "zh-Hant": "AWS 以列表形式返回、且欄位名會被遮蓋的機密",
}
EXAMPLE_CAVEAT = (
    "# -vv gives debug output: account IDs, ARNs, IP addresses, tag values and "
    "full AWS SDK responses (secrets are masked). In a public repository the job "
    "log is public: use -v there. The debug log is not uploaded as an artifact."
)
EXAMPLES = ("github_actions_cicd_example.yml", "aws_codebuild_buildspec.yml")
DENIED_IN_V150 = (
    "cognito-idp:GetDerivedToken",
    "wellarchitected:GetAgentOrganizationalReportData",
    "partnercentral-marketing:GetCampaignAssetExportTask",
    "partnercentral-selling:GetCustomerAccountBulkJobReportUrl",
    "partnercentral-selling:GetOpportunityBulkJobReportUrl",
    "glue:GetDashboardUrl",
    "gameliftstreams:GetStreamUrl",
    "gameliftstreams:ListStreamUrls",
    "quicksight:GetDashboardEmbedUrl",
    "quicksight:GetSessionEmbedUrl",
    "polly:GetVoice",
    "opensearchmemory:GetMemory",
    "opensearchmemory:SearchMemories",
    "opensearchmemory:SearchEvents",
    "connecthealth:GetMedicalCodingJob",
    "finspace-data:GetProgrammaticAccessCredentials",
    "finspace-data:GetExternalDataViewAccessDetails",
)


def page(rel, lang):
    base = (
        ROOT / "docs" if lang is None else ROOT / "website/translations" / lang / "docs"
    )
    return (base / rel).read_text(encoding="utf-8")


def flat(text):
    """Whitespace folded; CJK text has no spaces at line breaks."""
    text = re.sub(r"\n\s*", "\n", text)
    text = re.sub(r"(?<=[\u3000-\u9fff\uff00-\uffef])\n", "", text)
    return " ".join(text.split())


# ------------------------------------------------------------ finding 8
@pytest.mark.parametrize("lang", LANGS)
def test_the_old_list_gap_is_gone(lang):
    for rel in (
        "security/index.md",
        "getting-started/status.md",
        "guides/run-in-ci.md",
        "guides/run-a-scan.md",
        "reference/cli.md",
    ):
        assert OLD_GAP[lang] not in flat(page(rel, lang)), (rel, lang)


@pytest.mark.parametrize("lang", LANGS)
def test_security_and_status_name_the_gaps_that_remain(lang):
    assert SEC_GAP[lang] in flat(page("security/index.md", lang))
    assert STATUS_GAP[lang] in flat(page("getting-started/status.md", lang))


@pytest.mark.parametrize("lang", LANGS)
def test_status_names_the_url_limit(lang):
    assert STATUS_URL[lang] in flat(page("getting-started/status.md", lang))


@pytest.mark.parametrize("lang", LANGS)
def test_security_names_the_denied_classes(lang):
    assert SEC_CLASS[lang] in flat(page("security/index.md", lang))


def test_the_masking_gaps_the_pages_name():
    # fixed in v1.5.0 (A-74): a list under a masked name is masked
    assert "hunter2" not in redact('{"Passphrase": ["hunter2"]}')
    # stated limits (the pages name them): a mapping, and an XML list
    assert "hunter2" in redact('{"Passphrase": {"Value": "hunter2"}}')
    assert "hunter2" in redact("<Password><member>hunter2</member></Password>")


def test_validate_operations_blocks_the_v150_names():
    ok, lines = safety.validate_operations(list(DENIED_IN_V150))
    assert ok is False
    assert len(lines) == len(DENIED_IN_V150)
    for name, line in zip(DENIED_IN_V150, lines):
        assert line.startswith(f"BLOCKED  {name} "), line


def test_the_changelog_has_a_security_section():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index("## [v1.5.0]")
    unreleased = text[start : text.index("\n## [", start + 1)]
    security = unreleased[unreleased.index("### Security") :]
    flat_security = " ".join(security.split())
    for name in DENIED_IN_V150:
        service, operation = name.split(":")
        assert f"`{name}`" in flat_security or (
            operation in flat_security and service in flat_security
        ), name
    assert "`--validate-operations` now prints BLOCKED for them" in flat_security
    assert OLD_GAP[None] not in " ".join(unreleased.split())


# ------------------------------------------------------------ finding 2
@pytest.mark.parametrize("name", EXAMPLES)
def test_the_examples_do_not_keep_the_debug_log(name):
    text = (ROOT / "examples" / name).read_text(encoding="utf-8")
    assert EXAMPLE_CAVEAT in text
    assert "--log-file" not in text
    assert ".log" not in text.replace("changelog", "")
    for line in text.splitlines():
        if "inventag_cli.py" in line and "--verbose" in line:
            pytest.fail(line)


@pytest.mark.e2e
def test_vv_output_holds_tag_values_and_account_ids(tmp_path):
    from tests.unit.finops.conftest import run_scans

    vv, v = run_scans(tmp_path, ["-vv"], ["-v"])
    assert vv.code == 0 and v.code == 0
    assert "CC-1234" in vv.text  # a tag value in an SDK response body
    assert "123456789012" in vv.text
    assert "arn:aws:" in vv.text
    assert re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", vv.text)
    assert "CC-1234" not in v.text


# ------------------------------------- findings 1 and 4 to 7 (English pages)
POLICY_FILES = (
    "Exact, or a pattern when it contains `*` or `?`. A pattern with no literal "
    "character, such as `*`, `**`, `?*` or `[a-z]*`, is refused: a waiver cannot "
    "match every resource.",
    "It also lists every other file in the folder that a set names by path, "
    "whatever its suffix and also under `tests/`. When a policy uses "
    "`required-tags` with `policy: NAME`, the key `tag_policies` holds the "
    "SHA-256 of that tag policy's rules and scope as InvenTag resolves them. A "
    "change of the tag policy (in `INVENTAG_TEMPLATE_PATH`, "
    "`.inventag/templates/`, `~/.config/inventag/templates/` or a new InvenTag "
    "version) then also fails the check; run `inventag policy lock` again after "
    "such a change.",
    "Another placeholder, or a placeholder with a format spec or a conversion "
    "(such as `{name:>10}` or `{name!r}`), is an error.",
    "A pattern that repeats a group holding another repeat or a `|`, such as "
    "`(a+)+`, `(a|a)+` or `(.*a){20}`, is refused: it can take very long to "
    "match a value from a scanned account.",
    "| Length of a found text compared with `glob`, `regex`, `regex-case`, "
    "`name-pattern` or a tag `pattern` | 4096 characters (longer: not "
    "evaluated, `value_too_long`) |",
    "| Levels of lists and mappings in one file | 50 |",
    "| Set files reached through set files | 10 |",
    "A set file that a chain of set files reaches again is an error that names "
    "the chain.",
)
GOVERNANCE = (
    "A resource with no literal character, such as `*`, `**`, `?*` or "
    "`[a-z]*`, is refused.",
    "It also lists every other file a set names by path, and the rules of each "
    "tag policy that a `required-tags` check names with `policy:`.",
)


@pytest.mark.parametrize("sentence", POLICY_FILES)
def test_policy_files_page(sentence):
    assert sentence in flat(page("reference/policy-files.md", None))


@pytest.mark.parametrize("sentence", GOVERNANCE)
def test_governance_page(sentence):
    assert sentence in flat(page("guides/governance-as-code.md", None))


def test_the_pattern_limits_on_the_page_are_the_code():
    from inventag.policy import model

    assert model.LIMITS.yaml_depth == 50
    assert model.LIMITS.set_file_depth == 10
    assert model.LIMITS.found_string_length == 4096
