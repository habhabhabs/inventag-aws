#!/usr/bin/env python3
"""Benchmark change detection (``DeltaDetector.detect_changes``) on synthetic snapshots.

What it does
    1. Builds two snapshots of N resources each, in the shape the scanner saves
       (ARN, id, service, type, region, tags, and the relationship fields
       ``vpc_id``, ``subnet_id``, ``security_groups``, ``iam_role``,
       ``kms_key_id``). The estate is VPCs, subnets and security groups
       (service ``VPC``), EC2 instances and EBS volumes (service ``EC2``), RDS
       databases, S3 buckets, Lambda functions and load balancers (``ELB``).
    2. The second snapshot differs from the first by ``--changed-share`` of N:
       a third of that share is removed, a third added and a third modified
       (a tag value changes; every fourth modified resource also changes a
       security-related field).
    3. Times ``detect_changes`` for each N and, with ``--changelog``, the
       changelog built from its result. With ``--profile N`` it prints a
       cProfile of one run at that size instead.

Run it
        python scripts/benchmark_delta.py                      # N = 100..1600
        python scripts/benchmark_delta.py --sizes 100 200 400
        python scripts/benchmark_delta.py --changed-share 1.0  # every resource changes
        python scripts/benchmark_delta.py --fresh --shape scanner  # the CLI case
        python scripts/benchmark_delta.py --profile 800

No AWS call is made: the snapshots are plain Python data.
"""

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from inventag.state.delta_detector import DeltaDetector  # noqa: E402

ACCOUNT = "123456789012"
REGION = "ap-southeast-1"

# Share of the estate per kind (adds up to 1.0).
MIX = [
    ("vpc", 0.02),
    ("subnet", 0.06),
    ("sg", 0.10),
    ("instance", 0.30),
    ("volume", 0.20),
    ("rds", 0.08),
    ("bucket", 0.10),
    ("lambda", 0.10),
    ("elb", 0.04),
]


def _resource(kind: str, i: int, vpcs: int) -> dict:
    """One resource of the given kind, number i, spread over ``vpcs`` VPCs."""
    v = i % vpcs
    vpc_id = f"vpc-{v:08x}"
    subnet_id = f"subnet-{v:04x}{i % 3:04x}"
    sgs = [f"sg-{v:04x}{(i + k) % 5:04x}" for k in range(2)]
    tags = {"Name": f"{kind}-{i}", "Environment": "prod", "Owner": "team-a"}
    base = {
        "region": REGION,
        "account_id": ACCOUNT,
        "tags": tags,
        "discovered_at": "2026-11-14T00:00:00+00:00",
    }
    if kind == "vpc":
        rid = vpc_id if i < vpcs else f"vpc-x{i:07x}"
        return {
            **base,
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT}:vpc/{rid}",
            "id": rid,
            "service": "VPC",
            "type": "VPC",
            "vpc_id": rid,
        }
    if kind == "subnet":
        rid = f"subnet-{i:08x}"
        return {
            **base,
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT}:subnet/{rid}",
            "id": rid,
            "service": "VPC",
            "type": "Subnet",
            "vpc_id": vpc_id,
            "subnet_id": rid,
        }
    if kind == "sg":
        rid = f"sg-{i:08x}"
        return {
            **base,
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT}:security-group/{rid}",
            "id": rid,
            "service": "VPC",
            "type": "SecurityGroup",
            "vpc_id": vpc_id,
        }
    if kind == "instance":
        rid = f"i-{i:017x}"
        return {
            **base,
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT}:instance/{rid}",
            "id": rid,
            "service": "EC2",
            "type": "Instance",
            "state": "running",
            "instance_type": "t3.micro",
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "security_groups": sgs,
            "iam_role": f"arn:aws:iam::{ACCOUNT}:role/app-{i % 7}",
        }
    if kind == "volume":
        rid = f"vol-{i:017x}"
        return {
            **base,
            "arn": f"arn:aws:ec2:{REGION}:{ACCOUNT}:volume/{rid}",
            "id": rid,
            "service": "EC2",
            "type": "EBS Volume",
            "size": 8,
            "encrypted": True,
            "kms_key_id": f"arn:aws:kms:{REGION}:{ACCOUNT}:key/k{i % 4}",
        }
    if kind == "rds":
        rid = f"db-{i}"
        return {
            **base,
            "arn": f"arn:aws:rds:{REGION}:{ACCOUNT}:db:{rid}",
            "id": rid,
            "service": "RDS",
            "type": "DBInstance",
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "security_groups": sgs[:1],
            "kms_key_id": f"arn:aws:kms:{REGION}:{ACCOUNT}:key/k{i % 4}",
        }
    if kind == "bucket":
        rid = f"bucket-{i}"
        return {
            **base,
            "arn": f"arn:aws:s3:::{rid}",
            "id": rid,
            "service": "S3",
            "type": "Bucket",
            "kms_key_id": f"arn:aws:kms:{REGION}:{ACCOUNT}:key/k{i % 4}",
        }
    if kind == "lambda":
        rid = f"fn-{i}"
        return {
            **base,
            "arn": f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{rid}",
            "id": rid,
            "service": "Lambda",
            "type": "Function",
            "vpc_id": vpc_id,
            "security_groups": sgs[:1],
            "iam_role": f"arn:aws:iam::{ACCOUNT}:role/app-{i % 7}",
        }
    if kind == "elb":
        rid = f"lb-{i}"
        return {
            **base,
            "arn": f"arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:loadbalancer/app/{rid}/{i:016x}",
            "id": rid,
            "service": "ELB",
            "type": "LoadBalancer",
            "vpc_id": vpc_id,
            "security_groups": sgs[:1],
        }
    raise ValueError(kind)


