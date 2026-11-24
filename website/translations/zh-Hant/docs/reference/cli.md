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
inventag selftest                      check this copy of InvenTag, offline
inventag completion bash|zsh|fish      print a shell completion script
inventag policy validate PATH [PATH ...]
inventag policy list [--policies PATH ...] [--set NAME] [--shipped]
inventag policy schema [FIELD] [--json]
inventag policy test [DIR]
inventag policy check --snapshot FILE [--policies PATH ...] [--set NAME] [--fail-on SEVERITY]
inventag policy explain POLICY --snapshot FILE [--policies PATH ...] [--set NAME]
inventag policy lock [PATH] [--check]
```

`inventag` 命令在 Linux、macOS 和 Windows 上的用法相同。

未針對 Windows 或 macOS 驗證：`inventag` 命令的行為與在 Linux 上相同。

`templates`、`selftest`、`completion` 和 `policy` 必須是程式名之後的第一個詞。

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

### `selftest` 和 `completion` {#selftest-and-completion}

| 命令 | 作用 |
|---|---|
| `selftest` | 檢查這份 InvenTag 是否能正常工作：軟體包、內建範本、AWS 服務資料、唯讀保護，以及寫入臨時資料夾後刪除的一個 Excel 檔案和一個 Word 檔案。它不呼叫 AWS，不開啟網路連線，也不需要憑證。結束代碼 0：所有檢查透過。結束代碼 1：有檢查失敗；其他檢查仍會執行。結束代碼 2：未知引數。 |
| `completion bash\|zsh\|fish` | 把 shell 補全指令碼輸出到標準輸出。它唯讀取命令自身的選項，不呼叫 AWS，也不開啟網路連線。結束代碼 0。缺少 shell 名或 shell 名未知：顯示用法行，結束代碼 2。 |

安裝補全指令碼，見 [命令列補全](../getting-started/installation.md#shell-completion)。命令如下：

```text
source <(inventag completion bash)
inventag completion zsh > "${fpath[1]}/_inventag"
inventag completion fish > ~/.config/fish/completions/inventag.fish
```

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
| `--account-services LIST` | 全部 | 可用 | 以逗號分隔的服務名稱，與 Service 欄匹配，例如 `EC2,S3`。只掃描這些服務，報告中也只保留這些服務。 |
| `--account-tags JSON` | 無 | 可用 | 標籤篩選，例如 `'{"Environment":"prod"}'`。只保留帶有這些標籤的資源。 |
| `--fallback-display auto\|always\|never` | `auto` | 可用 | 是否顯示只透過 Resource Groups Tagging API 找到的資源。`auto` 只對自身發現程式碼沒有返回結果的服務顯示它們。 |
| `--hide-fallback-resources` | 關 | 可用 | 等同於 `--fallback-display never`。已棄用。 |

## 分析 {#analysis}

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--finops-cost-allocation` | 關閉 | 可用 | 用每個帳戶自己的憑證，從 Cost Explorer 讀取該帳戶上個月的支出：按服務、按關聯帳戶，以及按內建 `finops-cost-allocation` 策略中每個已啟用的成本分配標籤鍵。在末尾新增一個 `FinOps costs` 工作表。每個帳戶最多 7 個 Cost Explorer 請求；SDK 的重試會增加請求，AWS 對每個請求收費。需要 `ce:ListCostAllocationTags`。使用 `--template` 時不新增任何內容。見 [FinOps 檢查](../guides/finops-checks.md#cost-allocation-from-cost-explorer)。 |
| `--no-cost-in-snapshot` | 關閉 | 可用 | 與 `--finops-cost-allocation` 一起使用：不把成本數字寫入狀態快照；工作表照常寫出。單獨使用時只顯示一條警告，沒有作用。 |
| `--finops-checks` | 關閉 | 可用 | 對掃描找到的資源執行六項 FinOps 檢查（`FIN-001` 到 `FIN-006`），並在 Excel 報告末尾新增一個 `FinOps` 工作表。不再發出任何 AWS 呼叫，不需要額外的權限，其檢查結果也不改變結束代碼。使用 `--template` 時不新增工作表：檢查在本次執行的狀態快照上進行，發現項寫入 `policy_findings_<timestamp>.json`；同時使用 `--disable-state-management` 時，會有一則警告說明沒有寫入任何 FinOps 發現項。見 [FinOps 檢查](../guides/finops-checks.md)。 |
| `--enable-network-analysis` | 關 | 可用 | 找到 VPC 時，在 Excel 報告中新增 `Network Analysis` 工作表。與 `--template` 一起使用時不新增任何內容。見[網路與安全分析](../guides/network-and-security-analysis.md)。 |
| `--enable-security-analysis` | 關 | 可用 | 找到安全組時，在 Excel 報告中新增 `Security Analysis` 工作表。與 `--template` 一起使用時不新增任何內容。 |
| `--enable-cost-analysis` | 關 | 可用 | 在預設工作簿中新增 Cost Analysis 工作表（以及四個 `forgotten_analysis.*` 欄）。會呼叫 Cost Explorer、Pricing 和 CloudWatch；`--no-billing-validation` 與它相互獨立，不會停止這些呼叫。 一次執行中的 Cost Explorer 請求：帳單驗證（預設開啟）每個帳戶最多一次，成本趨勢每個帳戶最多 2 次，每次都使用該帳戶自己的憑證讀取。單帳戶執行同時使用兩者時最多發出 3 次；使用 `--no-billing-validation` 時最多發出 2 次。被限流的請求會重試，總共最多 10 次嘗試，每次重試都是一次新的請求。AWS 對每次請求收費。執行會在探索開始前以警告形式說明最多的請求數。需要 `pricing:GetProducts` 和 `cloudwatch:GetMetricStatistics`。費用是根據 AWS Pricing API 得出的估算值，不是你的帳單；成本趨勢表顯示 Cost Explorer 的已計費金額，每個帳戶和服務一列。見[輸出檔案](./outputs.md#cost-analysis-sheet)和 [FinOps 檢查](../guides/finops-checks.md#the-cost-trend-of---enable-cost-analysis)。 |
| `--billing-validation`, `--no-billing-validation` | 開 | 可用 | 在發現階段使用 Cost Explorer 找出有支出的服務。AWS 對每次 Cost Explorer 請求收費。詳見[Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。`--no-billing-validation` 會停止這些呼叫；`--enable-cost-analysis` 與它相互獨立，仍會呼叫 Cost Explorer。 |

未針對真實的 AWS 驗證：`--enable-cost-analysis` 只需要這兩項額外權限，並且估算值與 AWS 價格一致。

未針對真實的 AWS 驗證：AWS 計費的請求次數，以及 AWS 是否對重試計費。

## 策略 {#policies}

策略是描述資源應當是什麼樣子的檔案。InvenTag 讀取並報告；策略不會改變帳戶中的任何內容。下面的引數在掃描之後，對本次執行的狀態快照檢查策略。`inventag policy` 命令不需要掃描，直接檢查已儲存的快照（見 [`policy` 子命令](#policy-subcommands)）。

| 引數 | 預設值 | 狀態 | 作用 |
|---|---|---|---|
| `--policy PATH` | 無 | 可用 | 策略檔案、策略集或資料夾；可重複指定。掃描之後，對本次執行的狀態快照檢查這些策略，列印文字摘要，並把 `policy_findings_<timestamp>.json` 寫入輸出目錄。也可與 `--template` 一起使用：檢查在狀態快照上進行，使用範本的執行同樣會寫出狀態快照。無效的策略會在任何 AWS 呼叫之前以結束代碼 1 停止執行。與 `--disable-state-management` 一起使用時，執行以結束代碼 2 停止。 |
| `--policy-waivers FILE` | 無 | 可用 | `--policy` 使用的豁免檔案。沒有 `--policy`：結束代碼 2。 |
| `--policy-fail-on SEVERITY` | 無 | 可用 | `info`、`low`、`medium`、`high` 或 `critical`。當有發現項在該嚴重程度或更高程度失敗時，結束代碼為 7。結束代碼 5、6、3 和 4 優先。沒有 `--policy`：結束代碼 2。掃描沒有對應結束代碼 8 的引數。 |
| `--policy-format LIST` | `json` | 可用 | 要寫出的檔案，用逗號分隔：`json`、`sarif`、`junit`、`markdown`。未知格式：結束代碼 2。沒有 `--policy`：結束代碼 2。見[策略發現項](./outputs.md#policy-findings)。 |

### `policy` 子命令 {#policy-subcommands}

`inventag policy` 讀取已儲存的狀態快照（`state/state_<timestamp>.json`）和策略檔案。它不發出任何 AWS 呼叫，也不需要憑證。`inventag policy COMMAND --help` 會列印某個命令的引數。

| 命令 | 作用 |
|---|---|
| `policy validate PATH ...` | 檢查策略、策略集和豁免檔案及資料夾，但不做任何評估。每個檔案列印一行 `OK`，每個問題列印為 `error: FILE:LINE: FIELD: PROBLEM`。`--now DATE`（`YYYY-MM-DD`，預設為 UTC 的今天）是判斷豁免是否過期所用的日期。結束代碼 0：沒有問題。結束代碼 1：有問題。結束代碼 2：沒有給出路徑。 |
| `policy list` | 列出策略：ID、嚴重程度、版本、12 個字元的摘要（digest）和檔案。`--policies PATH ...` 指定檔案或資料夾（預設 `.inventag/policies`）。`--set NAME` 列出一個策略集的成員：先在給定的路徑中找，找不到則用隨 InvenTag 提供的策略集。`--shipped` 列出隨 InvenTag 提供的策略集及各自的策略數（不能與 `--set` 同用：結束代碼 2）。結束代碼 0；檔案無法讀取或策略集未知時為 1。 |
| `policy schema [FIELD]` | 列印策略檔案的欄位及其規則；給出欄位名時，列印該欄位的說明。`--json` 列印供編輯器使用的 JSON Schema（比 `policy validate` 寬鬆：最終以 `validate` 為準）。結束代碼 0；欄位未知時為 1。 |
| `policy test [DIR]` | 執行策略資料夾（預設 `.inventag/policies`）下 `tests/<policy name>/*.yaml` 中的測試案例（fixture），每個案例列印一行 `PASS` 或 `FAIL`，最後列印計數。沒有測試案例的策略會收到警告。結束代碼 0：所有預期都成立。結束代碼 1：有案例失敗或無效。 |
| `policy check --snapshot FILE` | 對快照評估策略並報告。`--policies PATH ...`（預設 `.inventag/policies`）、`--set NAME`（只用該策略集：先在給定路徑中找，找不到則用隨附的）、`--waivers FILE`、`--baseline FILE`（較早的快照，用於基線檢查）、`--now DATE`、`--show-values`（顯示未通過檢查的值；被遮蔽的值仍然遮蔽）、`--locked`（拒絕與 `policy.lock` 不一致的策略檔案）。`--format LIST` 用逗號分隔：`text`（預設；輸出到螢幕，不寫檔案）、`json`、`sarif`、`junit` 和 `markdown`（寫成檔案，位於 `--output-directory`，預設為目前資料夾）。`--fail-on SEVERITY` 在有發現項於該嚴重程度或更高程度失敗時給出結束代碼 7；`--fail-on-not-evaluated` 在有內容無法評估時給出結束代碼 8。不帶這兩個引數時，命令只報告並以結束代碼 0 結束。結束代碼：0、1（檔案無效或無法讀取；不寫出任何內容）、2（選項無效；不寫出任何內容）、7、8（8 優先於 7）。 |
| `policy explain POLICY --snapshot FILE` | 顯示一條策略如何對每一列做出判定：結果、起決定作用的每項檢查，以及策略各部分及其判定的 `trace:`。`--resource ARN` 只看一個資源。`--policies`、`--set`、`--baseline`、`--now` 和 `--show-values` 與 `check` 相同。結束代碼 0 或 1。 |
| `policy lock [PATH]` | 在策略資料夾（預設 `.inventag/policies`）中寫入 `policy.lock`：每個策略、策略集和豁免檔案的 SHA-256 摘要。`--check` 只檢查鎖定檔是否是最新的。結束代碼 0 或 1。 |

未針對真實 AWS 驗證：真實帳戶產生的快照。測試使用的是由模擬帳戶產生的快照和手寫的列。

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
| `--concurrency N` | `64` | 可用 | 整個執行中同時進行的 AWS 請求的最大數量（1 到 256）。1 表示一次只傳送一個請求。超出 1 到 256 的值，或不是整數的值：結束代碼 2。在設定範本中：`spec.concurrency`。見[併發](../guides/run-a-scan.md#concurrency)。 |
| `--account-processing-timeout SECONDS` | `1800` | 可用 | 每個帳戶允許的時間，從該帳戶開始掃描時算起（至少 60）。超時的帳戶算作失敗；它找到的資源保留在報告中。 |
| `--disable-parallel-processing` | 關 | 可用 | 一次只掃描一個帳戶。它不改變帳戶內部的執行緒。 |
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
| `--fail-on-account-error` | 關 | 可用 | 有帳戶無法掃描或超出時限時，以結束代碼 5 結束。報告仍會寫出。不帶該引數時，這樣的執行以結束代碼 0 結束，除非所有帳戶都失敗。 |
| `--fail-if-empty` | 關 | 可用 | 沒有找到資源或篩選條件把它們全部去掉時，以結束代碼 6 結束。 |

如果同時滿足多個條件，先是 5，然後是 6，然後是 3，最後是 4。結束代碼 7（使用 `--policy-fail-on` 時）只在上述都不適用時出現。結束代碼 3、4、5 和 7 會寫出報告。
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
| `--validate-credentials` | 關 | 可用 | 按掃描使用憑證的方式檢查每個帳戶的憑證（對於其他帳戶中沒有憑證的條目，使用跨帳戶角色），然後退出（全部可用為 0，否則為 1）。 |
| `--credential-timeout SECONDS` | `30` | 可用 | 登入和憑證檢查（包括 AssumeRole）的超時時間。 |
| `--skip-credential-validation` | 關 | 可用 | 在執行開始時跳過憑證檢查。 |

## 唯讀防護與審計 {#read-only-guard-and-audit}

唯讀防護始終開啟。它會阻止每一個不是讀取的 AWS 呼叫，以及會返回金鑰或資料的讀取呼叫。

| 引數 | 預設值 | 狀態 | 功能 |
|---|---|---|---|
| `--audit-output FILE` | 無 | 可用 | 寫出一份 JSON 列表，記錄本次執行呼叫的每個 AWS 操作，包括被允許的和被阻止的。當執行無權使用某個 IAM 操作時，該檔案還會有列表 `permissions_denied`：見[僅使用 ReadOnlyAccess 執行](../guides/read-only-access.md#run-with-only-readonlyaccess)。 |
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

以結束代碼 2 停止的引數會列印如下內容（第一個範例來自沒有安裝 Google 庫的機器）：

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
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour. InvenTag does not assess compliance. To check your tags against a built-in baseline, run: inventag --template security-baseline --create-excel
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="輸出"
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked. Remove this option; nothing else is needed. To see which calls are allowed, run: inventag --validate-operations ec2:DescribeInstances
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
| 2 | 命令列無效：未知、格式錯誤或相互衝突的選項，超出 1 到 256 的 `--concurrency` 值，尚未實現的引數，Google 選項有誤，版面配置檔案引數缺少它所需的報告，或給了角色名稱但沒有 `--accounts-file` |
| 3 | 報告已寫出，但帶有 `fail_on_tag_violations: true` 的設定範本發現了標籤策略違規 |
| 4 | 報告已寫出，但 `--risk-threshold` 發現有安全組規則達到或超過該級別 |
| 5 | 報告已寫出，但有帳戶無法掃描或超出時限，並且你傳入了 `--fail-on-account-error` |
| 6 | 沒有可報告的資源，並且你傳入了 `--fail-if-empty` |
| 7 | 有策略發現項在你給出的嚴重程度或更高程度失敗：掃描中用 `--policy-fail-on`，或 `inventag policy check` 的 `--fail-on`。在掃描中，7 只在 5、6、3 和 4 都不適用時出現。發現項檔案會寫出。 |
| 8 | 僅來自帶 `--fail-on-not-evaluated` 的 `inventag policy check`：有內容無法評估。8 優先於 7。掃描從不以 8 結束。發現項檔案會寫出。 |
