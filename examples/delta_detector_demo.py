#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeltaDetector Demo - Comprehensive change tracking demonstration

This script demonstrates the enhanced DeltaDetector capabilities for
comprehensive change tracking between AWS resource inventory states.
"""

import json
import sys
import os
from datetime import datetime, timezone

# Add the parent directory to the path to import inventag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.state.delta_detector import (
    DeltaDetector,
    ChangeType,
    ChangeSeverity,
    ChangeCategory,
)

# Ensure proper encoding for Windows console
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")


def create_sample_old_resources():
    """Create sample old resource data"""
    return [
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "id": "i-1234567890abcdef0",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "tags": {"Name": "web-server", "Environment": "dev"},
            "compliance_status": "compliant",
            "vpc_id": "vpc-12345",
            "subnet_id": "subnet-12345",
            "security_groups": ["sg-web"],
            "state": "running",
            "public_access": False,
        },
        {
            "arn": "arn:aws:s3:::company-data-bucket",
            "id": "company-data-bucket",
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "tags": {"Name": "company-data-bucket", "Environment": "dev"},
            "compliance_status": "non-compliant",
            "encryption": {"enabled": False},
            "public_access": False,
            "compliance_violations": ["missing_required_tag:CostCenter"],
        },
        {
            "arn": "arn:aws:rds:us-east-1:123456789012:db:legacy-db",
            "id": "legacy-db",
            "service": "RDS",
            "type": "DBInstance",
            "region": "us-east-1",
            "tags": {"Name": "legacy-db", "Environment": "dev"},
            "compliance_status": "compliant",
            "vpc_id": "vpc-12345",
            "subnet_id": "subnet-db",
        },
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-web",
            "id": "sg-web",
            "service": "EC2",
            "type": "SecurityGroup",
            "region": "us-east-1",
            "tags": {"Name": "web-security-group"},
            "compliance_status": "compliant",
            "vpc_id": "vpc-12345",
            "rules": [
                {"protocol": "tcp", "port": 80, "source": "0.0.0.0/0"},
                {"protocol": "tcp", "port": 443, "source": "0.0.0.0/0"},
            ],
        },
    ]


def create_sample_new_resources():
    """Create sample new resource data with various changes"""
    return [
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "id": "i-1234567890abcdef0",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "tags": {
                "Name": "web-server",
                "Environment": "prod",
                "CostCenter": "IT",
            },  # Environment changed, CostCenter added
            "compliance_status": "compliant",
            "vpc_id": "vpc-12345",
            "subnet_id": "subnet-67890",  # Subnet changed
            "security_groups": [
                "sg-web",
                "sg-monitoring",
            ],  # Added monitoring security group
            "state": "running",
            "public_access": False,
        },
        {
            "arn": "arn:aws:s3:::company-data-bucket",
            "id": "company-data-bucket",
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "tags": {
                "Name": "company-data-bucket",
                "Environment": "prod",
                "CostCenter": "IT",
            },  # Environment changed, CostCenter added
            "compliance_status": "compliant",  # Compliance status improved
            "encryption": {
                "enabled": True,
                "kms_key": "arn:aws:kms:us-east-1:123456789012:key/12345",
            },  # Encryption enabled
            "public_access": False,
            "compliance_violations": [],  # Violations resolved
        },
        # RDS instance removed (legacy-db)
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-web",
            "id": "sg-web",
            "service": "EC2",
            "type": "SecurityGroup",
            "region": "us-east-1",
            "tags": {
                "Name": "web-security-group",
                "Environment": "prod",
            },  # Environment tag added
            "compliance_status": "non-compliant",  # Compliance status degraded
            "vpc_id": "vpc-12345",
            "rules": [
                {
                    "protocol": "tcp",
                    "port": 80,
                    "source": "10.0.0.0/8",
                },  # Restricted source
                {"protocol": "tcp", "port": 443, "source": "0.0.0.0/0"},  # Still open
                {
                    "protocol": "tcp",
                    "port": 22,
                    "source": "0.0.0.0/0",
                },  # New SSH rule (security risk)
            ],
        },
        # New Lambda function added
        {
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:data-processor",
            "id": "data-processor",
            "service": "Lambda",
            "type": "Function",
            "region": "us-east-1",
            "tags": {
                "Name": "data-processor",
                "Environment": "prod",
                "CostCenter": "IT",
            },
            "compliance_status": "compliant",
            "vpc_id": "vpc-12345",
            "security_groups": ["sg-lambda"],
            "runtime": "python3.9",
            "memory": 512,
        },
        # New monitoring security group added
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-monitoring",
            "id": "sg-monitoring",
            "service": "EC2",
            "type": "SecurityGroup",
            "region": "us-east-1",
            "tags": {"Name": "monitoring-security-group", "Environment": "prod"},
            "compliance_status": "compliant",
            "vpc_id": "vpc-12345",
            "rules": [
                {
                    "protocol": "tcp",
                    "port": 9090,
                    "source": "10.0.0.0/8",
                }  # Prometheus monitoring
            ],
        },
    ]


def print_delta_report_summary(delta_report):
    """Print a comprehensive summary of the delta report"""
    print("=" * 80)
    print("DELTA DETECTION REPORT")
    print("=" * 80)
    print(f"State Comparison: {delta_report.state1_id} -> {delta_report.state2_id}")
    print(f"Generated: {delta_report.timestamp}")
    print()

    # Summary statistics
    print("SUMMARY STATISTICS")
    print("-" * 40)
    summary = delta_report.summary
    print(f"Total Resources (Old): {summary['total_resources_old']}")
    print(f"Total Resources (New): {summary['total_resources_new']}")
    print(f"Added Resources: {summary['added_count']}")
    print(f"Removed Resources: {summary['removed_count']}")
    print(f"Modified Resources: {summary['modified_count']}")
    print(f"Unchanged Resources: {summary['unchanged_count']}")
    print(f"Total Changes: {summary['total_changes']}")
    print()

    # Added resources
    if delta_report.added_resources:
        print("ADDED RESOURCES")
        print("-" * 40)
        for resource in delta_report.added_resources:
            print(f"+ {resource.service}/{resource.resource_type}: {resource.resource_id}")
            print(f"  ARN: {resource.resource_arn}")
            print(f"  Severity: {resource.severity.value}")
            if resource.security_impact:
                print(f"  Security Impact: {resource.security_impact}")
            if resource.network_impact:
                print(f"  Network Impact: {resource.network_impact}")
            print()

    # Removed resources
    if delta_report.removed_resources:
        print("REMOVED RESOURCES")
        print("-" * 40)
        for resource in delta_report.removed_resources:
            print(f"- {resource.service}/{resource.resource_type}: {resource.resource_id}")
            print(f"  ARN: {resource.resource_arn}")
            print(f"  Severity: {resource.severity.value}")
            if resource.security_impact:
                print(f"  Security Impact: {resource.security_impact}")
            if resource.network_impact:
                print(f"  Network Impact: {resource.network_impact}")
            print()

    # Modified resources
    if delta_report.modified_resources:
        print("MODIFIED RESOURCES")
        print("-" * 40)
        for resource in delta_report.modified_resources:
            print(f"~ {resource.service}/{resource.resource_type}: {resource.resource_id}")
            print(f"  ARN: {resource.resource_arn}")
            print(f"  Severity: {resource.severity.value}")
            print(f"  Attribute Changes: {len(resource.attribute_changes)}")

            # Show detailed attribute changes
            for change in resource.attribute_changes[:5]:  # Show first 5 changes
                print(f"    * {change.attribute_path}: {change.old_value} -> {change.new_value}")
                print(f"      Category: {change.category.value}, Severity: {change.severity.value}")

            if len(resource.attribute_changes) > 5:
                print(f"    ... and {len(resource.attribute_changes) - 5} more changes")

            if resource.compliance_changes:
                print(f"  Compliance Changes: {len(resource.compliance_changes)}")
                for change in resource.compliance_changes:
                    print(
                        f"    * {change.attribute_path}: {change.old_value} -> {change.new_value}"
                    )

            if resource.security_impact:
                print(f"  Security Impact: {resource.security_impact}")
            if resource.network_impact:
                print(f"  Network Impact: {resource.network_impact}")
            print()

    # Compliance changes
    print("COMPLIANCE ANALYSIS")
    print("-" * 40)
    compliance = delta_report.compliance_changes
    old_stats = compliance["old_compliance_stats"]
    new_stats = compliance["new_compliance_stats"]
    trend = compliance["compliance_trend"]

    print(
        f"Old Compliance: {old_stats['compliant_resources']}/{old_stats['total_resources']} ({old_stats['compliance_percentage']:.1f}%)"
    )
    print(
        f"New Compliance: {new_stats['compliant_resources']}/{new_stats['total_resources']} ({new_stats['compliance_percentage']:.1f}%)"
    )
    print(f"Compliance Change: {trend['compliance_percentage_change']:+.1f}%")
    print(f"Newly Compliant: {trend['newly_compliant']}")
    print(f"Newly Non-Compliant: {trend['newly_non_compliant']}")
    print()

    # Security changes
    print("SECURITY ANALYSIS")
    print("-" * 40)
    security = delta_report.security_changes
    print(f"Total Security Changes: {security['total_security_changes']}")
    print(f"High Risk Resources: {len(security['high_risk_resources'])}")

    security_summary = security["security_summary"]
    print(f"Critical Changes: {security_summary['critical_changes']}")
    print(f"High Changes: {security_summary['high_changes']}")
    print(f"Medium Changes: {security_summary['medium_changes']}")
    print(f"Low Changes: {security_summary['low_changes']}")
    print()

    # Network changes
    print("NETWORK ANALYSIS")
    print("-" * 40)
    network = delta_report.network_changes
    print(f"Total Network Changes: {network['total_network_changes']}")
    print(f"VPC Affected Resources: {len(network['vpc_affected_resources'])}")
    print(f"Subnet Affected Resources: {len(network['subnet_affected_resources'])}")
    print()

    # Impact analysis
    print("IMPACT ANALYSIS")
    print("-" * 40)
    impact = delta_report.impact_analysis
    print(f"High Impact Changes: {len(impact['high_impact_changes'])}")
    print(f"Cascade Risks: {len(impact['cascade_risks'])}")

    if impact["high_impact_changes"]:
        print("\nHigh Impact Changes:")
        for change in impact["high_impact_changes"]:
            print(f"  * {change['service']}: {change['resource_arn']}")
            print(f"    Impact: {change['potential_impact']}")

    if impact["cascade_risks"]:
        print("\nCascade Risks:")
        for risk in impact["cascade_risks"]:
            print(f"  * {risk['service']}: {risk['resource_arn']}")
            print(f"    Risk Level: {risk['risk_level']}")
            print(f"    Description: {risk['description']}")
    print()

    # Change statistics
    print("CHANGE STATISTICS")
    print("-" * 40)
    stats = delta_report.change_statistics
    print(f"Total Changes: {stats['total_changes']}")
    print(f"Change Percentage: {stats['change_percentage']:.1f}%")
    print(f"Most Changed Service: {stats['most_changed_service']}")

    print("\nBy Service:")
    for service, counts in stats["service_statistics"].items():
        total = sum(counts.values())
        print(
            f"  {service}: {total} changes (Added: {counts.get('added', 0)}, Removed: {counts.get('removed', 0)}, Modified: {counts.get('modified', 0)})"
        )

    print("\nBy Severity:")
    for severity, count in stats["severity_statistics"].items():
        print(f"  {severity.title()}: {count}")

    print("\nBy Category:")
    for category, count in stats["category_statistics"].items():
        print(f"  {category.title()}: {count}")


def main():
    """Main demo function"""
    print("DeltaDetector Comprehensive Change Tracking Demo")
    print("=" * 60)
    print()

    # Create sample data
    old_resources = create_sample_old_resources()
    new_resources = create_sample_new_resources()

    print(f"Old State: {len(old_resources)} resources")
    print(f"New State: {len(new_resources)} resources")
    print()

    # Initialize DeltaDetector
    detector = DeltaDetector()

    # Detect changes
    print("Detecting changes...")
    delta_report = detector.detect_changes(
        old_resources=old_resources,
        new_resources=new_resources,
        state1_id="20231201_120000",
        state2_id="20231201_130000",
    )

    # Print comprehensive report
    print_delta_report_summary(delta_report)

    # Demonstrate specific change analysis
    print("DETAILED CHANGE ANALYSIS")
    print("=" * 80)

    # Show specific examples of different change types
    if delta_report.modified_resources:
        print("Example: EC2 Instance Changes")
        print("-" * 40)
        ec2_change = next(
            (
                r
                for r in delta_report.modified_resources
                if r.service == "EC2" and r.resource_type == "Instance"
            ),
            None,
        )
        if ec2_change:
            print(f"Resource: {ec2_change.resource_id}")
            print("Attribute Changes:")
            for change in ec2_change.attribute_changes:
                print(f"  * {change.attribute_path}")
                print(f"    Old: {change.old_value}")
                print(f"    New: {change.new_value}")
                print(f"    Category: {change.category.value}")
                print(f"    Severity: {change.severity.value}")
                print(f"    Description: {change.description}")
                print()

    print("Demo completed successfully!")


if __name__ == "__main__":
    main()
