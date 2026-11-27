---
title: 輸出檔案
description: InvenTag 寫出的每個檔案（Excel 和 Word 報告、標籤合規 JSON、快照和變更日誌）的名稱、位置和內容。
sidebar_position: 4
---

# 輸出檔案

**適合誰閱讀：** 你要在指令碼中處理 InvenTag 的輸出，或向他人解釋這些報告。

**讀完後你會知道：** InvenTag 寫出的每個檔案的名稱、位置和內容。

所有檔案都寫入輸出資料夾：預設是 `bom_output/`，除非你設定了 `--output-directory`，或在設定範本中設定了 `output_directory`。
InvenTag 寫入的其他位置只有你指定的檔案（`--log-file`、`--audit-output`、`templates init --output`）、使用 `--s3-bucket` 時的 S3 儲存貯體，以及使用 Google 選項時的 Google Drive；使用 `--google-oauth-client` 時還有位於 `~/.config/inventag/google-token.json` 的登入權杖檔案。

輸出檔案建立後只有你的使用者可以讀寫，新建的輸出資料夾同樣只對你的使用者私有。

未針對 Windows 驗證：檔案和資料夾僅對你的使用者私有。

本頁的範例來自針對模擬 AWS 的離線執行（範例資料）。

## 檔案列表 {#file-list}

