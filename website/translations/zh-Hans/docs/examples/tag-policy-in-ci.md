---
title: "示例：在 CI 中强制执行标签策略"
description: 当 AWS 资源违反你的标签策略时，让 CI 作业以退出码 3 失败，同时把 InvenTag 报告保留为构建产物。
sidebar_position: 4
---

# 示例：在 CI 中强制执行标签策略

**目标：** 一个流水线步骤，在资源缺少必需标签或标签值错误时失败，并保留证据。

**你需要：** 一个带有只读 AWS 凭证的 CI 运行器，最好通过 OIDC（OpenID Connect）获取。
参见[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md)。

## 模板 {#template}

内置的 `ci-pipeline` 配置模板会写出 Excel 和一个 JSON 文件，检查 `finops-cost-allocation`，
并在出现违规时失败：

```yaml title="ci-pipeline (built-in)"
format_version: 1
kind: config
name: ci-pipeline
description: Excel report plus tag-compliance JSON; exits with code 3 on tag policy violations.
spec:
  regions: [us-east-1]
  outputs: [excel]
  output_directory: bom_output
  report_template: standard-bom
  tag_policy: finops-cost-allocation
  fail_on_tag_violations: true
  parallel_processing: false
```

## 命令 {#command}

```bash title="Terminal"
inventag --template ci-pipeline
```

