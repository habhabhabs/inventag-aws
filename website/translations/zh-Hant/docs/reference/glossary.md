---
title: 術語表
description: InvenTag 文件中所用術語的通俗解釋，從帳戶檔案和 ARN 到標籤策略和唯讀防護。
sidebar_position: 6
---

# 術語表

**適合誰閱讀：** 在這些文件中遇到不熟悉詞語的任何人。

下面的每個術語在文件中都只用一種含義。

| 術語 | 含義 |
|---|---|
| **帳戶檔案（Accounts file）** | 用 `--accounts-file` 傳入的 YAML 或 JSON 檔案，列出要掃描的 AWS 帳戶。見[設定檔](./configuration-files.md#accounts-file)。 |
| **ARN** | Amazon Resource Name：AWS 給資源的唯一 ID，例如 `arn:aws:s3:::acme-app-logs`。 |
| **AWS 帳戶** | 一個 AWS 帳戶，由 12 位數字的帳戶 ID 標識，例如 `123456789012`。 |
| **BOM** | 物料清單（Bill of materials）：InvenTag 寫入 Excel 或 Word 的資源列表。 |
| **合規（Compliant）** | 具有標籤策略要求的每個標籤，且值在允許範圍內的資源。 |
| **設定範本（Config template）** | `kind: config` 的範本：掃描哪些帳戶和區域、寫出哪些檔案，以及使用哪個報告範本和標籤策略。 |
| **Cost Explorer** | 報告支出的 AWS 服務。InvenTag 呼叫它來找出有支出的服務；AWS 按請求收費。 |
| **憑證鏈（Credential chain）** | AWS 工具查詢憑證的順序：先是環境變數，然後是設定檔，再然後是 IAM 角色。 |
| **結束代碼（Exit code）** | 命令結束時返回的數字。`0` 表示成功；InvenTag 用 `1` 表示錯誤，`2` 表示選項無效或相互衝突，`3` 表示標籤策略違規，`4` 表示有安全組規則達到或超過 `--risk-threshold`，`5` 表示有帳戶未能完整掃描（使用 `--fail-on-account-error` 時），`6` 表示沒有可報告的內容（使用 `--fail-if-empty` 時）。如果同時滿足多個條件，先是 5，然後是 6，然後是 3，最後是 4。見[結束代碼](./cli.md#exit-codes)。 |
| **IAM** | AWS Identity and Access Management：使用者、角色，以及規定它們可以做什麼的策略。 |
| **IAM Identity Center** | 用於單點登入（SSO）AWS 帳戶的 AWS 服務。它曾叫 AWS SSO。 |
| **IAM 角色（IAM role）** | 一種帶有權限的身份，其他身份可以臨時擔任它。 |
| **moto** | 一個在你的電腦上模擬 AWS 的 Python 庫。文件中的範例輸出來自針對 moto 的執行。 |
| **OIDC** | OpenID Connect：讓 GitHub Actions 或 GitLab CI/CD 等 CI 系統無需儲存金鑰即可獲得短期 AWS 憑證。 |
| **範圍外（Out of scope）** | 由於 `scope` 設定，標籤策略不檢查的資源。 |
| **唯讀防護（Read-only guard）** | InvenTag 中在每個 AWS 呼叫發出之前進行檢查，並阻止所有非讀取呼叫的部分。始終開啟。 |
| **區域（Region）** | AWS 的地理位置，以 `us-east-1` 或 `eu-west-1` 這樣的程式碼表示。 |
| **報告範本（Report template）** | `kind: report` 的範本：Excel 和 Word 檔案的標題、顏色、欄、工作表和章節。 |
| **範例資料（Sample data）** | 針對 moto 執行 InvenTag 得到的輸出，帳戶和資源均為虛構。這些頁面使用的就是它。 |
| **快照（Snapshot）** | `bom_output/state/` 中的一個 JSON 檔案，記錄某次執行發現的內容，以便比較各次執行。 |
| **標籤（Tag）** | 附加在 AWS 資源上的鍵和值，例如 `Owner=platform`。鍵區分大小寫。 |
| **標籤策略（Tag policy）** | `kind: tag-policy` 的範本：資源必須具有的標籤以及允許的值。 |
| **範本（Template）** | 控制一次執行中某一部分的小型 YAML 檔案：報告範本、標籤策略或設定範本。見[範本](../templates/index.md)。 |
| **限流（Throttling）** | 由於同時到達的請求太多，AWS 放慢或拒絕請求。 |
