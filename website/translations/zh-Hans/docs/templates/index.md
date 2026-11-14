---
title: 模板
description: 用可以列出、复制、调整和验证的小型 YAML 模板，在 InvenTag 中复用报告版式、标签策略和运行设置。
sidebar_position: 1
---

# 模板

**适合谁阅读：** 需要多次运行 InvenTag，并希望每次都使用相同的报告版式、相同的标签规则或相同的扫描设置的人。

**读完后你可以：** 选择一个内置模板，通过 `--template` 使用它，并知道什么时候该自己制作模板。

## 什么是模板 {#what-a-template-is}

模板是一个简短的 YAML 文件，告诉 InvenTag 如何完成一次运行中的某一部分。模板分三种：

| 种类 | 控制什么 | 内置示例 |
|---|---|---|
| `report` | Excel 工作簿和 Word 文档的外观：标题、颜色、列，以及出现哪些工作表和章节 | `standard-bom`, `executive-summary` |
| `tag-policy` | 每个资源必须有哪些标签，以及允许哪些值 | `finops-cost-allocation`, `security-baseline` |
| `config` | 扫描什么、生成什么：账户、区域、输出文件，以及使用哪个报告和标签策略 | `single-account`, `org-multi-account`, `ci-pipeline` |

InvenTag 自带八个[内置模板](./catalogue.md)。你可以把其中任何一个复制到自己的项目中并[调整它](./adapt-a-template.md)。

## 使用模板 {#use-a-template}

在普通运行中添加 `--template`。你可以给出名称或文件路径：

```bash
inventag --template executive-summary --create-word
inventag --template ./my-templates/acme-bom.yaml --create-excel
```

重复使用 `--template`，可以组合每种各一个的模板：

```bash
inventag --template standard-bom --template security-baseline --create-excel
```

设置发生重叠时，由以下规则决定哪个生效：

1. **你输入的参数优先。** 如果 config 模板写了 `outputs: [excel]`，
   而你输入了 `--create-word`，那么你只会得到 Word 文件：你输入的 `--create-excel` 或
   `--create-word` 会完全替换 `outputs`。
2. **命令行上的模板优先于另一个模板内部的引用。**
   `--template security-baseline` 会替换 `finops-cost-report` 所指定的标签策略。
3. **没有报告模板时，InvenTag 使用 `standard-bom`。**

不带 `--template` 的运行使用原来的报告版式。

`--tag-mappings` 和 `--service-descriptions` 会为原来的版式添加列。使用 `--template` 时，报告只显示它列出的列，所以这些列在你把它们写进 `columns`（例如 `- field: service_description`）之前不会出现。InvenTag 会记录一条警告，指出缺少的列。参见[字段列表](./reference.md#resource-fields-you-can-use-as-columns)。

## 标签策略为报告增加什么 {#what-a-tag-policy-adds-to-your-reports}

启用标签策略后，InvenTag 会检查范围内的每个资源，并添加：

- 工作簿中的 **Tag Compliance** 工作表，每个资源一行，说明缺少什么或哪里有错；
- Word 文档中的 **Tag compliance** 章节；
- 一个 `tag_compliance_<timestamp>.json` 文件，可用于脚本或 CI；
- 终端中的一行摘要。

使用 `--template finops-cost-report` 离线运行的示例输出（示例数据）：

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

config 模板可以设置 `fail_on_tag_violations: true`，让 InvenTag 在有资源违反策略时以退出码 3 结束。
内置的 `ci-pipeline` 模板就是这样做的。

有两个可选标志使用各自的退出码：`--fail-on-account-error` 在有账户无法扫描或超出时间限制时以退出码 5 结束，`--fail-if-empty` 在没有找到任何资源时以退出码 6 结束。两者都优先于退出码 3。报告仍然会写出。

## InvenTag 在哪里查找模板 {#where-inventag-looks-for-templates}

当你给出名称时，InvenTag 会按顺序检查以下文件夹，并使用第一个匹配项：

1. 环境变量 `INVENTAG_TEMPLATE_PATH` 中的每个文件夹（在 Linux 和 macOS 上用 `:` 分隔，
   在 Windows 上用 `;` 分隔）。
2. 你运行 InvenTag 所在文件夹中的 `.inventag/templates/`（你的项目）。
3. `~/.config/inventag/templates/`（或 `$XDG_CONFIG_HOME/inventag/templates/`）。
4. 内置模板。

未针对 Windows 验证：`INVENTAG_TEMPLATE_PATH` 中的 `;` 分隔符。

因此，一个名为 `.inventag/templates/standard-bom.yaml` 的文件会在该项目中替换内置的
`standard-bom`。它仍然可以用 `extends: standard-bom` 在原模板的基础上构建。
运行 `inventag templates list` 可以查看找到了什么以及来自哪里。

## 设计上的安全性 {#safe-by-design}

模板是纯数据：

- InvenTag 用安全的 YAML 加载器读取它们。会创建 Python 对象的 YAML 标签，
  例如 `!!python/object`，会被拒绝。
- 模板不能运行代码、计算表达式，也不能从互联网获取任何内容。
- 模板内部的文件引用（`extends`、`tag_policy`、
  `report_template`、`logo`）必须是相对路径，并且位于模板所在的文件夹之内。
- config 模板不能包含访问密钥。请使用 `profile_name` 或 `role_arn`。
- 来自 AWS、以 `=` 开头的值会作为文本写入 Excel，因此标签值不会变成电子表格公式。

## 下一步 {#next-steps}

- [内置模板](./catalogue.md)：每个模板会生成什么。
- [调整模板](./adapt-a-template.md)：复制、编辑、验证、运行。
- [模板参考](./reference.md)：每个字段。
- [示例](../examples/index.md)：使用模板的完整方案。
