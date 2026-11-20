"""PyInstaller hook for the inventag package.

``inventag.compliance`` imports its modules by name (``importlib.import_module``),
so every submodule is listed. The built-in YAML and JSON files are the package
data of the wheel (``pyproject.toml``: ``**/*.json``, ``**/*.yaml``, ``**/*.yml``).
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# colorama is a declared runtime dependency (requirements.txt) that the package
# does not import; it is carried so the executable holds every declared
# dependency, as a pip install does (``inventag selftest`` imports it).
hiddenimports = collect_submodules("inventag") + ["colorama"]
datas = collect_data_files("inventag", includes=["**/*.json", "**/*.yaml", "**/*.yml"])
