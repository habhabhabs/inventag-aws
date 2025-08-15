"""
StateManager - Comprehensive inventory state persistence

Provides state saving, loading, cleanup, and export functionality with
timestamp tracking, metadata management, and efficient resource tracking.
"""

import json
import yaml
import os
import hashlib
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


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


@dataclass
class StateSnapshot:
    """Complete state snapshot with metadata and resources"""

    metadata: StateMetadata
    resources: List[Dict[str, Any]]
    compliance_data: Optional[Dict] = None
    network_analysis: Optional[Dict] = None
    security_analysis: Optional[Dict] = None


class StateManager:
    """
    Manages comprehensive inventory state persistence with versioning,
    cleanup policies, and export capabilities for CI/CD integration.
    """

    def __init__(
        self,
        state_dir: str = ".inventag/state",
        retention_days: int = 30,
        max_snapshots: int = 100,
        compression: bool = True,
    ):
        """
        Initialize StateManager with configurable storage and retention policies.

        Args:
            state_dir: Directory to store state files
            retention_days: Number of days to retain state snapshots
            max_snapshots: Maximum number of snapshots to keep
            compression: Whether to compress state files
        """
        self.state_dir = Path(state_dir)
        self.retention_days = retention_days
        self.max_snapshots = max_snapshots
        self.compression = compression

        # Create state directory if it doesn't exist
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metadata tracking
        self.metadata_file = self.state_dir / "metadata.json"
        self._load_metadata_index()

    def _load_metadata_index(self):
        """Load the metadata index for quick state lookup"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    self.metadata_index = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load metadata index: {e}")
                self.metadata_index = {}
        else:
            self.metadata_index = {}

    def _save_metadata_index(self):
        """Save the metadata index"""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata_index, f, indent=2)
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
    ) -> str:
        """
        Save current state with comprehensive metadata and tracking.

        Args:
            resources: List of discovered resources
            account_id: AWS account ID
            regions: List of scanned regions
            discovery_method: Method used for discovery
            compliance_data: Optional compliance analysis results
            network_analysis: Optional network analysis results
            security_analysis: Optional security analysis results
            tags: Optional custom tags for this state

        Returns:
            State ID (timestamp-based) for the saved state
        """
        # Generate unique timestamp with microseconds to avoid collisions
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        # Ensure timestamp uniqueness
        counter = 0
        original_timestamp = timestamp
        while timestamp in self.metadata_index:
            counter += 1
            timestamp = f"{original_timestamp}_{counter:03d}"

        checksum = self._calculate_checksum(resources)

        # Create metadata
        metadata = StateMetadata(
            timestamp=timestamp,
            version="1.0",
            account_id=account_id,
            regions=regions,
            resource_count=len(resources),
            checksum=checksum,
            discovery_method=discovery_method,
            compliance_status=(
                compliance_data.get("summary") if compliance_data else None
            ),
            tags=tags,
        )

        # Create state snapshot
        snapshot = StateSnapshot(
            metadata=metadata,
            resources=resources,
            compliance_data=compliance_data,
            network_analysis=network_analysis,
            security_analysis=security_analysis,
        )

        # Save state file
        state_file = self.state_dir / f"state_{timestamp}.json"
        try:
            with open(state_file, "w") as f:
                json.dump(asdict(snapshot), f, indent=2, default=str)

            # Update metadata index
            self.metadata_index[timestamp] = {
                "file": str(state_file),
                "metadata": asdict(metadata),
                "size_bytes": state_file.stat().st_size,
            }
            self._save_metadata_index()

            logger.info(
                f"State saved: {timestamp} ({len(resources)} resources, checksum: {checksum[:8]})"
            )

            # Perform cleanup if needed
            self._cleanup_old_states()

            return timestamp

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            raise

    def load_state(self, state_id: Optional[str] = None) -> Optional[StateSnapshot]:
        """
        Load state by ID or get the most recent state.

        Args:
            state_id: Specific state ID to load, or None for most recent

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

        state_file = Path(self.metadata_index[state_id]["file"])
        if not state_file.exists():
            logger.warning(f"State file {state_file} not found")
            return None

        try:
            with open(state_file, "r") as f:
                data = json.load(f)

            # Convert back to StateSnapshot
            metadata = StateMetadata(**data["metadata"])
            snapshot = StateSnapshot(
                metadata=metadata,
                resources=data["resources"],
                compliance_data=data.get("compliance_data"),
                network_analysis=data.get("network_analysis"),
                security_analysis=data.get("security_analysis"),
            )

            logger.info(
                f"State loaded: {state_id} ({len(snapshot.resources)} resources)"
            )
            return snapshot

        except Exception as e:
            logger.error(f"Failed to load state {state_id}: {e}")
            return None

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
                with open(output_file, "w") as f:
                    json.dump(export_data, f, indent=2, default=str)

            elif export_format == "yaml":
                export_data = (
                    asdict(snapshot) if include_metadata else snapshot.resources
                )
                with open(output_file, "w") as f:
                    yaml.dump(export_data, f, default_flow_style=False)

            elif export_format == "csv":
                try:
                    import pandas as pd

                    df = pd.DataFrame(snapshot.resources)
                    df.to_csv(output_file, index=False)
                except ImportError:
                    # Fallback to basic CSV writing without pandas
                    import csv

                    if snapshot.resources:
                        fieldnames = set()
                        for resource in snapshot.resources:
                            fieldnames.update(resource.keys())
                        fieldnames = sorted(list(fieldnames))

                        with open(output_file, "w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(snapshot.resources)

            else:
                raise ValueError(f"Unsupported export format: {export_format}")

            logger.info(f"State exported to {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Failed to export state: {e}")
            raise

    def _cleanup_old_states(self):
        """Clean up old states based on retention policies"""
        try:
            current_time = datetime.now(timezone.utc)
            states_to_remove = []

            # Check retention by age
            for state_id, state_info in self.metadata_index.items():
                try:
                    # Handle timestamp format with potential counter suffix
                    base_timestamp = (
                        state_id.split("_")[0] + "_" + state_id.split("_")[1]
                    )
                    if len(state_id.split("_")) == 2:
                        # Standard format: YYYYMMDD_HHMMSS
                        state_time = datetime.strptime(
                            state_id, "%Y%m%d_%H%M%S"
                        ).replace(tzinfo=timezone.utc)
                    else:
                        # Format with counter: YYYYMMDD_HHMMSS_NNN
                        state_time = datetime.strptime(
                            base_timestamp, "%Y%m%d_%H%M%S"
                        ).replace(tzinfo=timezone.utc)

                    age_days = (current_time - state_time).days

                    if age_days > self.retention_days:
                        states_to_remove.append(state_id)
                except ValueError as e:
                    logger.warning(
                        f"Could not parse timestamp for state {state_id}: {e}"
                    )
                    continue

            # Check retention by count (keep most recent)
            if len(self.metadata_index) > self.max_snapshots:
                sorted_states = sorted(self.metadata_index.keys(), reverse=True)
                states_to_remove.extend(sorted_states[self.max_snapshots :])

            # Remove duplicate entries
            states_to_remove = list(set(states_to_remove))

            # Perform cleanup
            for state_id in states_to_remove:
                self._remove_state(state_id)

            if states_to_remove:
                logger.info(f"Cleaned up {len(states_to_remove)} old states")
                # Save updated metadata index after cleanup
                self._save_metadata_index()

        except Exception as e:
            logger.error(f"Error during state cleanup: {e}")

    def _remove_state(self, state_id: str):
        """Remove a specific state and its files"""
        if state_id in self.metadata_index:
            state_file = Path(self.metadata_index[state_id]["file"])
            try:
                if state_file.exists():
                    state_file.unlink()
                del self.metadata_index[state_id]
                logger.debug(f"Removed state: {state_id}")
            except Exception as e:
                logger.error(f"Error removing state {state_id}: {e}")

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

            state_file = Path(self.metadata_index[sid]["file"])
            if not state_file.exists():
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
