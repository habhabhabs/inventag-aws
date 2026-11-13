"""Compute outcome states bottom-up. Pure functions: no I/O, no logging.

Input is what a run already records:

* the coverage ledger of discovery (one entry per listing call; objects of
  :class:`inventag.discovery.coverage.CoverageEntry` or their ``asdict``
  form), and
* issues that are not listing calls (credentials, region check, details,
  outputs), made by :func:`inventag.outcome.classify.classify`.

State rules (design 2.2):

* Service unit. COMPLETE: every call ended ok or empty (benign failures of
  single calls allowed). SKIPPED: nothing read and every failure benign.
  PARTIAL: some calls succeeded, or pages were kept before a failure.
  FAILED: nothing read and at least one failure is not benign.
* Region. SKIPPED: the access check ended benign, or every unit skipped.
  FAILED: the access check failed otherwise, or every non-skipped unit
  failed. PARTIAL: a unit partial or failed. Else COMPLETE.
* Account. SKIPPED: not attempted. With an account-scope issue: PARTIAL when
  something was kept, else FAILED. Without one: FAILED (``derived_failure``)
  when every non-skipped region failed; PARTIAL when a region is partial or
  failed; else COMPLETE.

Resource-scope issues never change a state: the rows are kept.
"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from .classify import EXPIRED_SESSION_CODES, category_for_class_name, category_for_code
from .model import (
    BENIGN,
    RETRYABLE,
    AccountOutcome,
    Category,
    Findings,
    Issue,
    OutputOutcome,
    RegionOutcome,
    RunOutcome,
    Scope,
    ServiceOutcome,
    State,
    merge_issues,
    worst_category,
)

C = Category

OK_OUTCOMES = frozenset({"ok", "empty"})

#: The ledger's coarse ``outcome`` when an entry carries no usable code.
_OUTCOME_CATEGORY = {
    "denied": C.PERMISSION_DENIED,
    "throttled": C.THROTTLED,
    "timeout": C.TIMEOUT,
    "error": C.SERVICE_ERROR,
    "skipped": C.NOT_ENABLED,
    "blocked": C.GUARD_BLOCK,
}

#: Phase of a ledger entry, by its ``source``.
_SOURCE_PHASE = {
    "service-api": "listing",
    "tagging-api": "tagging",
    "billing": "billing",
}


def _get(entry: Any, name: str, default: Any = "") -> Any:
    if isinstance(entry, Mapping):
        return entry.get(name, default)
    return getattr(entry, name, default)


def entry_failed(entry: Any) -> bool:
    return _get(entry, "outcome") not in OK_OUTCOMES


def entry_category(entry: Any) -> Optional[Category]:
    """Category of a ledger entry (``None`` when the call ended ok or empty).

    Uses the entry's ``category`` when it has one (WP-F1b); else the error
    code (an AWS code or an exception class name); else the coarse outcome.
    """
    outcome = _get(entry, "outcome")
    if outcome in OK_OUTCOMES:
        return None
    declared = _get(entry, "category", "")
    if declared:
        return Category(declared)
    if outcome == "timeout":
        return C.TIMEOUT
    code = _get(entry, "error_code", "") or ""
    if code:
        by_class = category_for_class_name(code)
        if by_class is not None:
            return by_class
        category = category_for_code(
            code,
            scope=Scope.SERVICE,
            phase=_SOURCE_PHASE.get(_get(entry, "source", ""), "listing"),
            service=_get(entry, "service", ""),
        )
        if category is C.SERVICE_ERROR and outcome in ("denied", "throttled"):
            # A code InvenTag does not map, but discovery already knew better.
            return _OUTCOME_CATEGORY[outcome]
        return category
    return _OUTCOME_CATEGORY.get(outcome, C.SERVICE_ERROR)


def entry_issue(entry: Any) -> Optional[Issue]:
    """The service-scope issue of a failed ledger entry (``None`` if it was ok)."""
    category = entry_category(entry)
    if category is None:
        return None
    source = _get(entry, "source", "service-api")
    return Issue(
        scope=Scope.SERVICE,
        category=category,
        account=_get(entry, "account_id", ""),
        region=_get(entry, "region", ""),
        service=_get(entry, "service", ""),
        operation=_get(entry, "operation", ""),
        code=_get(entry, "error_code", "") or "",
        phase=_SOURCE_PHASE.get(source, "listing"),
        retryable=category in RETRYABLE,
    )


UnitKey = Tuple[str, str, str]  # (region, service, source)


def unit_key(entry: Any) -> UnitKey:
    return (
        _get(entry, "region", ""),
        _get(entry, "service", ""),
        _get(entry, "source", "service-api"),
    )


def reduce_service(entries: Sequence[Any], account: str = "") -> ServiceOutcome:
    """Fold the ledger entries of one unit (account, region, service, source)."""
    if not entries:
        raise ValueError("a unit needs at least one ledger entry")
    first = entries[0]
    unit = ServiceOutcome(
        account=account or _get(first, "account_id", ""),
        region=_get(first, "region", ""),
        service=_get(first, "service", ""),
        source=_get(first, "source", "service-api"),
    )
    failures: List[Category] = []
    kept = 0
    for entry in entries:
        count = int(_get(entry, "count", 0) or 0)
        unit.resources += count
        unit.seconds += float(_get(entry, "seconds", 0.0) or 0.0)
        category = entry_category(entry)
        if category is None:
            unit.calls_ok += 1
        else:
            unit.calls_failed += 1
            failures.append(category)
            kept += count
    hard = [c for c in failures if c not in BENIGN]
    if not failures:
        unit.state = State.COMPLETE
    elif not hard:
        # Benign failures of single calls are allowed next to good calls.
        unit.state = State.COMPLETE if unit.calls_ok else State.SKIPPED
        unit.category = None if unit.calls_ok else worst_category(failures)
    elif unit.calls_ok or kept:
        unit.state = State.PARTIAL
        unit.category = worst_category(hard)
    else:
        unit.state = State.FAILED
        unit.category = worst_category(hard)
    unit.seconds = round(unit.seconds, 3)
    return unit


def reduce_units(
    entries: Iterable[Any], account: str = ""
) -> Dict[UnitKey, ServiceOutcome]:
    """Group ledger entries by unit and fold each group."""
    groups: Dict[UnitKey, List[Any]] = {}
    for entry in entries:
        groups.setdefault(unit_key(entry), []).append(entry)
    return {
        key: reduce_service(group, account) for key, group in sorted(groups.items())
    }


def reduce_region(
    region: str,
    units: Iterable[ServiceOutcome] = (),
    check: Optional[Issue] = None,
) -> RegionOutcome:
    """State of one region from its units and the access check's issue."""
    outcome = RegionOutcome(region=region)
    for unit in units:
        outcome.services[(unit.service, unit.source)] = unit
    if check is not None:
        outcome.category = check.category
        outcome.state = State.SKIPPED if check.category in BENIGN else State.FAILED
        return outcome
    states = [u.state for u in outcome.services.values()]
    active = [s for s in states if s is not State.SKIPPED]
    if states and not active:
        outcome.state = State.SKIPPED
    elif active and all(s is State.FAILED for s in active):
        outcome.state = State.FAILED
    elif any(s in (State.PARTIAL, State.FAILED) for s in active):
        outcome.state = State.PARTIAL
    else:
        outcome.state = State.COMPLETE
    if outcome.state is not State.COMPLETE:
        outcome.category = worst_category(
            u.category
            for u in outcome.services.values()
            if u.state is not State.COMPLETE
        )
    return outcome


