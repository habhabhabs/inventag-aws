#!/usr/bin/env python3
"""Check that `inventag ...` command lines in docs are accepted by the real parser.

Parse only: nothing is scanned and AWS is never called. The parser comes from
`inventag.cli.main.create_parser` (and `inventag.templating.cli.build_parser`
for `inventag templates ...`).

Shell variables ("$BUCKET", "${BUCKET}"), GitHub expressions
("${{ vars.BUCKET }}"), "<placeholder>" and "%VERSION%" count as placeholder
values. A placeholder in a value position is replaced by a value the option
accepts (its first choice, "1" for numbers). A placeholder in a flag position
is skipped, because it cannot be checked.

Library use: `extract_commands(text)` and `check_command(tokens)`.
Command line use: `check_cli_examples.py FILE...` checks every command found
in the given text files (one command per line, continuations allowed).
"""

import argparse
import re
import shlex
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_GHA_EXPR = re.compile(r"\$\{\{.*?\}\}")
_PLACEHOLDER = re.compile(r"\$|__GHA__|<[^<>\s]+>|%[A-Z_]+%")
_PREFIX = re.compile(r"^\s*(?:-\s+|[\w.-]+:\s+|\$\s+|[|>][-+]?\s*$)")


class _ParserError(Exception):
    """Raised in place of argparse printing usage and exiting."""


def _quiet(parser: argparse.ArgumentParser) -> None:
    def error(message: str):
        raise _ParserError(message)

    def exit_(status: int = 0, message: Optional[str] = None):
        raise _ParserError(f"exited with status {status}")

    parser.error = error  # type: ignore[method-assign]
    parser.exit = exit_  # type: ignore[method-assign]
    for action in parser._actions:
        for sub in getattr(action, "choices", None) or {}:
            child = action.choices[sub] if isinstance(action.choices, dict) else None
            if isinstance(child, argparse.ArgumentParser):
                _quiet(child)


def build_main_parser() -> argparse.ArgumentParser:
    from inventag.cli.main import create_parser

    parser = create_parser()
    _quiet(parser)
    return parser


def build_templates_parser() -> argparse.ArgumentParser:
    from inventag.templating.cli import build_parser

    parser = build_parser()
    _quiet(parser)
    return parser


def is_placeholder(token: str) -> bool:
    return bool(_PLACEHOLDER.search(token))


def _substitute(parser: argparse.ArgumentParser, tokens: List[str]) -> List[str]:
    """Replace placeholder tokens by values that the option would accept."""
    by_flag = {}
    for action in parser._actions:
        for flag in action.option_strings:
            by_flag[flag] = action
    out: List[str] = []
    previous_action = None
    for token in tokens:
        if is_placeholder(token):
            if token.startswith("-") and "=" not in token:
                previous_action = None
                continue  # placeholder in a flag position: cannot be checked
            if token.startswith("-") and "=" in token:
                flag, _, _ = token.partition("=")
                action = by_flag.get(flag)
                out.append(f"{flag}={_value_for(action)}")
                previous_action = None
                continue
            out.append(_value_for(previous_action))
            previous_action = None
            continue
        out.append(token)
        previous_action = by_flag.get(token.partition("=")[0])
        if "=" in token:
            previous_action = None
    return out


def _value_for(action: Optional[argparse.Action]) -> str:
    if action is not None:
        if action.choices:
            return str(next(iter(action.choices)))
        if action.type in (int, float):
            return "1"
    return "placeholder"


def check_command(tokens: List[str]) -> List[str]:
    """Return problems for one tokenised command (first token is `inventag`)."""
    if not tokens or tokens[0] != "inventag":
        return ["not an inventag command"]
    args = tokens[1:]
    if args and args[0] == "templates":
        parser = build_templates_parser()
        args = args[1:]
    else:
        parser = build_main_parser()
    args = _substitute(parser, args)
    try:
        parser.parse_args(args)
    except _ParserError as exc:
        return [str(exc)]
    except SystemExit as exc:  # defensive: an exit we did not intercept
        return [f"exited with status {exc.code}"]
    return []


def _tokenise(line: str) -> Optional[List[str]]:
    line = _GHA_EXPR.sub("__GHA__", line)
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        return list(lexer)
    except ValueError:
        return None


def extract_commands(text: str) -> List[Tuple[int, str, Optional[List[str]]]]:
    """Find `inventag ...` commands. Returns (line number, text, tokens).

    Line continuations (a trailing backslash) are joined. A command ends at
    a shell operator (`&&`, `||`, `;`, `|`, a redirect). `tokens` is None
    when the line cannot be split (unbalanced quote).
    """
    found: List[Tuple[int, str, Optional[List[str]]]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        start = i
        line = lines[i]
        while line.rstrip().endswith("\\") and i + 1 < len(lines):
            i += 1
            line = line.rstrip()[:-1] + " " + lines[i].strip()
        i += 1
        stripped = line
        for _ in range(4):
            match = _PREFIX.match(stripped)
            if not match or not match.group(0).strip():
                break
            stripped = stripped[match.end() :]
        tokens = _tokenise(stripped)
        if tokens is None:
            if re.match(r"\s*inventag\s", stripped):
                found.append((start + 1, stripped.strip(), None))
            continue
        segment: List[str] = []
        for token in tokens + [";"]:
            if re.fullmatch(r"[;&|<>()]+", token) or re.match(r"\d*[<>]", token):
                if segment and segment[0] == "inventag":
                    found.append((start + 1, " ".join(segment), list(segment)))
                segment = []
            else:
                segment.append(token)
    return found


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ns = ap.parse_args(argv)
    bad = 0
    for path in ns.files:
        for lineno, text, tokens in extract_commands(path.read_text("utf-8")):
            problems = (
                ["cannot split the command line (unbalanced quote)"]
                if tokens is None
                else check_command(tokens)
            )
            for problem in problems:
                bad += 1
                print(f"{path}:{lineno}: {problem}: {text}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
