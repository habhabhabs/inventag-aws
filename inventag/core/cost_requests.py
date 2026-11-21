"""The Cost Explorer requests a run plans to make, and what it says about them.

AWS charges for each Cost Explorer request, so a run says how many it will
make before discovery starts (one WARNING line). Every feature that calls
Cost Explorer adds its term here and nowhere else. Pure: no AWS call, no
clock, no logging.
"""

from typing import Optional, Tuple

Parts = Tuple[Tuple[str, int], ...]


def planned(
    accounts: int, billing_validation: bool, cost_analysis: bool
) -> Tuple[int, Parts]:
    """The most Cost Explorer requests of a run, and each feature's share.

    Billing validation: one request for each account. The cost trend of
    ``--enable-cost-analysis``: one request for the whole run.
    """
    accounts = max(int(accounts), 0)
    parts: Parts = (
        ("billing validation", accounts if billing_validation else 0),
        ("cost trend", 1 if cost_analysis and accounts else 0),
    )
    return sum(n for _, n in parts), parts


def announcement(count: int, parts: Parts) -> Optional[str]:
    """The run's line, or None when the run makes no Cost Explorer request."""
    if not count:
        return None
    shares = "; ".join(f"{name}: {n}" for name, n in parts)
    return (
        f"Cost Explorer: up to {count} request(s) in this run ({shares}). "
        "AWS charges for each."
    )


def trend_note(account_id: str) -> str:
    """Run note of a run with several accounts (A-80): the cost trend reads
    one bill, with the credentials of one account."""
    return (
        f"Cost trend: read once, with the credentials of account {account_id}. "
        "Its figures are that account's Cost Explorer view, not each account's own."
    )
