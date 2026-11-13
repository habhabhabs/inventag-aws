---
title: 选择要扫描什么、生成什么
description: 为一次 InvenTag 运行选择账户、区域和输出文件，保存日志，并选择报告的写入位置。
sidebar_position: 1
slug: /user-guides/cli-user-guide
---

# 选择要扫描什么、生成什么

**适合谁阅读：** 你已经运行过一次 InvenTag，想控制它扫描什么、写出什么。

**读完后你可以：** 为一次运行选择账户、区域、输出文件和日志。
所有参数请参阅 [CLI 参考](../reference/cli.md)。

`inventag` 命令在 Linux、macOS 和 Windows 上的用法相同。

## 选择账户 {#choose-the-accounts}

| 你想扫描…… | 使用 |
|---|---|
| 当前凭证所属的账户 | 不需要额外参数 |
| 通过角色访问的另一个账户 | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly`（完整的角色 ARN） |
| 多个账户 | `--accounts-file accounts.yaml` 或配置模板：[扫描多个账户](./scan-multiple-accounts.md) |
| 多个账户，每个账户中的角色同名 | `--accounts-file accounts.yaml --cross-account-role InvenTagReadOnly` |
| 在被询问时由你输入的账户 | `--accounts-prompt` |

## 选择区域 {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

不使用 `--account-regions` 时，InvenTag 会向 EC2 询问账户中启用了哪些区域，并扫描全部区域。
这样很全面，但速度较慢。如果这次查询失败，InvenTag 会记录一条警告，只扫描 `us-east-1`、
`us-west-2`、`eu-west-1` 和 `ap-southeast-1`。

访问检查失败的区域会被跳过，并给出警告。

### 全局服务 {#global-services}

你不需要把 `us-east-1` 加入列表。无论你选择哪些区域，InvenTag 都会针对每个账户，
从 `us-east-1` 读取一次全局服务：IAM、S3 存储桶列表、CloudFront、Route 53，
以及 CloudFront 使用的 ACM 证书。如果 `us-east-1` 已在你的列表中，它们不会被重复读取。

- `--account-services` 和 `--account-tags` 对它们的作用与对其他资源相同。
  使用 `--account-services ec2` 时，不会读取任何 IAM 资源。
- IAM、CloudFront 和 Route 53 资源在区域列中显示 `global`。
  S3 存储桶显示它自己所在的区域，例如 `eu-west-1`。
- 它们的标签来自 `us-east-1` 的 Resource Groups Tagging API，AWS 在那里保存全局资源的标签。
- 离线测试覆盖了仅 `eu-west-1`、所有区域，以及包含 `us-east-1` 的列表。
  真实 AWS 会如何响应，没有测试过。

## 选择输出文件 {#choose-the-output-files}

| 参数 | 写出 |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | 同样的文件，由[报告模板](../templates/index.md)决定版式 |
| `--output-directory reports` | 把所有内容写入 `reports/`，而不是 `bom_output/` |

如果不指定输出参数，InvenTag 只写出 Excel。如果扫描没有发现任何资源，或者你的过滤条件把它们全部排除了，
InvenTag 不会写出任何文件，并且仍以退出码 0 退出。添加 `--s3-bucket` 还可以上传这些文件：
参见[定时把报告上传到 S3](../examples/scheduled-s3-upload.md)。

使用 `--template standard-bom --create-excel
--create-word --account-regions us-east-1` 运行时的示例输出（离线，示例数据）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

## 把多项设置合并到一个文件中 {#combine-several-settings-in-one-file}

如果你总是使用相同的设置运行，请把它们放进[配置模板](../templates/catalogue.md#config-templates)，
而不是每次都输入：

```bash
inventag templates init single-account --output .inventag/templates/my-scan.yaml
# edit regions and outputs, then:
inventag --template my-scan
```

你输入的参数仍然优先于模板。

## 查看运行情况 {#see-what-is-happening}

| 参数 | 显示 |
|---|---|
| （无） | 警告、错误，以及文件写到了哪里。单个调用的 AWS 权限错误不会显示。 |
| `--verbose` 或 `-v` | 运行的每一步 |
| `--log-file run.log` | 同时把详细日志写入文件 |
| `--debug` 或 `-d` | 每一个 AWS 请求。机密会被遮蔽，但仍应把日志视为敏感信息。 |
| `--audit-output audit.json` | 一份 JSON 列表，列出本次运行调用过的每个 AWS 操作 |

## 不扫描，只验证配置文件 {#validate-configuration-files-without-scanning}

```bash title="Terminal"
inventag --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
inventag templates validate my-scan
```

退出码 0 表示文件有效。第一条命令仍会发出一次 `ec2:DescribeRegions` 调用来列出区域；
如果它失败，会记录一条警告并继续。损坏的账户文件如下所示（示例数据）：

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

## 下一步 {#next-steps}

- [扫描多个账户](./scan-multiple-accounts.md)
- [按策略检查标签](./check-tag-compliance.md)
- [CLI 参考](../reference/cli.md)
