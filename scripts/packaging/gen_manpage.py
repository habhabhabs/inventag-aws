#!/usr/bin/env python3
"""Write the man page ``inventag.1`` from InvenTag's argument parser.

A build-time tool (plan section 3.4); it is not part of the package. Run it
with a Python that can import ``inventag`` and its dependencies:

    python scripts/packaging/gen_manpage.py --out build/inventag.1

The page has no date and no build path, so the same source gives the same
bytes. The version comes from ``inventag/_version.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Words before the flags that main() dispatches (cli/main.py). selftest and
# completion are listed only when their modules exist (work order B1).
SUBCOMMANDS = (
    ("templates", "inventag.templating.cli", "List, show and check BOM templates."),
    (
        "selftest",
        "inventag.cli.selftest",
        "Check offline that this installation works.",
    ),
    (
        "completion",
        "inventag.cli.completion",
        "Print a shell completion script for bash, zsh or fish.",
    ),
)


def esc(text: str) -> str:
    """Escape text for roff: backslashes, hyphens, and a leading dot or quote."""
    text = text.replace("\\", "\\e").replace("-", "\\-")
    lines = []
    for line in text.splitlines():
        if line.startswith((".", "'")):
            line = "\\&" + line
        lines.append(line)
    return "\n".join(lines)


def _flags(action: argparse.Action) -> str:
    names = ", ".join(f"\\fB{esc(o)}\\fR" for o in action.option_strings)
    if action.nargs == 0:
        return names
    if action.choices:
        meta = "{" + ",".join(str(c) for c in action.choices) + "}"
    else:
        meta = action.metavar or action.dest.upper()
        if isinstance(meta, tuple):
            meta = " ".join(meta)
    return f"{names} \\fI{esc(str(meta))}\\fR"


def _help(action: argparse.Action) -> str:
    text = action.help or ""
    if "%(default)" in text:
        text = text.replace("%(default)s", str(action.default))
    return " ".join(text.split())


def _module_exists(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def render(parser: Optional[argparse.ArgumentParser] = None) -> str:
    from inventag import exit_codes
    from inventag._version import __version__

    if parser is None:
        from inventag.cli.main import create_parser

        parser = create_parser()

    out: List[str] = [
        f'.TH INVENTAG 1 "" "inventag {__version__}" "User Commands"',
        ".SH NAME",
        "inventag \\- read\\-only AWS inventory, tag checks and BOM reports",
        ".SH SYNOPSIS",
        ".B inventag",
        "[\\fIOPTIONS\\fR]",
    ]
    commands = [c for c in SUBCOMMANDS if _module_exists(c[1])]
    for word, _module, _text in commands:
        out += [".br", f".B inventag {word}", "[\\fIARGS\\fR]"]
    out += [".SH DESCRIPTION", esc(parser.description or "")]
    out += [
        ".PP",
        "InvenTag reads an AWS account and writes reports. It makes no change in "
        "the account.",
    ]
    if commands:
        out.append(".SH COMMANDS")
        for word, _module, text in commands:
            out += [
                ".TP",
                f"\\fB{word}\\fR",
                esc(text) + f" See \\fBinventag {word} \\-\\-help\\fR.",
            ]
    for group in parser._action_groups:
        actions = [
            a
            for a in group._group_actions
            if a.option_strings and a.help != argparse.SUPPRESS
        ]
        if not actions:
            continue
        title = (group.title or "options").upper()
        out.append(f".SH {esc(title)}")
        for action in actions:
            out += [".TP", _flags(action), esc(_help(action))]
    codes = sorted(
        (value, name)
        for name, value in vars(exit_codes).items()
        if name.startswith("EXIT_") and isinstance(value, int)
    )
    out.append(".SH EXIT STATUS")
    for value, name in codes:
        out += [
            ".TP",
            f"\\fB{value}\\fR",
            esc(name[len("EXIT_") :].replace("_", " ").lower()),
        ]
    if parser.epilog:
        out += [".SH EXAMPLES", ".nf", esc(parser.epilog.strip()), ".fi"]
    out += [
        ".SH SEE ALSO",
        "https://habhabhabs.github.io/inventag\\-aws/",
    ]
    return "\n".join(out) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ns = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ns.add_argument("--out", type=Path, required=True)
    args = ns.parse_args(argv)
    args.out.write_text(render(), encoding="utf-8")
    print(f"man page written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
