---
title: 软件物料清单
description: InvenTag 软件物料清单（SBOM）列出了什么、如何生成，以及如何检查你所安装的依赖项。
sidebar_position: 3
---

# 软件物料清单

**适合谁阅读：** 需要了解 InvenTag 由什么构成的安全和采购审查人员。

**读完后你会了解：** 有哪些 SBOM 文件、它们如何生成，如何检查发布文件，以及如何为你自己的安装生成一份 SBOM。

## 文档构建会生成什么 {#what-the-documentation-build-generates}

每次部署文档网站时，构建都会为仓库及其依赖项生成 SBOM 文件，并随网站一起发布：

| 文件 | 列出什么 | 格式 |
|---|---|---|
| 仓库 SBOM | Syft 在仓库中发现的所有内容 | Syft JSON、CycloneDX JSON 和 SPDX JSON |
| Python，来自 `requirements.txt` | InvenTag 声明的最低版本 | CycloneDX JSON 和 XML |
| Python，来自全新安装 | 实际安装的版本 | CycloneDX JSON 和 `pip freeze` 列表 |
| 文档网站 | 构建本网站所用的 Node.js 包 | CycloneDX JSON |

未针对 GitHub Actions Runner 验证：文档构建发布的 SBOM 文件；本页读自工作流文件。

同一次构建还会向本节添加一个摘要页面，**Software Bill of Materials (SBOM)**，
因此它出现在线上网站中，但不会出现在本地构建中。

Python 依赖项声明的是最低版本，而不是精确固定，所以“已安装版本”的文件才能显示，
在构建当天一次真实安装会得到什么。

## 一个发布版本包含什么 {#what-a-release-carries}

