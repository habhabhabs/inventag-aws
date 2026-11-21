"""FinOps checks on the rows a scan already has (``--finops-checks``).

No AWS call and no change to any account: the checks read the inventory.
"""

from .checks import CHECKS, SCHEMA_VERSION, SNAPSHOT_AGE_DAYS, run_checks

__all__ = ["CHECKS", "SCHEMA_VERSION", "SNAPSHOT_AGE_DAYS", "run_checks"]
