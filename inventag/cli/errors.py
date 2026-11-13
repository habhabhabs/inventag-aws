"""One way to stop a command: what is wrong, what to do instead, where to read.

Every path that ends the process with a non-zero code prints:

    inventag: error: <subject>: <what happened>.
      Why: <reason>.                       (optional)
      Instead: <a command or edit that works>
      More: <one URL of a documentation page>

on standard error, before any AWS call, with no traceback. This module is the
only place that turns such a stop into ``sys.exit``:

* :class:`UsageError` holds the four parts (``instead`` and ``more`` are
  required, so a message without a next step cannot be built).
* :func:`fail` / :func:`fail_all` print one or several errors and exit.
* :func:`finish` exits with a code the run itself decided (results-type exits
  such as 3, 4, 5, 6); the caller prints its own findings and ``Instead`` line.
* :class:`InventagArgumentParser` sends argparse's own errors through the same
  form, with a hint for removed options, options of the development scripts
  and misspelled options.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from typing import Dict, Iterable, List, NoReturn, Optional, Sequence, Tuple

DOCS_BASE = "https://habhabhabs.github.io/inventag-aws/docs/"
S3_BUCKET_RULES_URL = (
    "https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html"
)
ISSUES_URL = "https://github.com/habhabhabs/inventag-aws/issues"

EXIT_ERROR = 1
EXIT_USAGE = 2


def docs_url(more: str) -> str:
    """A full URL for ``more``: ``guides/run-in-ci#x`` or an https URL."""
    if more.startswith(("http://", "https://")):
        return more
    return DOCS_BASE + more.lstrip("/")


class UsageError(Exception):
    """A command line or file problem that stops the run.

    ``subject`` is the flag, the ``file:line: key`` or the account; it may be
    empty when ``what`` already names it. ``code`` is 2 for invalid, conflicting,
    unknown or refused options and 1 for a configuration file or template that
    is not valid.
    """

    def __init__(
        self,
        subject: Optional[str],
        what: str,
        instead: str,
        more: str,
        why: Optional[str] = None,
        code: int = EXIT_USAGE,
    ):
        if not instead or not more:
            raise ValueError("a UsageError needs an 'instead' and a 'more'")
        self.subject = subject or None
        self.what = what.rstrip()
        self.instead = instead.rstrip()
        self.more = docs_url(more)
        self.why = why.rstrip() if why else None
        self.code = code
        super().__init__(self.first_line())

    def first_line(self) -> str:
        what = self.what if self.what.endswith((".", "?")) else self.what + "."
        return f"{self.subject}: {what}" if self.subject else what

    def lines(self) -> List[str]:
        out = [self.first_line()]
        if self.why:
            out.append(f"  Why: {self.why}")
        out.append(f"  Instead: {self.instead}")
        out.append(f"  More: {self.more}")
        return out

    def render(self) -> str:
        """The text printed on stderr, starting with ``inventag: error:``."""
        return "inventag: error: " + "\n".join(self.lines())

    def __str__(self) -> str:
        # Without the prefix, so a caller that still prints
        # f"inventag: error: {message}" prints the same text as render().
        return "\n".join(self.lines())


def _clean(text: str) -> str:
    try:
        from ..security.redaction import redact

        return redact(text)
    except Exception:  # redaction must never hide the real message
        return text


def _write(text: str) -> None:
    print(_clean(text), file=sys.stderr)


def emit(errors: Iterable["UsageError"], stream=None) -> None:
    """Print errors on ``stream`` (default standard error) without exiting."""
    for error in errors:
        print(_clean(error.render()), file=stream or sys.stderr)


def note(text: str) -> None:
    """``inventag: note: ...`` on stderr (an implied option, for example)."""
    _write(f"inventag: note: {text}")


def warn(text: str) -> None:
    """``inventag: warning: ...`` on stderr."""
    _write(f"inventag: warning: {text}")


def exit_code_of(errors: Iterable[UsageError]) -> int:
    """2 beats 1 (the precedence of the exit-code table)."""
    return max((e.code for e in errors), default=EXIT_USAGE)


