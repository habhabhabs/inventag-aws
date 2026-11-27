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

Not verified against Windows or macOS: the `inventag` command works the same as on Linux.

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

Not verified against real AWS: the error AWS returns for a region that is not enabled.

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

  Not verified against real AWS: AWS keeps the tags of global resources in the home region.
- Offline tests cover `eu-west-1` alone, all regions, and a list that includes
  `us-east-1`. How real AWS answers is not tested.

### Services

InvenTag has its own read-only listing calls for 46 AWS services. Resources of
other services appear only when the Resource Groups Tagging API returns them.
See [Feature status](../getting-started/status.md).

### Throttling and failed calls

InvenTag retries a throttled call up to 10 times in total (the AWS SDK
"standard" retry mode). If you set `AWS_RETRY_MODE` or `AWS_MAX_ATTEMPTS`,
your values are used instead. A listing that still fails is logged as a
warning for that service and region: `<service> <operation> in <region>
failed (<error>); its resources there may be incomplete.` The state snapshot
counts how the listings of each account ended, in
`metadata.tags.coverage_summary`. A denied permission is logged once for the
service.

Not verified against real AWS: how AWS throttles calls and how the SDK retries cope with it.

## Time limit and parallel accounts

InvenTag scans up to four accounts at a time. Change that with
`--max-concurrent-accounts` (at least 1), or use
`--disable-parallel-processing` to scan one account at a time. For the
requests inside the accounts, see [Concurrency](#concurrency).

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

## Concurrency

InvenTag sends AWS requests from several threads at the same time. Three
settings control how many:

| Setting | Default | What it limits |
|---|---|---|
| `--concurrency N` | 64 | The most AWS requests in flight at once, for the whole run. |
| `--max-concurrent-accounts N` | 4 | The accounts that are scanned at the same time. |
| `--disable-parallel-processing` | off | Scans one account after the other. It does not change the threads inside an account. |

`--concurrency` takes a whole number from 1 to 256. A value outside this
range, or a value that is not a whole number, stops the run with exit code 2
before anything is scanned. In a config template, the field is
`spec.concurrency`. A flag that you type wins over the template.

```bash title="Terminal"
inventag --concurrency 16 --create-excel
```

With `--concurrency 1`, InvenTag sends one request at a time in the whole run.

Two more limits are fixed. You cannot change them:

- At most 16 requests of one account are in flight at the same time.
- At most 4 requests are in flight for one service in one region of one
  account.

Each account also has 8 threads for the detail calls. A detail call reads one
detail of one resource, for example the S3 bucket location or the Lambda
function configuration. InvenTag makes the same calls as with
`--concurrency 1`. Only the order in time changes.

A request that waits for a free place counts against
`--account-processing-timeout`.

### When AWS throttles

When AWS answers a request with a throttling error, InvenTag lowers the limit
for that service and region of that account. It halves the limit, but never
below 1. It starts no new request for that service and region for 0.5 to 1
second. After 10 answers without a throttling error, it raises the limit by 1,
up to 4. The AWS SDK still retries the request in standard mode, as described
under [Throttling and failed calls](#throttling-and-failed-calls). InvenTag has
no retry loop of its own.

Not verified against real AWS: how the request limit and the pause behave
under real AWS rate limits.

### What does not depend on timing

For the same AWS answers, a run with `--concurrency 1` and a run with
`--concurrency 64` write the same files and make the same calls. Rows and
analysis sheets follow the order of your accounts, whatever order the accounts
finish in. The order of log lines and the time stamps can differ from run to
run.

### Stop a run

Ctrl-C and SIGTERM stop every waiting request at once, and no new request
starts. The message and the exit status are the same as in v1.3.1. See
[Troubleshooting](./troubleshooting.md#the-run-is-stopped-with-ctrl-c-or-sigterm).

### Speed

More requests at the same time can make a run shorter. Not verified against
real AWS: any speed-up. The benchmark script `scripts/benchmark_scan.py` runs
a simulated AWS with a fixed delay per request. A result from it is not a
promise for a real account.

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
and the report's notes list each reused account with its scan time. The
console names a reused account once, in that log line. Without
`--resume`, a warning says that saved results exist and are scanned again.
InvenTag deletes the saved results after a run in which every account
finishes.
An account whose session expired part-way is not saved, so `--resume` scans it
again.

## Choose the output files

| Flag | Writes |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | The same files, laid out by a [report template](../templates/index.md) |
| `--output-directory reports` | Writes everything to `reports/` instead of `bom_output/` |

If you give no output flag, InvenTag writes Excel only and logs one line,
`No output formats specified. Defaulting to Excel format.` If the scan finds
no resources, or your filters remove them all, InvenTag writes no file, logs
`No resources to report (none found, or the filters removed all of them).`
With `--account-services` or `--account-tags`, the message names the filter,
for example `No resources to report: none found with --account-services EC2
(from the command line or the accounts file). No report file was written; run
without that filter to see every resource.`
and still exits with code 0. With `--template`, it writes a report that lists
no resources. Add `--s3-bucket` to also upload the files: see
[Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md). With
`--s3-bucket` and no resources, the run says `Nothing to upload to
s3://<bucket>/<prefix>/: the run wrote no report file because there are no
resources to report.` and exits with code 1.

Sample output of a run with `--template standard-bom --create-excel
--create-word --account-regions us-east-1` (offline, sample data):

<!-- BEGIN EXAMPLE OUTPUT: standard-console -->

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Cost Explorer: up to 1 request(s) in this run (billing validation: 1; cost trend: 0). AWS charges for each.
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
| `-vv` | Debug output, the same as `--debug` |
| `--log-file run.log` | Writes a detailed log to a file as well |
| `--debug` or `-d` | Every AWS request. Secrets are masked, but treat the log as sensitive. The same as `-vv`. |
| `--audit-output audit.json` | A JSON list of every AWS operation the run called |

For CI/CD runs, use `-vv`. Debug output holds account IDs, ARNs, IP addresses, tag values and the AWS SDK's full request and response bodies. Secrets are masked; the known gaps are listed under [Feature status](../getting-started/status.md#security-notes). In a public repository the job log is public, so use `-v` there. Elsewhere, restrict who can read the job log, and do not upload the debug log as an artifact.

## Validate configuration files without scanning

```bash title="Terminal"
inventag --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
inventag templates validate my-scan
```

Exit code 0 means the files are valid. With `--skip-credential-validation`,
the first command makes no AWS call. A broken accounts file looks like this
(sample data):

<!-- BEGIN EXAMPLE OUTPUT: error-bad-accounts -->

```text title="Output"
inventag - WARNING -    - Account 1: no credentials given; InvenTag will assume the --cross-account-role role (default InvenTagCrossAccountRole) in this account, or use the default credentials only if they belong to this account
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="Output"
1
```

<!-- END EXAMPLE OUTPUT: error-bad-accounts -->

## Exit codes

InvenTag exits with code 0 even when an account failed or nothing was found.
Two opt-in flags change that. With code 5 the reports are still written.

| Flag | Exit code | When |
|---|---|---|
| `--fail-on-account-error` | 5 | An account could not be scanned or ran out of time |
| `--fail-if-empty` | 6 | No resources to report |

With code 6, a run with `--template` writes a report that lists no resources,
and a run without it writes no file.

The full list is in [Run InvenTag in CI/CD](./run-in-ci.md#exit-codes).

## Next steps

- [Scan several accounts](./scan-multiple-accounts.md)
- [Check tags against a policy](./check-tag-compliance.md)
- [CLI reference](../reference/cli.md)
