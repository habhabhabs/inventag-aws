---
title: IAM permissions
description: The AWS IAM permissions InvenTag uses, why each is needed, which ones cost money, and which features need extra permissions.
sidebar_position: 3
---

# IAM permissions

**Who this is for:** you review or write the IAM policy for InvenTag.

**What you can do after reading:** grant exactly what InvenTag needs and
explain each permission to a reviewer.

For step-by-step setup, see [Set up read-only access](../guides/read-only-access.md).

## What every run needs

| Permission | Why | Notes |
|---|---|---|
| `sts:GetCallerIdentity` | Finds out which account the credentials belong to | AWS allows this for every identity; you don't need to grant it. |
| `ec2:DescribeRegions` | Lists enabled regions | Needed unless every account sets `regions`. |
| `tag:GetResources` | Finds tagged resources (Resource Groups Tagging API) | The IAM prefix is `tag`, not `resourcegroupstaggingapi`. |
| `ce:GetCostAndUsage` | Finds services with spend | **AWS charges per request.** If denied, discovery continues without billing data. |
| `List*`, `Describe*`, `Get*` for each service you want in the report | Per-service discovery | For example `s3:ListAllMyBuckets`, `s3:GetBucketTagging`, `lambda:ListFunctions`, `dynamodb:ListTables`. The AWS managed `ReadOnlyAccess` policy covers these. |

## What some features need

| Feature | Extra permission |
|---|---|
| Scanning other accounts through a role | `sts:AssumeRole` on those roles, and a trust policy in each account that allows your identity |
| `--enable-cost-analysis` | `pricing:GetProducts` |

## What InvenTag never needs

Any write, create, delete, put or tag action. If a reviewer finds one in your
InvenTag policy, remove it. Two library functions in the code can write to
AWS when called from your own Python code (the CLI does not call them); see
[Feature status](../getting-started/status.md#security-notes).

## Policies in the repository

- `config/defaults/iam-policy-read-only.json` lists specific read actions per
  service. It does not include `ce:GetCostAndUsage` or `pricing:GetProducts`.
  Its `OptionalS3ReportUpload` statement grants `s3:PutObject` to a reports
  bucket; remove it unless you upload reports yourself.

## Check a policy

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

The first two should be `allowed`, and `s3:PutObject` should be denied.
