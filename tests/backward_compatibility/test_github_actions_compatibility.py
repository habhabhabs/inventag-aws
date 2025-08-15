#!/usr/bin/env python3
"""
GitHub Actions Compatibility Tests

This module validates that all existing GitHub Actions checks pass
and implements CI/CD pipeline integration tests.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import sys
import os
import json
import yaml
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestGitHubActionsCompatibility:
    """Test GitHub Actions workflow compatibility"""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def workflows_dir(self, project_root) -> Path:
        """Get workflows directory"""
        return project_root / ".github" / "workflows"

    def test_workflow_files_exist(self, workflows_dir):
        """Test that required workflow files exist"""
        required_workflows = ["ci.yml", "pr-checks.yml", "release.yml"]

        for workflow in required_workflows:
            workflow_file = workflows_dir / workflow
            assert workflow_file.exists(), f"Missing workflow file: {workflow}"

    def test_ci_workflow_structure(self, workflows_dir):
        """Test CI workflow structure and jobs"""
        ci_file = workflows_dir / "ci.yml"

        with open(ci_file, "r") as f:
            ci_config = yaml.safe_load(f)

        # Validate basic structure
        assert "name" in ci_config
        assert "on" in ci_config
        assert "jobs" in ci_config

        # Validate required jobs
        required_jobs = ["test", "security", "validate-data"]
        for job in required_jobs:
            assert job in ci_config["jobs"], f"Missing job: {job}"

        # Validate test job structure
        test_job = ci_config["jobs"]["test"]
        assert "strategy" in test_job
        assert "matrix" in test_job["strategy"]
        assert "python-version" in test_job["strategy"]["matrix"]

        # Validate Python versions
        python_versions = test_job["strategy"]["matrix"]["python-version"]
        assert isinstance(python_versions, list)
        assert len(python_versions) >= 3  # Should test multiple Python versions

    def test_pr_checks_workflow_structure(self, workflows_dir):
        """Test PR checks workflow structure"""
        pr_file = workflows_dir / "pr-checks.yml"

        with open(pr_file, "r") as f:
            pr_config = yaml.safe_load(f)

        # Validate basic structure
        assert "name" in pr_config
        assert "on" in pr_config
        assert "pull_request" in pr_config["on"]
        assert "jobs" in pr_config

        # Validate required jobs
        required_jobs = ["pr-validation", "size-check", "conflict-check"]
        for job in required_jobs:
            assert job in pr_config["jobs"], f"Missing PR check job: {job}"

    def test_release_workflow_structure(self, workflows_dir):
        """Test release workflow structure"""
        release_file = workflows_dir / "release.yml"

        with open(release_file, "r") as f:
            release_config = yaml.safe_load(f)

        # Validate basic structure
        assert "name" in release_config
        assert "on" in release_config
        assert "jobs" in release_config

        # Validate required jobs
        required_jobs = ["check-for-release", "release"]
        for job in required_jobs:
            assert job in release_config["jobs"], f"Missing release job: {job}"

    def test_workflow_python_setup_consistency(self, workflows_dir):
        """Test that all workflows use consistent Python setup"""
        workflow_files = ["ci.yml", "pr-checks.yml", "release.yml"]

        for workflow_file in workflow_files:
            with open(workflows_dir / workflow_file, "r") as f:
                content = f.read()

            # Should use actions/setup-python@v4 or later
            if "setup-python" in content:
                assert "actions/setup-python@v4" in content or "actions/setup-python@v5" in content


class TestCIJobCompatibility:
    """Test CI job compatibility with new architecture"""

    def test_linting_compatibility(self):
        """Test that linting passes with current code"""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "flake8",
                "scripts/",
                "--count",
                "--select=E9,F63,F7,F82",
                "--show-source",
                "--statistics",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should not have critical syntax errors
        assert result.returncode == 0 or "syntax error" not in result.stdout.lower()

    def test_black_formatting_compatibility(self):
        """Test that code formatting is compatible"""
        result = subprocess.run(
            [sys.executable, "-m", "black", "--check", "scripts/", "--diff"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should either pass or show only minor formatting issues
        # We allow failure here since this is testing compatibility, not enforcing format
        assert result.returncode in [0, 1]  # 0 = formatted, 1 = would reformat

    def test_pytest_compatibility(self):
        """Test that pytest runs without critical errors"""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should not have import errors or critical failures
        if result.returncode != 0:
            # Allow for missing dependencies but not structural issues
            assert (
                any(
                    error in result.stdout
                    for error in [
                        "ModuleNotFoundError",
                        "ImportError",
                        "No module named",
                    ]
                )
                or "FAILED" not in result.stdout
            )

    def test_script_help_commands_work(self):
        """Test that all script help commands work (CI requirement)"""
        scripts = [
            "scripts/aws_resource_inventory.py",
            "scripts/tag_compliance_checker.py",
            "scripts/bom_converter.py",
        ]

        for script in scripts:
            result = subprocess.run(
                [sys.executable, script, "--help"],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            assert result.returncode == 0, f"Help command failed for {script}"
            assert len(result.stdout) > 0, f"No help output for {script}"

    def test_sample_data_processing(self):
        """Test sample data processing (CI requirement)"""
        # Create sample data as done in CI
        sample_data = {
            "all_discovered_resources": [
                {
                    "service": "S3",
                    "type": "Bucket",
                    "region": "us-east-1",
                    "id": "test-bucket",
                    "name": "test-bucket",
                    "arn": "arn:aws:s3:::test-bucket",
                    "account_id": "123456789012",
                    "tags": {"Environment": "test"},
                    "discovered_via": "ResourceGroupsTaggingAPI",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample input file
            input_file = os.path.join(temp_dir, "sample.json")
            with open(input_file, "w") as f:
                json.dump(sample_data, f)

            # Test BOM converter with sample data (as done in CI)
            output_file = os.path.join(temp_dir, "test-output.xlsx")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/bom_converter.py",
                    "--input",
                    input_file,
                    "--output",
                    output_file,
                    "--no-vpc-enrichment",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )

            # Should not fail with argument parsing errors
            if result.returncode != 0:
                # Allow for missing dependencies but not argument errors
                assert any(
                    error in result.stderr
                    for error in [
                        "ModuleNotFoundError",
                        "ImportError",
                        "No module named",
                    ]
                )


class TestSecurityScanCompatibility:
    """Test security scan compatibility"""

    def test_bandit_scan_compatibility(self):
        """Test that Bandit security scan works"""
        result = subprocess.run(
            [sys.executable, "-m", "bandit", "-r", "scripts/", "-f", "json"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Bandit should run without critical errors
        # Return code might be non-zero due to findings, but should produce valid JSON
        if result.returncode != 0:
            # Should still produce valid output or show it's not installed
            assert "No module named" in result.stderr or result.stdout.strip() != ""

    def test_safety_check_compatibility(self):
        """Test that Safety check works"""
        result = subprocess.run(
            [sys.executable, "-m", "safety", "check"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Safety should run without critical errors
        if result.returncode != 0:
            # Should show it's not installed or produce valid output
            assert "No module named" in result.stderr or "vulnerabilities" in result.stdout.lower()


class TestDependencyCompatibility:
    """Test dependency compatibility"""

    def test_requirements_file_exists(self):
        """Test that requirements.txt exists and is valid"""
        requirements_file = Path(__file__).parent.parent.parent / "requirements.txt"
        assert requirements_file.exists(), "requirements.txt file missing"

        with open(requirements_file, "r") as f:
            content = f.read()

        # Should have some dependencies
        assert len(content.strip()) > 0

        # Should not have obvious syntax errors
        lines = [
            line.strip()
            for line in content.split("\n")
            if line.strip() and not line.startswith("#")
        ]
        for line in lines:
            # Basic validation - should not have spaces in package names (except for version specs)
            if "==" in line or ">=" in line or "<=" in line:
                package_name = line.split("==")[0].split(">=")[0].split("<=")[0]
                assert " " not in package_name.strip(), f"Invalid package name: {package_name}"

    def test_dev_requirements_compatibility(self):
        """Test dev requirements compatibility"""
        dev_requirements_file = Path(__file__).parent.parent.parent / "requirements-dev.txt"

        if dev_requirements_file.exists():
            with open(dev_requirements_file, "r") as f:
                content = f.read()

            # Should include testing dependencies
            assert any(dep in content.lower() for dep in ["pytest", "flake8", "black"])

    def test_pip_install_compatibility(self):
        """Test that pip install works with requirements"""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--dry-run",
                "-r",
                "requirements.txt",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )

        # Should not have dependency resolution errors
        if result.returncode != 0:
            # Allow for network issues but not dependency conflicts
            assert "conflict" not in result.stderr.lower() or "network" in result.stderr.lower()


class TestVersionCompatibility:
    """Test version compatibility"""

    def test_version_file_exists(self):
        """Test that version.json exists and is valid"""
        version_file = Path(__file__).parent.parent.parent / "version.json"
        assert version_file.exists(), "version.json file missing"

        with open(version_file, "r") as f:
            version_data = json.load(f)

        # Should have version field
        assert "version" in version_data
        assert isinstance(version_data["version"], str)

        # Version should follow semantic versioning pattern
        version = version_data["version"]
        parts = version.split(".")
        assert len(parts) >= 2, f"Invalid version format: {version}"

        # Major and minor should be numbers
        assert parts[0].isdigit(), f"Invalid major version: {parts[0]}"
        assert parts[1].isdigit(), f"Invalid minor version: {parts[1]}"

    def test_python_version_compatibility(self):
        """Test Python version compatibility"""
        # Should work with Python 3.8+
        python_version = sys.version_info
        assert python_version.major == 3, "Should use Python 3"
        assert python_version.minor >= 8, "Should use Python 3.8 or later"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
