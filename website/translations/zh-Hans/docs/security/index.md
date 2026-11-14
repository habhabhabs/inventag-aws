---
title: 安全
description: 如何报告 InvenTag 的漏洞、应使用哪些 Python 版本、依赖项如何检查，以及发生供应链事件后该怎么做。
sidebar_position: 1
---

# 安全

**适合谁阅读：** 安全审查人员，以及针对生产账户运行 InvenTag 的任何人。

**读完后你会了解：** 如何报告问题、InvenTag 的依赖项如何检查，以及出现问题时如何限制损失。

## 报告漏洞 {#report-a-vulnerability}

请不要把漏洞利用的细节发布在公开的 issue 中。

本仓库目前还没有 `SECURITY.md` 文件，也没有设置 GitHub 的私密漏洞报告（2026 年 11 月检查）。
在设置之前，请开一个标题为“Security contact request”的
[issue](https://github.com/habhabhabs/inventag-aws/issues)，不要写任何技术细节，
并向维护者索取一个私密的联系渠道。

## InvenTag 如何处理你的账户 {#what-inventag-does-with-your-accounts}

- **它只读取，除了一次由你要求的上传。** 只读防护会在每个 AWS 调用发出之前检查它。唯一的例外是把它自己的报告文件上传到你的 S3 存储桶，而且仅在你传入 `--s3-bucket` 时才会这样做。它会拦截所有非读取的调用，
  以及会返回机密或数据的读取，例如 `secretsmanager:GetSecretValue`、`s3:GetObject`、
  `cloudformation:GetTemplate` 或 `ec2:GetLaunchTemplateData`。当参数要求返回机密时
  （带 `includeValue` 的 API 密钥、针对 `userData` 的 `ec2:DescribeInstanceAttribute`），
  它也会拦截原本允许的操作；它还会检查预签名 URL 和数据库认证令牌，这些在签名时不会调用 AWS。
  它还会拦截返回签名 URL、文件或文档正文、命令输出或含有机密的已存储定义的读取（例如 `ssm:GetDocument`、
  `ssm:GetCommandInvocation`、API Gateway 导出、Data Pipeline 定义，以及 Support 和 Connect 附件），
  以及会创建身份的 `cognito-identity:GetId`。拒绝列表中的每个条目都会与 AWS SDK 的操作列表进行核对。
  它始终开启。
- **登录仍然可用。** 防护允许 AWS SDK 把 IAM Identity Center（SSO）、Web 身份或 `aws login`
  令牌换成凭证。它只允许以下四个未签名的调用：`sso:GetRoleCredentials`、
  `sso-oidc:CreateToken`、`sts:AssumeRoleWithWebIdentity` 和 `signin:CreateOAuth2Token`。
  已签名的客户端发出同样的调用会被拦截。

  未针对 AWS IAM Identity Center 验证：真实 SDK 发出的登录调用。
- **它会遮盖允许的响应中的机密值。** 常用于存放机密的字段（例如 Lambda 环境变量、EC2 用户数据或
  CloudFormation 参数值）的值，在报告、快照和日志中会变成 `***REDACTED***`。名称会保留。
  参见[功能状态](../getting-started/status.md#what-inventag-finds-and-what-it-does-not)。
- **它不发送使用数据。** InvenTag 没有遥测。命令行工具只与 AWS 通信，使用 Google 选项时也会与 Google 通信。
  Python 库中可选的 CI 辅助功能可以向 Slack、Microsoft Teams 或 Prometheus Pushgateway 发送消息，
  但只会发送到你自己配置的地址。
- **它的文件是私有的。** 报告、快照和日志创建时只有你的用户可读。

  未针对 Windows 验证：文件只有你的用户可读。
- **它的日志会隐藏机密。** 会话令牌、密钥、请求签名以及上面提到的被遮盖的值都会被隐藏，即使使用 `--debug` 也是如此。

你可以用 `--audit-output audit.json` 检查一次运行做了什么，用 `--validate-operations`
检查防护允许什么：

```text title="输出"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
```

```bash title="Terminal"
echo $?
```

```text title="输出"
1
```

## 使用受支持的 Python 版本 {#use-a-supported-python-version}

请使用 Python 3.11 或更高版本。Python 3.10 及更早版本不再获得安全修复：
3.10 已于 2026 年 10 月终止支持
（[Python 版本状态](https://devguide.python.org/versions/)）。

## 依赖项如何检查 {#how-dependencies-are-checked}

| 内容 | 在当前 `main` 分支上的做法 |
|---|---|
| Python 依赖项 | 列在 `requirements.txt` 中，使用最低版本（`>=`），而不是精确固定。每个安全下限都会注明它所规避的安全公告。全新安装会得到最新的匹配版本。 |
| 开发工具 | 列在 `requirements-dev.txt` 中，测试和 lint 工具使用精确固定（`==`），它们的依赖项使用最低版本。 |
| 网站 | 锁定在 `website/package-lock.json` 中。 |
| CI 中的依赖项检查 | CI 工作流运行 `pip-audit -r requirements.txt`，发现问题就失败。它也运行 Bandit 和 `npm audit`，但它们的发现不会导致失败。 |
| 定时扫描 | 另一个工作流在推送到 `main` 和 `develop`、指向 `main` 的拉取请求以及每周（周日 02:00 UTC）时运行。它运行 Bandit、Safety、pip-audit、`npm audit` 和 detect-secrets。发现的问题会被报告，但不会让该工作流失败。 |
| 软件物料清单 | 文档构建会为 Python 和网站的依赖项生成 SBOM 文件。 |

未针对 GitHub Actions Runner 验证：CI、定时和文档工作流的行为；此表读自工作流文件。

要检查你自己的安装：

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

模板功能没有增加新的依赖项。它使用 PyYAML、openpyxl 和 python-docx，这些都是 InvenTag 本来就需要的。

## 出问题时减小影响 {#reduce-the-impact-if-something-goes-wrong}

InvenTag 会读取你的 AWS 账户，所以你给它的凭证比工具本身更重要。

- **只读，最小权限。** 只给 InvenTag 读取权限：[设置只读访问](../guides/read-only-access.md)。
- **短期凭证。** 使用 IAM Identity Center 或被代入的角色，而不是放在磁盘上或 CI 机密中的访问密钥。
  在 GitHub Actions 中使用 OIDC。
- **保持日志私有。** 日志中的机密会被遮蔽，但日志仍然会描述你的账户。
- **固定你运行的版本。** 检出 InvenTag 的发布标签，并把 GitHub Actions 固定到提交 SHA。

## 供应链事件之后 {#after-a-supply-chain-incident}

如果某个依赖项、某个 CI action，或者运行 InvenTag 的机器可能已被入侵：

1. **吊销并轮换** InvenTag 使用过的凭证：删除访问密钥，吊销活动的角色会话，并退出 SSO 会话。
2. **检查 AWS CloudTrail**，查看该身份发出的、InvenTag 不会发出的调用，
   尤其是任何不是 `List`、`Describe` 或 `Get` 的调用。
3. **检查 IAM 策略是否仍然只读**，并移除任何多余的权限。
4. **重建环境**，使用干净的虚拟环境：`pip install -r requirements.txt`，然后运行 `pip-audit`。
5. **把旧报告视为敏感信息。** 它们列出了你的资源和标签。

## 模板是数据，不是代码 {#templates-are-data-not-code}

模板用安全的 YAML 加载器读取，不能运行代码或获取 URL，只能引用它们自己文件夹内的文件，
也不能包含访问密钥。详情：[模板](../templates/index.md#safe-by-design)。
