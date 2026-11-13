---
title: "Ejemplo: etiquetas de asignación de costes para FinOps"
description: Descubre qué recursos de AWS no tienen las etiquetas CostCenter, Owner, Project y Environment que necesitan los informes de costes, con finops-cost-report.
sidebar_position: 5
---

# Ejemplo: etiquetas de asignación de costes para FinOps

**Objetivo:** un informe para el equipo de FinOps (operaciones financieras de
la nube) o de finanzas que muestre, por recurso, si las etiquetas de
asignación de costes están presentes y son válidas.

**Necesitas:** credenciales de solo lectura. Las etiquetas solo aparecen en los
informes de costes de AWS después de activarlas como etiquetas de asignación de
costes en la consola de AWS Billing and Cost Management. InvenTag muestra qué
recursos las llevan; no calcula costes.

## Plantilla {#template}

`finops-cost-report` (una plantilla de informe) muestra CostCenter, Owner,
Project y Environment como columnas y activa la política de etiquetas
`finops-cost-allocation`:

| Tag key | Regla en `finops-cost-allocation` |
|---|---|
| `CostCenter` | `CC-` y cuatro dígitos, por ejemplo `CC-1234` |
| `Owner` | Cualquier valor |
| `Project` | Cualquier valor |
| `Environment` | `prod`, `staging`, `dev`, `test` o `sandbox` |

Si tus centros de coste tienen otro formato, adapta la política y conserva el
informe:

```yaml title=".inventag/templates/our-cost-tags.yaml"
format_version: 1
kind: tag-policy
name: our-cost-tags
description: Our cost centres are five-digit numbers
extends: finops-cost-allocation
spec:
  required_tags:
    - key: CostCenter
      pattern: "[0-9]{5}"
```

## Comando {#command}

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
# with your own policy:
inventag --template finops-cost-report --template our-cost-tags --create-excel
```

## Salida {#output}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

**Hojas:** `Summary`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

Hoja `Tag Compliance`, primeras filas:

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

<img src={require("../assets/examples/img/finops-tag-compliance-sheet.png").default} alt="Hoja Tag Compliance: una fila por recurso con cuenta, región, servicio, tipo, recurso, ARN, estado, etiquetas que faltan y problemas, seguida de la tabla de reglas de la política (datos de ejemplo)" width="1074" height="295" loading="lazy" />

La sección Tag compliance del documento de Word:

**Esquema del documento:**

- **Cost Allocation Tag Report** (título)
- Summary
- Tag compliance
  - Required tags
  - Non-compliant resources
- Resources by service
- About this report

Una tabla del documento:

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| CostCenter | Matches: CC-[0-9]&#123;4&#125; | 19 | 1 |
| Owner | Any value | 16 | 0 |
| Project | Any value | 20 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 16 | 1 |

El archivo JSON:

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 22,
    "compliant": 1,
    "non_compliant": 21,
    "out_of_scope": 14,
    "percent_compliant": 4.5,
    "missing_by_key": {
      "CostCenter": 19,
      "Owner": 16,
      "Project": 20,
      "Environment": 16
    },
    "invalid_by_key": {
      "CostCenter": 1,
      "Owner": 0,
      "Project": 0,
      "Environment": 1
    }
  },
  "non_compliant_resources": [
    {
      "account": "123456789012",
      "service": "S3",
      "resource_type": "Bucket",
      "resource_id": "acme-reports",
      "arn": "arn:aws:s3:::acme-reports",
      "region": "us-east-1",
      "missing": [],
      "invalid": [
        "CostCenter: '1234' does not match CC-[0-9]{4}",
        "Environment: 'Production' is not one of prod, staging, dev, test, sandbox"
      ]
    }
  ]
}
```

[Descargar el JSON de cumplimiento de etiquetas de ejemplo](pathname:///inventag-aws/downloads/tag-compliance-sample.json) (8 KB, datos de ejemplo)

## Siguientes pasos {#next-steps}

- Envía el documento de Word a los responsables de presupuesto. Su sección Tag
  compliance enumera los recursos que no cumplen.
- Haz un seguimiento semanal: [Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md).
