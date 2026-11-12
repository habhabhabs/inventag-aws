---
title: Output files
description: Every file InvenTag writes - Excel and Word reports, tag compliance JSON, snapshots and changelogs - with their names, locations and contents.
sidebar_position: 4
---

# Output files

**Who this is for:** you process InvenTag's output in scripts, or explain the
reports to others.

**What you will know after reading:** the name, location and content of every
file InvenTag writes.

Everything goes into the output folder: `bom_output/` unless you set
`--output-directory` or `output_directory` in a config template. InvenTag
writes nothing else, and nothing to AWS.

## File list

| File | When | Content |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`, or no output flag | The Excel report |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | The Word report |
| `tag_compliance_<timestamp>.json` | A tag policy is active | Tag check results |
| `state/state_<timestamp>.json` | Every run, unless `--disable-state-management` | Snapshot of every resource found |
| `state/metadata.json` | With snapshots | Index of snapshots: time, account, regions, resource count, checksum |
| `changelog_<timestamp>.md` | Second and later runs | Change report. Currently always reports 0 changes; see [Track changes](../guides/track-changes.md). |

`<timestamp>` is `YYYYMMDD_HHMMSS`.

## Excel report

**Without a template**, the workbook has:

- **Summary:** Service, Resource Count, Percentage, and a total.
- **One sheet per service** (for example `EC2`, `S3`, `VPC`) with every field
  found on its resources, including flattened `raw_data.*` and `tags.*`
  columns.

**With a report template**, the layout follows the template:

- **Summary:** title, generation time, the number of accounts and regions, a
  Service / Resources / Share table and, with a tag policy, the compliance
  counts.
- **Resource sheets:** one per service, or one sheet with `layout:
  single-sheet`. Header rows are styled, frozen and filterable by default.
- **Tag Compliance** (with a tag policy): one row per resource in scope, then
  a table of rules with missing and invalid counts.

Sheet names follow Excel's rules: at most 31 characters, without
`[ ] : * ? / \`. Duplicate names get a number. Cell values that start with `=`
are stored as text, never as formulas.

## Word report

**Without a template:** a title, an executive summary, a service table, and
up to 50 resources per service in six columns.

**With a report template:** the sections listed in `word.sections`. Tables
have a header row that repeats on each page and is marked as a header for
screen readers. The logo, if any, carries alt text.

## Tag compliance JSON

```json
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 23,
    "compliant": 1,
    "non_compliant": 22,
    "out_of_scope": 14,
    "percent_compliant": 4.3,
    "missing_by_key": {"CostCenter": 20, "Owner": 20, "Project": 21, "Environment": 20},
    "invalid_by_key": {"CostCenter": 1, "Owner": 0, "Project": 0, "Environment": 1}
  },
  "non_compliant_resources": [
    {
      "account": "123456789012",
      "service": "S3",
      "resource_type": "Bucket",
      "resource_id": "acme-reports",
      "arn": "arn:aws:s3:::acme-reports",
      "region": "us-east-1",
      "missing": [],
      "invalid": [
        "CostCenter: '1234' does not match CC-[0-9]{4}",
        "Environment: 'Production' is not one of prod, staging, dev, test, sandbox"
      ]
    }
  ]
}
```

Sample data from an offline run, with one resource shown.

## Terminal output

Without `--verbose`, a run prints warnings, errors and the files written. With
a template, each file is printed as `Wrote <path>`, followed by a one-line tag
policy summary when a policy is active.

## Exit codes

See [Command-line reference](./cli.md#exit-codes).
