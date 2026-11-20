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

Latency, regions, accounts, concurrency (plan v14, section 2.9)
        --latency-ms 50          wait 50 ms before every AWS request (outside moto's lock,
                                 see tests/latency.py), so parallel code can show a gain
        --regions us-east-1,eu-west-1   the first region holds the whole estate, the others
                                 everything but buckets and functions (S3 is global)
        --accounts 4             account 1 is the default credentials, the others are
                                 assumed roles with an estate each (--accounts-file)
        --concurrency N          passed to the scan only when given (v1.4.0 and later)
        --inventag-root DIR      scan the inventag package in DIR (for example a checkout of
                                 tag v1.3.0) with this harness
        --case B1..B8            the estate and delay of a case of plan section 2.9
    The JSON result then also holds ``requests`` (attempts, peak in flight), ``stages``
    (credentials, listings, tagging, details, analyses, reports) and ``ledger``.

    The comparison is a ratio of two runs made in the same job, never seconds:
        python scripts/benchmark_scan.py --case B2 --json base.json --inventag-root /tmp/v130
        python scripts/benchmark_scan.py --case B2 --json cand.json
        python scripts/benchmark_scan.py --check-case B2 --baseline base.json --candidate cand.json
    Not verified against real AWS: any speed-up. The numbers come from a simulated
    AWS with a fixed delay per request.

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


def prepare_environment() -> None:
    """Fake credentials and no metadata service, before boto3 is imported."""
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
def build_estate(counts: dict, region: str, creds: dict = None, tag: str = "") -> dict:
    """Create the synthetic estate. Call inside ``mock_aws()``.

    ``creds`` are boto3 client keywords of another account (assumed role);
    ``tag`` goes into the names of S3 buckets, which are global in moto.
    """
    import io
    import zipfile

    import boto3

    ec2 = boto3.client("ec2", region_name=region, **(creds or {}))
    s3 = boto3.client("s3", region_name=region, **(creds or {}))
    sqs = boto3.client("sqs", region_name=region, **(creds or {}))
    sns = boto3.client("sns", region_name=region, **(creds or {}))
    ddb = boto3.client("dynamodb", region_name=region, **(creds or {}))

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
        name = f"bench-{tag}bucket-{i:05d}"
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
        role_arn = boto3.client("iam", region_name=region, **(creds or {})).create_role(
            RoleName="bench-lambda-role", AssumeRolePolicyDocument="{}"
        )["Role"]["Arn"]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("app.py", "def handler(event, context):\n    return 1\n")
        code = buffer.getvalue()
        lam = boto3.client("lambda", region_name=region, **(creds or {}))
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
DEFAULT_REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
ACCOUNT_ID = "123456789012"  # moto's default account: account 1


def other_account_id(index: int) -> str:
    """Account ``index`` (2, 3, ...) of the run: 222222222222, 333333333333, ..."""
    return str(index) * 12


def role_arn(account_id: str) -> str:
    return f"arn:aws:iam::{account_id}:role/InvenTagRole"


def scan_argv(
    output_dir, audit_path, regions, accounts_file, concurrency, analyses=False
) -> list:
    """The command line of one scan. ``--concurrency`` only when asked for, so the
    same script also runs against v1.3.0, which does not know the flag."""
    argv = [
        "inventag",
        "--create-excel",
        "--no-billing-validation",
        "--output-directory",
        str(output_dir),
        "--audit-output",
        str(audit_path),
        "--disable-account-logging",
    ]
    if accounts_file is not None:
        argv += ["--accounts-file", str(accounts_file)]
    else:
        argv += ["--account-regions", ",".join(regions)]
    if analyses:
        argv += ["--enable-network-analysis", "--enable-security-analysis"]
    if concurrency is not None:
        argv += ["--concurrency", str(concurrency)]
    return argv


def run_scan(argv: list) -> int:
    from inventag.cli.main import main

    old_argv = sys.argv
    sys.argv = argv
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
# S3 buckets and Lambda functions exist only in the first region of the estate.
FIRST_REGION_ONLY = ("buckets", "functions")


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


