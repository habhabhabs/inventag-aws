---
title: Layout files for one report
description: Change the title, sections, sheets, columns, header and footer of the Word and Excel BOM reports with a YAML or JSON template file.
sidebar_position: 5
---

# Layout files for one report

This page describes the `--word-template` and `--excel-template` flags. Each flag
takes one layout file for one report format. For named templates that you select
with `--template`, see [Templates](./index.md).

A report template is a YAML or JSON file. The template controls the structure
of the Word report or the Excel report. Give the file to the CLI with
`--word-template` or `--excel-template`.

If you give no template, InvenTag uses the built-in default template. The
report then has the same structure as in versions without templates.

## What a template can change

| Item | Word report | Excel report |
|---|---|---|
| Title and subtitle | Title section of the document | Workbook properties, and optional rows above the summary table |
| Company name | Value of `{{ company_name }}` | Value of `{{ company_name }}`, and the workbook creator property |
| Logo | PNG or JPEG file above the title | Not available |
| Sections or sheets | Which sections appear, and their order | Which sheets appear, and their order |
| Columns | Which columns appear, their order, heading and width | Which columns appear, their order, heading and width |
| Services | Which services appear in the resource tables, and their order | Which services get a sheet, and their order |
| Header and footer | Page header, page footer, page number | Print header and print footer of each sheet |
| Header row color | Not available | Fill color of the header row |
| Free text | Headings and paragraphs with variables | Not available |

## Make a template

1. Print the default template to a file.

   ```bash
   inventag --print-default-template word > my_word_template.yaml
   inventag --print-default-template excel > my_excel_template.json
   ```

