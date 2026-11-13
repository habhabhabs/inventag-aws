---
title: 输出文件
description: InvenTag 写出的每个文件（Excel 和 Word 报告、标签合规 JSON、快照和变更日志）的名称、位置和内容。
sidebar_position: 4
---

# 输出文件

**适合谁阅读：** 你要在脚本中处理 InvenTag 的输出，或向他人解释这些报告。

**读完后你会知道：** InvenTag 写出的每个文件的名称、位置和内容。

所有文件都写入输出文件夹：默认是 `bom_output/`，除非你设置了 `--output-directory`，或在配置模板中设置了 `output_directory`。
InvenTag 写入的其他位置只有你指定的文件（`--log-file`、`--audit-output`），以及使用 `--s3-bucket` 时的 S3 存储桶。

输出文件创建后只有你的用户可以读写，新建的输出文件夹同样只对你的用户私有。

本页的示例来自针对模拟 AWS 的离线运行（示例数据）。

## 文件列表 {#file-list}

| 文件 | 何时生成 | 内容 |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`，或没有指定任何输出参数 | Excel 报告 |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | Word 报告 |
| `<account-id>_bom_<timestamp>.xlsx` 和 `.docx` | `--per-account-reports`，代替 `multi_account_bom_*` 文件 | 每个有资源的账户一份报告 |
| `tag_compliance_<timestamp>.json` | 启用了标签策略 | 标签检查结果 |
| `state/state_<timestamp>.json` | 每次运行，除非使用 `--disable-state-management` | 所发现的每个资源的快照。超过 30 天的快照，或最新 100 份之外的快照会被删除。 |
| `state/metadata.json` | 有快照时 | 快照索引：时间、账户、区域、资源数量、校验和 |
| `changelog_<timestamp>.md` | 第二次及之后的运行，除非使用 `--no-generate-changelog` 或 `--disable-delta-detection` | 自上一份快照以来新增、删除或变更了什么。见[跟踪变更](../guides/track-changes.md)。 |
| 你用 `--audit-output` 指定的文件 | 你要求时 | 本次运行调用的每个 AWS 操作 |

`<timestamp>` 的格式是 `YYYYMMDD_HHMMSS`。

## Excel 报告 {#excel-report}

**不使用模板时**，工作簿包含：

- **Summary：** Service、Resource Count、Percentage，以及合计。
- **每个服务一个工作表**（例如 `EC2`、`S3`、`VPC`），按服务名称排序，包含其资源上发现的所有字段，
  包括展平后的 `raw_data.*` 和 `tags.*` 列。行按类型、名称和 ID 排序。
- **Network Analysis** 和 **Security Analysis** 工作表，仅在使用 `--enable-network-analysis` 或 `--enable-security-analysis` 时出现。
- **Cost Analysis** 工作表，仅在使用 `--enable-cost-analysis` 时出现：根据 AWS Pricing API 估算的每月费用，不是你的账单。

**使用报告模板时**，版式遵循模板：

- **Summary：** 标题、生成时间、账户和区域数量、一张 Service / Resources / Share 表，
  以及（有标签策略时）合规计数。
- **资源工作表：** 每个服务一个，或使用 `layout:
  single-sheet` 时只有一个工作表。表头行默认带样式、已冻结并可筛选。
- **Tag Compliance**（有标签策略时）：范围内每个资源一行，之后是一张规则表，列出缺失和无效的计数。

工作表名称遵循 Excel 的规则：最多 31 个字符，且不含 `[ ] : * ? / \`。
重名的工作表会加上编号。以 `=` 开头的单元格值会按文本存储，绝不会作为公式。
行按服务、类型、名称和 ID 排序。

每种版式的预览由真实文件制作，见[内置模板](../templates/catalogue.md)。

## Word 报告 {#word-report}

**不使用模板时：** 一个标题、一份执行摘要、一张服务表，以及每个服务最多 50 个资源，共六列。

**使用报告模板时：** 即 `word.sections` 中列出的各节。表格的表头行会在每页重复，并为屏幕阅读器标记为表头。
徽标（如果有）带有替代文本。

## 标签合规 JSON {#tag-compliance-json}

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 22,
    "compliant": 1,
    "non_compliant": 21,
    "out_of_scope": 14,
    "percent_compliant": 4.5,
    "missing_by_key": {
      "CostCenter": 19,
      "Owner": 16,
      "Project": 20,
      "Environment": 16
    },
    "invalid_by_key": {
      "CostCenter": 1,
      "Owner": 0,
      "Project": 0,
      "Environment": 1
    }
  },
  "non_compliant_resources": [
    {
      "account": "123456789012",
      "service": "S3",
      "resource_type": "Bucket",
      "resource_id": "acme-reports",
      "arn": "arn:aws:s3:::acme-reports",
      "region": "us-east-1",
      "missing": [],
      "invalid": [
        "CostCenter: '1234' does not match CC-[0-9]{4}",
        "Environment: 'Production' is not one of prod, staging, dev, test, sandbox"
      ]
    }
  ]
}
```

## 快照 {#snapshots}

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

```json title="state/state_<timestamp>.json (structure)"
{
  "top_level_keys": [
    "compliance_data",
    "metadata",
    "network_analysis",
    "resources",
    "security_analysis"
  ],
  "one_resource": {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "acme-app-logs",
    "arn": "arn:aws:s3:::acme-app-logs",
    "region": "us-east-1",
    "tags": {
      "Environment": "prod",
      "Owner": "platform",
      "CostCenter": "CC-1001",
      "Project": "storefront",
      "DataClassification": "internal"
    },
    "source_account_id": "123456789012"
  }
}
```

## 审计 JSON {#audit-json}

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 71,
  "allowed_calls": 71,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "ce",
      "operation": "GetCostAndUsage",
      "allowed": true,
      "count": 2
    },
    {
      "service": "cloudformation",
      "operation": "DescribeStacks",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudformation",
      "operation": "ListStackSets",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudfront",
      "operation": "ListDistributions",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## S3 对象 {#s3-objects}

使用 `--s3-bucket acme-inventory-reports --s3-key-prefix inventag/` 时，每次运行都会把文件放在以该次运行命名的文件夹下：

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

## 终端输出 {#terminal-output}

不使用 `--verbose` 时，运行会打印警告、错误和已写出的文件。
使用模板时，每个文件会打印为 `Wrote <path>`，如果启用了标签策略，随后还有一行标签策略摘要。

## 退出码 {#exit-codes}

见[命令行参考](./cli.md#exit-codes)。