def expected_counts(counts: dict, regions: int, accounts: int) -> dict:
    """Resources created in the whole estate, per estate key."""
    return {
        key: n * accounts * (1 if key in FIRST_REGION_ONLY else regions)
        for key, n in counts.items()
    }


def compare_with_estate(created: dict, found: dict) -> dict:
    """Created versus found, so a fast scan that missed resources is visible."""
    out = {}
    for key, expected in created.items():
        got = found.get(EXPECTED_ROWS[key], 0)
        out[key] = {"created": expected, "in_report": got, "complete": got >= expected}
    return out


def summarize_calls(audit: dict) -> dict:
    by_service: dict = {}
    by_operation: dict = {}
    for op in audit.get("operations", []):
        by_service[op["service"]] = by_service.get(op["service"], 0) + op["count"]
        name = f"{op['service']}:{op['operation']}"
        by_operation[name] = by_operation.get(name, 0) + op["count"]
    top = sorted(audit.get("operations", []), key=lambda o: -o["count"])[:8]
    return {
        "total": audit.get("total_calls", 0),
        "blocked": audit.get("blocked_calls", 0),
        "distinct_operations": len(audit.get("operations", [])),
        "by_service": dict(sorted(by_service.items(), key=lambda kv: -kv[1])),
        "by_operation": dict(sorted(by_operation.items())),
        "top_operations": [
            {"call": f"{o['service']}:{o['operation']}", "count": o["count"]}
            for o in top
        ],
    }


# ------------------------------------------------------------------- stages
# Which stage a request belongs to, by service and operation (names as
# botocore's events give them, lower case without hyphens). The stage of
# "details" and "analyses" is the list below; credentials are every STS call and
# the region access test; tagging is the Tagging API; every other request is a
# listing. "reports" is the time after the last request until the scan ends.
# RDS and CloudFormation detail calls use the same operations as their listings
# (DescribeDBInstances, DescribeStacks), so the benchmark estate, which holds
# neither, cannot tell them apart; they would count as listings.
DETAIL_OPERATIONS = frozenset(
    {
        "s3:GetBucketLocation",
        "lambda:GetFunctionConfiguration",
        "eks:DescribeCluster",
    }
)
# The analyses call operations that the listings call too (ec2 Describe*), so
# these count as "analyses" only when they start after the last tagging or
# detail request: in v1.3.0 the analyses run while the reports are made, after
# the whole discovery. In a run of several accounts that overlap, a late
# listing of one account can be counted as an analysis call: a heuristic, and
# the same one for the baseline and the candidate.
ANALYSIS_OPERATIONS = frozenset(
    {
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeRouteTables",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeNatGateways",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeNetworkAcls",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeTransitGatewayAttachments",
        "ec2:DescribeVpcEndpoints",
        "ec2:DescribeVpcPeeringConnections",
        "elasticache:DescribeCacheSubnetGroups",
    }
)
CREDENTIAL_OPERATIONS = frozenset({"ec2:DescribeRegions"})
STAGE_ORDER = ("credentials", "listings", "tagging", "details", "analyses")


def _key(service: str, operation: str) -> str:
    return f"{service.replace('-', '').lower()}:{operation}"


def stage_of(service: str, operation: str) -> str:
    """Stage of a request, except that analyses are told apart by time (below)."""
    key = _key(service, operation)
    if key in DETAIL_OPERATIONS:
        return "details"
    if service == "sts" or key in CREDENTIAL_OPERATIONS:
        return "credentials"
    if service.replace("-", "") == "resourcegroupstaggingapi":
        return "tagging"
    return "listings"


