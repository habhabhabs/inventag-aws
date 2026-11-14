---
title: 术语表
description: InvenTag 文档中所用术语的通俗解释，从账户文件和 ARN 到标签策略和只读防护。
sidebar_position: 6
---

# 术语表

**适合谁阅读：** 在这些文档中遇到不熟悉词语的任何人。

下面的每个术语在文档中都只用一种含义。

| 术语 | 含义 |
|---|---|
| **账户文件（Accounts file）** | 用 `--accounts-file` 传入的 YAML 或 JSON 文件，列出要扫描的 AWS 账户。见[配置文件](./configuration-files.md#accounts-file)。 |
| **ARN** | Amazon Resource Name：AWS 给资源的唯一 ID，例如 `arn:aws:s3:::acme-app-logs`。 |
| **AWS 账户** | 一个 AWS 账户，由 12 位数字的账户 ID 标识，例如 `123456789012`。 |
| **BOM** | 物料清单（Bill of materials）：InvenTag 写入 Excel 或 Word 的资源列表。 |
| **合规（Compliant）** | 具有标签策略要求的每个标签，且值在允许范围内的资源。 |
| **配置模板（Config template）** | `kind: config` 的模板：扫描哪些账户和区域、写出哪些文件，以及使用哪个报告模板和标签策略。 |
| **Cost Explorer** | 报告支出的 AWS 服务。InvenTag 调用它来找出有支出的服务；AWS 按请求收费。 |
| **凭证链（Credential chain）** | AWS 工具查找凭证的顺序：先是环境变量，然后是配置文件，再然后是 IAM 角色。 |
| **退出码（Exit code）** | 命令结束时返回的数字。`0` 表示成功；InvenTag 用 `1` 表示错误，`2` 表示选项无效或相互冲突，`3` 表示标签策略违规，`4` 表示有安全组规则达到或超过 `--risk-threshold`，`5` 表示有账户未能完整扫描（使用 `--fail-on-account-error` 时），`6` 表示没有可报告的内容（使用 `--fail-if-empty` 时）。如果同时满足多个条件，先是 5，然后是 6，然后是 3，最后是 4。见[退出码](./cli.md#exit-codes)。 |
| **IAM** | AWS Identity and Access Management：用户、角色，以及规定它们可以做什么的策略。 |
| **IAM Identity Center** | 用于单点登录（SSO）AWS 账户的 AWS 服务。它曾叫 AWS SSO。 |
| **IAM 角色（IAM role）** | 一种带有权限的身份，其他身份可以临时代入它。 |
| **moto** | 一个在你的电脑上模拟 AWS 的 Python 库。文档中的示例输出来自针对 moto 的运行。 |
| **OIDC** | OpenID Connect：让 GitHub Actions 或 GitLab CI/CD 等 CI 系统无需存储密钥即可获得短期 AWS 凭证。 |
| **范围外（Out of scope）** | 由于 `scope` 设置，标签策略不检查的资源。 |
| **只读防护（Read-only guard）** | InvenTag 中在每个 AWS 调用发出之前进行检查，并阻止所有非读取调用的部分。始终开启。 |
| **区域（Region）** | AWS 的地理位置，以 `us-east-1` 或 `eu-west-1` 这样的代码表示。 |
| **报告模板（Report template）** | `kind: report` 的模板：Excel 和 Word 文件的标题、颜色、列、工作表和章节。 |
| **示例数据（Sample data）** | 针对 moto 运行 InvenTag 得到的输出，账户和资源均为虚构。这些页面使用的就是它。 |
| **快照（Snapshot）** | `bom_output/state/` 中的一个 JSON 文件，记录某次运行发现的内容，以便比较各次运行。 |
| **标签（Tag）** | 附加在 AWS 资源上的键和值，例如 `Owner=platform`。键区分大小写。 |
| **标签策略（Tag policy）** | `kind: tag-policy` 的模板：资源必须具有的标签以及允许的值。 |
| **模板（Template）** | 控制一次运行中某一部分的小型 YAML 文件：报告模板、标签策略或配置模板。见[模板](../templates/index.md)。 |
| **限流（Throttling）** | 由于同时到达的请求太多，AWS 放慢或拒绝请求。 |
