"""v1.5.1: the CLI surface differs from v1.5.0 only by what ``--create-html``
adds (behaviour review H1).

The allowed differences, and nothing else:

* help and usage text (also shown on a bad option and on a bare ``inventag``):
  the ``--create-html`` option, its help text and one epilog example;
* the shell completion word list: the word ``--create-html``;
* ``inventag selftest``: one more module (``inventag.reporting.html_report``),
  so "112 InvenTag modules import" where v1.5.0 printed 111.

The golden ``golden/v150_cli_surface.json`` was written from the v1.5.0
sources (``git archive 457a80cd inventag``) with COLUMNS=100: the help text,
the ``--`` words of ``inventag completion bash`` and the module names that
``selftest`` walks.
"""

import json
import pkgutil
import re
from pathlib import Path

import inventag
from inventag.cli import completion
from inventag.cli.main import create_parser

GOLDEN = json.loads(
    (Path(__file__).resolve().parent / "golden" / "v150_cli_surface.json").read_text()
)
EXAMPLE = (
    "\n  # Static HTML report next to the Excel workbook\n"
    "  inventag --create-excel --create-html\n"
)


def _without_create_html(parser):
    action = parser._option_string_actions.pop("--create-html")
    parser._remove_action(action)
    for group in parser._action_groups:
        if action in group._group_actions:
            group._group_actions.remove(action)
    assert parser.epilog.count(EXAMPLE) == 1
    parser.epilog = parser.epilog.replace(EXAMPLE, "")
    return parser


def test_help_differs_only_by_the_create_html_option_and_example(monkeypatch):
    monkeypatch.setenv("COLUMNS", "100")
    full = create_parser().format_help()
    assert "--create-html" in full and "inventag --create-excel --create-html" in full
    assert _without_create_html(create_parser()).format_help() == GOLDEN["help"]


def test_completion_differs_only_by_the_create_html_word():
    script = completion.render_bash(completion.real_model())
    words = set(re.findall(r"--[a-z0-9][a-z0-9-]*", script))
    assert words - set(GOLDEN["completion_bash_options"]) == {"--create-html"}
    assert set(GOLDEN["completion_bash_options"]) - words == set()


def test_selftest_finds_one_more_module_the_html_writer():
    modules = {
        info.name
        for info in pkgutil.walk_packages(inventag.__path__, "inventag.")
        if info.name != "inventag.__main__"
    }
    assert modules - set(GOLDEN["modules"]) == {"inventag.reporting.html_report"}
    assert set(GOLDEN["modules"]) - modules == set()
    assert len(modules) == len(GOLDEN["modules"]) + 1 == 112
