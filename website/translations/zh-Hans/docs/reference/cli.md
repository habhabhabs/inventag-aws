---
title: 命令行参考
description: InvenTag 的每个命令和参数、它在当前版本上的行为及默认值，均已对照 inventag --help 核对。
sidebar_position: 1
---

# 命令行参考

**适合谁阅读：** 你需要知道某个参数的确切名称或行为。

**读完后你可以：** 写出任意 InvenTag 命令行，并知道哪些参数现在可用。

本页与这一版文档所描述的发行版的 `inventag --help` 一致。运行 `inventag --help` 可查看你已安装的发行版的参数。**状态**列说明我们针对模拟 AWS 离线运行该参数时看到的结果。
“未重新测试”表示我们没有为本页运行它。详情见[功能状态](../getting-started/status.md)。

## 命令 {#commands}

```text
inventag [flags]                       run a scan and write reports
inventag --version                     print the version and exit
inventag templates list [--kind K] [--all]
inventag templates show NAME|PATH [--resolved]
inventag templates init NAME|PATH --output FILE|FOLDER [--name NAME] [--extend] [--force]
inventag templates validate NAME|PATH [NAME|PATH ...]
```

`inventag` 命令在 Linux、macOS 和 Windows 上的用法相同。
`templates` 必须是程序名之后的第一个词。

## 模板 {#templates}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--template NAME\|PATH` | 无 | 可用 | 使用模板。可重复指定，一份报告模板、一份标签策略模板和一份配置模板各一个。见[模板](../templates/index.md)。 |

### `templates` 子命令 {#templates-subcommands}

| 命令 | 功能 |
|---|---|
| `templates list` | 列出模板的类型、来源和说明，以及搜索过的文件夹。`--kind report\|tag-policy\|config` 用于筛选；`--all` 还会显示被同名模板遮住的模板。 |
| `templates show NAME` | 打印该文件。`--resolved` 打印应用 `extends` 和默认值之后的结果。 |
| `templates init NAME --output PATH` | 把模板复制到你的项目中。`--extend` 写出一个继承原模板的简短文件；`--name` 设置名称；`--force` 覆盖已有文件。 |
| `templates validate NAME\|PATH ...` | 检查文件以及它们引用的模板。全部有效时退出码为 0，否则为 1。 |

## 账户 {#accounts}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--accounts-file FILE` | 无 | 可用 | 从 JSON 或 YAML 文件读取账户。见[配置文件](./configuration-files.md#accounts-file)。`--accounts-file` 和 `--accounts-prompt` 只能给一个（否则退出码 2）。 |
| `--accounts-prompt` | 关 | 可用 | 以交互方式询问账户和凭证。 |
| `--cross-account-role ARN\|NAME` | 无 | 可用 | 完整的角色 ARN 会被直接代入；与 `--accounts-file` 或 `--accounts-prompt` 一起使用时以退出码 2 停止。角色名称会与 `--accounts-file` 中的每个账户 ID 组合。只给角色名称而没有 `--accounts-file` 时，会以退出码 2 停止。 |

