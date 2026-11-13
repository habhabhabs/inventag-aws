---
title: 代码如何组合在一起
description: 面向贡献者的 InvenTag Python 包地图：CLI、多账户编排、发现、处理、模板、报告和状态。
sidebar_position: 2
slug: /architecture/core-module-integration
---

# 代码如何组合在一起

**适合谁阅读：** 想要熟悉代码结构的贡献者。

**读完后你会知道：** 一次运行中每个模块负责什么，以及做某项更改应该从哪里入手。

## 一次运行的路径 {#the-path-of-one-run}

```text
inventag_cli.py
  -> inventag/cli/main.py              parse flags, validate, set up logging
       -> templating/runner.py         only with --template: load templates,
                                       apply a config template to the flags
  -> core/cloud_bom_generator.py       CloudBOMGenerator
       1. sessions per account         profiles, keys or sts:AssumeRole
       2. discovery per account        discovery/inventory.py and friends
       3. consolidation                one list of resource dictionaries
       4. documents                    reporting/bom_processor.py, then
                                       reporting/converter.py (default) or
                                       templating/render_excel.py and
                                       render_word.py (with --template)
       5. state                        state/ snapshots and changelog
```

## 各个包 {#packages}

| 包 | 职责 | 从哪里入手 |
|---|---|---|
| `inventag/cli/` | 标志、配置验证、日志 | `main.py`, `config_validator.py` |
| `inventag/core/` | 多账户编排和凭证 | `cloud_bom_generator.py` |
| `inventag/discovery/` | 发现资源：逐个服务的 API 调用、Tagging API、Cost Explorer | `inventory.py`, `comprehensive_discovery.py` |
| `inventag/reporting/` | 规范化资源，并写出默认的 Excel 和 Word 文件 | `bom_processor.py`, `converter.py` |
| `inventag/templating/` | 模板加载、验证、继承、标签策略检查，以及由模板驱动的 Excel 和 Word 输出 | `schema.py`, `registry.py`, `runner.py` |
| `inventag/state/` | 快照、差异和变更日志 | `state_manager.py` |
| `inventag/compliance/` | 用于标签检查和安全的库类；目前 CLI 基本不使用 | `checker.py` |
| `inventag/security/` | 只读保护、IAM 策略列表、日志脱敏、安全的输出文件 | `read_only_guard.py`, `iam_policy.py` |

## 资源字典 {#the-resource-dictionary}

从发现到输出之间的所有环节，传递的都是普通字典，每个资源一个。
模板和报告所依赖的字段列在
[模板参考](../templates/reference.md#resource-fields-you-can-use-as-columns)中。
请保持它们稳定：重命名其中一个，就会破坏别人的模板。

## 模板如何接入 {#how-templates-hook-in}

`templating/runner.py` 定义了 `TemplatedCloudBOMGenerator`，它是 `CloudBOMGenerator` 的子类，只替换文档生成这一步。
一次运行的其余部分，包括发现、凭证和状态，都保持不变。
不使用 `--template` 时，仍使用原来的类，输出与以前完全一样。

## 值得修复的已知缺口 {#known-gaps-worth-fixing}

这些缺口记录在[功能状态](../getting-started/status.md)以及 `CHANGELOG.md` 的 "Open work" 列表中。
每一项都适合作为入门贡献：

- `discovery/arn_utils.py` 是构建和比较 ARN 的唯一位置
  （`build_arn`、`normalize_arn`、`ResourceArnIndex`）。`inventory.py` 和
  `comprehensive_discovery.py` 都使用它。来自 Resource Groups Tagging API 的标签，
  先按规范化后的 ARN 匹配，再按服务、区域和 ID 匹配。
- 全局服务（IAM、S3 列表、CloudFront、Route 53、CloudFront 的 ACM 证书）
  对每个账户从 `us-east-1` 运行一次，并带有区域 `global`。
- 当 `DescribeRegions` 失败时，`cloud_bom_generator.py` 中的区域查找会回退到四个区域。
  `discovery/inventory.py` 使用另一份包含十四个区域的回退列表。
- 对于已有内置模板的服务（S3、EC2、RDS、Lambda、VPC），服务描述文件中自定义的 `description` 会被忽略。
- 即使使用了 `--no-billing-validation`，`--enable-cost-analysis` 仍会调用 Cost Explorer。
- 一个账户失败并不会改变退出码。
- 这些模块不在 CLI 的执行路径上：`reporting/template_framework.py`、
  `branding_system.py`、`word_builder.py`、`excel_builder.py`、
  `document_generator.py` 和 `configuration_manager.py`。

较早的设计笔记已从仓库中删除。请使用本站的页面。
