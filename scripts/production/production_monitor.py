#!/usr/bin/env python3
"""
Production Monitoring Script
Monitor AWS operations for compliance and security validation in real-time.
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
    parser = argparse.ArgumentParser(description="InvenTag Production Safety Monitor")
    parser.add_argument(
        "--config", type=str, help="Path to compliance configuration file"
    )
    parser.add_argument(
        "--operations",
        type=str,
        nargs="+",
        help="AWS operations to validate (format: service:operation)",
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default=f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        help="Output file for compliance report",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()
    # Initialize compliance manager
    config = ComplianceConfiguration(
        standard=ComplianceStandard.GENERAL,
        enable_security_validation=True,
        enforce_read_only=True,
    )

    compliance_manager = ComplianceManager(config)

    if args.operations:
        print("🔒 Production Safety Monitor - Validating Operations")
        print("=" * 60)

        for operation in args.operations:
            if ":" not in operation:
                print(
                    f"❌ Invalid operation format: {operation} (expected service:operation)"
                )
                continue

            service, op = operation.split(":", 1)
            result = compliance_manager.validate_operation(service, op)

            status = "✅ ALLOWED" if result.is_valid else "🚫 BLOCKED"
            risk = result.risk_level
            print(f"  {operation} - {status} (Risk: {risk})")

            if not result.is_valid:
                print(f"    Reason: {result.validation_message}")

    # Generate compliance report
    report = compliance_manager.generate_comprehensive_report()

    with open(args.report_output, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n📊 Compliance report saved to: {args.report_output}")
    print(f"📈 Overall Compliance: {report['compliance_status']}")
    print(f"📊 Compliance Score: {report['compliance_score']:.1f}%")


if __name__ == "__main__":
    main()
