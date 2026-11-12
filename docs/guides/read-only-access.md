---
title: Set up read-only access
description: Give InvenTag a least-privilege, read-only AWS identity with IAM Identity Center or an IAM role, and check that it cannot change anything.
sidebar_position: 2
slug: /user-guides/production-safety
---

# Set up read-only access

**Who this is for:** whoever creates the AWS identity that InvenTag runs as.

**What you can do after reading:** create a read-only identity for InvenTag
and confirm it cannot change your resources.

## Why this matters

InvenTag only needs to read. Its discovery code calls `List*`, `Describe*`
and `Get*` APIs and Cost Explorer. On the current release, nothing inside
InvenTag blocks a write call at runtime, so the IAM policy is what keeps your
accounts safe. Give InvenTag nothing more than it needs.

## Option 1: AWS managed ReadOnlyAccess plus three extras (simplest)

1. Attach the AWS managed policy `ReadOnlyAccess`.
2. Add this inline policy for the calls that `ReadOnlyAccess` may not cover:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvenTagExtras",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "ce:GetCostAndUsage",
        "ec2:DescribeRegions"
      ],
      "Resource": "*"
    }
  ]
}
```

| Action | Why InvenTag needs it |
|---|---|
| `tag:GetResources` | Finds tagged resources through the Resource Groups Tagging API (its IAM prefix is `tag`). |
| `ce:GetCostAndUsage` | Finds services that have spend. AWS charges per request. |
| `ec2:DescribeRegions` | Lists the regions enabled in the account. |

Add `pricing:GetProducts` only if you use `--enable-cost-analysis`.

`ReadOnlyAccess` is broad: it can read data such as S3 object listings and
some configuration that InvenTag never looks at. If that is too much for your
organisation, use option 2.

## Option 2: the narrower policy in the repository

`config/defaults/iam-policy-read-only.json` lists specific read actions for the
services InvenTag knows. Before you use it:

- Add `ce:GetCostAndUsage` (it is missing from the file today).
- Remove the `OptionalS3ReportUpload` statement unless you upload reports
  yourself. The CLI does not upload on the current release.

Where an action is missing, discovery carries on and that detail is left
empty.

## With IAM Identity Center (SSO)

Create a permission set that holds the policy, then assign it to every account
you want to scan:

```bash
aws sso-admin create-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --name InvenTagReadOnly \
  --description "Read-only access for InvenTag"

aws sso-admin attach-managed-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

aws sso-admin put-inline-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --inline-policy file://inventag-extras.json
```

Then sign in with `aws sso login --profile <profile>` and run InvenTag with
`AWS_PROFILE=<profile>`.

## With an IAM role in each account

For scans across many accounts, create a role with the same name, for example
`InvenTagReadOnly`, in every account. Attach the policy, and let only your
scanning identity assume it. A trust policy for that looks like this:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::999999999999:role/InvenTagScanner" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Replace `999999999999:role/InvenTagScanner` with the identity that runs
InvenTag. The scanning identity itself needs only `sts:AssumeRole` on those
roles.

## Check that it cannot write

Use the IAM policy simulator to confirm a write is denied, for example:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Both should show `implicitDeny` or `explicitDeny`.

## After a security incident

If you suspect your credentials or a dependency were compromised, rotate or
revoke the credentials InvenTag used, check AWS CloudTrail for calls you do
not expect from that identity, and keep the identity read-only. More on the
[Security](../security/index.md) page.

## Next steps

- [IAM permissions reference](../reference/iam-permissions.md)
- [Scan several accounts](./scan-multiple-accounts.md)
