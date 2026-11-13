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

- **有自己发现代码的服务（46 个）：** VPC（VPC、子网、安全组、互联网网关和 NAT 网关、路由表、网络 ACL、
  弹性 IP 地址）、EC2（实例、卷、快照、密钥对）、S3、RDS、Lambda、ELB、ELBv2、IAM、CloudFront、
  Route 53、KMS、CloudWatch、ECS（集群，以及每个集群中的服务）、EKS、SNS、SQS、DynamoDB、
  API Gateway、Glue、WorkMail、CloudFormation、ACM、CloudTrail、EventBridge、ElastiCache、
  Redshift、Redshift Serverless、OpenSearch、EFS、ECR、Step Functions、Kinesis、Firehose、
  Secrets Manager（仅名称）、Systems Manager 参数（仅名称）、Auto Scaling 组、Backup 保管库、
  Cognito 用户池、CodeBuild、CodePipeline、Athena 工作组、EMR、MSK、AppSync、Elastic Beanstalk
  和 WAF Web ACL。
- **其他所有服务**只有在 Resource Groups Tagging API 返回时才会出现。该 API 列出有标签或曾经有过标签的资源，
  因此其他服务中没有标签的资源会缺失。使用 `--fallback-display auto`（默认值）时，
  这类资源只在其自身发现代码没有结果的服务中显示。使用 `--fallback-display always` 可显示全部。
- **不收集：** 机密值、参数值、对象内容或任何其他数据。只读防护会阻止返回这些内容的调用。
- **允许的响应中的机密值会被遮盖。** 有些读取调用会在设置旁边返回机密。常用于存放机密的字段，其值在报告、
  JSON 输出、状态快照、续扫检查点和日志中会被替换为 `***REDACTED***`：Lambda 和 App Runner 环境变量、
  ECS 和 CodeBuild 环境值、EC2 用户数据、CloudFormation 参数值和输出值、Glue 作业和触发器参数以及连接属性，
  以及任何名称类似 password、secret、token、private key 或 credentials 的字段。名称会保留。
- **其他字段中的机密不会被发现。** InvenTag 按字段名称判断，因此描述、标签或其他自由文本字段中的机密不会被遮盖。
- **v1.2.0 之前的版本写出的报告和快照可能包含机密值。** 请删除旧的 `bom_output/` 文件夹和共享副本，或限制其访问。
- **全局服务**（IAM、S3 存储桶列表、CloudFront、Route 53、用于 CloudFront 的 WAF Web ACL，以及
  CloudFront 使用的 ACM 证书）每个账户只从 `us-east-1`（中国为 `cn-north-1`，GovCloud 为
  `us-gov-west-1`）读取一次，无论你选择哪些区域。它们的区域列显示 `global`；S3 存储桶保留自己的区域。
  参见[运行扫描](../guides/run-a-scan.md)。
- **区域。** 没有 `--account-regions` 时，InvenTag 向 EC2 查询账户中已启用的区域。如果
  `ec2:DescribeRegions` 失败，它会查询 `account:ListRegions`；如果这也失败，它会尝试该分区的每个区域，
  并跳过未通过访问检查的区域。未通过访问检查的区域会被跳过并记录警告，运行仍然成功。

## 运行出错时 {#when-a-run-goes-wrong}

- **一个账户失败，其他账户正常：** 运行以退出码 0 结束；传入 `--fail-on-account-error` 时以退出码 5 结束。
  运行摘要和报告会列出每个失败的账户及原因。如果所有账户都失败，运行以退出码 1 结束。
- **账户超时：** 它算作失败。超时前找到的资源保留在报告中，报告会说明该账户不完整。
- **没有找到资源，或筛选条件把它们全部去掉了：** 不使用 `--template` 时，InvenTag 不写报告，
  记录一条警告并以退出码 0 结束。使用 `--template` 时，它会写出一份空报告。`--fail-if-empty`
  让这两种情况都以退出码 6 结束。
- **你没有权限的服务：** InvenTag 跳过该调用，为该服务记录一条说明原因的警告，然后继续。
  如果 Resource Groups Tagging API 返回该服务的资源，它们仍可能出现。
