"""Run the fixtures of a shipped set (spec 5): what ``inventag policy test``
does, written for the tests because package P4's command is not in this branch.

A fixture is ``tests/<policy name>/<file>.yaml`` next to the policy files,
``kind: policy-test``. Every row of the fixture is either named in ``expect``
with its result (and reason, when given) or is listed as ``out_of_scope``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, List

import yaml

from inventag.policy import engine, loader, model


def fixtures_of(set_dir: Path) -> List[Path]:
    return sorted((set_dir / "tests").rglob("*.yaml"))


def run_fixture(set_dir: Path, path: Path) -> List[str]:
    """The problems of one fixture; an empty list means the fixture holds."""
    doc = yaml.safe_load(path.read_text())
    problems: List[str] = []
    if doc.get("kind") != "policy-test" or doc.get("format_version") != 1:
        return [f"{path.name}: not a policy-test document"]
    spec = doc["spec"]
    loaded = loader.load([set_dir])
    by_name = {p.name: p for p in loaded.policies}
    policy = by_name[spec["policy"]]
    snapshot: Dict[str, Any] = {
        "metadata": {
            "timestamp": "2026-11-20T00:00:00+00:00",
            "tags": {"units_not_read": spec.get("units_not_read") or []},
        },
        "resources": spec["resources"],
    }
    result = engine.evaluate(
        snapshot,
        [policy],
        now=(
            dt.datetime.fromisoformat(str(spec["now"]) + "T00:00:00+00:00")
            if len(str(spec["now"])) == 10
            else spec["now"]
        ),
        include_pass=True,
    )
    got: Dict[str, Any] = {}
    for finding in result["findings"]:
        got[finding["resource"]] = (finding["result"], finding.get("reason"))
    for row in spec["resources"]:
        got.setdefault(model.resource(row), ("out_of_scope", None))
    wanted: Dict[str, Any] = {}
    for item in spec["expect"]:
        wanted[item["resource"]] = (item["result"], item.get("reason"))
    for resource in sorted(set(got) | set(wanted)):
        if got.get(resource) != wanted.get(resource):
            problems.append(
                f"{path.name}: {resource}: expected {wanted.get(resource)}, "
                f"got {got.get(resource)}"
            )
    if "expect_units" in spec:
        units = [
            {k: v for k, v in u.items() if k != "policy"}
            for u in result["not_evaluated_units"]
        ]
        if units != spec["expect_units"]:
            problems.append(
                f"{path.name}: units expected {spec['expect_units']}, got {units}"
            )
    return problems
