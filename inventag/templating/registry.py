"""Finding templates and resolving ``extends``.

Search order (first match wins):

1. Folders in the ``INVENTAG_TEMPLATE_PATH`` environment variable, in order
   (separated by ``:`` on Linux and macOS, ``;`` on Windows).
2. ``.inventag/templates/`` in the current working directory (project).
3. ``$XDG_CONFIG_HOME/inventag/templates/`` (user; defaults to
   ``~/.config/inventag/templates/``).
4. The built-in templates shipped with InvenTag.

A template is found by its file name without ``.yaml``/``.yml``. A user
template with the same name as a built-in one shadows it, and may still
``extends:`` the built-in one: resolving ``extends`` by name skips the file
that is asking.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .errors import TemplateError, TemplateIssue, TemplateNotFoundError
from .loader import TemplateFile, load_template_file, safe_relative_path
from .schema import SPECS, TOP_LEVEL, apply_defaults, validate_fields

BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"
MAX_EXTENDS_DEPTH = 10
SUFFIXES = (".yaml", ".yml")


@dataclass
class SearchDir:
    origin: str  # env | project | user | builtin
    path: Path


@dataclass
class TemplateEntry:
    """A template file found in a search folder."""

    name: str
    path: Path
    origin: str
    shadowed_by: Optional["TemplateEntry"] = None


@dataclass
class ResolvedTemplate:
    """A template with ``extends`` applied and defaults filled in."""

    name: str
    kind: str
    description: str
    spec: Dict[str, Any]
    chain: List[TemplateFile]  # child first, root last
    data: Dict[str, Any] = field(default_factory=dict)  # merged, before defaults

    @property
    def file(self) -> TemplateFile:
        return self.chain[0]

    @property
    def source(self) -> str:
        return self.chain[0].source

    @property
    def directory(self) -> Path:
        return self.chain[0].directory or BUILTIN_DIR


def looks_like_path(reference: str) -> bool:
    return (
        "/" in reference
        or "\\" in reference
        or reference.endswith(SUFFIXES)
        or reference.startswith(".")
    )


def search_dirs(
    cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None
) -> List[SearchDir]:
    env = os.environ if env is None else env
    cwd = Path.cwd() if cwd is None else Path(cwd)
    dirs: List[SearchDir] = []
    for part in env.get("INVENTAG_TEMPLATE_PATH", "").split(os.pathsep):
        if part.strip():
            dirs.append(SearchDir("env", Path(part).expanduser()))
    dirs.append(SearchDir("project", cwd / ".inventag" / "templates"))
    config_home = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    dirs.append(SearchDir("user", Path(config_home) / "inventag" / "templates"))
    dirs.append(SearchDir("builtin", BUILTIN_DIR))
    return dirs


class TemplateRegistry:
    """Looks up templates by name across the search folders."""

    def __init__(self, dirs: Optional[Sequence[SearchDir]] = None):
        self.dirs = list(dirs) if dirs is not None else search_dirs()

    # ---------------------------------------------------------------- lookup
    def _files_in(self, directory: Path) -> List[Path]:
        if not directory.is_dir():
            return []
        found: Dict[str, Path] = {}
        for path in sorted(directory.iterdir()):
            if path.suffix in SUFFIXES and path.is_file():
                # foo.yaml wins over foo.yml in the same folder
                if path.stem not in found or path.suffix == ".yaml":
                    found[path.stem] = path
        return list(found.values())

    def entries(self) -> List[TemplateEntry]:
        """Every template file in search order, with shadowing marked."""
        winners: Dict[str, TemplateEntry] = {}
        result: List[TemplateEntry] = []
        for directory in self.dirs:
            for path in self._files_in(directory.path):
                entry = TemplateEntry(path.stem, path, directory.origin)
                if path.stem in winners:
                    entry.shadowed_by = winners[path.stem]
                else:
                    winners[path.stem] = entry
                result.append(entry)
        return result

    def find(self, name: str, skip: Optional[Path] = None) -> TemplateEntry:
        """Find a template by name. ``skip`` ignores one file (for ``extends``).

        When ``skip`` is given, the search continues *after* that file's
        folder, so a user template can extend the built-in of the same name.
        """
        skip_resolved = skip.resolve() if skip else None
        # A file outside every search folder has nothing "before" it.
        passed_skip = skip_resolved is None or not any(
            p.resolve() == skip_resolved
            for d in self.dirs
            for p in self._files_in(d.path)
        )
        for directory in self.dirs:
            for path in self._files_in(directory.path):
                if skip_resolved is not None and path.resolve() == skip_resolved:
                    passed_skip = True
                    continue
                if path.stem == name and (passed_skip or path.stem != skip.stem):
                    return TemplateEntry(name, path, directory.origin)
        searched = ", ".join(str(d.path) for d in self.dirs)
        raise TemplateNotFoundError(
            [
                TemplateIssue(
                    f"no template named '{name}'. Run 'inventag templates list' to "
                    f"see what is available (searched: {searched})"
                )
            ]
        )

    def load(self, reference: str, base_dir: Optional[Path] = None) -> TemplateFile:
        """Load a template by name or by path.

        Paths given on the command line (``base_dir`` is None) may be anywhere.
        Paths written inside a template (``extends``, ``tag_policy``...) are
        relative to that template and must stay inside its folder.
        """
        if "://" in reference:
            raise TemplateError(
                [
                    TemplateIssue(
                        "templates are loaded from local files only; URLs are not "
                        f"supported (got '{reference}')"
                    )
                ]
            )
        if looks_like_path(reference):
            if base_dir is None:
                path = Path(reference).expanduser()
            else:
                try:
                    path = safe_relative_path(base_dir, reference)
                except ValueError as error:
                    raise TemplateError([TemplateIssue(str(error))]) from None
            if not path.is_file():
                raise TemplateNotFoundError(
                    [TemplateIssue("file not found", str(path))]
                )
            return load_template_file(path, origin="file")
        entry = self.find(reference)
        return load_template_file(entry.path, origin=entry.origin)

    # --------------------------------------------------------------- resolve
    def resolve(
        self, reference: str, base_dir: Optional[Path] = None
    ) -> ResolvedTemplate:
        return self.resolve_file(self.load(reference, base_dir))

    def resolve_file(self, template: TemplateFile) -> ResolvedTemplate:
        """Apply ``extends``, validate the result and fill defaults."""
        chain = [template]
        seen = {self._identity(template)}
        current = template
        while current.data.get("extends"):
            if len(chain) > MAX_EXTENDS_DEPTH:
                raise TemplateError(
                    [
                        TemplateIssue(
                            f"'extends' chain is longer than {MAX_EXTENDS_DEPTH} "
                            "templates",
                            template.source,
                            template.line_of(("extends",)),
                            "extends",
                        )
                    ]
                )
            parent = self._load_parent(current)
            identity = self._identity(parent)
            if identity in seen:
                names = " -> ".join(t.name or t.source for t in chain + [parent])
                raise TemplateError(
                    [
                        TemplateIssue(
                            f"'extends' loop: {names}",
                            current.source,
                            current.line_of(("extends",)),
                            "extends",
                        )
                    ]
                )
            if parent.kind != current.kind and parent.kind and current.kind:
                raise TemplateError(
                    [
                        TemplateIssue(
                            f"cannot extend '{parent.name}': it is a {parent.kind} "
                            f"template and this one is a {current.kind} template",
                            current.source,
                            current.line_of(("extends",)),
                            "extends",
                        )
                    ]
                )
            seen.add(identity)
            chain.append(parent)
            current = parent

        # Validate each file on its own first: unknown keys and bad types are
        # reported against the file that has them.
        issues: List[TemplateIssue] = []
        for index, item in enumerate(chain):
            partial = index < len(chain) - 1 or bool(item.data.get("extends"))
            issues.extend(
                validate_fields(item.data, _file_lookup(item), partial=partial)
            )
        if issues:
            raise TemplateError(issues)

        merged, provenance = merge_chain(chain)
        issues = validate_fields(merged, _provenance_lookup(provenance, chain[0]))
        if issues:
            raise TemplateError(issues)

        kind = merged["kind"]
        spec = apply_defaults(merged.get("spec") or {}, SPECS[kind])
        top = apply_defaults(merged, TOP_LEVEL)
        return ResolvedTemplate(
            name=str(top["name"]),
            kind=kind,
            description=str(top.get("description") or ""),
            spec=spec,
            chain=chain,
            data=merged,
        )

    def _load_parent(self, child: TemplateFile) -> TemplateFile:
        reference = child.data["extends"]
        if not isinstance(reference, str) or not reference.strip():
            raise TemplateError(
                [
                    TemplateIssue(
                        "must be a template name or a relative path",
                        child.source,
                        child.line_of(("extends",)),
                        "extends",
                    )
                ]
            )
        try:
            if looks_like_path(reference):
                base = child.directory or BUILTIN_DIR
                return self.load(reference, base_dir=base)
            entry = self.find(reference, skip=child.path)
            return load_template_file(entry.path, origin=entry.origin)
        except TemplateError as error:
            raise TemplateError(
                [
                    TemplateIssue(
                        f"cannot load '{reference}': "
                        + "; ".join(i.message for i in error.issues),
                        child.source,
                        child.line_of(("extends",)),
                        "extends",
                    )
                ]
            ) from None

    @staticmethod
    def _identity(template: TemplateFile) -> str:
        return str(template.path.resolve()) if template.path else id(template).__str__()


# ------------------------------------------------------------------- merging

Provenance = Dict[Tuple[Any, ...], Tuple[str, Optional[int]]]


def _file_lookup(template: TemplateFile):
    return lambda path: (template.source, template.line_of(path))


def _provenance_lookup(provenance: Provenance, fallback: TemplateFile):
    def lookup(path):
        key = tuple(path)
        while key:
            if key in provenance:
                return provenance[key]
            key = key[:-1]
        return fallback.source, None

    return lookup


def _record(provenance: Provenance, template: TemplateFile, value: Any, path) -> None:
    provenance[path] = (template.source, template.line_of(path))
    if isinstance(value, dict):
        for key, item in value.items():
            _record(provenance, template, item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _record(provenance, template, item, path + (index,))


def _merge_required_tags(base: List[Any], override: List[Any]) -> List[Any]:
    """Merge tag lists by ``key``: replace, append, or ``remove: true``."""
    result = [copy.deepcopy(t) for t in base]
    for tag in override:
        if not isinstance(tag, dict):
            result.append(tag)
            continue
        key = tag.get("key")
        index = next(
            (
                i
                for i, t in enumerate(result)
                if isinstance(t, dict) and t.get("key") == key
            ),
            None,
        )
        if tag.get("remove"):
            if index is not None:
                result.pop(index)
            continue
        if index is None:
            result.append(copy.deepcopy(tag))
        else:
            result[index] = copy.deepcopy(tag)
    return result


def _merge(base: Any, override: Any, path: Tuple[Any, ...]) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        result = copy.deepcopy(base)
        for key, value in override.items():
            if value is None:
                result.pop(key, None)  # null resets to the default
            elif key in result:
                result[key] = _merge(result[key], value, path + (key,))
            else:
                result[key] = copy.deepcopy(value)
        return result
    if (
        path == ("spec", "required_tags")
        and isinstance(base, list)
        and isinstance(override, list)
    ):
        return _merge_required_tags(base, override)
    return copy.deepcopy(override)


def merge_chain(chain: List[TemplateFile]) -> Tuple[Dict[str, Any], Provenance]:
    """Merge a child-first chain into one dictionary, root first.

    Mappings merge key by key, ``null`` removes an inherited key, lists
    replace the inherited list (except ``spec.required_tags``, merged by key).
    The child's ``name``, ``description`` and ``kind`` always win, and the
    result has no ``extends``.
    """
    merged: Dict[str, Any] = {}
    provenance: Provenance = {}
    for template in reversed(chain):
        data = {k: v for k, v in template.data.items() if k != "extends"}
        merged = _merge(merged, data, ())
        _record(provenance, template, data, ())
    spec = merged.get("spec")
    if isinstance(spec, dict) and isinstance(spec.get("required_tags"), list):
        for tag in spec["required_tags"]:
            if isinstance(tag, dict):
                tag.pop("remove", None)
    return merged, provenance
