"""Generate the template field reference (Markdown) from the schema.

Run ``python -m inventag.templating.reference --write`` after changing
``schema.py``. A unit test fails if ``docs/templates/reference.md`` is out of
date.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from .schema import SPECS, TOP_LEVEL, TYPE_LABELS, Field

BEGIN = "<!-- BEGIN GENERATED FIELD REFERENCE: do not edit by hand -->"
END = "<!-- END GENERATED FIELD REFERENCE -->"
DOC = Path(__file__).resolve().parents[2] / "docs" / "templates" / "reference.md"
HEADINGS = {
    "report": "Report templates (`kind: report`)",
    "tag-policy": "Tag-policy templates (`kind: tag-policy`)",
    "config": "Config templates (`kind: config`)",
}


def _default(spec: Field) -> str:
    if spec.required:
        return "required"
    if spec.type == "mapping" and spec.fields:
        return "see below"
    if spec.default is None:
        return "not set"
    if spec.default == "":
        return "empty"
    if (
        isinstance(spec.default, list)
        and spec.default
        and isinstance(spec.default[0], dict)
    ):
        return "see the built-in `standard-bom`"
    return f"`{json.dumps(spec.default)}`".replace('`"', "`").replace('"`', "`")


def _type(spec: Field) -> str:
    label = TYPE_LABELS.get(spec.type, spec.type)
    if spec.type == "enum":
        return "one of " + ", ".join(f"`{c}`" for c in spec.choices)
    if spec.type == "list" and spec.item is not None:
        inner = "mappings" if spec.item.fields else TYPE_LABELS.get(spec.item.type, "")
        if spec.item.type == "enum":
            inner = "values from " + ", ".join(f"`{c}`" for c in spec.item.choices)
        return f"list of {inner}"
    bounds = []
    if spec.minimum is not None:
        bounds.append(f"min {spec.minimum}")
    if spec.maximum is not None:
        bounds.append(f"max {spec.maximum}")
    return label + (f" ({', '.join(bounds)})" if bounds else "")


def _rows(fields: Dict[str, Field], prefix: str) -> List[str]:
    rows: List[str] = []
    nested: List[str] = []
    for name, spec in fields.items():
        path = f"{prefix}{name}"
        description = spec.description.replace("|", "\\|").replace("\n", " ")
        rows.append(f"| `{path}` | {_type(spec)} | {_default(spec)} | {description} |")
        if spec.type == "mapping" and spec.fields:
            nested.extend(_rows(spec.fields, f"{path}."))
        if spec.type == "list" and spec.item is not None and spec.item.fields:
            nested.extend(_rows(spec.item.fields, f"{path}[]."))
    return rows + nested


def render() -> str:
    header = "| Field | Type | Default | What it does |\n|---|---|---|---|"
    parts = [BEGIN, "", "### Fields in every template", "", header]
    parts.extend(_rows(TOP_LEVEL, ""))
    for kind, fields in SPECS.items():
        parts += ["", f"### {HEADINGS[kind]}", "", header]
        parts.extend(_rows(fields, "spec."))
    parts += ["", END]
    return "\n".join(parts) + "\n"


def update(text: str) -> str:
    start, end = text.index(BEGIN), text.index(END) + len(END)
    return text[:start] + render().rstrip("\n") + text[end:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help=f"Update {DOC}")
    args = parser.parse_args()
    if args.write:
        DOC.write_text(update(DOC.read_text()))
        print(f"Updated {DOC}")
    else:
        print(render())


if __name__ == "__main__":
    main()
