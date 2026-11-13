---
title: 示例
description: 可直接复制的 InvenTag 常见任务方案，每个都附有命令、模板和生成的输出，从快速审计到定时上传到 S3。
sidebar_position: 1
---

# 示例

**适合谁阅读：** 你清楚自己要完成什么任务，想要一个可以直接复制的方案。

**你会得到：** 每个示例的目标、模板、命令、生成的输出，以及下一步该做什么。

这些页面上的每一份输出都来自针对模拟 AWS（[moto](https://github.com/getmoto/moto)）的真实 InvenTag 运行，而不是来自真实账户。
它们是**示例数据**：账户（例如 `123456789012`）和 `acme-*` 资源都是虚构的，你的名称和数量会有所不同。
这些示例由 `scripts/docs/generate_example_outputs.py` 生成，因此与当前代码保持一致。

| 示例 | 你将得到 |
|---|---|
| [快速审计一个账户](./quick-audit.md) | 你当前登录账户的 Excel 和 Word 清单 |
| [盘点组织中的每个账户](./accounts-setup.md) | 通过每个账户中的只读角色生成覆盖多个账户的一份报告 |
| [在 CI 中强制执行标签策略](./tag-policy-in-ci.md) | 资源违反标签规则时会失败的流水线步骤 |
| [FinOps 成本分摊标签](./finops-cost-allocation.md) | 一份报告，说明哪些资源带有成本报告所需的标签 |
| [安全标签审查](./security-review.md) | Owner、Environment 和数据分类标签的覆盖情况 |
| [带品牌标识的高管 Word 报告](./branded-executive-report.md) | 带有你的徽标和颜色的简短横向 Word 报告 |
| [自定义列](./custom-columns.md) | 只包含你所选列、且在同一个工作表上的工作簿 |
| [按计划将报告上传到 S3](./scheduled-s3-upload.md) | 每次运行后，S3 存储桶中都有加密的报告 |
| [在 SOC 2 范围讨论之前检查标签证据](./evidence-soc2.md) | 一份列表，列出没有记录 SOC 2 范围、系统、创建方式或关键程度的资源 |

所有示例都假定你已经[安装了 InvenTag](../getting-started/installation.md)，
并使用[只读身份](../guides/read-only-access.md)登录。
