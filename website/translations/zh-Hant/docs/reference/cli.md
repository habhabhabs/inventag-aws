---
title: 命令列參考
description: InvenTag 的每個命令和引數、它在目前版本上的行為及預設值，均已對照 inventag --help 核對。
sidebar_position: 1
---

# 命令列參考

**適合誰閱讀：** 你需要知道某個引數的確切名稱或行為。

**讀完後你可以：** 寫出任意 InvenTag 命令列，並知道哪些引數現在可用。

本頁與這一版文件所描述的發行版的 `inventag --help` 一致。執行 `inventag --help` 可檢視你已安裝的發行版的引數。**狀態**欄說明針對模擬 AWS 的離線測試顯示的結果。
「未測試」表示還沒有測試覆蓋該行所述的內容。「僅限模擬的 Google」表示測試使用的是模擬的 Google 客戶端。詳情見[功能狀態](../getting-started/status.md)。

## 命令 {#commands}

```text
inventag [flags]                       run a scan and write reports
inventag --version                     print the version and exit
inventag templates list [--kind K] [--all]
inventag templates show NAME|PATH [--resolved]
inventag templates init NAME|PATH --output FILE|FOLDER [--name NAME] [--extend] [--force]
inventag templates validate NAME|PATH [NAME|PATH ...]
```

`inventag` 命令在 Linux、macOS 和 Windows 上的用法相同。

未針對 Windows 或 macOS 驗證：`inventag` 命令的行為與在 Linux 上相同。

`templates` 必須是程式名之後的第一個詞。

## 範本 {#templates}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--template NAME\|PATH` | 無 | 可用 | 使用範本。可重複指定，一份報告範本、一份標籤策略範本和一份設定範本各一個。見[範本](../templates/index.md)。 |

### `templates` 子命令 {#templates-subcommands}

| 命令 | 功能 |
|---|---|
| `templates list` | 列出範本的型別、來源和說明，以及搜尋過的資料夾。`--kind report\|tag-policy\|config` 用於篩選；`--all` 還會顯示被同名範本遮住的範本。 |
| `templates show NAME` | 列印該檔案。`--resolved` 列印應用 `extends` 和預設值之後的結果。 |
| `templates init NAME --output PATH` | 把範本複製到你的專案中。`--extend` 寫出一個繼承原範本的簡短檔案；`--name` 設定名稱；`--force` 覆蓋已有檔案。 |
| `templates validate NAME\|PATH ...` | 檢查檔案以及它們引用的範本。全部有效時結束代碼為 0，否則為 1。 |

## 帳戶 {#accounts}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--accounts-file FILE` | 無 | 可用 | 從 JSON 或 YAML 檔案讀取帳戶。見[設定檔](./configuration-files.md#accounts-file)。`--accounts-file` 和 `--accounts-prompt` 只能給一個（否則結束代碼 2）。 |
| `--accounts-prompt` | 關 | 可用 | 以互動方式詢問帳戶和憑證。 |
| `--cross-account-role ARN\|NAME` | 無 | 可用 | 完整的角色 ARN 會被直接擔任；與 `--accounts-file` 或 `--accounts-prompt` 一起使用時以結束代碼 2 停止。角色名稱會與 `--accounts-file` 中的每個帳戶 ID 組合。只給角色名稱而沒有 `--accounts-file` 時，會以結束代碼 2 停止。 |

## 輸出 {#output}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--create-excel` | 沒有其他輸出引數時為開 | 可用 | 寫出 `multi_account_bom_<timestamp>.xlsx`。 |
| `--create-word` | 關 | 可用 | 寫出 `multi_account_bom_<timestamp>.docx`。 |
| `--create-google-docs` | 關 | 僅限模擬的 Google | 把 Word 報告建立為 Google 文件。需要 Google 附加元件（`pip install "inventag-aws[google]"`）。見 [Google Sheets 和 Docs](../guides/google-sheets-and-docs.md)。 |
| `--create-google-sheets` | 關 | 僅限模擬的 Google | 把 Excel 報告建立為 Google Sheets 電子表格。 |
| `--google-credentials FILE` | 無 | 僅限模擬的 Google | 服務帳號金鑰檔案。不給出時使用應用預設憑證（Application Default Credentials）。 |
| `--google-oauth-client FILE` | 無 | 僅限模擬的 Google | OAuth 客戶端檔案；你在瀏覽器中登入。 |
| `--google-folder-id ID` | 無 | 僅限模擬的 Google | 存放檔案的 Drive 資料夾。 |
| `--google-share-with EMAIL` | 無 | 僅限模擬的 Google | 與該地址共享。可重複指定以新增更多地址。 |
| `--google-share-role ROLE` | `reader` | 僅限模擬的 Google | `reader`、`commenter` 或 `writer`。 |
| `--google-share-anyone` | 關 | 僅限模擬的 Google | 任何拿到連結的人都可以讀取。不加此引數時檔案是私有的。 |
| `--google-title TITLE` | 帶日期的名稱 | 僅限模擬的 Google | Google 檔案的標題。 |
| `--output-directory DIR` | `bom_output` | 可用 | 存放所有輸出檔案的資料夾。 |
| `--per-account-reports` | 關 | 可用 | 每個帳戶寫出一個 `<account-id>_bom_<timestamp>` 檔案，而不是一份合併的報告。 |

