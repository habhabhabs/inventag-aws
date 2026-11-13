"""The three Excel writers name sheets the same way (`-` for characters Excel
forbids, 31 characters, ` (2)` for a repeat, `History` avoided)."""

import pytest

from inventag.reporting.converter import _sheet_name
from inventag.reporting.document_generator import safe_sheet_name
from inventag.templating.columns import unique_sheet_name

NAMES = [
    "S3",
    "a/b:c?*[x]\\",
    "History",
    "x" * 40,
    "x" * 40,
    "Route 53",
    "route 53",
]


def _converter(names):
    used, out = [], []
    for n in names:
        out.append(_sheet_name(n, used))
        used.append(out[-1])
    return out


def _generator(names):
    taken = set()
    return [safe_sheet_name(n, taken) for n in names]


def _templating(names):
    used = set()
    return [unique_sheet_name(n, used) for n in names]


@pytest.mark.parametrize("writer", [_generator, _templating])
def test_writers_agree(writer):
    assert writer(NAMES) == _converter(NAMES)


def test_expected_names():
    names = _converter(NAMES)
    assert names[1] == "a-b-c---x--"
    assert names[2] == "History (2)"
    assert names[3] == "x" * 31 and names[4] == "x" * 27 + " (2)"
    assert names[6] == "route 53 (2)"
    assert all(len(n) <= 31 for n in names)
