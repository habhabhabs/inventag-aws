---
title: 在 CI/CD 中运行 InvenTag
description: 在 GitHub Actions 中定时运行 InvenTag，使用短期的 OIDC 凭证，把报告保存为构件，并在标签策略违规时让作业失败。
sidebar_position: 7
---

# 在 CI/CD 中运行 InvenTag

**适合谁阅读：** 你想定时生成清单，或者希望在资源标签不规范时让流水线失败。

**读完后你可以：** 搭建一个 GitHub Actions 工作流，用短期凭证运行 InvenTag 并保存报告。

## 组成部分 {#the-pieces}

1. **不存储密钥的凭证。** 使用 OpenID Connect（OIDC）：GitHub 证明工作流的身份，
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
      - uses: aws-actions/configure-aws-credentials@<full-commit-SHA> # pin the current release
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
你也能得到保护。上面 `checkout`、`setup-python` 和 `upload-artifact` 的 SHA，
是本仓库自己的工作流所使用的。对于 `aws-actions/configure-aws-credentials`，
请到它的 GitHub 发布页面查找当前发布版本的 SHA：我们没有为本页验证过任何一个。
更新版本时，请同时更新 SHA。

InvenTag 从你仓库的文件夹运行，因此 `.inventag/templates/nightly.yaml` 可以按名称找到。

不加这两个退出码参数时，即使有账户无法扫描或什么都没找到，作业也会成功。`--fail-on-account-error` 会让前一种情况以退出码 5 使作业失败，
`--fail-if-empty` 会让后一种情况以退出码 6 使作业失败。报告仍会写出，所以上传构件的步骤可以保留它们。

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
- 把 InvenTag 固定到某个发布版本（`inventag-aws==%INVENTAG_VERSION%`），而不是最新版本。想升级时再自己提高版本号。

## 下一步 {#next-steps}

- [示例：在 CI 中强制执行标签策略](../examples/tag-policy-in-ci.md)
- [跟踪两次运行之间的变化](./track-changes.md)
