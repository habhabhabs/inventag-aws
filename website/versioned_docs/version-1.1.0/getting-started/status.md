---
title: Feature status and known limitations
description: Which InvenTag features work in v1.0.2, which are partial, which flags stop with an error, and the specific limits, costs and risks to know before you rely on it.
sidebar_position: 5
---

# Feature status and known limitations

**Who this is for:** anyone about to rely on InvenTag for real work.

**What you will know after reading:** which features work, where they stop
short, which flags stop with an error, and what to do about each limit.

This page is deliberately blunt. This page describes InvenTag v1.0.2. We
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
| `--service-descriptions` | Custom descriptions work for services InvenTag has no built-in description for. For S3, EC2, RDS, Lambda and VPC resources, a built-in description wins unless your entry also names a `template`. See [Configuration files](../reference/configuration-files.md#service-descriptions). |
| `--enable-cost-analysis` | Adds a Cost Analysis sheet and the four `forgotten_analysis.*` columns. It makes many extra Cost Explorer, Pricing and CloudWatch calls. See [Costs](#costs). |
| `--compliance-standard` | Stops with exit code 2. A standard such as SOC 2 cannot be checked from an inventory, and a flag that only printed a label would mislead you. Use a tag-policy template. |
| `--create-google-docs`, `--create-google-sheets` | Work against mocked Google clients only. See [Google Sheets and Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Kept so old commands still run. The read-only guard is always on. |
| `--disable-production-safety` | Stops with exit code 2. The guard cannot be turned off. |

<!-- BEGIN EXAMPLE OUTPUT: failing-flags -->

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
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
- **Global services** (IAM, the S3 bucket list, CloudFront, Route 53 and
  the ACM certificates CloudFront uses) are read once per account from
  `us-east-1`, whatever regions you choose. Their region column says `global`;
  an S3 bucket keeps its own region. See [Run a scan](../guides/run-a-scan.md).
- **Regions.** Without `--account-regions`, InvenTag asks EC2 for the regions
  enabled in the account. If that call fails, it logs a warning and scans only
  `us-east-1`, `us-west-2`, `eu-west-1` and `ap-southeast-1`. A region that
  fails its access check is skipped with a warning, and the run still succeeds.

## When a run goes wrong

- **One account fails, the others work:** the run exits with code 0. The
  run summary and the report name each account that failed and the reason.
  If every account fails, the run exits with code 1.
- **No resources found, or the filters removed all of them:** InvenTag writes
  no report, logs a warning and exits with code 0. Check for the file in
  scripts.
- **A service you lack permission for:** InvenTag skips that call, logs one
  warning for the service with the reason, and carries on. Resources of that
  service can still appear if the Resource Groups Tagging API returns them.
- **Cost Explorer access denied:** the run carries on without billing data and
  logs one warning.
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

## Security notes

- **Use a read-only IAM identity anyway.** The guard blocks write calls, and
  your IAM (Identity and Access Management) policy is a second, independent
  safety net. See [Set up read-only access](../guides/read-only-access.md).
- **Debug logs are redacted** by default: session tokens, keys and signatures
  are masked. Still treat debug logs as sensitive.
- **Two library functions write to AWS** when called from your own Python
  code (the CLI does not call them): `CredentialManager.setup_cross_account_roles()`
  creates IAM roles, and the S3 helper can change bucket lifecycle rules
  (off by default, and it merges with existing rules).

## Tests and the software bill of materials

The test suite and the dependency inventory have their own pages:
[Tests](../security/tests.md) and
[Software bill of materials](../security/sbom.md).
