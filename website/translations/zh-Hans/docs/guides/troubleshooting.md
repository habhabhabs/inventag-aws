---
title: 解决常见问题
description: 人们最常遇到的 InvenTag 错误（凭证、权限、区域、限流、模板和配置文件），附真实消息和解决办法。
sidebar_position: 8
---

# 解决常见问题

**适合谁阅读：** 出了问题，你想要最快的解决办法。

**读完后你可以：** 认出你看到的消息，并修复其原因。

下面的消息是 InvenTag 离线运行的真实输出（示例数据）。
对于离线无法产生的 AWS 错误，例如令牌过期，我们模拟了确切的 AWS 错误响应，并记录了 InvenTag 如何报告它。
这些代码块标注为“simulated AWS error response”。

加上 `--verbose` 可以看到每一步，加上 `--debug` 可以看到每个 AWS 调用。调试日志会遮蔽密钥，但仍应把它当作敏感信息对待。

## 凭证 {#credentials}

### 找不到凭证 {#no-credentials-found}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ No AWS credentials found!
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Set AWS environment variables:
inventag.cli.main - ERROR -       export AWS_ACCESS_KEY_ID=your-key
inventag.cli.main - ERROR -       export AWS_SECRET_ACCESS_KEY=your-secret
inventag.cli.main - ERROR -    3. Use IAM roles if running on EC2/ECS/Lambda
inventag.cli.main - ERROR -    4. Use --accounts-prompt for interactive setup
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**解决办法：** 登录，例如运行 `aws sso login --profile my-readonly` 和
`export AWS_PROFILE=my-readonly`，然后用 `aws sts get-caller-identity` 检查。

### 凭证已过期或无效 {#expired-or-invalid-credentials}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ AWS credential validation failed!
inventag.cli.main - ERROR -    Issue: Invalid or expired security token
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Check if your access keys are correct
inventag.cli.main - ERROR -    3. If using temporary credentials, they may have expired
inventag.cli.main - ERROR -    4. If using AWS SSO, run 'aws sso login'
inventag.cli.main - ERROR -
inventag.cli.main - ERROR - 💡 Quick diagnostic commands:
inventag.cli.main - ERROR -    aws configure list          # Show current config
inventag.cli.main - ERROR -    aws sts get-caller-identity # Test credentials
inventag.cli.main - ERROR -    aws configure               # Set up new credentials
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**解决办法：** 重新登录（`aws sso login --profile <name>`），或刷新你的临时密钥。
如果你使用访问密钥，请用 `aws configure list` 检查它们。

### 无法代入角色 {#a-role-cannot-be-assumed}

**你会看到：** 日志中出现如下内容，并且报告中缺少该账户：

```text
inventag.core.cloud_bom_generator.CloudBOMGenerator - ERROR - Failed to establish context for account 999999999999: Role assumption failed for account 999999999999: An error occurred (AccessDenied) when calling the AssumeRole operation: ...
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Skipping account 999999999999 due to invalid session
```

如果其他账户正常，InvenTag 仍会写出它们的报告，并以**退出码 0** 结束；如果你传入了 `--fail-on-account-error`，则以退出码 5 结束。`Summary` 工作表和 Word 报告中有“运行备注”（Run notes）部分，会写出该账户的名称，日志末尾则有下面这份列表：

```text
1 of 2 account(s) finished and were saved. Run the same command with --resume within 24 hours to scan only the other 1.
1 account(s) were not scanned, or only partly. The report does not include them:
  - 222222222222 (Dev): Context establishment failed: Role assumption failed for account 222222222222: ...
```

如果每个账户都失败，InvenTag 以退出码 1 结束，并且不写报告：`Resource discovery failed for all 1 configured account(s); no report was generated`。（消息文本来自带有模拟 AWS 错误的离线运行。）

**解决办法：** 检查角色 ARN，并检查该角色的信任策略是否允许你的身份。
InvenTag 不会回退到其他凭证，因此在问题解决之前，该账户会被跳过。然后用 `--resume` 运行同一条命令，只扫描缺少的账户。

