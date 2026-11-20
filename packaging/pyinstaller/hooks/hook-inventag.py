"""PyInstaller hook for the inventag package.

``inventag.compliance`` imports its modules by name (``importlib.import_module``),
so every submodule is listed. The built-in YAML and JSON files are the package
data of the wheel (``pyproject.toml``: ``**/*.json``, ``**/*.yaml``, ``**/*.yml``).
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("inventag")
datas = collect_data_files("inventag", includes=["**/*.json", "**/*.yaml", "**/*.yml"])
