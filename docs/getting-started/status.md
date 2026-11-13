---
title: Feature status and known limitations
description: Which InvenTag features work in v5.0.0, which are partial, which flags stop with an error, and the specific limits, costs and risks to know before you rely on it.
sidebar_position: 5
---

# Feature status and known limitations

**Who this is for:** anyone about to rely on InvenTag for real work.

**What you will know after reading:** which features work, where they stop
short, which flags stop with an error, and what to do about each limit.

This page is deliberately blunt. This page describes InvenTag v5.0.0. We
checked each item by running the code offline against mocked AWS (moto), or by
reading the code path. **No test has run against a real AWS account.** Where a
point below depends on how real AWS behaves, the page says so. If you fix or
change one of these, update this page in the same pull request.

## Works

| Feature | How to use it |
|---|---|
| Find resources in one or more accounts | Your current credentials, `--accounts-file`, `--accounts-prompt` or `--cross-account-role` |
| Excel report | `--create-excel` writes `bom_output/multi_account_bom_<timestamp>.xlsx` |
| Word report | `--create-word` writes `bom_output/multi_account_bom_<timestamp>.docx` |
| Same sheet and row order on every run | Sheets are sorted by service name, and rows by type, name and ID |
| Report layouts and tag columns | `--template` with a [report template](../templates/index.md) |
| Tag-policy checks | `--template` with a tag-policy template: adds a Tag Compliance sheet, a Word section and a JSON file |
| Fail a CI job on tag problems | A config template with `fail_on_tag_violations: true` (exit code 3) |
| Tag columns from a file | `--tag-mappings`: one named column per mapping, with a default value |
| Filters | `--account-regions`, `--account-services` and `--account-tags` apply to every discovery path |
| Network and security sheets | `--enable-network-analysis` and `--enable-security-analysis` add Excel sheets, in the default layout or with `--excel-template`. With `--template` they add nothing. |
| Change report between runs | `changelog_<timestamp>.md` compares the newest snapshot with the one before it |
| Read-only guard | Always on. Every AWS call that is not a read is blocked before it is sent. |
| Audit of AWS calls | `--audit-output audit.json` lists every AWS operation the run called |
| Check operations against the guard | `--validate-operations ec2:DescribeInstances s3:PutObject` |
| Upload reports to S3 | `--s3-bucket` (server-side encrypted; the run fails if an upload fails) |
| Credential check | `--validate-credentials` |
| Snapshots of each run | Saved in `bom_output/state/` |
| Private output files | Reports, snapshots and logs are created readable by your user only |

## Partly working

