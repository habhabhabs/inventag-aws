#!/usr/bin/env python3
"""
StateManager Demonstration Script

This script demonstrates the comprehensive state management capabilities
of the InvenTag StateManager, including state persistence, change tracking,
and audit trail generation.
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the parent directory to the path to import inventag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.state import StateManager


def main():
    """Demonstrate StateManager functionality"""
    print("=== InvenTag StateManager Demonstration ===\n")

    # Initialize StateManager with demo configuration
    state_manager = StateManager(state_dir="demo_state", retention_days=30, max_snapshots=10)

    # Sample resource data for demonstration
    initial_resources = [
        {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "id": "i-1234567890abcdef0",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "tags": {"Name": "web-server", "Environment": "production"},
            "compliance_status": "compliant",
        },
        {
            "arn": "arn:aws:s3:::my-app-bucket",
            "id": "my-app-bucket",
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "tags": {"Name": "my-app-bucket", "Environment": "production"},
            "compliance_status": "compliant",
        },
    ]

    # Sample compliance data
    compliance_data = {
        "summary": {
            "total_resources": 2,
            "compliant_resources": 2,
            "non_compliant_resources": 0,
            "compliance_percentage": 100.0,
        },
        "violations": [],
    }

    print("1. Saving initial state...")
    state_id1 = state_manager.save_state(
        resources=initial_resources,
        account_id="123456789012",
        regions=["us-east-1"],
        discovery_method="demo",
        compliance_data=compliance_data,
        tags={"demo": "initial_state", "purpose": "demonstration"},
    )
    print(f"   Initial state saved with ID: {state_id1}")

    # Simulate changes - add a new resource and modify compliance
    modified_resources = initial_resources.copy()
    modified_resources.append(
        {
            "arn": "arn:aws:rds:us-east-1:123456789012:db:mydb",
            "id": "mydb",
            "service": "RDS",
            "type": "DBInstance",
            "region": "us-east-1",
            "tags": {"Name": "mydb"},  # Missing Environment tag
            "compliance_status": "non-compliant",
        }
    )

    # Update compliance data
    modified_compliance_data = {
        "summary": {
            "total_resources": 3,
            "compliant_resources": 2,
            "non_compliant_resources": 1,
            "compliance_percentage": 66.7,
        },
        "violations": [
            {
                "resource_arn": "arn:aws:rds:us-east-1:123456789012:db:mydb",
                "violation_type": "missing_required_tag",
                "details": "Missing required tag: Environment",
            }
        ],
    }

    print("\n2. Saving modified state...")
    state_id2 = state_manager.save_state(
        resources=modified_resources,
        account_id="123456789012",
        regions=["us-east-1"],
        discovery_method="demo",
        compliance_data=modified_compliance_data,
        tags={"demo": "modified_state", "purpose": "demonstration"},
    )
    print(f"   Modified state saved with ID: {state_id2}")

    print("\n3. Listing all available states...")
    states = state_manager.list_states()
    for state in states:
        metadata = state["metadata"]
        print(f"   State ID: {state['state_id']}")
        print(f"   - Resources: {metadata['resource_count']}")
        print(
            f"   - Compliance: {metadata.get('compliance_status', {}).get('compliance_percentage', 'N/A')}%"
        )
        print(f"   - Checksum: {metadata['checksum'][:8]}...")
        print()

    print("4. Getting comparison data for delta analysis...")
    comparison = state_manager.get_state_comparison_data(state_id1, state_id2)

    state1_resources = {r["arn"]: r for r in comparison["state1"]["resources"]}
    state2_resources = {r["arn"]: r for r in comparison["state2"]["resources"]}

    # Find added resources
    added_arns = set(state2_resources.keys()) - set(state1_resources.keys())
    print(f"   Added resources: {len(added_arns)}")
    for arn in added_arns:
        resource = state2_resources[arn]
        print(f"   + {resource['service']}: {resource['id']} ({resource['compliance_status']})")

    # Find removed resources
    removed_arns = set(state1_resources.keys()) - set(state2_resources.keys())
    print(f"   Removed resources: {len(removed_arns)}")
    for arn in removed_arns:
        resource = state1_resources[arn]
        print(f"   - {resource['service']}: {resource['id']}")

    # Find modified resources (same ARN, different checksum)
    common_arns = set(state1_resources.keys()) & set(state2_resources.keys())
    modified_arns = []
    for arn in common_arns:
        if state1_resources[arn] != state2_resources[arn]:
            modified_arns.append(arn)

    print(f"   Modified resources: {len(modified_arns)}")
    for arn in modified_arns:
        resource = state2_resources[arn]
        print(f"   ~ {resource['service']}: {resource['id']}")

    print("\n5. Exporting state for CI/CD integration...")
    export_file = state_manager.export_state(
        state_id=state_id2,
        export_format="json",
        output_file="demo_export.json",
        include_metadata=True,
    )
    print(f"   State exported to: {export_file}")

    print("\n6. Validating state integrity...")
    validation_results = state_manager.validate_state_integrity()
    print(f"   Valid states: {len(validation_results['valid_states'])}")
    print(f"   Invalid states: {len(validation_results['invalid_states'])}")
    print(f"   Missing files: {len(validation_results['missing_files'])}")
    print(f"   Checksum mismatches: {len(validation_results['checksum_mismatches'])}")

    print("\n7. Storage statistics...")
    stats = state_manager.get_storage_stats()
    print(f"   Total states: {stats['total_states']}")
    print(f"   Total size: {stats['total_size_mb']} MB")
    print(
        f"   Retention policy: {stats['retention_days']} days, max {stats['max_snapshots']} snapshots"
    )
    print(f"   Storage directory: {stats['state_directory']}")

    print("\n=== StateManager Demonstration Complete ===")
    print("\nKey capabilities demonstrated:")
    print("✓ State saving with comprehensive metadata and tracking")
    print("✓ State loading and listing with timestamp tracking")
    print("✓ Change detection through checksum comparison")
    print("✓ Delta analysis between states")
    print("✓ Export functionality for CI/CD integration")
    print("✓ State integrity validation")
    print("✓ Storage statistics and retention management")
    print("✓ Audit trail generation with complete data lineage")


if __name__ == "__main__":
    main()
