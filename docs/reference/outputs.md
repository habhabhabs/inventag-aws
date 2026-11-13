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
`--output-directory` or `output_directory` in a config template. The only
other places InvenTag writes are the files you name (`--log-file`,
`--audit-output`) and, with `--s3-bucket`, your S3 bucket.

Output files are created readable and writable by your user only, and new
output folders are private to your user too.

The samples on this page come from offline runs against mocked AWS (sample
data).

## File list

| File | When | Content |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`, or no output flag | The Excel report |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | The Word report |
| `tag_compliance_<timestamp>.json` | A tag policy is active | Tag check results |
| `state/state_<timestamp>.json` | Every run, unless `--disable-state-management` | Snapshot of every resource found. Snapshots older than 30 days, or beyond the newest 100, are removed. |
| `state/metadata.json` | With snapshots | Index of snapshots: time, account, regions, resource count, checksum |
| `changelog_<timestamp>.md` | Second and later runs, unless `--no-generate-changelog` or `--disable-delta-detection` | What was added, removed or changed since the previous snapshot. See [Track changes](../guides/track-changes.md). |
| The file you name with `--audit-output` | When you ask for it | Every AWS operation the run called |

`<timestamp>` is `YYYYMMDD_HHMMSS`.

## Excel report

**Without a template**, the workbook has:

- **Summary:** Service, Resource Count, Percentage, and a total.
- **One sheet per service** (for example `EC2`, `S3`, `VPC`), sorted by
  service name, with every field found on its resources, including flattened
  `raw_data.*` and `tags.*` columns. Rows are sorted by type, name and ID.
- **Network Analysis** and **Security Analysis** sheets, only with
  `--enable-network-analysis` or `--enable-security-analysis`.

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
are stored as text, never as formulas. Rows are sorted by service, type,
name and ID.

Previews of each layout, made from real files, are in
[Built-in templates](../templates/catalogue.md).

## Word report

**Without a template:** a title, an executive summary, a service table, and
up to 50 resources per service in six columns.

**With a report template:** the sections listed in `word.sections`. Tables
have a header row that repeats on each page and is marked as a header for
screen readers. The logo, if any, carries alt text.

## Tag compliance JSON

<!-- BEGIN EXAMPLE OUTPUT: outputs-json -->

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 22,
    "compliant": 1,
    "non_compliant": 21,
    "out_of_scope": 14,
    "percent_compliant": 4.5,
    "missing_by_key": {
      "CostCenter": 19,
      "Owner": 18,
      "Project": 20,
      "Environment": 18
    },
    "invalid_by_key": {
      "CostCenter": 1,
      "Owner": 0,
      "Project": 0,
      "Environment": 1
    }
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

<!-- END EXAMPLE OUTPUT: outputs-json -->

## Snapshots

<!-- BEGIN EXAMPLE OUTPUT: changes-tree -->

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

<!-- END EXAMPLE OUTPUT: changes-tree -->

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

## Audit JSON

<!-- BEGIN EXAMPLE OUTPUT: audit-json -->

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 72,
  "allowed_calls": 72,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "ce",
      "operation": "GetCostAndUsage",
      "allowed": true,
      "count": 2
    },
    {
      "service": "cloudformation",
      "operation": "DescribeStacks",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudformation",
      "operation": "ListStackSets",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudfront",
      "operation": "ListDistributions",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

<!-- END EXAMPLE OUTPUT: audit-json -->

## S3 objects

With `--s3-bucket acme-inventory-reports --s3-key-prefix inventag/`, each run
puts its files under a folder named after the run:

<!-- BEGIN EXAMPLE OUTPUT: s3-keys -->

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

<!-- END EXAMPLE OUTPUT: s3-keys -->

## Terminal output

Without `--verbose`, a run prints warnings, errors and the files written. With
a template, each file is printed as `Wrote <path>`, followed by a one-line tag
policy summary when a policy is active.

## Exit codes

See [Command-line reference](./cli.md#exit-codes).
