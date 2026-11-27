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
| `multi_account_bom_<timestamp>.html` | `--create-html` | El informe HTML. Consulta [Informe HTML](#html-report). |
| `<account-id>_bom_<timestamp>.xlsx`, `.docx` y `.html` | `--per-account-reports`, en lugar de los archivos `multi_account_bom_*` | Un informe por cada cuenta que tiene recursos |
| `tag_compliance_<timestamp>.json` | Hay una política de etiquetas activa | Resultados de la comprobación de etiquetas |
| `state/state_<timestamp>.json` | Cada ejecución, salvo con `--disable-state-management` | Instantánea de todos los recursos encontrados, con los valores secretos ocultos. `metadata.tags.coverage_summary` cuenta, por cuenta, cómo terminaron las llamadas de listado (`ok`, `empty`, `denied`, `throttled`, `error`, `timeout`, y `out_of_scope` para los servicios que `--account-services` dejó fuera). `metadata.tags.units_not_read` lista los listados que no se leyeron (solo cuando alguno falló), y `metadata.tags.inventag_version` nombra la versión de InvenTag que escribió la instantánea. Las instantáneas con más de 30 días, o más allá de las 100 más recientes, se eliminan (`--state-retention-days`, `--state-max-snapshots`). |
| `state/metadata.json` | Con instantáneas | Índice de instantáneas: hora, cuenta, regiones, número de recursos, suma de comprobación |
| `policy_findings_<timestamp>.json` | `--policy` (el valor por defecto de `--policy-format`), `--finops-checks` con `--template`, o `inventag policy check --format json` | El resultado de comprobar políticas sobre una instantánea. Consulta [Hallazgos de las políticas](#policy-findings). |
| `policy_findings_<timestamp>.sarif`, `.xml` y `.md` | `--policy-format sarif`, `junit` o `markdown`, o las mismas palabras en `--format` de `inventag policy check` | El mismo resultado como SARIF 2.1.0, JUnit XML y Markdown. `junit` escribe `.xml` y `markdown` escribe `.md`. |
| `changelog_<timestamp>.md` | Segunda ejecución y siguientes, salvo con `--no-generate-changelog` o `--disable-delta-detection` | Qué se añadió, eliminó o cambió desde la instantánea anterior. Consulta [Sigue los cambios](../guides/track-changes.md). |
| El archivo que nombres con `--audit-output` | Cuando lo pides | Todas las operaciones de AWS que llamó la ejecución |
| `state/partial/<key>/<account-id>.json` | Una ejecución en la que fallaron algunas cuentas | Resultados de las cuentas que terminaron; `--resume` los reutiliza y se borran tras una ejecución completa |

`<timestamp>` es `YYYYMMDD_HHMMSS`. Los nombres del informe, de Word, del registro de cambios y del cumplimiento de etiquetas usan la hora local de tu equipo. La instantánea y la carpeta de S3 usan UTC. El `<timestamp>` de un archivo `policy_findings_` es la hora guardada en la instantánea que se comprobó (UTC), no el reloj de la comprobación.

El libro predeterminado tiene una columna `raw_data.*` por cada campo de la API, así que sus hojas pueden ser anchas. Una instantánea es JSON con sangría y contiene todo el `raw_data` de cada recurso, así que puede ser grande. Ninguna opción omite las columnas `raw_data.*` ni comprime una instantánea; ambas están previstas para una versión posterior.

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
  estimados a partir de la API AWS Pricing, no tu factura, y una tabla del coste
  facturado por cada cuenta y servicio, de Cost Explorer. Consulta
  [Hoja Cost Analysis](#cost-analysis-sheet).
- Hoja **FinOps**, la última, solo con `--finops-checks`: consulta
  [Hoja FinOps y la clave `finops_checks`](#finops-sheet-and-the-finops_checks-key).

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

## Hoja FinOps y la clave `finops_checks` {#finops-sheet-and-the-finops_checks-key}

Con `--finops-checks`, el libro predeterminado termina con una hoja `FinOps`.
Su primera línea es una nota; después vienen los resultados listados con las
columnas `Check ID`, `Check`, `Result`, `Reason`, `Account`, `Region`,
`Service`, `Resource Type`, `Resource ID`, `Name` y `Observed`, ordenados por
ID de comprobación, cuenta, región e ID de recurso. Le sigue una tabla con los
recuentos de cada comprobación (`Fail`, `Not evaluated`, `Pass`). Con
`--template` no se escribe ninguna hoja `FinOps`.

La línea de comandos no escribe ningún archivo JSON con estos resultados. En
Python, el resultado de `CloudBOMGenerator.generate_multi_account_bom()` tiene
la clave `finops_checks`, y también la tiene el `metadata` de un informe JSON
escrito con el formato de salida `json`. Sin la opción, la clave no está. Los
campos se describen en [Comprobaciones FinOps](../guides/finops-checks.md#the-finops_checks-result).

## Hoja FinOps costs y la clave `finops_costs` {#finops-costs-sheet-and-the-finops_costs-key}

Con `--finops-cost-allocation`, el libro predeterminado termina con una hoja
`FinOps costs` (después de la hoja `FinOps` cuando las dos opciones están
activas): una nota y después una fila por cuenta, agrupación y valor, con las
columnas `Account`, `Grouping`, `Value`, `Amount`, `Currency`, `Metric`,
`Period start`, `Period end` y `Status`. El resultado de
`CloudBOMGenerator.generate_multi_account_bom()` y el `metadata` de un informe
JSON tienen la clave `finops_costs`; la instantánea tiene
`metadata.tags.cost_allocation` (solo tablas, salvo con `--no-cost-in-snapshot`).
Consulta [Comprobaciones FinOps](../guides/finops-checks.md#cost-allocation-from-cost-explorer).
## Hoja Cost Analysis {#cost-analysis-sheet}

Con `--enable-cost-analysis`, el libro predeterminado tiene una hoja `Cost Analysis`. Su primera fila dice que las cifras son estimaciones de la API AWS Pricing y no tu factura. Las tablas siguen en este orden: `Summary`, el coste mensual estimado por servicio, los recursos más caros (los 50 primeros), la tendencia de costes, los recursos posiblemente olvidados y las recomendaciones. Toda tabla posterior a `Summary` se omite cuando no tiene filas.

La tabla de tendencia de costes se titula «Billed cost by account and service, last two full months (Cost Explorer; a service total, not a resource's cost)». Tiene una fila por cada cuenta y servicio, de la factura propia de Cost Explorer de esa cuenta, con las columnas:

| Columna | Contenido |
|---|---|
| `Account` | El ID de cuenta de los recursos |
| `Service` | El servicio tal como lo nombra el informe, por ejemplo `EC2` o `S3` |
| `Resources` | Cuántos recursos de ese servicio tiene la cuenta en el informe |
| `Earlier month` | El más antiguo de los dos meses completos anteriores a la ejecución, como `YYYY-MM` |
| `Billed (USD)` (primera) | Lo que Cost Explorer facturó por el servicio en ese mes |
| `Later month` | El mes más reciente, como `YYYY-MM` |
| `Billed (USD)` (segunda) | Lo que Cost Explorer facturó por el servicio en el mes más reciente |
| `Change %` | El cambio del mes anterior al más reciente, redondeado a un decimal. Desde una factura de cero es 100 si el mes más reciente se facturó, y 0 en caso contrario |
| `Direction` | `increasing` o `decreasing`, o `stable` cuando el cambio es inferior al 5 por ciento en cualquiera de los dos sentidos |
| `Billing names counted` | Los nombres de servicio de Cost Explorer que se sumaron en esa fila, separados por comas |

Las columnas de importes muestran la unidad que devolvió Cost Explorer: `Billed (USD)` cuando todas las filas tienen la misma unidad y, si no, `Billed (unit as returned)`, y cada celda termina entonces con su unidad. Una fila es un total del servicio en la cuenta, no el coste de un recurso, y no se reparte entre recursos. La cifra de un servicio es la suma de los nombres de facturación que muestra su fila. `EC2 - Other` (volúmenes, gateways NAT, transferencia de datos) es un nombre de facturación distinto y no está en la fila de EC2; `Amazon EC2 Container Registry (ECR)` tampoco. Una cuenta cuya solicitud de tendencia fue denegada o falló, o que no tiene sesión, no tiene filas, y la ejecución lo dice en una advertencia. Los meses son los dos meses completos anteriores a la ejecución.

En Python, las mismas filas son `cost_analysis["cost_trends"]` del resultado de `CloudBOMGenerator.generate_multi_account_bom()`. Cada entrada tiene `account_id`, `service`, `billing_names`, `resource_count`, `previous_month`, `current_month`, `previous_monthly_cost`, `current_monthly_cost`, `cost_change_percentage`, `trend_direction`, `alert_triggered` y `unit`. Antes de v1.5.0, ninguna hoja mostraba la tendencia; cada entrada de `cost_trends` nombraba un recurso (`resource_id`) y contenía el total del servicio dividido por el número de sus recursos. Esas entradas ya no existen: el código que lee `resource_id` de `cost_trends` debe leer una entrada por cada cuenta y servicio. Consulta [Comprobaciones FinOps](../guides/finops-checks.md#the-cost-trend-of---enable-cost-analysis).

No verificado contra AWS real: las facturas que devuelve una cuenta real, incluido lo que ven una cuenta de administración (pagadora) y una cuenta miembro.

## Hallazgos de las políticas {#policy-findings}

`inventag policy check`, `--policy` y `--finops-checks` con `--template` escriben el resultado de comprobar políticas sobre una instantánea de estado en archivos llamados `policy_findings_<timestamp>.<extension>` en el directorio de salida (la carpeta de `--output-directory` para `inventag policy check`):

| Extensión | Formato | Se escribe para |
|---|---|---|
| `.json` | El resultado completo | `json` |
| `.sarif` | SARIF 2.1.0, para herramientas de análisis de código | `sarif` |
| `.xml` | JUnit XML, un caso de prueba por cada política | `junit` |
| `.md` | Tablas Markdown, como máximo 50 filas por política | `markdown` |

Un escaneo escribe `.json` salvo que `--policy-format` diga otra cosa. `inventag policy check` imprime texto en pantalla y no escribe ningún archivo salvo que `--format` nombre uno; no escribe nada cuando termina con el código 1 o 2. En Linux y macOS solo su propietario puede leer y escribir los archivos (modo 0600), tanto de un escaneo como de `inventag policy check`; una carpeta que InvenTag crea para ellos tiene el modo 0700, y una carpeta existente conserva su modo.

El archivo JSON tiene estas claves de primer nivel: `schema_version`, `inventag_version`, `now`, `snapshot`, `baseline`, `policies`, `summary`, `findings`, `not_evaluated_units`, `not_evaluated_policies` y `unused_waivers`. Las claves van ordenadas y el archivo termina con un salto de línea. No contiene nombre de host, nombre de usuario, ruta absoluta ni hora del reloj, así que la misma instantánea y las mismas políticas dan los mismos bytes. Con InvenTag se empaqueta un JSON Schema para él (`inventag/policy/outputs/schemas/policy-findings-1.json`); su `$id` es el nombre `urn:inventag:schema:policy-findings:1`, no una dirección web.

- `findings` lista cada fila cuyo resultado es `fail`, `waived` o `not_evaluated`. Un `pass` y una fila que una política no selecciona (`out_of_scope`) se cuentan en `summary` y en el `counts` de cada política, pero no se listan.
- Un hallazgo `not_evaluated` tiene un `reason`: `identity_only`, `field_missing`, `tags_not_read`, `listing_not_read`, `not_comparable`, `not_convertible` o `value_too_long`. Un hueco en los datos nunca es un acierto.
- `not_evaluated_units` lista los listados del escaneo que no se leyeron y que una política habría necesitado. `unused_waivers` lista las exenciones que no coincidieron con nada, con `why`: `no match`, `expired`, `unknown policy` o `superseded`.
- `summary.exit_code` es 0, 7 u 8 con `inventag policy check`. En un escaneo es el código con el que termina el escaneo: 0, 3, 4, 5, 6 o 7 (5, 6, 3 y 4 van antes que 7), y la última línea del texto dice lo mismo.
- El valor de un campo de un recurso se muestra solo con `--show-values`, y un valor enmascarado sigue enmascarado. SARIF y JUnit nunca llevan un valor.

En las formas de texto y Markdown, la última línea dice qué significa el código de salida, por ejemplo `Exit code 7: at least one finding failed at severity high or higher.` Sin umbral dice `Exit code 0: findings are reported; no threshold was set.` Consulta [Códigos de salida](./cli.md#exit-codes).

En un escaneo con `--policy`, la última línea da el código con el que termina el escaneo: 7 cuando un hallazgo falló con la gravedad de `--policy-fail-on` o más alta (un escaneo nunca termina con 8; solo `inventag policy check` da 8). 3, 4, 5 y 6 conservan su significado y ganan cuando se aplican; la línea es entonces una de estas:

- `Exit code 3: the template's tag policy found violations (fail_on_tag_violations); this code comes before the policy check's code.`
- `Exit code 4: a security group rule is at or above --risk-threshold; this code comes before the policy check's code.`
- `Exit code 5: an account could not be scanned (--fail-on-account-error); this code comes before the policy check's code.`
- `Exit code 6: no resources were found (--fail-if-empty); this code comes before the policy check's code.`

No verificado: cómo muestra GitHub code scanning el archivo SARIF, o cómo muestra GitLab el archivo JUnit. Las pruebas comparan los archivos con archivos de referencia (golden), y el archivo SARIF con un esquema corto que se empaqueta con InvenTag, no con el esquema SARIF completo.

## Informe de Word {#word-report}

**Sin plantilla:** un título, un resumen ejecutivo, una tabla de servicios y
hasta 50 recursos por servicio en seis columnas: Name, Id, Type, Region, Tags y Service. Si ningún recurso del servicio tiene nombre, las columnas son Id, Type, Region, Tags, Service y Source Account Name.

**Con una plantilla de informe:** las secciones listadas en `word.sections`. Las tablas
tienen una fila de encabezado que se repite en cada página y está marcada como encabezado para
los lectores de pantalla. El logotipo, si lo hay, lleva texto alternativo.

## Informe HTML {#html-report}

`--create-html` escribe el informe como un único archivo HTML estático,
`multi_account_bom_<timestamp>.html`, en la carpeta de salida, con la misma
raíz de nombre que los archivos de Excel y Word de la ejecución. Con
`--per-account-reports`, cada cuenta tiene su propio
`<account-id>_bom_<timestamp>.html`. Abre el archivo en un navegador web.

```bash
inventag --create-excel --create-html
```

- `--create-html` sola escribe solo el archivo HTML. Con `--create-excel` o
  `--create-word`, el archivo HTML se escribe además de esos informes.
- Una ejecución sin `--create-html` no escribe ningún archivo HTML y no cambia.
- Cuando la ejecución no encuentra recursos, no se escribe ningún archivo
  HTML, igual que con los informes de Excel y Word.
- Con `--s3-bucket`, el archivo HTML se sube con los demás informes. InvenTag
  no fija ningún tipo de contenido en la subida. No verificado contra AWS
  real: que un navegador descargue el objeto de S3 en lugar de mostrarlo.

**Qué contiene el archivo**, en este orden:

- **Resumen:** recursos por servicio (con un total), recursos por región y
  las notas de la ejecución.
- **Recursos por servicio:** una sección cerrada por cada servicio. Abre una
  sección para ver su tabla. Cada tabla tiene las mismas columnas y filas que
  la hoja del servicio en el informe de Excel predeterminado, con los valores
  secretos enmascarados como `***REDACTED***` de la misma forma.
- **Cumplimiento de etiquetas:** el resumen de una política de etiquetas, solo
  cuando la ejecución comprobó una (por ejemplo, con una plantilla de política
  de etiquetas).
- **Análisis de red** y **análisis de seguridad:** la tabla de VPC y la tabla
  de grupos de seguridad, solo con `--enable-network-analysis` o
  `--enable-security-analysis`.
- **FinOps** y **FinOps costs:** las mismas tablas que las hojas de Excel,
  solo con `--finops-checks` o `--finops-cost-allocation`.
- **Cobertura y errores:** las cuentas, cómo terminaron las llamadas de
  listado en cada cuenta (`ok`, `empty`, `denied` y los demás resultados) y
  los permisos denegados. La columna `Read in part` de la tabla de cuentas
  es `Yes` cuando la cuenta se detuvo antes del final de su análisis o no se
  leyó uno de sus listados: las mismas cuentas que nombra una nota de la
  ejecución "Not read in account".

El archivo no contiene las tablas de Cost Analysis de `--enable-cost-analysis`
ni los hallazgos de `--policy` (están en `policy_findings_<timestamp>.json`).
No tiene ordenación, filtros ni gráficos.

**Con una plantilla de informe:** con `--template`, el archivo HTML tiene el
diseño descrito arriba; las secciones de la plantilla se aplican solo a los
informes de Excel y Word, y la ejecución muestra un aviso que lo indica. Con
`--word-template` o `--excel-template`, el archivo HTML usa el título del
documento, el nombre de la empresa y el logotipo de esa plantilla (primero la
de Word). El logotipo debe ser un archivo PNG o JPEG; se incrusta en el
archivo. `--excel-template` con `--create-html` sola se detiene con el código
de salida 2, porque no se escribe ningún informe de Excel.

**Seguridad del archivo:**

- Cada valor de tus cuentas (nombres, etiquetas, configuración) se escapa, de
  modo que el marcado en un valor de etiqueta se muestra como texto y nunca se
  ejecuta. Los caracteres de dirección del texto y de control se eliminan,
  de modo que un valor no puede mostrarse invertido ni reordenado.
- El archivo no tiene JavaScript y no carga nada de fuera del archivo: ningún
  script, hoja de estilo, fuente ni imagen de otro sitio. Sus únicos enlaces
  van a secciones del mismo archivo. Su única imagen es el logotipo de la
  plantilla, incrustado como URI `data:`.
- El archivo lleva esta Content-Security-Policy, que indica al navegador que
  no cargue nada más:
  `default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'`.
- El archivo se escribe completo o no se escribe, y solo tu usuario puede
  leerlo y escribirlo, como los demás informes.
- Por esta opción, la ejecución no escribe en el registro ningún valor de tus
  recursos.

:::warning Mantén privado el archivo HTML

El archivo HTML contiene datos de tus cuentas de AWS: nombres de recursos,
ID, etiquetas y configuración. Trátalo como el informe de Excel. No lo
publiques en un sitio web ni lo compartas más que el archivo de Excel.

:::

El archivo tiene estilos de impresión: ocultan la lista de contenidos y piden
al navegador que no divida una fila de tabla entre páginas. No verificado
contra un navegador: cómo se ve y se imprime el archivo, y si una sección
cerrada se imprime abierta.

Los ejemplos siguientes vienen de una ejecución sin conexión contra AWS
simulado (datos de ejemplo).

```html title="multi_account_bom_20261112_090000.html (first lines)"
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; style-src &#x27;unsafe-inline&#x27;; img-src data:; base-uri &#x27;none&#x27;; form-action &#x27;none&#x27;">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AWS Resource Inventory - BOM Report</title>
```

```text title="multi_account_bom_20261112_090000.html (outline)"
AWS Resource Inventory - BOM Report
  Contents
  Summary
      table: Resources by service
      table: Resources by region
  Resources by service
    ATHENA (1) (closed section)
      table: ATHENA resources
    DYNAMODB (1) (closed section)
      table: DYNAMODB resources
    EC2 (4) (closed section)
      table: EC2 resources
    EVENTS (1) (closed section)
      table: EVENTS resources
    IAM (1) (closed section)
      table: IAM resources
    KMS (14) (closed section)
      table: KMS resources
    LAMBDA (1) (closed section)
      table: LAMBDA resources
    S3 (6) (closed section)
      table: S3 resources
    VPC (10) (closed section)
      table: VPC resources
  Coverage and errors
      table: Accounts
      table: Listings by outcome
```

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
  "total_calls": 93,
  "allowed_calls": 93,
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
bom-reports/20261112_090000/multi_account_bom_20261112_090000.xlsx
```

## Salida del terminal {#terminal-output}

Sin `--verbose`, una ejecución imprime advertencias, errores y los archivos escritos. Con
una plantilla, cada archivo se imprime como `Wrote <path>`, seguido de un resumen de una línea de la
política de etiquetas cuando hay una activa. Sin plantilla, el informe predeterminado se imprime como `Data exported to <path>`, y con `--create-html` el archivo HTML tiene su propia línea `Data exported to <path>`. Con `--policy`, el resumen de las políticas se imprime siempre; la línea `Policy findings: <path>` se registra con nivel INFO y solo se muestra con `--verbose`. Sin ninguna opción, `inventag` imprime la página de ayuda y termina con el código 2.

## Códigos de salida {#exit-codes}

Consulta la [Referencia de la línea de comandos](./cli.md#exit-codes).