### 给了角色名称但没有账户文件 {#a-role-name-without-an-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
$ echo $?
2
```

**解决办法：** 传入完整的角色 ARN，或加上带有账户 ID 的 `--accounts-file`。

## 权限 {#permissions}

### Cost Explorer 访问被拒绝 {#cost-explorer-access-denied}

InvenTag 会在没有账单数据的情况下继续，运行也会成功，所以这个问题很容易被忽略。它只会在使用 `--debug` 时显示：

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0

$ # the same run with --debug, lines that mention AccessDeniedException
[AWS Account 123456789012 (moto)] inventag.discovery.inventory - WARNING - No permission for the Cost Explorer API (AccessDeniedException). Skipping billing validation; add ce:GetCostAndUsage or use --no-billing-validation.
[AWS Account 123456789012 (moto)] inventag.discovery.comprehensive_discovery - WARNING - Cost Explorer data is not available, so billing checks are skipped: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

**解决办法：** 把 `ce:GetCostAndUsage` 添加到策略中，或者接受缺少账单数据。

### 某个服务或某一列为空 {#a-service-or-column-is-empty}

**原因：** 该身份缺少该服务的某个 `List*`、`Describe*` 或 `Get*` 权限。对于列表调用，InvenTag 会为该服务记录一条警告，并在没有其资源的情况下继续：

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

对于只补充资源某个细节的调用，发现过程会在没有消息的情况下继续，并让该细节留空。AWS 错误只在调试级别记录。请用同一个身份运行对应的 AWS CLI 调用来检查。

**解决办法：** 使用 `config/defaults/iam-policy-read-only.json` 中的策略，它涵盖了 InvenTag 发出的每个调用。
见 [IAM 权限](../reference/iam-permissions.md)。

### 被只读防护阻止 {#blocked-by-the-read-only-guard}

**你会看到：** 日志中有 `Read-only guard blocked <service>:<Operation>`，
以及以 `Blocked AWS operation <service>:<Operation>` 开头的错误。

**原因：** 一个不是读取的调用，或者会返回密钥或客户数据的读取（例如 `cloudformation:GetTemplate` 或 `ssm:GetParameter`），到达了防护。InvenTag 自己不会发出这样的调用，因此这通常意味着自定义代码或插件。见[只读防护会阻止什么](./read-only-access.md#what-the-read-only-guard-blocks)。

**解决办法：** 用 `inventag --validate-operations <service>:<Operation>` 检查是哪个操作。防护无法关闭。

## 区域 {#regions}

### 区域未对该账户启用 {#a-region-is-not-enabled-for-the-account}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0
```

运行会使用可用的区域继续。

**解决办法：** 从 `--account-regions` 中删除该区域，或在 AWS 控制台中为该账户启用它（Account settings，AWS Regions）。

### 无法读取区域列表 {#the-list-of-regions-cannot-be-read}

如果 `ec2:DescribeRegions` 失败，InvenTag 会改用 `account:ListRegions`，再不行就尝试该分区的每个区域：

```text
ec2:DescribeRegions failed (An error occurred (UnauthorizedOperation) when calling the DescribeRegions operation: ...); trying account:ListRegions instead.
account:ListRegions failed (An error occurred (AccessDeniedException) when calling the ListRegions operation: ...).
Could not read the account's enabled regions. Trying all 34 regions of the aws partition known to botocore; regions the account has not enabled will fail the access check and be skipped. Use --account-regions to choose.
```

每个区域的访问检查也使用 `ec2:DescribeRegions`。如果它在每个区域都被拒绝，InvenTag 就无法判断哪些区域可用：

```text
ec2:DescribeRegions is denied in every region, so region access cannot be checked; scanning all 34 regions.
```

**解决办法：** 允许 `ec2:DescribeRegions`，或用 `--account-regions` 指定区域。

## 限流 {#throttling}

当同时到达的请求太多时，AWS 会放慢它们。AWS SDK（软件开发工具包）会自动重试，最多共 10 次。如果列表调用在那之后仍然失败，InvenTag 会为该服务和区域记录一条警告，该区域的资源可能不在报告中：

```text
sqs list_queues in us-east-1 failed (ThrottlingException); its resources there may be incomplete.
```

**解决办法：** 减少同时扫描的账户数（`--max-concurrent-accounts 2`），扫描更少的区域，
或给大型账户更多时间（`--account-processing-timeout 3600`）。

## 时间限制和部分结果 {#time-limits-and-partial-results}

### 账户用完了时间 {#an-account-runs-out-of-time}

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

该账户算作失败，但在限制之前找到的资源会进入报告，并且“运行备注”会写出该账户。其他账户会保留。如果没有任何账户完成，InvenTag 仍会写出报告，记录 `No account finished within its time limit (--account-processing-timeout)`，并以退出码 1 结束。（消息文本来自 60 秒限制的离线运行。）

**解决办法：** 提高 `--account-processing-timeout`（默认 1800），扫描更少的区域或服务，或减少同时扫描的账户数。用 `--resume` 运行同一条命令，只扫描没有完成的账户。

### 已保存的结果没有被重用 {#saved-results-are-not-reused}