## 输出 {#output}

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
```

```bash title="Terminal"
echo $?
```

```text title="输出"
3
```

因为模板写了 `outputs: [excel]`，所以只会写出 Excel 文件和 JSON 文件：

```text title="bom_output/"
multi_account_bom_20261112_090000.xlsx
state
tag_compliance_20261112_090000.json
```

要在 GitHub Actions 作业摘要中列出前十个不合规的资源：

```bash title="Workflow step"
python3 -c "
import json, glob
r = json.load(open(sorted(glob.glob('bom_output/tag_compliance_*.json'))[-1]))
print(f\"{r['summary']['non_compliant']} non-compliant resources\")
for x in r['non_compliant_resources'][:10]:
    print('-', x['service'], x['resource_id'], 'missing:', ', '.join(x['missing']))
" >> "$GITHUB_STEP_SUMMARY"
```

```text title="Job summary"
22 non-compliant resources
- ATHENA primary missing: CostCenter, Owner, Project, Environment
- DYNAMODB acme-orders missing: CostCenter, Project
- EC2 i-855a01aabe3d29d3a missing: CostCenter, Project
- EC2 snap-3585ce88e25ef1196 missing: CostCenter, Owner, Project, Environment
- EC2 vol-680d0e08d01dd52e7 missing: CostCenter, Owner, Project, Environment
- EC2 vol-57d5df4cfc9884b48 missing: CostCenter, Owner, Project, Environment
- EVENTS default missing: CostCenter, Owner, Project, Environment
- IAM acme-orders-api-role missing: CostCenter, Owner, Project, Environment
- LAMBDA acme-orders-api missing: CostCenter, Project
- S3 acme-data-lake missing: Project
```

未针对 GitHub Actions Runner 验证：作业摘要会显示此输出。

`acme-reports` 拥有所有标签，但有两个值是错误的。JSON 文件中的 `invalid` 列表和工作簿中的 Problems 列会说明具体是哪两个。

## GitLab CI/CD {#gitlab-cicd}

同样的检查可以作为 GitLab CI/CD 作业，在合并请求流水线中运行。**该检查读取的是 AWS 当前的状态，不会读取合并请求中的更改。**

请先设置角色和 CI/CD 变量：参见[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)。合并请求作业需要第二个角色，见下面的第三点。

未针对 GitLab Runner 或真实的 AWS 账户验证：此流水线尚未在 GitLab 上运行。它的 YAML 和 `inventag` 命令行会在构建文档时检查。它的作业已在本地用 gitlab-ci-local 4.77.1（用替身代替 rsync）针对模拟的 AWS 运行，使用的是虚拟令牌。

```yaml
# .gitlab-ci.yml
stages:
  - check

tag-policy:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour                             # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    # Exit code 3 (tag policy violations) fails this job.
    # Exit code 5 (an account could not be scanned) and 6 (no resources found) fail it too.
    - inventag --template ci-pipeline --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports when the job fails
    paths:
      - bom_output/
    expire_in: 1 week

security-groups:
  stage: check
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  timeout: 1 hour
  allow_failure:
    exit_codes: 4                             # warn only; delete these two lines to block on exit code 4
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --create-excel --enable-security-analysis --risk-threshold HIGH --fail-on-account-error --fail-if-empty
  artifacts:
    when: always
    paths:
      - bom_output/
    expire_in: 1 week
```

### 每个退出码的结果 {#what-each-exit-code-does}

此文件中，GitLab 对 InvenTag 每个退出码的处理：

| 退出码 | 作业 `tag-policy` | 作业 `security-groups` |
|---|---|---|
| 0 | 通过 | 通过 |
| 3（标签策略违规） | **失败**，与 GitHub Actions 示例一致（[GitLab：`script`](https://docs.gitlab.com/ci/yaml/script/)） | 不会出现（此命令没有标签策略） |
| 4（有安全组规则达到或超过 `HIGH`） | 不会出现（没有 `--risk-threshold`） | “允许失败”：作业显示警告，流水线继续运行，并算作通过（[GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)） |
| 5（有账户无法扫描；`--fail-on-account-error`）、6（没有找到资源；`--fail-if-empty`） | 失败 | 失败：该退出码不在 `exit_codes` 中，所以对它而言 `allow_failure` 为 false |
| 1、2 | 失败 | 失败 |

### 各部分的作用 {#what-each-part-does}

所有 GitLab 示例共用的行（`image`、`timeout`、`id_tokens`、两行令牌命令和 `artifacts`）见[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)中的表格。下表列出本示例特有的部分：

| 部分 | 作用 |
|---|---|
| `rules: - if: $CI_PIPELINE_SOURCE == "merge_request_event"` | 作业只在合并请求流水线中运行（[GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)）。 |
| `inventag --template ci-pipeline --fail-on-account-error --fail-if-empty` | 本页的命令，加上两个需要主动开启的选项。退出码 5 和 6 优先于 3（顺序为 5、6、3、4），所以有账户无法扫描、或没有找到资源的运行，绝不会显示为“无违规”。已连接账户内某次服务调用失败不会给出 5。在本地运行中，此作业以退出码 3 失败，其报告文件已被收集。 |
| `allow_failure: exit_codes: 4` | 只容许退出码 4。其他任何非零退出码，作业照常失败（[GitLab：`script`](https://docs.gitlab.com/ci/yaml/script/)）。若要让退出码 4 也阻止合并请求，删除这两行。若要让 `tag-policy` 作业以警告模式启动，用同样的方式给它加上 `allow_failure:` 和 `exit_codes: 3`，或者像“下一步”所说，保持 `fail_on_tag_violations: false`（[GitLab](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)）。在本地运行中，`security-groups` 以警告和退出码 4 结束。 |
| `inventag --create-excel --enable-security-analysis --risk-threshold HIGH ...` | 有安全组规则达到或超过 `HIGH` 时退出码为 4。`--risk-threshold` 需要 `--enable-security-analysis`，否则退出码为 2。这里没有 `--template`，因为 `--enable-security-analysis` 与 `--template` 一起使用时不会增加任何内容（见 [CLI 参考](../reference/cli.md)）。此作业会扫描每个已启用的区域。 |

尚未验证的内容：

- 未针对 GitLab 或 AWS 验证：GitLab 签发 ID 令牌，以及 AWS 为该角色接受它，包括信任策略中对 `aud` 和 `sub` 的条件。
- 未针对 GitLab 验证：`image`、`timeout` 和 `expire_in`（gitlab-ci-local 会忽略它们）。
- 未针对 GitLab 验证：失败的作业或允许失败的作业如何影响后续作业、流水线状态和合并请求。

### 需要了解的三点 {#three-things-to-know}

1. **该检查读取的是 AWS 当前的状态，不会读取合并请求中的更改。** 这些命令除了模板文件之外，不会把仓库中的任何内容交给 InvenTag。每个作业对账户扫描一次，所以一次合并请求流水线会扫描两次。默认情况下，每次运行还会使用 Cost Explorer，AWS 对每次 Cost Explorer 请求收费；`--no-billing-validation` 会停止这些调用（见 [CLI 参考](../reference/cli.md)）。
2. **只有项目要求时，失败的作业才会阻止合并。** 请开启 **Settings > Merge requests > Merge checks > Pipelines must succeed**。你需要 Maintainer 或 Owner 角色（[GitLab](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)）。
3. **在合并请求流水线中，ID 令牌指明的是源分支，而不是 `main`**（[GitLab](https://docs.gitlab.com/ci/secrets/id_token_authentication/)）。信任策略只允许 `ref:main` 的角色会拒绝这些作业。请为它们创建第二个只读角色，不带上传语句（`s3:PutObject`）。这种情况的信任策略见[在 CI/CD 中运行 InvenTag](../guides/run-in-ci.md#gitlab-cicd)。任何能向项目推送分支并创建合并请求的人，都可以用这个角色运行作业，还可以在自己的分支中修改作业的脚本。该角色是只读的，所以他们能读取 InvenTag 能读取的内容。不要复用定时作业所用的角色。
   - 受保护的 CI/CD 变量只有在源分支和目标分支都受保护、两者在同一个项目中、并且该用户可以合并到目标分支时，才会传给合并请求流水线。来自复刻（fork）的流水线永远得不到它（[GitLab](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)）。因此，不要为这些作业保护 `AWS_ROLE_ARN`。
   - 示例读取的是 `AWS_ROLE_ARN`，这适用于只有这些合并请求作业的项目。如果项目还用第一个角色运行定时作业，第二个角色需要另一个变量名。本示例没有演示如何映射。

## 下一步 {#next-steps}

- 先从仅报告模式开始：在数字接近零之前，把 `fail_on_tag_violations` 设为 `false`，然后再打开它。
- 不要让有账户失败的运行被当作通过：有账户无法扫描或超出时间限制时，`--fail-on-account-error` 以退出码 5 结束；没有找到任何资源时，`--fail-if-empty` 以退出码 6 结束。两者都优先于退出码 3。
- 使用你自己的规则：[对照策略检查标签](../guides/check-tag-compliance.md#write-your-own-policy)。
