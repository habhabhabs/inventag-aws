---
title: Upgrade from v4 to v5
description: Every change in InvenTag v5 that can break a v4 command, script or IAM policy, with before-and-after commands and what to do about each one.
sidebar_position: 4
---

# Upgrade from v4 to v5

**Who this is for:** you run InvenTag v4 (any 4.x release) in a script, a
scheduled job or a CI pipeline.

**What you can do after reading:** find every change that affects you and fix
it before you switch to v5.

v5 is a major release because some commands that used to "work" now stop with
an error. In v4 those flags were accepted and then quietly ignored, so your
report never did what the command said. v5 tells you.

## Checklist

1. [Use Python 3.11 or later](#python-311-or-later).
2. [Remove flags that now stop with an error](#flags-that-now-stop-with-an-error).
3. [Check how you use `--cross-account-role`](#--cross-account-role-takes-a-name-or-an-arn).
4. [Expect failed sign-ins to stop the run](#no-silent-fallback-to-other-credentials).
5. [Update your IAM policy](#iam-policy-changes).
6. [Check who can read the output files](#output-files-are-private).
7. [If you passed `--s3-bucket`, check the upload permissions](#--s3-bucket-now-uploads).
8. Try the new [templates](../templates/index.md). They are optional.

## Python 3.11 or later

Python 3.10 reached its end of life in October 2026 and gets no more security
fixes. Use Python 3.11 or later for v5.

```bash title="Before (v4)"
python3.9 -m venv .venv
```

```bash title="After (v5)"
python3.12 -m venv .venv      # any version from 3.11 up
```

:::note What happens on an older Python
`pip install inventag-aws` refuses to install on an older Python, and
`python inventag_cli.py` on an older Python stops with a message. The package metadata (`requires-python`) says
`>=3.11`.
:::

## The read-only guard is always on

v4 had `--enforce-read-only` and similar flags, but nothing used them. In v5
a guard checks every AWS call before it is sent and blocks anything that is
not a read. It also blocks reads that return secrets or data, such as
`secretsmanager:GetSecretValue` or `s3:GetObject`. You can't turn it off.

You usually don't need to change anything. To check an operation against the
guard:

```bash title="After (v5)"
inventag --validate-operations ec2:DescribeInstances s3:PutObject secretsmanager:GetSecretValue
```

Sample output from an offline run:

<!-- BEGIN EXAMPLE OUTPUT: validate-operations -->

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: validate-operations -->

`--enable-production-safety`, `--enforce-read-only` and
`--security-validation` are still accepted, so old commands keep running.

## Flags that now stop with an error

These flags did nothing in v4. In v5 they stop the run with exit code 2
before anything is scanned.

| v4 flag | What to do in v5 |
|---|---|
| `--create-google-docs` | Remove it. Use `--create-excel` and import the file into Google Sheets. |
| `--per-account-reports` | Remove it. Run InvenTag once per account if you need separate reports. |
| `--compliance-standard ...` | Remove it. It never changed anything. Use a [tag-policy template](../guides/check-tag-compliance.md). |
| `--risk-threshold ...` | Remove it. |
| `--disable-production-safety` | Remove it. The read-only guard cannot be turned off. |

```bash title="Before (v4): ran, but ignored two flags"
inventag --create-excel --compliance-standard soc2 --per-account-reports
```

```bash title="After (v5)"
inventag --create-excel --template finops-cost-allocation
```

What v5 prints if you keep them:

<!-- BEGIN EXAMPLE OUTPUT: failing-flags -->

```text title="Terminal"
$ inventag --create-google-docs
inventag: error: --create-google-docs: Google Docs/Sheets output is not implemented yet (InvenTag has no Google API integration). Use --create-excel or --create-word.
(exit code 2)

$ inventag --per-account-reports
inventag: error: --per-account-reports: Per-account reports are not implemented yet; InvenTag writes one consolidated report. Run once per account to get separate reports.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

<!-- END EXAMPLE OUTPUT: failing-flags -->

## `--cross-account-role` takes a name or an ARN

In v4 the help said "role name", but a name never worked; only a full role
ARN (Amazon Resource Name) did. In v5:

- a **full role ARN** is assumed directly, as before;
- a **role name** is combined with each account ID in `--accounts-file`;
- a role name **without** `--accounts-file` stops with exit code 2.

```bash title="Before (v4): failed"
inventag --cross-account-role InvenTagReadOnly
```

```bash title="After (v5)"
inventag --cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly
# or, for every account listed in accounts.yaml:
inventag --accounts-file accounts.yaml --cross-account-role InvenTagReadOnly
```

What v5 prints for a bare name:

<!-- BEGIN EXAMPLE OUTPUT: bare-role -->

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
$ echo $?
2
```

<!-- END EXAMPLE OUTPUT: bare-role -->

## No silent fallback to other credentials

In v4, if a profile or role in your accounts file failed, InvenTag quietly
used your default credentials instead and could scan the wrong account under
the right name. In v5 that account fails with an error, and a session that
belongs to a different account than expected is refused.

What to do: if a v5 run reports an account as failed, fix that account's
`profile_name` or `role_arn`. Don't rely on the default credentials as a
backup.

## IAM policy changes

- `config/defaults/iam-policy-read-only.json` is now generated from an
  explicit list of 106 read actions. It now includes `ce:GetCostAndUsage` and
  `pricing:GetProducts`, so you no longer need to add them yourself.
- InvenTag now calls `lambda:GetFunctionConfiguration` instead of
  `lambda:GetFunction`. If you wrote your own policy, add the new action. You
  can remove `lambda:GetFunction`; it also exposed a download link for the
  function code.
- The optional `s3:PutObject` statement only allows uploads that use
  server-side encryption, which is what `--s3-bucket` does.
- The library function `setup_cross_account_roles()` no longer grants
  `config:*` and `resource-groups:*`, which included write actions. If you
  created roles with it in v4, replace their policy with the v5 file.

```bash title="Re-apply the v5 policy to an existing role"
aws iam put-role-policy \
  --role-name InvenTagReadOnly \
  --policy-name InvenTagReadOnly \
  --policy-document file://config/defaults/iam-policy-read-only.json
```

See [IAM permissions](../reference/iam-permissions.md) for what each part is for.

## Output files are private

v5 creates reports, snapshots, logs and other output files readable by your
user only, and new output folders accessible by your user only.

What to do: if another user or a later CI step that runs as a different user
reads `bom_output/`, give it access on purpose, for example by uploading the
files as a CI artifact or with `--s3-bucket`.

## `--s3-bucket` now uploads

In v4, `--s3-bucket` did nothing and the run still succeeded. In v5 it uploads
the reports with server-side encryption, and **the run fails if an upload
fails**. Public-read uploads are refused.

What to do: if you kept `--s3-bucket` in a v4 job, give the identity
`s3:PutObject` on that bucket, or remove the flag.

```bash title="After (v5)"
inventag --template standard-bom --create-excel \
  --s3-bucket acme-inventory-reports --s3-key-prefix inventag/
```

See [Upload reports to S3 on a schedule](../examples/scheduled-s3-upload.md).

## Smaller changes

| Change | Effect |
|---|---|
| `--validate-credentials` works | In v4 it reported every account as invalid. |
| `--audit-output FILE` works | Writes a JSON list of every AWS operation the run called. |
| `--debug` logs are redacted | Tokens, keys and signatures are masked. |
| `--accounts-prompt` hides secrets as you type | The secret key and session token are no longer shown on screen. |
| CSV values that start with `=`, `+`, `-` or `@`, and Excel values that start with `=`, are written as text | A tag value can no longer become a spreadsheet formula. |
| Encrypted credential files use stronger key derivation | Files written by v4 can still be read. |

## New in v5: templates

Templates let you reuse a report layout, a tag policy or a set of scan
settings:

```bash title="After (v5)"
inventag templates list
inventag --template executive-summary --create-word
```

Start with [Templates](../templates/index.md).
