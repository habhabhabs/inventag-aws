#!/usr/bin/env python3
"""Live smoke test for InvenTag, for the owner to run against a real AWS account.

Why this exists
    Every InvenTag test runs against mocked AWS (moto). This script is the
    first check against the real thing. It scans ONE region, then compares the
    report with what plain boto3 list calls return, and prints a PASS/FAIL
    table.

Safe by construction
    * Only List/Describe/Get calls are made, by InvenTag and by this script.
    * The same read-only guard that InvenTag uses (inventag.security.
      read_only_guard) is installed in this process before any client exists.
      This script also wraps its own clients so that only list_*, describe_*
      and get_* methods can be called on them.
    * ``--no-billing-validation`` is on by default, so no Cost Explorer call is
      made and the run costs nothing. Add ``--billing-validation`` to include
      it (AWS charges per Cost Explorer request).
    * Credentials, account IDs and full ARNs are never printed. Account IDs
      show as ****1234 and ARNs and resource IDs as ...abcd, unless you pass
      ``--show-ids``. The scan's own log is not printed unless a check fails,
      and then only with account IDs, ARNs and access keys masked.
    * The scan runs as a child process: ``python -m inventag ...``.

Run it
    Use a read-only profile (for example the AWS managed policy ReadOnlyAccess
    or the policy in docs/reference/iam-permissions.md), then:

        python scripts/live_smoke_test.py --profile my-readonly --region eu-west-1

    Options:
        --profile NAME         AWS profile to use (default: the usual AWS
                               credential chain)
        --region REGION        the one region to scan (default: AWS_REGION,
                               AWS_DEFAULT_REGION, or us-east-1)
        --output-directory D   keep the report there (default: a temporary
                               directory that is removed afterwards)
        --billing-validation   also use Cost Explorer (costs money)
        --create-word          also write and open a Word report
        --sample-size N        resources whose tags are compared per service
                               (default 3)
        --show-ids             print full IDs and ARNs
        --in-process           run the scan inside this process instead of a
                               child process (used by the script's own tests)

What it checks (each line of the table)
    scan exit code            InvenTag finished with exit code 0
    report opens              the .xlsx (and .docx, if asked) opens
    state snapshot            the JSON file in <output>/state parses
    count <service/type>      resources in the report equal the number a direct
                              boto3 list call returns (S3 buckets, EC2
                              instances, VPCs, security groups, Lambda
                              functions, DynamoDB tables, SQS queues, SNS
                              topics)
    tags <service/type>       tags of up to N resources in the report equal the
                              tags that a direct call returns (aws:* tags
                              are ignored)
    no write calls            the guard's blocked-call counter is 0 and every
                              recorded operation is a read operation

    A count check is SKIP when both sides are zero, so an account without
    Lambda functions does not pass for free: the table says SKIP, not PASS.

Exit code
    0  every check passed (SKIP does not count as a failure)
    1  at least one check failed
    2  the script could not start (no credentials, unreadable profile, no
       region)

Direct calls made by this script (all read-only)
    sts:GetCallerIdentity, s3:ListBuckets, s3:GetBucketTagging,
    ec2:DescribeInstances, ec2:DescribeVpcs, ec2:DescribeSecurityGroups,
    lambda:ListFunctions, lambda:ListTags, dynamodb:ListTables,
    dynamodb:ListTagsOfResource, sqs:ListQueues, sqs:ListQueueTags,
    sns:ListTopics, sns:ListTagsForResource.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

READ_METHOD_PREFIXES = ("list_", "describe_", "get_", "head_")
READ_OPERATION_PREFIXES = (
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet",
)
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

_ACCOUNT_ID = re.compile(r"(?<!\d)\d{12}(?!\d)")
_ARN = re.compile(r"arn:aws[a-z-]*:[A-Za-z0-9-]*:[a-z0-9-]*:\d*:[^\s\"',)]+")
_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")


# ------------------------------------------------------------------ masking
def mask_tail(value: str, show_ids: bool, keep: int = 4) -> str:
    """``...abcd`` instead of the whole identifier."""
    if show_ids or not value:
        return value
    return "..." + value[-keep:] if len(value) > keep else "..."


def mask_account(account_id: str, show_ids: bool) -> str:
    if show_ids or not account_id:
        return account_id
    return "****" + account_id[-4:]


def mask_arn(arn: str, show_ids: bool) -> str:
    if show_ids:
        return arn
    parts = arn.split(":", 5)
    if len(parts) < 6:
        return mask_tail(arn, show_ids)
    parts[4] = mask_account(parts[4], show_ids) if parts[4] else ""
    parts[5] = mask_tail(parts[5], show_ids)
    return ":".join(parts)


def scrub(text: str, show_ids: bool = False) -> str:
    """Remove account IDs, ARNs and access keys from free text."""
    if show_ids:
        return text
    text = _ACCESS_KEY.sub("AKIA****", text)
    text = _ARN.sub(lambda m: mask_arn(m.group(0), False), text)
    return _ACCOUNT_ID.sub(lambda m: "****" + m.group(0)[-4:], text)


# -------------------------------------------------------- read-only clients
class ReadOnlyClient:
    """Lets only list_*, describe_*, get_* and head_* methods through."""

    def __init__(self, client):
        object.__setattr__(self, "_client", client)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if not name.startswith(READ_METHOD_PREFIXES):
            raise PermissionError(
                f"live_smoke_test only calls read methods; refused {name}()"
            )
        return getattr(self._client, name)


def make_session(profile: Optional[str], region: str):
    import boto3

    return boto3.Session(profile_name=profile, region_name=region)


def read_client(session, service: str, region: str):
    return ReadOnlyClient(session.client(service, region_name=region))


# ------------------------------------------------------- direct list calls
def _paginate(client, method: str, key: str, **kwargs) -> list:
    items: list = []
    for page in client.get_paginator(method).paginate(**kwargs):
        items.extend(page.get(key, []))
    return items


@dataclass
class Direct:
    """What a direct boto3 call returns for one service/type."""

    ids: Dict[str, str] = field(default_factory=dict)  # report id -> tag lookup id
    tags: Callable[[str], Dict[str, str]] = lambda _id: {}


def _tag_dict(pairs) -> Dict[str, str]:
    return {t["Key"]: t["Value"] for t in pairs or []}


def direct_s3(session, region):
    s3 = read_client(session, "s3", region)
    names = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]

    def tags(name):
        from botocore.exceptions import ClientError

        try:
            return _tag_dict(s3.get_bucket_tagging(Bucket=name)["TagSet"])
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchTagSet":
                return {}
            raise

    return Direct({n: n for n in names}, tags)


def direct_ec2_instances(session, region):
    ec2 = read_client(session, "ec2", region)
    found = {}
    for res in _paginate(ec2, "describe_instances", "Reservations"):
        for inst in res.get("Instances", []):
            if inst.get("State", {}).get("Name") == "terminated":
                continue
            found[inst["InstanceId"]] = _tag_dict(inst.get("Tags"))
    return Direct({i: i for i in found}, lambda i: found[i])


def direct_vpcs(session, region):
    ec2 = read_client(session, "ec2", region)
    found = {v["VpcId"]: _tag_dict(v.get("Tags")) for v in ec2.describe_vpcs()["Vpcs"]}
    return Direct({i: i for i in found}, lambda i: found[i])


def direct_security_groups(session, region):
    ec2 = read_client(session, "ec2", region)
    groups = _paginate(ec2, "describe_security_groups", "SecurityGroups")
    found = {g["GroupId"]: _tag_dict(g.get("Tags")) for g in groups}
    return Direct({i: i for i in found}, lambda i: found[i])


def direct_lambda(session, region):
    lam = read_client(session, "lambda", region)
    functions = _paginate(lam, "list_functions", "Functions")
    arns = {f["FunctionName"]: f["FunctionArn"] for f in functions}

    def tags(name):
        return dict(lam.list_tags(Resource=arns[name]).get("Tags", {}))

    return Direct({n: n for n in arns}, tags)


def direct_dynamodb(session, region):
    ddb = read_client(session, "dynamodb", region)
    names = _paginate(ddb, "list_tables", "TableNames")
    arns: Dict[str, str] = {}

    def tags(name):
        if name not in arns:
            arns[name] = ddb.describe_table(TableName=name)["Table"]["TableArn"]
        pages = _paginate(ddb, "list_tags_of_resource", "Tags", ResourceArn=arns[name])
        return _tag_dict(pages)

    return Direct({n: n for n in names}, tags)


def direct_sqs(session, region):
    sqs = read_client(session, "sqs", region)
    urls: list = []
    for page in sqs.get_paginator("list_queues").paginate():
        urls.extend(page.get("QueueUrls", []))
    return Direct(
        {u.rsplit("/", 1)[-1]: u for u in urls},
        lambda url: dict(sqs.list_queue_tags(QueueUrl=url).get("Tags", {})),
    )


def direct_sns(session, region):
    sns = read_client(session, "sns", region)
    arns = [t["TopicArn"] for t in _paginate(sns, "list_topics", "Topics")]
    return Direct(
        {a.rsplit(":", 1)[-1]: a for a in arns},
        lambda arn: _tag_dict(
            sns.list_tags_for_resource(ResourceArn=arn).get("Tags", [])
        ),
    )


# (label, report service, report type, how to list directly, regional?)
CORE_CHECKS: List[Tuple[str, str, str, Callable]] = [
    ("S3 buckets", "S3", "Bucket", direct_s3),
    ("EC2 instances", "EC2", "Instance", direct_ec2_instances),
    ("VPCs", "VPC", "VPC", direct_vpcs),
    ("Security groups", "VPC", "SecurityGroup", direct_security_groups),
    ("Lambda functions", "LAMBDA", "Function", direct_lambda),
    ("DynamoDB tables", "DYNAMODB", "Table", direct_dynamodb),
    ("SQS queues", "SQS", "Queue", direct_sqs),
    ("SNS topics", "SNS", "Topic", direct_sns),
]


# ------------------------------------------------------------ report reading
def read_report_rows(xlsx: Path) -> List[Dict[str, object]]:
    """Every resource row of every service sheet of the workbook."""
    from openpyxl import load_workbook

    wb = load_workbook(str(xlsx), read_only=True)
    rows: List[Dict[str, object]] = []
    try:
        for name in wb.sheetnames:
            if not name.isupper():  # Summary, analysis sheets, ...
                continue
            data = list(wb[name].iter_rows(values_only=True))
            if not data:
                continue
            header = list(data[0])
            rows.extend(dict(zip(header, row)) for row in data[1:])
    finally:
        wb.close()
    return rows


def row_tags(row: Dict[str, object]) -> Dict[str, str]:
    return {
        key[len("tags.") :]: str(value)
        for key, value in row.items()
        if isinstance(key, str)
        and key.startswith("tags.")
        and value is not None
        and value != ""
    }


def without_aws_tags(tags: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in tags.items() if not k.startswith("aws:")}


def short_id(row: Dict[str, object]) -> str:
    """The identifier used to look a resource up directly.

    SQS reports the queue URL and SNS the topic ARN; both are shortened to the
    queue or topic name.
    """
    value = str(row.get("id") or row.get("resource_id") or "")
    if value.startswith("http"):
        return value.rsplit("/", 1)[-1]
    if value.startswith("arn:"):
        return value.rsplit(":", 1)[-1]
    return value


# -------------------------------------------------------------------- checks
@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def check_counts_and_tags(
    session, region, rows, sample_size, show_ids, checks: List[Check]
):
    for label, service, rtype, lister in CORE_CHECKS:
        in_report = [
            r for r in rows if r.get("service") == service and r.get("type") == rtype
        ]
        try:
            direct = lister(session, region)
        except Exception as exc:  # noqa: BLE001 - one service must not stop the rest
            checks.append(
                Check(
                    f"count {label}",
                    FAIL,
                    f"direct call failed: {type(exc).__name__}: "
                    f"{scrub(str(exc), show_ids)[:120]}",
                )
            )
            continue
        report_n, direct_n = len(in_report), len(direct.ids)
        detail = f"report {report_n}, direct {direct_n}"
        if report_n == direct_n == 0:
            checks.append(Check(f"count {label}", SKIP, "none in this account"))
            checks.append(Check(f"tags {label}", SKIP, "nothing to compare"))
            continue
        checks.append(
            Check(
                f"count {label}",
                PASS if report_n == direct_n else FAIL,
                detail,
            )
        )
        if report_n != direct_n:
            missing = sorted(set(direct.ids) - {short_id(r) for r in in_report})
            extra = sorted({short_id(r) for r in in_report} - set(direct.ids))
            if missing:
                shown = ", ".join(mask_tail(m, show_ids) for m in missing[:5])
                checks[-1].detail += f"; not in report: {shown}"
            if extra:
                shown = ", ".join(mask_tail(m, show_ids) for m in extra[:5])
                checks[-1].detail += f"; not found directly: {shown}"
        checks.append(check_tags(label, in_report, direct, sample_size, show_ids))


def check_tags(label, in_report, direct: Direct, sample_size, show_ids) -> Check:
    tagged = sorted(
        (r for r in in_report if row_tags(r) and short_id(r) in direct.ids),
        key=short_id,
    )
    name = f"tags {label}"
    if not tagged:
        return Check(name, SKIP, "no tagged resource in the report")
    bad = []
    for row in tagged[:sample_size]:
        key = short_id(row)
        try:
            expected = without_aws_tags(direct.tags(direct.ids[key]))
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{mask_tail(key, show_ids)}: {type(exc).__name__}")
            continue
        if without_aws_tags(row_tags(row)) != expected:
            bad.append(f"{mask_tail(key, show_ids)}: tags differ")
    sampled = min(sample_size, len(tagged))
    if bad:
        return Check(name, FAIL, f"{len(bad)} of {sampled}: " + "; ".join(bad))
    return Check(name, PASS, f"{sampled} sampled")


def check_files(output_dir: Path, create_word: bool) -> Tuple[List[Check], List[dict]]:
    checks: List[Check] = []
    rows: List[dict] = []
    xlsx = sorted(output_dir.glob("*.xlsx"))
    if not xlsx:
        checks.append(Check("report opens", FAIL, "no .xlsx written"))
    else:
        try:
            rows = read_report_rows(xlsx[0])
            checks.append(
                Check("report opens", PASS, f"{xlsx[0].name}, {len(rows)} rows")
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(Check("report opens", FAIL, f"{type(exc).__name__}: {exc}"))
    if create_word:
        docs = sorted(output_dir.glob("*.docx"))
        try:
            from docx import Document

            if not docs:
                raise FileNotFoundError("no .docx written")
            paragraphs = len(Document(str(docs[0])).paragraphs)
            checks.append(Check("word report opens", PASS, f"{paragraphs} paragraphs"))
        except Exception as exc:  # noqa: BLE001
            checks.append(
                Check("word report opens", FAIL, f"{type(exc).__name__}: {exc}")
            )
    states = sorted((output_dir / "state").glob("state_*.json"))
    try:
        data = json.loads(states[0].read_text(encoding="utf-8"))
        count = data["metadata"]["resource_count"]
        checks.append(Check("state snapshot", PASS, f"{count} resources recorded"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("state snapshot", FAIL, f"{type(exc).__name__}: {exc}"))
    return checks, rows


def check_no_writes(audit_files: List[dict]) -> Check:
    """Zero blocked calls, and every recorded operation is a read operation."""
    blocked = sum(a.get("blocked_calls", 0) for a in audit_files)
    total = sum(a.get("total_calls", 0) for a in audit_files)
    non_read = sorted(
        {
            f"{op['service']}:{op['operation']}"
            for a in audit_files
            for op in a.get("operations", [])
            if not op["operation"].startswith(READ_OPERATION_PREFIXES)
            and (op["service"], op["operation"]) != ("sts", "AssumeRole")
        }
    )
    if blocked or non_read:
        return Check(
            "no write calls",
            FAIL,
            f"blocked={blocked}; non-read operations: {', '.join(non_read) or 'none'}",
        )
    if total == 0:
        return Check("no write calls", FAIL, "the guard recorded no calls at all")
    return Check("no write calls", PASS, f"blocked 0 of {total} calls")


# ------------------------------------------------------------------ the scan
def scan_command(args, output_dir: Path, audit_path: Path) -> List[str]:
    cmd = [
        "--account-regions",
        args.region,
        "--create-excel",
        "--output-directory",
        str(output_dir),
        "--audit-output",
        str(audit_path),
    ]
    cmd.append(
        "--billing-validation" if args.billing_validation else "--no-billing-validation"
    )
    if args.create_word:
        cmd.append("--create-word")
    return cmd


def run_scan(args, output_dir: Path, audit_path: Path) -> Tuple[int, str, float]:
    """Returns (exit code, combined log, seconds)."""
    argv = scan_command(args, output_dir, audit_path)
    started = time.time()
    if args.in_process:
        import contextlib
        import io

        from inventag.cli.main import main

        buffer = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["inventag", *argv]
        code = 0
        try:
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                try:
                    main()
                except SystemExit as exc:
                    code = 0 if exc.code is None else int(exc.code)
        finally:
            sys.argv = old_argv
        return code, buffer.getvalue(), time.time() - started
    proc = subprocess.run(
        [sys.executable, "-m", "inventag", *argv],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=dict(os.environ),
    )
    return proc.returncode, proc.stdout + proc.stderr, time.time() - started


def load_audit(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------- output
def format_table(checks: List[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = [f"{'CHECK'.ljust(width)}  RESULT  DETAIL", "-" * (width + 40)]
    for c in checks:
        lines.append(f"{c.name.ljust(width)}  {c.status:<6}  {c.detail}")
    return "\n".join(lines)


def service_counts(rows) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        service = str(row.get("service"))
        counts[service] = counts.get(service, 0) + 1
    return dict(sorted(counts.items()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan one region with InvenTag and compare the result with "
        "direct read-only boto3 calls. Read the header of this file first."
    )
    parser.add_argument("--profile")
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1",
    )
    parser.add_argument("--output-directory")
    parser.add_argument("--billing-validation", action="store_true")
    parser.add_argument("--create-word", action="store_true")
    parser.add_argument("--sample-size", type=int, default=3)
    parser.add_argument("--show-ids", action="store_true")
    parser.add_argument("--in-process", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[List[str]] = None, out=print) -> int:
    args = build_parser().parse_args(argv)
    show = args.show_ids

    # The guard first: every client made below, and by the scan, is covered.
    from inventag.security.read_only_guard import install_global_guard

    guard = install_global_guard()

    if args.profile:
        os.environ["AWS_PROFILE"] = args.profile
    session = make_session(args.profile, args.region)
    try:
        sts = read_client(session, "sts", args.region)
        identity = sts.get_caller_identity()
    except Exception as exc:  # noqa: BLE001
        out(f"Cannot start: no usable AWS credentials ({type(exc).__name__}).")
        return 2
    out(
        f"Account {mask_account(identity['Account'], show)}, region {args.region}, "
        f"profile {args.profile or '(default chain)'}, "
        f"billing validation {'ON' if args.billing_validation else 'off'}"
    )

    own_dir = args.output_directory is None
    output_dir = Path(
        args.output_directory or tempfile.mkdtemp(prefix="inventag-smoke-")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit" / "aws_calls.json"
    checks: List[Check] = []
    try:
        code, log, seconds = run_scan(args, output_dir, audit_path)
        checks.append(
            Check(
                "scan exit code", PASS if code == 0 else FAIL, f"{code}, {seconds:.1f}s"
            )
        )
        file_checks, rows = check_files(output_dir, args.create_word)
        checks.extend(file_checks)
        if rows:
            check_counts_and_tags(
                session, args.region, rows, args.sample_size, show, checks
            )
        audits = [load_audit(audit_path), guard.audit_report()]
        checks.append(check_no_writes(audits))

        out("")
        out(format_table(checks))
        out("")
        if rows:
            counts = ", ".join(f"{s}={n}" for s, n in service_counts(rows).items())
            out(f"Resources in the report by service: {counts}")
        scan_audit = audits[0]
        if scan_audit:
            out(
                f"AWS calls made by the scan: {scan_audit.get('total_calls', 0)} "
                f"({scan_audit.get('blocked_calls', 0)} blocked)"
            )
        failed = [c for c in checks if c.status == FAIL]
        if failed:
            tail = "\n".join(scrub(log, show).splitlines()[-25:])
            out("")
            out("Last lines of the scan log (account IDs, ARNs and keys masked):")
            out(tail)
        out("")
        out(f"RESULT: {'FAIL' if failed else 'PASS'} ({len(failed)} failed)")
        if not own_dir:
            out(f"Report kept in {output_dir}")
        return 1 if failed else 0
    finally:
        if own_dir:
            shutil.rmtree(output_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
