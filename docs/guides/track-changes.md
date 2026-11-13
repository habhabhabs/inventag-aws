---
title: Track changes between runs
description: How InvenTag saves a snapshot of each run in bom_output/state, what the change report contains, and its current limitation.
sidebar_position: 6
slug: /architecture/state-management
---

# Track changes between runs

**Who this is for:** you run InvenTag on a schedule and want to know what
changed.

**What you will know after reading:** where snapshots are stored, what the
change report contains, and how to compare runs today.

## Snapshots

Every run saves what it found in the output folder. After two runs against
mocked AWS (sample data):

<!-- BEGIN EXAMPLE OUTPUT: changes-tree -->

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090000.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090100.json
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

Keep the `state/` folder between runs, for example as a CI cache or in a
bucket, if you want history. Turn snapshots off with
`--disable-state-management`.

## The change report: known limitation

From the second run on, InvenTag writes `changelog_<timestamp>.md`. On the
current release it compares the newest snapshot with **itself**, so it always
reports zero changes. In this sample a bucket was added between the two runs,
yet the changelog says:

<!-- BEGIN EXAMPLE OUTPUT: changes-changelog -->

<details>
<summary>changelog_20261112_090000.md (first 30 lines)</summary>

```markdown
# Multi-Account Infrastructure Changes

**Generated:** 2026-11-12T09:00:00+00:00

## State Comparison

- **from_state:** 20261112_090000
- **to_state:** 20261112_090000
- **comparison_timestamp:** 2026-11-12T09:00:00+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total Changes | 1 |
| Critical Changes | 0 |
| High Severity | 0 |
| Security Changes | 0 |
| Compliance Changes | 0 |
| Network Changes | 0 |

**Most Impacted Services:**
- S3: 1 changes

## S3 Service Changes

Changes detected in S3 service resources

### New Bucket 'acme-new-bucket' was created in S3
- **Type:** added
```

</details>

<!-- END EXAMPLE OUTPUT: changes-changelog -->

Until this is fixed, don't rely on the changelog.

## Compare runs today

The snapshots themselves are correct, so you can compare two of them. Each
snapshot is JSON with a `resources` list:

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

```text title="Terminal"
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

<!-- END EXAMPLE OUTPUT: changes-diff -->

## Next steps

- [Feature status and known limitations](../getting-started/status.md)
- [Run InvenTag in CI/CD](./run-in-ci.md)
