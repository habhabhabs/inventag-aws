---
title: Feature status and known limitations
sidebar_label: Feature status
description: Which InvenTag features work, which are partial, which flags stop with an error, and the limits, costs and risks to know before you rely on it.
sidebar_position: 5
---

# Feature status and known limitations

**Who this is for:** anyone about to rely on InvenTag for real work.

**What you will know after reading:** which features work, where they stop
short, which flags stop with an error, and what to do about each limit.

This page is deliberately blunt. It describes the current release; the
[changelog](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md) lists what changed in each release. Each item below is proven by an offline test or run against mocked AWS (moto). **No test has run against a real AWS account.** Where an item depends on how real AWS behaves, the page says so. If you fix or change one of these, update this page in the same pull request.

## What is tested

The [Tests](../security/tests.md) page lists the offline tests against mocked AWS (moto) and what each one checks. A statement in these docs that no test proves carries a note that starts with "Not verified against".

## Flags with a limit

| Flag | What actually happens |
|---|---|
| `--enable-cost-analysis` | Adds a Cost Analysis sheet and the four `forgotten_analysis.*` columns, with estimates from the AWS Pricing API that are not your invoice, and makes extra Cost Explorer, Pricing and CloudWatch calls (see [Costs](#costs)). |
| `--compliance-standard` | Stops with exit code 2, because a standard such as SOC 2 cannot be checked from an inventory; use a tag-policy template instead. |
| `--create-google-docs`, `--create-google-sheets` | Tested against mocked Google clients only (see [what is not verified](../guides/google-sheets-and-docs.md#what-is-not-verified)). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Accepted so that old commands still run, and have no effect, because the read-only guard is always on. |
| `--disable-production-safety` | Stops with exit code 2, because the read-only guard cannot be turned off. |

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
- **Everything else** appears only when the Resource Groups Tagging API
  returns it, so untagged resources of any other service are missing. With
  `--fallback-display auto` (the default), such resources are shown only for
  services that have no results from their own discovery code;
  `--fallback-display always` shows all of them.
- **Not collected:** secret values, parameter values, object contents or any
  other data, because the read-only guard blocks the calls that return them.
- **Secret values in allowed responses are masked.** Some read calls return a
  secret next to a setting. Values of fields that often hold secrets are
  replaced by `***REDACTED***` in reports, JSON output, state snapshots,
  resume checkpoints and logs: Lambda and App Runner environment variables,
  ECS and CodeBuild environment values, EC2 user data, CloudFormation
  parameter values, stack output values and stack set template bodies, Glue
  job, trigger and job-run arguments and connection properties, EMR on EKS job
  arguments, WorkSpaces Thin Client activation codes, DMS certificate wallets,
  connection strings, signed, download and upload URLs, Splunk HEC, Grafana and
  join tokens, and any field named like a password, secret, token, access or
  refresh token, private key or credentials, also inside JSON text. The names
  stay.
- **Secrets in other fields are not found:** a secret in a description, a
  tag, another free-text field or a field that AWS adds later is copied into
  reports as it is, because masking goes by field name.
- **Tags are shown as they are**, also when a tag key looks like a secret, such
  as `password`.
- **Reports and snapshots written by versions before v1.2.0 may contain
  secret values**, so delete or restrict old `bom_output/` folders and shared
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
  code 5 when you pass `--fail-on-account-error`.
- **A report made with `--template`** does not name the accounts that failed;
  the run summary and the default report do.
- **Every account fails:** the run exits with code 1, also with
  `--fail-on-account-error`, and writes no report unless the accounts ran out
  of time, in which case the report lists what was found.
- **An account runs out of time:** it counts as failed, and the resources
  found before the limit stay in the report.
- **No resources found, or the filters removed all of them:** InvenTag writes
  no report without `--template` and an empty report with `--template`, and
  exits with code 0 unless you pass `--fail-if-empty` (code 6).
- **A tag policy with no resource in scope** reports
  `0 of 0 resources compliant (100.0%)`, although nothing was checked.
- **A service you lack permission for** is skipped with one warning, and its
  resources appear only if the Resource Groups Tagging API returns them.
- **A listing that fails for another reason** (throttled after the retries, or
  an error) is a warning and a count in the snapshot
  (`metadata.tags.coverage_summary`), and no report names it.
- **Every call in an account denied:** the account does not count as failed,
  the run exits with code 0, and the next change report lists every resource
  of that account as removed.
- **A service whose listing was throttled or failed** in one run shows its
  resources as removed in the next change report.
- **A run with other regions or services than the run before** shows the
  resources outside the new scope as removed in the change report.
- **The first change report after upgrading from v1.1.4** lists the resources
  of newly covered services as added, although they existed before.
- **A session that expires during the scan** leaves a report with only what
  was read before it expired, without a note, and the run exits with code 0,
  also with `--fail-on-account-error`.
- **A session that is already expired when the scan starts** gives no report
  file and exit code 0.
- **With `--resume`**, an account whose session expired part-way in the first
  run can be reused as if it were complete.
- **An expired IAM Identity Center (SSO) token** stops the run with exit code
  1 and a Python traceback, and the message does not tell you to run
  `aws sso login`.
- **Cost Explorer access denied:** the run carries on without billing data,
  and the two warnings about it show only with `--debug`.
- **A call blocked by the read-only guard** inside a listing skips that
  listing with an error line, and the run still exits with code 0.
- **A failed S3 upload** makes the whole run exit with code 1, after the
  reports are written locally.
- **A failed report format** makes the run exit with code 1 and upload nothing
  to S3, not even the formats that were written.
- **A snapshot that cannot be saved** is an error line only, and the run still
  exits with code 0.
- **Google output with `--template`** is skipped, and the run exits with
  code 0.
- **Some invalid values stop with exit code 1, not 2,** for example
  `--max-concurrent-accounts 0` or `--account-processing-timeout 0`.
- **Values in the `settings` block of an accounts file override the matching
  command-line flags**, for example `max_concurrent_accounts`.
- **An empty result with `--s3-bucket`** makes the run exit with code 1
  (`S3 upload of reports failed: no files`), also with `--fail-if-empty`.
- **A region name typed wrong in `--account-regions`** ends the run with exit
  code 0, a raw `KeyError` text and no report.
- **A profile that needs MFA, run without a terminal,** stops with a Python
  traceback and an empty message, or waits for ever when the input stays open.
- **An `--audit-output` or `--log-file` path that cannot be written** ends the
  run with a Python traceback, and an output folder that cannot be used is
  found only after the whole scan.
- **Ctrl-C** stops the run without a visible message, and a SIGTERM stops it
  without any message.
- **A second entry with the same account ID** in an accounts file is dropped
  without a message, so its regions are not scanned.
- **Two runs that use the same output folder at the same time** are not
  prevented.

## Costs

By default, discovery calls the Cost Explorer `GetCostAndUsage` API. In our
offline test it made two requests for each account. AWS charges for each Cost
Explorer request: see the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` stops those calls, and the report then has no
  billing data to compare with.
- `--enable-cost-analysis` makes more Cost Explorer, Pricing and CloudWatch
  calls, even with `--no-billing-validation`, and the number depends on your
  resources. Each different price lookup is made once and then reused, so the
  number of Pricing calls grows with the number of different resource types and
  sizes, not with the number of resources.

Not verified against real AWS: the cost estimates of `--enable-cost-analysis`.

InvenTag retries a throttled call up to 10 times (standard retry mode);
`AWS_RETRY_MODE` and `AWS_MAX_ATTEMPTS` override this.

## Performance and limits

- InvenTag has no benchmark numbers for real accounts, and a scan makes one
  set of calls per service per region.
- Against moto (in process, so no network time),
  `scripts/benchmark_scan.py --scale 60` scanned 10,948 resources in one
  region with 2,053 API calls: 1,200 `s3:GetBucketLocation` calls (one for
  each bucket), 600 `lambda:GetFunctionConfiguration` calls (one for each
  function), 150 Resource Groups Tagging API calls and 103 other calls. The
  call count is the useful figure for real accounts.
- Accounts are scanned four at a time by default (`--max-concurrent-accounts`).
  Each account has 1800 seconds from when its scan starts
  (`--account-processing-timeout`).
- When some accounts fail, the results of the finished ones are saved. Run the
  same command with `--resume` within 24 hours (`--resume-max-age-hours`) to
  scan only the others.
- Excel sheet names are cut to 31 characters, characters Excel does not allow
  become `-`, a repeated name gets ` (2)`, and the log names each changed
  sheet.
- Word tables show up to 50 resources per service by default (`max_rows`).
- When a run saves a snapshot, InvenTag removes snapshots in `bom_output/state/`
  that are older than 30 days or beyond the newest 100. The snapshot just
  written and the one it is compared with are never removed. Change the limits
  with `--state-retention-days` and `--state-max-snapshots`, or keep everything
  with `none`.
- With `--enable-network-analysis` or `--enable-security-analysis`, the
  analysis calls are made twice in one run.
- Network analysis counts a resource in several subnets for the first subnet
  only, and counts load balancers for their VPC but not for a subnet.
- Service attribute enrichment (`enable_service_enrichment` in the BOM
  settings) does not run; reports contain the fields that discovery returns.
- In a template report, the Name column is empty when AWS returns no `Name`
  field or `Name` tag for the resource; the ID column identifies it. For
  Lambda functions, IAM roles and KMS aliases, a template report shows the ID
  as the name.

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
- **A config template can set the output folder and the accounts and roles to
  scan.** Use only templates you trust.
- **Assumed-role sessions are not refreshed**, so an account scan that outlasts
  the session runs into an expired token.

  Not verified against real AWS: assumed-role sessions last one hour.
- **MFA works only through AWS profiles** (`mfa_serial`), not for `role_arn`
  entries in an accounts file.

  Not verified against a real MFA device: MFA through an AWS profile with `mfa_serial`.

## Tests and the software bill of materials

The test suite and the dependency inventory have their own pages:
[Tests](../security/tests.md) and
[Software bill of materials](../security/sbom.md).
