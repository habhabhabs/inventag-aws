---
title: Plantillas de evidencia de etiquetas
description: Qué comprueban las cinco plantillas de evidencia (SOC 2, HIPAA, PCI DSS, GDPR, PDPA), qué no afirman nunca, qué etiquetas y valores usan y cómo copiar una y cambiar su alcance.
sidebar_position: 6
---

# Plantillas de evidencia de etiquetas

**A quién va dirigida esta página:** te preparas para una conversación sobre SOC 2, HIPAA, PCI DSS, GDPR o PDPA y quieres saber qué recursos no tienen registrada una respuesta a las preguntas con las que empieza esa conversación.

**Qué podrás hacer después de leerla:** elegir la plantilla de tu marco, leer bien sus resultados y copiarla para adaptarla a tus propias etiquetas y tipos de recurso.

## Qué comprueban {#what-they-check}

Cada plantilla es una política de etiquetas. Comprueba que cada recurso dentro del alcance tenga las etiquetas que lista la plantilla, con un valor de la lista permitida o con la forma permitida. Nada más. Las etiquetas son la evidencia: un registro, escrito por el propietario del recurso, del alcance, del tipo de datos, de la retención o de la ubicación.

Las cinco plantillas están en el [catálogo integrado](./catalogue.md#tag-evidence-templates). El conjunto completo es `evidence-soc2`, `evidence-hipaa`, `evidence-pci-dss`, `evidence-gdpr` y `evidence-pdpa`.

## Qué no afirman nunca {#what-they-never-claim}

- Solo comprueban la evidencia de las etiquetas. No evalúan controles, salvaguardas, segmentación, licitud ni consentimiento.
- Los valores de las etiquetas los declara el propietario del recurso. InvenTag no puede verificarlos.
- Un resultado correcto no significa que la cuenta cumpla SOC 2, HIPAA, PCI DSS, GDPR o PDPA. Significa que las etiquetas están.
- InvenTag es de solo lectura. Lee etiquetas y escribe informes; nunca modifica un recurso.

Cada plantilla lo dice en su descripción y en la cabecera de su archivo. Conserva la frase «Checks tag evidence only; certifies nothing.» en la descripción de cualquier plantilla que copies.

## Las etiquetas {#the-tags}

Las cinco comprueban además las tres etiquetas de `security-baseline`: `Owner` (cualquier valor), `Environment` (`prod`, `staging`, `dev`, `test`, `sandbox`) y `DataClassification` (`public`, `internal`, `confidential`, `restricted`). `evidence-hipaa` sustituye la última regla y añade `phi`.

| Plantilla | Clave de etiqueta | Valores permitidos |
|---|---|---|
| `evidence-soc2` | `Soc2Scope` | `in-scope`, `out-of-scope` |
|  | `SystemName` | Cualquier texto que no esté vacío |
|  | `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual`, `other` |
|  | `Criticality` | `high`, `medium`, `low` |
| `evidence-hipaa` | `PHI` | `yes`, `no` |
|  | `DataClassification` | `public`, `internal`, `confidential`, `restricted`, `phi` |
|  | `RetentionPeriod` | Un número y `d` o `y`, o `indefinite` |
| `evidence-pci-dss` | `PciScope` | `cde`, `connected`, `out-of-scope` |
|  | `CardholderData` | `stores`, `processes`, `transmits`, `none` (un solo valor) |
| `evidence-gdpr` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `ProcessingRecord` | De 1 a 64 letras, dígitos, `.`, `_` o `-` |
|  | `DataResidency` | `eu`, `uk`, `other` |
|  | `RetentionPeriod` | Un número y `d` o `y`, o `indefinite` |
| `evidence-pdpa` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `Purpose` | Cualquier texto que no esté vacío |
|  | `RetentionPeriod` | Un número y `d` o `y`, o `indefinite` |
|  | `DataLocation` | `sg`, `overseas` |

`evidence-gdpr` y `evidence-pdpa` usan la misma clave `PersonalData` y los mismos valores. Si etiquetas un recurso para una, la etiqueta ya sirve para la otra. Una ejecución usa una plantilla, así que ejecuta la comprobación dos veces para ver ambas.

Un valor de etiqueta puede contener letras, dígitos, espacios y `_ . : / = + - @`. Todos los valores anteriores caben.

## Copia una plantilla y cambia su alcance {#copy-a-template-and-change-its-scope}

`evidence-soc2` mira todos los tipos de recurso salvo los alias de KMS. Las otras cuatro listan los tipos de recurso que miran. La lista pertenece a toda la plantilla, así que también limita las comprobaciones de `Owner`, `Environment` y `DataClassification`. Los recursos de otros tipos cuentan como fuera del alcance, no como fallos.

Para ver exactamente qué comprueba una plantilla, imprímela tras la herencia:

```bash title="Terminal"
inventag templates show evidence-hipaa --resolved
```

Para crear tu propia copia que hereda todo:

```bash title="Terminal"
inventag templates init evidence-soc2 --output .inventag/templates/our-soc2.yaml --extend
```

Para comprobar menos servicios, define `services` en tu copia:

```yaml title=".inventag/templates/data-soc2.yaml"
format_version: 1
kind: tag-policy
name: data-soc2
description: SOC 2 tag evidence for data stores only. Checks tag evidence only; certifies nothing.
extends: evidence-soc2
spec:
  scope:
    services: [S3, DYNAMODB, SQS]
```

Para comprobar más tipos de recurso, copia la lista completa `resource_types` de `inventag templates show <name> --resolved` y añade el tipo. Una lista en tu copia sustituye a la heredada; no se suma a ella. Usa el valor de la columna Type de tu informe para el tipo nuevo.

Valida la copia antes de usarla y después ejecútala:

```bash title="Terminal"
inventag templates validate data-soc2
inventag --template data-soc2 --create-excel
```

## Lo que el motor no puede expresar {#what-the-engine-cannot-express}

- Una plantilla de política de etiquetas por ejecución.
- No hay reglas «solo si». Un recurso con `PersonalData=none` sigue necesitando una etiqueta `ProcessingRecord`, con el valor `none`.
- No hay comprobaciones cruzadas entre etiquetas ni con la región del recurso. `PHI=no` junto con `DataClassification=phi` no se señala, ni tampoco `DataResidency=eu` en un recurso de otra región.
- Los patrones distinguen mayúsculas: `7y` pasa y `7Y` no. Las listas de valores permitidos no distinguen mayúsculas.
- El patrón de `ProcessingRecord` solo comprueba la forma del ID. Cámbialo por tu propio formato de ID en tu copia.

## Próximos pasos {#next-steps}

- [Ejemplo: comprobar la evidencia de etiquetas antes de una conversación sobre el alcance de SOC 2](../examples/evidence-soc2.md)
- [Adaptar una plantilla](./adapt-a-template.md)
- [Comprobar etiquetas con una política](../guides/check-tag-compliance.md)
