---
title: 软件物料清单
description: InvenTag 软件物料清单（SBOM）列出了什么、如何生成，以及如何检查你所安装的依赖项。
sidebar_position: 3
---

# 软件物料清单

**适合谁阅读：** 需要了解 InvenTag 由什么构成的安全和采购审查人员。

**读完后你会了解：** 有哪些 SBOM 文件、它们如何生成，以及如何为你自己的安装生成一份。

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

## 为你自己的安装生成 SBOM {#produce-an-sbom-for-your-own-installation}

```bash title="Terminal"
pip install inventag-aws cyclonedx-bom
cyclonedx-py environment --output-format json --output-file inventag-sbom.json
```

未针对 你安装的 cyclonedx-bom 版本验证：`cyclonedx-py environment` 的选项。

请在你安装 InvenTag 的虚拟环境中运行，这样文件列出的就恰好是你所运行的内容。

## 留意漏洞 {#keep-an-eye-on-vulnerabilities}

有一个定时工作流会扫描依赖项中的已知漏洞。运行了什么、什么会让构建失败，
请阅读[依赖项如何检查](./index.md#how-dependencies-are-checked)；
如果你认为有东西被入侵了，请阅读[供应链事件之后](./index.md#after-a-supply-chain-incident)。
