"""Which IAM actions a run was not allowed to use (the "Permissions" block of the run notes).

Everything here is pure: the run's records come in as arguments, a sorted list and the
note lines come out. There is no AWS call, no preflight check, no ``iam:Simulate*``, no
clock and no file. The list is built from what the run already saw, so a run that was
denied nothing has an empty list and prints nothing new.

Inputs, all optional:

* ``coverage``: the ledger entries (``CoverageEntry.to_dict``). A denied entry is a
  listing, a detail call, a Tagging API call or the Cost Explorer read, by its ``source``.
* ``account_failures``: ``{"account_id", "error_code"}`` for each account whose role could
  not be assumed. Only a denial code makes it ``sts:AssumeRole``.
* ``upload_outcomes``: ``{"error_code"}`` for each report file that failed to upload.
  The upload uses the default credentials, not a scanned account's session, so its
  entry names no account (``account`` is empty) and its line names "the identity that
  uploads the reports (the default credentials)".
* ``cost_denials``: ``(service, operation, error class)`` as the cost analyzer hands them
  over; ``analysis_denials``: ``(service, operation, error class, region)``.
* ``run_account``: the account whose session the steps of the whole run use (cost and
  network analysis).
* ``allocation_denials``: ``(account, service, operation)`` of each Cost Explorer request
  of ``--finops-cost-allocation`` that was denied (each account's own session).

Nothing of AWS's own error text is read or kept: only the error code decides, and the
code is not written into the result. An operation with no known IAM action is listed by
its API name with no action; no action is ever guessed.
"""

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .iam_policy import (
    NOT_IN_READONLYACCESS,
    PARENT_LISTINGS,
    action_for,
    botocore_call,
    in_readonlyaccess,
)

KINDS = (
    "role",
    "listing",
    "detail",
    "tagging",
    "billing",
    "pricing",
    "analysis",
    "upload",
    "optional",
    "allocation",
)

# A run-time listing of a billed service that nothing else listed: tried, not permitted,
# optional, never a failure. (No code writes this source yet: those listings leave no
# ledger entry today.)
OPTIONAL_SOURCE = "service-api-dynamic"

_KIND_OF_SOURCE = {
    "service-api": "listing",
    "service-api-detail": "detail",
    "tagging-api": "tagging",
    "billing": "billing",
    OPTIONAL_SOURCE: "optional",
}

# Error codes that mean "this identity may not do that".
DENIED_CODES = frozenset(
    {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
        "UnauthorizedAccess",
        "AuthorizationError",
    }
)
# Codes the ledger counts as denied that are not a missing permission.
_NOT_A_PERMISSION = frozenset({"OptInRequired"})

_EFFECT = {
    "role": "the account was not scanned",
    "listing": "resources of some services are missing",
    "detail": "some rows lack details",
    "tagging": "tags from the Tagging API are missing",
    "billing": "billing checks are skipped",
    "pricing": "cost estimates are missing",
    "analysis": "some analysis data is missing",
    "upload": "the reports were not uploaded",
    "optional": "listings of billed services that nothing else listed were not tried",
    "allocation": "cost allocation figures are missing",
}

_UNKNOWN = "IAM action not known to InvenTag"
_UPLOADER = "the identity that uploads the reports (the default credentials)"

Entry = Dict[str, Any]


def _entry(account: str, service: str, operation: str, kind: str, regions) -> Entry:
    call = botocore_call(service, operation)
    if call is not None:
        service, operation = call
    return {
        "account": account,
        "action": action_for(service, operation),
        "service": service,
        "operation": operation,
        "regions": sorted(set(regions)),
        "kind": kind,
    }


def _call_of(item: Mapping[str, Any]) -> Tuple[str, str]:
    """(service, operation) of a ledger entry, as botocore names when known."""
    service, operation = str(item.get("service") or ""), str(
        item.get("operation") or ""
    )
    return botocore_call(service, operation) or (service, operation)


def _sort_key(entry: Entry) -> Tuple:
    return (
        entry["account"],
        entry["action"] is None,
        entry["action"] or "",
        entry["service"],
        entry["operation"],
        entry["kind"],
    )