| 消息 | 含义 |
|---|---|
| `1 account(s) have saved results from an earlier run of this command that did not finish. They are scanned again; add --resume to reuse them.` | 已保存的结果存在，但你没有传入 `--resume`。 |
| `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)` | 已保存的结果被重用。报告的备注会列出该账户和扫描时间。 |
| `inventag: error: --resume: needs state management ...` | 状态管理已关闭。`--resume` 与 `--disable-state-management` 一起使用时，以退出码 2 停止。 |

只有在命令的账户、区域、服务和筛选条件都相同，并且结果的年龄不超过 `--resume-max-age-hours`（默认 24，最大 168）时，InvenTag 才会重用已保存的结果。否则它会重新扫描该账户。

## 模板和配置文件 {#templates-and-configuration-files}

### 无效的模板 {#invalid-template}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
$ echo $?
1
```

**解决办法：** 更正所示行上的字段。运行 `inventag templates validate <file>` 可以在不扫描的情况下检查。

### 未知的模板名称 {#unknown-template-name}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
$ echo $?
1
```

**解决办法：** 用 `inventag templates list` 检查拼写。项目模板必须位于你运行命令的文件夹下的 `.inventag/templates/` 中。

### 无效的账户文件 {#invalid-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

**解决办法：** 给账户 ID 加上引号（`account_id: "123456789012"`），并给每个账户提供 `profile_name`、`role_arn` 或访问密钥。

文件本身也可能有问题。下面每一种都会以退出码 1 停止：

| 消息包含 | 原因 |
|---|---|
| `the file is empty` | 文件没有内容。 |
| `duplicate key 'accounts'` | 同一个键写了两次。消息会给出行号，例如 `accounts file accounts.yaml:3: duplicate key 'accounts'`。 |
| `the top level must be a mapping of key: value pairs, but the file holds a list` | 文件以列表开头。请把列表放在 `accounts:` 下面。 |
| `unsupported file type '.txt'. Use .json, .yaml or .yml` | 文件名使用了其他扩展名。 |
| `the file is ... bytes; the maximum is 1048576 bytes` | 文件超过 1 MiB。 |
| `Accounts file not found` | 路径不对。 |

如果带有 `secret_access_key` 或 `session_token` 的文件可以被其他用户读取，InvenTag 会发出警告：`<file> contains secret access keys and other users can read it (mode 0644). Run: chmod 600 <file>.`

### 其他模板消息 {#other-template-messages}

| 消息包含 | 解决办法 |
|---|---|
| `did you mean '...'?` | 更正所示行上的拼写。 |
| `Put account IDs in quotes` | 写成 `account_id: "012345678901"`。 |
| `must stay inside the template's folder` | 把被引用的文件移到模板旁边，或移到子文件夹中。 |
| `templates must not contain credentials` | 删除访问密钥；改用 `profile_name` 或 `role_arn`。 |
| `--template given two report templates` | 每种类型最多只给一个模板。 |

## 会让运行停止的参数 {#flags-that-stop-the-run}

有些选项会在扫描任何内容之前，以退出码 2 和 `inventag: error: ...` 消息停止运行：

- `--compliance-standard` 的消息是尚未实现。
- `--disable-production-safety` 的消息是只读保护无法关闭。
- 不能一起使用的选项：

```text
inventag: error: --accounts-file and --accounts-prompt: give one of them, not both.
inventag: error: --cross-account-role: a full role ARN names one account and cannot be combined with --accounts-file or --accounts-prompt. Give a role name to use in every account, or put role_arn in the accounts file.
inventag: error: --s3-kms-key-id: needs --s3-encryption aws:kms.
inventag: error: --resume: needs state management (saved results live in the state folder); remove --disable-state-management.
```

超出范围的值会以退出码 1 停止，并写出选项名称：`--max-concurrent-accounts must be a positive integer`、`--account-processing-timeout must be at least 60 seconds`、`--resume-max-age-hours must be above 0 and at most 168`。`--state-retention-days` 或 `--state-max-snapshots` 的值如果不是数字，则以退出码 2 停止：`expected a whole number or 'none'`。

见[功能状态](../getting-started/status.md)。

## 退出码 3 {#exit-code-3}

这不是 InvenTag 的错误。标签策略发现了违规，并且配置模板设置了 `fail_on_tag_violations: true`。
打开 Tag Compliance 工作表或 JSON 文件，查看是哪些资源。

## 退出码 4、5 和 6 {#exit-codes-4-5-and-6}

只有在你要求时才会出现这些退出码。

