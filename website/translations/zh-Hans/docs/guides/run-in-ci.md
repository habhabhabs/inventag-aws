---
title: 在 CI/CD 中运行 InvenTag
description: 在 GitHub Actions 或 GitLab CI/CD 中定时运行 InvenTag，使用短期的 OIDC 凭证，把报告保存为构件，并在标签策略违规时让作业失败。
sidebar_position: 7
---

# 在 CI/CD 中运行 InvenTag

**适合谁阅读：** 你想定时生成清单，或者希望在资源标签不规范时让流水线失败。

**读完后你可以：** 搭建一个 GitHub Actions 工作流或 GitLab CI/CD 流水线，用短期凭证运行 InvenTag 并保存报告。

## 组成部分 {#the-pieces}

1. **不存储密钥的凭证。** 使用 OpenID Connect（OIDC）：CI 系统证明作业的身份，
   AWS 为它提供一个临时的角色会话。你的仓库机密中不保存任何访问密钥。
2. **一个配置模板**，包含你的区域、输出和标签策略。内置的 `ci-pipeline` 模板是个不错的起点。
3. **一个构件**，用来保存 `bom_output/`。

## 1. 让 GitHub 代入只读角色 {#1-let-github-assume-a-read-only-role}

在 AWS 中，把 GitHub 添加为 OIDC 身份提供商（`token.actions.githubusercontent.com`），
并创建一个角色，附加[设置只读访问](./read-only-access.md)中的只读策略。
把它的信任策略限制在你的仓库和分支上。AWS 的指南
[Use IAM roles to connect GitHub Actions to actions in AWS](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)
有详细讲解。

## 2. 把配置模板添加到你的仓库 {#2-add-a-config-template-to-your-repository}

```bash
inventag templates init ci-pipeline --output .inventag/templates/nightly.yaml
```

设置你的区域和标签策略，然后提交该文件。

## 3. 添加工作流 {#3-add-the-workflow}

```yaml
# .github/workflows/inventory.yml
name: AWS inventory
on:
  schedule:
    - cron: "17 2 * * 1-5"   # 02:17 UTC on weekdays
  workflow_dispatch:

permissions:
  contents: read
  id-token: write            # needed for OIDC

jobs:
  inventory:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - run: pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: arn:aws:iam::123456789012:role/InvenTagGitHubReadOnly
          aws-region: us-east-1
      - name: Run InvenTag
        run: inventag --template nightly --fail-on-account-error --fail-if-empty
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()          # keep the reports even when the tag check fails
        with:
          name: inventory
          path: bom_output/
          retention-days: 30
```

请把每个 action 固定到完整的提交 SHA，并在注释中注明版本。这样即使某个标签被移到恶意代码上，
你也能得到保护。上面四个 SHA 是注释中所标版本的标签所对应的提交。
更新版本时，请同时更新 SHA。

InvenTag 从你仓库的文件夹运行，因此 `.inventag/templates/nightly.yaml` 可以按名称找到。

不加这两个退出码参数时，即使有账户无法扫描或什么都没找到，作业也会成功。`--fail-on-account-error` 会让前一种情况以退出码 5 使作业失败，
`--fail-if-empty` 会让后一种情况以退出码 6 使作业失败。报告仍会写出，所以上传构件的步骤可以保留它们。

## GitLab CI/CD {#gitlab-cicd}