## 输出 {#output}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--create-excel` | 没有其他输出参数时为开 | 可用 | 写出 `multi_account_bom_<timestamp>.xlsx`。 |
| `--create-word` | 关 | 可用 | 写出 `multi_account_bom_<timestamp>.docx`。 |
| `--create-google-docs` | 关 | 可用（仅限模拟客户端） | 把 Word 报告创建为 Google 文档。需要 Google 附加组件（`pip install "inventag-aws[google]"`）。见 [Google Sheets 和 Docs](../guides/google-sheets-and-docs.md)。 |
| `--create-google-sheets` | 关 | 可用（仅限模拟客户端） | 把 Excel 报告创建为 Google Sheets 电子表格。 |
| `--google-credentials FILE` | 无 | 可用（仅限模拟客户端） | 服务账号密钥文件。不给出时使用应用默认凭证（Application Default Credentials）。 |
| `--google-oauth-client FILE` | 无 | 可用（仅限模拟客户端） | OAuth 客户端文件；你在浏览器中登录。 |
| `--google-folder-id ID` | 无 | 可用（仅限模拟客户端） | 存放文件的 Drive 文件夹。 |
| `--google-share-with EMAIL` | 无 | 可用（仅限模拟客户端） | 与该地址共享。可重复指定以添加更多地址。 |
| `--google-share-role ROLE` | `reader` | 可用（仅限模拟客户端） | `reader`、`commenter` 或 `writer`。 |
| `--google-share-anyone` | 关 | 可用（仅限模拟客户端） | 任何拿到链接的人都可以读取。不加此参数时文件是私有的。 |
| `--google-title TITLE` | 带日期的名称 | 可用（仅限模拟客户端） | Google 文件的标题。 |
| `--output-directory DIR` | `bom_output` | 可用 | 存放所有输出文件的文件夹。 |
| `--per-account-reports` | 关 | 可用 | 每个账户写出一个 `<account-id>_bom_<timestamp>` 文件，而不是一份合并的报告。 |

## 扫描什么 {#what-to-scan}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--account-regions LIST` | 每个已启用的区域 | 可用 | 以逗号分隔的区域代码，例如 `us-east-1,eu-west-1`。IAM、S3 存储桶列表、CloudFront 和 Route 53 始终只从 `us-east-1` 读取一次，因此无需列出它。 |
| `--account-services LIST` | 全部 | 可用 | 以逗号分隔的服务名称，只有这些服务会保留在报告中，与 Service 列匹配，例如 `EC2,S3`。 |
| `--account-tags JSON` | 无 | 可用 | 标签筛选，例如 `'{"Environment":"prod"}'`。只保留带有这些标签的资源。 |
| `--fallback-display auto\|always\|never` | `auto` | 可用 | 是否显示只通过 Resource Groups Tagging API 找到的资源。`auto` 只对自身发现代码没有返回结果的服务显示它们。 |
| `--hide-fallback-resources` | 关 | 未重新测试 | 等同于 `--fallback-display never`。已弃用。 |

## 分析 {#analysis}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--enable-network-analysis` | 关 | 可用 | 找到 VPC 时，在 Excel 报告中添加 `Network Analysis` 工作表。与 `--template` 一起使用时不添加任何内容。见[网络与安全分析](../guides/network-and-security-analysis.md)。 |
| `--enable-security-analysis` | 关 | 可用 | 找到安全组时，在 Excel 报告中添加 `Security Analysis` 工作表。与 `--template` 一起使用时不添加任何内容。 |
| `--enable-cost-analysis` | 关 | 可用 | 在默认工作簿中添加 Cost Analysis 工作表（以及四个 `forgotten_analysis.*` 列）。会额外调用 Cost Explorer、Pricing 和 CloudWatch，即使加了 `--no-billing-validation` 也一样。需要 `pricing:GetProducts` 和 `cloudwatch:GetMetricStatistics`。费用是根据 AWS Pricing API 得出的估算值，不是你的账单。 |
| `--billing-validation`, `--no-billing-validation` | 开 | 可用 | 在发现阶段使用 Cost Explorer 找出有支出的服务。AWS 对每次 Cost Explorer 请求收费。`--no-billing-validation` 会停止这些调用。 |

