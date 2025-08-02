#!/usr/bin/env python3
"""
ChangelogGenerator Demo

Demonstrates the ChangelogGenerator functionality for creating professional
change documentation with structured entries, impact assessment, and
multi-format output support.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add the parent directory to the path so we can import inventag
sys.path.insert(0, str(Path(__file__).parent.parent))

from inventag.state.changelog_generator import (
    ChangelogGenerator, ChangelogFormat, ChangelogEntry, ChangelogSection,
    ChangelogSummary, TrendAnalysis, Changelog
)
from inventag.state.delta_detector import (
    DeltaReport, ResourceChange, AttributeChange, ChangeType, ChangeSeverity, ChangeCategory
)


def create_sample_delta_report():
    """Create a comprehensive sample delta report for demonstration"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Create various types of attribute changes
    security_change = AttributeChange(
        attribute_path="security_groups",
        old_value=["sg-old123"],
        new_value=["sg-new456", "sg-additional789"],
        change_type=ChangeType.MODIFIED,
        category=ChangeCategory.SECURITY,
        severity=ChangeSeverity.CRITICAL,
        description="Security groups modified - added additional group"
    )
    
    encryption_change = AttributeChange(
        attribute_path="encryption.enabled",
        old_value=False,
        new_value=True,
        change_type=ChangeType.MODIFIED,
        category=ChangeCategory.SECURITY,
        severity=ChangeSeverity.HIGH,
        description="Encryption enabled on resource"
    )
    
    tag_change = AttributeChange(
        attribute_path="tags.Environment",
        old_value="dev",
        new_value="prod",
        change_type=ChangeType.MODIFIED,
        category=ChangeCategory.TAGS,
        severity=ChangeSeverity.MEDIUM,
        description="Environment tag updated"
    )
    
    compliance_change = AttributeChange(
        attribute_path="compliance_status",
        old_value="compliant",
        new_value="non-compliant",
        change_type=ChangeType.MODIFIED,
        category=ChangeCategory.COMPLIANCE,
        severity=ChangeSeverity.HIGH,
        description="Compliance status changed due to policy violation"
    )
    
    # Create resource changes
    added_resources = [
        ResourceChange(
            resource_arn="arn:aws:s3:::new-security-bucket-2024",
            resource_id="new-security-bucket-2024",
            service="S3",
            resource_type="Bucket",
            region="us-east-1",
            change_type=ChangeType.ADDED,
            severity=ChangeSeverity.MEDIUM,
            security_impact="New S3 bucket created with default security settings",
            network_impact=None,
            related_resources=["arn:aws:iam::123456789012:role/S3AccessRole"],
            timestamp=timestamp
        ),
        ResourceChange(
            resource_arn="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
            resource_id="12345678-1234-1234-1234-123456789012",
            service="KMS",
            resource_type="Key",
            region="us-east-1",
            change_type=ChangeType.ADDED,
            severity=ChangeSeverity.HIGH,
            security_impact="New KMS key created for encryption - requires access policy review",
            network_impact=None,
            related_resources=[],
            timestamp=timestamp
        )
    ]
    
    removed_resources = [
        ResourceChange(
            resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-obsolete123",
            resource_id="i-obsolete123",
            service="EC2",
            resource_type="Instance",
            region="us-east-1",
            change_type=ChangeType.REMOVED,
            severity=ChangeSeverity.HIGH,
            security_impact="EC2 instance terminated - security group rules may be orphaned",
            network_impact="Network connectivity to this instance is no longer available",
            related_resources=["sg-old123", "subnet-12345"],
            timestamp=timestamp
        )
    ]
    
    modified_resources = [
        ResourceChange(
            resource_arn="arn:aws:rds:us-east-1:123456789012:db:production-database",
            resource_id="production-database",
            service="RDS",
            resource_type="DBInstance",
            region="us-east-1",
            change_type=ChangeType.MODIFIED,
            attribute_changes=[encryption_change, tag_change],
            compliance_changes=[compliance_change],
            severity=ChangeSeverity.HIGH,
            security_impact="Database encryption enabled - improved security posture",
            network_impact=None,
            related_resources=["subnet-group-prod", "sg-database"],
            timestamp=timestamp
        ),
        ResourceChange(
            resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-webserver001",
            resource_id="i-webserver001",
            service="EC2",
            resource_type="Instance",
            region="us-east-1",
            change_type=ChangeType.MODIFIED,
            attribute_changes=[security_change],
            compliance_changes=[],
            severity=ChangeSeverity.CRITICAL,
            security_impact="Critical: Security group changes may expose instance to unauthorized access",
            network_impact="Network access rules modified - connectivity may be affected",
            related_resources=["sg-new456", "sg-additional789", "vpc-12345"],
            timestamp=timestamp
        ),
        ResourceChange(
            resource_arn="arn:aws:lambda:us-east-1:123456789012:function:data-processor",
            resource_id="data-processor",
            service="Lambda",
            resource_type="Function",
            region="us-east-1",
            change_type=ChangeType.MODIFIED,
            attribute_changes=[
                AttributeChange(
                    attribute_path="environment.variables.LOG_LEVEL",
                    old_value="INFO",
                    new_value="DEBUG",
                    change_type=ChangeType.MODIFIED,
                    category=ChangeCategory.CONFIGURATION,
                    severity=ChangeSeverity.LOW,
                    description="Log level changed to DEBUG"
                )
            ],
            compliance_changes=[],
            severity=ChangeSeverity.LOW,
            security_impact=None,
            network_impact=None,
            related_resources=[],
            timestamp=timestamp
        )
    ]
    
    # Create delta report
    delta_report = DeltaReport(
        state1_id="20240130_120000",
        state2_id="20240130_130000",
        timestamp=timestamp,
        summary={
            'total_resources_old': 150,
            'total_resources_new': 151,
            'added_count': len(added_resources),
            'removed_count': len(removed_resources),
            'modified_count': len(modified_resources),
            'unchanged_count': 146,
            'total_changes': len(added_resources) + len(removed_resources) + len(modified_resources)
        },
        added_resources=added_resources,
        removed_resources=removed_resources,
        modified_resources=modified_resources,
        unchanged_resources=[],  # Not needed for demo
        compliance_changes={
            'total_compliance_changes': 1,
            'new_violations': 1,
            'resolved_violations': 0
        },
        security_changes={
            'critical_security_changes': 1,
            'high_security_changes': 2,
            'new_security_risks': 1
        },
        network_changes={
            'network_impacting_changes': 2,
            'connectivity_changes': 1
        },
        impact_analysis={
            'high_impact_services': ['EC2', 'RDS'],
            'affected_resource_count': 5
        },
        change_statistics={
            'changes_by_service': {
                'EC2': 2,
                'RDS': 1,
                'S3': 1,
                'KMS': 1,
                'Lambda': 1
            }
        }
    )
    
    return delta_report