def stage_report(records, scan_started: float, scan_ended: float) -> dict:
    """Calls and time span (seconds since the scan began) of every stage."""
    stages = {name: {"calls": 0, "first": None, "last": None} for name in STAGE_ORDER}
    last_end = scan_started
    names = {id(r): stage_of(r.service, r.operation) for r in records}
    discovery_end = max(
        (r.ended for r in records if names[id(r)] in ("tagging", "details")),
        default=None,
    )
    for r in records:
        if (
            discovery_end is not None
            and _key(r.service, r.operation) in ANALYSIS_OPERATIONS
            and r.started >= discovery_end
        ):
            names[id(r)] = "analyses"
    for r in records:
        st = stages[names[id(r)]]
        st["calls"] += 1
        st["first"] = r.started if st["first"] is None else min(st["first"], r.started)
        st["last"] = r.ended if st["last"] is None else max(st["last"], r.ended)
        last_end = max(last_end, r.ended)
    out = {}
    for name, st in stages.items():
        if st["calls"]:
            out[name] = {
                "calls": st["calls"],
                "from_seconds": round(st["first"] - scan_started, 2),
                "to_seconds": round(st["last"] - scan_started, 2),
                "seconds": round(st["last"] - st["first"], 2),
            }
        else:
            out[name] = {"calls": 0, "from_seconds": 0, "to_seconds": 0, "seconds": 0}
    out["reports"] = {"calls": 0, "seconds": round(max(0.0, scan_ended - last_end), 2)}
    return out


class LedgerTap:
    """Collects what the coverage ledger records (source, outcome, seconds)."""

    def __init__(self):
        self.entries = []
        self._lock = threading.Lock()
        self._original = None

    def __enter__(self):
        from inventag.discovery.coverage import CoverageLedger

        tap, original = self, CoverageLedger.record
        self._original = original

        def record(ledger, **fields):
            entry = original(ledger, **fields)
            with tap._lock:
                tap.entries.append(entry)
            return entry

        CoverageLedger.record = record
        return self

    def __exit__(self, *exc):
        from inventag.discovery.coverage import CoverageLedger

        CoverageLedger.record = self._original

    def summary(self) -> dict:
        by_source: dict = {}
        for e in self.entries:
            row = by_source.setdefault(e.source, {"entries": 0, "seconds": 0.0})
            row["entries"] += 1
            row["seconds"] = round(row["seconds"] + (e.seconds or 0.0), 2)
        outcomes: dict = {}
        for e in self.entries:
            outcomes[e.outcome] = outcomes.get(e.outcome, 0) + 1
        return {
            "entries": len(self.entries),
            "by_source": dict(sorted(by_source.items())),
            "outcomes": dict(sorted(outcomes.items())),
        }


# ------------------------------------------------------------------- cases
# Plan section 2.9. ``accept`` holds the limits; see evaluate_case.
CASES = {
    "B1": dict(
        accounts=1,
        regions=1,
        scale=1,
        latency_ms=50,
        concurrency=None,
        accept={"wall_ratio": 0.85},
    ),
    "B2": dict(
        accounts=1,
        regions=1,
        scale=5,
        latency_ms=50,
        concurrency=None,
        accept={"wall_ratio": 0.60},
    ),
    "B3": dict(
        accounts=1,
        regions=3,
        scale=3,
        latency_ms=200,
        concurrency=None,
        accept={"wall_ratio": 0.55},
    ),
    "B4": dict(
        accounts=4,
        regions=3,
        scale=1,
        latency_ms=50,
        concurrency=None,
        accept={"wall_ratio": 1.00, "peak_max": 64},
    ),
    "B5": dict(
        accounts=1,
        regions=1,
        scale=1,
        latency_ms=50,
        concurrency=1,
        accept={"peak_exact": 1, "wall_at_least_requests_x_delay": True},
    ),
    "B6": dict(
        accounts=4,
        regions=3,
        scale=1,
        latency_ms=50,
        concurrency=8,
        accept={"peak_max": 8},
    ),
    "B7": dict(
        accounts=1,
        regions=1,
        scale=1,
        latency_ms=0,
        concurrency=None,
        accept={"wall_ratio": 1.10},
    ),
    "B8": dict(
        accounts=1,
        regions=1,
        scale=5,
        latency_ms=50,
        concurrency=None,
        accept={"memory_ratio": 1.15, "memory_limit": True},
    ),
}
MEMORY_LIMIT_MB = 1400.0


