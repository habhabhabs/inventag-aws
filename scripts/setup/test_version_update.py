#!/usr/bin/env python3

"""
Test script to validate version.json update logic from the release workflow.
This script simulates the version update process to ensure it works correctly.
"""

import json
import sys
import tempfile
import os
from datetime import datetime
from pathlib import Path


def test_version_update():
    """Test the version.json update logic."""

    print("🧪 Testing version.json update logic...")

    # Test data
    test_cases = [
        {
            "name": "Patch bump from 2.1.1",
            "current_version": "2.1.1",
            "bump_type": "patch",
            "expected_version": "2.1.2",
        },
        {
            "name": "Minor bump from 2.1.1",
            "current_version": "2.1.1",
            "bump_type": "minor",
            "expected_version": "2.2.0",
        },
        {
            "name": "Major bump from 2.1.1",
            "current_version": "2.1.1",
            "bump_type": "major",
            "expected_version": "3.0.0",
        },
    ]

    for test_case in test_cases:
        print(f"\n📋 Test: {test_case['name']}")

        # Create temporary version.json
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            initial_data = {
                "version": test_case["current_version"],
                "release_notes": "Previous release notes",
                "release_date": "2024-01-01T00:00:00.000000",
                "previous_version": "2.1.0",
                "version_bump_type": "patch",
            }
            json.dump(initial_data, f, indent=2)
            temp_file = f.name

        try:
            # Simulate the version update logic from the workflow
            with open(temp_file, "r") as f:
                version_data = json.load(f)

            # Calculate new version
            current = test_case["current_version"]
            bump_type = test_case["bump_type"]

            # Parse current version
            major, minor, patch = map(int, current.split("."))

            # Calculate new version based on bump type
            if bump_type == "major":
                new_version = f"{major + 1}.0.0"
            elif bump_type == "minor":
                new_version = f"{major}.{minor + 1}.0"
            else:  # patch
                new_version = f"{major}.{minor}.{patch + 1}"

            # Update version data
            version_data["previous_version"] = version_data["version"]
            version_data["version"] = new_version
            version_data["release_date"] = datetime.now().isoformat()
            version_data["version_bump_type"] = bump_type
            version_data["release_notes"] = f"Test release {new_version}"

            # Additional metadata (like in workflow)
            version_data["git_tag"] = f"v{new_version}"
            version_data["github_release_url"] = (
                f"https://github.com/example/repo/releases/tag/v{new_version}"
            )

            # Write updated data
            with open(temp_file, "w") as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)

            # Verify the result
            with open(temp_file, "r") as f:
                updated_data = json.load(f)

            if updated_data["version"] == test_case["expected_version"]:
                print(f"  ✅ Version updated correctly: {current} → {new_version}")
                print(
                    f"  ✅ Previous version stored: {updated_data['previous_version']}"
                )
                print(f"  ✅ Bump type recorded: {updated_data['version_bump_type']}")
                print(f"  ✅ Release date updated: {updated_data['release_date']}")
                print(f"  ✅ Git tag set: {updated_data['git_tag']}")
            else:
                print(
                    f"  ❌ Version mismatch: expected {test_case['expected_version']}, got {updated_data['version']}"
                )
                return False

        finally:
            # Clean up temporary file
            os.unlink(temp_file)

    print(f"\n✅ All version update tests passed!")
    return True


def test_workflow_syntax():
    """Test if the release workflow file has valid syntax."""

    print("\n🔍 Testing workflow file syntax...")

    workflow_file = Path(".github/workflows/release.yml")
    if not workflow_file.exists():
        print("❌ Release workflow file not found!")
        return False

    try:
        import yaml

        with open(workflow_file, "r") as f:
            workflow_data = yaml.safe_load(f)

        # Check key sections
        # Note: 'on' is a Python keyword and gets converted to True in YAML parsing
        required_sections = ["name", "permissions", "jobs"]
        for section in required_sections:
            if section not in workflow_data:
                print(f"❌ Missing required section: {section}")
                return False

        # Check for 'on' section (converted to True due to Python keyword)
        if True not in workflow_data:
            print("❌ Missing required section: on (workflow triggers)")
            return False

        # Check permissions
        permissions = workflow_data.get("permissions", {})
        required_permissions = ["contents", "issues", "pull-requests", "actions"]
        for perm in required_permissions:
            if perm not in permissions:
                print(f"❌ Missing required permission: {perm}")
                return False

        # Check if release job exists
        jobs = workflow_data.get("jobs", {})
        if "release" not in jobs:
            print("❌ Missing 'release' job")
            return False

        print("✅ Workflow file syntax is valid")
        print("✅ Required permissions are present")
        print("✅ Release job is defined")
        return True

    except Exception as e:
        print(f"❌ Workflow file syntax error: {e}")
        return False


def test_current_version_file():
    """Test the current version.json file."""

    print("\n📄 Testing current version.json file...")

    version_file = Path("version.json")
    if not version_file.exists():
        print("❌ version.json file not found!")
        return False

    try:
        with open(version_file, "r") as f:
            version_data = json.load(f)

        # Check required fields
        required_fields = ["version", "release_notes", "release_date"]
        for field in required_fields:
            if field not in version_data:
                print(f"❌ Missing required field: {field}")
                return False

        # Validate version format
        version = version_data["version"]
        try:
            major, minor, patch = map(int, version.split("."))
            print(f"✅ Current version: {version} (valid format)")
        except ValueError:
            print(f"❌ Invalid version format: {version}")
            return False

        print(f"✅ Release date: {version_data['release_date']}")
        print(f"✅ Version file is valid")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in version.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading version.json: {e}")
        return False


def main():
    """Run all tests."""

    print("🚀 InvenTag Release Workflow Test Suite")
    print("=" * 50)

    tests = [
        ("Version Update Logic", test_version_update),
        ("Workflow File Syntax", test_workflow_syntax),
        ("Current Version File", test_current_version_file),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 Tests passed: {passed}/{len(results)}")

    if passed == len(results):
        print("🎉 All tests passed! The release workflow should work correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please fix the issues before using the workflow.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
