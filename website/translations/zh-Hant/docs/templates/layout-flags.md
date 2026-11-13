---
title: 單份報告的版面配置檔案
description: 用 YAML 或 JSON 範本檔案修改 Word 和 Excel BOM 報告的標題、章節、工作表、欄、頁首和頁尾。
sidebar_position: 5
---

# 單份報告的版面配置檔案

本頁介紹 `--word-template` 和 `--excel-template` 引數。每個引數接收一個版面配置檔案，
對應一種報告格式。關於用 `--template` 選擇的命名範本，請參閱[範本](./index.md)。

報告範本是一個 YAML 或 JSON 檔案。範本控制 Word 報告或 Excel 報告的結構。
用 `--word-template` 或 `--excel-template` 把檔案交給 CLI。

如果不提供範本，InvenTag 使用內建的預設範本。此時報告的結構與沒有範本功能的版本相同。

## 範本可以修改什麼 {#what-a-template-can-change}

| 專案 | Word 報告 | Excel 報告 |
|---|---|---|
| 標題和副標題 | 文件的標題部分 | 工作簿屬性，以及摘要表上方的可選行 |
| 公司名稱 | `{{ company_name }}` 的值 | `{{ company_name }}` 的值，以及工作簿的建立者屬性 |
| 徽標 | 標題上方的 PNG 或 JPEG 檔案 | 不可用 |
| 章節或工作表 | 顯示哪些章節及其順序 | 顯示哪些工作表及其順序 |
| 欄 | 顯示哪些欄，以及它們的順序、標題和寬度 | 顯示哪些欄，以及它們的順序、標題和寬度 |
| 服務 | 資源表中出現哪些服務及其順序 | 哪些服務有工作表及其順序 |
| 頁首和頁尾 | 頁首、頁尾、頁碼 | 每個工作表的列印頁首和列印頁尾 |
| 表頭列顏色 | 不可用 | 表頭列的填充顏色 |
| 自由文字 | 帶變數的標題和段落 | 不可用 |

## 製作範本 {#make-a-template}

1. 把預設範本列印到檔案。

   ```bash
   inventag --print-default-template word > my_word_template.yaml
   inventag --print-default-template excel > my_excel_template.json
   ```

