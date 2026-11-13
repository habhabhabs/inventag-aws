---
title: 輸出檔案
description: InvenTag 寫出的每個檔案（Excel 和 Word 報告、標籤合規 JSON、快照和變更日誌）的名稱、位置和內容。
sidebar_position: 4
---

# 輸出檔案

**適合誰閱讀：** 你要在指令碼中處理 InvenTag 的輸出，或向他人解釋這些報告。

**讀完後你會知道：** InvenTag 寫出的每個檔案的名稱、位置和內容。

所有檔案都寫入輸出資料夾：預設是 `bom_output/`，除非你設定了 `--output-directory`，或在設定範本中設定了 `output_directory`。
InvenTag 寫入的其他位置只有你指定的檔案（`--log-file`、`--audit-output`），以及使用 `--s3-bucket` 時的 S3 儲存貯體。

輸出檔案建立後只有你的使用者可以讀寫，新建的輸出資料夾同樣只對你的使用者私有。

本頁的範例來自針對模擬 AWS 的離線執行（範例資料）。

## 檔案列表 {#file-list}

| 檔案 | 何時生成 | 內容 |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`，或沒有指定任何輸出引數 | Excel 報告 |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | Word 報告 |
| `<account-id>_bom_<timestamp>.xlsx` 和 `.docx` | `--per-account-reports`，代替 `multi_account_bom_*` 檔案 | 每個有資源的帳戶一份報告 |
| `tag_compliance_<timestamp>.json` | 啟用了標籤策略 | 標籤檢查結果 |
| `state/state_<timestamp>.json` | 每次執行，除非使用 `--disable-state-management` | 所發現的每個資源的快照，機密值已被遮蓋。`metadata.tags.coverage_summary` 按帳戶統計列出呼叫的結束方式（`ok`、`empty`、`denied`、`throttled`、`error`、`timeout`）。超過 30 天的快照，或最新 100 份之外的快照會被刪除（`--state-retention-days`、`--state-max-snapshots`）。 |
| `state/metadata.json` | 有快照時 | 快照索引：時間、帳戶、區域、資源數量、校驗和 |
| `changelog_<timestamp>.md` | 第二次及之後的執行，除非使用 `--no-generate-changelog` 或 `--disable-delta-detection` | 自上一份快照以來新增、刪除或變更了什麼。見[跟蹤變更](../guides/track-changes.md)。 |
| 你用 `--audit-output` 指定的檔案 | 你要求時 | 本次執行呼叫的每個 AWS 操作 |
| `state/partial/<key>/<account-id>.json` | 有帳戶失敗的執行 | 已完成帳戶的結果，供 `--resume` 複用，完整執行後會被刪除 |

`<timestamp>` 的格式是 `YYYYMMDD_HHMMSS`。

## Excel 報告 {#excel-report}

**不使用範本時**，工作簿包含：

- **Summary：** Service、Resource Count、Percentage，以及合計。
- **每個服務一個工作表**（例如 `EC2`、`S3`、`VPC`），按服務名稱排序，包含其資源上發現的所有欄位，
  包括展平後的 `raw_data.*` 和 `tags.*` 欄。以 ID 為鍵的對應型別 API 欄位放在一個 JSON 單元格中。列按型別、名稱和 ID 排序。
  每行都有 `source` 欄（`service-api`、`tagging-api` 或 `billing`：返回該行的 API）、
  `sources` 欄（所有這些 API，用 `+` 連線）和 `detail_level` 欄（來自服務自身 API 的行為 `full`，其他為 `identity`）。
- **Network Analysis** 和 **Security Analysis** 工作表，僅在使用 `--enable-network-analysis` 或 `--enable-security-analysis` 時出現。
- **Cost Analysis** 工作表，僅在使用 `--enable-cost-analysis` 時出現：根據 AWS Pricing API 估算的每月費用，不是你的帳單。

常用於存放機密的欄位（例如 Lambda 環境變數、CloudFormation 堆疊輸出、Glue 觸發器引數、連線字串和簽名 URL）的值，在每份報告、快照和日誌中都顯示為 `***REDACTED***`。
欄位名稱會保留。參見[功能狀態](../getting-started/status.md#what-inventag-finds-and-what-it-does-not)。

**使用報告範本時**，版面配置遵循範本：

- **Summary：** 標題、生成時間、帳戶和區域數量、一張 Service / Resources / Share 表，
  以及（有標籤策略時）合規計數。
- **資源工作表：** 每個服務一個，或使用 `layout:
  single-sheet` 時只有一個工作表。表頭列預設帶樣式、已凍結並可篩選。
- **Tag Compliance**（有標籤策略時）：範圍內每個資源一列，之後是一張規則表，列出缺失和無效的計數。

工作表名稱遵循 Excel 的規則：最多 31 個字元，且不含 `[ ] : * ? / \`。
重名的工作表會加上編號。以 `=` 開頭的單元格值會按文字儲存，絕不會作為公式。
列按服務、型別、名稱和 ID 排序。

每種版面配置的預覽由真實檔案製作，見[內建範本](../templates/catalogue.md)。

## Word 報告 {#word-report}

**不使用範本時：** 一個標題、一份執行摘要、一張服務表，以及每個服務最多 50 個資源，共六欄。

**使用報告範本時：** 即 `word.sections` 中列出的各節。表格的表頭列會在每頁重複，併為螢幕閱讀器標記為表頭。
徽標（如果有）帶有替代文字。

## 標籤合規 JSON {#tag-compliance-json}

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 23,
    "compliant": 1,
    "non_compliant": 22,
    "out_of_scope": 14,
    "percent_compliant": 4.3,
    "missing_by_key": {
      "CostCenter": 20,
      "Owner": 17,
      "Project": 21,
      "Environment": 17
    },
    "invalid_by_key": {
      "CostCenter": 1,
      "Owner": 0,
      "Project": 0,
      "Environment": 1
    }
  },
  "non_compliant_resources": [
    {
      "account": "123456789012",
      "service": "S3",
      "resource_type": "Bucket",
      "resource_id": "acme-reports",
      "arn": "arn:aws:s3:::acme-reports",
      "region": "us-east-1",
      "missing": [],
      "invalid": [
        "CostCenter: '1234' does not match CC-[0-9]{4}",
        "Environment: 'Production' is not one of prod, staging, dev, test, sandbox"
      ]
    }
  ]
}
```

## 快照 {#snapshots}

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

```json title="state/state_<timestamp>.json (structure)"
{
  "top_level_keys": [
    "compliance_data",
    "metadata",
    "network_analysis",
    "resources",
    "security_analysis"
  ],
  "one_resource": {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "acme-app-logs",
    "arn": "arn:aws:s3:::acme-app-logs",
    "region": "us-east-1",
    "tags": {
      "Environment": "prod",
      "Owner": "platform",
      "CostCenter": "CC-1001",
      "Project": "storefront",
      "DataClassification": "internal"
    },
    "source_account_id": "123456789012"
  }
}
```

## 審計 JSON {#audit-json}

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

## S3 物件 {#s3-objects}

使用 `--s3-bucket acme-inventory-reports --s3-key-prefix inventag/` 時，每次執行都會把檔案放在以該次執行命名的資料夾下：

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

## 終端輸出 {#terminal-output}

不使用 `--verbose` 時，執行會列印警告、錯誤和已寫出的檔案。
使用範本時，每個檔案會列印為 `Wrote <path>`，如果啟用了標籤策略，隨後還有一行標籤策略摘要。

## 結束代碼 {#exit-codes}

見[命令列參考](./cli.md#exit-codes)。
