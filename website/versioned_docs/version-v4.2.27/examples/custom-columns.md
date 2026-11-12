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

```yaml
# .inventag/templates/team-sheet.yaml
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
  blank for resources that don't have it. To discover the names, run once
  with `excel.include_all_fields: true`.

## Command

```bash
./inventag.sh templates validate team-sheet
./inventag.sh --template team-sheet --create-excel --account-regions us-east-1
```

## Expected output

Sample data from an offline run:

```text
OK    ~/acme-infra/.inventag/templates/team-sheet.yaml (report 'team-sheet')
Wrote bom_output/multi_account_bom_20261112_132609.xlsx
```

The workbook has two sheets, `Summary` and `Inventory`. The Inventory header
row is frozen and has filter buttons. A few rows from the sample:

| Account | Service | Type | Name | Region | Volume type | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | EC2 | Volume | | us-east-1 | gp2 | | | |
| 123456789012 | S3 | Bucket | acme-app-logs | us-east-1 | | platform | CC-1001 | prod |
| 123456789012 | S3 | Bucket | acme-reports | us-east-1 | | finance | 1234 | Production |

## Tag mappings and service descriptions

`--tag-mappings` and `--service-descriptions` also add custom columns. See
[Configuration files](../reference/configuration-files.md#tag-mappings).

## Next steps

- All column fields: [Template reference](../templates/reference.md#resource-fields-you-can-use-as-columns).
