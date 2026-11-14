---
title: IAM 權限
description: InvenTag 使用的 AWS IAM 權限、每項權限為何需要、哪些會產生費用，以及哪些功能需要額外權限。
sidebar_position: 3
---

# IAM 權限

**適合誰閱讀：** 你要審查或編寫 InvenTag 的 IAM 策略。

**讀完後你可以：** 只授予 InvenTag 所需的權限，並向審查者解釋每一項權限。

分步設定請見[設定唯讀存取](../guides/read-only-access.md)。

## 每次執行都需要什麼 {#what-every-run-needs}

| 權限 | 原因 | 說明 |
|---|---|---|
| `sts:GetCallerIdentity` | 確定憑證屬於哪個帳戶 | AWS 對每個身份都允許此操作；你無需授予。 |
| `ec2:DescribeRegions` | 列出已啟用的區域，並檢查你掃描的每個區域 | 即使使用 `--account-regions`，每個區域都會進行檢查。檢查失敗的區域會被跳過並給出警告。如果該呼叫在每個區域都被拒絕，則掃描所有區域。 |
| `account:ListRegions` | 在 `ec2:DescribeRegions` 失敗時列出已啟用的區域 | `ec2:DescribeRegions` 正常時不會呼叫。 |
| `tag:GetResources` | 找出帶標籤的資源（Resource Groups Tagging API） | IAM 字首是 `tag`，而不是 `resourcegroupstaggingapi`。 |
| `ce:GetCostAndUsage` | 找出有支出的服務 | **AWS 按請求收費。** 詳見[Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。 在我們的離線測試中，每個帳戶一次執行會發出兩次。如果被拒絕，發現過程會在沒有帳單資料的情況下繼續。`--no-billing-validation` 會停止這些呼叫，此後你可以不授予這項權限。 |
| 你想放入報告的每個服務的 `List*`、`Describe*`、`Get*` | 按服務發現 | 例如 `s3:ListAllMyBuckets`、`s3:GetBucketTagging`、`lambda:ListFunctions`、`dynamodb:ListTables`。AWS 託管的 `ReadOnlyAccess` 策略涵蓋了這些。 |

未針對真實的 AWS 驗證：`GetCallerIdentity` 不需要權限，Tagging API 的 IAM 字首是 `tag`，並且 `ReadOnlyAccess` 涵蓋 List、Describe 和 Get 操作。

## 某些功能需要什麼 {#what-some-features-need}

| 功能 | 額外權限 |
|---|---|
| 透過角色掃描其他帳戶 | 對這些角色的 `sts:AssumeRole`，以及每個帳戶中允許你的身份的信任策略 |
| `--enable-cost-analysis` | `pricing:GetProducts` 和 `cloudwatch:GetMetricStatistics`（兩者都在儲存庫的策略中） |
| `--s3-bucket` | 對該儲存貯體的 `s3:PutObject`（如果使用 `aws:kms`，還需要對該金鑰的 `kms:GenerateDataKey`） |

未針對真實的 AWS 驗證：這些是擔任角色、成本分析和上傳所需的僅有的額外權限。

## InvenTag 從不需要什麼 {#what-inventag-never-needs}

任何寫入、建立、刪除或打標籤的操作，但如果你上傳報告，則需要對報告儲存貯體的 `s3:PutObject`。
如果審查者在你的 InvenTag 策略中發現其他此類權限，請把它刪除。無論如何，InvenTag 的唯讀防護都會阻止這類呼叫。
程式碼中有兩個庫函式，在你自己的 Python 程式碼中呼叫時可以寫入 AWS（CLI 不會呼叫它們）；見[功能狀態](../getting-started/status.md#security-notes)。

## 儲存庫中的策略 {#the-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` 由程式碼中明確列出的 122 個讀取操作
（`inventag/security/iam_policy.py`）生成，因此它與 InvenTag 的呼叫一致。
它包含 `tag:GetResources`、`ce:GetCostAndUsage`、`pricing:GetProducts` 和
`lambda:GetFunctionConfiguration`。第二條語句只允許對 `/restapis`、`/domainnames` 和
`/usageplans` 使用 `apigateway:GET`，因此無法讀取 API 金鑰的值。

未針對真實的 AWS 驗證：對這三個路徑的 `apigateway:GET` 不會返回 API 金鑰值。

v1.2.0 為新服務和區域回退新增了以下 17 個操作：
`account:ListRegions`, `appsync:ListGraphqlApis`, `athena:ListWorkGroups`, `autoscaling:DescribeAutoScalingGroups`, `backup:ListBackupVaults`, `cognito-idp:ListUserPools`, `ec2:DescribeNetworkInterfaces`, `ecr:DescribeRepositories`, `elasticbeanstalk:DescribeApplications`, `elasticbeanstalk:DescribeEnvironments`, `elasticfilesystem:DescribeFileSystems`, `elasticmapreduce:ListClusters`, `es:ListDomainNames`, `firehose:ListDeliveryStreams`, `kafka:ListClustersV2`, `redshift-serverless:ListNamespaces`, `redshift-serverless:ListWorkgroups`。
它還刪除了 `cloudtrail:LookupEvents`，`inventag` 命令不會呼叫它。

它的 `OptionalS3ReportUpload` 語句允許 `s3:PutObject`，但僅限使用伺服器端加密時。
請把你的儲存貯體名稱填在 `YOUR-REPORTS-BUCKET-NAME` 的位置；如果你不使用 `--s3-bucket`，就刪除這條語句。如果你使用其他 `--s3-key-prefix`，請同時修改資源。

未針對真實的 AWS 驗證：該語句僅在使用伺服器端加密時才允許上傳。

## 檢查策略 {#check-a-policy}

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

前兩項應為 `allowed`。只有保留了帶有你的儲存貯體名稱的 `OptionalS3ReportUpload` 語句時，`s3:PutObject` 才會被允許。

未針對真實的 AWS 驗證：`aws iam simulate-principal-policy` 對此策略的輸出。
