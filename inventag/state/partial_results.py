"""
PartialResultStore - per-account results of a run that is not finished yet.

A multi-account run can take a long time. If it stops (timeout, Ctrl+C, one
account failing), accounts that finished are lost and the next run scans them
again. This store keeps the resources of each account that finished, so a
later run with the *same scope* can reuse them.

This is the storage part only. Nothing calls it yet: the discovery loop
decides when to save, load and clear (see ``docs`` of the audit report).

Layout (inside the state folder, so it is kept and cleaned with it)::

    <state_dir>/partial/<run_key>/<account>.json

``run_key`` is a hash of the scan scope (accounts, regions, services, tag
filters, InvenTag version). A different scope has a different folder, so
results of another scope are never reused. Files are written privately
(0600) through a temp file and an atomic rename, with secrets redacted the
same way as snapshots. Only files this class wrote are ever removed.
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..security.safe_output import ensure_private_dir, safe_filename_component
from .state_manager import _atomic_write_json, _redact

logger = logging.getLogger(__name__)

PARTIAL_SCHEMA_VERSION = 1
PARTIAL_DIR_NAME = "partial"
DEFAULT_MAX_AGE_HOURS = 24.0

_RUN_KEY_RE = re.compile(r"^[0-9a-f]{16}$")
_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.json$")


@dataclass
class PartialAccount:
    """What a finished account left behind."""

    account_id: str
    resources: List[Dict[str, Any]]
    completed_at: datetime
    regions: List[str]

    def age(self, now: Optional[datetime] = None) -> timedelta:
        return (now or datetime.now(timezone.utc)) - self.completed_at


def make_run_key(scope: Dict[str, Any]) -> str:
    """A stable key for a scan scope (any JSON-serializable description).

    Include everything that changes what a scan returns: the account IDs,
    regions, services, tag filters, billing options and the InvenTag version.
    """
    text = json.dumps(scope, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class PartialResultStore:
    """Save, load and clear per-account results for one run scope."""

    def __init__(
        self,
        state_dir: str,
        run_key: str,
        max_age_hours: Optional[float] = DEFAULT_MAX_AGE_HOURS,
    ):
        """
        Args:
            state_dir: The snapshot folder (``bom_output/state``).
            run_key: Value of :func:`make_run_key` for this run's scope.
            max_age_hours: Results older than this are not reused (and are
                removed by :meth:`clear`). None reuses results of any age.
        """
        if not _RUN_KEY_RE.match(str(run_key)):
            raise ValueError("run_key must come from make_run_key()")
        if max_age_hours is not None and max_age_hours <= 0:
            raise ValueError("max_age_hours must be above 0, or None")
        self.root = Path(state_dir) / PARTIAL_DIR_NAME
        self.directory = self.root / run_key
        self.run_key = run_key
        self.max_age_hours = max_age_hours

    def _path(self, account_id: str) -> Path:
        return self.directory / f"{safe_filename_component(account_id, 64)}.json"

    def save_account(
        self,
        account_id: str,
        resources: List[Dict[str, Any]],
        regions: Optional[List[str]] = None,
    ) -> Path:
        """Record a finished account. Call only when the account was scanned
        completely (no failed region or service): a partly scanned account
        reused later would hide resources."""
        ensure_private_dir(self.directory)
        path = self._path(account_id)
        _atomic_write_json(
            path,
            {
                "schema": PARTIAL_SCHEMA_VERSION,
                "run_key": self.run_key,
                "account_id": str(account_id),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "regions": list(regions or []),
                "resources": _redact(resources),
            },
            default=str,
        )
        return path

    def load_account(self, account_id: str) -> Optional[PartialAccount]:
        """Results saved for this account in this scope, or None.

        None also means: file missing, corrupt, from another scope or schema,
        or too old. Problems are logged, never raised, and the file is left
        alone; the account is then simply scanned again.
        """
        path = self._path(account_id)
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if (
                data.get("schema") != PARTIAL_SCHEMA_VERSION
                or data.get("run_key") != self.run_key
                or str(data.get("account_id")) != str(account_id)
                or not isinstance(data.get("resources"), list)
            ):
                raise ValueError("not a partial result for this account and scope")
            completed = datetime.fromisoformat(data["completed_at"])
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.warning(f"Ignoring partial result {path}: {e}")
            return None
        result = PartialAccount(
            account_id=str(account_id),
            resources=data["resources"],
            completed_at=completed,
            regions=list(data.get("regions") or []),
        )
        if self.max_age_hours is not None and result.age() > timedelta(
            hours=self.max_age_hours
        ):
            logger.info(
                f"Partial result for account {account_id} is older than "
                f"{self.max_age_hours} hours; scanning it again"
            )
            return None
        return result

    def completed_accounts(self) -> Dict[str, datetime]:
        """Accounts with a usable saved result (account ID -> completed time)."""
        found: Dict[str, datetime] = {}
        if not self.directory.is_dir():
            return found
        for name in sorted(os.listdir(self.directory)):
            if not _FILE_RE.match(name):
                continue
            account = name[: -len(".json")]
            loaded = self.load_account(account)
            if loaded is not None:
                found[account] = loaded.completed_at
        return found

    def clear(self) -> int:
        """Remove this scope's results (call after a fully successful run) and
        any results of other scopes that are past ``max_age_hours``. Returns
        the number of files removed. Empty folders are removed too."""
        removed = 0
        now = datetime.now(timezone.utc).timestamp()
        if not self.root.is_dir():
            return 0
        for scope_dir in [p for p in self.root.iterdir() if p.is_dir()]:
            if not _RUN_KEY_RE.match(scope_dir.name):
                continue  # not ours
            own = scope_dir.name == self.run_key
            for path in [p for p in scope_dir.iterdir() if p.is_file()]:
                if not _FILE_RE.match(path.name):
                    continue
                try:
                    old = (
                        self.max_age_hours is not None
                        and now - path.stat().st_mtime > self.max_age_hours * 3600
                    )
                    if own or old:
                        path.unlink()
                        removed += 1
                except OSError as e:
                    logger.warning(f"Could not remove partial result {path}: {e}")
            for folder in (scope_dir, self.root):
                try:
                    folder.rmdir()  # only succeeds when empty
                except OSError:
                    pass
        return removed
