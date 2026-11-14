---
title: 範本參考
description: InvenTag 範本的每個欄位（report、tag-policy 和 config），包括型別、預設值以及各自的作用。
sidebar_position: 4
---

# 範本參考

**適合誰閱讀：** 你正在編寫或審查範本，需要某個欄位的確切名稱、型別或預設值。

**讀完後你可以：** 不用猜測就能寫出任何範本，並有把握地讀懂驗證錯誤。

## 檔案結構 {#file-layout}

每個範本都是一個 YAML 檔案，頂層欄位相同：

```yaml
format_version: 1          # optional; 1 is the only version
kind: report               # report | tag-policy | config
name: acme-bom             # lower-case letters, digits and hyphens
description: One sentence shown by 'templates list'
extends: standard-bom      # optional: a template name or a relative path
spec:                      # the settings for this kind
  title: Acme Cloud Inventory
```

- 檔案以 `.yaml` 或 `.yml` 結尾，必須是 UTF-8 文字，最大 256 KiB。按路徑給出的檔案也可以是 JSON（`.json`），例如
  `--template ./my.json`。在搜尋資料夾中按名稱查詢的範本必須是 `.yaml` 或 `.yml`，
  `templates init` 寫出的是 `.yaml`。
- 檔名應與 `name` 一致（`acme-bom.yaml` 的 `name: acme-bom`）。按名稱查詢時使用檔名。
- 未知欄位是錯誤，因此拼寫錯誤不會被悄悄放過。
- 重複的鍵是錯誤。
- 帳戶 ID 和十六進位制顏色要放在引號中（`"012345678901"`、`"1F3A5F"`），
  這樣 YAML 會把它們保留為文字。

## 對其他檔案的引用 {#references-to-other-files}

`extends`、`tag_policy`、`report_template` 和 `logo` 可以指向另一個檔案：