2. 編輯檔案。參見[鍵參考](#key-reference)。

3. 驗證檔案。此命令不會發出任何 AWS 呼叫。

   ```bash
   inventag --validate-templates \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

   如果檔案有效，CLI 會為每個檔案列印一列 `OK`，並以結束代碼 `0` 結束。

4. 在執行中使用該檔案。

   ```bash
   inventag --create-word --create-excel \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

CLI 接受 `.yaml`、`.yml` 和 `.json` 這幾種副檔名，兩種格式均適用。預設範本檔案也在儲存庫中：
`templates/default_word_template.yaml` 和
`templates/default_excel_template.json`。

## 範本引數 {#template-flags}

| 引數 | 功能 |
|---|---|
| `--word-template PATH` | Word 報告的範本。此引數需要 `--create-word`。 |
| `--excel-template PATH` | Excel 報告的範本。此標誌需要 `--create-excel`。沒有它，CLI 會以結束代碼 `2` 停止。 |
| `--print-default-template word` 或 `--print-default-template excel` | 列印預設範本並以結束代碼 `0` 結束。 |
| `--validate-templates` | 驗證 `--word-template` 和 `--excel-template` 指定的檔案，然後結束。不發出 AWS 呼叫。 |

## 最小範例 {#minimal-examples}

這個 Word 範本包含一個標題、每個服務一張資源表，以及一張摘要表。

```yaml title="my_word_template.yaml"
template_version: "2.0"
format_type: word
document:
  title: "{{ company_name }} Cloud Inventory"
  subtitle: "Accounts: {{ account_ids }}"
branding:
  company_name: Example Corp
header_footer:
  header_text: "{{ company_name }} - Internal"
  footer_text: "Generated {{ generated_date }}"
  include_page_numbers: true
sections:
  - id: title
    content_type: title
  - id: inventory
    content_type: resources
    title: Resources
    service_title: "{{ service }} ({{ service_resource_count }})"
    columns:
      - field: name
        heading: Resource name
        width: 2.5
      - field: region
      - field: tags.Owner
        heading: Owner
  - id: summary
    content_type: service_summary
    title: "Summary of {{ total_resources }} resources"
```

這個 Excel 範本包含一個列出所有資源的工作表，然後是摘要工作表。

```json title="my_excel_template.json"
{
  "template_version": "2.0",
  "format_type": "excel",
  "document": {"title": "{{ company_name }} inventory"},
  "branding": {"company_name": "Example Corp", "header_color": "1F4E78"},
  "sections": [
    {
      "id": "all_resources",
      "content_type": "resources",
      "group_by_service": false,
      "sheet_name": "All resources",
      "columns": [
        {"field": "service", "heading": "Service", "width": 14},
        {"field": "name", "heading": "Name"},
        {"field": "region", "heading": "Region"},
        {"field": "tags.Owner", "heading": "Owner"}
      ]
    },
    {
      "id": "summary",
      "content_type": "service_summary",
      "sheet_name": "Summary",
      "show_title": true
    }
  ]
}
```

## 變數 {#variables}

在文字值中把變數寫成 `{{ name }}`。InvenTag 在寫入報告時用變數的值替換它。

| 變數 | 值 |
|---|---|
| `{{ company_name }}` | `branding.company_name` 的值。 |
| `{{ document_title }}` | 替換之後的 `document.title` 的值。 |
| `{{ document_subtitle }}` | 替換之後的 `document.subtitle` 的值。 |
| `{{ generated_at }}` | UTC 生成時間，格式為 `YYYY-MM-DD HH:MM:SS`。 |
| `{{ generated_date }}` | UTC 生成日期，格式為 `YYYY-MM-DD`。 |
| `{{ account_ids }}` | 報告中的帳戶 ID，已排序，以逗號加空格分隔。 |
| `{{ account_count }}` | 報告中不同帳戶 ID 的數量。 |
| `{{ total_resources }}` | 報告中的資源數量。 |
| `{{ service_count }}` | 報告中不同服務的數量。 |
| `{{ region_count }}` | 報告中不同區域的數量。 |

下面這些變數只在 Word `resources` 章節的 `service_title` 和 `truncation_note` 中有效：

| 變數 | 值 |
|---|---|
| `{{ service }}` | 目前表格的服務名稱。 |
| `{{ service_resource_count }}` | 目前服務的資源數量。 |
| `{{ shown_resource_count }}` | 目前表格中的列數。 |

你可以在 `variables` 下定義自己的變數：

```yaml
variables:
  classification: Internal
header_footer:
  footer_text: "Classification: {{ classification }}"
```

變數規則：

- 變數名只能包含字母、數字和下劃線。
- 自定義變數的名稱以小寫字母開頭，只能包含小寫字母、數字和下劃線。
- 自定義變數不能使用內建變數的名稱。
- 變數的值是純文字。值中不能包含另一個變數。
- `document.title` 和 `document.subtitle` 不能使用 `{{ document_title }}`
  或 `{{ document_subtitle }}`。
- 以下鍵接受變數：`document.title`、`document.subtitle`、
  `header_footer.header_text`、`header_footer.footer_text`，以及章節鍵
  `title`、`paragraphs`、`service_title` 和 `truncation_note`。
- 欄標題、工作表名稱和 `branding.company_name` 不接受變數。
- InvenTag 不支援表示式、過濾器、條件、迴圈或檔案包含。例如，`{{ company_name | upper }}` 是錯誤。
- InvenTag 不會替換資源資料中的變數。名稱中含有文字 `{{ company_name }}` 的資源，
  在報告中保持原樣。

## 鍵參考 {#key-reference}

`tests/unit/test_template_system.py` 中的一個測試會確保本參考包含
`inventag/reporting/report_template.py` 中模式的每一個鍵。

### 頂層鍵 {#top-level-keys}

| 鍵 | 型別 | 格式 | 預設值 | 說明 |
|---|---|---|---|---|
| `template_version` | 字串 | Word 和 Excel | 必填 | 模式版本。必須是 `"2.0"`。 |
| `format_type` | 字串 | Word 和 Excel | 必填 | `word` 或 `excel`。 |
| `name` | 字串 | Word 和 Excel | 空 | 範本的名稱。不會顯示在報告中。 |
| `description` | 字串 | Word 和 Excel | 空 | 說明。不會顯示在報告中。 |
| `document` | 對應 | Word 和 Excel | 見下文 | 標題和副標題。 |
| `branding` | 對應 | Word 和 Excel | 見下文 | 公司名稱、徽標和顏色。 |
| `variables` | 對應 | Word 和 Excel | 空 | 你自己的變數：名稱對應文字。 |
| `extra_fields` | 列表 | Word 和 Excel | 空 | `columns` 可以使用的更多資源欄位名。例如，來自你的標籤對應的欄。 |
| `header_footer` | 對應 | Word 和 Excel | 見下文 | 頁首和頁尾文字。 |
| `sections` | 列表 | Word 和 Excel | 必填 | 章節（Word）或工作表（Excel），按報告順序排列。 |

### `document` {#document}

| 鍵 | 型別 | 格式 | 預設值 | 說明 |
|---|---|---|---|---|
| `title` | 字串 | Word 和 Excel | 空 | Word：`title` 章節的文字。Excel：工作簿的標題屬性。 |
| `subtitle` | 字串 | Word 和 Excel | 空 | Word：標題下方的一行。Excel：工作簿的主題屬性。 |

### `branding` {#branding}

| 鍵 | 型別 | 格式 | 預設值 | 說明 |
|---|---|---|---|---|
| `company_name` | 字串 | Word 和 Excel | 空 | `{{ company_name }}` 的值。Excel：同時也是工作簿的建立者屬性。 |
| `logo_path` | 字串 | Word | 無 | 顯示在標題上方的 PNG 或 JPEG 檔案。路徑相對於範本檔案，且必須位於其目錄之內。 |
| `logo_width_inches` | 數字 | Word | `1.5` | 徽標寬度，0.25 到 7。 |
| `header_color` | 字串 | Excel | `366092` | 表頭列的填充顏色，六位十六進位制數字。 |

### `header_footer` {#header_footer}

| 鍵 | 型別 | 格式 | 預設值 | 說明 |
|---|---|---|---|---|
| `header_text` | 字串 | Word 和 Excel | 空 | Word：頁首。Excel：每個工作表的列印頁首。最多 255 個字元。 |
| `footer_text` | 字串 | Word 和 Excel | 空 | Word：頁尾。Excel：每個工作表的列印頁尾。最多 255 個字元。 |
| `include_page_numbers` | 布林值 | Word | `false` | 在頁尾中新增 `Page <number>`。 |

Excel 的列印頁首和列印頁尾只會在頁面佈局檢視和紙張上顯示。

### `sections` {#sections}

`sections` 的每個條目都是一個對應。`content_type` 鍵決定該章節顯示什麼。

| `content_type` | 格式 | 功能 |
|---|---|---|
| `title` | Word | 文件標題、副標題和徽標。 |
| `text` | Word | 一個可選的標題和一組段落。 |
| `service_summary` | Word 和 Excel | 每個服務一列：名稱、資源數量、百分比。在 Word 中是一張表，在 Excel 中是一個工作表。 |
| `resources` | Word 和 Excel | 資源表。Word：每個服務一張表。Excel：每個服務一個工作表，或所有資源共用一個工作表。 |
| `network_analysis` | Excel | 網路分析工作表。只有存在網路分析資料時，InvenTag 才會寫入它。 |
| `security_analysis` | Excel | 安全分析工作表。只有存在安全分析資料時，InvenTag 才會寫入它。 |
| `cost_analysis` | Excel | 成本分析工作表。只有存在成本分析資料時，InvenTag 才會寫入它（--enable-cost-analysis）。 |

章節鍵：

| 鍵 | 型別 | 格式 | 章節型別 | 預設值 | 說明 |
|---|---|---|---|---|---|
| `id` | 字串 | Word 和 Excel | 全部 | 必填 | 章節的唯一名稱：小寫字母、數字和下劃線。 |
| `content_type` | 字串 | Word 和 Excel | 全部 | 必填 | 章節顯示什麼。 |
| `enabled` | 布林值 | Word 和 Excel | 全部 | `true` | 設為 `false` 可省略該章節。 |
| `title` | 字串 | Word | `text`、`service_summary`、`resources` | 空 | 章節的標題文字。 |
| `level` | 整數 | Word | `text`、`service_summary`、`resources` | `1` | 標題級別，1 到 3。服務標題使用下一級。 |
| `page_break_before` | 布林值 | Word | 全部 | `false` | 讓章節從新的一頁開始。 |
| `paragraphs` | 列表 | Word | `text` | 空列表 | `text` 章節的段落。 |
| `columns` | `auto` 或列表 | Word 和 Excel | `service_summary`、`resources` | `auto` | `auto`，或欄的列表。參見[欄](#columns)。 |
| `table_style` | 字串 | Word | `service_summary`、`resources` | `service_summary` 為 `Light Grid Accent 1`，`resources` 為 `Light List Accent 1` | Word 表格樣式。 |
| `services` | 列表 | Word 和 Excel | `resources` | 所有服務 | 只顯示這些服務，並按此順序。比較時忽略大小寫、空格以及字首 `Amazon` 和 `AWS`。 |
| `service_title` | 字串 | Word | `resources` | `{{ service }} Resources ({{ service_resource_count }})` | 每個服務表的標題。 |
| `max_rows` | 整數 | Word | `resources` | `50` | 每個服務表的最大列數，1 到 100000。 |
| `max_columns` | 整數 | Word | `resources` | `6` | 當 `columns` 為 `auto` 時的最大欄數，1 到 100。 |
| `truncation_note` | 字串 | Word | `resources` | `Note: Showing first {{ shown_resource_count }} of {{ service_resource_count }} {{ service }} resources.` | 未顯示全部資源的表格下方的段落。 |
| `page_break_after_service` | 布林值 | Word | `resources` | `true` | 在每個服務表之後另起一頁。 |
| `sheet_name` | 字串 | Excel | `service_summary`、`resources` | `service_summary` 為 `Summary` | 工作表名稱，1 到 31 個字元。對於 `group_by_service: false` 的 `resources` 章節，此項必填。 |
| `group_by_service` | 布林值 | Excel | `resources` | `true` | `true`：每個服務一個工作表。`false`：所有資源共用一個工作表。 |
| `show_title` | 布林值 | Excel | `service_summary` | `false` | 在表格上方寫入文件標題和副標題。 |

注意：

- Word 文件按列表的順序顯示章節。
- 工作簿按列表的順序顯示工作表。
- 使用 `group_by_service: true` 時，每個工作表以其服務的名稱命名。
- Word 的 `resources` 章節按名稱對服務排序，除非你給出 `services`。
- `table_style` 的有效值是預設 Word 文件中的表格樣式。例如 `Table Grid`、`Light List Accent 1`、
  `Light Grid Accent 1` 和 `Medium Shading 1 Accent 1`。

### 欄 {#columns}

`columns` 鍵是 `auto` 或一個列表。列表的每個條目是一個欄位名，或者是帶有以下鍵的對應：

| 鍵 | 型別 | 格式 | 預設值 | 說明 |
|---|---|---|---|---|
| `field` | 字串 | Word 和 Excel | 必填 | 要顯示的欄位。 |
| `heading` | 字串 | Word 和 Excel | 見下文 | 欄標題。 |
| `width` | 數字 | Word 和 Excel | 自動 | 欄寬。Word：英寸，0.2 到 10。Excel：字元數，1 到 255。 |

預設標題：

- Word：把欄位名轉換為帶空格和大寫字母的形式。例如，
  `source_account_id` 變為 `Source Account Id`。
- Excel：欄位名。

`auto` 的功能：

- Word `resources` 章節：每個服務最多 `max_columns` 個欄位。如果服務有這些欄位，
  最先出現的是 `name`、`id`、`type`、`region`、
  `compliance_status` 和 `tags`。
- Excel `resources` 章節：該工作表上資源的所有欄位。
- `service_summary` 章節：`service`、`resource_count` 和 `percentage`。

`service_summary` 章節的欄位：`service`、`resource_count`、
`percentage`。

`resources` 章節的欄位：

| 分組 | 欄位 |
|---|---|
| 標識 | `service`, `type`, `id`, `name`, `arn` |
| 帳戶和位置 | `account_id`, `source_account_id`, `source_account_name`, `account_name`, `region`, `availability_zone` |
| 資源詳情 | `status`, `state`, `creation_date`, `created_time`, `launch_time`, `size`, `instance_type`, `storage_type`, `engine`, `engine_version`, `allocated_storage`, `storage_encrypted`, `multi_az`, `publicly_accessible`, `vpc_id`, `vpc_name`, `subnet_id`, `subnet_name`, `security_groups`, `security_group_ids` |
| 網路 | `vpc_cidr_block`, `vpc_total_ips`, `vpc_utilization_percentage`, `subnet_cidr_block`, `subnet_total_ips`, `subnet_utilization_percentage`, `subnet_is_public`, `subnet_availability_zone` |
| 安全 | `security_risk_level`, `security_group_count`, `max_security_risk`, `inbound_rules_count`, `outbound_rules_count`, `associated_resources_count`, `has_permissive_rules`, `permissive_rules` |
| 成本 | `estimated_monthly_cost`, `cost_breakdown`, `pricing_model`, `confidence_level`, `cost_optimization_opportunities`, `monthly_spend`, `service_monthly_spend`, `billing_validated` |
| 發現與合規 | `compliance_status`, `compliance_score`, `discovery_timestamp`, `consolidation_timestamp`, `total_accounts_in_consolidation`, `discovered_at`, `discovered_via`, `priority`, `tagged`, `tags`, `service_description`, `resource_id`, `resource_name`, `resource_type` |
| 單個標籤 | `tags.<key>`，例如 `tags.Owner` |
| 單個原始 API 屬性 | `raw_data.<key>`，例如 `raw_data.InstanceType` |
| 你自己的欄位 | `extra_fields` 中的每個名稱 |

如果資源沒有某個欄位，單元格為空。`tags` 欄位會在一個單元格中顯示資源的所有標籤。

## 驗證錯誤 {#validation-errors}

CLI 在第一次 AWS 呼叫之前驗證每個範本。如果範本無效，CLI 會向標準錯誤輸出為每個問題列印一列，
並以結束代碼 `1` 結束。每一行的格式如下：

```text
inventag: error: <file>: <key path>: <reason>
```

範例：

```text
inventag: error: my_word_template.yaml: colour: unknown key. Allowed keys: template_version, format_type, name, description, document, branding, variables, extra_fields, header_footer, sections
inventag: error: my_word_template.yaml: sections[1].columns[2].field: unknown column 'owner_name'. Use a known field (for example service, type, id, name, region, account_id, tags), a tags.<key> field, or add the name to extra_fields
```

| 問題 | 原因的開頭 |
|---|---|
| 模式中沒有的鍵 | `unknown key. Allowed keys: ...` |
| 屬於另一種報告格式的鍵 | `this key is not valid in a Word template` 或 `this key is not valid in an Excel template` |
| 值的型別錯誤 | `must be a string, but the value is integer` |
| 缺少必填鍵 | `missing key` |
| 不存在的章節型別 | `unknown section type 'cover_page' for a Word template. Allowed values: ...` |
| 不存在的欄 | `unknown column 'owner_name'` |
| 不存在的變數 | `unknown variable 'owner'. Allowed variables: ...` |
| 表示式、過濾器或巢狀的大括號 | `malformed placeholder` |
| 兩個章節使用相同的 `id` | `duplicate id 'summary'` |
| 範本的格式錯誤 | `the file is a template for Excel reports, but this flag needs a template for Word reports` |
| 帶有 `template_version: "1.0"` 的舊範本 | `unsupported version '1.0'` |
| 超出範本目錄的徽標路徑 | `the path must stay in the directory of the template file` |
| 不是 YAML 或 JSON 的檔案 | `YAML syntax error at line ...` 或 `JSON syntax error at line ...` |
| 副檔名不同的檔案 | `unsupported file type` |
| 過大的檔案 | `The maximum is 262144 bytes` |

範本引數的結束代碼：

| 結束代碼 | 條件 |
|---|---|
| `0` | `--validate-templates` 未發現問題，或 `--print-default-template` 列印了範本。 |
| `1` | 範本檔案無效。 |
| `2` | 用法錯誤。例如，使用 `--word-template` 而沒有 `--create-word`，或使用 `--validate-templates` 而沒有範本引數。 |

## 限制 {#limits}

| 專案 | 限制 |
|---|---|
| 範本檔案大小 | 262144 位元組（256 KiB） |
| 文字值 | 2000 個字元 |
| 頁首文字和頁尾文字 | 255 個字元 |
| 章節 | 50 |
| 一個章節中的欄 | 100 |
| 一個 `text` 章節中的段落 | 100 |
| 你自己的變數 | 50 |
| `extra_fields` 中的條目 | 200 |
| 徽標檔案大小 | 5242880 位元組（5 MiB） |
| 徽標檔案型別 | `.png`, `.jpg`, `.jpeg` |
| Excel 工作表名稱 | 31 個字元，不能包含 `[ ] : * ? / \` |

其他限制：

- 範本不能更改 Word 報告的字型、標題顏色或頁面大小。
- 範本不能更改網路分析工作表和安全分析工作表的欄。
- 範本不能在 Excel 報告中新增目錄、圖表或徽標。
- Word 表格樣式必須是預設 Word 文件中的樣式。
- `scripts/legacy/` 中的舊指令碼沒有範本引數。
- 舊設定範例中的設定鍵 `templates`、`document_templates` 和
  `default_template` 沒有任何作用。只有 `--word-template` 和 `--excel-template` 會選擇範本。
- 帶有 `template_version: "1.0"` 的範本檔案無效。1.0.0 之前的 alpha 建置都附帶了這類檔案，
  但 CLI 並不會讀取它們。

## 範本檔案的安全性 {#safety-of-template-files}

- InvenTag 用 `yaml.safe_load` 讀取 YAML。YAML 檔案無法執行程式碼。
- InvenTag 不會計算表示式。替換隻會替換[變數](#variables)表中的名稱。
- InvenTag 不會替換來自 AWS 的資源資料中的變數。
- 範本不能包含另一個檔案。唯一的檔案引用是 `branding.logo_path`，
  而且該檔案必須位於範本目錄中。
- Excel 建置器把每個值都存為文字。以 `=` 開頭的值不會作為公式執行。
