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

Give `--accounts-file` or `--accounts-prompt`, not both. A full role ARN in
`--cross-account-role` names one account, so it cannot go with either of them.
Both mistakes stop the run with exit code 2.

## Choose the regions

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

Without `--account-regions`, InvenTag asks EC2 which regions are enabled in
the account and scans all of them. That is thorough but slow. If
`ec2:DescribeRegions` fails, InvenTag asks `account:ListRegions`. If that also
fails, it logs a warning and tries every region of the partition that your
AWS SDK knows. Regions that the account has not enabled fail the access check
and are skipped. Use `--account-regions` to choose the regions yourself.

A region that fails its access check is skipped with a warning. If the check
fails in every region, because the identity lacks `ec2:DescribeRegions`,
InvenTag cannot tell which regions work and scans all of them.

### Global services

You do not need to add the home region to the list. For any region choice,
InvenTag reads the global services once for each account, from the home region
of the partition: `us-east-1` in the standard partition, `cn-north-1` in China
and `us-gov-west-1` in GovCloud. These are IAM, the S3 bucket list,
CloudFront, Route 53 and the ACM certificates that CloudFront uses. If the home
region is in your list, they are not read twice.

- `--account-services` and `--account-tags` apply to them like to any other
  resource. With `--account-services ec2`, no IAM resource is read.
- IAM, CloudFront and Route 53 resources show `global` in the region column.
  An S3 bucket shows its own region, for example `eu-west-1`.
- Their tags come from the Resource Groups Tagging API in the home region,
  where AWS keeps the tags of global resources.
- Offline tests cover `eu-west-1` alone, all regions, and a list that includes
  `us-east-1`. How real AWS answers is not tested.

### Services

InvenTag has its own read-only listing calls for 46 AWS services. Resources of
other services appear only when the Resource Groups Tagging API returns them.
See [Feature status and known limitations](../getting-started/status.md).

### Throttling and failed calls

InvenTag retries a throttled call up to 10 times in total (the AWS SDK
"standard" retry mode). If you set `AWS_RETRY_MODE` or `AWS_MAX_ATTEMPTS`,
your values are used instead. A listing that still fails is logged as a
warning for that service and region: `<service> <operation> in <region>
failed (<error>); its resources there may be incomplete.` The JSON output
records how each listing ended. A denied permission is logged once for the
service.

## Time limit and parallel accounts

InvenTag scans up to four accounts at a time. Change that with
`--max-concurrent-accounts` (at least 1), or use
`--disable-parallel-processing` to scan one account at a time.

Each account has `--account-processing-timeout` seconds (default 1800, at
least 60), counted from when that account's scan starts. Discovery stops a
little earlier, by 300 seconds or 20% of the limit, whichever is smaller, so
that tags, details and billing can still be read.

An account that runs out of time is reported as failed, and the other accounts
are kept. The resources it found before the limit stay in the report, and the
report's notes say the account is incomplete. A log line from an offline run
with `--account-processing-timeout 60` (sample data):

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

If no account finishes, InvenTag still writes the report with what it found,
logs `No account finished within its time limit`, and exits with code 1.

## Continue after a failed run

When some accounts fail, InvenTag saves the accounts that finished in
`bom_output/state/partial/`. Fix the cause, then run the same command with
`--resume`. InvenTag scans only the accounts that are missing:

```bash
inventag --accounts-file accounts.yaml --create-excel --resume
```

InvenTag reuses a saved result only if the command used the same accounts,
regions, services and filters, and the result is not older than
`--resume-max-age-hours` (default 24, at most 168). It needs state management,
so `--resume` with `--disable-state-management` stops with exit code 2. The log
says `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)`,
and the report's notes list each reused account with its scan time. Without
`--resume`, a warning says that saved results exist and are scanned again.
InvenTag deletes the saved results after a run in which every account
finishes.

## Choose the output files

| Flag | Writes |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | The same files, laid out by a [report template](../templates/index.md) |
| `--output-directory reports` | Writes everything to `reports/` instead of `bom_output/` |

If you give no output flag, InvenTag writes Excel only. If the scan finds
no resources, or your filters remove them all, InvenTag writes no file, logs
`No resources to report (none found, or the filters removed all of them).`
and still exits with code 0. With `--template`, it writes a report that lists
no resources. Add `--s3-bucket` to also upload the files: see
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

Exit code 0 means the files are valid. With `--skip-credential-validation`,
the first command makes no AWS call. A broken accounts file looks like this
(sample data):

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

## Exit codes

InvenTag exits with code 0 even when an account failed or nothing was found.
Two opt-in flags change that. With code 5 the reports are still written.

| Flag | Exit code | When |
|---|---|---|
| `--fail-on-account-error` | 5 | An account could not be scanned, or only partly |
| `--fail-if-empty` | 6 | No resources to report |

The full list is in [Run InvenTag in CI/CD](./run-in-ci.md#exit-codes).

## Next steps

- [Scan several accounts](./scan-multiple-accounts.md)
- [Check tags against a policy](./check-tag-compliance.md)
- [CLI reference](../reference/cli.md)
