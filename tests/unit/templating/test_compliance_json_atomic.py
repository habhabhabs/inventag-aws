"""The tag compliance JSON is written whole or not at all (register row A-14)."""

import json
import os
import stat

import pytest

from inventag.templating.runner import _write_json_atomically


def test_compliance_json_mode_is_what_open_gives(tmp_path):
    umask = os.umask(0o022)
    try:
        path = tmp_path / "tag_compliance_x.json"
        _write_json_atomically(str(path), {"a": 1})
    finally:
        os.umask(umask)
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}
    assert os.listdir(tmp_path) == ["tag_compliance_x.json"]


def test_compliance_json_text_is_as_in_v121(tmp_path):
    path = tmp_path / "c.json"
    _write_json_atomically(str(path), {"name": "café"})
    assert path.read_text(encoding="utf-8") == '{\n  "name": "caf\\u00e9"\n}'


def test_failed_write_keeps_the_old_file_and_leaves_no_partial(tmp_path):
    path = tmp_path / "tag_compliance_x.json"
    _write_json_atomically(str(path), {"old": True})

    class Unserialisable:
        def __str__(self):
            raise RuntimeError("cannot serialise")

    with pytest.raises(RuntimeError):
        _write_json_atomically(str(path), {"new": Unserialisable()})
    assert json.loads(path.read_text()) == {"old": True}
    assert os.listdir(tmp_path) == ["tag_compliance_x.json"]


def test_failed_first_write_leaves_no_file(tmp_path):
    path = tmp_path / "tag_compliance_x.json"

    class Unserialisable:
        def __str__(self):
            raise RuntimeError("cannot serialise")

    with pytest.raises(RuntimeError):
        _write_json_atomically(str(path), {"new": Unserialisable()})
    assert os.listdir(tmp_path) == []
