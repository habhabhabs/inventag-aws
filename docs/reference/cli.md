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
| `--cross-account-role ARN` | none | Works with a full role ARN | Assume this role and scan its account. The help text says "role name", but a bare name fails. |

## Output

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--create-excel` | on if no other output flag | Works | Write `multi_account_bom_<timestamp>.xlsx`. |
| `--create-word` | off | Works | Write `multi_account_bom_<timestamp>.docx`. |
| `--create-google-docs` | off | Not implemented | No output is produced. |
| `--output-directory DIR` | `bom_output` | Works | Folder for all output files. |
| `--per-account-reports` | off | Not implemented | Stored but not used. |

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
| `--debug`, `-d` | off | Works, with a risk | Show every AWS request. The log contains temporary session tokens. |
| `--log-file FILE` | none | Works | Also write a detailed log to this file. |
| `--disable-account-logging` | off | Not re-tested | Don't prefix log lines with the account. |

## Credentials

| Flag | Default | Status | What it does |
|---|---|---|---|
| `--validate-credentials` | off | Broken | Reports every account as invalid. Use `aws sts get-caller-identity`. |
| `--credential-timeout SECONDS` | `30` | Not re-tested | Timeout for credential checks. |
| `--skip-credential-validation` | off | Works | Skip the credential check at the start of a run. |

## Production safety

All of these are accepted and currently have no effect:
`--enable-production-safety`, `--disable-production-safety`,
`--enforce-read-only`, `--security-validation`,
`--compliance-standard general|soc2|pci|hipaa|gdpr`,
`--risk-threshold LOW|MEDIUM|HIGH|CRITICAL`, `--audit-output FILE`,
`--validate-operations SERVICE:OPERATION ...`.

`--compliance-standard` never makes a report compliant with anything. Use a
read-only IAM policy for safety: [Set up read-only access](../guides/read-only-access.md).

## S3 upload

`--s3-bucket`, `--s3-key-prefix`, `--s3-encryption AES256|aws:kms` and
`--s3-kms-key-id` are accepted, but nothing is uploaded on the current
release. Upload `bom_output/` yourself, for example:

```bash
aws s3 cp bom_output/ s3://my-reports-bucket/inventag/ --recursive --sse AES256
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | An error: invalid arguments, configuration or template, failed credentials, or a failed run |
| 2 | Invalid command-line syntax (from the argument parser) |
| 3 | Reports written, but a config template with `fail_on_tag_violations: true` found tag policy violations |
