---
title: 功能状态与已知限制
description: 当前发行版中哪些 InvenTag 功能可用、哪些只是部分可用、哪些参数会报错停止，以及在依赖它之前需要了解的具体限制、费用和风险。
sidebar_position: 5
---

# 功能状态与已知限制

**适合谁阅读：** 打算把 InvenTag 用于真实工作的人。

**读完后你会了解：** 哪些功能可用、它们在哪里止步、哪些参数会报错停止，
以及每项限制该怎么应对。

这一页刻意写得直白。本页描述的是当前发行版；[更新日志](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md)列出了每个发行版的变化。我们逐项检查过：
要么对模拟的 AWS（moto）离线运行代码，要么阅读代码路径。
**没有任何测试在真实的 AWS 账户上运行过。** 凡是下面某一点取决于真实 AWS 的行为，
本页都会明说。如果你修复或改动了其中一项，请在同一个拉取请求中更新本页。

## 测试了什么 {#what-is-tested}

每项功能都有针对模拟 AWS（moto）的离线测试。测试清单以及每个测试检查什么，
见[测试](../security/tests.md)页面。

## 有限制的参数 {#flags-with-a-limit}

| 参数 | 实际会发生什么 |
|---|---|
| `--service-descriptions` | 自定义描述对 InvenTag 没有内置描述的服务有效。对于 S3、EC2、RDS、Lambda 和 VPC 资源，内置描述优先，除非你的条目同时指定了 `template`。参见[配置文件](../reference/configuration-files.md#service-descriptions)。 |
| `--enable-cost-analysis` | 增加一个 Cost Analysis 工作表和四个 `forgotten_analysis.*` 列。其中的费用是根据 AWS Pricing API 得出的估算值，不是你的账单。它会额外发出 Cost Explorer、Pricing 和 CloudWatch 调用。参见[费用](#costs)。 |
| `--compliance-standard` | 以退出码 2 停止。像 SOC 2 这样的标准无法从资源清单中检查，而一个只打印标签的参数会误导你。请使用标签策略模板。 |
| `--create-google-docs`、`--create-google-sheets` | 只针对模拟的 Google 客户端验证过。参见 [Google Sheets 和 Docs](../guides/google-sheets-and-docs.md#what-is-not-verified)。 |
| `--enable-production-safety`、`--security-validation`、`--enforce-read-only` | 保留下来，让旧命令仍能运行。只读防护始终开启。 |
| `--disable-production-safety` | 以退出码 2 停止。防护无法关闭。 |

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)

$ inventag --risk-threshold HIGH
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## InvenTag 能找到什么，不能找到什么 {#what-inventag-finds-and-what-it-does-not}

- **有自己发现代码的服务（24 种）：** VPC（VPC、子网、安全组、互联网网关和 NAT 网关、
  路由表、网络 ACL、弹性 IP 地址）、EC2（实例、卷、快照、密钥对）、S3、RDS、Lambda、
  ELB、ELBv2、IAM、CloudFront、Route 53、KMS、CloudWatch、ECS、EKS、SNS、SQS、
  DynamoDB、API Gateway、Glue、WorkMail、CloudFormation、ACM、CloudTrail 和 EventBridge。
- **其他一切**只有在 Resource Groups Tagging API 返回时才会出现。该 API 列出的是
  现有标签或曾经有过标签的资源，因此其他服务中没有标签的资源会缺失。
  在 `--fallback-display auto`（默认值）下，这类资源只会针对自己的发现代码没有结果的服务显示。
  使用 `--fallback-display always` 可显示全部。
- **不会收集：** 密钥、参数、对象内容或任何其他数据。只读防护会拦截这些调用。
- **全局服务**（IAM、S3 存储桶列表、CloudFront、Route 53，以及 CloudFront 使用的 ACM 证书）
  无论你选择哪些区域，都会针对每个账户从 `us-east-1` 读取一次。它们的区域列显示 `global`；
  S3 存储桶则保留它自己的区域。参见[运行扫描](../guides/run-a-scan.md)。
- **区域。** 不指定 `--account-regions` 时，InvenTag 会向 EC2 询问账户中启用的区域。
  如果该调用失败，它会记录一条警告，并且只扫描 `us-east-1`、`us-west-2`、`eu-west-1`
  和 `ap-southeast-1`。访问检查失败的区域会被跳过并给出警告，运行仍然成功。

## 运行出错时 {#when-a-run-goes-wrong}

- **一个账户失败，其他账户正常：** 运行以退出码 0 结束。运行摘要和报告会列出每个失败的账户及原因。
  如果所有账户都失败，运行以退出码 1 结束。
- **没有找到资源，或过滤器把它们全部去掉了：** InvenTag 不会写出报告，记录一条警告，
  并以退出码 0 结束。请在脚本中检查文件是否存在。
- **你缺少某个服务的权限：** InvenTag 跳过该调用，为该服务记录一条带原因的警告，然后继续。
  如果 Resource Groups Tagging API 返回了该服务的资源，它们仍可能出现。
- **Cost Explorer 访问被拒绝：** 运行在没有计费数据的情况下继续，并记录一条警告。
- **被只读防护拦截的调用**会引发一个指明具体操作的错误。命令行本身不会发出这类调用。
- **S3 上传失败**会让整个运行以退出码 1 结束，此时报告已经写入本地。
- **某种报告格式生成失败**会让运行以退出码 1 结束。

## 费用 {#costs}

默认情况下，发现过程会调用 Cost Explorer 的 `GetCostAndUsage` API。
在我们的离线测试中，它为每个账户发出两次请求。AWS 对每次 Cost Explorer 请求收费。
请参阅最新的
[Cost Explorer 定价](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。

- `--no-billing-validation` 会停止这些调用。此时报告里没有可供对比的计费数据。
- `--enable-cost-analysis` 即使加上 `--no-billing-validation` 也会发出更多调用。在我们的离线测试中
  （一个账户，`us-east-1`），它发出了 5 次 Cost Explorer、3 次 Pricing 和 2 次 CloudWatch 调用。
  估算会对每种实例类型（以及其他规格或类别）分别定价。每个不同的价格查询只发出一次，之后重复使用，
  因此 Pricing 调用次数随不同资源类型和规格的数量增长，而不是随资源数量增长。

其他调用是免费的，但大型账户意味着请求很多，并可能遇到限流（AWS 放慢你的请求）。

## 性能与限制 {#performance-and-limits}

- InvenTag 没有针对真实账户的基准数据。扫描大型账户的所有区域很慢：
  每个服务在每个区域各有一组调用。
- 默认同时扫描四个账户。每个账户有 1800 秒（30 分钟）。运行不会续跑；如果中途停止，请重新开始。
- Excel 工作表名称会被截断为 31 个字符。Word 表格默认每个服务最多显示 50 条资源（`max_rows`）。
- 运行保存快照时，InvenTag 会删除 `bom_output/state/` 中超过 30 天或超出最新 100 个的快照。
  如果需要更长的历史，请自行保留副本。

## 安全说明 {#security-notes}

- **无论如何都要使用只读 IAM 身份。** 防护会拦截写入调用，而你的 IAM（身份与访问管理）策略是第二道独立的保险。
  参见[设置只读访问](../guides/read-only-access.md)。
- **调试日志默认经过脱敏：** 会话令牌、密钥和签名会被遮蔽。但仍应把调试日志视为敏感信息。
- **有两个库函数在你自己的 Python 代码中调用时会写入 AWS**（命令行不会调用它们）：
  `CredentialManager.setup_cross_account_roles()` 会创建 IAM 角色，
  S3 辅助工具可以修改存储桶的生命周期规则（默认关闭，并且会与现有规则合并）。

## 测试与软件物料清单 {#tests-and-the-software-bill-of-materials}

测试套件和依赖清单有各自的页面：
[测试](../security/tests.md)和
[软件物料清单](../security/sbom.md)。
