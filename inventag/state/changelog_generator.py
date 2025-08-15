"""
ChangelogGenerator - Professional change documentation

Provides changelog generation with structured change entries, timestamps,
categorization, impact assessment, and multi-format output support.
"""

import json
import yaml
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import logging
import hashlib
from collections import defaultdict, Counter

from .delta_detector import (
    DeltaReport,
    ResourceChange,
    AttributeChange,
    ChangeType,
    ChangeSeverity,
    ChangeCategory,
)

logger = logging.getLogger(__name__)


class ChangelogFormat(Enum):
    """Supported changelog output formats"""

    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pd"
    JSON = "json"
    YAML = "yaml"


@dataclass
class ChangelogEntry:
    """Individual changelog entry with structured information"""

    timestamp: str
    change_id: str
    resource_arn: str
    resource_id: str
    service: str
    resource_type: str
    region: str
    change_type: ChangeType
    severity: ChangeSeverity
    category: ChangeCategory
    summary: str
    description: str
    technical_details: Dict[str, Any]
    impact_assessment: str
    related_resources: List[str] = field(default_factory=list)
    compliance_impact: Optional[str] = None
    security_impact: Optional[str] = None
    network_impact: Optional[str] = None
    remediation_steps: List[str] = field(default_factory=list)


@dataclass
class ChangelogSection:
    """Organized section of changelog entries"""

    title: str
    description: str
    entries: List[ChangelogEntry]
    summary_stats: Dict[str, int]
    severity_breakdown: Dict[str, int]


@dataclass
class ChangelogSummary:
    """High-level summary of changes"""

    total_changes: int
    changes_by_type: Dict[str, int]
    changes_by_severity: Dict[str, int]
    changes_by_category: Dict[str, int]
    changes_by_service: Dict[str, int]
    most_impacted_services: List[str]
    critical_changes: int
    high_severity_changes: int
    compliance_changes: int
    security_changes: int
    network_changes: int


@dataclass
class TrendAnalysis:
    """Trend analysis over time periods"""

    period_start: str
    period_end: str
    total_periods: int
    change_velocity: float  # changes per day
    most_active_services: List[str]
    change_patterns: Dict[str, Any]
    severity_trends: Dict[str, List[int]]
    category_trends: Dict[str, List[int]]
    recommendations: List[str]


