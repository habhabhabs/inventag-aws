"""--audit-output on a path that is not a regular file behaves as in v1.2.1
(review L2).

v1.2.1 (measured on a5398a2 with ``--validate-config``): a symlink gives exit 1
with "--audit-output: cannot write '<path>': Too many levels of symbolic links"
and the link and its target stay as they were; a named pipe receives the JSON
(exit 0). The atomic write of A-14 replaced both with a regular file. A
regular file or a new path keeps the atomic write.
"""

import json
import os
import threading

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    empty_aws,
    run_cli,
)


def test_a_symlink_is_refused_and_left_as_it_is(
    empty_aws, tmp_path, capsys  # noqa: F811
):
    target = tmp_path / "target.json"
    target.write_text("old")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    assert run_cli("--validate-config", "--audit-output", str(link)) == 1
    out = capsys.readouterr()
    assert (
        f"--audit-output: cannot write '{link}': Too many levels of symbolic links"
        in out.out + out.err
    )
    assert link.is_symlink() and os.readlink(link) == str(target)
    assert target.read_text() == "old"


def test_a_named_pipe_receives_the_audit_json(empty_aws, tmp_path):  # noqa: F811
    pipe = tmp_path / "audit.pipe"
    os.mkfifo(pipe)
    received = []

    def read():
        with open(pipe, encoding="utf-8") as reader:
            received.append(reader.read())

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    assert run_cli("--validate-config", "--audit-output", str(pipe)) == 0
    reader.join(10)
    assert not reader.is_alive()
    assert isinstance(json.loads(received[0]), dict)
    assert pipe.is_fifo()
