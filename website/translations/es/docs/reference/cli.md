---
title: Referencia de la línea de comandos
description: Todos los comandos y opciones de InvenTag, qué hace cada uno en la versión actual y su valor predeterminado, comprobados con inventag --help.
sidebar_position: 1
---

# Referencia de la línea de comandos

**Para quién es:** necesitas el nombre exacto o el comportamiento de una opción.

**Qué podrás hacer después de leerlo:** construir cualquier línea de comandos de
InvenTag y saber qué opciones funcionan hoy.

Esta página coincide con `inventag --help` de la versión que describe esta versión
de la documentación. Ejecuta `inventag --help` para ver las opciones de la versión
que tienes instalada. La columna **Estado**
indica lo que vimos al ejecutar la opción sin conexión contra AWS simulado. «No se
volvió a probar» significa que no la ejecutamos para esta página. Hay más detalles en
[Estado de las funciones](../getting-started/status.md).

## Comandos {#commands}

```text
inventag [flags]                       run a scan and write reports
inventag --version                     print the version and exit
inventag templates list [--kind K] [--all]
inventag templates show NAME|PATH [--resolved]
inventag templates init NAME|PATH --output FILE|FOLDER [--name NAME] [--extend] [--force]
inventag templates validate NAME|PATH [NAME|PATH ...]
```

El comando `inventag` funciona igual en Linux, macOS y Windows.
`templates` debe ser la primera palabra después del nombre del programa.

## Plantillas {#templates}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--template NAME\|PATH` | ninguno | Funciona | Usa una plantilla. Repítela para indicar una plantilla de informe, una de política de etiquetas y una de configuración. Consulta [Plantillas](../templates/index.md). |

### Subcomandos de `templates` {#templates-subcommands}

| Comando | Qué hace |
|---|---|
| `templates list` | Lista las plantillas con su tipo, origen y descripción, y las carpetas donde se busca. `--kind report\|tag-policy\|config` filtra; `--all` muestra también las plantillas ocultas por otra con el mismo nombre. |
| `templates show NAME` | Imprime el archivo. `--resolved` imprime el resultado después de aplicar `extends` y los valores predeterminados. |
| `templates init NAME --output PATH` | Copia una plantilla a tu proyecto. `--extend` escribe un archivo corto que hereda; `--name` define el nombre; `--force` sobrescribe. |
| `templates validate NAME\|PATH ...` | Comprueba los archivos y las plantillas a las que hacen referencia. Código de salida 0 si todo es válido, 1 en caso contrario. |

## Cuentas {#accounts}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--accounts-file FILE` | ninguno | Funciona | Lee las cuentas de un archivo JSON o YAML. Consulta [Archivos de configuración](./configuration-files.md#accounts-file). Indica `--accounts-file` o `--accounts-prompt`, no ambos (código de salida 2). |
| `--accounts-prompt` | desactivado | Funciona | Pide las cuentas y las credenciales de forma interactiva. |
| `--cross-account-role ARN\|NAME` | ninguno | Funciona | Un ARN de rol completo se asume directamente; con `--accounts-file` o `--accounts-prompt` se detiene con el código de salida 2. Un nombre de rol se combina con cada ID de cuenta de `--accounts-file`. Un nombre sin `--accounts-file` se detiene con el código de salida 2. |