def evaluate_case(case: str, baseline, candidate) -> list:
    """[(check, ok, detail)] for one case. ``baseline`` is the result of the same
    case on the v1.3.0 checkout, measured in the same job (None when the case
    needs none: B5, B6)."""
    accept = CASES[case]["accept"]
    checks = []
    if "wall_ratio" in accept:
        ratio = candidate["scan_seconds"] / baseline["scan_seconds"]
        limit = accept["wall_ratio"]
        checks.append(
            ("wall ratio", ratio <= limit, f"{ratio:.2f} (limit {limit:.2f})")
        )
    peak = candidate["requests"]["peak_in_flight"]
    if "peak_max" in accept:
        checks.append(
            (
                "peak in flight",
                peak <= accept["peak_max"],
                f"{peak} (limit {accept['peak_max']})",
            )
        )
    if "peak_exact" in accept:
        checks.append(
            (
                "peak in flight",
                peak == accept["peak_exact"],
                f"{peak} (must be {accept['peak_exact']})",
            )
        )
    if accept.get("wall_at_least_requests_x_delay"):
        floor = candidate["requests"]["total"] * candidate["latency_ms"] / 1000.0
        checks.append(
            (
                "wall at least requests x delay",
                candidate["scan_seconds"] >= floor,
                f"{candidate['scan_seconds']:.2f} s (floor {floor:.2f} s)",
            )
        )
    if "memory_ratio" in accept:
        ratio = candidate["peak_memory_mb"] / baseline["peak_memory_mb"]
        limit = accept["memory_ratio"]
        checks.append(
            ("memory ratio", ratio <= limit, f"{ratio:.2f} (limit {limit:.2f})")
        )
    if accept.get("memory_limit"):
        mem = candidate["peak_memory_mb"]
        checks.append(
            (
                "memory under the limit",
                mem <= MEMORY_LIMIT_MB,
                f"{mem:.0f} MB (limit {MEMORY_LIMIT_MB:.0f} MB)",
            )
        )
    if baseline is not None:
        a = baseline["api_calls"]["by_operation"]
        b = candidate["api_calls"]["by_operation"]
        differing = sorted(k for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0))
        checks.append(
            (
                "same calls by operation",
                not differing,
                (
                    "equal"
                    if not differing
                    else "differs: "
                    + ", ".join(
                        f"{k} {a.get(k, 0)} -> {b.get(k, 0)}" for k in differing[:8]
                    )
                ),
            )
        )
    return checks


def check_main(args) -> int:
    if args.check_case not in CASES:
        sys.stderr.write(f"benchmark_scan: unknown case {args.check_case}\n")
        return 2
    needs_baseline = (
        "wall_ratio" in CASES[args.check_case]["accept"]
        or "memory_ratio" in CASES[args.check_case]["accept"]
    )
    if needs_baseline and not args.baseline:
        sys.stderr.write("benchmark_scan: this case needs --baseline\n")
        return 2
    baseline = json.loads(Path(args.baseline).read_text()) if args.baseline else None
    candidate = json.loads(Path(args.candidate).read_text())
    ok_all = True
    print(f"=== {args.check_case}: acceptance of plan section 2.9 ===")
    for name, ok, detail in evaluate_case(args.check_case, baseline, candidate):
        ok_all = ok_all and ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    print(
        "Not verified against real AWS: any speed-up. The numbers come from a simulated AWS with a fixed delay per request."
    )
    return 0 if ok_all else 1


# ----------------------------------------------------------------- the run
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
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument(
        "--region", default="us-east-1", help="the region when --regions is not given"
    )
    parser.add_argument(
        "--regions",
        default=None,
        help="comma separated; or a number: that many of " + ", ".join(DEFAULT_REGIONS),
    )
    parser.add_argument(
        "--accounts",
        type=int,
        default=None,
        help="accounts in the run (default 1; at most 9)",
    )
    parser.add_argument(
        "--latency-ms",
        type=float,
        default=None,
        help="wait before every AWS request (default 0)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="passed to the scan as --concurrency (v1.4.0 and later)",
    )
    parser.add_argument(
        "--inventag-root",
        default=None,
        help="folder that holds the inventag package to scan (default: this repository)",
    )
    parser.add_argument(
        "--case",
        choices=sorted(CASES),
        default=None,
        help="estate, delay and concurrency of a case of plan section 2.9",
    )
    parser.add_argument(
        "--check-case",
        default=None,
        metavar="CASE",
        help="compare two --json results against the acceptance of CASE (no scan)",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        metavar="FILE",
        help="with --check-case: the result of v1.3.0",
    )
    parser.add_argument(
        "--candidate",
        default=None,
        metavar="FILE",
        help="with --check-case: the result of the candidate",
    )
    parser.add_argument(
        "--analyses",
        action="store_true",
        help="also run the network and security analyses",
    )
    parser.add_argument("--time-limit", type=float, default=170.0)
    parser.add_argument("--memory-limit", type=float, default=MEMORY_LIMIT_MB)
    parser.add_argument("--json", metavar="FILE", help="also write the result as JSON")
    return parser


