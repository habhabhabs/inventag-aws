---
title: 程式碼如何組合在一起
description: 面向貢獻者的 InvenTag Python 包地圖：CLI、多帳戶編排、發現、處理、範本、報告和狀態。
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
| `inventag/cli/` | 標誌、設定驗證、日誌 | `main.py`, `config_validator.py` |
| `inventag/core/` | 多帳戶編排和憑證 | `cloud_bom_generator.py` |
| `inventag/discovery/` | 發現資源：逐個服務的 API 呼叫、Tagging API、Cost Explorer | `inventory.py`, `comprehensive_discovery.py` |
| `inventag/reporting/` | 規範化資源，並寫出預設的 Excel 和 Word 檔案 | `bom_processor.py`, `converter.py` |
| `inventag/templating/` | 範本載入、驗證、繼承、標籤策略檢查，以及由範本驅動的 Excel 和 Word 輸出 | `schema.py`, `registry.py`, `runner.py` |
| `inventag/state/` | 快照、差異和變更日誌 | `state_manager.py` |
| `inventag/compliance/` | 用於標籤檢查和安全的庫類。標籤策略路徑使用 `checker.py`；CLI 不使用其他類 | `checker.py` |
| `inventag/security/` | 唯讀保護、IAM 策略列表、日誌脫敏、安全的輸出檔案 | `read_only_guard.py`, `iam_policy.py` |

## 共享模組 {#shared-modules}

下面每個模組都是決定其主題的唯一位置。要改變行為，請改這裡，不要改副本。

| 模組 | 決定什麼 |
|---|---|
| `inventag/exit_codes.py` | 結束代碼（0 到 6） |
| `inventag/security/secret_values.py` | 哪些欄位值是機密，會變成 `***REDACTED***` |
| `inventag/discovery/regions.py` | 一次執行掃描哪些區域，以及每個分割槽的主區域 |
| `inventag/discovery/aws_clients.py` | AWS 客戶端的重試設定 |
| `inventag/discovery/coverage.py` | 每個列出呼叫在每個服務和區域的結束方式 |
| `inventag/reporting/settings_loader.py` | 如何讀取和檢查設定檔案 |
| `inventag/reporting/safe_save.py` | 把報告寫到臨時檔案，再移動到位 |
| `inventag/state/partial_results.py` | 為 `--resume` 儲存和複用已完成的帳戶 |

## 資源字典 {#the-resource-dictionary}

從發現到輸出之間的所有環節，傳遞的都是普通字典，每個資源一個。
範本和報告所依賴的欄位列在
[範本參考](../templates/reference.md#resource-fields-you-can-use-as-columns)中。
請保持它們穩定：重新命名其中一個，就會破壞別人的範本。

## 範本如何接入 {#how-templates-hook-in}

`templating/runner.py` 定義了 `TemplatedCloudBOMGenerator`，它是 `CloudBOMGenerator` 的子類，只替換文件生成這一步。
一次執行的其餘部分，包括髮現、憑證和狀態，都保持不變。
不使用 `--template` 時，仍使用原來的類。

## 值得修復的已知缺口 {#known-gaps-worth-fixing}

面向使用者的限制列在[功能狀態](../getting-started/status.md)中。下面是程式碼方面的缺口。
每一項都適合作為入門貢獻：

- `discovery/arn_utils.py` 是建置和比較 ARN 的唯一位置（`build_arn`、`normalize_arn`、
  `ResourceArnIndex`）。`inventory.py` 和 `comprehensive_discovery.py` 都使用它。
  來自 Resource Groups Tagging API 的標籤先按規範化後的 ARN 匹配，再按服務、區域和 ID 匹配。
- 全域性服務（IAM、S3 列表、CloudFront、Route 53、用於 CloudFront 的 WAF、CloudFront 的 ACM 證書）
  每個帳戶從該分割槽的主區域執行一次，區域為 `global`。
- `discovery/inventory.py` 仍有一份包含十四個區域的靜態列表，只在庫呼叫方沒有給出區域時使用。
- 即使使用 `--no-billing-validation`，`--enable-cost-analysis` 也會呼叫 Cost Explorer。
- 一個帳戶失敗不會改變結束代碼，除非你傳入 `--fail-on-account-error`（結束代碼 5）。
- 網路和安全分析在一次執行中會執行兩次（在 BOM 處理器和轉換器中），因此它的 AWS 呼叫也會發出兩次。
- CLI 不會呼叫這些模組：`reporting/template_framework.py`、`branding_system.py`、
  `word_builder.py`、`excel_builder.py`、`document_generator.py` 和 `configuration_manager.py`，
  以及 `discovery/enhanced_readonly_discovery.py`。`reporting/template_framework.py`
  和 `reporting/document_generator.py` 會在 CLI 啟動時被匯入。

較早的設計筆記已從儲存庫中刪除。請使用本站的頁面。
