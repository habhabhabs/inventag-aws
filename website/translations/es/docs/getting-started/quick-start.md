---
title: Generar tu primer informe
description: Analiza una cuenta y una región de AWS con InvenTag y abre los informes de lista de materiales en Excel y Word que genera, en unos diez minutos.
sidebar_position: 3
---

# Generar tu primer informe

**Para quién es:** ya has [instalado InvenTag](./installation.md) y tienes
credenciales de AWS de solo lectura.

**Qué podrás hacer después de leerlo:** analizar una cuenta, abrir los informes
de Excel y Word y elegir un diseño más claro con una plantilla.

Toda la salida de ejemplo de esta página procede de una ejecución sin conexión contra AWS
simulado (datos de ejemplo). La cuenta `123456789012` y los recursos `acme-*` son inventados.

## 1. Comprueba en qué cuenta estás {#1-check-which-account-you-are-in}

```bash title="Terminal"
aws sts get-caller-identity
```

InvenTag analiza la cuenta a la que pertenecen estas credenciales.

## 2. Analiza una región {#2-scan-one-region}

Empieza con poco. Una región es rápida y barata.

Este comando solo lee. Una protección integrada bloquea las llamadas que podrían
cambiar tu cuenta ([configurar el acceso de solo lectura](../guides/read-only-access.md)).
De forma predeterminada también envía solicitudes a Cost Explorer, que AWS cobra;
añade `--no-billing-validation` para omitirlas ([cuánto cuesta una ejecución](#what-a-run-costs)).

```bash title="Terminal"
inventag --create-excel --create-word --account-regions us-east-1
```

- `--create-excel` y `--create-word` eligen los archivos que se escriben. Sin
  ninguna de las dos, obtienes solo Excel.
- `--account-regions` limita el análisis a las regiones que indiques, separadas por
  comas. Sin ella, InvenTag analiza todas las regiones habilitadas en la cuenta,
  lo que tarda más. IAM, la lista de buckets de S3, CloudFront y Route 53 se
  leen siempre una vez desde `us-east-1`, sean cuales sean las regiones que indiques.

Al final ves dónde se guardaron los archivos:

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Word document saved: bom_output/multi_account_bom_20261112_090000.docx
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

El aviso solo indica que no nombraste ninguna cuenta, así que InvenTag usó tus
credenciales actuales. Añade `--verbose` para ver cada paso.

## 3. Abre los informes {#3-open-the-reports}

El libro de Excel tiene una hoja **Summary** y una hoja por servicio. Sin
plantilla, cada hoja de servicio lista todos los campos que InvenTag encontró, por lo que las
hojas son anchas:

**Hojas:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`

Hoja `S3`, primeras filas:

| service | type | id | name | arn | account_id | source_account_id | source_account_name | ... |
|---|---|---|---|---|---|---|---|---|
| S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports |  | 123456789012 | AWS Account 123456789012 (moto) | ... |

La hoja tiene 33 columnas; se muestran las 8 primeras.

El documento de Word tiene un resumen, una tabla de servicios y hasta 50 recursos
por servicio:

**Esquema del documento:**

- **AWS Resource Inventory - BOM Report** (título)
- Executive Summary
  - Service Summary
- Detailed Resource Inventory
  - ATHENA Resources (1)
  - DYNAMODB Resources (1)
  - EC2 Resources (4)
  - EVENTS Resources (1)
  - IAM Resources (1)
  - KMS Resources (14)
  - LAMBDA Resources (1)
  - S3 Resources (4)
  - VPC Resources (10)
- Report Information

Una tabla del documento:

| Service | Resource Count | Percentage |
|---|---|---|
| ATHENA | 1 | 2.7% |
| DYNAMODB | 1 | 2.7% |
| EC2 | 4 | 10.8% |
| EVENTS | 1 | 2.7% |

(9 filas en total; se muestran 4.)

InvenTag también guarda una instantánea de la ejecución en `bom_output/state/`.

## 4. Elige un diseño con una plantilla {#4-choose-a-layout-with-a-template}

Una [plantilla de informe](../templates/index.md) te da nombres de columna legibles,
una columna por etiqueta, una fila de encabezado fija y botones de filtro:

```bash title="Terminal"
inventag --template standard-bom --create-excel --create-word --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

Mira cómo queda el resultado en
[Plantillas integradas](../templates/catalogue.md#standard-bom).

## 5. Revisa tus etiquetas {#5-check-your-tags}

Añade una política de etiquetas para ver qué recursos carecen de etiquetas:

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

El libro ahora tiene una hoja **Tag Compliance** que lista lo que falta en
cada recurso. Más en [Comprobar etiquetas con una política](../guides/check-tag-compliance.md).

## Cuánto cuesta una ejecución {#what-a-run-costs}

Las llamadas de solo lectura que hace InvenTag son gratuitas. Las llamadas
`GetCostAndUsage` de Cost Explorer no: AWS cobra por solicitud, y una ejecución
predeterminada hace dos por cada cuenta en nuestra prueba sin conexión. Consulta los
[precios actuales de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Añade `--no-billing-validation` para no hacer ninguna llamada a Cost Explorer.

## Siguientes pasos {#next-steps}

- [Estado de las funciones y limitaciones conocidas](./status.md): léelo antes de
  depender de una opción.
- [Elegir qué analizar y qué generar](../guides/run-a-scan.md)
- [Ejemplos](../examples/index.md): recetas para copiar y pegar.