def create_historical_reports():
    """Create historical delta reports for trend analysis"""
    historical_reports = []
    base_time = datetime.now(timezone.utc)
    
    for i in range(5):
        timestamp = (base_time - timedelta(days=i*7)).isoformat()  # Weekly reports
        
        # Simulate varying change patterns
        change_count = 3 + (i % 3)  # Vary between 3-5 changes
        severity_pattern = [ChangeSeverity.HIGH, ChangeSeverity.MEDIUM, ChangeSeverity.LOW][i % 3]
        
        resources = []
        for j in range(change_count):
            resource = ResourceChange(
                resource_arn=f"arn:aws:ec2:us-east-1:123456789012:instance/i-historical{i}{j}",
                resource_id=f"i-historical{i}{j}",
                service=["EC2", "RDS", "S3", "Lambda"][j % 4],
                resource_type="Instance",
                region="us-east-1",
                change_type=[ChangeType.ADDED, ChangeType.MODIFIED, ChangeType.REMOVED][j % 3],
                severity=severity_pattern,
                timestamp=timestamp
            )
            resources.append(resource)
        
        report = DeltaReport(
            state1_id=f"historical_state_{i}",
            state2_id=f"historical_state_{i+1}",
            timestamp=timestamp,
            summary={'total_changes': change_count},
            added_resources=[r for r in resources if r.change_type == ChangeType.ADDED],
            removed_resources=[r for r in resources if r.change_type == ChangeType.REMOVED],
            modified_resources=[r for r in resources if r.change_type == ChangeType.MODIFIED],
            unchanged_resources=[],
            compliance_changes={},
            security_changes={},
            network_changes={},
            impact_analysis={},
            change_statistics={}
        )
        historical_reports.append(report)
    
    return historical_reports


