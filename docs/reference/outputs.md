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
`--audit-output`, `templates init --output`), your S3 bucket with `--s3-bucket`,
and with the Google options your Google Drive and, for `--google-oauth-client`,
a sign-in token file at `~/.config/inventag/google-token.json`.

Output files are created readable and writable by your user only, and new
output folders are private to your user too.

Not verified against Windows: files and folders private to your user.

The samples on this page come from offline runs against mocked AWS (sample
data).

## File list

| File | When | Content |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`, or no output flag | The Excel report |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | The Word report |
| `<account-id>_bom_<timestamp>.xlsx` and `.docx` | `--per-account-reports`, instead of the `multi_account_bom_*` files | One report for each account that has resources |
| `tag_compliance_<timestamp>.json` | A tag policy is active | Tag check results |
| `state/state_<timestamp>.json` | Every run, unless `--disable-state-management` | Snapshot of every resource found, with secret values masked. `metadata.tags.coverage_summary` counts, per account, how the listing calls ended (`ok`, `empty`, `denied`, `throttled`, `error`, `timeout`, and `out_of_scope` for services that `--account-services` left out). `metadata.tags.units_not_read` lists the listings that were not read (only when one failed), and `metadata.tags.inventag_version` names the InvenTag version that wrote the snapshot. Snapshots older than 30 days, or beyond the newest 100, are removed (`--state-retention-days`, `--state-max-snapshots`). |
| `state/metadata.json` | With snapshots | Index of snapshots: time, account, regions, resource count, checksum |
| `policy_findings_<timestamp>.json` | `--policy` (the default of `--policy-format`), `--finops-checks` with `--template`, or `inventag policy check --format json` | The result of checking policies on a snapshot. See [Policy findings](#policy-findings). |
| `policy_findings_<timestamp>.sarif`, `.xml` and `.md` | `--policy-format sarif`, `junit` or `markdown`, or the same words in `--format` of `inventag policy check` | The same result as SARIF 2.1.0, JUnit XML and Markdown. `junit` writes `.xml` and `markdown` writes `.md`. |
| `changelog_<timestamp>.md` | Second and later runs, unless `--no-generate-changelog` or `--disable-delta-detection` | What was added, removed or changed since the previous snapshot. See [Track changes](../guides/track-changes.md). |
| The file you name with `--audit-output` | When you ask for it | Every AWS operation the run called |
| `state/partial/<key>/<account-id>.json` | A run in which some accounts failed | Results of the accounts that finished, reused by `--resume` and removed after a complete run |

`<timestamp>` is `YYYYMMDD_HHMMSS`. Report, Word, changelog and tag compliance names use your computer's local time. The snapshot and the S3 folder use UTC. The `<timestamp>` of a `policy_findings_` file is the time stored in the snapshot that was checked (UTC), not the clock of the check.

The default workbook has a `raw_data.*` column for every API field, so its sheets can be wide. A snapshot is indented JSON and holds the whole `raw_data` of every resource, so it can be large. No option leaves the `raw_data.*` columns out or compresses a snapshot; both are planned for a later release.

## Excel report

**Without a template**, the workbook has:

- **Summary:** Service, Resource Count, Percentage, and a total.
- **One sheet per service** (for example `EC2`, `S3`, `VPC`), sorted by
  service name, with every field found on its resources, including flattened
  `raw_data.*` and `tags.*` columns. An API field that is a map keyed by IDs
  is one JSON cell. Rows are sorted by type, name and ID.
  Every row has a `source` column (`service-api`, `tagging-api` or
  `billing`: the API that returned it), a `sources` column (all of them,
  joined with `+`) and a `detail_level` column (`full` for rows from the
  service's own API, `identity` for the others).
- **Network Analysis** and **Security Analysis** sheets, only with
  `--enable-network-analysis` or `--enable-security-analysis`.
- **Cost Analysis** sheet, only with `--enable-cost-analysis`: estimated
  monthly costs from the AWS Pricing API, not your invoice, and a table of
  billed cost for each account and service from Cost Explorer. See
  [Cost Analysis sheet](#cost-analysis-sheet).
- **FinOps** sheet, the last sheet, only with `--finops-checks`: see
  [FinOps sheet and the `finops_checks` key](#finops-sheet-and-the-finops_checks-key).

Values of fields that often hold secrets, such as Lambda environment
variables, CloudFormation stack outputs, Glue trigger arguments, connection
strings and signed URLs, show `***REDACTED***` in every report, snapshot and log. The field
names stay. See [Feature status](../getting-started/status.md#what-inventag-finds-and-what-it-does-not).

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

## FinOps sheet and the `finops_checks` key

With `--finops-checks`, the default workbook ends with a `FinOps` sheet. Its
first line is a note, then come the listed results with the columns
`Check ID`, `Check`, `Result`, `Reason`, `Account`, `Region`, `Service`,
`Resource Type`, `Resource ID`, `Name` and `Observed`, sorted by check ID,
account, region and resource ID. A table of the counts per check (`Fail`,
`Not evaluated`, `Pass`) follows. With `--template`, no `FinOps` sheet is
written.

The command line writes no JSON file for these results. In Python, the result
of `CloudBOMGenerator.generate_multi_account_bom()` has the key
`finops_checks`, and so has the `metadata` of a JSON report written with the
`json` output format. Without the flag, the key is not there. The fields are
listed in [FinOps checks](../guides/finops-checks.md#the-finops_checks-result).

## FinOps costs sheet and the `finops_costs` key

With `--finops-cost-allocation`, the default workbook ends with a
`FinOps costs` sheet (after the `FinOps` sheet when both flags are on): a
note, then one row for each account, grouping and value, with the columns
`Account`, `Grouping`, `Value`, `Amount`, `Currency`, `Metric`, `Period start`,
`Period end` and `Status`. The result of
`CloudBOMGenerator.generate_multi_account_bom()` and the `metadata` of a JSON
report have the key `finops_costs`; the snapshot has
`metadata.tags.cost_allocation` (tables only, unless `--no-cost-in-snapshot`).
See [FinOps checks](../guides/finops-checks.md#cost-allocation-from-cost-explorer).

## Cost Analysis sheet

With `--enable-cost-analysis`, the default workbook has a `Cost Analysis`
sheet. Its first row says that the figures are estimates from the AWS Pricing
API and not your invoice. The tables follow in this order: `Summary`,
estimated monthly cost by service, the most expensive resources (top 50), the
cost trend, possibly forgotten resources and recommendations. Every table after
`Summary` is left out when it has no rows.

The cost trend table is titled "Billed cost by account and service, last two
full months (Cost Explorer; a service total, not a resource's cost)". It has
one row for each account and service, from that account's own Cost Explorer
bill, with the columns:

| Column | Content |
|---|---|
| `Account` | The account ID of the resources |
| `Service` | The service as the report names it, for example `EC2` or `S3` |
| `Resources` | How many resources of that service the account has in the report |
| `Earlier month` | The earlier of the two full months before the run, as `YYYY-MM` |
| `Billed (USD)` (first) | What Cost Explorer billed for the service in that month |
| `Later month` | The later month, as `YYYY-MM` |
| `Billed (USD)` (second) | What Cost Explorer billed for the service in the later month |
| `Change %` | The change from the earlier to the later month, rounded to one decimal. From a zero bill it is 100 when the later month is billed, else 0 |
| `Direction` | `increasing` or `decreasing`, or `stable` when the change is less than 5 percent either way |
| `Billing names counted` | The Cost Explorer service names that were added up in that row, separated by commas |

The amount columns show the unit that Cost Explorer returned: `Billed (USD)`
when every row has the same unit, else `Billed (unit as returned)` and each
cell then ends with its unit. A row is a service total in the account, not the
cost of one resource, and it is not divided among resources. A service's figure
is the sum of the billing names shown in its row. `EC2 - Other` (volumes, NAT
gateways, data transfer) is a separate billing name and is not in EC2's row;
`Amazon EC2 Container Registry (ECR)` is not in it either. An account whose
trend request was denied or failed, or that has no session, has no rows, and
the run says so in a warning. Months are the two full months before the run.

In Python, the same rows are `cost_analysis["cost_trends"]` of the result of
`CloudBOMGenerator.generate_multi_account_bom()`. Each entry has `account_id`,
`service`, `billing_names`, `resource_count`, `previous_month`,
`current_month`, `previous_monthly_cost`, `current_monthly_cost`,
`cost_change_percentage`, `trend_direction`, `alert_triggered` and `unit`.
Before v1.5.0, no sheet showed the trend; each entry of `cost_trends` named a
resource (`resource_id`) and held the service total divided by the number of
its resources. Those entries are gone:
code that reads `resource_id` from `cost_trends` must read one entry for each
account and service instead. See
[FinOps checks](../guides/finops-checks.md#the-cost-trend-of---enable-cost-analysis).

Not verified against real AWS: the bills a real account returns, including
what a management (payer) account and a member account each see.

## Policy findings

`inventag policy check`, `--policy` and `--finops-checks` with `--template`
write the result of checking policies on a state snapshot to files named
`policy_findings_<timestamp>.<extension>` in the output directory (the folder
of `--output-directory` for `inventag policy check`):

| Extension | Format | Written for |
|---|---|---|
| `.json` | The full result | `json` |
| `.sarif` | SARIF 2.1.0, for code scanning tools | `sarif` |
| `.xml` | JUnit XML, one test case for each policy | `junit` |
| `.md` | Markdown tables, at most 50 rows for each policy | `markdown` |

A scan writes `.json` unless `--policy-format` says otherwise.
`inventag policy check` prints text to the screen and writes no file unless
`--format` names one; it writes nothing when it exits with code 1 or 2. On Linux and macOS the files are readable and writable by their owner only (mode 0600), from a scan and from `inventag policy check`; a folder InvenTag creates for them is mode 0700, and an existing folder keeps its mode.

The JSON file has these top-level keys: `schema_version`, `inventag_version`,
`now`, `snapshot`, `baseline`, `policies`, `summary`, `findings`,
`not_evaluated_units`, `not_evaluated_policies` and `unused_waivers`. Keys are
sorted and the file ends with a newline. It holds no host name, user name,
absolute path or clock time, so the same snapshot and policies give the same
bytes. A JSON Schema for it is packaged with InvenTag
(`inventag/policy/outputs/schemas/policy-findings-1.json`); its `$id` is the
name `urn:inventag:schema:policy-findings:1`, not a web address.

- `findings` lists each row whose result is `fail`, `waived` or
  `not_evaluated`. A `pass` and a row that a policy does not select
  (`out_of_scope`) are counted in `summary` and in each policy's `counts`, not
  listed.
- A `not_evaluated` finding has a `reason`: `identity_only`, `field_missing`,
  `tags_not_read`, `listing_not_read`, `not_comparable`, `not_convertible` or
  `value_too_long`. A gap in the data is never a pass.
- `not_evaluated_units` lists the listings of the scan that were not read and
  that a policy would have needed. `unused_waivers` lists waivers that matched
  nothing, with `why`: `no match`, `expired`, `unknown policy` or
  `superseded`.
- `summary.exit_code` is 0, 7 or 8.
- A value of a resource field is shown only with `--show-values`, and a masked
  value stays masked. SARIF and JUnit never carry a value.

In the text and Markdown forms, the last line says what the exit code stands
for, for example `Exit code 7: at least one finding failed at severity high or
higher.` With no threshold it reads `Exit code 0: findings are reported; no
threshold was set.` See [Exit codes](./cli.md#exit-codes).

Not verified: how GitHub code scanning shows the SARIF file, or how GitLab
shows the JUnit file. The tests compare the files with golden files, and the
SARIF file with a short schema that is packaged with InvenTag, not with the
full SARIF schema.

## Word report

**Without a template:** a title, an executive summary, a service table, and
up to 50 resources per service in six columns: Name, Id, Type, Region, Tags and Service. If no resource of the service has a name, the columns are Id, Type, Region, Tags, Service and Source Account Name.

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
    "checked": 23,
    "compliant": 1,
    "non_compliant": 22,
    "out_of_scope": 14,
    "percent_compliant": 4.3,
    "missing_by_key": {
      "CostCenter": 20,
      "Owner": 17,
      "Project": 21,
      "Environment": 17
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
  "total_calls": 93,
  "allowed_calls": 93,
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
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
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

With `--s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/`, each run
puts its files under a folder named after the run:

<!-- BEGIN EXAMPLE OUTPUT: s3-keys -->

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: s3-keys -->

## Terminal output

Without `--verbose`, a run prints warnings, errors and the files written. With
a template, each file is printed as `Wrote <path>`, followed by a one-line tag
policy summary when a policy is active. Without a template, the default report is printed as `Data exported to <path>`. With `--policy`, the policy summary is always printed; the line `Policy findings: <path>` is logged at INFO level and shows only with `--verbose`. With no option at all, `inventag` prints the help page and exits with code 2.

## Exit codes

See [Command-line reference](./cli.md#exit-codes).
