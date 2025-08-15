#!/usr/bin/env python3
"""
Quick Regression Test Suite for InvenTag AWS
Validates core functionality without requiring AWS credentials or long execution times.
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime


class QuickRegressionTestRunner:
    def __init__(self):
        self.test_results = []
        self.start_time = None

    def setup(self):
        """Set up test environment."""
        print("🚀 Setting up quick regression test environment...")
        self.start_time = datetime.now()

        # Verify we're in the correct directory
        if not Path("inventag.sh").exists():
            raise Exception("Must run from InvenTag AWS root directory")

        print("✅ Environment setup complete")

    def run_command(self, cmd, description, timeout=30, expect_success=True):
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
                if result.stderr and len(result.stderr) < 1000:
                    print("Error output:")
                    print(result.stderr)

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

        # Test fallback display options
        cmd = (
            "python3 -c \"import sys; sys.path.append('.'); "
            "from inventag.cli.main import create_parser; parser = create_parser(); "
            "args = parser.parse_args(['--fallback-display=auto', '--help']); "
            "print('✓ Fallback options available')\""
        )
        self.run_command(cmd, "Fallback Display Options Available", timeout=15)

        # Test configuration validation (should work without AWS credentials)
        self.run_command(
            "python3 -m inventag.cli.main --validate-config-only",
            "Config Validation Check",
            timeout=30,
        )

    def test_core_imports(self):
        """Test that all core modules can be imported."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Core Module Imports")
        print("=" * 60)

        # Test core imports
        cmd1 = (
            'python3 -c "from inventag.core import CloudBOMGenerator, '
            "MultiAccountConfig, AccountCredentials; "
            "print('✓ Core modules imported successfully')\""
        )
        self.run_command(cmd1, "Core Module Import Test", timeout=15)

        # Test discovery imports
        cmd2 = (
            'python3 -c "from inventag.discovery import comprehensive_discovery; '
            "print('✓ Discovery modules imported successfully')\""
        )
        self.run_command(cmd2, "Discovery Module Import Test", timeout=15)

        # Test CLI imports
        cmd3 = (
            'python3 -c "from inventag.cli.main import create_parser; '
            "print('✓ CLI modules imported successfully')\""
        )
        self.run_command(cmd3, "CLI Module Import Test", timeout=15)

    def test_fallback_logic(self):
        """Test fallback logic without AWS calls."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Fallback Logic Implementation")
        print("=" * 60)

        # Test fallback display mode logic
        # Test fallback display mode logic using a temporary file
        test_script_content = """
import sys
sys.path.append(".")
from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

# Test fallback mode initialization
try:
    discovery = ComprehensiveAWSDiscovery("fake-account", fallback_display_mode="auto")
    assert discovery.fallback_display_mode == "auto"
    print("Auto mode initialization works")

    discovery_always = ComprehensiveAWSDiscovery("fake-account", fallback_display_mode="always")
    assert discovery_always.fallback_display_mode == "always"
    print("Always mode initialization works")

    discovery_never = ComprehensiveAWSDiscovery("fake-account", fallback_display_mode="never")
    assert discovery_never.fallback_display_mode == "never"
    print("Never mode initialization works")

    print("All fallback modes working correctly")
except Exception as e:
    print(f"Fallback logic test failed: {e}")
    sys.exit(1)
"""

        # Write test script to temporary file to avoid quoting issues
        with open("/tmp/fallback_test.py", "w") as f:
            f.write(test_script_content)

        self.run_command(
            "python3 /tmp/fallback_test.py",
            "Fallback Logic Implementation Test",
            timeout=15,
        )

    def test_aws_templates(self):
        """Test AWS Prescriptive Guidance templates exist."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: AWS Prescriptive Guidance Templates")
        print("=" * 60)

        # Check template files exist
        self.run_command(
            "ls -la config/aws-prescriptive-guidance/",
            "AWS Template Files Check",
            timeout=10,
        )

        # Validate template YAML syntax
        cmd1 = (
            'python3 -c "import yaml; '
            "data = yaml.safe_load(open('config/aws-prescriptive-guidance/tag-mappings.yaml')); "
            "print(f'✓ Tag mappings YAML valid with {len(data)} sections')\""
        )
        self.run_command(cmd1, "Tag Mappings YAML Validation", timeout=10)

        cmd2 = (
            'python3 -c "import yaml; '
            "data = yaml.safe_load("
            "open('config/aws-prescriptive-guidance/service-descriptions.yaml')); "
            "print(f'Service descriptions valid with {len(data)} services')\""
        )
        self.run_command(cmd2, "Service Descriptions YAML Validation", timeout=10)

    def test_documentation_completeness(self):
        """Test documentation files are complete."""
        print("\n" + "=" * 60)
        print("🧪 TESTING: Documentation Completeness")
        print("=" * 60)

        # Check key documentation files
        key_docs = [
            "docs/development/regression-testing.md",
            "docs/advanced/fallback-mechanism.md",
            "docs/development/deprecation-roadmap.md",
            "docs/user-guides/cli-user-guide.md",
            "README.md",
        ]

        for doc_file in key_docs:
            self.run_command(
                f"test -f {doc_file} && echo '✓ {doc_file} exists'",
                f"Documentation Check: {doc_file}",
                timeout=5,
            )

    def generate_report(self):
        """Generate final test report."""
        print("\n" + "=" * 80)
        print("📊 QUICK REGRESSION TEST REPORT")
        print("=" * 80)

        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t["success"]])
        failed_tests = total_tests - passed_tests

        total_time = (datetime.now() - self.start_time).total_seconds()

        print(f"🕐 Test Duration: {total_time:.1f} seconds")
        print(f"📋 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for test in self.test_results:
                if not test["success"]:
                    print(f"   • {test['test']}")
                    if "error" in test:
                        print(f"     Error: {test['error']}")
                    elif test.get("return_code", 0) != 0:
                        print(f"     Exit Code: {test['return_code']}")

        return failed_tests == 0

    def run_all_tests(self):
        """Run all quick regression tests."""
        try:
            self.setup()

            # Core functionality tests (no AWS required)
            self.test_cli_help_and_validation()
            self.test_core_imports()
            self.test_fallback_logic()
            self.test_aws_templates()
            self.test_documentation_completeness()

            # Generate final report
            success = self.generate_report()

            return success

        except KeyboardInterrupt:
            print("\n🛑 Tests interrupted by user")
            return False
        except Exception as e:
            print(f"\n💥 Test runner error: {e}")
            return False


if __name__ == "__main__":
    print("🧪 InvenTag AWS - Quick Regression Test Suite")
    print("=" * 60)

    runner = QuickRegressionTestRunner()
    success = runner.run_all_tests()

    if success:
        print("\n🎉 All quick regression tests PASSED!")
        sys.exit(0)
    else:
        print("\n💥 Some quick regression tests FAILED!")
        sys.exit(1)