def demonstrate_changelog_generation():
    """Demonstrate comprehensive changelog generation"""
    print("🔄 ChangelogGenerator Demo - Professional Change Documentation")
    print("=" * 70)
    
    # Create output directory
    output_dir = Path("demo_output/changelogs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize ChangelogGenerator
    print("\n1. Initializing ChangelogGenerator...")
    generator = ChangelogGenerator(
        output_dir=str(output_dir),
        include_technical_details=True,
        include_remediation_steps=True,
        group_by_service=True
    )
    print(f"   ✓ Output directory: {output_dir}")
    print(f"   ✓ Technical details: Enabled")
    print(f"   ✓ Remediation steps: Enabled")
    print(f"   ✓ Grouping: By service")
    
    # Create sample data
    print("\n2. Creating sample delta report...")
    delta_report = create_sample_delta_report()
    print(f"   ✓ Added resources: {len(delta_report.added_resources)}")
    print(f"   ✓ Removed resources: {len(delta_report.removed_resources)}")
    print(f"   ✓ Modified resources: {len(delta_report.modified_resources)}")
    print(f"   ✓ Total changes: {delta_report.summary['total_changes']}")
    
    # Generate basic changelog
    print("\n3. Generating comprehensive changelog...")
    changelog = generator.generate_changelog(
        delta_report,
        title="Production Infrastructure Changes - Weekly Review"
    )
    print(f"   ✓ Title: {changelog.title}")
    print(f"   ✓ Total entries: {changelog.summary.total_changes}")
    print(f"   ✓ Critical changes: {changelog.summary.critical_changes}")
    print(f"   ✓ High severity changes: {changelog.summary.high_severity_changes}")
    print(f"   ✓ Security changes: {changelog.summary.security_changes}")
    print(f"   ✓ Sections: {len(changelog.sections)}")
    
    # Display summary statistics
    print("\n4. Change Summary Statistics:")
    print(f"   • Changes by Type:")
    for change_type, count in changelog.summary.changes_by_type.items():
        print(f"     - {change_type.title()}: {count}")
    
    print(f"   • Changes by Service:")
    for service, count in changelog.summary.changes_by_service.items():
        print(f"     - {service}: {count}")
    
    print(f"   • Most Impacted Services: {', '.join(changelog.summary.most_impacted_services)}")
    
    # Generate changelog with trend analysis
    print("\n5. Generating changelog with trend analysis...")
    historical_reports = create_historical_reports()
    changelog_with_trends = generator.generate_changelog(
        delta_report,
        title="Infrastructure Changes with Trend Analysis",
        include_trend_analysis=True,
        historical_reports=historical_reports
    )
    
    if changelog_with_trends.trend_analysis:
        trend = changelog_with_trends.trend_analysis
        print(f"   ✓ Analysis period: {len(historical_reports) + 1} reports")
        print(f"   ✓ Change velocity: {trend.change_velocity} changes/day")
        print(f"   ✓ Most active services: {', '.join(trend.most_active_services)}")
        print(f"   ✓ Recommendations: {len(trend.recommendations)}")
    
    # Generate multiple output formats
    print("\n6. Generating multiple output formats...")
    generated_files = []
    
    formats = [
        (ChangelogFormat.MARKDOWN, "Markdown"),
        (ChangelogFormat.HTML, "HTML"),
        (ChangelogFormat.JSON, "JSON"),
        (ChangelogFormat.YAML, "YAML")
    ]
    
    for format_type, format_name in formats:
        try:
            output_file = generator.format_changelog(changelog, format_type)
            generated_files.append(output_file)
            file_size = Path(output_file).stat().st_size
            print(f"   ✓ {format_name}: {Path(output_file).name} ({file_size:,} bytes)")
        except Exception as e:
            print(f"   ✗ {format_name}: Failed - {e}")
    
    # Generate BOM integration section
    print("\n7. Creating BOM document integration...")
    try:
        # Create dummy BOM document
        bom_path = output_dir / "sample_bom_document.xlsx"
        bom_path.touch()
        
        section_file = generator.integrate_into_bom_document(changelog, str(bom_path))
        section_size = Path(section_file).stat().st_size
        print(f"   ✓ BOM section: {Path(section_file).name} ({section_size:,} bytes)")
        generated_files.append(section_file)
    except Exception as e:
        print(f"   ✗ BOM integration: Failed - {e}")
    
    # Display sample changelog entries
    print("\n8. Sample Changelog Entries:")
    print("-" * 50)
    
    for i, section in enumerate(changelog.sections[:2]):  # Show first 2 sections
        print(f"\n   Section: {section.title}")
        print(f"   Description: {section.description}")
        print(f"   Changes: {section.summary_stats['total_changes']}")
        
        for j, entry in enumerate(section.entries[:2]):  # Show first 2 entries per section
            print(f"\n   Entry {j+1}:")
            print(f"     • Summary: {entry.summary}")
            print(f"     • Resource: {entry.resource_type} '{entry.resource_id}'")
            print(f"     • Severity: {entry.severity.value.upper()}")
            print(f"     • Category: {entry.category.value.title()}")
            print(f"     • Impact: {entry.impact_assessment[:100]}...")
            
            if entry.remediation_steps:
                print(f"     • Remediation: {entry.remediation_steps[0][:80]}...")
    
    # Show trend analysis details
    if changelog_with_trends.trend_analysis:
        print("\n9. Trend Analysis Details:")
        print("-" * 50)
        trend = changelog_with_trends.trend_analysis
        
        print(f"   • Period: {trend.period_start[:10]} to {trend.period_end[:10]}")
        print(f"   • Change Velocity: {trend.change_velocity} changes per day")
        print(f"   • Total Periods Analyzed: {trend.total_periods}")
        
        print(f"   • Severity Trends:")
        for severity, counts in trend.severity_trends.items():
            if any(counts):  # Only show if there are changes
                avg_count = sum(counts) / len(counts) if counts else 0
                print(f"     - {severity.title()}: avg {avg_count:.1f} per period")
        
        print(f"   • Recommendations:")
        for rec in trend.recommendations[:3]:  # Show first 3 recommendations
            print(f"     - {rec}")
    
    # Summary
    print(f"\n10. Demo Summary:")
    print("=" * 50)
    print(f"   ✓ Generated {len(generated_files)} output files")
    print(f"   ✓ Processed {changelog.summary.total_changes} infrastructure changes")
    print(f"   ✓ Identified {changelog.summary.critical_changes} critical changes")
    print(f"   ✓ Created {len(changelog.sections)} organized sections")
    print(f"   ✓ Output directory: {output_dir}")
    
    print(f"\n   Generated Files:")
    for file_path in generated_files:
        print(f"     - {Path(file_path).name}")
    
    print(f"\n🎉 ChangelogGenerator demo completed successfully!")
    print(f"   Check the '{output_dir}' directory for all generated files.")
    
    return generated_files


def demonstrate_advanced_features():
    """Demonstrate advanced changelog features"""
    print("\n" + "=" * 70)
    print("🚀 Advanced ChangelogGenerator Features")
    print("=" * 70)
    
    output_dir = Path("demo_output/advanced_changelogs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Test different configuration options
    print("\n1. Testing different configuration options...")
    
    configs = [
        {
            'name': 'Minimal Configuration',
            'options': {
                'include_technical_details': False,
                'include_remediation_steps': False,
                'group_by_service': False
            }
        },
        {
            'name': 'Security-Focused Configuration',
            'options': {
                'include_technical_details': True,
                'include_remediation_steps': True,
                'group_by_service': True
            }
        }
    ]
    
    delta_report = create_sample_delta_report()
    
    for config in configs:
        print(f"\n   Testing: {config['name']}")
        generator = ChangelogGenerator(
            output_dir=str(output_dir / config['name'].lower().replace(' ', '_')),
            **config['options']
        )
        
        changelog = generator.generate_changelog(
            delta_report,
            title=f"Infrastructure Changes - {config['name']}"
        )
        
        # Generate markdown for comparison
        output_file = generator.format_changelog(changelog, ChangelogFormat.MARKDOWN)
        file_size = Path(output_file).stat().st_size
        
        print(f"     ✓ Sections: {len(changelog.sections)}")
        print(f"     ✓ Output size: {file_size:,} bytes")
        print(f"     ✓ File: {Path(output_file).name}")
    
    print(f"\n2. Advanced features demonstration completed!")
    print(f"   Check '{output_dir}' for configuration comparison files.")


if __name__ == "__main__":
    try:
        # Run main demonstration
        generated_files = demonstrate_changelog_generation()
        
        # Run advanced features demo
        demonstrate_advanced_features()
        
        print(f"\n✨ All demonstrations completed successfully!")
        print(f"   Total files generated: {len(generated_files)}")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)