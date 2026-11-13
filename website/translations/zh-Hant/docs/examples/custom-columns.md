---
title: "範例：自定義欄"
description: 精確選擇 InvenTag 的 Excel 報告中出現哪些欄和標籤欄、按什麼順序排列，並放在同一個可篩選的工作表上。
sidebar_position: 8
---

# 範例：自定義欄

**目標：** 一個工作表，包含團隊真正會看的欄，並按你想要的順序排列。

**你需要：** 唯讀憑證。

## 範本 {#template}

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

- `columns` 會完全替換繼承來的列表，所以請列出你想要的每一欄。
- `tag_columns` 在 `columns` 之後，為每個標籤鍵新增一欄。用 `all` 表示每個找到的標籤，
  或用 `none` 表示不新增。
- `raw_data.<Name>` 直接從 AWS API 回應中讀取一個值。對於沒有該值的資源，它是空白的。
  要查詢名稱，請先用 `excel.include_all_fields: true` 執行一次。

## 命令 {#command}

```bash title="Terminal"
inventag templates validate team-sheet
inventag --template team-sheet --create-excel --account-regions us-east-1
```

## 輸出 {#output}

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/team-sheet.yaml (report 'team-sheet')
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`Inventory`

`Inventory` 工作表的前幾列：

| Account | Service | Type | Name | Region | Volume type | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | EC2 | Volume |  | us-east-1 | gp2 |  |  |  |
| 123456789012 | EC2 | Volume | acme-build-cache | us-east-1 | gp3 |  |  |  |
| 123456789012 | S3 | Bucket | acme-app-logs | us-east-1 |  | platform | CC-1001 | prod |
| 123456789012 | S3 | Bucket | acme-data-lake | us-east-1 |  | data | CC-2002 | prod |
| 123456789012 | S3 | Bucket | acme-reports | us-east-1 |  | finance | 1234 | Production |
| 123456789012 | S3 | Bucket | acme-scratch | us-east-1 |  |  |  |  |

![使用 team-sheet 範本所選欄的 Inventory 工作表：Account、Service、Type、Name、Region、Volume type 和三個標籤欄（範例資料）](../assets/examples/img/team-sheet-inventory.png)

表頭列已凍結，並帶有篩選按鈕。

## 標籤對應和服務描述 {#tag-mappings-and-service-descriptions}

`--tag-mappings` 和 `--service-descriptions` 會為預設工作簿新增欄。
與 `--template` 一起使用時它們不會新增任何內容，
所以請像上面那樣使用 `tag_columns`。如果使用版面配置檔案（`--excel-template` 或 `--word-template`），
請把對應的欄列在 `extra_fields` 下。參見
[設定檔](../reference/configuration-files.md#tag-mappings)。

## 下一步 {#next-steps}

- 所有可用的欄欄位：[範本參考](../templates/reference.md#resource-fields-you-can-use-as-columns)。
