---
title: Fix common problems
description: The InvenTag errors people hit most - credentials, permissions, regions, throttling, templates and configuration files - with the real messages and how to fix them.
sidebar_position: 8
---

# Fix common problems

**Who this is for:** something went wrong and you want the quickest fix.

**What you can do after reading:** recognise the message you see and fix its
cause.

The messages below are real InvenTag output from offline runs (sample data).
Where an AWS error can't be produced offline, such as an expired token, we
simulated the exact AWS error response and recorded how InvenTag reported it.
Those blocks are marked "simulated AWS error response".

Add `--verbose` to see each step, or `--debug` to see every AWS call. Debug
logs mask secrets, but treat them as sensitive.

## Credentials

### No credentials found

<!-- BEGIN EXAMPLE OUTPUT: error-no-credentials -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ No AWS credentials found!
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Set AWS environment variables:
inventag.cli.main - ERROR -       export AWS_ACCESS_KEY_ID=your-key
inventag.cli.main - ERROR -       export AWS_SECRET_ACCESS_KEY=your-secret
inventag.cli.main - ERROR -    3. Use IAM roles if running on EC2/ECS/Lambda
inventag.cli.main - ERROR -    4. Use --accounts-prompt for interactive setup
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: error-no-credentials -->

**Fix:** sign in, for example `aws sso login --profile my-readonly` and
`export AWS_PROFILE=my-readonly`, then check with
`aws sts get-caller-identity`.

### Expired or invalid credentials

<!-- BEGIN EXAMPLE OUTPUT: error-expired-token -->

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ AWS credential validation failed!
inventag.cli.main - ERROR -    Issue: Invalid or expired security token
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Check if your access keys are correct
inventag.cli.main - ERROR -    3. If using temporary credentials, they may have expired
inventag.cli.main - ERROR -    4. If using AWS SSO, run 'aws sso login'
inventag.cli.main - ERROR -
inventag.cli.main - ERROR - 💡 Quick diagnostic commands:
inventag.cli.main - ERROR -    aws configure list          # Show current config
inventag.cli.main - ERROR -    aws sts get-caller-identity # Test credentials
inventag.cli.main - ERROR -    aws configure               # Set up new credentials
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: error-expired-token -->

**Fix:** sign in again (`aws sso login --profile <name>`), or refresh your
temporary keys. If you use access keys, check them with `aws configure list`.

### A role cannot be assumed

**What you see:** the account is listed as failed, with a line such as
`Role assumption failed for account 123456789012: ...` in the log.

**Fix:** check the role ARN, and check that the role's trust policy allows
your identity. InvenTag does not fall back to other credentials, so that
account is skipped until it works.

### A role name without an accounts file

<!-- BEGIN EXAMPLE OUTPUT: bare-role -->

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
$ echo $?
2
```

<!-- END EXAMPLE OUTPUT: bare-role -->

**Fix:** pass the full role ARN, or add `--accounts-file` with the account
IDs.

## Permissions

### Cost Explorer access denied

InvenTag carries on without billing data and the run succeeds, so the problem
is easy to miss. It only shows with `--debug`:

<!-- BEGIN EXAMPLE OUTPUT: error-access-denied-ce -->

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0

$ # the same run with --debug, lines that mention AccessDeniedException
Billing discovery failed: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

<!-- END EXAMPLE OUTPUT: error-access-denied-ce -->

**Fix:** add `ce:GetCostAndUsage` to the policy, or accept that billing data
is missing.

### A service or column is empty

**Cause:** the identity lacks a `List*`, `Describe*` or `Get*` permission for
that service. Discovery carries on without it.

**Fix:** use the policy in `config/defaults/iam-policy-read-only.json`, which
covers every call InvenTag makes. See [IAM permissions](../reference/iam-permissions.md).

### Blocked by the read-only guard

**What you see:** `Read-only guard blocked <service>:<Operation>` in the log.

**Cause:** a call that is not a read reached the guard. InvenTag itself
doesn't make such calls, so this usually means custom code or a plug-in.

**Fix:** check which operation it was with
`./inventag.sh --validate-operations <service>:<Operation>`. The guard cannot
be turned off.

## Regions

### A region is not enabled for the account

<!-- BEGIN EXAMPLE OUTPUT: error-region-disabled -->

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0
```

<!-- END EXAMPLE OUTPUT: error-region-disabled -->

The run carries on with the regions that work.

**Fix:** remove the region from `--account-regions`, or enable it for the
account in the AWS console (Account settings, AWS Regions).

## Throttling

When too many requests arrive at once, AWS slows them down. The AWS SDK
(software development kit) retries automatically. We have not tested how
InvenTag reports throttling that persists after retries.

**Fix:** scan fewer accounts at once (`--max-concurrent-accounts 2`), scan
fewer regions, or give big accounts more time
(`--account-processing-timeout 3600`).

## Templates and configuration files

### Invalid template

<!-- BEGIN EXAMPLE OUTPUT: error-bad-template -->

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: error-bad-template -->

**Fix:** correct the field on the line shown. Run
`./inventag.sh templates validate <file>` to check without scanning.

### Unknown template name

<!-- BEGIN EXAMPLE OUTPUT: error-unknown-template -->

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: error-unknown-template -->

**Fix:** check the spelling with `./inventag.sh templates list`. Project
templates must be in `.inventag/templates/` in the folder you run from.

### Invalid accounts file

<!-- BEGIN EXAMPLE OUTPUT: error-bad-accounts -->

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - Invalid accounts configuration:
inventag.cli.main - ERROR -   - Account 1: 'account_id' must be a non-empty string
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: error-bad-accounts -->

**Fix:** put account IDs in quotes (`account_id: "123456789012"`), and give
each account `profile_name`, `role_arn` or access keys.

### Other template messages

| Message contains | Fix |
|---|---|
| `did you mean '...'?` | Fix the spelling on the line shown. |
| `Put account IDs in quotes` | Write `account_id: "012345678901"`. |
| `must stay inside the template's folder` | Move the referenced file next to the template, or into a subfolder. |
| `templates must not contain credentials` | Remove access keys; use `profile_name` or `role_arn`. |
| `--template given two report templates` | Give at most one template of each kind. |

## Flags that stop the run

Exit code 2 with `not implemented yet` means the flag was removed in v5. See
[Upgrade from v4 to v5](../getting-started/upgrade-to-v5.md#flags-that-now-stop-with-an-error).

## Exit code 3

Not an error in InvenTag. A tag policy found violations and the config
template has `fail_on_tag_violations: true`. Open the Tag Compliance sheet or
the JSON file to see which resources.

## Reports look wrong

| What you see | Cause and fix |
|---|---|
| Very wide sheets with `raw_data.*` columns | That is the default layout. Use `--template standard-bom`. |
| Tag mappings or service descriptions are missing | A known bug: they are loaded but not applied. Use a report template's `tag_columns`. |
| No network or security sheets | A known limitation. See [Network and security analysis](./network-and-security-analysis.md). |
| The change report says 0 changes | A known bug. See [Track changes between runs](./track-changes.md). |
| Another user can't open `bom_output/` | Since v5, output files are private to the user who ran InvenTag. Share them on purpose. |

## Install problems

See [Install InvenTag](../getting-started/installation.md#fix-install-problems).

## Still stuck?

Open an [issue](https://github.com/habhabhabs/inventag-aws/issues) with the
command you ran, the version (`git describe --tags`) and the message. Remove
account IDs and names you don't want to share. Never paste credentials.