## 配置文件 {#configuration-files}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--tag-mappings FILE` | 无 | 可用 | 每条映射添加一个命名列。见[配置文件](./configuration-files.md#tag-mappings)。 |
| `--service-descriptions FILE` | 无 | 可用 | 添加 `service_description` 列。你的条目会替换内置描述。见[配置文件](./configuration-files.md#service-descriptions)。 |
| `--bom-config FILE` | 无 | 可用 | 从 YAML 或 JSON 文件设置 BOM 处理配置的字段。其他键会被忽略，并给出指明这些键的警告。类型错误的值会以退出码 1 停止，并指明该键。 |
| `--validate-config` | 关 | 可用 | 加载并检查配置，然后退出。 |
| `--validate-config-only` | 关 | 可用 | 只检查你指定的文件，然后退出。不会进行任何 AWS 调用。 |

## 报告版式文件 {#report-layout-files}

这些参数用一个 YAML 或 JSON 文件改变默认 Excel 和 Word 报告的版式。见[单份报告的版式文件](../templates/layout-flags.md)。

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--word-template PATH` | 无 | 可用 | Word 报告的版式文件。需要 `--create-word`；没有它时运行以退出码 2 停止。 |
| `--excel-template PATH` | 无 | 可用 | Excel 报告的版式文件。只给了 `--create-word` 时，运行以退出码 2 停止。 |
| `--print-default-template word\|excel` | 无 | 可用 | 打印该格式的默认版式文件，然后以退出码 0 退出。 |
| `--validate-templates` | 关 | 可用 | 检查 `--word-template` 和 `--excel-template` 给出的文件，然后退出。不调用 AWS。两个参数都没有时：退出码 2。 |

## 并行处理 {#parallel-processing}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--max-concurrent-accounts N` | `4` | 可用 | 同时扫描的账户数（至少 1）。 |
| `--account-processing-timeout SECONDS` | `1800` | 可用 | 每个账户允许的时间，从该账户开始扫描时算起（至少 60）。超时的账户算作失败；它找到的资源保留在报告中。 |
| `--disable-parallel-processing` | 关 | 可用 | 一次只扫描一个账户。 |
| `--resume` | 关 | 可用 | 复用同一条命令之前未完成的运行中已完成账户的保存结果（相同的账户、区域、服务和筛选条件），只扫描其他账户。与 `--disable-state-management` 一起使用：退出码 2。 |
| `--resume-max-age-hours HOURS` | `24` | 可用 | 与 `--resume` 一起使用时，只复用不超过这个时长的保存结果（最多 168）。 |

## 状态与变更跟踪 {#state-and-change-tracking}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--enable-state-management` | 开 | 可用 | 在 `<output>/state/` 中保存快照。 |
| `--disable-state-management` | 关 | 可用 | 不保存快照和变更日志。 |
| `--enable-delta-detection` / `--disable-delta-detection` | 开 | 可用 | 把新快照与上一份快照比较。`--disable-delta-detection` 不写出变更报告。 |
| `--generate-changelog`, `--no-generate-changelog` | 开 | 可用 | 从第二次运行起写出 `changelog_<timestamp>.md`。`--no-generate-changelog` 会停止写出。 |
| `--state-retention-days N` | `30` | 可用 | 运行保存新快照时，删除超过 N 天的状态快照。`0` 或 `none` 保留任何时长的快照。 |
| `--state-max-snapshots N` | `100` | 可用 | 只保留最新的 N 个状态快照。`0` 或 `none` 保留所有快照。 |

## 可选的退出码 {#opt-in-exit-codes}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--fail-on-account-error` | 关 | 可用 | 有账户未能完整扫描时以退出码 5 结束。报告仍会写出。 |
| `--fail-if-empty` | 关 | 可用 | 没有找到资源或筛选条件把它们全部去掉时，以退出码 6 结束。 |

退出码 5 和 6 优先于 3 和 4。

## 日志 {#logging}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--verbose`, `-v` | 关 | 可用 | 显示每一步。 |
| `--debug`, `-d` | 关 | 可用 | 显示每个 AWS 请求。密钥会被遮蔽。 |
| `--log-file FILE` | 无 | 可用 | 同时把详细日志写入该文件。 |
| `--disable-account-logging` | 关 | 可用 | 不在日志行前加账户前缀。 |

## 凭证 {#credentials}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--validate-credentials` | 关 | 可用 | 检查每个账户的凭证，然后退出（全部可用为 0，否则为 1）。 |
| `--credential-timeout SECONDS` | `30` | 可用 | 登录和凭证检查（包括 AssumeRole）的超时时间。 |
| `--skip-credential-validation` | 关 | 可用 | 在运行开始时跳过凭证检查。 |

## 只读防护与审计 {#read-only-guard-and-audit}

只读防护始终开启。它会阻止每一个不是读取的 AWS 调用，以及会返回密钥或数据的读取调用。

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--audit-output FILE` | 无 | 可用 | 写出一份 JSON 列表，记录本次运行调用的每个 AWS 操作，包括被允许的和被阻止的。 |
| `--validate-operations SERVICE:OPERATION ...` | 无 | 可用 | 对照防护检查这些操作，然后退出（全部允许为 0，否则为 1）。 |
| `--enforce-read-only`, `--security-validation`, `--enable-production-safety` | 开 | 无效果 | 保留这些参数是为了让旧命令仍能运行。防护始终开启。 |
| `--disable-production-safety` | 关 | 以退出码 2 停止 | 防护无法关闭。 |
| `--compliance-standard ...` | 无 | 以退出码 2 停止 | 未实现：无法根据清单检查某个标准。请使用标签策略模板。 |
| `--risk-threshold LEVEL` | 无 | 可用 | 与 `--enable-security-analysis` 一起使用时：如果有安全组规则达到或超过 `LOW`、`MEDIUM`、`HIGH` 或 `CRITICAL`，退出码为 4。没有 `--enable-security-analysis` 时：退出码为 2。 |

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

以退出码 2 停止的参数会打印如下内容：

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)

$ inventag --risk-threshold HIGH
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## S3 上传 {#s3-upload}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--s3-bucket BUCKET` | 无 | 可用 | 把本次运行写出的每个文件（Excel、Word 和标签合规 JSON）上传到该存储桶。上传失败时，运行以退出码 1 结束。需要 `s3:PutObject`。 |
| `--s3-key-prefix PREFIX` | `bom-reports/` | 可用 | 存储桶中的文件夹（键前缀）。文件位于 `<prefix><UTC timestamp>/` 之下。 |
| `--s3-encryption AES256\|aws:kms` | `AES256` | 可用 | 上传文件使用的服务器端加密。 |
| `--s3-kms-key-id KEY` | 无 | 可用 | 用于 `aws:kms` 的 KMS 密钥。不给出时，S3 使用 AWS 托管密钥 `aws/s3`。需要 `--s3-encryption aws:kms`，否则退出码 2。 |

见[按计划把报告上传到 S3](../examples/scheduled-s3-upload.md)。

## 退出码 {#exit-codes}

| 代码 | 含义 |
|---|---|
| 0 | 成功。部分账户失败但其他账户正常，以及没有找到任何资源时，也是 0，除非你传入 `--fail-on-account-error` 或 `--fail-if-empty`。见[功能状态](../getting-started/status.md#when-a-run-goes-wrong)。 |
| 1 | 出错：参数、配置或模板无效，凭证失败，所有账户都失败（包括有些只扫描了一部分），S3 上传失败，或某种报告格式无法写出 |
| 2 | 命令行无效：未知、格式错误或相互冲突的选项，尚未实现的参数，Google 选项有误，版式文件参数缺少它所需的报告，或给了角色名称但没有 `--accounts-file` |
| 3 | 报告已写出，但带有 `fail_on_tag_violations: true` 的配置模板发现了标签策略违规 |
| 4 | 报告已写出，但 `--risk-threshold` 发现有安全组规则达到或超过该级别 |
| 5 | 报告已写出，但有账户未能完整扫描，并且你传入了 `--fail-on-account-error` |
| 6 | 没有可报告的资源，并且你传入了 `--fail-if-empty` |
