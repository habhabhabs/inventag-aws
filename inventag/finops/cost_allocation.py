"""Cost allocation from Cost Explorer (``--finops-cost-allocation``).

For each account, with that account's own credentials, a fixed and small
number of Cost Explorer requests for the last full month (metric
``UnblendedCost``):

1. ``ListCostAllocationTags`` for the keys of the built-in
   ``finops-cost-allocation`` tag policy: which keys are active;
2. ``GetCostAndUsage`` grouped by SERVICE;
3. ``GetCostAndUsage`` grouped by LINKED_ACCOUNT;
4. ``GetCostAndUsage`` grouped by each active key (at most 4).

That is at most :data:`MAX_REQUESTS_PER_ACCOUNT` (7) requests. A page that
follows (``NextPageToken``) is a request too and is taken from the same
budget, at most :data:`MAX_PAGES_PER_GROUPING` per grouping; a table that
needs more is marked ``incomplete``. The SDK's own retries of a throttled
request are not counted here (AWS may charge them too).

Amounts are kept as the text AWS returns. No amount is computed, divided or
given to a resource. The run's start time comes in as an argument (no clock).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional, Sequence, Tuple

from botocore.exceptions import ClientError

from ..discovery.aws_clients import create_client
from ..discovery.regions import cost_explorer_region

SCHEMA_VERSION = 1
METRIC = "UnblendedCost"
MAX_REQUESTS_PER_ACCOUNT = 7
MAX_PAGES_PER_GROUPING = 3
NO_VALUE = "(no value)"

DENIED_CODES = frozenset(
    {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
        "UnauthorizedAccess",
        "AuthorizationError",
    }
)
THROTTLED_CODES = frozenset(
    {"Throttling", "ThrottlingException", "LimitExceededException"}
)

# Table status words.
READ = "read"
INCOMPLETE = "incomplete"
DENIED = "denied"
THROTTLED = "throttled"
ERROR = "error"
NOT_ACTIVE = "not_active"
NOT_FOUND = "not_found"
NOT_QUERIED = "not_queried"

# Key status words (ListCostAllocationTags).
ACTIVE = "active"
UNKNOWN = "unknown"


def allocation_keys() -> List[str]:
    """The keys of the built-in ``finops-cost-allocation`` tag policy, in order."""
    from .checks import builtin_policy

    return [rule["key"] for rule in builtin_policy().spec["required_tags"]]


def planned_requests(accounts: int) -> int:
    """The most requests of the feature for a run (SDK retries not counted)."""
    return MAX_REQUESTS_PER_ACCOUNT * max(int(accounts), 0)


def last_full_month(run_started: dt.datetime) -> Tuple[str, str]:
    """(start, end) of the month before the run's month; ``end`` is exclusive."""
    if not isinstance(run_started, dt.datetime) or run_started.tzinfo is None:
        raise ValueError("run_started must be a datetime with a time zone")
    day = run_started.astimezone(dt.timezone.utc).date()
    end = day.replace(day=1)
    start = (end - dt.timedelta(days=1)).replace(day=1)
    return start.isoformat(), end.isoformat()


def _outcome(error: BaseException) -> Tuple[str, str]:
    """(status, error code) of a failed request."""
    if isinstance(error, ClientError):
        code = str(error.response.get("Error", {}).get("Code", ""))
        if code in DENIED_CODES:
            return DENIED, code
        if code in THROTTLED_CODES:
            return THROTTLED, code
        return ERROR, code
    return ERROR, type(error).__name__


