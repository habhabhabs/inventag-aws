---
title: Track changes between runs
description: How InvenTag saves a snapshot of each run in bom_output/state, what the change report contains, and what to know before you rely on it.
sidebar_position: 6
slug: /architecture/state-management
---

# Track changes between runs

**Who this is for:** you run InvenTag on a schedule and want to know what
changed.

**What you will know after reading:** where snapshots are stored, what the
change report contains, and how to compare runs yourself.

## Snapshots

Every run saves what it found in the output folder. After two runs against
mocked AWS (sample data):

<!-- BEGIN EXAMPLE OUTPUT: changes-tree -->

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

<!-- END EXAMPLE OUTPUT: changes-tree -->

Each snapshot holds every resource the run found:

<!-- BEGIN EXAMPLE OUTPUT: changes-snapshot -->

```json title="state/state_<timestamp>.json (structure)"
{
  "top_level_keys": [
    "compliance_data",
    "metadata",
    "network_analysis",
    "resources",
    "security_analysis"
  ],
  "one_resource": {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "acme-app-logs",
    "arn": "arn:aws:s3:::acme-app-logs",
    "region": "us-east-1",
    "tags": {
      "Environment": "prod",
      "Owner": "platform",
      "CostCenter": "CC-1001",
      "Project": "storefront",
      "DataClassification": "internal"
    },
    "source_account_id": "123456789012"
  }
}
```

<!-- END EXAMPLE OUTPUT: changes-snapshot -->

The `metadata` part of a snapshot records the snapshot version (`1.1`;
version `1.0` files still load), `accounts_scanned` and `accounts_failed`.
Values of fields that often hold secrets, such as Lambda environment
variables, passwords, tokens and private keys, are replaced by
`***REDACTED***`; the names stay. The full list, which also covers
CloudFormation stack outputs, Glue trigger arguments, connection strings and
signed URLs, is on [Feature status](../getting-started/status.md#what-inventag-finds-and-what-it-does-not). A change to such a value is not reported.
Snapshots from earlier versions may still hold these values, so delete or
restrict old `bom_output/` folders. The first run after the upgrade shows the
masked values as changed.

Keep the `state/` folder between runs, for example as a CI cache or in a
bucket, if you want history. Turn snapshots off with
`--disable-state-management`. The `state/partial/` folder holds saved account
results for [`--resume`](./run-a-scan.md#continue-after-a-failed-run). It is
not part of the history.

## The change report

From the second run on, InvenTag compares the new snapshot with the one before
it and writes `changelog_<timestamp>.md` in the output folder. The first run
has nothing to compare with, so it writes no change report.

In this sample a bucket was added between the two runs. The change report
lists it:

<!-- BEGIN EXAMPLE OUTPUT: changes-changelog -->

<details>
<summary>changelog_20261112_090100.md (first 30 lines)</summary>

```markdown
# Multi-Account Infrastructure Changes

**Generated:** 2026-11-12T09:00:00+00:00

## State Comparison

- **from_state:** 20261112_090000
- **to_state:** 20261112_090100
- **comparison_timestamp:** 2026-11-12T09:00:00+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total Changes | 2 |
| Critical Changes | 0 |
| High Severity | 0 |
| Security Changes | 0 |
| Compliance Changes | 0 |
| Network Changes | 0 |

**Most Impacted Services:**
- S3: 1 changes
- ATHENA: 1 changes

## S3 Service Changes

Changes detected in S3 service resources

### New Bucket 'acme-new-bucket' was created in S3
```

</details>

<!-- END EXAMPLE OUTPUT: changes-changelog -->

The report has a summary table, then a section for each service with
changes. Each change has a type (such as `added`), a severity, the resource and
its ARN.

What to know:

- It compares one run with the run before it. It does not compare with an
  older run you pick.
- It compares the resources each run found. Use the same regions, services and
  filters for both runs, so that a change in scope is not read as a change in
  your estate.
- `--no-generate-changelog` stops the report but keeps the snapshots.
  `--disable-delta-detection` also stops it. `--disable-state-management`
  stops snapshots and reports.
- If an account could not be scanned, or only partly, in either of the two
  runs, its resources are left out of the comparison. Otherwise all of them
  would show as added or removed. The change report names the account in its
  State Comparison section (`accounts_not_compared`).
- InvenTag compares lists as unordered, so moving items around in a list is
  not a change. It also ignores fields that change on every run: the
  discovery route, cost figures and usage counters such as `ItemCount` or
  `ApproximateNumberOfMessages`.
- When a run saves a snapshot, InvenTag removes snapshots older than 30 days
  or beyond the newest 100. Change the limits with `--state-retention-days N`
  and `--state-max-snapshots N`; `0` or `none` turns a limit off. The snapshot
  just written and the one it is compared with are never removed, so
  `--state-max-snapshots 1` leaves two files. InvenTag removes only the
  `state_<timestamp>.json` files it wrote itself. A scheduled job on a fresh
  runner has no earlier snapshot, so keep the `state/` folder between runs.

## Compare two snapshots yourself

You can compare any two snapshots, because each is JSON with a `resources`
list:

```bash
python3 - <<'EOF'
import json, sys, glob
old, new = sorted(glob.glob("bom_output/state/state_*.json"))[-2:]
ids = lambda f: {r.get("arn") or r.get("id") for r in json.load(open(f))["resources"]}
a, b = ids(old), ids(new)
print("Added:", sorted(b - a))
print("Removed:", sorted(a - b))
EOF
```

Sample output after adding one bucket between two runs (sample data):

<!-- BEGIN EXAMPLE OUTPUT: changes-diff -->

```text title="Output"
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

<!-- END EXAMPLE OUTPUT: changes-diff -->

## Next steps

- [Feature status](../getting-started/status.md)
- [Run InvenTag in CI/CD](./run-in-ci.md)
