---
title: "示例：带品牌标识的高管 Word 报告"
description: 使用 InvenTag 报告模板，为管理层生成一份带有你的徽标、颜色和标签合规摘要的简短横向 Word 报告。
sidebar_position: 7
---

# 示例：带品牌标识的高管 Word 报告

**目标：** 一份给管理层看的简短 Word 文档，带有你的徽标和颜色：
包含总数、服务和标签合规情况，不含逐个资源的表格。

**你需要：** 只读凭证，以及一个 PNG、JPEG、GIF 或 BMP 格式的徽标文件。
Word 无法嵌入 SVG 徽标。

## 模板 {#template}

把徽标放在模板旁边，同一文件夹或子文件夹中均可：

```text title="Project layout"
.inventag/templates/
  board-report.yaml
  brand/
    acme-logo.png
```

```yaml title=".inventag/templates/board-report.yaml"
format_version: 1
kind: report
name: board-report
description: Branded summary for the leadership team
extends: executive-summary
spec:
  title: Cloud Estate Summary
  subtitle: Quarterly review
  company_name: Acme Ltd
  logo: brand/acme-logo.png
  logo_alt_text: Acme Ltd logo        # read by screen readers
  colors:
    header_fill: "4B2E83"             # 10.4:1 contrast with white text
  tag_policy: security-baseline
  word:
    orientation: landscape
```

## 命令 {#command}

```bash title="Terminal"
inventag templates validate board-report
inventag --template board-report --create-word --account-regions us-east-1
```

## 输出 {#output}

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/board-report.yaml (report 'board-report')
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Tag policy 'security-baseline': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

**文档大纲：**

- **Cloud Estate Summary**（标题）
- Summary
- Resources by service
- Tag compliance
  - Required tags
  - Non-compliant resources
- About this report

文档中的一个表格：

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| Owner | Any value | 16 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 16 | 1 |
| DataClassification | One of: public, internal, confidential, restr... | 21 | 0 |

<img src={require("../assets/examples/img/board-report-word-page1.png").default} alt="带品牌标识的横向 Word 报告第一页：紫色方形徽标、标题 Cloud Estate Summary、Quarterly review、Prepared for Acme Ltd，以及摘要列表（示例数据）" width="977" height="736" loading="lazy" />

[下载示例 Word 报告](pathname:///inventag-aws/downloads/board-report-sample.docx)（38 KB，示例数据）

如果徽标缺失，或者不是 Word 支持的图片格式，运行会在扫描之前停止：

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   ~/acme-infra/.inventag/templates/board-report.yaml:10: spec.logo: logo file not found: ~/acme-infra/.inventag/templates/brand/acme-logo.png
$ echo $?
1
```

## 下一步 {#next-steps}

- 保持颜色易读：选择与表头文字对比度至少为 4.5:1 的表头颜色。
- 把完整清单也生成为 Excel 文件：
  `inventag --template board-report --create-word --create-excel`。
