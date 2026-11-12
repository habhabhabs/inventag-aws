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
        from inventag import MIN_PYTHON

        assert MIN_PYTHON == (3, 11)
        assert sys.version_info >= MIN_PYTHON, (
            f"Python 3.11+ required, got {sys.version_info.major}.{sys.version_info.minor}"
        )

    @pytest.mark.parametrize("old_version", [(2, 7, 18), (3, 8, 20), (3, 10, 14)])
    def test_package_refuses_unsupported_python(self, old_version):
        """Importing the package on an old Python fails with a plain message."""
        from inventag._python_version import (
            check_python_version,
            unsupported_python_message,
        )

        message = unsupported_python_message(old_version)
        assert "requires Python 3.11 or later" in message
        assert f"Python {old_version[0]}.{old_version[1]}" in message
        with pytest.raises(ImportError, match="requires Python 3.11 or later"):
            check_python_version(old_version)

    @pytest.mark.parametrize("version", [(3, 11, 0), (3, 12, 3), (3, 13, 18), (3, 14, 0)])
    def test_package_accepts_supported_python(self, version):
        from inventag._python_version import (
            check_python_version,
            unsupported_python_message,
        )

        assert unsupported_python_message(version) is None
        check_python_version(version)  # does not raise

    def test_cli_entry_point_exits_on_unsupported_python(self, repo_root):
        """inventag_cli.py exits with a message (not a traceback) on Python < 3.11."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "inventag_cli_under_test", repo_root / "inventag_cli.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # importing must not start the CLI

        with pytest.raises(SystemExit) as excinfo:
            module.require_supported_python((3, 10, 14))
        message = str(excinfo.value)
        assert "requires Python 3.11 or later" in message
        assert "Python 3.10" in message
        assert "Traceback" not in message

        module.require_supported_python((3, 11, 0))  # does not exit
        module.require_supported_python()  # the interpreter running the tests

    def test_version_check_modules_parse_on_old_python(self, repo_root):
        """The two files that carry the check must not use newer syntax.

        An f-string or annotation there would raise SyntaxError on the very
        interpreters the message is meant for.
        """
        import ast

        for relative in ("inventag_cli.py", "inventag/_python_version.py"):
            tree = ast.parse((repo_root / relative).read_text())
            for node in ast.walk(tree):
                assert not isinstance(node, ast.JoinedStr), f"f-string in {relative}"
                assert not isinstance(node, ast.AnnAssign), f"annotation in {relative}"
                if isinstance(node, ast.FunctionDef):
                    assert node.returns is None, f"annotation in {relative}"
                    for arg in node.args.args + node.args.kwonlyargs:
                        assert arg.annotation is None, f"annotation in {relative}"

    def test_launchers_require_python_311(self, repo_root):
        """The wrapper scripts check for the same minimum version."""
        for name in ("inventag.sh", "inventag.bat"):
            text = (repo_root / name).read_text()
            assert "sys.version_info >= (3, 11)" in text
            assert "(3, 8)" not in text
            assert "Python 3.11 or later" in text

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

        # Walrus operator (3.8+)
        test_list = [1, 2, 3, 4, 5]
        if (length := len(test_list)) > 3:
            assert length == 5

        # Pattern matching (3.10+)
        test_value = "match"
        match test_value:
            case "match":
                result = "matched"
            case _:
                result = "not matched"
        assert result == "matched"

        # Features of the minimum supported version (3.11)
        import tomllib
        from datetime import UTC, datetime

        assert tomllib.loads('minimum = "3.11"') == {"minimum": "3.11"}
        assert datetime.now(UTC).utcoffset().total_seconds() == 0
        with pytest.raises(ExceptionGroup) as excinfo:
            raise ExceptionGroup("discovery", [ValueError("us-east-1")])
        assert excinfo.group_contains(ValueError)


if __name__ == "__main__":
    pytest.main([__file__])