def fail_all(errors: Sequence[UsageError]) -> NoReturn:
    """Print every error, then exit with the highest code among them."""
    for error in errors:
        _write(error.render())
    sys.exit(exit_code_of(errors))


def fail(error: UsageError) -> NoReturn:
    """Print one error and exit with its code."""
    fail_all([error])


def finish(code: int) -> NoReturn:
    """Exit with a code the run decided (3, 4, 5, 6, 130 ...).

    The caller has printed its findings and one line saying what to do.
    """
    sys.exit(code)


def unexpected_error(error: BaseException, debug: bool = False) -> UsageError:
    """The catch-all message: type and text, traceback only with ``--debug``."""
    text = _clean(str(error)) or "no further detail"
    return UsageError(
        None,
        f"unexpected {type(error).__name__}: {text}",
        "run again with --debug to see the traceback; if it repeats, report it "
        f"with the output of 'inventag --version' at {ISSUES_URL}",
        "guides/troubleshooting",
        code=EXIT_ERROR,
    )


# ---------------------------------------------------------------- the parser

# Options of scripts/development/cicd_bom_generation.py that people try on
# the inventag command.
DEV_SCRIPT = "scripts/development/cicd_bom_generation.py"
DEV_SCRIPT_FLAGS = (
    "--formats",
    "--compliance-threshold",
    "--fail-on-security-issues",
    "--slack-webhook",
    "--dry-run",
    "--required-tags",
)


def _removed_flags() -> Dict[str, Tuple[str, str]]:
    """``{flag: (removed_in, instead)}`` from ``inventag/cli/removed_flags.py``.

    The table is kept by the deprecation work; until that file exists the
    answer is empty.
    """
    try:
        from .removed_flags import REMOVED_FLAGS  # type: ignore[attr-defined]
    except ImportError:
        return {}
    return dict(REMOVED_FLAGS)


_ARG_PREFIX = re.compile(r"^argument (?P<subject>.+?): (?P<what>.*)$", re.DOTALL)
_CHOICES = re.compile(r"\(choose from (?P<choices>.*)\)\s*$", re.DOTALL)
_AMBIGUOUS = re.compile(r"^ambiguous option: (?P<given>\S+) could match (?P<c>.*)$")


class InventagArgumentParser(argparse.ArgumentParser):
    """``ArgumentParser`` whose errors follow the error contract (exit 2)."""

    #: documentation page (and optional anchor) for the More line
    docs_page = "reference/cli"

    def _visible_options(self) -> List[str]:
        names = []
        for action in self._actions:
            if action.help == argparse.SUPPRESS:
                continue
            names.extend(o for o in action.option_strings if o.startswith("--"))
        return names

    def _help_command(self) -> str:
        return f"{self.prog} --help"

    def _unrecognized(self, tokens: List[str]) -> List[UsageError]:
        flags = [t for t in tokens if t.startswith("-") and t != "-"]
        if not flags:
            word = tokens[0] if tokens else ""
            return [
                UsageError(
                    None,
                    f"unrecognized argument '{word}'",
                    "check for a missing '--' before an option name or a missing "
                    f"quote around a value with spaces. Run '{self._help_command()}'"
                    " for every option.",
                    self.docs_page,
                )
            ]
        removed = _removed_flags()
        errors = []
        for token in flags:
            flag = token.split("=", 1)[0]  # never print what follows '='
            if flag in removed:
                version, instead = removed[flag]
                errors.append(
                    UsageError(
                        None,
                        f"{flag} was removed in {version}",
                        instead,
                        "reference/cli",
                    )
                )
            elif flag in DEV_SCRIPT_FLAGS:
                errors.append(
                    UsageError(
                        None,
                        f"'{flag}' is an option of {DEV_SCRIPT}, not of inventag",
                        "for output formats use --create-excel or --create-word; "
                        "for CI gates use --risk-threshold, --fail-on-account-error, "
                        "--fail-if-empty or a tag-policy template (--template).",
                        "guides/run-in-ci",
                    )
                )
            else:
                close = difflib.get_close_matches(
                    flag, self._visible_options(), n=1, cutoff=0.6
                )
                guess = f"did you mean {close[0]}? " if close else ""
                errors.append(
                    UsageError(
                        None,
                        f"unrecognized argument '{flag}'",
                        f"{guess}Run '{self._help_command()}' for every option.",
                        self.docs_page,
                    )
                )
        return errors

    def usage_errors_for(self, message: str) -> List[UsageError]:
        """Turn one argparse message into contract errors (testable)."""
        if message.startswith("unrecognized arguments: "):
            tokens = message[len("unrecognized arguments: ") :].split()
            return self._unrecognized(tokens)
        subject: Optional[str] = None
        what = message
        match = _ARG_PREFIX.match(message)
        if match:
            subject, what = match.group("subject"), match.group("what")
        ambiguous = _AMBIGUOUS.match(what)
        choices = _CHOICES.search(what)
        if ambiguous:
            instead = f"type the whole option, one of: {ambiguous.group('c')}."
        elif choices:
            instead = f"use one of: {choices.group('choices')}."
        elif "expected one argument" in what or "expected at least one" in what:
            instead = (
                f"give a value after {subject or 'the option'}. Run "
                f"'{self._help_command()}' to see what it takes."
            )
        elif "invalid" in what and "value" in what:
            instead = (
                f"give a value of the right kind. Run '{self._help_command()}' "
                f"to see what {subject or 'the option'} takes."
            )
        else:
            instead = (
                f"run '{self._help_command()}' to see the options and their values."
            )
        return [UsageError(subject, what, instead, self.docs_page)]

    def error(self, message: str) -> NoReturn:  # argparse API
        fail_all(self.usage_errors_for(message))


