---
title: Command-line reference
description: Every InvenTag command and flag, what it does on the current release, and its default, checked against inventag --help.
sidebar_position: 1
---

# Command-line reference

**Who this is for:** you need the exact name or behaviour of a flag.

**What you can do after reading:** build any InvenTag command line, and know
which flags work today.

This page matches `./inventag.sh --help` on the current release. The
**Status** column says what we saw when we ran the flag offline against
mocked AWS. "Not re-tested" means we did not run it for this page. Details
are on [Feature status](../getting-started/status.md).

## Commands

```text
./inventag.sh [flags]                       run a scan and write reports
./inventag.sh templates list [--kind K] [--all]
./inventag.sh templates show NAME|PATH [--resolved]
./inventag.sh templates init NAME|PATH --output FILE|FOLDER [--name NAME] [--extend] [--force]
./inventag.sh templates validate NAME|PATH [NAME|PATH ...]
```

On Windows use `inventag.bat`, or run `python inventag_cli.py` anywhere.
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
| `--accounts-file FILE` | none | Works | Read accounts from a JSON or YAML file. See [Configuration files](./configuration-files.md#accounts-file). |
| `--accounts-prompt` | off | Not re-tested | Ask for accounts and credentials interactively. |
| `--cross-account-role ARN\|NAME` | none | Works | A full role ARN is assumed directly. A role name is combined with each account ID in `--accounts-file`. A name without `--accounts-file` stops with exit code 2. |

## Output

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--create-excel` | on if no other output flag | Works | Write `multi_account_bom_<timestamp>.xlsx`. |
| `--create-word` | off | Works | Write `multi_account_bom_<timestamp>.docx`. |
| `--create-google-docs` | off | Stops with exit code 2 | Not implemented. |
| `--output-directory DIR` | `bom_output` | Works | Folder for all output files. |
| `--per-account-reports` | off | Stops with exit code 2 | Not implemented. |

## What to scan

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--account-regions LIST` | every enabled region | Works | Comma-separated region codes, for example `us-east-1,eu-west-1`. |
| `--account-services LIST` | all | Partial | Comma-separated service names. Applied in one discovery path only. |
| `--account-tags JSON` | none | Partial | Tag filter, for example `'{"Environment":"prod"}'`. Applied in one discovery path only. |
| `--fallback-display auto\|always\|never` | `auto` | Not re-tested | Whether to show resources found only through fallback methods. `auto` shows them only for services with no other results. |
| `--hide-fallback-resources` | off | Not re-tested | Same as `--fallback-display never`. Deprecated. |

## Analysis

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--enable-network-analysis` | off | No effect on reports | No sheets are added. |
| `--enable-security-analysis` | off | No effect on reports | No sheets are added. |
| `--enable-cost-analysis` | off | Not verified | Turns on cost estimation in processing. Needs `pricing:GetProducts`. |

## Configuration files

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--tag-mappings FILE` | none | Loaded, not applied | See [Configuration files](./configuration-files.md#tag-mappings). |
| `--service-descriptions FILE` | none | Loaded, not applied | See [Configuration files](./configuration-files.md#service-descriptions). |
| `--bom-config FILE` | none | Not re-tested | Sets fields of the BOM processing configuration from a YAML or JSON file. |
| `--validate-config` | off | Works | Load and check the configuration, then exit. |
| `--validate-config-only` | off | Works | Check only the files you name, then exit. Add `--skip-credential-validation` to skip the AWS check. |

## Parallel processing

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--max-concurrent-accounts N` | `4` | Works | Accounts scanned at the same time. |
| `--account-processing-timeout SECONDS` | `1800` | Works | Time allowed per account (at least 60). |
| `--disable-parallel-processing` | off | Works | Scan one account at a time. |

## State and change tracking

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--enable-state-management` | on | Works | Save a snapshot in `<output>/state/`. |
| `--disable-state-management` | off | Works | Don't save snapshots or changelogs. |
| `--enable-delta-detection` / `--disable-delta-detection` | on | Partial | Compare snapshots. The comparison currently uses the newest snapshot twice. |
| `--generate-changelog` | on | Cannot be turned off | Changelogs are always written when state management is on. |

## Logging

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--verbose`, `-v` | off | Works | Show each step. |
| `--debug`, `-d` | off | Works | Show every AWS request. Secrets are masked. |
| `--log-file FILE` | none | Works | Also write a detailed log to this file. |
| `--disable-account-logging` | off | Not re-tested | Don't prefix log lines with the account. |

## Credentials

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--validate-credentials` | off | Works | Check every account's credentials, then exit (0 if all work, 1 if not). |
| `--credential-timeout SECONDS` | `30` | Not re-tested | Timeout for each credential check. |
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
| `--compliance-standard ...` | none | Stops with exit code 2 | Not implemented. Use a tag-policy template. |
| `--risk-threshold ...` | none | Stops with exit code 2 | Not implemented. |

<!-- BEGIN EXAMPLE OUTPUT: validate-operations -->

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: validate-operations -->

What the flags that stop with exit code 2 print:

<!-- BEGIN EXAMPLE OUTPUT: failing-flags -->

```text title="Terminal"
$ ./inventag.sh --create-google-docs
inventag: error: --create-google-docs: Google Docs/Sheets output is not implemented yet (InvenTag has no Google API integration). Use --create-excel or --create-word.
(exit code 2)

$ ./inventag.sh --per-account-reports
inventag: error: --per-account-reports: Per-account reports are not implemented yet; InvenTag writes one consolidated report. Run once per account to get separate reports.
(exit code 2)

$ ./inventag.sh --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ ./inventag.sh --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

<!-- END EXAMPLE OUTPUT: failing-flags -->

## S3 upload

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--s3-bucket BUCKET` | none | Works | Upload the reports to this bucket after the run. The run fails if an upload fails. Needs `s3:PutObject`. |
| `--s3-key-prefix PREFIX` | `bom-reports/` | Works | Folder (key prefix) in the bucket. |
| `--s3-encryption AES256\|aws:kms` | `AES256` | Works | Server-side encryption for the uploads. |
| `--s3-kms-key-id KEY` | none | Works | KMS key for `aws:kms`. |

See [Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | An error: invalid arguments, configuration or template, failed credentials, or a failed run |
| 2 | Invalid command line: unknown or badly formed options, flags that are not implemented, or a role name without `--accounts-file` |
| 3 | Reports written, but a config template with `fail_on_tag_violations: true` found tag policy violations |
