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

The `inventag` command works the same on Linux, macOS and Windows.

## Choose the accounts

| You want to scan... | Use |
|---|---|
| The account of your current credentials | Nothing extra |
| One other account, through a role | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly` (a full role ARN) |
| Several accounts | `--accounts-file accounts.yaml` or a config template: [Scan several accounts](./scan-multiple-accounts.md) |
| Several accounts, same role name in each | `--accounts-file accounts.yaml --cross-account-role InvenTagReadOnly` |
| Accounts you type in when asked | `--accounts-prompt` |

## Choose the regions

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

Without `--account-regions`, InvenTag asks EC2 which regions are enabled in
the account and scans all of them. That is thorough but slow. If that lookup
fails, InvenTag logs a warning and scans only `us-east-1`, `us-west-2`,
`eu-west-1` and `ap-southeast-1`.

A region that fails its access check is skipped with a warning.

### Global services

You do not need to add `us-east-1` to the list. For any region choice,
InvenTag reads the global services once for each account, from `us-east-1`:
IAM, the S3 bucket list, CloudFront, Route 53 and the ACM certificates that
CloudFront uses. If `us-east-1` is in your list, they are not read twice.

- `--account-services` and `--account-tags` apply to them like to any other
  resource. With `--account-services ec2`, no IAM resource is read.
- IAM, CloudFront and Route 53 resources show `global` in the region column.
  An S3 bucket shows its own region, for example `eu-west-1`.
- Their tags come from the Resource Groups Tagging API in `us-east-1`, where
  AWS keeps the tags of global resources.
- Offline tests cover `eu-west-1` alone, all regions, and a list that includes
  `us-east-1`. How real AWS answers is not tested.

## Choose the output files

| Flag | Writes |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | The same files, laid out by a [report template](../templates/index.md) |
| `--output-directory reports` | Writes everything to `reports/` instead of `bom_output/` |

If you give no output flag, InvenTag writes Excel only. If the scan finds
no resources, or your filters remove them all, InvenTag writes no file and
still exits with code 0. Add `--s3-bucket` to also upload the files: see
[Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md).

Sample output of a run with `--template standard-bom --create-excel
--create-word --account-regions us-east-1` (offline, sample data):

<!-- BEGIN EXAMPLE OUTPUT: standard-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: standard-console -->

## Combine several settings in one file

If you always run with the same settings, put them in a
[config template](../templates/catalogue.md#config-templates) instead of
typing them:

```bash
inventag templates init single-account --output .inventag/templates/my-scan.yaml
# edit regions and outputs, then:
inventag --template my-scan
```

Flags you type still win over the template.

## See what is happening

| Flag | Shows |
|---|---|
| (none) | Warnings, errors and where the files were written. AWS permission errors for single calls are not shown. |
| `--verbose` or `-v` | Each step of the run |
| `--log-file run.log` | Writes a detailed log to a file as well |
| `--debug` or `-d` | Every AWS request. Secrets are masked, but treat the log as sensitive. |
| `--audit-output audit.json` | A JSON list of every AWS operation the run called |

## Validate configuration files without scanning

```bash title="Terminal"
inventag --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
inventag templates validate my-scan
```

Exit code 0 means the files are valid. The first command still makes one
`ec2:DescribeRegions` call to list regions; if it fails, it logs a warning and
carries on. A broken accounts file looks like this (sample data):

<!-- BEGIN EXAMPLE OUTPUT: error-bad-accounts -->

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: error-bad-accounts -->

## Next steps

- [Scan several accounts](./scan-multiple-accounts.md)
- [Check tags against a policy](./check-tag-compliance.md)
- [CLI reference](../reference/cli.md)
