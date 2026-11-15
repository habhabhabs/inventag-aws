"""--audit-output is written whole or not at all (A-14, the part in cli/):
a failing write keeps the old file and leaves no partial or temporary file."""

import json
import os

import pytest

from inventag.cli import safety


class Guard:
    def __init__(self, report):
        self._report = report

    def audit_report(self):
        return self._report


def test_a_failing_write_keeps_the_old_audit_file_and_leaves_nothing_else(tmp_path):
    path = tmp_path / "audit.json"
    safety.write_audit_output(Guard({"operations": ["old"]}), str(path))
    assert json.loads(path.read_text()) == {"operations": ["old"]}

    class Unwritable:
        pass  # json cannot serialise it, after the opening brace is written

    with pytest.raises(TypeError):
        safety.write_audit_output(Guard({"operations": Unwritable()}), str(path))
    assert json.loads(path.read_text()) == {"operations": ["old"]}
    assert sorted(os.listdir(tmp_path)) == ["audit.json"]


def test_a_failing_first_write_leaves_no_file(tmp_path):
    path = tmp_path / "audit.json"

    class Unwritable:
        pass

    with pytest.raises(TypeError):
        safety.write_audit_output(Guard({"x": Unwritable()}), str(path))
    assert os.listdir(tmp_path) == []


def test_a_good_write_is_owner_only_and_complete(tmp_path):
    path = tmp_path / "sub" / "audit.json"
    returned = safety.write_audit_output(Guard({"operations": []}), str(path))
    assert returned == str(path)
    assert json.loads(path.read_text()) == {"operations": []}
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert os.listdir(path.parent) == ["audit.json"]


@pytest.mark.parametrize("umask", [0o022, 0o077])
def test_audit_file_is_owner_only_under_any_umask_as_in_v1_2_1(tmp_path, umask):
    old = os.umask(umask)
    try:
        path = tmp_path / "audit.json"
        safety.write_audit_output(Guard({"operations": []}), str(path))
    finally:
        os.umask(old)
    assert oct(path.stat().st_mode & 0o777) == "0o600"