class _Budget:
    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0

    def take(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def _rows(groups: Sequence[Dict[str, Any]], tag_key: Optional[str]) -> List[Dict]:
    rows = []
    for group in groups:
        keys = group.get("Keys") or [""]
        name = str(keys[0])
        if tag_key is not None:
            prefix = f"{tag_key}$"
            value = name[len(prefix) :] if name.startswith(prefix) else name
            name = value if value else NO_VALUE
        metric = (group.get("Metrics") or {}).get(METRIC) or {}
        rows.append(
            {
                "name": name,
                "amount": str(metric.get("Amount", "")),
                "unit": str(metric.get("Unit", "")),
            }
        )
    return rows


def _groups(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    found = []
    for result in response.get("ResultsByTime") or []:
        found.extend(result.get("Groups") or [])
    return found


def _table(rows: List[Dict], status: str, code: str = "") -> Dict[str, Any]:
    units = sorted({r["unit"] for r in rows if r["unit"]})
    table = {
        "status": status,
        "currency": units[0] if len(units) == 1 else ("mixed" if units else ""),
        "rows": sorted(rows, key=lambda r: (r["name"], r["amount"], r["unit"])),
    }
    if code:
        table["error_code"] = code
    return table


def read_account(
    client, account_id: str, run_started: dt.datetime, keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """The cost allocation tables of one account (its own client)."""
    start, end = last_full_month(run_started)
    keys = list(allocation_keys() if keys is None else keys)
    budget = _Budget(MAX_REQUESTS_PER_ACCOUNT)
    failed: List[Dict[str, str]] = []

    # 1. Which keys are active as cost allocation tags.
    key_status = {key: UNKNOWN for key in keys}
    if keys and budget.take():
        try:
            answer = client.list_cost_allocation_tags(TagKeys=keys)
        except Exception as error:  # noted; every key is then queried
            status, code = _outcome(error)
            failed.append(
                {"operation": "ListCostAllocationTags", "status": status, "code": code}
            )
        else:
            seen = {
                str(t.get("TagKey")): str(t.get("Status", ""))
                for t in answer.get("CostAllocationTags") or []
            }
            for key in keys:
                if key not in seen:
                    key_status[key] = NOT_FOUND
                elif seen[key] == "Active":
                    key_status[key] = ACTIVE
                else:
                    key_status[key] = NOT_ACTIVE

    groupings: List[Tuple[str, Dict[str, str], Optional[str]]] = [
        ("service", {"Type": "DIMENSION", "Key": "SERVICE"}, None),
        ("linked_account", {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}, None),
    ]
    tables: Dict[str, Dict[str, Any]] = {}
    for key in keys:
        if key_status[key] in (ACTIVE, UNKNOWN):
            groupings.append((f"tag:{key}", {"Type": "TAG", "Key": key}, key))
        else:
            tables[f"tag:{key}"] = _table([], key_status[key])

    def request(group_by, token=None):
        params = {
            "TimePeriod": {"Start": start, "End": end},
            "Granularity": "MONTHLY",
            "Metrics": [METRIC],
            "GroupBy": [group_by],
        }
        if token:
            params["NextPageToken"] = token
        return client.get_cost_and_usage(**params)

    # After a denied or throttled GetCostAndUsage, no further request is made
    # for this account: each would be denied too, or retried by the SDK.
    stop: Optional[Tuple[str, str]] = None

    # 2 to 4. First pages, in a fixed order.
    pending: List[Tuple[str, Dict[str, str], Optional[str], str]] = []
    collected: Dict[str, List[Dict]] = {}
    for name, group_by, tag_key in groupings:
        if stop is not None:
            tables[name] = _table([], *stop)
            continue
        if not budget.take():
            tables[name] = _table([], NOT_QUERIED)
            continue
        try:
            answer = request(group_by)
        except Exception as error:
            status, code = _outcome(error)
            failed.append(
                {"operation": "GetCostAndUsage", "status": status, "code": code}
            )
            tables[name] = _table([], status, code)
            if status in (DENIED, THROTTLED):
                stop = (status, code)
            continue
        collected[name] = _rows(_groups(answer), tag_key)
        token = answer.get("NextPageToken")
        if token:
            pending.append((name, group_by, tag_key, token))
        else:
            tables[name] = _table(collected[name], READ)

    # Pages that follow, with what is left of the budget.
    for name, group_by, tag_key, token in pending:
        pages = 0
        status, code = READ, ""
        while token:
            if stop is not None:
                status = INCOMPLETE
                break
            if pages >= MAX_PAGES_PER_GROUPING or not budget.take():
                status = INCOMPLETE
                break
            pages += 1
            try:
                answer = request(group_by, token)
            except Exception as error:
                failed_status, code = _outcome(error)
                failed.append(
                    {
                        "operation": "GetCostAndUsage",
                        "status": failed_status,
                        "code": code,
                    }
                )
                status = INCOMPLETE  # the first pages are kept
                if failed_status in (DENIED, THROTTLED):
                    stop = (failed_status, code)
                break
            collected[name].extend(_rows(_groups(answer), tag_key))
            token = answer.get("NextPageToken")
        tables[name] = _table(collected[name], status, code)

    order = ["service", "linked_account"] + [f"tag:{k}" for k in keys]
    return {
        "account": str(account_id),
        "period": {"start": start, "end": end},
        "metric": METRIC,
        "requests": budget.used,
        "tag_keys": [{"key": k, "status": key_status[k]} for k in keys],
        "tables": {name: tables[name] for name in order},
        "failed": failed,
        **({"stopped_after": stop[0]} if stop else {}),
    }


def read_for_session(session, account_id: str, regions, run_started) -> Dict:
    """``read_account`` with a Cost Explorer client of ``session``."""
    client = create_client(session, "ce", cost_explorer_region(regions or None))
    return read_account(client, account_id, run_started)


def result(accounts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The ``finops_costs`` key: every account's tables, sorted by account."""
    return {
        "schema_version": SCHEMA_VERSION,
        "metric": METRIC,
        "accounts": sorted(accounts, key=lambda a: a["account"]),
    }


def snapshot_totals(costs: Dict[str, Any]) -> Dict[str, Any]:
    """``metadata.tags.cost_allocation``: the tables only (totals by service,
    linked account and tag value; no resource ID exists in them)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "metric": costs.get("metric", METRIC),
        "accounts": [
            {
                "account": a["account"],
                "period": dict(a["period"]),
                "tables": {
                    name: {
                        "status": t["status"],
                        "currency": t["currency"],
                        "rows": [dict(r) for r in t["rows"]],
                    }
                    for name, t in a["tables"].items()
                },
            }
            for a in costs.get("accounts", [])
        ],
    }


def for_account(costs: Dict[str, Any], account_id: str) -> Dict[str, Any]:
    """The key with one account only (``--per-account-reports``)."""
    return {
        **costs,
        "accounts": [
            a for a in costs.get("accounts", []) if a["account"] == account_id
        ],
    }


_STATUS_TEXT = {
    NOT_ACTIVE: "not active as a cost allocation tag",
    NOT_FOUND: "not found as a cost allocation tag",
    NOT_QUERIED: "not queried: request limit reached",
    INCOMPLETE: "incomplete: more pages than the request limit allows",
    DENIED: "not read: access denied",
    THROTTLED: "not read: throttled",
    ERROR: "not read: error",
}


def status_text(status: str) -> str:
    return _STATUS_TEXT.get(status, "")


def table_label(name: str) -> str:
    if name == "service":
        return "Service"
    if name == "linked_account":
        return "Linked account"
    return "Tag " + name.split(":", 1)[1]


def run_notes(costs: Dict[str, Any]) -> List[str]:
    """One note per account whose tables were not all read."""
    notes = []
    for account in costs.get("accounts", []):
        missing = [
            f"{table_label(name)} ({status_text(t['status'])})"
            for name, t in account["tables"].items()
            if t["status"] in (DENIED, THROTTLED, ERROR, INCOMPLETE, NOT_QUERIED)
        ]
        if missing:
            note = (
                f"Cost allocation in account {account['account']}: "
                + "; ".join(missing)
                + "."
            )
            if account.get("stopped_after"):
                note += (
                    " No further Cost Explorer request was made for this account "
                    f"after a request was {account['stopped_after']}."
                )
            notes.append(note)
    return notes


def denials(costs: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(account, service, operation) of each denied request."""
    found = []
    for account in costs.get("accounts", []):
        for item in account.get("failed", []):
            if item["status"] == DENIED:
                entry = (account["account"], "ce", item["operation"])
                if entry not in found:
                    found.append(entry)
    return found


def change_lines(previous: Any, current: Any, opted_out: bool = False) -> List[str]:
    """The block "Cost, previous run to this run" of the change report, or the
    one line that says why there is none. Empty when this run has no field and
    did not read cost allocation."""
    title = ["## Cost, previous run to this run", ""]
    if opted_out:
        return title + [
            "Not compared: this run's snapshot holds no cost figures "
            "(--no-cost-in-snapshot).",
            "",
        ]
    if not isinstance(current, dict):
        return []
    if not isinstance(previous, dict):
        return title + [
            "Not compared: the previous snapshot holds no cost allocation figures.",
            "",
        ]
    before = {a["account"]: a for a in previous.get("accounts", [])}
    lines = list(title)
    compared = False
    for account in current.get("accounts", []):
        old = before.get(account["account"])
        if old is None:
            lines.append(
                f"Account {account['account']}: not compared, the previous "
                "snapshot has no figures for it."
            )
            continue
        if old["period"] == account["period"]:
            lines.append(
                f"Account {account['account']}: not compared, both runs read the "
                f"same month ({account['period']['start']} to "
                f"{account['period']['end']})."
            )
            continue
        compared = True
        lines.append(
            f"Account {account['account']}, {current.get('metric', METRIC)}: "
            f"{old['period']['start']} to {old['period']['end']} (previous run), "
            f"{account['period']['start']} to {account['period']['end']} (this run)."
        )
        lines.append("")
        lines.append("| Grouping | Value | Previous run | This run | Currency |")
        lines.append("|---|---|---|---|---|")
        for name, table in account["tables"].items():
            old_rows = {
                r["name"]: r for r in (old["tables"].get(name) or {}).get("rows", [])
            }
            new_rows = {r["name"]: r for r in table.get("rows", [])}
            for value in sorted(set(old_rows) | set(new_rows)):
                o, n = old_rows.get(value), new_rows.get(value)
                unit = (n or o)["unit"]
                lines.append(
                    f"| {table_label(name)} | {value} | "
                    f"{o['amount'] if o else '-'} | {n['amount'] if n else '-'} | "
                    f"{unit} |"
                )
        lines.append("")
    if not compared and len(lines) == len(title):
        return []
    return lines + ([""] if lines[-1] != "" else [])


def failed_account(account_id: str, run_started, error: BaseException) -> Dict:
    """The tables of an account whose reading stopped on an unexpected error."""
    status, code = _outcome(error)
    try:
        start, end = last_full_month(run_started)
    except ValueError:
        start = end = ""
    names = ["service", "linked_account"] + [f"tag:{k}" for k in allocation_keys()]
    return {
        "account": str(account_id),
        "period": {"start": start, "end": end},
        "metric": METRIC,
        "requests": 0,
        "tag_keys": [],
        "tables": {name: _table([], status, code) for name in names},
        "failed": [],
    }