每个发布版本都有打包构建：可执行文件压缩包、`.deb` 和 `.rpm` 软件包。发布工作流为它们生成下面的文件。
这些构建见[安装 InvenTag](../getting-started/installation.md#choose-how-to-install)。

| 文件 | 内容 |
|---|---|
| `inventag-<version>-<os>-<cpu>.tar.gz`、`inventag_<version>_<cpu>.deb`、`inventag-<version>-1.<cpu>.rpm` | 打包构建 |
| 上述每个文件对应一个 `.cdx.json` 文件，例如 `inventag_<version>_amd64.deb.cdx.json` | 该文件的 SBOM：它的 Python 包和 C 库，含名称、版本和许可证 |
| `inventag-<version>-<os>-<cpu>.THIRD-PARTY-LICENSES.txt` | 声明文件：每个所携带组件的许可证文本 |
| `inventag-<version>-<os>-<cpu>.components.json` | 用来生成 SBOM 和声明文件的组件列表 |
| `inventag-<version>-linux-<cpu>.build-image.txt` | Linux 构建系统的记录：它的发行版本，以及构建所携带的库的版本 |
| `SHA256SUMS` | 该发布版本其他每个文件的 SHA-256 校验和 |

SBOM 文件使用 CycloneDX 格式，1.5 版，JSON 编码。工作流根据构建结果写出它们，所以它们列出的是文件里实际有的内容，
而不是 `requirements.txt` 所允许的内容。

未针对 CycloneDX 架构验证：SBOM 文件能通过验证器。

未针对 GitHub 验证：发布页带有这些文件。到目前为止的测试运行不会向发布页附加任何文件，带有这些文件的第一次正式发布运行还没有进行。

### 检查发布文件 {#check-a-release-file}

发布工作流在签名文件时不使用我们自己的密钥。它把 `SHA256SUMS` 交给 GitHub 的 `actions/attest` 步骤，
该步骤以这个工作流的名义写入构建证明。用 GitHub CLI 检查一个文件：

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb \
  --repo habhabhabs/inventag-aws \
  --signer-workflow habhabhabs/inventag-aws/.github/workflows/package.yml
```

检查校验和，见[检查下载的文件](../getting-started/installation.md#check-the-download)。

`--repo` 指明仓库。如果证明是由另一个工作流文件生成的，`--signer-workflow` 会让检查失败。

未针对 GitHub 验证：对发布文件使用这些选项运行 `gh attestation verify`。这些选项读自 `gh attestation verify --help`。测试运行不会生成任何构建证明。第一份真实的构建证明由第一次正式发布运行生成，这次运行还没有进行。

### 打包构建中的许可证 {#licenses-in-the-packaged-builds}

InvenTag 使用 MIT 许可证。打包构建还携带其他项目的文件。声明文件列出了它们和它们的许可证文本。

可执行文件压缩包、`.deb` 和 `.rpm` 包含 GNU libiconv，这是一个使用 GNU 宽通用公共许可证（LGPL）2.1 版的库。
Homebrew formula（尚未发布）安装同一个压缩包，所以它也包含 libiconv。libiconv 的代码位于 lxml 的扩展模块内部。
InvenTag 需要 lxml 来写 Word 文件。lxml 项目构建这些模块，并把 libiconv 链接进去。
在压缩包、`.deb` 和 `.rpm` 中，InvenTag 原样携带 lxml 的文件：构建时会把每个文件与锁定文件所指定的 wheel 中的文件逐字节比较。

- 用 pip、pipx 或 uv 安装时，InvenTag 的文件中不包含 libiconv。你的安装工具会从 Python 包索引下载 lxml 自己的 wheel。
- 声明文件是 `THIRD-PARTY-LICENSES.txt`：在压缩包中是 `inventag/THIRD-PARTY-LICENSES.txt`，
  在 `.deb` 和 `.rpm` 中是 `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` 和
  `/opt/inventag/THIRD-PARTY-LICENSES.txt`。发布页还为每种系统单独列出它。它包含 LGPL 2.1 的全文。
- 这个库的源代码位于声明文件所写明的地址。在这个发布版本中：libiconv 1.18 位于
  <https://www.gnu.org/software/libiconv/> 和
  <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>，lxml 6.1.3 位于
  <https://github.com/lxml/lxml>。发布工作流在签名文件之前会请求这两个 libiconv 地址，其中任何一个没有响应就会停止。
- InvenTag 不提供寄送源代码的书面承诺。如果某个地址打不开，
  请到 <https://github.com/habhabhabs/inventag-aws/issues> 提交一个 issue。
- lxml 的模块是安装目录中的独立文件。你可以用你自己构建的同版本 lxml 替换它们。
  文件夹在压缩包中是 `inventag/_internal/lxml/`，在 `.deb` 和 `.rpm` 中是 `/opt/inventag/_internal/lxml/`。
  在 macOS 上，替换模块之后要重新签名：`codesign -s - --force <file>`。

未针对你自己构建的 lxml 验证：你构建的模块能代替内置的模块正常工作。

未针对 Homebrew 安装验证：Homebrew 不会改动 lxml 的文件。

未针对 GNU 的服务器验证：这两个 libiconv 地址会一直有响应。工作流在它的测试运行当天取到了这两个地址。

本节不构成法律意见。

## 为你自己的安装生成 SBOM {#produce-an-sbom-for-your-own-installation}

```bash title="Terminal"
pip install inventag-aws cyclonedx-bom
cyclonedx-py environment --output-format json --output-file inventag-sbom.json
```

未针对你安装的 cyclonedx-bom 版本验证：`cyclonedx-py environment` 的选项。

请在你安装 InvenTag 的虚拟环境中运行，这样文件列出的就恰好是你所运行的内容。

## 留意漏洞 {#keep-an-eye-on-vulnerabilities}

有一个定时工作流会扫描依赖项中的已知漏洞。运行了什么、什么会让构建失败，
请阅读[依赖项如何检查](./index.md#how-dependencies-are-checked)；
如果你认为有东西被入侵了，请阅读[供应链事件之后](./index.md#after-a-supply-chain-incident)。
