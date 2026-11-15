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
| `ec2:DescribeRegions` | Lists enabled regions, and checks each region you scan | The check runs for every region, even with `--account-regions`. A region that fails it is skipped with a warning. If the call is denied in every region, all regions are scanned. |
| `account:ListRegions` | Lists enabled regions when `ec2:DescribeRegions` fails | Not called when `ec2:DescribeRegions` works. |
| `tag:GetResources` | Finds tagged resources (Resource Groups Tagging API) | The IAM prefix is `tag`, not `resourcegroupstaggingapi`. |
| `ce:GetCostAndUsage` | Finds services with spend | **AWS charges per request.** In our offline test a run made two for each account. If denied, discovery continues without billing data. `--no-billing-validation` stops the calls, and then you can leave this permission out. |
| `List*`, `Describe*`, `Get*` for each service you want in the report | Per-service discovery | For example `s3:ListAllMyBuckets`, `s3:GetBucketTagging`, `lambda:ListFunctions`, `dynamodb:ListTables`. The AWS managed `ReadOnlyAccess` policy covers these. |

## What some features need

| Feature | Extra permission |
|---|---|
| Scanning other accounts through a role | `sts:AssumeRole` on those roles, and a trust policy in each account that allows your identity |
| `--enable-cost-analysis` | `pricing:GetProducts`, and `cloudwatch:GetMetricStatistics` (both are in the repository policy) |
| `--s3-bucket` | `s3:PutObject` on that bucket (and `kms:GenerateDataKey` on the key if you use `aws:kms`) |

## What InvenTag never needs

Any write, create, delete or tag action, apart from `s3:PutObject` on a reports
bucket if you upload reports. If a reviewer finds another one in your
InvenTag policy, remove it. InvenTag's read-only guard blocks such calls
anyway. Two library functions in the code can write to
AWS when called from your own Python code (the CLI does not call them); see
[Feature status](../getting-started/status.md#security-notes).

## The policy in the repository

`config/defaults/iam-policy-read-only.json` is generated from an explicit list
of 122 read actions in the code (`inventag/security/iam_policy.py`), so it
matches what InvenTag calls. It includes `tag:GetResources`,
`ce:GetCostAndUsage`, `pricing:GetProducts` and
`lambda:GetFunctionConfiguration`. A second statement allows `apigateway:GET`
only on `/restapis`, `/domainnames` and `/usageplans`, so API key values
cannot be read.

v1.2.0 added these 17 actions for the new services and the region fallback:
`account:ListRegions`, `appsync:ListGraphqlApis`, `athena:ListWorkGroups`, `autoscaling:DescribeAutoScalingGroups`, `backup:ListBackupVaults`, `cognito-idp:ListUserPools`, `ec2:DescribeNetworkInterfaces`, `ecr:DescribeRepositories`, `elasticbeanstalk:DescribeApplications`, `elasticbeanstalk:DescribeEnvironments`, `elasticfilesystem:DescribeFileSystems`, `elasticmapreduce:ListClusters`, `es:ListDomainNames`, `firehose:ListDeliveryStreams`, `kafka:ListClustersV2`, `redshift-serverless:ListNamespaces`, `redshift-serverless:ListWorkgroups`. It also
removed `cloudtrail:LookupEvents`, which the `inventag` command does not call.

Its `OptionalS3ReportUpload` statement allows `s3:PutObject`, but only with
server-side encryption. Put your bucket name in place of
`YOUR-REPORTS-BUCKET-NAME`, or remove the statement if you don't use
`--s3-bucket`.

## Check a policy

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

The first two should be `allowed`, and `s3:PutObject` should be denied.
