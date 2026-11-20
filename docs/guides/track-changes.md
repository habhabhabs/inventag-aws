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
- It compares the resources each run found. Resources that the current run
  did not look at (a region or a service it did not scan) or could not read (a
  denied, throttled or failed listing) are not compared: the State Comparison
  section counts them under `resources_not_compared`, and they do not show as
  removed. A region or service that only the current run scanned shows its
  resources as added, so use the same regions, services and filters for both
  runs.
- A snapshot names the listings its run could not read
  (`metadata.tags.units_not_read`: account, service, region, source and
  outcome; present only when a listing failed). The next change report leaves
  the resources of those listings out instead of showing them as added. A
  snapshot written by v1.2.2 or earlier has no such list, so the first
  comparison with it behaves as before.
- When a call that reads the details of a resource (for example the S3 bucket
  location or the Lambda function configuration) fails in one of the two runs,
  the fields that call adds are not compared for the resources of that service
  and region. The change report names those units in one line that starts
  `Details not read, so the fields they add are not compared:`. The State
  Comparison data calls it `details_not_compared`. A snapshot records the units
  whose detail calls failed in `metadata.tags.details_not_read`. The key is
  there only when such a call failed.
- A snapshot records the InvenTag version that wrote it
  (`metadata.tags.inventag_version`). The first change report after an
  upgrade does not count a field that the new version reads for the first
  time as a change, and says in one line how many fields it left out. A real
  change to such a field in that window is not reported, once.
- The change report lists attribute changes in a fixed order, so two reports
  of the same change are identical.
- `--no-generate-changelog` stops the report but keeps the snapshots.
  `--disable-delta-detection` also stops it. `--disable-state-management`
  stops snapshots and reports.
- If an account could not be scanned or ran out of time in either of the two
  runs, its resources are left out of the comparison. Otherwise all of them
  would show as added or removed. The change report names the account in its
  State Comparison section (`accounts_not_compared`), with the reason: "could
  not scan it", or "read it only in part" when some of its resources were
  read.
  The same holds for an account whose session expired part-way and for an
  account in which nothing at all could be read. A resource that the Tagging
  API returned before is still compared when the Tagging API read its region in
  this run; when the Tagging API did not answer for a region, tags are not
  compared there.
- InvenTag compares lists as unordered, so moving items around in a list is
  not a change, except Lambda layers, Auto Scaling termination policies and
  CloudFront cache behaviors, whose order is configuration. It also ignores
  fields that change on every run: the discovery route, cost figures and usage
  counters such as `ItemCount`, `ApproximateNumberOfMessages` or the EFS size.
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