def fold_expired_session(
    issues: Iterable[Issue], account_id: str
) -> Tuple[List[Issue], Optional[Issue]]:
    """Fold "session expired" issues of units into one account-scope issue.

    Returns the remaining issues and the folded issue (``None`` when no unit
    failed with an expired session). ``count`` is the number of merged unit
    issues.
    """
    rest: List[Issue] = []
    expired: List[Issue] = []
    for issue in issues:
        if (
            issue.scope in (Scope.SERVICE, Scope.REGION)
            and issue.category is C.CREDENTIALS
            and issue.code in EXPIRED_SESSION_CODES
        ):
            expired.append(issue)
        else:
            rest.append(issue)
    if not expired:
        return rest, None
    regions = sorted({r for i in expired for r in i.regions})
    folded = Issue(
        scope=Scope.ACCOUNT,
        category=C.CREDENTIALS,
        account=account_id,
        code=expired[0].code,
        phase="listing",
        count=sum(i.count for i in expired),
        regions=tuple(regions),
        aws_message=next((i.aws_message for i in expired if i.aws_message), ""),
    )
    return rest, folded


def reduce_account(
    account_id: str,
    entries: Iterable[Any] = (),
    issues: Iterable[Issue] = (),
    *,
    account_name: str = "",
    resources: int = 0,
    seconds: float = 0.0,
    reused_from: str = "",
    regions: Iterable[str] = (),
    attempted: bool = True,
) -> Tuple[AccountOutcome, List[Issue]]:
    """State of one account, and every issue of that account (merged).

    ``entries``: the account's ledger. ``issues``: issues that are not
    listing calls (account, region and resource scope). Region-scope issues
    with phase ``region_check`` are the access check of their region.
    ``regions``: regions the scan was asked for (a region with no entry and no
    check issue is complete). ``attempted=False``: the account was not
    started (cancelled before it began) and is SKIPPED.
    """
    entries = list(entries)
    given = [i for i in issues if i.account in ("", account_id)]
    entry_issues = [i for i in (entry_issue(e) for e in entries) if i is not None]
    rest, expired = fold_expired_session(entry_issues + given, account_id)
    all_issues = merge_issues(rest + ([expired] if expired else []))

    outcome = AccountOutcome(
        account_id=account_id,
        account_name=account_name,
        resources=resources,
        seconds=seconds,
        reused_from=reused_from,
    )
    if not attempted:
        outcome.state = State.SKIPPED
        return outcome, all_issues

    units = reduce_units(entries, account_id)
    by_region: Dict[str, List[ServiceOutcome]] = {r: [] for r in regions}
    for (region, _service, _source), unit in units.items():
        by_region.setdefault(region, []).append(unit)
    checks: Dict[str, Issue] = {}
    for issue in all_issues:
        if issue.scope is Scope.REGION and issue.phase == "region_check":
            for region in issue.regions or (issue.region,):
                checks.setdefault(region, issue)
                by_region.setdefault(region, [])
    for region in sorted(by_region):
        outcome.regions[region] = reduce_region(
            region, by_region[region], checks.get(region)
        )

    account_level = [
        i
        for i in all_issues
        if i.scope is Scope.ACCOUNT and i.category is not C.CANCELLED
    ]
    read_something = resources > 0 or any(u.calls_ok for u in units.values())

    if account_level:
        outcome.account_issue = True
        outcome.category = worst_category(i.category for i in account_level)
        outcome.state = State.PARTIAL if read_something else State.FAILED
        # Owner decision O1 covers an expired session (X4) like a run that
        # read nothing: it is a "derived" failure when that is the only cause.
        outcome.derived_failure = all(
            i.category is C.CREDENTIALS and i.code in EXPIRED_SESSION_CODES
            for i in account_level
        )
        return outcome, all_issues

    if reused_from:
        outcome.state = State.COMPLETE
        return outcome, all_issues

    region_states = [r.state for r in outcome.regions.values()]
    active = [r for r in outcome.regions.values() if r.state is not State.SKIPPED]
    if active and all(r.state is State.FAILED for r in active):
        outcome.state = State.FAILED
        outcome.derived_failure = True
    elif any(s in (State.PARTIAL, State.FAILED) for s in region_states):
        outcome.state = State.PARTIAL
    else:
        outcome.state = State.COMPLETE
    if outcome.state is not State.COMPLETE:
        outcome.category = worst_category(
            r.category for r in active if r.state is not State.COMPLETE
        )
    return outcome, all_issues


