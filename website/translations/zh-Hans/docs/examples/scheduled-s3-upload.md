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
  并且只允许加密上传。它的资源是
  `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`：请替换存储桶名称，并注意它只覆盖以
  `bom-reports/` 开头的键。这也是 `--s3-key-prefix` 的默认值。若使用其他前缀，请修改该
  资源；
- 一个调度器：cron、CI 定时任务或类似工具。

## 命令 {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ \
  --audit-output audit.json
```

- `--s3-bucket` 会上传本次运行写出的每份报告。上传使用服务器端加密
  （默认为 `AES256`；若要使用 KMS 密钥，请用 `--s3-encryption aws:kms` 和
  `--s3-kms-key-id`）。`--s3-kms-key-id` 只能与 `--s3-encryption aws:kms`
  一起使用；否则运行会以退出码 2 停止。使用 `aws:kms` 但不给密钥 ID 时，S3 使用 AWS
  托管密钥 `aws/s3`。
- 每个文件会放到 `<prefix><UTC timestamp>/<file name>`，因此各次运行不会互相覆盖。
  如果有标签合规 JSON 文件，也会一并上传。
- 如果上传失败，运行会以退出码 1 结束，调度器因此可以察觉。报告仍然保留在你的磁盘上。
- `--audit-output` 会写出一份 JSON 列表，记录本次运行调用过的每个 AWS 操作。
  无论是否使用 S3，它都可以使用。

## 输出 {#output}

以下来自针对模拟 AWS 的离线运行（示例数据）：

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

存储桶中收到的内容：

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090100.xlsx
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
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ >> /var/log/inventag.log 2>&1
```

在 GitHub Actions 中，把 `--s3-bucket` 选项添加到
[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md)里的运行步骤。

### GitLab CI/CD {#gitlab-cicd}

未针对 GitLab Runner 或真实的 AWS 账户验证：此流水线尚未在 GitLab 上运行。它的 YAML 和 `inventag` 命令行会在构建文档时检查。它的作业已在本地用 gitlab-ci-local 4.77.1（用替身代替 rsync）针对模拟的 AWS 运行，使用的是虚拟令牌。

这个作业按流水线计划运行上面的命令，把报告上传到你的存储桶，并把一份副本保存为作业产物。使用之前：

- 按照[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)中的说明，创建 GitLab 用来登录的角色和 CI/CD 变量 `AWS_ROLE_ARN`。该部分也说明了如何创建流水线计划。
- 再添加两个 CI/CD 变量：`INVENTAG_REPORTS_BUCKET`（存储桶名称）和 `INVENTAG_KMS_KEY_ID`（KMS 密钥 ID）。两者都不是机密。
- 给该角色加上 `config/defaults/iam-policy-read-only.json` 中的 `OptionalS3ReportUpload` 语句，并把 `YOUR-REPORTS-BUCKET-NAME` 换成你的存储桶名称。它的资源是 `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`，所以请保留 `--s3-key-prefix bom-reports/`，或修改该资源。使用 `aws:kms` 时，角色还需要对该密钥拥有 `kms:GenerateDataKey` 权限（[IAM 权限](../reference/iam-permissions.md)）。

```yaml
# .gitlab-ci.yml
stages:
  - inventory

inventory-to-s3:
  stage: inventory
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
  timeout: 2 hours                            # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    # --s3-kms-key-id works only together with --s3-encryption aws:kms.
    # Without KMS, delete that line: uploads then use AES256.
    - |
      inventag --template standard-bom --create-excel --account-regions us-east-1 \
        --s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/ \
        --s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID" \
        --audit-output bom_output/audit.json \
        --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # a copy in GitLab, also when the upload fails
    paths:
      - bom_output/
    expire_in: 1 week
```

所有 GitLab 示例共有的行，在[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)中说明。下表只说明这个示例特有的部分。

| 部分 | 作用 |
|---|---|
| `- \|`，行尾带 `\` | 把一条 shell 命令分成五行来写（[GitLab：script](https://docs.gitlab.com/ci/yaml/script/)）。 |
| `--s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/` | 把本次运行的每份报告上传到 `<prefix><UTC timestamp>/<file name>`。存储桶名称来自 CI/CD 变量。`bom-reports/` 也是默认值，这里把它写出来，是因为已发布的策略只允许对 `YOUR-REPORTS-BUCKET-NAME/bom-reports/*` 执行 `s3:PutObject`。如果上传失败，运行会以退出码 1 结束，作业随之失败（[GitLab：script](https://docs.gitlab.com/ci/yaml/script/)）。 |
| `--s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID"` | 本页的 KMS 规则：`--s3-kms-key-id` 只能与 `--s3-encryption aws:kms` 一起使用；否则运行会以退出码 2 停止。使用 `aws:kms` 但不给密钥 ID 时，S3 使用 AWS 托管密钥 `aws/s3`。不用 KMS 时，删除这一行：上传就使用 `AES256`。角色需要对该密钥拥有 `kms:GenerateDataKey` 权限。 |
| `--fail-on-account-error --fail-if-empty` | 有账户无法扫描时，退出码为 5；没有找到任何资源时，退出码为 6。任何非 0 的退出码都会使作业失败（[GitLab：script](https://docs.gitlab.com/ci/yaml/script/)）。 |
| `--audit-output bom_output/audit.json` | 把本次运行调用过的 AWS 操作列表写入产物文件夹。 |
| `artifacts:`，带 `expire_in: 1 week` | 在 GitLab 中保留第二份副本，上传失败时也会保留（[`when`](https://docs.gitlab.com/ci/yaml/#artifactswhen)、[`expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in)）。可选。 |

本地运行没有覆盖的部分：

- 未针对 GitLab 或 AWS 验证：GitLab 签发 ID 令牌，以及 AWS 为该角色接受它，包括信任策略中对 `aud` 和 `sub` 的条件。
- 未针对 GitLab 验证：`image`、`timeout` 和 `expire_in`（gitlab-ci-local 会忽略它们）。
- 未针对 GitLab 流水线计划验证：本地运行时，流水线来源是手动设置的。
- 未针对 AWS 验证：用真实的存储桶和密钥上传时的 S3 和 KMS 权限。
- 未针对 AWS 验证：`aws:kms` 没有密钥 ID 时，S3 是否使用 AWS 托管密钥 `aws/s3`。

## 下一步 {#next-steps}

- 如果希望过一段时间后删除旧报告，请为存储桶添加 S3 生命周期规则。
  InvenTag 不会更改你存储桶的生命周期规则。
- 如果需要历史记录，请在多次运行之间保留 `state/` 文件夹：
  [跟踪各次运行之间的变化](../guides/track-changes.md)。
