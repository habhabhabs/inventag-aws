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
| `--create-html` | HTML 报告只有一种固定版式（报告模板的各个部分只用于 Excel 和 Word），没有 Cost Analysis 表格和 `--policy` 的发现项，也没有排序或筛选。未针对浏览器验证：文件的外观和打印效果。参见 [HTML 报告](../reference/outputs.md#html-report)。 |
| `--finops-cost-allocation` | 使用与 AWS 应答形式相同的 Cost Explorer 应答测试过，没有针对真实的 AWS 测试。标签键只有在付费账户中被激活为成本分配标签之后才会显示支出，成员账户看到的可能比付费账户少（未验证）。参见 [成本分配](../guides/finops-checks.md#cost-allocation-from-cost-explorer)。 |
| `--finops-checks` | `FIN-004` 列出已停止的实例，不论它已停止多久，因为实例列表中没有可靠的停止时间。`FIN-005` 不读取目标的健康状态，所以目标全部不健康的负载均衡器结果为 pass。使用 `--template` 时不写出工作表：检查在状态快照上运行，发现项写入 `policy_findings_<timestamp>.json`。不使用 `--template` 时，结果只在 Excel 工作表中，没有 JSON 文件。参见 [FinOps 检查](../guides/finops-checks.md#what-the-checks-cannot-see)。 |
| `--policy`、`--policy-waivers`、`--policy-fail-on`、`--policy-format`、`inventag policy` | 已离线测试，使用的是模拟账户和手写的快照，没有针对真实 AWS 测试。策略读取扫描放在行上的字段，所以无法判断扫描没有显示的字段。数据未被读取的行是 `not_evaluated`，从不算通过。扫描因策略最多以退出码 7 结束；只有 `inventag policy check` 会以退出码 8 结束。见 [`policy` 子命令](../reference/cli.md#policy-subcommands)和[策略发现项](../reference/outputs.md#policy-findings)。 |
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
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour. InvenTag does not assess compliance. To check your tags against a built-in baseline, run: inventag --template security-baseline --create-excel
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="输出"
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked. Remove this option; nothing else is needed. To see which calls are allowed, run: inventag --validate-operations ec2:DescribeInstances
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
- **所有账户都失败：** 运行以退出码 1 结束，使用 `--fail-on-account-error` 时也是如此；除非这些账户是因超时而失败，否则不写报告，超时时报告会列出已找到的资源。
- **账户超时：** 它算作失败，超时前找到的资源保留在报告中。账户被放弃时仍在等待的调用不会被重试，也不会让进程继续存活：报告写出后运行随即结束。未针对真实 AWS 验证：真实的挂起端点（测试在 moto 中挂起一个调用）。
- **没有找到资源，或筛选条件把它们全部去掉了：** 不使用 `--template` 时 InvenTag 不写报告，使用 `--template` 时写出一份空报告；除非你传入 `--fail-if-empty`（退出码 6），否则运行以退出码 0 结束。
- **范围内没有任何资源的标签策略**会报告 `0 of 0 resources compliant (100.0%)`，尽管什么都没有检查。
- **你没有权限的服务**会被跳过并记录一条警告；只有 Resource Groups Tagging API 返回时，它的资源才会出现。
- **因其他原因失败的列出调用**（重试后仍被限流，或出现错误）会记为一条警告，并计入快照（`metadata.tags.coverage_summary`）。
- **账户中的所有调用都被拒绝：** 该账户不算失败，运行以退出码 0 结束。使用 `--fail-on-account-error` 时，如果某个账户的每个列举都被拒绝，它仍算作已扫描，运行以退出码 0 结束。要让 CI 作业在什么都读不到时失败，请加上 `--fail-if-empty`。
- **运行无权使用某个 IAM 操作：** 运行备注中，每个账户会输出一行 `Permissions:`，当上传被拒绝时还会为上传报告的身份输出一行，并且 `permissions_denied` 列表会写入 `--audit-output` 文件（见[仅使用 ReadOnlyAccess 运行](../guides/read-only-access.md#run-with-only-readonlyaccess)）。这一行不会列出 `ec2:DescribeRegions` 或 `account:ListRegions`，带 KMS 密钥的上传失败时只会列出 `s3:PutObject`。

  未针对真实的 AWS 验证：带 KMS 密钥的上传被拒绝时，S3 会点名哪个操作。
- **从 v1.1.4 升级后的第一份变更报告**会把新覆盖服务的资源列为新增，尽管它们之前就存在。
- **扫描过程中会话过期**时，报告只包含会话过期前读取到的内容，运行以退出码 0 结束，使用 `--fail-on-account-error` 时也是如此。未针对真实的 AWS 验证：会话过期时 AWS 返回的错误代码。
- **扫描开始时会话已经过期**时，不会生成报告文件，退出码为 0。
- **Cost Explorer 访问被拒绝或被限流：** 运行在没有账单数据的情况下继续，并输出一条指明原因的警告。AWS 错误文本只在使用 `--debug` 或 `-vv` 时显示。
- **`--account-processing-timeout` 小于 1200 秒时，** 每次 Cost Explorer 调用在连接和读取时最多等待该限制的四十分之一，且至少 5 秒，共尝试两次。如果它没有及时响应，账户仍会被扫描，并且运行备注（Run notes）会指出其账单数据缺失。未针对真实的 AWS 验证：响应缓慢的 Cost Explorer 会在该上限内以超时结束。
- **被只读防护阻止的调用**如果发生在列出调用中，该列出会被跳过并输出一行错误，运行仍以退出码 0 结束。
- **S3 上传失败**会让整个运行以退出码 1 结束，此时报告已写到本地。
- **某个报告格式写入失败**会让运行以退出码 1 结束，并且不会向 S3 上传任何文件，已写出的格式也不会上传。
- **无法保存的快照**（或失败的快照列表、变更报告）会在运行摘要之后的说明中列出，并给出要检查的文件夹，运行仍以退出码 0 结束。
- **与 `--template` 一起使用的 Google 输出**会被跳过，运行以退出码 0 结束。
- **有些无效值以退出码 1 而不是 2 停止，** 例如 `--max-concurrent-accounts 0` 或
  `--account-processing-timeout 0`。`--concurrency` 的值超出 1 到 256 时，以退出码 2 停止。
- **账户文件 `settings` 块中的值会覆盖对应的命令行参数，** 例如 `max_concurrent_accounts`。
- **使用 `--s3-bucket` 时结果为空**会让运行以退出码 1 结束，并输出 `Nothing to upload to s3://<bucket>/<prefix>/: the run wrote no report file because there are no resources to report.`，使用 `--fail-if-empty` 时也是如此。
- **`--account-regions` 中输入错误的区域名称**只会被指出一次，并附上列出有效区域的命令，运行以退出码 0 结束。其他区域正常时，报告会不含该区域写出，并且运行备注会说明这一点。
- **账户文件中账户 ID 相同的第二个条目**会被丢弃并给出一条警告，因此它的区域不会被扫描。
- **两个同时使用同一输出文件夹的运行**不会被阻止。
- **带有值有误的 `--bom-config` 文件的 `--validate-config-only`** 会输出一条警告并以退出码 0 结束，而真正运行时会以退出码 1 停止。
- **缺少顶层键 `service_descriptions` 的服务描述文件**能通过 `--validate-config-only`，只给出一条警告并以退出码 0 结束；运行时它会被忽略，日志中记录一条错误，并使用内置描述。
- **`inventag --validate-operations` 把 `apigateway:GetApiKeys` 和 `ec2:DescribeInstanceAttribute` 显示为 ALLOWED**，并附上防护适用的规则（`blocked when includeValues=true`、`blocked when Attribute=userdata`），退出码为 0，因为只有带该参数调用它们时，防护才会拦截。

## 费用 {#costs}

默认情况下，发现过程会为每个账户调用一次 Cost Explorer 的 `GetCostAndUsage` API。该请求覆盖从当月第一天之前 30 天到今天的时间段，计费验证和支出列都读取它，因此只在这段时间内产生费用的服务也算作已计费。AWS 对每次 Cost Explorer 请求收费：
请参阅最新的
[Cost Explorer 定价](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。

一次运行中的 Cost Explorer 请求：账单验证（默认开启）每个账户最多一次，使用 `--enable-cost-analysis` 时成本趋势每个账户再多最多 2 次，每次都使用该账户自己的凭证读取。单账户运行同时使用两者时最多发出 3 次；使用 `--no-billing-validation` 时最多发出 2 次。被限流的请求会重试，总共最多 10 次尝试，每次重试都是一次新的请求。AWS 对每次请求收费。发现开始之前，每次调用 Cost Explorer 的运行都会以警告形式给出这个次数（不含重试）。例如 `Cost Explorer: up to 3 request(s) in this run (billing validation: 1; cost trend: 2). AWS charges for each.`

- `--no-billing-validation` 会停止这些调用，此时报告里没有可供对比的计费数据。
- `--enable-cost-analysis` 也会调用 Cost Explorer，即使加上 `--no-billing-validation` 也是如此。它还会发出 Pricing 和 CloudWatch 调用，次数取决于你的资源。每个不同的价格查询只发出一次，之后重复使用，因此 Pricing 调用次数随不同资源类型和规格的数量增长，而不是随资源数量增长。
- 成本趋势用每个账户自己的凭证读取该账户的账单，并比较运行之前的两个完整月份。对于答复能放进一页的账户，第一次请求就够了（未针对真实 AWS 验证）；第二次请求读取答复的下一页。如果答复的页数超过这个数量，每个账户会有一条警告，说明后面页上的服务没有趋势。请求被拒绝或失败的账户没有趋势，运行会用一条警告说明。
- 服务按其计费名称在账单中查找，所以 S3、SQS 和 SNS 有趋势，EC2 的数字不包含 ECR。`EC2 - Other`（卷、NAT 网关、数据传输）是单独的计费名称，不在 EC2 的数字中。一个服务的数字是该账户和服务的总额，在 Cost Analysis 工作表中只显示一次；它不是某个资源的成本，也不会在资源之间分摊。见 [Cost Analysis 工作表](../reference/outputs.md#cost-analysis-sheet)。
- 在 v1.5.0 之前，趋势只读取一份账单，使用第一个账户的凭证，涵盖所有账户的资源，结果中每个资源一个条目（`cost_analysis["cost_trends"]`；没有工作表显示它）。这类运行的数字与现在的数字不可比较。

未针对真实的 AWS 验证：`--enable-cost-analysis` 的成本估算。

未针对真实的 AWS 验证：AWS 计费的请求次数，以及 AWS 是否对重试计费。

InvenTag 会把被限流的调用最多重试 10 次（standard 重试模式）；`AWS_RETRY_MODE` 和 `AWS_MAX_ATTEMPTS` 可以覆盖这一设置。

## 性能与限制 {#performance-and-limits}

- InvenTag 没有针对真实账户的基准数据，扫描会为每个服务在每个区域发出一组调用。
- 针对 moto（在进程内运行，因此没有网络时间），`scripts/benchmark_scan.py --scale 60` 在一个区域中扫描了 10,948 个资源，发出了 2,053 次 API 调用：1,200 次 `s3:GetBucketLocation` 调用（每个存储桶一次）、600 次 `lambda:GetFunctionConfiguration` 调用（每个函数一次）、150 次 Resource Groups Tagging API 调用，以及 103 次其他调用。对真实账户有用的是调用次数。
- 默认同时扫描四个账户（`--max-concurrent-accounts`）。每个账户从开始扫描起有 1800 秒
  （`--account-processing-timeout`）。
- 一次运行最多有 64 个 AWS 请求在途（`--concurrency`），一个账户最多 16 个，同一个账户、同一个区域、同一个服务最多 4 个。收到限流回应后，InvenTag 会降低该服务和区域的上限。见[并发](../guides/run-a-scan.md#concurrency)。

  未针对真实的 AWS 验证：并行请求带来的任何提速，以及请求上限和限流回应之后的暂停在真实 AWS 速率限制下如何表现。
- 日志行的顺序和其中的时间戳在每次运行中可能不同。文件不依赖线程的时间。
- 当有些账户失败时，已完成账户的结果会被保存。在 24 小时内（`--resume-max-age-hours`）用 `--resume`
  运行同一条命令，只扫描其他账户。
- Excel 工作表名称会被截断为 31 个字符，Excel 不允许的字符会变成 `-`，重复的名称会加上 ` (2)`，日志会列出每个被改名的工作表。
- Word 表格默认每个服务最多显示 50 个资源（`max_rows`）。
- 当运行保存快照时，InvenTag 会删除 `bom_output/state/` 中超过 30 天或超出最新 100 个的快照。
  刚写入的快照和与之比较的快照永远不会被删除。用 `--state-retention-days` 和 `--state-max-snapshots`
  修改这些限制，或用 `none` 保留全部。
- 网络分析不会把 EFS 文件系统计为 VPC 或子网的关联资源：它的挂载目标需要 `elasticfilesystem:DescribeMountTargets`，而只读策略没有授予该权限。
- 服务属性补充（BOM 设置中的 `enable_service_enrichment`）不会运行；报告包含发现过程返回的字段。
- 在模板报告中，如果 AWS 没有为资源返回 `Name` 字段或 `Name` 标签，Name 列为空；ID 列用于识别该资源。
  对于 Lambda 函数、IAM 角色和 KMS 别名，模板报告会把 ID 显示为名称。

- 在 Intel Mac 上，`pip install inventag-aws` 会编译 cryptography 库，因为从版本 50 起，cryptography 不再为 Intel Mac 发布现成的构建。这需要 Rust 工具链。

  未针对 Intel Mac 验证：`pip install inventag-aws`。

## 安全说明 {#security-notes}

- **仍然使用只读 IAM 身份。** 防护会阻止写入调用，而你的 IAM（身份和访问管理）策略是第二道独立的安全网。
  参见[设置只读访问](../guides/read-only-access.md)。
- **调试日志默认经过脱敏：** 会话令牌、密钥、签名以及上面列出的机密值都会被遮盖。仍请把调试日志当作敏感信息。使用 `--debug` 或 `-vv` 时，AWS 在会被遮盖的字段名下以映射形式返回的机密，或以 XML 列表（`<member>` 项）形式返回的机密，可能出现在日志文件中。
- 少数 AWS 响应会在仅名为 `Url` 的字段中包含 URL；InvenTag 不调用这些操作，也不遮盖该字段名。
- **只读防护按名称识别操作。** 较新的 AWS SDK 新增的操作，只要名称以读取类前缀开头就会被允许，直到某个 InvenTag 发行版为它命名。见[安全](../security/index.md)。
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
