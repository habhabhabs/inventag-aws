"""Read a settings file (YAML or JSON) and apply it to ``BOMProcessingConfig``.

Used for files such as ``--bom-config``. Every problem is a
:class:`SettingsFileError` whose message names the file, and the line or key
when there is one, so the command line can print it as it is.

What it does that plain ``yaml.safe_load`` / ``json.load`` do not:

* reads UTF-8 on every system, with or without a byte order mark;
* refuses a key that is written twice in one mapping (the last one would win
  without a word);
* says "empty" for an empty file, and what it found for a file whose top level
  is not a mapping;
* limits the file size;
* names the key and the expected type when a value has the wrong type.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from ..discovery.cost_analyzer import CostThresholds
from .bom_processor import BOMProcessingConfig
from .report_template import _UniqueKeyLoader, _no_duplicate_keys

MAX_SETTINGS_BYTES = 1024 * 1024
SETTINGS_SUFFIXES = (".json", ".yaml", ".yml")


class SettingsFileError(ValueError):
    """A settings file cannot be read or has a wrong value."""


def load_settings_file(
    path: Any, what: str = "settings file", max_bytes: int = MAX_SETTINGS_BYTES
) -> Dict[str, Any]:
    """Return the mapping in a ``.json``, ``.yaml`` or ``.yml`` file.

    A file without a suffix is read as JSON when it starts with ``{`` and as
    YAML otherwise. Any other suffix is refused.
    """
    source = str(path)
    if not isinstance(path, (str, Path)) or not source or "\x00" in source:
        raise SettingsFileError(f"{what}: the path is not valid")
    file_path = Path(source).expanduser()
    suffix = file_path.suffix.lower()
    if suffix and suffix not in SETTINGS_SUFFIXES:
        raise SettingsFileError(
            f"{what} {source}: unsupported file type '{file_path.suffix}'. Use "
            ".json, .yaml or .yml"
        )
    try:
        if not file_path.is_file():
            raise SettingsFileError(
                f"{what} {source}: file not found, or not a regular file"
            )
        size = file_path.stat().st_size
        if size > max_bytes:
            raise SettingsFileError(
                f"{what} {source}: the file is {size} bytes; the maximum is "
                f"{max_bytes} bytes"
            )
        raw = file_path.read_bytes()
    except OSError as error:
        raise SettingsFileError(
            f"{what} {source}: cannot read the file: {error.strerror or error}"
        ) from None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SettingsFileError(
            f"{what} {source}: the file is not UTF-8 text"
        ) from None

    as_json = suffix == ".json" or (not suffix and text.lstrip().startswith("{"))
    try:
        if as_json:
            data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
        else:
            data = yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader
    except json.JSONDecodeError as error:
        raise SettingsFileError(
            f"{what} {source}:{error.lineno}: invalid JSON: {error.msg} "
            f"(column {error.colno})"
        ) from None
    except ValueError as error:  # a key written twice in a JSON file
        raise SettingsFileError(f"{what} {source}: {error}") from None
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f":{mark.line + 1}" if mark is not None else ""
        problem = getattr(error, "problem", None) or "not valid YAML"
        raise SettingsFileError(f"{what} {source}{where}: {problem}") from None
    except RecursionError:
        raise SettingsFileError(f"{what} {source}: nested too deeply") from None

    if data is None:
        raise SettingsFileError(f"{what} {source}: the file is empty")
    if not isinstance(data, dict):
        found = {list: "a list", str: "text"}.get(type(data), type(data).__name__)
        raise SettingsFileError(
            f"{what} {source}: the top level must be a mapping of "
            f"key: value pairs, but the file holds {found}"
        )
    return data


class Locator:
    """Say where a key is in a settings file: ``file:line: key``.

    One helper for every configuration file the command line reads (accounts
    file, tag mappings, service descriptions, ``--bom-config``), so each of
    them prints a problem as ``file:line: key: problem``. A key is a path of
    mapping keys and list positions, for example ``("accounts", 1,
    "account_id")``, shown as ``accounts[1].account_id``. When the key is
    missing the line is the one of the closest part that exists.
    """

    def __init__(self, source: Any, text: Optional[str] = None):
        self.source = str(source)
        self._root: Optional[yaml.Node] = None
        if text is None:
            try:
                text = Path(self.source).expanduser().read_bytes().decode("utf-8-sig")
            except (OSError, UnicodeDecodeError):
                text = ""
        try:
            self._root = yaml.compose(text, Loader=yaml.SafeLoader)
        except yaml.YAMLError:
            self._root = None

    @staticmethod
    def key_text(path: Any) -> str:
        out = ""
        for part in path:
            if isinstance(part, int):
                out += f"[{part}]"
            else:
                out += f".{part}" if out else str(part)
        return out

    def line(self, path: Any) -> Optional[int]:
        node = self._root
        if node is None:
            return None
        line = node.start_mark.line + 1
        for part in path:
            if isinstance(node, yaml.MappingNode):
                found = None
                for key_node, value_node in node.value:
                    if getattr(key_node, "value", None) == part:
                        found = (key_node, value_node)
                        break
                if found is None:
                    break
                line = found[0].start_mark.line + 1
                node = found[1]
            elif isinstance(node, yaml.SequenceNode) and isinstance(part, int):
                if not 0 <= part < len(node.value):
                    break
                node = node.value[part]
                line = node.start_mark.line + 1
            else:
                break
        return line

    def where(self, path: Any) -> str:
        line = self.line(path)
        at = f"{self.source}:{line}" if line else self.source
        key = self.key_text(path)
        return f"{at}: {key}" if key else at

    def message(self, path: Any, problem: str) -> str:
        return f"{self.where(path)}: {problem}"


def did_you_mean(name: Any, known: Any) -> str:
    """``; did you mean 'x'?`` for the closest known name, or an empty string."""
    import difflib

    close = difflib.get_close_matches(str(name), sorted(known), n=1, cutoff=0.6)
    return f"; did you mean '{close[0]}'?" if close else ""


_BOOL_FIELDS = (
    "enable_network_analysis",
    "enable_security_analysis",
    "enable_service_enrichment",
    "enable_service_descriptions",
    "enable_tag_mapping",
    "enable_cost_analysis",
    "enable_parallel_processing",
    "cache_results",
)
_INT_FIELDS = ("max_worker_threads", "processing_timeout")
_PATH_FIELDS = ("service_descriptions_config", "tag_mappings_config")
_DECIMAL_THRESHOLDS = (
    "expensive_resource_monthly_threshold",
    "high_cost_alert_threshold",
)
_INT_THRESHOLDS = ("forgotten_resource_days_threshold",)
_FLOAT_THRESHOLDS = (
    "cost_trend_alert_percentage",
    "unused_resource_utilization_threshold",
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _cost_thresholds(value: Any, source: str) -> CostThresholds:
    if not isinstance(value, dict):
        raise SettingsFileError(
            f"{source}: cost_thresholds must be a mapping of threshold names to "
            "numbers"
        )
    known = set(_DECIMAL_THRESHOLDS + _INT_THRESHOLDS + _FLOAT_THRESHOLDS)
    unknown = sorted(str(k) for k in value if k not in known)
    if unknown:
        raise SettingsFileError(
            f"{source}: cost_thresholds: unknown key(s) {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(known))}"
        )
    values: Dict[str, Any] = {}
    for key, item in value.items():
        if not _is_number(item) or item < 0:
            raise SettingsFileError(
                f"{source}: cost_thresholds.{key} must be a number of zero or more"
            )
        if key in _DECIMAL_THRESHOLDS:
            try:
                values[key] = Decimal(str(item))
            except InvalidOperation:
                raise SettingsFileError(
                    f"{source}: cost_thresholds.{key} is not a valid number"
                ) from None
        elif key in _INT_THRESHOLDS:
            if int(item) != item:
                raise SettingsFileError(
                    f"{source}: cost_thresholds.{key} must be a whole number"
                )
            values[key] = int(item)
        else:
            values[key] = float(item)
    return CostThresholds(**values)


def apply_bom_settings(
    config: BOMProcessingConfig, settings: Mapping[str, Any], source: str = "settings"
) -> List[str]:
    """Copy ``settings`` onto ``config`` and return the keys that were ignored.

    Raises :class:`SettingsFileError` naming the key when a value has the wrong
    type, before anything is changed.
    """
    valid = set(_BOOL_FIELDS + _INT_FIELDS + _PATH_FIELDS + ("cost_thresholds",))
    ignored = sorted(str(k) for k in settings if k not in valid)
    updates: Dict[str, Any] = {}
    for key, value in settings.items():
        if key not in valid:
            continue
        if key in _BOOL_FIELDS:
            if not isinstance(value, bool):
                raise SettingsFileError(
                    f"{source}: {key} must be true or false, got {value!r}"
                )
        elif key in _INT_FIELDS:
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise SettingsFileError(
                    f"{source}: {key} must be a whole number of 1 or more, "
                    f"got {value!r}"
                )
        elif key in _PATH_FIELDS:
            if value is not None and (not isinstance(value, str) or not value):
                raise SettingsFileError(
                    f"{source}: {key} must be a file path as text, got {value!r}"
                )
        elif key == "cost_thresholds" and value is not None:
            value = _cost_thresholds(value, source)
        updates[key] = value
    for key, value in updates.items():
        setattr(config, key, value)
    return ignored


def valid_bom_setting_names() -> List[str]:
    """The keys ``apply_bom_settings`` accepts."""
    return sorted(_BOOL_FIELDS + _INT_FIELDS + _PATH_FIELDS + ("cost_thresholds",))


def read_bom_settings(
    path: Any, config: BOMProcessingConfig, what: str = "--bom-config"
) -> Optional[List[str]]:
    """Load ``path`` and apply it to ``config``; return the ignored keys."""
    return apply_bom_settings(config, load_settings_file(path, what), f"{what} {path}")
