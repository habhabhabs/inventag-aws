---
title: 功能状态与已知限制
sidebar_label: 功能状态
description: 当前发行版中哪些 InvenTag 功能可用、哪些只是部分可用、哪些参数会报错停止，以及在依赖它之前需要了解的具体限制、费用和风险。
sidebar_position: 5
---

# 功能状态与已知限制

**适合谁阅读：** 打算把 InvenTag 用于真实工作的人。

**读完后你会了解：** 哪些功能可用、它们在哪里止步、哪些参数会报错停止，
以及每项限制该怎么应对。

这一页刻意写得直白。本页描述的是当前发行版；[更新日志](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md)列出了每个发行版的变化。下面每一项都有离线测试或针对模拟 AWS（moto）的运行作为证明。**没有任何测试在真实的 AWS 账户上运行过。** 凡是某一项取决于真实 AWS 的行为，本页都会明说。如果你修复或改动了其中一项，请在同一个拉取请求中更新本页。

## 测试了什么 {#what-is-tested}

[测试](../security/tests.md)页面列出了针对模拟 AWS（moto）的离线测试，以及每个测试检查什么。本文档中没有任何测试证明的陈述，会带有一条以“未针对”开头的说明。

## 有限制的参数 {#flags-with-a-limit}

| 参数 | 实际会发生什么 |
|---|---|
| `--enable-cost-analysis` | 增加一个 Cost Analysis 工作表和四个 `forgotten_analysis.*` 列，其中的估算值来自 AWS Pricing API，不是你的账单，并且会额外发出 Cost Explorer、Pricing 和 CloudWatch 调用（参见[费用](#costs)）。 |
| `--compliance-standard` | 以退出码 2 停止，因为像 SOC 2 这样的标准无法从资源清单中检查；请改用标签策略模板。 |
| `--create-google-docs`、`--create-google-sheets` | 只针对模拟的 Google 客户端验证过。参见 [Google Sheets 和 Docs](../guides/google-sheets-and-docs.md#what-is-not-verified)。 |
| `--enable-production-safety`、`--security-validation`、`--enforce-read-only` | 保留下来，让旧命令仍能运行。只读防护始终开启。 |
| `--disable-production-safety` | 以退出码 2 停止，因为只读防护无法关闭。 |

```bash title="Terminal"
inventag --create-google-docs
```

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)
```

```bash title="Terminal"
inventag --risk-threshold HIGH
```

```text title="输出"
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)
```

```bash title="Terminal"
inventag --compliance-standard soc2
```

```text title="输出"
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="输出"
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
- **其他所有服务**只有在 Resource Groups Tagging API 返回时才会出现，因此其他服务中没有标签的资源会缺失。使用 `--fallback-display auto`（默认值）时，这类资源只在其自身发现代码没有结果的服务中显示；`--fallback-display always` 会显示全部。
- **不收集：** 机密值、参数值、对象内容或任何其他数据，因为只读防护会阻止返回这些内容的调用。
- **允许的响应中的机密值会被遮盖。** 有些读取调用会在设置旁边返回机密。常用于存放机密的字段，其值在报告、
  JSON 输出、状态快照、续扫检查点和日志中会被替换为 `***REDACTED***`：Lambda 和 App Runner 环境变量、
  ECS 和 CodeBuild 环境值、EC2 用户数据、CloudFormation 参数值、堆栈输出值和堆栈集模板正文、
  Glue 作业、触发器和作业运行参数以及连接属性、EMR on EKS 作业参数、WorkSpaces Thin Client 激活码、
  DMS 证书钱包、连接字符串、签名 URL、下载和上传 URL、Splunk HEC、Grafana 和加入令牌，
  以及任何名称类似 password、secret、token、access token 或 refresh token、private key 或 credentials 的字段，
  在 JSON 文本中也是如此。名称会保留。
- **其他字段中的机密不会被发现：** 描述、标签、其他自由文本字段或 AWS 以后新增的字段中的机密，会按原样复制到报告中，因为遮盖是按字段名称进行的。
- **标签按原样显示**，即使标签键看起来像机密，例如 `password`。
- **v1.2.0 之前的版本写出的报告和快照可能包含机密值**，因此请删除旧的 `bom_output/` 文件夹和共享副本，或限制其访问。
- **全局服务**（IAM、S3 存储桶列表、CloudFront、Route 53、用于 CloudFront 的 WAF Web ACL，以及
  CloudFront 使用的 ACM 证书）每个账户只从 `us-east-1`（中国为 `cn-north-1`，GovCloud 为
  `us-gov-west-1`）读取一次，无论你选择哪些区域。它们的区域列显示 `global`；S3 存储桶保留自己的区域。
  参见[运行扫描](../guides/run-a-scan.md)。
- **区域。** 没有 `--account-regions` 时，InvenTag 向 EC2 查询账户中已启用的区域。如果
  `ec2:DescribeRegions` 失败，它会查询 `account:ListRegions`；如果这也失败，它会尝试该分区的每个区域，
  并跳过未通过访问检查的区域。未通过访问检查的区域会被跳过并记录警告，运行仍然成功。

