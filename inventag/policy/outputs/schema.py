"""The two schemas that ship in the package (``schemas/*.json``).

``policy-findings-1.json`` is spec 3.3 with the reasons of amendment 1; its
``$id`` is a URN, not a URL. ``sarif-2.1.0-subset.json`` is our own short
schema for the part of SARIF 2.1.0 the SARIF writer produces: the OASIS schema
is not shipped (its licence was not checked, see the P3 report).
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_DIR = Path(__file__).resolve().parent / "schemas"


@lru_cache(maxsize=None)
def _load(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8")


def findings_schema() -> Dict[str, Any]:
    """A fresh copy of the findings schema (JSON Schema 2020-12)."""
    return json.loads(_load("policy-findings-1.json"))


def sarif_schema() -> Dict[str, Any]:
    """A fresh copy of our own SARIF subset schema (JSON Schema 2020-12)."""
    return json.loads(_load("sarif-2.1.0-subset.json"))
