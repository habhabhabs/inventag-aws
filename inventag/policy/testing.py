"""``inventag policy test``: run policy fixtures (v15-policy-spec.md section 5).

A fixture is a YAML file ``tests/<policy name>/<name>.yaml`` next to the
policies. It holds rows, the date, optional waivers, baseline rows and unread
units, and the expected result of every row. The fixture runs through the
engine on a snapshot built from its rows, so it needs no AWS call and no
scan.

Every row of ``resources`` must be named in ``expect``: a selected row with its
result, any other row with ``out_of_scope``. A missing or an extra expectation
fails the fixture. ``expect_units`` (optional) lists the units that the policy
must report as not read; the spec names the field without its shape, so an
entry is ``{account, service, region}`` and the set must be equal.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..templating.errors import TemplateIssue
from ..templating.schema import NAME_PATTERN
from . import engine, loader, model
from .schema import PolicyError, Validator, parse_date, validate_document

FIELDS = (
    "policy",
    "now",
    "units_not_read",
    "resources",
    "baseline_resources",
    "waivers",
    "expect",
    "expect_units",
)
REQUIRED = ("policy", "now", "resources", "expect")
EXPECTED_RESULTS = model.RESULTS + ("out_of_scope",)
SUFFIXES = (".yaml", ".yml")


@dataclass
class FixtureResult:
    name: str  # "<policy name>/<file name>"
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class Report:
    results: List[FixtureResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)


@dataclass
class Fixture:
    name: str
    policy: model.Policy
    now: dt.datetime
    units: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]
    baseline_rows: Optional[List[Dict[str, Any]]]
    waivers: List[model.Waiver]
    expect: List[Tuple[str, str]]
    expect_units: Optional[List[Tuple[str, str, str]]]


def _fixture_files(directory: Path) -> List[Path]:
    found = []
    for tests in sorted(directory.rglob("tests")):
        if not tests.is_dir():
            continue
        for folder in sorted(p for p in tests.iterdir() if p.is_dir()):
            for path in sorted(folder.iterdir()):
                if path.is_file() and path.suffix in SUFFIXES:
                    found.append(path)
    return found


def _list_of_mappings(v: Validator, value: Any, path: Tuple[Any, ...]) -> bool:
    if not isinstance(value, list):
        v.add(path, "must be a list")
        return False
    ok = True
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            v.add(path + (i,), "must be a mapping (key: value pairs)")
            ok = False
    return ok


def _parse(
    doc: loader.Document, by_name: Dict[str, model.Policy], directory: Path
) -> Tuple[Optional[Fixture], List[TemplateIssue]]:
    v = Validator(doc.file, doc.line_of)
    data = doc.data
    header = ["format_version", "kind", "name", "description", "spec"]
    if not v.fields(data, (), header, ["format_version", "kind", "name", "spec"]):
        return None, v.issues
    if data.get("format_version") not in (None, 1):
        v.add(("format_version",), "must be 1")
    if data.get("kind") not in (None, "policy-test"):
        v.add(("kind",), "must be policy-test")
    name = data.get("name")
    if name is not None and not (
        isinstance(name, str) and NAME_PATTERN.fullmatch(name)
    ):
        v.add(
            ("name",),
            "must use lower-case letters, digits and hyphens (at most 63 characters)",
        )
    spec = data.get("spec")
    if spec is None or not v.fields(spec, ("spec",), FIELDS, REQUIRED):
        return None, v.issues

    policy = None
    wanted = spec.get("policy")
    if wanted is not None and v.text(wanted, ("spec", "policy")):
        policy = by_name.get(wanted)
        folder = doc.path.parent.name
        if policy is None:
            v.add(
                ("spec", "policy"),
                f"no policy named '{wanted}' in this folder; use a name shown by "
                "'inventag policy list'.",
            )
        elif folder != wanted:
            v.add(
                ("spec", "policy"),
                f"the fixture is in tests/{folder} but tests the policy "
                f"'{wanted}'; move it to tests/{wanted}.",
            )
            policy = None

    now = None
    if spec.get("now") is not None:
        day = parse_date(spec["now"])
        if day is None:
            v.add(("spec", "now"), "must be a date YYYY-MM-DD")
        else:
            now = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)

    rows = spec.get("resources")
    rows_ok = rows is not None and _list_of_mappings(v, rows, ("spec", "resources"))
    base = spec.get("baseline_resources")
    base_ok = base is None or _list_of_mappings(v, base, ("spec", "baseline_resources"))
    units = spec.get("units_not_read")
    units_ok = units is None or _list_of_mappings(v, units, ("spec", "units_not_read"))

    expect: List[Tuple[str, str]] = []
    entries = spec.get("expect")
    if entries is not None and not isinstance(entries, list):
        v.add(("spec", "expect"), "must be a list")
    for i, entry in enumerate(entries or []):
        path = ("spec", "expect", i)
        if not v.fields(entry, path, ["resource", "result"], ["resource", "result"]):
            continue
        if entry.get("result") is not None and entry["result"] not in EXPECTED_RESULTS:
            v.add(path + ("result",), f"must be one of {', '.join(EXPECTED_RESULTS)}")
        elif isinstance(entry.get("resource"), str) and entry.get("result"):
            expect.append((entry["resource"], entry["result"]))
        elif entry.get("resource") is not None:
            v.add(path + ("resource",), "must be text")

    expect_units = None
    if spec.get("expect_units") is not None:
        expect_units = []
        listed = spec["expect_units"]
        if not isinstance(listed, list):
            v.add(("spec", "expect_units"), "must be a list")
        for i, entry in enumerate(listed if isinstance(listed, list) else []):
            path = ("spec", "expect_units", i)
            keys = ["account", "service", "region"]
            if v.fields(entry, path, keys, keys):
                expect_units.append(tuple(str(entry.get(k, "")) for k in keys))

    waivers: List[model.Waiver] = []
    if spec.get("waivers") is not None and now is not None:
        shaped = {
            "format_version": 1,
            "kind": "waivers",
            "name": "fixture",
            "spec": {"waivers": spec["waivers"]},
        }
        _, found = validate_document(shaped, doc.file, doc.line_of, now)
        v.issues.extend(found)
        if not found:
            for entry in spec["waivers"]:
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
    if v.issues or not (policy and now and rows_ok and base_ok and units_ok):
        return None, v.issues
    return (
        Fixture(
            name=f"{doc.path.parent.name}/{doc.path.name}",
            policy=policy,
            now=now,
            units=list(units or []),
            rows=list(rows),
            baseline_rows=list(base) if base is not None else None,
            waivers=waivers,
            expect=expect,
            expect_units=expect_units,
        ),
        v.issues,
    )


def _snapshot(fixture: Fixture, rows, units=None) -> Dict[str, Any]:
    tags: Dict[str, Any] = {}
    if units is not None:
        tags["units_not_read"] = units
    return {
        "metadata": {"timestamp": fixture.now.isoformat(), "tags": tags},
        "resources": rows,
    }


def run_fixture(fixture: Fixture) -> FixtureResult:
    """Evaluate one fixture and compare the result with ``expect``."""
    snapshot = _snapshot(fixture, fixture.rows, fixture.units)
    baseline = (
        _snapshot(fixture, fixture.baseline_rows)
        if fixture.baseline_rows is not None
        else None
    )
    result = engine.evaluate(
        snapshot,
        [fixture.policy],
        fixture.waivers,
        baseline,
        fixture.now,
        include_pass=True,
        inventag_version="fixture",
    )
    got: Dict[str, str] = {}
    for finding in result["findings"]:
        got.setdefault(finding["resource"], finding["result"])
    for row in fixture.rows:
        got.setdefault(model.resource(row), "out_of_scope")

    problems: List[str] = []
    wanted: Dict[str, str] = {}
    for resource, expected in fixture.expect:
        if resource in wanted:
            problems.append(f"{resource}: listed twice in expect")
        wanted.setdefault(resource, expected)
    for resource in sorted(set(got) | set(wanted)):
        if resource not in wanted:
            problems.append(
                f"{resource}: no expectation for this row (got {got[resource]})"
            )
        elif resource not in got:
            problems.append(
                f"{resource}: expected {wanted[resource]}, but the fixture has "
                "no such row"
            )
        elif wanted[resource] != got[resource]:
            problems.append(
                f"{resource}: expected {wanted[resource]}, got {got[resource]}"
            )
    if fixture.expect_units is not None:
        listed = set(fixture.expect_units)
        reported = {
            (u["account"], u["service"], u["region"])
            for u in result["not_evaluated_units"]
        }
        for unit in sorted(listed - reported):
            problems.append(
                "unit {}/{}/{}: expected not read, but the policy reports no "
                "such unit".format(*unit)
            )
        for unit in sorted(reported - listed):
            problems.append(
                "unit {}/{}/{}: reported not read, but expect_units does not "
                "list it".format(*unit)
            )
    return FixtureResult(fixture.name, problems)


def run(directory: Path) -> Report:
    """Run every fixture under ``directory``.

    Raises :class:`PolicyError` (exit code 1) when a policy or a fixture is not
    valid; nothing runs in that case.
    """
    directory = Path(directory)
    loaded = loader.load([directory], root=directory)
    by_name = {p.name: p for p in loaded.policies}
    issues: List[TemplateIssue] = []
    fixtures: List[Fixture] = []
    for path in _fixture_files(directory):
        try:
            docs = loader.read_documents(path, directory)
        except PolicyError as error:
            issues.extend(error.issues)
            continue
        if len(docs) > 1:
            issues.append(
                TemplateIssue("a fixture file holds one document", docs[0].file, 1)
            )
            continue
        fixture, found = _parse(docs[0], by_name, directory)
        issues.extend(found)
        if fixture is not None:
            fixtures.append(fixture)
    if issues:
        raise PolicyError(issues)
    fixtures.sort(key=lambda f: f.name)
    covered = {f.policy.name for f in fixtures}
    return Report(
        results=[run_fixture(f) for f in fixtures],
        warnings=[
            f"policy {p.name} has no fixtures; add tests/{p.name}/NAME.yaml."
            for p in sorted(loaded.policies, key=lambda p: p.name)
            if p.name not in covered
        ],
    )
