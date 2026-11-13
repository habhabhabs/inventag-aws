"""The outcome of a run: what was read, what was not, and why.

One direction of data flow (failure model, design section 0)::

    exception --classify()--> Issue --IssueLog--\\
    coverage ledger ----------------------------> reduce --> RunOutcome
    RunOutcome --> exit_codes.decide()  -> exit code
               --> render               -> log lines, end-of-run summary,
                                           report block, run_summary.json

Pure code: nothing here makes an AWS call, writes a file or prints.
"""

from .classify import category_for_code, classify, clean_aws_message
from .model import (
    BENIGN,
    AccountOutcome,
    Category,
    Findings,
    Issue,
    IssueLog,
    OutputOutcome,
    RegionOutcome,
    RunOutcome,
    Scope,
    ServiceOutcome,
    State,
    merge_issues,
)
from .reduce import (
    entry_category,
    entry_issue,
    guard_issues,
    reduce_account,
    reduce_region,
    reduce_run,
    reduce_service,
    reduce_units,
)

__all__ = [
    "BENIGN",
    "AccountOutcome",
    "Category",
    "Findings",
    "Issue",
    "IssueLog",
    "OutputOutcome",
    "RegionOutcome",
    "RunOutcome",
    "Scope",
    "ServiceOutcome",
    "State",
    "category_for_code",
    "classify",
    "clean_aws_message",
    "entry_category",
    "entry_issue",
    "guard_issues",
    "merge_issues",
    "reduce_account",
    "reduce_region",
    "reduce_run",
    "reduce_service",
    "reduce_units",
]