未針對真實的 Google 驗證：此表中的 Google 引數會建立、共享和輸出什麼。

## 掃描什麼 {#what-to-scan}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--account-regions LIST` | 每個已啟用的區域 | 可用 | 以逗號分隔的區域程式碼，例如 `us-east-1,eu-west-1`。IAM、S3 儲存貯體列表、CloudFront 和 Route 53 始終只從 `us-east-1` 讀取一次，因此無需列出它。 |
| `--account-services LIST` | 全部 | 可用 | 以逗號分隔的服務名稱，只有這些服務會保留在報告中，與 Service 欄匹配，例如 `EC2,S3`。 |
| `--account-tags JSON` | 無 | 可用 | 標籤篩選，例如 `'{"Environment":"prod"}'`。只保留帶有這些標籤的資源。 |
| `--fallback-display auto\|always\|never` | `auto` | 可用 | 是否顯示只透過 Resource Groups Tagging API 找到的資源。`auto` 只對自身發現程式碼沒有返回結果的服務顯示它們。 |
| `--hide-fallback-resources` | 關 | 可用 | 等同於 `--fallback-display never`。已棄用。 |

## 分析 {#analysis}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--enable-network-analysis` | 關 | 可用 | 找到 VPC 時，在 Excel 報告中新增 `Network Analysis` 工作表。與 `--template` 一起使用時不新增任何內容。見[網路與安全分析](../guides/network-and-security-analysis.md)。 |
| `--enable-security-analysis` | 關 | 可用 | 找到安全組時，在 Excel 報告中新增 `Security Analysis` 工作表。與 `--template` 一起使用時不新增任何內容。 |
| `--enable-cost-analysis` | 關 | 可用 | 在預設工作簿中新增 Cost Analysis 工作表（以及四個 `forgotten_analysis.*` 欄）。會額外呼叫 Cost Explorer、Pricing 和 CloudWatch，即使加了 `--no-billing-validation` 也一樣。需要 `pricing:GetProducts` 和 `cloudwatch:GetMetricStatistics`。費用是根據 AWS Pricing API 得出的估算值，不是你的帳單。 |
| `--billing-validation`, `--no-billing-validation` | 開 | 可用 | 在發現階段使用 Cost Explorer 找出有支出的服務。AWS 對每次 Cost Explorer 請求收費。詳見[Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。`--no-billing-validation` 會停止這些呼叫。 |

未針對真實的 AWS 驗證：`--enable-cost-analysis` 只需要這兩項額外權限，並且估算值與 AWS 價格一致。

## 設定檔 {#configuration-files}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--tag-mappings FILE` | 無 | 可用 | 每條對應新增一個命名欄。見[設定檔](./configuration-files.md#tag-mappings)。 |
| `--service-descriptions FILE` | 無 | 可用 | 新增 `service_description` 欄。你的條目會替換內建描述。見[設定檔](./configuration-files.md#service-descriptions)。 |
| `--bom-config FILE` | 無 | 可用 | 從 YAML 或 JSON 檔案設定 BOM 處理設定的欄位。其他鍵會被忽略，並給出指明這些鍵的警告。型別錯誤的值會以結束代碼 1 停止，並指明該鍵。 |
| `--validate-config` | 關 | 可用 | 載入並檢查設定，然後退出。 |
| `--validate-config-only` | 關 | 可用 | 檢查 `--accounts-file`、`--tag-mappings` 和 `--service-descriptions`，然後退出。不會讀取 `--bom-config`。不會進行任何 AWS 呼叫。 |

## 報告版面配置檔案 {#report-layout-files}

這些引數用一個 YAML 或 JSON 檔案改變預設 Excel 和 Word 報告的版面配置。見[單份報告的版面配置檔案](../templates/layout-flags.md)。

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--word-template PATH` | 無 | 可用 | Word 報告的版面配置檔案。需要 `--create-word`；沒有它時執行以結束代碼 2 停止。 |
| `--excel-template PATH` | 無 | 可用 | Excel 報告的版面配置檔案。只給了 `--create-word` 時，執行以結束代碼 2 停止。 |
| `--print-default-template word\|excel` | 無 | 可用 | 列印該格式的預設版面配置檔案，然後以結束代碼 0 退出。 |
| `--validate-templates` | 關 | 可用 | 檢查 `--word-template` 和 `--excel-template` 給出的檔案，然後退出。不呼叫 AWS。兩個引數都沒有時：結束代碼 2。 |

## 平行處理 {#parallel-processing}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--max-concurrent-accounts N` | `4` | 可用 | 同時掃描的帳戶數（至少 1）。 |
| `--account-processing-timeout SECONDS` | `1800` | 可用 | 每個帳戶允許的時間，從該帳戶開始掃描時算起（至少 60）。超時的帳戶算作失敗；它找到的資源保留在報告中。 |
| `--disable-parallel-processing` | 關 | 可用 | 一次只掃描一個帳戶。 |
| `--resume` | 關 | 可用 | 複用同一條命令之前未完成的執行中已完成帳戶的儲存結果（相同的帳戶、區域、服務和篩選條件），只掃描其他帳戶。與 `--disable-state-management` 一起使用：結束代碼 2。 |
| `--resume-max-age-hours HOURS` | `24` | 可用 | 與 `--resume` 一起使用時，只複用不超過這個時長的儲存結果（最多 168）。 |

## 狀態與變更跟蹤 {#state-and-change-tracking}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--enable-state-management` | 開 | 可用 | 在 `<output>/state/` 中儲存快照。 |
| `--disable-state-management` | 關 | 可用 | 不儲存快照和變更日誌。 |
| `--enable-delta-detection` / `--disable-delta-detection` | 開 | 可用 | 把新快照與上一份快照比較。`--disable-delta-detection` 不寫出變更報告。 |
| `--generate-changelog`, `--no-generate-changelog` | 開 | 可用 | 從第二次執行起寫出 `changelog_<timestamp>.md`。`--no-generate-changelog` 會停止寫出。 |
| `--state-retention-days N` | `30` | 可用 | 執行儲存新快照時，刪除超過 N 天的狀態快照。`0` 或 `none` 保留任何時長的快照。 |
| `--state-max-snapshots N` | `100` | 可用 | 只保留最新的 N 個狀態快照。`0` 或 `none` 保留所有快照。 |

## 可選的結束代碼 {#opt-in-exit-codes}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--fail-on-account-error` | 關 | 可用 | 有帳戶無法掃描或超出時限時，以結束代碼 5 結束。報告仍會寫出。 |
| `--fail-if-empty` | 關 | 可用 | 沒有找到資源或篩選條件把它們全部去掉時，以結束代碼 6 結束。 |

如果同時滿足多個條件，先是 5，然後是 6，然後是 3，最後是 4。結束代碼 3、4 和 5 會寫出報告。
對於結束代碼 6，帶 `--template` 的執行會寫出一份不列出任何資源的報告，不帶 `--template` 的執行則不寫檔案。

## 日誌 {#logging}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--verbose`, `-v` | 關 | 可用 | 顯示每一步。 |
| `--debug`, `-d` | 關 | 可用 | 顯示 AWS 請求。金鑰會被遮蔽。 |
| `--log-file FILE` | 無 | 可用 | 同時把詳細日誌寫入該檔案。 |
| `--disable-account-logging` | 關 | 可用 | 不在日誌行前加帳戶字首。 |

## 憑證 {#credentials}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--validate-credentials` | 關 | 可用 | 檢查每個帳戶的憑證，然後退出（全部可用為 0，否則為 1）。 |
| `--credential-timeout SECONDS` | `30` | 可用 | 登入和憑證檢查（包括 AssumeRole）的超時時間。 |
| `--skip-credential-validation` | 關 | 可用 | 在執行開始時跳過憑證檢查。 |

## 唯讀防護與審計 {#read-only-guard-and-audit}

唯讀防護始終開啟。它會阻止每一個不是讀取的 AWS 呼叫，以及會返回金鑰或資料的讀取呼叫。

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--audit-output FILE` | 無 | 可用 | 寫出一份 JSON 列表，記錄本次執行呼叫的每個 AWS 操作，包括被允許的和被阻止的。 |
| `--validate-operations SERVICE:OPERATION ...` | 無 | 可用 | 對照防護檢查這些操作，然後退出（全部允許為 0，否則為 1）。 |
| `--enforce-read-only`, `--security-validation`, `--enable-production-safety` | 開 | 無效果 | 保留這些引數是為了讓舊命令仍能執行。防護始終開啟。 |
| `--disable-production-safety` | 關 | 以結束代碼 2 停止 | 防護無法關閉。 |
| `--compliance-standard ...` | 無 | 以結束代碼 2 停止 | 未實現：無法根據清單檢查某個標準。請使用標籤策略範本。 |
| `--risk-threshold LEVEL` | 無 | 可用 | 與 `--enable-security-analysis` 一起使用時：如果有安全組規則達到或超過 `LOW`、`MEDIUM`、`HIGH` 或 `CRITICAL`，結束代碼為 4。沒有 `--enable-security-analysis` 時：結束代碼為 2。 |

```text title="輸出"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
```

```bash title="Terminal"
echo $?
```

```text title="輸出"
1
```

以結束代碼 2 停止的引數會列印如下內容：

```bash title="Terminal"
inventag --create-google-docs
```

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)
```

```bash title="Terminal"
inventag --risk-threshold HIGH
```

```text title="輸出"
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)
```

```bash title="Terminal"
inventag --compliance-standard soc2
```

```text title="輸出"
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="輸出"
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## S3 上傳 {#s3-upload}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--s3-bucket BUCKET` | 無 | 可用 | 把本次執行寫出的每個檔案（Excel、Word 和標籤合規 JSON）上傳到該儲存貯體。上傳失敗時，執行以結束代碼 1 結束。需要 `s3:PutObject`。 |
| `--s3-key-prefix PREFIX` | `bom-reports/` | 可用 | 儲存貯體中的資料夾（鍵字首）。檔案位於 `<prefix><UTC timestamp>/` 之下。 |
| `--s3-encryption AES256\|aws:kms` | `AES256` | 可用 | 上傳檔案使用的伺服器端加密。 |
| `--s3-kms-key-id KEY` | 無 | 可用 | 用於 `aws:kms` 的 KMS 金鑰。不給出時，S3 使用 AWS 託管金鑰 `aws/s3`。需要 `--s3-encryption aws:kms`，否則結束代碼 2。 |

未針對真實的 AWS 驗證：上傳只需要 `s3:PutObject`（使用 `aws:kms` 時還需要 `kms:GenerateDataKey`）。

未針對 AWS 驗證：`aws:kms` 沒有金鑰 ID 時，S3 是否使用 AWS 託管金鑰 `aws/s3`。

見[按計劃把報告上傳到 S3](../examples/scheduled-s3-upload.md)。

## 結束代碼 {#exit-codes}

| 程式碼 | 含義 |
|---|---|
| 0 | 成功。部分帳戶失敗但其他帳戶正常，以及沒有找到任何資源時，也是 0，除非你傳入 `--fail-on-account-error` 或 `--fail-if-empty`。見[功能狀態](../getting-started/status.md#when-a-run-goes-wrong)。 |
| 1 | 出錯：引數、設定或範本無效，數值超出範圍（例如 `--max-concurrent-accounts 0`），憑證失敗，所有帳戶都失敗（無法掃描或超出時限），S3 上傳失敗，或某種報告格式無法寫出 |
| 2 | 命令列無效：未知、格式錯誤或相互衝突的選項，尚未實現的引數，Google 選項有誤，版面配置檔案引數缺少它所需的報告，或給了角色名稱但沒有 `--accounts-file` |
| 3 | 報告已寫出，但帶有 `fail_on_tag_violations: true` 的設定範本發現了標籤策略違規 |
| 4 | 報告已寫出，但 `--risk-threshold` 發現有安全組規則達到或超過該級別 |
| 5 | 報告已寫出，但有帳戶無法掃描或超出時限，並且你傳入了 `--fail-on-account-error` |
| 6 | 沒有可報告的資源，並且你傳入了 `--fail-if-empty` |
