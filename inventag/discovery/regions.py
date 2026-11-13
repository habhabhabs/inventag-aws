"""Which regions to scan, and where account-wide (global) services live.

``discover_regions`` replaces the old fallback to four hard-coded regions when
``ec2:DescribeRegions`` fails. It tries, in order:

1. ``ec2:DescribeRegions``: the regions enabled for the account.
2. ``account:ListRegions`` (regions with status ENABLED or ENABLED_BY_DEFAULT):
   a second read-only source, which works when only EC2 is denied.
3. Every region botocore knows for the session's partition (``aws``,
   ``aws-cn``, ``aws-us-gov`` ...), with a warning. Regions the account has
   not enabled then fail the per-region access check and are skipped.

All calls are read-only (``Describe``/``List``). Nothing here raises: the
worst case is the offline list in step 3.
"""

import logging
from typing import List, Optional, Tuple

from .arn_utils import partition_for_region
from .aws_clients import create_client

logger = logging.getLogger(__name__)

# Region that serves account-wide services (IAM, Route 53, CloudFront, the S3
# bucket list, Cost Explorer) in each partition.
_HOME_REGION = {
    "aws": "us-east-1",
    "aws-cn": "cn-north-1",
    "aws-us-gov": "us-gov-west-1",
    "aws-iso": "us-iso-east-1",
    "aws-iso-b": "us-isob-east-1",
}

# Cost Explorer has its own endpoint region per partition.
_COST_EXPLORER_REGION = {
    "aws": "us-east-1",
    "aws-cn": "cn-northwest-1",
    "aws-us-gov": "us-gov-west-1",
}


def partition_of(regions: Optional[List[str]] = None, session=None) -> str:
    """The partition of the scan: from the regions, else the session region."""
    for region in regions or []:
        if region:
            return _partition(region, session)
    region = getattr(session, "region_name", None) if session else None
    return _partition(region, session) if region else "aws"


def _partition(region: str, session=None) -> str:
    try:
        if session is not None and hasattr(session, "get_partition_for_region"):
            found = session.get_partition_for_region(region)
            if isinstance(found, str) and found:
                return found
    except Exception:
        pass
    return partition_for_region(region)


def global_home_region(regions: Optional[List[str]] = None, session=None) -> str:
    """Region to read global services from for this scan's partition."""
    return _HOME_REGION.get(partition_of(regions, session), "us-east-1")


def cost_explorer_region(regions: Optional[List[str]] = None, session=None) -> str:
    """Cost Explorer endpoint region for this scan's partition."""
    return _COST_EXPLORER_REGION.get(partition_of(regions, session), "us-east-1")


def _from_describe_regions(session, home: str) -> List[str]:
    ec2 = create_client(session, "ec2", home)
    return sorted(r["RegionName"] for r in ec2.describe_regions()["Regions"])


def _from_account_list_regions(session, home: str) -> List[str]:
    account = create_client(session, "account", home)
    regions = []
    for page in account.get_paginator("list_regions").paginate(
        RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
    ):
        regions.extend(r["RegionName"] for r in page.get("Regions", []))
    return sorted(set(regions))


def _from_botocore(session, partition: str) -> List[str]:
    try:
        return sorted(session.get_available_regions("ec2", partition_name=partition))
    except Exception:
        return []


def discover_regions(
    session, log: Optional[logging.Logger] = None
) -> Tuple[List[str], str]:
    """Regions to scan when the user named none, and where the list came from.

    Returns ``(regions, source)`` with ``source`` one of ``"ec2"``,
    ``"account"``, ``"botocore"`` or ``"none"``.
    """
    log = log or logger
    partition = partition_of(None, session)
    home = _HOME_REGION.get(partition, "us-east-1")
    if (
        getattr(session, "region_name", None)
        and partition_of([session.region_name], session) == partition
    ):
        # The session's own region is in the right partition and may be the
        # only one an SCP allows.
        home = session.region_name

    try:
        regions = _from_describe_regions(session, home)
        if regions:
            return regions, "ec2"
    except Exception as e:
        log.warning(
            f"ec2:DescribeRegions failed ({e}); trying account:ListRegions instead."
        )

    try:
        regions = _from_account_list_regions(session, home)
        if regions:
            log.info(f"Using {len(regions)} enabled regions from account:ListRegions.")
            return regions, "account"
    except Exception as e:
        log.warning(f"account:ListRegions failed ({e}).")

    regions = _from_botocore(session, partition)
    if regions:
        log.warning(
            f"Could not read the account's enabled regions. Trying all "
            f"{len(regions)} regions of the {partition} partition known to "
            "botocore; regions the account has not enabled will fail the "
            "access check and be skipped. Use --account-regions to choose."
        )
        return regions, "botocore"
    return [], "none"
