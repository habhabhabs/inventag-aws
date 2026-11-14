---
title: 範本
description: 用可以列出、複製、調整和驗證的小型 YAML 範本，在 InvenTag 中複用報告版面配置、標籤策略和執行設定。
sidebar_position: 1
---

# 範本

**適合誰閱讀：** 需要多次執行 InvenTag，並希望每次都使用相同的報告版面配置、相同的標籤規則或相同的掃描設定的人。

**讀完後你可以：** 選擇一個內建範本，透過 `--template` 使用它，並知道什麼時候該自己製作範本。

## 什麼是範本 {#what-a-template-is}

範本是一個簡短的 YAML 檔案，告訴 InvenTag 如何完成一次執行中的某一部分。範本分三種：

| 種類 | 控制什麼 | 內建範例 |
|---|---|---|
| `report` | Excel 工作簿和 Word 文件的外觀：標題、顏色、欄，以及出現哪些工作表和章節 | `standard-bom`, `executive-summary` |
| `tag-policy` | 每個資源必須有哪些標籤，以及允許哪些值 | `finops-cost-allocation`, `security-baseline` |
| `config` | 掃描什麼、生成什麼：帳戶、區域、輸出檔案，以及使用哪個報告和標籤策略 | `single-account`, `org-multi-account`, `ci-pipeline` |

InvenTag 自帶八個[內建範本](./catalogue.md)。你可以把其中任何一個複製到自己的專案中並[調整它](./adapt-a-template.md)。

## 使用範本 {#use-a-template}

在普通執行中新增 `--template`。你可以給出名稱或檔案路徑：

```bash
inventag --template executive-summary --create-word
inventag --template ./my-templates/acme-bom.yaml --create-excel
```

重複使用 `--template`，可以組合每種各一個的範本：

```bash
inventag --template standard-bom --template security-baseline --create-excel
```

設定發生重疊時，由以下規則決定哪個生效：

1. **你輸入的引數優先。** 如果 config 範本寫了 `outputs: [excel]`，
   而你輸入了 `--create-word`，那麼你只會得到 Word 檔案：你輸入的 `--create-excel` 或
   `--create-word` 會完全替換 `outputs`。
2. **命令列上的範本優先於另一個範本內部的引用。**
   `--template security-baseline` 會替換 `finops-cost-report` 所指定的標籤策略。
3. **沒有報告範本時，InvenTag 使用 `standard-bom`。**

不帶 `--template` 的執行使用原來的報告版面配置。

`--tag-mappings` 和 `--service-descriptions` 會為原來的版面配置新增欄。使用 `--template` 時，報告只顯示它列出的欄，所以這些列在你把它們寫進 `columns`（例如 `- field: service_description`）之前不會出現。InvenTag 會記錄一條警告，指出缺少的欄。參見[欄位列表](./reference.md#resource-fields-you-can-use-as-columns)。

## 標籤策略為報告增加什麼 {#what-a-tag-policy-adds-to-your-reports}

啟用標籤策略後，InvenTag 會檢查範圍內的每個資源，並新增：

- 工作簿中的 **Tag Compliance** 工作表，每個資源一列，說明缺少什麼或哪裡有錯；
- Word 文件中的 **Tag compliance** 章節；
- 一個 `tag_compliance_<timestamp>.json` 檔案，可用於指令碼或 CI；
- 終端中的一行摘要。

使用 `--template finops-cost-report` 離線執行的範例輸出（範例資料）：

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

config 範本可以設定 `fail_on_tag_violations: true`，讓 InvenTag 在有資源違反策略時以結束代碼 3 結束。
內建的 `ci-pipeline` 範本就是這樣做的。

有兩個可選標誌使用各自的結束代碼：`--fail-on-account-error` 在有帳戶無法掃描或超出時間限制時以結束代碼 5 結束，`--fail-if-empty` 在沒有找到任何資源時以結束代碼 6 結束。兩者都優先於結束代碼 3。報告仍然會寫出。

## InvenTag 在哪裡查詢範本 {#where-inventag-looks-for-templates}

當你給出名稱時，InvenTag 會按順序檢查以下資料夾，並使用第一個匹配項：

1. 環境變數 `INVENTAG_TEMPLATE_PATH` 中的每個資料夾（在 Linux 和 macOS 上用 `:` 分隔，
   在 Windows 上用 `;` 分隔）。
2. 你執行 InvenTag 所在資料夾中的 `.inventag/templates/`（你的專案）。
3. `~/.config/inventag/templates/`（或 `$XDG_CONFIG_HOME/inventag/templates/`）。
4. 內建範本。

未針對 Windows 驗證：`INVENTAG_TEMPLATE_PATH` 中的 `;` 分隔符。

因此，一個名為 `.inventag/templates/standard-bom.yaml` 的檔案會在該專案中替換內建的
`standard-bom`。它仍然可以用 `extends: standard-bom` 在原範本的基礎上建置。
執行 `inventag templates list` 可以檢視找到了什麼以及來自哪裡。

## 設計上的安全性 {#safe-by-design}

範本是純資料：

- InvenTag 用安全的 YAML 載入器讀取它們。會建立 Python 物件的 YAML 標籤，
  例如 `!!python/object`，會被拒絕。
- 範本不能執行程式碼、計算表示式，也不能從網際網路獲取任何內容。
- 範本內部的檔案引用（`extends`、`tag_policy`、
  `report_template`、`logo`）必須是相對路徑，並且位於範本所在的資料夾之內。
- config 範本不能包含存取金鑰。請使用 `profile_name` 或 `role_arn`。
- 來自 AWS、以 `=` 開頭的值會作為文字寫入 Excel，因此標籤值不會變成電子表格公式。

## 下一步 {#next-steps}

- [內建範本](./catalogue.md)：每個範本會生成什麼。
- [調整範本](./adapt-a-template.md)：複製、編輯、驗證、執行。
- [範本參考](./reference.md)：每個欄位。
- [範例](../examples/index.md)：使用範本的完整方案。
