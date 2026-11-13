---
title: 调整模板
description: 把 InvenTag 模板复制到你的项目中，只修改需要改的部分，用 templates validate 检查，然后在运行中使用它。
sidebar_position: 3
---

# 调整模板

**适合谁阅读：** 你喜欢某个内置模板，但想要自己的标题、颜色、列或标签规则。

**读完后你可以：** 分四步创建自己的模板：`init`、编辑、`validate`、运行。

下面的输出来自针对模拟 AWS 的离线运行（示例数据）。你的项目文件夹显示为 `~/acme-infra/`。

## 1. 把模板复制到你的项目中 {#1-copy-the-template-into-your-project}

在你的项目文件夹中运行：

```bash
inventag templates init standard-bom --output .inventag/templates/acme-bom.yaml --extend
```

```text title="Terminal"
Created .inventag/templates/acme-bom.yaml (kind: report, name: acme-bom).
Next: edit it, then run 'inventag templates validate .inventag/templates/acme-bom.yaml'.
```

你有两种选择：

- **`--extend`**（上面使用的）会写出一个简短的文件，继承 `standard-bom` 的所有内容。
  你只需添加想要更改的部分，并且可以免费获得内置模板的改进。
- **不使用 `--extend`** 会得到带有全部注释的完整副本。当你想查看并掌控每一项设置时，请使用这种方式。

模板名称来自文件名（`acme-bom.yaml` 变成 `acme-bom`）。用 `--name` 可以选择其他名称，
用 `--force` 可以替换已有的文件。

由于该文件位于 `.inventag/templates/` 中，现在你可以在这个项目里按名称引用它。

## 2. 编辑模板 {#2-edit-it}

新文件如下所示：

```yaml title=".inventag/templates/acme-bom.yaml"
# Inherits everything from 'standard-bom'. Add only what you want to change.
# See: inventag templates show standard-bom --resolved
format_version: 1
kind: report
name: acme-bom
description: "Adapted from standard-bom"
extends: standard-bom
spec: {}
```

把 `spec: {}` 替换成你的更改。这个版本把所有内容放在一个工作表上，使用绿色表头，并显示三个标签列：

```yaml
format_version: 1
kind: report
name: acme-bom
description: "Acme's inventory layout"
extends: standard-bom
spec:
  title: Acme Cloud Inventory
  company_name: Acme Ltd
  colors:
    header_fill: "0B5D1E"
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
```

继承的工作方式：

- **映射会合并。** 设置 `excel.layout` 会保留 `standard-bom` 中 `excel` 的其他所有设置。
- **列表会替换。** 如果你设置了 `columns`，你的列表会替换继承来的列表。请复制你想保留的条目。
- **`null` 会把值重置**为默认值，例如 `tag_policy: null`。
- **标签策略按键合并 `required_tags`。** 子策略可以修改某个标签、添加标签，或用 `remove: true` 删除某个标签，而无需重复其余部分。

要查看继承之后的最终结果，请运行
`inventag templates show acme-bom --resolved`。

## 3. 验证模板 {#3-validate-it}

```bash
inventag templates validate acme-bom
```

如果有错误，你会得到文件、行号和提示。这里把单词 `layout` 误拼成了 `layuot`：

```text title="Terminal"
ERROR ~/acme-infra/.inventag/templates/acme-bom.yaml:13: spec.excel.layuot: unknown field 'layuot'; did you mean 'layout'? Allowed here: autofilter, freeze_header, include_all_fields, layout, max_column_width, single_sheet_name, summary_sheet, tag_compliance_sheet
(exit code 1)
```

修正之后：

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/acme-bom.yaml (report 'acme-bom')
```

当每个文件都有效时，`validate` 以 0 退出，否则以 1 退出，因此你可以在 CI 中运行它。
它还会检查你引用的模板（例如 `tag_policy`）是否存在，以及种类是否正确。

现在你的模板会出现在列表中：

```bash title="Terminal"
inventag templates list --kind report
```

```text title="Terminal"
NAME                KIND    SOURCE   DESCRIPTION
acme-bom            report  project  Acme's inventory layout
board-report        report  project  Branded summary for the leadership team
executive-summary   report  builtin  Short Word report with totals and tag compliance; Excel has one filterable sheet.
finops-cost-report  report  builtin  Standard layout with cost-allocation tag columns, checked against finops-cost-allocation.
network-review      report  project  Every field, for a network review
standard-bom        report  builtin  Summary plus one sheet per service, with readable columns and every tag as a column.
team-sheet          report  project  One sheet, our columns

Search order (first match wins):
  1. project  ~/acme-infra/.inventag/templates
  2. user     ~/.config/inventag/templates  (not created)
  3. builtin  ~/inventag-aws/inventag/templating/builtin
```

示例项目中还包含这些文档中使用的其他模板。

## 4. 使用模板 {#4-use-it}

```bash
inventag --template acme-bom --create-excel --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`Resources`

`Resources` 工作表的前几行：

| Account | Region | Service | Type | Name | ID | ARN | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs | platform | CC-1001 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake | data | CC-2002 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports | finance | 1234 | Production |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | acme-scratch | arn:aws:s3:::acme-scratch |  |  |  |

表头行是绿色的，与模板中的设置一致。

## 与团队共享模板 {#share-templates-with-your-team}

- **一个项目：** 把 `.inventag/templates/` 提交到该项目的仓库。
- **你机器上的每个项目：** 把模板放在 `~/.config/inventag/templates/`。
- **共享文件夹或 CI 镜像：** 设置
  `INVENTAG_TEMPLATE_PATH=/opt/acme/inventag-templates`。

如果两个文件夹中有同名的模板，则以[搜索顺序](./index.md#where-inventag-looks-for-templates)中靠前的为准。
`inventag templates list --all` 也会显示被隐藏的模板。

## 下一步 {#next-steps}

- [模板参考](./reference.md)：你可以设置的每个字段。
- [制作带品牌标识的高管 Word 报告](../examples/branded-executive-report.md)：
  添加徽标。
