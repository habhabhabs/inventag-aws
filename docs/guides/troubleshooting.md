---
title: Fix common problems
description: Solutions for the InvenTag errors people hit most - credentials, permissions, templates, slow scans and empty reports.
sidebar_position: 8
---

# Fix common problems

**Who this is for:** something went wrong and you want the quickest fix.

**What you can do after reading:** recognise the common errors and fix them.

Add `--verbose` to see each step. Avoid `--debug` with temporary credentials:
the log contains your session token.

## Credentials

| What you see | Cause | Fix |
|---|---|---|
| `No AWS credentials found!` | No credentials in the environment | Run `aws sso login --profile <name>` and set `AWS_PROFILE`, or run `aws configure`. |
| `Issue: Invalid or expired security token` | Expired SSO session or temporary keys | Log in again: `aws sso login --profile <name>`. |
| `Issue: AWS SSO token needs refresh` | Expired SSO token | `aws sso login --profile <name>`. |
| Every account reported invalid by `--validate-credentials` | A known bug | Use `aws sts get-caller-identity` instead. |
| `Role assumption failed` | The role's trust policy does not allow your identity, or the ARN is wrong | Check the trust policy and the ARN. Pass a full role ARN to `--cross-account-role`. |

## Permissions

| What you see | Fix |
|---|---|
| `AccessDenied` for `ce:GetCostAndUsage` | Add `ce:GetCostAndUsage` to the policy, or ignore it: discovery continues without billing data. |
| A service is missing from the report | The identity may lack its `List*`/`Describe*` permission. Run with `--verbose` and look for `AccessDenied`. |
| Columns are empty for some resources | A `Describe*` or `Get*` call was denied. See [IAM permissions](../reference/iam-permissions.md). |

## Templates

| What you see | Fix |
|---|---|
| `no template named 'x'` | Run `./inventag.sh templates list`. Check the file is in `.inventag/templates/` of the folder you run from, and that its file name matches. |
| `unknown field 'x'; did you mean 'y'?` | Fix the spelling on the line shown. |
| `must be text, got a number. Put account IDs in quotes` | Write `account_id: "012345678901"`. |
| `must stay inside the template's folder` | Move the referenced file next to the template, or into a subfolder. |
| `templates must not contain credentials` | Remove access keys; use `profile_name` or `role_arn`. |
| `--template given two report templates` | Give at most one template of each kind. |
| Exit code 3 | Not an error in InvenTag: the tag policy found violations and `fail_on_tag_violations` is on. Open the Tag Compliance sheet. |

## Slow or large scans

- Limit regions: `--account-regions us-east-1,eu-west-1`.
- Scan fewer accounts at once if you are throttled:
  `--max-concurrent-accounts 2`.
- Give big accounts more time: `--account-processing-timeout 3600`.

## Reports look wrong

| What you see | Fix |
|---|---|
| Very wide sheets with `raw_data.*` columns | That is the default layout. Use `--template standard-bom`. |
| Tag mappings or service descriptions do not appear | A known bug: they are loaded but not applied. Use a report template's `tag_columns`. |
| No network or security sheets | A known limitation. See [Network and security analysis](./network-and-security-analysis.md). |
| The change report says 0 changes | A known bug. See [Track changes between runs](./track-changes.md). |

## Install problems

See [Install InvenTag](../getting-started/installation.md#fix-install-problems).

## Still stuck?

Open an [issue](https://github.com/habhabhabs/inventag-aws/issues) with the
command you ran, the InvenTag version (`git describe --tags`) and the error.
Remove account IDs and names you don't want to share, and never paste
credentials or `--debug` logs.
