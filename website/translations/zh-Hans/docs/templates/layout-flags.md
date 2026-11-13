---
title: 单份报告的版式文件
description: 用 YAML 或 JSON 模板文件修改 Word 和 Excel BOM 报告的标题、章节、工作表、列、页眉和页脚。
sidebar_position: 5
---

# 单份报告的版式文件

本页介绍 `--word-template` 和 `--excel-template` 参数。每个参数接收一个版式文件，
对应一种报告格式。关于用 `--template` 选择的命名模板，请参阅[模板](./index.md)。

报告模板是一个 YAML 或 JSON 文件。模板控制 Word 报告或 Excel 报告的结构。
用 `--word-template` 或 `--excel-template` 把文件交给 CLI。

如果不提供模板，InvenTag 使用内置的默认模板。此时报告的结构与没有模板功能的版本相同。

## 模板可以修改什么 {#what-a-template-can-change}

| 项目 | Word 报告 | Excel 报告 |
|---|---|---|
| 标题和副标题 | 文档的标题部分 | 工作簿属性，以及摘要表上方的可选行 |
| 公司名称 | `{{ company_name }}` 的值 | `{{ company_name }}` 的值，以及工作簿的创建者属性 |
| 徽标 | 标题上方的 PNG 或 JPEG 文件 | 不可用 |
| 章节或工作表 | 显示哪些章节及其顺序 | 显示哪些工作表及其顺序 |
| 列 | 显示哪些列，以及它们的顺序、标题和宽度 | 显示哪些列，以及它们的顺序、标题和宽度 |
| 服务 | 资源表中出现哪些服务及其顺序 | 哪些服务有工作表及其顺序 |
| 页眉和页脚 | 页眉、页脚、页码 | 每个工作表的打印页眉和打印页脚 |
| 表头行颜色 | 不可用 | 表头行的填充颜色 |
| 自由文本 | 带变量的标题和段落 | 不可用 |

## 制作模板 {#make-a-template}

1. 把默认模板打印到文件。

   ```bash
   inventag --print-default-template word > my_word_template.yaml
   inventag --print-default-template excel > my_excel_template.json
   ```

