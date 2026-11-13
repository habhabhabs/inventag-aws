---
title: 程式碼如何組合在一起
description: 面向貢獻者的 InvenTag Python 包地圖：CLI、多賬戶編排、發現、處理、模板、報告和狀態。
sidebar_position: 2
slug: /architecture/core-module-integration
---

# 程式碼如何組合在一起

**適合誰閱讀：** 想要熟悉程式碼結構的貢獻者。

**讀完後你會知道：** 一次執行中每個模組負責什麼，以及做某項更改應該從哪裡入手。

## 一次執行的路徑 {#the-path-of-one-run}

```text
inventag_cli.py
  -> inventag/cli/main.py              parse flags, validate, set up logging
       -> templating/runner.py         only with --template: load templates,
                                       apply a config template to the flags
  -> core/cloud_bom_generator.py       CloudBOMGenerator
       1. sessions per account         profiles, keys or sts:AssumeRole
       2. discovery per account        discovery/inventory.py and friends
       3. consolidation                one list of resource dictionaries
       4. documents                    reporting/bom_processor.py, then
                                       reporting/converter.py (default) or
                                       templating/render_excel.py and
                                       render_word.py (with --template)
       5. state                        state/ snapshots and changelog
```

## 各個包 {#packages}

| 包 | 職責 | 從哪裡入手 |
|---|---|---|
| `inventag/cli/` | 標誌、配置驗證、日誌 | `main.py`, `config_validator.py` |
| `inventag/core/` | 多賬戶編排和憑證 | `cloud_bom_generator.py` |
| `inventag/discovery/` | 發現資源：逐個服務的 API 呼叫、Tagging API、Cost Explorer | `inventory.py`, `comprehensive_discovery.py` |
| `inventag/reporting/` | 規範化資源，並寫出預設的 Excel 和 Word 檔案 | `bom_processor.py`, `converter.py` |
| `inventag/templating/` | 模板載入、驗證、繼承、標籤策略檢查，以及由模板驅動的 Excel 和 Word 輸出 | `schema.py`, `registry.py`, `runner.py` |
| `inventag/state/` | 快照、差異和變更日誌 | `state_manager.py` |
| `inventag/compliance/` | 用於標籤檢查和安全的庫類；目前 CLI 基本不使用 | `checker.py` |
| `inventag/security/` | 只讀保護、IAM 策略列表、日誌脫敏、安全的輸出檔案 | `read_only_guard.py`, `iam_policy.py` |

## 資源字典 {#the-resource-dictionary}

從發現到輸出之間的所有環節，傳遞的都是普通字典，每個資源一個。
模板和報告所依賴的欄位列在
[模板參考](../templates/reference.md#resource-fields-you-can-use-as-columns)中。
請保持它們穩定：重新命名其中一個，就會破壞別人的模板。

## 模板如何接入 {#how-templates-hook-in}

`templating/runner.py` 定義了 `TemplatedCloudBOMGenerator`，它是 `CloudBOMGenerator` 的子類，只替換文件生成這一步。
一次執行的其餘部分，包括髮現、憑證和狀態，都保持不變。
不使用 `--template` 時，仍使用原來的類，輸出與以前完全一樣。

## 值得修復的已知缺口 {#known-gaps-worth-fixing}

這些缺口記錄在[功能狀態](../getting-started/status.md)以及 `CHANGELOG.md` 的 "Open work" 列表中。
每一項都適合作為入門貢獻：

- `discovery/arn_utils.py` 是構建和比較 ARN 的唯一位置
  （`build_arn`、`normalize_arn`、`ResourceArnIndex`）。`inventory.py` 和
  `comprehensive_discovery.py` 都使用它。來自 Resource Groups Tagging API 的標籤，
  先按規範化後的 ARN 匹配，再按服務、區域和 ID 匹配。
- 全域性服務（IAM、S3 列表、CloudFront、Route 53、CloudFront 的 ACM 證書）
  對每個賬戶從 `us-east-1` 執行一次，並帶有區域 `global`。
- 當 `DescribeRegions` 失敗時，`cloud_bom_generator.py` 中的區域查詢會回退到四個區域。
  `discovery/inventory.py` 使用另一份包含十四個區域的回退列表。
- 對於已有內建模板的服務（S3、EC2、RDS、Lambda、VPC），服務描述檔案中自定義的 `description` 會被忽略。
- 即使使用了 `--no-billing-validation`，`--enable-cost-analysis` 仍會呼叫 Cost Explorer。
- 一個賬戶失敗並不會改變退出碼。
- 這些模組不在 CLI 的執行路徑上：`reporting/template_framework.py`、
  `branding_system.py`、`word_builder.py`、`excel_builder.py`、
  `document_generator.py` 和 `configuration_manager.py`。

較早的設計筆記已從倉庫中刪除。請使用本站的頁面。
