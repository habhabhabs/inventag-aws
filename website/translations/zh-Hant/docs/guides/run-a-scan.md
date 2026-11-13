---
title: 選擇要掃描什麼、生成什麼
description: 為一次 InvenTag 執行選擇帳戶、區域和輸出檔案，儲存日誌，並選擇報告的寫入位置。
sidebar_position: 1
slug: /user-guides/cli-user-guide
---

# 選擇要掃描什麼、生成什麼

**適合誰閱讀：** 你已經執行過一次 InvenTag，想控制它掃描什麼、寫出什麼。

**讀完後你可以：** 為一次執行選擇帳戶、區域、輸出檔案和日誌。
所有引數請參閱 [CLI 參考](../reference/cli.md)。

`inventag` 命令在 Linux、macOS 和 Windows 上的用法相同。

## 選擇帳戶 {#choose-the-accounts}

| 你想掃描…… | 使用 |
|---|---|
| 目前憑證所屬的帳戶 | 不需要額外引數 |
| 透過角色存取的另一個帳戶 | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly`（完整的角色 ARN） |
| 多個帳戶 | `--accounts-file accounts.yaml` 或設定範本：[掃描多個帳戶](./scan-multiple-accounts.md) |
| 多個帳戶，每個帳戶中的角色同名 | `--accounts-file accounts.yaml --cross-account-role InvenTagReadOnly` |
| 在被詢問時由你輸入的帳戶 | `--accounts-prompt` |

`--accounts-file` 和 `--accounts-prompt` 只能給一個，不能同時給。`--cross-account-role` 中的完整角色 ARN 只指向一個帳戶，所以不能與它們同用。這兩種錯誤都會讓執行以結束代碼 2 停止。

## 選擇區域 {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

不使用 `--account-regions` 時，InvenTag 會向 EC2 詢問帳戶中啟用了哪些區域，並掃描全部區域。
這樣很全面，但速度較慢。如果 `ec2:DescribeRegions` 失敗，InvenTag 會改問 `account:ListRegions`。
如果它也失敗，InvenTag 會記錄一條警告，並嘗試你的 AWS SDK 所知的該分割槽的每個區域。
帳戶未啟用的區域會通不過存取檢查而被跳過。可以用 `--account-regions` 自己選擇區域。

存取檢查失敗的區域會被跳過，並給出警告。如果檢查在每個區域都失敗（因為該身份缺少 `ec2:DescribeRegions`），
InvenTag 無法判斷哪些區域可用，會掃描全部區域。

### 全域性服務 {#global-services}

你不需要把主區域加入列表。無論你選擇哪些區域，InvenTag 都會針對每個帳戶，
從該分割槽的主區域讀取一次全域性服務：標準分割槽是 `us-east-1`，中國是 `cn-north-1`，GovCloud 是 `us-gov-west-1`。
這些服務是 IAM、S3 儲存貯體列表、CloudFront、Route 53，以及 CloudFront 使用的 ACM 證書。
如果主區域已在你的列表中，它們不會被重複讀取。

- `--account-services` 和 `--account-tags` 對它們的作用與對其他資源相同。
  使用 `--account-services ec2` 時，不會讀取任何 IAM 資源。
- IAM、CloudFront 和 Route 53 資源在區域欄中顯示 `global`。
  S3 儲存貯體顯示它自己所在的區域，例如 `eu-west-1`。
- 它們的標籤來自主區域的 Resource Groups Tagging API，AWS 在那裡儲存全域性資源的標籤。
- 離線測試覆蓋了僅 `eu-west-1`、所有區域，以及包含 `us-east-1` 的列表。
  真實 AWS 會如何回應，沒有測試過。

### 服務 {#services}

InvenTag 為 46 個 AWS 服務提供了自己的唯讀列舉呼叫。其他服務的資源只有在 Resource Groups Tagging API 返回它們時才會出現。
見[功能狀態與已知限制](../getting-started/status.md)。

### 限流與失敗的呼叫 {#throttling-and-failed-calls}

對於被限流的呼叫，InvenTag 總共最多重試 10 次（AWS SDK 的 「standard」 重試模式）。
如果你設定了 `AWS_RETRY_MODE` 或 `AWS_MAX_ATTEMPTS`，則使用你的值。仍然失敗的列舉會為該服務和區域記錄一條警告：
`<service> <operation> in <region> failed (<error>); its resources there may be incomplete.`
JSON 輸出會記錄每次列舉的結果。被拒絕的權限對每個服務只記錄一次。

## 時間限制與平行帳戶 {#time-limit-and-parallel-accounts}

InvenTag 預設同時掃描最多四個帳戶。用 `--max-concurrent-accounts`（至少為 1）修改，
或用 `--disable-parallel-processing` 一次只掃描一個帳戶。

每個帳戶有 `--account-processing-timeout` 秒（預設 1800，至少 60），從該帳戶開始掃描時計時。
發現過程會提前一點結束，提前 300 秒或限制的 20%（取較小者），以便還能讀取標籤、詳情和帳單資料。

超時的帳戶會被報告為失敗，其他帳戶會保留。它在限制之前找到的資源仍留在報告中，報告的備註會說明該帳戶不完整。
下面是用 `--account-processing-timeout 60` 做離線執行時的一行日誌（範例資料）：

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

如果沒有任何帳戶完成，InvenTag 仍會用已找到的內容寫出報告，記錄 `No account finished within its time limit`，並以結束代碼 1 結束。

## 失敗的執行之後繼續 {#continue-after-a-failed-run}

有帳戶失敗時，InvenTag 會把已完成的帳戶儲存在 `bom_output/state/partial/` 中。排除原因後，用同一條命令加上 `--resume` 再執行一次。
InvenTag 只掃描缺少的帳戶：

```bash
inventag --accounts-file accounts.yaml --create-excel --resume
```

只有當命令使用相同的帳戶、區域、服務和篩選條件，並且儲存的結果不早於 `--resume-max-age-hours`（預設 24，最多 168）時，InvenTag 才會複用它。
它需要狀態管理，所以 `--resume` 與 `--disable-state-management` 同用會以結束代碼 2 停止。
日誌會顯示 `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)`，報告的備註會列出每個被複用的帳戶及其掃描時間。
不帶 `--resume` 時，警告會說明存在已儲存的結果，並且它們會被重新掃描。所有帳戶都完成的執行結束後，InvenTag 會刪除已儲存的結果。

## 選擇輸出檔案 {#choose-the-output-files}

| 引數 | 寫出 |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | 同樣的檔案，由[報告範本](../templates/index.md)決定版面配置 |
| `--output-directory reports` | 把所有內容寫入 `reports/`，而不是 `bom_output/` |

如果不指定輸出引數，InvenTag 只寫出 Excel。如果掃描沒有發現任何資源，或者你的過濾條件把它們全部排除了，
InvenTag 不會寫出任何檔案，並且仍以結束代碼 0 退出。新增 `--s3-bucket` 還可以上傳這些檔案：
參見[定時把報告上傳到 S3](../examples/scheduled-s3-upload.md)。

使用 `--template standard-bom --create-excel
--create-word --account-regions us-east-1` 執行時的範例輸出（離線，範例資料）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

## 把多項設定合併到一個檔案中 {#combine-several-settings-in-one-file}

如果你總是使用相同的設定執行，請把它們放進[設定範本](../templates/catalogue.md#config-templates)，
而不是每次都輸入：

```bash
inventag templates init single-account --output .inventag/templates/my-scan.yaml
# edit regions and outputs, then:
inventag --template my-scan
```

你輸入的引數仍然優先於範本。

## 檢視執行情況 {#see-what-is-happening}

| 引數 | 顯示 |
|---|---|
| （無） | 警告、錯誤，以及檔案寫到了哪裡。單個呼叫的 AWS 權限錯誤不會顯示。 |
| `--verbose` 或 `-v` | 執行的每一步 |
| `--log-file run.log` | 同時把詳細日誌寫入檔案 |
| `--debug` 或 `-d` | 每一個 AWS 請求。機密會被遮蔽，但仍應把日誌視為敏感資訊。 |
| `--audit-output audit.json` | 一份 JSON 列表，列出本次執行呼叫過的每個 AWS 操作 |

## 不掃描，只驗證設定檔 {#validate-configuration-files-without-scanning}

```bash title="Terminal"
inventag --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
inventag templates validate my-scan
```

結束代碼 0 表示檔案有效。使用 `--skip-credential-validation` 時，第一條命令不發出任何 AWS 呼叫。損壞的帳戶檔案如下所示（範例資料）：

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

## 結束代碼 {#exit-codes}

即使有帳戶失敗或什麼都沒找到，InvenTag 也以結束代碼 0 結束。兩個可選引數可以改變這一點。報告仍會寫出。

| 引數 | 結束代碼 | 何時 |
|---|---|---|
| `--fail-on-account-error` | 5 | 有帳戶無法掃描，或只掃描了一部分 |
| `--fail-if-empty` | 6 | 沒有可報告的資源 |

完整列表見[在 CI/CD 中執行 InvenTag](./run-in-ci.md#exit-codes)。

## 下一步 {#next-steps}

- [掃描多個帳戶](./scan-multiple-accounts.md)
- [按策略檢查標籤](./check-tag-compliance.md)
- [CLI 參考](../reference/cli.md)
