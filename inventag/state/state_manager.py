"""
StateManager - Comprehensive inventory state persistence

Provides state saving, loading, cleanup, and export functionality with
timestamp tracking, metadata management, and efficient resource tracking.
"""

import json
import yaml
import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, fields
import logging

from ..security.safe_output import ensure_private_dir, open_private, write_safe_csv
from ..security.secret_values import MASK, mask_secret_values

logger = logging.getLogger(__name__)

# Version written into new snapshots. "1.0" snapshots (no account scope) are
# still read. A snapshot with a higher major version is refused with a clear
# message instead of being half-read.
SNAPSHOT_VERSION = "1.1"
SUPPORTED_MAJOR_VERSION = 1

# Defaults for the retention policy (same as the values the status page lists).
DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_SNAPSHOTS = 100

# The only files InvenTag creates in the state folder, and the only ones the
# retention policy may delete.
STATE_FILE_RE = re.compile(r"^state_(\d{8}_\d{6})(?:_(\d{3}))?\.json$")
_TEMP_FILE_RE = re.compile(r"^\.state_[\w.]+\.tmp$")
_STALE_TEMP_SECONDS = 24 * 3600

# Secret values are hidden with the shared deny-list (one mechanism for
# discovery, reports, snapshots and checkpoints).
REDACTED = MASK


class StateLoadError(Exception):
    """A snapshot could not be read. The message says why and names the file."""


def _redact(value: Any) -> Any:
    """Copy of ``value`` with secret values replaced (see ``secret_values``)."""
    return mask_secret_values(value)


