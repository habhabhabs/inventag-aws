---
title: 安裝 InvenTag
description: 把 InvenTag 安裝到 Python 虛擬環境中，連線你的 AWS 憑證，並確認一切正常。
sidebar_position: 2
---

# 安裝 InvenTag

**適合誰閱讀：** 在膝上型電腦、伺服器或 CI 執行器上安裝 InvenTag 的人。

**讀完後你可以：** 執行 `inventag --help`，並確認 InvenTag 能連上你的 AWS 賬戶。

## 你需要準備 {#what-you-need}

- **Python 3.11 或更高版本。** Python 3.10 自 2026 年 10 月起不再獲得安全修復。
  用 `python3 --version` 檢視你的版本。
- **pip**，隨 Python 一同提供。（只有從原始碼安裝時才需要 Git。）
- 只讀身份的 **AWS 憑證**。
  [AWS 命令列介面（AWS CLI）](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  是可選的，但它是最簡單的配置方式。

## 用 pip 安裝（推薦） {#install-with-pip-recommended}

InvenTag 以
[`inventag-aws`](https://pypi.org/project/inventag-aws/) 之名釋出在 Python 包索引上。
用虛擬環境安裝最整潔，但 InvenTag 並不要求使用虛擬環境，它就是一個普通的 Python 包。
虛擬環境能讓它的依賴（boto3、openpyxl 等）與你其他的 Python 工具互不干擾；
而且許多較新的系統（Debian、Ubuntu、Homebrew 的 Python）會拒絕向系統 Python 執行
`pip install`，並報出“externally-managed-environment”錯誤。
在這些系統上可行的兩種辦法是虛擬環境，或者 `pipx`：

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

這樣你就有了 `inventag` 命令。本文件中所有出現 `inventag` 的地方，用法都相同。
報告模板已包含在軟體包中。

升級請執行 `pip install --upgrade inventag-aws`。安裝指定版本請執行
`pip install inventag-aws==1.0.2`。想讓它遠離你的專案環境？
`pipx install inventag-aws` 會把它裝進獨立的隱藏環境，並把 `inventag` 命令放到
PATH 中，你無需啟用任何環境。如果你的系統允許，直接把 `pip install inventag-aws`
裝到使用者或系統 Python 中也可以。

## 從原始碼安裝 {#install-from-source}

如果你想用最新的未釋出程式碼，或打算修改 InvenTag，請用這種方式。

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
inventag --help               # Windows: inventag --help
```

在克隆下來的資料夾裡執行 `pip install -e .`，即可從你的原始碼副本獲得 `inventag` 命令。
你也可以直接執行 `python inventag_cli.py --help`。

若要從原始碼使用固定的釋出版本，而不是最新程式碼，請檢出它的標籤，例如
`git checkout v1.0.2`。
[釋出頁面](https://github.com/habhabhabs/inventag-aws/releases)列出了所有版本。

## 連線你的 AWS 憑證 {#connect-your-aws-credentials}

InvenTag 使用標準的 AWS 憑證鏈，因此以下任一方式都可以：

```bash title="Terminal"
aws sso login --profile my-readonly     # IAM Identity Center (recommended)
export AWS_PROFILE=my-readonly

aws configure                           # long-lived access keys (avoid if you can)
```

請優先使用短期憑證，例如 IAM Identity Center 或代入的角色，
而不是存放在磁碟上的訪問金鑰。

## 檢查是否可用 {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

退出碼為 0 表示 InvenTag 能夠登入。加上 `--verbose` 還能看到各個步驟。
下面是針對模擬 AWS 離線執行得到的示例輸出（示例資料）：

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

## 授予 InvenTag 只讀許可權 {#give-inventag-read-only-permissions}

在第一次真正掃描之前，請給該身份配置只讀策略：
[設定只讀訪問](../guides/read-only-access.md)。

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

[生成第一份報告](./quick-start.md)
