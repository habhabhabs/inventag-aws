#!/usr/bin/env python3
"""Benchmark an InvenTag scan against a synthetic AWS estate built in moto.

What it does
    1. Builds an estate of the size you ask for inside moto's in-memory AWS
       (S3 buckets, SQS queues, SNS topics, DynamoDB tables, VPCs, security
       groups, EC2 instances, Lambda functions; all tagged).
    2. Runs one InvenTag scan of it (``inventag.cli.main.main()`` in this
       process, Excel report, one region, no Cost Explorer calls).
    3. Prints how long the scan took, how many AWS API calls it made (from the
       read-only guard's audit, split by service) and the peak memory of the
       process.

What the numbers mean
    moto answers inside this process, so there is no network time. The scan
    time is InvenTag's own work plus moto's. Against real AWS the time is
    dominated by API latency and rate limits, so use the call counts to
    estimate that, not the seconds. Peak memory includes moto's copy of the
    estate; the report shows the memory before the scan too, so the scan's own
    growth is visible. moto also ships a few hundred default objects that are
    switched off here (``MOTO_EC2_LOAD_DEFAULT_AMIS=false``) so they do not
    count as part of the estate.

Run it
        python scripts/benchmark_scan.py                   # modest default size
        python scripts/benchmark_scan.py --scale 4         # 4 times as many
        python scripts/benchmark_scan.py --buckets 200 --queues 200
        python scripts/benchmark_scan.py --json result.json

    Counts (each defaults to the value shown, multiplied by --scale):
        --buckets 20  --queues 40  --topics 20  --tables 10  --vpcs 3
        --security-groups 30  --instances 20  --functions 10

Limits (a run that goes over stops with exit code 3 and says so)
    --time-limit SECONDS   default 170 (the whole run, estate included)
    --memory-limit MB      default 1400 (resident memory of this process)

Exit code
    0  finished and every created resource is in the report; 1  the scan failed
    or missed resources; 3  a limit was exceeded.

Needs the project's dev dependencies (moto). It makes no real AWS call: moto
intercepts every request and the credentials are fake.
"""

import argparse
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fake credentials and no metadata service, set before boto3 is imported.
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ.pop("AWS_SESSION_TOKEN", None)
os.environ.pop("AWS_PROFILE", None)
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["MOTO_EC2_LOAD_DEFAULT_AMIS"] = "false"

DEFAULT_COUNTS = {
    "buckets": 20,
    "queues": 40,
    "topics": 20,
    "tables": 10,
    "vpcs": 3,
    "security_groups": 30,
    "instances": 20,
    "functions": 10,
}
TAGS = [
    {"Key": "Owner", "Value": "platform"},
    {"Key": "Environment", "Value": "bench"},
]


