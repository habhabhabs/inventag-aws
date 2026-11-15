"""Files the generator writes itself are written whole or not at all (A-14).

v1.2.1 opened the JSON output and the change log in place: a write that
failed part-way left a partial (or empty) file, and replaced a file of the
same name that was there before. Now each is written to a temporary file in
the same folder and moved into place (``reporting.safe_save``): a failing
write leaves no partial file and keeps the old one. Names and the owner-only
mode (0600) are as in v1.2.1.
"""

import datetime as real_datetime
import os
import stat
from unittest.mock import patch

from inventag.core import cloud_bom_generator as cbg
from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
from tests.unit.test_account_time_limit_and_failures import (  # noqa: F401
    CountingInventory,
    _contexts,
    aws,
)
from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    empty_aws,
    run_cli,
)

STAMP = "20261115_120000"


class FixedDatetime(real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        moment = real_datetime.datetime(2026, 11, 15, 12, 0, 0)
        return moment.replace(tzinfo=tz) if tz else moment


def _json_run(tmp_path):
    generator = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[object()],
            output_directory=str(tmp_path),
            enable_state_management=False,
        )
    )

    def establish():
        contexts = _contexts(["111111111111"])
        for account_id, ctx in contexts.items():
            ctx.session._account = account_id
        generator.account_contexts = dict(contexts)
        return contexts

    generator._establish_account_contexts = establish
    CountingInventory.fail = set()
    with patch.object(cbg, "AWSResourceInventory", CountingInventory):
        return generator.generate_multi_account_bom(output_formats=["json"])


def leftovers(folder):
    return [p.name for p in folder.iterdir() if p.name.endswith(".tmp")]


def test_a_failing_json_write_keeps_the_old_file(
    aws, tmp_path, monkeypatch
):  # noqa: F811
    monkeypatch.setattr(cbg, "datetime", FixedDatetime)
    target = tmp_path / f"multi_account_bom_{STAMP}.json"
    target.write_text("OLD")

    def broken_dump(data, f, **kwargs):
        f.write('{"resources": [')
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cbg.json, "dump", broken_dump)
    result = _json_run(tmp_path)
    assert result["success"] is False  # a format that failed fails the run
    assert target.read_text() == "OLD"
    assert leftovers(tmp_path) == []


def test_a_json_write_gives_the_same_name_and_mode(
    aws, tmp_path, monkeypatch
):  # noqa: F811
    monkeypatch.setattr(cbg, "datetime", FixedDatetime)
    result = _json_run(tmp_path)
    assert result["success"] is True
    target = tmp_path / f"multi_account_bom_{STAMP}.json"
    assert target.exists() and target.read_text().startswith("{")
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert leftovers(tmp_path) == []


def test_a_failing_change_log_write_keeps_the_old_file(
    empty_aws, tmp_path, monkeypatch  # noqa: F811
):
    args = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
    assert run_cli(*args) == 0  # first snapshot
    monkeypatch.setattr(cbg, "datetime", FixedDatetime)
    target = tmp_path / "out" / f"changelog_{STAMP}.md"
    target.write_text("OLD")

    class Broken:
        def to_markdown(self):
            raise ValueError("cannot render")

    with patch.object(
        cbg.ChangelogGenerator, "generate_changelog", return_value=Broken()
    ):
        assert run_cli(*args) == 0  # as in v1.2.1: the change log is optional
    assert target.read_text() == "OLD"
    assert leftovers(tmp_path / "out") == []


def test_a_change_log_keeps_its_name_and_mode(
    empty_aws, tmp_path, monkeypatch  # noqa: F811
):
    args = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]
    assert run_cli(*args) == 0
    monkeypatch.setattr(cbg, "datetime", FixedDatetime)
    assert run_cli(*args) == 0
    target = tmp_path / "out" / f"changelog_{STAMP}.md"
    assert target.exists()
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
