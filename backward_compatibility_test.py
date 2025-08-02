#!/usr/bin/env python3
"""
Comprehensive backward compatibility test for InvenTag tasks 1-14.
This test ensures no breaking changes were introduced across all implemented features.
"""

import subprocess
import json
import tempfile
import os
import sys
from pathlib import Path

def test_original_interfaces():
    """Test that all original script interfaces work unchanged."""
    
    print("🔍 Testing Backward Compatibility for InvenTag Tasks 1-14")
    print("=" * 60)
    
    # Test data
    sample_inventory = [
        {
            "service": "EC2",
            "type": "Instance",
            "id": "i-1234567890abcdef0",
            "name": "test-instance",
            "region": "us-east-1",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "tags": {"Name": "test-instance", "Environment": "test"},
            "account_id": "123456789012"
        }
    ]
    
    sample_policy = {
        "required_tags": [{"key": "Environment"}]
    }
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Original tag_compliance_checker.py interface
    print("\n1. Testing tag_compliance_checker.py original interface...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as policy_file:
            json.dump(sample_policy, policy_file)
            policy_path = policy_file.name
        
        # Test original arguments work
        result = subprocess.run([
            sys.executable, "scripts/tag_compliance_checker.py", 
            "--config", policy_path,
            "--output", "test_compliance",
            "--format", "json",
            "--verbose"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("   ✅ Original CLI interface works")
            tests_passed += 1
        else:
            print(f"   ❌ Original CLI failed: {result.stderr}")
            tests_failed += 1
        
        # Clean up
        os.unlink(policy_path)
        for file in Path(".").glob("test_compliance*"):
            try:
                file.unlink()
            except:
                pass
                
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        tests_failed += 1
    
    # Test 2: Original bom_converter.py interface
    print("\n2. Testing bom_converter.py original interface...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as inventory_file:
            json.dump(sample_inventory, inventory_file)
            inventory_path = inventory_file.name
        
        # Test original arguments work
        result = subprocess.run([
            sys.executable, "scripts/bom_converter.py",
            "--input", inventory_path,
            "--output", "test_bom.xlsx",
            "--format", "excel",
            "--no-vpc-enrichment",
            "--verbose"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("   ✅ Original CLI interface works")
            tests_passed += 1
        else:
            print(f"   ❌ Original CLI failed: {result.stderr}")
            tests_failed += 1
        
        # Clean up
        os.unlink(inventory_path)
        if os.path.exists("test_bom.xlsx"):
            os.unlink("test_bom.xlsx")
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        tests_failed += 1
    
    # Test 3: New unified CLI doesn't break existing patterns
    print("\n3. Testing unified inventag CLI...")
    try:
        result = subprocess.run([
            sys.executable, "inventag_cli.py", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "inventag" in result.stdout.lower():
            print("   ✅ Unified CLI available")
            tests_passed += 1
        else:
            print(f"   ❌ Unified CLI failed: {result.stderr}")
            tests_failed += 1
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        tests_failed += 1
    
    # Test 4: Import compatibility
    print("\n4. Testing import compatibility...")
    try:
        # Test that old imports still work through wrappers
        from inventag.compliance import ComprehensiveTagComplianceChecker
        from inventag.reporting import BOMConverter
        
        # Test that classes can be instantiated
        checker = ComprehensiveTagComplianceChecker()
        converter = BOMConverter()
        
        print("   ✅ All imports work correctly")
        tests_passed += 1
        
    except Exception as e:
        print(f"   ❌ Import test failed: {e}")
        tests_failed += 1
    
    # Test 5: New features are optional and don't break existing workflows
    print("\n5. Testing new features are optional...")
    try:
        # Test that new BOM generation options don't break existing compliance workflow
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as policy_file:
            json.dump(sample_policy, policy_file)
            policy_path = policy_file.name
        
        # Test with new BOM generation flag (should work)
        result = subprocess.run([
            sys.executable, "scripts/tag_compliance_checker.py",
            "--config", policy_path,
            "--output", "test_with_bom",
            "--generate-bom",
            "--bom-formats", "excel"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("   ✅ New BOM generation features work")
            tests_passed += 1
        else:
            print(f"   ❌ New features failed: {result.stderr}")
            tests_failed += 1
        
        # Clean up
        os.unlink(policy_path)
        for file in Path(".").glob("test_with_bom*"):
            try:
                file.unlink()
            except:
                pass
        for file in Path("bom_output").glob("*") if Path("bom_output").exists() else []:
            try:
                file.unlink()
            except:
                pass
        if Path("bom_output").exists():
            try:
                Path("bom_output").rmdir()
            except:
                pass
                
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        tests_failed += 1
    
    # Test 6: Enhanced BOM converter features are optional
    print("\n6. Testing enhanced BOM converter features...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as inventory_file:
            json.dump(sample_inventory, inventory_file)
            inventory_path = inventory_file.name
        
        # Test with advanced analysis (should work)
        result = subprocess.run([
            sys.executable, "scripts/bom_converter.py",
            "--input", inventory_path,
            "--output", "test_advanced.xlsx",
            "--enable-advanced-analysis",
            "--no-vpc-enrichment"  # Disable to avoid AWS credential requirements
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("   ✅ Enhanced BOM features work")
            tests_passed += 1
        else:
            print(f"   ❌ Enhanced features failed: {result.stderr}")
            tests_failed += 1
        
        # Clean up
        os.unlink(inventory_path)
        if os.path.exists("test_advanced.xlsx"):
            os.unlink("test_advanced.xlsx")
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        tests_failed += 1
    
    # Summary
    print(f"\n📊 Backward Compatibility Test Results:")
    print(f"   ✅ Tests Passed: {tests_passed}")
    print(f"   ❌ Tests Failed: {tests_failed}")
    print(f"   📈 Success Rate: {(tests_passed/(tests_passed+tests_failed)*100):.1f}%")
    
    if tests_failed == 0:
        print("\n🎉 ALL BACKWARD COMPATIBILITY TESTS PASSED!")
        print("✅ No breaking changes detected across tasks 1-14")
        return True
    else:
        print(f"\n⚠️  {tests_failed} compatibility issues detected")
        return False

def test_feature_completeness():
    """Test that all major features from tasks 1-14 are available."""
    
    print("\n🔧 Testing Feature Completeness...")
    print("-" * 40)
    
    features_available = 0
    features_missing = 0
    
    # Test Task 1-2: Package structure and testing
    try:
        import inventag
        import inventag.core
        import inventag.discovery
        import inventag.compliance
        import inventag.reporting
        print("✅ Task 1-2: Unified package structure available")
        features_available += 1
    except ImportError as e:
        print(f"❌ Task 1-2: Package structure missing: {e}")
        features_missing += 1
    
    # Test Task 3: State management and delta detection
    try:
        from inventag.core import StateManager, DeltaDetector
        print("✅ Task 3: State management and delta detection available")
        features_available += 1
    except ImportError:
        print("❌ Task 3: State management components missing")
        features_missing += 1
    
    # Test Task 4: Service discovery and enrichment
    try:
        from inventag.discovery import ServiceAttributeEnricher
        print("✅ Task 4: Service discovery and enrichment available")
        features_available += 1
    except ImportError:
        print("❌ Task 4: Service enrichment missing")
        features_missing += 1
    
    # Test Task 5: Network analysis
    try:
        from inventag.discovery import NetworkAnalyzer, SecurityAnalyzer
        print("✅ Task 5: Network and security analysis available")
        features_available += 1
    except ImportError:
        print("❌ Task 5: Network analysis missing")
        features_missing += 1
    
    # Test Task 6: Service descriptions and tag mapping
    try:
        from inventag.discovery import ServiceDescriptionManager, TagMappingEngine
        print("✅ Task 6: Service descriptions and tag mapping available")
        features_available += 1
    except ImportError:
        print("❌ Task 6: Description and mapping engines missing")
        features_missing += 1
    
    # Test Task 7: BOM data processing
    try:
        from inventag.reporting import BOMDataProcessor
        print("✅ Task 7: BOM data processing available")
        features_available += 1
    except ImportError:
        print("❌ Task 7: BOM data processor missing")
        features_missing += 1
    
    # Test Task 8: Document generation
    try:
        from inventag.reporting import DocumentGenerator
        print("✅ Task 8: Document generation system available")
        features_available += 1
    except ImportError:
        print("❌ Task 8: Document generator missing")
        features_missing += 1
    
    # Test Task 9: Multi-account support
    try:
        from inventag.core import CloudBOMGenerator, MultiAccountConfig
        print("✅ Task 9: Multi-account support available")
        features_available += 1
    except ImportError:
        print("❌ Task 9: Multi-account components missing")
        features_missing += 1
    
    # Test Task 10: Security and compliance
    try:
        from inventag.compliance import ReadOnlyAccessValidator, ProductionSafetyMonitor
        print("✅ Task 10: Security and compliance features available")
        features_available += 1
    except ImportError:
        print("❌ Task 10: Security components missing")
        features_missing += 1
    
    # Test Task 11: Template system
    try:
        from inventag.reporting import TemplateManager, TemplateVariableResolver
        print("✅ Task 11: Template and branding system available")
        features_available += 1
    except ImportError:
        print("❌ Task 11: Template system missing")
        features_missing += 1
    
    # Test Task 12: Testing suite (check if tests exist)
    test_files = list(Path("tests").glob("**/*.py")) if Path("tests").exists() else []
    if len(test_files) > 0:
        print(f"✅ Task 12: Testing suite available ({len(test_files)} test files)")
        features_available += 1
    else:
        print("❌ Task 12: Testing suite missing")
        features_missing += 1
    
    # Test Task 13: CLI interface
    if Path("inventag_cli.py").exists():
        print("✅ Task 13: CLI interface available")
        features_available += 1
    else:
        print("❌ Task 13: CLI interface missing")
        features_missing += 1
    
    # Test Task 14: Integration (check if BOM generation is in compliance checker)
    try:
        from inventag.compliance import ComprehensiveTagComplianceChecker
        checker = ComprehensiveTagComplianceChecker()
        if hasattr(checker, 'generate_bom_documents'):
            print("✅ Task 14: Workflow integration available")
            features_available += 1
        else:
            print("❌ Task 14: BOM integration missing")
            features_missing += 1
    except Exception:
        print("❌ Task 14: Integration test failed")
        features_missing += 1
    
    print(f"\n📊 Feature Completeness Results:")
    print(f"   ✅ Features Available: {features_available}")
    print(f"   ❌ Features Missing: {features_missing}")
    print(f"   📈 Completeness: {(features_available/(features_available+features_missing)*100):.1f}%")
    
    return features_missing == 0

if __name__ == "__main__":
    print("InvenTag Comprehensive Backward Compatibility Test")
    print("Testing all features from Tasks 1-14")
    print("=" * 60)
    
    # Run backward compatibility tests
    compatibility_ok = test_original_interfaces()
    
    # Run feature completeness tests
    features_ok = test_feature_completeness()
    
    # Final summary
    print("\n" + "=" * 60)
    print("🏁 FINAL RESULTS:")
    
    if compatibility_ok and features_ok:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Full backward compatibility maintained")
        print("✅ All features from tasks 1-14 are available")
        print("✅ No breaking changes detected")
        exit(0)
    else:
        print("⚠️  ISSUES DETECTED:")
        if not compatibility_ok:
            print("❌ Backward compatibility issues found")
        if not features_ok:
            print("❌ Some features are missing or incomplete")
        exit(1)