"""Docs claims of v1.5.0 (package P8b): the pages equal the code.

Each test names the page and the sentence it protects. They read the English
pages and, where a claim is a number or a command, the four translations too.
"""

import importlib
import re
from pathlib import Path

import pytest

from inventag import exit_codes
from inventag.core import cost_requests
from inventag.policy import cli as policy_cli

cli_main = importlib.import_module("inventag.cli.main")

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LANGS = ("es", "fr", "zh-Hans", "zh-Hant")
POLICY_COMMANDS = ("validate", "list", "schema", "test", "check", "explain", "lock")


def page(rel, lang=None):
    base = DOCS if lang is None else ROOT / "website" / "translations" / lang / "docs"
    return (base / rel).read_text(encoding="utf-8")


def all_languages(rel):
    return [("en", page(rel))] + [(lang, page(rel, lang)) for lang in LANGS]


def policy_subparsers():
    parser = policy_cli.build_parser()
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return action.choices
    raise AssertionError("no subcommands")


# ------------------------------------------------------------ exit codes
def test_cli_exit_table_lists_0_to_8_in_order():
    cells = {}
    for line in page("reference/cli.md").splitlines():
        match = re.match(r"^\| (\d) \| (.*) \|$", line)
        if match:
            cells[int(match.group(1))] = match.group(2)
    assert sorted(cells) == list(range(9))
    assert exit_codes.EXIT_POLICY_FAIL == 7
    assert exit_codes.EXIT_POLICY_NOT_EVALUATED == 8
    assert "--policy-fail-on" in cells[7] and "--fail-on" in cells[7]
    assert "inventag policy check" in cells[8]
    assert "--fail-on-not-evaluated" in cells[8]


def test_a_scan_has_no_flag_that_gives_code_8():
    scan_options = {
        o for a in cli_main.create_parser()._actions for o in a.option_strings
    }
    assert "--fail-on-not-evaluated" not in scan_options
    assert "--policy-fail-on-not-evaluated" not in scan_options
    check = policy_subparsers()["check"]
    assert "--fail-on-not-evaluated" in {
        o for a in check._actions for o in a.option_strings
    }
    for lang, text in all_languages("reference/cli.md"):
        assert "--fail-on-not-evaluated" in text, lang


@pytest.mark.parametrize("lang", [None, *LANGS])
def test_glossary_exit_codes_include_7_and_8(lang):
    text = page("reference/glossary.md", lang)
    row = next(
        l
        for l in text.splitlines()
        if "--fail-if-empty" in l and "--risk-threshold" in l
    )
    assert "`7`" in row and "`8`" in row
    assert row.index("`7`") < row.index("`8`")


# --------------------------------------------------- commands and flags
def test_cli_commands_block_lists_every_policy_command():
    text = page("reference/cli.md")
    block = text.split("```text", 1)[1].split("```", 1)[0]
    for command in POLICY_COMMANDS:
        assert f"inventag policy {command}" in block, command
    assert sorted(policy_subparsers()) == sorted(POLICY_COMMANDS)


@pytest.mark.parametrize("command", POLICY_COMMANDS)
def test_cli_page_names_every_flag_of_each_policy_command(command):
    parser = policy_subparsers()[command]
    flags = {
        o
        for a in parser._actions
        for o in a.option_strings
        if o.startswith("--") and o != "--help"
    }
    for lang, text in all_languages("reference/cli.md"):
        section = text.split("inventag policy", 1)[1]
        for flag in flags:
            assert f"`{flag}" in section, (lang, command, flag)


def test_cli_page_policy_flag_rows_say_template_works():
    text = page("reference/cli.md")
    row = next(l for l in text.splitlines() if l.startswith("| `--policy PATH`"))
    assert "--template" in row


def test_cli_finops_checks_row_names_template_and_the_findings_file():
    text = page("reference/cli.md")
    row = next(l for l in text.splitlines() if l.startswith("| `--finops-checks`"))
    assert "--template" in row and "policy_findings_<timestamp>.json" in row


# ------------------------------------------------------------- outputs
def test_outputs_page_names_the_four_findings_files():
    from inventag.policy import outputs

    assert outputs.FORMATS == ("json", "sarif", "xml", "md")
    for lang, text in all_languages("reference/outputs.md"):
        assert "policy_findings_<timestamp>.json" in text, lang
        for ext in ("sarif", "xml", "md"):
            assert f"policy_findings_<timestamp>.{ext}" in text, (lang, ext)


