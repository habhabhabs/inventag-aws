---
title: Seguir los cambios entre ejecuciones
description: Cómo guarda InvenTag una instantánea de cada ejecución en bom_output/state, qué contiene el informe de cambios y qué debes saber antes de fiarte de él.
sidebar_position: 6
slug: /architecture/state-management
---

# Seguir los cambios entre ejecuciones

**Para quién es:** ejecutas InvenTag de forma programada y quieres saber qué ha
cambiado.

**Qué sabrás después de leerlo:** dónde se guardan las instantáneas, qué
contiene el informe de cambios y cómo comparar ejecuciones por tu cuenta.

## Instantáneas {#snapshots}

Cada ejecución guarda lo que encontró en la carpeta de salida. Tras dos
ejecuciones contra AWS simulado (datos de ejemplo):

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

Cada instantánea contiene todos los recursos que encontró la ejecución:

```json title="state/state_<timestamp>.json (structure)"
{
  "top_level_keys": [
    "compliance_data",
    "metadata",
    "network_analysis",
    "resources",
    "security_analysis"
  ],
  "one_resource": {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "acme-app-logs",
    "arn": "arn:aws:s3:::acme-app-logs",
    "region": "us-east-1",
    "tags": {
      "Environment": "prod",
      "Owner": "platform",
      "CostCenter": "CC-1001",
      "Project": "storefront",
      "DataClassification": "internal"
    },
    "source_account_id": "123456789012"
  }
}
```

Conserva la carpeta `state/` entre ejecuciones, por ejemplo como caché de CI o
en un bucket, si quieres historial. Desactiva las instantáneas con
`--disable-state-management`.

## El informe de cambios {#the-change-report}

A partir de la segunda ejecución, InvenTag compara la nueva instantánea con la
anterior y escribe `changelog_<timestamp>.md` en la carpeta de salida. La
primera ejecución no tiene con qué comparar, así que no escribe informe de
cambios.

En este ejemplo se añadió un bucket entre las dos ejecuciones. El informe de
cambios lo lista:

<details>
<summary>changelog_20261112_090100.md (primeras 30 líneas)</summary>

```markdown
# Multi-Account Infrastructure Changes

**Generated:** 2026-11-12T09:00:00+00:00

## State Comparison

- **from_state:** 20261112_090000
- **to_state:** 20261112_090100
- **comparison_timestamp:** 2026-11-12T09:00:00+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total Changes | 1 |
| Critical Changes | 0 |
| High Severity | 0 |
| Security Changes | 0 |
| Compliance Changes | 0 |
| Network Changes | 0 |

**Most Impacted Services:**
- S3: 1 changes

## S3 Service Changes

Changes detected in S3 service resources

### New Bucket 'acme-new-bucket' was created in S3
- **Type:** added
```

</details>

El informe tiene una tabla resumen y después una sección por cada servicio con
cambios. Cada cambio tiene un tipo (como `added`), una gravedad, el recurso y
su ARN.

Qué debes saber:

- Compara una ejecución con la anterior. No compara con una ejecución más
  antigua que elijas.
- Compara los recursos que encontró cada ejecución. Usa las mismas regiones,
  servicios y filtros en ambas, para que un cambio de ámbito no se lea como un
  cambio en tu infraestructura.
- `--no-generate-changelog` detiene el informe pero conserva las instantáneas.
  `--disable-delta-detection` también lo detiene. `--disable-state-management`
  detiene las instantáneas y los informes.
- InvenTag elimina las instantáneas con más de 30 días o que superan las 100
  más recientes. Un trabajo programado en un ejecutor nuevo no tiene ninguna
  instantánea anterior, así que conserva la carpeta `state/` entre ejecuciones.

## Compara dos instantáneas por tu cuenta {#compare-two-snapshots-yourself}

Puedes comparar dos instantáneas cualesquiera, porque cada una es JSON con una
lista `resources`:

```bash
python3 - <<'EOF'
import json, sys, glob
old, new = sorted(glob.glob("bom_output/state/state_*.json"))[-2:]
ids = lambda f: {r.get("arn") or r.get("id") for r in json.load(open(f))["resources"]}
a, b = ids(old), ids(new)
print("Added:", sorted(b - a))
print("Removed:", sorted(a - b))
EOF
```

Ejemplo de salida tras añadir un bucket entre dos ejecuciones (datos de
ejemplo):

```text title="Terminal"
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

## Siguientes pasos {#next-steps}

- [Estado de las funciones y limitaciones conocidas](../getting-started/status.md)
- [Ejecutar InvenTag en CI/CD](./run-in-ci.md)
