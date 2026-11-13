---
title: 模板参考
description: InvenTag 模板的每个字段（report、tag-policy 和 config），包括类型、默认值以及各自的作用。
sidebar_position: 4
---

# 模板参考

**适合谁阅读：** 你正在编写或审查模板，需要某个字段的确切名称、类型或默认值。

**读完后你可以：** 不用猜测就能写出任何模板，并有把握地读懂验证错误。

## 文件结构 {#file-layout}

每个模板都是一个 YAML 文件，顶层字段相同：

```yaml
format_version: 1          # optional; 1 is the only version
kind: report               # report | tag-policy | config
name: acme-bom             # lower-case letters, digits and hyphens
description: One sentence shown by 'templates list'
extends: standard-bom      # optional: a template name or a relative path
spec:                      # the settings for this kind
  title: Acme Cloud Inventory
```

- 文件以 `.yaml` 或 `.yml` 结尾，必须是 UTF-8 文本，最大 256 KiB。
- 文件名应与 `name` 一致（`acme-bom.yaml` 的 `name: acme-bom`）。按名称查找时使用文件名。
- 未知字段是错误，因此拼写错误不会被悄悄放过。
- 重复的键是错误。
- 账户 ID 和十六进制颜色要放在引号中（`"012345678901"`、`"1F3A5F"`），
  这样 YAML 会把它们保留为文本。

## 对其他文件的引用 {#references-to-other-files}

`extends`、`tag_policy`、`report_template` 和 `logo` 可以指向另一个文件：

