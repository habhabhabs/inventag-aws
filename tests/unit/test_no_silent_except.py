"""D4: no silent ``except Exception`` in discovery.

Every handler of ``Exception`` (or a bare ``except``) in ``inventag/discovery``
must do one of these: log at WARNING or above, write a coverage-ledger entry
(or call one of discovery's recording helpers), re-raise, or carry the comment
``# silent-ok: <reason>`` on its ``except`` line for a fallback that is not a
failure (a probe, a parse with a default). A DEBUG line alone is not enough:
a failure that only the debug log knows about looks like "nothing there".

The network, security and cost analyzers belong to other owners and are not scanned.
"""

import ast
import re
from pathlib import Path

import pytest

DISCOVERY = Path(__file__).resolve().parents[2] / "inventag" / "discovery"
NOT_SCANNED = {"network_analyzer.py", "security_analyzer.py", "cost_analyzer.py"}
LOUD = {
    "warning",
    "error",
    "exception",
    "critical",
    "_warn_once",
    "record",
    "_record_billing",
    "_record_detail_failures",
    "_detail_failure",
    "_unreadable_answer",
    "_record_certificate_failure",
}
MARK = re.compile(r"#\s*silent-ok:\s*\S.{8,}")


def silent_handlers(source: str):
    """Line numbers of the ``except Exception`` handlers that say nothing."""
    lines = source.splitlines()
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        names = (
            {n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)}
            if node.type is not None
            else {"Exception"}
        )
        if not names & {"Exception", "BaseException"}:
            continue
        loud = False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise):
                loud = True
            elif isinstance(sub, ast.Call):
                fn = sub.func
                name = (
                    fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                )
                loud = loud or name in LOUD
        marked = MARK.search(lines[node.lineno - 1]) or (
            node.lineno < len(lines) and MARK.search(lines[node.lineno])
        )
        if not loud and not marked:
            found.append(node.lineno)
    return found


def test_the_check_sees_a_silent_handler_and_accepts_the_loud_ones():
    silent = "try:\n    f()\nexcept Exception as e:\n    log.debug(e)\n"
    assert silent_handlers(silent) == [3]
    assert silent_handlers("try:\n    f()\nexcept Exception:\n    pass\n") == [3]
    for body in (
        "log.warning(e)",
        "self._warn_once('k', 'm')",
        "ledger.record(outcome='error')",
        "raise",
    ):
        assert (
            silent_handlers(f"try:\n    f()\nexcept Exception as e:\n    {body}\n")
            == []
        )
    marked = (
        "try:\n    f()\nexcept Exception:  # silent-ok: a probe, the default follows\n"
        "    pass\n"
    )
    assert silent_handlers(marked) == []
    bare_reason = "try:\n    f()\nexcept Exception:  # silent-ok:\n    pass\n"
    assert silent_handlers(bare_reason) == [3]


@pytest.mark.parametrize(
    "path",
    sorted(p for p in DISCOVERY.glob("*.py") if p.name not in NOT_SCANNED),
    ids=lambda p: p.name,
)
def test_no_silent_except_exception_in_discovery(path):
    assert silent_handlers(path.read_text()) == []
