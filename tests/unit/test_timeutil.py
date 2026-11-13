"""
Timestamp compatibility tests.

InvenTag now writes UTC timestamps with an explicit offset
(``2026-11-12T10:42:47.647344+00:00``). State snapshots written by releases up
to 4.2.27 contain the same instants without an offset
(``2026-11-12T10:42:47.647344``, from the deprecated ``datetime.utcnow()``).
These tests pin down that old and new values can be parsed, compared and
sorted together, and that an old snapshot compared with a new one does not
report every resource as modified.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inventag.state.changelog_generator import ChangelogGenerator
from inventag.state.delta_detector import DeltaDetector, DeltaReport
from inventag.state.state_manager import StateManager
from inventag.timeutil import parse_timestamp, utc_now, utc_now_iso

REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY = "2026-10-01T08:15:30.123456"  # written by datetime.utcnow().isoformat()
CURRENT = "2026-10-01T08:15:30.123456+00:00"  # written by this release


class TestUtcNow:
    def test_utc_now_is_timezone_aware(self):
        now = utc_now()
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(0)

    def test_utc_now_iso_has_explicit_utc_offset(self):
        text = utc_now_iso()
        assert text.endswith("+00:00")
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?\+00:00", text
        )
        # Round trip without losing the instant
        assert parse_timestamp(text).isoformat() == text


class TestParseTimestamp:
    def test_legacy_string_without_offset_is_utc(self):
        parsed = parse_timestamp(LEGACY)
        assert parsed == datetime(2026, 10, 1, 8, 15, 30, 123456, tzinfo=timezone.utc)

    def test_legacy_and_current_forms_are_the_same_instant(self):
        assert parse_timestamp(LEGACY) == parse_timestamp(CURRENT)

    def test_old_and_new_values_can_be_compared_and_subtracted(self):
        old = parse_timestamp("2026-10-01T08:15:30")  # old state file
        new = parse_timestamp("2026-11-12T10:42:47.647344+00:00")  # new state file
        assert old < new
        assert (new - old).days == 42

        # The reason the helper exists: the naive/aware mix fails in Python
        with pytest.raises(TypeError):
            datetime.fromisoformat("2026-10-01T08:15:30") < datetime.fromisoformat(
                "2026-11-12T10:42:47.647344+00:00"
            )

    def test_trailing_z_is_utc(self):
        assert parse_timestamp("2026-10-01T08:15:30Z") == parse_timestamp(
            "2026-10-01T08:15:30+00:00"
        )

    def test_other_offsets_are_converted_to_utc(self):
        parsed = parse_timestamp("2026-10-01T16:15:30+08:00")  # Singapore
        assert parsed.utcoffset() == timedelta(0)
        assert parsed == datetime(2026, 10, 1, 8, 15, 30, tzinfo=timezone.utc)

    def test_datetime_input(self):
        naive = datetime(2026, 10, 1, 8, 15, 30)
        assert parse_timestamp(naive) == datetime(
            2026, 10, 1, 8, 15, 30, tzinfo=timezone.utc
        )
        aware = datetime(2026, 10, 1, 8, 15, 30, tzinfo=timezone.utc)
        assert parse_timestamp(aware) == aware

    @pytest.mark.parametrize("bad", ["", "not-a-date", "2026-13-45T00:00:00"])
    def test_invalid_text_raises_value_error(self, bad):
        with pytest.raises(ValueError):
            parse_timestamp(bad)

    def test_wrong_type_raises_type_error(self):
        with pytest.raises(TypeError):
            parse_timestamp(1760000000)

    def test_mixed_strings_sort_chronologically(self):
        """discovered_at is sorted as text when duplicates are resolved."""
        values = [
            "2026-11-12T10:42:47.647344+00:00",  # new
            "2026-10-01T08:15:30.123456",  # legacy
            "2026-11-12T10:42:47.647343",  # legacy, one microsecond earlier
            "2026-10-01T08:15:30.123457+00:00",  # new, one microsecond later
        ]
        assert sorted(values) == sorted(values, key=parse_timestamp)


class TestNoDeprecatedUtcnow:
    def test_package_does_not_call_utcnow(self):
        """datetime.utcnow()/utcfromtimestamp() are deprecated since Python 3.12."""
        pattern = re.compile(r"\.utcnow\(|\.utcfromtimestamp\(")
        offenders = []
        for folder in ("inventag", "scripts"):
            for path in sorted((REPO_ROOT / folder).rglob("*.py")):
                for number, line in enumerate(path.read_text().splitlines(), 1):
                    if pattern.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")
        assert offenders == []


def _resource(discovered_at, instance_type="t3.micro"):
    return {
        "service": "EC2",
        "type": "Instance",
        "region": "ap-southeast-1",
        "id": "i-0abc1234def567890",
        "name": "web-server-01",
        "arn": "arn:aws:ec2:ap-southeast-1:123456789012:instance/i-0abc1234def567890",
        "account_id": "123456789012",
        "tags": {"Name": "web-server-01", "Environment": "production"},
        "instance_type": instance_type,
        "discovered_at": discovered_at,
        "discovery_timestamp": discovered_at,
        "consolidation_timestamp": discovered_at,
    }


class TestOldAndNewStateSnapshots:
    def test_timestamp_format_change_is_not_a_resource_change(self):
        old = [_resource("2026-10-01T08:15:30.123456")]
        new = [_resource("2026-11-12T10:42:47.647344+00:00")]

        report = DeltaDetector().detect_changes(
            old, new, "20261001_081530", "20261112_104247"
        )

        assert report.summary["modified_count"] == 0
        assert report.summary["unchanged_count"] == 1
        assert report.summary["total_changes"] == 0

    def test_real_change_is_still_detected_across_formats(self):
        old = [_resource("2026-10-01T08:15:30.123456")]
        new = [_resource("2026-11-12T10:42:47.647344+00:00", instance_type="m5.large")]

        report = DeltaDetector().detect_changes(
            old, new, "20261001_081530", "20261112_104247"
        )

        (modified,) = report.modified_resources
        assert [c.attribute_path for c in modified.attribute_changes] == [
            "instance_type"
        ]

    def test_state_file_from_older_release_loads_and_compares(self, tmp_path):
        """A snapshot written by 4.2.27 (naive timestamps) next to a new one."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        old_id = "20261001_081530"
        old_resources = [_resource("2026-10-01T08:15:30.123456")]
        old_file = state_dir / f"state_{old_id}.json"
        old_metadata = {
            "timestamp": old_id,
            "version": "1.0",
            "account_id": "123456789012",
            "regions": ["ap-southeast-1"],
            "resource_count": 1,
            "checksum": "0" * 64,
            "discovery_method": "multi-account",
            "compliance_status": None,
            "tags": {"multi_account": True},
        }
        old_file.write_text(
            json.dumps(
                {
                    "metadata": old_metadata,
                    "resources": old_resources,
                    "compliance_data": None,
                    "network_analysis": None,
                    "security_analysis": None,
                }
            )
        )
        (state_dir / "metadata.json").write_text(
            json.dumps(
                {
                    old_id: {
                        "file": str(old_file),
                        "metadata": old_metadata,
                        "size_bytes": 1,
                    }
                }
            )
        )

        manager = StateManager(state_dir=str(state_dir), retention_days=3650)
        new_id = manager.save_state(
            resources=[_resource(utc_now_iso())],
            account_id="123456789012",
            regions=["ap-southeast-1"],
            discovery_method="multi-account",
        )

        # Newest first; the old snapshot is still there and readable
        assert [s["state_id"] for s in manager.list_states()] == [new_id, old_id]
        assert manager.load_state(old_id).resources == old_resources

        report = DeltaDetector().detect_changes_by_state_id(manager, old_id, new_id)
        assert report.summary["total_changes"] == 0
        assert report.summary["unchanged_count"] == 1
        # The report itself is stamped in the new format
        assert parse_timestamp(report.timestamp).utcoffset() == timedelta(0)
        assert report.timestamp.endswith("+00:00")

    def test_trend_analysis_over_old_and_new_reports(self, tmp_path):
        """Changelog trends span reports stamped by old and new releases."""

        def report(timestamp, total_changes):
            return DeltaReport(
                state1_id="a",
                state2_id="b",
                timestamp=timestamp,
                summary={"total_changes": total_changes},
                added_resources=[],
                removed_resources=[],
                modified_resources=[],
                unchanged_resources=[],
                compliance_changes={},
                security_changes={},
                network_changes={},
                impact_analysis={},
                change_statistics={},
            )

        generator = ChangelogGenerator(output_dir=str(tmp_path))
        trend = generator._generate_trend_analysis(
            [
                report("2026-11-11T08:15:30.000001+00:00", 6),  # new format
                report("2026-11-01T08:15:30", 4),  # legacy format, oldest
            ]
        )

        assert trend.total_periods == 2
        # The legacy value is normalised to the current format on output
        assert trend.period_start == "2026-11-01T08:15:30+00:00"
        assert trend.period_end == "2026-11-11T08:15:30.000001+00:00"
        # 10 changes over 10 days
        assert trend.change_velocity == pytest.approx(1.0)
