"""Turning resource dictionaries into table rows."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

ILLEGAL_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


EXCEL_CELL_LIMIT = 32767


def clean_text(value: str) -> str:
    """Remove control characters that Word and Excel files cannot hold."""
    return CONTROL_CHARS.sub("\ufffd", value)


def normalize_tags(tags: Any) -> Dict[str, str]:
    """Accept ``{"k": "v"}`` or ``[{"Key": "k", "Value": "v"}]`` and return a dict."""
    if isinstance(tags, dict):
        return {str(k): "" if v is None else str(v) for k, v in tags.items()}
    result: Dict[str, str] = {}
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, dict):
                key = item.get("Key", item.get("key"))
                if key is not None:
                    value = item.get("Value", item.get("value"))
                    result[str(key)] = "" if value is None else str(value)
    return result


# Types whose discovery record has no name key: the ID is the name (the
# function name, the role name, the alias). The standard report shows this
# value in its ID column; a template Name column shows it too.
_ID_IS_NAME = {("LAMBDA", "FUNCTION"), ("IAM", "ROLE"), ("KMS", "ALIAS")}


def _id_as_name(resource: Dict[str, Any]) -> Any:
    key = (
        str(resource.get("service") or "").upper(),
        str(resource.get("resource_type") or resource.get("type") or "").upper(),
    )
    if key in _ID_IS_NAME:
        return resource.get("resource_id") or resource.get("id")
    return None


def get_field(resource: Dict[str, Any], dotted: str) -> Any:
    """Read ``a.b.c`` from nested dictionaries; ``tags.X`` reads tag X."""
    if dotted.startswith("tags."):
        return normalize_tags(resource.get("tags")).get(dotted[5:])
    if dotted in resource and not (
        dotted in ("resource_name", "name") and not resource[dotted]
    ):
        return resource[dotted]
    if dotted in ("resource_name", "name"):
        fallback = _id_as_name(resource)
        if fallback:
            return fallback
        if dotted in resource:
            return resource[dotted]
    current: Any = resource
    for part in dotted.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def format_value(value: Any, field_name: str = "") -> str:
    """Render a value as plain text for a table cell."""
    if value is None:
        return ""
    if field_name == "tags" or (
        isinstance(value, list)
        and value
        and isinstance(value[0], dict)
        and "Key" in value[0]
    ):
        tags = normalize_tags(value)
        if tags or field_name == "tags":
            return ", ".join(f"{k}={v}" for k, v in sorted(tags.items()))
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, dict):
        return "; ".join(f"{k}={format_value(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return ", ".join(format_value(v) for v in value)
    text = str(value)
    return CONTROL_CHARS.sub("\ufffd", text)


def humanize(field_name: str) -> str:
    if field_name.startswith("tags."):
        return f"Tag: {field_name[5:]}"
    text = (
        field_name.split(".")[-1] if field_name.startswith("raw_data.") else field_name
    )
    text = text.replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else field_name


def flatten(resource: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in resource.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if key == "tags" and not prefix:
            for tag_key, tag_value in normalize_tags(value).items():
                out[f"tags.{tag_key}"] = tag_value
        elif isinstance(value, dict):
            out.update(flatten(value, name))
        else:
            out[name] = value
    return out


def tag_keys(resources: Iterable[Dict[str, Any]]) -> List[str]:
    keys = set()
    for resource in resources:
        keys.update(normalize_tags(resource.get("tags")).keys())
    return sorted(keys, key=lambda k: (k.lower(), k))


def build_columns(
    spec: Dict[str, Any],
    resources: List[Dict[str, Any]],
    include_all_fields: bool = False,
    columns: Optional[List[Dict[str, Any]]] = None,
    with_tags: bool = True,
) -> List[Tuple[str, str, Optional[int]]]:
    """Return ``(field, header, width)`` for a table of ``resources``."""
    chosen = columns if columns is not None else spec["columns"]
    result: List[Tuple[str, str, Optional[int]]] = []
    seen = set()
    for column in chosen:
        name = column["field"]
        if name in seen:
            continue
        seen.add(name)
        result.append(
            (name, column.get("header") or humanize(name), column.get("width"))
        )
    if with_tags:
        wanted = spec.get("tag_columns", "all")
        if wanted == "all":
            keys = tag_keys(resources)
        elif wanted == "none" or not wanted:
            keys = []
        else:
            keys = list(wanted)
        for key in keys:
            name = f"tags.{key}"
            if name not in seen:
                seen.add(name)
                result.append((name, f"Tag: {key}", None))
    if include_all_fields:
        extra = set()
        for resource in resources:
            extra.update(flatten(resource).keys())
        for name in sorted(extra - seen, key=_field_sort_key):
            if name.startswith("tags."):
                continue
            seen.add(name)
            result.append((name, name, None))
    return result


def _field_sort_key(name: str) -> Tuple[int, str]:
    return (1 if name.startswith("raw_data.") else 0, name.lower())


def unique_sheet_name(name: str, used: set) -> str:
    """Excel sheet names: max 31 chars, no []:*?/\\ and unique (case-insensitive)."""
    base = ILLEGAL_SHEET_CHARS.sub("-", name).strip("'") or "Sheet"
    base = base[:31]
    candidate = base
    counter = 2
    # "History" is kept by Excel for itself
    while candidate.lower() in used or candidate.lower() == "history":
        suffix = f" ({counter})"
        candidate = base[: 31 - len(suffix)] + suffix
        counter += 1
    used.add(candidate.lower())
    if candidate != name:
        logging.getLogger(__name__).warning(
            f"Excel sheet name '{name}' is not allowed or is already used; the "
            f"sheet is called '{candidate}'"
        )
    return candidate


def resource_sort_key(resource: Dict[str, Any]) -> Tuple[str, ...]:
    """Stable order: service, type, name, ID, account, region."""
    keys = (
        "service",
        "resource_type",
        "resource_name",
        "resource_id",
        "source_account_id",
        "region",
    )
    return tuple(str(resource.get(k) or "").lower() for k in keys)


def group_by_service(
    resources: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group by service; services and rows are sorted so output is repeatable."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for resource in sorted(resources, key=resource_sort_key):
        groups.setdefault(str(resource.get("service") or "Unknown"), []).append(
            resource
        )
    return dict(sorted(groups.items(), key=lambda item: item[0].lower()))
