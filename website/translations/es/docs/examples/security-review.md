---
title: "Ejemplo: revisión de etiquetado de seguridad"
description: Comprueba que los recursos de AWS llevan las etiquetas Owner, Environment y DataClassification antes de una revisión de seguridad, con security-baseline.
sidebar_position: 6
---

# Ejemplo: revisión de etiquetado de seguridad

**Objetivo:** antes de una revisión de seguridad o de un simulacro de
incidente, encontrar los recursos sin propietario, sin entorno o sin
clasificación de datos.

**Necesitas:** credenciales de solo lectura.

Esto comprueba únicamente las etiquetas. No evalúa lo seguro que es ninguna
configuración, y superarlo no te hace cumplir ningún marco normativo.

## Plantilla {#template}

La política de etiquetas integrada `security-baseline` exige:

| Tag key | Regla |
|---|---|
| `Owner` | Cualquier valor |
| `Environment` | `prod`, `staging`, `dev`, `test` o `sandbox` |
| `DataClassification` | `public`, `internal`, `confidential` o `restricted` |

## Comando {#command}

```bash title="Terminal"
inventag --template standard-bom --template security-baseline \
  --create-excel --create-word --account-regions us-east-1
```

## Salida {#output}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'security-baseline': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

**Hojas:** `Summary`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

Hoja `Tag Compliance`, primeras filas:

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | Owner, Environment, DataClassification |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | Owner, Environment, DataClassification |  |

Filtra la columna "Missing tags" por `Owner` para encontrar primero los
recursos sin propietario.

## Siguientes pasos {#next-steps}

- Acuerda propietarios para los recursos que no tienen, y luego etiquétalos en
  tu código de infraestructura.
- Limita la comprobación solo a los almacenes de datos:

```yaml title=".inventag/templates/data-stores.yaml"
format_version: 1
kind: tag-policy
name: data-stores
description: Classification on data stores only
extends: security-baseline
spec:
  scope:
    services: [S3, DYNAMODB, RDS]
```
