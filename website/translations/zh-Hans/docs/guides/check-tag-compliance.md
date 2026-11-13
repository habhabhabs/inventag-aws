---
title: 按策略检查标签
description: 使用 InvenTag 标签策略模板，检查 AWS 资源是否带有必需的标签且取值合规，并解读检查结果。
sidebar_position: 4
slug: /architecture/tag-compliance
---

# 按策略检查标签

**适合谁阅读：** 你负责制定标签规范，想知道哪些资源违反了它。

**读完后你可以：** 运行标签检查、解读结果，并编写自己的策略。

## 运行检查 {#run-a-check}

选择一个内置策略，或者使用你自己的：

```bash
inventag --template finops-cost-allocation --create-excel --account-regions us-east-1
```

InvenTag 照常扫描，然后检查范围内的每个资源。下面是使用
`--template finops-cost-report` 离线运行的示例输出（示例数据）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

## 解读结果 {#read-the-results}

| 位置 | 内容 |
|---|---|
| Excel，**Tag Compliance** 工作表 | 范围内每个资源一行：账户、区域、服务、类型、资源、ARN、状态、缺少的标签和其他问题。不合规的行排在最前。表格下方列出每条规则，以及有多少资源缺少该标签或取值错误。 |
| Excel，**Summary** 工作表 | 计数：已检查、合规、不合规、范围外、百分比。 |
| Word，**Tag compliance** 章节 | 同样的计数、各条规则，以及不合规资源的表格（默认最多 100 行）。 |
| `tag_compliance_<timestamp>.json` | 每条规则的计数和每个不合规资源，供脚本和 CI 使用。 |

当资源具有所有必需标签，并且每个取值都符合其规则时，该资源即为**合规**。
问题会被逐一写明，例如：

- `CostCenter: '1234' does not match CC-[0-9]{4}`（格式错误）
- `Environment: 'Production' is not one of prod, staging, dev, test, sandbox`
- `Owner: found 'owner' instead (tag keys are case-sensitive)`

同一示例中的 Tag Compliance 工作表：

**工作表：** `Summary`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Tag Compliance`

`Tag Compliance` 工作表的前几行：

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

Word 章节：

**文档大纲：**

- **Cost Allocation Tag Report**（标题）
- Summary
- Tag compliance
  - Required tags
  - Non-compliant resources
- Resources by service
- About this report

文档中的一张表：

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| CostCenter | Matches: CC-[0-9]&#123;4&#125; | 19 | 1 |
| Owner | Any value | 16 | 0 |
| Project | Any value | 20 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 16 | 1 |

JSON 文件中的 `summary` 部分：

```json title="summary"
{
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
}
```

**范围外**的资源只计数、不检查：策略的 `scope` 把它们排除在外，
例如无法携带标签的 KMS 别名。

**在相信这些数字之前请先了解：** InvenTag 会按 ARN 把 Resource Groups Tagging API
返回的标签与资源匹配；当 ARN 不一致时，则退而使用服务、区域和资源 ID 匹配。
使用 moto 的离线测试针对每个有自己发现代码的服务检查了这一点。真实的 AWS
可能给出不同的答案，因此在依赖某个策略结果之前，请把 ARN 列中的几行与控制台对照一下。

## 编写你自己的策略 {#write-your-own-policy}

从一个内置策略出发，只修改不同的部分：

```bash
inventag templates init finops-cost-allocation --output .inventag/templates/our-tags.yaml --extend
```

```yaml
format_version: 1
kind: tag-policy
name: our-tags
description: Our cost-allocation tags
extends: finops-cost-allocation
spec:
  required_tags:
    - key: Environment                 # replaces the inherited rule
      allowed_values: [production, staging, development]
    - key: Project                     # drops an inherited tag
      remove: true
    - key: DataClassification          # adds a new one
      allowed_values: [public, internal, confidential]
  scope:
    services: [EC2, S3, RDS, LAMBDA]   # only check these services
```

每个标签的规则：

- `allowed_values`：取值必须是其中之一。除非设置 `case_sensitive: true`，否则不区分大小写。
- `pattern`：整个取值必须匹配这个正则表达式。
- 两者都不写：只要标签存在，任何取值都可以。

每个标签使用 `allowed_values` 或 `pattern` 之一，不要两者同时使用。所有字段都列在
[模板参考](../templates/reference.md)中。

## 发现违规时让流水线失败 {#fail-a-pipeline-on-violations}

添加一个设置了 `fail_on_tag_violations: true` 的配置模板。InvenTag 仍会写出所有报告，
然后以退出码 3 退出。参见
[在 CI 中强制执行标签策略](../examples/tag-policy-in-ci.md)。

## 旧版检查脚本 {#the-older-checker-script}

`scripts/legacy/tag_compliance_checker.py --config policy.yaml` 早于模板出现，
有自己的选项（`--help` 会列出）。本文档不涵盖它。请优先使用标签策略模板。

## 下一步 {#next-steps}

- [内置标签策略](../templates/catalogue.md#tag-policy-templates)
- [示例：FinOps 成本分摊标签](../examples/finops-cost-allocation.md)
