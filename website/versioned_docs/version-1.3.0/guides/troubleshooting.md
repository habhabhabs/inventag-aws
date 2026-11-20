---
title: Fix common problems
description: The InvenTag errors people hit most (credentials, permissions, regions, throttling, templates, config files), with the real messages and how to fix them.
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

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ No AWS credentials found!
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Set AWS environment variables:
inventag.cli.main - ERROR -       export AWS_ACCESS_KEY_ID=your-key
inventag.cli.main - ERROR -       export AWS_SECRET_ACCESS_KEY=your-secret
inventag.cli.main - ERROR -    3. Use IAM roles if running on EC2/ECS/Lambda
inventag.cli.main - ERROR -    4. Use --accounts-prompt for interactive setup
inventag.cli.main - ERROR -    5. If you use AWS SSO, run 'aws sso login --profile <name>' and set AWS_PROFILE=<name>, or name the profile in an accounts file
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
```

```bash title="Terminal"
echo $?
```

```text title="Output"
1
```

<!-- END EXAMPLE OUTPUT: error-no-credentials -->

**Fix:** sign in, for example `aws sso login --profile my-readonly` and
`export AWS_PROFILE=my-readonly`, then check with
`aws sts get-caller-identity`.

Not verified against the AWS CLI: the commands in this fix.

### Expired or invalid credentials

<!-- BEGIN EXAMPLE OUTPUT: error-expired-token -->

```text title="Output (simulated AWS error response)"
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
```

```bash title="Terminal"
echo $?
```

```text title="Output (simulated AWS error response)"
1
```

<!-- END EXAMPLE OUTPUT: error-expired-token -->

**Fix:** sign in again (`aws sso login --profile <name>`), or refresh your
temporary keys. If you use access keys, check them with `aws configure list`.

Not verified against the AWS CLI: the commands in this fix.

### A role cannot be assumed

**What you see:** this in the log, and a report that lacks the account:

```text
inventag.core.cloud_bom_generator.CloudBOMGenerator - ERROR - Failed to establish context for account 999999999999: Role assumption failed for account 999999999999: An error occurred (AccessDenied) when calling the AssumeRole operation: ...
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Skipping account 999999999999 due to invalid session
```

If other accounts worked, InvenTag still writes their report and **exits with
code 0**, or with code 5 if you pass `--fail-on-account-error`. The `Summary`
sheet and the Word report have a "Run notes" section that names the account,
and the log ends with this list:

```text
1 of 2 account(s) finished and were saved. Run the same command with --resume within 24 hours to scan only the other 1.
1 account(s) were not scanned, or only partly. The report does not include them:
  - 222222222222 (Dev): Context establishment failed: Role assumption failed for account 222222222222: ...
```

If every account fails, it exits with code 1 and writes no report:
`Resource discovery failed for all 1 configured account(s); no report was
generated`. (Message text from an offline run with a simulated AWS error.)

**Fix:** check the role ARN, and check that the role's trust policy allows
your identity. InvenTag does not scan the account with credentials that belong to another account, so that account is skipped until the role works. Then run the same command with `--resume`
to scan only the accounts that are missing.

### A profile that needs an MFA code, without a terminal

When the profile (the default one, or one named in an accounts file) has
`mfa_serial` and InvenTag runs without a terminal (a CI job, a pipe, a
scheduled task), the run stops at once with a message instead of waiting for
the code. For the default credentials:

```text
❌ Profile 'mfa1' needs an MFA code, and there is no terminal to type it.
   Run InvenTag in a terminal, or get temporary credentials first and set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_SESSION_TOKEN:
   aws sts get-session-token --serial-number <MFA device ARN> --token-code <code>
```

For an accounts-file entry, the account fails with `Profile 'mfa1' for account
123456789012 needs an MFA code, and there is no terminal to type it in. ...`
and the other accounts are scanned. Exit code 1 when no account could be
used. `--validate-credentials` checks the same way. With a terminal, the code
is asked for as before. Not verified against real AWS: a real MFA device.

**Fix:** run InvenTag in a terminal, or use temporary credentials from
`aws sts get-session-token`.

### A role name without an accounts file

<!-- BEGIN EXAMPLE OUTPUT: bare-role -->

```text title="Output"
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
```

```bash title="Terminal"
echo $?
```

```text title="Output"
2
```

<!-- END EXAMPLE OUTPUT: bare-role -->

**Fix:** pass the full role ARN, or add `--accounts-file` with the account
IDs.

## Permissions

### Cost Explorer access denied

InvenTag carries on without billing data and the run succeeds, so the problem
is easy to miss. A default run prints one warning that names the cause, and
`--debug` adds the AWS error text:

<!-- BEGIN EXAMPLE OUTPUT: error-access-denied-ce -->

```text title="Output (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