- **4：** 向互联网开放的安全组规则达到或超过 `--risk-threshold`。日志会列出这些规则。见[网络与安全分析](./network-and-security-analysis.md#fail-a-pipeline-on-risky-rules)。
- **5：** 设置了 `--fail-on-account-error`，并且有账户无法扫描，或只扫描了一部分。日志会写出 `N account(s) failed and --fail-on-account-error is set (exit code 5)`。
- **6：** 设置了 `--fail-if-empty`，并且没有任何内容可报告。日志会写出 `No resources in the report and --fail-if-empty is set (exit code 6)`。

报告会先写出。如果同时满足多个条件，先是 5，然后是 6，然后是 3 和 4。见[在 CI/CD 中运行 InvenTag](./run-in-ci.md#exit-codes)。

## 报告看起来不对 {#reports-look-wrong}

| 你看到的情况 | 原因和解决办法 |
|---|---|
| 工作表很宽，带有 `raw_data.*` 列 | 这是默认版式。请使用 `--template standard-bom`。 |
| 缺少标签映射列 | 标签映射只会向默认工作簿添加列。使用 `--template` 时，请用 `tag_columns`。见[配置文件](../reference/configuration-files.md#tag-mappings)。 |
| 自定义服务描述被忽略 | S3、EC2、RDS、Lambda 和 VPC 有内置描述，除非你的条目指定了 `template`，否则内置描述优先。见[配置文件](../reference/configuration-files.md#service-descriptions)。 |
| 没有网络或安全工作表 | 添加 `--enable-network-analysis` 或 `--enable-security-analysis`，并确认扫描找到了 VPC 或安全组。与 `--template` 一起使用时，这些参数不添加任何内容。见[网络与安全分析](./network-and-security-analysis.md)。 |
| 缺少 IAM、S3、CloudFront 或 Route 53 资源 | 它们被 `--account-services` 或 `--account-tags` 筛掉了，或者该身份缺少权限（在日志中查找每个服务一条的警告）。区域列表无关紧要：全局服务始终从主区域读取（`us-east-1`；中国区为 `cn-north-1`，GovCloud 为 `us-gov-west-1`）。 |
| 某个资源没有显示标签，或出现了两次 | 用 `--debug` 运行，并把 ARN 列与 AWS 控制台中的 ARN 对比。如果不一致，请作为 issue 报告，并附上服务和资源类型。 |
| 没有报告文件，且退出码为 0 | 扫描没有找到任何内容，或者 `--account-services` 或 `--account-tags` 把所有内容都筛掉了。在日志中查找 `No resources to report`。使用 `--template` 时，InvenTag 会写出一份不列出任何资源的报告。 |
| 报告中缺少某个账户 | 它的凭证或角色失败了，或者它用完了时间。`Summary` 工作表上的“运行备注”会写出该账户。见[无法代入角色](#a-role-cannot-be-assumed)和[账户用完了时间](#an-account-runs-out-of-time)。 |
| 缺少变更报告 | 第一次运行不会写出变更报告。它还要求状态管理和差异检测处于开启状态。见[跟踪两次运行之间的变更](./track-changes.md)。 |
| `Skipped unreadable snapshot 20261113_222847: Snapshot ... is corrupt or truncated (...). The file was not changed or deleted` | 最新的快照已损坏，所以 InvenTag 改与它之前的快照比较。该文件仍留在 `state/` 中。如果不需要它，请删除。 |
| `Account 222222222222 left out of the comparison: the previous run could not scan it` | 两次运行中有一次无法扫描该账户。变更报告会在 `accounts_not_compared` 下写出它。 |
| `Excel sheet name 'x' is not allowed or is already used; the sheet is called 'y'` | Excel 不允许工作表名称使用某些字符（它们会变成 `-`），名称必须唯一，且最多 31 个字符。报告仍然完整。 |
| 其他用户无法打开 `bom_output/` | 输出文件只对运行 InvenTag 的用户私有。请有意识地共享它们。 |

## 可以忽略的噪音 {#noise-you-can-ignore}

有些消息看起来像错误，但不会改变你的报告。

| 消息 | 为什么可以忽略 |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'``（使用 `--service-descriptions` 时） | VPC 描述模板需要一个该资源没有的字段。报告不受影响。 |
| `No account specification method provided. Using default AWS credentials.` | 你没有指定账户，所以 InvenTag 使用了你当前的凭证。这是正常情况。 |
| `Cross-account role not usable for account ... trying default credentials` | InvenTag 尝试了默认的角色名称，无法代入它，于是用你自己的凭证继续。每个账户只记录一次，并且只在使用 `--verbose` 时。 |

## 安装问题 {#install-problems}

见[安装 InvenTag](../getting-started/installation.md#fix-install-problems)。

## 还是解决不了？ {#still-stuck}

请提交一个 [issue](https://github.com/habhabhabs/inventag-aws/issues)，附上你运行的命令、版本（`inventag --version`）和消息。
请删除你不想分享的账户 ID 和名称。切勿粘贴凭证。
