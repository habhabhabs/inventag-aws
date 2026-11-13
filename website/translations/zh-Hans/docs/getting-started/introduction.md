---
title: InvenTag 是什么
description: InvenTag 一次运行做什么——查找 AWS 资源、检查标签、生成 Excel 和 Word 报告——它写出什么，以及它不是什么。
sidebar_position: 1
---

# InvenTag 是什么

**适合谁阅读：** 正在判断 InvenTag 是否适合自己工作的人。

**读完后你会了解：** 一次运行做了什么、它会改动什么（只有你磁盘上的文件），
以及它的局限在哪里。

## 三个问题，一份报告 {#three-questions-one-report}

InvenTag 回答关于你的 AWS 账户的三个问题：

1. **有什么？** 跨账户、跨区域的资源清单。
2. **标签规范吗？** 报告中的标签列；配合[标签策略模板](../templates/index.md)，
   还能检查必填标签和允许的取值。
3. **和上次相比有什么变化？** 每次运行都会保存快照，以便比较。
   参见[追踪两次运行之间的变化](../guides/track-changes.md)。

结果就是一份物料清单（BOM）：一个 Excel 工作簿、一个 Word 文档，或两者都有。

## 一次运行如何进行 {#how-a-run-works}

```text
your AWS credentials
        |
        v
  1. find resources   --> List/Describe/Get calls per service,
        |                 the Resource Groups Tagging API, Cost Explorer
        v
  2. tidy and enrich  --> service names, IDs, tags
        |
        v
  3. check tags       --> only when a tag policy is active
        |
        v
  4. write files      --> bom_output/*.xlsx, *.docx, state/ snapshot
```

1. **凭证。** InvenTag 使用标准的 AWS 凭证链：配置文件、环境变量、
   IAM Identity Center（SSO）会话或 IAM 角色。它也可以在其他账户中代入角色。
2. **发现。** 对每个账户和区域，它调用只读的 AWS 应用程序编程接口（API）。
   默认情况下，它还会调用 Cost Explorer 的 `GetCostAndUsage`，找出产生费用的服务。
   AWS 会对 Cost Explorer API 请求收费；`--no-billing-validation` 可关闭这些调用。
3. **处理。** 它统一服务名称和 ID，并收集标签。
4. **输出。** 它把文件写入输出文件夹（默认为 `bom_output/`），
   并把快照写入 `bom_output/state/`。

## 它会改动什么 {#what-it-changes}

只有你磁盘上的文件。InvenTag 读取你的 AWS 账户，绝不会修改它们。

**只读防护**会在每次 AWS 调用发出前进行检查。不属于读取的调用
（`List`、`Describe`、`Get` 等以外的调用）会被拦截，会返回密钥或文件内容的读取
（例如读取密钥值或下载 S3 对象）也会被拦截。你无法关闭这道防护。

仍然请给 InvenTag 使用只读的 IAM 身份。两道相互独立的保险胜过一道：
[设置只读访问](../guides/read-only-access.md)。

## 它不是什么 {#what-it-is-not}

- **不是合规工具。** InvenTag 可以收集证据，例如资源清单和标签覆盖率。
  它不评估也不认证对 SOC 2、PCI DSS、HIPAA、GDPR 或任何其他框架的合规性。
- **不是成本管理工具。** 它列出资源和标签，不跟踪你的账单。可选的 `--enable-cost-analysis`
  参数会添加一个 Cost Analysis 工作表，其中是根据 AWS Pricing API 估算的每月费用。
  这些只是估算值，不是你的账单。
- **与 AWS 无关联。**
- **并不完整。** 它自带 46 种 AWS 服务的发现代码，并非所有服务，
  而且从未在真实的 AWS 账户上测试过。
  [功能状态与已知限制](./status.md)列出了这些限制。

## 下一步 {#next-steps}

- [安装 InvenTag](./installation.md)
- [生成第一份报告](./quick-start.md)
