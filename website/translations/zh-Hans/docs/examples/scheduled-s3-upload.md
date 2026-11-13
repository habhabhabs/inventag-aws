---
title: "示例：按计划将报告上传到 S3"
description: 每次定时运行后，把 InvenTag 加密的 Excel 报告上传到 S3 存储桶，并附上本次运行所做的每个 AWS 调用的审计记录。
sidebar_position: 9
---

# 示例：按计划将报告上传到 S3

**目标：** 每次定时运行都把报告加密后放入 S3 存储桶，并留下它所做的每个 AWS 调用的记录。

**你需要：**

- 一个存放报告的存储桶，例如 `acme-inventory-reports`；
- 运行 InvenTag 的身份对该存储桶拥有 `s3:PutObject` 权限。
  `config/defaults/iam-policy-read-only.json` 中的 `OptionalS3ReportUpload` 语句就提供这个权限，
  并且只允许加密上传；
- 一个调度器：cron、CI 定时任务或类似工具。

## 命令 {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ \
  --audit-output audit.json
```

- `--s3-bucket` 会上传本次运行写出的每份报告。上传使用服务器端加密
  （默认为 `AES256`；若要使用 KMS 密钥，请用 `--s3-encryption aws:kms` 和
  `--s3-kms-key-id`）。
- 每个文件会放到 `<prefix><UTC timestamp>/<file name>`，因此各次运行不会互相覆盖。
  如果有标签合规 JSON 文件，也会一并上传。
- 如果上传失败，运行会以退出码 1 结束，调度器因此可以察觉。报告仍然保留在你的磁盘上。
- `--audit-output` 会写出一份 JSON 列表，记录本次运行调用过的每个 AWS 操作。
  无论是否使用 S3，它都可以使用。

## 输出 {#output}

以下来自针对模拟 AWS 的离线运行（示例数据）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

存储桶中收到的内容：

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

审计文件（节选）：

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
  "total_calls": 96,
  "allowed_calls": 96,
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
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

`blocked_calls` 为 0：本次运行只发出了读取调用。

## 设置定时运行 {#schedule-it}

使用 cron，每个工作日 02:17 运行：

```text title="crontab -e"
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ >> /var/log/inventag.log 2>&1
```

在 GitHub Actions 中，把 `--s3-bucket` 选项添加到
[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md)里的运行步骤。

## 下一步 {#next-steps}

- 如果希望过一段时间后删除旧报告，请为存储桶添加 S3 生命周期规则。
  InvenTag 不会更改你存储桶的生命周期规则。
- 如果需要历史记录，请在多次运行之间保留 `state/` 文件夹：
  [跟踪各次运行之间的变化](../guides/track-changes.md)。
