---
title: Choose what to scan and what to produce
description: Pick the accounts, regions and output files for an InvenTag run, keep logs, and choose where the reports are written.
sidebar_position: 1
slug: /user-guides/cli-user-guide
---

# Choose what to scan and what to produce

**Who this is for:** you have run InvenTag once and want to control what it
scans and what it writes.

**What you can do after reading:** choose accounts, regions, output files and
logging for a run. For every flag, see the [CLI reference](../reference/cli.md).

On Windows, use `inventag.bat` wherever this page says `./inventag.sh`.

## Choose the accounts

| You want to scan... | Use |
|---|---|
| The account of your current credentials | Nothing extra |
| One other account, through a role | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly` (a full ARN, not a role name) |
| Several accounts | `--accounts-file accounts.yaml` or a config template: [Scan several accounts](./scan-multiple-accounts.md) |
| Accounts you type in when asked | `--accounts-prompt` |

## Choose the regions

```bash
./inventag.sh --account-regions us-east-1,eu-west-1 --create-excel
```

Without `--account-regions`, InvenTag asks EC2 which regions are enabled in
the account and scans all of them. That is thorough but slow. Global services
such as IAM and S3 are found whichever regions you choose.

## Choose the output files

| Flag | Writes |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | The same files, laid out by a [report template](../templates/index.md) |
| `--output-directory reports` | Writes everything to `reports/` instead of `bom_output/` |

If you give no output flag, InvenTag writes Excel only.

## Combine several settings in one file

If you always run with the same settings, put them in a
[config template](../templates/catalogue.md#config-templates) instead of
typing them:

```bash
./inventag.sh templates init single-account --output .inventag/templates/my-scan.yaml
# edit regions and outputs, then:
./inventag.sh --template my-scan
```

Flags you type still win over the template.

## See what is happening

| Flag | Shows |
|---|---|
| (none) | Warnings, errors and where the files were written |
| `--verbose` or `-v` | Each step of the run |
| `--log-file run.log` | Writes a detailed log to a file as well |
| `--debug` or `-d` | Every AWS request. **Avoid with temporary credentials**: the log contains your session token. |

## Validate configuration files without scanning

```bash
./inventag.sh --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
./inventag.sh templates validate my-scan
```

## Next steps

- [Scan several accounts](./scan-multiple-accounts.md)
- [Check tags against a policy](./check-tag-compliance.md)
- [CLI reference](../reference/cli.md)