def resolve_settings(args) -> dict:
    """Explicit options win over the case; the case wins over the defaults."""
    case = CASES[args.case] if args.case else {}

    def pick(value, key, default):
        return value if value is not None else case.get(key, default)

    regions = pick(args.regions, "regions", None)
    if regions is None:
        region_list = [args.region]
    elif isinstance(regions, int) or str(regions).isdigit():
        region_list = DEFAULT_REGIONS[: int(regions)]
    else:
        region_list = [r for r in str(regions).split(",") if r]
    return {
        "scale": pick(args.scale, "scale", 1.0),
        "regions": region_list,
        "accounts": pick(args.accounts, "accounts", 1),
        "latency_ms": pick(args.latency_ms, "latency_ms", 0),
        "concurrency": pick(args.concurrency, "concurrency", None),
    }


def resolve_counts(args, scale: float) -> dict:
    counts = {}
    for name, default in DEFAULT_COUNTS.items():
        given = getattr(args, name)
        counts[name] = given if given is not None else max(0, round(default * scale))
    return counts


def seed_accounts(counts: dict, regions: list, accounts: int) -> Path:
    """Build the estate of every account. Returns nothing; account 1 is moto's default."""
    import boto3

    for index in range(1, accounts + 1):
        creds, tag = None, ""
        if index > 1:
            assumed = boto3.client("sts", region_name=regions[0]).assume_role(
                RoleArn=role_arn(other_account_id(index)), RoleSessionName="seed"
            )["Credentials"]
            creds = dict(
                aws_access_key_id=assumed["AccessKeyId"],
                aws_secret_access_key=assumed["SecretAccessKey"],
                aws_session_token=assumed["SessionToken"],
            )
            tag = f"a{index}-"
        for position, region in enumerate(regions):
            here = dict(counts)
            if position:
                for key in FIRST_REGION_ONLY:
                    here[key] = 0
            build_estate(here, region, creds=creds, tag=tag)


