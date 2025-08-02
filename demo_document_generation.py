#!/usr/bin/env python3
"""
Demo script for the InvenTag Document Generation System

Demonstrates the complete document generation workflow with:
- DocumentGenerator orchestration layer
- ExcelWorkbookBuilder for Excel BOM generation
- WordDocumentBuilder for Word document generation
- Professional formatting and branding
"""

import os
import tempfile
from datetime import datetime, timezone

from inventag.reporting.document_generator import create_document_generator, BrandingConfig
from inventag.reporting.bom_processor import BOMData


def create_demo_bom_data():
    """Create comprehensive demo BOM data."""
    return BOMData(
        resources=[
            {
                "service": "EC2",
                "type": "Instance",
                "id": "i-1234567890abcdef0",
                "name": "web-server-1",
                "region": "us-east-1",
                "account_id": "123456789012",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                "compliance_status": "compliant",
                "tags": {
                    "Name": "web-server-1",
                    "Environment": "production",
                    "inventag:remarks": "Primary web server",
                    "inventag:costcenter": "IT-001"
                },
                "vpc_id": "vpc-12345678",
                "subnet_id": "subnet-12345678",
                "security_groups": ["sg-12345678"],
                "instance_type": "t3.medium",
                "state": "running"
            },
            {
                "service": "S3",
                "type": "Bucket",
                "id": "company-data-bucket",
                "name": "company-data-bucket",
                "region": "us-east-1",
                "account_id": "123456789012",
                "arn": "arn:aws:s3:::company-data-bucket",
                "compliance_status": "non_compliant",
                "tags": {
                    "Name": "company-data-bucket",
                    "Environment": "production"
                },
                "encryption": "AES256",
                "versioning": "Enabled",
                "public_access_blocked": True
            },
            {
                "service": "RDS",
                "type": "DBInstance",
                "id": "production-database",
                "name": "production-database",
                "region": "us-east-1",
                "account_id": "123456789012",
                "arn": "arn:aws:rds:us-east-1:123456789012:db:production-database",
                "compliance_status": "compliant",
                "tags": {
                    "Name": "production-database",
                    "Environment": "production",
                    "inventag:remarks": "Main application database",
                    "inventag:costcenter": "IT-001"
                },
                "engine": "mysql",
                "engine_version": "8.0.35",
                "instance_class": "db.t3.micro",
                "allocated_storage": 100
            },
            {
                "service": "LAMBDA",
                "type": "Function",
                "id": "data-processor",
                "name": "data-processor",
                "region": "us-east-1",
                "account_id": "123456789012",
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:data-processor",
                "compliance_status": "compliant",
                "tags": {
                    "Name": "data-processor",
                    "Environment": "production",
                    "inventag:costcenter": "DEV-001"
                },
                "runtime": "python3.9",
                "memory_size": 512,
                "timeout": 60
            },
            {
                "service": "VPC",
                "type": "SecurityGroup",
                "id": "sg-12345678",
                "name": "web-server-sg",
                "region": "us-east-1",
                "account_id": "123456789012",
                "arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-12345678",
                "compliance_status": "non_compliant",
                "tags": {
                    "Name": "web-server-sg",
                    "Environment": "production"
                },
                "vpc_id": "vpc-12345678",
                "group_name": "web-server-sg",
                "description": "Security group for web servers"
            }
        ],
        network_analysis={
            "total_vpcs": 2,
            "total_subnets": 6,
            "vpc_utilization": {
                "vpc-12345678": {
                    "name": "production-vpc",
                    "cidr_block": "10.0.0.0/16",
                    "utilization_percentage": 35.2,
                    "available_ips": 42000
                },
                "vpc-87654321": {
                    "name": "development-vpc",
                    "cidr_block": "10.1.0.0/16",
                    "utilization_percentage": 18.7,
                    "available_ips": 53000
                }
            }
        },
        security_analysis={
            "total_security_groups": 12,
            "high_risk_rules": 2,
            "overly_permissive_rules": [
                {
                    "group_id": "sg-12345678",
                    "rule": "0.0.0.0/0:22",
                    "risk_level": "high"
                },
                {
                    "group_id": "sg-87654321",
                    "rule": "0.0.0.0/0:3389",
                    "risk_level": "high"
                }
            ]
        },
        compliance_summary={
            "total_resources": 5,
            "compliant_resources": 3,
            "non_compliant_resources": 2,
            "compliance_percentage": 60.0
        },
        generation_metadata={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_resources": 5,
            "processing_time_seconds": 2.8,
            "data_source": "aws_resource_inventory.py"
        },
        custom_attributes=["inventag:remarks", "inventag:costcenter"]
    )