def test_the_findings_file_names_are_the_ones_the_page_states(tmp_path):
    from .policy.cli_helpers import policies_dir, run, snapshot_file

    snapshot = snapshot_file(tmp_path)
    folder = policies_dir(tmp_path, "ex01.yaml")
    code, _out, _err = run(
        [
            "check",
            "--snapshot",
            snapshot,
            "--policies",
            folder,
            "--format",
            "json,sarif,junit,markdown",
            "--output-directory",
            tmp_path / "out",
            "--now",
            "2026-11-20",
        ]
    )
    assert code == 0
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
        "policy_findings_20261120_000000.json",
        "policy_findings_20261120_000000.md",
        "policy_findings_20261120_000000.sarif",
        "policy_findings_20261120_000000.xml",
    ]


def test_outputs_page_lists_the_cost_trend_table_columns_of_the_converter():
    source = (ROOT / "inventag" / "reporting" / "converter.py").read_text()
    columns = [
        "Account",
        "Service",
        "Resources",
        "Earlier month",
        "Later month",
        "Change %",
        "Direction",
        "Billing names counted",
    ]
    for lang, text in all_languages("reference/outputs.md"):
        for column in columns:
            assert f'"{column}"' in source, column
            assert f"`{column}`" in text, (lang, column)


# ------------------------------------------------------- the Cost Explorer count
def test_the_count_line_and_the_request_numbers_of_the_pages():
    count, parts = cost_requests.planned(1, True, True)
    assert count == 3
    assert cost_requests.announcement(count, parts) == (
        "Cost Explorer: up to 3 request(s) in this run "
        "(billing validation: 1; cost trend: 2). AWS charges for each."
    )
    assert cost_requests.planned(1, False, True)[0] == 2
    assert cost_requests.planned(4, True, True)[0] == 12
    from inventag.discovery.cost_analyzer import TREND_PAGES_PER_ACCOUNT

    assert TREND_PAGES_PER_ACCOUNT == 2
    status = page("getting-started/status.md")
    assert (
        "Cost Explorer: up to 3 request(s) in this run (billing validation: 1; "
        "cost trend: 2). AWS charges for each." in status
    )


@pytest.mark.parametrize(
    "rel",
    [
        "getting-started/status.md",
        "reference/cli.md",
        "reference/iam-permissions.md",
    ],
)
def test_pages_state_two_requests_for_each_account_not_one_for_the_run(rel):
    for lang, text in all_languages(rel):
        flat = " ".join(text.split())
        assert "at most one more for the whole run" not in flat, (lang, rel)
        assert "at most one more `ce:GetCostAndUsage` request" not in flat, (lang, rel)
        assert "A fix is planned for v1.5.0" not in flat, (lang, rel)
        assert "Cost trend: read once, with the credentials" not in flat or (
            # status.md may quote the old line in a migration note, never as current
            rel == "getting-started/status.md"
            and "v1.4" in flat
        ), (lang, rel)


def test_status_says_the_count_line_is_a_warning_on_every_run_that_calls_ce():
    en = " ".join(page("getting-started/status.md").split())
    assert "as a warning" in en
    assert "at info level" not in en


@pytest.mark.parametrize(
    "rel", ["getting-started/status.md", "guides/finops-checks.md"]
)
def test_ec2_other_stays_out_of_ec2_and_the_removal_is_noted(rel):
    for lang, text in all_languages(rel):
        assert "EC2 - Other" in text, (lang, rel)
    en = page("guides/finops-checks.md")
    assert "cost_trends" in en and "resource_id" in en


# ----------------------------------------------------------- changelog
def test_changelog_unreleased_has_added_changed_removed():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = text.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    headings = re.findall(r"^### (\w+)", unreleased, re.M)
    assert headings == ["Added", "Changed", "Removed"]
    flat = " ".join(unreleased.split())
    for word in (
        "inventag policy",
        "--policy",
        "--policy-waivers",
        "--policy-fail-on",
        "exit codes 7 and 8",
        "policy_findings_<timestamp>",
        "scope.filters",
        "jmespath",
        "--finops-checks",
        "--template",
        "per-resource",
        "EC2 - Other",
    ):
        assert word in flat, word