## Salida {#output}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--create-excel` | activado si no hay otra opción de salida | Funciona | Escribe `multi_account_bom_<timestamp>.xlsx`. |
| `--create-word` | desactivado | Funciona | Escribe `multi_account_bom_<timestamp>.docx`. |
| `--create-google-docs` | desactivado | Funciona (solo con clientes simulados) | Crea el informe de Word como un documento de Google Docs. Necesita el complemento de Google (`pip install "inventag-aws[google]"`). Consulta [Google Sheets y Docs](../guides/google-sheets-and-docs.md). |
| `--create-google-sheets` | desactivado | Funciona (solo con clientes simulados) | Crea el informe de Excel como una hoja de cálculo de Google Sheets. |
| `--google-credentials FILE` | ninguno | Funciona (solo con clientes simulados) | Archivo de clave de la cuenta de servicio. Sin él, se usan las credenciales predeterminadas de la aplicación (Application Default Credentials). |
| `--google-oauth-client FILE` | ninguno | Funciona (solo con clientes simulados) | Archivo de cliente OAuth; inicias sesión en el navegador. |
| `--google-folder-id ID` | ninguno | Funciona (solo con clientes simulados) | Carpeta de Drive para los archivos. |
| `--google-share-with EMAIL` | ninguno | Funciona (solo con clientes simulados) | Comparte con esta dirección. Repítela para añadir más. |
| `--google-share-role ROLE` | `reader` | Funciona (solo con clientes simulados) | `reader`, `commenter` o `writer`. |
| `--google-share-anyone` | desactivado | Funciona (solo con clientes simulados) | Cualquiera con el enlace puede leer. Sin esta opción, los archivos son privados. |
| `--google-title TITLE` | nombre con fecha | Funciona (solo con clientes simulados) | Título de los archivos de Google. |
| `--output-directory DIR` | `bom_output` | Funciona | Carpeta para todos los archivos de salida. |
| `--per-account-reports` | desactivado | Funciona | Un archivo `<account-id>_bom_<timestamp>` por cuenta en lugar de un único informe consolidado. |

## Qué analizar {#what-to-scan}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--account-regions LIST` | todas las regiones habilitadas | Funciona | Códigos de región separados por comas, por ejemplo `us-east-1,eu-west-1`. IAM, la lista de buckets de S3, CloudFront y Route 53 se leen siempre una vez desde `us-east-1`, así que no hace falta que la indiques. |
| `--account-services LIST` | todos | Funciona | Nombres de servicio separados por comas que se conservan en el informe, comparados con la columna Service, por ejemplo `EC2,S3`. |
| `--account-tags JSON` | ninguno | Funciona | Filtro de etiquetas, por ejemplo `'{"Environment":"prod"}'`. Solo se conservan los recursos con esas etiquetas. |
| `--fallback-display auto\|always\|never` | `auto` | Funciona | Si se muestran los recursos encontrados solo a través de la API Resource Groups Tagging. `auto` los muestra solo para los servicios sin resultados de su propio código de descubrimiento. |
| `--hide-fallback-resources` | desactivado | No se volvió a probar | Igual que `--fallback-display never`. Obsoleta. |

## Análisis {#analysis}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--enable-network-analysis` | desactivado | Funciona | Añade una hoja `Network Analysis` al informe de Excel cuando se encuentran VPC. No añade nada con `--template`. Consulta [Análisis de red y seguridad](../guides/network-and-security-analysis.md). |
| `--enable-security-analysis` | desactivado | Funciona | Añade una hoja `Security Analysis` al informe de Excel cuando se encuentran grupos de seguridad. No añade nada con `--template`. |
| `--enable-cost-analysis` | desactivado | Funciona | Añade una hoja Cost Analysis (y las cuatro columnas `forgotten_analysis.*`) al libro predeterminado. Hace llamadas adicionales a Cost Explorer, Pricing y CloudWatch, también con `--no-billing-validation`. Necesita `pricing:GetProducts` y `cloudwatch:GetMetricStatistics`. Los costes son estimaciones de la API AWS Pricing, no tu factura. |
| `--billing-validation`, `--no-billing-validation` | activado | Funciona | Usa Cost Explorer durante el descubrimiento para encontrar servicios con gasto. AWS cobra cada solicitud a Cost Explorer. `--no-billing-validation` detiene esas llamadas. |

