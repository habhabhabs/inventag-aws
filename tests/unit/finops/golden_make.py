"""Write ``golden/checks-v143.json`` from ``inventag.finops.checks.run_checks``.

Run ONLY against the v1.4.3 code (base f5ca9e24); the file is committed and
never regenerated from the engine-backed module.

    python tests/unit/finops/golden_make.py
"""

import json
from pathlib import Path

from inventag.finops import checks
from tests.unit.finops import golden_cases


def render() -> str:
    out = {
        name: checks.run_checks(rows, units, started)
        for name, (rows, units, started) in golden_cases.cases().items()
    }
    return json.dumps(out, indent=1) + "\n"


if __name__ == "__main__":
    target = Path(__file__).parent / "golden" / "checks-v143.json"
    target.write_text(render())
    print(target, target.stat().st_size)
