---
title: Archivos de salida
description: Los archivos que escribe InvenTag (informes Excel y Word, JSON de cumplimiento, instantáneas y registros de cambios), con nombres, ubicaciones y contenido.
sidebar_position: 4
---

# Archivos de salida

**Para quién es:** procesas la salida de InvenTag en scripts, o explicas los
informes a otras personas.

**Qué sabrás después de leerlo:** el nombre, la ubicación y el contenido de cada
archivo que escribe InvenTag.

Todo va a la carpeta de salida: `bom_output/`, salvo que definas
`--output-directory` o `output_directory` en una plantilla de configuración. Los únicos
otros lugares donde escribe InvenTag son los archivos que nombres (`--log-file`,
`--audit-output`, `templates init --output`), tu bucket de S3 con `--s3-bucket` y,
con las opciones de Google, tu Google Drive y, con `--google-oauth-client`, un archivo
de token de inicio de sesión en `~/.config/inventag/google-token.json`.

Los archivos de salida se crean con lectura y escritura solo para tu usuario, y las
carpetas de salida nuevas también son privadas para tu usuario.

No verificado contra Windows: archivos y carpetas privados para tu usuario.

Los ejemplos de esta página proceden de ejecuciones sin conexión contra AWS simulado (datos
de ejemplo).

## Lista de archivos {#file-list}

| Archivo | Cuándo | Contenido |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`, o ninguna opción de salida | El informe de Excel |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | El informe de Word |
| `<account-id>_bom_<timestamp>.xlsx` y `.docx` | `--per-account-reports`, en lugar de los archivos `multi_account_bom_*` | Un informe por cada cuenta que tiene recursos |
| `tag_compliance_<timestamp>.json` | Hay una política de etiquetas activa | Resultados de la comprobación de etiquetas |
| `state/state_<timestamp>.json` | Cada ejecución, salvo con `--disable-state-management` | Instantánea de todos los recursos encontrados, con los valores secretos ocultos. `metadata.tags.coverage_summary` cuenta, por cuenta, cómo terminaron las llamadas de listado (`ok`, `empty`, `denied`, `throttled`, `error`, `timeout`). Las instantáneas con más de 30 días, o más allá de las 100 más recientes, se eliminan (`--state-retention-days`, `--state-max-snapshots`). |
| `state/metadata.json` | Con instantáneas | Índice de instantáneas: hora, cuenta, regiones, número de recursos, suma de comprobación |
| `changelog_<timestamp>.md` | Segunda ejecución y siguientes, salvo con `--no-generate-changelog` o `--disable-delta-detection` | Qué se añadió, eliminó o cambió desde la instantánea anterior. Consulta [Sigue los cambios](../guides/track-changes.md). |
| El archivo que nombres con `--audit-output` | Cuando lo pides | Todas las operaciones de AWS que llamó la ejecución |
| `state/partial/<key>/<account-id>.json` | Una ejecución en la que fallaron algunas cuentas | Resultados de las cuentas que terminaron; `--resume` los reutiliza y se borran tras una ejecución completa |

`<timestamp>` es `YYYYMMDD_HHMMSS`. Los nombres del informe, de Word, del registro de cambios y del cumplimiento de etiquetas usan la hora local de tu equipo. La instantánea y la carpeta de S3 usan UTC.

## Informe de Excel {#excel-report}

**Sin plantilla**, el libro tiene:

- **Summary:** Service, Resource Count, Percentage y un total.
- **Una hoja por servicio** (por ejemplo `EC2`, `S3`, `VPC`), ordenadas por
  nombre de servicio, con todos los campos encontrados en sus recursos, incluidas las
  columnas aplanadas `raw_data.*` y `tags.*`. Un campo de la API que es un mapa con ID como claves
  ocupa una sola celda JSON. Las filas se ordenan por tipo, nombre e ID.
  Cada fila tiene una columna `source` (`service-api`, `tagging-api` o `billing`:
  la API que la devolvió), una columna `sources` (todas ellas, unidas con `+`) y
  una columna `detail_level` (`full` para las filas de la API del propio servicio,
  `identity` para las demás).
- Hojas **Network Analysis** y **Security Analysis**, solo con
  `--enable-network-analysis` o `--enable-security-analysis`.
- Hoja **Cost Analysis**, solo con `--enable-cost-analysis`: costes mensuales
  estimados a partir de la API AWS Pricing, no tu factura.

Los valores de los campos que suelen contener secretos, como las variables de
entorno de Lambda, las salidas de pilas de CloudFormation, los argumentos de
desencadenadores de Glue, las cadenas de conexión y las URL firmadas, aparecen como `***REDACTED***` en todos los informes,
instantáneas y registros. Los nombres de los campos se mantienen. Consulta
[Estado de las funciones](../getting-started/status.md#what-inventag-finds-and-what-it-does-not).

**Con una plantilla de informe**, el diseño sigue la plantilla:

- **Summary:** título, hora de generación, el número de cuentas y regiones, una
  tabla Service / Resources / Share y, con una política de etiquetas, los recuentos de
  cumplimiento.
- **Hojas de recursos:** una por servicio, o una sola hoja con `layout:
  single-sheet`. Las filas de encabezado tienen estilo, están inmovilizadas y se pueden filtrar de forma predeterminada.
- **Tag Compliance** (con una política de etiquetas): una fila por recurso dentro del alcance, y luego
  una tabla de reglas con los recuentos de faltantes e inválidos.

Los nombres de las hojas siguen las reglas de Excel: como máximo 31 caracteres, sin
`[ ] : * ? / \`. Los nombres duplicados reciben un número. Los valores de celda que empiezan con `=`
se almacenan como texto, nunca como fórmulas. Las filas se ordenan por servicio, tipo,
nombre e ID.

Las vistas previas de cada diseño, hechas a partir de archivos reales, están en
[Plantillas integradas](../templates/catalogue.md).

## Informe de Word {#word-report}

**Sin plantilla:** un título, un resumen ejecutivo, una tabla de servicios y
hasta 50 recursos por servicio en seis columnas: Name, Id, Type, Region, Tags y Service. Si ningún recurso del servicio tiene nombre, las columnas son Id, Type, Region, Tags, Service y Source Account Name.

**Con una plantilla de informe:** las secciones listadas en `word.sections`. Las tablas
tienen una fila de encabezado que se repite en cada página y está marcada como encabezado para
los lectores de pantalla. El logotipo, si lo hay, lleva texto alternativo.

## JSON de cumplimiento de etiquetas {#tag-compliance-json}

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
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

## Instantáneas {#snapshots}

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

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

## JSON de auditoría {#audit-json}

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 96,
  "allowed_calls": 96,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## Objetos de S3 {#s3-objects}

Con `--s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/`, cada ejecución
coloca sus archivos en una carpeta con el nombre de la ejecución:

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

## Salida del terminal {#terminal-output}

Sin `--verbose`, una ejecución imprime advertencias, errores y los archivos escritos. Con
una plantilla, cada archivo se imprime como `Wrote <path>`, seguido de un resumen de una línea de la
política de etiquetas cuando hay una activa. Sin plantilla, el informe predeterminado se imprime como `Data exported to <path>`.

## Códigos de salida {#exit-codes}

Consulta la [Referencia de la línea de comandos](./cli.md#exit-codes).
