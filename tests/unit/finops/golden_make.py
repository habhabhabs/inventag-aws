"""Write ``golden/checks-v143.json`` from ``inventag.finops.checks.run_checks``.

Run ONLY against the v1.4.3 code (base f5ca9e24); the file is committed and
never regenerated from the engine-backed module.

    git show f5ca9e24:inventag/finops/checks.py > inventag/finops/_v143.py
    python tests/unit/finops/golden_make.py inventag.finops._v143
    rm inventag/finops/_v143.py

(without an argument, ``inventag.finops.checks`` is used: only before it
changes).
"""

import importlib
import json
import sys
from pathlib import Path

from tests.unit.finops import golden_cases


def render(module: str = "inventag.finops.checks") -> str:
    checks = importlib.import_module(module)
    out = {
        name: checks.run_checks(rows, units, started)
        for name, (rows, units, started) in golden_cases.cases().items()
    }
    return json.dumps(out, indent=1) + "\n"


if __name__ == "__main__":
    target = Path(__file__).parent / "golden" / "checks-v143.json"
    target.write_text(render(*sys.argv[1:2]))
    print(target, target.stat().st_size)
