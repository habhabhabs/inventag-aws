---
title: Command-line reference
description: Every InvenTag command and flag, what it does on the current release, and its default, checked against inventag --help.
sidebar_position: 1
---

# Command-line reference

**Who this is for:** you need the exact name or behaviour of a flag.

**What you can do after reading:** build any InvenTag command line, and know
which flags work today.

This page matches `inventag --help` of the release that this version of the
docs describes. Run `inventag --help` to see the flags of the release you have
installed. The **Status** column says what an offline test against mocked AWS shows.
"Not tested" means no test covers what the row says yet. "Mocked Google only"
means the tests use mocked Google clients. Details are on
[Feature status](../getting-started/status.md).

## Commands

```text
inventag [flags]                       run a scan and write reports
inventag --version                     print the version and exit
inventag templates list [--kind K] [--all]
inventag templates show NAME|PATH [--resolved]
inventag templates init NAME|PATH --output FILE|FOLDER [--name NAME] [--extend] [--force]
inventag templates validate NAME|PATH [NAME|PATH ...]
```

The `inventag` command works the same on Linux, macOS and Windows.

Not verified against Windows or macOS: the `inventag` command works the same as on Linux.

`templates` must be the first word after the program name.

## Templates

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--template NAME\|PATH` | none | Works | Use a template. Repeat for one report, one tag-policy and one config template. See [Templates](../templates/index.md). |

### `templates` subcommands

| Command | What it does |
|---|---|
| `templates list` | Lists templates with kind, source and description, and the folders searched. `--kind report\|tag-policy\|config` filters; `--all` also shows templates hidden by one with the same name. |
| `templates show NAME` | Prints the file. `--resolved` prints the result after `extends` and defaults. |
| `templates init NAME --output PATH` | Copies a template into your project. `--extend` writes a short file that inherits; `--name` sets the name; `--force` overwrites. |
| `templates validate NAME\|PATH ...` | Checks files and the templates they refer to. Exit code 0 if all are valid, 1 otherwise. |

## Accounts

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--accounts-file FILE` | none | Works | Read accounts from a JSON or YAML file. See [Configuration files](./configuration-files.md#accounts-file). Give `--accounts-file` or `--accounts-prompt`, not both (exit code 2). |
| `--accounts-prompt` | off | Works | Ask for accounts and credentials interactively. |
| `--cross-account-role ARN\|NAME` | none | Works | A full role ARN is assumed directly; with `--accounts-file` or `--accounts-prompt` it stops with exit code 2. A role name is combined with each account ID in `--accounts-file`. A name without `--accounts-file` stops with exit code 2. |

## Output

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--create-excel` | on if no other output flag | Works | Write `multi_account_bom_<timestamp>.xlsx`. |
| `--create-word` | off | Works | Write `multi_account_bom_<timestamp>.docx`. |
| `--create-google-docs` | off | Mocked Google only | Create the Word report as a Google Doc. Needs the Google add-on (`pip install "inventag-aws[google]"`). See [Google Sheets and Docs](../guides/google-sheets-and-docs.md). |
| `--create-google-sheets` | off | Mocked Google only | Create the Excel report as a Google Sheets spreadsheet. |
| `--google-credentials FILE` | none | Mocked Google only | Service account key file. Without it, Application Default Credentials are used. |
| `--google-oauth-client FILE` | none | Mocked Google only | OAuth client file; you sign in in the browser. |
| `--google-folder-id ID` | none | Mocked Google only | Drive folder for the files. |
| `--google-share-with EMAIL` | none | Mocked Google only | Share with this address. Repeat for more. |
| `--google-share-role ROLE` | `reader` | Mocked Google only | `reader`, `commenter` or `writer`. |
| `--google-share-anyone` | off | Mocked Google only | Anyone with the link can read. Files are private without it. |
| `--google-title TITLE` | dated name | Mocked Google only | Title of the Google files. |
| `--output-directory DIR` | `bom_output` | Works | Folder for all output files. |
| `--per-account-reports` | off | Works | One `<account-id>_bom_<timestamp>` file per account instead of one consolidated report. |

Not verified against real Google: what the Google flags in this table create, share and print.

## What to scan

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--account-regions LIST` | every enabled region | Works | Comma-separated region codes, for example `us-east-1,eu-west-1`. IAM, the S3 bucket list, CloudFront and Route 53 are always read once from `us-east-1`, so you need not list it. |
| `--account-services LIST` | all | Works | Comma-separated service names that are kept in the report, matched against the Service column, for example `EC2,S3`. |
| `--account-tags JSON` | none | Works | Tag filter, for example `'{"Environment":"prod"}'`. Only resources with those tags are kept. |
| `--fallback-display auto\|always\|never` | `auto` | Works | Whether to show resources found only through the Resource Groups Tagging API. `auto` shows them only for services with no results from their own discovery code. |
| `--hide-fallback-resources` | off | Works | Same as `--fallback-display never`. Deprecated. |

## Analysis

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--enable-network-analysis` | off | Works | Adds a `Network Analysis` sheet to the Excel report when VPCs are found. Adds nothing with `--template`. See [Network and security analysis](../guides/network-and-security-analysis.md). |
| `--enable-security-analysis` | off | Works | Adds a `Security Analysis` sheet to the Excel report when security groups are found. Adds nothing with `--template`. |
| `--enable-cost-analysis` | off | Works | Adds a Cost Analysis sheet (and the four `forgotten_analysis.*` columns) to the default workbook. Makes extra Cost Explorer, Pricing and CloudWatch calls, also with `--no-billing-validation`. Needs `pricing:GetProducts` and `cloudwatch:GetMetricStatistics`. The costs are estimates from the AWS Pricing API, not your invoice. |
| `--billing-validation`, `--no-billing-validation` | on | Works | Use Cost Explorer during discovery to find services with spend. AWS charges for each Cost Explorer request. See [Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/). `--no-billing-validation` stops those calls. |

Not verified against real AWS: `--enable-cost-analysis` needs only these two extra permissions, and the estimates match AWS prices.

## Configuration files

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--tag-mappings FILE` | none | Works | Adds one named column per mapping. See [Configuration files](./configuration-files.md#tag-mappings). |
| `--service-descriptions FILE` | none | Works | Adds a `service_description` column. Your entry replaces the built-in description. See [Configuration files](./configuration-files.md#service-descriptions). |
| `--bom-config FILE` | none | Works | Sets fields of the BOM processing configuration from a YAML or JSON file. Other keys are ignored with a warning that names them. A value of the wrong type stops with exit code 1 and names the key. |
| `--validate-config` | off | Works | Load and check the configuration, then exit. |
| `--validate-config-only` | off | Works | Check `--accounts-file`, `--tag-mappings` and `--service-descriptions`, then exit. It does not read `--bom-config`. It makes no AWS call. |

## Report layout files

These flags change the layout of the default Excel and Word reports with a
YAML or JSON file. See [Layout files for one report](../templates/layout-flags.md).

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--word-template PATH` | none | Works | Layout file for the Word report. Needs `--create-word`; without it the run stops with exit code 2. |
| `--excel-template PATH` | none | Works | Layout file for the Excel report. With `--create-word` alone, the run stops with exit code 2. |
| `--print-default-template word\|excel` | none | Works | Print the default layout file for that format, then exit with code 0. |
| `--validate-templates` | off | Works | Check the files given with `--word-template` and `--excel-template`, then exit. It makes no AWS call. Without one of those flags: exit code 2. |

## Parallel processing

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--max-concurrent-accounts N` | `4` | Works | Accounts scanned at the same time (at least 1). |
| `--account-processing-timeout SECONDS` | `1800` | Works | Time allowed per account, counted from when its scan starts (at least 60). An account that runs out of time counts as failed; the resources it found stay in the report. |
| `--disable-parallel-processing` | off | Works | Scan one account at a time. |
| `--resume` | off | Works | Reuse the saved results of accounts that finished in an earlier run of the same command that did not complete (same accounts, regions, services and filters), and scan only the others. With `--disable-state-management`: exit code 2. |
| `--resume-max-age-hours HOURS` | `24` | Works | With `--resume`, reuse saved results only up to this age (at most 168). |

## State and change tracking

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--enable-state-management` | on | Works | Save a snapshot in `<output>/state/`. |
| `--disable-state-management` | off | Works | Don't save snapshots or changelogs. |
| `--enable-delta-detection` / `--disable-delta-detection` | on | Works | Compare the new snapshot with the previous one. `--disable-delta-detection` writes no change report. |
| `--generate-changelog`, `--no-generate-changelog` | on | Works | Write `changelog_<timestamp>.md` from the second run on. `--no-generate-changelog` stops it. |
| `--state-retention-days N` | `30` | Works | Delete state snapshots older than N days when a run saves a new one. `0` or `none` keeps snapshots of any age. |
| `--state-max-snapshots N` | `100` | Works | Keep only the newest N state snapshots. `0` or `none` keeps every snapshot. |

## Opt-in exit codes

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--fail-on-account-error` | off | Works | Exit with code 5 when an account could not be scanned or ran out of time. The reports are still written. |
| `--fail-if-empty` | off | Works | Exit with code 6 when no resources were found or the filters removed all of them. |

If more than one applies, 5 comes first, then 6, then 3, then 4. Reports are
written for codes 3, 4 and 5. With code 6, a run with `--template` writes a
report that lists no resources, and a run without it writes no file.

## Logging

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--verbose`, `-v` | off | Works | Show each step. |
| `--debug`, `-d` | off | Works | Show the AWS requests. Secrets are masked. |
| `--log-file FILE` | none | Works | Also write a detailed log to this file. |
| `--disable-account-logging` | off | Works | Don't prefix log lines with the account. |

## Credentials

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--validate-credentials` | off | Works | Check every account's credentials, then exit (0 if all work, 1 if not). |
| `--credential-timeout SECONDS` | `30` | Works | Timeout for sign-in and credential checks, including AssumeRole. |
| `--skip-credential-validation` | off | Works | Skip the credential check at the start of a run. |

## Read-only guard and audit

The read-only guard is always on. It blocks every AWS call that is not a
read, and reads that return secrets or data.

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--audit-output FILE` | none | Works | Write a JSON list of every AWS operation the run called, allowed and blocked. |
| `--validate-operations SERVICE:OPERATION ...` | none | Works | Check operations against the guard, then exit (0 if all allowed, 1 if not). |
| `--enforce-read-only`, `--security-validation`, `--enable-production-safety` | on | No effect | Kept so old commands still run. The guard is always on. |
| `--disable-production-safety` | off | Stops with exit code 2 | The guard cannot be turned off. |
| `--compliance-standard ...` | none | Stops with exit code 2 | Not implemented: a standard cannot be checked from an inventory. Use a tag-policy template. |
| `--risk-threshold LEVEL` | none | Works | With `--enable-security-analysis`: exit code 4 if a security group rule is at or above `LOW`, `MEDIUM`, `HIGH` or `CRITICAL`. Without `--enable-security-analysis`: exit code 2. |

<!-- BEGIN EXAMPLE OUTPUT: validate-operations -->

```text title="Output"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
```

```bash title="Terminal"
echo $?
```

```text title="Output"
1
```

<!-- END EXAMPLE OUTPUT: validate-operations -->

What flags that stop with exit code 2 print (the first sample is from a machine without the Google libraries):

<!-- BEGIN EXAMPLE OUTPUT: failing-flags -->

```bash title="Terminal"
inventag --create-google-docs
```

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)
```

```bash title="Terminal"
inventag --risk-threshold HIGH
```

```text title="Output"
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)
```

```bash title="Terminal"
inventag --compliance-standard soc2
```

```text title="Output"
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="Output"
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

<!-- END EXAMPLE OUTPUT: failing-flags -->

## S3 upload

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--s3-bucket BUCKET` | none | Works | Upload every file the run wrote (Excel, Word and tag-compliance JSON) to this bucket. The run exits with code 1 if an upload fails. Needs `s3:PutObject`. |
| `--s3-key-prefix PREFIX` | `bom-reports/` | Works | Folder (key prefix) in the bucket. Files go under `<prefix><UTC timestamp>/`. |
| `--s3-encryption AES256\|aws:kms` | `AES256` | Works | Server-side encryption for the uploads. |
| `--s3-kms-key-id KEY` | none | Works | KMS key for `aws:kms`. Without it, S3 uses the AWS managed key `aws/s3`. Needs `--s3-encryption aws:kms`, else exit code 2. |

Not verified against real AWS: the upload needs only `s3:PutObject` (and `kms:GenerateDataKey` with `aws:kms`).

Not verified against AWS: that S3 uses the AWS managed key `aws/s3` when `aws:kms` has no key ID.

See [Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. Also 0 when some accounts failed but others worked, and when no resources were found, unless you pass `--fail-on-account-error` or `--fail-if-empty`. See [Feature status](../getting-started/status.md#when-a-run-goes-wrong). |
| 1 | An error: invalid arguments, configuration or template, a number out of range (for example `--max-concurrent-accounts 0`), failed credentials, every account failed (could not be scanned or ran out of time), a failed S3 upload, or a report format that could not be written |
| 2 | Invalid command line: unknown, badly formed or conflicting options, flags that are not implemented, bad Google options, a layout file flag without the report it needs, or a role name without `--accounts-file` |
| 3 | Reports written, but a config template with `fail_on_tag_violations: true` found tag policy violations |
| 4 | Reports written, but `--risk-threshold` found a security group rule at or above that level |
| 5 | Reports written, but an account could not be scanned or ran out of time, and you passed `--fail-on-account-error` |
| 6 | No resources to report, and you passed `--fail-if-empty` |
