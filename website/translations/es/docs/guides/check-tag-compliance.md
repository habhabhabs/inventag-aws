---
title: Comprobar etiquetas con una política
description: Comprueba que tus recursos de AWS llevan las etiquetas obligatorias con valores permitidos, usando una plantilla de política de etiquetas, y lee los resultados.
sidebar_position: 4
slug: /architecture/tag-compliance
---

# Comprobar etiquetas con una política

**Para quién es:** eres responsable de un estándar de etiquetado y quieres saber
qué recursos lo incumplen.

**Qué podrás hacer después de leerlo:** ejecutar una comprobación de etiquetas,
leer los resultados y escribir tu propia política.

## Ejecuta una comprobación {#run-a-check}

Elige una política integrada o la tuya:

```bash
inventag --template finops-cost-allocation --create-excel --account-regions us-east-1
```

InvenTag analiza como siempre y después comprueba cada recurso incluido en el
ámbito. Ejemplo de salida de una ejecución sin conexión con
`--template finops-cost-report` (datos de ejemplo):

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

## Lee los resultados {#read-the-results}

| Dónde | Qué obtienes |
|---|---|
| Excel, hoja **Tag Compliance** | Una fila por recurso incluido en el ámbito: cuenta, región, servicio, tipo, recurso, ARN, estado, etiquetas que faltan y otros problemas. Las filas no conformes van primero. Debajo de la tabla, cada regla con cuántos recursos la incumplen o tienen un valor incorrecto. |
| Excel, hoja **Summary** | Recuentos: comprobados, conformes, no conformes, fuera del ámbito y porcentaje. |
| Word, sección **Tag compliance** | Los mismos recuentos, las reglas y una tabla de recursos no conformes (hasta 100 filas por defecto). |
| `tag_compliance_<timestamp>.json` | Recuentos por regla y todos los recursos no conformes, para scripts y CI. |

Un recurso es **conforme** cuando tiene todas las etiquetas obligatorias y cada
valor cumple su regla. Los problemas se describen con detalle, por ejemplo:

- `CostCenter: '1234' does not match CC-[0-9]{4}` (formato incorrecto)
- `Environment: 'Production' is not one of prod, staging, dev, test, sandbox`
- `Owner: found 'owner' instead (tag keys are case-sensitive)`

La hoja Tag Compliance del mismo ejemplo:

**Hojas:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

Hoja `Tag Compliance`, primeras filas:

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

La sección de Word:

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
| CostCenter | Matches: CC-[0-9]&#123;4&#125; | 20 | 1 |
| Owner | Any value | 17 | 0 |
| Project | Any value | 21 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 17 | 1 |

La parte `summary` del archivo JSON:

```json title="summary"
{
  "checked": 23,
  "compliant": 1,
  "non_compliant": 22,
  "out_of_scope": 14,
  "percent_compliant": 4.3,
  "missing_by_key": {
    "CostCenter": 20,
    "Owner": 17,
    "Project": 21,
    "Environment": 17
  },
  "invalid_by_key": {
    "CostCenter": 1,
    "Owner": 0,
    "Project": 0,
    "Environment": 1
  }
}
```

Los recursos **fuera del ámbito** se cuentan pero no se comprueban: el `scope`
de la política los excluye, por ejemplo los alias de KMS, que no pueden llevar
etiquetas.

**Ten esto en cuenta antes de fiarte de los números:** InvenTag asocia las
etiquetas de la API Resource Groups Tagging con los recursos por ARN y, si el
ARN no coincide, recurre al servicio, la región y el ID del recurso. Las
pruebas sin conexión con moto comprueban esto para cada servicio con código de
descubrimiento propio. AWS real puede responder de otra forma, así que compara
unas cuantas filas de la columna ARN con la consola antes de confiar en el
resultado de una política.

## Escribe tu propia política {#write-your-own-policy}

Parte de una política integrada y cambia solo lo que difiera:

```bash
inventag templates init finops-cost-allocation --output .inventag/templates/our-tags.yaml --extend
```

```yaml
format_version: 1
kind: tag-policy
name: our-tags
description: Our cost-allocation tags
extends: finops-cost-allocation
spec:
  required_tags:
    - key: Environment                 # replaces the inherited rule
      allowed_values: [production, staging, development]
    - key: Project                     # drops an inherited tag
      remove: true
    - key: DataClassification          # adds a new one
      allowed_values: [public, internal, confidential]
  scope:
    services: [EC2, S3, RDS, LAMBDA]   # only check these services
```

Reglas de cada etiqueta:

- `allowed_values`: el valor debe ser uno de estos. Las mayúsculas y minúsculas
  no importan salvo que indiques `case_sensitive: true`.
- `pattern`: el valor completo debe coincidir con esta expresión regular.
- Ninguna de las dos: cualquier valor es válido, siempre que la etiqueta exista.

Usa `allowed_values` o `pattern` en una etiqueta, no ambas. Todos los campos
están en la [referencia de plantillas](../templates/reference.md).

## Evidencia de etiquetas para una conversación sobre un marco {#tag-evidence-for-a-framework-conversation}

Cinco políticas integradas parten de `security-baseline` y añaden las etiquetas que apoyan una conversación sobre SOC 2, HIPAA, PCI DSS, GDPR o PDPA; por ejemplo `inventag --template evidence-soc2 --create-excel`. Solo comprueban la evidencia de las etiquetas, los valores los declara el propietario del recurso y un resultado correcto no significa que la cuenta cumpla ninguno de esos marcos. Consulta [Plantillas de evidencia de etiquetas](../templates/tag-evidence.md).

## Haz fallar una canalización ante incumplimientos {#fail-a-pipeline-on-violations}

Añade una plantilla de configuración con `fail_on_tag_violations: true`.
InvenTag sigue escribiendo todos los informes y después termina con el código
3. Si además pasas `--fail-on-account-error` o `--fail-if-empty` y se cumple alguna de las dos condiciones, el código de salida es 5 o 6 en su lugar,
porque los datos están incompletos. Consulta [Aplicar una política de etiquetas en CI](../examples/tag-policy-in-ci.md).

## El script comprobador anterior {#the-older-checker-script}

`scripts/legacy/tag_compliance_checker.py --config policy.yaml` es anterior a
las plantillas y tiene sus propias opciones (`--help` las lista). Solo
comprueba que existan las claves de etiqueta obligatorias. No aplica `allowed_values`, `pattern` ni ningún otro campo de su archivo de política:
registra una advertencia y los lista en `summary.ignored_policy_fields` de su informe. Ignora las etiquetas cuya clave empieza por `aws:`,
porque las crea AWS, así que un recurso con solo etiquetas `aws:` cuenta como sin etiquetar, y una clave de etiqueta obligatoria que empiece por `aws:` es un error.
Aparte de eso, esta documentación no lo cubre. Es preferible usar plantillas de política de etiquetas.

Los scripts antiguos de `scripts/legacy/` se ejecutan con la protección de solo lectura y escriben
archivos que solo puede leer su propietario. `aws_resource_inventory.py --s3-bucket` sube los archivos
con cifrado SSE-S3.

## Siguientes pasos {#next-steps}

- [Políticas de etiquetas integradas](../templates/catalogue.md#tag-policy-templates)
- [Ejemplo: etiquetas de asignación de costes de FinOps](../examples/finops-cost-allocation.md)