def build(
    coverage: Iterable[Mapping[str, Any]] = (),
    account_failures: Iterable[Mapping[str, Any]] = (),
    upload_outcomes: Iterable[Mapping[str, Any]] = (),
    cost_denials: Iterable[Sequence[str]] = (),
    analysis_denials: Iterable[Sequence[str]] = (),
    *,
    run_account: str = "",
    allocation_denials: Iterable[Sequence[str]] = (),
) -> List[Entry]:
    """The calls this run was not allowed to make, one entry per account, call and kind.

    Each entry has ``account``, ``action`` (None when InvenTag does not know it),
    ``service`` and ``operation`` (botocore names when InvenTag knows the call),
    ``regions`` (sorted) and ``kind``. The list is sorted by account, then action.
    """
    found: Dict[Tuple[str, str, str, str], Entry] = {}

    def add(account, service, operation, kind, regions=()):
        entry = _entry(str(account), service, operation, kind, regions)
        key = (entry["account"], entry["service"], entry["operation"], kind)
        if key in found:
            entry["regions"] = sorted(
                set(entry["regions"]) | set(found[key]["regions"])
            )
        found[key] = entry

    denied_ledger = []
    for item in coverage:
        kind = _KIND_OF_SOURCE.get(str(item.get("source", "")))
        code = str(item.get("error_code") or "")
        if kind is None or item.get("outcome") != "denied" or code in _NOT_A_PERMISSION:
            continue
        denied_ledger.append((kind, item))
    # Listings that were refused, by account, call and region: a child listing that
    # reads its parent first is recorded as refused when the parent was (see
    # PARENT_LISTINGS), and then its own action was never tried.
    refused = {
        (str(i.get("account_id") or ""), *_call_of(i), str(i.get("region") or ""))
        for kind, i in denied_ledger
        if kind == "listing"
    }
    for kind, item in denied_ledger:
        account = str(item.get("account_id") or "")
        region = str(item.get("region") or "")
        parent = PARENT_LISTINGS.get(_call_of(item))
        if kind == "listing" and parent and (account, *parent, region) in refused:
            continue
        add(
            account,
            str(item.get("service") or ""),
            str(item.get("operation") or ""),
            kind,
            [region] if region else [],
        )
    for failure in account_failures:
        if str(failure.get("error_code") or "") in DENIED_CODES:
            add(failure.get("account_id") or "", "sts", "AssumeRole", "role")
    if any(str(o.get("error_code") or "") in DENIED_CODES for o in upload_outcomes):
        add("", "s3", "PutObject", "upload")
    for service, operation, error_class in cost_denials:
        if error_class in DENIED_CODES:
            kind = {"pricing": "pricing", "ce": "billing"}.get(service, "analysis")
            add(run_account, service, operation, kind)
    for service, operation, error_class, region in analysis_denials:
        if error_class in DENIED_CODES:
            add(run_account, service, operation, "analysis", [region])
    # --finops-cost-allocation: (account, service, operation), each account's own.
    for account, service, operation in allocation_denials:
        add(account, service, operation, "allocation")
    return sorted(found.values(), key=_sort_key)


def _name_of(entry: Entry) -> str:
    if entry["action"]:
        return entry["action"]
    name = " ".join(p for p in (entry["service"], entry["operation"]) if p)
    return f"{name} ({_UNKNOWN})"


def _access_sentence(entries: Sequence[Entry]) -> str:
    known = sorted({e["action"] for e in entries if e["action"]})
    unknown = any(not e["action"] for e in entries)
    outside = [a for a in known if in_readonlyaccess(a) is False]
    inside = [a for a in known if in_readonlyaccess(a) is True]
    sentences = [
        f"{action} is not in ReadOnlyAccess; it is needed only for "
        f"{NOT_IN_READONLYACCESS[action]}."
        for action in outside
    ]
    if inside:
        if outside or unknown:
            sentences.append(
                "The other actions that InvenTag knows are in the AWS managed "
                "policy ReadOnlyAccess."
            )
        else:
            sentences.append(
                "All of them are in the AWS managed policy ReadOnlyAccess."
            )
    return " ".join(sentences)


def notes(entries: Sequence[Entry]) -> List[str]:
    """The "Permissions:" lines of the run notes, one per account, then one for the
    upload's identity; empty when nothing was denied."""
    lines = []
    groups = sorted({(e["kind"] == "upload", e["account"]) for e in entries})
    for upload, account in groups:
        mine = [
            e
            for e in entries
            if e["account"] == account and (e["kind"] == "upload") == upload
        ]
        names = []
        for entry in mine:
            name = _name_of(entry)
            if name not in names:
                names.append(name)
        effects = [_EFFECT[k] for k in KINDS if any(e["kind"] == k for e in mine)]
        if upload:
            where = _UPLOADER
        else:
            where = f"account {account}" if account else "this run"
        line = (
            f"Permissions: {len(names)} action(s) were not allowed for {where}: "
            f"{', '.join(names)}. Effect: {'; '.join(effects)}."
        )
        sentence = _access_sentence(mine)
        lines.append(f"{line} {sentence}" if sentence else line)
    return lines
