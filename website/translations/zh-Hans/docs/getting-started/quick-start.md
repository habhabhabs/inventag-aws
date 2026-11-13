---
title: 生成第一份报告
description: 用 InvenTag 扫描一个 AWS 账户和区域，并在大约十分钟内打开它生成的 Excel 和 Word 物料清单报告。
sidebar_position: 3
---

# 生成第一份报告

**适合谁阅读：** 你已经[安装了 InvenTag](./installation.md)，并且有只读的 AWS 凭证。

**读完后你可以：** 扫描一个账户、打开 Excel 和 Word 报告，并用模板选择更清晰的版式。

下面的命令使用 `inventag`。如果你是用 `pip install inventag-aws` 安装的，
请改输入 `inventag`；选项完全相同。

本页所有示例输出都来自针对模拟 AWS 的离线运行（示例数据）。
账户 `123456789012` 和 `acme-*` 资源都是虚构的。

## 1. 确认你在哪个账户 {#1-check-which-account-you-are-in}

```bash title="Terminal"
aws sts get-caller-identity
```

InvenTag 扫描这组凭证所属的账户。

## 2. 扫描一个区域 {#2-scan-one-region}

先从小处着手。一个区域既快又省钱。

```bash title="Terminal"
inventag --create-excel --create-word --account-regions us-east-1
```

- `--create-excel` 和 `--create-word` 用来选择要写出的文件。两者都不指定时，只生成 Excel。
- `--account-regions` 把扫描限制在你列出的区域内，用逗号分隔。不指定时，
  InvenTag 会扫描账户中启用的所有区域，耗时更长。无论你列出哪些区域，
  IAM、S3 存储桶列表、CloudFront 和 Route 53 都只会从 `us-east-1` 读取一次。

结束时你会看到文件写到了哪里：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Word document saved: bom_output/multi_account_bom_20261112_090000.docx
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

这条警告只是说明你没有指定账户，所以 InvenTag 使用了你当前的凭证。
加上 `--verbose` 可以看到每一步。

## 3. 打开报告 {#3-open-the-reports}

Excel 工作簿有一个 **Summary** 工作表，每个服务一个工作表。
不使用模板时，每个服务工作表会列出 InvenTag 找到的所有字段，因此工作表很宽：

**工作表：** `Summary`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`

`S3` 工作表的前几行：

| service | type | id | name | arn | account_id | source_account_id | source_account_name | ... |
|---|---|---|---|---|---|---|---|---|
| S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports |  | 123456789012 | AWS Account 123456789012 (moto) | ... |

该工作表共有 30 列；此处显示前 8 列。

Word 文档包含摘要、服务表格，以及每个服务最多 50 条资源：

**文档大纲：**

- **AWS Resource Inventory - BOM Report**（标题）
- Executive Summary
  - Service Summary
- Detailed Resource Inventory
  - DYNAMODB Resources (1)
  - EC2 Resources (4)
  - EVENTS Resources (1)
  - IAM Resources (1)
  - KMS Resources (14)
  - LAMBDA Resources (1)
  - S3 Resources (4)
  - VPC Resources (10)
- Report Information

文档中的一张表：

| Service | Resource Count | Percentage |
|---|---|---|
| DYNAMODB | 1 | 2.8% |
| EC2 | 4 | 11.1% |
| EVENTS | 1 | 2.8% |
| IAM | 1 | 2.8% |

（共 8 行；显示 4 行。）

InvenTag 还会把本次运行的快照保存到 `bom_output/state/`。

## 4. 用模板选择版式 {#4-choose-a-layout-with-a-template}

[报告模板](../templates/index.md)能提供易读的列名、每个标签一列、冻结的表头行和筛选按钮：

```bash title="Terminal"
inventag --template standard-bom --create-excel --create-word --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

效果请见[内置模板](../templates/catalogue.md#standard-bom)。

## 5. 检查你的标签 {#5-check-your-tags}

添加标签策略，查看哪些资源缺少标签：

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

工作簿里现在有一个 **Tag Compliance** 工作表，列出每个资源缺少什么。
更多内容见[按策略检查标签](../guides/check-tag-compliance.md)。

## 一次运行的费用 {#what-a-run-costs}

InvenTag 发出的只读调用是免费的，但 Cost Explorer 的 `GetCostAndUsage`
调用不是：AWS 按请求收费，在我们的离线测试中，默认运行会为每个账户发出两次。
请参阅最新的
[Cost Explorer 定价](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。
加上 `--no-billing-validation` 就不会发出任何 Cost Explorer 调用。

## 下一步 {#next-steps}

- [功能状态与已知限制](./status.md)：依赖某个参数之前请先阅读。
- [选择要扫描什么、生成什么](../guides/run-a-scan.md)
- [示例](../examples/index.md)：可复制粘贴的方案。
