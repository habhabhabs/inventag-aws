---
title: Elegir qué analizar y qué generar
description: Elige las cuentas, regiones y archivos de salida de una ejecución de InvenTag, conserva los registros y decide dónde se escriben los informes.
sidebar_position: 1
slug: /user-guides/cli-user-guide
---

# Elegir qué analizar y qué generar

**Para quién es:** has ejecutado InvenTag una vez y quieres controlar qué
analiza y qué escribe.

**Qué podrás hacer después de leerlo:** elegir cuentas, regiones, archivos de
salida y registro de una ejecución. Para ver todas las opciones, consulta la
[referencia de la CLI](../reference/cli.md).

El comando `inventag` funciona igual en Linux, macOS y Windows.

## Elige las cuentas {#choose-the-accounts}

| Quieres analizar... | Usa |
|---|---|
| La cuenta de tus credenciales actuales | Nada adicional |
| Otra cuenta, mediante un rol | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly` (un ARN de rol completo) |
| Varias cuentas | `--accounts-file accounts.yaml` o una plantilla de configuración: [Analizar varias cuentas](./scan-multiple-accounts.md) |
| Varias cuentas, con el mismo nombre de rol en cada una | `--accounts-file accounts.yaml --cross-account-role InvenTagReadOnly` |
| Cuentas que escribes cuando se te pide | `--accounts-prompt` |

Da `--accounts-file` o `--accounts-prompt`, no ambos. Un ARN de rol completo en `--cross-account-role` nombra una sola cuenta, así que no puede ir con ninguno de los dos. Ambos errores detienen la ejecución con código de salida 2.

## Elige las regiones {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

Sin `--account-regions`, InvenTag pregunta a EC2 qué regiones están habilitadas
en la cuenta y las analiza todas. Es exhaustivo pero lento. Si
`ec2:DescribeRegions` falla, InvenTag consulta `account:ListRegions`. Si eso
también falla, registra una advertencia y prueba todas las regiones de la
partición que conoce tu AWS SDK. Las regiones que la cuenta no ha habilitado no
superan la comprobación de acceso y se omiten. Usa `--account-regions` para
elegir tú las regiones.

Una región que no supera su comprobación de acceso se omite con una
advertencia. Si la comprobación falla en todas las regiones, porque la identidad
no tiene `ec2:DescribeRegions`, InvenTag no puede saber cuáles funcionan y las
analiza todas.

### Servicios globales {#global-services}

No necesitas añadir la región principal a la lista. Elijas las regiones que elijas,
InvenTag lee los servicios globales una vez por cuenta, desde la región principal
de la partición: `us-east-1` en la partición estándar, `cn-north-1` en China y
`us-gov-west-1` en GovCloud. Son IAM, la lista de buckets de S3, CloudFront,
Route 53 y los certificados de ACM que usa CloudFront. Si la región principal
está en tu lista, no se leen dos veces.

- `--account-services` y `--account-tags` se aplican a ellos como a cualquier
  otro recurso. Con `--account-services ec2`, no se lee ningún recurso de IAM.
- Los recursos de IAM, CloudFront y Route 53 muestran `global` en la columna de
  región. Un bucket de S3 muestra su propia región, por ejemplo `eu-west-1`.
- Sus etiquetas proceden de la API Resource Groups Tagging en la región
  principal, donde AWS guarda las etiquetas de los recursos globales.
- Las pruebas sin conexión cubren `eu-west-1` solo, todas las regiones y una
  lista que incluye `us-east-1`. No se ha probado cómo responde AWS real.

### Servicios {#services}

InvenTag tiene sus propias llamadas de listado de solo lectura para 46 servicios de AWS. Los recursos de otros servicios solo aparecen cuando la API Resource Groups Tagging los devuelve.
Consulta [Estado de las funciones y limitaciones conocidas](../getting-started/status.md).

### Limitación y llamadas fallidas {#throttling-and-failed-calls}

InvenTag reintenta una llamada limitada hasta 10 veces en total (el modo de reintentos
«standard» del AWS SDK). Si defines `AWS_RETRY_MODE` o `AWS_MAX_ATTEMPTS`, se usan tus valores.
Un listado que sigue fallando se registra como advertencia para ese servicio y región:
`<service> <operation> in <region> failed (<error>); its resources there may be incomplete.`
La salida JSON registra cómo terminó cada listado. Un permiso denegado se registra una sola vez por servicio.

## Límite de tiempo y cuentas en paralelo {#time-limit-and-parallel-accounts}

InvenTag analiza hasta cuatro cuentas a la vez. Cámbialo con `--max-concurrent-accounts`
(al menos 1), o usa `--disable-parallel-processing` para analizar una cuenta cada vez.

Cada cuenta tiene `--account-processing-timeout` segundos (por defecto 1800, al menos 60),
contados desde que empieza el análisis de esa cuenta. El descubrimiento se detiene un poco antes,
300 segundos o el 20 % del límite, lo que sea menor, para que aún se puedan leer etiquetas, detalles y facturación.

Una cuenta que se queda sin tiempo se informa como fallida y las demás cuentas se conservan.
Los recursos que encontró antes del límite siguen en el informe, y las notas del informe indican que la cuenta está incompleta.
Una línea de registro de una ejecución sin conexión con `--account-processing-timeout 60` (datos de ejemplo):

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

Si ninguna cuenta termina, InvenTag escribe igualmente el informe con lo que encontró, registra `No account finished within its time limit` y sale con código 1.

## Continúa tras una ejecución fallida {#continue-after-a-failed-run}

Cuando algunas cuentas fallan, InvenTag guarda las que terminaron en `bom_output/state/partial/`.
Corrige la causa y ejecuta el mismo comando con `--resume`. InvenTag analiza solo las cuentas que faltan:

```bash
inventag --accounts-file accounts.yaml --create-excel --resume
```

InvenTag reutiliza un resultado guardado solo si el comando usó las mismas cuentas, regiones, servicios y filtros,
y el resultado no es más antiguo que `--resume-max-age-hours` (por defecto 24, como máximo 168).
Necesita la gestión de estado, así que `--resume` con `--disable-state-management` se detiene con código de salida 2.
El registro dice `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)`, y las notas del informe
listan cada cuenta reutilizada con su hora de análisis. Sin `--resume`, una advertencia indica que existen resultados guardados
y que se analizan de nuevo. InvenTag borra los resultados guardados tras una ejecución en la que todas las cuentas terminan.

## Elige los archivos de salida {#choose-the-output-files}

| Opción | Escribe |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | Los mismos archivos, con el diseño de una [plantilla de informe](../templates/index.md) |
| `--output-directory reports` | Escribe todo en `reports/` en lugar de `bom_output/` |

Si no indicas ninguna opción de salida, InvenTag escribe solo Excel. Si el
análisis no encuentra recursos, o tus filtros los eliminan todos, InvenTag no
escribe ningún archivo, registra `No resources to report (none found, or the filters removed all of them).` y aun así termina con el código 0. Con `--template`, escribe un informe que no lista ningún recurso. Añade `--s3-bucket`
para subir también los archivos: consulta
[Subir informes a S3 de forma programada](../examples/scheduled-s3-upload.md).

Ejemplo de salida de una ejecución con `--template standard-bom --create-excel
--create-word --account-regions us-east-1` (sin conexión, datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

## Combina varios ajustes en un archivo {#combine-several-settings-in-one-file}

Si siempre ejecutas con los mismos ajustes, ponlos en una
[plantilla de configuración](../templates/catalogue.md#config-templates) en
lugar de escribirlos cada vez:

```bash
inventag templates init single-account --output .inventag/templates/my-scan.yaml
# edit regions and outputs, then:
inventag --template my-scan
```

Las opciones que escribes siguen teniendo prioridad sobre la plantilla.

## Mira qué está pasando {#see-what-is-happening}

| Opción | Muestra |
|---|---|
| (ninguna) | Advertencias, errores y dónde se escribieron los archivos. No se muestran los errores de permisos de AWS en llamadas individuales. |
| `--verbose` o `-v` | Cada paso de la ejecución |
| `--log-file run.log` | Escribe además un registro detallado en un archivo |
| `--debug` o `-d` | Cada solicitud a AWS. Los secretos se enmascaran, pero trata el registro como sensible. |
| `--audit-output audit.json` | Una lista JSON de cada operación de AWS que llamó la ejecución |

## Valida los archivos de configuración sin analizar {#validate-configuration-files-without-scanning}

```bash title="Terminal"
inventag --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
inventag templates validate my-scan
```

El código de salida 0 significa que los archivos son válidos. Con `--skip-credential-validation`,
el primer comando no hace ninguna llamada a AWS. Un archivo de cuentas erróneo se ve
así (datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

## Códigos de salida {#exit-codes}

InvenTag sale con código 0 aunque una cuenta haya fallado o no se haya encontrado nada. Dos opciones lo cambian. Con el código 5 los informes se escriben igualmente.

| Opción | Código de salida | Cuándo |
|---|---|---|
| `--fail-on-account-error` | 5 | Una cuenta no se pudo analizar, o solo en parte |
| `--fail-if-empty` | 6 | No hay recursos que informar |

La lista completa está en [Ejecutar InvenTag en CI/CD](./run-in-ci.md#exit-codes).

## Siguientes pasos {#next-steps}

- [Analizar varias cuentas](./scan-multiple-accounts.md)
- [Comprobar etiquetas con una política](./check-tag-compliance.md)
- [Referencia de la CLI](../reference/cli.md)
