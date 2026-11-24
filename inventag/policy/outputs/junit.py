"""JUnit XML: one ``testsuite`` per policy file, one ``testcase`` per policy;
``failure`` when the policy has a fail (the first 20 resources and the count),
``skipped`` when it has none but something is not evaluated; ``time="0"``; no
``timestamp`` attribute (spec 3.4). No raw value is ever written here."""

from typing import Any, Dict, List, Mapping
from xml.sax.saxutils import escape, quoteattr

from . import _common
from ._common import clean

MAX_LISTED = 20


def _attr(value: Any) -> str:
    return quoteattr(clean(value))


def _text(value: Any) -> str:
    return escape(clean(value))


def render(data: Mapping[str, Any]) -> str:
    grouped = _common.findings_by_policy(data)
    units: Dict[str, int] = {}
    for u in data.get("not_evaluated_units") or []:
        units[u["policy"]] = units.get(u["policy"], 0) + 1
    unevaluated = {p["policy"] for p in data.get("not_evaluated_policies") or []}
    suites: Dict[str, List[Mapping[str, Any]]] = {}
    for policy in data.get("policies") or []:
        suites.setdefault(policy.get("file", ""), []).append(policy)

    body: List[str] = []
    total = fails = skips = 0
    for file in sorted(suites):
        cases: List[str] = []
        s_fail = s_skip = 0
        for policy in sorted(suites[file], key=lambda p: p["id"]):
            pid = policy["id"]
            c = _common.counts(policy)
            listed = grouped.get(pid, [])
            failed = [f for f in listed if f["result"] == "fail"]
            n_fail = max(c.get("fail", 0), len(failed))
            n_skip = c.get("not_evaluated", 0) + units.get(pid, 0)
            n_skip += 1 if pid in unevaluated else 0
            head = f'    <testcase classname={_attr(file)} name={_attr(pid)} time="0"'
            if n_fail:
                s_fail += 1
                noun = "failing resource" if n_fail == 1 else "failing resources"
                names = [_text(f["resource"]) for f in failed[:MAX_LISTED]]
                more = n_fail - len(names)
                detail = "\n".join(names)
                if more > 0:
                    detail += f"\nand {more} more"
                cases.append(
                    f"{head}>\n      <failure message={_attr(f'{n_fail} {noun}')} "
                    f"type={_attr(policy.get('severity', ''))}>"
                    f"{_text(pid)}: {n_fail} {noun}\n{detail}</failure>\n"
                    "    </testcase>"
                )
            elif n_skip:
                s_skip += 1
                cases.append(
                    f"{head}>\n      <skipped message="
                    f"{_attr(f'{n_skip} not evaluated')}/>\n    </testcase>"
                )
            else:
                cases.append(head + "/>")
        total += len(cases)
        fails += s_fail
        skips += s_skip
        body.append(
            f'  <testsuite name={_attr(file)} tests="{len(cases)}" '
            f'failures="{s_fail}" errors="0" skipped="{s_skip}" time="0">\n'
            + "\n".join(cases)
            + "\n  </testsuite>"
        )
    head = (
        f'<testsuites name="InvenTag" tests="{total}" failures="{fails}" '
        f'errors="0" skipped="{skips}" time="0"'
    )
    inner = ("\n" + "\n".join(body) + "\n</testsuites>") if body else "/>"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + head
        + (">" + inner if body else inner)
        + "\n"
    )
