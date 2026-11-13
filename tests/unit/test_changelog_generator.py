"""
Unit tests for ChangelogGenerator

Tests changelog generation with structured change entries, timestamps,
categorization, impact assessment, and multi-format output support.
"""

import pytest
import json
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from dataclasses import asdict

from inventag.state.changelog_generator import (
    ChangelogGenerator,
    ChangelogFormat,
    ChangelogEntry,
    ChangelogSection,
    ChangelogSummary,
    TrendAnalysis,
    Changelog,
)
from inventag.state.delta_detector import (
    DeltaReport,
    ResourceChange,
    AttributeChange,
    ChangeType,
    ChangeSeverity,
    ChangeCategory,
)


class TestChangelogGenerator:
    """Test ChangelogGenerator functionality"""

    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """Create temporary output directory"""
        output_dir = tmp_path / "changelogs"
        output_dir.mkdir()
        return str(output_dir)

    @pytest.fixture
    def changelog_generator(self, temp_output_dir):
        """Create ChangelogGenerator instance"""
        return ChangelogGenerator(
            output_dir=temp_output_dir,
            include_technical_details=True,
            include_remediation_steps=True,
            group_by_service=True,
        )

    @pytest.fixture
    def sample_attribute_change(self):
        """Create sample attribute change"""
        return AttributeChange(
            attribute_path="security_groups",
            old_value=["sg-old123"],
            new_value=["sg-new456"],
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.SECURITY,
            severity=ChangeSeverity.HIGH,
            description="Security group changed",
        )

    @pytest.fixture
    def sample_resource_change(self, sample_attribute_change):
        """Create sample resource change"""
        return ResourceChange(
            resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_id="i-1234567890abcdef0",
            service="EC2",
            resource_type="Instance",
            region="us-east-1",
            change_type=ChangeType.MODIFIED,
            attribute_changes=[sample_attribute_change],
            compliance_changes=[],
            security_impact="Security group modification may affect network access",
            network_impact="Network connectivity may be affected",
            related_resources=["sg-new456"],
            severity=ChangeSeverity.HIGH,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @pytest.fixture
    def sample_delta_report(self, sample_resource_change):
        """Create sample delta report"""
        return DeltaReport(
            state1_id="20240101_120000",
            state2_id="20240101_130000",
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary={
                "total_resources_old": 100,
                "total_resources_new": 101,
                "added_count": 1,
                "removed_count": 0,
                "modified_count": 1,
                "unchanged_count": 99,
                "total_changes": 2,
            },
            added_resources=[
                ResourceChange(
                    resource_arn="arn:aws:s3:::new-bucket",
                    resource_id="new-bucket",
                    service="S3",
                    resource_type="Bucket",
                    region="us-east-1",
                    change_type=ChangeType.ADDED,
                    severity=ChangeSeverity.MEDIUM,
                )
            ],
            removed_resources=[],
            modified_resources=[sample_resource_change],
            unchanged_resources=[],
            compliance_changes={},
            security_changes={},
            network_changes={},
            impact_analysis={},
            change_statistics={},
        )

    def test_changelog_generator_initialization(self, temp_output_dir):
        """Test ChangelogGenerator initialization"""
        generator = ChangelogGenerator(
            output_dir=temp_output_dir,
            include_technical_details=False,
            include_remediation_steps=False,
            group_by_service=False,
        )

        assert generator.output_dir == Path(temp_output_dir)
        assert not generator.include_technical_details
        assert not generator.include_remediation_steps
        assert not generator.group_by_service
        assert generator.output_dir.exists()

    def test_generate_changelog_basic(self, changelog_generator, sample_delta_report):
        """Test basic changelog generation"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)

        assert isinstance(changelog, Changelog)
        assert "Infrastructure Changes" in changelog.title
        assert changelog.state_comparison["from_state"] == "20240101_120000"
        assert changelog.state_comparison["to_state"] == "20240101_130000"
        assert changelog.summary.total_changes == 2
        assert len(changelog.sections) > 0

    def test_generate_changelog_with_custom_title(
        self, changelog_generator, sample_delta_report
    ):
        """Test changelog generation with custom title"""
        custom_title = "Custom Infrastructure Changes Report"
        changelog = changelog_generator.generate_changelog(
            sample_delta_report, title=custom_title
        )

        assert changelog.title == custom_title

    def test_convert_delta_to_entries(self, changelog_generator, sample_delta_report):
        """Test conversion of delta report to changelog entries"""
        entries = changelog_generator._convert_delta_to_entries(sample_delta_report)

        assert len(entries) == 2  # 1 added + 1 modified

        # Check that entries are sorted by severity
        assert entries[0].severity in [ChangeSeverity.CRITICAL, ChangeSeverity.HIGH]

        # Verify entry content
        ec2_entry = next((e for e in entries if e.service == "EC2"), None)
        assert ec2_entry is not None
        assert ec2_entry.change_type == ChangeType.MODIFIED
        assert ec2_entry.severity == ChangeSeverity.HIGH
        assert ec2_entry.security_impact is not None

    def test_create_changelog_entry(self, changelog_generator, sample_resource_change):
        """Test creation of individual changelog entry"""
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = changelog_generator._create_changelog_entry(
            sample_resource_change, timestamp
        )

        assert isinstance(entry, ChangelogEntry)
        assert entry.resource_arn == sample_resource_change.resource_arn
        assert entry.service == "EC2"
        assert entry.change_type == ChangeType.MODIFIED
        assert entry.severity == ChangeSeverity.HIGH
        assert entry.category == ChangeCategory.SECURITY
        assert len(entry.change_id) == 12  # MD5 hash truncated to 12 chars
        assert entry.summary is not None
        assert entry.description is not None
        assert entry.impact_assessment is not None

    def test_generate_change_summary(self, changelog_generator, sample_resource_change):
        """Test change summary generation"""
        summary = changelog_generator._generate_change_summary(sample_resource_change)

        assert "Instance" in summary
        assert "EC2" in summary
        assert "modified" in summary.lower()

    def test_generate_change_description(
        self, changelog_generator, sample_resource_change
    ):
        """Test detailed change description generation"""
        description = changelog_generator._generate_change_description(
            sample_resource_change
        )

        assert "Instance" in description
        assert "EC2" in description
        assert "modified" in description
        assert "attribute modification" in description

    def test_determine_primary_category(
        self, changelog_generator, sample_resource_change
    ):
        """Test primary category determination"""
        category = changelog_generator._determine_primary_category(
            sample_resource_change
        )

        assert category == ChangeCategory.SECURITY

    def test_generate_impact_assessment(
        self, changelog_generator, sample_resource_change
    ):
        """Test impact assessment generation"""
        impact = changelog_generator._generate_impact_assessment(sample_resource_change)

        assert "HIGH" in impact
        assert "Security Impact" in impact
        assert "Network Impact" in impact

    def test_collect_technical_details(
        self, changelog_generator, sample_resource_change
    ):
        """Test technical details collection"""
        details = changelog_generator._collect_technical_details(sample_resource_change)

        assert "resource_arn" in details
        assert "attribute_changes_count" in details
        assert "attribute_changes" in details
        assert len(details["attribute_changes"]) == 1

        attr_change = details["attribute_changes"][0]
        assert attr_change["path"] == "security_groups"
        assert attr_change["category"] == "security"
        assert attr_change["severity"] == "high"

    def test_generate_remediation_steps(
        self, changelog_generator, sample_resource_change
    ):
        """Test remediation steps generation"""
        steps = changelog_generator._generate_remediation_steps(sample_resource_change)

        assert len(steps) > 0
        assert any("security group" in step.lower() for step in steps)
        assert any("review" in step.lower() for step in steps)

    def test_generate_summary(self, changelog_generator, sample_delta_report):
        """Test summary statistics generation"""
        entries = changelog_generator._convert_delta_to_entries(sample_delta_report)
        summary = changelog_generator._generate_summary(entries, sample_delta_report)

        assert isinstance(summary, ChangelogSummary)
        assert summary.total_changes == 2
        assert summary.changes_by_type["added"] == 1
        assert summary.changes_by_type["modified"] == 1
        assert "EC2" in summary.changes_by_service
        assert "S3" in summary.changes_by_service
        assert len(summary.most_impacted_services) <= 5

    def test_organize_entries_by_service(
        self, changelog_generator, sample_delta_report
    ):
        """Test organizing entries by service"""
        changelog_generator.group_by_service = True
        entries = changelog_generator._convert_delta_to_entries(sample_delta_report)
        sections = changelog_generator._organize_entries_into_sections(entries)

        assert len(sections) == 2  # EC2 and S3 sections

        service_names = [section.title for section in sections]
        assert any("EC2" in name for name in service_names)
        assert any("S3" in name for name in service_names)

        # Check section statistics
        for section in sections:
            assert section.summary_stats["total_changes"] > 0
            assert "added" in section.summary_stats
            assert "modified" in section.summary_stats
            assert "removed" in section.summary_stats

    def test_organize_entries_by_severity(
        self, changelog_generator, sample_delta_report
    ):
        """Test organizing entries by severity"""
        changelog_generator.group_by_service = False
        entries = changelog_generator._convert_delta_to_entries(sample_delta_report)
        sections = changelog_generator._organize_entries_into_sections(entries)

        assert len(sections) > 0

        # Check that sections are organized by severity
        severity_titles = [section.title for section in sections]
        assert any("Severity" in title for title in severity_titles)

    def test_generate_trend_analysis(self, changelog_generator):
        """Test trend analysis generation"""
        # Create multiple historical reports
        base_time = datetime.now(timezone.utc)
        historical_reports = []

        for i in range(3):
            timestamp = (base_time - timedelta(days=i)).isoformat()
            report = DeltaReport(
                state1_id=f"state_{i}",
                state2_id=f"state_{i+1}",
                timestamp=timestamp,
                summary={"total_changes": 5 + i},
                added_resources=[
                    ResourceChange(
                        resource_arn=f"arn:aws:ec2:us-east-1:123456789012:instance/i-{i}",
                        resource_id=f"i-{i}",
                        service="EC2",
                        resource_type="Instance",
                        region="us-east-1",
                        change_type=ChangeType.ADDED,
                        severity=ChangeSeverity.MEDIUM,
                    )
                ],
                removed_resources=[],
                modified_resources=[],
                unchanged_resources=[],
                compliance_changes={},
                security_changes={},
                network_changes={},
                impact_analysis={},
                change_statistics={},
            )
            historical_reports.append(report)

        trend_analysis = changelog_generator._generate_trend_analysis(
            historical_reports
        )

        assert isinstance(trend_analysis, TrendAnalysis)
        assert trend_analysis.total_periods == 3
        assert trend_analysis.change_velocity > 0
        assert len(trend_analysis.most_active_services) > 0
        assert "EC2" in trend_analysis.most_active_services
        assert len(trend_analysis.recommendations) > 0

    def test_format_changelog_markdown(
        self, changelog_generator, sample_delta_report, temp_output_dir
    ):
        """Test Markdown formatting"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)

        output_file = changelog_generator.format_changelog(
            changelog, ChangelogFormat.MARKDOWN
        )

        assert Path(output_file).exists()
        assert output_file.endswith(".markdown")

        # Check content
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert changelog.title in content
        assert "## Summary" in content
        assert "### Changes by Type" in content
        assert "## Detailed Changes" in content
        assert "EC2" in content
        assert "S3" in content

    def test_format_changelog_html(
        self, changelog_generator, sample_delta_report, temp_output_dir
    ):
        """Test HTML formatting"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)

        output_file = changelog_generator.format_changelog(
            changelog, ChangelogFormat.HTML
        )

        assert Path(output_file).exists()
        assert output_file.endswith(".html")

        # Check content
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "<!DOCTYPE html>" in content
        assert changelog.title in content
        assert "severity-high" in content
        assert "severity-medium" in content

    def test_format_changelog_json(
        self, changelog_generator, sample_delta_report, temp_output_dir
    ):
        """Test JSON formatting"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)

        output_file = changelog_generator.format_changelog(
            changelog, ChangelogFormat.JSON
        )

        assert Path(output_file).exists()
        assert output_file.endswith(".json")

        # Check content
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["title"] == changelog.title
        assert "summary" in data
        assert "sections" in data
        assert len(data["sections"]) > 0

    def test_format_changelog_yaml(
        self, changelog_generator, sample_delta_report, temp_output_dir
    ):
        """Test YAML formatting"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)

        output_file = changelog_generator.format_changelog(
            changelog, ChangelogFormat.YAML
        )

        assert Path(output_file).exists()
        assert output_file.endswith(".yaml")

        # Check content
        with open(output_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["title"] == changelog.title
        assert "summary" in data
        assert "sections" in data

    def test_format_changelog_pdf_fallback(
        self, changelog_generator, sample_delta_report, temp_output_dir
    ):
        """Test PDF formatting (falls back to HTML)"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)

        output_file = changelog_generator.format_changelog(
            changelog, ChangelogFormat.PDF
        )

        # Should create HTML file instead
        assert Path(output_file).exists()
        assert output_file.endswith(".html")

    def test_integrate_into_bom_document(
        self, changelog_generator, sample_delta_report, temp_output_dir
    ):
        """Test BOM document integration"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)
        bom_document_path = Path(temp_output_dir) / "bom_document.xlsx"

        # Create dummy BOM document
        bom_document_path.touch()

        section_file = changelog_generator.integrate_into_bom_document(
            changelog, str(bom_document_path)
        )

        assert Path(section_file).exists()
        assert "changelog_section.md" in section_file

        # Check content
        with open(section_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "# Infrastructure Change Log" in content
        assert "## Change Summary" in content
        assert "| Total Changes |" in content

    def test_generate_bom_section_content(
        self, changelog_generator, sample_delta_report
    ):
        """Test BOM section content generation"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)
        content = changelog_generator._generate_bom_section_content(changelog)

        assert "# Infrastructure Change Log" in content
        assert "## Change Summary" in content
        assert "| Metric | Count |" in content
        assert str(changelog.summary.total_changes) in content

    def test_changelog_with_compliance_changes(self, changelog_generator):
        """Test changelog generation with compliance changes"""
        compliance_change = AttributeChange(
            attribute_path="compliance_status",
            old_value="compliant",
            new_value="non-compliant",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.COMPLIANCE,
            severity=ChangeSeverity.HIGH,
            description="Compliance status changed",
        )

        resource_change = ResourceChange(
            resource_arn="arn:aws:s3:::test-bucket",
            resource_id="test-bucket",
            service="S3",
            resource_type="Bucket",
            region="us-east-1",
            change_type=ChangeType.MODIFIED,
            compliance_changes=[compliance_change],
            severity=ChangeSeverity.HIGH,
        )

        delta_report = DeltaReport(
            state1_id="state1",
            state2_id="state2",
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary={"total_changes": 1},
            added_resources=[],
            removed_resources=[],
            modified_resources=[resource_change],
            unchanged_resources=[],
            compliance_changes={},
            security_changes={},
            network_changes={},
            impact_analysis={},
            change_statistics={},
        )

        changelog = changelog_generator.generate_changelog(delta_report)

        assert changelog.summary.compliance_changes == 1

        # Check that compliance impact is extracted
        entry = changelog.sections[0].entries[0]
        assert entry.compliance_impact is not None
        assert "compliant" in entry.compliance_impact

    def test_changelog_with_trend_analysis(
        self, changelog_generator, sample_delta_report
    ):
        """Test changelog generation with trend analysis"""
        # Create historical reports
        historical_reports = [sample_delta_report]

        changelog = changelog_generator.generate_changelog(
            sample_delta_report,
            include_trend_analysis=True,
            historical_reports=historical_reports,
        )

        assert changelog.trend_analysis is not None
        assert changelog.trend_analysis.change_velocity >= 0
        assert len(changelog.trend_analysis.most_active_services) > 0

    def test_error_handling_invalid_format(
        self, changelog_generator, sample_delta_report
    ):
        """Test error handling for invalid format"""
        changelog = changelog_generator.generate_changelog(sample_delta_report)

        with pytest.raises(ValueError, match="Unsupported format"):
            changelog_generator.format_changelog(changelog, "invalid_format")

    def test_changelog_without_technical_details(
        self, temp_output_dir, sample_delta_report
    ):
        """Test changelog generation without technical details"""
        generator = ChangelogGenerator(
            output_dir=temp_output_dir,
            include_technical_details=False,
            include_remediation_steps=False,
        )

        changelog = generator.generate_changelog(sample_delta_report)

        # Check that technical details are minimal
        entry = changelog.sections[0].entries[0]
        assert len(entry.technical_details) == 0
        assert len(entry.remediation_steps) == 0

    def test_changelog_entry_uniqueness(self, changelog_generator, sample_delta_report):
        """Test that changelog entries have unique IDs"""
        entries = changelog_generator._convert_delta_to_entries(sample_delta_report)

        change_ids = [entry.change_id for entry in entries]
        assert len(change_ids) == len(set(change_ids))  # All IDs should be unique

    def test_severity_ordering(self, changelog_generator, sample_delta_report):
        """Test that entries are properly ordered by severity"""
        # Add a critical change to the delta report
        critical_change = ResourceChange(
            resource_arn="arn:aws:iam::123456789012:role/critical-role",
            resource_id="critical-role",
            service="IAM",
            resource_type="Role",
            region="us-east-1",
            change_type=ChangeType.REMOVED,
            severity=ChangeSeverity.CRITICAL,
        )

        sample_delta_report.removed_resources.append(critical_change)

        entries = changelog_generator._convert_delta_to_entries(sample_delta_report)

        # Critical should come first
        assert entries[0].severity == ChangeSeverity.CRITICAL

        # Verify ordering
        severity_order = [
            ChangeSeverity.CRITICAL,
            ChangeSeverity.HIGH,
            ChangeSeverity.MEDIUM,
            ChangeSeverity.LOW,
            ChangeSeverity.INFO,
        ]
        prev_severity_index = -1

        for entry in entries:
            current_severity_index = severity_order.index(entry.severity)
            assert current_severity_index >= prev_severity_index
            prev_severity_index = current_severity_index


class TestChangelogIntegration:
    """Integration tests for changelog generation workflow"""

    def test_end_to_end_changelog_generation(self, tmp_path):
        """Test complete changelog generation workflow"""
        output_dir = tmp_path / "changelogs"
        generator = ChangelogGenerator(output_dir=str(output_dir))

        # Create comprehensive delta report
        delta_report = DeltaReport(
            state1_id="20240101_120000",
            state2_id="20240101_130000",
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary={"total_changes": 3},
            added_resources=[
                ResourceChange(
                    resource_arn="arn:aws:s3:::new-bucket",
                    resource_id="new-bucket",
                    service="S3",
                    resource_type="Bucket",
                    region="us-east-1",
                    change_type=ChangeType.ADDED,
                    severity=ChangeSeverity.MEDIUM,
                )
            ],
            removed_resources=[
                ResourceChange(
                    resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-removed",
                    resource_id="i-removed",
                    service="EC2",
                    resource_type="Instance",
                    region="us-east-1",
                    change_type=ChangeType.REMOVED,
                    severity=ChangeSeverity.HIGH,
                )
            ],
            modified_resources=[
                ResourceChange(
                    resource_arn="arn:aws:rds:us-east-1:123456789012:db:modified-db",
                    resource_id="modified-db",
                    service="RDS",
                    resource_type="DBInstance",
                    region="us-east-1",
                    change_type=ChangeType.MODIFIED,
                    attribute_changes=[
                        AttributeChange(
                            attribute_path="encryption",
                            old_value=False,
                            new_value=True,
                            change_type=ChangeType.MODIFIED,
                            category=ChangeCategory.SECURITY,
                            severity=ChangeSeverity.HIGH,
                            description="Encryption enabled",
                        )
                    ],
                    severity=ChangeSeverity.HIGH,
                )
            ],
            unchanged_resources=[],
            compliance_changes={},
            security_changes={},
            network_changes={},
            impact_analysis={},
            change_statistics={},
        )

        # Generate changelog
        changelog = generator.generate_changelog(
            delta_report, title="Test Infrastructure Changes"
        )

        # Verify changelog structure
        assert changelog.title == "Test Infrastructure Changes"
        assert changelog.summary.total_changes == 3
        assert len(changelog.sections) == 3  # S3, EC2, RDS sections

        # Generate all formats
        formats = [
            ChangelogFormat.MARKDOWN,
            ChangelogFormat.HTML,
            ChangelogFormat.JSON,
            ChangelogFormat.YAML,
        ]
        generated_files = []

        for format_type in formats:
            output_file = generator.format_changelog(changelog, format_type)
            generated_files.append(output_file)
            assert Path(output_file).exists()

        # Verify all files were created
        assert len(generated_files) == 4

        # Test BOM integration
        bom_path = tmp_path / "test_bom.xlsx"
        bom_path.touch()

        section_file = generator.integrate_into_bom_document(changelog, str(bom_path))
        assert Path(section_file).exists()

        # Verify section content
        with open(section_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Infrastructure Change Log" in content
        assert "3" in content  # Total changes count
