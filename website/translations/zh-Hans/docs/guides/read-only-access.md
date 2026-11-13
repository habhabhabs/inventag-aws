---
title: 设置只读访问
description: 用 IAM Identity Center 或 IAM 角色，为 InvenTag 提供最小权限的只读 AWS 身份，并确认它无法更改任何内容。
sidebar_position: 2
slug: /user-guides/production-safety
---

# 设置只读访问

**适合谁阅读：** 负责创建 InvenTag 所用 AWS 身份的人。

**读完后你可以：** 为 InvenTag 创建只读身份，并确认它无法更改你的资源。

## 为什么这很重要 {#why-this-matters}

InvenTag 只需要读取。它有自己的只读防护，会在发送前拦截所有非读取的 AWS 调用。
你的 IAM 策略是第二道独立的安全网：即使某个缺陷绕过了防护，AWS 仍会拒绝该调用。
只给 InvenTag 它所需要的权限，不要更多。

## 方案 1：AWS 托管的 ReadOnlyAccess 加三项额外权限（最简单） {#option-1-aws-managed-readonlyaccess-plus-three-extras-simplest}

1. 附加 AWS 托管策略 `ReadOnlyAccess`。
2. 为 `ReadOnlyAccess` 可能没有覆盖的调用，添加下面这条内联策略：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvenTagExtras",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "ce:GetCostAndUsage",
        "ec2:DescribeRegions"
      ],
      "Resource": "*"
    }
  ]
}
```

| 操作 | InvenTag 为什么需要它 |
|---|---|
| `tag:GetResources` | 通过 Resource Groups Tagging API 查找带标签的资源（它的 IAM 前缀是 `tag`）。 |
| `ce:GetCostAndUsage` | 查找有支出的服务。AWS 按请求收费。 |
| `ec2:DescribeRegions` | 列出账户中已启用的区域。 |

只有在使用 `--enable-cost-analysis` 时才需要添加 `pricing:GetProducts`（它还会调用
`cloudwatch:GetMetricStatistics`，`ReadOnlyAccess` 已覆盖该调用）；
如果使用 `--s3-bucket`，则需要在报告存储桶上添加 `s3:PutObject`。

`ReadOnlyAccess` 范围很宽：它可以读取 S3 对象列表等数据，以及 InvenTag 从不查看的某些配置。
如果这对你的组织来说太宽，请使用方案 2。

## 方案 2：仓库中范围更窄的策略 {#option-2-the-narrower-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` 列出了 106 个具体的读取操作，
包括 `tag:GetResources`、`ce:GetCostAndUsage` 和 `pricing:GetProducts`。
它由代码所用的同一份清单生成，因此与 InvenTag 实际发出的调用一致。

其中的 `OptionalS3ReportUpload` 语句允许带服务端加密的 `s3:PutObject`，用于 `--s3-bucket`。
请把 `YOUR-REPORTS-BUCKET-NAME` 替换为你的存储桶；如果不上传报告，就删除这条语句。

如果缺少某个操作，发现过程会继续进行，不打印任何消息，并把相应的细节留空。

## 使用 IAM Identity Center（SSO） {#with-iam-identity-center-sso}

创建一个包含该策略的权限集，然后把它分配给你想扫描的每个账户：

```bash
aws sso-admin create-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --name InvenTagReadOnly \
  --description "Read-only access for InvenTag"

aws sso-admin attach-managed-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

aws sso-admin put-inline-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --inline-policy file://inventag-extras.json
```

然后用 `aws sso login --profile <profile>` 登录，并以 `AWS_PROFILE=<profile>` 运行 InvenTag。

## 在每个账户中使用 IAM 角色 {#with-an-iam-role-in-each-account}

对于跨多个账户的扫描，请在每个账户中创建同名的角色，例如 `InvenTagReadOnly`。
附加该策略，并且只允许你的扫描身份来代入它。对应的信任策略如下：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::999999999999:role/InvenTagScanner" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

请把 `999999999999:role/InvenTagScanner` 替换为运行 InvenTag 的身份。
扫描身份本身只需要对这些角色拥有 `sts:AssumeRole` 权限。

## 确认它无法写入 {#check-that-it-cannot-write}

用 IAM 策略模拟器确认写入操作会被拒绝：

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

两者都应显示 `implicitDeny` 或 `explicitDeny`。

你也可以问 InvenTag 的防护，它会允许哪些操作（来自离线运行的示例输出）：

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

要查看一次真实运行调用了什么，请添加 `--audit-output audit.json`。
下面是一次离线运行的节选（示例数据）：

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 73,
  "allowed_calls": 73,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "ce",
      "operation": "GetCostAndUsage",
      "allowed": true,
      "count": 2
    },
    {
      "service": "cloudformation",
      "operation": "DescribeStacks",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudformation",
      "operation": "ListStackSets",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudfront",
      "operation": "ListDistributions",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## 安全事件之后 {#after-a-security-incident}

如果你怀疑凭证或某个依赖项已被入侵，请轮换或吊销 InvenTag 使用过的凭证，
在 AWS CloudTrail 中检查该身份发出的、你意料之外的调用，并保持该身份为只读。
更多内容见[安全](../security/index.md)页面。

## 下一步 {#next-steps}

- [IAM 权限参考](../reference/iam-permissions.md)
- [扫描多个账户](./scan-multiple-accounts.md)
