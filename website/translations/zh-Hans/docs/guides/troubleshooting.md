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

如果其他账户正常，InvenTag 仍会写出它们的报告，并以**退出码 0** 结束。
如果每个账户都失败，则以退出码 1 结束。（消息文本来自带有模拟 AWS 错误的离线运行。）

**解决办法：** 检查角色 ARN，并检查该角色的信任策略是否允许你的身份。
InvenTag 不会回退到其他凭证，因此在问题解决之前，该账户会被跳过。

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
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0

$ # the same run with --debug, lines that mention AccessDeniedException
Cost Explorer data is not available, so billing checks are skipped: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

**解决办法：** 把 `ce:GetCostAndUsage` 添加到策略中，或者接受缺少账单数据。

### 某个服务或某一列为空 {#a-service-or-column-is-empty}

**原因：** 该身份缺少该服务的某个 `List*`、`Describe*` 或 `Get*` 权限。
发现过程会在没有它的情况下继续，并且不打印任何消息。AWS 错误只在调试级别记录，在很长的输出中很难找到。
请用同一个身份运行对应的 AWS CLI 调用来检查。

**解决办法：** 使用 `config/defaults/iam-policy-read-only.json` 中的策略，它涵盖了 InvenTag 发出的每个调用。
见 [IAM 权限](../reference/iam-permissions.md)。

### 被只读防护阻止 {#blocked-by-the-read-only-guard}

**你会看到：** 日志中有 `Read-only guard blocked <service>:<Operation>`，
以及以 `Blocked AWS operation <service>:<Operation>` 开头的错误。

**原因：** 一个不是读取的调用到达了防护。InvenTag 自己不会发出这样的调用，因此这通常意味着自定义代码或插件。

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

## 限流 {#throttling}

当同时到达的请求太多时，AWS 会放慢它们。AWS SDK（软件开发工具包）会自动重试。
对于重试之后仍然持续的限流，InvenTag 会如何报告，我们还没有测试过。

**解决办法：** 减少同时扫描的账户数（`--max-concurrent-accounts 2`），扫描更少的区域，
或给大型账户更多时间（`--account-processing-timeout 3600`）。

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

### 其他模板消息 {#other-template-messages}

| 消息包含 | 解决办法 |
|---|---|
| `did you mean '...'?` | 更正所示行上的拼写。 |
| `Put account IDs in quotes` | 写成 `account_id: "012345678901"`。 |
| `must stay inside the template's folder` | 把被引用的文件移到模板旁边，或移到子文件夹中。 |
| `templates must not contain credentials` | 删除访问密钥；改用 `profile_name` 或 `role_arn`。 |
| `--template given two report templates` | 每种类型最多只给一个模板。 |

## 会让运行停止的参数 {#flags-that-stop-the-run}

有两个参数会被接受，但会让运行以退出码 2 停止，并输出以参数名开头的消息。`--compliance-standard` 的消息是尚未实现；`--disable-production-safety` 的消息是只读保护无法关闭。见[功能状态与已知限制](../getting-started/status.md)。

## 退出码 3 {#exit-code-3}

这不是 InvenTag 的错误。标签策略发现了违规，并且配置模板设置了 `fail_on_tag_violations: true`。
打开 Tag Compliance 工作表或 JSON 文件，查看是哪些资源。

## 报告看起来不对 {#reports-look-wrong}

| 你看到的情况 | 原因和解决办法 |
|---|---|
| 工作表很宽，带有 `raw_data.*` 列 | 这是默认版式。请使用 `--template standard-bom`。 |
| 缺少标签映射列 | 标签映射只会向默认工作簿添加列。使用 `--template` 时，请用 `tag_columns`。见[配置文件](../reference/configuration-files.md#tag-mappings)。 |
| 自定义服务描述被忽略 | S3、EC2、RDS、Lambda 和 VPC 有内置描述，除非你的条目指定了 `template`，否则内置描述优先。见[配置文件](../reference/configuration-files.md#service-descriptions)。 |
| 没有网络或安全工作表 | 添加 `--enable-network-analysis` 或 `--enable-security-analysis`，并确认扫描找到了 VPC 或安全组。与 `--template` 一起使用时，这些参数不添加任何内容。见[网络与安全分析](./network-and-security-analysis.md)。 |
| 缺少 IAM、S3、CloudFront 或 Route 53 资源 | 它们被 `--account-services` 或 `--account-tags` 筛掉了，或者该身份缺少权限（在日志中查找每个服务一条的警告）。区域列表无关紧要：全局服务始终从 `us-east-1` 读取。 |
| 某个资源没有显示标签，或出现了两次 | 用 `--debug` 运行，并把 ARN 列与 AWS 控制台中的 ARN 对比。如果不一致，请作为 issue 报告，并附上服务和资源类型。 |
| 没有报告文件，且退出码为 0 | 扫描没有找到任何内容，或者 `--account-services` 或 `--account-tags` 把所有内容都筛掉了。在日志中查找 `No resources to report`。 |
| 报告中缺少某个账户 | 它的凭证或角色失败了。见[无法代入角色](#a-role-cannot-be-assumed)。 |
| 缺少变更报告 | 第一次运行不会写出变更报告。它还要求状态管理和差异检测处于开启状态。见[跟踪两次运行之间的变更](./track-changes.md)。 |
| 其他用户无法打开 `bom_output/` | 输出文件只对运行 InvenTag 的用户私有。请有意识地共享它们。 |

## 可以忽略的噪音 {#noise-you-can-ignore}

有些消息看起来像错误，但不会改变你的报告。

| 消息 | 为什么可以忽略 |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'``（使用 `--service-descriptions` 时） | VPC 描述模板需要一个该资源没有的字段。报告不受影响。 |
| `No account specification method provided. Using default AWS credentials.` | 你没有指定账户，所以 InvenTag 使用了你当前的凭证。这是正常情况。 |
| `Cross-account role ... not usable ... trying default credentials` | InvenTag 尝试了默认的角色名称，无法代入它，于是用你自己的凭证继续。每个账户只记录一次。 |

## 安装问题 {#install-problems}

见[安装 InvenTag](../getting-started/installation.md#fix-install-problems)。

## 还是解决不了？ {#still-stuck}

请提交一个 [issue](https://github.com/habhabhabs/inventag-aws/issues)，附上你运行的命令、版本（`python -m pip show inventag-aws`；如果是克隆的仓库，则用 `git describe --tags`）和消息。
请删除你不想分享的账户 ID 和名称。切勿粘贴凭证。
