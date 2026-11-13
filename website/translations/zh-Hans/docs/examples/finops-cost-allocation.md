---
title: "示例：FinOps 成本分摊标签"
description: 使用 InvenTag 的 finops-cost-report 模板，找出哪些 AWS 资源缺少成本分摊报告所依赖的 CostCenter、Owner、Project 和 Environment 标签。
sidebar_position: 5
---

# 示例：FinOps 成本分摊标签

**目标：** 为 FinOps（云财务运营）或财务团队生成一份报告，逐个资源显示成本分摊标签是否存在且有效。

**你需要：** 只读凭证。标签只有在你于 AWS Billing and Cost Management 控制台中将其激活为成本分摊标签之后，
才会出现在 AWS 成本报告中。InvenTag 显示哪些资源带有这些标签；它不计算成本。

## 模板 {#template}

`finops-cost-report`（一个报告模板）把 CostCenter、Owner、Project 和 Environment 显示为列，
并启用 `finops-cost-allocation` 标签策略：

| 标签键 | `finops-cost-allocation` 中的规则 |
|---|---|
| `CostCenter` | `CC-` 加四位数字，例如 `CC-1234` |
| `Owner` | 任意值 |
| `Project` | 任意值 |
| `Environment` | `prod`、`staging`、`dev`、`test` 或 `sandbox` |

如果你的成本中心格式不同，可以调整策略并保留报告：

```yaml title=".inventag/templates/our-cost-tags.yaml"
format_version: 1
kind: tag-policy
name: our-cost-tags
description: Our cost centres are five-digit numbers
extends: finops-cost-allocation
spec:
  required_tags:
    - key: CostCenter
      pattern: "[0-9]{5}"
```

## 命令 {#command}

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
# with your own policy:
inventag --template finops-cost-report --template our-cost-tags --create-excel
```

## 输出 {#output}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

**工作表：** `Summary`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Tag Compliance`

`Tag Compliance` 工作表的前几行：

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

<img src={require("../assets/examples/img/finops-tag-compliance-sheet.png").default} alt="Tag Compliance 工作表：每个资源一行，包含账户、区域、服务、类型、资源、ARN、状态、缺少的标签和问题，其后是策略规则表（示例数据）" width="1074" height="295" loading="lazy" />

Word 文档的 Tag compliance 章节：

**文档大纲：**

- **Cost Allocation Tag Report**（标题）
- Summary
- Tag compliance
  - Required tags
  - Non-compliant resources
- Resources by service
- About this report

文档中的一个表格：

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| CostCenter | Matches: CC-[0-9]&#123;4&#125; | 19 | 1 |
| Owner | Any value | 16 | 0 |
| Project | Any value | 20 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 16 | 1 |

JSON 文件：

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

[下载示例标签合规 JSON](pathname:///inventag-aws/downloads/tag-compliance-sample.json)（8 KB，示例数据）

## 下一步 {#next-steps}

- 把 Word 文档发给预算负责人。其中的 Tag compliance 章节列出了不合规的资源。
- 每周跟踪进展：[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md)。
