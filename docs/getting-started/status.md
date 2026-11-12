---
title: Current status and known limitations
description: What the InvenTag CLI does today, which flags stop with an error, and the costs and risks to know about.
sidebar_position: 3
---

# Current status and known limitations

This page describes the code on the `main` branch after release v4.2.27
(November 2026). Each row comes from a code review and from offline test runs.
The offline test runs use a simulated AWS backend (`moto`), not a real AWS
account. If you change the behavior of a flag, update this page in the same
pull request.

## Works today

| Feature | How |
|---|---|
| Resource discovery in one account or in many accounts | `./inventag.sh`, `--accounts-file`, `--accounts-prompt`, `--cross-account-role` |
| Excel BOM | `--create-excel` writes `bom_output/multi_account_bom_<timestamp>.xlsx`. Excel is the default format. |
| Word BOM | `--create-word` writes `bom_output/multi_account_bom_<timestamp>.docx`. Each service table shows a maximum of 50 resources. |
| Custom tag columns and service descriptions | `--tag-mappings`, `--service-descriptions`. For the file formats, see [Configuration examples](../user-guides/configuration-examples.md). |
| Snapshots between runs | On by default. The CLI writes each snapshot to `bom_output/state/`. |
| Change report between runs | On by default. The CLI writes `bom_output/changelog_<timestamp>.md` when a previous snapshot exists. Use `--no-generate-changelog` to stop this output. |
| Region filter | `--account-regions us-east-1,eu-west-1` |
| Service filter | `--account-services EC2,S3`. See [Service and tag filters](#service-and-tag-filters). |
| Tag filter | `--account-tags '{"env":"prod"}'`. See [Service and tag filters](#service-and-tag-filters). |
| Upload of reports to Amazon S3 | `--s3-bucket`, `--s3-key-prefix`, `--s3-encryption`, `--s3-kms-key-id`. See [S3 upload](#s3-upload). |
| Read-only guard | Always on. See [Read-only guard](#read-only-guard). |
| Check of operation names against the guard | `--validate-operations ec2:DescribeInstances s3:PutObject`. Exit code `0` if the guard allows all names, `1` if not. This flag makes no AWS call. |
| Audit of AWS API calls | `--audit-output audit.json` writes one JSON file with each operation, its call count, and each blocked call. |
| Cost Explorer switch | `--no-billing-validation`. See [Costs](#costs). |
| Private output files | The CLI creates files with mode `0600` and new directories with mode `0700`. |
| Tag-policy compliance | Separate script: `python3 scripts/legacy/tag_compliance_checker.py --config policy.yaml` |

## Flags that stop with an error

These features are not implemented. If you use one of these flags, the CLI
prints `inventag: error: <flag>: <reason>` and stops with exit code `2`. The
CLI makes no AWS call before it stops.

| Flag | Status |
|---|---|
| `--create-google-docs` | Not implemented. The package contains no Google API code. Use `--create-excel` or `--create-word`. |
| `--per-account-reports` | Not implemented. The CLI writes one consolidated report. To get one report for each account, run the CLI one time for each account. |
| `--compliance-standard` | Not implemented. InvenTag does not certify or assess compliance with SOC 2, PCI DSS, HIPAA or GDPR. |
| `--risk-threshold` | Not implemented. The read-only guard blocks each operation that is not a read operation. |
| `--disable-production-safety` | Not supported. You cannot set the read-only guard to off. |

## Flags that have no effect

| Flag | Detail |
|---|---|
| `--enable-production-safety`, `--enforce-read-only`, `--security-validation` | The CLI accepts these flags for compatibility. The read-only guard is always on, with or without these flags. |
| `--generate-changelog` | The changelog is on by default. Only `--no-generate-changelog` changes the behavior. |
| `--enable-network-analysis`, `--enable-security-analysis` | In an offline test run with VPC, subnet and security-group resources, these flags added no sheets, columns or sections to the Excel report. |

## Read-only guard

The CLI installs a guard on each AWS client before the first AWS call. The
guard examines each API operation before the request goes to AWS.

- The guard allows operations with these name prefixes: `List`, `Describe`,
  `Get`, `Head`, `Lookup`, `Search`, `BatchGet`.
- The guard allows `sts:AssumeRole`. InvenTag uses it to get access to other
  accounts.
- The guard blocks read operations that return secrets or data. Examples are
  `secretsmanager:GetSecretValue`, `ssm:GetParameter`, `s3:GetObject`,
  `lambda:GetFunction` and `dynamodb:GetItem`.
- The guard blocks all other operations. A blocked operation causes a
  `ReadOnlyViolationError`, and AWS does not receive the request.
- If you use `--s3-bucket`, the guard allows `s3:PutObject` on the upload
  client only.

The guard is a second layer. Use a read-only IAM policy as the first layer.
See [Permissions and production safety](../user-guides/production-safety.md).

## Cross-account role

`--cross-account-role` accepts a role name or a full role ARN.

- If you give a full ARN, the CLI assumes that role. For example:
  `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly`.
- If you give a role name, also give `--accounts-file`. The CLI makes one role
  ARN for each account ID in the file.
- If you give a role name without `--accounts-file`, the CLI stops with exit
  code `2`.
- If the role name or the ARN is not valid, the CLI stops with exit code `2`.

## Service and tag filters

`--account-services` and `--account-tags` filter the final resource list. The
result is the same for all discovery paths.

- `--account-services` compares each name with the `Service` column of the
  report. The comparison ignores case, spaces, and the prefixes `Amazon` and
  `AWS`. For example, `s3`, `S3` and `Amazon S3` are the same service.
- `--account-tags` keeps a resource only if it has each tag in the JSON
  object. A string value must be equal to the tag value. A list value matches
  if the tag value is in the list.
- The filters apply to the results. The CLI continues to make most discovery
  API calls. Thus a filter does not make a run much faster. In an offline test,
  a run with `--account-services` made 1398 API calls and a run with no filter
  made 1400.
- If no resource stays after the filters, the CLI writes no report file. The
  CLI then prints `No data to export` and stops with exit code `0`.

## S3 upload

`--s3-bucket` uploads each generated report to
`s3://<bucket>/<prefix>/<UTC timestamp>/<file name>`.

- The default prefix is `bom-reports/`. Use `--s3-key-prefix` to change it.
- Each object has server-side encryption. The default is `AES256`. Use
  `--s3-encryption aws:kms` for SSE-KMS.
- `--s3-kms-key-id` is optional. If you use `aws:kms` without a key ID, Amazon
  S3 uses the AWS managed key for the bucket.
- The upload uses the default AWS credentials, not the role of a scanned
  account. These credentials must have `s3:PutObject` on the bucket.
- The CLI refuses public ACLs.
- If an upload fails, the run stops with exit code `1`.
- The CLI does not change the lifecycle configuration of the bucket.

## Costs

AWS bills each Cost Explorer API request. See the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- By default, discovery makes two `GetCostAndUsage` requests for each account
  in each run.
- With `--no-billing-validation`, discovery makes no Cost Explorer request.
  The `billing_validated` column is then `False`, and the `monthly_spend`
  column is `0.0`.
- `--enable-cost-analysis` makes its own Cost Explorer requests. In an offline
  test, `--no-billing-validation --enable-cost-analysis` made one
  `GetCostAndUsage` request.
- If the identity has no permission for Cost Explorer, discovery continues
  without billing data.

The other API calls are free of charge. A large account causes many API
requests, and AWS can throttle them.

## Security notes

- **`--debug` writes a detailed log.** Debug mode sets the AWS SDK log level
  to DEBUG. InvenTag removes these values from the log before it writes a
  line: secret access keys, session tokens, `Authorization` headers,
  `X-Amz-Security-Token` headers, presigned URL signatures, and the secret
  part of Slack and Microsoft Teams webhook URLs. The replacement text is
  `***REDACTED***`.
- **The debug log is not anonymous.** InvenTag does not remove account IDs,
  user IDs, ARNs, resource names, tag values, or API request and response
  bodies. Do not publish a debug log. Do not upload a debug log as a
  public CI artifact.
- **Use a read-only IAM policy.** The shipped policy
  `config/defaults/iam-policy-read-only.json` lists 106 discovery actions by
  name and uses no wildcard action. See
  [Permissions and production safety](../user-guides/production-safety.md).
- **`--accounts-prompt` hides secrets.** The prompt does not show the secret
  access key or the session token while you type.
- **Spreadsheet formulas.** The Excel builder stores each discovered value as
  text. A resource name that starts with `=` does not run as a formula.

Two library functions write to AWS if you call them from your own code. The
CLI does not call them.

- `CredentialManager.setup_cross_account_roles()` creates an IAM role, creates
  a managed policy with the same read actions, and attaches the policy to the
  role. The function does this in each target account.
- `CICDIntegration` uploads reports to Amazon S3 with server-side encryption
  and refuses public ACLs. The `lifecycle_days` setting has the default `0`,
  and then `CICDIntegration` does not change the bucket lifecycle. If
  `lifecycle_days` is more than `0`, `CICDIntegration` adds or updates one
  rule with the ID `InvenTagBOMLifecycle`. It keeps all other rules of the
  bucket.

The read-only guard is part of the CLI. If you call the library from your own
code, install the guard with `inventag.security.install_global_guard()`.

## Known defects

| Defect | Detail |
|---|---|
| EC2 instances can be absent from the report | In an offline test run, `ec2:DescribeInstances` returned one instance and the report did not list it. The report listed the EBS volume of the instance. |
| Report path in the log for an empty result | If the filters remove all resources, the log shows a report path, but the CLI writes no file. |
| Many `sts:GetCallerIdentity` calls | In an offline test run with 1335 resources, the CLI made 1338 `GetCallerIdentity` calls. |

## Tests

Run the unit tests with `python -m pytest tests/unit -q`. The tests use a
simulated AWS backend and need no AWS credentials.

<!-- TEST-STATUS: filled in at merge -->