- **因其他原因失败的列出调用**（重试后仍被限流，或出现错误）会针对该服务和区域记录为警告，
  并记录在 JSON 输出中（`metadata.coverage`）。
- **Cost Explorer 访问被拒绝：** 运行在没有账单数据的情况下继续，并记录一条警告。
- **被只读防护阻止的调用**会引发一个指明该操作的错误。CLI 本身不会发出这类调用。
- **S3 上传失败**会让整个运行以退出码 1 结束，此时报告已写到本地。
- **某个报告格式写入失败**会让运行以退出码 1 结束。
- **有些无效值以退出码 1 而不是 2 停止，** 例如 `--max-concurrent-accounts 0` 或
  `--account-processing-timeout 0`。
- **账户文件 `settings` 块中的值会覆盖对应的命令行参数，** 例如 `max_concurrent_accounts`。

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

其他调用是免费的，但大型账户意味着请求很多，并可能遇到限流（AWS 放慢你的请求）。InvenTag 会把被限流的调用
最多重试 10 次（standard 重试模式）；`AWS_RETRY_MODE` 和 `AWS_MAX_ATTEMPTS` 可以覆盖这一设置。

## 性能与限制 {#performance-and-limits}

- InvenTag 没有针对真实账户的基准数据。扫描大型账户的每个区域很慢：每个服务在每个区域都要发出一组调用。
- 针对 moto（在进程内运行，因此没有网络时间），`scripts/benchmark_scan.py` 在一个区域中扫描了
  9,547 个资源，发出了 2,027 次 API 调用。对真实账户有用的是调用次数：每个区域约 60 次固定调用，
  加上每个 S3 存储桶和每个 Lambda 函数各一次调用，再加上每 100 个带标签的资源一页 Tagging API。
- 默认同时扫描四个账户（`--max-concurrent-accounts`）。每个账户从开始扫描起有 1800 秒
  （`--account-processing-timeout`）。
- 当有些账户失败时，已完成账户的结果会被保存。在 24 小时内（`--resume-max-age-hours`）用 `--resume`
  运行同一条命令，只扫描其他账户。
- Excel 工作表名称最多 31 个字符：更长的名称会被截断，Excel 不允许的字符会变成 `-`，重复的名称会加上
  ` (2)`，日志会列出每个被改名的工作表。Word 表格默认每个服务最多显示 50 个资源（`max_rows`）。
- 当运行保存快照时，InvenTag 会删除 `bom_output/state/` 中超过 30 天或超出最新 100 个的快照。
  刚写入的快照和与之比较的快照永远不会被删除。用 `--state-retention-days` 和 `--state-max-snapshots`
  修改这些限制，或用 `none` 保留全部。
- 使用 `--enable-network-analysis` 或 `--enable-security-analysis` 时，分析调用在一次运行中会发出两次。

## 安全说明 {#security-notes}

- **仍然使用只读 IAM 身份。** 防护会阻止写入调用，而你的 IAM（身份和访问管理）策略是第二道独立的安全网。
  参见[设置只读访问](../guides/read-only-access.md)。
- **调试日志默认经过脱敏：** 会话令牌、密钥、签名以及上面列出的机密值都会被遮盖。仍请把调试日志当作敏感信息。
- **两个库函数可以写入 AWS**，前提是从你自己的 Python 代码中调用（CLI 不会调用它们）：
  `CredentialManager.setup_cross_account_roles()` 只在 `allow_iam_writes=True` 时运行，S3 生命周期辅助函数
  只在 `allow_bucket_writes=True` 时运行。在 CLI 运行中，只读防护会阻止这两者。
- **从你自己的 Python 代码中使用 `CloudBOMGenerator`** 不会安装只读防护。只有 `inventag` 命令会安装。

## 测试与软件物料清单 {#tests-and-the-software-bill-of-materials}

测试套件和依赖清单有各自的页面：
[测试](../security/tests.md)和
[软件物料清单](../security/sbom.md)。
