#!/usr/bin/env python3
"""
Security Validation Script
Validate AWS operations against security policies and generate audit reports.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add the project root to the Python path to import inventag
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

from inventag.compliance import (
    ComplianceManager,
    ComplianceConfiguration,
    ComplianceStandard,
)


def main():
    parser = argparse.ArgumentParser(
        description="InvenTag Security Validator - Validate AWS operations for security compliance"
    )
    parser.add_argument(
        "--validate-inventory",
        action="store_true",
        help="Validate resource inventory operations",
    )
    parser.add_argument(
        "--security-policy", type=str, help="Path to custom security policy file"
    )
    parser.add_argument(
        "--audit-output",
        type=str,
        default=f"security_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        help="Output file for security audit report",
    )
    parser.add_argument(
        "--enforce-read-only",
        action="store_true",
        default=True,
        help="Enforce read-only operations only (default: enabled)",
    )
    parser.add_argument(
        "--risk-threshold",
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        default="MEDIUM",
        help="Risk threshold for operation blocking (default: MEDIUM)",
    )

    args = parser.parse_args()

    print("🛡️  InvenTag Security Validator")
    print("=" * 50)

    # Initialize compliance manager with security focus
    config = ComplianceConfiguration(
        standard=ComplianceStandard.GENERAL,
        enable_security_validation=True,
        enable_production_monitoring=True,
        enforce_read_only=args.enforce_read_only,
    )

    compliance_manager = ComplianceManager(config)

    # Common AWS operations to validate
    operations_to_test = [
        ("ec2", "describe_instances"),
        ("ec2", "describe_security_groups"),
        ("s3", "list_buckets"),
        ("s3", "get_bucket_policy"),
        ("iam", "list_users"),
        ("iam", "get_user_policy"),
        ("rds", "describe_db_instances"),
        ("lambda", "list_functions"),
        ("cloudformation", "describe_stacks"),
        ("vpc", "describe_vpcs"),
    ]

    if args.validate_inventory:
        print("\n🔍 Validating standard inventory operations:")
        print("-" * 50)

        allowed_count = 0
        blocked_count = 0

        for service, operation in operations_to_test:
            result = compliance_manager.validate_operation(service, operation)

            status = "✅ ALLOWED" if result.is_valid else "🚫 BLOCKED"
            risk_color = {
                "LOW": "🟢",
                "MEDIUM": "🟡",
                "HIGH": "🟠",
                "CRITICAL": "🔴",
            }.get(result.risk_level, "⚪")

            print(
                f"  {service}:{operation} - {status} {risk_color} {result.risk_level}"
            )

            if result.is_valid:
                allowed_count += 1
            else:
                blocked_count += 1
                print(f"    ⚠️  {result.validation_message}")

        print(f"\n📊 Validation Summary:")
        print(f"  ✅ Allowed: {allowed_count}")
        print(f"  🚫 Blocked: {blocked_count}")
        print(
            f"  📈 Approval Rate: {(allowed_count / len(operations_to_test) * 100):.1f}%"
        )

    # Generate security audit report
    print(f"\n📋 Generating security audit report...")
    report = compliance_manager.generate_comprehensive_report()

    # Add security-specific metadata
    security_report = {
        "audit_type": "security_validation",
        "timestamp": datetime.now().isoformat(),
        "risk_threshold": args.risk_threshold,
        "enforce_read_only": args.enforce_read_only,
        "compliance_report": report,
    }

    with open(args.audit_output, "w") as f:
        json.dump(security_report, f, indent=2, default=str)

    print(f"✅ Security audit report saved to: {args.audit_output}")

    # Security recommendations
    if report.get("compliance_score", 0) < 80:
        print("\n⚠️  Security Recommendations:")
        print("  • Review blocked operations for compliance")
        print("  • Consider implementing additional security controls")
        print("  • Enable CloudTrail for comprehensive audit logging")


if __name__ == "__main__":
    main()