## 运行出错时 {#when-a-run-goes-wrong}

- **一个账户失败，其他账户正常：** 运行以退出码 0 结束；传入 `--fail-on-account-error` 时以退出码 5 结束。
- **用 `--template` 生成的报告**不会列出失败的账户；运行摘要和默认报告会列出。
- **所有账户都失败：** 运行以退出码 1 结束，使用 `--fail-on-account-error` 时也是如此；除非这些账户是因超时而失败，否则不写报告，超时时报告会列出已找到的资源。
- **账户超时：** 它算作失败，超时前找到的资源保留在报告中。
- **没有找到资源，或筛选条件把它们全部去掉了：** 不使用 `--template` 时 InvenTag 不写报告，使用 `--template` 时写出一份空报告；除非你传入 `--fail-if-empty`（退出码 6），否则运行以退出码 0 结束。
- **范围内没有任何资源的标签策略**会报告 `0 of 0 resources compliant (100.0%)`，尽管什么都没有检查。
- **你没有权限的服务**会被跳过并记录一条警告；只有 Resource Groups Tagging API 返回时，它的资源才会出现。
- **因其他原因失败的列出调用**（重试后仍被限流，或出现错误）会记为一条警告，并计入快照（`metadata.tags.coverage_summary`），没有任何报告会提到它。
- **账户中的所有调用都被拒绝：** 该账户不算失败，运行以退出码 0 结束，下一份变更报告会把该账户的所有资源列为已删除。
- **某个服务的列出调用被限流或失败**，在下一份变更报告中，该服务的资源会显示为已删除。
- **与上一次运行相比，区域或服务不同的运行**，会在变更报告中把新范围之外的资源显示为已删除。
- **从 v1.1.4 升级后的第一份变更报告**会把新覆盖服务的资源列为新增，尽管它们之前就存在。
- **扫描过程中会话过期**时，报告只包含会话过期前读取到的内容，没有任何说明，运行以退出码 0 结束，使用 `--fail-on-account-error` 时也是如此。
- **扫描开始时会话已经过期**时，不会生成报告文件，退出码为 0。
- **使用 `--resume` 时**，第一次运行中会话中途过期的账户，可能会被当作已完整扫描而复用。
- **IAM Identity Center（SSO）令牌过期**时，运行会以退出码 1 和 Python 回溯停止，并且消息不会告诉你运行 `aws sso login`。
- **Cost Explorer 访问被拒绝：** 运行在没有账单数据的情况下继续，关于它的两条警告只在使用 `--debug` 时显示。
- **被只读防护阻止的调用**如果发生在列出调用中，该列出会被跳过并输出一行错误，运行仍以退出码 0 结束。
- **S3 上传失败**会让整个运行以退出码 1 结束，此时报告已写到本地。
- **某个报告格式写入失败**会让运行以退出码 1 结束，并且不会向 S3 上传任何文件，已写出的格式也不会上传。
- **无法保存的快照**只会输出一行错误，运行仍以退出码 0 结束。
- **与 `--template` 一起使用的 Google 输出**会被跳过，运行以退出码 0 结束。
- **有些无效值以退出码 1 而不是 2 停止，** 例如 `--max-concurrent-accounts 0` 或
  `--account-processing-timeout 0`。
- **账户文件 `settings` 块中的值会覆盖对应的命令行参数，** 例如 `max_concurrent_accounts`。
- **使用 `--s3-bucket` 时结果为空**会让运行以退出码 1 结束（`S3 upload of reports failed: no files`），使用 `--fail-if-empty` 时也是如此。
- **`--account-regions` 中输入错误的区域名称**会让运行以退出码 0 结束，输出原始的 `KeyError` 文本，并且不写报告。
- **需要 MFA 的配置文件在没有终端的情况下运行**时，会以 Python 回溯和空消息停止，或者在输入保持打开时一直等待。
- **无法写入的 `--audit-output` 或 `--log-file` 路径**会让运行以 Python 回溯结束，而无法使用的输出文件夹要到整个扫描结束后才会发现。
- **Ctrl-C** 会让运行停止且没有可见消息，SIGTERM 会让它停止且没有任何消息。
- **账户文件中账户 ID 相同的第二个条目**会被丢弃且没有任何消息，因此它的区域不会被扫描。
- **两个同时使用同一输出文件夹的运行**不会被阻止。
- **`--validate-config-only` 不读取 `--bom-config`**，因此值有误的 BOM 设置文件能通过检查，只有在真正运行时才会停止（退出码 1）。
- **缺少顶层键 `service_descriptions` 的服务描述文件**能通过检查，运行时会被忽略，日志中记录一条错误，并使用内置描述。
- **`inventag --validate-operations` 只按名称回答：** 它把 `apigateway:GetApiKeys` 和 `ec2:DescribeInstanceAttribute` 显示为 ALLOWED，但带 `includeValues` 或 `Attribute=userData` 调用它们时，防护会拦截。
- **配置模板中设置了 `services` 时**，报告只包含这些服务，但扫描仍会读取所有服务，因此可能出现关于其他服务的警告。

