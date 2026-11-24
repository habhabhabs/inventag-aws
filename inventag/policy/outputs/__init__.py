"""Writers for the policy findings (spec 3.3 and 3.4).

``render(result, fmt)`` returns the text of one format; ``write`` puts the four
files ``policy_findings_<ts>.{json,sarif,xml,md}`` in a folder, owner-only.
The input is the mapping that ``inventag.policy.engine.evaluate`` returns. No
writer reads the clock, the host or the environment, so the same result gives
the same bytes. A raw value from a resource is written only with
``show_values``, and then only to the JSON, Markdown and text forms; a secret
stays masked (``***REDACTED***``) in every form.
"""

import re
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence

from ...security import safe_output
from . import _common, junit, markdown, sarif, text
from ._common import prepared
from .schema import findings_schema, sarif_schema

FORMATS = ("json", "sarif", "xml", "md")
SUFFIX = {"json": "json", "sarif": "sarif", "xml": "xml", "md": "md", "text": "txt"}

__all__ = [
    "FORMATS",
    "file_stem",
    "findings_schema",
    "render",
    "sarif_schema",
    "write",
]

_STAMP = re.compile(r"(\d{4})-?(\d\d)-?(\d\d)[T _-]?(\d\d):?(\d\d):?(\d\d)")


def file_stem(result: Mapping[str, Any]) -> str:
    """``policy_findings_<ts>``: ``<ts>`` is the snapshot's timestamp, never the clock.

    The usual ``YYYYMMDD_HHMMSS`` form is built from an ISO timestamp; anything
    else is reduced to ``[A-Za-z0-9._-]`` so no stamp can leave the folder.
    """
    stamp = str((result.get("snapshot") or {}).get("timestamp") or "")
    found = _STAMP.match(stamp)
    if found:
        y, mo, d, h, mi, s = found.groups()
        part = f"{y}{mo}{d}_{h}{mi}{s}"
    else:
        part = safe_output.safe_filename_component(stamp, default="snapshot")
    return f"policy_findings_{part}"


def render(
    result: Mapping[str, Any],
    fmt: str,
    *,
    show_values: bool = False,
    policy_lines: Optional[Mapping[str, int]] = None,
    fail_on: Optional[str] = None,
    thresholds: Optional[Iterable[str]] = None,
) -> str:
    """The text of one format: json, sarif, xml, md or text.

    ``policy_lines`` overrides the result's ``policies[].line`` (the line of
    ``spec.id`` in the policy file; default 1).

    ``fail_on`` (a severity) and ``thresholds`` (the names of the thresholds
    the caller set: ``fail_on``, ``fail_on_not_evaluated``) give the last line
    of the text and Markdown forms (spec 11.3). Without both, that line is
    left out: the result alone does not say which thresholds were set.
    """
    if fmt not in SUFFIX:
        raise ValueError(f"unknown format: {fmt}")
    gate = _common.gates(fail_on, thresholds)
    data = prepared(result, show_values)
    if fmt == "json":
        return _common.dumps(data)
    if fmt == "sarif":
        return sarif.render(data, policy_lines or {})
    if fmt == "xml":
        return junit.render(data)
    if fmt == "md":
        return markdown.render(data, show_values, gate)
    return text.render(data, show_values, gate)


def write(
    result: Mapping[str, Any],
    directory,
    *,
    formats: Sequence[str] = FORMATS,
    show_values: bool = False,
    policy_lines: Optional[Mapping[str, int]] = None,
    fail_on: Optional[str] = None,
    thresholds: Optional[Iterable[str]] = None,
) -> List[Path]:
    """Write ``policy_findings_<ts>.<ext>`` for each format; return the paths."""
    for fmt in formats:
        if fmt not in FORMATS:
            raise ValueError(f"unknown format: {fmt}")
    folder = safe_output.ensure_private_dir(directory)
    stem = file_stem(result)
    paths: List[Path] = []
    for fmt in formats:
        body = render(
            result,
            fmt,
            show_values=show_values,
            policy_lines=policy_lines,
            fail_on=fail_on,
            thresholds=thresholds,
        )
        path = folder / f"{stem}.{SUFFIX[fmt]}"
        with safe_output.open_private(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        paths.append(path)
    return paths
