---
title: 調整範本
description: 把 InvenTag 範本複製到你的專案中，只修改需要改的部分，用 templates validate 檢查，然後在執行中使用它。
sidebar_position: 3
---

# 調整範本

**適合誰閱讀：** 你喜歡某個內建範本，但想要自己的標題、顏色、欄或標籤規則。

**讀完後你可以：** 分四步建立自己的範本：`init`、編輯、`validate`、執行。

下面的輸出來自針對模擬 AWS 的離線執行（範例資料）。你的專案資料夾顯示為 `~/acme-infra/`。

## 1. 把範本複製到你的專案中 {#1-copy-the-template-into-your-project}

在你的專案資料夾中執行：

```bash
inventag templates init standard-bom --output .inventag/templates/acme-bom.yaml --extend
```

```text title="輸出"
Created .inventag/templates/acme-bom.yaml (kind: report, name: acme-bom).
Next: edit it, then run 'inventag templates validate .inventag/templates/acme-bom.yaml'.
```

你有兩種選擇：

- **`--extend`**（上面使用的）會寫出一個簡短的檔案，繼承 `standard-bom` 的所有內容。
  你只需新增想要更改的部分，並且可以免費獲得內建範本的改進。
- **不使用 `--extend`** 會得到帶有全部註釋的完整副本。當你想檢視並掌控每一項設定時，請使用這種方式。

範本名稱來自檔名（`acme-bom.yaml` 變成 `acme-bom`）。用 `--name` 可以選擇其他名稱，
用 `--force` 可以替換已有的檔案。

由於該檔案位於 `.inventag/templates/` 中，現在你可以在這個專案裡按名稱引用它。

## 2. 編輯範本 {#2-edit-it}

新檔案如下所示：

```yaml title=".inventag/templates/acme-bom.yaml"
# Inherits everything from 'standard-bom'. Add only what you want to change.
# See: inventag templates show standard-bom --resolved
format_version: 1
kind: report
name: acme-bom
description: "Adapted from standard-bom"
extends: standard-bom
spec: {}
```

把 `spec: {}` 替換成你的更改。這個版本把所有內容放在一個工作表上，使用綠色表頭，並顯示三個標籤欄：

```yaml
format_version: 1
kind: report
name: acme-bom
description: "Acme's inventory layout"
extends: standard-bom
spec:
  title: Acme Cloud Inventory
  company_name: Acme Ltd
  colors:
    header_fill: "0B5D1E"
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
```

繼承的工作方式：

- **對應會合並。** 設定 `excel.layout` 會保留 `standard-bom` 中 `excel` 的其他所有設定。
- **列表會替換。** 如果你設定了 `columns`，你的列表會替換繼承來的列表。請複製你想保留的條目。
- **`null` 會把值重置**為預設值，例如 `tag_policy: null`。
- **標籤策略按鍵合併 `required_tags`。** 子策略可以修改某個標籤、新增標籤，或用 `remove: true` 刪除某個標籤，而無需重複其餘部分。

要檢視繼承之後的最終結果，請執行
`inventag templates show acme-bom --resolved`。

## 3. 驗證範本 {#3-validate-it}

```bash
inventag templates validate acme-bom
```

也可以給出檔案路徑，例如 `inventag templates validate ./acme-bom.yaml`。任何包含點或斜槓的引用都會被當作路徑。

如果有錯誤，你會得到檔案、行號和提示。這裡把單詞 `layout` 誤拼成了 `layuot`：

```text title="輸出"
ERROR ~/acme-infra/.inventag/templates/acme-bom.yaml:13: spec.excel.layuot: unknown field 'layuot'; did you mean 'layout'? Allowed here: autofilter, freeze_header, include_all_fields, layout, max_column_width, single_sheet_name, summary_sheet, tag_compliance_sheet
(exit code 1)
```

修正之後：

```text title="輸出"
OK    ~/acme-infra/.inventag/templates/acme-bom.yaml (report 'acme-bom')
```

當每個檔案都有效時，`validate` 以 0 退出，否則以 1 退出，因此你可以在 CI 中執行它。
它還會檢查你引用的範本（例如 `tag_policy`）是否存在，以及種類是否正確。

現在你的範本會出現在列表中：

```bash title="Terminal"
inventag templates list --kind report
```

```text title="輸出"
NAME                KIND    SOURCE   DESCRIPTION
acme-bom            report  project  Acme's inventory layout
board-report        report  project  Branded summary for the leadership team
executive-summary   report  builtin  Short Word report with totals and tag compliance; Excel has one filterable sheet.
finops-cost-report  report  builtin  Standard layout with cost-allocation tag columns, checked against finops-cost-allocation.
network-review      report  project  Every field, for a network review
standard-bom        report  builtin  Summary plus one sheet per service, with readable columns and every tag as a column.
team-sheet          report  project  One sheet, our columns

Search order (first match wins):
  1. project  ~/acme-infra/.inventag/templates
  2. user     ~/.config/inventag/templates  (not created)
  3. builtin  ~/inventag-aws/inventag/templating/builtin
```

範例專案中還包含這些文件中使用的其他範本。

## 4. 使用範本 {#4-use-it}

```bash
inventag --template acme-bom --create-excel --account-regions us-east-1
```

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`Resources`

`Resources` 工作表的前幾列：

| Account | Region | Service | Type | Name | ID | ARN | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs | platform | CC-1001 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake | data | CC-2002 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports | finance | 1234 | Production |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | acme-scratch | arn:aws:s3:::acme-scratch |  |  |  |

表頭列是綠色的，與範本中的設定一致。

## 與團隊共享範本 {#share-templates-with-your-team}

- **一個專案：** 把 `.inventag/templates/` 提交到該專案的儲存庫。
- **你機器上的每個專案：** 把範本放在 `~/.config/inventag/templates/`。
- **共享資料夾或 CI 映象：** 設定
  `INVENTAG_TEMPLATE_PATH=/opt/acme/inventag-templates`。

如果兩個資料夾中有同名的範本，則以[搜尋順序](./index.md#where-inventag-looks-for-templates)中靠前的為準。
`inventag templates list --all` 也會顯示被隱藏的範本。

## 下一步 {#next-steps}

- [範本參考](./reference.md)：你可以設定的每個欄位。
- [製作帶品牌標識的高管 Word 報告](../examples/branded-executive-report.md)：
  新增徽標。
