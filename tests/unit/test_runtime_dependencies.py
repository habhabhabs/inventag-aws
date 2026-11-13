"""Runtime imports are declared as dependencies.

CI installs requirements-dev.txt as well, and moto pulls jsonschema in, so a
missing runtime dependency does not show up as an ImportError in the tests.
pyproject.toml reads its dependencies from requirements.txt.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _declared():
    names = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(re.split(r"[<>=!~\[ ;]", line, maxsplit=1)[0].lower())
    return names


def test_pyproject_reads_dependencies_from_requirements():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dependencies = { file = ["requirements.txt"] }' in text


def test_jsonschema_is_a_declared_dependency():
    assert "jsonschema" in _declared()


def test_config_schema_validation_runs():
    from inventag.reporting.configuration_manager import (
        JSONSCHEMA_AVAILABLE,
        ConfigurationValidator,
    )

    assert JSONSCHEMA_AVAILABLE
    errors = ConfigurationValidator().validate_branding_config({"company_name": 3})
    assert any("not of type 'string'" in e for e in errors)
    assert not any("not available" in e for e in errors)
