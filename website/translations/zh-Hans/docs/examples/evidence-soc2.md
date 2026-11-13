---
title: "示例：在 SOC 2 范围讨论之前检查标签证据"
description: 使用 InvenTag 的 evidence-soc2 标签策略模板，找出没有记录 SOC 2 范围、系统名称、创建方式或关键程度标签的 AWS 资源。
sidebar_position: 10
---

# 示例：在 SOC 2 范围讨论之前检查标签证据

:::note

这里只检查标签证据。标签值由资源所有者自行填写，InvenTag 不会核实。检查通过并不代表账户满足 SOC 2。

:::

**目标：** 在与审计人员或客户讨论哪些系统属于 SOC 2 范围之前，列出没有记录范围、系统名称、创建方式或关键程度的资源。

**你需要：** 只读凭证。InvenTag 读取标签；它不评估控制措施。

## 模板 {#template}

内置的 `evidence-soc2` 标签策略以 `security-baseline`（`Owner`、`Environment` 和 `DataClassification`）为起点，并加入四个标签：

| 标签键 | 规则 |
|---|---|
| `Soc2Scope` | `in-scope` 或 `out-of-scope` |
| `SystemName` | 任意非空文本 |
| `ManagedBy` | `terraform`、`cloudformation`、`cdk`、`manual` 或 `other` |
| `Criticality` | `high`、`medium` 或 `low` |

它覆盖除 KMS 别名之外的所有资源类型。它能显示什么、不能显示什么，见[模板目录](../templates/catalogue.md#evidence-soc2)。

## 命令 {#command}

```bash title="Terminal"
inventag --template evidence-soc2 --create-excel --account-regions us-east-1
```

## 输出 {#output}

示例账户有四个存储桶、一个 DynamoDB 表和一个队列，它们的标签各不相同，另外还有每个账户都有的默认资源。

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'evidence-soc2': 2 of 18 resources compliant (11.1%), 16 non-compliant, 14 out of scope.
```

范围之外的 14 个资源是 KMS 别名。在缺少内容的 16 个资源中，有 12 个是没人打标签的默认资源（默认 VPC 及其子网、路由表、网络 ACL 和安全组，一个 Athena 工作组，以及默认事件总线）。状态列只说明该资源是否带有模板中的每个标签且值在允许范围内。

**工作表：** `Summary`, `ATHENA`, `DYNAMODB`, `EVENTS`, `KMS`, `S3`, `SQS`, `VPC`, `Tag Compliance`

`Tag Compliance` 工作表的前几行：

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | arn:aws:s3:::acme-data-lake | Non-compliant | Criticality |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | arn:aws:s3:::acme-reports | Non-compliant |  | Soc2Scope: 'yes' is not one of in-scope, out-... |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | arn:aws:s3:::acme-scratch | Non-compliant | Owner, Environment, DataClassification, Soc2S... |  |
| 123456789012 | us-east-1 | SQS | Queue | acme-jobs | arn:aws:sqs:us-east-1:123456789012:acme-jobs | Non-compliant | DataClassification, Soc2Scope, SystemName, Cr... |  |
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Compliant |  |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | arn:aws:s3:::acme-app-logs | Compliant |  |  |

各行说明的内容：

- `acme-data-lake` 没有 `Criticality` 标签。
- `acme-reports` 的 `Soc2Scope` 设为 `yes`，不在允许的值之内。
- `acme-scratch` 没有任何标签。
- `acme-jobs` 有 `Owner`、`Environment` 和 `ManagedBy`，但没有 `DataClassification`、`Soc2Scope`、`SystemName` 或 `Criticality`。
- `acme-app-logs` 带有每个标签，且值都在允许范围内。
- `acme-orders` 被其所有者标为 `out-of-scope`，并且仍带有每个标签。检查的是答案已被记录，而不是答案是什么。

要查看哪个标签最常缺失，请阅读 JSON 文件中的摘要：

```json title="tag_compliance_20261112_090000.json (summary, two fields)"
{
  "missing_by_key": {
    "Owner": 13,
    "Environment": 13,
    "DataClassification": 14,
    "Soc2Scope": 14,
    "SystemName": 14,
    "ManagedBy": 13,
    "Criticality": 15
  },
  "invalid_by_key": {
    "Owner": 0,
    "Environment": 0,
    "DataClassification": 0,
    "Soc2Scope": 1,
    "SystemName": 0,
    "ManagedBy": 0,
    "Criticality": 0
  }
}
```

## 它不能告诉你什么 {#what-this-does-not-tell-you}

- 它不能告诉你范围是否正确、控制措施是否存在或是否有效，也不能告诉你审计人员会测试什么。
- 它不检查 `ManagedBy` 是否属实。请与 AWS 添加的 `aws:cloudformation:*` 标签比对。
- 标签存在，只表示所有者写了一些内容。

## 下一步 {#next-steps}

- 为默认资源打上标签，或缩小策略范围使它们不被检查：把 `evidence-soc2` 复制到你的项目中并设置 `spec.scope.services`，做法见[示例：安全标签审查](./security-review.md#next-steps)。
- 在 CI 中先从仅报告模式开始：[示例：在 CI 中强制执行标签策略](./tag-policy-in-ci.md)。
- 编写你自己的规则：[按策略检查标签](../guides/check-tag-compliance.md#write-your-own-policy)。
