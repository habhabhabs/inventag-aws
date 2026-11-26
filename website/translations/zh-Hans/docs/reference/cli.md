---
title: 命令行参考
description: InvenTag 的每个命令和参数、它在当前版本上的行为及默认值，均已对照 inventag --help 核对。
sidebar_position: 1
---

# 命令行参考

**适合谁阅读：** 你需要知道某个参数的确切名称或行为。

**读完后你可以：** 写出任意 InvenTag 命令行，并知道哪些参数现在可用。

本页与这一版文档所描述的发行版的 `inventag --help` 一致。运行 `inventag --help` 可查看你已安装的发行版的参数。**状态**列说明针对模拟 AWS 的离线测试显示的结果。
“未测试”表示还没有测试覆盖该行所述的内容。“仅限模拟的 Google”表示测试使用的是模拟的 Google 客户端。详情见[功能状态](../getting-started/status.md)。

## 命令 {#commands}

```text
inventag [flags]                       run a scan and write reports
inventag --version                     print the version and exit
inventag templates list [--kind K] [--all]
inventag templates show NAME|PATH [--resolved]
inventag templates init NAME|PATH --output FILE|FOLDER [--name NAME] [--extend] [--force]
inventag templates validate NAME|PATH [NAME|PATH ...]
inventag selftest                      check this copy of InvenTag, offline
inventag completion bash|zsh|fish      print a shell completion script
inventag policy validate PATH [PATH ...]
inventag policy list [--policies PATH ...] [--set NAME] [--shipped]
inventag policy schema [FIELD] [--json]
inventag policy test [DIR]
inventag policy check --snapshot FILE [--policies PATH ...] [--set NAME] [--fail-on SEVERITY]
inventag policy explain POLICY --snapshot FILE [--policies PATH ...] [--set NAME]
inventag policy lock [PATH] [--check]
```

`inventag` 命令在 Linux、macOS 和 Windows 上的用法相同。

未针对 Windows 或 macOS 验证：`inventag` 命令的行为与在 Linux 上相同。

`templates`、`selftest`、`completion` 和 `policy` 必须是程序名之后的第一个词。

## 不带选项运行 {#run-without-options}

不带任何选项的 `inventag` 会打印帮助页面（与 `inventag --help` 相同的文本）和一行错误信息，并以退出码 2 结束。它不会开始扫描，也不会发出任何 AWS 调用。请加上 `--create-excel`：`inventag --create-excel` 会运行 v1.5.0 之前 `inventag` 所运行的扫描。

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

### `selftest` 和 `completion` {#selftest-and-completion}

| 命令 | 作用 |
|---|---|
| `selftest` | 检查这份 InvenTag 是否能正常工作：软件包、内置模板、AWS 服务数据、只读保护，以及写入临时文件夹后删除的一个 Excel 文件和一个 Word 文件。它不调用 AWS，不打开网络连接，也不需要凭证。退出码 0：所有检查通过。退出码 1：有检查失败；其他检查仍会运行。退出码 2：未知参数。 |
| `completion bash\|zsh\|fish` | 把 shell 补全脚本输出到标准输出。它只读取命令自身的选项，不调用 AWS，也不打开网络连接。退出码 0。缺少 shell 名或 shell 名未知：显示用法行，退出码 2。 |

