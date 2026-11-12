---
title: Current status and known limitations
description: What the InvenTag CLI does today, which flags are accepted but not wired up yet, and the costs and risks to know about.
sidebar_position: 3
---

# Current status and known limitations

This page is deliberately blunt. It was written from a code review of
v4.2.26 (November 2026). If you fix one of these, please update this page in
the same pull request.

## Works today

| Feature | How |
|---|---|
| Resource discovery (single or multiple accounts) | `./inventag.sh`, `--accounts-file`, `--accounts-prompt`, `--cross-account-role` |
| Excel BOM | `--create-excel` → `bom_output/multi_account_bom_<timestamp>.xlsx` |
| Word BOM | `--create-word` → `bom_output/multi_account_bom_<timestamp>.docx` |
| Custom tag columns / service descriptions | `--tag-mappings`, `--service-descriptions` (file formats: [Configuration examples](../user-guides/configuration-examples.md)) |
| Network and security-group sheets | `--enable-network-analysis`, `--enable-security-analysis` |
| Snapshots and change reports between runs | on by default; stored in `bom_output/state/` |
| Region filtering | `--account-regions` |
| Service filtering (partial) | `--account-services` is applied in one discovery path only (`inventory.py`, around line 1152), so other services can still appear |
| Tag-policy compliance | separate script: `python3 scripts/legacy/tag_compliance_checker.py --config policy.yaml` |

## Accepted by the CLI but not implemented yet

These flags parse without error, so a command that uses them *looks* fine.
They currently have no effect.

| Flag | What actually happens |
|---|---|
| `--s3-bucket`, `--s3-key-prefix`, `--s3-encryption`, `--s3-kms-key-id` | Nothing is uploaded. The generator logs `S3 upload configuration passed but not implemented in this method` (`inventag/core/cloud_bom_generator.py`). Upload the files from `bom_output/` yourself, e.g. `aws s3 cp`. |
| `--create-google-docs` | No Google Docs/Sheets output is produced; there is no Google API code in the package. |
| `--enable-production-safety`, `--disable-production-safety`, `--enforce-read-only`, `--security-validation`, `--compliance-standard`, `--risk-threshold`, `--audit-output`, `--validate-operations` | Parsed, then not used. The `ReadOnlyAccessValidator` in `inventag/compliance/` exists as a library class but the CLI never calls it. Read-only behaviour comes from the discovery code itself and, more importantly, from **your IAM policy**. |
| `--generate-changelog` | Changelogs are always generated; the flag cannot turn them off. |

## Works differently from its help text

| Flag | Detail |
|---|---|
| `--cross-account-role` | The help says "role name", but the value is passed to STS as `RoleArn`. A bare name such as `InvenTagRole` fails botocore's parameter validation before any request is sent. Pass the **full role ARN** (`arn:aws:iam::123456789012:role/InvenTagRole`). The report then labels the account `cross-account`. |

`--compliance-standard soc2|pci|hipaa|gdpr` does **not** make a report
"compliant" with anything. InvenTag can help you gather evidence (an inventory
and tag coverage); it does not certify or assess compliance.

## Costs

Discovery calls the Cost Explorer `GetCostAndUsage` API by default (to find
services that have spend). AWS bills Cost Explorer API requests per request;
check the current [Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Everything else InvenTag calls is free to call, but large accounts mean many
API requests and possible throttling.

## Security notes

- **`--debug` writes session tokens to the log.** Debug mode turns on
  botocore's DEBUG logging, which includes request headers such as
  `X-Amz-Security-Token`. Don't combine `--debug --log-file` with temporary
  credentials unless you delete the log afterwards, and never upload it as a
  CI artifact.
- **Use a read-only IAM policy.** The CLI's discovery path only calls
  `List*`/`Describe*`/`Get*` operations and Cost Explorer, but nothing in the
  CLI enforces that at runtime. A read-only policy does. See
  [Permissions and production safety](../user-guides/production-safety.md).
- Two library functions do write to AWS if you call them from your own code:
  `CredentialManager.setup_cross_account_roles()` (creates an IAM role and
  policy) and `CICDIntegration`'s S3 upload, which also replaces the target
  bucket's **entire** lifecycle configuration with a single InvenTag rule when
  `lifecycle_days > 0` (the default is 90). Don't point it at a bucket that has
  lifecycle rules you care about.

## Tests

On the reviewed commit, `pytest tests` reported 591 passed, 122 failed and 47
errors, plus one module that fails to import. The failures come from tests that
no longer match the code (renamed methods, missing shared fixtures), not from
missing AWS credentials. The CI workflow currently masks this (`|| true`, and a
`--timeout` flag whose plugin isn't installed).