| 檔案 | 何時生成 | 內容 |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`，或沒有指定任何輸出引數 | Excel 報告 |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | Word 報告 |
| `multi_account_bom_<timestamp>.html` | `--create-html` | HTML 報告。參見 [HTML 報告](#html-report)。 |
| `<account-id>_bom_<timestamp>.xlsx`、`.docx` 和 `.html` | `--per-account-reports`，代替 `multi_account_bom_*` 檔案 | 每個有資源的帳戶一份報告 |
| `tag_compliance_<timestamp>.json` | 啟用了標籤策略 | 標籤檢查結果 |
| `state/state_<timestamp>.json` | 每次執行，除非使用 `--disable-state-management` | 所發現的每個資源的快照，機密值已被遮蓋。`metadata.tags.coverage_summary` 按帳戶統計列出呼叫的結束方式（`ok`、`empty`、`denied`、`throttled`、`error`、`timeout`，以及 `--account-services` 排除的服務對應的 `out_of_scope`）。`metadata.tags.units_not_read` 列出未能讀取的列出呼叫（僅在有呼叫失敗時出現），`metadata.tags.inventag_version` 記錄寫出該快照的 InvenTag 版本。超過 30 天的快照，或最新 100 份之外的快照會被刪除（`--state-retention-days`、`--state-max-snapshots`）。 |
| `state/metadata.json` | 有快照時 | 快照索引：時間、帳戶、區域、資源數量、校驗和 |
| `policy_findings_<timestamp>.json` | `--policy`（`--policy-format` 的預設值）、與 `--template` 一起使用的 `--finops-checks`，或 `inventag policy check --format json` | 對快照檢查策略的結果。見[策略發現項](#policy-findings)。 |
| `policy_findings_<timestamp>.sarif`、`.xml` 和 `.md` | `--policy-format sarif`、`junit` 或 `markdown`，或 `inventag policy check` 的 `--format` 中的同樣詞語 | 同一結果的 SARIF 2.1.0、JUnit XML 和 Markdown 形式。`junit` 寫出 `.xml`，`markdown` 寫出 `.md`。 |
| `changelog_<timestamp>.md` | 第二次及之後的執行，除非使用 `--no-generate-changelog` 或 `--disable-delta-detection` | 自上一份快照以來新增、刪除或變更了什麼。見[跟蹤變更](../guides/track-changes.md)。 |
| 你用 `--audit-output` 指定的檔案 | 你要求時 | 本次執行呼叫的每個 AWS 操作 |
| `state/partial/<key>/<account-id>.json` | 有帳戶失敗的執行 | 已完成帳戶的結果，供 `--resume` 複用，完整執行後會被刪除 |

`<timestamp>` 的格式是 `YYYYMMDD_HHMMSS`。報告、Word、變更日誌和標籤合規檔案的名稱使用你電腦的本地時間。快照和 S3 資料夾使用 UTC。`policy_findings_` 檔案的 `<timestamp>` 是被檢查快照中儲存的時間（UTC），不是檢查時的時鐘。

預設工作簿為每個 API 欄位提供一個 `raw_data.*` 欄，因此工作表可能很寬。快照是帶縮排的 JSON，包含每個資源的完整 `raw_data`，因此可能很大。目前沒有選項可以省略 `raw_data.*` 欄或壓縮快照；兩者都計劃在以後的版本中提供。

## Excel 報告 {#excel-report}

**不使用範本時**，工作簿包含：

- **Summary：** Service、Resource Count、Percentage，以及合計。
- **每個服務一個工作表**（例如 `EC2`、`S3`、`VPC`），按服務名稱排序，包含其資源上發現的所有欄位，
  包括展平後的 `raw_data.*` 和 `tags.*` 欄。以 ID 為鍵的對應型別 API 欄位放在一個 JSON 單元格中。列按型別、名稱和 ID 排序。
  每行都有 `source` 欄（`service-api`、`tagging-api` 或 `billing`：返回該行的 API）、
  `sources` 欄（所有這些 API，用 `+` 連線）和 `detail_level` 欄（來自服務自身 API 的行為 `full`，其他為 `identity`）。
- **Network Analysis** 和 **Security Analysis** 工作表，僅在使用 `--enable-network-analysis` 或 `--enable-security-analysis` 時出現。
- **Cost Analysis** 工作表，僅在使用 `--enable-cost-analysis` 時出現：根據 AWS Pricing API 估算的每月費用，不是你的帳單，另有一張來自 Cost Explorer 的、按帳戶和服務列出的已計費成本表。見 [Cost Analysis 工作表](#cost-analysis-sheet)。
- **FinOps** 工作表，位於最後，僅在使用 `--finops-checks` 時出現：見 [FinOps 工作表和 `finops_checks` 鍵](#finops-sheet-and-the-finops_checks-key)。

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

## FinOps 工作表和 `finops_checks` 鍵 {#finops-sheet-and-the-finops_checks-key}

使用 `--finops-checks` 時，預設工作簿以一個 `FinOps` 工作表結束。第一行是一條說明，然後是列出的結果，列為 `Check ID`、`Check`、`Result`、`Reason`、`Account`、`Region`、`Service`、`Resource Type`、`Resource ID`、`Name` 和 `Observed`，按檢查 ID、帳戶、區域和資源 ID 排序。隨後是一張表，列出每項檢查的計數（`Fail`、`Not evaluated`、`Pass`）。使用 `--template` 時不寫 `FinOps` 工作表。

命令列不為這些結果寫 JSON 檔案。在 Python 中，`CloudBOMGenerator.generate_multi_account_bom()` 的結果帶有 `finops_checks` 鍵，用 `json` 輸出格式寫出的 JSON 報告的 `metadata` 中也有這個鍵。不使用該引數時沒有這個鍵。欄位見 [FinOps 檢查](../guides/finops-checks.md#the-finops_checks-result)。

## FinOps costs 工作表和 `finops_costs` 鍵 {#finops-costs-sheet-and-the-finops_costs-key}

使用 `--finops-cost-allocation` 時，預設工作簿以一個 `FinOps costs` 工作表結束（兩個引數都使用時，位於 `FinOps` 工作表之後）：一條說明，然後每個帳戶、分組和值各佔一列，列為 `Account`、`Grouping`、`Value`、`Amount`、`Currency`、`Metric`、`Period start`、`Period end` 和 `Status`。`CloudBOMGenerator.generate_multi_account_bom()` 的結果和 JSON 報告的 `metadata` 帶有 `finops_costs` 鍵；快照帶有 `metadata.tags.cost_allocation`（只有表格，除非使用 `--no-cost-in-snapshot`）。見 [FinOps 檢查](../guides/finops-checks.md#cost-allocation-from-cost-explorer)。
## Cost Analysis 工作表 {#cost-analysis-sheet}

使用 `--enable-cost-analysis` 時，預設工作簿有一個 `Cost Analysis` 工作表。它的第一列說明這些數字是根據 AWS Pricing API 得出的估算值，不是你的帳單。各表按以下順序排列：`Summary`、按服務的每月估算費用、最貴的資源（前 50 個）、成本趨勢、可能被遺忘的資源和建議。`Summary` 之後的每張表在沒有列時都會省略。

成本趨勢表的標題是「Billed cost by account and service, last two full months (Cost Explorer; a service total, not a resource's cost)」。每個帳戶和服務一列，來自該帳戶自己的 Cost Explorer 帳單，欄位如下：

| 欄位 | 內容 |
|---|---|
| `Account` | 資源所在的帳戶 ID |
| `Service` | 報告中所用的服務名稱，例如 `EC2` 或 `S3` |
| `Resources` | 該帳戶在報告中該服務的資源數量 |
| `Earlier month` | 執行之前兩個完整月份中較早的一個，格式為 `YYYY-MM` |
| `Billed (USD)`（第一個） | Cost Explorer 在該月對該服務計費的金額 |
| `Later month` | 較晚的月份，格式為 `YYYY-MM` |
| `Billed (USD)`（第二個） | Cost Explorer 在較晚月份對該服務計費的金額 |
| `Change %` | 從較早月份到較晚月份的變化，四捨五入到一位小數。從零帳單開始時，較晚月份有計費則為 100，否則為 0 |
| `Direction` | `increasing` 或 `decreasing`；任一方向的變化小於 5% 時為 `stable` |
| `Billing names counted` | 該列中累加的 Cost Explorer 服務名稱，用逗號分隔 |

金額欄顯示 Cost Explorer 回傳的單位：所有列單位相同時為 `Billed (USD)`，否則為 `Billed (unit as returned)`，此時每個儲存格以其單位結尾。一列是該帳戶中某服務的總額，不是單一資源的成本，也不會在資源之間分攤。服務的數字是其列中所示計費名稱的總和。`EC2 - Other`（磁碟區、NAT 閘道、資料傳輸）是單獨的計費名稱，不在 EC2 的列中；`Amazon EC2 Container Registry (ECR)` 也不在其中。趨勢請求被拒絕或失敗的帳戶，或沒有工作階段的帳戶，沒有任何列，執行會用一則警告說明。月份是執行之前的兩個完整月份。

在 Python 中，同樣的列是 `CloudBOMGenerator.generate_multi_account_bom()` 結果中的 `cost_analysis["cost_trends"]`。每個項目有 `account_id`、`service`、`billing_names`、`resource_count`、`previous_month`、`current_month`、`previous_monthly_cost`、`current_monthly_cost`、`cost_change_percentage`、`trend_direction`、`alert_triggered` 和 `unit`。在 v1.5.0 之前，沒有任何工作表顯示趨勢；`cost_trends` 的每個項目指向一個資源（`resource_id`），內容是服務總額除以其資源數量。這些項目已經移除：從 `cost_trends` 讀取 `resource_id` 的程式碼，必須改為讀取每個帳戶和服務的一個項目。見 [FinOps 檢查](../guides/finops-checks.md#the-cost-trend-of---enable-cost-analysis)。

未針對真實 AWS 驗證：真實帳戶回傳的帳單，包括管理（付款）帳戶和成員帳戶各自看到的內容。

## 策略發現項 {#policy-findings}

`inventag policy check`、`--policy` 以及與 `--template` 一起使用的 `--finops-checks`，會把對狀態快照檢查策略的結果寫入輸出目錄中名為 `policy_findings_<timestamp>.<extension>` 的檔案（`inventag policy check` 則寫入 `--output-directory` 的資料夾）：

| 副檔名 | 格式 | 對應的格式名 |
|---|---|---|
| `.json` | 完整結果 | `json` |
| `.sarif` | SARIF 2.1.0，供程式碼掃描工具使用 | `sarif` |
| `.xml` | JUnit XML，每個策略一個測試案例 | `junit` |
| `.md` | Markdown 表格，每個策略最多 50 列 | `markdown` |

掃描預設寫出 `.json`，除非 `--policy-format` 另有指定。`inventag policy check` 把文字列印到螢幕，除非 `--format` 指定了檔案格式，否則不寫檔案；以結束代碼 1 或 2 結束時不寫任何內容。在 Linux 和 macOS 上，這些檔案只有其擁有者可以讀寫（模式 0600），無論來自掃描還是 `inventag policy check`；InvenTag 為它們新建的資料夾為模式 0700，既有的資料夾保持原有模式。

JSON 檔案有這些頂層鍵：`schema_version`、`inventag_version`、`now`、`snapshot`、`baseline`、`policies`、`summary`、`findings`、`not_evaluated_units`、`not_evaluated_policies` 和 `unused_waivers`。鍵已排序，檔案以換行字元結尾。其中沒有主機名稱、使用者名稱、絕對路徑或時鐘時間，所以相同的快照和策略得到相同的位元組。InvenTag 隨附了它的 JSON Schema（`inventag/policy/outputs/schemas/policy-findings-1.json`）；其 `$id` 是名稱 `urn:inventag:schema:policy-findings:1`，不是網址。

- `findings` 列出結果為 `fail`、`waived` 或 `not_evaluated` 的每一列。`pass` 和策略未選中的列（`out_of_scope`）只計入 `summary` 和每個策略的 `counts`，不會列出。
- `not_evaluated` 發現項有 `reason`：`identity_only`、`field_missing`、`tags_not_read`、`listing_not_read`、`not_comparable`、`not_convertible` 或 `value_too_long`。資料缺口永遠不算通過。
- `not_evaluated_units` 列出掃描中未讀取、而策略本需要的清單。`unused_waivers` 列出沒有匹配任何內容的豁免，並帶有 `why`：`no match`、`expired`、`unknown policy` 或 `superseded`。
- 使用 `inventag policy check` 時，`summary.exit_code` 是 0、7 或 8。在掃描中，它是掃描的結束代碼：0、3、4、5、6 或 7（5、6、3 和 4 優先於 7），文字的最後一行也給出同一個結束代碼。
- 資源欄位的值只有在使用 `--show-values` 時才顯示，被遮蔽的值仍然遮蔽。SARIF 和 JUnit 從不帶值。

在文字和 Markdown 形式中，最後一行說明結束代碼代表什麼，例如 `Exit code 7: at least one finding failed at severity high or higher.` 沒有閾值時為 `Exit code 0: findings are reported; no threshold was set.` 見[結束代碼](./cli.md#exit-codes)。

在使用 `--policy` 的掃描中，最後一行給出掃描的結束代碼：當某個發現項在 `--policy-fail-on` 或更高的嚴重程度上失敗時為 7（掃描從不以 8 退出；只有 `inventag policy check` 會給出 8）。3、4、5 和 6 保持其含義，並在適用時優先；此時最後一行是以下之一：

- `Exit code 3: the template's tag policy found violations (fail_on_tag_violations); this code comes before the policy check's code.`
- `Exit code 4: a security group rule is at or above --risk-threshold; this code comes before the policy check's code.`
- `Exit code 5: an account could not be scanned (--fail-on-account-error); this code comes before the policy check's code.`
- `Exit code 6: no resources were found (--fail-if-empty); this code comes before the policy check's code.`