安装补全脚本，见 [命令行补全](../getting-started/installation.md#shell-completion)。命令如下：

```text
source <(inventag completion bash)
inventag completion zsh > "${fpath[1]}/_inventag"
inventag completion fish > ~/.config/fish/completions/inventag.fish
```

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
| `--create-google-docs` | 关 | 仅限模拟的 Google | 把 Word 报告创建为 Google 文档。需要 Google 附加组件（`pip install "inventag-aws[google]"`）。见 [Google Sheets 和 Docs](../guides/google-sheets-and-docs.md)。 |
| `--create-google-sheets` | 关 | 仅限模拟的 Google | 把 Excel 报告创建为 Google Sheets 电子表格。 |
| `--google-credentials FILE` | 无 | 仅限模拟的 Google | 服务账号密钥文件。不给出时使用应用默认凭证（Application Default Credentials）。 |
| `--google-oauth-client FILE` | 无 | 仅限模拟的 Google | OAuth 客户端文件；你在浏览器中登录。 |
| `--google-folder-id ID` | 无 | 仅限模拟的 Google | 存放文件的 Drive 文件夹。 |
| `--google-share-with EMAIL` | 无 | 仅限模拟的 Google | 与该地址共享。可重复指定以添加更多地址。 |
| `--google-share-role ROLE` | `reader` | 仅限模拟的 Google | `reader`、`commenter` 或 `writer`。 |
| `--google-share-anyone` | 关 | 仅限模拟的 Google | 任何拿到链接的人都可以读取。不加此参数时文件是私有的。 |
| `--google-title TITLE` | 带日期的名称 | 仅限模拟的 Google | Google 文件的标题。 |
| `--output-directory DIR` | `bom_output` | 可用 | 存放所有输出文件的文件夹。 |
| `--per-account-reports` | 关 | 可用 | 每个账户写出一个 `<account-id>_bom_<timestamp>` 文件，而不是一份合并的报告。 |

未针对真实的 Google 验证：此表中的 Google 参数会创建、共享和输出什么。

## 扫描什么 {#what-to-scan}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--account-regions LIST` | 每个已启用的区域 | 可用 | 以逗号分隔的区域代码，例如 `us-east-1,eu-west-1`。IAM、S3 存储桶列表、CloudFront 和 Route 53 始终只从 `us-east-1` 读取一次，因此无需列出它。 |
| `--account-services LIST` | 全部 | 可用 | 以逗号分隔的服务名称，与 Service 列匹配，例如 `EC2,S3`。只扫描这些服务，报告中也只保留这些服务。 |
| `--account-tags JSON` | 无 | 可用 | 标签筛选，例如 `'{"Environment":"prod"}'`。只保留带有这些标签的资源。 |
| `--fallback-display auto\|always\|never` | `auto` | 可用 | 是否显示只通过 Resource Groups Tagging API 找到的资源。`auto` 只对自身发现代码没有返回结果的服务显示它们。 |
| `--hide-fallback-resources` | 关 | 可用 | 等同于 `--fallback-display never`。已弃用。 |

## 分析 {#analysis}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--finops-cost-allocation` | 关闭 | 可用 | 用每个账户自己的凭证，从 Cost Explorer 读取该账户上个月的支出：按服务、按关联账户，以及按内置 `finops-cost-allocation` 策略中每个已激活的成本分配标签键。在末尾添加一个 `FinOps costs` 工作表。每个账户最多 7 个 Cost Explorer 请求；SDK 的重试会增加请求，AWS 对每个请求收费。需要 `ce:ListCostAllocationTags`。使用 `--template` 时不添加任何内容。见 [FinOps 检查](../guides/finops-checks.md#cost-allocation-from-cost-explorer)。 |
| `--no-cost-in-snapshot` | 关闭 | 可用 | 与 `--finops-cost-allocation` 一起使用：不把成本数字写入状态快照；工作表照常写出。单独使用时只显示一条警告，没有作用。 |
| `--finops-checks` | 关闭 | 可用 | 对扫描找到的资源运行六项 FinOps 检查（`FIN-001` 到 `FIN-006`），并在 Excel 报告末尾添加一个 `FinOps` 工作表。不再发出任何 AWS 调用，不需要额外的权限，其检查结果也不改变退出码，只有一个例外：同时使用 `--template`、`--policy` 和 `--policy-fail-on SEVERITY` 时，FinOps 检查与你的策略一起检查，因此严重级别达到或高于该级别的失败 `FIN-` 发现项会得到退出码 7。使用 `--template` 时不添加工作表：检查在本次运行的状态快照上进行，发现项写入 `policy_findings_<timestamp>.json`；同时使用 `--disable-state-management` 时，会有一条警告说明没有写入任何 FinOps 发现项。见 [FinOps 检查](../guides/finops-checks.md)。 |
| `--enable-network-analysis` | 关 | 可用 | 找到 VPC 时，在 Excel 报告中添加 `Network Analysis` 工作表。与 `--template` 一起使用时不添加任何内容。见[网络与安全分析](../guides/network-and-security-analysis.md)。 |
| `--enable-security-analysis` | 关 | 可用 | 找到安全组时，在 Excel 报告中添加 `Security Analysis` 工作表。与 `--template` 一起使用时不添加任何内容。 |
| `--enable-cost-analysis` | 关 | 可用 | 在默认工作簿中添加 Cost Analysis 工作表（以及四个 `forgotten_analysis.*` 列）。会调用 Cost Explorer、Pricing 和 CloudWatch；`--no-billing-validation` 与它相互独立，不会停止这些调用。 一次运行中的 Cost Explorer 请求：账单验证（默认开启）每个账户最多一次，成本趋势每个账户最多 2 次，每次都使用该账户自己的凭证读取。单账户运行同时使用两者时最多发出 3 次；使用 `--no-billing-validation` 时最多发出 2 次。被限流的请求会重试，总共最多 10 次尝试，每次重试都是一次新的请求。AWS 对每次请求收费。运行会在发现开始前以警告形式说明最多的请求数。需要 `pricing:GetProducts` 和 `cloudwatch:GetMetricStatistics`。费用是根据 AWS Pricing API 得出的估算值，不是你的账单；成本趋势表显示 Cost Explorer 的已计费金额，每个账户和服务一行。见[输出文件](./outputs.md#cost-analysis-sheet)和 [FinOps 检查](../guides/finops-checks.md#the-cost-trend-of---enable-cost-analysis)。 |
| `--billing-validation`, `--no-billing-validation` | 开 | 可用 | 在发现阶段使用 Cost Explorer 找出有支出的服务。AWS 对每次 Cost Explorer 请求收费。详见[Cost Explorer 定价](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。`--no-billing-validation` 会停止这些调用；`--enable-cost-analysis` 与它相互独立，仍会调用 Cost Explorer。 |

未针对真实的 AWS 验证：`--enable-cost-analysis` 只需要这两项额外权限，并且估算值与 AWS 价格一致。

未针对真实的 AWS 验证：AWS 计费的请求次数，以及 AWS 是否对重试计费。

## 策略 {#policies}

策略是描述资源应当是什么样子的文件。InvenTag 读取并报告；策略不会改变账户中的任何内容。下面的参数在扫描之后，对本次运行的状态快照检查策略。`inventag policy` 命令不需要扫描，直接检查已保存的快照（见 [`policy` 子命令](#policy-subcommands)）。

| 参数 | 默认值 | 状态 | 作用 |
|---|---|---|---|
| `--policy PATH` | 无 | 可用 | 策略文件、策略集或文件夹；可重复指定。扫描之后，对本次运行的状态快照检查这些策略，打印摘要（每个策略的计数、按严重程度统计的失败数以及前 10 条发现项；`-v` 会打印全部发现项，文件中总是包含全部发现项），并把 `policy_findings_<timestamp>.json` 写入输出目录。摘要总是会打印；`Policy findings: <path>` 这一行以 INFO 级别记录，因此只在使用 `--verbose` 时显示。也可与 `--template` 一起使用：检查在状态快照上进行，使用模板的运行同样会写出状态快照。无效的策略会在任何 AWS 调用之前以退出码 1 停止运行。与 `--disable-state-management` 一起使用时，运行以退出码 2 停止。 |
| `--policy-waivers FILE` | 无 | 可用 | `--policy` 使用的豁免文件。没有 `--policy`：退出码 2。 |
| `--policy-fail-on SEVERITY` | 无 | 可用 | `info`、`low`、`medium`、`high` 或 `critical`。当有发现项在该严重程度或更高程度失败时，退出码为 7。退出码 5、6、3 和 4 优先。没有 `--policy`：退出码 2。扫描没有对应退出码 8 的参数。 |
| `--policy-format LIST` | `json` | 可用 | 要写出的文件，用逗号分隔：`json`、`sarif`、`junit`、`markdown`。未知格式：退出码 2。没有 `--policy`：退出码 2。见[策略发现项](./outputs.md#policy-findings)。 |

### `policy` 子命令 {#policy-subcommands}

`inventag policy` 读取已保存的状态快照（`state/state_<timestamp>.json`）和策略文件。它不发出任何 AWS 调用，也不需要凭证。`inventag policy COMMAND --help` 会打印某个命令的参数。

| 命令 | 作用 |
|---|---|
| `policy validate PATH ...` | 检查策略、策略集和豁免文件及文件夹，但不做任何评估。每个文件打印一行 `OK`，每个问题打印为 `error: FILE:LINE: FIELD: PROBLEM`。`--now DATE`（`YYYY-MM-DD`，默认为 UTC 的今天）是判断豁免是否过期所用的日期。可能需要很长时间才能匹配的正则表达式（长度可变的重复组，或两个重复之间没有固定内容）算作问题；见[策略文件](./policy-files.md)。退出码 0：没有问题。退出码 1：有问题。退出码 2：没有给出路径。 |
| `policy list` | 列出策略：ID、严重程度、版本、12 个字符的摘要（digest）和文件。`--policies PATH ...` 指定文件或文件夹（默认 `.inventag/policies`）。`--set NAME` 列出一个策略集的成员：先在给定的路径中找，找不到则用随 InvenTag 提供的策略集。`--shipped` 列出随 InvenTag 提供的策略集及各自的策略数（不能与 `--set` 同用：退出码 2）。退出码 0；文件无法读取或策略集未知时为 1。 |
| `policy schema [FIELD]` | 打印策略文件的字段及其规则；给出字段名时，打印该字段的帮助。`--json` 打印供编辑器使用的 JSON Schema（比 `policy validate` 宽松：最终以 `validate` 为准）。退出码 0；字段未知时为 1。 |
| `policy test [DIR]` | 运行策略文件夹（默认 `.inventag/policies`）下 `tests/<policy name>/*.yaml` 中的测试用例（fixture），每个用例打印一行 `PASS` 或 `FAIL`，最后打印计数。没有测试用例的策略会收到警告。退出码 0：所有预期都成立。退出码 1：有用例失败或无效。 |
| `policy check --snapshot FILE` | 对快照评估策略并报告。`--policies PATH ...`（默认 `.inventag/policies`）、`--set NAME`（只用该策略集：先在给定路径中找，找不到则用随附的）、`--waivers FILE`、`--baseline FILE`（较早的快照，用于基线检查）、`--now DATE`、`--show-values`（显示未通过检查的值；被屏蔽的值仍然屏蔽）、`--locked`（拒绝与 `policy.lock` 不一致的策略文件）。`--format LIST` 用逗号分隔：`text`（默认；输出到屏幕，不写文件）、`json`、`sarif`、`junit` 和 `markdown`（写成文件，位于 `--output-directory`，默认当前文件夹）。`--fail-on SEVERITY` 在有发现项于该严重程度或更高程度失败时给出退出码 7；`--fail-on-not-evaluated` 在有内容无法评估时给出退出码 8。不带这两个参数时，命令只报告并以退出码 0 结束。退出码：0、1（文件无效或无法读取；不写出任何内容）、2（选项无效；不写出任何内容）、7、8（8 优先于 7）。 |
| `policy explain POLICY --snapshot FILE` | 显示一条策略如何对每一行做出判定：结果、起决定作用的每项检查，以及策略各部分及其判定的 `trace:`。`--resource ARN` 只看一个资源。`--policies`、`--set`、`--baseline`、`--now` 和 `--show-values` 与 `check` 相同。退出码 0 或 1。 |
| `policy lock [PATH]` | 在策略文件夹（默认 `.inventag/policies`）中写入 `policy.lock`：每个策略、策略集和豁免文件的 SHA-256 摘要。`--check` 只检查锁文件是否是最新的。退出码 0 或 1。 |

未针对真实 AWS 验证：真实账户生成的快照。测试使用的是由模拟账户生成的快照和手写的行。

## 配置文件 {#configuration-files}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--tag-mappings FILE` | 无 | 可用 | 每条映射添加一个命名列。见[配置文件](./configuration-files.md#tag-mappings)。 |
| `--service-descriptions FILE` | 无 | 可用 | 添加 `service_description` 列。你的条目会替换内置描述。见[配置文件](./configuration-files.md#service-descriptions)。 |
| `--bom-config FILE` | 无 | 可用 | 从 YAML 或 JSON 文件设置 BOM 处理配置的字段。其他键会被忽略，并给出指明这些键的警告。类型错误的值会以退出码 1 停止，并指明该键。 |
| `--validate-config` | 关 | 可用 | 加载并检查配置，然后退出。 |
| `--validate-config-only` | 关 | 可用 | 检查 `--accounts-file`、`--tag-mappings` 和 `--service-descriptions`，然后退出。不会读取 `--bom-config`。不会进行任何 AWS 调用。 |

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
| `--concurrency N` | `64` | 可用 | 整个运行中同时进行的 AWS 请求的最大数量（1 到 256）。1 表示一次只发送一个请求。超出 1 到 256 的值，或不是整数的值：退出码 2。在配置模板中：`spec.concurrency`。见[并发](../guides/run-a-scan.md#concurrency)。 |
| `--account-processing-timeout SECONDS` | `1800` | 可用 | 每个账户允许的时间，从该账户开始扫描时算起（至少 60）。超时的账户算作失败；它找到的资源保留在报告中。 |
| `--disable-parallel-processing` | 关 | 可用 | 一次只扫描一个账户。它不改变账户内部的线程。 |
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
| `--fail-on-account-error` | 关 | 可用 | 有账户无法扫描或超出时限时，以退出码 5 结束。报告仍会写出。不带该参数时，这样的运行以退出码 0 结束，除非所有账户都失败。 |
| `--fail-if-empty` | 关 | 可用 | 没有找到资源或筛选条件把它们全部去掉时，以退出码 6 结束。 |

如果同时满足多个条件，先是 5，然后是 6，然后是 3，最后是 4。退出码 7（使用 `--policy-fail-on` 时）只在上述都不适用时出现。退出码 3、4、5 和 7 会写出报告。
对于退出码 6，带 `--template` 的运行会写出一份不列出任何资源的报告，不带 `--template` 的运行则不写文件。

## 日志 {#logging}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--verbose`, `-v` | 关 | 可用 | 显示每一步（INFO）。给两次（`-vv`）可得到调试输出，与 `--debug` 相同。 |
| `--debug`, `-d` | 关 | 可用 | 显示调试输出和每一个 AWS 请求，与 `-vv` 相同。密钥会被遮蔽；仍应把输出视为敏感信息。 |
| `--log-file FILE` | 无 | 可用 | 同时把日志写入该文件：与终端相同的行，另带函数名和行号。加上 `-v` 或 `-vv` 可看到更多。 |
| `--disable-account-logging` | 关 | 可用 | 不在日志行前加账户前缀。 |

在 CI/CD 运行中，请使用 `-vv`。调试输出包含账户 ID、ARN、IP 地址、标签值，以及 AWS SDK 完整的请求和响应正文。机密会被遮盖；已知的缺口列在[功能状态](../getting-started/status.md#security-notes)中。在公开仓库中，作业日志是公开的，因此请在那里使用 `-v`。在其他情况下，请限制谁可以读取作业日志，并且不要把调试日志作为产物上传。

## 凭证 {#credentials}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--validate-credentials` | 关 | 可用 | 按扫描使用凭证的方式检查每个账户的凭证（对于其他账户中没有凭证的条目，使用跨账户角色），然后退出（全部可用为 0，否则为 1）。 |
| `--credential-timeout SECONDS` | `30` | 可用 | 登录和凭证检查（包括 AssumeRole）的超时时间。 |
| `--skip-credential-validation` | 关 | 可用 | 在运行开始时跳过凭证检查。 |

## 只读防护与审计 {#read-only-guard-and-audit}

只读防护始终开启。它会阻止每一个不是读取的 AWS 调用，以及会返回密钥或数据的读取调用。

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--audit-output FILE` | 无 | 可用 | 写出一份 JSON 列表，记录本次运行调用的每个 AWS 操作，包括被允许的和被阻止的。当运行无权使用某个 IAM 操作时，该文件还会有列表 `permissions_denied`：见[仅使用 ReadOnlyAccess 运行](../guides/read-only-access.md#run-with-only-readonlyaccess)。 |
| `--validate-operations SERVICE:OPERATION ...` | 无 | 可用 | 对照防护检查这些操作，然后退出（全部允许为 0，否则为 1）。 |
| `--enforce-read-only`, `--security-validation`, `--enable-production-safety` | 开 | 无效果 | 保留这些参数是为了让旧命令仍能运行。防护始终开启。 |
| `--disable-production-safety` | 关 | 以退出码 2 停止 | 防护无法关闭。 |
| `--compliance-standard ...` | 无 | 以退出码 2 停止 | 未实现：无法根据清单检查某个标准。请使用标签策略模板。 |
| `--risk-threshold LEVEL` | 无 | 可用 | 与 `--enable-security-analysis` 一起使用时：如果有安全组规则达到或超过 `LOW`、`MEDIUM`、`HIGH` 或 `CRITICAL`，退出码为 4。没有 `--enable-security-analysis` 时：退出码为 2。 |

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

以退出码 2 停止的参数会打印如下内容（第一个示例来自没有安装 Google 库的机器）：

```bash title="Terminal"
inventag --create-google-docs
```

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)
```

```bash title="Terminal"
inventag --risk-threshold HIGH
```

```text title="输出"
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)
```

```bash title="Terminal"
inventag --compliance-standard soc2
```

```text title="输出"
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour. InvenTag does not assess compliance. To check your tags against a built-in baseline, run: inventag --template security-baseline --create-excel
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="输出"
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked. Remove this option; nothing else is needed. To see which calls are allowed, run: inventag --validate-operations ec2:DescribeInstances
(exit code 2)
```

## S3 上传 {#s3-upload}

| 参数 | 默认值 | 状态 | 功能 |
|---|---|---|---|
| `--s3-bucket BUCKET` | 无 | 可用 | 把本次运行写出的每个文件（Excel、Word 和标签合规 JSON）上传到该存储桶。上传失败时，运行以退出码 1 结束。需要 `s3:PutObject`。 |
| `--s3-key-prefix PREFIX` | `bom-reports/` | 可用 | 存储桶中的文件夹（键前缀）。文件位于 `<prefix><UTC timestamp>/` 之下。 |
| `--s3-encryption AES256\|aws:kms` | `AES256` | 可用 | 上传文件使用的服务器端加密。 |
| `--s3-kms-key-id KEY` | 无 | 可用 | 用于 `aws:kms` 的 KMS 密钥。不给出时，S3 使用 AWS 托管密钥 `aws/s3`。需要 `--s3-encryption aws:kms`，否则退出码 2。 |

未针对真实的 AWS 验证：上传只需要 `s3:PutObject`（使用 `aws:kms` 时还需要 `kms:GenerateDataKey`）。

未针对 AWS 验证：`aws:kms` 没有密钥 ID 时，S3 是否使用 AWS 托管密钥 `aws/s3`。

见[按计划把报告上传到 S3](../examples/scheduled-s3-upload.md)。

## 退出码 {#exit-codes}

| 代码 | 含义 |
|---|---|
| 0 | 成功。部分账户失败但其他账户正常，以及没有找到任何资源时，也是 0，除非你传入 `--fail-on-account-error` 或 `--fail-if-empty`。见[功能状态](../getting-started/status.md#when-a-run-goes-wrong)。 |
| 1 | 出错：参数、配置或模板无效，数值超出范围（例如 `--max-concurrent-accounts 0`），凭证失败，所有账户都失败（无法扫描或超出时限），S3 上传失败，或某种报告格式无法写出 |
| 2 | 命令行无效：未知、格式错误或相互冲突的选项，超出 1 到 256 的 `--concurrency` 值，尚未实现的参数，Google 选项有误，版式文件参数缺少它所需的报告，或给了角色名称但没有 `--accounts-file`，或完全没有选项（单独的 `inventag` 会打印帮助页面） |
| 3 | 报告已写出，但带有 `fail_on_tag_violations: true` 的配置模板发现了标签策略违规 |
| 4 | 报告已写出，但 `--risk-threshold` 发现有安全组规则达到或超过该级别 |
| 5 | 报告已写出，但有账户无法扫描或超出时限，并且你传入了 `--fail-on-account-error` |
| 6 | 没有可报告的资源，并且你传入了 `--fail-if-empty` |
| 7 | 有策略发现项在你给出的严重程度或更高程度失败：扫描中用 `--policy-fail-on`，或 `inventag policy check` 的 `--fail-on`。在扫描中，7 只在 5、6、3 和 4 都不适用时出现。发现项文件会写出。 |
| 8 | 仅来自带 `--fail-on-not-evaluated` 的 `inventag policy check`：有内容无法评估。8 优先于 7。扫描从不以 8 结束。发现项文件会写出。 |
