#!/usr/bin/env python3
"""Smoke scan of a packaged InvenTag against a local moto server (plan 3.5).

The moto server runs in this Python, outside the build under test. The script
seeds an EC2 instance and an S3 bucket, runs the given ``inventag`` with
``AWS_ENDPOINT_URL`` pointing at the server and dummy credentials, then checks
the exit code, the Excel file and the read-only guard's counters in the
``--audit-output`` file:

- the guard was on (``read_only_enforced``);
- no call was blocked and every call was allowed (``blocked_calls == 0``,
  ``allowed_calls == total_calls > 0``);
- every operation starts with a read prefix that the guard lists;
- the seeded resources were read (``ec2 DescribeInstances``, ``s3 ListBuckets``).

    python scripts/packaging/smoke_scan.py -- /opt/inventag/inventag

Needs moto with its server extra (``pip install "moto[server]"``) in the Python
running this. Opens sockets on 127.0.0.1 only. Exit 0 when every check
passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

REGION = "us-east-1"
DUMMY = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_DEFAULT_REGION": REGION,
}
MUST_SEE = (("ec2", "DescribeInstances"), ("s3", "ListBuckets"))


def seed(endpoint: str) -> None:
    import boto3

    kw = dict(region_name=REGION, endpoint_url=endpoint, **_creds())
    ec2 = boto3.client("ec2", **kw)
    image = ec2.describe_images()["Images"][0]["ImageId"]
    ec2.run_instances(
        ImageId=image,
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.micro",
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "smoke"}]}
        ],
    )
    s3 = boto3.client("s3", **kw)
    s3.create_bucket(Bucket="inventag-smoke-bucket")
    s3.put_bucket_tagging(
        Bucket="inventag-smoke-bucket",
        Tagging={"TagSet": [{"Key": "Owner", "Value": "smoke"}]},
    )


def _creds() -> Dict[str, str]:
    return {
        "aws_access_key_id": DUMMY["AWS_ACCESS_KEY_ID"],
        "aws_secret_access_key": DUMMY["AWS_SECRET_ACCESS_KEY"],
    }


def check_audit(report: dict) -> List[str]:
    """Problems with the guard's counters; empty when they are as expected."""
    problems = []
    if report.get("read_only_enforced") is not True:
        problems.append("the read-only guard was not on")
    total = report.get("total_calls", 0)
    if not total:
        problems.append("the guard counted no AWS call")
    if report.get("blocked_calls") != 0 or report.get("blocked"):
        problems.append(f"blocked calls: {report.get('blocked_calls')}")
    if report.get("allowed_calls") != total:
        problems.append(f"allowed {report.get('allowed_calls')} of {total} calls")
    prefixes = tuple(report.get("allowed_prefixes") or ())
    for op in report.get("operations", []):
        if not op.get("allowed") or not op["operation"].startswith(prefixes):
            problems.append(f"not a read: {op['service']} {op['operation']}")
    seen = {(op["service"], op["operation"]) for op in report.get("operations", [])}
    for service, operation in MUST_SEE:
        if (service, operation) not in seen:
            problems.append(f"not called: {service} {operation}")
    return problems


def run(command: Sequence[str], keep: Optional[Path]) -> int:
    import logging

    from moto.server import ThreadedMotoServer

    # moto answers unknown requests with a 500 and a traceback: keep it quiet.
    logging.getLogger("werkzeug").setLevel(logging.CRITICAL)
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    try:
        host, port = server.get_host_and_port()
        endpoint = f"http://{host}:{port}"
        seed(endpoint)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            audit = Path(tmp) / "audit.json"
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": tmp,
                "LANG": "C.UTF-8",
                "AWS_ENDPOINT_URL": endpoint,
                "AWS_CONFIG_FILE": str(Path(tmp) / "none"),
                "AWS_SHARED_CREDENTIALS_FILE": str(Path(tmp) / "none"),
                **DUMMY,
            }
            argv = [
                *command,
                "--create-excel",
                "--account-regions",
                REGION,
                "--output-directory",
                str(out),
                "--audit-output",
                str(audit),
            ]
            started = time.monotonic()
            result = subprocess.run(
                argv, env=env, capture_output=True, text=True, timeout=900
            )
            seconds = time.monotonic() - started
            problems = []
            if result.returncode != 0:
                problems.append(f"exit code {result.returncode}")
            excel = sorted(out.rglob("*.xlsx")) if out.exists() else []
            if not excel:
                problems.append("no Excel file written")
            report = json.loads(audit.read_text("utf-8")) if audit.is_file() else {}
            if not report:
                problems.append("no audit file written")
            else:
                problems += check_audit(report)
            if keep is not None:
                keep.mkdir(parents=True, exist_ok=True)
                (keep / "stdout.txt").write_text(result.stdout, "utf-8")
                (keep / "stderr.txt").write_text(result.stderr, "utf-8")
                if report:
                    (keep / "audit.json").write_text(
                        json.dumps(report, indent=2), "utf-8"
                    )
        print(
            f"scan: exit {result.returncode} in {seconds:.1f} s; Excel files: {len(excel)}"
        )
        if report:
            print(
                "guard: total {total_calls}, allowed {allowed_calls}, blocked "
                "{blocked_calls}, operations {n}".format(
                    n=len(report["operations"]), **report
                )
            )
        for p in problems:
            print(f"SMOKE SCAN: {p}", file=sys.stderr)
        if problems:
            print(result.stderr[-4000:], file=sys.stderr)
        print("smoke scan: " + ("FAIL" if problems else "pass"))
        return 1 if problems else 0
    finally:
        server.stop()


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print(
            "usage: smoke_scan.py [--keep DIR] -- <inventag command...>",
            file=sys.stderr,
        )
        return 2
    split = argv.index("--")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--keep", type=Path, help="copy stdout, stderr and the audit here"
    )
    ns = parser.parse_args(argv[:split])
    return run(argv[split + 1 :], ns.keep)


if __name__ == "__main__":
    sys.exit(main())
