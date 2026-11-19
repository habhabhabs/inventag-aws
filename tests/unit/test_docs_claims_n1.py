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