- **名称**（`standard-bom`）会在[搜索文件夹](./index.md#where-inventag-looks-for-templates)中查找。
- **相对路径**（`./policies/strict.yaml`）相对于包含它的模板，并且必须位于该模板所在的文件夹之内。
  离开该文件夹的 `..`、绝对路径、`~` 和 URL 都会被拒绝。

## 字段参考 {#field-reference}

本节由代码生成
（`python -m inventag.templating.reference --write`），因此始终与验证器接受的内容一致。

### 所有模板中的字段 {#fields-in-every-template}

| 字段 | 类型 | 默认值 | 作用 |
|---|---|---|---|
| `format_version` | 整数（最小 1，最大 1） | `1` | 模板格式版本。目前只有 `1`。 |
| `kind` | `report`、`tag-policy`、`config` 之一 | 必填 | 模板控制什么：`report`、`tag-policy` 或 `config`。 |
| `name` | 模板名称 | 必填 | 小写字母、数字和连字符。应与文件名一致（`my-report.yaml` 的 `name: my-report`）。 |
| `description` | 文本 | 空 | 由 `templates list` 显示的一句话。 |
| `extends` | 模板名称或相对路径 | 未设置 | 要继承的模板，按名称或相对路径指定。必须是同一种 kind。 |
| `spec` | 映射 | 必填 | 该 kind 的设置（见下文）。 |

### 报告模板（`kind: report`） {#report-templates-kind-report}

| 字段 | 类型 | 默认值 | 作用 |
|---|---|---|---|
| `spec.title` | 文本 | `AWS Resource Inventory` | 报告标题，用于 Word 封面和 Excel 摘要工作表。 |
| `spec.subtitle` | 文本 | 空 | 标题下方的可选一行。 |
| `spec.company_name` | 文本 | 空 | 显示在封面上并存入文件属性的组织名称。 |
| `spec.colors` | 映射 | 见下文 | 表头颜色，六位十六进制值（带或不带 `#`）。 |
| `spec.logo` | 相对文件路径 | 未设置 | 显示在 Word 封面上的图像（PNG、JPEG、GIF 或 BMP）。路径相对于模板文件，并且必须位于其文件夹之内。 |
| `spec.logo_alt_text` | 文本 | 空 | 徽标的替代文本，供屏幕阅读器朗读。默认为 `<company_name> logo`。 |
| `spec.columns` | 映射列表 | 见内置的 `standard-bom` | 资源表的列，按顺序排列。 |
| `spec.tag_columns` | `all`、`none` 或标签键列表 | `all` | 额外的列，每个标签键一列，添加在 `columns` 之后。可以是标签键列表，或 `all`（该表中资源上找到的每个标签键），或 `none`。 |
| `spec.tag_policy` | 模板名称或相对路径 | 未设置 | 要检查的标签策略，按名称或相对路径指定。命令行上带标签策略的 `--template` 优先。 |
| `spec.excel` | 映射 | 见下文 | Excel 工作簿版式。 |
| `spec.word` | 映射 | 见下文 | Word 文档版式。 |
| `spec.colors.header_fill` | 十六进制颜色 | `1F3A5F` | 表头行的背景。 |
| `spec.colors.header_text` | 十六进制颜色 | `FFFFFF` | 表头行的文字颜色。 |
| `spec.columns[].field` | 文本 | 必填 | 要显示的资源字段。嵌套值用点表示：`tags.Owner` 是 `Owner` 标签，`raw_data.InstanceType` 是 AWS API 响应中的值。 |
| `spec.columns[].header` | 文本 | 未设置 | 列标题。默认是用普通词语写出的字段名（`resource_name` 变为 `Resource name`）。 |
| `spec.columns[].width` | 整数（最小 4，最大 120） | 未设置 | Excel 列宽，以字符数计。默认是适合内容的宽度，上限为 `excel.max_column_width`。 |
| `spec.excel.summary_sheet` | true 或 false | `true` | 添加一个 Summary 工作表，列出每个服务的资源数量。 |
| `spec.excel.layout` | `per-service`、`single-sheet` 之一 | `per-service` | `per-service` 把每个服务放在各自的工作表上。`single-sheet` 把所有资源放在一个带 Service 列的工作表上。 |
| `spec.excel.single_sheet_name` | 文本 | `Resources` | `layout` 为 `single-sheet` 时的工作表名称。 |
| `spec.excel.include_all_fields` | true 或 false | `false` | 在列出的列之后，同时添加资源上找到的所有其他字段。对审计有用；会让工作表变宽。 |
| `spec.excel.freeze_header` | true 或 false | `true` | 滚动时保持表头行可见。 |
| `spec.excel.autofilter` | true 或 false | `true` | 在表头行添加筛选按钮。 |
| `spec.excel.max_column_width` | 整数（最小 10，最大 120） | `50` | 自动列宽的上限，以字符数计。 |
| `spec.excel.tag_compliance_sheet` | true 或 false | `true` | 启用标签策略时添加 Tag Compliance 工作表。 |
| `spec.word.orientation` | `portrait`、`landscape` 之一 | `portrait` | 页面方向。 |
| `spec.word.sections` | 取自 `cover`、`summary`、`service-summary`、`tag-compliance`、`service-tables`、`about` 的值列表 | `["cover", "summary", "service-summary", "tag-compliance", "service-tables", "about"]` | 要包含的章节，按顺序排列。可选值：`cover`、`summary`、`service-summary`、`tag-compliance`、`service-tables`、`about`。没有启用标签策略时会跳过 `tag-compliance`。 |
| `spec.word.columns` | 映射列表 | 未设置 | 每个服务表的列。默认是 `columns` 的前 `max_columns` 项。不会添加标签列。 |
| `spec.word.max_columns` | 整数（最小 1，最大 12） | `6` | 未设置 `word.columns` 时使用 `columns` 中的多少列。Word 表格超过六七列就难以阅读。 |
| `spec.word.max_rows_per_service` | 整数（最小 1，最大 10000） | `50` | 每个服务表显示的行数。会有一条说明指出省略了多少行。 |
| `spec.word.max_noncompliant_rows` | 整数（最小 1，最大 10000） | `100` | 不合规资源表中显示的行数。 |
| `spec.word.columns[].field` | 文本 | 必填 | 要显示的资源字段。嵌套值用点表示：`tags.Owner` 是 `Owner` 标签，`raw_data.InstanceType` 是 AWS API 响应中的值。 |
| `spec.word.columns[].header` | 文本 | 未设置 | 列标题。默认是用普通词语写出的字段名（`resource_name` 变为 `Resource name`）。 |
| `spec.word.columns[].width` | 整数（最小 4，最大 120） | 未设置 | Excel 列宽，以字符数计。默认是适合内容的宽度，上限为 `excel.max_column_width`。 |

### 标签策略模板（`kind: tag-policy`） {#tag-policy-templates-kind-tag-policy}

| 字段 | 类型 | 默认值 | 作用 |
|---|---|---|---|
| `spec.required_tags` | 映射列表 | 必填 | 范围内的资源必须具有的标签。当一个模板 `extends` 另一个模板时，条目按 `key` 合并：相同的键会替换，新键会添加，`remove: true` 会删除一个。 |
| `spec.scope` | 映射 | 见下文 | 策略适用于哪些资源。范围之外的资源会被计数但不会被检查。 |
| `spec.required_tags[].key` | 文本 | 必填 | 标签键。AWS 标签键区分大小写，因此 `costcenter` 不能满足 `CostCenter`。 |
| `spec.required_tags[].description` | 文本 | 空 | 该标签存在的原因。显示在报告中。 |
| `spec.required_tags[].allowed_values` | 文本列表 | 未设置 | 如果设置，标签值必须是其中之一。 |
| `spec.required_tags[].case_sensitive` | true 或 false | `false` | 对 `allowed_values` 区分大小写地比较。 |
| `spec.required_tags[].pattern` | 正则表达式 | 未设置 | 如果设置，整个标签值必须匹配此正则表达式（Python 语法）。 |
| `spec.required_tags[].remove` | true 或 false | `false` | 在 `extends` 另一个模板的模板中，从继承的列表中删除此标签。 |
| `spec.scope.services` | 文本列表 | `[]` | 只检查这些服务（与报告中显示的一致，例如 `EC2`、`S3`）。为空表示所有服务。 |
| `spec.scope.resource_types` | 文本列表 | `[]` | 只检查这些资源类型（例如 `Bucket`、`Instance`）。为空表示所有类型。 |
| `spec.scope.exclude_resource_types` | 文本列表 | `[]` | 从不检查这些资源类型，例如无法携带标签的类型。 |

### config 模板（`kind: config`） {#config-templates-kind-config}

| 字段 | 类型 | 默认值 | 作用 |
|---|---|---|---|
| `spec.accounts` | 映射列表 | 未设置 | 要扫描的账户。省略则扫描你当前 AWS 凭证所属的账户。每个账户需要 `profile_name` 或 `role_arn`。 |
| `spec.regions` | 文本列表 | 未设置 | 要扫描的区域（`--account-regions`）。省略则扫描每个已启用的区域。 |
| `spec.services` | 文本列表 | 未设置 | 要包含的服务（`--account-services`）。目前只在一条发现路径中生效，因此其他服务仍可能出现。 |
| `spec.outputs` | 取自 `excel`、`word` 的值列表 | `["excel"]` | 要生成的文件（`--create-excel`、`--create-word`）。 |
| `spec.output_directory` | 文本 | `bom_output` | 报告所在的文件夹（`--output-directory`）。 |
| `spec.report_template` | 模板名称或相对路径 | `standard-bom` | 要使用的报告模板，按名称或相对路径指定。 |
| `spec.tag_policy` | 模板名称或相对路径 | 未设置 | 要检查的标签策略，按名称或相对路径指定。 |
| `spec.fail_on_tag_violations` | true 或 false | `false` | 如果任何范围内的资源违反标签策略，则在写出报告后以退出码 3 结束。需要 `tag_policy`。 |
| `spec.max_concurrent_accounts` | 整数（最小 1，最大 64） | `4` | 同时扫描的账户数（`--max-concurrent-accounts`）。 |
| `spec.account_processing_timeout` | 整数（最小 60） | `1800` | 每个账户允许的秒数（`--account-processing-timeout`）。 |
| `spec.parallel_processing` | true 或 false | `true` | 并行扫描账户。`false` 等同于 `--disable-parallel-processing`。 |
| `spec.accounts[].account_id` | 文本 | 必填 | 12 位 AWS 账户 ID，放在引号中，以便 YAML 保留前导零。 |
| `spec.accounts[].account_name` | 文本 | 空 | 报告中使用的易读名称。 |
| `spec.accounts[].profile_name` | 文本 | 未设置 | 此账户使用的 AWS CLI 配置文件。 |
| `spec.accounts[].role_arn` | 文本 | 未设置 | 在此账户中要代入的 IAM 角色，使用完整 ARN。 |
| `spec.accounts[].external_id` | 文本 | 未设置 | 角色的信任策略所要求的外部 ID。 |
| `spec.accounts[].regions` | 文本列表 | 未设置 | 在此账户中要扫描的区域。覆盖 `spec.regions`。 |
| `spec.accounts[].services` | 文本列表 | 未设置 | 在此账户中要扫描的服务。 |

## 可用作列的资源字段 {#resource-fields-you-can-use-as-columns}

列的 `field` 会从每个资源读取一个值。正常运行产生的资源上都有这些字段：

| 字段 | 包含 |
|---|---|
| `service` | 报告中显示的服务名称，例如 `S3`、`EC2`、`VPC` |
| `resource_type` | 例如 `Bucket`、`Volume`、`Subnet` |
| `resource_name` | 名称（如果资源有名称） |
| `resource_id` | 资源的 ID |
| `arn` | Amazon Resource Name（如果已知） |
| `region` | 区域代码 |
| `source_account_id` | 发现该资源所在的账户 |
| `source_account_name` | 你给该账户设置的 `account_name` |
| `tags` | 所有标签，写成 `Key=Value, Key=Value` |
| `tags.<Key>` | 单个标签的值，例如 `tags.Owner` |
| `tagged` | `Yes` 或 `No` |
| `discovered_via` | 由哪个 API 发现了该资源 |
| `raw_data.<Name>` | AWS API 响应中的值，例如 `raw_data.VolumeType` |

缺失的值留空。要查看你的资源有哪些字段，请设置 `excel.include_all_fields: true`，然后查看多出来的列。

## 验证消息 {#validation-messages}

`inventag templates validate <file>` 以及每个带 `--template` 的运行，都会按以下格式打印问题：

```text
<file>:<line>: <field>: <what is wrong>
```

例如，一个带有 `header_fill: blue` 的模板在运行中被使用：

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
$ echo $?
1
```

以及拼错的模板名称：

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
$ echo $?
1
```

当一个模板 `extends` 另一个模板时，问题会针对包含它们的文件报告。

## 退出码 {#exit-codes}

| 命令 | 代码 | 含义 |
|---|---|---|
| `templates validate` | 0 | 每个文件都有效 |
| `templates validate` | 1 | 至少有一个文件有问题 |
| `templates init` | 1 | 输出文件已存在（使用 `--force`），或模板无效 |
| `templates init` | 2 | 输出名称或扩展名不被允许 |
| `inventag --template ...` | 1 | 模板无效，或运行失败 |
| `inventag --template ...` | 3 | 报告已写出，但资源违反标签策略，且 `fail_on_tag_violations` 为 `true` |
| `inventag --template ...` | 5 | 报告已写出，但有账户失败或只扫描了一部分，且你传入了 `--fail-on-account-error` |
| `inventag --template ...` | 6 | 没有找到任何资源，且你传入了 `--fail-if-empty` |
