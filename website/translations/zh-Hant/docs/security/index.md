---
title: 安全
description: 如何報告 InvenTag 的漏洞、應使用哪些 Python 版本、依賴項如何檢查，以及發生供應鏈事件後該怎麼做。
sidebar_position: 1
---

# 安全

**適合誰閱讀：** 安全審查人員，以及針對生產賬戶執行 InvenTag 的任何人。

**讀完後你會了解：** 如何報告問題、InvenTag 的依賴項如何檢查，以及出現問題時如何限制損失。

## 報告漏洞 {#report-a-vulnerability}

請不要把漏洞利用的細節釋出在公開的 issue 中。

本倉庫目前還沒有 `SECURITY.md` 檔案，也沒有設定 GitHub 的私密漏洞報告（2026 年 11 月檢查）。
在設定之前，請開一個標題為“Security contact request”的
[issue](https://github.com/habhabhabs/inventag-aws/issues)，不要寫任何技術細節，
並向維護者索取一個私密的聯絡渠道。

## InvenTag 如何處理你的賬戶 {#what-inventag-does-with-your-accounts}

- **它只讀取。** 只讀防護會在每個 AWS 呼叫發出之前檢查它。它會攔截所有非讀取的呼叫，
  以及會返回機密或資料的讀取，例如 `secretsmanager:GetSecretValue` 或 `s3:GetObject`。
  它始終開啟。
- **它不傳送使用資料。** InvenTag 沒有遙測。命令列工具只與 AWS 通訊。
  Python 庫中可選的 CI 輔助功能可以向 Slack、Microsoft Teams 或 Prometheus Pushgateway 傳送訊息，
  但只會傳送到你自己配置的地址。
- **它的檔案是私有的。** 報告、快照和日誌建立時只有你的使用者可讀。
- **它的日誌會隱藏機密。** 會話令牌、金鑰和請求簽名會被遮蔽，即使使用 `--debug` 也是如此。

你可以用 `--audit-output audit.json` 檢查一次執行做了什麼，用 `--validate-operations`
檢查防護允許什麼：

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

## 使用受支援的 Python 版本 {#use-a-supported-python-version}

請使用 Python 3.11 或更高版本。Python 3.10 及更早版本不再獲得安全修復：
3.10 已於 2026 年 10 月終止支援
（[Python 版本狀態](https://devguide.python.org/versions/)）。

## 依賴項如何檢查 {#how-dependencies-are-checked}

| 內容 | 在當前 `main` 分支上的做法 |
|---|---|
| Python 依賴項 | 列在 `requirements.txt` 中，使用最低版本（`>=`），而不是精確固定。每個安全下限都會註明它所規避的安全公告。全新安裝會得到最新的匹配版本。 |
| 開發工具 | 列在 `requirements-dev.txt` 中，測試和 lint 工具使用精確固定（`==`），它們的依賴項使用最低版本。 |
| 網站 | 鎖定在 `website/package-lock.json` 中。 |
| CI 中的依賴項檢查 | CI 工作流執行 `pip-audit -r requirements.txt`，發現問題就失敗。它也執行 Bandit 和 `npm audit`，但它們的發現不會導致失敗。 |
| 定時掃描 | 另一個工作流在推送到 `main` 和 `develop`、指向 `main` 的拉取請求以及每週（週日 02:00 UTC）時執行。它執行 Bandit、Safety、pip-audit、`npm audit` 和 detect-secrets。發現的問題會被報告，但不會讓該工作流失敗。 |
| 軟體物料清單 | 文件構建會為 Python 和網站的依賴項生成 SBOM 檔案。 |

要檢查你自己的安裝：

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

模板功能沒有增加新的依賴項。它使用 PyYAML、openpyxl 和 python-docx，這些都是 InvenTag 本來就需要的。

## 出問題時減小影響 {#reduce-the-impact-if-something-goes-wrong}

InvenTag 會讀取你的 AWS 賬戶，所以你給它的憑證比工具本身更重要。

- **只讀，最小許可權。** 只給 InvenTag 讀取許可權：[設定只讀訪問](../guides/read-only-access.md)。
- **短期憑證。** 使用 IAM Identity Center 或被擔任的角色，而不是放在磁碟上或 CI 機密中的訪問金鑰。
  在 GitHub Actions 中使用 OIDC。
- **保持日誌私有。** 日誌中的機密會被遮蔽，但日誌仍然會描述你的賬戶。
- **固定你執行的版本。** 檢出 InvenTag 的釋出標籤，並把 GitHub Actions 固定到提交 SHA。

## 供應鏈事件之後 {#after-a-supply-chain-incident}

如果某個依賴項、某個 CI action，或者執行 InvenTag 的機器可能已被入侵：

1. **吊銷並輪換** InvenTag 使用過的憑證：刪除訪問金鑰，吊銷活動的角色會話，並退出 SSO 會話。
2. **檢查 AWS CloudTrail**，檢視該身份發出的、InvenTag 不會發出的呼叫，
   尤其是任何不是 `List`、`Describe` 或 `Get` 的呼叫。
3. **檢查 IAM 策略是否仍然只讀**，並移除任何多餘的許可權。
4. **重建環境**，使用乾淨的虛擬環境：`pip install -r requirements.txt`，然後執行 `pip-audit`。
5. **把舊報告視為敏感資訊。** 它們列出了你的資源和標籤。

## 模板是資料，不是程式碼 {#templates-are-data-not-code}

模板用安全的 YAML 載入器讀取，不能執行程式碼或獲取 URL，只能引用它們自己資料夾內的檔案，
也不能包含訪問金鑰。詳情：[模板](../templates/index.md#safe-by-design)。