2. 编辑文件。参见[键参考](#key-reference)。

3. 验证文件。此命令不会发出任何 AWS 调用。

   ```bash
   inventag --validate-templates \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

   如果文件有效，CLI 会为每个文件打印一行 `OK`，并以退出码 `0` 结束。

4. 在运行中使用该文件。

   ```bash
   inventag --create-word --create-excel \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

CLI 接受 `.yaml`、`.yml` 和 `.json` 这几种文件扩展名，两种格式均适用。默认模板文件也在仓库中：
`templates/default_word_template.yaml` 和
`templates/default_excel_template.json`。

## 模板参数 {#template-flags}

| 参数 | 功能 |
|---|---|
| `--word-template PATH` | Word 报告的模板。此参数需要 `--create-word`。 |
| `--excel-template PATH` | Excel 报告的模板。此标志需要 `--create-excel`。没有它，CLI 会以退出码 `2` 停止。 |
| `--print-default-template word` 或 `--print-default-template excel` | 打印默认模板并以退出码 `0` 结束。 |
| `--validate-templates` | 验证 `--word-template` 和 `--excel-template` 指定的文件，然后结束。不发出 AWS 调用。 |

## 最小示例 {#minimal-examples}

这个 Word 模板包含一个标题、每个服务一张资源表，以及一张摘要表。

```yaml title="my_word_template.yaml"
template_version: "2.0"
format_type: word
document:
  title: "{{ company_name }} Cloud Inventory"
  subtitle: "Accounts: {{ account_ids }}"
branding:
  company_name: Example Corp
header_footer:
  header_text: "{{ company_name }} - Internal"
  footer_text: "Generated {{ generated_date }}"
  include_page_numbers: true
sections:
  - id: title
    content_type: title
  - id: inventory
    content_type: resources
    title: Resources
    service_title: "{{ service }} ({{ service_resource_count }})"
    columns:
      - field: name
        heading: Resource name
        width: 2.5
      - field: region
      - field: tags.Owner
        heading: Owner
  - id: summary
    content_type: service_summary
    title: "Summary of {{ total_resources }} resources"
```

这个 Excel 模板包含一个列出所有资源的工作表，然后是摘要工作表。

```json title="my_excel_template.json"
{
  "template_version": "2.0",
  "format_type": "excel",
  "document": {"title": "{{ company_name }} inventory"},
  "branding": {"company_name": "Example Corp", "header_color": "1F4E78"},
  "sections": [
    {
      "id": "all_resources",
      "content_type": "resources",
      "group_by_service": false,
      "sheet_name": "All resources",
      "columns": [
        {"field": "service", "heading": "Service", "width": 14},
        {"field": "name", "heading": "Name"},
        {"field": "region", "heading": "Region"},
        {"field": "tags.Owner", "heading": "Owner"}
      ]
    },
    {
      "id": "summary",
      "content_type": "service_summary",
      "sheet_name": "Summary",
      "show_title": true
    }
  ]
}
```

## 变量 {#variables}

在文本值中把变量写成 `{{ name }}`。InvenTag 在写入报告时用变量的值替换它。

| 变量 | 值 |
|---|---|
| `{{ company_name }}` | `branding.company_name` 的值。 |
| `{{ document_title }}` | 替换之后的 `document.title` 的值。 |
| `{{ document_subtitle }}` | 替换之后的 `document.subtitle` 的值。 |
| `{{ generated_at }}` | UTC 生成时间，格式为 `YYYY-MM-DD HH:MM:SS`。 |
| `{{ generated_date }}` | UTC 生成日期，格式为 `YYYY-MM-DD`。 |
| `{{ account_ids }}` | 报告中的账户 ID，已排序，以逗号加空格分隔。 |
| `{{ account_count }}` | 报告中不同账户 ID 的数量。 |
| `{{ total_resources }}` | 报告中的资源数量。 |
| `{{ service_count }}` | 报告中不同服务的数量。 |
| `{{ region_count }}` | 报告中不同区域的数量。 |

下面这些变量只在 Word `resources` 章节的 `service_title` 和 `truncation_note` 中有效：

| 变量 | 值 |
|---|---|
| `{{ service }}` | 当前表格的服务名称。 |
| `{{ service_resource_count }}` | 当前服务的资源数量。 |
| `{{ shown_resource_count }}` | 当前表格中的行数。 |

你可以在 `variables` 下定义自己的变量：

```yaml
variables:
  classification: Internal
header_footer:
  footer_text: "Classification: {{ classification }}"
```

变量规则：

- 变量名只能包含字母、数字和下划线。
- 自定义变量的名称以小写字母开头，只能包含小写字母、数字和下划线。
- 自定义变量不能使用内置变量的名称。
- 变量的值是纯文本。值中不能包含另一个变量。
- `document.title` 和 `document.subtitle` 不能使用 `{{ document_title }}`
  或 `{{ document_subtitle }}`。
- 以下键接受变量：`document.title`、`document.subtitle`、
  `header_footer.header_text`、`header_footer.footer_text`，以及章节键
  `title`、`paragraphs`、`service_title` 和 `truncation_note`。
- 列标题、工作表名称和 `branding.company_name` 不接受变量。
- InvenTag 不支持表达式、过滤器、条件、循环或文件包含。例如，`{{ company_name | upper }}` 是错误。
- InvenTag 不会替换资源数据中的变量。名称中含有文本 `{{ company_name }}` 的资源，
  在报告中保持原样。

## 键参考 {#key-reference}

`tests/unit/test_template_system.py` 中的一个测试会确保本参考包含
`inventag/reporting/report_template.py` 中模式的每一个键。

### 顶层键 {#top-level-keys}

| 键 | 类型 | 格式 | 默认值 | 说明 |
|---|---|---|---|---|
| `template_version` | 字符串 | Word 和 Excel | 必填 | 模式版本。必须是 `"2.0"`。 |
| `format_type` | 字符串 | Word 和 Excel | 必填 | `word` 或 `excel`。 |
| `name` | 字符串 | Word 和 Excel | 空 | 模板的名称。不会显示在报告中。 |
| `description` | 字符串 | Word 和 Excel | 空 | 说明。不会显示在报告中。 |
| `document` | 映射 | Word 和 Excel | 见下文 | 标题和副标题。 |
| `branding` | 映射 | Word 和 Excel | 见下文 | 公司名称、徽标和颜色。 |
| `variables` | 映射 | Word 和 Excel | 空 | 你自己的变量：名称对应文本。 |
| `extra_fields` | 列表 | Word 和 Excel | 空 | `columns` 可以使用的更多资源字段名。例如，来自你的标签映射的列。 |
| `header_footer` | 映射 | Word 和 Excel | 见下文 | 页眉和页脚文本。 |
| `sections` | 列表 | Word 和 Excel | 必填 | 章节（Word）或工作表（Excel），按报告顺序排列。 |

### `document` {#document}

| 键 | 类型 | 格式 | 默认值 | 说明 |
|---|---|---|---|---|
| `title` | 字符串 | Word 和 Excel | 空 | Word：`title` 章节的文本。Excel：工作簿的标题属性。 |
| `subtitle` | 字符串 | Word 和 Excel | 空 | Word：标题下方的一行。Excel：工作簿的主题属性。 |

### `branding` {#branding}

| 键 | 类型 | 格式 | 默认值 | 说明 |
|---|---|---|---|---|
| `company_name` | 字符串 | Word 和 Excel | 空 | `{{ company_name }}` 的值。Excel：同时也是工作簿的创建者属性。 |
| `logo_path` | 字符串 | Word | 无 | 显示在标题上方的 PNG 或 JPEG 文件。路径相对于模板文件，且必须位于其目录之内。 |
| `logo_width_inches` | 数字 | Word | `1.5` | 徽标宽度，0.25 到 7。 |
| `header_color` | 字符串 | Excel | `366092` | 表头行的填充颜色，六位十六进制数字。 |

### `header_footer` {#header_footer}

| 键 | 类型 | 格式 | 默认值 | 说明 |
|---|---|---|---|---|
| `header_text` | 字符串 | Word 和 Excel | 空 | Word：页眉。Excel：每个工作表的打印页眉。最多 255 个字符。 |
| `footer_text` | 字符串 | Word 和 Excel | 空 | Word：页脚。Excel：每个工作表的打印页脚。最多 255 个字符。 |
| `include_page_numbers` | 布尔值 | Word | `false` | 在页脚中添加 `Page <number>`。 |

Excel 的打印页眉和打印页脚只会在页面布局视图和纸张上显示。

### `sections` {#sections}

`sections` 的每个条目都是一个映射。`content_type` 键决定该章节显示什么。

| `content_type` | 格式 | 功能 |
|---|---|---|
| `title` | Word | 文档标题、副标题和徽标。 |
| `text` | Word | 一个可选的标题和一组段落。 |
| `service_summary` | Word 和 Excel | 每个服务一行：名称、资源数量、百分比。在 Word 中是一张表，在 Excel 中是一个工作表。 |
| `resources` | Word 和 Excel | 资源表。Word：每个服务一张表。Excel：每个服务一个工作表，或所有资源共用一个工作表。 |
| `network_analysis` | Excel | 网络分析工作表。只有存在网络分析数据时，InvenTag 才会写入它。 |
| `security_analysis` | Excel | 安全分析工作表。只有存在安全分析数据时，InvenTag 才会写入它。 |
| `cost_analysis` | Excel | 成本分析工作表。只有存在成本分析数据时，InvenTag 才会写入它（--enable-cost-analysis）。 |

章节键：

| 键 | 类型 | 格式 | 章节类型 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | 字符串 | Word 和 Excel | 全部 | 必填 | 章节的唯一名称：小写字母、数字和下划线。 |
| `content_type` | 字符串 | Word 和 Excel | 全部 | 必填 | 章节显示什么。 |
| `enabled` | 布尔值 | Word 和 Excel | 全部 | `true` | 设为 `false` 可省略该章节。 |
| `title` | 字符串 | Word | `text`、`service_summary`、`resources` | 空 | 章节的标题文本。 |
| `level` | 整数 | Word | `text`、`service_summary`、`resources` | `1` | 标题级别，1 到 3。服务标题使用下一级。 |
| `page_break_before` | 布尔值 | Word | 全部 | `false` | 让章节从新的一页开始。 |
| `paragraphs` | 列表 | Word | `text` | 空列表 | `text` 章节的段落。 |
| `columns` | `auto` 或列表 | Word 和 Excel | `service_summary`、`resources` | `auto` | `auto`，或列的列表。参见[列](#columns)。 |
| `table_style` | 字符串 | Word | `service_summary`、`resources` | `service_summary` 为 `Light Grid Accent 1`，`resources` 为 `Light List Accent 1` | Word 表格样式。 |
| `services` | 列表 | Word 和 Excel | `resources` | 所有服务 | 只显示这些服务，并按此顺序。比较时忽略大小写、空格以及前缀 `Amazon` 和 `AWS`。 |
| `service_title` | 字符串 | Word | `resources` | `{{ service }} Resources ({{ service_resource_count }})` | 每个服务表的标题。 |
| `max_rows` | 整数 | Word | `resources` | `50` | 每个服务表的最大行数，1 到 100000。 |
| `max_columns` | 整数 | Word | `resources` | `6` | 当 `columns` 为 `auto` 时的最大列数，1 到 100。 |
| `truncation_note` | 字符串 | Word | `resources` | `Note: Showing first {{ shown_resource_count }} of {{ service_resource_count }} {{ service }} resources.` | 未显示全部资源的表格下方的段落。 |
| `page_break_after_service` | 布尔值 | Word | `resources` | `true` | 在每个服务表之后另起一页。 |
| `sheet_name` | 字符串 | Excel | `service_summary`、`resources` | `service_summary` 为 `Summary` | 工作表名称，1 到 31 个字符。对于 `group_by_service: false` 的 `resources` 章节，此项必填。 |
| `group_by_service` | 布尔值 | Excel | `resources` | `true` | `true`：每个服务一个工作表。`false`：所有资源共用一个工作表。 |
| `show_title` | 布尔值 | Excel | `service_summary` | `false` | 在表格上方写入文档标题和副标题。 |

注意：

- Word 文档按列表的顺序显示章节。
- 工作簿按列表的顺序显示工作表。
- 使用 `group_by_service: true` 时，每个工作表以其服务的名称命名。
- Word 的 `resources` 章节按名称对服务排序，除非你给出 `services`。
- `table_style` 的有效值是默认 Word 文档中的表格样式。例如 `Table Grid`、`Light List Accent 1`、
  `Light Grid Accent 1` 和 `Medium Shading 1 Accent 1`。

### 列 {#columns}

`columns` 键是 `auto` 或一个列表。列表的每个条目是一个字段名，或者是带有以下键的映射：

| 键 | 类型 | 格式 | 默认值 | 说明 |
|---|---|---|---|---|
| `field` | 字符串 | Word 和 Excel | 必填 | 要显示的字段。 |
| `heading` | 字符串 | Word 和 Excel | 见下文 | 列标题。 |
| `width` | 数字 | Word 和 Excel | 自动 | 列宽。Word：英寸，0.2 到 10。Excel：字符数，1 到 255。 |

默认标题：

- Word：把字段名转换为带空格和大写字母的形式。例如，
  `source_account_id` 变为 `Source Account Id`。
- Excel：字段名。

`auto` 的功能：

- Word `resources` 章节：每个服务最多 `max_columns` 个字段。如果服务有这些字段，
  最先出现的是 `name`、`id`、`type`、`region`、
  `compliance_status` 和 `tags`。
- Excel `resources` 章节：该工作表上资源的所有字段。
- `service_summary` 章节：`service`、`resource_count` 和 `percentage`。

`service_summary` 章节的字段：`service`、`resource_count`、
`percentage`。

`resources` 章节的字段：

| 分组 | 字段 |
|---|---|
| 标识 | `service`, `type`, `id`, `name`, `arn` |
| 账户和位置 | `account_id`, `source_account_id`, `source_account_name`, `account_name`, `region`, `availability_zone` |
| 资源详情 | `status`, `state`, `creation_date`, `created_time`, `launch_time`, `size`, `instance_type`, `storage_type`, `engine`, `engine_version`, `allocated_storage`, `storage_encrypted`, `multi_az`, `publicly_accessible`, `vpc_id`, `vpc_name`, `subnet_id`, `subnet_name`, `security_groups`, `security_group_ids` |
| 网络 | `vpc_cidr_block`, `vpc_total_ips`, `vpc_utilization_percentage`, `subnet_cidr_block`, `subnet_total_ips`, `subnet_utilization_percentage`, `subnet_is_public`, `subnet_availability_zone` |
| 安全 | `security_risk_level`, `security_group_count`, `max_security_risk`, `inbound_rules_count`, `outbound_rules_count`, `associated_resources_count`, `has_permissive_rules`, `permissive_rules` |
| 成本 | `estimated_monthly_cost`, `cost_breakdown`, `pricing_model`, `confidence_level`, `cost_optimization_opportunities`, `monthly_spend`, `service_monthly_spend`, `billing_validated` |
| 发现与合规 | `compliance_status`, `compliance_score`, `discovery_timestamp`, `consolidation_timestamp`, `total_accounts_in_consolidation`, `discovered_at`, `discovered_via`, `priority`, `tagged`, `tags`, `service_description`, `resource_id`, `resource_name`, `resource_type` |
| 单个标签 | `tags.<key>`，例如 `tags.Owner` |
| 单个原始 API 属性 | `raw_data.<key>`，例如 `raw_data.InstanceType` |
| 你自己的字段 | `extra_fields` 中的每个名称 |

如果资源没有某个字段，单元格为空。`tags` 字段会在一个单元格中显示资源的所有标签。

## 验证错误 {#validation-errors}

CLI 在第一次 AWS 调用之前验证每个模板。如果模板无效，CLI 会向标准错误输出为每个问题打印一行，
并以退出码 `1` 结束。每一行的格式如下：

```text
inventag: error: <file>: <key path>: <reason>
```

示例：

```text
inventag: error: my_word_template.yaml: colour: unknown key. Allowed keys: template_version, format_type, name, description, document, branding, variables, extra_fields, header_footer, sections
inventag: error: my_word_template.yaml: sections[1].columns[2].field: unknown column 'owner_name'. Use a known field (for example service, type, id, name, region, account_id, tags), a tags.<key> field, or add the name to extra_fields
```

| 问题 | 原因的开头 |
|---|---|
| 模式中没有的键 | `unknown key. Allowed keys: ...` |
| 属于另一种报告格式的键 | `this key is not valid in a Word template` 或 `this key is not valid in an Excel template` |
| 值的类型错误 | `must be a string, but the value is integer` |
| 缺少必填键 | `missing key` |
| 不存在的章节类型 | `unknown section type 'cover_page' for a Word template. Allowed values: ...` |
| 不存在的列 | `unknown column 'owner_name'` |
| 不存在的变量 | `unknown variable 'owner'. Allowed variables: ...` |
| 表达式、过滤器或嵌套的大括号 | `malformed placeholder` |
| 两个章节使用相同的 `id` | `duplicate id 'summary'` |
| 模板的格式错误 | `the file is a template for Excel reports, but this flag needs a template for Word reports` |
| 带有 `template_version: "1.0"` 的旧模板 | `unsupported version '1.0'` |
| 超出模板目录的徽标路径 | `the path must stay in the directory of the template file` |
| 不是 YAML 或 JSON 的文件 | `YAML syntax error at line ...` 或 `JSON syntax error at line ...` |
| 扩展名不同的文件 | `unsupported file type` |
| 过大的文件 | `The maximum is 262144 bytes` |

模板参数的退出码：

| 退出码 | 条件 |
|---|---|
| `0` | `--validate-templates` 未发现问题，或 `--print-default-template` 打印了模板。 |
| `1` | 模板文件无效。 |
| `2` | 用法错误。例如，使用 `--word-template` 而没有 `--create-word`，或使用 `--validate-templates` 而没有模板参数。 |

## 限制 {#limits}

| 项目 | 限制 |
|---|---|
| 模板文件大小 | 262144 字节（256 KiB） |
| 文本值 | 2000 个字符 |
| 页眉文本和页脚文本 | 255 个字符 |
| 章节 | 50 |
| 一个章节中的列 | 100 |
| 一个 `text` 章节中的段落 | 100 |
| 你自己的变量 | 50 |
| `extra_fields` 中的条目 | 200 |
| 徽标文件大小 | 5242880 字节（5 MiB） |
| 徽标文件类型 | `.png`, `.jpg`, `.jpeg` |
| Excel 工作表名称 | 31 个字符，不能包含 `[ ] : * ? / \` |

其他限制：

- 模板不能更改 Word 报告的字体、标题颜色或页面大小。
- 模板不能更改网络分析工作表和安全分析工作表的列。
- 模板不能在 Excel 报告中添加目录、图表或徽标。
- Word 表格样式必须是默认 Word 文档中的样式。
- `scripts/legacy/` 中的旧脚本没有模板参数。
- 旧配置示例中的配置键 `templates`、`document_templates` 和
  `default_template` 没有任何作用。只有 `--word-template` 和 `--excel-template` 会选择模板。
- 带有 `template_version: "1.0"` 的模板文件无效。1.0.0 之前的 alpha 构建都附带了这类文件，
  但 CLI 并不会读取它们。

## 模板文件的安全性 {#safety-of-template-files}

- InvenTag 用 `yaml.safe_load` 读取 YAML。YAML 文件无法运行代码。
- InvenTag 不会计算表达式。替换只会替换[变量](#variables)表中的名称。
- InvenTag 不会替换来自 AWS 的资源数据中的变量。
- 模板不能包含另一个文件。唯一的文件引用是 `branding.logo_path`，
  而且该文件必须位于模板目录中。
- Excel 构建器把每个值都存为文本。以 `=` 开头的值不会作为公式运行。
