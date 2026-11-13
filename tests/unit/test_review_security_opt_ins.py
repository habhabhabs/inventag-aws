"""Release-gate review: the write helpers cannot be reached from the CLI or
from configuration files."""

import ast
from pathlib import Path

import pytest

from inventag.reporting.settings_loader import valid_bom_setting_names

ROOT = Path(__file__).resolve().parents[2]
WRITE_HELPERS = {
    "setup_cross_account_roles",
    "ensure_lifecycle_rule",
    "upload_to_s3",
    "uninstall_global_guard",
    "allow_iam_writes",
    "allow_bucket_writes",
    "allow_write",
}


def _names(path: Path) -> set:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.keyword) and node.arg:
            found.add(node.arg)
        elif isinstance(node, ast.alias):
            found.add(node.name.split(".")[-1])
    return found


@pytest.mark.parametrize(
    "module",
    [
        "inventag/cli/main.py",
        "inventag/cli/safety.py",
        "inventag/cli/config_validator.py",
        "inventag/templating/runner.py",
        "inventag/templating/cli.py",
        "inventag/core/cloud_bom_generator.py",
        "inventag/__main__.py",
    ],
)
def test_cli_path_does_not_name_a_write_helper(module):
    assert not (_names(ROOT / module) & WRITE_HELPERS)


def test_config_files_cannot_turn_on_writes():
    names = {n.lower() for n in valid_bom_setting_names()}
    assert not any(
        word in n
        for n in names
        for word in ("allow", "lifecycle", "write", "guard", "iam", "upload")
    ), names


def test_cli_has_no_flag_that_disables_the_guard():
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "inventag", "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
    ).stdout.lower()
    assert "lifecycle" not in out
    assert "allow-write" not in out and "allow_iam" not in out