- **名稱**（`standard-bom`）會在[搜尋資料夾](./index.md#where-inventag-looks-for-templates)中查詢。
- **相對路徑**（`./policies/strict.yaml`）相對於包含它的範本，並且必須位於該範本所在的資料夾之內。
  離開該資料夾的 `..`、絕對路徑、`~` 和 URL 都會被拒絕。

## 欄位參考 {#field-reference}

本節由程式碼生成
（`python -m inventag.templating.reference --write`），因此始終與驗證器接受的內容一致。

### 所有範本中的欄位 {#fields-in-every-template}

| 欄位 | 型別 | 預設值 | 作用 |
|---|---|---|---|
| `format_version` | 整數（最小 1，最大 1） | `1` | 範本格式版本。目前只有 `1`。 |
| `kind` | `report`、`tag-policy`、`config` 之一 | 必填 | 範本控制什麼：`report`、`tag-policy` 或 `config`。 |
| `name` | 範本名稱 | 必填 | 小寫字母、數字和連字元。應與檔名一致（`my-report.yaml` 的 `name: my-report`）。 |
| `description` | 文字 | 空 | 由 `templates list` 顯示的一句話。 |
| `extends` | 範本名稱或相對路徑 | 未設定 | 要繼承的範本，按名稱或相對路徑指定。必須是同一種 kind。 |
| `spec` | 對應 | 必填 | 該 kind 的設定（見下文）。 |

### 報告範本（`kind: report`） {#report-templates-kind-report}

| 欄位 | 型別 | 預設值 | 作用 |
|---|---|---|---|
| `spec.title` | 文字 | `AWS Resource Inventory` | 報告標題，用於 Word 封面和 Excel 摘要工作表。 |
| `spec.subtitle` | 文字 | 空 | 標題下方的可選一行。 |
| `spec.company_name` | 文字 | 空 | 顯示在封面上並存入檔案屬性的組織名稱。 |
| `spec.colors` | 對應 | 見下文 | 表頭顏色，六位十六進位制值（帶或不帶 `#`）。 |
| `spec.logo` | 相對檔案路徑 | 未設定 | 顯示在 Word 封面上的影象（PNG、JPEG、GIF 或 BMP）。路徑相對於範本檔案，並且必須位於其資料夾之內。 |
| `spec.logo_alt_text` | 文字 | 空 | 徽標的替代文字，供螢幕閱讀器朗讀。預設為 `<company_name> logo`。 |
| `spec.columns` | 對應列表 | 見內建的 `standard-bom` | 資源表的欄，按順序排列。 |
| `spec.tag_columns` | `all`、`none` 或標籤鍵列表 | `all` | 額外的欄，每個標籤鍵一欄，新增在 `columns` 之後。可以是標籤鍵列表，或 `all`（該表中資源上找到的每個標籤鍵），或 `none`。 |
| `spec.tag_policy` | 範本名稱或相對路徑 | 未設定 | 要檢查的標籤策略，按名稱或相對路徑指定。命令列上帶標籤策略的 `--template` 優先。 |
| `spec.excel` | 對應 | 見下文 | Excel 工作簿版面配置。 |
| `spec.word` | 對應 | 見下文 | Word 文件版面配置。 |
| `spec.colors.header_fill` | 十六進位制顏色 | `1F3A5F` | 表頭列的背景。 |
| `spec.colors.header_text` | 十六進位制顏色 | `FFFFFF` | 表頭列的文字顏色。 |
| `spec.columns[].field` | 文字 | 必填 | 要顯示的資源欄位。巢狀值用點表示：`tags.Owner` 是 `Owner` 標籤，`raw_data.InstanceType` 是 AWS API 回應中的值。 |
| `spec.columns[].header` | 文字 | 未設定 | 欄標題。預設是用普通詞語寫出的欄位名（`resource_name` 變為 `Resource name`）。 |
| `spec.columns[].width` | 整數（最小 4，最大 120） | 未設定 | Excel 欄寬，以字元數計。預設是適合內容的寬度，上限為 `excel.max_column_width`。 |
| `spec.excel.summary_sheet` | true 或 false | `true` | 新增一個 Summary 工作表，列出每個服務的資源數量。 |
| `spec.excel.layout` | `per-service`、`single-sheet` 之一 | `per-service` | `per-service` 把每個服務放在各自的工作表上。`single-sheet` 把所有資源放在一個帶 Service 欄的工作表上。 |
| `spec.excel.single_sheet_name` | 文字 | `Resources` | `layout` 為 `single-sheet` 時的工作表名稱。 |
| `spec.excel.include_all_fields` | true 或 false | `false` | 在列出的欄之後，同時新增資源上找到的所有其他欄位。對審計有用；會讓工作表變寬。 |
| `spec.excel.freeze_header` | true 或 false | `true` | 滾動時保持表頭列可見。 |
| `spec.excel.autofilter` | true 或 false | `true` | 在表頭列新增篩選按鈕。 |
| `spec.excel.max_column_width` | 整數（最小 10，最大 120） | `50` | 自動欄寬的上限，以字元數計。 |
| `spec.excel.tag_compliance_sheet` | true 或 false | `true` | 啟用標籤策略時新增 Tag Compliance 工作表。 |
| `spec.word.orientation` | `portrait`、`landscape` 之一 | `portrait` | 頁面方向。 |
| `spec.word.sections` | 取自 `cover`、`summary`、`service-summary`、`tag-compliance`、`service-tables`、`about` 的值列表 | `["cover", "summary", "service-summary", "tag-compliance", "service-tables", "about"]` | 要包含的章節，按順序排列。可選值：`cover`、`summary`、`service-summary`、`tag-compliance`、`service-tables`、`about`。沒有啟用標籤策略時會跳過 `tag-compliance`。 |
| `spec.word.columns` | 對應列表 | 未設定 | 每個服務表的欄。預設是 `columns` 的前 `max_columns` 項。不會新增標籤欄。 |
| `spec.word.max_columns` | 整數（最小 1，最大 12） | `6` | 未設定 `word.columns` 時使用 `columns` 中的多少欄。Word 表格超過六七欄就難以閱讀。 |
| `spec.word.max_rows_per_service` | 整數（最小 1，最大 10000） | `50` | 每個服務表顯示的列數。會有一條說明指出省略了多少行。 |
| `spec.word.max_noncompliant_rows` | 整數（最小 1，最大 10000） | `100` | 不合規資源表中顯示的列數。 |
| `spec.word.columns[].field` | 文字 | 必填 | 要顯示的資源欄位。巢狀值用點表示：`tags.Owner` 是 `Owner` 標籤，`raw_data.InstanceType` 是 AWS API 回應中的值。 |
| `spec.word.columns[].header` | 文字 | 未設定 | 欄標題。預設是用普通詞語寫出的欄位名（`resource_name` 變為 `Resource name`）。 |
| `spec.word.columns[].width` | 整數（最小 4，最大 120） | 未設定 | Excel 欄寬，以字元數計。預設是適合內容的寬度，上限為 `excel.max_column_width`。 |

### 標籤策略範本（`kind: tag-policy`） {#tag-policy-templates-kind-tag-policy}

| 欄位 | 型別 | 預設值 | 作用 |
|---|---|---|---|
| `spec.required_tags` | 對應列表 | 必填 | 範圍內的資源必須具有的標籤。當一個範本 `extends` 另一個範本時，條目按 `key` 合併：相同的鍵會替換，新鍵會新增，`remove: true` 會刪除一個。 |
| `spec.scope` | 對應 | 見下文 | 策略適用於哪些資源。範圍之外的資源會被計數但不會被檢查。 |
| `spec.required_tags[].key` | 文字 | 必填 | 標籤鍵。AWS 標籤鍵區分大小寫，因此 `costcenter` 不能滿足 `CostCenter`。 |
| `spec.required_tags[].description` | 文字 | 空 | 該標籤存在的原因。顯示在報告中。 |
| `spec.required_tags[].allowed_values` | 文字列表 | 未設定 | 如果設定，標籤值必須是其中之一。 |
| `spec.required_tags[].case_sensitive` | true 或 false | `false` | 對 `allowed_values` 區分大小寫地比較。 |
| `spec.required_tags[].pattern` | 正規表示式 | 未設定 | 如果設定，整個標籤值必須匹配此正規表示式（Python 語法）。 |
| `spec.required_tags[].remove` | true 或 false | `false` | 在 `extends` 另一個範本的範本中，從繼承的列表中刪除此標籤。 |
| `spec.scope.services` | 文字列表 | `[]` | 只檢查這些服務（與報告中顯示的一致，例如 `EC2`、`S3`）。為空表示所有服務。 |
| `spec.scope.resource_types` | 文字列表 | `[]` | 只檢查這些資源型別（例如 `Bucket`、`Instance`）。為空表示所有型別。 |
| `spec.scope.exclude_resource_types` | 文字列表 | `[]` | 從不檢查這些資源型別，例如無法攜帶標籤的型別。 |

### config 範本（`kind: config`） {#config-templates-kind-config}

| 欄位 | 型別 | 預設值 | 作用 |
|---|---|---|---|
| `spec.accounts` | 對應列表 | 未設定 | 要掃描的帳戶。省略則掃描你目前 AWS 憑證所屬的帳戶。每個帳戶需要 `profile_name` 或 `role_arn`。 |
| `spec.regions` | 文字列表 | 未設定 | 要掃描的區域（`--account-regions`）。省略則掃描每個已啟用的區域。 |
| `spec.services` | 文字列表 | 未設定 | 要包含的服務（`--account-services`）。目前只在一條發現路徑中生效，因此其他服務仍可能出現。 |
| `spec.outputs` | 取自 `excel`、`word` 的值列表 | `["excel"]` | 要生成的檔案（`--create-excel`、`--create-word`）。 |
| `spec.output_directory` | 文字 | `bom_output` | 報告所在的資料夾（`--output-directory`）。 |
| `spec.report_template` | 範本名稱或相對路徑 | `standard-bom` | 要使用的報告範本，按名稱或相對路徑指定。 |
| `spec.tag_policy` | 範本名稱或相對路徑 | 未設定 | 要檢查的標籤策略，按名稱或相對路徑指定。 |
| `spec.fail_on_tag_violations` | true 或 false | `false` | 如果任何範圍內的資源違反標籤策略，則在寫出報告後以結束代碼 3 結束。需要 `tag_policy`。 |
| `spec.max_concurrent_accounts` | 整數（最小 1，最大 64） | `4` | 同時掃描的帳戶數（`--max-concurrent-accounts`）。 |
| `spec.account_processing_timeout` | 整數（最小 60） | `1800` | 每個帳戶允許的秒數（`--account-processing-timeout`）。 |
| `spec.parallel_processing` | true 或 false | `true` | 平行掃描帳戶。`false` 等同於 `--disable-parallel-processing`。 |
| `spec.accounts[].account_id` | 文字 | 必填 | 12 位 AWS 帳戶 ID，放在引號中，以便 YAML 保留前導零。 |
| `spec.accounts[].account_name` | 文字 | 空 | 報告中使用的易讀名稱。 |
| `spec.accounts[].profile_name` | 文字 | 未設定 | 此帳戶使用的 AWS CLI 設定檔。 |
| `spec.accounts[].role_arn` | 文字 | 未設定 | 在此帳戶中要擔任的 IAM 角色，使用完整 ARN。 |
| `spec.accounts[].external_id` | 文字 | 未設定 | 角色的信任策略所要求的外部 ID。 |
| `spec.accounts[].regions` | 文字列表 | 未設定 | 在此帳戶中要掃描的區域。覆蓋 `spec.regions`。 |
| `spec.accounts[].services` | 文字列表 | 未設定 | 在此帳戶中要掃描的服務。 |

## 可用作欄的資源欄位 {#resource-fields-you-can-use-as-columns}

欄的 `field` 會從每個資源讀取一個值。正常執行產生的資源上都有這些欄位：

| 欄位 | 包含 |
|---|---|
| `service` | 報告中顯示的服務名稱，例如 `S3`、`EC2`、`VPC` |
| `resource_type` | 例如 `Bucket`、`Volume`、`Subnet` |
| `resource_name` | 名稱（如果資源有名稱） |
| `resource_id` | 資源的 ID |
| `arn` | Amazon Resource Name（如果已知） |
| `region` | 區域程式碼 |
| `source_account_id` | 發現該資源所在的帳戶 |
| `source_account_name` | 你給該帳戶設定的 `account_name` |
| `tags` | 所有標籤，寫成 `Key=Value, Key=Value` |
| `tags.<Key>` | 單個標籤的值，例如 `tags.Owner` |
| `tagged` | `Yes` 或 `No` |
| `discovered_via` | 由哪個 API 發現了該資源 |
| `source` | 這一行來自哪裡：`service-api`、`tagging-api` 或 `billing` |
| `sources` | 報告過該資源的所有來源，用 `+` 連線，例如 `service-api+tagging-api` |
| `detail_level` | 服務自己的 API 描述了該資源時為 `full`；只知道其身份（ARN 和標籤）時為 `identity` |
| `raw_data.<Name>` | AWS API 回應中的值，例如 `raw_data.VolumeType` |

在寫出任何報告之前，InvenTag 會把常含機密的欄位的值替換為 `***REDACTED***`。例如 Lambda 環境變數的值、EC2 使用者資料、CloudFormation 引數值和 Glue 連線密碼。名稱會保留，所以你仍能看到該變數存在。如果機密放在 InvenTag 列表之外的欄位中，例如描述或標籤，則不會被識別。

缺失的值留空。要檢視你的資源有哪些欄位，請設定 `excel.include_all_fields: true`，然後檢視多出來的欄。

## 驗證訊息 {#validation-messages}

`inventag templates validate <file>` 以及每個帶 `--template` 的執行，都會按以下格式列印問題：

```text
<file>:<line>: <field>: <what is wrong>
```

例如，一個帶有 `header_fill: blue` 的範本在執行中被使用：

```text title="輸出"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
```

```bash title="Terminal"
echo $?
```

```text title="輸出"
1
```

以及拼錯的範本名稱：

```text title="輸出"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
```

```bash title="Terminal"
echo $?
```

```text title="輸出"
1
```

當一個範本 `extends` 另一個範本時，問題會針對包含它們的檔案報告。

## 結束代碼 {#exit-codes}

| 命令 | 程式碼 | 含義 |
|---|---|---|
| `templates validate` | 0 | 每個檔案都有效 |
| `templates validate` | 1 | 至少有一個檔案有問題 |
| `templates init` | 1 | 輸出檔案已存在（使用 `--force`），或範本無效 |
| `templates init` | 2 | 輸出名稱或副檔名不被允許 |
| `inventag --template ...` | 1 | 範本無效，或執行失敗 |
| `inventag --template ...` | 3 | 報告已寫出，但資源違反標籤策略，且 `fail_on_tag_violations` 為 `true` |
| `inventag --template ...` | 5 | 報告已寫出，但有帳戶無法掃描或超出時間限制，且你傳入了 `--fail-on-account-error` |
| `inventag --template ...` | 6 | 沒有找到任何資源，且你傳入了 `--fail-if-empty` |