| Feature | What actually happens |
|---|---|
| `--service-descriptions` | Custom descriptions work for services InvenTag has no built-in description for. For S3, EC2, RDS, Lambda and VPC resources, a built-in description wins unless your entry also names a `template`. See [Configuration files](../reference/configuration-files.md#service-descriptions). |
| `--enable-cost-analysis` | Adds four `forgotten_analysis.*` columns to the default workbook. It makes many extra Cost Explorer, Pricing and CloudWatch calls. It adds no cost sheet. |
| `--bom-config` | Applies only keys that are fields of the BOM processing configuration. Other keys are ignored without a message. |
| `--validate-config-only` | Checks the files, but still makes one `ec2:DescribeRegions` call to list regions. If that fails, it logs a warning and carries on. |
| `--accounts-prompt`, `--credential-timeout`, `--disable-account-logging` | Accepted. We did not re-test them for v5.0.0. |

## Accepted but with no effect

| Flag | What actually happens |
|---|---|
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Kept so old commands still run. The read-only guard is always on. |

## Stop with an error

These flags used to be accepted and silently ignored. They now stop the run
with exit code 2 and say why:

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

`--risk-threshold` also stops with exit code 2.

## What InvenTag finds, and what it does not

- **Services with their own discovery code (24):** VPC (VPCs, subnets,
  security groups, internet and NAT gateways, route tables, network ACLs,
  Elastic IP addresses), EC2 (instances, volumes, snapshots, key pairs), S3,
  RDS, Lambda, ELB, ELBv2, IAM, CloudFront, Route 53, KMS, CloudWatch, ECS,
  EKS, SNS, SQS, DynamoDB, API Gateway, Glue, WorkMail, CloudFormation, ACM,
  CloudTrail and EventBridge.
- **Everything else** can appear only if the Resource Groups Tagging API
  returns it. That API lists resources that have, or once had, tags, so
  untagged resources of any other service are missing. With
  `--fallback-display auto` (the default), such resources are shown only for
  services that have no results from their own discovery code. Use
  `--fallback-display always` to show all of them.
- **Not collected:** secrets, parameters, object contents or any other data.
  The read-only guard blocks those calls.
- **Global services need `us-east-1`.** S3, IAM, CloudFront and Route 53 are
  listed only when `us-east-1` is one of the regions scanned. With
  `--account-regions eu-west-1` alone, IAM resources do not appear. Always
  include `us-east-1` in the list.
- **Regions.** Without `--account-regions`, InvenTag asks EC2 for the regions
  enabled in the account. If that call fails, it logs a warning and scans only
  `us-east-1`, `us-west-2`, `eu-west-1` and `ap-southeast-1`. A region that
  fails its access check is skipped with a warning, and the run still succeeds.

## Tags and ARNs

InvenTag builds an ARN itself for resources whose list call does not return
one, and it matches Resource Groups Tagging API tags to resources by ARN.
For some services the built ARN is not the real ARN, so those tags are not
matched. We saw this offline for:

| Service | ARN column shows | Real AWS ARN form |
|---|---|---|
| Lambda | `...:function/<name>` | `...:function:<name>` |
| RDS DB instance | `...:dbinstance/<id>` | `...:db:<id>` |
| DynamoDB | the table name | `...:table/<name>` |
| SQS | the queue URL | `arn:aws:sqs:<region>:<account>:<name>` |
| SNS | `...:topic/arn:aws:sns:...` | `arn:aws:sns:<region>:<account>:<name>` |
| VPC, subnets, security groups, route tables, network ACLs | `arn:aws:vpc:...` (not an AWS service prefix) | `arn:aws:ec2:...` |
| EC2 snapshot | includes the account ID | has no account ID |

S3 buckets, EC2 instances and volumes, ECS clusters and IAM roles matched in
our tests. We did not check the other services.

Effect: in our offline tests, tags on Lambda functions, DB instances, tables,
queues and topics did not reach the report, so a tag-policy check reports them
as missing tags even if they exist. With `--fallback-display always`, the same
Lambda function or table appears twice: once without tags, and once with the
tags and the type `Unknown`. Treat tag-policy results for these services with
care, and check the ARN column.

## When a run goes wrong

- **One account fails, the others work:** InvenTag logs the error, leaves that
  account out and exits with code 0. The report does not say which account is
  missing. Check the log for `Failed to establish context for account`. If
  every account fails, the run exits with code 1.
- **No resources found, or the filters removed all of them:** InvenTag writes
  no report, logs a warning and exits with code 0. Check for the file in
  scripts.
- **A service you lack permission for:** InvenTag skips that call, does not
  print a message and carries on. The reason is logged only at debug level, so
  a missing sheet can mean a missing permission. (Resources of that service can
  still appear if the Resource Groups Tagging API returns them.)
- **Cost Explorer access denied:** the run carries on without billing data.
  The reason is logged only at debug level.
- **A call blocked by the read-only guard** raises an error that names the
  operation. The CLI does not make such calls itself.
- **A failed S3 upload** makes the whole run exit with code 1, after the
  reports are written locally.
- **A failed report format** makes the run exit with code 1.

## Costs

By default, discovery calls the Cost Explorer `GetCostAndUsage` API. In our
offline test it made two requests for each account. AWS charges for each Cost
Explorer request. See the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` stops those calls. The report then has no billing
  data to compare with.
- `--enable-cost-analysis` makes more Cost Explorer calls even with
  `--no-billing-validation` (eight more in our offline test), as well as
  Pricing and CloudWatch calls.

Other calls are free, but large accounts mean many requests and possible
throttling (AWS slowing down your requests).

## Performance and limits

- InvenTag has no benchmark numbers for real accounts. Scanning every region
  of a large account is slow: one set of calls per service per region.
- Accounts are scanned four at a time by default. Each account has 1800 seconds
  (30 minutes). A run does not resume; if it stops, start it again.
- Excel sheet names are cut to 31 characters. Word tables show up to 50
  resources per service by default (`max_rows`).
- When a run saves a snapshot, InvenTag removes snapshots in `bom_output/state/`
  that are older than 30 days or beyond the newest 100. Keep a copy if you need
  longer history.
- A second run creates an empty `bom_output/changelogs/` folder. It is not used.

## Noise you can ignore

With `--service-descriptions`, VPC resources log
`Failed to render template vpc_vpc: 'cidr_block'` warnings. The report is not
affected.

## Security notes

- **Use a read-only IAM identity anyway.** The guard blocks write calls, and
  your IAM (Identity and Access Management) policy is a second, independent
  safety net. See [Set up read-only access](../guides/read-only-access.md).
- **Debug logs are redacted** since v5: session tokens, keys and signatures
  are masked. Still treat debug logs as sensitive.
- **Two library functions write to AWS** when called from your own Python
  code (the CLI does not call them): `CredentialManager.setup_cross_account_roles()`
  creates IAM roles, and the S3 helper can change bucket lifecycle rules
  (off by default, and it merges with existing rules).

## Tests

The suite has 1315 passing tests and 9 performance benchmarks that run only on
request. All of them use moto. CI runs them on Python 3.11, 3.12, 3.13 and
3.14. No test runs against a real AWS account.
