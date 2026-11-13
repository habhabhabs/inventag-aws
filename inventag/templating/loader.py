"""Safe YAML loading for InvenTag templates.

Templates are data, never code:

* Only ``yaml.SafeLoader`` is used, so tags such as ``!!python/object`` are
  rejected instead of being executed.
* Files are limited in size, number of nodes and nesting depth, which also
  stops "billion laughs" alias expansion and recursive aliases.
* Duplicate keys are an error (plain PyYAML silently keeps the last one).
* A line map records where every key was written, so validation errors can
  point at ``file:line``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from .errors import TemplateError, TemplateIssue

MAX_TEMPLATE_BYTES = 256 * 1024
MAX_NODES = 10_000
MAX_DEPTH = 32

PathKey = Tuple[Any, ...]


@dataclass
class TemplateFile:
    """A template file as read from disk, before ``extends`` is applied."""

    data: Dict[str, Any]
    text: str
    source: str  # path as shown to users
    path: Optional[Path] = None
    origin: str = "file"  # file | env | project | user | builtin
    lines: Dict[PathKey, int] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return str(self.data.get("name", ""))

    @property
    def kind(self) -> str:
        return str(self.data.get("kind", ""))

    @property
    def directory(self) -> Optional[Path]:
        return self.path.parent if self.path else None

    def line_of(self, key: PathKey) -> Optional[int]:
        """Line for a path, falling back to the nearest parent that has one."""
        key = tuple(key)
        while key:
            if key in self.lines:
                return self.lines[key]
            key = key[:-1]
        return None


def _mark_line(error: yaml.YAMLError) -> Optional[int]:
    mark = getattr(error, "problem_mark", None) or getattr(error, "context_mark", None)
    return mark.line + 1 if mark is not None else None


def _walk(node: yaml.Node, path: PathKey, lines: Dict[PathKey, int], source: str):
    """Record line numbers, enforce limits and reject duplicate keys."""
    count = 0
    stack = [(node, path, 0)]
    while stack:
        current, current_path, depth = stack.pop()
        count += 1
        if count > MAX_NODES:
            raise TemplateError(
                [
                    TemplateIssue(
                        f"template is too large (more than {MAX_NODES} YAML nodes, "
                        "including expanded aliases)",
                        source,
                    )
                ]
            )
        if depth > MAX_DEPTH:
            raise TemplateError(
                [
                    TemplateIssue(
                        f"template is nested too deeply (more than {MAX_DEPTH} levels)",
                        source,
                        current.start_mark.line + 1,
                    )
                ]
            )
        if isinstance(current, yaml.MappingNode):
            seen: Dict[str, int] = {}
            for key_node, value_node in current.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    stack.append((value_node, current_path, depth + 1))
                    continue
                key = key_node.value if isinstance(key_node, yaml.ScalarNode) else None
                line = key_node.start_mark.line + 1
                if key in seen:
                    raise TemplateError(
                        [
                            TemplateIssue(
                                f"duplicate key '{key}' (first defined on line "
                                f"{seen[key]})",
                                source,
                                line,
                                ".".join(str(p) for p in current_path + (key,)),
                            )
                        ]
                    )
                seen[key] = line
                child_path = current_path + (key,)
                lines.setdefault(child_path, line)
                stack.append((value_node, child_path, depth + 1))
        elif isinstance(current, yaml.SequenceNode):
            for index, item in enumerate(current.value):
                child_path = current_path + (index,)
                lines.setdefault(child_path, item.start_mark.line + 1)
                stack.append((item, child_path, depth + 1))


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key '{key}'")
        result[key] = value
    return result


def parse_template_text(
    text: str,
    source: str = "<template>",
    path: Optional[Path] = None,
    origin: str = "file",
) -> TemplateFile:
    """Parse template text safely and return a :class:`TemplateFile`."""
    if len(text.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise TemplateError(
            [
                TemplateIssue(
                    f"template file is larger than {MAX_TEMPLATE_BYTES // 1024} KiB",
                    source,
                )
            ]
        )
    stripped = text.lstrip("\ufeff").lstrip()
    is_json_file = source.lower().endswith(".json")
    data: Any = None
    parsed_as_json = False
    if is_json_file or stripped.startswith("{"):
        # JSON allows tabs and \u escapes that YAML does not, so read it as JSON.
        try:
            data = json.loads(stripped, object_pairs_hook=_no_duplicate_keys)
            parsed_as_json = True
        except json.JSONDecodeError as error:
            if is_json_file:
                raise TemplateError(
                    [
                        TemplateIssue(
                            f"invalid JSON: {error.msg} (column {error.colno})",
                            source,
                            error.lineno,
                        )
                    ]
                ) from None
        except ValueError as error:  # a key written twice
            raise TemplateError([TemplateIssue(str(error), source)]) from None
        except RecursionError:
            raise TemplateError(
                [
                    TemplateIssue(
                        f"template is nested too deeply (more than {MAX_DEPTH} "
                        "levels)",
                        source,
                    )
                ]
            ) from None

    lines: Dict[PathKey, int] = {}
    if parsed_as_json:
        # Line numbers are a courtesy; a tab-indented file cannot give them.
        try:
            _walk(yaml.compose(text, Loader=yaml.SafeLoader), (), lines, source)
        except (yaml.YAMLError, TemplateError, RecursionError):
            lines = {}
    else:
        try:
            root = yaml.compose(text, Loader=yaml.SafeLoader)
        except RecursionError:
            raise TemplateError(
                [
                    TemplateIssue(
                        f"template is nested too deeply (more than {MAX_DEPTH} "
                        "levels)",
                        source,
                    )
                ]
            ) from None
        except yaml.YAMLError as error:
            problem = getattr(error, "problem", None) or str(error)
            raise TemplateError(
                [TemplateIssue(f"invalid YAML: {problem}", source, _mark_line(error))]
            ) from None
        if root is None:
            raise TemplateError([TemplateIssue("template file is empty", source, 1)])

        _walk(root, (), lines, source)

        try:
            data = yaml.load(text, Loader=yaml.SafeLoader)  # noqa: S506 - SafeLoader
        except yaml.constructor.ConstructorError as error:
            raise TemplateError(
                [
                    TemplateIssue(
                        f"unsupported YAML tag: {error.problem}. Templates are "
                        "plain data; tags such as !!python/object are not allowed",
                        source,
                        _mark_line(error),
                    )
                ]
            ) from None
        except yaml.YAMLError as error:
            raise TemplateError(
                [TemplateIssue(f"invalid YAML: {error}", source, _mark_line(error))]
            ) from None

    if not isinstance(data, dict):
        raise TemplateError(
            [
                TemplateIssue(
                    "a template must be a YAML mapping (key: value pairs) at the top "
                    "level",
                    source,
                    1,
                )
            ]
        )
    return TemplateFile(
        data=data, text=text, source=source, path=path, origin=origin, lines=lines
    )


def load_template_file(path: Path, origin: str = "file") -> TemplateFile:
    """Read and parse one template file from disk."""
    path = Path(path)
    source = str(path)
    if not path.is_file():
        raise TemplateError([TemplateIssue("file not found", source)])
    try:
        size = path.stat().st_size
        if size > MAX_TEMPLATE_BYTES:
            raise TemplateError(
                [
                    TemplateIssue(
                        "template file is larger than "
                        f"{MAX_TEMPLATE_BYTES // 1024} KiB",
                        source,
                    )
                ]
            )
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise TemplateError(
            [TemplateIssue("template file is not valid UTF-8 text", source)]
        ) from None
    except OSError as error:
        raise TemplateError(
            [TemplateIssue(f"cannot read file: {error.strerror}", source)]
        ) from None
    return parse_template_text(text, source=source, path=path, origin=origin)


def safe_relative_path(base_dir: Path, reference: str) -> Path:
    """Resolve ``reference`` inside ``base_dir`` and refuse anything outside it.

    Absolute paths, ``~`` and any ``..`` that climbs out of ``base_dir`` (also
    through symlinks) raise ``ValueError``.
    """
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("must be a non-empty relative path")
    if "\x00" in reference:
        raise ValueError("must not contain NUL characters")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", reference) and not re.match(
        r"^[A-Za-z]:[\\/]", reference
    ):
        raise ValueError(
            "must be a local relative path; URLs and other schemes are not allowed "
            f"(got '{reference}')"
        )
    # A template written on Windows uses backslashes; read them as folder
    # separators on every system, so "..\\x.png" cannot slip past the check below
    # on Linux and macOS, and "assets\\logo.png" works there.
    reference = reference.replace("\\", "/")
    if re.match(r"^[A-Za-z]:", reference):
        raise ValueError(f"must not include a drive letter (got '{reference}')")
    candidate = Path(reference)
    if candidate.is_absolute() or reference.startswith(("~", "/", "\\")):
        raise ValueError(
            "must be a relative path inside the template's folder "
            f"(got '{reference}')"
        )
    if len(candidate.drive) > 0:
        raise ValueError(f"must not include a drive letter (got '{reference}')")
    base = Path(base_dir).resolve()
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(
            "must stay inside the template's folder; '..' that leaves the folder "
            f"is not allowed (got '{reference}')"
        ) from None
    return resolved