def write_accounts_file(path: Path, regions: list, accounts: int) -> Path:
    entries = [{"account_id": ACCOUNT_ID, "regions": regions}]
    for index in range(2, accounts + 1):
        account_id = other_account_id(index)
        entries.append(
            {
                "account_id": account_id,
                "role_arn": role_arn(account_id),
                "regions": regions,
            }
        )
    path.write_text(json.dumps({"accounts": entries}))
    return path


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.check_case:
        return check_main(args)
    settings = resolve_settings(args)
    if not 1 <= settings["accounts"] <= 9:
        sys.stderr.write("benchmark_scan: --accounts must be from 1 to 9\n")
        return 2
    counts = resolve_counts(args, settings["scale"])
    regions, accounts = settings["regions"], settings["accounts"]

    prepare_environment()
    root = Path(args.inventag_root).resolve() if args.inventag_root else REPO_ROOT
    # The harness (tests.latency) always comes from this repository. A baseline
    # checkout has its own tests/ package without it, so load the harness first
    # (it stays in sys.modules), then put the root of the scanned inventag first.
    sys.path.insert(0, str(REPO_ROOT))
    from tests.latency import inject_latency

    sys.path.insert(0, str(root))

    watchdog = Watchdog(args.time_limit, args.memory_limit)
    watchdog.start()

    from moto import mock_aws

    import inventag

    result: dict = {
        "counts": counts,
        "region": regions[0],
        "regions": regions,
        "accounts": accounts,
        "latency_ms": settings["latency_ms"],
        "concurrency": settings["concurrency"],
        "case": args.case,
        "inventag_root": str(Path(inventag.__file__).resolve().parent.parent),
        "inventag_version": getattr(
            sys.modules.get("inventag._version"), "__version__", None
        )
        or _version_of(inventag),
    }
    started = time.time()
    with mock_aws(), tempfile.TemporaryDirectory(prefix="inventag-bench-") as tmp:
        out_dir = Path(tmp) / "out"
        audit_path = Path(tmp) / "audit.json"
        accounts_file = (
            write_accounts_file(Path(tmp) / "accounts.json", regions, accounts)
            if accounts > 1
            else None
        )

        t0 = time.time()
        seed_accounts(counts, regions, accounts)
        result["estate_build_seconds"] = round(time.time() - t0, 2)
        result["memory_mb_before_scan"] = round(rss_mb(), 1)

        argv_scan = scan_argv(
            out_dir,
            audit_path,
            regions,
            accounts_file,
            settings["concurrency"],
            args.analyses,
        )
        with inject_latency(settings["latency_ms"]) as harness, LedgerTap() as ledger:
            t_scan = time.monotonic()
            t0 = time.time()
            code = run_scan(argv_scan)
            result["scan_seconds"] = round(time.time() - t0, 2)
            t_end = time.monotonic()
        result["wall_seconds"] = result["scan_seconds"]
        result["scan_exit_code"] = code
        result["peak_memory_mb"] = round(max(peak_rss_mb(), watchdog.max_rss_seen), 1)
        result["requests"] = {
            "total": harness.total_requests,
            "peak_in_flight": harness.peak_in_flight,
            "retried_or_injected": sum(
                1 for r in harness.requests if r.attempt > 1 or r.injected
            ),
        }
        result["stages"] = stage_report(harness.requests, t_scan, t_end)
        result["ledger"] = ledger.summary()

        audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
        result["api_calls"] = summarize_calls(audit)
        reports = sorted(out_dir.glob("*.xlsx"))
        if reports:
            found = count_report_rows(reports[0])
            result["resources_in_report"] = sum(found.values())
            result["report_size_kb"] = round(reports[0].stat().st_size / 1024, 1)
            result["reports_written"] = len(reports)
            result["completeness"] = compare_with_estate(
                expected_counts(counts, len(regions), accounts), found
            )
        result["total_seconds"] = round(time.time() - started, 2)
    watchdog.stop()

    print_result(result)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    complete = all(c["complete"] for c in result.get("completeness", {}).values())
    return 0 if result["scan_exit_code"] == 0 and complete else 1


def _version_of(package) -> str:
    try:
        from inventag._version import __version__

        return __version__
    except ImportError:
        return getattr(package, "__version__", "unknown")


def print_result(result: dict) -> None:
    calls = result["api_calls"]
    print("\n=== InvenTag scan benchmark (moto, in process) ===")
    print("Estate: " + ", ".join(f"{k}={v}" for k, v in result["counts"].items()))
    print(
        f"Run: {result['accounts']} account(s), regions {','.join(result['regions'])}, "
        f"{result['latency_ms']} ms per request, concurrency {result['concurrency']}, "
        f"inventag {result['inventag_version']}"
    )
    print(f"Resources in the report : {result.get('resources_in_report', 'n/a')}")
    print(
        f"Scan time               : {result['scan_seconds']} s (estate build {result['estate_build_seconds']} s)"
    )
    print(
        f"AWS API calls           : {calls['total']} ({calls['blocked']} blocked, {calls['distinct_operations']} distinct operations)"
    )
    print(
        f"Requests sent           : {result['requests']['total']}, peak in flight {result['requests']['peak_in_flight']}"
    )
    print(
        "Stages (calls, seconds) : "
        + ", ".join(
            f"{k} {v['calls']}, {v['seconds']}" for k, v in result["stages"].items()
        )
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
    print(
        "Time excludes network latency unless --latency-ms is given: moto answers inside this process."
    )
    print("Not verified against real AWS: any speed-up.")


if __name__ == "__main__":
    sys.exit(main())
