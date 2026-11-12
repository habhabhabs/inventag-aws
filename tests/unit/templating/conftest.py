import json
from pathlib import Path

import pytest

from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry

HERE = Path(__file__).parent


@pytest.fixture
def sample_resources():
    """Sample data captured from an offline run against moto (mocked AWS)."""
    return json.loads((HERE / "sample_resources.json").read_text())["resources"]


@pytest.fixture
def user_dir(tmp_path):
    path = tmp_path / "user-templates"
    path.mkdir()
    return path


@pytest.fixture
def registry(user_dir):
    """Registry that only sees ``user_dir`` and the built-in templates."""
    return TemplateRegistry(
        [SearchDir("user", user_dir), SearchDir("builtin", BUILTIN_DIR)]
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
