---
title: Archivos de configuración
description: Los formatos de archivo que lee InvenTag (cuentas, asignaciones de etiquetas y descripciones de servicios) y los campos que los cargadores aceptan de verdad.
sidebar_position: 2
slug: /user-guides/configuration-examples
---

# Archivos de configuración

**Para quién es:** escribes o revisas a mano los archivos de configuración de InvenTag.

**Qué podrás hacer después de leerlo:** escribir un archivo de cuentas, un archivo de
asignaciones de etiquetas y un archivo de descripciones de servicios que los cargadores acepten.

Para las plantillas (diseños de informe, políticas de etiquetas, ajustes de ejecución), consulta la
[Referencia de plantillas](../templates/reference.md). Una plantilla de configuración puede hacer
todo lo que hace un archivo de cuentas salvo contener claves de acceso, y se
valida con más rigor, así que prefiérela para las configuraciones nuevas.

Todos los archivos pueden ser YAML (`.yaml`, `.yml`) o JSON (`.json`). Compruébalos sin
analizar nada:

```bash
inventag --accounts-file accounts.yaml --tag-mappings tags.yaml \
  --validate-config-only --skip-credential-validation
```

Esto lee los archivos y no hace ninguna llamada a AWS.

InvenTag lee estos archivos como UTF-8, con o sin marca de orden de bytes. Un
archivo vacío, una clave escrita dos veces o un nivel superior que no es un
mapeo detienen la ejecución con el código de salida 1 y un mensaje que nombra el archivo.

## Archivo de cuentas {#accounts-file}

Se usa con `--accounts-file`.

```yaml
accounts:
  - account_id: "123456789012"         # required, in quotes
    account_name: Production           # optional, shown in reports
    role_arn: arn:aws:iam::123456789012:role/InvenTagReadOnly
    external_id: optional-external-id  # only if the trust policy needs it
    regions: [us-east-1, eu-west-1]    # optional; empty = every enabled region
    services: []                       # optional; empty = all services
  - account_id: "210987654321"
    account_name: Development
    profile_name: dev-readonly         # an AWS CLI profile instead of a role
settings:                              # optional
  max_concurrent_accounts: 4
  account_processing_timeout: 1800     # seconds, at least 60
  output_directory: bom_output
```

Cada cuenta necesita **una** forma de obtener credenciales:

| Campo | Uso |
|---|---|
| `profile_name` | Un perfil de la AWS CLI, por ejemplo un perfil de IAM Identity Center. |
| `role_arn` | Un rol que InvenTag asume a partir de tus credenciales actuales. |
| `access_key_id` y `secret_access_key` (y `session_token` opcional) | Claves escritas en el archivo. Evítalo: cualquiera que pueda leer el archivo tiene las claves. InvenTag avisa cuando otros usuarios pueden leer un archivo así. |

Los valores de `settings` sustituyen a las opciones equivalentes de la línea de comandos.

Para usar el mismo nombre de rol en todas las cuentas, omite `role_arn` y añade
`--cross-account-role InvenTagReadOnly` al comando.

Un archivo de cuentas roto detiene la ejecución antes de analizar. Por ejemplo, un
ID de cuenta sin comillas (datos de ejemplo):

```text title="Salida"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

Hay ejemplos listos para usar en la carpeta
[`examples/`](https://github.com/habhabhabs/inventag-aws/tree/main/examples)
del repositorio, por ejemplo `accounts_cross_account_roles.json` y
`accounts_with_profiles.json`.

## Asignaciones de etiquetas {#tag-mappings}

Se usa con `--tag-mappings`. Cada entrada añade una columna con nombre al informe.
La columna muestra el valor de la etiqueta, o el valor predeterminado si el recurso no
tiene la etiqueta.

```yaml
tag_mappings:
  - tag: CostCenter          # required: the tag key
    name: Cost Center        # required: the column name
    default_value: Unknown   # optional: shown when the tag is missing
    description: Budget that pays for the resource
    required: false
    case_sensitive: false
```

La columna aparece en el libro predeterminado (sin `--template`). Con
`--template` no aparece, y una advertencia lo indica: usa `tag_columns` en la plantilla de informe en su lugar. Con
un archivo de diseño (`--excel-template`, `--word-template`), añade el nombre de la
columna a `extra_fields`.

Usa la clave de nivel superior `tag_mappings` con una **lista** de entradas. InvenTag también
acepta el diseño anterior, que usa cada clave de etiqueta como clave de nivel superior con un
valor `column_name`.

Resultado de ejemplo de la entrada anterior, en la hoja de EC2:

| service | type | id | Cost Center |
|---|---|---|---|
| EC2 | Instance | i-0abc1234def567890 | CC-1042 |
| EC2 | Volume | vol-0abc1234def567890 | Unknown |

## Descripciones de servicios {#service-descriptions}

Se usa con `--service-descriptions`. Añade la columna `service_description`
al informe. Sin archivo, InvenTag escribe una descripción integrada, por
ejemplo `Amazon EC2 Instance (i-0abc1234def567890) in us-east-1`.

```yaml
service_descriptions:
  DYNAMODB:
    default:
      description: Application data table
  EC2:
    Volume:
      description: Block storage
      template: volume_text       # optional: a text with variables
templates:
  volume_text:
    template: "Disk {resource_id} in {region}"
```

La clave de nivel superior `service_descriptions` es obligatoria. Bajo cada servicio,
cada tipo de recurso (o `default`) necesita una `description`.

**Tu entrada sustituye a la descripción integrada**, en todos los servicios. Una
entrada con `template` usa esa plantilla, definida en `templates`; una entrada sin
ella usa su `description` tal cual (en el ejemplo, `Application data table` para
las tablas de DynamoDB). Una plantilla puede usar `{resource_id}`,
`{resource_type}`, `{service}`, `{region}` y `{account_id}`. Los servicios sin
entrada en tu archivo conservan el texto integrado.

Si una plantilla no se puede rellenar, InvenTag registra una advertencia como
`Failed to render template vpc_vpc: 'cidr_block'` y usa el texto de respaldo.

## Configuración de procesamiento de la BOM {#bom-processing-configuration}

Se usa con `--bom-config`. Un mapeo YAML o JSON cuyas claves son campos de la
configuración de procesamiento de la BOM, por ejemplo:

```yaml
enable_network_analysis: false
enable_parallel_processing: true
max_worker_threads: 4
```

Las claves desconocidas se ignoran con una advertencia que las nombra, así que revisa el registro
por si hay una clave mal escrita. Un valor de tipo incorrecto detiene la ejecución con el
código de salida 1 y nombra la clave.
Por ejemplo, `enable_network_analysis: true` añade la misma hoja que
`--enable-network-analysis`. Este archivo es para ajustes avanzados; la mayoría de la gente nunca
lo necesita.

## Siguientes pasos {#next-steps}

- [Referencia de plantillas](../templates/reference.md)
- [Analiza varias cuentas](../guides/scan-multiple-accounts.md)
