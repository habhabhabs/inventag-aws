"""Docs claim checks of wave N-1 (docs only; no application change).

DOC1  examples/README.md says what the shipped accounts files do (C-12)
DOC4  every command in the shipped CI examples is accepted by the parser of the
      program it runs; every shipped configuration file loads with no warning (D-10, D-11)
DOC2  the sentences added for T-12, A-08b, A-43, D-02b to D-05 are on the pages
      in all five languages
"""

import importlib.util
import json
import logging
import re
import shlex
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
LOCALES = ("zh-Hans", "zh-Hant", "es", "fr")


# --------------------------------------------------------------------------- DOC1


def _accounts_settings(path):
    text = path.read_text("utf-8")
    data = yaml.safe_load(text)
    return data


def test_readme_names_the_five_files_with_an_explicit_role_arn():
    named = set()
    for path in EXAMPLES.glob("*accounts*"):
        if path.suffix not in (".json", ".yaml"):
            continue
        data = _accounts_settings(path)
        if any(
            isinstance(a, dict) and a.get("role_arn")
            for a in data.get("accounts", [])
            if not (a.get("access_key_id") or a.get("profile_name"))
        ):
            named.add(path.name)
    readme = (EXAMPLES / "README.md").read_text("utf-8")
    sentence = readme.split("Five of these files", 1)[1].split("\n\n", 1)[0]
    in_readme = set(
        re.findall(r"`([\w.-]+\.(?:json|yaml))`", sentence.split("Six files")[0])
    )
    # accounts_cross_account_roles.json and accounts_cli_example.* name roles too,
    # but never for an entry without credentials of its own to replace
    assert in_readme == {
        "accounts_aws_secrets_manager.json",
        "accounts_cicd_environment.json",
        "accounts_flexible_credentials.json",
        "accounts_github_secrets.json",
        "cicd_accounts_example.yaml",
    }
    assert in_readme <= named


def test_readme_names_the_six_files_that_cap_the_accounts_at_three_or_two():
    capped = set()
    for path in EXAMPLES.glob("*accounts*"):
        if path.suffix not in (".json", ".yaml"):
            continue
        value = (_accounts_settings(path).get("settings") or {}).get(
            "max_concurrent_accounts"
        )
        if value in (2, 3):
            capped.add(path.name)
    readme = (EXAMPLES / "README.md").read_text("utf-8")
    sentence = readme.split("Six files", 1)[1].split("\n\n", 1)[0]
    in_readme = set(re.findall(r"`([\w.-]+\.(?:json|yaml))`", sentence))
    assert len(in_readme) == 6
    # accounts_cli_example.* also say 3: they had the key under settings before
    assert in_readme <= capped


# --------------------------------------------------------------------------- DOC4

DEV_SCRIPT = ROOT / "scripts" / "development" / "cicd_bom_generation.py"
CI_FILES = [
    "aws_codebuild_buildspec.yml",
    "aws_codebuild_with_secrets_manager.yml",
    "docker_compose_cicd.yml",
    "github_actions_cicd_example.yml",
    "github_actions_with_secrets.yml",
    "jenkins_pipeline.groovy",
    "cicd_config_complete.json",
    "quick_start.sh",
]
_PLACEHOLDER = re.compile(r"\$|__GHA__|<[^<>\s]+>|%[A-Z_]+%|\\\$|\{\{")
_START = re.compile(
    r"(?:python3?\s+|\$PYTHON_CMD\s+)(inventag_cli\.py|(?:scripts/(?:development/)?)?cicd_bom_generation\.py)\b"
)


