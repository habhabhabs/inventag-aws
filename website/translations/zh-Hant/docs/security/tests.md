---
title: 測試
description: InvenTag 如何測試：測試套件覆蓋什麼、無法證明什麼、如何執行，以及 CI 在哪些 Python 版本上執行它。
sidebar_position: 2
---

# 測試

**適合誰閱讀：** 正在判斷該在多大程度上信任 InvenTag 的人，以及要修改程式碼的人。

**讀完後你會了解：** 測試覆蓋什麼、不覆蓋什麼，以及如何自己執行它們。

## 執行什麼，在哪裡執行 {#what-runs-and-where}

測試套件共有 1,389 個測試（加上九個基準測試為 1,398 個）。沒有一個呼叫真實的
AWS：需要 AWS 的測試使用 [moto](https://github.com/getmoto/moto)（它在記憶體中模擬 AWS）或模擬客戶端，並使用假憑證。
測試離線執行，不產生費用。
九個效能基準測試不在常規執行之內，只有在你要求時才會啟動。

CI 在每次推送到 `main` 或 `develop`、以及每個指向 `main` 的拉取請求時，都會在 Python 3.11、3.12、3.13、3.14 和 3.15 上執行測試套件，
外加 lint、整合和基礎安全作業。

**沒有任何測試針對真實的 AWS 賬戶執行。** 凡是結果取決於真實 AWS 行為的地方，
[功能狀態](../getting-started/status.md)都會說明。

## 每項功能用什麼測試 {#what-each-feature-is-tested-with}

每一行都是針對模擬的 AWS（moto）離線檢查的，Google 相關的行則針對模擬的 Google 客戶端。
moto 的 Resource Groups Tagging API 是 ARN 和標籤的參照。

| 功能 | 測試 |
|---|---|
| 一個或多個賬戶中的資源，在報告和執行摘要中點名失敗的賬戶 | `tests/integration/test_status_validation.py`, `tests/unit/test_cli_security.py` |
| Excel 和 Word 報告，穩定的工作表和行順序，標籤列 | `tests/integration/test_status_validation.py`, `tests/test_bom_converter.py` |
| 報告模板、標籤策略檢查、退出碼 3 | `tests/integration/test_status_validation.py`, `tests/unit/templating/` |
| 每條路徑上的過濾條件（`--account-regions`、`--account-services`、`--account-tags`） | `tests/integration/test_status_validation.py`, `tests/unit/test_global_services.py` |
| 每個服務真實的 ARN 和標籤匹配，無重複 | `tests/unit/test_arn_and_tags.py` |
| 僅 `eu-west-1`、所有區域，以及包含 `us-east-1` 的列表下的全域性服務 | `tests/unit/test_global_services.py` |
| 網路和安全工作表，`--risk-threshold`（退出碼 4） | `tests/integration/test_status_validation.py` |
| `--enable-cost-analysis` 及其工作表 | `tests/integration/test_status_validation.py` |
| `--per-account-reports`、`--accounts-prompt`、`--credential-timeout`、`--disable-account-logging` | `tests/integration/test_status_validation.py` |
| `--bom-config` 警告、不發出 AWS 呼叫的 `--validate-config-only`、每個被拒絕的服務一條警告 | `tests/integration/test_status_validation.py` |
| 兩次執行之間的變更報告、快照 | `tests/integration/test_status_validation.py`, `tests/unit/test_changelog_generator.py` |
| 只讀防護、審計、`--validate-operations`、S3 上傳、私有檔案 | `tests/unit/test_cli_security.py`, `tests/unit/test_security_read_only_guard.py` |
| 機密的遮蔽，包括 Google 機密 | `tests/unit/test_security_redaction.py`, `tests/unit/test_google_output.py` |
| Google Sheets 和 Docs 輸出（模擬的 Google 客戶端） | `tests/unit/test_google_output.py` |

## 自己執行測試 {#run-the-tests-yourself}

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

用 `pytest -m performance` 執行基準測試。搭建完整的開發環境：
[參與貢獻 InvenTag](../development/CONTRIBUTING.md)。

## 還檢查什麼 {#what-else-is-checked}

- **文件網站**在 CI 中構建。遇到失效連結時構建會失敗，並且會對構建出的頁面執行無障礙檢查。
- **依賴項**會被掃描已知漏洞。參見[安全](./index.md#how-dependencies-are-checked)和
  [軟體物料清單](./sbom.md)。
