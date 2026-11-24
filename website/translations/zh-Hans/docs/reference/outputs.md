---
title: 输出文件
description: InvenTag 写出的每个文件（Excel 和 Word 报告、标签合规 JSON、快照和变更日志）的名称、位置和内容。
sidebar_position: 4
---

# 输出文件

**适合谁阅读：** 你要在脚本中处理 InvenTag 的输出，或向他人解释这些报告。

**读完后你会知道：** InvenTag 写出的每个文件的名称、位置和内容。

所有文件都写入输出文件夹：默认是 `bom_output/`，除非你设置了 `--output-directory`，或在配置模板中设置了 `output_directory`。
InvenTag 写入的其他位置只有你指定的文件（`--log-file`、`--audit-output`、`templates init --output`）、使用 `--s3-bucket` 时的 S3 存储桶，以及使用 Google 选项时的 Google Drive；使用 `--google-oauth-client` 时还有位于 `~/.config/inventag/google-token.json` 的登录令牌文件。

输出文件创建后只有你的用户可以读写，新建的输出文件夹同样只对你的用户私有。

未针对 Windows 验证：文件和文件夹仅对你的用户私有。

本页的示例来自针对模拟 AWS 的离线运行（示例数据）。

## 文件列表 {#file-list}

| 文件 | 何时生成 | 内容 |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`，或没有指定任何输出参数 | Excel 报告 |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | Word 报告 |
| `<account-id>_bom_<timestamp>.xlsx` 和 `.docx` | `--per-account-reports`，代替 `multi_account_bom_*` 文件 | 每个有资源的账户一份报告 |
| `tag_compliance_<timestamp>.json` | 启用了标签策略 | 标签检查结果 |
| `state/state_<timestamp>.json` | 每次运行，除非使用 `--disable-state-management` | 所发现的每个资源的快照，机密值已被遮盖。`metadata.tags.coverage_summary` 按账户统计列出调用的结束方式（`ok`、`empty`、`denied`、`throttled`、`error`、`timeout`，以及 `--account-services` 排除的服务对应的 `out_of_scope`）。`metadata.tags.units_not_read` 列出未能读取的列出调用（仅在有调用失败时出现），`metadata.tags.inventag_version` 记录写出该快照的 InvenTag 版本。超过 30 天的快照，或最新 100 份之外的快照会被删除（`--state-retention-days`、`--state-max-snapshots`）。 |
| `state/metadata.json` | 有快照时 | 快照索引：时间、账户、区域、资源数量、校验和 |
| `policy_findings_<timestamp>.json` | `--policy`（`--policy-format` 的默认值）、与 `--template` 一起使用的 `--finops-checks`，或 `inventag policy check --format json` | 对快照检查策略的结果。见[策略发现项](#policy-findings)。 |
| `policy_findings_<timestamp>.sarif`、`.xml` 和 `.md` | `--policy-format sarif`、`junit` 或 `markdown`，或 `inventag policy check` 的 `--format` 中的同样词语 | 同一结果的 SARIF 2.1.0、JUnit XML 和 Markdown 形式。`junit` 写出 `.xml`，`markdown` 写出 `.md`。 |
| `changelog_<timestamp>.md` | 第二次及之后的运行，除非使用 `--no-generate-changelog` 或 `--disable-delta-detection` | 自上一份快照以来新增、删除或变更了什么。见[跟踪变更](../guides/track-changes.md)。 |
| 你用 `--audit-output` 指定的文件 | 你要求时 | 本次运行调用的每个 AWS 操作 |
| `state/partial/<key>/<account-id>.json` | 有账户失败的运行 | 已完成账户的结果，供 `--resume` 复用，完整运行后会被删除 |

`<timestamp>` 的格式是 `YYYYMMDD_HHMMSS`。报告、Word、变更日志和标签合规文件的名称使用你电脑的本地时间。快照和 S3 文件夹使用 UTC。`policy_findings_` 文件的 `<timestamp>` 是被检查快照中保存的时间（UTC），不是检查时的时钟。

默认工作簿为每个 API 字段提供一个 `raw_data.*` 列，因此工作表可能很宽。快照是带缩进的 JSON，包含每个资源的完整 `raw_data`，因此可能很大。目前没有选项可以省略 `raw_data.*` 列或压缩快照；两者都计划在以后的版本中提供。

## Excel 报告 {#excel-report}

**不使用模板时**，工作簿包含：

- **Summary：** Service、Resource Count、Percentage，以及合计。
- **每个服务一个工作表**（例如 `EC2`、`S3`、`VPC`），按服务名称排序，包含其资源上发现的所有字段，
  包括展平后的 `raw_data.*` 和 `tags.*` 列。以 ID 为键的映射类型 API 字段放在一个 JSON 单元格中。行按类型、名称和 ID 排序。
  每行都有 `source` 列（`service-api`、`tagging-api` 或 `billing`：返回该行的 API）、
  `sources` 列（所有这些 API，用 `+` 连接）和 `detail_level` 列（来自服务自身 API 的行为 `full`，其他为 `identity`）。
- **Network Analysis** 和 **Security Analysis** 工作表，仅在使用 `--enable-network-analysis` 或 `--enable-security-analysis` 时出现。
- **Cost Analysis** 工作表，仅在使用 `--enable-cost-analysis` 时出现：根据 AWS Pricing API 估算的每月费用，不是你的账单，另有一张来自 Cost Explorer 的、按账户和服务列出的已计费成本表。见 [Cost Analysis 工作表](#cost-analysis-sheet)。
- **FinOps** 工作表，位于最后，仅在使用 `--finops-checks` 时出现：见 [FinOps 工作表和 `finops_checks` 键](#finops-sheet-and-the-finops_checks-key)。

常用于存放机密的字段（例如 Lambda 环境变量、CloudFormation 堆栈输出、Glue 触发器参数、连接字符串和签名 URL）的值，在每份报告、快照和日志中都显示为 `***REDACTED***`。
字段名称会保留。参见[功能状态](../getting-started/status.md#what-inventag-finds-and-what-it-does-not)。

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

## FinOps 工作表和 `finops_checks` 键 {#finops-sheet-and-the-finops_checks-key}

使用 `--finops-checks` 时，默认工作簿以一个 `FinOps` 工作表结束。第一行是一条说明，然后是列出的结果，列为 `Check ID`、`Check`、`Result`、`Reason`、`Account`、`Region`、`Service`、`Resource Type`、`Resource ID`、`Name` 和 `Observed`，按检查 ID、账户、区域和资源 ID 排序。随后是一张表，列出每项检查的计数（`Fail`、`Not evaluated`、`Pass`）。使用 `--template` 时不写 `FinOps` 工作表。

命令行不为这些结果写 JSON 文件。在 Python 中，`CloudBOMGenerator.generate_multi_account_bom()` 的结果带有 `finops_checks` 键，用 `json` 输出格式写出的 JSON 报告的 `metadata` 中也有这个键。不使用该参数时没有这个键。字段见 [FinOps 检查](../guides/finops-checks.md#the-finops_checks-result)。

## FinOps costs 工作表和 `finops_costs` 键 {#finops-costs-sheet-and-the-finops_costs-key}

使用 `--finops-cost-allocation` 时，默认工作簿以一个 `FinOps costs` 工作表结束（两个参数都使用时，位于 `FinOps` 工作表之后）：一条说明，然后每个账户、分组和值各占一行，列为 `Account`、`Grouping`、`Value`、`Amount`、`Currency`、`Metric`、`Period start`、`Period end` 和 `Status`。`CloudBOMGenerator.generate_multi_account_bom()` 的结果和 JSON 报告的 `metadata` 带有 `finops_costs` 键；快照带有 `metadata.tags.cost_allocation`（只有表格，除非使用 `--no-cost-in-snapshot`）。见 [FinOps 检查](../guides/finops-checks.md#cost-allocation-from-cost-explorer)。
## Cost Analysis 工作表 {#cost-analysis-sheet}

使用 `--enable-cost-analysis` 时，默认工作簿有一个 `Cost Analysis` 工作表。它的第一行说明这些数字是根据 AWS Pricing API 得出的估算值，不是你的账单。各表按以下顺序排列：`Summary`、按服务的每月估算费用、最贵的资源（前 50 个）、成本趋势、可能被遗忘的资源和建议。`Summary` 之后的每张表在没有行时都会省略。

成本趋势表的标题是“Billed cost by account and service, last two full months (Cost Explorer; a service total, not a resource's cost)”。每个账户和服务一行，来自该账户自己的 Cost Explorer 账单，列如下：

| 列 | 内容 |
|---|---|
| `Account` | 资源所在的账户 ID |
| `Service` | 报告中所用的服务名，例如 `EC2` 或 `S3` |
| `Resources` | 该账户在报告中该服务的资源数量 |
| `Earlier month` | 运行之前两个完整月份中较早的一个，格式为 `YYYY-MM` |
| `Billed (USD)`（第一个） | Cost Explorer 在该月对该服务计费的金额 |
| `Later month` | 较晚的月份，格式为 `YYYY-MM` |
| `Billed (USD)`（第二个） | Cost Explorer 在较晚月份对该服务计费的金额 |
| `Change %` | 从较早月份到较晚月份的变化，四舍五入到一位小数。从零账单开始时，较晚月份有计费则为 100，否则为 0 |
| `Direction` | `increasing` 或 `decreasing`；任一方向的变化小于 5% 时为 `stable` |
| `Billing names counted` | 该行中累加的 Cost Explorer 服务名，用逗号分隔 |

金额列显示 Cost Explorer 返回的单位：所有行单位相同时为 `Billed (USD)`，否则为 `Billed (unit as returned)`，此时每个单元格以其单位结尾。一行是该账户中某服务的总额，不是单个资源的成本，也不会在资源之间分摊。服务的数字是其行中所示计费名称的总和。`EC2 - Other`（卷、NAT 网关、数据传输）是单独的计费名称，不在 EC2 的行中；`Amazon EC2 Container Registry (ECR)` 也不在其中。趋势请求被拒绝或失败的账户，或没有会话的账户，没有任何行，运行会用一条警告说明。月份是运行之前的两个完整月份。

在 Python 中，同样的行是 `CloudBOMGenerator.generate_multi_account_bom()` 结果中的 `cost_analysis["cost_trends"]`。每个条目有 `account_id`、`service`、`billing_names`、`resource_count`、`previous_month`、`current_month`、`previous_monthly_cost`、`current_monthly_cost`、`cost_change_percentage`、`trend_direction`、`alert_triggered` 和 `unit`。在 v1.5.0 之前，没有任何工作表显示趋势；`cost_trends` 的每个条目指向一个资源（`resource_id`），内容是服务总额除以其资源数量。这些条目已经移除：从 `cost_trends` 读取 `resource_id` 的代码，必须改为读取每个账户和服务的一个条目。见 [FinOps 检查](../guides/finops-checks.md#the-cost-trend-of---enable-cost-analysis)。

未针对真实 AWS 验证：真实账户返回的账单，包括管理（付款）账户和成员账户各自看到的内容。

## 策略发现项 {#policy-findings}

`inventag policy check`、`--policy` 以及与 `--template` 一起使用的 `--finops-checks`，会把对状态快照检查策略的结果写入输出目录中名为 `policy_findings_<timestamp>.<extension>` 的文件（`inventag policy check` 则写入 `--output-directory` 的文件夹）：

| 扩展名 | 格式 | 对应的格式名 |
|---|---|---|
| `.json` | 完整结果 | `json` |
| `.sarif` | SARIF 2.1.0，供代码扫描工具使用 | `sarif` |
| `.xml` | JUnit XML，每个策略一个测试用例 | `junit` |
| `.md` | Markdown 表格，每个策略最多 50 行 | `markdown` |

扫描默认写出 `.json`，除非 `--policy-format` 另有指定。`inventag policy check` 把文字打印到屏幕，除非 `--format` 指定了文件格式，否则不写文件；以退出码 1 或 2 结束时不写任何内容。在 Linux 和 macOS 上，这些文件只有其所有者可以读写（模式 0600），无论来自扫描还是 `inventag policy check`；InvenTag 为它们新建的文件夹为模式 0700，已有的文件夹保持原有模式。

JSON 文件有这些顶层键：`schema_version`、`inventag_version`、`now`、`snapshot`、`baseline`、`policies`、`summary`、`findings`、`not_evaluated_units`、`not_evaluated_policies` 和 `unused_waivers`。键已排序，文件以换行符结尾。其中没有主机名、用户名、绝对路径或时钟时间，所以相同的快照和策略得到相同的字节。InvenTag 随附了它的 JSON Schema（`inventag/policy/outputs/schemas/policy-findings-1.json`）；其 `$id` 是名称 `urn:inventag:schema:policy-findings:1`，不是网址。

- `findings` 列出结果为 `fail`、`waived` 或 `not_evaluated` 的每一行。`pass` 和策略未选中的行（`out_of_scope`）只计入 `summary` 和每个策略的 `counts`，不会列出。
- `not_evaluated` 发现项有 `reason`：`identity_only`、`field_missing`、`tags_not_read`、`listing_not_read`、`not_comparable`、`not_convertible` 或 `value_too_long`。数据缺口永远不算通过。
- `not_evaluated_units` 列出扫描中未读取、而策略本需要的列表。`unused_waivers` 列出没有匹配任何内容的豁免，并带有 `why`：`no match`、`expired`、`unknown policy` 或 `superseded`。
- `summary.exit_code` 是 0、7 或 8。
- 资源字段的值只有在使用 `--show-values` 时才显示，被屏蔽的值仍然屏蔽。SARIF 和 JUnit 从不带值。

在文字和 Markdown 形式中，最后一行说明退出码代表什么，例如 `Exit code 7: at least one finding failed at severity high or higher.` 没有阈值时为 `Exit code 0: findings are reported; no threshold was set.` 见[退出码](./cli.md#exit-codes)。

未验证：GitHub code scanning 如何显示 SARIF 文件，或 GitLab 如何显示 JUnit 文件。测试把文件与黄金文件（golden）比较，并把 SARIF 文件与随 InvenTag 提供的简短 schema 比较，而不是与完整的 SARIF schema 比较。

## Word 报告 {#word-report}

**不使用模板时：** 一个标题、一份执行摘要、一张服务表，以及每个服务最多 50 个资源，共六列：Name、Id、Type、Region、Tags 和 Service。如果该服务的资源都没有名称，则这六列是 Id、Type、Region、Tags、Service 和 Source Account Name。

**使用报告模板时：** 即 `word.sections` 中列出的各节。表格的表头行会在每页重复，并为屏幕阅读器标记为表头。
徽标（如果有）带有替代文本。

## 标签合规 JSON {#tag-compliance-json}

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 23,
    "compliant": 1,
    "non_compliant": 22,
    "out_of_scope": 14,
    "percent_compliant": 4.3,
    "missing_by_key": {
      "CostCenter": 20,
      "Owner": 17,
      "Project": 21,
      "Environment": 17
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
  "total_calls": 93,
  "allowed_calls": 93,
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
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## S3 对象 {#s3-objects}

使用 `--s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/` 时，每次运行都会把文件放在以该次运行命名的文件夹下：

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

## 终端输出 {#terminal-output}

不使用 `--verbose` 时，运行会打印警告、错误和已写出的文件。
使用模板时，每个文件会打印为 `Wrote <path>`，如果启用了标签策略，随后还有一行标签策略摘要。不使用模板时，默认报告会打印为 `Data exported to <path>`。使用 `--policy` 时，总是会打印策略摘要；`Policy findings: <path>` 这一行以 INFO 级别记录，只在使用 `--verbose` 时显示。完全不带选项时，`inventag` 会打印帮助页面并以退出码 2 结束。

## 退出码 {#exit-codes}

见[命令行参考](./cli.md#exit-codes)。