未驗證：GitHub code scanning 如何顯示 SARIF 檔案，或 GitLab 如何顯示 JUnit 檔案。測試把檔案與黃金檔案（golden）比較，並把 SARIF 檔案與隨 InvenTag 提供的簡短 schema 比較，而不是與完整的 SARIF schema 比較。

## Word 報告 {#word-report}

**不使用範本時：** 一個標題、一份執行摘要、一張服務表，以及每個服務最多 50 個資源，共六欄：Name、Id、Type、Region、Tags 和 Service。如果該服務的資源都沒有名稱，則這六欄是 Id、Type、Region、Tags、Service 和 Source Account Name。

**使用報告範本時：** 即 `word.sections` 中列出的各節。表格的表頭列會在每頁重複，併為螢幕閱讀器標記為表頭。
徽標（如果有）帶有替代文字。

## HTML 報告 {#html-report}

`--create-html` 把報告寫成一個靜態 HTML 檔案
`multi_account_bom_<timestamp>.html`，放在輸出資料夾中，檔名主幹與本次執行的
Excel 和 Word 檔案相同。使用 `--per-account-reports` 時，每個帳戶有自己的
`<account-id>_bom_<timestamp>.html`。用網頁瀏覽器開啟該檔案。

```bash
inventag --create-excel --create-html
```