def build_estate(n: int, start: int = 0, vpcs: int = 0) -> list:
    """N resources in the MIX proportions, numbered from ``start``."""
    vpcs = vpcs or max(1, n // 100)
    kinds = []
    for kind, share in MIX:
        kinds.extend([kind] * int(round(n * share)))
    kinds = (kinds + ["instance"] * n)[:n]
    return [_resource(kind, start + i, vpcs) for i, kind in enumerate(kinds)]


RELATIONSHIP_FIELDS = (
    "vpc_id",
    "subnet_id",
    "security_groups",
    "iam_role",
    "kms_key_id",
)


def build_pair(n: int, changed_share: float, vpcs: int = 0, shape: str = "linked"):
    """(old, new) snapshots of n resources; ``changed_share`` of n differ.

    ``shape`` "scanner" drops the relationship fields, as the v1.2.0 scanner
    saves rows (they are not top-level fields there); "linked" keeps them.
    ``changed_share`` above 1 is not allowed; use ``fresh`` for an estate where
    every ID differs.
    """
    old, new = _build_pair(n, changed_share, vpcs)
    if shape == "scanner":
        for r in old + new:
            for f in RELATIONSHIP_FIELDS:
                r.pop(f, None)
    return old, new


def _build_pair(n: int, changed_share: float, vpcs: int = 0):
    if changed_share < 0:  # fresh estate: same shape, every ID different
        return build_estate(n, vpcs=vpcs), build_estate(n, start=n, vpcs=vpcs)
    old = build_estate(n, vpcs=vpcs)
    changed = int(round(n * changed_share))
    removed = changed // 3
    added = changed // 3
    modified = changed - removed - added
    step = max(1, n // max(1, changed))
    picks = list(range(0, n, step))[:changed]
    removed_idx = set(picks[:removed])
    modified_idx = picks[removed : removed + modified]
    new = []
    for i, r in enumerate(old):
        if i in removed_idx:
            continue
        r2 = {**r, "tags": dict(r["tags"])}
        new.append(r2)
    by_arn = {r["arn"]: r for r in new}
    for k, i in enumerate(modified_idx):
        r = by_arn.get(old[i]["arn"])
        if r is None:
            continue
        r["tags"]["Environment"] = "staging"
        if k % 4 == 0 and "security_groups" in r:
            r["security_groups"] = list(r["security_groups"]) + ["sg-ffffffff"]
    extra = build_estate(added, start=n, vpcs=vpcs or max(1, n // 100))
    new.extend(extra)
    return old, new


def time_once(old, new, changelog: bool):
    detector = DeltaDetector()
    t0 = time.perf_counter()
    report = detector.detect_changes(old, new, "old", "new")
    t1 = time.perf_counter()
    t_changelog = None
    if changelog:
        from inventag.state.changelog_generator import ChangelogGenerator

        gen = ChangelogGenerator()
        t2 = time.perf_counter()
        gen.generate_changelog(report).to_markdown()
        t_changelog = time.perf_counter() - t2
    related = sum(
        len(c.related_resources)
        for c in report.added_resources
        + report.removed_resources
        + report.modified_resources
    )
    return t1 - t0, t_changelog, report.summary["total_changes"], related


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sizes", type=int, nargs="+", default=[100, 200, 400, 800, 1600]
    )
    parser.add_argument(
        "--changed-share",
        type=float,
        default=0.2,
        help="share of N that differs (default 0.2)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="every ID differs (a run against another estate): N added, N removed",
    )
    parser.add_argument(
        "--shape",
        choices=["linked", "scanner"],
        default="linked",
        help="linked: rows carry vpc_id, subnet_id, security_groups, iam_role, "
        "kms_key_id; scanner: rows without them, as the v1.2.0 scanner saves",
    )
    parser.add_argument(
        "--vpcs", type=int, default=0, help="VPCs in the estate (default N/100)"
    )
    parser.add_argument("--changelog", action="store_true")
    parser.add_argument("--profile", type=int, default=0, metavar="N")
    args = parser.parse_args(argv)

    share = -1.0 if args.fresh else args.changed_share
    if args.profile:
        old, new = build_pair(args.profile, share, args.vpcs, args.shape)
        prof = cProfile.Profile()
        prof.enable()
        time_once(old, new, args.changelog)
        prof.disable()
        out = io.StringIO()
        stats = pstats.Stats(prof, stream=out).sort_stats("cumulative")
        stats.print_stats(25)
        print(out.getvalue())
        return 0

    changed = (
        "fresh estate (all IDs differ)"
        if args.fresh
        else (f"changed share {args.changed_share:.0%}")
    )
    print(
        f"{changed}, shape {args.shape}, VPCs {args.vpcs or 'N/100'}, "
        f"Python {sys.version.split()[0]}"
    )
    header = "| N | changes | related links | detect_changes s | x prev |"
    if args.changelog:
        header += " changelog s |"
    print(header)
    print(header_rule(header))
    prev = None
    for n in args.sizes:
        old, new = build_pair(n, share, args.vpcs, args.shape)
        secs, t_cl, changes, related = time_once(old, new, args.changelog)
        ratio = f"{secs / prev:.1f}" if prev else "-"
        row = f"| {n} | {changes} | {related} | {secs:.3f} | {ratio} |"
        if args.changelog:
            row += f" {t_cl:.3f} |"
        print(row, flush=True)
        prev = secs
    return 0


def header_rule(header: str) -> str:
    return "|" + "---|" * (header.count("|") - 1)


if __name__ == "__main__":
    sys.exit(main())
