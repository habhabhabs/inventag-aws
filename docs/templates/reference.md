---
title: Template reference
description: Every field of an InvenTag template - report, tag-policy and config - with types, defaults and what each one does.
sidebar_position: 4
---

# Template reference

**Who this is for:** you are writing or reviewing a template and need the
exact name, type or default of a field.

**What you can do after reading:** write any template without guessing, and
read validation errors with confidence.

## File layout

Every template is a YAML file with the same top-level fields:

```yaml
format_version: 1          # optional; 1 is the only version
kind: report               # report | tag-policy | config
name: acme-bom             # lower-case letters, digits and hyphens
description: One sentence shown by 'templates list'
extends: standard-bom      # optional: a template name or a relative path
spec:                      # the settings for this kind
  title: Acme Cloud Inventory
```

- Files end in `.yaml` or `.yml` and must be UTF-8 text, at most 256 KiB.
- The file name should match `name` (`acme-bom.yaml` has `name: acme-bom`).
  Lookups by name use the file name.
- Unknown fields are errors, so typos never pass silently.
- Duplicate keys are errors.
- Put account IDs and hex colours in quotes (`"012345678901"`, `"1F3A5F"`)
  so YAML keeps them as text.

## References to other files

`extends`, `tag_policy`, `report_template` and `logo` can point at another
file:

- **A name** (`standard-bom`) is looked up in the
  [search folders](./index.md#where-inventag-looks-for-templates).
- **A relative path** (`./policies/strict.yaml`) is relative to the template
  that contains it, and must stay inside that template's folder. `..` that
  leaves the folder, absolute paths, `~` and URLs are rejected.

## Field reference

This section is generated from the code
(`python -m inventag.templating.reference --write`), so it always matches what
the validator accepts.

<!-- BEGIN GENERATED FIELD REFERENCE: do not edit by hand -->

### Fields in every template

| Field | Type | Default | What it does |
|---|---|---|---|
| `format_version` | whole number (min 1, max 1) | `1` | Template format version. Only `1` exists today. |
| `kind` | one of `report`, `tag-policy`, `config` | required | What the template controls: `report`, `tag-policy` or `config`. |
| `name` | template name | required | Lower-case letters, digits and hyphens. Should match the file name (`my-report.yaml` has `name: my-report`). |
| `description` | text | empty | One sentence shown by `templates list`. |
| `extends` | template name or relative path | not set | Template to inherit from, by name or by relative path. Must be the same kind. |
| `spec` | mapping | required | The settings for this kind (see below). |

### Report templates (`kind: report`)

| Field | Type | Default | What it does |
|---|---|---|---|
| `spec.title` | text | `AWS Resource Inventory` | Report title, used on the Word cover and the Excel summary sheet. |
| `spec.subtitle` | text | empty | Optional line under the title. |
| `spec.company_name` | text | empty | Organisation name shown on the cover and stored in the file properties. |
| `spec.colors` | mapping | see below | Header colours as six-digit hex values (with or without `#`). |
| `spec.logo` | relative file path | not set | Image shown on the Word cover (PNG, JPEG, GIF or BMP). The path is relative to the template file and must stay inside its folder. |
| `spec.logo_alt_text` | text | empty | Alternative text for the logo, read by screen readers. Defaults to `<company_name> logo`. |
| `spec.columns` | list of mappings | see the built-in `standard-bom` | Columns for resource tables, in order. |
| `spec.tag_columns` | `all`, `none` or list of tag keys | `all` | Extra columns, one per tag key, added after `columns`. Either a list of tag keys, or `all` for every tag key found on the resources in that table, or `none`. |
| `spec.tag_policy` | template name or relative path | not set | Tag policy to check, by name or by relative path. A `--template` with a tag policy on the command line takes precedence. |
| `spec.excel` | mapping | see below | Excel workbook layout. |
| `spec.word` | mapping | see below | Word document layout. |
| `spec.colors.header_fill` | hex colour | `1F3A5F` | Background of table header rows. |
| `spec.colors.header_text` | hex colour | `FFFFFF` | Text colour of table header rows. |
| `spec.columns[].field` | text | required | Resource field to show. Use dots for nested values: `tags.Owner` is the `Owner` tag, `raw_data.InstanceType` is a value from the AWS API response. |
| `spec.columns[].header` | text | not set | Column heading. Defaults to the field name in plain words (`resource_name` becomes `Resource name`). |
| `spec.columns[].width` | whole number (min 4, max 120) | not set | Excel column width in characters. Defaults to a width that fits the content, capped by `excel.max_column_width`. |
| `spec.excel.summary_sheet` | true or false | `true` | Add a Summary sheet with resource counts per service. |
| `spec.excel.layout` | one of `per-service`, `single-sheet` | `per-service` | `per-service` puts each service on its own sheet. `single-sheet` puts every resource on one sheet with a Service column. |
| `spec.excel.single_sheet_name` | text | `Resources` | Sheet name when `layout` is `single-sheet`. |
| `spec.excel.include_all_fields` | true or false | `false` | Also add every other field found on the resources, after the listed columns. Useful for audits; makes wide sheets. |
| `spec.excel.freeze_header` | true or false | `true` | Keep the header row visible when scrolling. |
| `spec.excel.autofilter` | true or false | `true` | Add filter buttons to the header row. |
| `spec.excel.max_column_width` | whole number (min 10, max 120) | `50` | Upper limit for automatic column widths, in characters. |
| `spec.excel.tag_compliance_sheet` | true or false | `true` | Add a Tag Compliance sheet when a tag policy is active. |
| `spec.word.orientation` | one of `portrait`, `landscape` | `portrait` | Page orientation. |
| `spec.word.sections` | list of values from `cover`, `summary`, `service-summary`, `tag-compliance`, `service-tables`, `about` | `["cover", "summary", "service-summary", "tag-compliance", "service-tables", "about"]` | Sections to include, in order. Choose from: `cover`, `summary`, `service-summary`, `tag-compliance`, `service-tables`, `about`. `tag-compliance` is skipped when no tag policy is active. |
| `spec.word.columns` | list of mappings | not set | Columns for the per-service tables. Defaults to the first `max_columns` entries of `columns`. Tag columns are not added. |
| `spec.word.max_columns` | whole number (min 1, max 12) | `6` | How many of `columns` to use when `word.columns` is not set. Word tables get hard to read beyond six or seven columns. |
| `spec.word.max_rows_per_service` | whole number (min 1, max 10000) | `50` | Rows shown per service table. A note says how many were left out. |
| `spec.word.max_noncompliant_rows` | whole number (min 1, max 10000) | `100` | Rows shown in the non-compliant resources table. |
| `spec.word.columns[].field` | text | required | Resource field to show. Use dots for nested values: `tags.Owner` is the `Owner` tag, `raw_data.InstanceType` is a value from the AWS API response. |
| `spec.word.columns[].header` | text | not set | Column heading. Defaults to the field name in plain words (`resource_name` becomes `Resource name`). |
| `spec.word.columns[].width` | whole number (min 4, max 120) | not set | Excel column width in characters. Defaults to a width that fits the content, capped by `excel.max_column_width`. |

### Tag-policy templates (`kind: tag-policy`)

| Field | Type | Default | What it does |
|---|---|---|---|
| `spec.required_tags` | list of mappings | required | Tags that in-scope resources must have. When a template `extends` another, entries are merged by `key`: same key replaces, new keys are added, and `remove: true` drops one. |
| `spec.scope` | mapping | see below | Which resources the policy applies to. Resources outside the scope are counted but not checked. |
| `spec.required_tags[].key` | text | required | Tag key. AWS tag keys are case-sensitive, so `costcenter` does not satisfy `CostCenter`. |
| `spec.required_tags[].description` | text | empty | Why the tag exists. Shown in reports. |
| `spec.required_tags[].allowed_values` | list of text | not set | If set, the tag value must be one of these. |
| `spec.required_tags[].case_sensitive` | true or false | `false` | Compare `allowed_values` case-sensitively. |
| `spec.required_tags[].pattern` | regular expression | not set | If set, the whole tag value must match this regular expression (Python syntax). |
| `spec.required_tags[].remove` | true or false | `false` | In a template that `extends` another, drop this tag from the inherited list. |
| `spec.scope.services` | list of text | `[]` | Only check these services (as shown in the report, for example `EC2`, `S3`). Empty means all services. |
| `spec.scope.resource_types` | list of text | `[]` | Only check these resource types (for example `Bucket`, `Instance`). Empty means all types. |
| `spec.scope.exclude_resource_types` | list of text | `[]` | Never check these resource types, for example types that cannot carry tags. |

### Config templates (`kind: config`)

| Field | Type | Default | What it does |
|---|---|---|---|
| `spec.accounts` | list of mappings | not set | Accounts to scan. Leave out to scan the account of your current AWS credentials. Each account needs `profile_name` or `role_arn`. |
| `spec.regions` | list of text | not set | Regions to scan (`--account-regions`). Leave out to scan every enabled region. |
| `spec.services` | list of text | not set | Services to include (`--account-services`). Currently applied in one discovery path only, so other services can still appear. |
| `spec.outputs` | list of values from `excel`, `word` | `["excel"]` | Files to produce (`--create-excel`, `--create-word`). |
| `spec.output_directory` | text | `bom_output` | Folder for the reports (`--output-directory`). |
| `spec.report_template` | template name or relative path | `standard-bom` | Report template to use, by name or relative path. |
| `spec.tag_policy` | template name or relative path | not set | Tag policy to check, by name or relative path. |
| `spec.fail_on_tag_violations` | true or false | `false` | Exit with code 3 after writing the reports if any in-scope resource breaks the tag policy. Needs `tag_policy`. |
| `spec.max_concurrent_accounts` | whole number (min 1, max 64) | `4` | Accounts scanned at the same time (`--max-concurrent-accounts`). |
| `spec.account_processing_timeout` | whole number (min 60) | `1800` | Seconds allowed per account (`--account-processing-timeout`). |
| `spec.parallel_processing` | true or false | `true` | Scan accounts in parallel. `false` is the same as `--disable-parallel-processing`. |
| `spec.accounts[].account_id` | text | required | 12-digit AWS account ID, in quotes so YAML keeps leading zeros. |
| `spec.accounts[].account_name` | text | empty | Friendly name used in reports. |
| `spec.accounts[].profile_name` | text | not set | AWS CLI profile to use for this account. |
| `spec.accounts[].role_arn` | text | not set | IAM role to assume in this account, as a full ARN. |
| `spec.accounts[].external_id` | text | not set | External ID required by the role's trust policy. |
| `spec.accounts[].regions` | list of text | not set | Regions to scan in this account. Overrides `spec.regions`. |
| `spec.accounts[].services` | list of text | not set | Services to scan in this account. |

<!-- END GENERATED FIELD REFERENCE -->

## Resource fields you can use as columns

A column's `field` reads a value from each resource. These fields are present
on resources from a normal run:

| Field | Contains |
|---|---|
| `service` | Service name as shown in the report, for example `S3`, `EC2`, `VPC` |
| `resource_type` | For example `Bucket`, `Volume`, `Subnet` |
| `resource_name` | Name, when the resource has one |
| `resource_id` | The resource's ID |
| `arn` | Amazon Resource Name, when known |
| `region` | Region code |
| `source_account_id` | Account the resource was found in |
| `source_account_name` | The `account_name` you gave that account |
| `tags` | All tags, written as `Key=Value, Key=Value` |
| `tags.<Key>` | The value of one tag, for example `tags.Owner` |
| `tagged` | `Yes` or `No` |
| `discovered_via` | Which API found the resource |
| `raw_data.<Name>` | A value from the AWS API response, for example `raw_data.VolumeType` |

Missing values are left blank. To see every field your resources have, set
`excel.include_all_fields: true` and look at the extra columns.

## Validation messages

`./inventag.sh templates validate <file>` and every run with `--template`
print problems as:

```text
<file>:<line>: <field>: <what is wrong>
```

For example:

```text
acme-bom.yaml:13: spec.excel.layuot: unknown field 'layuot'; did you mean 'layout'? ...
org.yaml:9: spec.accounts[0].account_id: must be text, got a number. Put account IDs in quotes, for example "012345678901".
org.yaml:12: spec.accounts[1].access_key_id: templates must not contain credentials; use profile_name or role_arn
```

When a template `extends` another, problems are reported against the file
that contains them.

## Exit codes

| Command | Code | Meaning |
|---|---|---|
| `templates validate` | 0 | Every file is valid |
| `templates validate` | 1 | At least one file has a problem |
| `templates init` | 1 | The output file exists (use `--force`) or the template is invalid |
| `templates init` | 2 | The output name or extension is not allowed |
| `inventag --template ...` | 1 | A template is invalid, or the run failed |
| `inventag --template ...` | 3 | Reports were written, but resources break the tag policy and `fail_on_tag_violations` is `true` |