```bash title="Terminal"
echo $?
```

```text title="Output (simulated AWS error response)"
0
```

```bash title="Terminal"
# the same run with --debug, lines that mention AccessDeniedException
```

```text title="Output (simulated AWS error response)"
[AWS Account 123456789012 (moto)] inventag.discovery.inventory - WARNING - Cost Explorer was denied (AccessDeniedException), so billing data is missing and billing checks are skipped. Allow ce:GetCostAndUsage for this role.
[AWS Account 123456789012 (moto)] inventag.discovery.inventory - DEBUG - Cost Explorer detail: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
[AWS Account 123456789012 (moto)] inventag.discovery.comprehensive_discovery - DEBUG - Cost Explorer detail: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

<!-- END EXAMPLE OUTPUT: error-access-denied-ce -->

**Fix:** add `ce:GetCostAndUsage` to the policy, or accept that billing data
is missing.

### A service or column is empty

**Cause:** the identity lacks a `List*`, `Describe*` or `Get*` permission for
that service. For a listing call, InvenTag logs one warning for the service
and carries on without its resources:

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

For a call that fills in one detail of a resource (a bucket's location, a
function's configuration), discovery keeps the resource, leaves that detail
empty and says so in the report's "Run notes":

```text
Details of 5 resource(s) in account 111111111111 could not be read, so those rows have some fields missing: lambda GetFunctionConfiguration in us-east-1 (throttled, 2); s3 GetBucketLocation in us-east-1 (denied, 3).
```

The AWS error is logged at debug level. Run the matching AWS CLI call with
the same identity to check.

**Fix:** use the policy in `config/defaults/iam-policy-read-only.json`, which
covers every call InvenTag makes. See [IAM permissions](../reference/iam-permissions.md).

### Blocked by the read-only guard

**What you see:** `Read-only guard blocked <service>:<Operation>` in the log,
and an error that starts `Blocked AWS operation <service>:<Operation>`.

**Cause:** a call that is not a read, or a read that returns secrets or
customer data (for example `cloudformation:GetTemplate` or
`ssm:GetParameter`), reached the guard. This should not happen in a normal run. If it does, InvenTag logs one error line
that names the blocked operation and says it is a defect in InvenTag (the
report's "Run notes" say it too when the block happened during the scan), and
the run still exits with code 0. Please open an issue with the operation name.
See
[What the read-only guard blocks](./read-only-access.md#what-the-read-only-guard-blocks).

**Fix:** check which operation it was with
`inventag --validate-operations <service>:<Operation>`. The guard cannot
be turned off.

## Regions

### A region is not enabled for the account

<!-- BEGIN EXAMPLE OUTPUT: error-region-disabled -->

```text title="Output (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
inventag - WARNING - Notes about this run:
inventag - WARNING -   - Regions skipped in account 123456789012 because the region check (ec2:DescribeRegions) was denied or failed there: ap-east-1.
```

```bash title="Terminal"
echo $?
```

```text title="Output (simulated AWS error response)"
0
```

<!-- END EXAMPLE OUTPUT: error-region-disabled -->

The run carries on with the regions that work.

**Fix:** remove the region from `--account-regions`, or enable it for the
account in the AWS console (Account settings, AWS Regions).

Not verified against real AWS: the console path to enable a region.

### A region name is misspelled

A region name that fails the region check and that the installed boto3 does
not know, such as `us-east-9` in `--account-regions`, is named once with the
command that lists the valid ones:

```text
Region 'us-east-9' could not be checked and the installed boto3 does not know it: check its spelling in --account-regions or in the accounts file, or, if it is a new AWS region, upgrade boto3. To list the regions of your account, run: aws ec2 describe-regions --query 'Regions[].RegionName' --output text
```

The run exits with code 0. When other regions work, they are scanned, and the
"Run notes" say `Regions not scanned in account 123456789012 because their region check failed and the installed boto3 does not know them (a misspelled name, or a region newer than boto3): us-east-9.`
A region that boto3 does not know but that AWS answers for is scanned.

**Fix:** correct the region name.

### A region of another partition

A China (`cn-`) or GovCloud (`us-gov-`) region in `--account-regions` with
credentials of the commercial partition (or the other way round) is named
once:

```text
Region 'cn-north-1' is in the aws-cn partition, but the credentials of account 123456789012 are for the aws partition, so it cannot be scanned with them; scan it with credentials of that partition.
```

The region is still tried, and the run exits with code 0. The account check
(`sts:GetCallerIdentity`) uses the STS endpoint of the scanned partition.
Not verified against real AWS: GovCloud and China credentials.

**Fix:** scan that region in a separate run with credentials of its
partition.

### The list of regions cannot be read

If `ec2:DescribeRegions` fails, InvenTag asks `account:ListRegions`, and then
tries every region of the partition:

```text
ec2:DescribeRegions failed (An error occurred (UnauthorizedOperation) when calling the DescribeRegions operation: ...); trying account:ListRegions instead.
account:ListRegions failed (An error occurred (AccessDeniedException) when calling the ListRegions operation: ...).
Could not read the account's enabled regions. Trying all 34 regions of the aws partition known to botocore; regions the account has not enabled will fail the access check and be skipped. Use --account-regions to choose.
```

The access check of each region also uses `ec2:DescribeRegions`. If it is
denied in every region, InvenTag cannot tell which regions work:

```text
ec2:DescribeRegions is denied in every region, so region access cannot be checked; scanning all 34 regions.
```

The number of regions comes from the installed AWS SDK (botocore) and changes with its version.

**Fix:** allow `ec2:DescribeRegions`, or name the regions with
`--account-regions`.

## Throttling

When too many requests arrive at once, AWS slows them down. The AWS SDK
(software development kit) retries automatically, up to 10 attempts in total.
If a listing still fails after that, InvenTag logs a warning for the service
and region, and its resources there may be missing from the report:

```text
sqs list_queues in us-east-1 failed (ThrottlingException); its resources there may be incomplete.
```

**Fix:** scan fewer accounts at once (`--max-concurrent-accounts 2`), scan
fewer regions, or give big accounts more time
(`--account-processing-timeout 3600`).

Not verified against real AWS: fewer accounts or regions at once reduce throttling.

## Time limits and partial results

### An account runs out of time

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

The account counts as failed, but the resources found before the limit are in
the report, and the "Run notes" name the account. The other accounts are kept.
If no account finishes, InvenTag still writes the report, logs `No account
finished within its time limit (--account-processing-timeout)` and exits with
code 1. (Message text from an offline run with a 60-second limit.)

**Fix:** raise `--account-processing-timeout` (default 1800), scan fewer
regions or services, or scan fewer accounts at the same time. Run the same
command with `--resume` to scan only the accounts that did not finish.

### A slow Cost Explorer

With `--account-processing-timeout` under 1200 seconds, each Cost Explorer call
waits at most a fortieth of the limit, and at least 5 seconds, to connect and
to read, with two attempts. If it does not answer in time, the account is
still scanned and its resources are in the report. The "Run notes" say:

```text
Cost Explorer did not answer in time for account 123456789012, so its billing checks were skipped and services that only billing shows are not listed for it.
```

**Fix:** add `--no-billing-validation` to make no Cost Explorer calls, or
set `--account-processing-timeout` to 1200 or more.

### The run is stopped with Ctrl-C or SIGTERM

Ctrl-C and SIGTERM each print one line that says what was written:

```text
Stopped by the user (Ctrl-C). No report was written.
Terminated (SIGTERM). No report was written.
```

When a report file was already written, the line says
`1 report file(s) already written stay in <output folder>.` instead. Ctrl-C
exits with code 1. A SIGTERM ends the process by the signal after the line.

### Saved results are not reused

| Message | Meaning |
|---|---|
| `1 account(s) have saved results from an earlier run of this command that did not finish. They are scanned again; add --resume to reuse them.` | The saved results exist, but you did not pass `--resume`. |
| `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)` | The saved result is reused. The report's notes list the account and the scan time. |
| `inventag: error: --resume: needs state management ...` | State management is off. `--resume` with `--disable-state-management` stops with exit code 2. |

InvenTag reuses a saved result only when the command has the same accounts,
regions, services and filters, and the result is at most
`--resume-max-age-hours` old (default 24, at most 168). Otherwise it scans the
account again.

## Templates and configuration files

### Invalid template

<!-- BEGIN EXAMPLE OUTPUT: error-bad-template -->

```text title="Output"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
```

```bash title="Terminal"
echo $?
```

```text title="Output"
1
```

<!-- END EXAMPLE OUTPUT: error-bad-template -->

**Fix:** correct the field on the line shown. Run
`inventag templates validate <file>` to check without scanning.

### Unknown template name

<!-- BEGIN EXAMPLE OUTPUT: error-unknown-template -->

```text title="Output"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
```

```bash title="Terminal"
echo $?
```

```text title="Output"
1
```

<!-- END EXAMPLE OUTPUT: error-unknown-template -->

**Fix:** check the spelling with `inventag templates list`. Project
templates must be in `.inventag/templates/` in the folder you run from.

### Invalid accounts file

<!-- BEGIN EXAMPLE OUTPUT: error-bad-accounts -->

```text title="Output"
inventag - WARNING -    - Account 1: no credentials given; InvenTag will assume the --cross-account-role role (default InvenTagCrossAccountRole) in this account, or use the default credentials only if they belong to this account
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="Output"
1
```

<!-- END EXAMPLE OUTPUT: error-bad-accounts -->

**Fix:** put account IDs in quotes (`account_id: "123456789012"`), and give
each account `profile_name`, `role_arn` or access keys.

The file itself can also be wrong. Each of these stops with exit code 1:

| Message contains | Cause |
|---|---|
| `the file is empty` | The file has no content. |
| `duplicate key 'accounts'` | A key is written twice. The message gives the line, for example `accounts file accounts.yaml:3: duplicate key 'accounts'`. |
| `the top level must be a mapping of key: value pairs, but the file holds a list` | The file starts with a list. Put the list under `accounts:`. |
| `unsupported file type '.txt'. Use .json, .yaml or .yml` | The file name has another extension. |
| `the file is ... bytes; the maximum is 1048576 bytes` | The file is larger than 1 MiB. |
| `Accounts file not found` | The path is wrong. |

InvenTag warns when a file with `secret_access_key` or `session_token` can be
read by other users: `<file> contains secret access keys and other users can
read it (mode 0644). Run: chmod 600 <file>.`

### Other template messages

| Message contains | Fix |
|---|---|
| `did you mean '...'?` | Fix the spelling on the line shown. |
| `Put account IDs in quotes` | Write `account_id: "012345678901"`. |
| `must stay inside the template's folder` | Move the referenced file next to the template, or into a subfolder. |
| `templates must not contain credentials` | Remove access keys; use `profile_name` or `role_arn`. |
| `--template given two report templates` | Give at most one template of each kind. |

