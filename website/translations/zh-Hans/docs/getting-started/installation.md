---
title: 安装 InvenTag
description: 选择安装 InvenTag 的方式（pipx、独立压缩包、.deb 或 .rpm 软件包、Homebrew 或 pip），连接你的 AWS 凭证，并确认一切正常。
sidebar_position: 2
---

# 安装 InvenTag

**适合谁阅读：** 在笔记本电脑、服务器或 CI 运行器上安装 InvenTag 的人。

**读完后你可以：** 选择安装方式，安装、升级和卸载 InvenTag，并确认 InvenTag 能连上你的 AWS 账户。

## 你需要准备 {#what-you-need}

- **Python 3.11 或更高版本**，用于 pipx、pip 和源码这三种方式。Python 3.10 自 2026 年 10 月起不再获得安全修复。
  请参阅 [Python 版本状态](https://devguide.python.org/versions/)。
  用 `python3 --version` 查看你的版本。独立压缩包、`.deb` 和 `.rpm` 自带 Python，你的机器上不需要安装 Python。
- 只读身份的 **AWS 凭证**。
  [AWS 命令行界面（AWS CLI）](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  是可选的，但它是最简单的配置方式。

## 选择安装方式 {#choose-how-to-install}

| 方式 | 适用情况 | 你的机器上需要 | 系统 |
|---|---|---|---|
| [pipx](#install-with-pipx-recommended)（首选） | 你有 Python 3.11 或更高版本。你想用一条命令安装、一条命令升级。 | Python 3.11 或更高版本和 pipx | 任何有 Python 的系统 |
| [独立压缩包](#install-the-standalone-archive)（`.tar.gz`） | 机器上没有 Python，或者你想要一份不依赖包管理器的副本。 | 无 | Linux x86_64 和 arm64（glibc 2.34 或更高版本）。macOS arm64（Apple 芯片）。 |
| [`.deb` 软件包](#install-the-deb-package) | Debian、Ubuntu 以及使用 `dpkg` 的系统。 | 无 | Linux x86_64 和 arm64（glibc 2.34 或更高版本） |
| [`.rpm` 软件包](#install-the-rpm-package) | Fedora、RHEL 系列和 Amazon Linux。 | 无 | Linux x86_64 和 arm64（glibc 2.34 或更高版本） |
| [Homebrew](#install-with-homebrew) | 装有 Homebrew 的 macOS 或 Linux。尚未发布。 | Homebrew | 见该节 |
| [虚拟环境中的 pip](#install-with-pip-in-a-virtual-environment) | 你想把 InvenTag 装进项目环境。 | Python 3.11 或更高版本 | 任何有 Python 的系统 |
| [从源码安装](#install-from-source) | 你想用最新的未发布代码，或者要修改 InvenTag。 | Python 3.11 或更高版本和 Git | 任何有 Python 的系统 |

### 每种打包构建支持的系统 {#systems-that-each-packaged-build-supports}

- Linux 的可执行文件、`.deb` 和 `.rpm` 需要 glibc 2.34 或更高版本。
  下表中的 Linux 系统都满足这个要求。
  在更旧的系统上，例如 RHEL、AlmaLinux 和 Rocky Linux 8、Debian 11、Ubuntu 20.04 或
  Amazon Linux 2，如果系统有 Python 3.11 或更高版本，请使用 pipx。
- 没有适用于 Intel 版 Mac 的可执行文件：InvenTag 所需的一个库（cryptography，从第 50 版起）没有为它们发布现成的构建。
- macOS 可执行文件只适用于 Apple 芯片（arm64）。构建记录显示，它的文件需要 macOS 11.0 或更高版本。
- 可执行文件不支持 Alpine 和其他使用 musl 的系统。请使用 pipx。
- Windows 没有打包构建。

未针对 Intel 版 Mac 验证：`pipx install inventag-aws`，它必须编译那个库，并且需要 Rust 工具链。

未针对 glibc 低于 2.34 的系统验证：可执行文件、`.deb` 和 `.rpm`。

未针对 Alpine 或其他 musl 系统验证：可执行文件；请使用 pipx。

未针对 Windows 验证：任何安装方式。

未针对 macOS 11.0 的 Mac 验证：可执行文件。这个版本号来自构建记录，不是在该版本上运行得到的。

### 测试了什么 {#what-was-tested}

发布工作流先构建每种格式，再把它安装到一个全新的系统上。在 x86_64 的 Linux 系统和 macOS 上，
它运行 `inventag --version` 和 `inventag selftest`，检查手册页和补全文件，扫描一个模拟的 AWS，
卸载软件包，并检查软件包的文件是否一个不剩。下面这些系统通过了测试：

| 系统 | 格式 | CPU |
|---|---|---|
| Ubuntu 22.04 | `.deb` | x86_64 |
| Ubuntu 24.04 | `.deb` | x86_64 |
| Debian 12 | `.deb` 和独立压缩包 | x86_64 |
| Debian 12 | `.deb`（安装、版本、selftest、卸载） | arm64 |
| Fedora（测试当天的最新版本） | `.rpm` | x86_64 |
| Rocky Linux 9 | `.rpm` 和独立压缩包 | x86_64 |
| Rocky Linux 9 | `.rpm`（安装、版本、selftest、卸载） | arm64 |
| AlmaLinux 9（构建系统，glibc 2.34） | `.rpm` | x86_64 |
| Amazon Linux 2023 | `.rpm` | x86_64 |
| GitHub Runner上的 macOS 15 | 独立压缩包 | arm64 |
| Ubuntu 24.04 | pipx，使用由标签构建的 wheel（安装、版本、selftest、卸载） | x86_64 |

未针对真实的 AWS 验证：从打包构建发起的扫描；这个测试扫描的是模拟的 AWS。

未针对全新的 Linux arm64 系统验证：独立压缩包。构建过程在它上面运行了 `inventag selftest`，没有其他测试解压过它。

未针对 GitHub 验证：发布页是否带有本页所说的文件。到目前为止的测试运行不会向发布页附加任何文件，带有这些文件的第一次正式发布运行还没有进行。

## 用 pipx 安装（推荐） {#install-with-pipx-recommended}

[pipx](https://pipx.pypa.io/) 把 InvenTag 安装到它自己的隐藏环境中，并把 `inventag` 命令放到你的 PATH 上。
你不需要激活任何东西。Python 包索引上的包名是
[`inventag-aws`](https://pypi.org/project/inventag-aws/)。请先安装 pipx，
使用你的系统建议的方式。请参阅 pipx 文档。

```bash title="Terminal"
pipx install inventag-aws
inventag --version
inventag selftest
```

`inventag selftest` 在离线状态下检查这份 InvenTag 是否能正常工作。它不调用 AWS，不打开网络连接，
也不需要凭证。退出码 0 表示所有检查都通过。退出码 1 表示有检查失败。

如果你使用 [uv](https://docs.astral.sh/uv/)，`uv tool install inventag-aws` 的效果相同。

- **升级：** `pipx upgrade inventag-aws`。要安装某个指定版本，请固定版本：
  `pipx install inventag-aws==%INVENTAG_VERSION%`。
- **卸载：** `pipx uninstall inventag-aws`。这会删除程序，但不会删除 `bom_output/` 中的报告和快照。
- **补全：** `inventag completion bash`、`inventag completion zsh` 和
  `inventag completion fish` 会输出补全脚本。见[命令行补全](#shell-completion)。
- **手册页：** 这种方式不安装手册页。请使用 `inventag --help`。

未针对 pipx 验证：升级命令和固定版本命令。

## 安装独立压缩包 {#install-the-standalone-archive}

压缩包里只有一个目录 `inventag`。目录中有程序、它自带的 Python 和它的库。每个发布版本为每种系统提供一个压缩包：

- `inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz`
- `inventag-%INVENTAG_VERSION%-linux-arm64.tar.gz`
- `inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz`（macOS，Apple 芯片）

运行 `uname -m` 查看你的 CPU。Linux 会输出 `x86_64` 或 `aarch64`。`aarch64` 使用 arm64 压缩包。
从[发布页](https://github.com/habhabhabs/inventag-aws/releases)下载压缩包和 `SHA256SUMS`，
或者使用 GitHub CLI：

```bash title="Terminal"
gh release download v%INVENTAG_VERSION% --repo habhabhabs/inventag-aws \
  --pattern 'inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz' --pattern SHA256SUMS
```

解压之前，先[检查下载的文件](#check-the-download)。然后，在 Linux 上：

```bash title="Terminal"
sudo tar -xzf inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz -C /opt
sudo ln -s /opt/inventag/inventag /usr/local/bin/inventag
inventag --version
inventag selftest
```

在 macOS 上，把压缩包解压到你选的文件夹，并用路径运行程序。测试就是这样做的，它没有在 PATH 上创建链接。

```bash title="Terminal"
mkdir -p "$HOME/inventag-install"
tar -xzf inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz -C "$HOME/inventag-install"
"$HOME/inventag-install/inventag/inventag" --version
```

macOS 可执行文件没有经过 Apple 公证。macOS 可能会拦截浏览器下载的文件。

未针对 GitHub Runner 之外的 macOS 验证：Homebrew 安装和 Gatekeeper 的行为。

- **升级：** 删除旧目录，再把新压缩包解压到同一位置。
- **卸载（Linux）：** `sudo rm -rf /opt/inventag` 和 `sudo rm /usr/local/bin/inventag`。
  在 macOS 上，删除你解压出来的文件夹。
- **补全：** 目录的 `share/completions/` 中有脚本：`inventag.bash`、`_inventag`（zsh）和 `inventag.fish`。
  见[命令行补全](#shell-completion)。
- **手册页：** 目录中的手册页是 `share/man/man1/inventag.1`。
  用 `man /opt/inventag/share/man/man1/inventag.1` 阅读。

未针对每个系统的 man 工具验证：`man` 能显示这个页面。测试读取了页面文件，并检查了它的标题行和名称行。

未针对同一位置已有旧版 InvenTag 的系统验证：升级步骤。

## 安装 .deb 软件包 {#install-the-deb-package}

在 Debian、Ubuntu 以及使用 `dpkg` 的系统上使用 `.deb`。x86_64 的文件名是
`inventag_%INVENTAG_VERSION%_amd64.deb`，arm64 的文件名是
`inventag_%INVENTAG_VERSION%_arm64.deb`。下载文件并[检查它](#check-the-download)。然后运行：

```bash title="Terminal"
sudo dpkg -i inventag_%INVENTAG_VERSION%_amd64.deb
inventag --version
inventag selftest
```

软件包把程序放在 `/opt/inventag/`，并在 `/usr/bin/inventag` 创建一个链接。它还会安装手册页、补全文件，
并把许可证文件放在 `/usr/share/doc/inventag/`。软件包没有安装脚本。

- **升级：** 用 `sudo dpkg -i` 安装更新的 `.deb`。
- **卸载：** `sudo dpkg -r inventag`。测试检查过软件包的文件一个不剩。
- **补全：** 软件包会安装 bash、zsh 和 fish 的文件。见[命令行补全](#shell-completion)。
- **手册页：** `man inventag`。文件是 `/usr/share/man/man1/inventag.1.gz`。

未针对已有旧版 InvenTag 软件包的系统验证：升级。

未针对每个系统的 man 工具验证：`man inventag` 能显示这个页面。测试读取了页面文件，并检查了它的标题行和名称行。

## 安装 .rpm 软件包 {#install-the-rpm-package}

在 Fedora、RHEL 系列和 Amazon Linux 上使用 `.rpm`。x86_64 的文件名是
`inventag-%INVENTAG_VERSION%-1.x86_64.rpm`，arm64 的文件名是
`inventag-%INVENTAG_VERSION%-1.aarch64.rpm`。下载文件并[检查它](#check-the-download)。然后运行：

```bash title="Terminal"
sudo dnf install ./inventag-%INVENTAG_VERSION%-1.x86_64.rpm
inventag --version
inventag selftest
```

软件包把程序放在 `/opt/inventag/`，并在 `/usr/bin/inventag` 创建一个链接。它还会安装手册页、补全文件，
并把许可证文件放在 `/usr/share/doc/inventag/`。

- **升级：** 用 `sudo dnf install` 安装更新的 `.rpm`。
- **卸载：** `sudo dnf remove inventag`。测试检查过软件包的文件一个不剩。
- **补全：** 软件包会安装 bash、zsh 和 fish 的文件。见[命令行补全](#shell-completion)。
- **手册页：** `man inventag`。文件是 `/usr/share/man/man1/inventag.1.gz`。

未针对已有旧版 InvenTag 软件包的系统验证：升级。

未针对每个系统的 man 工具验证：`man inventag` 能显示这个页面。测试读取了页面文件，并检查了它的标题行和名称行。

## 用 Homebrew 安装 {#install-with-homebrew}

Homebrew tap 由项目所有者创建。这个 tap 尚未发布，所以下面的命令今天还不能用：

```bash title="Terminal"
brew install habhabhabs/inventag/inventag
```

计划是提供一个从发布压缩包安装可执行文件的 formula。它面向 macOS arm64 和两种 Linux CPU，
不面向 Intel 版 Mac。这个 formula 还没有编写。本页没有说明它会安装哪些补全文件或手册页。
在那之前，请使用[命令行补全](#shell-completion)和 `inventag --help`。

- **升级：** `brew upgrade inventag`。
- **卸载：** `brew uninstall inventag`。

未针对 GitHub Runner 之外的 macOS 验证：Homebrew 安装和 Gatekeeper 的行为。

## 在虚拟环境中用 pip 安装 {#install-with-pip-in-a-virtual-environment}

InvenTag 并不要求使用虚拟环境。虚拟环境能让它的依赖（boto3、openpyxl 等）与你其他的 Python 工具互不干扰。
许多较新的系统（Debian、Ubuntu、Homebrew 的 Python）会拒绝向系统 Python 执行 `pip install`，
并报出“externally-managed-environment”错误。在这些系统上可行的两种办法是虚拟环境，
或者 [pipx](#install-with-pipx-recommended)。

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

未针对 Debian、Ubuntu 或 Homebrew 验证：externally-managed-environment 错误以及绕过它的两种办法。

这样你就有了本文档所使用的 `inventag` 命令。报告模板已包含在包中。

- **升级：** `pip install --upgrade inventag-aws`。要安装某个指定版本，请固定版本：
  `pip install inventag-aws==%INVENTAG_VERSION%`。
- **卸载：** `pip uninstall inventag-aws`。
- **补全和手册页：** 与 [pipx](#install-with-pipx-recommended) 相同。

未针对 pip 验证：升级、固定版本和卸载命令。

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

仓库根目录还有两个启动脚本：`inventag.sh` 和 `inventag.bat`。请改用 `inventag` 命令。这两个脚本不属于已安装的包，也没有测试运行过它们。

若要从源码使用固定的发布版本，而不是最新代码，请检出它的标签，例如
`git checkout v%INVENTAG_VERSION%`。
[发布页面](https://github.com/habhabhabs/inventag-aws/releases)列出了所有版本。

## 命令行补全 {#shell-completion}

`inventag completion bash`、`inventag completion zsh` 和 `inventag completion fish` 会输出补全脚本。
这个命令只读取它自己的选项，不调用 AWS，也不打开网络连接。未知的 shell 名称会以退出码 2 结束。

```bash title="Terminal"
source <(inventag completion bash)                                    # bash, this session
inventag completion zsh > "${fpath[1]}/_inventag"                     # zsh
inventag completion fish > ~/.config/fish/completions/inventag.fish  # fish
```

`.deb` 和 `.rpm` 会为你安装这三个脚本：

| Shell | `.deb` | `.rpm` |
|---|---|---|
| bash | `/usr/share/bash-completion/completions/inventag` | `/usr/share/bash-completion/completions/inventag` |
| zsh | `/usr/share/zsh/vendor-completions/_inventag` | `/usr/share/zsh/site-functions/_inventag` |
| fish | `/usr/share/fish/vendor_completions.d/inventag.fish` | `/usr/share/fish/vendor_completions.d/inventag.fish` |

未针对每种 shell 配置验证：新开的 shell 会自动加载这些文件。测试在 bash、zsh 和 fish 中手动加载了每个文件。
在 Rocky Linux 9、AlmaLinux 9 和 Amazon Linux 2023 上，测试没有加载 fish 文件。

## 检查下载的文件 {#check-the-download}

每个发布版本都在 `SHA256SUMS` 中列出它的所有文件。校验和能说明文件是完整的，但不能说明是谁制作的。
构建证明可以说明这一点。

在 Linux 上，把文件和 `SHA256SUMS` 放在同一个文件夹中，然后运行：

```bash title="Terminal"
sha256sum --check --ignore-missing SHA256SUMS
```

在 macOS 上，输出你的文件的校验和，并用肉眼与 `SHA256SUMS` 中的那一行比对：

```bash title="Terminal"
shasum -a 256 inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz
grep darwin-arm64.tar.gz SHA256SUMS
```

发布工作流在签名文件时不使用我们自己的密钥。它把 `SHA256SUMS` 交给 GitHub 的 `actions/attest` 步骤，
该步骤以这个工作流的名义写入构建证明。要检查一个文件，请使用 GitHub CLI：

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb --repo habhabhabs/inventag-aws
```

未针对 GitHub 验证：对发布文件运行 `gh attestation verify`。测试运行不会生成任何构建证明。第一份真实的构建证明由第一次正式发布运行生成，这次运行还没有进行。

每个 `.tar.gz`、`.deb` 和 `.rpm` 还有一份 SBOM，文件名是在原文件名后加 `.cdx.json`。
见[软件物料清单](../security/sbom.md)。

## 打包构建中的许可证 {#licenses-in-packaged-builds}

InvenTag 使用 MIT 许可证。可执行文件压缩包、`.deb` 和 `.rpm` 包含 GNU libiconv，
这是一个使用 GNU 宽通用公共许可证（LGPL）2.1 版的库。计划中的 Homebrew formula 安装同一个压缩包，所以它也包含 libiconv。
libiconv 的代码位于 lxml 的扩展模块内部。InvenTag 需要 lxml 来写 Word 文件。lxml 项目构建这些模块，并把 libiconv 链接进去。
InvenTag 原样携带 lxml 的文件，不做任何修改。

- 用 pip、pipx 或 uv 安装时，InvenTag 的文件中不包含 libiconv。你的安装工具会从 Python 包索引下载 lxml 自己的 wheel。
- 声明文件是 `THIRD-PARTY-LICENSES.txt`。它列出每个携带的组件、它的许可证和许可证文本，并包含 LGPL 2.1 的全文。
  每个发布版本为每种系统提供一个声明文件，文件名是
  `inventag-%INVENTAG_VERSION%-<os>-<cpu>.THIRD-PARTY-LICENSES.txt`。
  同一个文件也在软件包里面：
  - 压缩包：`inventag/THIRD-PARTY-LICENSES.txt`
  - `.deb` 和 `.rpm`：`/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` 和
    `/opt/inventag/THIRD-PARTY-LICENSES.txt`
- 声明文件写明了 libiconv 的版本和源代码的位置。在这个发布版本中，它写明的是 lxml 6.1.3 内部的 libiconv 1.18：
  - libiconv：<https://www.gnu.org/software/libiconv/> 和
    <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>
  - lxml：<https://github.com/lxml/lxml>
- InvenTag 不提供寄送源代码的书面承诺。上面的地址就是源代码所在。如果某个地址打不开，
  请到 <https://github.com/habhabhabs/inventag-aws/issues> 提交一个 issue。
- lxml 的模块是安装目录中的独立文件。你可以用你自己构建的同版本 lxml 替换它们。
  文件夹在压缩包中是 `inventag/_internal/lxml/`，在 `.deb` 和 `.rpm` 中是 `/opt/inventag/_internal/lxml/`。
  在 macOS 上，替换模块之后要重新签名：`codesign -s - --force <file>`。

未针对你自己构建的 lxml 验证：你构建的模块能代替内置的模块正常工作。

未针对 GitHub Runner 之外的 macOS 验证：Homebrew 安装和 Gatekeeper 的行为。

本页不构成法律意见。

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

未针对 AWS CLI 验证：本节中的登录命令。

请优先使用短期凭证，例如 IAM Identity Center 或代入的角色，
而不是存放在磁盘上的访问密钥。

## 检查是否可用 {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

退出码为 0 表示 InvenTag 能够登录。加上 `--verbose` 还能看到各个步骤。
下面是针对模拟 AWS 离线运行得到的示例输出（示例数据）：

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
```

```bash title="Terminal"
echo $?
```

```text title="输出"
0
```

如果凭证缺失，或安全令牌无效或已过期，InvenTag 会说明原因并给出修复建议。
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
  仓库中的策略新增了 17 个读取操作（并且不再列出 `cloudtrail:LookupEvents`）；没有这些权限时，每个被拒绝的列出调用都会给出一条警告，这些资源仍会像以前一样通过 Tagging API 找到（如果它们带有标签）。升级后的第一份变更报告会把新列出服务的资源显示为新增，尽管它们之前就存在。
  参见 [IAM 权限](../reference/iam-permissions.md)。
- **更严格的文件检查。** 空的设置文件、写了两次的键，或类型错误的 `--bom-config` 值，都会以退出码 1 停止运行。
- **相互冲突的选项会以退出码 2 停止**，例如同时使用 `--accounts-file` 和 `--accounts-prompt`，
  或给了 `--s3-kms-key-id` 但没有 `--s3-encryption aws:kms`。
- **时间限制按账户计算**，从该账户开始扫描时算起。超时的账户保留已找到的资源，并算作失败。
- **默认退出码不变。** 退出码 5 和 6 是新增的，只在使用 `--fail-on-account-error` 和 `--fail-if-empty` 时出现。无法写出的报告格式会以退出码 1 结束。
- **服务名称和工作表名称保持不变。** v1.1.4 只通过 Tagging API 找到的资源保留其服务名称和工作表（例如
  `ELASTICFILESYSTEM`、`STATES`、`COGNITO-IDP`、`ELASTICMAPREDUCE`、`KAFKA`、`ES`）。它们的行现在带有服务 API 的详细信息，
  Secrets Manager 密钥和 MSK 集群的 ID 列显示名称，而不是 ARN 的最后一部分。

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
| `inventag: command not found` | 激活你运行 `pip install inventag-aws` 的那个虚拟环境，或运行 `python -m pip show inventag-aws` 检查是否已安装。如果你使用独立压缩包，请把 `/opt/inventag/inventag` 链接到 PATH 中的某个文件夹，或者用完整路径运行程序。 |
| `ModuleNotFoundError` | 激活虚拟环境，再次运行 `pip install -r requirements.txt`。 |
| `inventag selftest` 失败 | 重新安装 InvenTag，或重新下载发布文件，然后再次运行 `inventag selftest`。如果再次失败，请到 <https://github.com/habhabhabs/inventag-aws/issues> 提交 issue，并附上输出。 |
| `No AWS credentials found!` | 运行 `aws sso login` 或 `aws configure`，或设置 `AWS_PROFILE`。 |

未针对 AWS CLI 验证：“怎么办”列中的命令。

## 下一步 {#next-step}

[快速开始](./quick-start.md)