def _load_dev_parser(monkeypatch):
    spec = importlib.util.spec_from_file_location("n1_cicd_bom_generation", DEV_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    class _Stop(Exception):
        pass

    import argparse

    original = argparse.ArgumentParser.parse_args

    def grab(self, args=None, namespace=None):
        captured["parser"] = self
        raise _Stop

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", grab)
    monkeypatch.setattr(sys, "argv", ["cicd_bom_generation.py"])
    with pytest.raises(_Stop):
        module.parse_arguments()
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", original)
    return captured["parser"]


def _invocations(text):
    """Yield (script, argument string) for each shipped command that runs a program."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        match = _START.search(lines[i])
        if not match:
            i += 1
            continue
        rest = lines[i][match.end() :]
        i += 1
        while True:
            stripped = rest.rstrip()
            if stripped.endswith("\\") or stripped.endswith("\\\\"):
                rest = stripped.rstrip("\\") + " " + lines[i].strip()
                i += 1
            elif i < len(lines) and lines[i].strip().startswith("--"):
                rest = stripped + " " + lines[i].strip()
                i += 1
            else:
                break
        yield match.group(1).rsplit("/", 1)[-1], rest


def _tokens(arg_string):
    cleaned = re.sub(r"\$\{\{.*?\}\}", "__GHA__", arg_string)
    cleaned = cleaned.split("&&")[0].split(" || ")[0].split("; ")[0]
    cleaned = re.split(r"\s[|>]\s|\s2>", cleaned)[0]
    cleaned = re.sub(r"[\\\"']+$", "", cleaned.replace('\\"', '"').strip())
    try:
        return shlex.split(cleaned)
    except ValueError:
        return shlex.split(cleaned.replace("'", "").replace('"', ""))


def _clean(parser, tokens):
    """Placeholders: a value is replaced by one the option accepts; a placeholder
    that is not a value of a flag (a variable holding flags) is dropped."""
    by_flag = {f: a for a in parser._actions for f in a.option_strings}
    out, prev = [], None
    for token in tokens:
        if _PLACEHOLDER.search(token):
            if token.startswith("-"):
                prev = None
                continue
            if prev is None or prev.nargs == 0:
                continue
            if prev.choices:
                out.append(str(next(iter(prev.choices))))
            elif prev.type in (int, float):
                out.append("1")
            else:
                out.append("placeholder")
            continue
        out.append(token)
        prev = by_flag.get(token.partition("=")[0])
    return out


def _quiet(parser):
    import argparse

    def error(message):
        raise ValueError(message)

    parser.error = error
    for action in parser._actions:
        if isinstance(action.choices, dict):
            for child in action.choices.values():
                if isinstance(child, argparse.ArgumentParser):
                    _quiet(child)


def _jenkins_arguments(text):
    """The Groovy script builds the argument list from quoted strings."""
    block = text.split("def args = [", 1)[1].split("]", 1)[0]
    args = re.findall(r'"(--[^"]*)"', block)
    args += re.findall(r'args\.add\("(--[^"]*)"\)', text)
    return " ".join(args)


@pytest.mark.parametrize("name", CI_FILES)
def test_every_command_of_a_ci_example_is_accepted_by_its_program(name, monkeypatch):
    from inventag.cli.main import create_parser

    text = (EXAMPLES / name).read_text("utf-8")
    if name.endswith(".json"):
        text = "\n".join(
            str(v) for v in json.loads(text).get("cli_examples", {}).values()
        )
    found = [f for f in _invocations(text) if "args.join" not in f[1]]
    if name == "jenkins_pipeline.groovy":
        found.append(("cicd_bom_generation.py", _jenkins_arguments(text)))
    assert found, f"no command found in {name}"
    main_parser = create_parser()
    _quiet(main_parser)
    dev_parser = _load_dev_parser(monkeypatch)
    _quiet(dev_parser)
    for script, arguments in found:
        parser = main_parser if script == "inventag_cli.py" else dev_parser
        tokens = _clean(parser, _tokens(arguments))
        try:
            parser.parse_args(tokens)
        except SystemExit as exc:  # --help
            assert exc.code == 0, f"{name}: {script} {arguments}"
        except ValueError as exc:
            pytest.fail(f"{name}: {script} {arguments}: {exc}")


def test_no_example_names_the_development_script_by_a_path_that_does_not_exist():
    for path in EXAMPLES.iterdir():
        if path.is_file() and path.suffix in (
            ".yml",
            ".yaml",
            ".groovy",
            ".json",
            ".sh",
            ".md",
        ):
            for found in re.findall(
                r"scripts/[\w/]*cicd_bom_generation\.py", path.read_text("utf-8")
            ):
                assert (ROOT / found).is_file(), f"{path.name}: {found}"


CONFIG_FILES = {
    "service_descriptions": [
        "config/aws-prescriptive-guidance/service-descriptions.yaml",
        "config/defaults/services/service_descriptions_example.yaml",
        "examples/service-descriptions-example.yaml",
        "docs/assets/files/service-descriptions-example.yaml",
        "website/static/files/service-descriptions.yaml",
        "website/static/files/service-descriptions-example.yaml",
    ],
    "tag_mappings": [
        "config/aws-prescriptive-guidance/tag-mappings.yaml",
        "config/defaults/mappings/tag_to_column_mappings_example.yaml",
        "examples/tag-mappings-example.yaml",
        "docs/assets/files/tag-mappings-example.yaml",
        "website/static/files/tag-mappings.yaml",
        "website/static/files/tag-mappings-example.yaml",
    ],
}


@pytest.mark.parametrize("relative", CONFIG_FILES["service_descriptions"])
def test_a_shipped_service_descriptions_file_loads_with_no_warning(relative, caplog):
    from inventag.cli.config_validator import ConfigValidator
    from inventag.discovery.service_descriptions import ServiceDescriptionManager

    path = ROOT / relative
    result = ConfigValidator().validate_service_descriptions_file(str(path))
    assert result.errors == [] and result.warnings == [] and result.is_valid
    with caplog.at_level(logging.WARNING):
        manager = ServiceDescriptionManager()
        assert manager.load_descriptions_from_file(str(path)) is True
    assert [r.getMessage() for r in caplog.records] == []
    assert manager.get_service_description("EC2", "NoSuchType")


@pytest.mark.parametrize("relative", CONFIG_FILES["tag_mappings"])
def test_a_shipped_tag_mappings_file_loads_with_no_warning(relative, caplog):
    from inventag.cli.config_validator import ConfigValidator
    from inventag.discovery.tag_mapping import TagMappingEngine

    path = ROOT / relative
    result = ConfigValidator().validate_tag_mappings_file(str(path))
    assert result.errors == [] and result.warnings == [] and result.is_valid
    with caplog.at_level(logging.WARNING):
        engine = TagMappingEngine()
        assert engine.load_mappings_from_file(str(path)) is True
    assert [r.getMessage() for r in caplog.records] == []
    assert engine.mappings


@pytest.mark.parametrize(
    "name",
    [
        "service-descriptions.yaml",
        "tag-mappings.yaml",
        "service-descriptions-example.yaml",
        "tag-mappings-example.yaml",
    ],
)
def test_the_downloads_of_the_site_are_the_shipped_files(name):
    sources = {
        "service-descriptions.yaml": "config/aws-prescriptive-guidance",
        "tag-mappings.yaml": "config/aws-prescriptive-guidance",
        "service-descriptions-example.yaml": "examples",
        "tag-mappings-example.yaml": "examples",
    }
    shipped = (ROOT / sources[name] / name).read_bytes()
    assert (ROOT / "website" / "static" / "files" / name).read_bytes() == shipped


def test_the_tagging_dictionary_is_valid_yaml():
    path = ROOT / "config" / "aws-prescriptive-guidance" / "tagging-dictionary.yaml"
    assert isinstance(yaml.safe_load(path.read_text("utf-8")), dict)


def test_the_readme_lists_the_examples_that_run_the_development_script():
    readme = (EXAMPLES / "README.md").read_text("utf-8")
    section = readme.split("### CI examples", 1)[1].split("###", 1)[0]
    flat = " ".join(section.split())
    first, second = flat.split(" run the `inventag` options of `inventag --help`. ")
    second = second.split("run `scripts/development/cicd_bom_generation.py`")[0]
    pattern = r"`([\w.-]+\.(?:yml|sh|groovy|json))`"
    listed_main = set(re.findall(pattern, first))
    listed_dev = set(re.findall(pattern, second))
    dev, main = set(), set()
    for path in EXAMPLES.iterdir():
        if path.suffix not in (".yml", ".sh", ".groovy", ".json"):
            continue
        body = path.read_text("utf-8")
        if "scripts/development/cicd_bom_generation.py" in body:
            dev.add(path.name)
        elif "inventag_cli.py" in body:
            main.add(path.name)
    assert listed_dev == dev
    assert listed_main == main


def test_the_wheel_holds_only_the_package():
    text = (ROOT / "pyproject.toml").read_text("utf-8")
    assert 'include = ["inventag*"]' in text


# --------------------------------------------------------------------------- DOC2
# Each row: the English sentence, then the sentence of each other language.
# Pages are read from docs/ and website/translations/<locale>/docs/.

CAVEATS = {
    "getting-started/status.md": {
        "en": "Not verified against real AWS: the error code AWS returns when a session expires.",
        "zh-Hans": "未针对真实的 AWS 验证：会话过期时 AWS 返回的错误代码。",
        "zh-Hant": "未針對真實的 AWS 驗證：會話過期時 AWS 返回的錯誤程式碼。",
        "es": "No verificado contra AWS real: el código de error que devuelve AWS cuando caduca una sesión.",
        "fr": "Non vérifié sur un vrai AWS : le code d’erreur que renvoie AWS quand une session expire.",
    },
    "getting-started/introduction.md": {
        "en": "Not verified against AWS IAM Identity Center: sign-in with a real SSO session and the message for an expired token.",
        "zh-Hans": "未针对 AWS IAM Identity Center 验证：使用真实 SSO 会话登录，以及令牌过期时的提示信息。",
        "zh-Hant": "未針對 AWS IAM Identity Center 驗證：使用真實 SSO 會話登入，以及權杖過期時的提示資訊。",
        "es": "No verificado contra AWS IAM Identity Center: el inicio de sesión con una sesión SSO real y el mensaje de un token caducado.",
        "fr": "Non vérifié sur AWS IAM Identity Center : la connexion avec une vraie session SSO et le message d’un jeton expiré.",
    },
    "guides/troubleshooting.md": {
        "en": "Not verified against AWS IAM Identity Center: the message for an expired token.",
        "zh-Hans": "未针对 AWS IAM Identity Center 验证：令牌过期时的提示信息。",
        "zh-Hant": "未針對 AWS IAM Identity Center 驗證：權杖過期時的提示資訊。",
        "es": "No verificado contra AWS IAM Identity Center: el mensaje de un token caducado.",
        "fr": "Non vérifié sur AWS IAM Identity Center : le message d’un jeton expiré.",
    },
    "examples/scheduled-s3-upload.md": {
        "en": "Not verified against real AWS: the answer S3 gives for a bucket in another region.",
        "zh-Hans": "未针对真实的 AWS 验证：S3 对另一个区域中的存储桶给出的回应。",
        "zh-Hant": "未針對真實的 AWS 驗證：S3 對另一個區域中的儲存貯體給出的回應。",
        "es": "No verificado contra AWS real: la respuesta que da S3 para un bucket de otra región.",
        "fr": "Non vérifié sur un vrai AWS : la réponse que donne S3 pour un bucket d’une autre région.",
    },
}

# A distinctive part of each added sentence, per page and language.
ADDED = {
    "guides/network-and-security-analysis.md": {
        "en": "The subnet columns of a resource row name its first subnet only.",
        "zh-Hans": "资源行中的子网列只写出该资源的第一个子网。",
        "zh-Hant": "資源行中的子網欄只寫出該資源的第一個子網。",
        "es": "Las columnas de subred de la fila de un recurso nombran solo su primera subred.",
        "fr": "Les colonnes de sous-réseau de la ligne d’une ressource ne nomment que son premier sous-réseau.",
    },
    "reference/outputs.md": {
        "en": "No option leaves the `raw_data.*` columns out or compresses a snapshot; both are planned for a later release.",
        "zh-Hans": "目前没有选项可以省略 `raw_data.*` 列或压缩快照；两者都计划在以后的版本中提供。",
        "zh-Hant": "目前沒有選項可以省略 `raw_data.*` 欄或壓縮快照；兩者都計劃在以後的版本中提供。",
        "es": "Ninguna opción omite las columnas `raw_data.*` ni comprime una instantánea; ambas están previstas para una versión posterior.",
        "fr": "Aucune option n’omet les colonnes `raw_data.*` ni ne compresse un instantané ; les deux sont prévues pour une version ultérieure.",
    },
    "development/architecture.md": {
        "en": "Planned for removal in a later release:",
        "zh-Hans": "计划在以后的版本中移除：",
        "zh-Hant": "計劃在以後的版本中移除：",
        "es": "Previstos para su eliminación en una versión posterior:",
        "fr": "Dont la suppression est prévue dans une version ultérieure :",
    },
    "getting-started/installation.md": {
        "en": "The launchers are not part\nof the installed package, and no test runs them.",
        "zh-Hans": "这两个脚本不属于已安装的包，也没有测试运行过它们。",
        "zh-Hant": "這兩個指令碼不屬於已安裝的包，也沒有測試執行過它們。",
        "es": "ninguna prueba los ejecuta.",
        "fr": "aucun test ne les exécute.",
    },
    "examples/scheduled-s3-upload.md": {
        "en": "the error text in the log\n  adds a hint: set `AWS_DEFAULT_REGION` to the bucket's region and run again.",
        "zh-Hans": "日志中的错误文本会附上一条提示：把 `AWS_DEFAULT_REGION` 设为存储桶所在的区域，然后重新运行。",
        "zh-Hant": "日誌中的錯誤文字會附上一條提示：把 `AWS_DEFAULT_REGION` 設為儲存貯體所在的區域，然後重新執行。",
        "es": "el texto del error en el registro añade una pista: define `AWS_DEFAULT_REGION` con la región del bucket y ejecuta de nuevo.",
        "fr": "le texte de l’erreur dans le journal ajoute une indication : définissez `AWS_DEFAULT_REGION` sur la région du bucket et relancez.",
    },
    "guides/troubleshooting.md": {
        "en": "It prints no traceback.",
        "zh-Hans": "不会输出回溯信息。",
        "zh-Hant": "不會輸出回溯資訊。",
        "es": "No muestra ningún traceback.",
        "fr": "Elle n’affiche aucune trace d’appels (traceback).",
    },
}


def _page(locale, relative):
    if locale == "en":
        path = ROOT / "docs" / relative
    else:
        path = ROOT / "website" / "translations" / locale / "docs" / relative
    return path.read_text("utf-8")


def _flat(text):
    return " ".join(text.split())


@pytest.mark.parametrize("locale", ("en",) + LOCALES)
@pytest.mark.parametrize("relative", sorted(CAVEATS))
def test_the_added_caveats_are_on_the_pages_in_five_languages(locale, relative):
    assert CAVEATS[relative][locale] in _flat(_page(locale, relative))


@pytest.mark.parametrize("locale", ("en",) + LOCALES)
@pytest.mark.parametrize("relative", sorted(ADDED))
def test_the_added_sentences_are_on_the_pages_in_five_languages(locale, relative):
    assert _flat(ADDED[relative][locale]) in _flat(_page(locale, relative))


def test_the_caveats_use_the_frame_of_each_language():
    frames = {
        "en": "Not verified against ",
        "zh-Hans": "未针对",
        "zh-Hant": "未針對",
        "es": "No verificado contra ",
        "fr": "Non vérifié sur ",
    }
    for relative, by_locale in CAVEATS.items():
        for locale, sentence in by_locale.items():
            assert sentence.startswith(frames[locale]), (relative, locale)


def test_no_space_between_han_characters_in_the_added_chinese_sentences():
    han_space_han = re.compile(r"[一-鿿] [一-鿿]")
    for table in (CAVEATS, ADDED):
        for relative, by_locale in table.items():
            for locale in ("zh-Hans", "zh-Hant"):
                assert not han_space_han.search(by_locale[locale]), (relative, locale)


@pytest.mark.parametrize("locale", LOCALES)
def test_the_translated_pages_keep_the_english_code_and_links_of_the_new_text(locale):
    # a translated page names the same commands and file names as the English one
    for relative, by_locale in ADDED.items():
        english = _page("en", relative)
        translated = _page(locale, relative)
        for token in re.findall(r"`([^`]+)`", ADDED[relative]["en"]):
            if token in english:
                assert token in translated, (relative, token)


# ----- proofs of the sentences

SESSION_PAGE = "getting-started/status.md"


def test_the_expired_session_sentence_is_in_the_item_it_belongs_to():
    text = _page("en", SESSION_PAGE)
    item = text.split("- **A session that expires during the scan**", 1)[1]
    item = item.split("- **A session that is already expired", 1)[0]
    assert CAVEATS[SESSION_PAGE]["en"] in item


def test_permanent_redirect_adds_the_region_hint_to_the_logged_error(tmp_path, caplog):
    from unittest.mock import MagicMock

    from botocore.exceptions import ClientError

    from inventag.core.s3_upload import upload_files

    report = tmp_path / "r.xlsx"
    report.write_bytes(b"1")
    client = MagicMock()
    client.meta.region_name = "us-east-1"
    client.put_object.side_effect = ClientError(
        {"Error": {"Code": "PermanentRedirect", "Message": "use endpoint"}},
        "PutObject",
    )
    with caplog.at_level(logging.ERROR, logger="inventag.core.s3_upload"):
        upload_files(client, [str(report)], "reports", "p", timestamp="t")
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "PermanentRedirect" in logged
    assert "AWS_DEFAULT_REGION" in logged
    assert "different region" in logged


def test_a_resource_row_names_the_first_subnet_and_the_network_sheet_counts_each():
    import boto3
    from moto import mock_aws

    from inventag.discovery.network_analyzer import NetworkAnalyzer

    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        first, second = (
            ec2.create_subnet(VpcId=vpc, CidrBlock=f"10.0.{n}.0/24")["Subnet"][
                "SubnetId"
            ]
            for n in (1, 2)
        )
        function = {
            "id": "fn",
            "service": "LAMBDA",
            "type": "Function",
            "region": "us-east-1",
            "raw_data": {"VpcConfig": {"VpcId": vpc, "SubnetIds": [second, first]}},
        }
        analyzer = NetworkAnalyzer(boto3.Session(region_name="us-east-1"))
        analyzer.analyze_vpc_resources([function])
        rows = analyzer.map_resources_to_network([function])
        assert rows[0]["subnet_id"] == second
        for subnet in (first, second):
            assert analyzer.subnet_cache[subnet].associated_resources == ["fn"]


def test_a_snapshot_is_indented_json_with_the_whole_raw_data(tmp_path):
    from inventag.state.state_manager import StateManager

    resource = {
        "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1",
        "id": "i-1",
        "service": "EC2",
        "type": "Instance",
        "region": "us-east-1",
        "raw_data": {"InstanceId": "i-1", "Placement": {"AvailabilityZone": "a"}},
    }
    manager = StateManager(state_dir=str(tmp_path / "state"))
    state_id = manager.save_state([resource], "123456789012", ["us-east-1"])
    text = next((tmp_path / "state").glob(f"*{state_id}*.json")).read_text("utf-8")
    assert '\n  "' in text  # indent=2
    data = json.loads(text)
    assert data["resources"][0]["raw_data"]["Placement"] == {"AvailabilityZone": "a"}


def test_no_option_leaves_out_raw_data_or_compresses_a_snapshot():
    from inventag.cli.main import create_parser

    flags = [f for a in create_parser()._actions for f in a.option_strings]
    assert [f for f in flags if re.search(r"raw|compress|gzip|zip", f)] == []


def _package_sources():
    return {
        p: p.read_text("utf-8")
        for p in (ROOT / "inventag").rglob("*.py")
        if "__pycache__" not in p.parts
    }


def test_the_modules_planned_for_removal_are_imported_by_no_other_module():
    sources = _package_sources()
    for name in (
        "excel_branding_applicator",
        "word_branding_applicator",
        "enhanced_readonly_discovery",
        "configuration_manager",
    ):
        users = [
            p.relative_to(ROOT).as_posix()
            for p, text in sources.items()
            if p.stem != name and re.search(rf"\b{name}\b", text)
        ]
        assert users == [], (name, users)
    importers = sorted(
        p.relative_to(ROOT).as_posix()
        for p, text in sources.items()
        if re.search(r"^\s*(?:import|from)\s+jsonschema\b", text, re.M)
    )
    assert importers == ["inventag/reporting/configuration_manager.py"]


def test_template_framework_and_branding_system_have_only_the_named_importers():
    sources = _package_sources()

    def importers(name):
        return sorted(
            p.relative_to(ROOT).as_posix()
            for p, text in sources.items()
            if p.stem != name and re.search(rf"\b{name}\b", text)
        )

    assert importers("branding_system") == [
        "inventag/reporting/configuration_manager.py",
        "inventag/reporting/excel_branding_applicator.py",
        "inventag/reporting/word_branding_applicator.py",
    ]
    assert importers("template_framework") == [
        "inventag/reporting/__init__.py",
        "inventag/reporting/configuration_manager.py",
    ]


@pytest.mark.parametrize(
    "function",
    [
        "get_state_comparison_data",
        "export_state",
        "validate_state_integrity",
        "get_storage_stats",
        "get_all_aws_regions",
        "from_interactive_prompt",
    ],
)
def test_nothing_in_the_package_calls_the_functions_planned_for_removal(function):
    uses = []
    for path, text in _package_sources().items():
        for number, line in enumerate(text.split("\n"), 1):
            if re.search(rf"\b{function}\b", line) and not re.match(
                rf"\s*def {function}\b", line
            ):
                uses.append(f"{path.relative_to(ROOT)}:{number}")
    assert uses == []
    definitions = [
        p
        for p, text in _package_sources().items()
        if re.search(rf"^\s*def {function}\b", text, re.M)
    ]
    assert len(definitions) == 1


def test_the_launchers_are_outside_the_wheel_and_no_test_runs_them():
    assert (ROOT / "inventag.sh").is_file() and (ROOT / "inventag.bat").is_file()
    assert 'include = ["inventag*"]' in (ROOT / "pyproject.toml").read_text("utf-8")
    naming = {}
    for path in (ROOT / "tests").rglob("*.py"):
        text = path.read_text("utf-8")
        for number, line in enumerate(text.split("\n"), 1):
            if re.search(r"inventag\.(sh|bat)", line):
                naming.setdefault(path.name, []).append(line.strip())
    naming.pop("test_docs_claims_n1.py", None)
    assert list(naming) == ["test_python_compatibility.py"]
    # that test only reads the files and checks the Python version text
    assert naming["test_python_compatibility.py"] == [
        'for name in ("inventag.sh", "inventag.bat"):'
    ]


# ------------------------------------------------- the complete configuration example

COMPLETE_EXAMPLE = ROOT / "config" / "defaults" / "complete_configuration_example.yaml"


def test_the_complete_example_holds_only_keys_the_bom_config_reader_accepts():
    from inventag.reporting.bom_processor import BOMProcessingConfig
    from inventag.reporting.settings_loader import (
        read_bom_settings,
        valid_bom_setting_names,
    )

    keys = yaml.safe_load(COMPLETE_EXAMPLE.read_text("utf-8"))
    assert set(keys) <= set(valid_bom_setting_names())
    assert read_bom_settings(COMPLETE_EXAMPLE, BOMProcessingConfig()) == []


def test_validate_config_only_prints_no_unknown_key_warning_for_the_example(
    caplog,
):
    from inventag.cli.main import main

    argv = [
        "inventag",
        "--validate-config-only",
        "--bom-config",
        str(COMPLETE_EXAMPLE),
    ]
    with caplog.at_level(logging.WARNING):
        import sys as _sys
        from unittest import mock

        with mock.patch.object(_sys, "argv", argv):
            try:
                main()
            except SystemExit as exc:
                assert exc.code in (0, None)
            finally:
                # The CLI installs the read-only guard on boto3's default
                # session.
                from inventag.security.read_only_guard import (
                    uninstall_global_guard,
                )

                uninstall_global_guard()
    assert "unknown key" not in caplog.text
    assert "would be ignored" not in caplog.text