- 只給 `--create-html` 時只寫 HTML 檔案。同時給 `--create-excel` 或
  `--create-word` 時，除了這些報告，還會寫 HTML 檔案。
- 不帶 `--create-html` 的執行不寫 HTML 檔案，行為不變。
- 執行沒有找到資源時，不寫 HTML 檔案，與 Excel 和 Word 報告相同。
- 使用 `--s3-bucket` 時，HTML 檔案與其他報告一起上傳。InvenTag 上傳時不設定內容型別。
  未針對真實的 AWS 驗證：瀏覽器會從 S3 下載該物件，而不是直接顯示它。

**檔案內容**，按以下順序：

- **摘要：** 按服務統計的資源（含合計）、按區域統計的資源，以及執行說明。
- **按服務列出的資源：** 每個服務一個摺疊的部分。展開一個部分即可看到它的表格。
  每個表格的欄和行與預設 Excel 報告中該服務的工作表相同，機密值同樣顯示為
  `***REDACTED***`。
- **標籤合規：** 標籤策略的摘要，僅當本次執行檢查了標籤策略時出現（例如使用標籤策略範本）。
- **網路分析** 和 **安全分析：** VPC 表和安全組表，僅在使用
  `--enable-network-analysis` 或 `--enable-security-analysis` 時出現。
- **FinOps** 和 **FinOps costs：** 與 Excel 工作表相同的表格，僅在使用
  `--finops-checks` 或 `--finops-cost-allocation` 時出現。
