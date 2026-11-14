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

`--accounts-file` 和 `--accounts-prompt` 只能给一个，不能同时给。`--cross-account-role` 中的完整角色 ARN 只指向一个账户，所以不能与它们同用。这两种错误都会让运行以退出码 2 停止。

## 选择区域 {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

不使用 `--account-regions` 时，InvenTag 会向 EC2 询问账户中启用了哪些区域，并扫描全部区域。
这样很全面，但速度较慢。如果 `ec2:DescribeRegions` 失败，InvenTag 会改问 `account:ListRegions`。
如果它也失败，InvenTag 会记录一条警告，并尝试你的 AWS SDK 所知的该分区的每个区域。
账户未启用的区域会通不过访问检查而被跳过。可以用 `--account-regions` 自己选择区域。

访问检查失败的区域会被跳过，并给出警告。如果检查在每个区域都失败（因为该身份缺少 `ec2:DescribeRegions`），
InvenTag 无法判断哪些区域可用，会扫描全部区域。

### 全局服务 {#global-services}

你不需要把主区域加入列表。无论你选择哪些区域，InvenTag 都会针对每个账户，
从该分区的主区域读取一次全局服务：标准分区是 `us-east-1`，中国是 `cn-north-1`，GovCloud 是 `us-gov-west-1`。
这些服务是 IAM、S3 存储桶列表、CloudFront、Route 53，以及 CloudFront 使用的 ACM 证书。
如果主区域已在你的列表中，它们不会被重复读取。

- `--account-services` 和 `--account-tags` 对它们的作用与对其他资源相同。
  使用 `--account-services ec2` 时，不会读取任何 IAM 资源。
- IAM、CloudFront 和 Route 53 资源在区域列中显示 `global`。
  S3 存储桶显示它自己所在的区域，例如 `eu-west-1`。
- 它们的标签来自主区域的 Resource Groups Tagging API，AWS 在那里保存全局资源的标签。
- 离线测试覆盖了仅 `eu-west-1`、所有区域，以及包含 `us-east-1` 的列表。
  真实 AWS 会如何响应，没有测试过。

### 服务 {#services}

InvenTag 为 46 个 AWS 服务提供了自己的只读列举调用。其他服务的资源只有在 Resource Groups Tagging API 返回它们时才会出现。
见[功能状态](../getting-started/status.md)。

### 限流与失败的调用 {#throttling-and-failed-calls}

对于被限流的调用，InvenTag 总共最多重试 10 次（AWS SDK 的 “standard” 重试模式）。
如果你设置了 `AWS_RETRY_MODE` 或 `AWS_MAX_ATTEMPTS`，则使用你的值。仍然失败的列举会为该服务和区域记录一条警告：
`<service> <operation> in <region> failed (<error>); its resources there may be incomplete.`
JSON 输出会记录每次列举的结果。被拒绝的权限对每个服务只记录一次。

## 时间限制与并行账户 {#time-limit-and-parallel-accounts}

InvenTag 默认同时扫描最多四个账户。用 `--max-concurrent-accounts`（至少为 1）修改，
或用 `--disable-parallel-processing` 一次只扫描一个账户。

每个账户有 `--account-processing-timeout` 秒（默认 1800，至少 60），从该账户开始扫描时计时。
发现过程会提前一点结束，提前 300 秒或限制的 20%（取较小者），以便还能读取标签、详情和账单数据。

超时的账户会被报告为失败，其他账户会保留。它在限制之前找到的资源仍留在报告中，报告的备注会说明该账户不完整。
下面是用 `--account-processing-timeout 60` 做离线运行时的一行日志（示例数据）：

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

如果没有任何账户完成，InvenTag 仍会用已找到的内容写出报告，记录 `No account finished within its time limit`，并以退出码 1 结束。

## 失败的运行之后继续 {#continue-after-a-failed-run}

有账户失败时，InvenTag 会把已完成的账户保存在 `bom_output/state/partial/` 中。排除原因后，用同一条命令加上 `--resume` 再运行一次。
InvenTag 只扫描缺少的账户：

```bash
inventag --accounts-file accounts.yaml --create-excel --resume
```

只有当命令使用相同的账户、区域、服务和筛选条件，并且保存的结果不早于 `--resume-max-age-hours`（默认 24，最多 168）时，InvenTag 才会复用它。
它需要状态管理，所以 `--resume` 与 `--disable-state-management` 同用会以退出码 2 停止。
日志会显示 `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)`，报告的备注会列出每个被复用的账户及其扫描时间。
不带 `--resume` 时，警告会说明存在已保存的结果，并且它们会被重新扫描。所有账户都完成的运行结束后，InvenTag 会删除已保存的结果。

## 选择输出文件 {#choose-the-output-files}

| 参数 | 写出 |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | 同样的文件，由[报告模板](../templates/index.md)决定版式 |
| `--output-directory reports` | 把所有内容写入 `reports/`，而不是 `bom_output/` |

如果不指定输出参数，InvenTag 只写出 Excel。如果扫描没有发现任何资源，或者你的过滤条件把它们全部排除了，
InvenTag 不会写出任何文件，记录 `No resources to report (none found, or the filters removed all of them).`，并且仍以退出码 0 退出。使用 `--template` 时，它会写出一份不列出任何资源的报告。添加 `--s3-bucket` 还可以上传这些文件：
参见[定时把报告上传到 S3](../examples/scheduled-s3-upload.md)。

使用 `--template standard-bom --create-excel
--create-word --account-regions us-east-1` 运行时的示例输出（离线，示例数据）：

```text title="输出"
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

退出码 0 表示文件有效。使用 `--skip-credential-validation` 时，第一条命令不发出任何 AWS 调用。损坏的账户文件如下所示（示例数据）：

```text title="输出"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="输出"
1
```

## 退出码 {#exit-codes}

即使有账户失败或什么都没找到，InvenTag 也以退出码 0 结束。两个可选参数可以改变这一点。退出码 5 时报告仍会写出。

| 参数 | 退出码 | 何时 |
|---|---|---|
| `--fail-on-account-error` | 5 | 有账户无法扫描，或只扫描了一部分 |
| `--fail-if-empty` | 6 | 没有可报告的资源 |

对于退出码 6，带 `--template` 的运行会写出一份不列出任何资源的报告，不带 `--template` 的运行则不写文件。

完整列表见[在 CI/CD 中运行 InvenTag](./run-in-ci.md#exit-codes)。

## 下一步 {#next-steps}

- [扫描多个账户](./scan-multiple-accounts.md)
- [按策略检查标签](./check-tag-compliance.md)
- [CLI 参考](../reference/cli.md)
