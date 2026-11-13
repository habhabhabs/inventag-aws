---
title: "Example: your own columns"
description: Choose exactly which columns and tag columns appear in InvenTag's Excel report, in which order, on a single filterable sheet.
sidebar_position: 8
---

# Example: your own columns

**Goal:** one sheet with the columns your team actually reads, in the order
you want.

**You need:** read-only credentials.

## Template

```yaml title=".inventag/templates/team-sheet.yaml"
format_version: 1
kind: report
name: team-sheet
description: One sheet, our columns
extends: standard-bom
spec:
  title: Platform team inventory
  columns:
    - { field: source_account_id, header: Account }
    - { field: service, header: Service }
    - { field: resource_type, header: Type }
    - { field: resource_name, header: Name }
    - { field: region, header: Region }
    - { field: raw_data.VolumeType, header: Volume type }
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
    single_sheet_name: Inventory
```

- `columns` replaces the inherited list completely, so list every column you
  want.
- `tag_columns` adds one column per tag key, after `columns`. Use `all` for
  every tag found, or `none`.
- `raw_data.<Name>` reads a value straight from the AWS API response. It is
  blank for resources that don't have it. To find the names, run once with
  `excel.include_all_fields: true`.

## Command

```bash title="Terminal"
inventag templates validate team-sheet
inventag --template team-sheet --create-excel --account-regions us-east-1
```

## Output

<!-- BEGIN EXAMPLE OUTPUT: columns-validate -->

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/team-sheet.yaml (report 'team-sheet')
```

<!-- END EXAMPLE OUTPUT: columns-validate -->

<!-- BEGIN EXAMPLE OUTPUT: columns-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: columns-console -->

<!-- BEGIN EXAMPLE OUTPUT: columns-excel -->

**Sheets:** `Summary`, `Inventory`

`Inventory` sheet, first rows:

| Account | Service | Type | Name | Region | Volume type | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | EC2 | Volume |  | us-east-1 | gp2 |  |  |  |
| 123456789012 | EC2 | Volume | acme-build-cache | us-east-1 | gp3 |  |  |  |
| 123456789012 | S3 | Bucket | acme-app-logs | us-east-1 |  | platform | CC-1001 | prod |
| 123456789012 | S3 | Bucket | acme-data-lake | us-east-1 |  | data | CC-2002 | prod |
| 123456789012 | S3 | Bucket | acme-reports | us-east-1 |  | finance | 1234 | Production |
| 123456789012 | S3 | Bucket | acme-scratch | us-east-1 |  |  |  |  |

<!-- END EXAMPLE OUTPUT: columns-excel -->

<!-- BEGIN EXAMPLE OUTPUT: columns-image -->

<img src={require("../assets/examples/img/team-sheet-inventory.png").default} alt="Inventory sheet with the columns chosen in the team-sheet template: Account, Service, Type, Name, Region, Volume type and three tag columns (sample data)" width="1075" height="600" loading="lazy" />

<!-- END EXAMPLE OUTPUT: columns-image -->

The header row is frozen and has filter buttons.

## Tag mappings and service descriptions

`--tag-mappings` and `--service-descriptions` add columns to the default
workbook. With `--template` they add nothing (we checked with
`--template standard-bom --tag-mappings`), so use `tag_columns` as above. With
a layout file (`--excel-template` or `--word-template`), list the mapped
column under `extra_fields`. See
[Configuration files](../reference/configuration-files.md#tag-mappings).

## Next steps

- All column fields: [Template reference](../templates/reference.md#resource-fields-you-can-use-as-columns).
