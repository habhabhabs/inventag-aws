---
title: IAM 权限
description: InvenTag 使用的 AWS IAM 权限、每项权限为何需要、哪些会产生费用，以及哪些功能需要额外权限。
sidebar_position: 3
---

# IAM 权限

**适合谁阅读：** 你要审查或编写 InvenTag 的 IAM 策略。

**读完后你可以：** 只授予 InvenTag 所需的权限，并向审查者解释每一项权限。

分步设置请见[设置只读访问](../guides/read-only-access.md)。

## 每次运行都需要什么 {#what-every-run-needs}

| 权限 | 原因 | 说明 |
|---|---|---|
| `sts:GetCallerIdentity` | 确定凭证属于哪个账户 | AWS 对每个身份都允许此操作；你无需授予。 |
| `ec2:DescribeRegions` | 列出已启用的区域，并检查你扫描的每个区域 | 即使使用 `--account-regions`，每个区域都会进行检查。检查失败的区域会被跳过并给出警告。如果该调用在每个区域都被拒绝，则扫描所有区域。 |
| `account:ListRegions` | 在 `ec2:DescribeRegions` 失败时列出已启用的区域 | `ec2:DescribeRegions` 正常时不会调用。 |
| `tag:GetResources` | 找出带标签的资源（Resource Groups Tagging API） | IAM 前缀是 `tag`，而不是 `resourcegroupstaggingapi`。 |
| `ce:GetCostAndUsage` | 找出有支出的服务 | **AWS 按请求收费。** 在我们的离线测试中，每个账户一次运行会发出两次。如果被拒绝，发现过程会在没有账单数据的情况下继续。`--no-billing-validation` 会停止这些调用，此后你可以不授予这项权限。 |
| 你想放入报告的每个服务的 `List*`、`Describe*`、`Get*` | 按服务发现 | 例如 `s3:ListAllMyBuckets`、`s3:GetBucketTagging`、`lambda:ListFunctions`、`dynamodb:ListTables`。AWS 托管的 `ReadOnlyAccess` 策略涵盖了这些。 |

## 某些功能需要什么 {#what-some-features-need}

| 功能 | 额外权限 |
|---|---|
| 通过角色扫描其他账户 | 对这些角色的 `sts:AssumeRole`，以及每个账户中允许你的身份的信任策略 |
| `--enable-cost-analysis` | `pricing:GetProducts` 和 `cloudwatch:GetMetricStatistics`（两者都在仓库的策略中） |
| `--s3-bucket` | 对该存储桶的 `s3:PutObject`（如果使用 `aws:kms`，还需要对该密钥的 `kms:GenerateDataKey`） |

## InvenTag 从不需要什么 {#what-inventag-never-needs}

任何写入、创建、删除或打标签的操作，但如果你上传报告，则需要对报告存储桶的 `s3:PutObject`。
如果审查者在你的 InvenTag 策略中发现其他此类权限，请把它删除。无论如何，InvenTag 的只读防护都会阻止这类调用。
代码中有两个库函数，在你自己的 Python 代码中调用时可以写入 AWS（CLI 不会调用它们）；见[功能状态](../getting-started/status.md#security-notes)。

## 仓库中的策略 {#the-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` 由代码中明确列出的 123 个读取操作
（`inventag/security/iam_policy.py`）生成，因此它与 InvenTag 的调用一致。
它包含 `tag:GetResources`、`ce:GetCostAndUsage`、`pricing:GetProducts` 和
`lambda:GetFunctionConfiguration`。第二条语句只允许对 `/restapis`、`/domainnames` 和
`/usageplans` 使用 `apigateway:GET`，因此无法读取 API 密钥的值。

v1.2.0 为新服务和区域回退添加了以下 17 个操作：
`account:ListRegions`, `appsync:ListGraphqlApis`, `athena:ListWorkGroups`, `autoscaling:DescribeAutoScalingGroups`, `backup:ListBackupVaults`, `cognito-idp:ListUserPools`, `ec2:DescribeNetworkInterfaces`, `ecr:DescribeRepositories`, `elasticbeanstalk:DescribeApplications`, `elasticbeanstalk:DescribeEnvironments`, `elasticfilesystem:DescribeFileSystems`, `elasticmapreduce:ListClusters`, `es:ListDomainNames`, `firehose:ListDeliveryStreams`, `kafka:ListClustersV2`, `redshift-serverless:ListNamespaces`, `redshift-serverless:ListWorkgroups`。

它的 `OptionalS3ReportUpload` 语句允许 `s3:PutObject`，但仅限使用服务器端加密时。
请把你的存储桶名称填在 `YOUR-REPORTS-BUCKET-NAME` 的位置；如果你不使用 `--s3-bucket`，就删除这条语句。

## 检查策略 {#check-a-policy}

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

前两项应为 `allowed`，而 `s3:PutObject` 应被拒绝。
