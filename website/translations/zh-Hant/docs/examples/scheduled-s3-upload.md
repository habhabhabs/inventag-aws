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
  並且只允許加密上傳。它的資源是
  `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`：請替換儲存貯體名稱，並注意它只覆蓋以
  `bom-reports/` 開頭的鍵。這也是 `--s3-key-prefix` 的預設值。若使用其他字首，請修改該
  資源；
- 一個排程器：cron、CI 定時任務或類似工具。

## 命令 {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ \
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

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

儲存貯體中收到的內容：

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090100.xlsx
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
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ >> /var/log/inventag.log 2>&1
```

在 GitHub Actions 中，把 `--s3-bucket` 選項新增到
[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md)裡的執行步驟。

### GitLab CI/CD {#gitlab-cicd}

未針對 GitLab Runner 或真實的 AWS 帳戶驗證：此流水線尚未在 GitLab 上執行。它的 YAML 和 `inventag` 命令列會在建置文件時檢查。它的作業已在本地用 gitlab-ci-local 4.77.1（用替身代替 rsync）針對模擬的 AWS 執行，使用的是虛擬權杖。

這個作業按流水線計劃執行上面的命令，把報告上傳到你的儲存貯體，並把一份副本儲存為作業產物。使用之前：

- 按照[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)中的說明，建立 GitLab 用來登入的角色和 CI/CD 變數 `AWS_ROLE_ARN`。該部分也說明了如何建立流水線計劃。
- 再新增兩個 CI/CD 變數：`INVENTAG_REPORTS_BUCKET`（儲存貯體名稱）和 `INVENTAG_KMS_KEY_ID`（KMS 金鑰 ID）。兩者都不是機密。
- 給該角色加上 `config/defaults/iam-policy-read-only.json` 中的 `OptionalS3ReportUpload` 語句，並把 `YOUR-REPORTS-BUCKET-NAME` 換成你的儲存貯體名稱。它的資源是 `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`，所以請保留 `--s3-key-prefix bom-reports/`，或修改該資源。使用 `aws:kms` 時，角色還需要對該金鑰擁有 `kms:GenerateDataKey` 權限（[IAM 權限](../reference/iam-permissions.md)）。

```yaml
# .gitlab-ci.yml
stages:
  - inventory

inventory-to-s3:
  stage: inventory
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
  timeout: 2 hours                            # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    # --s3-kms-key-id works only together with --s3-encryption aws:kms.
    # Without KMS, delete that line: uploads then use AES256.
    - |
      inventag --template standard-bom --create-excel --account-regions us-east-1 \
        --s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/ \
        --s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID" \
        --audit-output bom_output/audit.json \
        --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # a copy in GitLab, also when the upload fails
    paths:
      - bom_output/
    expire_in: 1 week
```

所有 GitLab 範例共有的行，在[在 CI/CD 中執行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)中說明。下表只說明這個範例特有的部分。

| 部分 | 作用 |
|---|---|
| `- \|`，行尾帶 `\` | 把一條 shell 命令分成五行來寫（[GitLab：script](https://docs.gitlab.com/ci/yaml/script/)）。 |
| `--s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/` | 把本次執行的每份報告上傳到 `<prefix><UTC timestamp>/<file name>`。儲存貯體名稱來自 CI/CD 變數。`bom-reports/` 也是預設值，這裡把它寫出來，是因為已發佈的策略只允許對 `YOUR-REPORTS-BUCKET-NAME/bom-reports/*` 執行 `s3:PutObject`。如果上傳失敗，執行會以結束代碼 1 結束，作業隨之失敗（[GitLab：script](https://docs.gitlab.com/ci/yaml/script/)）。 |
| `--s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID"` | 本頁的 KMS 規則：`--s3-kms-key-id` 只能與 `--s3-encryption aws:kms` 一起使用；否則執行會以結束代碼 2 停止。使用 `aws:kms` 但不給金鑰 ID 時，S3 使用 AWS 託管金鑰 `aws/s3`。不用 KMS 時，刪除這一行：上傳就使用 `AES256`。角色需要對該金鑰擁有 `kms:GenerateDataKey` 權限。 |
| `--fail-on-account-error --fail-if-empty` | 有帳戶無法掃描時，結束代碼為 5；沒有找到任何資源時，結束代碼為 6。任何非 0 的結束代碼都會使作業失敗（[GitLab：script](https://docs.gitlab.com/ci/yaml/script/)）。 |
| `--audit-output bom_output/audit.json` | 把本次執行呼叫過的 AWS 操作列表寫入產物資料夾。 |
| `artifacts:`，帶 `expire_in: 1 week` | 在 GitLab 中保留第二份副本，上傳失敗時也會保留（[`when`](https://docs.gitlab.com/ci/yaml/#artifactswhen)、[`expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in)）。可選。 |

本地執行沒有覆蓋的部分：

- 未針對 GitLab 或 AWS 驗證：GitLab 簽發 ID 權杖，以及 AWS 為該角色接受它，包括信任策略中對 `aud` 和 `sub` 的條件。
- 未針對 GitLab 驗證：`image`、`timeout` 和 `expire_in`（gitlab-ci-local 會忽略它們）。
- 未針對 GitLab 流水線計劃驗證：本地執行時，流水線來源是手動設定的。
- 未針對 AWS 驗證：用真實的儲存貯體和金鑰上傳時的 S3 和 KMS 權限。

## 下一步 {#next-steps}

- 如果希望過一段時間後刪除舊報告，請為儲存貯體新增 S3 生命週期規則。
  InvenTag 不會更改你儲存貯體的生命週期規則。
- 如果需要歷史記錄，請在多次執行之間保留 `state/` 資料夾：
  [跟蹤各次執行之間的變化](../guides/track-changes.md)。
