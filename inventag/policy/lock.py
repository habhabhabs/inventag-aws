"""``policy.lock``: the sha256 of every policy and policy-set file of a folder.

``inventag policy lock`` writes it (``write``); ``lock --check`` and
``--locked`` compare the folder with it (``verify``, ``require_unchanged``). A
file that changed, was added or is missing is a problem. Waiver files are not
in the lock: they expire and change by design. The hash is of the file bytes,
as ``Policy.sha256`` in the result file.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..templating.errors import TemplateIssue
from ..templating.loader import safe_relative_path
from . import loader
from .schema import PolicyError

LOCK_NAME = "policy.lock"
FORMAT_VERSION = 1
_NEXT = "run 'inventag policy lock' to record the files as they are now"
_HEX = re.compile(r"[0-9a-f]{64}")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(root) -> Dict[str, str]:
    """``{relative path: sha256}`` of the policy files under ``root``
    (``tests/`` folders left out, as the loader does)."""
    root = Path(root)
    return {
        path.relative_to(root).as_posix(): _digest(path)
        for path in loader._files([root])
    }


def render(root) -> str:
    """The text of ``policy.lock`` for ``root``: sorted keys, two-space
    indent, final newline (same input, same bytes)."""
    data = {
        "files": current(root),
        "format_version": FORMAT_VERSION,
        "kind": "lock",
    }
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def write(root) -> Path:
    """Write ``<root>/policy.lock`` and return its path."""
    path = Path(root) / LOCK_NAME
    path.write_text(render(root), encoding="utf-8")
    return path


def _refuse(message: str, field: Optional[str] = None) -> PolicyError:
    return PolicyError([TemplateIssue(message, LOCK_NAME, None, field)])


def read(root) -> Dict[str, str]:
    """The ``files`` of ``<root>/policy.lock``; a missing or invalid file is a
    :class:`PolicyError` that starts with ``policy.lock``."""
    path = Path(root) / LOCK_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise _refuse(f"file not found; {_NEXT}") from None
    except (OSError, UnicodeDecodeError) as error:
        raise _refuse(f"cannot be read ({type(error).__name__})") from None
    try:
        data = json.loads(text)
    except ValueError:
        raise _refuse("not valid JSON") from None
    if not isinstance(data, dict):
        raise _refuse("must be an object")
    if data.get("kind") != "lock":
        raise _refuse("must be 'lock'", "kind")
    if data.get("format_version") != FORMAT_VERSION:
        raise _refuse(f"must be {FORMAT_VERSION}", "format_version")
    files = data.get("files")
    if not isinstance(files, dict):
        raise _refuse("must be an object of path and sha256", "files")
    for name, digest in files.items():
        try:
            safe_relative_path(Path(root), name)
        except ValueError:
            raise _refuse(
                f"{name}: path must stay inside the policy directory", "files"
            )
        if not isinstance(digest, str) or not _HEX.fullmatch(digest):
            raise _refuse(f"{name}: sha256 must be 64 hex digits", "files")
    return files


def problems(root) -> List[TemplateIssue]:
    """Differences between the folder and its lock, sorted by path."""
    locked = read(root)
    found = current(root)
    issues = []
    for name in sorted(set(locked) | set(found)):
        if name not in found:
            text = "listed in policy.lock but missing"
        elif name not in locked:
            text = "not listed in policy.lock"
        elif locked[name] != found[name]:
            text = "changed since policy.lock was written"
        else:
            continue
        issues.append(TemplateIssue(text, name))
    return issues


def verify(root) -> List[str]:
    """The problems as ``"<path>: <text>"`` lines; empty when the lock holds."""
    return [str(issue) for issue in problems(root)]


def require_unchanged(root) -> None:
    """``--locked``: raise :class:`PolicyError` when a file differs from the lock.
    Each issue ends with the next step."""
    issues = problems(root)
    if issues:
        raise PolicyError(
            [TemplateIssue(f"{i.message}; {_NEXT}", i.source) for i in issues]
        )
