"""``inventag completion bash|zsh|fish``: print a shell completion script.

The scripts are generated from the argparse parsers of the command (the flags
of ``inventag``, and the words ``templates``, ``selftest`` and ``completion``
with their own parsers), so they follow the command when a flag is added. The
generator is this module; it needs no package beyond the standard library and
makes no call: it only reads the parsers and prints text.

The command is a word before the flags, like ``inventag templates``;
:func:`main` takes the arguments after that word and returns the exit code.

Reading argparse's ``_actions``, ``_SubParsersAction`` and ``_choices_actions``
uses attributes that argparse does not document; a test builds the scripts from
the real parsers on every supported Python, so a change there shows at once.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, TextIO, Tuple

from ..exit_codes import EXIT_OK

PROG = "inventag"
SHELLS = ("bash", "zsh", "fish")
HELP_LIMIT = 100

EPILOG = """\
Install:
  bash   source <(inventag completion bash)
  zsh    inventag completion zsh > "${fpath[1]}/_inventag"
  fish   inventag completion fish > ~/.config/fish/completions/inventag.fish
"""


# ------------------------------------------------------------------- the model


@dataclass(frozen=True)
class Option:
    strings: Tuple[str, ...]
    help: str
    # None for a flag; otherwise "choices", "file", "dir" or "text".
    value: Optional[str] = None
    choices: Tuple[str, ...] = ()
    label: str = "value"


@dataclass(frozen=True)
class Positional:
    kind: str  # "choices", "file" or "text"
    choices: Tuple[str, ...] = ()
    label: str = "argument"
    multiple: bool = False


@dataclass
class Command:
    name: str
    help: str = ""
    options: List[Option] = field(default_factory=list)
    positionals: List[Positional] = field(default_factory=list)
    subcommands: List["Command"] = field(default_factory=list)


_FILE_WORDS = (
    "file",
    "path",
    "json",
    "template",
    "config",
    "mappings",
    "descriptions",
    "output",
    "credentials",
    "oauth",
)


def _short(text: Optional[str], action: Optional[argparse.Action] = None) -> str:
    """The first sentence of a help text, on one line, at most HELP_LIMIT characters."""
    if not text or text == argparse.SUPPRESS:
        return ""
    if "%" in text:
        params = dict(vars(action)) if action is not None else {}
        params["prog"] = PROG
        try:
            text = text % params
        except (KeyError, ValueError, TypeError):
            text = text.replace("%%", "%")
    text = " ".join(text.split())
    text = re.split(r"\.(?:\s+(?=[A-Z])|$)", text, maxsplit=1)[0]
    if len(text) > HELP_LIMIT:
        text = text[:HELP_LIMIT].rsplit(" ", 1)[0]
    return text.rstrip(" .,;:")


def _label(action: argparse.Action) -> str:
    raw = action.metavar if isinstance(action.metavar, str) else action.dest
    words = re.sub(r"[^A-Za-z0-9]+", " ", str(raw)).strip().lower()
    return words or "value"


def _kind(action: argparse.Action) -> str:
    if action.choices:
        return "choices"
    text = f"{action.dest} {action.metavar if isinstance(action.metavar, str) else ''}"
    text = text.lower()
    if "dir" in text:
        return "dir"
    if any(word in text for word in _FILE_WORDS):
        return "file"
    return "text"


def build_command(
    parser: argparse.ArgumentParser, name: str, help_text: str = ""
) -> Command:
    """Read one parser (and the sub-parsers under it) into a :class:`Command`."""
    command = Command(name=name, help=help_text)
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            helps = {a.dest: _short(a.help, a) for a in action._choices_actions}
            for sub_name, sub_parser in action.choices.items():
                text = helps.get(sub_name) or _short(sub_parser.description)
                command.subcommands.append(build_command(sub_parser, sub_name, text))
        elif action.option_strings:
            if action.help == argparse.SUPPRESS:
                continue
            takes_value = action.nargs != 0
            kind = _kind(action) if takes_value else None
            command.options.append(
                Option(
                    strings=tuple(action.option_strings),
                    help=_short(action.help, action),
                    value=kind,
                    choices=(
                        tuple(str(c) for c in action.choices or ())
                        if takes_value
                        else ()
                    ),
                    label=_label(action) if takes_value else "value",
                )
            )
        else:
            kind = _kind(action)
            command.positionals.append(
                Positional(
                    kind="text" if kind == "dir" else kind,
                    choices=tuple(str(c) for c in action.choices or ()),
                    label=_label(action),
                    multiple=action.nargs in ("*", "+", argparse.REMAINDER),
                )
            )
    return command


def build_model(
    root: argparse.ArgumentParser, words: Mapping[str, argparse.ArgumentParser]
) -> Command:
    """The command ``inventag``: the flags of ``root`` and one word per parser in ``words``."""
    model = build_command(root, PROG)
    for name, parser in words.items():
        model.subcommands.append(
            build_command(parser, name, _short(parser.description))
        )
    return model


def real_model() -> Command:
    from ..templating.cli import build_parser as templates_parser
    from . import selftest
    from .main import create_parser

    return build_model(
        create_parser(),
        {
            "templates": templates_parser(),
            "selftest": selftest.build_parser(),
            "completion": build_parser(),
        },
    )


def _walk(command: Command, path: Tuple[str, ...] = ()):
    """Every command with its path of words below the root, parents first."""
    yield path, command
    for sub in command.subcommands:
        yield from _walk(sub, path + (sub.name,))


# ----------------------------------------------------------------------- bash


def _bash_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def render_bash(model: Command) -> str:
    nodes = list(_walk(model))
    top = [sub.name for sub in model.subcommands]
    lines = [
        f"# bash completion for {PROG}. Made by '{PROG} completion bash'.",
        f"_{PROG}_words() {{",
        '    COMPREPLY=( $(compgen -W "$1" -- "$cur") )',
        "}",
        "",
        f"_{PROG}_files() {{",
        "    compopt -o filenames 2>/dev/null",
        "    local IFS=$'\\n'",
        '    COMPREPLY=( $(compgen -f -- "$cur") )',
        "}",
        "",
        f"_{PROG}_dirs() {{",
        "    compopt -o filenames 2>/dev/null",
        "    local IFS=$'\\n'",
        '    COMPREPLY=( $(compgen -d -- "$cur") )',
        "}",
        "",
        f"_{PROG}() {{",
        "    local cur prev path word i",
        "    COMPREPLY=()",
        '    cur="${COMP_WORDS[COMP_CWORD]}"',
        '    prev=""',
        '    if (( COMP_CWORD > 0 )); then prev="${COMP_WORDS[COMP_CWORD-1]}"; fi',
        "    # bash splits '--option=value' at the '=': look one word further back.",
        '    if [[ "$cur" == "=" ]]; then',
        '        cur=""',
        '    elif [[ "$prev" == "=" && $COMP_CWORD -ge 2 ]]; then',
        '        prev="${COMP_WORDS[COMP_CWORD-2]}"',
        "    fi",
        '    path=""',
    ]
    if top:
        lines += [
            "    # The word after the command name picks a command, as in the program.",
            "    if (( COMP_CWORD > 1 )); then",
            '        case "${COMP_WORDS[1]}" in',
            f"            {'|'.join(top)}) path=\"${{COMP_WORDS[1]}}\" ;;",
            "        esac",
            "    fi",
        ]
    nested = [" ".join(path) for path, _ in nodes if len(path) >= 2]
    if nested:
        lines += [
            '    if [[ -n "$path" ]]; then',
            "        for (( i = 2; i < COMP_CWORD; i++ )); do",
            '            word="${COMP_WORDS[i]}"',
            '            case "$path $word" in',
            "                "
            + "|".join(f'"{n}"' for n in nested)
            + ') path="$path $word" ;;',
            "            esac",
            "        done",
            "    fi",
        ]
    # The value of an option.
    value_cases = []
    for path, node in nodes:
        for option in node.options:
            if option.value is None:
                continue
            if option.value == "choices":
                action = f"_{PROG}_words {_bash_quote(' '.join(option.choices))}"
            elif option.value == "file":
                action = f"_{PROG}_files"
            elif option.value == "dir":
                action = f"_{PROG}_dirs"
            else:
                action = "COMPREPLY=()"
            patterns = "|".join(f'"{" ".join(path)}|{s}"' for s in option.strings)
            value_cases.append(f"        {patterns}) {action}; return 0 ;;")
    if value_cases:
        lines += ['    case "$path|$prev" in'] + value_cases + ["    esac"]
    # The flags.
    flag_cases = [
        f'            "{" ".join(path)}") _{PROG}_words {_bash_quote(" ".join(s for o in node.options for s in o.strings))} ;;'
        for path, node in nodes
        if node.options
    ]
    lines += ['    if [[ "$cur" == -* ]]; then']
    if flag_cases:
        lines += ['        case "$path" in'] + flag_cases + ["        esac"]
    lines += ["        return 0", "    fi"]
    # Words and positional arguments.
    word_cases = []
    for path, node in nodes:
        key = " ".join(path)
        if node.subcommands:
            names = " ".join(sub.name for sub in node.subcommands)
            guard = "(( COMP_CWORD == 1 )) && " if not path else ""
            word_cases.append(
                f'        "{key}") {guard}_{PROG}_words {_bash_quote(names)} ;;'
            )
        elif node.positionals:
            first = node.positionals[0]
            if first.kind == "choices":
                word_cases.append(
                    f'        "{key}") _{PROG}_words {_bash_quote(" ".join(first.choices))} ;;'
                )
            elif first.kind == "file":
                word_cases.append(f'        "{key}") _{PROG}_files ;;')
    if word_cases:
        lines += ['    case "$path" in'] + word_cases + ["    esac"]
    lines += ["    return 0", "}", "", f"complete -F _{PROG} {PROG}", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------ zsh


def _sq(text: str) -> str:
    """Inside a single-quoted zsh string."""
    return text.replace("'", "'\\''")


def _zsh_text(text: str) -> str:
    """Help text that is safe inside '[...]' and in 'name:description' pairs."""
    text = text.replace(":", " -").replace("\\", "/")
    text = text.replace("[", "(").replace("]", ")")
    return _sq(text)


def _zsh_action(label: str, kind: Optional[str], choices: Sequence[str]) -> str:
    label = _zsh_text(label)
    if kind == "choices":
        words = " ".join(c.replace(":", "\\:") for c in choices)
        return f":{label}:({_sq(words)})"
    if kind == "file":
        return f":{label}:_files"
    if kind == "dir":
        return f":{label}:_files -/"
    return f":{label}: "


def _zsh_option(option: Option) -> str:
    help_text = _zsh_text(option.help)
    if option.value is None:
        names = list(option.strings)
        suffix = f"[{help_text}]"
    else:
        names = [s + ("=" if s.startswith("--") else "+") for s in option.strings]
        suffix = f"[{help_text}]" + _zsh_action(
            option.label, option.value, option.choices
        )
    if len(names) == 1:
        return f"'{_sq(names[0])}{suffix}'"
    exclusive = " ".join(option.strings)
    return f"'({exclusive})'{{{','.join(names)}}}'{suffix}'"


def _zsh_function(path: Tuple[str, ...]) -> str:
    return "_".join((f"_{PROG}",) + tuple(re.sub(r"\W", "_", p) for p in path))


def _zsh_command(path: Tuple[str, ...], node: Command) -> List[str]:
    name = _zsh_function(path)
    lines = [
        f"{name}() {{",
        '    local curcontext="$curcontext" state state_descr line',
        "    typeset -A opt_args",
        "    local -a specs",
        "    specs=(",
    ]
    lines += [f"        {_zsh_option(o)}" for o in node.options]
    lines += ["    )"]
    if node.subcommands:
        entries = " ".join(
            f"'{_sq(s.name)}:{_zsh_text(s.help)}'" for s in node.subcommands
        )
        lines += [
            "    local -a commands",
            f"    commands=({entries})",
        ]
        if not path:
            lines += [
                "    if (( CURRENT == 2 )); then",
                "        specs+=('1:command:->command')",
                "    fi",
                "    _arguments -C -s $specs",
                "    case $state in",
                "        command) _describe -t commands 'command' commands ;;",
                "    esac",
            ]
        else:
            lines += [
                "    _arguments -C -s $specs \\",
                "        '1:command:->command' \\",
                "        '*::argument:->args'",
                "    case $state in",
                "        command) _describe -t commands 'command' commands ;;",
                "        args)",
                "            case $line[1] in",
            ]
            for sub in node.subcommands:
                lines.append(
                    f"                {sub.name}) {_zsh_function(path + (sub.name,))} ;;"
                )
            lines += ["            esac", "            ;;", "    esac"]
    else:
        positional_specs = []
        for index, pos in enumerate(node.positionals, start=1):
            lead = "*" if pos.multiple else str(index)
            positional_specs.append(
                f"'{lead}{_zsh_action(pos.label, pos.kind, pos.choices)}'"
            )
        lines.append(
            ("    _arguments -s $specs " + " ".join(positional_specs)).rstrip()
        )
    lines += ["}", ""]
    return lines


def render_zsh(model: Command) -> str:
    nodes = list(_walk(model))
    lines = [
        f"#compdef {PROG}",
        f"# zsh completion for {PROG}. Made by '{PROG} completion zsh'.",
        "",
    ]
    for path, node in nodes[1:]:
        lines += _zsh_command(path, node)
    # The root: the word after the command name picks a command.
    root_lines = _zsh_command((), model)
    if model.subcommands:
        dispatch = ["    if (( CURRENT > 2 )); then", "        case $words[2] in"]
        for sub in model.subcommands:
            dispatch.append(
                f"            {sub.name}) shift words; (( CURRENT-- )); "
                f"{_zsh_function((sub.name,))}; return ;;"
            )
        dispatch += ["        esac", "    fi"]
        at = root_lines.index("    local -a specs")
        root_lines[at:at] = dispatch
    lines += root_lines
    lines += [
        f'if [ "$funcstack[1]" = "_{PROG}" ]; then',
        f'    _{PROG} "$@"',
        "else",
        f"    compdef _{PROG} {PROG}",
        "fi",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------- fish


def _fq(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _fish_condition(path: Tuple[str, ...]) -> str:
    if not path:
        return "__fish_use_subcommand"
    return "; and ".join(f"__fish_seen_subcommand_from {word}" for word in path)


def render_fish(model: Command) -> str:
    lines = [f"# fish completion for {PROG}. Made by '{PROG} completion fish'."]
    for path, node in _walk(model):
        condition = _fish_condition(path)
        base = f"complete -c {PROG} -n {_fq(condition)}"
        for option in node.options:
            parts = [base]
            for string in option.strings:
                if string.startswith("--"):
                    parts.append(f"-l {string[2:]}")
                elif len(string) == 2:
                    parts.append(f"-s {string[1]}")
                else:
                    parts.append(f"-o {string[1:]}")
            if option.value is not None:
                parts.append("-r")
                if option.value == "choices":
                    parts += ["-f", f"-a {_fq(' '.join(option.choices))}"]
                elif option.value == "dir":
                    parts += ["-f", "-a '(__fish_complete_directories)'"]
                elif option.value == "text":
                    parts.append("-f")
            if option.help:
                parts.append(f"-d {_fq(option.help)}")
            lines.append(" ".join(parts))
        if node.subcommands:
            names = " ".join(sub.name for sub in node.subcommands)
            chosen = f"not __fish_seen_subcommand_from {names}"
            condition_for_names = chosen if not path else f"{condition}; and {chosen}"
            for sub in node.subcommands:
                lines.append(
                    f"complete -c {PROG} -n {_fq(condition_for_names)} -f "
                    f"-a {sub.name} -d {_fq(sub.help)}"
                )
        elif node.positionals and node.positionals[0].kind == "choices":
            lines.append(f"{base} -f -a {_fq(' '.join(node.positionals[0].choices))}")
    lines.append("")
    return "\n".join(lines)


# -------------------------------------------------------------------- command

RENDERERS = {"bash": render_bash, "zsh": render_zsh, "fish": render_fish}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inventag completion",
        description=(
            "Print a shell completion script for the inventag command.\n"
            "It only reads the command's own options and prints text:\n"
            "no AWS call and no network connection."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument(
        "shell", choices=SHELLS, help="the shell to print the script for"
    )
    return parser


def main(argv: Optional[Sequence[str]] = None, out: Optional[TextIO] = None) -> int:
    import sys

    args = build_parser().parse_args(argv)
    (out if out is not None else sys.stdout).write(RENDERERS[args.shell](real_model()))
    return EXIT_OK
