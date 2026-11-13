---
title: "Ejemplo: informe ejecutivo de Word con tu marca"
description: Genera un informe breve de Word en horizontal con tu logotipo, tus colores y un resumen del cumplimiento de etiquetas, usando una plantilla de informe.
sidebar_position: 7
---

# Ejemplo: informe ejecutivo de Word con tu marca

**Objetivo:** un documento breve de Word para la dirección con tu logotipo y
tus colores: totales, servicios y cumplimiento de etiquetas, sin tablas por
recurso.

**Necesitas:** credenciales de solo lectura y un logotipo en un archivo PNG,
JPEG, GIF o BMP. Word no puede incrustar logotipos SVG.

## Plantilla {#template}

Pon el logotipo junto a la plantilla, en la misma carpeta o en una subcarpeta:

```text title="Project layout"
.inventag/templates/
  board-report.yaml
  brand/
    acme-logo.png
```

```yaml title=".inventag/templates/board-report.yaml"
format_version: 1
kind: report
name: board-report
description: Branded summary for the leadership team
extends: executive-summary
spec:
  title: Cloud Estate Summary
  subtitle: Quarterly review
  company_name: Acme Ltd
  logo: brand/acme-logo.png
  logo_alt_text: Acme Ltd logo        # read by screen readers
  colors:
    header_fill: "4B2E83"             # 10.4:1 contrast with white text
  tag_policy: security-baseline
  word:
    orientation: landscape
```

## Comando {#command}

```bash title="Terminal"
inventag templates validate board-report
inventag --template board-report --create-word --account-regions us-east-1
```

## Salida {#output}

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/board-report.yaml (report 'board-report')
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Tag policy 'security-baseline': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

**Esquema del documento:**

- **Cloud Estate Summary** (título)
- Summary
- Resources by service
- Tag compliance
  - Required tags
  - Non-compliant resources
- About this report

Una tabla del documento:

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| Owner | Any value | 16 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 16 | 1 |
| DataClassification | One of: public, internal, confidential, restr... | 21 | 0 |

<img src={require("../assets/examples/img/board-report-word-page1.png").default} alt="Primera página del informe de Word en horizontal con marca: un logotipo cuadrado morado, el título Cloud Estate Summary, Quarterly review, Prepared for Acme Ltd y la lista de resumen (datos de ejemplo)" width="977" height="736" loading="lazy" />

[Descargar el informe de Word de ejemplo](pathname:///inventag-aws/downloads/board-report-sample.docx) (38 KB, datos de ejemplo)

Si falta el logotipo, o no es una imagen compatible con Word, la ejecución se
detiene antes de analizar:

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   ~/acme-infra/.inventag/templates/board-report.yaml:10: spec.logo: logo file not found: ~/acme-infra/.inventag/templates/brand/acme-logo.png
$ echo $?
1
```

## Siguientes pasos {#next-steps}

- Mantén los colores legibles: elige un color de encabezado con una relación de
  contraste de al menos 4,5:1 respecto al texto del encabezado.
- Añade el inventario completo como archivo de Excel:
  `inventag --template board-report --create-word --create-excel`.
