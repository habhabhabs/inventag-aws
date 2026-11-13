---
title: "示例：自定义列"
description: 精确选择 InvenTag 的 Excel 报告中出现哪些列和标签列、按什么顺序排列，并放在同一个可筛选的工作表上。
sidebar_position: 8
---

# 示例：自定义列

**目标：** 一个工作表，包含团队真正会看的列，并按你想要的顺序排列。

**你需要：** 只读凭证。

## 模板 {#template}

```yaml title=".inventag/templates/team-sheet.yaml"
format_version: 1
kind: report
name: team-sheet
description: One sheet, our columns
extends: standard-bom
spec:
  title: Platform team inventory
  columns:
    - { field: source_account_id, header: Account }
    - { field: service, header: Service }
    - { field: resource_type, header: Type }
    - { field: resource_name, header: Name }
    - { field: region, header: Region }
    - { field: raw_data.VolumeType, header: Volume type }
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
    single_sheet_name: Inventory
```

- `columns` 会完全替换继承来的列表，所以请列出你想要的每一列。
- `tag_columns` 在 `columns` 之后，为每个标签键添加一列。用 `all` 表示每个找到的标签，
  或用 `none` 表示不添加。
- `raw_data.<Name>` 直接从 AWS API 响应中读取一个值。对于没有该值的资源，它是空白的。
  要查找名称，请先用 `excel.include_all_fields: true` 运行一次。
- `source`、`sources` 和 `detail_level` 表示每一行来自哪里。参见[字段列表](../templates/reference.md#resource-fields-you-can-use-as-columns)。

## 命令 {#command}

```bash title="Terminal"
inventag templates validate team-sheet
inventag --template team-sheet --create-excel --account-regions us-east-1
```

## 输出 {#output}

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/team-sheet.yaml (report 'team-sheet')
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`Inventory`

`Inventory` 工作表的前几行：

| Account | Service | Type | Name | Region | Volume type | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | EC2 | Volume |  | us-east-1 | gp2 |  |  |  |
| 123456789012 | EC2 | Volume | acme-build-cache | us-east-1 | gp3 |  |  |  |
| 123456789012 | S3 | Bucket | acme-app-logs | us-east-1 |  | platform | CC-1001 | prod |
| 123456789012 | S3 | Bucket | acme-data-lake | us-east-1 |  | data | CC-2002 | prod |
| 123456789012 | S3 | Bucket | acme-reports | us-east-1 |  | finance | 1234 | Production |
| 123456789012 | S3 | Bucket | acme-scratch | us-east-1 |  |  |  |  |

![使用 team-sheet 模板所选列的 Inventory 工作表：Account、Service、Type、Name、Region、Volume type 和三个标签列（示例数据）](../assets/examples/img/team-sheet-inventory.png)

表头行已冻结，并带有筛选按钮。

## 标签映射和服务描述 {#tag-mappings-and-service-descriptions}

`--tag-mappings` 和 `--service-descriptions` 会为默认工作簿添加列。
与 `--template` 一起使用时，在你列出这一列之前它们不会添加任何内容：把 `- field: <列名>` 加到 `columns` 下（列名取自映射文件，或用 `service_description`），或设置 `excel.include_all_fields: true`。`tag_columns` 只显示原始标签值。InvenTag 会记录一条警告，指出缺少的列。如果使用版式文件（`--excel-template` 或 `--word-template`），
请把映射的列列在 `extra_fields` 下。参见
[配置文件](../reference/configuration-files.md#tag-mappings)。

## 下一步 {#next-steps}

- 所有可用的列字段：[模板参考](../templates/reference.md#resource-fields-you-can-use-as-columns)。
