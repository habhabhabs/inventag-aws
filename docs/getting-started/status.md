---
title: Feature status and known limitations
description: Which InvenTag features work today, which flags are accepted but do nothing yet, known bugs, and the costs and risks to know before you rely on it.
sidebar_position: 4
---

# Feature status and known limitations

**Who this is for:** anyone about to rely on InvenTag for real work.

**What you will know after reading:** which features you can trust today,
which flags do nothing yet, and what to do instead.

This page is deliberately blunt. Each item was checked by running the code
(offline, against mocked AWS) or by reading the exact code path, on the
`main` branch in November 2026. If you fix one of these, update this page in
the same pull request.

:::info Security fixes in progress
A security update is in progress that wires up the read-only guard, makes
unimplemented flags fail loudly and adds S3 upload. Until it is merged, the
items below describe the current `main` branch.
:::

## Works today

| Feature | How to use it |
|---|---|
| Find resources in one or more accounts | Default credentials, `--accounts-file`, `--accounts-prompt`, or `--cross-account-role` with a full role ARN |
| Excel report | `--create-excel` writes `bom_output/multi_account_bom_<timestamp>.xlsx` |
| Word report | `--create-word` writes `bom_output/multi_account_bom_<timestamp>.docx` |
| Report layouts | `--template <report template>`; see [Templates](../templates/index.md) |
| Tag columns | A report template's `tag_columns` |
| Tag-policy checks | `--template <tag-policy template>`; adds a Tag Compliance sheet, a Word section and a JSON file |
| Fail a CI job on tag problems | A config template with `fail_on_tag_violations: true` (exit code 3) |
| Region filter | `--account-regions us-east-1,eu-west-1` |
| Snapshots of each run | Saved automatically in `bom_output/state/` |

## Partly working

| Feature | What actually happens |
|---|---|
| `--account-services`, `--account-tags` | Applied in one discovery path only, so resources from other services, or with other tags, can still appear. |
| Change reports between runs | A `changelog_<timestamp>.md` file is written on the second and later runs, but it compares the newest snapshot with itself, so it always reports 0 changes. See [Track changes between runs](../guides/track-changes.md). |
| Discovery coverage | In offline tests, EC2 instances did not appear in the report (volumes and snapshots did), and Lambda and DynamoDB tags were not collected. This has not been checked against a real AWS account yet. |

## Accepted but not working yet

These flags parse without error, so a command that uses them *looks* fine,
but they have no effect.

| Flag | What actually happens | What to do instead |
|---|---|---|
| `--tag-mappings`, `--service-descriptions` | The files are validated and loaded, but the mapped columns and descriptions are never added to the report, because of a bug in the processing step. | Use a report template's `tag_columns`. |
| `--enable-network-analysis`, `--enable-security-analysis` | No network or security sheets are added to the Excel or Word report. | None yet. |
| `--validate-credentials` | Reports every account as invalid because of a bug, even when the credentials work. | Run `aws sts get-caller-identity`. |
| `--per-account-reports` | The setting is stored but never used. | Run once per account with `--accounts-file`. |
| `--s3-bucket`, `--s3-key-prefix`, `--s3-encryption`, `--s3-kms-key-id` | Nothing is uploaded. A warning is logged. | Upload `bom_output/` yourself, for example with `aws s3 cp`. |
| `--create-google-docs` | No Google output is produced. | Use `--create-excel` and import the file. |
| `--enable-production-safety`, `--disable-production-safety`, `--enforce-read-only`, `--security-validation`, `--compliance-standard`, `--risk-threshold`, `--audit-output`, `--validate-operations` | Parsed, then not used. | Rely on a read-only IAM policy: [Set up read-only access](../guides/read-only-access.md). |
| `--generate-changelog` | Changelogs are always generated; the flag cannot turn them off. | Use `--disable-state-management`. |

## Works differently from its help text

`--cross-account-role` says "role name", but the value is used as a role ARN.
A bare name such as `InvenTagReadOnly` fails. Pass the full ARN, for example
`arn:aws:iam::123456789012:role/InvenTagReadOnly`. To scan several accounts,
use an [accounts file or a config template](../guides/scan-multiple-accounts.md).

## Costs

Discovery calls the Cost Explorer `GetCostAndUsage` API on every run, and AWS
charges per Cost Explorer API request. See the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Other calls are free, but large accounts mean many requests and possible
throttling.

## Security notes

- **`--debug` writes temporary session tokens to the log.** Debug mode turns on
  detailed AWS SDK logging, which includes the `X-Amz-Security-Token` header.
  Don't keep debug logs, and never upload them as CI artifacts.
- **Use a read-only IAM identity.** Nothing in the current CLI blocks a write
  call at runtime. Your IAM policy does.
- **Two library functions write to AWS** if you call them from your own Python
  code (the CLI does not): `CredentialManager.setup_cross_account_roles()`
  creates an IAM role and policy, and the S3 upload helper in
  `inventag/core/cicd_integration.py` replaces the bucket's **whole**
  lifecycle configuration.

## Tests

The test suite on `main` has many failing tests that no longer match the code
(115 failures and 34 errors in our run, none caused by missing AWS
credentials). The template tests (`tests/unit/templating`,
`tests/integration/templating`) all pass. The CI workflow currently hides
test failures; a fix is in progress.
