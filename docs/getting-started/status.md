---
title: Feature status and known limitations
description: Which InvenTag features work today, which flags stop with an error, known bugs, and the costs and risks to know before you rely on it.
sidebar_position: 5
---

# Feature status and known limitations

**Who this is for:** anyone about to rely on InvenTag for real work.

**What you will know after reading:** which features you can trust, which
flags stop with an error, which known bugs remain, and what to do instead.

This page is deliberately blunt. We checked each item by running the code
offline against mocked AWS (moto), or by reading the exact code path. If you
fix one of these, update this page in the same pull request.

## Works

| Feature | How to use it |
|---|---|
| Find resources in one or more accounts | Your current credentials, `--accounts-file`, `--accounts-prompt` or `--cross-account-role` |
| Excel report | `--create-excel` writes `bom_output/multi_account_bom_<timestamp>.xlsx` |
| Word report | `--create-word` writes `bom_output/multi_account_bom_<timestamp>.docx` |
| Report layouts and tag columns | `--template` with a [report template](../templates/index.md) |
| Tag-policy checks | `--template` with a tag-policy template: adds a Tag Compliance sheet, a Word section and a JSON file |
| Fail a CI job on tag problems | A config template with `fail_on_tag_violations: true` (exit code 3) |
| Read-only guard | Always on. Every AWS call that is not a read is blocked before it is sent. |
| Audit of AWS calls | `--audit-output audit.json` lists every AWS operation the run called |
| Check operations against the guard | `--validate-operations ec2:DescribeInstances s3:PutObject` |
| Upload reports to S3 | `--s3-bucket` (server-side encrypted; the run fails if an upload fails) |
| Credential check | `--validate-credentials` |
| Region filter | `--account-regions us-east-1,eu-west-1` |
| Snapshots of each run | Saved in `bom_output/state/` |
| Private output files | Reports, snapshots and logs are created readable by your user only |

## Partly working

| Feature | What actually happens |
|---|---|
| `--account-services`, `--account-tags` | Applied in one discovery path only, so resources from other services, or with other tags, can still appear. |
| Change reports between runs | `changelog_<timestamp>.md` is written from the second run on, but it compares the newest snapshot with itself, so it always reports 0 changes. See [Track changes between runs](../guides/track-changes.md). |
| Discovery coverage | In our offline tests, EC2 instances did not appear (volumes did), and Lambda and DynamoDB tags were not collected. Not yet checked against a real AWS account. |
| Error messages for AWS failures during discovery | If Cost Explorer is denied or a call fails, the run continues and the report has less data. The reason only shows with `--debug`. |

## Accepted but with no effect

| Flag | What actually happens | What to do instead |
|---|---|---|
| `--tag-mappings`, `--service-descriptions` | The files are checked and loaded, but a bug stops the columns and descriptions reaching the report. | Use a report template's `tag_columns`. |
| `--enable-network-analysis`, `--enable-security-analysis` | No network or security sheets are added to the reports. | See [Network and security analysis](../guides/network-and-security-analysis.md). |
| `--generate-changelog` | Changelogs are always written; the flag cannot turn them off. | Use `--disable-state-management`. |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Kept so old commands still run. The read-only guard is always on. | Nothing to do. |

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

## Costs

Each run calls the Cost Explorer `GetCostAndUsage` API, and AWS charges per
Cost Explorer request. See the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Other calls are free, but large accounts mean many requests and possible
throttling (AWS slowing down your requests).

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

The template tests (`tests/unit/templating`, `tests/integration/templating`)
all pass. The rest of the suite still has older failing tests that no longer
match the code; they are being fixed.