本节是上面 GitHub Actions 步骤在 GitLab 上的对应做法。第 2 步的配置模板是同一个。示例按 GitLab.com 编写。[自托管实例](#on-a-self-managed-instance)需要做几处修改。

### 让 GitLab 代入只读角色 {#let-gitlab-assume-a-read-only-role}

未针对 GitLab 或 AWS 验证：GitLab 签发 ID 令牌，以及 AWS 为该角色接受它，包括信任策略中对 `aud` 和 `sub` 的条件。

**第 1 步：把 GitLab 添加为 IAM 中的 OIDC 身份提供商。** 在 IAM 控制台中打开 **Identity providers > Add provider**，选择 OpenID Connect（[AWS：创建 OIDC 身份提供商](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)）。

| 字段 | 值 |
|---|---|
| 提供商 URL | GitLab.com 用 `https://gitlab.com`。自托管实例用你自己实例的地址，例如 `https://gitlab.example.com`。AWS 要求 URL 以 `https://` 开头。GitLab 说明该地址必须可公开访问（[GitLab：OpenID Connect in AWS](https://docs.gitlab.com/ci/cloud_services/aws/)）。 |
| 受众 | `sts.amazonaws.com`。它必须与流水线中 `id_tokens` 下的 `aud` 文本相同。 |
| 指纹 | 无需填写。IAM 会自行获取，并且 AWS 会先对照自己的受信任根 CA 列表检查提供商的证书（[AWS：`create-open-id-connect-provider`](https://docs.aws.amazon.com/cli/latest/reference/iam/create-open-id-connect-provider.html)）。 |

每个 URL 在每个 AWS 账户中只能添加一个提供商。对同一个 URL 再次添加会失败。如果你的账户已经信任 `gitlab.com`，就把该受众添加到现有的提供商中。

**第 2 步：用信任策略创建角色。** 为这个提供商创建一个角色。下面的信任策略允许 GitLab.com 上的一个项目、一个分支代入该角色。这是定时示例的情形，它们在 `main` 上运行。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/gitlab.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "gitlab.com:aud": "sts.amazonaws.com",
          "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:main",
          "gitlab.com:project_id": "67890"
        }
      }
    }
  ]
}
```

替换这些值：

| 值 | 替换为 |
|---|---|
| `123456789012` | 保存身份提供商和角色的 AWS 账户 ID。提供商和角色必须在同一个账户中。 |
| `gitlab.com`（四处） | GitLab.com 保持不变。自托管实例则使用你实例的主机名，不带 `https://`。 |
| `sts.amazonaws.com` | 保持不变，除非你在第 1 步和 `id_tokens` 下选了别的受众。 |
| `mygroup/myproject` | 项目的完整路径：组、子组和项目。 |
| `main` | 定时流水线运行所在的分支。 |
| `67890` | 项目 ID。这一行只在 GitLab.com 上有效。在自托管或 Dedicated 实例上，AWS 只支持 `sub` 和 `aud` 声明，所以在那里要删除这一行。 |

`sub` 声明默认的形式是 `project_path:{group}/{project}:ref_type:{type}:ref:{branch_name}`。项目可以通过 projects API 改变这个形式，改变后上面的值就不再匹配（[GitLab：ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)）。建议使用针对稳定 ID（如 `project_id`）的条件，因为已删除的项目路径可能被别人重新创建（[AWS：IAM 条件键](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html)）。

条件中使用通配符需要 `StringLike`。如果用 `StringEquals`，AWS 会拒绝该调用。

**变体：任意受保护的分支（GitLab.com）。** 替换 `Condition` 块：

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890",
    "gitlab.com:ref_protected": "true"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

未针对 AWS 验证：`"true"` 是否正是 AWS 为 `ref_protected` 比较的文本。`ref_protected` 和 `pipeline_source` 只是 GitLab.com 的条件键。

**变体：受保护的标签（GitLab.com）。** 同一个块，把 `sub` 行中的 `ref_type:branch:ref:*` 部分换成 `ref_type:tag:ref:*`（或 `ref_type:tag:ref:v*`）。

**变体：合并请求流水线。** 合并请求流水线的令牌带的是源分支，所以角色必须接受项目的每一个分支：

```json
{
  "StringEquals": {
    "gitlab.com:aud": "sts.amazonaws.com",
    "gitlab.com:project_id": "67890"
  },
  "StringLike": {
    "gitlab.com:sub": "project_path:mygroup/myproject:ref_type:branch:ref:*"
  }
}
```

未针对 GitLab 验证：合并请求流水线中 `sub` 的确切文本。

