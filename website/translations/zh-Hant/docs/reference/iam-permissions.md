---
title: IAM 許可權
description: InvenTag 使用的 AWS IAM 許可權、每項許可權為何需要、哪些會產生費用，以及哪些功能需要額外許可權。
sidebar_position: 3
---

# IAM 許可權

**適合誰閱讀：** 你要審查或編寫 InvenTag 的 IAM 策略。

**讀完後你可以：** 只授予 InvenTag 所需的許可權，並向審查者解釋每一項許可權。

分步設定請見[設定只讀訪問](../guides/read-only-access.md)。

## 每次執行都需要什麼 {#what-every-run-needs}

| 許可權 | 原因 | 說明 |
|---|---|---|
| `sts:GetCallerIdentity` | 確定憑證屬於哪個賬戶 | AWS 對每個身份都允許此操作；你無需授予。 |
| `ec2:DescribeRegions` | 列出已啟用的區域，並檢查你掃描的每個區域 | 即使使用 `--account-regions`，每個區域都會進行檢查。檢查失敗的區域會被跳過並給出警告。 |
| `tag:GetResources` | 找出帶標籤的資源（Resource Groups Tagging API） | IAM 字首是 `tag`，而不是 `resourcegroupstaggingapi`。 |
| `ce:GetCostAndUsage` | 找出有支出的服務 | **AWS 按請求收費。** 在我們的離線測試中，每個賬戶一次執行會發出兩次。如果被拒絕，發現過程會在沒有賬單資料的情況下繼續。`--no-billing-validation` 會停止這些呼叫，此後你可以不授予這項許可權。 |
| 你想放入報告的每個服務的 `List*`、`Describe*`、`Get*` | 按服務發現 | 例如 `s3:ListAllMyBuckets`、`s3:GetBucketTagging`、`lambda:ListFunctions`、`dynamodb:ListTables`。AWS 託管的 `ReadOnlyAccess` 策略涵蓋了這些。 |

## 某些功能需要什麼 {#what-some-features-need}

| 功能 | 額外許可權 |
|---|---|
| 透過角色掃描其他賬戶 | 對這些角色的 `sts:AssumeRole`，以及每個賬戶中允許你的身份的信任策略 |
| `--enable-cost-analysis` | `pricing:GetProducts` 和 `cloudwatch:GetMetricStatistics`（兩者都在倉庫的策略中） |
| `--s3-bucket` | 對該儲存桶的 `s3:PutObject`（如果使用 `aws:kms`，還需要對該金鑰的 `kms:GenerateDataKey`） |

## InvenTag 從不需要什麼 {#what-inventag-never-needs}

任何寫入、建立、刪除或打標籤的操作，但如果你上傳報告，則需要對報告儲存桶的 `s3:PutObject`。
如果審查者在你的 InvenTag 策略中發現其他此類許可權，請把它刪除。無論如何，InvenTag 的只讀防護都會阻止這類呼叫。
程式碼中有兩個庫函式，在你自己的 Python 程式碼中呼叫時可以寫入 AWS（CLI 不會呼叫它們）；見[功能狀態](../getting-started/status.md#security-notes)。

## 倉庫中的策略 {#the-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` 由程式碼中明確列出的 106 個讀取操作
（`inventag/security/iam_policy.py`）生成，因此它與 InvenTag 的呼叫一致。
它包含 `tag:GetResources`、`ce:GetCostAndUsage`、`pricing:GetProducts` 和
`lambda:GetFunctionConfiguration`。

它的 `OptionalS3ReportUpload` 語句允許 `s3:PutObject`，但僅限使用伺服器端加密時。
請把你的儲存桶名稱填在 `YOUR-REPORTS-BUCKET-NAME` 的位置；如果你不使用 `--s3-bucket`，就刪除這條語句。

## 檢查策略 {#check-a-policy}

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

前兩項應為 `allowed`，而 `s3:PutObject` 應被拒絕。
