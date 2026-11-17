"""The change report is the same, byte for byte, in every Python process.

Python randomises the order of sets of strings per process (PYTHONHASHSEED).
The change report must not depend on it: two runs over the same snapshots
must give the same file.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = textwrap.dedent("""
    import json
    from dataclasses import asdict
    from inventag.state import ChangelogGenerator, DeltaDetector

    def row(tags, names):
        return {
            "service": "S3", "type": "Bucket", "id": "b1",
            "arn": "arn:aws:s3:::b1", "region": "us-east-1", "tags": tags,
            "names": names, "raw_data": {"Names": names, "Cfg": dict(tags)},
        }

    old = row({"a": "1"}, ["x"])
    new = row({k: str(i) for i, k in enumerate("abcdefgh")}, list("xpqrstuv"))
    report = DeltaDetector().detect_changes([old], [new], "s1", "s2")
    report.timestamp = "t"
    for c in report.modified_resources:
        c.timestamp = "t"
    changelog = ChangelogGenerator().generate_changelog(report, title="T")
    changelog.generation_timestamp = "t"
    print(changelog.to_markdown())
    print(json.dumps(asdict(report), default=str))
    """)


def _run(seed):
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    return subprocess.run(
        [sys.executable, "-c", SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    ).stdout


def test_change_report_does_not_depend_on_the_hash_seed():
    outputs = {_run(seed) for seed in (1, 2, 3, 4)}
    assert len(outputs) == 1
