---
title: Feature status and known limitations
description: Which InvenTag features work, which are partial, which flags stop with an error, and the limits, costs and risks to know before you rely on it.
sidebar_position: 5
---

# Feature status and known limitations

**Who this is for:** anyone about to rely on InvenTag for real work.

**What you will know after reading:** which features work, where they stop
short, which flags stop with an error, and what to do about each limit.

This page is deliberately blunt. It describes the current release; the
[changelog](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md) lists what changed in each release. We
checked each item by running the code offline against mocked AWS (moto), or by
reading the code path. **No test has run against a real AWS account.** Where a
point below depends on how real AWS behaves, the page says so. If you fix or
change one of these, update this page in the same pull request.

## What is tested

Every feature has an offline test against mocked AWS (moto). The list of tests
and what each one checks is on the [Tests](../security/tests.md) page.

## Flags with a limit

| Flag | What actually happens |
|---|---|
| `--enable-cost-analysis` | Adds a Cost Analysis sheet and the four `forgotten_analysis.*` columns. The costs are estimates from the AWS Pricing API, not your invoice. It makes extra Cost Explorer, Pricing and CloudWatch calls. See [Costs](#costs). |
| `--compliance-standard` | Stops with exit code 2. A standard such as SOC 2 cannot be checked from an inventory, and a flag that only printed a label would mislead you. Use a tag-policy template. |
| `--create-google-docs`, `--create-google-sheets` | Work against mocked Google clients only. See [Google Sheets and Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Kept so old commands still run. The read-only guard is always on. |
| `--disable-production-safety` | Stops with exit code 2. The guard cannot be turned off. |

<!-- BEGIN EXAMPLE OUTPUT: failing-flags -->

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)

$ inventag --risk-threshold HIGH
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

<!-- END EXAMPLE OUTPUT: failing-flags -->

## What InvenTag finds, and what it does not

- **Services with their own discovery code (46):** VPC (VPCs, subnets,
  security groups, internet and NAT gateways, route tables, network ACLs,
  Elastic IP addresses), EC2 (instances, volumes, snapshots, key pairs), S3,
  RDS, Lambda, ELB, ELBv2, IAM, CloudFront, Route 53, KMS, CloudWatch, ECS
  (clusters, and the services in every cluster), EKS, SNS, SQS, DynamoDB,
  API Gateway, Glue, WorkMail, CloudFormation, ACM, CloudTrail, EventBridge,
  ElastiCache, Redshift, Redshift Serverless, OpenSearch, EFS, ECR, Step
  Functions, Kinesis, Firehose, Secrets Manager (names only), Systems Manager
  parameters (names only), Auto Scaling groups, Backup vaults, Cognito user
  pools, CodeBuild, CodePipeline, Athena workgroups, EMR, MSK, AppSync,
  Elastic Beanstalk and WAF web ACLs.
- **Everything else** can appear only if the Resource Groups Tagging API
  returns it. That API lists resources that have, or once had, tags, so
  untagged resources of any other service are missing. With
  `--fallback-display auto` (the default), such resources are shown only for
  services that have no results from their own discovery code. Use
  `--fallback-display always` to show all of them.
- **Not collected:** secret values, parameter values, object contents or any
  other data. The read-only guard blocks the calls that return them.
- **Secret values in allowed responses are masked.** Some read calls return a
  secret next to a setting. Values of fields that often hold secrets are
  replaced by `***REDACTED***` in reports, JSON output, state snapshots,
  resume checkpoints and logs: Lambda and App Runner environment variables,
  ECS and CodeBuild environment values, EC2 user data, CloudFormation
  parameter and output values, Glue job and trigger arguments and connection
  properties, and any field named like a password, secret, token, private key
  or credentials. The names stay.
- **Secrets in other fields are not found.** InvenTag goes by field name, so a
  secret in a description, a tag or another free-text field is not masked.
- **Reports and snapshots written by versions before v1.2.0 may contain
  secret values.** Delete or restrict old `bom_output/` folders and shared
  copies.
- **Global services** (IAM, the S3 bucket list, CloudFront, Route 53, WAF web
  ACLs for CloudFront, and the ACM certificates CloudFront uses) are read once
  per account from `us-east-1` (`cn-north-1` in China, `us-gov-west-1` in
  GovCloud), whatever regions you choose. Their region column says `global`;
  an S3 bucket keeps its own region. See [Run a scan](../guides/run-a-scan.md).
- **Regions.** Without `--account-regions`, InvenTag asks EC2 for the regions
  enabled in the account. If `ec2:DescribeRegions` fails, it asks
  `account:ListRegions`; if that also fails, it tries every region of the
  partition and skips the ones that fail the access check. A region that fails
  its access check is skipped with a warning, and the run still succeeds.

## When a run goes wrong

- **One account fails, the others work:** the run exits with code 0, or with
  code 5 when you pass `--fail-on-account-error`. The run summary and the
  default report name each account that failed and the reason; a report made
  with `--template` does not. If every account
  fails, the run exits with code 1.
- **An account runs out of time:** it counts as failed. The resources found
  before the limit stay in the report, and the default report says the account
  is incomplete.
- **No resources found, or the filters removed all of them:** without
  `--template`, InvenTag writes no report, logs a warning and exits with code
  0. With `--template`, it writes an empty report. `--fail-if-empty` makes
  either case exit with code 6.
- **A service you lack permission for:** InvenTag skips that call, logs one
  warning for the service with the reason, and carries on. Resources of that
  service can still appear if the Resource Groups Tagging API returns them.
- **A listing that fails for another reason** (throttled after the retries,
  or an error) is logged as a warning for that service and region, and
  counted in the state snapshot (`metadata.tags.coverage_summary`).
- **Every call in an account denied:** the account does not count as failed.
  The run exits with code 0 with no resources to report, and the snapshot it
  saves makes the next run report every resource of that account as removed.
- **A service whose listing was throttled or failed with an error** in one run
  appears as removed in the next change report.
- **A session that expires during the scan:** the run exits with code 0 and
  the report looks complete.
- **An expired IAM Identity Center (SSO) token** stops the run with a Python
  traceback instead of a message. Run `aws sso login` again.
- **Warnings from discovery** appear on the console but are not written to the
  `--log-file` file.
- **Cost Explorer access denied:** the run carries on without billing data and
  logs one warning.
- **A call blocked by the read-only guard** is logged as an error that names
  the operation. If it happens inside a listing, that listing is skipped and
  the run carries on with exit code 0. The CLI does not make such calls itself.
- **A failed S3 upload** makes the whole run exit with code 1, after the
  reports are written locally.
- **A failed report format** makes the run exit with code 1, and nothing is
  uploaded to S3, not even the formats that were written.
- **A snapshot that cannot be saved** is logged as an error, and the run still
  exits with code 0.
- **Google output with `--template`** is skipped, and the run exits with
  code 0.
- **Some invalid values stop with exit code 1, not 2,** for example
  `--max-concurrent-accounts 0` or `--account-processing-timeout 0`.
- **Values in the `settings` block of an accounts file override the matching
  command-line flags**, for example `max_concurrent_accounts`.

## Costs

By default, discovery calls the Cost Explorer `GetCostAndUsage` API. In our
offline test it made two requests for each account. AWS charges for each Cost
Explorer request. See the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` stops those calls. The report then has no billing
  data to compare with.
- `--enable-cost-analysis` makes more calls, even with
  `--no-billing-validation`. In our offline test (one account, `us-east-1`) it
  made 5 Cost Explorer, 3 Pricing and 2 CloudWatch calls. The estimates price
  each instance type (and other size or class) separately. Each different
  price lookup is made once and then reused, so the number of Pricing calls
  grows with the number of different resource types and sizes, not with the
  number of resources.

Other calls are free, but large accounts mean many requests and possible
throttling (AWS slowing down your requests). InvenTag retries a throttled call
up to 10 times (standard retry mode); `AWS_RETRY_MODE` and `AWS_MAX_ATTEMPTS`
override this.

## Performance and limits

- InvenTag has no benchmark numbers for real accounts. Scanning every region
  of a large account is slow: one set of calls per service per region.
- Against moto (in process, so no network time), `scripts/benchmark_scan.py`
  scanned 9,547 resources in one region with 2,027 API calls. The call count
  is the useful figure for real accounts: about 60 fixed calls per region,
  plus one call per S3 bucket and per Lambda function, plus one Tagging API
  page per 100 tagged resources.
- Accounts are scanned four at a time by default (`--max-concurrent-accounts`).
  Each account has 1800 seconds from when its scan starts
  (`--account-processing-timeout`).
- When some accounts fail, the results of the finished ones are saved. Run the
  same command with `--resume` within 24 hours (`--resume-max-age-hours`) to
  scan only the others.
- Excel sheet names are limited to 31 characters: longer names are cut,
  characters Excel does not allow become `-`, a repeated name gets ` (2)`, and
  the log names each changed sheet. Word tables show up to 50 resources per
  service by default (`max_rows`).
- When a run saves a snapshot, InvenTag removes snapshots in `bom_output/state/`
  that are older than 30 days or beyond the newest 100. The snapshot just
  written and the one it is compared with are never removed. Change the limits
  with `--state-retention-days` and `--state-max-snapshots`, or keep everything
  with `none`.
- With `--enable-network-analysis` or `--enable-security-analysis`, the
  analysis calls are made twice in one run.

## Security notes

- **Use a read-only IAM identity anyway.** The guard blocks write calls, and
  your IAM (Identity and Access Management) policy is a second, independent
  safety net. See [Set up read-only access](../guides/read-only-access.md).
- **Debug logs are redacted** by default: session tokens, keys, signatures and
  the secret values listed above are masked. Still treat debug logs as
  sensitive.
- **Two library functions can write to AWS** when called from your own Python
  code (the CLI does not call them): `CredentialManager.setup_cross_account_roles()`
  runs only with `allow_iam_writes=True`, and the S3 lifecycle helper only
  with `allow_bucket_writes=True`. The read-only guard blocks both in a CLI run.
- **Using `CloudBOMGenerator` from your own Python code** does not install the
  read-only guard. Only the `inventag` command does.

## Tests and the software bill of materials

The test suite and the dependency inventory have their own pages:
[Tests](../security/tests.md) and
[Software bill of materials](../security/sbom.md).
