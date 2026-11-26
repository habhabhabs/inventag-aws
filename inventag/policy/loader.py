"""Read policy, policy-set and waiver files (spec 2).

Plain data only: ``yaml.SafeLoader``, no aliases, no environment expansion, at
most 256 KiB per file, at most 500 policies per run. One document per file,
or several separated by ``---``. A path inside a set stays inside the policy
directory (``templating.loader.safe_relative_path``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from ..templating.errors import TemplateError, TemplateIssue
from ..templating.loader import _walk, safe_relative_path
from . import model
from .schema import BACKTRACK_PROBLEM, PolicyError, backtracks, validate_document

SUFFIXES = (".yaml", ".yml", ".json")


@dataclass(frozen=True)
class Document:
    data: Dict[str, Any]
    file: str  # label: relative to the root, with "/"
    sha256: str
    lines: Dict[Tuple[Any, ...], int]
    path: Path

    def line_of(self, key) -> Optional[int]:
        key = tuple(key)
        while key:
            if key in self.lines:
                return self.lines[key]
            key = key[:-1]
        return None


@dataclass(frozen=True)
class Loaded:
    policies: Tuple[model.Policy, ...]
    sets: Tuple[model.PolicySet, ...]
    root: Optional[Path]
    # what decided the result, for policy.lock: every file read, and the
    # sha256 of each tag-policy template's rules (name -> digest)
    files_read: Tuple[Path, ...] = ()
    tag_policies: Dict[str, str] = field(default_factory=dict)


@dataclass
class _Trace:
    files: List[Path] = field(default_factory=list)
    tag_policies: Dict[str, str] = field(default_factory=dict)


def _label(path: Path, root: Optional[Path]) -> str:
    if root is not None:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return str(path)


def read_documents(path: Path, root: Optional[Path]) -> List[Document]:
    """The documents of one file, with line maps; refuses aliases and size."""
    label = _label(path, root)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise PolicyError([TemplateIssue(f"cannot read file: {error.strerror}", label)])
    if len(raw) > model.LIMITS.file_bytes:
        raise PolicyError(
            [
                TemplateIssue(
                    f"file is larger than {model.LIMITS.file_bytes // 1024} KiB", label
                )
            ]
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise PolicyError(
            [TemplateIssue("file is not valid UTF-8 text", label)]
        ) from None
    sha = hashlib.sha256(raw).hexdigest()
    try:
        depth = 0
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, (yaml.SequenceStartEvent, yaml.MappingStartEvent)):
                depth += 1
                if depth > model.LIMITS.yaml_depth:
                    raise PolicyError(
                        [
                            TemplateIssue(
                                "YAML is nested too deeply (more than "
                                f"{model.LIMITS.yaml_depth} levels)",
                                label,
                                event.start_mark.line + 1,
                            )
                        ]
                    )
            elif isinstance(event, (yaml.SequenceEndEvent, yaml.MappingEndEvent)):
                depth -= 1
            anchor = getattr(event, "anchor", None)
            if isinstance(event, yaml.AliasEvent) or anchor:
                raise PolicyError(
                    [
                        TemplateIssue(
                            "YAML aliases are not allowed in policy files",
                            label,
                            event.start_mark.line + 1,
                        )
                    ]
                )
        nodes = list(yaml.compose_all(text, Loader=yaml.SafeLoader))
        datas = list(yaml.load_all(text, Loader=yaml.SafeLoader))  # noqa: S506
    except RecursionError:
        raise PolicyError([TemplateIssue("YAML is nested too deeply", label)]) from None
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        problem = getattr(error, "problem", None) or str(error)
        raise PolicyError(
            [
                TemplateIssue(
                    f"invalid YAML: {problem}", label, mark.line + 1 if mark else None
                )
            ]
        ) from None
    documents = []
    for node, data in zip(nodes, datas):
        if node is None:
            continue
        lines: Dict[Tuple[Any, ...], int] = {}
        try:
            _walk(node, (), lines, label)
        except TemplateError as error:
            raise PolicyError(error.issues) from None
        except RecursionError:
            raise PolicyError(
                [TemplateIssue("YAML is nested too deeply", label)]
            ) from None
        if not isinstance(data, dict):
            raise PolicyError(
                [
                    TemplateIssue(
                        "a document must be a mapping (key: value pairs)",
                        label,
                        node.start_mark.line + 1,
                    )
                ]
            )
        documents.append(Document(data, label, sha, lines, path))
    if not documents:
        raise PolicyError([TemplateIssue("file is empty", label, 1)])
    return documents


def _files(paths: Iterable[Path]) -> List[Path]:
    """Files given, and the policy files of folders given (``tests/`` left out)."""
    found: List[Path] = []
    for path in paths:
        path = Path(path)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                rel = child.relative_to(path).parts
                if (
                    child.is_file()
                    and child.suffix in SUFFIXES
                    and "tests" not in rel[:-1]
                ):
                    found.append(child)
        else:
            found.append(path)
    return found


# Public name (architect P3/P4 rulings): the files of the paths given, with the
# policy files of folders (``tests/`` left out).
expand_paths = _files


def tag_policy_digest(rules: List[Dict], scope: Dict) -> str:
    """sha256 of what a tag-policy template decides: its rules and scope."""
    text = json.dumps(
        {"required_tags": rules, "scope": scope}, sort_keys=True, default=str
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tag_policy_rules(
    name: str, issue, trace=None, registry=None
) -> Tuple[List[Dict], Dict]:
    """The rules and scope of tag policy ``name``; each pattern is checked and
    the digest recorded in ``trace`` (for ``policy.lock``)."""
    from ..templating.registry import TemplateRegistry

    try:
        resolved = (registry or TemplateRegistry()).resolve(name)
    except TemplateError as error:
        issue(f"tag policy '{name}' cannot be loaded: {error.issues[0].message}")
        return [], {}
    if resolved.kind != "tag-policy":
        issue(f"'{name}' is a {resolved.kind} template, not a tag policy")
        return [], {}
    rules = list(resolved.spec["required_tags"])
    scope = dict(resolved.spec.get("scope") or {})
    for rule in rules:
        pattern = rule.get("pattern")
        if isinstance(pattern, str) and backtracks(pattern):
            issue(f"tag policy '{name}': {rule.get('key')}: {BACKTRACK_PROBLEM}")
    if trace is not None:
        trace.tag_policies[name] = tag_policy_digest(rules, scope)
    return rules, scope


def _prepare_entries(entries: Any, issue, trace=None) -> Any:
    """Copy entries; give each required-tags check its rules (``_rules``)."""
    if isinstance(entries, list):
        return [_prepare_entries(e, issue, trace) for e in entries]
    if not isinstance(entries, dict):
        return entries
    entry = {
        k: _prepare_entries(v, issue, trace) if k in ("and", "or", "not") else v
        for k, v in entries.items()
    }
    if entry.get("type") == "required-tags":
        if "policy" in entry:
            rules, scope = _tag_policy_rules(entry["policy"], issue, trace)
            entry["_rules"] = rules
            if entry.get("use_scope"):
                entry["_scope"] = scope
        else:
            entry["_rules"] = [dict(r) for r in entry["keys"]]
    return entry


def _policy(doc: Document, trace=None) -> Tuple[model.Policy, List[TemplateIssue]]:
    spec = doc.data["spec"]
    issues: List[TemplateIssue] = []

    def issue(message):
        issues.append(
            TemplateIssue(
                message, doc.file, doc.line_of(("spec", "check")), "spec.check"
            )
        )

    policy = model.Policy(
        id=spec["id"],
        name=doc.data["name"],
        severity=spec["severity"],
        check=tuple(_prepare_entries(spec["check"], issue, trace)),
        version=spec.get("version", 1),
        resource=dict(spec.get("resource") or {}),
        require=tuple(spec.get("require") or ()),
        message=spec.get("message"),
        references=tuple(spec.get("references") or ()),
        enabled=spec.get("enabled", True),
        description=str(doc.data.get("description") or ""),
        file=doc.file,
        sha256=doc.sha256,
        id_line=doc.line_of(("spec", "id")),
    )
    return policy, issues


def load(
    paths: Sequence[Path],
    root: Optional[Path] = None,
    *,
    _trace: Optional[_Trace] = None,
    _chain: Tuple[Path, ...] = (),
) -> Loaded:
    """Load policies and sets; resolve the sets; one :class:`PolicyError` with
    every problem found. ``_chain``: the set files whose paths led here."""
    trace = _trace if _trace is not None else _Trace()
    files = _files(paths)
    if root is None and files:
        root = Path(files[0]).parent
    root = Path(root) if root is not None else None
    issues: List[TemplateIssue] = []
    docs: List[Document] = []
    for path in files:
        trace.files.append(Path(path))
        try:
            docs.extend(read_documents(Path(path), root))
        except PolicyError as error:
            issues.extend(error.issues)
    policies: List[model.Policy] = []
    sets: Dict[str, Tuple[model.PolicySet, Document]] = {}
    for doc in docs:
        if isinstance(doc.data, dict) and doc.data.get("kind") == "waivers":
            continue  # waivers are loaded with --waivers
        kind, found = validate_document(doc.data, doc.file, doc.line_of, None)
        if found:
            issues.extend(found)
            continue
        if kind == "policy":
            policy, more = _policy(doc, trace)
            issues.extend(more)
            policies.append(policy)
        elif kind == "policy-set":
            spec = doc.data["spec"]
            sets[doc.data["name"]] = (
                model.PolicySet(
                    name=doc.data["name"],
                    policies=tuple(spec.get("policies") or ()),
                    include=tuple(spec.get("include") or ()),
                    severity_overrides=dict(spec.get("severity_overrides") or {}),
                    description=str(doc.data.get("description") or ""),
                    file=doc.file,
                ),
                doc,
            )
        else:
            issues.append(
                TemplateIssue("waivers are loaded with --waivers", doc.file, 1, "kind")
            )
    if issues:
        raise PolicyError(issues)

    by_name = {p.name: p for p in policies}
    overrides: Dict[str, str] = {}
    done: set = set()
    try:
        for set_name in sorted(sets):
            _resolve_set(
                set_name,
                sets,
                by_name,
                policies,
                overrides,
                root,
                issues,
                [],
                trace,
                _chain,
                done,
            )
    except RecursionError:
        issues.append(TemplateIssue("policy sets are nested too deeply"))
    issues[:] = list(dict.fromkeys(issues))  # one line for a repeated problem
    if issues:
        raise PolicyError(issues)

    seen: Dict[str, model.Policy] = {}
    unique: List[model.Policy] = []
    for policy in policies:
        other = seen.get(policy.id)
        if other is not None:
            if (other.file, other.name) == (policy.file, policy.name):
                continue  # reached twice: evaluated once
            issues.append(
                TemplateIssue(
                    f"id {policy.id} is also used in {other.file}",
                    policy.file,
                    policy.id_line,
                    "spec.id",
                )
            )
            continue
        seen[policy.id] = policy
        unique.append(policy)
    if len(unique) > model.LIMITS.policies_per_run:
        issues.append(
            TemplateIssue(
                f"at most {model.LIMITS.policies_per_run} policies per run "
                f"({len(unique)} given)"
            )
        )
    if issues:
        raise PolicyError(issues)
    final = []
    for policy in unique:
        if policy.id in overrides:
            set_name, severity = overrides[policy.id].split(":", 1)
            policy = replace(policy, severity=severity, severity_overridden_by=set_name)
        final.append(policy)
    return Loaded(
        tuple(final),
        tuple(s for s, _ in sets.values()),
        root,
        tuple(dict.fromkeys(trace.files)),
        dict(trace.tag_policies),
    )


def _resolve_set(
    name,
    sets,
    by_name,
    policies,
    overrides,
    root,
    issues,
    chain,
    trace,
    files=(),
    done=None,
):
    if name in chain:
        cycle = chain[chain.index(name) :] + [name]
        issues.append(
            TemplateIssue(
                f"policy sets include each other: {' -> '.join(cycle)}",
                sets[chain[0]][0].file,
                None,
                "spec.include",
            )
        )
        return
    if done is not None and name in done:
        return  # resolved already: a set reached twice is resolved once
    if len(chain) >= model.LIMITS.set_file_depth:
        issues.append(
            TemplateIssue(
                "policy sets include each other deeper than "
                f"{model.LIMITS.set_file_depth}",
                sets[chain[0]][0].file,
                None,
                "spec.include",
            )
        )
        return
    entry = sets.get(name)
    if entry is None:
        issues.append(
            TemplateIssue(
                f"no policy set named '{name}'",
                sets[chain[-1]][0].file,
                None,
                "spec.include",
            )
        )
        return
    policy_set, doc = entry
    if done is not None:
        done.add(name)
    for i, include in enumerate(policy_set.include):
        _resolve_set(
            include,
            sets,
            by_name,
            policies,
            overrides,
            root,
            issues,
            chain + [name],
            trace,
            files,
            done,
        )
    base = root or doc.path.parent
    for i, reference in enumerate(policy_set.policies):
        if reference in by_name:
            target = by_name[reference]
        elif "/" in reference or reference.endswith(SUFFIXES) or "\\" in reference:
            try:
                path = safe_relative_path(base, reference)
            except ValueError as error:
                issues.append(
                    TemplateIssue(
                        str(error),
                        doc.file,
                        doc.line_of(("spec", "policies", i)),
                        f"spec.policies.{i}",
                    )
                )
                continue
            here = files + (doc.path.resolve(),)
            target_path = path.resolve()
            where = (
                doc.file,
                doc.line_of(("spec", "policies", i)),
                f"spec.policies.{i}",
            )
            if target_path in here:
                labels = [_label(p, root) for p in here[here.index(target_path) :]]
                labels.append(_label(target_path, root))
                issues.append(
                    TemplateIssue(
                        "policy set file reached again: " + " -> ".join(labels),
                        *where,
                    )
                )
                continue
            if len(here) > model.LIMITS.set_file_depth:
                issues.append(
                    TemplateIssue(
                        "policy set files nested deeper than "
                        f"{model.LIMITS.set_file_depth}",
                        *where,
                    )
                )
                continue
            try:
                loaded = load([path], root=root, _trace=trace, _chain=here)
            except PolicyError as error:
                issues.extend(error.issues)
                continue
            for policy in loaded.policies:
                by_name.setdefault(policy.name, policy)
                policies.append(policy)
            continue
        else:
            issues.append(
                TemplateIssue(
                    f"no policy named '{reference}'",
                    doc.file,
                    doc.line_of(("spec", "policies", i)),
                    f"spec.policies.{i}",
                )
            )
            continue
        if target not in policies:
            policies.append(target)
    for pid, severity in policy_set.severity_overrides.items():
        overrides.setdefault(pid, f"{policy_set.name}:{severity}")


def load_waivers(
    paths: Sequence[Path], now: dt.datetime, root: Optional[Path] = None
) -> List[model.Waiver]:
    """The waivers of ``paths`` (spec 2.5), in file order."""
    files = _files(paths)
    if root is None and files:
        root = Path(files[0]).parent
    issues: List[TemplateIssue] = []
    waivers: List[model.Waiver] = []
    for path in files:
        try:
            docs = read_documents(Path(path), root)
        except PolicyError as error:
            issues.extend(error.issues)
            continue
        for doc in docs:
            kind, found = validate_document(doc.data, doc.file, doc.line_of, now)
            if kind not in (None, "waivers"):
                found.append(
                    TemplateIssue(
                        "must be kind: waivers",
                        doc.file,
                        doc.line_of(("kind",)),
                        "kind",
                    )
                )
            if found:
                issues.extend(found)
                continue
            from .schema import parse_date

            for entry in doc.data["spec"]["waivers"]:
                waivers.append(
                    model.Waiver(
                        policy=entry["policy"],
                        resource=entry["resource"],
                        reason=entry["reason"],
                        approved_by=entry["approved_by"],
                        expires=parse_date(entry["expires"]),
                        account=entry.get("account"),
                        file=doc.file,
                    )
                )
    if issues:
        raise PolicyError(issues)
    return waivers
