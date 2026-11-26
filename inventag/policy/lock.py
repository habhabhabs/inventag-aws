"""``policy.lock``: the sha256 of every file that decides the result of a folder.

``inventag policy lock`` writes it (``write``); ``lock --check`` and
``--locked`` compare the folder with it (``verify``, ``require_unchanged``). A
file that changed, was added or is missing is a problem.

``files``: every policy, policy-set and waivers file of the folder (spec 10.3;
a ``tests/`` folder is left out), and every other file inside the folder that
a set names by path, whatever its suffix and also under ``tests/``. The hash is
of the file bytes, as ``Policy.sha256`` in the result file.

``tag_policies`` (only when a policy uses ``required-tags`` with ``policy:``):
for each tag-policy template, the sha256 of its resolved rules and scope, so a
template changed on the runner (``INVENTAG_TEMPLATE_PATH``, ``./.inventag``,
``~/.config``) or by an upgrade is a problem too.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..templating.errors import TemplateIssue
from ..templating.loader import safe_relative_path
from . import loader
from .schema import PolicyError

LOCK_NAME = "policy.lock"
FORMAT_VERSION = 1
_NEXT = "run 'inventag policy lock' to record the files as they are now"
_NEXT_OUTSIDE = "move it into the policy directory, then run 'inventag policy lock'"
_HEX = re.compile(r"[0-9a-f]{64}")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(root) -> Tuple[Dict[str, str], Dict[str, str]]:
    """``(files, tag_policies)`` of the folder as it is now."""
    root = Path(root)
    base = root.resolve()
    files = {
        path.relative_to(root).as_posix(): _digest(path)
        for path in loader._files([root])
    }
    tag_policies: Dict[str, str] = {}
    try:
        loaded = loader.load([root], root=root)
    except PolicyError:
        # an invalid folder: the files are listed; the check refuses to load it
        return files, tag_policies
    for path in loaded.files_read:
        try:
            name = Path(path).resolve().relative_to(base).as_posix()
        except ValueError:
            continue  # the loader keeps set references inside the folder
        if name != LOCK_NAME and Path(path).is_file():
            files.setdefault(name, _digest(Path(path)))
    tag_policies.update(loaded.tag_policies)
    return files, tag_policies


def current(root) -> Dict[str, str]:
    """``{relative path: sha256}`` of the files under ``root`` that decide the
    result."""
    return _inputs(root)[0]


def render(root) -> str:
    """The text of ``policy.lock`` for ``root``: sorted keys, two-space
    indent, final newline (same input, same bytes)."""
    files, tag_policies = _inputs(root)
    data: Dict[str, object] = {
        "files": files,
        "format_version": FORMAT_VERSION,
        "kind": "lock",
    }
    if tag_policies:
        data["tag_policies"] = tag_policies
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
    return _read_all(root)[0]


def _read_all(root) -> Tuple[Dict[str, str], Dict[str, str]]:
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
    tag_policies = data.get("tag_policies", {})
    if not isinstance(tag_policies, dict):
        raise _refuse("must be an object of name and sha256", "tag_policies")
    for name, digest in tag_policies.items():
        if not isinstance(digest, str) or not _HEX.fullmatch(digest):
            raise _refuse(f"{name}: sha256 must be 64 hex digits", "tag_policies")
    return files, tag_policies


def problems(root) -> List[TemplateIssue]:
    """Differences between the folder and its lock, sorted by path."""
    locked, locked_tags = _read_all(root)
    found, found_tags = _inputs(root)
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
    for name in sorted(set(locked_tags) | set(found_tags)):
        if name not in found_tags:
            text = "listed in policy.lock but no policy uses it"
        elif name not in locked_tags:
            text = "not listed in policy.lock"
        elif locked_tags[name] != found_tags[name]:
            text = "changed since policy.lock was written"
        else:
            continue
        issues.append(TemplateIssue(text, f"tag policy {name}"))
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


def require_listed(root, files) -> None:
    """``--locked`` and ``--waivers``: each file must be inside ``root`` and
    listed in ``policy.lock``; otherwise raise :class:`PolicyError`."""
    root = Path(root).resolve()
    locked = read(root)
    issues = []
    for path in files:
        try:
            name = Path(path).resolve().relative_to(root).as_posix()
        except ValueError:
            issues.append(
                TemplateIssue(
                    f"outside the policy directory; {_NEXT_OUTSIDE}", str(path)
                )
            )
            continue
        if name not in locked:
            issues.append(TemplateIssue(f"not listed in policy.lock; {_NEXT}", name))
    if issues:
        raise PolicyError(issues)