- **覆蓋範圍和錯誤：** 帳戶、每個帳戶中列表呼叫的結束方式（`ok`、`empty`、
  `denied` 及其他結果），以及被拒絕的權限。
  帳戶表的 `Read in part` 欄在帳戶的掃描提前停止，
  或其中有列表沒有讀取時為 `Yes`，與執行說明 “Not read in account” 所列的帳戶相同。

該檔案不包含 `--enable-cost-analysis` 的 Cost Analysis 表格，也不包含
`--policy` 的發現項（它們在 `policy_findings_<timestamp>.json` 中）。
檔案沒有排序、篩選或圖表。

**使用報告範本時：** 使用 `--template` 時，HTML 檔案採用上面描述的版面配置；範本的各個部分只用於
Excel 和 Word 報告，執行會列印一條警告說明這一點。使用 `--word-template` 或
`--excel-template` 時，HTML 檔案使用該範本的文件標題、公司名稱和徽標（先用 Word 範本）。
徽標必須是 PNG 或 JPEG 檔案，並嵌入到檔案中。只給 `--create-html` 時使用
`--excel-template`，執行以結束代碼 2 停止，因為不會寫 Excel 報告。

**檔案的安全性：**

- 來自你帳戶的每個值（名稱、標籤、設定）都經過轉義，因此標籤值中的標記會顯示為文字，絕不會執行。
  文字方向字元和控制字元會被刪除，因此值不會被反轉或重新排序顯示。
- 檔案沒有 JavaScript，也不從檔案外部載入任何內容：沒有來自其他網站的指令碼、樣式表、字型或圖片。
  它的連結只指向同一檔案中的各個部分。它唯一的圖片是範本徽標，以 `data:` URI 嵌入。
- 檔案帶有以下 Content-Security-Policy，告訴瀏覽器不要載入其他任何內容：
  `default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'`。
- 檔案要麼完整寫出，要麼完全不寫，並且與其他報告一樣，只有你的使用者可以讀寫。
- 這個引數不會讓執行把你的資源中的任何值寫入日誌。

:::warning 請把 HTML 檔案保密

HTML 檔案包含來自你的 AWS 帳戶的資料：資源名稱、ID、標籤和設定。
請像對待 Excel 報告一樣對待它。不要把它發佈到網站上，也不要比 Excel 檔案分享得更廣。

:::

檔案帶有列印樣式：它們隱藏目錄，並要求瀏覽器不要把一個表格行拆到兩頁。
未針對瀏覽器驗證：檔案的外觀和列印效果，以及摺疊的部分列印時是否展開。

下面的範例來自針對模擬 AWS 的離線執行（範例資料）。

```html title="multi_account_bom_20261112_090000.html (first lines)"
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; style-src &#x27;unsafe-inline&#x27;; img-src data:; base-uri &#x27;none&#x27;; form-action &#x27;none&#x27;">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AWS Resource Inventory - BOM Report</title>
```

```text title="multi_account_bom_20261112_090000.html (outline)"
AWS Resource Inventory - BOM Report
  Contents
  Summary
      table: Resources by service
      table: Resources by region
  Resources by service
    ATHENA (1) (closed section)
      table: ATHENA resources
    DYNAMODB (1) (closed section)
      table: DYNAMODB resources
    EC2 (4) (closed section)
      table: EC2 resources
    EVENTS (1) (closed section)
      table: EVENTS resources
    IAM (1) (closed section)
      table: IAM resources
    KMS (14) (closed section)
      table: KMS resources
    LAMBDA (1) (closed section)
      table: LAMBDA resources
    S3 (6) (closed section)
      table: S3 resources
    VPC (10) (closed section)
      table: VPC resources
  Coverage and errors
      table: Accounts
      table: Listings by outcome
```

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
  "total_calls": 93,
  "allowed_calls": 93,
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

使用 `--s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/` 時，每次執行都會把檔案放在以該次執行命名的資料夾下：

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090000.xlsx
```

## 終端輸出 {#terminal-output}

不使用 `--verbose` 時，執行會列印警告、錯誤和已寫出的檔案。
使用範本時，每個檔案會列印為 `Wrote <path>`，如果啟用了標籤策略，隨後還有一行標籤策略摘要。不使用範本時，預設報告會列印為 `Data exported to <path>`；使用 `--create-html` 時，HTML 檔案也有自己的一行 `Data exported to <path>`。使用 `--policy` 時，一律會列印策略摘要；`Policy findings: <path>` 這一行以 INFO 層級記錄，只在使用 `--verbose` 時顯示。完全不帶選項時，`inventag` 會列印說明頁面並以結束代碼 2 結束。

## 結束代碼 {#exit-codes}

見[命令列參考](./cli.md#exit-codes)。
