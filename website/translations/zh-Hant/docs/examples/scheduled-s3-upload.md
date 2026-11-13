---
title: "範例：按計劃將報告上傳到 S3"
description: 每次定時執行後，把 InvenTag 加密的 Excel 報告上傳到 S3 儲存貯體，並附上本次執行所做的每個 AWS 呼叫的審計記錄。
sidebar_position: 9
---

# 範例：按計劃將報告上傳到 S3

**目標：** 每次定時執行都把報告加密後放入 S3 儲存貯體，並留下它所做的每個 AWS 呼叫的記錄。

**你需要：**

- 一個存放報告的儲存貯體，例如 `acme-inventory-reports`；
- 執行 InvenTag 的身份對該儲存貯體擁有 `s3:PutObject` 權限。
  `config/defaults/iam-policy-read-only.json` 中的 `OptionalS3ReportUpload` 語句就提供這個權限，
  並且只允許加密上傳；
- 一個排程器：cron、CI 定時任務或類似工具。

## 命令 {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ \
  --audit-output audit.json
```

- `--s3-bucket` 會上傳本次執行寫出的每份報告。上傳使用伺服器端加密
  （預設為 `AES256`；若要使用 KMS 金鑰，請用 `--s3-encryption aws:kms` 和
  `--s3-kms-key-id`）。`--s3-kms-key-id` 只能與 `--s3-encryption aws:kms`
  一起使用；否則執行會以結束代碼 2 停止。使用 `aws:kms` 但不給金鑰 ID 時，S3 使用 AWS
  託管金鑰 `aws/s3`。
- 每個檔案會放到 `<prefix><UTC timestamp>/<file name>`，因此各次執行不會互相覆蓋。
  如果有標籤合規 JSON 檔案，也會一併上傳。
- 如果上傳失敗，執行會以結束代碼 1 結束，排程器因此可以察覺。報告仍然保留在你的磁碟上。
- `--audit-output` 會寫出一份 JSON 列表，記錄本次執行呼叫過的每個 AWS 操作。
  無論是否使用 S3，它都可以使用。

## 輸出 {#output}

以下來自針對模擬 AWS 的離線執行（範例資料）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

儲存貯體中收到的內容：

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

審計檔案（節選）：

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

`blocked_calls` 為 0：本次執行只發出了讀取呼叫。

## 設定定時執行 {#schedule-it}

使用 cron，每個工作日 02:17 執行：

```text title="crontab -e"
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ >> /var/log/inventag.log 2>&1
```

在 GitHub Actions 中，把 `--s3-bucket` 選項新增到
[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md)裡的執行步驟。

## 下一步 {#next-steps}

- 如果希望過一段時間後刪除舊報告，請為儲存貯體新增 S3 生命週期規則。
  InvenTag 不會更改你儲存貯體的生命週期規則。
- 如果需要歷史記錄，請在多次執行之間保留 `state/` 資料夾：
  [跟蹤各次執行之間的變化](../guides/track-changes.md)。
