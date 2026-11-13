---
title: "Ejemplo: comprobar la evidencia de etiquetas antes de una conversación sobre el alcance de SOC 2"
description: Encuentra los recursos de AWS sin etiquetas de alcance SOC 2, nombre de sistema, método de aprovisionamiento o criticidad, con la plantilla evidence-soc2.
sidebar_position: 10
---

# Ejemplo: comprobar la evidencia de etiquetas antes de una conversación sobre el alcance de SOC 2

:::note

Esto comprueba únicamente la evidencia de las etiquetas. Los valores de las
etiquetas los declara el propietario del recurso e InvenTag no los verifica. Un
resultado correcto no significa que la cuenta cumpla SOC 2.

:::

**Objetivo:** antes de hablar con un auditor o con un cliente sobre qué
sistemas están dentro del alcance de SOC 2, listar los recursos que no tienen
registrados el alcance, el nombre del sistema, el método de aprovisionamiento
ni la criticidad.

**Necesitas:** credenciales de solo lectura. InvenTag lee etiquetas; no evalúa
controles.

## Plantilla {#template}

La política de etiquetas integrada `evidence-soc2` parte de `security-baseline`
(`Owner`, `Environment` y `DataClassification`) y añade cuatro etiquetas:

| Clave de etiqueta | Regla |
|---|---|
| `Soc2Scope` | `in-scope` o `out-of-scope` |
| `SystemName` | Cualquier texto que no esté vacío |
| `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual` u `other` |
| `Criticality` | `high`, `medium` o `low` |

Cubre todos los tipos de recurso salvo los alias de KMS. Consulta el
[catálogo de plantillas](../templates/catalogue.md#evidence-soc2) para ver qué
puede mostrar y qué no.

## Comando {#command}

```bash title="Terminal"
inventag --template evidence-soc2 --create-excel --account-regions us-east-1
```

## Salida {#output}

La cuenta de ejemplo tiene cuatro buckets, una tabla de DynamoDB y una cola,
etiquetados de formas distintas, además de los recursos predeterminados que
tiene toda cuenta.

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'evidence-soc2': 2 of 18 resources compliant (11.1%), 16 non-compliant, 14 out of scope.
```

Los 14 recursos fuera del alcance son alias de KMS. De los 16 recursos a los
que les falta algo, 12 son recursos predeterminados que nadie etiquetó (la VPC
predeterminada con sus subredes, tabla de rutas, ACL de red y grupo de
seguridad, un grupo de trabajo de Athena y el bus de eventos predeterminado). La
columna de estado solo indica si el recurso tiene todas las etiquetas de la
plantilla con un valor permitido.

**Hojas:** `Summary`, `ATHENA`, `DYNAMODB`, `EVENTS`, `KMS`, `S3`, `SQS`, `VPC`, `Tag Compliance`

Hoja `Tag Compliance`, primeras filas:

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | arn:aws:s3:::acme-data-lake | Non-compliant | Criticality |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | arn:aws:s3:::acme-reports | Non-compliant |  | Soc2Scope: 'yes' is not one of in-scope, out-... |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | arn:aws:s3:::acme-scratch | Non-compliant | Owner, Environment, DataClassification, Soc2S... |  |
| 123456789012 | us-east-1 | SQS | Queue | acme-jobs | arn:aws:sqs:us-east-1:123456789012:acme-jobs | Non-compliant | DataClassification, Soc2Scope, SystemName, Cr... |  |
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Compliant |  |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | arn:aws:s3:::acme-app-logs | Compliant |  |  |

Lo que dicen las filas:

- `acme-data-lake` no tiene la etiqueta `Criticality`.
- `acme-reports` tiene `Soc2Scope` con el valor `yes`, que no es uno de los
  valores permitidos.
- `acme-scratch` no tiene etiquetas.
- `acme-jobs` tiene `Owner`, `Environment` y `ManagedBy`, pero no
  `DataClassification`, `Soc2Scope`, `SystemName` ni `Criticality`.
- `acme-app-logs` tiene todas las etiquetas con un valor permitido.
- `acme-orders` está marcado como `out-of-scope` por su propietario y aun así
  tiene todas las etiquetas. Lo que se comprueba es que la respuesta esté
  registrada, no cuál es la respuesta.

Para ver qué etiqueta falta con más frecuencia, lee el resumen del archivo JSON:

```json title="tag_compliance_20261112_090000.json (summary, two fields)"
{
  "missing_by_key": {
    "Owner": 13,
    "Environment": 13,
    "DataClassification": 14,
    "Soc2Scope": 14,
    "SystemName": 14,
    "ManagedBy": 13,
    "Criticality": 15
  },
  "invalid_by_key": {
    "Owner": 0,
    "Environment": 0,
    "DataClassification": 0,
    "Soc2Scope": 1,
    "SystemName": 0,
    "ManagedBy": 0,
    "Criticality": 0
  }
}
```

## Lo que esto no te dice {#what-this-does-not-tell-you}

- No te dice que el alcance sea correcto, que exista o funcione un control, ni
  qué probaría un auditor.
- No comprueba que `ManagedBy` sea verdad. Compáralo con las etiquetas
  `aws:cloudformation:*` que añade AWS.
- Una etiqueta presente solo significa que el propietario escribió algo.

## Próximos pasos {#next-steps}

- Etiqueta los recursos predeterminados o reduce la política para que no se
  comprueben: copia `evidence-soc2` en tu proyecto y define
  `spec.scope.services`, como en
  [Ejemplo: revisión de etiquetado de seguridad](./security-review.md#next-steps).
- Empieza en modo solo informe en CI:
  [Ejemplo: aplicar una política de etiquetas en CI](./tag-policy-in-ci.md).
- Escribe tus propias reglas:
  [Comprobar etiquetas con una política](../guides/check-tag-compliance.md#write-your-own-policy).
