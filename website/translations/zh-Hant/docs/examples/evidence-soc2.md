---
title: "範例：在 SOC 2 範圍討論之前檢查標籤證據"
description: 使用 InvenTag 的 evidence-soc2 標籤策略範本，找出沒有記錄 SOC 2 範圍、系統名稱、建立方式或關鍵程度標籤的 AWS 資源。
sidebar_position: 10
---

# 範例：在 SOC 2 範圍討論之前檢查標籤證據

:::note

這裡只檢查標籤證據。標籤值由資源所有者自行填寫，InvenTag 不會核實。檢查透過並不代表帳戶滿足 SOC 2。

:::

**目標：** 在與審計人員或客戶討論哪些系統屬於 SOC 2 範圍之前，列出沒有記錄範圍、系統名稱、建立方式或關鍵程度的資源。

**你需要：** 唯讀憑證。InvenTag 讀取標籤；它不評估控制措施。

## 範本 {#template}

內建的 `evidence-soc2` 標籤策略以 `security-baseline`（`Owner`、`Environment` 和 `DataClassification`）為起點，並加入四個標籤：

| 標籤鍵 | 規則 |
|---|---|
| `Soc2Scope` | `in-scope` 或 `out-of-scope` |
| `SystemName` | 任意非空文字 |
| `ManagedBy` | `terraform`、`cloudformation`、`cdk`、`manual` 或 `other` |
| `Criticality` | `high`、`medium` 或 `low` |

它覆蓋除 KMS 別名之外的所有資源型別。它能顯示什麼、不能顯示什麼，見[範本目錄](../templates/catalogue.md#evidence-soc2)。

## 命令 {#command}

```bash title="Terminal"
inventag --template evidence-soc2 --create-excel --account-regions us-east-1
```

## 輸出 {#output}

範例帳戶有四個儲存貯體、一個 DynamoDB 表和一個隊欄，它們的標籤各不相同，另外還有每個帳戶都有的預設資源。

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'evidence-soc2': 2 of 18 resources compliant (11.1%), 16 non-compliant, 14 out of scope.
```

範圍之外的 14 個資源是 KMS 別名。在缺少內容的 16 個資源中，有 12 個是沒人打標籤的預設資源（預設 VPC 及其子網、路由表、網路 ACL 和安全組，一個 Athena 工作組，以及預設事件匯流排）。狀態欄只說明該資源是否帶有範本中的每個標籤且值在允許範圍內。

**工作表：** `Summary`, `ATHENA`, `DYNAMODB`, `EVENTS`, `KMS`, `S3`, `SQS`, `VPC`, `Tag Compliance`

`Tag Compliance` 工作表的前幾列：

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | arn:aws:s3:::acme-data-lake | Non-compliant | Criticality |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | arn:aws:s3:::acme-reports | Non-compliant |  | Soc2Scope: 'yes' is not one of in-scope, out-... |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | arn:aws:s3:::acme-scratch | Non-compliant | Owner, Environment, DataClassification, Soc2S... |  |
| 123456789012 | us-east-1 | SQS | Queue | acme-jobs | arn:aws:sqs:us-east-1:123456789012:acme-jobs | Non-compliant | DataClassification, Soc2Scope, SystemName, Cr... |  |
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Compliant |  |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | arn:aws:s3:::acme-app-logs | Compliant |  |  |

各行說明的內容：

- `acme-data-lake` 沒有 `Criticality` 標籤。
- `acme-reports` 的 `Soc2Scope` 設為 `yes`，不在允許的值之內。
- `acme-scratch` 沒有任何標籤。
- `acme-jobs` 有 `Owner`、`Environment` 和 `ManagedBy`，但沒有 `DataClassification`、`Soc2Scope`、`SystemName` 或 `Criticality`。
- `acme-app-logs` 帶有每個標籤，且值都在允許範圍內。
- `acme-orders` 被其所有者標為 `out-of-scope`，並且仍帶有每個標籤。檢查的是答案已被記錄，而不是答案是什麼。

要檢視哪個標籤最常缺失，請閱讀 JSON 檔案中的摘要：

```json title="tag_compliance_20261112_090000.json (summary, two fields)"
{
  "missing_by_key": {
    "Owner": 13,
    "Environment": 13,
    "DataClassification": 14,
    "Soc2Scope": 14,
    "SystemName": 14,
    "ManagedBy": 13,
    "Criticality": 15
  },
  "invalid_by_key": {
    "Owner": 0,
    "Environment": 0,
    "DataClassification": 0,
    "Soc2Scope": 1,
    "SystemName": 0,
    "ManagedBy": 0,
    "Criticality": 0
  }
}
```

## 它不能告訴你什麼 {#what-this-does-not-tell-you}

- 它不能告訴你範圍是否正確、控制措施是否存在或是否有效，也不能告訴你審計人員會測試什麼。
- 它不檢查 `ManagedBy` 是否屬實。請與 AWS 新增的 `aws:cloudformation:*` 標籤比對。
- 標籤存在，只表示所有者寫了一些內容。

## 下一步 {#next-steps}

- 為預設資源打上標籤，或縮小策略範圍使它們不被檢查：把 `evidence-soc2` 複製到你的專案中並設定 `spec.scope.services`，做法見[範例：安全標籤審查](./security-review.md#next-steps)。
- 在 CI 中先從僅報告模式開始：[範例：在 CI 中強制執行標籤策略](./tag-policy-in-ci.md)。
- 編寫你自己的規則：[按策略檢查標籤](../guides/check-tag-compliance.md#write-your-own-policy)。
