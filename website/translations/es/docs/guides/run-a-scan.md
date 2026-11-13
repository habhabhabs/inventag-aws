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

## Elige las regiones {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

Sin `--account-regions`, InvenTag pregunta a EC2 qué regiones están habilitadas
en la cuenta y las analiza todas. Es exhaustivo pero lento. Si esa consulta
falla, InvenTag registra una advertencia y analiza solo `us-east-1`,
`us-west-2`, `eu-west-1` y `ap-southeast-1`.

Una región que no supera su comprobación de acceso se omite con una
advertencia.

### Servicios globales {#global-services}

No necesitas añadir `us-east-1` a la lista. Elijas las regiones que elijas,
InvenTag lee los servicios globales una vez por cuenta, desde `us-east-1`: IAM,
la lista de buckets de S3, CloudFront, Route 53 y los certificados de ACM que
usa CloudFront. Si `us-east-1` está en tu lista, no se leen dos veces.

- `--account-services` y `--account-tags` se aplican a ellos como a cualquier
  otro recurso. Con `--account-services ec2`, no se lee ningún recurso de IAM.
- Los recursos de IAM, CloudFront y Route 53 muestran `global` en la columna de
  región. Un bucket de S3 muestra su propia región, por ejemplo `eu-west-1`.
- Sus etiquetas proceden de la API Resource Groups Tagging en `us-east-1`,
  donde AWS guarda las etiquetas de los recursos globales.
- Las pruebas sin conexión cubren `eu-west-1` solo, todas las regiones y una
  lista que incluye `us-east-1`. No se ha probado cómo responde AWS real.

## Elige los archivos de salida {#choose-the-output-files}

| Opción | Escribe |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | Los mismos archivos, con el diseño de una [plantilla de informe](../templates/index.md) |
| `--output-directory reports` | Escribe todo en `reports/` en lugar de `bom_output/` |

Si no indicas ninguna opción de salida, InvenTag escribe solo Excel. Si el
análisis no encuentra recursos, o tus filtros los eliminan todos, InvenTag no
escribe ningún archivo y aun así termina con el código 0. Añade `--s3-bucket`
para subir también los archivos: consulta
[Subir informes a S3 de forma programada](../examples/scheduled-s3-upload.md).

Ejemplo de salida de una ejecución con `--template standard-bom --create-excel
--create-word --account-regions us-east-1` (sin conexión, datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
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

El código de salida 0 significa que los archivos son válidos. El primer comando
sigue haciendo una llamada a `ec2:DescribeRegions` para listar las regiones; si
falla, registra una advertencia y continúa. Un archivo de cuentas erróneo se ve
así (datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

## Siguientes pasos {#next-steps}

- [Analizar varias cuentas](./scan-multiple-accounts.md)
- [Comprobar etiquetas con una política](./check-tag-compliance.md)
- [Referencia de la CLI](../reference/cli.md)