def _atomic_write_json(path: Path, data: Any, **dump_kwargs) -> None:
    """Write JSON to ``path`` through a private temp file and an atomic rename."""
    tmp = path.with_name(f".state_{path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open_private(tmp, "w") as f:
            json.dump(data, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _publish_new_file(tmp: Path, final: Path) -> bool:
    """Move ``tmp`` to ``final`` without overwriting. False if ``final`` exists."""
    try:
        os.link(tmp, final)
    except FileExistsError:
        return False
    except OSError:
        # Hard links not supported here: fall back to check-then-rename.
        if final.exists():
            return False
        os.replace(tmp, final)
        return True
    try:
        tmp.unlink()
    except OSError:
        pass
    return True


@dataclass
class StateMetadata:
    """Metadata for state snapshots"""

    timestamp: str
    version: str
    account_id: str
    regions: List[str]
    resource_count: int
    checksum: str
    discovery_method: str
    compliance_status: Optional[Dict] = None
    tags: Optional[Dict] = None
    # Which accounts this run scanned completely, and which it could not scan.
    # None (older snapshots, or callers that do not pass them) means "unknown":
    # the account list is then derived from source_account_id in the resources.
    accounts_scanned: Optional[List[str]] = None
    accounts_failed: Optional[List[str]] = None


@dataclass
class StateSnapshot:
    """Complete state snapshot with metadata and resources"""

    metadata: StateMetadata
    resources: List[Dict[str, Any]]
    compliance_data: Optional[Dict] = None
    network_analysis: Optional[Dict] = None
    security_analysis: Optional[Dict] = None


def _check_limit(name: str, value: Optional[int]) -> Optional[int]:
    """None keeps everything; otherwise a whole number of at least 1."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(
            f"{name} must be a whole number of 1 or more, or None to keep everything "
            f"(got {value!r})"
        )
    return value


class StateManager:
    """
    Manages comprehensive inventory state persistence with versioning,
    cleanup policies, and export capabilities for CI/CD integration.
    """

    def __init__(
        self,
        state_dir: str = ".inventag/state",
        retention_days: Optional[int] = DEFAULT_RETENTION_DAYS,
        max_snapshots: Optional[int] = DEFAULT_MAX_SNAPSHOTS,
        compression: bool = True,
    ):
        """
        Initialize StateManager with configurable storage and retention policies.

        Args:
            state_dir: Directory to store state files
            retention_days: Snapshots older than this many days are removed
                when a new snapshot is saved. None keeps snapshots of any age.
            max_snapshots: Only the newest this many snapshots are kept. None
                keeps every snapshot.
            compression: Not used (snapshots are plain JSON). Kept so existing
                callers keep working.

        The snapshot just written and the one it is compared against are never
        removed, so ``max_snapshots=1`` still leaves two files. Only files named
        ``state_<timestamp>.json`` that InvenTag wrote are ever removed.
        """
        self.state_dir = Path(state_dir)
        self.retention_days = _check_limit("retention_days", retention_days)
        self.max_snapshots = _check_limit("max_snapshots", max_snapshots)
        self.compression = compression

        # Create state directory if it doesn't exist
        ensure_private_dir(self.state_dir)

        # Initialize metadata tracking
        self.metadata_file = self.state_dir / "metadata.json"
        self._load_metadata_index()

    # ------------------------------------------------------------------ index
    def _state_path(self, state_id: str) -> Optional[Path]:
        """Path of a snapshot inside the state folder, or None if not valid.

        The index stores a path, but the file is always looked up by name in
        ``state_dir``: the folder may have moved (a CI cache restored to another
        path), and an edited index must not point deletes at other files.
        """
        entry = self.metadata_index.get(state_id)
        if not isinstance(entry, dict) or not entry.get("file"):
            return None
        name = Path(str(entry["file"])).name
        if not STATE_FILE_RE.match(name):
            return None
        return self.state_dir / name

    def _load_metadata_index(self):
        """Load the metadata index for quick state lookup.

        A missing, unreadable or damaged index is rebuilt from the snapshot
        files, so history is never lost because ``metadata.json`` is.
        """
        self.metadata_index = {}
        needs_rebuild = False
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    raise ValueError("index is not a JSON object")
                self.metadata_index = loaded
            except Exception as e:
                logger.warning(
                    f"Could not load metadata index {self.metadata_file} ({e}); "
                    "rebuilding it from the snapshot files"
                )
                needs_rebuild = True
        if needs_rebuild or self._unindexed_files():
            self._reconcile_index()

    def _unindexed_files(self) -> List[str]:
        """Snapshot file names in the folder that the index does not list."""
        known = {
            Path(str(e.get("file", ""))).name
            for e in self.metadata_index.values()
            if isinstance(e, dict)
        }
        try:
            names = os.listdir(self.state_dir)
        except OSError:
            return []
        return sorted(n for n in names if STATE_FILE_RE.match(n) and n not in known)

    def _reconcile_index(self):
        """Add snapshot files that another run (or a lost index) left unlisted."""
        added = 0
        for name in self._unindexed_files():
            path = self.state_dir / name
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                meta = data["metadata"]
                state_id = STATE_FILE_RE.match(name).group(1)
                if STATE_FILE_RE.match(name).group(2):
                    state_id += "_" + STATE_FILE_RE.match(name).group(2)
                self.metadata_index[state_id] = {
                    "file": str(path),
                    "metadata": meta,
                    "size_bytes": path.stat().st_size,
                }
                added += 1
            except Exception as e:
                logger.warning(
                    f"Snapshot file {path} is not a readable snapshot ({e}); "
                    "it was left in place and is not used"
                )
        if added:
            logger.info(f"Added {added} snapshot(s) found in {self.state_dir}")
            self._save_metadata_index()

    def _save_metadata_index(self):
        """Save the metadata index (private temp file, then atomic rename)"""
        try:
            _atomic_write_json(self.metadata_file, self.metadata_index, indent=2)
        except Exception as e:
            logger.error(f"Could not save metadata index: {e}")

    def _calculate_checksum(self, resources: List[Dict]) -> str:
        """Calculate checksum for resource data to detect changes"""
        # Sort resources by ARN/ID for consistent checksums
        sorted_resources = sorted(
            resources, key=lambda x: x.get("arn", x.get("id", ""))
        )

        # Create a simplified representation for checksum
        checksum_data = []
        for resource in sorted_resources:
            checksum_data.append(
                {
                    "arn": resource.get("arn", ""),
                    "id": resource.get("id", ""),
                    "service": resource.get("service", ""),
                    "type": resource.get("type", ""),
                    "region": resource.get("region", ""),
                    "tags": resource.get("tags", {}),
                    "compliance_status": resource.get("compliance_status", ""),
                }
            )

        data_str = json.dumps(checksum_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    @staticmethod
    def _derive_accounts(resources: List[Dict]) -> Optional[List[str]]:
        """Accounts named by source_account_id in the resources (None if none)."""
        accounts = {
            str(r["source_account_id"])
            for r in resources
            if isinstance(r, dict) and r.get("source_account_id")
        }
        return sorted(accounts) if accounts else None

    def save_state(
        self,
        resources: List[Dict],
        account_id: str,
        regions: List[str],
        discovery_method: str = "multi-method",
        compliance_data: Optional[Dict] = None,
        network_analysis: Optional[Dict] = None,
        security_analysis: Optional[Dict] = None,
        tags: Optional[Dict] = None,
        accounts_scanned: Optional[Iterable[str]] = None,
        accounts_failed: Optional[Iterable[str]] = None,
    ) -> str:
        """
        Save current state with comprehensive metadata and tracking.

        The file is written to a private temp file, flushed to disk and moved
        into place without overwriting another run's snapshot, so a crash or a
        second run in the same folder never leaves a half-written snapshot.
        Values that are secrets (Lambda environment variables, passwords,
        tokens, private keys) are replaced by ``[REDACTED]`` before writing.

        Args:
            resources: List of discovered resources
            account_id: AWS account ID
            regions: List of scanned regions
            discovery_method: Method used for discovery
            compliance_data: Optional compliance analysis results
            network_analysis: Optional network analysis results
            security_analysis: Optional security analysis results
            tags: Optional custom tags for this state
            accounts_scanned: Accounts this run scanned completely. Default:
                the accounts named by ``source_account_id`` in ``resources``.
            accounts_failed: Accounts this run could not scan (or scanned only
                in part). A comparison leaves them out instead of reporting
                all their resources as removed.

        Returns:
            State ID (timestamp-based) for the saved state
        """
        # Pick up snapshots another run wrote since this object was created.
        if self._unindexed_files():
            self._reconcile_index()
        previous_id = max(self.metadata_index) if self.metadata_index else None

        failed = sorted({str(a) for a in (accounts_failed or [])})
        if accounts_scanned is not None:
            scanned = sorted({str(a) for a in accounts_scanned} - set(failed))
        else:
            scanned = self._derive_accounts(resources)
            if scanned is not None:
                scanned = sorted(set(scanned) - set(failed))

        now = datetime.now(timezone.utc)
        base_timestamp = now.strftime("%Y%m%d_%H%M%S")
        checksum = self._calculate_checksum(resources)

        def build_metadata(timestamp: str) -> Dict[str, Any]:
            metadata = StateMetadata(
                timestamp=timestamp,
                version=SNAPSHOT_VERSION,
                account_id=account_id,
                regions=regions,
                resource_count=len(resources),
                checksum=checksum,
                discovery_method=discovery_method,
                compliance_status=(
                    compliance_data.get("summary") if compliance_data else None
                ),
                tags=tags,
                accounts_scanned=scanned,
                accounts_failed=failed or None,
            )
            return asdict(metadata)

        def build(timestamp: str) -> Dict[str, Any]:
            return {
                "metadata": build_metadata(timestamp),
                "resources": _redact(resources),
                "compliance_data": _redact(compliance_data),
                "network_analysis": _redact(network_analysis),
                "security_analysis": _redact(security_analysis),
            }

        tmp = (
            self.state_dir
            / f".state_{base_timestamp}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
        )

        def write_tmp(snapshot: Dict[str, Any]) -> None:
            with open_private(tmp, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())

        # The new ID must sort after every existing one: load_state() and the
        # comparison pick "newest" by ID. This also covers a clock that went
        # backwards, and a same-second ID freed by retention.
        newest = max(self.metadata_index) if self.metadata_index else ""
        if newest[:15] > base_timestamp:
            base_timestamp = newest[:15]
        counter = 0
        timestamp = base_timestamp
        while (
            timestamp <= newest or (self.state_dir / f"state_{timestamp}.json").exists()
        ):
            counter += 1
            timestamp = f"{base_timestamp}_{counter:03d}"
        state_file = self.state_dir / f"state_{timestamp}.json"
        try:
            data = build(timestamp)
            write_tmp(data)
            # Another process may take the name between the check and the move.
            while not _publish_new_file(tmp, state_file):
                counter += 1
                timestamp = f"{base_timestamp}_{counter:03d}"
                state_file = self.state_dir / f"state_{timestamp}.json"
                data["metadata"]["timestamp"] = timestamp
                write_tmp(data)
        except BaseException as e:
            logger.error(f"Failed to save state: {e}")
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        finally:
            data = None

        self.metadata_index[timestamp] = {
            "file": str(state_file),
            "metadata": build_metadata(timestamp),
            "size_bytes": state_file.stat().st_size,
        }
        self._save_metadata_index()

        logger.info(
            f"State saved: {timestamp} ({len(resources)} resources, checksum: {checksum[:8]})"
        )

        # Never remove the snapshot just written or the one it is compared with.
        protect = {timestamp}
        if previous_id:
            protect.add(previous_id)
        self._cleanup_old_states(protect=protect)

        return timestamp

    @staticmethod
    def _parse_snapshot(data: Any, source: str) -> "StateSnapshot":
        """Build a StateSnapshot from loaded JSON, or raise StateLoadError."""
        if not isinstance(data, dict) or not isinstance(data.get("metadata"), dict):
            raise StateLoadError(
                f"{source} is not an InvenTag snapshot (no 'metadata' section)"
            )
        if not isinstance(data.get("resources"), list):
            raise StateLoadError(
                f"{source} is not an InvenTag snapshot (no 'resources' list)"
            )
        meta = data["metadata"]
        version = str(meta.get("version", "1.0"))
        try:
            major = int(version.split(".")[0])
        except ValueError:
            major = None
        if major is None or major > SUPPORTED_MAJOR_VERSION:
            raise StateLoadError(
                f"{source} was written by a newer InvenTag (snapshot version "
                f"{version}; this release reads version {SUPPORTED_MAJOR_VERSION}.x). "
                "Update InvenTag, or move the file away to start a new history"
            )
        known = {f.name for f in fields(StateMetadata)}
        required = {
            "timestamp",
            "version",
            "account_id",
            "regions",
            "resource_count",
            "checksum",
            "discovery_method",
        }
        defaults = {
            "version": "1.0",
            "account_id": "unknown",
            "regions": [],
            "resource_count": len(data["resources"]),
            "checksum": "",
            "discovery_method": "unknown",
        }
        values = {k: v for k, v in meta.items() if k in known}
        for key in required - set(values):
            if key == "timestamp":
                raise StateLoadError(f"{source} has no timestamp in its metadata")
            values[key] = defaults[key]
        return StateSnapshot(
            metadata=StateMetadata(**values),
            resources=data["resources"],
            compliance_data=data.get("compliance_data"),
            network_analysis=data.get("network_analysis"),
            security_analysis=data.get("security_analysis"),
        )

    def load_state(
        self, state_id: Optional[str] = None, strict: bool = False
    ) -> Optional[StateSnapshot]:
        """
        Load state by ID or get the most recent state.

        Args:
            state_id: Specific state ID to load, or None for most recent
            strict: Raise StateLoadError (with the reason) when the snapshot
                exists but cannot be read, instead of logging and returning None.

        Returns:
            StateSnapshot or None if not found
        """
        if state_id is None:
            # Get most recent state
            if not self.metadata_index:
                return None
            state_id = max(self.metadata_index.keys())

        if state_id not in self.metadata_index:
            logger.warning(f"State {state_id} not found")
            return None

        state_file = self._state_path(state_id)
        if state_file is None or not state_file.exists():
            message = (
                f"Snapshot file for state {state_id} is missing from {self.state_dir}"
            )
            if strict:
                raise StateLoadError(message)
            logger.warning(message)
            return None

        try:
            with open(state_file, "r") as f:
                data = json.load(f)
            snapshot = self._parse_snapshot(data, f"Snapshot {state_file}")
        except StateLoadError as e:
            if strict:
                raise
            logger.error(f"Failed to load state {state_id}: {e}")
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            message = (
                f"Snapshot {state_file} is corrupt or truncated ({e}). "
                "The file was not changed or deleted"
            )
            if strict:
                raise StateLoadError(message) from e
            logger.error(message)
            return None
        except Exception as e:
            message = f"Snapshot {state_file} could not be read ({e})"
            if strict:
                raise StateLoadError(message) from e
            logger.error(f"Failed to load state {state_id}: {e}")
            return None

        logger.info(f"State loaded: {state_id} ({len(snapshot.resources)} resources)")
        return snapshot

    def find_previous_state(
        self, current_state_id: str
    ) -> Tuple[Optional[str], List[str]]:
        """The newest snapshot before ``current_state_id`` that can be read.

        Returns ``(state_id, problems)``. ``problems`` lists the newer
        snapshots that were skipped because they are corrupt, truncated or from
        a newer release, each with the reason, so the caller can tell the user.
        ``state_id`` is None when there is no readable earlier snapshot.
        """
        problems: List[str] = []
        for state_id in sorted(self.metadata_index, reverse=True):
            if state_id >= current_state_id:
                continue
            try:
                self.load_state(state_id, strict=True)
                return state_id, problems
            except StateLoadError as e:
                problems.append(f"{state_id}: {e}")
        return None, problems

    def list_states(self, limit: Optional[int] = None) -> List[Dict]:
        """
        List available states with metadata.

        Args:
            limit: Maximum number of states to return

        Returns:
            List of state metadata dictionaries
        """
        states = []
        for state_id in sorted(self.metadata_index.keys(), reverse=True):
            state_info = self.metadata_index[state_id].copy()
            state_info["state_id"] = state_id
            states.append(state_info)

            if limit and len(states) >= limit:
                break

        return states

    def get_state_comparison_data(self, state_id1: str, state_id2: str) -> Dict:
        """
        Get comparison data between two states for delta analysis.

        Args:
            state_id1: First state ID (typically older)
            state_id2: Second state ID (typically newer)

        Returns:
            Dictionary with comparison metadata and resource lists
        """
        state1 = self.load_state(state_id1)
        state2 = self.load_state(state_id2)

        if not state1 or not state2:
            raise ValueError("One or both states not found")

        return {
            "state1": {
                "id": state_id1,
                "metadata": asdict(state1.metadata),
                "resources": state1.resources,
            },
            "state2": {
                "id": state_id2,
                "metadata": asdict(state2.metadata),
                "resources": state2.resources,
            },
        }

    def export_state(
        self,
        state_id: str,
        export_format: str = "json",
        output_file: Optional[str] = None,
        include_metadata: bool = True,
    ) -> str:
        """
        Export state for CI/CD integration with versioning.

        Args:
            state_id: State ID to export
            export_format: Export format (json, yaml, csv)
            output_file: Output filename, auto-generated if None
            include_metadata: Whether to include metadata in export

        Returns:
            Path to exported file
        """
        snapshot = self.load_state(state_id)
        if not snapshot:
            raise ValueError(f"State {state_id} not found")

        if output_file is None:
            output_file = f"inventag_export_{state_id}.{export_format}"

        try:
            if export_format == "json":
                export_data = (
                    asdict(snapshot) if include_metadata else snapshot.resources
                )
                with open_private(output_file, "w") as f:
                    json.dump(export_data, f, indent=2, default=str)

            elif export_format == "yaml":
                export_data = (
                    asdict(snapshot) if include_metadata else snapshot.resources
                )
                with open_private(output_file, "w") as f:
                    yaml.dump(export_data, f, default_flow_style=False)

            elif export_format == "csv":
                # Values come from scanned accounts: neutralise spreadsheet formulas.
                fieldnames = sorted(
                    {key for resource in snapshot.resources for key in resource}
                )
                with open_private(output_file, "w", newline="", encoding="utf-8") as f:
                    write_safe_csv(f, fieldnames, snapshot.resources)

            else:
                raise ValueError(f"Unsupported export format: {export_format}")

            logger.info(f"State exported to {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Failed to export state: {e}")
            raise

    def _cleanup_old_states(self, protect: Optional[Iterable[str]] = None):
        """Remove snapshots beyond the retention policy.

        ``protect`` lists state IDs that are never removed (the snapshot just
        written and the one it is compared with). Only ``state_*.json`` files
        listed in the index, and stale temp files this class left behind, are
        ever deleted. Nothing is removed when both limits are None.
        """
        protected = set(protect or ())
        try:
            self._remove_stale_temp_files()
            if self.retention_days is None and self.max_snapshots is None:
                return

            current_time = datetime.now(timezone.utc)
            states_to_remove = set()

            # Check retention by age
            if self.retention_days is not None:
                for state_id in self.metadata_index:
                    match = STATE_FILE_RE.match(f"state_{state_id}.json")
                    if not match:
                        logger.warning(
                            f"Could not parse timestamp for state {state_id}"
                        )
                        continue
                    state_time = datetime.strptime(
                        match.group(1), "%Y%m%d_%H%M%S"
                    ).replace(tzinfo=timezone.utc)
                    if (current_time - state_time).days > self.retention_days:
                        states_to_remove.add(state_id)

            # Check retention by count (keep most recent)
            if (
                self.max_snapshots is not None
                and len(self.metadata_index) > self.max_snapshots
            ):
                sorted_states = sorted(self.metadata_index.keys(), reverse=True)
                states_to_remove.update(sorted_states[self.max_snapshots :])

            states_to_remove -= protected

            removed = 0
            for state_id in sorted(states_to_remove):
                if self._remove_state(state_id):
                    removed += 1

            if removed:
                logger.info(f"Cleaned up {removed} old states")
                # Save updated metadata index after cleanup
                self._save_metadata_index()

        except Exception as e:
            logger.error(f"Error during state cleanup: {e}")

    def _remove_stale_temp_files(self):
        """Delete temp files from crashed runs (ours, older than a day)."""
        now = datetime.now(timezone.utc).timestamp()
        try:
            names = os.listdir(self.state_dir)
        except OSError:
            return
        for name in names:
            if not _TEMP_FILE_RE.match(name):
                continue
            path = self.state_dir / name
            try:
                if now - path.stat().st_mtime > _STALE_TEMP_SECONDS:
                    path.unlink()
            except OSError:
                pass

    def _remove_state(self, state_id: str) -> bool:
        """Remove a specific state and its file. True if it was removed."""
        if state_id not in self.metadata_index:
            return False
        state_file = self._state_path(state_id)
        try:
            if state_file is not None and state_file.exists():
                state_file.unlink()
            del self.metadata_index[state_id]
            logger.debug(f"Removed state: {state_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing state {state_id}: {e}")
            return False

    def get_storage_stats(self) -> Dict:
        """Get storage statistics for state management"""
        total_size = 0
        total_files = 0

        for state_info in self.metadata_index.values():
            total_size += state_info.get("size_bytes", 0)
            total_files += 1

        return {
            "total_states": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "state_directory": str(self.state_dir),
            "retention_days": self.retention_days,
            "max_snapshots": self.max_snapshots,
        }

    def validate_state_integrity(self, state_id: Optional[str] = None) -> Dict:
        """
        Validate state integrity by checking checksums and file consistency.

        Args:
            state_id: Specific state to validate, or None for all states

        Returns:
            Validation results dictionary
        """
        results = {
            "valid_states": [],
            "invalid_states": [],
            "missing_files": [],
            "checksum_mismatches": [],
        }

        states_to_check = [state_id] if state_id else list(self.metadata_index.keys())

        for sid in states_to_check:
            if sid not in self.metadata_index:
                results["invalid_states"].append(sid)
                continue

            state_file = self._state_path(sid)
            if state_file is None or not state_file.exists():
                results["missing_files"].append(sid)
                continue

            # Load and validate checksum
            try:
                snapshot = self.load_state(sid)
                if snapshot:
                    calculated_checksum = self._calculate_checksum(snapshot.resources)
                    stored_checksum = snapshot.metadata.checksum

                    if calculated_checksum == stored_checksum:
                        results["valid_states"].append(sid)
                    else:
                        results["checksum_mismatches"].append(
                            {
                                "state_id": sid,
                                "stored": stored_checksum,
                                "calculated": calculated_checksum,
                            }
                        )
                else:
                    results["invalid_states"].append(sid)

            except Exception as e:
                results["invalid_states"].append(f"{sid}: {str(e)}")

        return results
