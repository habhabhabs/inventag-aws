"""The policy sets that ship with InvenTag (v1.5.0).

One folder per set: ``<set>/set.yaml``, the policy files, and
``<set>/tests/<policy name>/*.yaml`` (fixtures for ``inventag policy test``).
A set reads only fields that a moto scan shows on the row; what the scan does
not show is not shipped (see ``tests/unit/policy_builtin``).

``load_set`` reads the folder with the policy loader. A ``required-tags`` check
that names a tag policy is pinned to the tag policy that ships with InvenTag,
never to a copy of the same name in a template folder (the same rule as
``--finops-checks`` of v1.4.x): the result of a shipped set does not depend on
the user's files.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .. import loader, model

BUILTIN_DIR = Path(__file__).resolve().parent
SET_NAMES: Tuple[str, ...] = (
    "encryption-at-rest",
    "finops-checks",
    "naming",
    "public-exposure",
    "region-allowlist",
    "tagging-standard",
)

_LOCK = threading.Lock()
_CACHE: Dict[str, Tuple[model.Policy, ...]] = {}


def _shipped_tag_policy_rules(name: str, issue) -> Tuple[List[Dict], Dict]:
    """``loader._tag_policy_rules`` over the shipped templates only."""
    from ...templating.errors import TemplateError
    from ...templating.registry import BUILTIN_DIR as TEMPLATES
    from ...templating.registry import SearchDir, TemplateRegistry

    try:
        resolved = TemplateRegistry([SearchDir("builtin", TEMPLATES)]).resolve(name)
    except TemplateError as error:
        issue(f"tag policy '{name}' cannot be loaded: {error.issues[0].message}")
        return [], {}
    if resolved.kind != "tag-policy":
        issue(f"'{name}' is a {resolved.kind} template, not a tag policy")
        return [], {}
    return list(resolved.spec["required_tags"]), dict(resolved.spec.get("scope") or {})


def load_set(name: str) -> Tuple[model.Policy, ...]:
    """The policies of a shipped set, by the set's name (sorted by id)."""
    if name not in SET_NAMES:
        raise KeyError(f"no shipped policy set named '{name}'")
    with _LOCK:
        if name not in _CACHE:
            original = loader._tag_policy_rules
            loader._tag_policy_rules = _shipped_tag_policy_rules
            try:
                loaded = loader.load([BUILTIN_DIR / name], root=BUILTIN_DIR)
            finally:
                loader._tag_policy_rules = original
            _CACHE[name] = tuple(sorted(loaded.policies, key=lambda p: p.id))
        return _CACHE[name]


def policy_sets() -> Dict[str, Any]:
    """``{set name: policies}`` of every shipped set."""
    return {name: load_set(name) for name in SET_NAMES}