## Flags that stop the run

Some options stop the run with exit code 2 and a message `inventag: error: ...`
before anything is scanned:

- `--compliance-standard` says it is not implemented yet.
- `--disable-production-safety` says the read-only guard cannot be disabled.
- Options that cannot work together:

```text
inventag: error: --accounts-file and --accounts-prompt: give one of them, not both.
inventag: error: --cross-account-role: a full role ARN names one account and cannot be combined with --accounts-file or --accounts-prompt. Give a role name to use in every account, or put role_arn in the accounts file.
inventag: error: --s3-kms-key-id: needs --s3-encryption aws:kms.
inventag: error: --resume: needs state management (saved results live in the state folder); remove --disable-state-management.
```

A value that is out of range stops with exit code 1 and names the option:
`--max-concurrent-accounts must be a positive integer`,
`--account-processing-timeout must be at least 60 seconds`,
`--resume-max-age-hours must be above 0 and at most 168`. A value that is not
a number for `--state-retention-days` or `--state-max-snapshots` stops with
exit code 2: `expected a whole number or 'none'`.

A path for `--audit-output`, `--log-file` or `--output-directory` that cannot
be written stops the run at the start, before any AWS call, with a message that
names the option and exit code 1.

See [Feature status](../getting-started/status.md).

## Exit code 3

