"""One renderer, four outputs with the same content (design section 5).

* :func:`log_account` / :func:`log_run`: log lines, once per issue key.
* :func:`summary_lines`: the end-of-run summary (stderr).
* :func:`report_block`: the block inside each report ("Run notes" lines and
  the rows of a "Run issues" table).
* :func:`summary_json`: the ``run_summary.json`` payload.

All four use :func:`issue_line`, so the sentence in the log, the summary, the
report and the JSON ``message`` is the same sentence. Invariant I4: the issues
of severity warning or error are the same in all four. Info issues are only in
the JSON (and in the log at DEBUG level).

Nothing here prints, writes a file or reads the clock; the caller does.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from inventag.exit_codes import POLICY_1X, POLICY_2_0, Gates, Policy, decide

from . import wording
from .model import (
    ERROR,
    INFO,
    WARNING,
    AccountOutcome,
    Category,
    Issue,
    RunOutcome,
    State,
    issue_sort_key,
)

SCHEMA_VERSION = 1
VISIBLE = (ERROR, WARNING)
_LOG_LEVEL = {ERROR: logging.ERROR, WARNING: logging.WARNING, INFO: logging.DEBUG}
_NOTE_REASON_LIMIT = 300

REPORT_COLUMNS = (
    "Severity",
    "Category",
    "Account",
    "Service",
    "Where",
    "Operation",
    "AWS code",
    "Count",
    "What happened",
    "What to do",
)


def worded(issues: Iterable[Issue]) -> List[Issue]:
    """Issues with their wording filled, in the deterministic order."""
    return sorted((wording.apply(i) for i in issues), key=issue_sort_key)


def visible(issues: Iterable[Issue]) -> List[Issue]:
    """Issues of severity warning or error, worded and sorted."""
    return [i for i in worded(issues) if i.severity in VISIBLE]


def issue_line(issue: Issue) -> str:
    """``<account>: <what> (<Operation>: <Code>). Instead: <next step>``"""
    issue = wording.apply(issue)
    prefix = f"{issue.account}: " if issue.account else ""
    return f"{prefix}{issue.message}. Instead: {issue.next_step}"


def more_line(issue: Issue) -> str:
    return f"More: {wording.apply(issue).more}"


# ------------------------------------------------------------------ log lines
def log_lines(issues: Iterable[Issue]) -> List[Tuple[int, str]]:
    """``(level, text)`` for each issue: error, warning; info at DEBUG."""
    return [(_LOG_LEVEL[i.severity], issue_line(i)) for i in worded(issues)]


def log_account(
    account: AccountOutcome, issues: Iterable[Issue], logger: logging.Logger
) -> List[Tuple[int, str]]:
    """Log the issues of one account (called when the account ends)."""
    lines = log_lines(i for i in issues if i.account == account.account_id)
    for level, text in lines:
        logger.log(level, text)
    return lines


def log_run(outcome: RunOutcome, logger: logging.Logger) -> List[Tuple[int, str]]:
    """Log the issues no account has logged: run, output and guard issues."""
    known = {a.account_id for a in outcome.accounts}
    lines = log_lines(i for i in outcome.issues if i.account not in known)
    for level, text in lines:
        logger.log(level, text)
    return lines


# ----------------------------------------------------------------- summary
def _plural_accounts(outcome: RunOutcome) -> str:
    counts = _account_counts(outcome)
    parts = [f"{n} {state}" for state, n in counts.items() if n]
    if not parts:
        return ""
    joined = (
        parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    )
    return f" from {joined} account(s)"


def _account_counts(outcome: RunOutcome) -> Dict[str, int]:
    counts = {
        s.value: 0 for s in (State.COMPLETE, State.PARTIAL, State.SKIPPED, State.FAILED)
    }
    for a in outcome.accounts:
        counts[a.state.value] += 1
    return counts


def status_line(outcome: RunOutcome) -> str:
    shown = len(visible(outcome.issues))
    return (
        f"Run status: {outcome.state_word}. {outcome.resources_reported} resources"
        f"{_plural_accounts(outcome)}; {shown} issue(s)."
    )


def account_line(account: AccountOutcome) -> str:
    name = f" ({account.account_name})" if account.account_name else ""
    line = (
        f"{account.account_id}{name}: {account.state.value}, "
        f"{account.resources} resources"
    )
    if account.regions:
        done = sum(
            1
            for r in account.regions.values()
            if r.state in (State.COMPLETE, State.SKIPPED)
        )
        line += f", {done} of {len(account.regions)} regions complete"
    if account.reused_from:
        line += f", reused from the scan at {account.reused_from}"
    return line


def exit_line(outcome: RunOutcome, gates: Gates, policy: Policy) -> str:
    code, reason = decide(outcome, gates, policy)
    line = f"Exit code {code} ({reason})."
    if code == 0 and not gates.fail_on_incomplete:
        with_flag, _ = decide(outcome, replace(gates, fail_on_incomplete=True), policy)
        if with_flag != code:
            line += f" With --fail-on-incomplete this run exits {with_flag}."
    if policy != POLICY_2_0:
        later, later_reason = decide(outcome, gates, POLICY_2_0)
        if later != code:
            line += f" From v2.0.0 this run exits {later} ({later_reason})."
    return line


def summary_lines(
    outcome: RunOutcome,
    gates: Gates = Gates(),
    policy: Policy = POLICY_1X,
    written: Sequence[str] = (),
) -> List[str]:
    """The end-of-run summary: status, accounts not complete, every warning
    and error with its "More:" link, outputs not written, files written, and
    the exit code with its reason."""
    lines = [status_line(outcome)]
    for account in outcome.accounts:
        if account.state is not State.COMPLETE or account.reused_from:
            lines.append(account_line(account))
    for issue in visible(outcome.issues):
        lines.append(issue_line(issue))
        lines.append(f"  {more_line(issue)}")
    for out in outcome.outputs:
        if out.state is not State.COMPLETE:
            reason = f": {out.category.value}" if out.category else ""
            lines.append(f"Not written: {out.name} ({out.state.value}{reason})")
    files = list(written) or [f for out in outcome.outputs for f in out.files]
    if files:
        lines.append("Written: " + ", ".join(files))
    lines.append(exit_line(outcome, gates, policy))
    return lines


# ------------------------------------------------------------ report block
@dataclass
class ReportBlock:
    """What a report shows about the run.

    ``notes``: lines for the existing "Run notes" block (empty when the run is
    complete with nothing to say, as in v1.1.4). ``rows``: one row per warning
    or error, for a "Run issues" table with :data:`REPORT_COLUMNS`.
    """

    status_line: str
    notes: List[str] = field(default_factory=list)
    columns: Tuple[str, ...] = REPORT_COLUMNS
    rows: List[Tuple[Any, ...]] = field(default_factory=list)


def _where_cell(issue: Issue) -> str:
    regions = list(issue.regions) or ([issue.region] if issue.region else [])
    if len(regions) > 3:
        return f"{len(regions)} regions"
    return ", ".join(regions)


def _failed_accounts(outcome: RunOutcome) -> List[AccountOutcome]:
    return [
        a
        for a in outcome.accounts
        if a.state is not State.SKIPPED and (a.state is State.FAILED or a.account_issue)
    ]


def _account_reason(account: AccountOutcome, issues: Sequence[Issue]) -> str:
    own = [i for i in issues if i.account == account.account_id]
    top = [i for i in own if i.scope.value == "account"] or own
    text = "; ".join(i.message for i in top) or account.state.value
    return text[:_NOTE_REASON_LIMIT]


def report_block(outcome: RunOutcome) -> ReportBlock:
    """Status line, notes (same account wording as v1.1.4's "Run notes") and
    one row per warning or error."""
    shown = visible(outcome.issues)
    notes: List[str] = []
    failed = _failed_accounts(outcome)
    total = len(outcome.accounts)
    if failed:
        partial = [a for a in failed if a.state is State.PARTIAL]
        timed_out = all(a.category is Category.TIMEOUT for a in partial)
        why = " (time limit)" if timed_out else ""
        if len(partial) == len(failed):
            notes.append(
                f"{len(failed)} of {total} account(s) were only partly scanned{why}; "
                "the resources found are included, others may be missing:"
            )
        elif partial:
            notes.append(
                f"{len(failed)} of {total} account(s) failed: {len(partial)} were only "
                "partly scanned (the resources found are included), the others are "
                "not in this report:"
            )
        else:
            notes.append(
                f"{len(failed)} of {total} account(s) were not scanned, so this report "
                "does not include them:"
            )
        for account in failed:
            notes.append(
                f"{account.account_id} ({account.account_name}): "
                f"{_account_reason(account, shown)}"
            )
    reused = sorted(
        (a.account_id, a.reused_from) for a in outcome.accounts if a.reused_from
    )
    if reused:
        notes.append(
            f"{len(reused)} account(s) were not scanned again: their results come "
            "from an earlier run of the same command (--resume), scanned at:"
        )
        notes.extend(f"{account_id}: {when}" for account_id, when in reused)
    notes.extend(issue_line(i) for i in shown)
    rows = [
        (
            i.severity,
            i.category.value,
            i.account,
            i.service,
            _where_cell(i),
            i.operation,
            i.code,
            i.count,
            i.message,
            i.next_step,
        )
        for i in shown
    ]
    return ReportBlock(status_line=status_line(outcome), notes=notes, rows=rows)


# ------------------------------------------------------------ run_summary.json
def _issue_json(issue: Issue) -> Dict[str, Any]:
    return {
        "severity": issue.severity,
        "scope": issue.scope.value,
        "category": issue.category.value,
        "account": issue.account or None,
        "service": issue.service or None,
        "regions": list(issue.regions),
        "operation": issue.operation or None,
        "code": issue.code or None,
        "count": issue.count,
        "retryable": issue.retryable,
        "message": issue.message,
        "next_step": issue.next_step,
        "more": issue.more,
        "line": issue_line(issue),
        "aws_message": issue.aws_message or None,
        "examples": list(issue.examples),
    }


def _account_json(account: AccountOutcome) -> Dict[str, Any]:
    regions = {}
    for name, region in sorted(account.regions.items()):
        regions[name] = {
            "state": region.state.value,
            "category": region.category.value if region.category else None,
            "not_complete": [
                {
                    "service": unit.service,
                    "source": unit.source,
                    "state": unit.state.value,
                    "category": unit.category.value if unit.category else None,
                }
                for _key, unit in sorted(region.services.items())
                if unit.state is not State.COMPLETE
            ],
        }
    return {
        "account_id": account.account_id,
        "account_name": account.account_name,
        "state": account.state.value,
        "category": account.category.value if account.category else None,
        "account_issue": account.account_issue,
        "derived_failure": account.derived_failure,
        "resources": account.resources,
        "seconds": account.seconds,
        "reused_from": account.reused_from or None,
        "regions": regions,
    }


def summary_json(
    outcome: RunOutcome,
    gates: Gates = Gates(),
    meta: Optional[Mapping[str, Any]] = None,
    policy: Policy = POLICY_1X,
) -> Dict[str, Any]:
    """The ``run_summary.json`` payload (schema version 1, design 5.6).

    ``meta`` supplies ``inventag_version``, ``started_at``, ``finished_at``,
    ``duration_seconds`` and ``command``; the caller owns the clock.
    """
    meta = dict(meta or {})
    code, reason = decide(outcome, gates, policy)
    code_2, reason_2 = decide(outcome, gates, POLICY_2_0)
    issues = worded(outcome.issues)
    severities = {ERROR: 0, WARNING: 0, INFO: 0}
    for issue in issues:
        severities[issue.severity] += 1
    state = "cancelled" if outcome.cancelled else outcome.state.value
    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "inventag_version": meta.pop("inventag_version", _version()),
        "started_at": meta.pop("started_at", None),
        "finished_at": meta.pop("finished_at", None),
        "duration_seconds": meta.pop("duration_seconds", None),
        "command": meta.pop("command", {}),
        "state": state,
        "status": outcome.state_word,
        "empty": outcome.empty,
        "exit": {
            "code": code,
            "reason": reason,
            "code_in_2_0": code_2,
            "reason_in_2_0": reason_2,
        },
        "counts": {
            "resources": outcome.resources_reported,
            "resources_found": outcome.resources_found,
            "accounts": _account_counts(outcome),
            "issues": severities,
            "guard_blocks": outcome.guard_blocks,
        },
        "accounts": [_account_json(a) for a in outcome.accounts],
        "issues": [_issue_json(i) for i in issues],
        "outputs": [
            {
                "name": out.name,
                "required": out.required,
                "state": out.state.value,
                "category": out.category.value if out.category else None,
                "files": list(out.files),
            }
            for out in outcome.outputs
        ],
        "findings": {
            "tag_violations": outcome.findings.tag_violations,
            "risk_findings": outcome.findings.risk_findings,
        },
    }
    payload.update(meta)
    return payload


def _version() -> str:
    from inventag._version import __version__

    return __version__