2. Edit the file. See the [key reference](#key-reference).

3. Validate the file. This command makes no AWS call.

   ```bash
   inventag --validate-templates \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

   If the files are valid, the CLI prints one `OK` line for each file and
   stops with exit code `0`.

4. Use the file in a run.

   ```bash
   inventag --create-word --create-excel \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

The CLI accepts the file name extensions `.yaml`, `.yml` and `.json` for the
two formats. The default template files are also in the repository:
`templates/default_word_template.yaml` and
`templates/default_excel_template.json`.

## Template flags

| Flag | Function |
|---|---|
| `--word-template PATH` | Template for the Word report. This flag needs `--create-word`. |
| `--excel-template PATH` | Template for the Excel report. This flag needs `--create-excel`. Without it, the CLI stops with exit code `2`. |
| `--print-default-template word` or `--print-default-template excel` | Prints the default template and stops with exit code `0`. |
| `--validate-templates` | Validates the files from `--word-template` and `--excel-template`, then stops. No AWS call. |

## Minimal examples

This Word template gives a title, one resource table for each service, and a
summary table.

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

This Excel template gives one sheet with all resources, then the summary
sheet.

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

## Variables

Write a variable as `{{ name }}` in a text value. InvenTag replaces the
variable with its value when it writes the report.

| Variable | Value |
|---|---|
| `{{ company_name }}` | The value of `branding.company_name`. |
| `{{ document_title }}` | The value of `document.title` after substitution. |
| `{{ document_subtitle }}` | The value of `document.subtitle` after substitution. |
| `{{ generated_at }}` | Generation time in UTC, format `YYYY-MM-DD HH:MM:SS`. |
| `{{ generated_date }}` | Generation date in UTC, format `YYYY-MM-DD`. |
| `{{ account_ids }}` | The account IDs in the report, sorted, separated by a comma and a space. |
| `{{ account_count }}` | The number of different account IDs in the report. |
| `{{ total_resources }}` | The number of resources in the report. |
| `{{ service_count }}` | The number of different services in the report. |
| `{{ region_count }}` | The number of different regions in the report. |

These variables are valid only in `service_title` and `truncation_note` of a
Word `resources` section:

| Variable | Value |
|---|---|
| `{{ service }}` | The service name of the current table. |
| `{{ service_resource_count }}` | The number of resources of the current service. |
| `{{ shown_resource_count }}` | The number of rows in the current table. |

You can define your own variables under `variables`:

```yaml
variables:
  classification: Internal
header_footer:
  footer_text: "Classification: {{ classification }}"
```

Rules for variables:

- A variable name has only letters, digits and underscores.
- The name of your own variable starts with a lowercase letter and has only
  lowercase letters, digits and underscores.
- You cannot use the name of a built-in variable for your own variable.
- A variable value is plain text. A value cannot contain a different variable.
- `document.title` and `document.subtitle` cannot use `{{ document_title }}`
  or `{{ document_subtitle }}`.
- These keys accept variables: `document.title`, `document.subtitle`,
  `header_footer.header_text`, `header_footer.footer_text`, and the section
  keys `title`, `paragraphs`, `service_title` and `truncation_note`.
- Column headings, sheet names and `branding.company_name` do not accept
  variables.
- InvenTag does not support expressions, filters, conditions, loops or file
  inclusion. For example, `{{ company_name | upper }}` is an error.
- InvenTag does not replace variables in resource data. A resource name with
  the text `{{ company_name }}` stays unchanged in the report.

## Key reference

A test in `tests/unit/test_template_system.py` makes sure that this reference
contains each key of the schema in `inventag/reporting/report_template.py`.

### Top-level keys

| Key | Type | Formats | Default | Description |
|---|---|---|---|---|
| `template_version` | string | Word and Excel | Necessary | Schema version. Must be `"2.0"`. |
| `format_type` | string | Word and Excel | Necessary | `word` or `excel`. |
| `name` | string | Word and Excel | Empty | A name for the template. Not shown in the report. |
| `description` | string | Word and Excel | Empty | A description. Not shown in the report. |
| `document` | mapping | Word and Excel | See below | Title and subtitle. |
| `branding` | mapping | Word and Excel | See below | Company name, logo and color. |
| `variables` | mapping | Word and Excel | Empty | Your own variables: name to text. |
| `extra_fields` | list | Word and Excel | Empty | More resource field names that `columns` can use. For example, a column from your tag mappings. |
| `header_footer` | mapping | Word and Excel | See below | Header and footer text. |
| `sections` | list | Word and Excel | Necessary | The sections (Word) or sheets (Excel), in report order. |

### `document`

| Key | Type | Formats | Default | Description |
|---|---|---|---|---|
| `title` | string | Word and Excel | Empty | Word: the text of the `title` section. Excel: the workbook title property. |
| `subtitle` | string | Word and Excel | Empty | Word: a line below the title. Excel: the workbook subject property. |

### `branding`

| Key | Type | Formats | Default | Description |
|---|---|---|---|---|
| `company_name` | string | Word and Excel | Empty | The value of `{{ company_name }}`. Excel: also the workbook creator property. |
| `logo_path` | string | Word | None | PNG or JPEG file shown above the title. The path is relative to the template file and must stay in its directory. |
| `logo_width_inches` | number | Word | `1.5` | Logo width, 0.25 to 7. |
| `header_color` | string | Excel | `366092` | Fill color of the header row, six hexadecimal digits. |

### `header_footer`

| Key | Type | Formats | Default | Description |
|---|---|---|---|---|
| `header_text` | string | Word and Excel | Empty | Word: page header. Excel: print header of each sheet. Maximum 255 characters. |
| `footer_text` | string | Word and Excel | Empty | Word: page footer. Excel: print footer of each sheet. Maximum 255 characters. |
| `include_page_numbers` | boolean | Word | `false` | Add `Page <number>` to the page footer. |

The Excel print header and print footer show only in the page layout view and
on paper.

### `sections`

Each entry of `sections` is a mapping. The `content_type` key selects what the
section shows.

| `content_type` | Formats | Function |
|---|---|---|
| `title` | Word | The document title, the subtitle and the logo. |
| `text` | Word | An optional heading and a list of paragraphs. |
| `service_summary` | Word and Excel | One row for each service: name, resource count, percentage. A table in Word, a sheet in Excel. |
| `resources` | Word and Excel | The resource tables. Word: one table for each service. Excel: one sheet for each service, or one sheet for all resources. |
| `network_analysis` | Excel | The network analysis sheet. InvenTag writes it only if network analysis data exists. |
| `security_analysis` | Excel | The security analysis sheet. InvenTag writes it only if security analysis data exists. |
| `cost_analysis` | Excel | The cost analysis sheet. InvenTag writes it only if cost analysis data exists (--enable-cost-analysis). |

Section keys:

| Key | Type | Formats | Section types | Default | Description |
|---|---|---|---|---|---|
| `id` | string | Word and Excel | All | Necessary | Unique name of the section: lowercase letters, digits and underscores. |
| `content_type` | string | Word and Excel | All | Necessary | What the section shows. |
| `enabled` | boolean | Word and Excel | All | `true` | Set to `false` to leave the section out. |
| `title` | string | Word | `text`, `service_summary`, `resources` | Empty | Heading text of the section. |
| `level` | integer | Word | `text`, `service_summary`, `resources` | `1` | Heading level, 1 to 3. Service headings use the next level. |
| `page_break_before` | boolean | Word | All | `false` | Start the section on a new page. |
| `paragraphs` | list | Word | `text` | Empty list | The paragraphs of a `text` section. |
| `columns` | `auto` or list | Word and Excel | `service_summary`, `resources` | `auto` | `auto`, or a list of columns. See [Columns](#columns). |
| `table_style` | string | Word | `service_summary`, `resources` | `Light Grid Accent 1` for `service_summary`, `Light List Accent 1` for `resources` | Word table style. |
| `services` | list | Word and Excel | `resources` | All services | Show only these services, in this order. The comparison ignores case, spaces, and the prefixes `Amazon` and `AWS`. |
| `service_title` | string | Word | `resources` | `{{ service }} Resources ({{ service_resource_count }})` | Heading of each service table. |
| `max_rows` | integer | Word | `resources` | `50` | Maximum number of rows in each service table, 1 to 100000. |
| `max_columns` | integer | Word | `resources` | `6` | Maximum number of columns if `columns` is `auto`, 1 to 100. |
| `truncation_note` | string | Word | `resources` | `Note: Showing first {{ shown_resource_count }} of {{ service_resource_count }} {{ service }} resources.` | Paragraph below a table that does not show all resources. |
| `page_break_after_service` | boolean | Word | `resources` | `true` | Start a new page after each service table. |
| `sheet_name` | string | Excel | `service_summary`, `resources` | `Summary` for `service_summary` | Sheet name, 1 to 31 characters. Necessary for a `resources` section with `group_by_service: false`. |
| `group_by_service` | boolean | Excel | `resources` | `true` | `true`: one sheet for each service. `false`: one sheet for all resources. |
| `show_title` | boolean | Excel | `service_summary` | `false` | Write the document title and subtitle above the table. |

Notes:

- A Word document shows the sections in the order of the list.
- A workbook shows the sheets in the order of the list.
- With `group_by_service: true`, each sheet has the name of its service.
- A Word `resources` section sorts the services by name, unless you give
  `services`.
- Valid values for `table_style` are the table styles of the default Word
  document. Examples are `Table Grid`, `Light List Accent 1`,
  `Light Grid Accent 1` and `Medium Shading 1 Accent 1`.

### Columns

The `columns` key is `auto` or a list. Each list entry is a field name, or a
mapping with these keys:

| Key | Type | Formats | Default | Description |
|---|---|---|---|---|
| `field` | string | Word and Excel | Necessary | The field to show. |
| `heading` | string | Word and Excel | See below | The column heading. |
| `width` | number | Word and Excel | Automatic | Column width. Word: inches, 0.2 to 10. Excel: characters, 1 to 255. |

Default headings:

- Word: the field name with spaces and capital letters. For example,
  `source_account_id` becomes `Source Account Id`.
- Excel: the field name.

Function of `auto`:

- Word `resources` section: a maximum of `max_columns` fields for each
  service. The first fields are `name`, `id`, `type`, `region`,
  `compliance_status` and `tags`, if the service has them.
- Excel `resources` section: all fields of the resources on the sheet.
- `service_summary` section: `service`, `resource_count` and `percentage`.

Fields for a `service_summary` section: `service`, `resource_count`,
`percentage`.

Fields for a `resources` section:

| Group | Fields |
|---|---|
| Identity | `service`, `type`, `id`, `name`, `arn` |
| Account and location | `account_id`, `source_account_id`, `source_account_name`, `account_name`, `region`, `availability_zone` |
| Resource details | `status`, `state`, `creation_date`, `created_time`, `launch_time`, `size`, `instance_type`, `storage_type`, `engine`, `engine_version`, `allocated_storage`, `storage_encrypted`, `multi_az`, `publicly_accessible`, `vpc_id`, `vpc_name`, `subnet_id`, `subnet_name`, `security_groups`, `security_group_ids` |
| Network | `vpc_cidr_block`, `vpc_total_ips`, `vpc_utilization_percentage`, `subnet_cidr_block`, `subnet_total_ips`, `subnet_utilization_percentage`, `subnet_is_public`, `subnet_availability_zone` |
| Security | `security_risk_level`, `security_group_count`, `max_security_risk`, `inbound_rules_count`, `outbound_rules_count`, `associated_resources_count`, `has_permissive_rules`, `permissive_rules` |
| Cost | `estimated_monthly_cost`, `cost_breakdown`, `pricing_model`, `confidence_level`, `cost_optimization_opportunities`, `monthly_spend`, `service_monthly_spend`, `billing_validated` |
| Discovery and compliance | `compliance_status`, `compliance_score`, `discovery_timestamp`, `consolidation_timestamp`, `total_accounts_in_consolidation`, `discovered_at`, `discovered_via`, `priority`, `tagged`, `tags`, `service_description`, `resource_id`, `resource_name`, `resource_type` |
| One tag | `tags.<key>`, for example `tags.Owner` |
| One raw API attribute | `raw_data.<key>`, for example `raw_data.InstanceType` |
| Your own fields | Each name in `extra_fields` |

If a resource does not have a field, the cell is empty. The `tags` field
shows all tags of a resource in one cell.

## Validation errors

The CLI validates each template before the first AWS call. If a template is
not valid, the CLI prints one line for each problem to standard error and
stops with exit code `1`. Each line has this format:

```text
inventag: error: <file>: <key path>: <reason>
```

Example:

```text
inventag: error: my_word_template.yaml: colour: unknown key. Allowed keys: template_version, format_type, name, description, document, branding, variables, extra_fields, header_footer, sections
inventag: error: my_word_template.yaml: sections[1].columns[2].field: unknown column 'owner_name'. Use a known field (for example service, type, id, name, region, account_id, tags), a tags.<key> field, or add the name to extra_fields
```

| Problem | Start of the reason |
|---|---|
| A key that the schema does not have | `unknown key. Allowed keys: ...` |
| A key of the other report format | `this key is not valid in a Word template` or `this key is not valid in an Excel template` |
| A value of the wrong type | `must be a string, but the value is integer` |
| A necessary key is absent | `missing key` |
| A section type that does not exist | `unknown section type 'cover_page' for a Word template. Allowed values: ...` |
| A column that does not exist | `unknown column 'owner_name'` |
| A variable that does not exist | `unknown variable 'owner'. Allowed variables: ...` |
| An expression, a filter or nested braces | `malformed placeholder` |
| Two sections with the same `id` | `duplicate id 'summary'` |
| A template of the wrong format | `the file is a template for Excel reports, but this flag needs a template for Word reports` |
| An old template with `template_version: "1.0"` | `unsupported version '1.0'` |
| A logo path that leaves the template directory | `the path must stay in the directory of the template file` |
| A file that is not YAML or JSON | `YAML syntax error at line ...` or `JSON syntax error at line ...` |
| A file with a different extension | `unsupported file type` |
| A file that is too large | `The maximum is 262144 bytes` |

Exit codes for the template flags:

| Exit code | Condition |
|---|---|
| `0` | `--validate-templates` found no problem, or `--print-default-template` printed the template. |
| `1` | A template file is not valid. |
| `2` | Usage error. For example, `--word-template` without `--create-word`, or `--validate-templates` without a template flag. |

## Limits

| Item | Limit |
|---|---|
| Template file size | 262144 bytes (256 KiB) |
| Text value | 2000 characters |
| Header text and footer text | 255 characters |
| Sections | 50 |
| Columns in one section | 100 |
| Paragraphs in one `text` section | 100 |
| Your own variables | 50 |
| Entries in `extra_fields` | 200 |
| Logo file size | 5242880 bytes (5 MiB) |
| Logo file types | `.png`, `.jpg`, `.jpeg` |
| Excel sheet name | 31 characters, without `[ ] : * ? / \` |

Other limits:

- A template cannot change the fonts, the heading colors, or the page size of
  the Word report.
- A template cannot change the columns of the network analysis sheet and the
  security analysis sheet.
- A template cannot add a table of contents, charts, or a logo in the Excel
  report.
- A Word table style must be a style of the default Word document.
- The legacy scripts in `scripts/legacy/` do not have the template flags.
- The configuration keys `templates`, `document_templates` and
  `default_template` in older configuration examples have no effect. Only
  `--word-template` and `--excel-template` select a template.
- Template files with `template_version: "1.0"` are not valid. Alpha builds
  before v1.0.0 shipped such files, but the CLI did not read them.

## Safety of template files

- InvenTag reads YAML with `yaml.safe_load`. A YAML file cannot run code.
- InvenTag does not evaluate expressions. Substitution replaces only the
  names in the [variables](#variables) tables.
- InvenTag does not replace variables in resource data from AWS.
- A template cannot include a different file. The only file reference is
  `branding.logo_path`, and that file must be in the template directory.
- The Excel builder stores each value as text. A value that starts with `=`
  does not run as a formula.
