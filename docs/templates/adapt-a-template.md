---
title: Adapt a template
description: Copy an InvenTag template into your project, change only what you need, check it with templates validate, and use it in a run.
sidebar_position: 3
---

# Adapt a template

**Who this is for:** you like a built-in template but want your own title,
colours, columns or tag rules.

**What you can do after reading:** create your own template in four steps:
`init`, edit, `validate`, run.

The commands below come from a real run against mocked AWS. Long paths are
shortened to `~/acme-infra/`.

## 1. Copy the template into your project

Run this in your project folder:

```bash
./inventag.sh templates init standard-bom --output .inventag/templates/acme-bom.yaml --extend
```

```text
Created .inventag/templates/acme-bom.yaml (kind: report, name: acme-bom).
Next: edit it, then run 'inventag templates validate .inventag/templates/acme-bom.yaml'.
```

You have two choices:

- **`--extend`** (used above) writes a short file that inherits everything
  from `standard-bom`. You only add what you want to change, and you get
  improvements to the built-in template for free.
- **Without `--extend`** you get a full copy with all its comments. Use this
  when you want to see and own every setting.

The template name comes from the file name (`acme-bom.yaml` becomes
`acme-bom`). Use `--name` to choose a different one, and `--force` to replace
an existing file.

Because the file is in `.inventag/templates/`, you can now refer to it by name
from this project.

## 2. Edit it

The new file looks like this:

```yaml
# Inherits everything from 'standard-bom'. Add only what you want to change.
# See: inventag templates show standard-bom --resolved
format_version: 1
kind: report
name: acme-bom
description: "Adapted from standard-bom"
extends: standard-bom
spec: {}
```

Replace `spec: {}` with your changes. This version puts everything on one
sheet, uses a green header and shows three tag columns:

```yaml
format_version: 1
kind: report
name: acme-bom
description: "Acme's inventory layout"
extends: standard-bom
spec:
  title: Acme Cloud Inventory
  company_name: Acme Ltd
  colors:
    header_fill: "0B5D1E"
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
```

How inheritance works:

- **Mappings merge.** Setting `excel.layout` keeps every other `excel` setting
  from `standard-bom`.
- **Lists replace.** If you set `columns`, your list replaces the inherited
  one. Copy the entries you want to keep.
- **`null` resets** a value to its default, for example `tag_policy: null`.
- **Tag policies merge `required_tags` by key.** A child policy can change one
  tag, add a tag, or drop one with `remove: true`, without repeating the rest.

To see the final result after inheritance, run
`./inventag.sh templates show acme-bom --resolved`.

## 3. Validate it

```bash
./inventag.sh templates validate acme-bom
```

If something is wrong, you get the file, the line and a hint. Here the word
`layout` was mistyped:

```text
ERROR ~/acme-infra/.inventag/templates/acme-bom.yaml:13: spec.excel.layuot: unknown field 'layuot'; did you mean 'layout'? Allowed here: autofilter, freeze_header, include_all_fields, layout, max_column_width, single_sheet_name, summary_sheet, tag_compliance_sheet
```

After fixing it:

```text
OK    ~/acme-infra/.inventag/templates/acme-bom.yaml (report 'acme-bom')
```

`validate` exits with 0 when every file is valid and 1 otherwise, so you can
run it in CI. It also checks that templates you refer to (for example a
`tag_policy`) exist and are the right kind.

Your template now shows up in the list:

```bash
./inventag.sh templates list --kind report
```

```text
NAME                KIND    SOURCE   DESCRIPTION
acme-bom            report  project  Acme's inventory layout
executive-summary   report  builtin  Short Word report with totals and tag compliance; Excel has one filterable sheet.
finops-cost-report  report  builtin  Standard layout with cost-allocation tag columns, checked against finops-cost-allocation.
standard-bom        report  builtin  Summary plus one sheet per service, with readable columns and every tag as a column.
```

## 4. Use it

```bash
./inventag.sh --template acme-bom --create-excel --account-regions us-east-1
```

```text
Wrote bom_output/multi_account_bom_20261112_131926.xlsx
```

The workbook has two sheets, `Summary` and `Resources`. The `Resources`
header is green and reads: Account, Region, Service, Type, Name, ID, ARN,
Tag: Owner, Tag: CostCenter, Tag: Environment.

## Share templates with your team

- **One project:** commit `.inventag/templates/` to the project's repository.
- **Every project on your machine:** put templates in
  `~/.config/inventag/templates/`.
- **A shared folder or a CI image:** set
  `INVENTAG_TEMPLATE_PATH=/opt/acme/inventag-templates`.

If two folders contain a template with the same name, the first one in the
[search order](./index.md#where-inventag-looks-for-templates) wins.
`./inventag.sh templates list --all` shows the hidden ones too.

## Next steps

- [Template reference](./reference.md): every field you can set.
- [Brand an executive Word report](../examples/branded-executive-report.md):
  add a logo.