使用这个变体时，任何能向项目推送分支并创建合并请求的人，都能用这个角色运行作业，还能在自己的分支里修改作业的脚本。该角色是只读的，所以他们能读到 InvenTag 能读到的内容。为这个变体单独创建一个角色。不要复用定时作业的角色，也不要给它 `s3:PutObject`。参见[标签策略示例](../examples/tag-policy-in-ci.md#gitlab-cicd)。

**第 3 步：附加只读策略。** 附加[设置只读访问](./read-only-access.md)中的策略：方案 2，即 `config/defaults/iam-policy-read-only.json`，或方案 1（`ReadOnlyAccess` 加三个操作）。

- 对上传示例，保留语句 `OptionalS3ReportUpload`，并把你的存储桶名称填到 `YOUR-REPORTS-BUCKET-NAME` 的位置。它的资源以 `bom-reports/*` 结尾，所以键前缀必须是 `bom-reports/`（默认值），否则就要修改该资源。使用 `aws:kms` 时，还要允许对该密钥执行 `kms:GenerateDataKey`（[IAM 权限](../reference/iam-permissions.md)）。参见[定时把报告上传到 S3](../examples/scheduled-s3-upload.md)。其他示例请删除该语句。
- 对多账户示例，该角色还需要对每个账户的 `InvenTagReadOnly` 角色执行 `sts:AssumeRole`，并且这些角色都要信任此角色。仓库中的策略文件没有 `sts:AssumeRole` 语句。参见[设置只读访问](./read-only-access.md)和[扫描多个账户](./scan-multiple-accounts.md)。

InvenTag 保持只读。无论角色还是流水线，都不会让任何账户符合任何合规要求。

#### 在自托管实例上 {#on-a-self-managed-instance}

未针对自托管 GitLab 实例验证：本段内容。提供商 URL 和条件键使用你实例的主机名。在那里 AWS 只支持 `sub` 和 `aud` 声明，所以要删除 `project_id` 这一行。在那里 AWS 中没有 `ref_protected` 键，所以要按名称逐个固定分支。AWS 必须能从互联网访问该实例；对非公开的实例，GitLab 描述了一种变通办法，并称之为高级用法（[GitLab：configure a non-public GitLab instance](https://docs.gitlab.com/ci/cloud_services/aws/)）。Runner 必须能够运行容器镜像。

### 添加 CI/CD 变量 {#add-the-cicd-variable}

在你的 GitLab 项目中，打开 **Settings > CI/CD > Variables > Add variable**（需要 Maintainer 角色）。键填 `AWS_ROLE_ARN`，值填角色的 ARN，例如 `arn:aws:iam::123456789012:role/InvenTagGitLabReadOnly`。GitLab 会把该变量作为环境变量传给作业（[GitLab：CI/CD variables](https://docs.gitlab.com/ci/variables/)）。

- 对定时示例，勾选 **Protect variable** 并保护该分支。这样该变量只会传给受保护分支或标签上的流水线。
- 对合并请求示例，不要保护该变量。除非源分支和目标分支都受保护，否则受保护的变量不会传给合并请求流水线（[GitLab：merge request pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)）。如果用了两个角色，请在该示例的两个作业中使用第二个变量名。
- 自 GitLab 18.3 起，GitLab 默认把新变量设为 **Masked**，而被屏蔽的值必须是一行、至少 8 个字符且不含空格。角色 ARN 不是机密。如果 GitLab 拒绝屏蔽该值，请选择 **Visible**。未针对 GitLab 验证：GitLab 是否接受把角色 ARN 作为屏蔽值。
- 上传示例还需要另外两个变量，`INVENTAG_REPORTS_BUCKET` 和 `INVENTAG_KMS_KEY_ID`。两者都不是机密。

### 添加流水线 {#add-the-pipeline}

这个作业每晚运行 InvenTag，并把报告保存为作业产物。它需要第 2 步中的 `.inventag/templates/nightly.yaml`。把文件以 `.gitlab-ci.yml` 为名放到仓库根目录。如果该文件已经有 `stages`，就把阶段名加到那个列表里。

未针对 GitLab Runner 或真实的 AWS 账户验证：此流水线尚未在 GitLab 上运行。它的 YAML 和 `inventag` 命令行会在构建文档时检查。它的作业已在本地用 gitlab-ci-local 4.77.1（用替身代替 rsync）针对模拟的 AWS 运行，使用的是虚拟令牌。

```yaml
# .gitlab-ci.yml
stages:
  - inventory

inventory:
  stage: inventory
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"   # the pipeline schedule
    - if: $CI_PIPELINE_SOURCE == "web"        # "New pipeline" in the GitLab UI
  timeout: 2 hours                            # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  cache:
    key: pip
    paths:
      - .cache/pip
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - inventag --template nightly --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # keep the reports even when the tag check fails
    paths:
      - bom_output/
    expire_in: 30 days
```

各部分的作用：

| 部分 | 作用 |
|---|---|
| `stages:` 和 `stage:` | 声明阶段，并把作业放进该阶段。没有 `stage` 的作业会进入 `test`（[GitLab：`stages`](https://docs.gitlab.com/ci/yaml/#stages)）。 |
| `image: python:3.12` | 作业在这个容器镜像中运行，形式为 `<image-name>:<tag>`。InvenTag 需要 Python 3.11 或更高版本，GitHub 示例用的是 3.12（[GitLab：`image`](https://docs.gitlab.com/ci/yaml/#image)）。 |
| 带 `schedule` 和 `web` 的 `rules:` | 作业只会加入定时流水线，以及在 GitLab 界面中用 **New pipeline** 启动的流水线。在其他所有流水线（推送、合并请求）中，没有规则匹配，作业不会被加入（[GitLab：job rules](https://docs.gitlab.com/ci/jobs/job_rules/)）。 |
| `timeout: 2 hours` | 超过该时间后停止作业（[GitLab：`timeout`](https://docs.gitlab.com/ci/yaml/#timeout)）。它还决定 ID 令牌的有效期：如果设置了作业超时，GitLab 把令牌的过期时间设为该超时；没有设置则为 5 分钟（[GitLab：ID token authentication](https://docs.gitlab.com/ci/secrets/id_token_authentication/)）。InvenTag 在一次运行中不止一次交换令牌（已在本地对模拟的 AWS 验证），所以请始终设置 `timeout`。GitLab.com 上由 GitLab 托管的 Runner 会在 3 小时后停止每个作业（[GitLab：hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)）。 |
| `id_tokens:` | GitLab 为这个作业生成一个 OIDC ID 令牌（一种 JSON Web 令牌），受众写在 `aud` 中。脚本以 `$GITLAB_OIDC_TOKEN` 读取它。它在 Free、Premium 和 Ultimate 套餐中可用，适用于 GitLab.com、Self-Managed 和 Dedicated（[GitLab：`id_tokens`](https://docs.gitlab.com/ci/yaml/#id_tokens)）。 |
| `AWS_DEFAULT_REGION` | AWS SDK 在登录调用中使用的区域。请设置这个变量：只设 `AWS_REGION` 不够，因为 botocore（AWS 的 Python SDK）不读取它（已在本地验证）。 |
| `pip install "inventag-aws==..."` | 安装 InvenTag 的固定版本。 |
| 带 `AWS_WEB_IDENTITY_TOKEN_FILE` 的两行 | 把令牌写入项目文件夹之外的一个新的私有文件，并告诉 AWS SDK 它在哪里。有了 `AWS_ROLE_ARN`（CI/CD 变量），SDK 会自己把令牌换成临时凭证（[AWS：assume role credentials](https://docs.aws.amazon.com/sdkref/latest/guide/feature-assume-role-credentials.html)）。不需要 AWS CLI，也不需要访问密钥。项目文件夹之外的文件不会变成产物或缓存条目，因为两者都只接受项目文件夹内的路径（[GitLab：`artifacts:paths`](https://docs.gitlab.com/ci/yaml/#artifactspaths)、[GitLab：caching](https://docs.gitlab.com/ci/caching/)）。已在本地对模拟的 AWS 验证：该文件的权限是 600，SDK 用该令牌登录。 |
| `PIP_CACHE_DIR` 和 `cache:` | 在作业之间保留 pip 的下载缓存。缓存必须在项目文件夹内，因为 GitLab 只缓存那里的路径（[GitLab：caching examples](https://docs.gitlab.com/ci/caching/examples/)）。可选：没有这几行，作业也能运行。 |
| `inventag --template nightly --fail-on-account-error --fail-if-empty` | 与 GitHub 工作流中的命令相同。标签策略发现违规且模板中写了 `fail_on_tag_violations: true` 时退出码为 3，有账户无法扫描时为 5，没有找到任何资源时为 6。任何非 0 的退出码都会让作业失败（[GitLab：`script`](https://docs.gitlab.com/ci/yaml/script/)）。在本地（用替身代替 rsync），作业以退出码 3 结束，并收集到了四个报告文件。 |
| `artifacts:` | 把 `bom_output/` 作为作业产物上传。有 `when: always` 时，作业失败 GitLab 也会上传；没有它，则只在作业成功时上传。`always` 不包括超时的作业。`expire_in` 指定 GitLab 保留产物多久。无论 `expire_in` 如何，GitLab 都会保留某个 ref 最新流水线的产物（默认的项目设置）（[GitLab：`artifacts:when`](https://docs.gitlab.com/ci/yaml/#artifactswhen)、[GitLab：`artifacts:expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in)、[GitLab：job artifacts](https://docs.gitlab.com/ci/jobs/job_artifacts/)）。`expire_in: 30 days` 与 GitHub 工作流中的 `retention-days: 30` 对应。InvenTag 在以退出码 3、4 或 5 退出之前就已写出报告。 |
| 角色 ARN | 不在 YAML 中。它是上一步的 CI/CD 变量 `AWS_ROLE_ARN`。 |

这个示例还有两部分没有验证：

- 未针对 GitLab 验证：`image`、`timeout`、`expire_in` 和 `cache`（gitlab-ci-local 会忽略它们）。
- 未针对 GitLab 流水线计划验证：本地运行时，流水线来源是手动设置的。

### 设置定时运行 {#schedule-it}

定时设置不在文件里。请在 GitLab 中创建一个 schedule：打开 **Build > Pipeline schedules > New schedule**，填写 cron 表达式（例如 `17 2 * * 1-5`）和目标分支，然后保存。你需要 Developer 或更高的角色。流水线以该 schedule 所有者的权限运行（[GitLab：pipeline schedules](https://docs.gitlab.com/ci/pipelines/schedules/)）。要手动运行该作业，请在 GitLab 界面中选择 **New pipeline**，或在该 schedule 上选择 **Run**。

未针对 GitLab 验证：流水线计划对 cron 表达式使用的时区。

### 与 GitHub Actions 的差异 {#what-differs-from-github-actions}

GitHub 一列只描述上面的 GitHub 工作流所展示的内容。

| 主题 | GitHub Actions | GitLab CI/CD |
|---|---|---|
| 文件 | `.github/workflows/inventory.yml` | 仓库根目录的 `.gitlab-ci.yml` |
| 定时 | 文件内的 `on: schedule: - cron:` | 不在文件里。在 GitLab 界面中创建 schedule（**Build > Pipeline schedules**），再用一行 `rules` 让作业进入定时流水线 |
| 手动运行 | `workflow_dispatch` | 界面中的 **New pipeline**（`$CI_PIPELINE_SOURCE == "web"`），或在 schedule 上点 **Run** |
| 请求 OIDC 令牌 | `permissions: id-token: write` | 作业上的 `id_tokens:`，受众写在 `aud` 中 |
| 获取 AWS 凭证 | 动作 `aws-actions/configure-aws-credentials` | 没有动作。脚本中两行把令牌写入文件，由 InvenTag 内部的 AWS SDK 交换（`AWS_ROLE_ARN`、`AWS_WEB_IDENTITY_TOKEN_FILE`） |
| 角色 ARN | 在 YAML 中（`role-to-assume`） | CI/CD 变量 `AWS_ROLE_ARN`，不在 YAML 中 |
| 区域 | `aws-region: us-east-1` | `AWS_DEFAULT_REGION: us-east-1`。只设 `AWS_REGION` 不够 |
| AWS 中的身份提供商 | `token.actions.githubusercontent.com` | `gitlab.com`，或你自己实例的主机 |
| 信任策略限定什么 | 仓库和分支 | `sub` 声明：项目路径、ref 类型和 ref 名称。在 GitLab.com 上还有项目 ID |
| 令牌有效期 | 本页未说明 | 作业的 `timeout`；作业没有设置则为 5 分钟。请始终设置 `timeout` |
| Python | `actions/setup-python`，`python-version: "3.12"` | `image: python:3.12` |
| 固定版本 | 每个动作按完整的提交 SHA 固定 | 镜像按次版本标签固定。镜像摘要（`<image-name>@<digest>`）是更严格的形式；示例没有使用（[GitLab：`image`](https://docs.gitlab.com/ci/yaml/#image)） |
| 保存报告 | `actions/upload-artifact`，带 `if: always()` 和 `retention-days: 30` | `artifacts:`，带 `when: always` 和 `expire_in: 30 days`。作业超时则不会上传。产物中还包含 `bom_output/state/` |
| 容忍某个退出码 | 本页未展示 | 作业上的 `allow_failure: exit_codes:`（[GitLab：`allow_failure:exit_codes`](https://docs.gitlab.com/ci/yaml/#allow_failureexit_codes)） |
| 作业最长时间 | 本页未说明 | GitLab.com 上由 GitLab 托管的 Runner 为 3 小时（[GitLab：hosted runners](https://docs.gitlab.com/ci/runners/hosted_runners/)） |
| 合并请求或拉取请求的运行 | 本页未展示 | 令牌带的是源分支，受保护的变量只在 GitLab 的条件下才会传入。参见[标签策略示例](../examples/tag-policy-in-ci.md#gitlab-cicd) |
| 作业摘要 | `$GITHUB_STEP_SUMMARY`（见[标签策略示例](../examples/tag-policy-in-ci.md)） | 这些示例中没有使用 |

## 发生违规时会怎样 {#what-happens-on-a-violation}

设置了 `fail_on_tag_violations: true` 时，InvenTag 会先写出所有报告，然后以退出码 3 退出。
作业会失败，而构件中仍然保存着 Excel 文件和 `tag_compliance_<timestamp>.json`，
后者包含每个不合规的资源。

下面是离线运行 `inventag --template ci-pipeline` 的示例输出（示例数据）：

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

## 退出码 {#exit-codes}

| 退出码 | 含义 |
|---|---|
| 0 | 报告已写出，没有标签违规（或没有会导致失败的策略）。有账户失败或什么都没找到时也是 0，除非你传了对应退出码 5 和 6 的参数 |
| 1 | 错误：模板或配置文件无效、凭证问题、所有账户都失败、某个报告格式无法写出，或 S3 上传失败 |
| 2 | 选项无效或相互冲突，例如 `--accounts-file` 与 `--accounts-prompt` 同用，或 `--compliance-standard`（未实现）。不会扫描任何内容 |
| 3 | 报告已写出，发现标签策略违规（`fail_on_tag_violations: true`） |
| 4 | 报告已写出，有对互联网开放的安全组规则达到或超过 `--risk-threshold` |
| 5 | 报告已写出，有账户无法扫描或只扫描了一部分（`--fail-on-account-error`） |
| 6 | 没有可报告的资源（`--fail-if-empty`） |

如果同时满足多个条件，先是 5，然后是 6，然后是 3，最后是 4，因为缺少账户时，标签或风险结果背后的数据是不完整的。
退出码 3、4 和 5 会写出报告。对于退出码 6，带 `--template` 的运行会写出一份不列出任何资源的报告，不带 `--template` 的运行则不写文件。

## 保持安全 {#keep-it-safe}

- 在 CI 中避免使用 `--debug`。调试日志中的机密会被遮蔽，但日志很长，仍然会描述你的账户。
- 如果想把报告保存在 S3 中（代替构件，或与构件并用），请添加 `--s3-bucket`，
  并授予对该存储桶的 `s3:PutObject` 权限。参见
  [定时把报告上传到 S3](../examples/scheduled-s3-upload.md)。
- 保持角色只读，并把它限定在需要它的仓库和分支。
- 在 GitLab CI/CD 中，保护运行流水线的分支，把角色的信任策略限制在该分支上，并把角色 ARN 保存在 CI/CD 变量中。参见 [GitLab CI/CD](#gitlab-cicd)。
- 把 InvenTag 固定到某个发布版本（`inventag-aws==%INVENTAG_VERSION%`），而不是最新版本。想升级时再自己提高版本号。

## 下一步 {#next-steps}

- [示例：在 CI 中强制执行标签策略](../examples/tag-policy-in-ci.md)
- [跟踪两次运行之间的变化](./track-changes.md)
