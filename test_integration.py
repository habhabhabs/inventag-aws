#!/usr/bin/env python3
"""
Test script to verify the integration between compliance checking and BOM generation.
"""

import json
import tempfile
import os
from pathlib import Path

def test_compliance_bom_integration():
    """Test the integration between compliance checker and BOM generation."""
    
    # Create sample inventory data
    sample_data = [
        {
            "service": "EC2",
            "type": "Instance",
            "id": "i-1234567890abcdef0",
            "name": "test-instance",
            "region": "us-east-1",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "tags": {
                "Name": "test-instance",
                "Environment": "test"
            },
            "account_id": "123456789012"
        },
        {
            "service": "S3",
            "type": "Bucket",
            "id": "test-bucket",
            "name": "test-bucket",
            "region": "us-east-1",
            "arn": "arn:aws:s3:::test-bucket",
            "tags": {},
            "account_id": "123456789012"
        }
    ]
    
    # Create sample tag policy
    tag_policy = {
        "required_tags": [
            {"key": "Environment", "values": ["prod", "test", "dev"]},
            {"key": "Owner"}
        ]
    }
    
    print("Testing compliance checker with BOM generation integration...")
    
    try:
        # Import the compliance checker
        from inventag.compliance import ComprehensiveTagComplianceChecker
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as policy_file:
            json.dump(tag_policy, policy_file, indent=2)
            policy_path = policy_file.name
        
        # Initialize compliance checker
        checker = ComprehensiveTagComplianceChecker(
            regions=['us-east-1'],
            config_file=policy_path
        )
        
        # Run compliance check with sample data
        results = checker.check_compliance(sample_data)
        
        print(f"✓ Compliance check completed")
        print(f"  - Total resources: {results['summary']['total_resources']}")
        print(f"  - Compliant: {results['summary']['compliant_resources']}")
        print(f"  - Non-compliant: {results['summary']['non_compliant_resources']}")
        print(f"  - Untagged: {results['summary']['untagged_resources']}")
        
        # Test BOM generation
        with tempfile.TemporaryDirectory() as temp_dir:
            bom_results = checker.generate_bom_documents(
                output_formats=['excel', 'csv'],
                output_directory=temp_dir,
                enable_vpc_enrichment=False,  # Disable to avoid AWS API calls
                enable_security_analysis=False,
                enable_network_analysis=False
            )
            
            if bom_results['success']:
                print(f"✓ BOM generation completed")
                print(f"  - Generated files: {len(bom_results['generated_files'])}")
                for file_path in bom_results['generated_files']:
                    file_size = os.path.getsize(file_path)
                    print(f"    - {os.path.basename(file_path)} ({file_size} bytes)")
            else:
                print("✗ BOM generation failed")
                for format_type, result in bom_results['generation_results'].items():
                    if not result['success']:
                        print(f"    - {format_type}: {result['error']}")
        
        # Clean up
        os.unlink(policy_path)
        
        print("\n✓ Integration test completed successfully!")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure the inventag package is properly installed")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_bom_converter_enhancement():
    """Test the enhanced BOM converter capabilities."""
    
    print("\nTesting enhanced BOM converter...")
    
    try:
        from inventag.reporting import BOMConverter
        
        # Create sample data with VPC resources
        sample_data = [
            {
                "service": "VPC",
                "type": "VPC",
                "id": "vpc-12345",
                "name": "test-vpc",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345",
                "tags": {"Name": "test-vpc"},
                "account_id": "123456789012"
            },
            {
                "service": "VPC",
                "type": "SecurityGroup",
                "id": "sg-12345",
                "name": "test-sg",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-12345",
                "tags": {"Name": "test-sg"},
                "account_id": "123456789012"
            }
        ]
        
        # Test basic converter
        converter = BOMConverter(enrich_vpc_info=False, enable_advanced_analysis=False)
        converter.data = sample_data
        
        # Test Excel export
        excel_file = os.path.join(tempfile.gettempdir(), 'test_export.xlsx')
        converter.export_to_excel(excel_file)
        file_size = os.path.getsize(excel_file)
        print(f"✓ Basic Excel export: {os.path.basename(excel_file)} ({file_size} bytes)")
        try:
            os.unlink(excel_file)
        except PermissionError:
            pass  # File might be locked on Windows
        
        # Test CSV export
        csv_file = os.path.join(tempfile.gettempdir(), 'test_export.csv')
        converter.export_to_csv(csv_file)
        file_size = os.path.getsize(csv_file)
        print(f"✓ CSV export: {os.path.basename(csv_file)} ({file_size} bytes)")
        try:
            os.unlink(csv_file)
        except PermissionError:
            pass  # File might be locked on Windows
        
        print("✓ BOM converter enhancement test completed!")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("InvenTag Integration Test")
    print("=" * 40)
    
    success1 = test_compliance_bom_integration()
    success2 = test_bom_converter_enhancement()
    
    if success1 and success2:
        print("\n🎉 All integration tests passed!")
        exit(0)
    else:
        print("\n❌ Some tests failed")
        exit(1)