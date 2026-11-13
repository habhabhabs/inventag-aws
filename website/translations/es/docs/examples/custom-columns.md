---
title: "Ejemplo: tus propias columnas"
description: Elige exactamente qué columnas y columnas de etiquetas aparecen en el informe de Excel de InvenTag, en qué orden, en una sola hoja con filtros.
sidebar_position: 8
---

# Ejemplo: tus propias columnas

**Objetivo:** una hoja con las columnas que tu equipo lee de verdad, en el
orden que quieras.

**Necesitas:** credenciales de solo lectura.

## Plantilla {#template}

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

- `columns` sustituye por completo la lista heredada, así que enumera todas las
  columnas que quieras.
- `tag_columns` añade una columna por cada clave de etiqueta, después de
  `columns`. Usa `all` para todas las etiquetas encontradas, o `none`.
- `raw_data.<Name>` lee un valor directamente de la respuesta de la API de AWS.
  Queda en blanco en los recursos que no lo tienen. Para averiguar los nombres,
  ejecuta una vez con `excel.include_all_fields: true`.
- `source`, `sources` y `detail_level` indican de dónde viene cada fila. Consulta la
  [lista de campos](../templates/reference.md#resource-fields-you-can-use-as-columns).

## Comando {#command}

```bash title="Terminal"
inventag templates validate team-sheet
inventag --template team-sheet --create-excel --account-regions us-east-1
```

## Salida {#output}

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/team-sheet.yaml (report 'team-sheet')
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**Hojas:** `Summary`, `Inventory`

Hoja `Inventory`, primeras filas:

| Account | Service | Type | Name | Region | Volume type | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | EC2 | Volume |  | us-east-1 | gp2 |  |  |  |
| 123456789012 | EC2 | Volume | acme-build-cache | us-east-1 | gp3 |  |  |  |
| 123456789012 | S3 | Bucket | acme-app-logs | us-east-1 |  | platform | CC-1001 | prod |
| 123456789012 | S3 | Bucket | acme-data-lake | us-east-1 |  | data | CC-2002 | prod |
| 123456789012 | S3 | Bucket | acme-reports | us-east-1 |  | finance | 1234 | Production |
| 123456789012 | S3 | Bucket | acme-scratch | us-east-1 |  |  |  |  |

![Hoja Inventory con las columnas elegidas en la plantilla team-sheet: Account, Service, Type, Name, Region, Volume type y tres columnas de etiquetas (datos de ejemplo)](../assets/examples/img/team-sheet-inventory.png)

La fila de encabezado está inmovilizada y tiene botones de filtro.

## Asignaciones de etiquetas y descripciones de servicios {#tag-mappings-and-service-descriptions}

`--tag-mappings` y `--service-descriptions` añaden columnas al libro
predeterminado. Con `--template` no añaden nada hasta que enumeras la columna: añade
`- field: <nombre de la columna>` en `columns` (el nombre de tu archivo de
asignaciones, o `service_description`), o pon `excel.include_all_fields: true`.
`tag_columns` muestra solo los valores de etiqueta sin procesar. InvenTag registra
una advertencia con las columnas que faltan. Con un archivo de diseño (`--excel-template` o `--word-template`),
indica la columna asignada en `extra_fields`. Consulta
[Archivos de configuración](../reference/configuration-files.md#tag-mappings).

## Siguientes pasos {#next-steps}

- Todos los campos de columna: [Referencia de plantillas](../templates/reference.md#resource-fields-you-can-use-as-columns).
