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

InvenTag needs only read access, plus `s3:PutObject` if you upload reports with `--s3-bucket`. It has its own read-only guard, which blocks
every AWS call that is not a read before it is sent. Your IAM policy is a
second, independent safety net: if a bug ever got past the guard, AWS would
still refuse the call. Give InvenTag nothing more than it needs.

Not verified against real AWS: a read-only IAM policy refuses a call that gets past the guard.

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
| `ce:GetCostAndUsage` | Finds services that have spend. |
| `ec2:DescribeRegions` | Lists the regions enabled in the account. |

AWS charges for each Cost Explorer request: see [Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

InvenTag also calls `account:ListRegions`, but only when `ec2:DescribeRegions`
fails, to read the enabled regions. Add it if you want that fallback.

Add `pricing:GetProducts` only if you use `--enable-cost-analysis` (it also
calls `cloudwatch:GetMetricStatistics`, which `ReadOnlyAccess` covers), and
`s3:PutObject` on your reports bucket if you use `--s3-bucket`.

To run with `ReadOnlyAccess` alone, see
[Run with only ReadOnlyAccess](#run-with-only-readonlyaccess).

`ReadOnlyAccess` is broad: it can read data such as S3 object listings and
some configuration that InvenTag never looks at. If that is too much for your
organisation, use option 2.

Not verified against AWS: what the managed policy `ReadOnlyAccess` allows today, and which of these calls it covers.

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

Not verified against real AWS: the `apigateway:GET` statement keeps API key values out of reach.

Its `OptionalS3ReportUpload` statement allows `s3:PutObject` with server-side
encryption, for `--s3-bucket`. Replace `YOUR-REPORTS-BUCKET-NAME` with your
bucket, or remove the statement if you don't upload reports.

Not verified against real AWS: the statement allows the upload only with server-side encryption.

Where a listing action is missing, InvenTag logs one warning for that service
and carries on without its resources:

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Where an action for a detail of a resource is missing, discovery carries on
and leaves that detail empty.

## Run with only ReadOnlyAccess

You can attach only the AWS managed policy `ReadOnlyAccess` to the identity
and add nothing else. This section says what works, what does not, and what
InvenTag prints when AWS refuses an action.

The policy list in this section is PROVISIONAL. The project tests InvenTag
against a list of the `ReadOnlyAccess` actions that it wrote by hand from the
AWS reference page (policy version v192, 13 Nov 2026). The list stays
provisional until the project has a raw copy of the AWS policy. Not verified
against real AWS: that the list is what `ReadOnlyAccess` allows today, and a
scan with only `ReadOnlyAccess` attached.

### What works

By the provisional list, `ReadOnlyAccess` includes every one of the 122 read
actions in `config/defaults/iam-policy-read-only.json`, and `apigateway:GET`.
These include `tag:GetResources`, `ce:GetCostAndUsage` and
`ec2:DescribeRegions`, so the three extras of option 1 are a safeguard and not
a need.

In the tests, a scan of one account with only these actions exits with code 0.
AWS refuses no call. The log has no `No permission for` warning, and every
resource that the test created is in the report. This holds with
`--create-excel --create-word`, and also when you add
`--enable-network-analysis`, `--enable-security-analysis`,
`--enable-cost-analysis` and billing validation.

### Three actions that ReadOnlyAccess does not include

| Action | Needed only for | What happens without it |
|---|---|---|
| `sts:AssumeRole` | Scanning other accounts through a role (`role_arn`, or `--cross-account-role`) | That account fails. InvenTag scans the other accounts. The run exits with code 0, or with code 5 when you pass `--fail-on-account-error`. |
| `s3:PutObject` | Uploading the reports with `--s3-bucket` | The upload fails, and the reports stay in the local output folder. The run exits with code 1. |
| `kms:GenerateDataKey` | Uploading the reports with `--s3-encryption aws:kms` and a KMS key | Not tested. |

Not verified against real AWS: that a refused `kms:GenerateDataKey` stops the
upload, and which action S3 names then. Under a simulated AWS, the failed
upload is named `s3:PutObject` only.

### What else can refuse a call

An identity with `ReadOnlyAccess` can still be refused. These are the causes
that InvenTag cannot see apart from each other:

- a service control policy or a permissions boundary
- the policy of a resource, for example a KMS key policy or a bucket policy
- a region or a service that is not enabled for the account
- a later version of `ReadOnlyAccess`, because AWS changes the policy

Not verified against real AWS: these causes, and which of them AWS reports as
access denied.

The repository policy in option 2 is the choice with the fewest rights.
`ReadOnlyAccess` is wider than InvenTag needs, for example `s3:Get*`. The
read-only guard still refuses the calls that return object contents or
secrets, whatever the policy allows.

### When an action is refused

No refused action stops the run. This is what the run does:

| Refused | What the run does |
|---|---|
| `sts:AssumeRole` for one account | The account fails with its reason. The other accounts are scanned. |
| `ec2:DescribeRegions` | InvenTag asks `account:ListRegions`. If that fails too, it scans every region. |
| A listing of a service | One warning for the service. The run notes say `Not read`. The next change report leaves that listing out. |
| A detail call of a resource | The row stays, and the detail is empty. A run note counts the resources. |
| `tag:GetResources` | One warning. The scan goes on with the listings of the services. |
| `ce:GetCostAndUsage` | One warning. Billing checks are skipped. |
| `pricing:GetProducts` with `--enable-cost-analysis` | One warning. The cost estimates are missing. |
| `s3:PutObject` with `--s3-bucket` | The upload fails. Exit code 1. |

When only `sts:GetCallerIdentity` is allowed, the run finishes. It writes no
report and no snapshot, and the log says `No resources to report: nothing could
be read`. The exit code is 0. With `--fail-on-account-error`, an account whose
every listing was refused still counts as scanned and the run exits with code
0. To make a CI job fail when nothing could be read, add `--fail-if-empty`.

### The Permissions line and permissions_denied

When a run is not allowed to use an IAM action, the run notes get one line for
each account. The line is on the console, and in the "Run notes" of the Excel
report. It names each action, says what the report lacks, and says whether
`ReadOnlyAccess` includes the action. A run that is denied nothing prints no
such line. This is the line for a role that cannot be assumed (sample from an
offline run):

```text
Permissions: 1 action(s) were not allowed for account 222222222222: sts:AssumeRole. Effect: the account was not scanned. sts:AssumeRole is not in ReadOnlyAccess; it is needed only for scanning other accounts through a role.
```

The line has InvenTag's own words. It has no text from the AWS error. A call
for which InvenTag knows no IAM action is named by its API name, with the
words `(IAM action not known to InvenTag)`.

With `--audit-output`, the file also has the key `permissions_denied`. The key
is there only when something was denied. Each entry has these fields:

```json
"permissions_denied": [
  {
    "account": "123456789012",
    "action": "s3:GetBucketLocation",
    "service": "s3",
    "operation": "GetBucketLocation",
    "regions": ["us-east-1"],
    "kind": "detail"
  }
]
```

| Field | Meaning |
|---|---|
| `account` | The account ID. |
| `action` | The IAM action, or `null` when InvenTag does not know it. |
| `service`, `operation` | The AWS API names of the refused call. |
| `regions` | The regions in which the call was refused. Empty for an entry without a region, for example the kind `role`. |
| `kind` | `role`, `listing`, `detail`, `tagging`, `billing`, `pricing`, `analysis` or `upload`. |

The list is sorted by account and action. InvenTag makes no extra AWS call to
build it. Not verified against real AWS: the actions named are those of
InvenTag's tables, and a refusal by a service control policy or a permissions
boundary is shown as the action too.

The line does not name `ec2:DescribeRegions` or `account:ListRegions`. See
[Feature status](../getting-started/status.md#when-a-run-goes-wrong).

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
by the same rules. The guard knows operations by name. An operation that a newer AWS SDK adds is
allowed when its name starts like a read, until an InvenTag release names it.
Check a name with
`inventag --validate-operations <service>:<Operation>`. Where the answer depends on a parameter, it names the rule: `apigateway:GetApiKeys` shows `ALLOWED` with `blocked when includeValues=true`, and `ec2:DescribeInstanceAttribute` shows `ALLOWED` with `blocked when Attribute=userdata`. The guard blocks these calls only when they are called with that parameter.

IAM Identity Center (SSO) and web-identity profiles work under the guard.
The guard lets the sign-in step exchange a token for credentials, and nothing
else.

Not verified against AWS IAM Identity Center: sign-in with a real SSO or web-identity profile.

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

Not verified against real AWS: the `aws sso-admin` commands and the permission set they create.

Not verified against AWS: what the managed policy `ReadOnlyAccess` allows today, and which of these calls it covers.

Then sign in with `aws sso login --profile <profile>` and run InvenTag with
`AWS_PROFILE=<profile>`.

Not verified against the AWS CLI: the sign-in commands in this section.

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

Not verified against real AWS: the trust policy and `sts:AssumeRole` alone are enough for the scan.

## Check that it cannot write

Use the IAM policy simulator to confirm a write is denied:

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Both should show `implicitDeny` or `explicitDeny`.

Not verified against real AWS: the policy simulator result for these two actions.

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
