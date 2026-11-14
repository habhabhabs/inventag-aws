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

InvenTag only needs to read. It has its own read-only guard, which blocks
every AWS call that is not a read before it is sent. Your IAM policy is a
second, independent safety net: if a bug ever got past the guard, AWS would
still refuse the call. Give InvenTag nothing more than it needs.

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

InvenTag also calls `account:ListRegions`, but only when `ec2:DescribeRegions`
fails, to read the enabled regions. Add it if you want that fallback.

Add `pricing:GetProducts` only if you use `--enable-cost-analysis` (it also
calls `cloudwatch:GetMetricStatistics`, which `ReadOnlyAccess` covers), and
`s3:PutObject` on your reports bucket if you use `--s3-bucket`.

`ReadOnlyAccess` is broad: it can read data such as S3 object listings and
some configuration that InvenTag never looks at. If that is too much for your
organisation, use option 2.

## Option 2: the narrower policy in the repository

`config/defaults/iam-policy-read-only.json` lists 122 specific read actions,
including `tag:GetResources`, `ce:GetCostAndUsage` and `pricing:GetProducts`,
and `apigateway:GET` for API metadata only (not API keys). It is generated
from the same list the code uses, so it matches what InvenTag calls. It
includes the actions for the services that InvenTag lists with its own calls,
and `ec2:DescribeRouteTables` and `ec2:DescribeNetworkInterfaces` for the
[network and security analysis](./network-and-security-analysis.md#permissions).
If you copied an older version of the file, copy it again. A missing action
does not stop the run, but that service or detail is missing.

Its `OptionalS3ReportUpload` statement allows `s3:PutObject` with server-side
encryption, for `--s3-bucket`. Replace `YOUR-REPORTS-BUCKET-NAME` with your
bucket, or remove the statement if you don't upload reports.

Where a listing action is missing, InvenTag logs one warning for that service
and carries on without its resources:

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Where an action for a detail of a resource is missing, discovery carries on
and leaves that detail empty.

## What the read-only guard blocks

InvenTag checks every AWS call in the process before it is sent. It allows
only operations whose names start with `List`, `Describe`, `Get`, `Head`,
`Lookup`, `Search` or `BatchGet`, plus `sts:AssumeRole` to reach other
accounts. It cannot be turned off.

Some operations look like reads but return secrets or customer data. The guard
blocks them as well, so a broad policy cannot expose them through InvenTag.
Examples: `secretsmanager:GetSecretValue`, `ssm:GetParameter`,
`s3:GetObject`, `dynamodb:GetItem`, `lambda:GetFunction` (it returns a
download link for the code), `cloudformation:GetTemplate`,
`ec2:GetLaunchTemplateData`, `glue:GetConnection` and Athena query results.
It also blocks API keys with their values and `ec2:DescribeInstanceAttribute`
for user data, and it checks presigned URLs and database authentication tokens
by the same rules. Check a name with
`inventag --validate-operations <service>:<Operation>`.

IAM Identity Center (SSO) and web-identity profiles work under the guard.
The guard lets the sign-in step exchange a token for credentials, and nothing
else.

Two functions in the Python library can write to AWS when you call them from
your own code. The `inventag` command never calls them, and the guard blocks
them in a command run. `CredentialManager.setup_cross_account_roles()` creates
IAM roles and runs only with `allow_iam_writes=True`. The S3 lifecycle helper
changes bucket rules and runs only with `allow_bucket_writes=True`.

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

Use the IAM policy simulator to confirm a write is denied:

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Both should show `implicitDeny` or `explicitDeny`.

You can also ask InvenTag's guard which operations it would allow (sample
output from an offline run):

<!-- BEGIN EXAMPLE OUTPUT: validate-operations -->

```text title="Output"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
```

```bash title="Terminal"
echo $?
```

```text title="Output"
1
```

<!-- END EXAMPLE OUTPUT: validate-operations -->

To see what a real run called, add `--audit-output audit.json`. An excerpt
from an offline run (sample data):

<!-- BEGIN EXAMPLE OUTPUT: audit-json -->

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 96,
  "allowed_calls": 96,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

<!-- END EXAMPLE OUTPUT: audit-json -->

## After a security incident

If you suspect your credentials or a dependency were compromised, rotate or
revoke the credentials InvenTag used, check AWS CloudTrail for calls you do
not expect from that identity, and keep the identity read-only. More on the
[Security](../security/index.md) page.

## Next steps

- [IAM permissions reference](../reference/iam-permissions.md)
- [Scan several accounts](./scan-multiple-accounts.md)
