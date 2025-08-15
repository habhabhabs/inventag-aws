#!/usr/bin/env python3
"""
Comprehensive Regression Test Suite for InvenTag AWS
Tests full functionality including BOM generation, discovery, compliance, etc.
"""

import os
import sys
import json
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime


class RegressionTestRunner:
    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        self.start_time = None

    def setup(self):
        """Set up test environment."""
        print("🚀 Setting up regression test environment...")
        self.start_time = datetime.now()

        # Create temporary directory for test outputs
        self.temp_dir = tempfile.mkdtemp(prefix="inventag_regression_")
        print(f"📁 Test output directory: {self.temp_dir}")

        # Verify we're in the correct directory
        if not Path("inventag.sh").exists():
            raise Exception("Must run from InvenTag AWS root directory")

        print("✅ Environment setup complete")

    def cleanup(self):
        """Clean up test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")

    def run_command(self, cmd, description, timeout=300, expect_success=True):
        """Run a command and capture results."""
        print(f"\n📋 {description}")
        print(f"🔧 Command: {cmd}")

        test_start = time.time()

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )

            duration = time.time() - test_start

            success = (
                (result.returncode == 0) if expect_success else (result.returncode != 0)
            )

            test_result = {
                "test": description,
                "command": cmd,
                "success": success,
                "duration": duration,
                "return_code": result.returncode,
                "stdout_lines": len(result.stdout.splitlines()),
                "stderr_lines": len(result.stderr.splitlines()),
            }

            if success:
                print(f"✅ PASSED ({duration:.1f}s)")
                if result.stdout:
                    print(f"📊 Output: {len(result.stdout.splitlines())} lines")
            else:
                print(f"❌ FAILED ({duration:.1f}s)")
                print(f"Exit code: {result.returncode}")
                if result.stderr:
                    print("Error output:")
                    print(result.stderr[-500:])  # Last 500 chars

            self.test_results.append(test_result)
            return result

        except subprocess.TimeoutExpired:
            print(f"⏱️ TIMEOUT after {timeout}s")
            test_result = {
                "test": description,
                "command": cmd,
                "success": False,
                "duration": timeout,
                "return_code": -1,
                "error": "Timeout",
            }
            self.test_results.append(test_result)
            return None

    def test_cli_help_and_validation(self):
        """Test CLI help and basic validation."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: CLI Help and Validation")
        print("=" * 60)

        # Test CLI help
        self.run_command(
            "python3 -m inventag.cli.main --help", "CLI Help Display", timeout=30
        )

        # Test configuration validation
        self.run_command(
            "python3 -m inventag.cli.main --validate-config",
            "Configuration Validation",
            timeout=30,
        )

        # Test credential validation (may fail if no credentials)
        self.run_command(
            "python3 -m inventag.cli.main --validate-credentials --skip-credential-validation",
            "Credential Validation Check",
            timeout=30,
            expect_success=False,  # May fail if no valid credentials
        )

    def test_fallback_display_modes(self):
        """Test new fallback display modes."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Fallback Display Modes")
        print("=" * 60)

        base_cmd = f"./inventag.sh --output-directory {self.temp_dir}/fallback_test --regions us-east-1"

        # Test auto mode (default)
        self.run_command(
            f"{base_cmd} --fallback-display=auto --create-excel",
            "Fallback Display: Auto Mode",
            timeout=600,
        )

        # Test always mode
        self.run_command(
            f"{base_cmd} --fallback-display=always --create-excel",
            "Fallback Display: Always Mode",
            timeout=600,
        )

        # Test never mode
        self.run_command(
            f"{base_cmd} --fallback-display=never --create-excel",
            "Fallback Display: Never Mode",
            timeout=600,
        )

        # Test legacy compatibility
        self.run_command(
            f"{base_cmd} --hide-fallback-resources --create-excel",
            "Legacy Fallback Option Compatibility",
            timeout=600,
        )

    def test_bom_generation_formats(self):
        """Test BOM generation in different formats."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: BOM Generation Formats")
        print("=" * 60)

        base_cmd = f"./inventag.sh --output-directory {self.temp_dir}/bom_formats --regions us-east-1"

        # Test Excel generation
        self.run_command(
            f"{base_cmd} --create-excel", "BOM Generation: Excel Format", timeout=600
        )

        # Test Word generation
        self.run_command(
            f"{base_cmd} --create-word", "BOM Generation: Word Format", timeout=600
        )

        # Test both formats
        self.run_command(
            f"{base_cmd} --create-excel --create-word",
            "BOM Generation: Excel + Word Formats",
            timeout=600,
        )

    def test_aws_prescriptive_guidance_templates(self):
        """Test AWS Prescriptive Guidance templates."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: AWS Prescriptive Guidance Templates")
        print("=" * 60)

        # Test with AWS Prescriptive Guidance templates
        cmd = (
            f"./inventag.sh --output-directory {self.temp_dir}/aws_guidance "
            f"--regions us-east-1 --create-excel "
            f"--tag-mappings config/aws-prescriptive-guidance/tag-mappings.yaml "
            f"--service-descriptions config/aws-prescriptive-guidance/service-descriptions.yaml"
        )

        self.run_command(
            cmd, "AWS Prescriptive Guidance Template Integration", timeout=600
        )

        # Test with default templates for comparison
        cmd = (
            f"./inventag.sh --output-directory {self.temp_dir}/default_templates "
            f"--regions us-east-1 --create-excel "
            f"--tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml "
            f"--service-descriptions config/defaults/services/service_descriptions_example.yaml"
        )

        self.run_command(cmd, "Default Template Integration", timeout=600)

    def test_analysis_features(self):
        """Test analysis features."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Analysis Features")
        print("=" * 60)

        base_cmd = f"./inventag.sh --output-directory {self.temp_dir}/analysis --regions us-east-1"

        # Test network analysis
        self.run_command(
            f"{base_cmd} --enable-network-analysis --create-excel",
            "Network Analysis Feature",
            timeout=600,
        )

        # Test security analysis
        self.run_command(
            f"{base_cmd} --enable-security-analysis --create-excel",
            "Security Analysis Feature",
            timeout=600,
        )

        # Test cost analysis
        self.run_command(
            f"{base_cmd} --enable-cost-analysis --create-excel",
            "Cost Analysis Feature",
            timeout=600,
        )

        # Test all analyses combined
        combined_cmd = (
            f"{base_cmd} --enable-network-analysis --enable-security-analysis "
            f"--enable-cost-analysis --create-excel"
        )
        self.run_command(combined_cmd, "Combined Analysis Features", timeout=600)

    def test_production_safety_features(self):
        """Test production safety and security features."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Production Safety Features")
        print("=" * 60)

        base_cmd = f"./inventag.sh --output-directory {self.temp_dir}/safety --regions us-east-1"

        # Test production safety
        self.run_command(
            f"{base_cmd} --enable-production-safety --create-excel",
            "Production Safety Monitoring",
            timeout=600,
        )

        # Test security validation
        self.run_command(
            f"{base_cmd} --security-validation --create-excel",
            "Security Validation",
            timeout=600,
        )

        # Test combined safety features
        safety_cmd = (
            f"{base_cmd} --enable-production-safety --security-validation "
            f"--enforce-read-only --create-excel"
        )
        self.run_command(safety_cmd, "Combined Safety Features", timeout=600)

    def test_state_management(self):
        """Test state management and change detection."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: State Management")
        print("=" * 60)

        base_cmd = f"./inventag.sh --output-directory {self.temp_dir}/state --regions us-east-1"

        # First run to establish baseline state
        self.run_command(
            f"{base_cmd} --enable-state-management --create-excel",
            "State Management: Baseline Creation",
            timeout=600,
        )

        # Second run to test delta detection
        self.run_command(
            f"{base_cmd} --enable-state-management --enable-delta-detection --create-excel",
            "State Management: Delta Detection",
            timeout=600,
        )

        # Test changelog generation
        self.run_command(
            f"{base_cmd} --enable-state-management --generate-changelog --create-excel",
            "State Management: Changelog Generation",
            timeout=600,
        )

    def test_service_specific_discovery(self):
        """Test service-specific discovery."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Service-Specific Discovery")
        print("=" * 60)

        base_cmd = f"./inventag.sh --output-directory {self.temp_dir}/services --regions us-east-1"

        # Test specific services that often have resources
        services_to_test = ["ec2,s3,iam", "lambda,rds,vpc", "cloudformation,cloudtrail"]

        for services in services_to_test:
            self.run_command(
                f"{base_cmd} --services {services} --create-excel",
                f"Service Discovery: {services.upper()}",
                timeout=300,
            )

    def test_multi_region_discovery(self):
        """Test multi-region discovery."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Multi-Region Discovery")
        print("=" * 60)

        # Test multiple regions
        regions_to_test = [
            "us-east-1",
            "us-east-1,us-west-2",
            "us-east-1,eu-west-1,ap-southeast-1",
        ]

        for regions in regions_to_test:
            region_count = len(regions.split(","))
            region_cmd = (
                f"./inventag.sh --output-directory {self.temp_dir}/regions "
                f"--regions {regions} --create-excel"
            )
            self.run_command(
                region_cmd,
                f"Multi-Region Discovery: {region_count} region(s)",
                timeout=300 * region_count,  # Scale timeout with regions
            )

    def test_error_handling(self):
        """Test error handling and edge cases."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Error Handling")
        print("=" * 60)

        # Test invalid region
        self.run_command(
            "./inventag.sh --regions invalid-region --create-excel",
            "Error Handling: Invalid Region",
            timeout=60,
            expect_success=False,
        )

        # Test invalid service
        self.run_command(
            "./inventag.sh --services invalid-service --create-excel",
            "Error Handling: Invalid Service",
            timeout=60,
            expect_success=False,
        )

        # Test invalid output directory (read-only)
        self.run_command(
            "./inventag.sh --output-directory /root/readonly --create-excel",
            "Error Handling: Invalid Output Directory",
            timeout=60,
            expect_success=False,
        )

    def verify_output_files(self):
        """Verify that expected output files were created."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Output File Verification")
        print("=" * 60)

        # Check for generated files
        test_dirs = [
            "fallback_test",
            "bom_formats",
            "aws_guidance",
            "analysis",
            "safety",
            "state",
            "services",
            "regions",
        ]

        total_files = 0
        total_size = 0

        for test_dir in test_dirs:
            dir_path = Path(self.temp_dir) / test_dir
            if dir_path.exists():
                files = list(dir_path.rglob("*"))
                file_count = len([f for f in files if f.is_file()])
                dir_size = sum(f.stat().st_size for f in files if f.is_file())

                total_files += file_count
                total_size += dir_size

                print(f"📁 {test_dir}: {file_count} files, {dir_size/1024/1024:.1f} MB")

                # Check for specific file types
                excel_files = len([f for f in files if f.suffix == ".xlsx"])
                word_files = len([f for f in files if f.suffix == ".docx"])
                json_files = len([f for f in files if f.suffix == ".json"])

                if excel_files > 0:
                    print(f"   ✅ Excel files: {excel_files}")
                if word_files > 0:
                    print(f"   ✅ Word files: {word_files}")
                if json_files > 0:
                    print(f"   ✅ JSON files: {json_files}")

        print(f"\n📊 Total Output: {total_files} files, {total_size/1024/1024:.1f} MB")

        # Verify specific expected files exist
        expected_patterns = [
            "**/bom_*.xlsx",
            "**/bom_*.docx",
            "**/inventory_*.json",
            "**/state_*.json",
        ]

        for pattern in expected_patterns:
            matching_files = list(
                Path(self.temp_dir).glob(f"**/{pattern.split('/')[-1]}")
            )
            if matching_files:
                print(f"✅ Found {len(matching_files)} files matching {pattern}")
            else:
                print(f"⚠️  No files found matching {pattern}")

    def generate_report(self):
        """Generate final test report."""
        print("\n" + "=" * 80)
        print("📊 REGRESSION TEST REPORT")
        print("=" * 80)

        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t["success"]])
        failed_tests = total_tests - passed_tests

        total_time = (datetime.now() - self.start_time).total_seconds()

        print(
            f"🕐 Test Duration: {total_time:.1f} seconds ({total_time/60:.1f} minutes)"
        )
        print(f"📋 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        print("\n📊 Test Categories:")
        categories = {}
        for test in self.test_results:
            category = test["test"].split(":")[0]
            if category not in categories:
                categories[category] = {"passed": 0, "failed": 0}

            if test["success"]:
                categories[category]["passed"] += 1
            else:
                categories[category]["failed"] += 1

        for category, stats in categories.items():
            total = stats["passed"] + stats["failed"]
            success_rate = (stats["passed"] / total) * 100 if total > 0 else 0
            print(f"   {category}: {stats['passed']}/{total} ({success_rate:.1f}%)")

        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for test in self.test_results:
                if not test["success"]:
                    print(f"   • {test['test']}")
                    if "error" in test:
                        print(f"     Error: {test['error']}")
                    elif test.get("return_code", 0) != 0:
                        print(f"     Exit Code: {test['return_code']}")

        # Save detailed report
        report_file = Path(self.temp_dir) / "regression_test_report.json"
        with open(report_file, "w") as f:
            json.dump(
                {
                    "summary": {
                        "total_tests": total_tests,
                        "passed_tests": passed_tests,
                        "failed_tests": failed_tests,
                        "success_rate": (passed_tests / total_tests) * 100,
                        "total_time_seconds": total_time,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "test_results": self.test_results,
                },
                f,
                indent=2,
            )

        print(f"\n📝 Detailed report saved: {report_file}")
        print(f"📁 Test outputs saved in: {self.temp_dir}")

        return failed_tests == 0

    def run_all_tests(self):
        """Run all regression tests."""
        try:
            self.setup()

            # Core functionality tests
            self.test_cli_help_and_validation()
            self.test_fallback_display_modes()
            self.test_bom_generation_formats()
            self.test_aws_prescriptive_guidance_templates()

            # Feature tests
            self.test_analysis_features()
            self.test_production_safety_features()
            self.test_state_management()

            # Discovery tests
            self.test_service_specific_discovery()
            self.test_multi_region_discovery()

            # Error handling tests
            self.test_error_handling()

            # Verification
            self.verify_output_files()

            # Generate final report
            success = self.generate_report()

            return success

        except KeyboardInterrupt:
            print("\n🛑 Tests interrupted by user")
            return False
        except Exception as e:
            print(f"\n💥 Test runner error: {e}")
            return False
        finally:
            # Keep temp directory for analysis if tests failed
            if any(not t["success"] for t in self.test_results):
                print(f"⚠️  Keeping test outputs for analysis: {self.temp_dir}")
            else:
                self.cleanup()


if __name__ == "__main__":
    print("🧪 InvenTag AWS - Comprehensive Regression Test Suite")
    print("=" * 60)

    runner = RegressionTestRunner()
    success = runner.run_all_tests()

    if success:
        print("\n🎉 All regression tests PASSED!")
        sys.exit(0)
    else:
        print("\n💥 Some regression tests FAILED!")
        sys.exit(1)
