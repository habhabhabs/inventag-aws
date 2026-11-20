"""A2 (plan 2.7): ``spec.concurrency`` in a config template.

Same meaning and range as ``--concurrency`` (1 to 256, default 64); a value
typed on the command line wins, as for the other keys.
"""

import logging

import pytest

from inventag.cli.main import create_parser
from inventag.templating.errors import TemplateError
from inventag.templating.runner import apply_config, explicit_dests, load_templates
from inventag.templating.schema import CONFIG_SPEC

from .conftest import write


def _config_args(registry, user_dir, body, argv=()):
    write(
        user_dir / "cfg.yaml",
        f"format_version: 1\nkind: config\nname: cfg\nspec:\n{body}",
    )
    argv = ["--template", "cfg", *argv]
    args = create_parser().parse_args(argv)
    run = load_templates(args.template, registry)
    apply_config(run, args, explicit_dests(create_parser, argv), logging.getLogger("t"))
    return args


def test_schema_default_matches_the_cli_default():
    field = CONFIG_SPEC["concurrency"]
    assert field.type == "integer"
    assert (field.default, field.minimum, field.maximum) == (64, 1, 256)
    assert "`--concurrency`" in field.description
    assert create_parser().parse_args([]).concurrency == 64


def test_the_template_value_is_used(registry, user_dir):
    args = _config_args(registry, user_dir, "  concurrency: 8\n")
    assert args.concurrency == 8


def test_left_out_means_the_default(registry, user_dir):
    args = _config_args(registry, user_dir, "  outputs: [excel]\n")
    assert args.concurrency == 64


def test_the_command_line_wins(registry, user_dir):
    args = _config_args(
        registry, user_dir, "  concurrency: 8\n", ["--concurrency", "2"]
    )
    assert args.concurrency == 2


@pytest.mark.parametrize("value", ["0", "257", "many"])
def test_out_of_range_is_a_template_error(registry, user_dir, value):
    write(
        user_dir / "cfg.yaml",
        f"format_version: 1\nkind: config\nname: cfg\nspec:\n  concurrency: {value}\n",
    )
    with pytest.raises(TemplateError) as info:
        load_templates(["cfg"], registry)
    assert "concurrency" in str(info.value)