def main():
    """Demonstrate the document generation system."""
    print("🚀 InvenTag Document Generation System Demo")
    print("=" * 50)
    
    # Create demo data
    print("📊 Creating demo BOM data...")
    bom_data = create_demo_bom_data()
    print(f"   ✓ Created BOM data with {len(bom_data.resources)} resources")
    
    # Create output directory
    output_dir = tempfile.mkdtemp()
    print(f"📁 Output directory: {output_dir}")
    
    # Create document generator with custom branding
    print("\n🎨 Configuring document generator with custom branding...")
    branding = BrandingConfig(
        company_name="InvenTag Demo Corporation",
        color_scheme={
            "primary": "2E75B6",
            "accent": "70AD47", 
            "danger": "C5504B",
            "warning": "FFC000"
        },
        font_family="Calibri"
    )
    
    generator = create_document_generator(
        output_formats=["csv", "excel", "word"],
        branding_config=branding,
        output_directory=output_dir,
        filename_template="demo_bom_report_{timestamp}",
        validate_before_generation=True
    )
    
    print("   ✓ Document generator configured")
    print(f"   ✓ Available formats: {generator.get_available_formats()}")
    
    # Generate documents
    print("\n📄 Generating BOM documents...")
    try:
        summary = generator.generate_bom_documents(bom_data)
        
        print(f"   ✓ Generation completed in {summary.total_generation_time:.2f} seconds")
        print(f"   ✓ Successful formats: {summary.successful_formats}/{summary.total_formats}")
        
        if summary.failed_formats > 0:
            print(f"   ⚠️  Failed formats: {summary.failed_formats}")
            for error in summary.errors:
                print(f"      - {error}")
        
        # Display results
        print("\n📋 Generated Documents:")
        for result in summary.results:
            status = "✅" if result.success else "❌"
            size_mb = result.file_size_bytes / 1024 / 1024 if result.file_size_bytes > 0 else 0
            print(f"   {status} {result.format_type.upper()}: {result.filename}")
            if result.success:
                print(f"      Size: {size_mb:.2f} MB, Time: {result.generation_time_seconds:.2f}s")
                full_path = os.path.join(output_dir, result.filename)
                print(f"      Path: {full_path}")
            else:
                print(f"      Error: {result.error_message}")
        
        # Save generation report
        report_path = os.path.join(output_dir, "generation_report.json")
        generator.save_generation_report(summary, report_path)
        print(f"\n📊 Generation report saved: {report_path}")
        
        # Display format capabilities
        print("\n🔧 Format Capabilities:")
        capabilities = generator.get_format_capabilities()
        for format_type, caps in capabilities.items():
            status = "✅" if caps["available"] and caps["dependencies_met"] else "❌"
            print(f"   {status} {format_type.upper()}: {caps['builder_class']}")
            if not caps["dependencies_met"]:
                deps = generator.validate_format_dependencies(format_type)
                for dep in deps:
                    print(f"      Missing: {dep}")
        
        print(f"\n🎉 Demo completed successfully!")
        print(f"📁 All files saved to: {output_dir}")
        
    except Exception as e:
        print(f"❌ Document generation failed: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    exit(main())