# ------------------------------------------------------------- file problems

# kind -> (what to do, docs page) for the problems of a configuration file.
FILE_KINDS = {
    "accounts": (
        "fix the line named above, then check the file with: inventag "
        "--validate-config-only --accounts-file {path}",
        "reference/configuration-files#accounts-file",
    ),
    "tag mappings": (
        "fix the line named above, then check the file with: inventag "
        "--validate-config-only --tag-mappings {path}",
        "reference/configuration-files#tag-mappings",
    ),
    "service descriptions": (
        "fix the line named above, then check the file with: inventag "
        "--validate-config-only --service-descriptions {path}",
        "reference/configuration-files#service-descriptions",
    ),
    "bom config": (
        "fix the key named above; the valid keys are listed in the guide.",
        "reference/configuration-files#bom-processing-configuration",
    ),
    "report layout": (
        "fix the line named above, then check the file with: inventag "
        "--validate-templates --word-template {path}  (or --excel-template)",
        "reference/cli#report-layout-files",
    ),
}


def file_problem_errors(
    kind: str, path: str, problems: Iterable[str], code: int = EXIT_ERROR
) -> List["UsageError"]:
    """One error (exit 1) for each ``file:line: key: problem`` of a file."""
    instead, more = FILE_KINDS[kind]
    return [
        UsageError(None, problem, instead.format(path=path), more, code=code)
        for problem in problems
    ]


def account_failure_errors(contexts: dict) -> List["UsageError"]:
    """Why each account failed: its first cause and what to check."""
    out = []
    for account_id, ctx in contexts.items():
        causes = ctx.get("errors") or []
        if not causes:
            continue
        cause = str(causes[0])
        lowered = cause.lower()
        if "profile" in lowered and "found" in lowered:
            instead = (
                "check profile_name in your accounts file, or run: aws configure "
                "list-profiles"
            )
        elif "expired" in lowered or "token" in lowered:
            instead = (
                "refresh the credentials (for example aws sso login), then run "
                "the same command again; add --resume to reuse finished accounts"
            )
        else:
            instead = (
                "check this account's credentials and role with: inventag "
                "--validate-credentials --accounts-file <your accounts file>"
            )
        out.append(
            UsageError(
                account_id,
                cause.rstrip("."),
                instead,
                "guides/troubleshooting#credentials",
                code=EXIT_ERROR,
            )
        )
    return out
