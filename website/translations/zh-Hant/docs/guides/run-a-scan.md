---
title: 選擇要掃描什麼、生成什麼
description: 為一次 InvenTag 執行選擇賬戶、區域和輸出檔案，儲存日誌，並選擇報告的寫入位置。
sidebar_position: 1
slug: /user-guides/cli-user-guide
---

# 選擇要掃描什麼、生成什麼

**適合誰閱讀：** 你已經執行過一次 InvenTag，想控制它掃描什麼、寫出什麼。

**讀完後你可以：** 為一次執行選擇賬戶、區域、輸出檔案和日誌。
所有引數請參閱 [CLI 參考](../reference/cli.md)。

`inventag` 命令在 Linux、macOS 和 Windows 上的用法相同。

## 選擇賬戶 {#choose-the-accounts}

| 你想掃描…… | 使用 |
|---|---|
| 當前憑證所屬的賬戶 | 不需要額外引數 |
| 透過角色訪問的另一個賬戶 | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly`（完整的角色 ARN） |
| 多個賬戶 | `--accounts-file accounts.yaml` 或配置模板：[掃描多個賬戶](./scan-multiple-accounts.md) |
| 多個賬戶，每個賬戶中的角色同名 | `--accounts-file accounts.yaml --cross-account-role InvenTagReadOnly` |
| 在被詢問時由你輸入的賬戶 | `--accounts-prompt` |

## 選擇區域 {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

不使用 `--account-regions` 時，InvenTag 會向 EC2 詢問賬戶中啟用了哪些區域，並掃描全部區域。
這樣很全面，但速度較慢。如果這次查詢失敗，InvenTag 會記錄一條警告，只掃描 `us-east-1`、
`us-west-2`、`eu-west-1` 和 `ap-southeast-1`。

訪問檢查失敗的區域會被跳過，並給出警告。

### 全域性服務 {#global-services}

你不需要把 `us-east-1` 加入列表。無論你選擇哪些區域，InvenTag 都會針對每個賬戶，
從 `us-east-1` 讀取一次全域性服務：IAM、S3 儲存桶列表、CloudFront、Route 53，
以及 CloudFront 使用的 ACM 證書。如果 `us-east-1` 已在你的列表中，它們不會被重複讀取。

- `--account-services` 和 `--account-tags` 對它們的作用與對其他資源相同。
  使用 `--account-services ec2` 時，不會讀取任何 IAM 資源。
- IAM、CloudFront 和 Route 53 資源在區域列中顯示 `global`。
  S3 儲存桶顯示它自己所在的區域，例如 `eu-west-1`。
- 它們的標籤來自 `us-east-1` 的 Resource Groups Tagging API，AWS 在那裡儲存全域性資源的標籤。
- 離線測試覆蓋了僅 `eu-west-1`、所有區域，以及包含 `us-east-1` 的列表。
  真實 AWS 會如何響應，沒有測試過。

## 選擇輸出檔案 {#choose-the-output-files}

| 引數 | 寫出 |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | 同樣的檔案，由[報告模板](../templates/index.md)決定版式 |
| `--output-directory reports` | 把所有內容寫入 `reports/`，而不是 `bom_output/` |

如果不指定輸出引數，InvenTag 只寫出 Excel。如果掃描沒有發現任何資源，或者你的過濾條件把它們全部排除了，
InvenTag 不會寫出任何檔案，並且仍以退出碼 0 退出。新增 `--s3-bucket` 還可以上傳這些檔案：
參見[定時把報告上傳到 S3](../examples/scheduled-s3-upload.md)。

使用 `--template standard-bom --create-excel
--create-word --account-regions us-east-1` 執行時的示例輸出（離線，示例資料）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

## 把多項設定合併到一個檔案中 {#combine-several-settings-in-one-file}

如果你總是使用相同的設定執行，請把它們放進[配置模板](../templates/catalogue.md#config-templates)，
而不是每次都輸入：

```bash
inventag templates init single-account --output .inventag/templates/my-scan.yaml
# edit regions and outputs, then:
inventag --template my-scan
```

你輸入的引數仍然優先於模板。

## 檢視執行情況 {#see-what-is-happening}

| 引數 | 顯示 |
|---|---|
| （無） | 警告、錯誤，以及檔案寫到了哪裡。單個呼叫的 AWS 許可權錯誤不會顯示。 |
| `--verbose` 或 `-v` | 執行的每一步 |
| `--log-file run.log` | 同時把詳細日誌寫入檔案 |
| `--debug` 或 `-d` | 每一個 AWS 請求。機密會被遮蔽，但仍應把日誌視為敏感資訊。 |
| `--audit-output audit.json` | 一份 JSON 列表，列出本次執行呼叫過的每個 AWS 操作 |

## 不掃描，只驗證配置檔案 {#validate-configuration-files-without-scanning}

```bash title="Terminal"
inventag --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
inventag templates validate my-scan
```

退出碼 0 表示檔案有效。第一條命令仍會發出一次 `ec2:DescribeRegions` 呼叫來列出區域；
如果它失敗，會記錄一條警告並繼續。損壞的賬戶檔案如下所示（示例資料）：

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

## 下一步 {#next-steps}

- [掃描多個賬戶](./scan-multiple-accounts.md)
- [按策略檢查標籤](./check-tag-compliance.md)
- [CLI 參考](../reference/cli.md)
