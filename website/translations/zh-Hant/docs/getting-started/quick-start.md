---
title: 生成第一份報告
description: 用 InvenTag 掃描一個 AWS 帳戶和區域，並在大約十分鐘內開啟它生成的 Excel 和 Word 物料清單報告。
sidebar_position: 3
---

# 生成第一份報告

**適合誰閱讀：** 你已經[安裝了 InvenTag](./installation.md)，並且有隻讀的 AWS 憑證。

**讀完後你可以：** 掃描一個帳戶、開啟 Excel 和 Word 報告，並用範本選擇更清晰的版面配置。

本頁所有範例輸出都來自針對模擬 AWS 的離線執行（範例資料）。
帳戶 `123456789012` 和 `acme-*` 資源都是虛構的。

## 1. 確認你在哪個帳戶 {#1-check-which-account-you-are-in}

```bash title="Terminal"
aws sts get-caller-identity
```

InvenTag 掃描這組憑證所屬的帳戶。

## 2. 掃描一個區域 {#2-scan-one-region}

先從小處著手。一個區域既快又省錢。

這條命令唯讀取。內建防護會攔截可能改變你帳戶的呼叫（[設定唯讀存取](../guides/read-only-access.md)）。
預設情況下，它還會傳送 AWS 按次收費的 Cost Explorer 請求；加上 `--no-billing-validation`
可以跳過它們（[一次執行的費用](#what-a-run-costs)）。

```bash title="Terminal"
inventag --create-excel --create-word --account-regions us-east-1
```

- `--create-excel` 和 `--create-word` 用來選擇要寫出的檔案。兩者都不指定時，只生成 Excel。
- `--account-regions` 把掃描限制在你列出的區域內，用逗號分隔。不指定時，
  InvenTag 會掃描帳戶中啟用的所有區域，耗時更長。無論你列出哪些區域，
  IAM、S3 儲存貯體列表、CloudFront 和 Route 53 都只會從 `us-east-1` 讀取一次。

結束時你會看到檔案寫到了哪裡：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Word document saved: bom_output/multi_account_bom_20261112_090000.docx
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

這條警告只是說明你沒有指定帳戶，所以 InvenTag 使用了你目前的憑證。
加上 `--verbose` 可以看到每一步。

## 3. 開啟報告 {#3-open-the-reports}

Excel 工作簿有一個 **Summary** 工作表，每個服務一個工作表。
不使用範本時，每個服務工作表會列出 InvenTag 找到的所有欄位，因此工作表很寬：

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`

`S3` 工作表的前幾列：

| service | type | id | name | arn | account_id | source_account_id | source_account_name | ... |
|---|---|---|---|---|---|---|---|---|
| S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports |  | 123456789012 | AWS Account 123456789012 (moto) | ... |

該工作表共有 33 欄；此處顯示前 8 欄。

Word 文件包含摘要、服務表格，以及每個服務最多 50 條資源：

**文件大綱：**

- **AWS Resource Inventory - BOM Report**（標題）
- Executive Summary
  - Service Summary
- Detailed Resource Inventory
  - ATHENA Resources (1)
  - DYNAMODB Resources (1)
  - EC2 Resources (4)
  - EVENTS Resources (1)
  - IAM Resources (1)
  - KMS Resources (14)
  - LAMBDA Resources (1)
  - S3 Resources (4)
  - VPC Resources (10)
- Report Information

文件中的一張表：

| Service | Resource Count | Percentage |
|---|---|---|
| ATHENA | 1 | 2.7% |
| DYNAMODB | 1 | 2.7% |
| EC2 | 4 | 10.8% |
| EVENTS | 1 | 2.7% |

（共 9 列；顯示 4 行。）

InvenTag 還會把本次執行的快照儲存到 `bom_output/state/`。

## 4. 用範本選擇版面配置 {#4-choose-a-layout-with-a-template}

[報告範本](../templates/index.md)能提供易讀的欄名、每個標籤一欄、凍結的表頭列和篩選按鈕：

```bash title="Terminal"
inventag --template standard-bom --create-excel --create-word --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

效果請見[內建範本](../templates/catalogue.md#standard-bom)。

## 5. 檢查你的標籤 {#5-check-your-tags}

新增標籤策略，檢視哪些資源缺少標籤：

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

工作簿裡現在有一個 **Tag Compliance** 工作表，列出每個資源缺少什麼。
更多內容見[按策略檢查標籤](../guides/check-tag-compliance.md)。

## 一次執行的費用 {#what-a-run-costs}

InvenTag 發出的唯讀呼叫是免費的，但 Cost Explorer 的 `GetCostAndUsage`
呼叫不是：AWS 按請求收費，在我們的離線測試中，預設執行會為每個帳戶發出兩次。
請參閱最新的
[Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。
加上 `--no-billing-validation` 就不會發出任何 Cost Explorer 呼叫。

## 下一步 {#next-steps}

- [功能狀態與已知限制](./status.md)：依賴某個引數之前請先閱讀。
- [選擇要掃描什麼、生成什麼](../guides/run-a-scan.md)
- [範例](../examples/index.md)：可複製貼上的方案。
