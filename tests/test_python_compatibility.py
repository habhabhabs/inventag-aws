"""
Python version compatibility tests for InvenTag.

These tests ensure InvenTag works correctly across all supported Python versions.
"""

import sys
import pytest


class TestPythonCompatibility:
    """Test suite for Python version compatibility."""

    def test_python_version_support(self):
        """Test that we're running on a supported Python version."""
        version = sys.version_info
        assert version.major == 3, f"Python 3.x required, got {version.major}.x"
        assert version.minor >= 8, f"Python 3.8+ required, got 3.{version.minor}"

    def test_basic_imports(self):
        """Test that core InvenTag modules can be imported."""
        import inventag

        assert inventag.__name__ == "inventag"

        from inventag.core import CloudBOMGenerator

        assert CloudBOMGenerator.__name__ == "CloudBOMGenerator"

        from inventag.reporting import BOMConverter

        assert BOMConverter.__name__ == "BOMConverter"

    def test_aws_dependencies(self):
        """Test that AWS dependencies work correctly."""
        import boto3
        from botocore.exceptions import NoCredentialsError

        # Test session creation without credentials
        session = boto3.Session()
        assert session is not None

    def test_data_processing_dependencies(self):
        """Test that data processing dependencies work."""
        import openpyxl
        import yaml

        # Test Excel processing
        wb = openpyxl.Workbook()
        assert wb is not None

        # Test YAML processing
        test_data = {"test": "value"}
        yaml_str = yaml.dump(test_data)
        parsed_data = yaml.safe_load(yaml_str)
        assert parsed_data == test_data

    def test_optional_dependencies(self):
        """Test optional dependencies (Word processing)."""
        try:
            from docx import Document

            doc = Document()
            assert doc is not None
        except ImportError:
            # python-docx is optional, so this is acceptable
            pytest.skip("python-docx not available (optional dependency)")

    def test_python_version_specific_features(self):
        """Test Python version-specific language features."""
        # f-strings (Python 3.6+)
        name = "InvenTag"
        result = f"Testing {name}"
        assert result == "Testing InvenTag"

        # Type hints work (Python 3.5+)
        def test_function(x: int) -> str:
            return str(x)

        assert test_function(42) == "42"

        # Test features available in Python 3.8+
        if sys.version_info >= (3, 8):
            # Walrus operator
            test_list = [1, 2, 3, 4, 5]
            if (length := len(test_list)) > 3:
                assert length == 5

        # Test features available in Python 3.10+
        if sys.version_info >= (3, 10):
            # Pattern matching (basic test)
            test_value = "match"
            match test_value:
                case "match":
                    result = "matched"
                case _:
                    result = "not matched"
            assert result == "matched"


if __name__ == "__main__":
    pytest.main([__file__])
