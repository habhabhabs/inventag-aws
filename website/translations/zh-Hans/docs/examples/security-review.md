---
title: "示例：安全标签审查"
description: 使用 InvenTag 的 security-baseline 标签策略，在安全审查之前检查 AWS 资源是否带有 Owner、Environment 和 DataClassification 标签。
sidebar_position: 6
---

# 示例：安全标签审查

**目标：** 在安全审查或事件演练之前，找出没有负责人、没有环境或没有数据分类的资源。

**你需要：** 只读凭证。

这里只检查标签。它不评估任何东西的配置有多安全，通过检查也不代表你符合任何框架的要求。

## 模板 {#template}

内置的 `security-baseline` 标签策略要求：

| 标签键 | 规则 |
|---|---|
| `Owner` | 任意值 |
| `Environment` | `prod`、`staging`、`dev`、`test` 或 `sandbox` |
| `DataClassification` | `public`、`internal`、`confidential` 或 `restricted` |

## 命令 {#command}

```bash title="Terminal"
inventag --template standard-bom --template security-baseline \
  --create-excel --create-word --account-regions us-east-1
```

## 输出 {#output}

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'security-baseline': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Tag Compliance`

`Tag Compliance` 工作表的前几行：

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | Owner, Environment, DataClassification |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | Owner, Environment, DataClassification |  |

在 "Missing tags" 列中筛选 `Owner`，即可先找出没有负责人的资源。

## 下一步 {#next-steps}

- 为没有负责人的资源确定负责人，然后在你的基础设施代码中为它们打上标签。
- 把检查范围缩小到仅数据存储：

```yaml title=".inventag/templates/data-stores.yaml"
format_version: 1
kind: tag-policy
name: data-stores
description: Classification on data stores only
extends: security-baseline
spec:
  scope:
    services: [S3, DYNAMODB, RDS]
```