## Archivos de configuración {#configuration-files}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--tag-mappings FILE` | ninguno | Funciona | Añade una columna con nombre por cada asignación. Consulta [Archivos de configuración](./configuration-files.md#tag-mappings). |
| `--service-descriptions FILE` | ninguno | Funciona | Añade una columna `service_description`. Tu entrada sustituye a la descripción integrada. Consulta [Archivos de configuración](./configuration-files.md#service-descriptions). |
| `--bom-config FILE` | ninguno | Funciona | Define campos de la configuración de procesamiento de la BOM desde un archivo YAML o JSON. Las demás claves se ignoran con una advertencia que las nombra. Un valor de tipo incorrecto se detiene con el código de salida 1 y nombra la clave. |
| `--validate-config` | desactivado | Funciona | Carga y comprueba la configuración y después termina. |
| `--validate-config-only` | desactivado | Funciona | Comprueba solo los archivos que indiques y después termina. No hace ninguna llamada a AWS. |

## Archivos de diseño de informes {#report-layout-files}

Estas opciones cambian el diseño de los informes predeterminados de Excel y Word
con un archivo YAML o JSON. Consulta [Archivos de diseño para un informe](../templates/layout-flags.md).

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--word-template PATH` | ninguno | Funciona | Archivo de diseño del informe de Word. Necesita `--create-word`; sin ella, la ejecución se detiene con el código de salida 2. |
| `--excel-template PATH` | ninguno | Funciona | Archivo de diseño del informe de Excel. Con solo `--create-word`, la ejecución se detiene con el código de salida 2. |
| `--print-default-template word\|excel` | ninguno | Funciona | Imprime el archivo de diseño predeterminado de ese formato y sale con el código 0. |
| `--validate-templates` | desactivado | Funciona | Comprueba los archivos indicados con `--word-template` y `--excel-template` y sale. No hace ninguna llamada a AWS. Sin una de esas opciones: código de salida 2. |

## Procesamiento en paralelo {#parallel-processing}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--max-concurrent-accounts N` | `4` | Funciona | Cuentas que se analizan al mismo tiempo (mínimo 1). |
| `--account-processing-timeout SECONDS` | `1800` | Funciona | Tiempo permitido por cuenta, contado desde que empieza su análisis (mínimo 60). Una cuenta que se queda sin tiempo cuenta como fallida; los recursos que encontró se quedan en el informe. |
| `--disable-parallel-processing` | desactivado | Funciona | Analiza una cuenta cada vez. |
| `--resume` | desactivado | Funciona | Reutiliza los resultados guardados de las cuentas que terminaron en una ejecución anterior del mismo comando que no se completó (mismas cuentas, regiones, servicios y filtros) y analiza solo las demás. Con `--disable-state-management`: código de salida 2. |
| `--resume-max-age-hours HOURS` | `24` | Funciona | Con `--resume`, reutiliza los resultados guardados solo hasta esta antigüedad (como máximo 168). |

## Estado y seguimiento de cambios {#state-and-change-tracking}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--enable-state-management` | activado | Funciona | Guarda una instantánea en `<output>/state/`. |
| `--disable-state-management` | desactivado | Funciona | No guarda instantáneas ni registros de cambios. |
| `--enable-delta-detection` / `--disable-delta-detection` | activado | Funciona | Compara la instantánea nueva con la anterior. `--disable-delta-detection` no escribe informe de cambios. |
| `--generate-changelog`, `--no-generate-changelog` | activado | Funciona | Escribe `changelog_<timestamp>.md` a partir de la segunda ejecución. `--no-generate-changelog` lo evita. |
| `--state-retention-days N` | `30` | Funciona | Borra las instantáneas de estado con más de N días cuando una ejecución guarda una nueva. `0` o `none` conserva instantáneas de cualquier antigüedad. |
| `--state-max-snapshots N` | `100` | Funciona | Conserva solo las N instantáneas de estado más recientes. `0` o `none` conserva todas. |

## Códigos de salida opcionales {#opt-in-exit-codes}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--fail-on-account-error` | desactivado | Funciona | Termina con el código 5 cuando una cuenta no se pudo analizar por completo. Los informes se escriben igualmente. |
| `--fail-if-empty` | desactivado | Funciona | Termina con el código 6 cuando no se encontraron recursos o los filtros los quitaron todos. |

Los códigos 5 y 6 tienen prioridad sobre 3 y 4.

## Registro {#logging}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--verbose`, `-v` | desactivado | Funciona | Muestra cada paso. |
| `--debug`, `-d` | desactivado | Funciona | Muestra cada solicitud a AWS. Los secretos se enmascaran. |
| `--log-file FILE` | ninguno | Funciona | Escribe además un registro detallado en este archivo. |
| `--disable-account-logging` | desactivado | Funciona | No antepone la cuenta a las líneas del registro. |

## Credenciales {#credentials}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--validate-credentials` | desactivado | Funciona | Comprueba las credenciales de cada cuenta y después termina (0 si todas funcionan, 1 si no). |
| `--credential-timeout SECONDS` | `30` | Funciona | Tiempo de espera del inicio de sesión y de las comprobaciones de credenciales, incluido AssumeRole. |
| `--skip-credential-validation` | desactivado | Funciona | Omite la comprobación de credenciales al inicio de una ejecución. |

## Protección de solo lectura y auditoría {#read-only-guard-and-audit}

La protección de solo lectura está siempre activa. Bloquea toda llamada a AWS que no
sea de lectura, y las lecturas que devuelven secretos o datos.

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--audit-output FILE` | ninguno | Funciona | Escribe una lista JSON de cada operación de AWS que llamó la ejecución, permitida y bloqueada. |
| `--validate-operations SERVICE:OPERATION ...` | ninguno | Funciona | Comprueba operaciones contra la protección y después termina (0 si todas están permitidas, 1 si no). |
| `--enforce-read-only`, `--security-validation`, `--enable-production-safety` | activado | Sin efecto | Se mantienen para que los comandos antiguos sigan funcionando. La protección está siempre activa. |
| `--disable-production-safety` | desactivado | Se detiene con el código de salida 2 | La protección no se puede desactivar. |
| `--compliance-standard ...` | ninguno | Se detiene con el código de salida 2 | No implementada: un estándar no se puede comprobar a partir de un inventario. Usa una plantilla de política de etiquetas. |
| `--risk-threshold LEVEL` | ninguno | Funciona | Con `--enable-security-analysis`: código de salida 4 si una regla de un grupo de seguridad está en `LOW`, `MEDIUM`, `HIGH` o `CRITICAL`, o por encima. Sin `--enable-security-analysis`: código de salida 2. |

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

Lo que imprimen las opciones que se detienen con el código de salida 2:

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)

$ inventag --risk-threshold HIGH
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## Carga a S3 {#s3-upload}

| Opción | Predeterminado | Estado | Qué hace |
|---|---|---|---|
| `--s3-bucket BUCKET` | ninguno | Funciona | Sube a este bucket todos los archivos que escribió la ejecución (Excel, Word y JSON de cumplimiento de etiquetas). La ejecución termina con el código 1 si falla una carga. Necesita `s3:PutObject`. |
| `--s3-key-prefix PREFIX` | `bom-reports/` | Funciona | Carpeta (prefijo de clave) en el bucket. Los archivos van bajo `<prefix><UTC timestamp>/`. |
| `--s3-encryption AES256\|aws:kms` | `AES256` | Funciona | Cifrado del lado del servidor para las cargas. |
| `--s3-kms-key-id KEY` | ninguno | Funciona | Clave de KMS para `aws:kms`. Sin ella, S3 usa la clave administrada por AWS `aws/s3`. Necesita `--s3-encryption aws:kms`; si no, código de salida 2. |

Consulta [Subir informes a S3 de forma programada](../examples/scheduled-s3-upload.md).

## Códigos de salida {#exit-codes}

| Código | Significado |
|---|---|
| 0 | Correcto. También es 0 cuando algunas cuentas fallaron pero otras funcionaron, y cuando no se encontraron recursos, salvo que pases `--fail-on-account-error` o `--fail-if-empty`. Consulta [Estado de las funciones](../getting-started/status.md#when-a-run-goes-wrong). |
| 1 | Un error: argumentos, configuración o plantilla no válidos, credenciales fallidas, todas las cuentas fallaron (también cuando algunas solo se analizaron en parte), una carga a S3 fallida o un formato de informe que no se pudo escribir |
| 2 | Línea de comandos no válida: opciones desconocidas, mal formadas o incompatibles entre sí, opciones no implementadas, opciones de Google incorrectas, una opción de archivo de diseño sin el informe que necesita o un nombre de rol sin `--accounts-file` |
| 3 | Informes escritos, pero una plantilla de configuración con `fail_on_tag_violations: true` encontró infracciones de la política de etiquetas |
| 4 | Informes escritos, pero `--risk-threshold` encontró una regla de un grupo de seguridad en ese nivel o por encima |
| 5 | Informes escritos, pero una cuenta no se pudo analizar por completo, y pasaste `--fail-on-account-error` |
| 6 | No hay recursos que informar, y pasaste `--fail-if-empty` |