## 费用 {#costs}

默认情况下，发现过程会调用 Cost Explorer 的 `GetCostAndUsage` API。
在我们的离线测试中，它为每个账户发出两次请求。AWS 对每次 Cost Explorer 请求收费：
请参阅最新的
[Cost Explorer 定价](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。

- `--no-billing-validation` 会停止这些调用，此时报告里没有可供对比的计费数据。
- `--enable-cost-analysis` 会发出更多 Cost Explorer、Pricing 和 CloudWatch 调用，即使加上 `--no-billing-validation` 也是如此，调用次数取决于你的资源。每个不同的价格查询只发出一次，之后重复使用，因此 Pricing 调用次数随不同资源类型和规格的数量增长，而不是随资源数量增长。

未针对真实的 AWS 验证：`--enable-cost-analysis` 的成本估算。

InvenTag 会把被限流的调用最多重试 10 次（standard 重试模式）；`AWS_RETRY_MODE` 和 `AWS_MAX_ATTEMPTS` 可以覆盖这一设置。

## 性能与限制 {#performance-and-limits}

- InvenTag 没有针对真实账户的基准数据，扫描会为每个服务在每个区域发出一组调用。
- 针对 moto（在进程内运行，因此没有网络时间），`scripts/benchmark_scan.py --scale 60` 在一个区域中扫描了 10,948 个资源，发出了 2,053 次 API 调用：1,200 次 `s3:GetBucketLocation` 调用（每个存储桶一次）、600 次 `lambda:GetFunctionConfiguration` 调用（每个函数一次）、150 次 Resource Groups Tagging API 调用，以及 103 次其他调用。对真实账户有用的是调用次数。
- 默认同时扫描四个账户（`--max-concurrent-accounts`）。每个账户从开始扫描起有 1800 秒
  （`--account-processing-timeout`）。
- 当有些账户失败时，已完成账户的结果会被保存。在 24 小时内（`--resume-max-age-hours`）用 `--resume`
  运行同一条命令，只扫描其他账户。
- Excel 工作表名称会被截断为 31 个字符，Excel 不允许的字符会变成 `-`，重复的名称会加上 ` (2)`，日志会列出每个被改名的工作表。
- Word 表格默认每个服务最多显示 50 个资源（`max_rows`）。
- 当运行保存快照时，InvenTag 会删除 `bom_output/state/` 中超过 30 天或超出最新 100 个的快照。
  刚写入的快照和与之比较的快照永远不会被删除。用 `--state-retention-days` 和 `--state-max-snapshots`
  修改这些限制，或用 `none` 保留全部。
- 使用 `--enable-network-analysis` 或 `--enable-security-analysis` 时，分析调用在一次运行中会发出两次。
- 网络分析把位于多个子网中的资源只计入第一个子网，并且只把负载均衡器计入其 VPC，而不计入任何子网。
- 网络分析不会把 ElastiCache 集群计为 VPC 或子网的关联资源。
- 服务属性补充（BOM 设置中的 `enable_service_enrichment`）不会运行；报告包含发现过程返回的字段。
- 在模板报告中，如果 AWS 没有为资源返回 `Name` 字段或 `Name` 标签，Name 列为空；ID 列用于识别该资源。
  对于 Lambda 函数、IAM 角色和 KMS 别名，模板报告会把 ID 显示为名称。

## 安全说明 {#security-notes}

- **仍然使用只读 IAM 身份。** 防护会阻止写入调用，而你的 IAM（身份和访问管理）策略是第二道独立的安全网。
  参见[设置只读访问](../guides/read-only-access.md)。
- **调试日志默认经过脱敏：** 会话令牌、密钥、签名以及上面列出的机密值都会被遮盖。仍请把调试日志当作敏感信息。
- **两个库函数可以写入 AWS**，前提是从你自己的 Python 代码中调用（CLI 不会调用它们）：
  `CredentialManager.setup_cross_account_roles()` 只在 `allow_iam_writes=True` 时运行，S3 生命周期辅助函数
  只在 `allow_bucket_writes=True` 时运行。在 CLI 运行中，只读防护会阻止这两者。
- **从你自己的 Python 代码中使用 `CloudBOMGenerator`** 不会安装只读防护。只有 `inventag` 命令会安装。
- **配置模板可以设置输出文件夹以及要扫描的账户和角色。** 只使用你信任的模板。
- **代入角色的会话不会刷新**，因此持续时间超过会话的账户扫描会遇到令牌过期。

  未针对真实的 AWS 验证：代入角色的会话持续一小时。
- **MFA 只能通过 AWS 配置文件（`mfa_serial`）使用**，不支持账户文件中的 `role_arn` 条目。

  未针对真实的 MFA 设备验证：通过带 `mfa_serial` 的 AWS 配置文件使用 MFA。

## 测试与软件物料清单 {#tests-and-the-software-bill-of-materials}

测试套件和依赖清单有各自的页面：
[测试](../security/tests.md)和
[软件物料清单](../security/sbom.md)。