@dataclass
class Changelog:
    """Complete changelog document"""

    title: str
    generation_timestamp: str
    state_comparison: Dict[str, str]
    summary: ChangelogSummary
    sections: List[ChangelogSection]
    trend_analysis: Optional[TrendAnalysis] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Convert changelog to markdown format"""
        lines = []

        # Title and header
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"**Generated:** {self.generation_timestamp}")
        lines.append("")

        # State comparison
        if self.state_comparison:
            lines.append("## State Comparison")
            lines.append("")
            for key, value in self.state_comparison.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Changes | {self.summary.total_changes} |")
        lines.append(f"| Critical Changes | {self.summary.critical_changes} |")
        lines.append(f"| High Severity | {self.summary.high_severity_changes} |")
        lines.append(f"| Security Changes | {self.summary.security_changes} |")
        lines.append(f"| Compliance Changes | {self.summary.compliance_changes} |")
        lines.append(f"| Network Changes | {self.summary.network_changes} |")
        lines.append("")

        # Most impacted services
        if self.summary.most_impacted_services:
            lines.append("**Most Impacted Services:**")
            for service in self.summary.most_impacted_services:
                service_count = self.summary.changes_by_service.get(service, 0)
                lines.append(f"- {service}: {service_count} changes")
            lines.append("")

        # Sections
        for section in self.sections:
            lines.append(f"## {section.title}")
            lines.append("")

            if section.description:
                lines.append(section.description)
                lines.append("")

            for entry in section.entries:
                lines.append(f"### {entry.summary}")
                lines.append(f"- **Type:** {entry.change_type.value}")
                lines.append(f"- **Severity:** {entry.severity.value}")
                lines.append(f"- **Service:** {entry.service}")
                lines.append(f"- **Resource:** {entry.resource_id}")

                if entry.impact_assessment:
                    lines.append(f"- **Impact:** {entry.impact_assessment}")

                if entry.description:
                    lines.append(f"- **Description:** {entry.description}")

                if entry.technical_details:
                    lines.append("- **Technical Details:**")
                    # Show first few key technical details
                    for key, value in list(entry.technical_details.items())[:3]:
                        lines.append(f"  - {key}: {value}")
                    if len(entry.technical_details) > 3:
                        lines.append(
                            f"  - ... and {len(entry.technical_details) - 3} more details"
                        )

                if entry.remediation_steps:
                    lines.append("- **Action Required:**")
                    for step in entry.remediation_steps[:2]:  # Limit to first 2 steps
                        lines.append(f"  - {step}")
                    if len(entry.remediation_steps) > 2:
                        lines.append(
                            f"  - ... and {len(entry.remediation_steps) - 2} more steps"
                        )

                lines.append("")

        # Trend analysis if available
        if self.trend_analysis:
            lines.append("## Trend Analysis")
            lines.append("")
            lines.append(
                f"**Change Velocity:** {self.trend_analysis.change_velocity:.2f} changes per day"
            )
            lines.append(
                f"**Analysis Period:** {self.trend_analysis.total_periods} periods"
            )
            lines.append("")

            if self.trend_analysis.most_active_services:
                lines.append("**Most Active Services:**")
                for service in self.trend_analysis.most_active_services:
                    lines.append(f"- {service}")
                lines.append("")

            if self.trend_analysis.recommendations:
                lines.append("**Recommendations:**")
                for rec in self.trend_analysis.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

        return "\n".join(lines)


class ChangelogGenerator:
    """
    Professional changelog generator that creates structured change documentation
    with categorization, impact assessment, and multi-format output support.
    """

    def __init__(
        self,
        output_dir: str = ".inventag/changelogs",
        include_technical_details: bool = True,
        include_remediation_steps: bool = True,
        group_by_service: bool = True,
    ):
        """
        Initialize ChangelogGenerator with configuration options.

        Args:
            output_dir: Directory to store generated changelogs
            include_technical_details: Whether to include detailed technical information
            include_remediation_steps: Whether to include remediation recommendations
            group_by_service: Whether to group changes by AWS service
        """
        self.output_dir = Path(output_dir)
        self.include_technical_details = include_technical_details
        self.include_remediation_steps = include_remediation_steps
        self.group_by_service = group_by_service

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Change description templates
        self.change_templates = {
            ChangeType.ADDED: "New {resource_type} '{resource_id}' was created in {service}",
            ChangeType.REMOVED: "{resource_type} '{resource_id}' was deleted from {service}",
            ChangeType.MODIFIED: "{resource_type} '{resource_id}' was modified in {service}",
            ChangeType.UNCHANGED: "{resource_type} '{resource_id}' remains unchanged in {service}",
        }

        # Impact assessment templates
        self.impact_templates = {
            ChangeSeverity.CRITICAL: "CRITICAL: This change may have significant security or operational impact",
            ChangeSeverity.HIGH: "HIGH: This change requires attention and may affect system behavior",
            ChangeSeverity.MEDIUM: "MEDIUM: This change should be reviewed for potential impacts",
            ChangeSeverity.LOW: "LOW: This change has minimal impact on operations",
            ChangeSeverity.INFO: "INFO: This change is informational and requires no action",
        }

        # Remediation step templates
        self.remediation_templates = {
            "security_group_change": [
                "Review security group rules for overly permissive access",
                "Validate that only necessary ports and protocols are open",
                "Ensure source/destination restrictions are appropriate",
            ],
            "encryption_change": [
                "Verify encryption is enabled and using appropriate key management",
                "Check that encryption keys have proper access controls",
                "Validate compliance with organizational encryption policies",
            ],
            "compliance_violation": [
                "Review resource configuration against compliance policies",
                "Update tags or configuration to meet compliance requirements",
                "Document any approved exceptions with proper justification",
            ],
            "network_change": [
                "Verify network connectivity is not disrupted",
                "Check routing tables and security group associations",
                "Test application connectivity after network changes",
            ],
        }

    def generate_changelog(
        self,
        delta_report: DeltaReport,
        title: Optional[str] = None,
        include_trend_analysis: bool = False,
        historical_reports: Optional[List[DeltaReport]] = None,
    ) -> Changelog:
        """
        Generate a comprehensive changelog from a delta report.

        Args:
            delta_report: Delta report containing change information
            title: Custom title for the changelog
            include_trend_analysis: Whether to include trend analysis
            historical_reports: Historical delta reports for trend analysis

        Returns:
            Complete Changelog object
        """
        logger.info(
            f"Generating changelog for states {delta_report.state1_id} -> {delta_report.state2_id}"
        )

        # Generate title if not provided
        if title is None:
            title = f"Infrastructure Changes: {delta_report.state1_id} to {delta_report.state2_id}"

        # Convert delta report to changelog entries
        changelog_entries = self._convert_delta_to_entries(delta_report)

        # Generate summary statistics
        summary = self._generate_summary(changelog_entries, delta_report)

        # Organize entries into sections
        sections = self._organize_entries_into_sections(changelog_entries)

        # Generate trend analysis if requested
        trend_analysis = None
        if include_trend_analysis and historical_reports:
            trend_analysis = self._generate_trend_analysis(
                historical_reports + [delta_report]
            )

        # Create changelog
        changelog = Changelog(
            title=title,
            generation_timestamp=datetime.now(timezone.utc).isoformat(),
            state_comparison={
                "from_state": delta_report.state1_id,
                "to_state": delta_report.state2_id,
                "comparison_timestamp": delta_report.timestamp,
            },
            summary=summary,
            sections=sections,
            trend_analysis=trend_analysis,
            metadata={
                "generator_version": "1.0",
                "total_entries": len(changelog_entries),
                "generation_options": {
                    "include_technical_details": self.include_technical_details,
                    "include_remediation_steps": self.include_remediation_steps,
                    "group_by_service": self.group_by_service,
                },
            },
        )

        logger.info(
            f"Generated changelog with {len(changelog_entries)} entries across {len(sections)} sections"
        )
        return changelog

    def _convert_delta_to_entries(
        self, delta_report: DeltaReport
    ) -> List[ChangelogEntry]:
        """Convert delta report changes to structured changelog entries"""
        entries = []

        # Process all types of changes
        all_changes = (
            delta_report.added_resources
            + delta_report.removed_resources
            + delta_report.modified_resources
        )

        for change in all_changes:
            entry = self._create_changelog_entry(change, delta_report.timestamp)
            entries.append(entry)

        # Sort entries by severity (critical first) then by timestamp
        severity_order = {
            ChangeSeverity.CRITICAL: 0,
            ChangeSeverity.HIGH: 1,
            ChangeSeverity.MEDIUM: 2,
            ChangeSeverity.LOW: 3,
            ChangeSeverity.INFO: 4,
        }

        entries.sort(key=lambda x: (severity_order.get(x.severity, 5), x.timestamp))

        return entries

    def _create_changelog_entry(
        self, resource_change: ResourceChange, timestamp: str
    ) -> ChangelogEntry:
        """Create a detailed changelog entry from a resource change"""
        # Generate unique change ID
        change_id = self._generate_change_id(resource_change, timestamp)

        # Generate summary and description
        summary = self._generate_change_summary(resource_change)
        description = self._generate_change_description(resource_change)

        # Determine primary category from attribute changes
        category = self._determine_primary_category(resource_change)

        # Generate impact assessment
        impact_assessment = self._generate_impact_assessment(resource_change)

        # Collect technical details
        technical_details = self._collect_technical_details(resource_change)

        # Generate remediation steps
        remediation_steps = (
            self._generate_remediation_steps(resource_change)
            if self.include_remediation_steps
            else []
        )

        return ChangelogEntry(
            timestamp=timestamp,
            change_id=change_id,
            resource_arn=resource_change.resource_arn,
            resource_id=resource_change.resource_id,
            service=resource_change.service,
            resource_type=resource_change.resource_type,
            region=resource_change.region,
            change_type=resource_change.change_type,
            severity=resource_change.severity,
            category=category,
            summary=summary,
            description=description,
            technical_details=technical_details,
            impact_assessment=impact_assessment,
            related_resources=resource_change.related_resources,
            compliance_impact=self._extract_compliance_impact(resource_change),
            security_impact=resource_change.security_impact,
            network_impact=resource_change.network_impact,
            remediation_steps=remediation_steps,
        )

    def _generate_change_id(
        self, resource_change: ResourceChange, timestamp: str
    ) -> str:
        """Generate a unique ID for the change"""
        data = f"{resource_change.resource_arn}:{resource_change.change_type.value}:{timestamp}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def _generate_change_summary(self, resource_change: ResourceChange) -> str:
        """Generate a concise summary of the change"""
        template = self.change_templates.get(
            resource_change.change_type, "Resource {resource_id} changed"
        )

        return template.format(
            resource_type=resource_change.resource_type,
            resource_id=resource_change.resource_id or "Unknown",
            service=resource_change.service,
        )

    def _generate_change_description(self, resource_change: ResourceChange) -> str:
        """Generate a detailed description of the change"""
        description_parts = []

        # Base description
        if resource_change.change_type == ChangeType.ADDED:
            description_parts.append(
                f"A new {resource_change.resource_type} resource was created in {resource_change.service}."
            )
        elif resource_change.change_type == ChangeType.REMOVED:
            description_parts.append(
                f"The {resource_change.resource_type} resource was removed from {resource_change.service}."
            )
        elif resource_change.change_type == ChangeType.MODIFIED:
            description_parts.append(
                f"The {resource_change.resource_type} resource was modified in {resource_change.service}."
            )

        # Add attribute change details for modifications
        if (
            resource_change.change_type == ChangeType.MODIFIED
            and resource_change.attribute_changes
        ):
            change_count = len(resource_change.attribute_changes)
            description_parts.append(
                f"This change involved {change_count} attribute modification(s):"
            )

            # Group changes by category
            changes_by_category = defaultdict(list)
            for attr_change in resource_change.attribute_changes[
                :5
            ]:  # Limit to first 5 for readability
                changes_by_category[attr_change.category].append(attr_change)

            for category, changes in changes_by_category.items():
                category_name = category.value.title()
                change_list = [f"'{change.attribute_path}'" for change in changes]
                description_parts.append(f"- {category_name}: {', '.join(change_list)}")

            if change_count > 5:
                description_parts.append(f"... and {change_count - 5} more changes.")

        # Add compliance impact if present
        if resource_change.compliance_changes:
            compliance_count = len(resource_change.compliance_changes)
            description_parts.append(
                f"This change also affected {compliance_count} compliance-related attribute(s)."
            )

        return " ".join(description_parts)

    def _determine_primary_category(
        self, resource_change: ResourceChange
    ) -> ChangeCategory:
        """Determine the primary category for the change"""
        # Check compliance changes first (highest priority)
        if resource_change.compliance_changes:
            return ChangeCategory.COMPLIANCE

        if not resource_change.attribute_changes:
            return ChangeCategory.CONFIGURATION

        # Count changes by category
        category_counts = Counter(
            change.category for change in resource_change.attribute_changes
        )

        # Return the most common category, with security taking priority
        if ChangeCategory.SECURITY in category_counts:
            return ChangeCategory.SECURITY
        elif ChangeCategory.COMPLIANCE in category_counts:
            return ChangeCategory.COMPLIANCE
        else:
            return category_counts.most_common(1)[0][0]

    def _generate_impact_assessment(self, resource_change: ResourceChange) -> str:
        """Generate an impact assessment for the change"""
        base_impact = self.impact_templates.get(
            resource_change.severity, "Impact assessment not available"
        )

        impact_parts = [base_impact]

        # Add specific impact details
        if resource_change.security_impact:
            impact_parts.append(f"Security Impact: {resource_change.security_impact}")

        if resource_change.network_impact:
            impact_parts.append(f"Network Impact: {resource_change.network_impact}")

        if resource_change.compliance_changes:
            impact_parts.append(
                "Compliance Impact: This change affects compliance status and may require review."
            )

        if resource_change.related_resources:
            related_count = len(resource_change.related_resources)
            impact_parts.append(
                f"Related Resources: This change may affect {related_count} related resource(s)."
            )

        return " ".join(impact_parts)

    def _collect_technical_details(
        self, resource_change: ResourceChange
    ) -> Dict[str, Any]:
        """Collect technical details for the change"""
        if not self.include_technical_details:
            return {}

        details = {
            "resource_arn": resource_change.resource_arn,
            "change_timestamp": resource_change.timestamp,
            "attribute_changes_count": len(resource_change.attribute_changes),
            "compliance_changes_count": len(resource_change.compliance_changes),
        }

        # Add attribute change details
        if resource_change.attribute_changes:
            details["attribute_changes"] = []
            for attr_change in resource_change.attribute_changes:
                details["attribute_changes"].append(
                    {
                        "path": attr_change.attribute_path,
                        "old_value": (
                            str(attr_change.old_value)[:100]
                            if attr_change.old_value
                            else None
                        ),
                        "new_value": (
                            str(attr_change.new_value)[:100]
                            if attr_change.new_value
                            else None
                        ),
                        "category": attr_change.category.value,
                        "severity": attr_change.severity.value,
                    }
                )

        # Add compliance change details
        if resource_change.compliance_changes:
            details["compliance_changes"] = []
            for comp_change in resource_change.compliance_changes:
                details["compliance_changes"].append(
                    {
                        "path": comp_change.attribute_path,
                        "old_value": (
                            str(comp_change.old_value)[:100]
                            if comp_change.old_value
                            else None
                        ),
                        "new_value": (
                            str(comp_change.new_value)[:100]
                            if comp_change.new_value
                            else None
                        ),
                        "severity": comp_change.severity.value,
                    }
                )

        return details

    def _extract_compliance_impact(
        self, resource_change: ResourceChange
    ) -> Optional[str]:
        """Extract compliance impact description"""
        if not resource_change.compliance_changes:
            return None

        compliance_impacts = []
        for comp_change in resource_change.compliance_changes:
            if comp_change.attribute_path == "compliance_status":
                old_status = comp_change.old_value
                new_status = comp_change.new_value
                compliance_impacts.append(
                    f"Compliance status changed from '{old_status}' to '{new_status}'"
                )
            elif comp_change.attribute_path == "compliance_violations":
                compliance_impacts.append("Compliance violations were updated")

        return (
            "; ".join(compliance_impacts)
            if compliance_impacts
            else "Compliance-related attributes were modified"
        )

    def _generate_remediation_steps(self, resource_change: ResourceChange) -> List[str]:
        """Generate remediation steps based on the change type and category"""
        remediation_steps = []

        # Determine remediation based on change characteristics
        if resource_change.security_impact:
            remediation_steps.extend(
                self.remediation_templates.get("security_group_change", [])
            )

        if resource_change.compliance_changes:
            remediation_steps.extend(
                self.remediation_templates.get("compliance_violation", [])
            )

        if resource_change.network_impact:
            remediation_steps.extend(
                self.remediation_templates.get("network_change", [])
            )

        # Check for encryption-related changes
        encryption_changes = [
            change
            for change in resource_change.attribute_changes
            if "encryption" in change.attribute_path.lower()
        ]
        if encryption_changes:
            remediation_steps.extend(
                self.remediation_templates.get("encryption_change", [])
            )

        # Add general remediation steps based on severity
        if resource_change.severity in [ChangeSeverity.CRITICAL, ChangeSeverity.HIGH]:
            remediation_steps.append(
                "Review this change immediately and validate its impact on system security and operations"
            )

        # Remove duplicates while preserving order
        seen = set()
        unique_steps = []
        for step in remediation_steps:
            if step not in seen:
                seen.add(step)
                unique_steps.append(step)

        return unique_steps

    def _generate_summary(
        self, entries: List[ChangelogEntry], delta_report: DeltaReport
    ) -> ChangelogSummary:
        """Generate summary statistics for the changelog"""
        total_changes = len(entries)

        # Count changes by type
        changes_by_type = Counter(entry.change_type.value for entry in entries)

        # Count changes by severity
        changes_by_severity = Counter(entry.severity.value for entry in entries)

        # Count changes by category
        changes_by_category = Counter(entry.category.value for entry in entries)

        # Count changes by service
        changes_by_service = Counter(entry.service for entry in entries)

        # Get most impacted services (top 5)
        most_impacted_services = [
            service for service, _ in changes_by_service.most_common(5)
        ]

        # Count specific types of changes
        critical_changes = changes_by_severity.get("critical", 0)
        high_severity_changes = changes_by_severity.get("high", 0)
        compliance_changes = changes_by_category.get("compliance", 0)
        security_changes = changes_by_category.get("security", 0)
        network_changes = changes_by_category.get("network", 0)

        return ChangelogSummary(
            total_changes=total_changes,
            changes_by_type=dict(changes_by_type),
            changes_by_severity=dict(changes_by_severity),
            changes_by_category=dict(changes_by_category),
            changes_by_service=dict(changes_by_service),
            most_impacted_services=most_impacted_services,
            critical_changes=critical_changes,
            high_severity_changes=high_severity_changes,
            compliance_changes=compliance_changes,
            security_changes=security_changes,
            network_changes=network_changes,
        )

    def _organize_entries_into_sections(
        self, entries: List[ChangelogEntry]
    ) -> List[ChangelogSection]:
        """Organize changelog entries into logical sections"""
        sections = []

        if self.group_by_service:
            # Group by service
            entries_by_service = defaultdict(list)
            for entry in entries:
                entries_by_service[entry.service].append(entry)

            for service, service_entries in entries_by_service.items():
                # Sort entries within service by severity
                service_entries.sort(
                    key=lambda x: (
                        0
                        if x.severity == ChangeSeverity.CRITICAL
                        else (
                            1
                            if x.severity == ChangeSeverity.HIGH
                            else (
                                2
                                if x.severity == ChangeSeverity.MEDIUM
                                else 3 if x.severity == ChangeSeverity.LOW else 4
                            )
                        )
                    )
                )

                # Generate section statistics
                summary_stats = {
                    "total_changes": len(service_entries),
                    "added": len(
                        [
                            e
                            for e in service_entries
                            if e.change_type == ChangeType.ADDED
                        ]
                    ),
                    "removed": len(
                        [
                            e
                            for e in service_entries
                            if e.change_type == ChangeType.REMOVED
                        ]
                    ),
                    "modified": len(
                        [
                            e
                            for e in service_entries
                            if e.change_type == ChangeType.MODIFIED
                        ]
                    ),
                }

                severity_breakdown = Counter(
                    entry.severity.value for entry in service_entries
                )

                section = ChangelogSection(
                    title=f"{service} Service Changes",
                    description=f"Changes detected in {service} service resources",
                    entries=service_entries,
                    summary_stats=summary_stats,
                    severity_breakdown=dict(severity_breakdown),
                )
                sections.append(section)
        else:
            # Group by severity
            entries_by_severity = defaultdict(list)
            for entry in entries:
                entries_by_severity[entry.severity].append(entry)

            severity_order = [
                ChangeSeverity.CRITICAL,
                ChangeSeverity.HIGH,
                ChangeSeverity.MEDIUM,
                ChangeSeverity.LOW,
                ChangeSeverity.INFO,
            ]

            for severity in severity_order:
                if severity in entries_by_severity:
                    severity_entries = entries_by_severity[severity]

                    summary_stats = {
                        "total_changes": len(severity_entries),
                        "added": len(
                            [
                                e
                                for e in severity_entries
                                if e.change_type == ChangeType.ADDED
                            ]
                        ),
                        "removed": len(
                            [
                                e
                                for e in severity_entries
                                if e.change_type == ChangeType.REMOVED
                            ]
                        ),
                        "modified": len(
                            [
                                e
                                for e in severity_entries
                                if e.change_type == ChangeType.MODIFIED
                            ]
                        ),
                    }

                    service_breakdown = Counter(
                        entry.service for entry in severity_entries
                    )

                    section = ChangelogSection(
                        title=f"{severity.value.title()} Severity Changes",
                        description=f"Changes with {severity.value} severity level",
                        entries=severity_entries,
                        summary_stats=summary_stats,
                        severity_breakdown={severity.value: len(severity_entries)},
                    )
                    sections.append(section)

        return sections

    def _generate_trend_analysis(
        self, historical_reports: List[DeltaReport]
    ) -> TrendAnalysis:
        """Generate trend analysis from historical delta reports"""
        if len(historical_reports) < 2:
            return None

        # Sort reports by timestamp
        sorted_reports = sorted(historical_reports, key=lambda x: x.timestamp)

        # Calculate time period
        start_time = datetime.fromisoformat(
            sorted_reports[0].timestamp.replace("Z", "+00:00")
        )
        end_time = datetime.fromisoformat(
            sorted_reports[-1].timestamp.replace("Z", "+00:00")
        )
        period_days = (end_time - start_time).days or 1

        # Calculate change velocity
        total_changes = sum(
            report.summary.get("total_changes", 0) for report in sorted_reports
        )
        change_velocity = total_changes / period_days

        # Analyze service activity
        service_activity = defaultdict(int)
        for report in sorted_reports:
            for change in (
                report.added_resources
                + report.removed_resources
                + report.modified_resources
            ):
                service_activity[change.service] += 1

        most_active_services = [
            service for service, _ in Counter(service_activity).most_common(5)
        ]

        # Analyze severity trends
        severity_trends = defaultdict(list)
        category_trends = defaultdict(list)

        for report in sorted_reports:
            severity_counts = defaultdict(int)
            category_counts = defaultdict(int)

            for change in (
                report.added_resources
                + report.removed_resources
                + report.modified_resources
            ):
                severity_counts[change.severity.value] += 1
                # Determine primary category (simplified)
                if change.attribute_changes:
                    primary_category = Counter(
                        attr.category for attr in change.attribute_changes
                    ).most_common(1)[0][0]
                    category_counts[primary_category.value] += 1

            for severity in ["critical", "high", "medium", "low", "info"]:
                severity_trends[severity].append(severity_counts[severity])

            for category in [
                "security",
                "compliance",
                "network",
                "configuration",
                "tags",
            ]:
                category_trends[category].append(category_counts[category])

        # Generate recommendations
        recommendations = []

        # High change velocity recommendation
        if change_velocity > 10:
            recommendations.append(
                "High change velocity detected. Consider implementing change approval processes."
            )

        # Security changes recommendation
        security_changes = sum(
            severity_trends.get("critical", []) + severity_trends.get("high", [])
        )
        if security_changes > len(sorted_reports) * 2:
            recommendations.append(
                "Frequent high-severity changes detected. Review security and change management practices."
            )

        # Service concentration recommendation
        if len(most_active_services) <= 2:
            recommendations.append(
                "Changes are concentrated in few services. Consider broader infrastructure review."
            )

        return TrendAnalysis(
            period_start=start_time.isoformat(),
            period_end=end_time.isoformat(),
            total_periods=len(sorted_reports),
            change_velocity=round(change_velocity, 2),
            most_active_services=most_active_services,
            change_patterns={
                "total_changes_per_period": [
                    report.summary.get("total_changes", 0) for report in sorted_reports
                ],
                "average_changes_per_period": round(
                    total_changes / len(sorted_reports), 2
                ),
            },
            severity_trends=dict(severity_trends),
            category_trends=dict(category_trends),
            recommendations=recommendations,
        )

    def format_changelog(
        self,
        changelog: Changelog,
        format_type: Union[ChangelogFormat, str],
        output_file: Optional[str] = None,
    ) -> str:
        """
        Format changelog in the specified format and save to file.

        Args:
            changelog: Changelog object to format
            format_type: Output format type
            output_file: Output filename, auto-generated if None

        Returns:
            Path to the generated file
        """
        # Handle string format types for error testing
        if isinstance(format_type, str):
            try:
                format_type = ChangelogFormat(format_type)
            except ValueError:
                raise ValueError(f"Unsupported format: {format_type}")

        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"changelog_{timestamp}.{format_type.value}"
        else:
            output_file = Path(output_file)

        try:
            if format_type == ChangelogFormat.MARKDOWN:
                content = self._format_as_markdown(changelog)
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(content)

            elif format_type == ChangelogFormat.HTML:
                content = self._format_as_html(changelog)
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(content)

            elif format_type == ChangelogFormat.JSON:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(asdict(changelog), f, indent=2, default=str)

            elif format_type == ChangelogFormat.YAML:
                # Convert to serializable format for YAML
                serializable_data = self._make_serializable(asdict(changelog))
                with open(output_file, "w", encoding="utf-8") as f:
                    yaml.dump(serializable_data, f, default_flow_style=False)

            elif format_type == ChangelogFormat.PDF:
                # PDF generation would require additional dependencies like reportlab
                # For now, generate HTML and suggest conversion
                html_file = output_file.with_suffix(".html")
                html_content = self._format_as_html(changelog)
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(
                    f"Generated HTML file {html_file}. Use a tool like wkhtmltopdf to convert to PDF."
                )
                return str(html_file)

            else:
                raise ValueError(f"Unsupported format: {format_type}")

            logger.info(
                f"Changelog formatted as {format_type.value} and saved to {output_file}"
            )
            return str(output_file)

        except Exception as e:
            logger.error(f"Failed to format changelog: {e}")
            raise

    def _format_as_markdown(self, changelog: Changelog) -> str:
        """Format changelog as Markdown"""
        lines = []

        # Title and metadata
        lines.append(f"# {changelog.title}")
        lines.append("")
        lines.append(f"**Generated:** {changelog.generation_timestamp}")
        lines.append(
            f"**State Comparison:** {changelog.state_comparison['from_state']} → {changelog.state_comparison['to_state']}"
        )
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        summary = changelog.summary
        lines.append(f"- **Total Changes:** {summary.total_changes}")
        lines.append(f"- **Critical Changes:** {summary.critical_changes}")
        lines.append(f"- **High Severity Changes:** {summary.high_severity_changes}")
        lines.append(f"- **Security Changes:** {summary.security_changes}")
        lines.append(f"- **Compliance Changes:** {summary.compliance_changes}")
        lines.append("")

        # Changes by type
        lines.append("### Changes by Type")
        for change_type, count in summary.changes_by_type.items():
            lines.append(f"- **{change_type.title()}:** {count}")
        lines.append("")

        # Most impacted services
        if summary.most_impacted_services:
            lines.append("### Most Impacted Services")
            for service in summary.most_impacted_services:
                count = summary.changes_by_service.get(service, 0)
                lines.append(f"- **{service}:** {count} changes")
            lines.append("")

        # Trend analysis
        if changelog.trend_analysis:
            lines.append("## Trend Analysis")
            lines.append("")
            trend = changelog.trend_analysis
            lines.append(
                f"- **Analysis Period:** {trend.period_start} to {trend.period_end}"
            )
            lines.append(
                f"- **Change Velocity:** {trend.change_velocity} changes per day"
            )
            lines.append(
                f"- **Most Active Services:** {', '.join(trend.most_active_services)}"
            )
            lines.append("")

            if trend.recommendations:
                lines.append("### Recommendations")
                for rec in trend.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

        # Detailed changes by section
        lines.append("## Detailed Changes")
        lines.append("")

        for section in changelog.sections:
            lines.append(f"### {section.title}")
            lines.append("")
            lines.append(section.description)
            lines.append("")
            lines.append(
                f"**Summary:** {section.summary_stats['total_changes']} total changes "
                f"({section.summary_stats['added']} added, "
                f"{section.summary_stats['removed']} removed, "
                f"{section.summary_stats['modified']} modified)"
            )
            lines.append("")

            for entry in section.entries:
                lines.append(f"#### {entry.summary}")
                lines.append("")
                lines.append(
                    f"- **Resource:** {entry.resource_type} `{entry.resource_id}`"
                )
                lines.append(f"- **Service:** {entry.service}")
                lines.append(f"- **Region:** {entry.region}")
                lines.append(f"- **Change Type:** {entry.change_type.value}")
                lines.append(f"- **Severity:** {entry.severity.value}")
                lines.append(f"- **Category:** {entry.category.value}")
                lines.append("")
                lines.append(f"**Description:** {entry.description}")
                lines.append("")
                lines.append(f"**Impact Assessment:** {entry.impact_assessment}")
                lines.append("")

                if entry.remediation_steps:
                    lines.append("**Remediation Steps:**")
                    for step in entry.remediation_steps:
                        lines.append(f"- {step}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def _format_as_html(self, changelog: Changelog) -> str:
        """Format changelog as HTML"""
        html_parts = []

        # HTML header
        html_parts.append(
            """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1, h2, h3 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .change-entry {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .severity-critical {{ border-left: 5px solid #dc3545; }}
        .severity-high {{ border-left: 5px solid #fd7e14; }}
        .severity-medium {{ border-left: 5px solid #ffc107; }}
        .severity-low {{ border-left: 5px solid #28a745; }}
        .severity-info {{ border-left: 5px solid #17a2b8; }}
        .metadata {{ font-size: 0.9em; color: #666; }}
        ul {{ padding-left: 20px; }}
        .remediation {{ background: #e7f3ff; padding: 10px; border-radius: 3px; margin: 10px 0; }}
    </style>
</head>
<body>""".format(
                title=changelog.title
            )
        )

        # Title and metadata
        html_parts.append(f"<h1>{changelog.title}</h1>")
        html_parts.append('<div class="metadata">')
        html_parts.append(
            f"<p><strong>Generated:</strong> {changelog.generation_timestamp}</p>"
        )
        html_parts.append(
            f"<p><strong>State Comparison:</strong> {changelog.state_comparison['from_state']} → {changelog.state_comparison['to_state']}</p>"
        )
        html_parts.append("</div>")

        # Summary
        html_parts.append('<div class="summary">')
        html_parts.append("<h2>Summary</h2>")
        summary = changelog.summary
        html_parts.append(
            f"<p><strong>Total Changes:</strong> {summary.total_changes}</p>"
        )
        html_parts.append(
            f"<p><strong>Critical Changes:</strong> {summary.critical_changes}</p>"
        )
        html_parts.append(
            f"<p><strong>High Severity Changes:</strong> {summary.high_severity_changes}</p>"
        )
        html_parts.append(
            f"<p><strong>Security Changes:</strong> {summary.security_changes}</p>"
        )
        html_parts.append(
            f"<p><strong>Compliance Changes:</strong> {summary.compliance_changes}</p>"
        )
        html_parts.append("</div>")

        # Detailed changes
        html_parts.append("<h2>Detailed Changes</h2>")

        for section in changelog.sections:
            html_parts.append(f"<h3>{section.title}</h3>")
            html_parts.append(f"<p>{section.description}</p>")
            html_parts.append(
                f"<p><strong>Summary:</strong> {section.summary_stats['total_changes']} total changes</p>"
            )

            for entry in section.entries:
                severity_class = f"severity-{entry.severity.value}"
                html_parts.append(f'<div class="change-entry {severity_class}">')
                html_parts.append(f"<h4>{entry.summary}</h4>")
                html_parts.append(
                    f"<p><strong>Resource:</strong> {entry.resource_type} <code>{entry.resource_id}</code></p>"
                )
                html_parts.append(
                    f"<p><strong>Service:</strong> {entry.service} | <strong>Region:</strong> {entry.region}</p>"
                )
                html_parts.append(
                    f"<p><strong>Change Type:</strong> {entry.change_type.value} | <strong>Severity:</strong> {entry.severity.value}</p>"
                )
                html_parts.append(
                    f"<p><strong>Description:</strong> {entry.description}</p>"
                )
                html_parts.append(
                    f"<p><strong>Impact Assessment:</strong> {entry.impact_assessment}</p>"
                )

                if entry.remediation_steps:
                    html_parts.append('<div class="remediation">')
                    html_parts.append("<strong>Remediation Steps:</strong>")
                    html_parts.append("<ul>")
                    for step in entry.remediation_steps:
                        html_parts.append(f"<li>{step}</li>")
                    html_parts.append("</ul>")
                    html_parts.append("</div>")

                html_parts.append("</div>")

        # HTML footer
        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    def _make_serializable(self, obj: Any) -> Any:
        """Convert objects to serializable format for YAML/JSON output"""
        if isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (ChangeType, ChangeSeverity, ChangeCategory)):
            return obj.value
        elif hasattr(obj, "__dict__"):
            return self._make_serializable(obj.__dict__)
        else:
            return obj

    def integrate_into_bom_document(
        self, changelog: Changelog, bom_document_path: str
    ) -> str:
        """
        Integrate changelog as a dedicated section into BOM documents.

        Args:
            changelog: Changelog to integrate
            bom_document_path: Path to the BOM document

        Returns:
            Path to the updated BOM document
        """
        # This would integrate with the document generation system
        # For now, create a separate changelog section file
        changelog_section_path = Path(bom_document_path).parent / "changelog_section.md"

        # Generate markdown content for BOM integration
        content = self._generate_bom_section_content(changelog)

        with open(changelog_section_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(
            f"Changelog section created for BOM integration: {changelog_section_path}"
        )
        return str(changelog_section_path)

    def _generate_bom_section_content(self, changelog: Changelog) -> str:
        """Generate changelog content suitable for BOM document integration"""
        lines = []

        lines.append("# Infrastructure Change Log")
        lines.append("")
        lines.append(
            "This section documents changes detected between infrastructure scans."
        )
        lines.append("")

        # Summary table
        lines.append("## Change Summary")
        lines.append("")
        lines.append("| Metric | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Changes | {changelog.summary.total_changes} |")
        lines.append(f"| Critical Changes | {changelog.summary.critical_changes} |")
        lines.append(f"| High Severity | {changelog.summary.high_severity_changes} |")
        lines.append(f"| Security Changes | {changelog.summary.security_changes} |")
        lines.append(f"| Compliance Changes | {changelog.summary.compliance_changes} |")
        lines.append("")

        # Critical and high severity changes only for BOM
        critical_and_high = []
        for section in changelog.sections:
            for entry in section.entries:
                if entry.severity in [ChangeSeverity.CRITICAL, ChangeSeverity.HIGH]:
                    critical_and_high.append(entry)

        if critical_and_high:
            lines.append("## Critical and High Severity Changes")
            lines.append("")
            lines.append("The following changes require immediate attention:")
            lines.append("")

            for entry in critical_and_high:
                lines.append(f"### {entry.summary}")
                lines.append(f"- **Severity:** {entry.severity.value}")
                lines.append(f"- **Service:** {entry.service}")
                lines.append(f"- **Impact:** {entry.impact_assessment}")
                if entry.remediation_steps:
                    lines.append("- **Action Required:** " + entry.remediation_steps[0])
                lines.append("")

        return "\n".join(lines)