Not an error in InvenTag. A tag policy found violations and the config
template has `fail_on_tag_violations: true`. Open the Tag Compliance sheet or
the JSON file to see which resources.

## Exit codes 4, 5 and 6

These exist only when you ask for them.

- **4:** a security group rule open to the internet is at or above
  `--risk-threshold`. The log lists the rules. See
  [Network and security analysis](./network-and-security-analysis.md#fail-a-pipeline-on-risky-rules).
- **5:** `--fail-on-account-error` is set and an account could not be scanned
  or ran out of time. The log says `N account(s) failed and
  --fail-on-account-error is set (exit code 5)`.
- **6:** `--fail-if-empty` is set and there is nothing to report. The log says
  `No resources in the report and --fail-if-empty is set (exit code 6)`.

The reports are written first. If more than one applies, 5 comes first, then
6, then 3 and 4. See [Run InvenTag in CI/CD](./run-in-ci.md#exit-codes).

## Reports look wrong

| What you see | Cause and fix |
|---|---|
| Very wide sheets with `raw_data.*` columns | That is the default layout. Use `--template standard-bom`. |
| Tag mapping columns are missing | Tag mappings add columns only to the default workbook. With `--template`, use `tag_columns`. See [Configuration files](../reference/configuration-files.md#tag-mappings). |
| A custom service description is ignored | Your entry replaces the built-in description; services with no entry in your file keep the built-in text. See [Configuration files](../reference/configuration-files.md#service-descriptions). |
| No network or security sheets | Add `--enable-network-analysis` or `--enable-security-analysis`, and make sure the scan found VPCs or security groups. The flags add nothing with `--template`. See [Network and security analysis](./network-and-security-analysis.md). |
| IAM, S3, CloudFront or Route 53 resources are missing | `--account-services` or `--account-tags` removed them, or the identity lacks the permission (look for one warning per service in the log). The region list does not matter: global services are always read from the home region (`us-east-1`, or `cn-north-1` in China and `us-gov-west-1` in GovCloud). |
| A resource shows no tags, or appears twice | Run with `--debug` and compare the ARN column with the ARN in the AWS console. Report a mismatch as an issue with the service and resource type. |
| No report file, and the exit code is 0 | The scan found nothing, or `--account-services` or `--account-tags` removed everything. Check the log for `No resources to report`. With `--template`, InvenTag writes a report that lists no resources instead. |
| An account is missing from the report | Its credentials or role failed, or it ran out of time. The "Run notes" on the `Summary` sheet name it. See [A role cannot be assumed](#a-role-cannot-be-assumed) and [An account runs out of time](#an-account-runs-out-of-time). |
| The change report is missing | The first run writes none. It also needs state management and delta detection to be on. See [Track changes between runs](./track-changes.md). |
| `Skipped unreadable snapshot 20261113_222847: Snapshot ... is corrupt or truncated (...). The file was not changed or deleted` | The latest snapshot is damaged, so InvenTag compares with the one before it. The file stays in `state/`. Delete it if you do not need it. |
| `Account 222222222222 left out of the comparison: the previous run could not scan it` | One of the two runs could not scan that account. The change report names it under `accounts_not_compared`. |
| `Excel sheet name 'x' is not allowed or is already used; the sheet is called 'y'` | Excel does not allow some characters in sheet names (they become `-`), and names must be unique and at most 31 characters. The report is still complete. |
| `Nothing to upload to s3://<bucket>/<prefix>/: the run wrote no report file because there are no resources to report.` | `--s3-bucket` was given, but the scan found no resources, or the filters removed them all, so no file was written. The run exits with code 1. Check the scan with the "No report file" row above. |
| `Reports written; the state snapshot or the change report had a problem (see the notes below)` | The state snapshot or its list could not be saved, or the change report failed. The notes after the summary name the problem and the folder to check. The run exits with code 0. |
| With `--template`, one report format is missing | A format that cannot be written does not stop the other formats. The log names the failed format, the "Run notes" of the written files say it, and the run exits with code 1. |
| Another user can't open `bom_output/` | Output files are private to the user who ran InvenTag. Share them on purpose. |

Not verified against Microsoft Excel: the sheet name rules.

## Noise you can ignore

Some messages look like errors but change nothing in your report.

| Message | Why you can ignore it |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'`` (with `--service-descriptions`) | The VPC description template wants a field the resource does not have. The report is not affected. |
| `No account specification method provided. Using default AWS credentials.` | You did not name an account, so InvenTag used your current credentials. This is the normal case. |
| `Cross-account role not usable for account ... trying default credentials` | InvenTag could not assume the role in that account and tried your own credentials. It uses them only if they belong to that account; otherwise the account is skipped. Logged once per account, only with `--verbose`. |

## Install problems

See [Install InvenTag](../getting-started/installation.md#fix-install-problems).

## Still stuck?

Open an [issue](https://github.com/habhabhabs/inventag-aws/issues) with the
command you ran, the version (`inventag --version`) and the message. Remove
account IDs and names you don't want to share. Never paste credentials.