# ---------------------------------------------------------------- measuring
def rss_mb() -> float:
    """Current resident memory of this process in MB (Linux), else the peak."""
    try:
        with open("/proc/self/statm") as handle:
            pages = int(handle.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / 1024 / 1024
    except (OSError, ValueError, IndexError):
        return peak_rss_mb()


def peak_rss_mb() -> float:
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes, macOS bytes.
    return peak / 1024 / 1024 if sys.platform == "darwin" else peak / 1024


class Watchdog(threading.Thread):
    """Stops the run (exit code 3) when it runs too long or uses too much memory."""

    def __init__(self, time_limit: float, memory_limit_mb: float):
        super().__init__(daemon=True)
        self.started = time.time()
        self.time_limit = time_limit
        self.memory_limit_mb = memory_limit_mb
        self.max_rss_seen = 0.0
        self._halt = threading.Event()

    def run(self):
        while not self._halt.wait(0.25):
            rss = rss_mb()
            self.max_rss_seen = max(self.max_rss_seen, rss)
            if rss > self.memory_limit_mb:
                self._abort(
                    f"memory {rss:.0f} MB is over the {self.memory_limit_mb:.0f} MB limit"
                )
            if time.time() - self.started > self.time_limit:
                self._abort(f"time is over the {self.time_limit:.0f} s limit")

    def stop(self):
        self._halt.set()

    @staticmethod
    def _abort(reason: str):
        sys.stderr.write(f"\nbenchmark_scan: stopped, {reason}\n")
        sys.stderr.flush()
        os._exit(3)


# ----------------------------------------------------------- estate builder
def build_estate(counts: dict, region: str) -> dict:
    """Create the synthetic estate. Call inside ``mock_aws()``."""
    import io
    import zipfile

    import boto3

    ec2 = boto3.client("ec2", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    sqs = boto3.client("sqs", region_name=region)
    sns = boto3.client("sns", region_name=region)
    ddb = boto3.client("dynamodb", region_name=region)

    vpc_ids = []
    for i in range(counts["vpcs"]):
        vpc_ids.append(
            ec2.create_vpc(
                CidrBlock=f"10.{i}.0.0/16",
                TagSpecifications=[
                    {
                        "ResourceType": "vpc",
                        "Tags": TAGS + [{"Key": "Name", "Value": f"bench-vpc-{i}"}],
                    }
                ],
            )["Vpc"]["VpcId"]
        )
    subnet_id = None
    if vpc_ids:
        subnet_id = ec2.create_subnet(VpcId=vpc_ids[0], CidrBlock="10.0.0.0/17")[
            "Subnet"
        ]["SubnetId"]
    for i in range(counts["security_groups"]):
        group = {"GroupName": f"bench-sg-{i}", "Description": "benchmark"}
        if vpc_ids:
            group["VpcId"] = vpc_ids[i % len(vpc_ids)]
        ec2.create_security_group(**group)
    for i in range(counts["buckets"]):
        name = f"bench-bucket-{i:05d}"
        s3.create_bucket(Bucket=name)
        s3.put_bucket_tagging(Bucket=name, Tagging={"TagSet": TAGS})
    for i in range(counts["queues"]):
        sqs.create_queue(
            QueueName=f"bench-queue-{i:05d}", tags={t["Key"]: t["Value"] for t in TAGS}
        )
    for i in range(counts["topics"]):
        sns.create_topic(Name=f"bench-topic-{i:05d}", Tags=TAGS)
    for i in range(counts["tables"]):
        ddb.create_table(
            TableName=f"bench-table-{i:05d}",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=TAGS,
        )
    remaining = counts["instances"]
    while remaining > 0:
        batch = min(remaining, 50)
        kwargs = dict(
            ImageId="ami-12345678",
            MinCount=batch,
            MaxCount=batch,
            TagSpecifications=[{"ResourceType": "instance", "Tags": TAGS}],
        )
        if subnet_id:
            kwargs["SubnetId"] = subnet_id
        ec2.run_instances(**kwargs)
        remaining -= batch
    if counts["functions"]:
        role_arn = boto3.client("iam", region_name=region).create_role(
            RoleName="bench-lambda-role", AssumeRolePolicyDocument="{}"
        )["Role"]["Arn"]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("app.py", "def handler(event, context):\n    return 1\n")
        code = buffer.getvalue()
        lam = boto3.client("lambda", region_name=region)
        for i in range(counts["functions"]):
            lam.create_function(
                FunctionName=f"bench-fn-{i:05d}",
                Runtime="python3.12",
                Role=role_arn,
                Handler="app.handler",
                Code={"ZipFile": code},
                Tags={t["Key"]: t["Value"] for t in TAGS},
            )
    return {"vpc_ids": vpc_ids}


# --------------------------------------------------------------------- scan
def run_scan(region: str, output_dir: Path, audit_path: Path) -> int:
    from inventag.cli.main import main

    old_argv = sys.argv
    sys.argv = [
        "inventag",
        "--create-excel",
        "--account-regions",
        region,
        "--no-billing-validation",
        "--output-directory",
        str(output_dir),
        "--audit-output",
        str(audit_path),
        "--disable-account-logging",
    ]
    code = 0
    try:
        try:
            main()
        except SystemExit as exc:
            code = 0 if exc.code is None else int(exc.code)
    finally:
        sys.argv = old_argv
    return code


# estate key -> (report service, report type). Security groups and VPCs also
# exist as moto defaults, so the report may hold more than were created.
EXPECTED_ROWS = {
    "buckets": ("S3", "Bucket"),
    "queues": ("SQS", "Queue"),
    "topics": ("SNS", "Topic"),
    "tables": ("DYNAMODB", "Table"),
    "vpcs": ("VPC", "VPC"),
    "security_groups": ("VPC", "SecurityGroup"),
    "instances": ("EC2", "Instance"),
    "functions": ("LAMBDA", "Function"),
}


def count_report_rows(xlsx: Path) -> dict:
    """Rows per (service, type) over all service sheets of the workbook."""
    from openpyxl import load_workbook

    found: dict = {}
    wb = load_workbook(str(xlsx), read_only=True)
    try:
        for name in wb.sheetnames:
            if not name.isupper():
                continue
            rows = wb[name].iter_rows(values_only=True)
            header = list(next(rows, []))
            if "service" not in header or "type" not in header:
                continue
            si, ti = header.index("service"), header.index("type")
            for row in rows:
                key = (row[si], row[ti])
                found[key] = found.get(key, 0) + 1
    finally:
        wb.close()
    return found


def compare_with_estate(counts: dict, found: dict) -> dict:
    """Created versus found, so a fast scan that missed resources is visible."""
    out = {}
    for key, expected in counts.items():
        got = found.get(EXPECTED_ROWS[key], 0)
        out[key] = {"created": expected, "in_report": got, "complete": got >= expected}
    return out


def summarize_calls(audit: dict) -> dict:
    by_service: dict = {}
    for op in audit.get("operations", []):
        by_service[op["service"]] = by_service.get(op["service"], 0) + op["count"]
    top = sorted(audit.get("operations", []), key=lambda o: -o["count"])[:8]
    return {
        "total": audit.get("total_calls", 0),
        "blocked": audit.get("blocked_calls", 0),
        "distinct_operations": len(audit.get("operations", [])),
        "by_service": dict(sorted(by_service.items(), key=lambda kv: -kv[1])),
        "top_operations": [
            {"call": f"{o['service']}:{o['operation']}", "count": o["count"]}
            for o in top
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Time an InvenTag scan of a synthetic moto estate. "
        "Read the header of this file first."
    )
    for name, default in DEFAULT_COUNTS.items():
        parser.add_argument(
            f"--{name.replace('_', '-')}",
            type=int,
            default=None,
            metavar="N",
            help=f"default {default} (times --scale)",
        )
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--time-limit", type=float, default=170.0)
    parser.add_argument("--memory-limit", type=float, default=1400.0)
    parser.add_argument("--json", metavar="FILE", help="also write the result as JSON")
    return parser


def resolve_counts(args) -> dict:
    counts = {}
    for name, default in DEFAULT_COUNTS.items():
        given = getattr(args, name)
        counts[name] = (
            given if given is not None else max(0, round(default * args.scale))
        )
    return counts


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    counts = resolve_counts(args)
    watchdog = Watchdog(args.time_limit, args.memory_limit)
    watchdog.start()

    from moto import mock_aws

    result: dict = {"counts": counts, "region": args.region}
    started = time.time()
    with mock_aws(), tempfile.TemporaryDirectory(prefix="inventag-bench-") as tmp:
        out_dir = Path(tmp) / "out"
        audit_path = Path(tmp) / "audit.json"

        t0 = time.time()
        build_estate(counts, args.region)
        result["estate_build_seconds"] = round(time.time() - t0, 2)
        result["memory_mb_before_scan"] = round(rss_mb(), 1)

        t0 = time.time()
        code = run_scan(args.region, out_dir, audit_path)
        result["scan_seconds"] = round(time.time() - t0, 2)
        result["scan_exit_code"] = code
        result["peak_memory_mb"] = round(max(peak_rss_mb(), watchdog.max_rss_seen), 1)

        audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
        result["api_calls"] = summarize_calls(audit)
        reports = sorted(out_dir.glob("*.xlsx"))
        if reports:
            found = count_report_rows(reports[0])
            result["resources_in_report"] = sum(found.values())
            result["report_size_kb"] = round(reports[0].stat().st_size / 1024, 1)
            result["completeness"] = compare_with_estate(counts, found)
        result["total_seconds"] = round(time.time() - started, 2)
    watchdog.stop()

    print_result(result)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    complete = all(c["complete"] for c in result.get("completeness", {}).values())
    return 0 if result["scan_exit_code"] == 0 and complete else 1


def print_result(result: dict) -> None:
    calls = result["api_calls"]
    print("\n=== InvenTag scan benchmark (moto, in process) ===")
    print("Estate: " + ", ".join(f"{k}={v}" for k, v in result["counts"].items()))
    print(f"Resources in the report : {result.get('resources_in_report', 'n/a')}")
    print(
        f"Scan time               : {result['scan_seconds']} s (estate build {result['estate_build_seconds']} s)"
    )
    print(
        f"AWS API calls           : {calls['total']} ({calls['blocked']} blocked, {calls['distinct_operations']} distinct operations)"
    )
    print(
        "  by service            : "
        + ", ".join(f"{s}={n}" for s, n in list(calls["by_service"].items())[:10])
    )
    print(
        "  most frequent         : "
        + ", ".join(f"{o['call']}={o['count']}" for o in calls["top_operations"][:5])
    )
    print(
        f"Memory                  : {result['memory_mb_before_scan']} MB before the scan, peak {result['peak_memory_mb']} MB"
    )
    missing = {
        k: c for k, c in result.get("completeness", {}).items() if not c["complete"]
    }
    print(
        "Completeness            : "
        + (
            "every created resource is in the report"
            if not missing
            else "MISSING "
            + ", ".join(
                f"{k} {c['in_report']}/{c['created']}" for k, c in missing.items()
            )
        )
    )
    print(f"Report size             : {result.get('report_size_kb', 'n/a')} KB")
    print(f"Scan exit code          : {result['scan_exit_code']}")
    print("Time excludes network latency: moto answers inside this process.")


if __name__ == "__main__":
    sys.exit(main())
