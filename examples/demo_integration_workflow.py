#!/usr/bin/env python3
"""
Demo script showing the integrated compliance checking and BOM generation workflow.
"""

import json
import tempfile
import os
from datetime import datetime


def demo_integrated_workflow():
    """Demonstrate the integrated compliance-to-BOM workflow."""

    print("InvenTag Integrated Workflow Demo")
    print("=" * 50)

    # Create sample AWS resource inventory
    sample_resources = [
        {
            "service": "EC2",
            "type": "Instance",
            "id": "i-1234567890abcdef0",
            "name": "web-server-prod",
            "region": "us-east-1",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "tags": {
                "Name": "web-server-prod",
                "Environment": "production",
                "Owner": "web-team",
                "CostCenter": "engineering",
            },
            "account_id": "123456789012",
        },
        {
            "service": "S3",
            "type": "Bucket",
            "id": "company-data-backup",
            "name": "company-data-backup",
            "region": "us-east-1",
            "arn": "arn:aws:s3:::company-data-backup",
            "tags": {
                "Name": "company-data-backup",
                "Environment": "production",
                "Owner": "data-team",
                # Missing CostCenter tag - will be non-compliant
            },
            "account_id": "123456789012",
        },
        {
            "service": "RDS",
            "type": "DBInstance",
            "id": "prod-database",
            "name": "prod-database",
            "region": "us-east-1",
            "arn": "arn:aws:rds:us-east-1:123456789012:db:prod-database",
            "tags": {},  # No tags - will be untagged
            "account_id": "123456789012",
        },
        {
            "service": "VPC",
            "type": "VPC",
            "id": "vpc-12345678",
            "name": "main-vpc",
            "region": "us-east-1",
            "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
            "tags": {
                "Name": "main-vpc",
                "Environment": "production",
                "Owner": "network-team",
                "CostCenter": "infrastructure",
            },
            "account_id": "123456789012",
        },
    ]

    # Create tag compliance policy
    tag_policy = {
        "required_tags": [
            {"key": "Environment", "values": ["production", "staging", "development"]},
            {"key": "Owner"},
            {"key": "CostCenter"},
        ]
    }

    print(f"📊 Sample inventory: {len(sample_resources)} AWS resources")
    print("🔍 Tag policy requires: Environment, Owner, CostCenter")
    print()

    try:
        from inventag.compliance import ComprehensiveTagComplianceChecker

        # Create temporary policy file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as policy_file:
            json.dump(tag_policy, policy_file, indent=2)
            policy_path = policy_file.name

        print("Step 1: Running compliance analysis...")
        print("-" * 30)

        # Initialize compliance checker
        checker = ComprehensiveTagComplianceChecker(regions=["us-east-1"], config_file=policy_path)

        # Run compliance check
        results = checker.check_compliance(sample_resources)

        # Display compliance results
        summary = results["summary"]
        print(f"✅ Total resources: {summary['total_resources']}")
        print(f"✅ Compliant: {summary['compliant_resources']}")
        print(f"❌ Non-compliant: {summary['non_compliant_resources']}")
        print(f"⚠️  Untagged: {summary['untagged_resources']}")
        print(f"📈 Compliance rate: {summary['compliance_percentage']:.1f}%")
        print()

        # Show detailed compliance issues
        if results["non_compliant"]:
            print("Non-compliant resources:")
            for resource in results["non_compliant"]:
                missing_tags = resource.get("missing_tags", [])
                print(
                    f"  - {resource['service']}/{resource['name']}: Missing {', '.join(missing_tags)}"
                )

        if results["untagged"]:
            print("Untagged resources:")
            for resource in results["untagged"]:
                print(f"  - {resource['service']}/{resource['name']}: No tags")
        print()

        print("Step 2: Generating BOM documents...")
        print("-" * 30)

        # Generate BOM documents from compliance results
        with tempfile.TemporaryDirectory() as temp_dir:
            bom_results = checker.generate_bom_documents(
                output_formats=["excel", "csv"],
                output_directory=temp_dir,
                enable_vpc_enrichment=False,  # Disable to avoid AWS API calls
                enable_security_analysis=False,
                enable_network_analysis=False,
            )

            if bom_results["success"]:
                print("✅ BOM generation successful!")
                print(f"📄 Generated {len(bom_results['generated_files'])} documents:")

                for file_path in bom_results["generated_files"]:
                    file_size = os.path.getsize(file_path)
                    file_name = os.path.basename(file_path)
                    print(f"   - {file_name} ({file_size:,} bytes)")

                print()
                print("📋 BOM documents include:")
                print("   - Resource inventory with compliance status")
                print("   - Service-specific sheets (EC2, S3, RDS, VPC)")
                print("   - Summary dashboard with compliance metrics")
                print("   - Custom tag attributes and service descriptions")

            else:
                print("❌ BOM generation failed")
                for format_type, result in bom_results["generation_results"].items():
                    if not result["success"]:
                        print(f"   - {format_type}: {result['error']}")

        print()
        print("Step 3: Enhanced BOM converter demo...")
        print("-" * 30)

        # Demonstrate enhanced BOM converter
        from inventag.reporting import BOMConverter

        converter = BOMConverter(
            enrich_vpc_info=False,  # Disable to avoid AWS API calls
            enable_advanced_analysis=False,  # Disable for demo
        )

        # Add compliance status to resources for demo
        enhanced_resources = []
        for resource in sample_resources:
            resource_copy = resource.copy()

            # Simulate compliance status
            if resource["tags"]:
                required_tags = ["Environment", "Owner", "CostCenter"]
                missing = [tag for tag in required_tags if tag not in resource["tags"]]
                if not missing:
                    resource_copy["compliance_status"] = "Compliant"
                else:
                    resource_copy["compliance_status"] = "Non-Compliant"
                    resource_copy["missing_tags"] = ", ".join(missing)
            else:
                resource_copy["compliance_status"] = "Untagged"

            enhanced_resources.append(resource_copy)

        converter.data = enhanced_resources

        # Generate enhanced Excel report
        excel_file = os.path.join(
            tempfile.gettempdir(),
            f'enhanced_bom_demo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
        )
        converter.export_to_excel(excel_file)

        file_size = os.path.getsize(excel_file)
        print(f"✅ Enhanced Excel BOM: {os.path.basename(excel_file)} ({file_size:,} bytes)")
        print("📊 Enhanced features include:")
        print("   - Service-specific sheets with detailed resource information")
        print("   - Compliance status column for each resource")
        print("   - Summary dashboard with service breakdown")
        print("   - Professional formatting and conditional highlighting")

        # Clean up
        os.unlink(policy_path)
        try:
            os.unlink(excel_file)
        except PermissionError:
            pass  # File might be locked on Windows

        print()
        print("🎉 Integration demo completed successfully!")
        print()
        print("Key Benefits:")
        print("✅ Seamless workflow from compliance checking to BOM generation")
        print("✅ Professional documents suitable for regulatory compliance")
        print("✅ Backward compatibility with existing scripts")
        print("✅ Enhanced analysis capabilities (network, security, service-specific)")
        print("✅ Flexible output formats (Excel, Word, CSV)")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure the inventag package is properly installed")
        return False
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = demo_integrated_workflow()
    exit(0 if success else 1)
