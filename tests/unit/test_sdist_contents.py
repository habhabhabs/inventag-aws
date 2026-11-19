"""What an sdist or wheel of the package holds (T-08, the security review's "not checked").

``python -m build`` and setuptools are not in the development environment, so the
archive itself is not built here: ``test_a_built_sdist_holds_the_package_data``
builds it where ``build`` is installed and is skipped elsewhere. The other tests
read ``pyproject.toml`` and the tree, which decide what the archive holds:

* every directory of ``inventag/`` with Python files is a package (has ``__init__.py``),
  so ``packages.find`` ships it;
* every file in ``inventag/`` that is not Python matches a ``package-data`` pattern,
  so the built-in templates are not left out;
* the files the metadata reads (``requirements.txt``, ``README.md``, ``LICENSE``,
  ``inventag/_version.py``) exist;
* no key, certificate or environment file is inside the package.
"""

import fnmatch
import importlib.util
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "inventag"
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())


def _package_files():
    return sorted(
        path
        for path in PACKAGE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def test_every_directory_with_python_files_is_a_package():
    missing = [
        str(path.relative_to(ROOT))
        for path in [PACKAGE, *PACKAGE.rglob("*")]
        if path.is_dir()
        and "__pycache__" not in path.parts
        and any(path.glob("*.py"))
        and not (path / "__init__.py").is_file()
    ]
    assert missing == []


def test_packages_find_takes_the_inventag_tree():
    find = PYPROJECT["tool"]["setuptools"]["packages"]["find"]
    assert find["include"] == ["inventag*"]
    assert "exclude" not in find


def test_every_non_python_file_in_the_package_matches_a_package_data_pattern():
    patterns = PYPROJECT["tool"]["setuptools"]["package-data"]["inventag"]
    left_out = []
    for path in _package_files():
        if path.suffix == ".py":
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        if not any(
            fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(relative, pattern[3:])
            for pattern in patterns
        ):
            left_out.append(relative)
    assert left_out == []


def test_the_built_in_templates_are_package_data():
    names = {p.name for p in (PACKAGE / "templating" / "builtin").glob("*.yaml")}
    assert {"standard-bom.yaml", "org-multi-account.yaml", "ci-pipeline.yaml"} <= names
    assert "**/*.yaml" in PYPROJECT["tool"]["setuptools"]["package-data"]["inventag"]


def test_the_files_the_metadata_reads_exist():
    dynamic = PYPROJECT["tool"]["setuptools"]["dynamic"]
    assert dynamic["dependencies"] == {"file": ["requirements.txt"]}
    assert dynamic["version"] == {"attr": "inventag._version.__version__"}
    assert (ROOT / "requirements.txt").is_file()
    assert (ROOT / PYPROJECT["project"]["readme"]).is_file()
    for name in PYPROJECT["project"]["license-files"]:
        assert (ROOT / name).is_file(), name
    assert (PACKAGE / "_version.py").is_file()


def test_no_key_certificate_or_environment_file_is_inside_the_package():
    suspicious = [
        path.relative_to(ROOT).as_posix()
        for path in _package_files()
        if path.suffix in {".pem", ".key", ".p12", ".pfx", ".crt"}
        or path.name.startswith(".env")
        or path.name in {"credentials", "credentials.json", "id_rsa"}
    ]
    assert suspicious == []


def test_the_console_script_points_at_a_real_function():
    target = PYPROJECT["project"]["scripts"]["inventag"]
    module, _, function = target.partition(":")
    assert (ROOT / (module.replace(".", "/") + ".py")).is_file()
    source = (ROOT / (module.replace(".", "/") + ".py")).read_text()
    assert f"def {function}(" in source


@pytest.mark.skipif(
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("setuptools") is None,
    reason="python -m build and setuptools are not installed here",
)
def test_a_built_sdist_holds_the_package_data(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--no-isolation",
            "--outdir",
            str(tmp_path),
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    (archive,) = tmp_path.glob("*.tar.gz")
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert any(
        n.endswith("inventag/templating/builtin/org-multi-account.yaml") for n in names
    )
    assert any(n.endswith("/requirements.txt") for n in names)
    assert not [n for n in names if n.rsplit("/", 1)[-1].startswith(".env")]
