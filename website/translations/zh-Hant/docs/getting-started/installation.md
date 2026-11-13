---
title: 安裝 InvenTag
description: 把 InvenTag 安裝到 Python 虛擬環境中，連線你的 AWS 憑證，並確認一切正常。
sidebar_position: 2
---

# 安裝 InvenTag

**適合誰閱讀：** 在膝上型電腦、伺服器或 CI 執行器上安裝 InvenTag 的人。

**讀完後你可以：** 執行 `inventag --help`，並確認 InvenTag 能連上你的 AWS 帳戶。

## 你需要準備 {#what-you-need}

- **Python 3.11 或更高版本。** Python 3.10 自 2026 年 10 月起不再獲得安全修復。
  用 `python3 --version` 檢視你的版本。
- **pip**，隨 Python 一同提供。（只有從原始碼安裝時才需要 Git。）
- 唯讀身份的 **AWS 憑證**。
  [AWS 命令列介面（AWS CLI）](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  是可選的，但它是最簡單的設定方式。

## 用 pip 安裝（推薦） {#install-with-pip-recommended}

InvenTag 以
[`inventag-aws`](https://pypi.org/project/inventag-aws/) 之名發佈在 Python 包索引上。
用虛擬環境安裝最整潔，但 InvenTag 並不要求使用虛擬環境，它就是一個普通的 Python 包。
虛擬環境能讓它的依賴（boto3、openpyxl 等）與你其他的 Python 工具互不干擾；
而且許多較新的系統（Debian、Ubuntu、Homebrew 的 Python）會拒絕向系統 Python 執行
`pip install`，並報出「externally-managed-environment」錯誤。
在這些系統上可行的兩種辦法是虛擬環境，或者 `pipx`：

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

這樣你就有了本文件所用的 `inventag` 命令。
報告範本已包含在軟體包中。

升級請執行 `pip install --upgrade inventag-aws`。安裝指定版本請固定版本號，例如
`pip install inventag-aws==%INVENTAG_VERSION%`。想讓它遠離你的專案環境？
`pipx install inventag-aws` 會把它裝進獨立的隱藏環境，並把 `inventag` 命令放到
PATH 中，你無需啟用任何環境。如果你的系統允許，直接把 `pip install inventag-aws`
裝到使用者或系統 Python 中也可以。

## 從原始碼安裝 {#install-from-source}

如果你想用最新的未發佈程式碼，或打算修改 InvenTag，請用這種方式。

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
inventag --help
```

`pip install -e .` 會安裝 `requirements.txt` 中的依賴，以及一個執行你的原始碼副本的
`inventag` 命令，因此程式碼改動無需重新安裝即可生效。你也可以在
`pip install -r requirements.txt` 之後直接執行 `python inventag_cli.py --help`。

若要從原始碼使用固定的發佈版本，而不是最新程式碼，請檢出它的標籤，例如
`git checkout v%INVENTAG_VERSION%`。
[發佈頁面](https://github.com/habhabhabs/inventag-aws/releases)列出了所有版本。

## 連線你的 AWS 憑證 {#connect-your-aws-credentials}

InvenTag 使用標準的 AWS 憑證鏈，因此以下任一方式都可以：

使用 IAM Identity Center（推薦）：

```bash title="Terminal"
aws sso login --profile my-readonly
export AWS_PROFILE=my-readonly
```

使用長期存取金鑰（儘量避免）：

```bash title="Terminal"
aws configure
```

請優先使用短期憑證，例如 IAM Identity Center 或擔任的角色，
而不是存放在磁碟上的存取金鑰。

## 檢查是否可用 {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

結束代碼為 0 表示 InvenTag 能夠登入。加上 `--verbose` 還能看到各個步驟。
下面是針對模擬 AWS 離線執行得到的範例輸出（範例資料）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
$ echo $?
0
```

如果憑證不可用，InvenTag 會說明原因並給出修復建議。
參見[解決常見問題](../guides/troubleshooting.md#credentials)。

## 授予 InvenTag 唯讀權限 {#give-inventag-read-only-permissions}

在第一次真正掃描之前，請給該身份設定唯讀策略：
[設定唯讀存取](../guides/read-only-access.md)。

## 從 v1.1.x 升級 {#upgrade-from-v11x}

執行 `pip install --upgrade inventag-aws` 之後你會注意到：

- **機密值會被遮蓋。** 常用於存放機密的欄位（例如 Lambda 環境變數）的值，在報告、快照和日誌中會變成
  `***REDACTED***`。升級後的第一次執行會把這些資源報告為已更改一次。早期版本寫出的報告和快照可能仍包含這些值：
  請刪除它們或限制其存取。
- **新欄。** 每個服務工作表都有 `source`、`sources` 和 `detail_level` 欄。參見[輸出檔案](../reference/outputs.md)。
- **更多服務和更多 API 呼叫。** InvenTag 多列出 22 個服務，因此會增加工作表、行和呼叫。
  儲存庫中的策略新增了 17 個讀取操作（並且不再列出 `cloudtrail:LookupEvents`）；沒有這些權限時，每個被拒絕的列出呼叫都會給出一條警告，這些資源仍會像以前一樣透過 Tagging API 找到（如果它們帶有標籤）。升級後的第一份變更報告會把新列出服務的資源顯示為新增，儘管它們之前就存在。
  參見 [IAM 權限](../reference/iam-permissions.md)。
- **更嚴格的檔案檢查。** 空的設定檔案、寫了兩次的鍵，或型別錯誤的 `--bom-config` 值，都會以結束代碼 1 停止執行。
- **相互衝突的選項會以結束代碼 2 停止**，例如同時使用 `--accounts-file` 和 `--accounts-prompt`，
  或給了 `--s3-kms-key-id` 但沒有 `--s3-encryption aws:kms`。
- **時間限制按帳戶計算**，從該帳戶開始掃描時算起。超時的帳戶保留已找到的資源，並算作失敗。
- **預設結束代碼不變。** 結束代碼 5 和 6 是新增的，只在使用 `--fail-on-account-error` 和 `--fail-if-empty` 時出現。無法寫出的報告格式會以結束代碼 1 結束。
- **服務名稱和工作表名稱保持不變。** v1.1.4 只透過 Tagging API 找到的資源保留其服務名稱和工作表（例如
  `ELASTICFILESYSTEM`、`STATES`、`COGNITO-IDP`、`ELASTICMAPREDUCE`、`KAFKA`、`ES`）。它們的行現在帶有服務 API 的詳細資訊，
  Secrets Manager 金鑰和 MSK 叢集的 ID 欄顯示名稱，而不是 ARN 的最後一部分。

完整列表見[更新日誌](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md)。

## 為開發而安裝 {#install-for-development}

```bash title="Terminal"
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

[貢獻指南](../development/CONTRIBUTING.md)介紹了完整的測試套件。

## 解決安裝問題 {#fix-install-problems}

| 你看到的現象 | 怎麼辦 |
|---|---|
| `Error: No suitable Python interpreter found.` 或 `InvenTag requires Python 3.11 or later` | 安裝 Python 3.11 或更高版本，並確認 `python3 --version` 可用。 |
| `inventag: command not found` | 啟用你執行 `pip install inventag-aws` 的那個虛擬環境，或執行 `python -m pip show inventag-aws` 檢查是否已安裝。 |
| `ModuleNotFoundError` | 啟用虛擬環境，再次執行 `pip install -r requirements.txt`。 |
| `No AWS credentials found!` | 執行 `aws sso login` 或 `aws configure`，或設定 `AWS_PROFILE`。 |

## 下一步 {#next-step}

[快速開始](./quick-start.md)
