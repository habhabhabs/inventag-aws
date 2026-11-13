---
title: Adaptar una plantilla
description: Copia una plantilla de InvenTag en tu proyecto, cambia solo lo que necesites, compruébala con templates validate y úsala en una ejecución.
sidebar_position: 3
---

# Adaptar una plantilla

**Para quién es:** te gusta una plantilla integrada pero quieres tu propio
título, tus colores, tus columnas o tus reglas de etiquetas.

**Qué podrás hacer después de leerlo:** crear tu propia plantilla en cuatro
pasos: `init`, editar, `validate` y ejecutar.

Las salidas de abajo proceden de ejecuciones sin conexión contra AWS simulado
(datos de ejemplo). La carpeta de tu proyecto se muestra como `~/acme-infra/`.

## 1. Copia la plantilla en tu proyecto {#1-copy-the-template-into-your-project}

Ejecuta esto en la carpeta de tu proyecto:

```bash
inventag templates init standard-bom --output .inventag/templates/acme-bom.yaml --extend
```

```text title="Salida"
Created .inventag/templates/acme-bom.yaml (kind: report, name: acme-bom).
Next: edit it, then run 'inventag templates validate .inventag/templates/acme-bom.yaml'.
```

Tienes dos opciones:

- **`--extend`** (la usada arriba) escribe un archivo corto que hereda todo de
  `standard-bom`. Solo añades lo que quieres cambiar, y obtienes gratis las
  mejoras de la plantilla integrada.
- **Sin `--extend`** obtienes una copia completa con todos sus comentarios.
  Úsala cuando quieras ver y controlar cada ajuste.

El nombre de la plantilla sale del nombre del archivo (`acme-bom.yaml` pasa a
ser `acme-bom`). Usa `--name` para elegir otro y `--force` para reemplazar un
archivo existente.

Como el archivo está en `.inventag/templates/`, ya puedes referirte a él por su
nombre desde este proyecto.

## 2. Edítala {#2-edit-it}

El archivo nuevo tiene este aspecto:

```yaml title=".inventag/templates/acme-bom.yaml"
# Inherits everything from 'standard-bom'. Add only what you want to change.
# See: inventag templates show standard-bom --resolved
format_version: 1
kind: report
name: acme-bom
description: "Adapted from standard-bom"
extends: standard-bom
spec: {}
```

Sustituye `spec: {}` por tus cambios. Esta versión pone todo en una sola hoja,
usa un encabezado verde y muestra tres columnas de etiquetas:

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

Cómo funciona la herencia:

- **Los mapeos se combinan.** Si defines `excel.layout`, se conservan todos los
  demás ajustes de `excel` de `standard-bom`.
- **Las listas se reemplazan.** Si defines `columns`, tu lista reemplaza la
  heredada. Copia las entradas que quieras conservar.
- **`null` restablece** un valor a su valor predeterminado, por ejemplo
  `tag_policy: null`.
- **Las políticas de etiquetas combinan `required_tags` por clave.** Una
  política hija puede cambiar una etiqueta, añadir otra o quitar una con
  `remove: true`, sin repetir el resto.

Para ver el resultado final después de la herencia, ejecuta
`inventag templates show acme-bom --resolved`.

## 3. Valídala {#3-validate-it}

```bash
inventag templates validate acme-bom
```

También puedes indicar una ruta de archivo, por ejemplo
`inventag templates validate ./acme-bom.yaml`. Cualquier referencia que contenga
un punto o una barra se lee como una ruta.

Si algo está mal, obtienes el archivo, la línea y una pista. Aquí la palabra
`layout` se escribió mal como `layuot`:

```text title="Salida"
ERROR ~/acme-infra/.inventag/templates/acme-bom.yaml:13: spec.excel.layuot: unknown field 'layuot'; did you mean 'layout'? Allowed here: autofilter, freeze_header, include_all_fields, layout, max_column_width, single_sheet_name, summary_sheet, tag_compliance_sheet
(exit code 1)
```

Después de corregirlo:

```text title="Salida"
OK    ~/acme-infra/.inventag/templates/acme-bom.yaml (report 'acme-bom')
```

`validate` termina con 0 cuando todos los archivos son válidos y con 1 en caso
contrario, así que puedes ejecutarlo en CI. También comprueba que las
plantillas a las que te refieres (por ejemplo una `tag_policy`) existen y son
del tipo correcto.

Tu plantilla ya aparece en la lista:

```bash title="Terminal"
inventag templates list --kind report
```

```text title="Salida"
NAME                KIND    SOURCE   DESCRIPTION
acme-bom            report  project  Acme's inventory layout
board-report        report  project  Branded summary for the leadership team
executive-summary   report  builtin  Short Word report with totals and tag compliance; Excel has one filterable sheet.
finops-cost-report  report  builtin  Standard layout with cost-allocation tag columns, checked against finops-cost-allocation.
network-review      report  project  Every field, for a network review
standard-bom        report  builtin  Summary plus one sheet per service, with readable columns and every tag as a column.
team-sheet          report  project  One sheet, our columns

Search order (first match wins):
  1. project  ~/acme-infra/.inventag/templates
  2. user     ~/.config/inventag/templates  (not created)
  3. builtin  ~/inventag-aws/inventag/templating/builtin
```

El proyecto de ejemplo también contiene las otras plantillas usadas en esta
documentación.

## 4. Úsala {#4-use-it}

```bash
inventag --template acme-bom --create-excel --account-regions us-east-1
```

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**Hojas:** `Summary`, `Resources`

Hoja `Resources`, primeras filas:

| Account | Region | Service | Type | Name | ID | ARN | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs | platform | CC-1001 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake | data | CC-2002 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports | finance | 1234 | Production |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | acme-scratch | arn:aws:s3:::acme-scratch |  |  |  |

La fila de encabezado es verde, como se definió en la plantilla.

## Comparte plantillas con tu equipo {#share-templates-with-your-team}

- **Un proyecto:** confirma `.inventag/templates/` en el repositorio del
  proyecto.
- **Todos los proyectos de tu máquina:** pon las plantillas en
  `~/.config/inventag/templates/`.
- **Una carpeta compartida o una imagen de CI:** define
  `INVENTAG_TEMPLATE_PATH=/opt/acme/inventag-templates`.

Si dos carpetas contienen una plantilla con el mismo nombre, gana la primera
según el [orden de búsqueda](./index.md#where-inventag-looks-for-templates).
`inventag templates list --all` muestra también las ocultas.

## Siguientes pasos {#next-steps}

- [Referencia de plantillas](./reference.md): todos los campos que puedes
  definir.
- [Crear un informe ejecutivo de Word con tu marca](../examples/branded-executive-report.md):
  añade un logotipo.
