---
title: 安装 InvenTag
description: 把 InvenTag 安装到 Python 虚拟环境中，连接你的 AWS 凭证，并确认一切正常。
sidebar_position: 2
---

# 安装 InvenTag

**适合谁阅读：** 在笔记本电脑、服务器或 CI 运行器上安装 InvenTag 的人。

**读完后你可以：** 运行 `inventag --help`，并确认 InvenTag 能连上你的 AWS 账户。

## 你需要准备 {#what-you-need}

- **Python 3.11 或更高版本。** Python 3.10 自 2026 年 10 月起不再获得安全修复。
  用 `python3 --version` 查看你的版本。
- **pip**，随 Python 一同提供。（只有从源码安装时才需要 Git。）
- 只读身份的 **AWS 凭证**。
  [AWS 命令行界面（AWS CLI）](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  是可选的，但它是最简单的配置方式。

## 用 pip 安装（推荐） {#install-with-pip-recommended}

InvenTag 以
[`inventag-aws`](https://pypi.org/project/inventag-aws/) 之名发布在 Python 包索引上。
用虚拟环境安装最整洁，但 InvenTag 并不要求使用虚拟环境，它就是一个普通的 Python 包。
虚拟环境能让它的依赖（boto3、openpyxl 等）与你其他的 Python 工具互不干扰；
而且许多较新的系统（Debian、Ubuntu、Homebrew 的 Python）会拒绝向系统 Python 执行
`pip install`，并报出“externally-managed-environment”错误。
在这些系统上可行的两种办法是虚拟环境，或者 `pipx`：

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

这样你就有了本文档所用的 `inventag` 命令。
报告模板已包含在软件包中。

升级请运行 `pip install --upgrade inventag-aws`。安装指定版本请固定版本号，例如
`pip install inventag-aws==%INVENTAG_VERSION%`。想让它远离你的项目环境？
`pipx install inventag-aws` 会把它装进独立的隐藏环境，并把 `inventag` 命令放到
PATH 中，你无需激活任何环境。如果你的系统允许，直接把 `pip install inventag-aws`
装到用户或系统 Python 中也可以。

## 从源码安装 {#install-from-source}

如果你想用最新的未发布代码，或打算修改 InvenTag，请用这种方式。

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
inventag --help
```

`pip install -e .` 会安装 `requirements.txt` 中的依赖，以及一个运行你的源码副本的
`inventag` 命令，因此代码改动无需重新安装即可生效。你也可以在
`pip install -r requirements.txt` 之后直接运行 `python inventag_cli.py --help`。

若要从源码使用固定的发布版本，而不是最新代码，请检出它的标签，例如
`git checkout v%INVENTAG_VERSION%`。
[发布页面](https://github.com/habhabhabs/inventag-aws/releases)列出了所有版本。

## 连接你的 AWS 凭证 {#connect-your-aws-credentials}

InvenTag 使用标准的 AWS 凭证链，因此以下任一方式都可以：

使用 IAM Identity Center（推荐）：

```bash title="Terminal"
aws sso login --profile my-readonly
export AWS_PROFILE=my-readonly
```

使用长期访问密钥（尽量避免）：

```bash title="Terminal"
aws configure
```

请优先使用短期凭证，例如 IAM Identity Center 或代入的角色，
而不是存放在磁盘上的访问密钥。

## 检查是否可用 {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

退出码为 0 表示 InvenTag 能够登录。加上 `--verbose` 还能看到各个步骤。
下面是针对模拟 AWS 离线运行得到的示例输出（示例数据）：

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

如果凭证不可用，InvenTag 会说明原因并给出修复建议。
参见[解决常见问题](../guides/troubleshooting.md#credentials)。

## 授予 InvenTag 只读权限 {#give-inventag-read-only-permissions}

在第一次真正扫描之前，请给该身份配置只读策略：
[设置只读访问](../guides/read-only-access.md)。

## 从 v1.1.x 升级 {#upgrade-from-v11x}

运行 `pip install --upgrade inventag-aws` 之后你会注意到：

- **机密值会被遮盖。** 常用于存放机密的字段（例如 Lambda 环境变量）的值，在报告、快照和日志中会变成
  `***REDACTED***`。升级后的第一次运行会把这些资源报告为已更改一次。早期版本写出的报告和快照可能仍包含这些值：
  请删除它们或限制其访问。
- **新列。** 每个服务工作表都有 `source`、`sources` 和 `detail_level` 列。参见[输出文件](../reference/outputs.md)。
- **更多服务和更多 API 调用。** InvenTag 多列出 22 个服务，因此会增加工作表、行和调用。
  仓库中的策略多了 17 个读取操作；没有这些权限时，这些服务会被跳过并给出警告。
  参见 [IAM 权限](../reference/iam-permissions.md)。
- **更严格的文件检查。** 空的设置文件、写了两次的键，或类型错误的 `--bom-config` 值，都会以退出码 1 停止运行。
- **相互冲突的选项会以退出码 2 停止**，例如同时使用 `--accounts-file` 和 `--accounts-prompt`，
  或给了 `--s3-kms-key-id` 但没有 `--s3-encryption aws:kms`。
- **时间限制按账户计算**，从该账户开始扫描时算起。超时的账户保留已找到的资源，并算作失败。
- **默认退出码不变。** 退出码 5 和 6 是新增的，只在使用 `--fail-on-account-error` 和 `--fail-if-empty` 时出现。

完整列表见[更新日志](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md)。

## 为开发而安装 {#install-for-development}

```bash title="Terminal"
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

[贡献指南](../development/CONTRIBUTING.md)介绍了完整的测试套件。

## 解决安装问题 {#fix-install-problems}

| 你看到的现象 | 怎么办 |
|---|---|
| `Error: No suitable Python interpreter found.` 或 `InvenTag requires Python 3.11 or later` | 安装 Python 3.11 或更高版本，并确认 `python3 --version` 可用。 |
| `inventag: command not found` | 激活你运行 `pip install inventag-aws` 的那个虚拟环境，或运行 `python -m pip show inventag-aws` 检查是否已安装。 |
| `ModuleNotFoundError` | 激活虚拟环境，再次运行 `pip install -r requirements.txt`。 |
| `No AWS credentials found!` | 运行 `aws sso login` 或 `aws configure`，或设置 `AWS_PROFILE`。 |

## 下一步 {#next-step}

[快速开始](./quick-start.md)
