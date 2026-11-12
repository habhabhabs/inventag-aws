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

Every run saves what it found in the output folder:

```text
bom_output/
  state/
    metadata.json                  # index of saved snapshots
    state_20261112_050918.json     # one file per run
    state_20261112_051625.json
  changelog_20261112_131625.md     # written from the second run on
```

Keep the `state/` folder between runs, for example as a CI cache or in a
bucket, if you want history. Turn snapshots off with
`--disable-state-management`.

## The change report: known limitation

From the second run on, InvenTag writes `changelog_<timestamp>.md`. On the
current release, it compares the newest snapshot with **itself**, so it
always reports zero changes. We checked this by adding a bucket between two
runs against mocked AWS. The changelog said:

```text
- **from_state:** 20261112_051625
- **to_state:** 20261112_051625
...
| Total Changes | 0 |
```

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

Sample output after adding one bucket between two runs (mocked AWS, sample
data):

```text
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

## Next steps

- [Feature status and known limitations](../getting-started/status.md)
- [Run InvenTag in CI/CD](./run-in-ci.md)