def guard_issues(
    blocked: Iterable[Mapping[str, Any]], known: Iterable[Issue]
) -> List[Issue]:
    """Issues for guard blocks that no catch site reported (design 3.5, G5).

    ``blocked``: ``ReadOnlyGuard.audit_report()["blocked"]``. One issue per
    ``(service, operation)`` not already present as a ``guard_block`` issue.
    """
    seen = {(i.service, i.operation) for i in known if i.category is C.GUARD_BLOCK}
    found: Dict[Tuple[str, str], Issue] = {}
    for record in blocked:
        pair = (str(record.get("service", "")), str(record.get("operation", "")))
        if pair in seen:
            continue
        region = str(record.get("region") or "")
        issue = Issue(
            scope=Scope.SERVICE,
            category=C.GUARD_BLOCK,
            service=pair[0],
            operation=pair[1],
            code="ReadOnlyViolationError",
            region=region,
        )
        found[pair] = issue if pair not in found else found[pair].merged_with(issue)
    return [found[k] for k in sorted(found)]


def reduce_run(
    accounts: Iterable[AccountOutcome],
    outputs: Iterable[OutputOutcome] = (),
    issues: Iterable[Issue] = (),
    *,
    findings: Optional[Findings] = None,
    resources_found: int = 0,
    resources_reported: int = 0,
    guard_blocked: Iterable[Mapping[str, Any]] = (),
    guard_blocks: Optional[int] = None,
    cancelled_by: Optional[int] = None,
    usage_error: bool = False,
    run_error: Optional[Category] = None,
) -> RunOutcome:
    """The run's outcome. Issues are merged; unreported guard blocks added.

    ``guard_blocks`` defaults to the number of records in ``guard_blocked``.
    """
    guard_blocked = list(guard_blocked)
    issue_list = list(issues)
    issue_list.extend(guard_issues(guard_blocked, issue_list))
    return RunOutcome(
        accounts=list(accounts),
        outputs=list(outputs),
        issues=merge_issues(issue_list),
        findings=findings or Findings(),
        resources_found=resources_found,
        resources_reported=resources_reported,
        guard_blocks=len(guard_blocked) if guard_blocks is None else guard_blocks,
        cancelled_by=cancelled_by,
        usage_error=usage_error,
        run_error=Category(run_error) if run_error is not None else None,
    )
