---
title: Referencia de plantillas
description: Todos los campos de una plantilla de InvenTag (informe, política de etiquetas y configuración) con sus tipos, valores predeterminados y qué hace cada uno.
sidebar_position: 4
---

# Referencia de plantillas

**Para quién es:** estás escribiendo o revisando una plantilla y necesitas el
nombre, el tipo o el valor predeterminado exacto de un campo.

**Qué podrás hacer después de leerlo:** escribir cualquier plantilla sin
adivinar y leer los errores de validación con confianza.

## Estructura del archivo {#file-layout}

Toda plantilla es un archivo YAML con los mismos campos de nivel superior:

```yaml
format_version: 1          # optional; 1 is the only version
kind: report               # report | tag-policy | config
name: acme-bom             # lower-case letters, digits and hyphens
description: One sentence shown by 'templates list'
extends: standard-bom      # optional: a template name or a relative path
spec:                      # the settings for this kind
  title: Acme Cloud Inventory
```

- Los archivos terminan en `.yaml` o `.yml` y deben ser texto UTF-8 de como
  máximo 256 KiB. Un archivo que indicas por ruta también puede ser JSON (`.json`),
  por ejemplo `--template ./my.json`. Las plantillas que se buscan por nombre en
  las carpetas de búsqueda deben ser `.yaml` o `.yml`, y `templates init` escribe
  `.yaml`.
- El nombre del archivo debería coincidir con `name` (`acme-bom.yaml` tiene
  `name: acme-bom`). Las búsquedas por nombre usan el nombre del archivo.
- Los campos desconocidos son errores, así que los errores tipográficos nunca
  pasan en silencio.
- Las claves duplicadas son errores.
- Pon entre comillas los ID de cuenta y los colores hexadecimales
  (`"012345678901"`, `"1F3A5F"`) para que YAML los conserve como texto.

## Referencias a otros archivos {#references-to-other-files}

`extends`, `tag_policy`, `report_template` y `logo` pueden apuntar a otro
archivo:

- **Un nombre** (`standard-bom`) se busca en las
  [carpetas de búsqueda](./index.md#where-inventag-looks-for-templates).
- **Una ruta relativa** (`./policies/strict.yaml`) es relativa a la plantilla
  que la contiene y debe permanecer dentro de la carpeta de esa plantilla. Se
  rechazan `..` que salga de la carpeta, las rutas absolutas, `~` y las URL.

## Referencia de campos {#field-reference}

Esta sección se genera a partir del código
(`python -m inventag.templating.reference --write`), así que siempre coincide
con lo que acepta el validador.

### Campos de toda plantilla {#fields-in-every-template}

| Campo | Tipo | Predeterminado | Qué hace |
|---|---|---|---|
| `format_version` | número entero (mín. 1, máx. 1) | `1` | Versión del formato de plantilla. Hoy solo existe `1`. |
| `kind` | uno de `report`, `tag-policy`, `config` | obligatorio | Qué controla la plantilla: `report`, `tag-policy` o `config`. |
| `name` | nombre de plantilla | obligatorio | Letras minúsculas, dígitos y guiones. Debería coincidir con el nombre del archivo (`my-report.yaml` tiene `name: my-report`). |
| `description` | texto | vacío | Una frase que muestra `templates list`. |
| `extends` | nombre de plantilla o ruta relativa | sin definir | Plantilla de la que heredar, por nombre o por ruta relativa. Debe ser del mismo tipo. |
| `spec` | mapeo | obligatorio | Los ajustes de este tipo (ver más abajo). |

### Plantillas de informe (`kind: report`) {#report-templates-kind-report}

| Campo | Tipo | Predeterminado | Qué hace |
|---|---|---|---|
| `spec.title` | texto | `AWS Resource Inventory` | Título del informe, usado en la portada de Word y en la hoja de resumen de Excel. |
| `spec.subtitle` | texto | vacío | Línea opcional bajo el título. |
| `spec.company_name` | texto | vacío | Nombre de la organización que se muestra en la portada y se guarda en las propiedades del archivo. |
| `spec.colors` | mapeo | ver más abajo | Colores del encabezado como valores hexadecimales de seis dígitos (con o sin `#`). |
| `spec.logo` | ruta de archivo relativa | sin definir | Imagen que se muestra en la portada de Word (PNG, JPEG, GIF o BMP). La ruta es relativa al archivo de plantilla y debe permanecer dentro de su carpeta. |
| `spec.logo_alt_text` | texto | vacío | Texto alternativo del logotipo, que leen los lectores de pantalla. Por defecto es `<company_name> logo`. |
| `spec.columns` | lista de mapeos | ver el `standard-bom` integrado | Columnas de las tablas de recursos, en orden. |
| `spec.tag_columns` | `all`, `none` o lista de claves de etiqueta | `all` | Columnas adicionales, una por clave de etiqueta, añadidas después de `columns`. Puede ser una lista de claves de etiqueta, `all` para todas las claves de etiqueta que se encuentren en los recursos de esa tabla, o `none`. |
| `spec.tag_policy` | nombre de plantilla o ruta relativa | sin definir | Política de etiquetas que se comprueba, por nombre o por ruta relativa. Un `--template` con una política de etiquetas en la línea de comandos tiene prioridad. |
| `spec.excel` | mapeo | ver más abajo | Diseño del libro de Excel. |
| `spec.word` | mapeo | ver más abajo | Diseño del documento de Word. |
| `spec.colors.header_fill` | color hexadecimal | `1F3A5F` | Fondo de las filas de encabezado de las tablas. |
| `spec.colors.header_text` | color hexadecimal | `FFFFFF` | Color del texto de las filas de encabezado de las tablas. |
| `spec.columns[].field` | texto | obligatorio | Campo del recurso que se muestra. Usa puntos para los valores anidados: `tags.Owner` es la etiqueta `Owner`, `raw_data.InstanceType` es un valor de la respuesta de la API de AWS. |
| `spec.columns[].header` | texto | sin definir | Encabezado de la columna. Por defecto es el nombre del campo en lenguaje llano (`resource_name` pasa a ser `Resource name`). |
| `spec.columns[].width` | número entero (mín. 4, máx. 120) | sin definir | Ancho de la columna de Excel en caracteres. Por defecto es un ancho que se ajusta al contenido, limitado por `excel.max_column_width`. |
| `spec.excel.summary_sheet` | verdadero o falso | `true` | Añade una hoja Summary con el recuento de recursos por servicio. |
| `spec.excel.layout` | uno de `per-service`, `single-sheet` | `per-service` | `per-service` pone cada servicio en su propia hoja. `single-sheet` pone todos los recursos en una hoja con una columna Service. |
| `spec.excel.single_sheet_name` | texto | `Resources` | Nombre de la hoja cuando `layout` es `single-sheet`. |
| `spec.excel.include_all_fields` | verdadero o falso | `false` | Añade también todos los demás campos que se encuentren en los recursos, después de las columnas indicadas. Útil para auditorías; genera hojas anchas. |
| `spec.excel.freeze_header` | verdadero o falso | `true` | Mantiene visible la fila de encabezado al desplazarte. |
| `spec.excel.autofilter` | verdadero o falso | `true` | Añade botones de filtro a la fila de encabezado. |
| `spec.excel.max_column_width` | número entero (mín. 10, máx. 120) | `50` | Límite superior de los anchos de columna automáticos, en caracteres. |
| `spec.excel.tag_compliance_sheet` | verdadero o falso | `true` | Añade una hoja Tag Compliance cuando hay una política de etiquetas activa. |
| `spec.word.orientation` | uno de `portrait`, `landscape` | `portrait` | Orientación de la página. |
| `spec.word.sections` | lista de valores de `cover`, `summary`, `service-summary`, `tag-compliance`, `service-tables`, `about` | `["cover", "summary", "service-summary", "tag-compliance", "service-tables", "about"]` | Secciones que se incluyen, en orden. Elige entre: `cover`, `summary`, `service-summary`, `tag-compliance`, `service-tables`, `about`. `tag-compliance` se omite cuando no hay una política de etiquetas activa. |
| `spec.word.columns` | lista de mapeos | sin definir | Columnas de las tablas por servicio. Por defecto son las primeras `max_columns` entradas de `columns`. No se añaden columnas de etiquetas. |
| `spec.word.max_columns` | número entero (mín. 1, máx. 12) | `6` | Cuántas de las `columns` se usan cuando no se define `word.columns`. Las tablas de Word se vuelven difíciles de leer a partir de seis o siete columnas. |
| `spec.word.max_rows_per_service` | número entero (mín. 1, máx. 10000) | `50` | Filas que se muestran por tabla de servicio. Una nota indica cuántas se dejaron fuera. |
| `spec.word.max_noncompliant_rows` | número entero (mín. 1, máx. 10000) | `100` | Filas que se muestran en la tabla de recursos que no cumplen. |
| `spec.word.columns[].field` | texto | obligatorio | Campo del recurso que se muestra. Usa puntos para los valores anidados: `tags.Owner` es la etiqueta `Owner`, `raw_data.InstanceType` es un valor de la respuesta de la API de AWS. |
| `spec.word.columns[].header` | texto | sin definir | Encabezado de la columna. Por defecto es el nombre del campo en lenguaje llano (`resource_name` pasa a ser `Resource name`). |
| `spec.word.columns[].width` | número entero (mín. 4, máx. 120) | sin definir | Ancho de la columna de Excel en caracteres. Por defecto es un ancho que se ajusta al contenido, limitado por `excel.max_column_width`. |

### Plantillas de política de etiquetas (`kind: tag-policy`) {#tag-policy-templates-kind-tag-policy}

| Campo | Tipo | Predeterminado | Qué hace |
|---|---|---|---|
| `spec.required_tags` | lista de mapeos | obligatorio | Etiquetas que deben tener los recursos dentro del alcance. Cuando una plantilla usa `extends` con otra, las entradas se combinan por `key`: la misma clave sustituye, las claves nuevas se añaden y `remove: true` elimina una. |
| `spec.scope` | mapeo | ver más abajo | A qué recursos se aplica la política. Los recursos fuera del alcance se cuentan, pero no se comprueban. |
| `spec.required_tags[].key` | texto | obligatorio | Clave de la etiqueta. Las claves de etiqueta de AWS distinguen mayúsculas y minúsculas, así que `costcenter` no satisface `CostCenter`. |
| `spec.required_tags[].description` | texto | vacío | Por qué existe la etiqueta. Se muestra en los informes. |
| `spec.required_tags[].allowed_values` | lista de textos | sin definir | Si se define, el valor de la etiqueta debe ser uno de estos. |
| `spec.required_tags[].case_sensitive` | verdadero o falso | `false` | Compara `allowed_values` distinguiendo mayúsculas y minúsculas. |
| `spec.required_tags[].pattern` | expresión regular | sin definir | Si se define, todo el valor de la etiqueta debe coincidir con esta expresión regular (sintaxis de Python). |
| `spec.required_tags[].remove` | verdadero o falso | `false` | En una plantilla que usa `extends` con otra, elimina esta etiqueta de la lista heredada. |
| `spec.scope.services` | lista de textos | `[]` | Comprueba solo estos servicios (tal como se muestran en el informe, por ejemplo `EC2`, `S3`). Vacío significa todos los servicios. |
| `spec.scope.resource_types` | lista de textos | `[]` | Comprueba solo estos tipos de recurso (por ejemplo `Bucket`, `Instance`). Vacío significa todos los tipos. |
| `spec.scope.exclude_resource_types` | lista de textos | `[]` | No comprueba nunca estos tipos de recurso, por ejemplo tipos que no pueden llevar etiquetas. |

### Plantillas de configuración (`kind: config`) {#config-templates-kind-config}

| Campo | Tipo | Predeterminado | Qué hace |
|---|---|---|---|
| `spec.accounts` | lista de mapeos | sin definir | Cuentas que se analizan. Omítelo para analizar la cuenta de tus credenciales de AWS actuales. Cada cuenta necesita `profile_name` o `role_arn`. |
| `spec.regions` | lista de textos | sin definir | Regiones que se analizan (`--account-regions`). Omítelo para analizar todas las regiones habilitadas. |
| `spec.services` | lista de textos | sin definir | Servicios que se incluyen (`--account-services`). Por ahora se aplica solo en una ruta de descubrimiento, así que aún pueden aparecer otros servicios. |
| `spec.outputs` | lista de valores de `excel`, `word` | `["excel"]` | Archivos que se producen (`--create-excel`, `--create-word`). |
| `spec.output_directory` | texto | `bom_output` | Carpeta de los informes (`--output-directory`). |
| `spec.report_template` | nombre de plantilla o ruta relativa | `standard-bom` | Plantilla de informe que se usa, por nombre o ruta relativa. |
| `spec.tag_policy` | nombre de plantilla o ruta relativa | sin definir | Política de etiquetas que se comprueba, por nombre o ruta relativa. |
| `spec.fail_on_tag_violations` | verdadero o falso | `false` | Termina con el código 3 tras escribir los informes si algún recurso dentro del alcance incumple la política de etiquetas. Requiere `tag_policy`. |
| `spec.max_concurrent_accounts` | número entero (mín. 1, máx. 64) | `4` | Cuentas que se analizan al mismo tiempo (`--max-concurrent-accounts`). |
| `spec.account_processing_timeout` | número entero (mín. 60) | `1800` | Segundos permitidos por cuenta (`--account-processing-timeout`). |
| `spec.parallel_processing` | verdadero o falso | `true` | Analiza las cuentas en paralelo. `false` equivale a `--disable-parallel-processing`. |
| `spec.accounts[].account_id` | texto | obligatorio | ID de cuenta de AWS de 12 dígitos, entre comillas para que YAML conserve los ceros iniciales. |
| `spec.accounts[].account_name` | texto | vacío | Nombre descriptivo que se usa en los informes. |
| `spec.accounts[].profile_name` | texto | sin definir | Perfil de la CLI de AWS que se usa para esta cuenta. |
| `spec.accounts[].role_arn` | texto | sin definir | Rol de IAM que se asume en esta cuenta, como ARN completo. |
| `spec.accounts[].external_id` | texto | sin definir | ID externo que exige la política de confianza del rol. |
| `spec.accounts[].regions` | lista de textos | sin definir | Regiones que se analizan en esta cuenta. Sustituye a `spec.regions`. |
| `spec.accounts[].services` | lista de textos | sin definir | Servicios que se analizan en esta cuenta. |

## Campos de recurso que puedes usar como columnas {#resource-fields-you-can-use-as-columns}

El `field` de una columna lee un valor de cada recurso. Estos campos están
presentes en los recursos de una ejecución normal:

| Campo | Contiene |
|---|---|
| `service` | Nombre del servicio tal como se muestra en el informe, por ejemplo `S3`, `EC2`, `VPC` |
| `resource_type` | Por ejemplo `Bucket`, `Volume`, `Subnet` |
| `resource_name` | Nombre, cuando el recurso tiene uno |
| `resource_id` | El ID del recurso |
| `arn` | Amazon Resource Name, cuando se conoce |
| `region` | Código de región |
| `source_account_id` | Cuenta en la que se encontró el recurso |
| `source_account_name` | El `account_name` que le diste a esa cuenta |
| `tags` | Todas las etiquetas, escritas como `Key=Value, Key=Value` |
| `tags.<Key>` | El valor de una etiqueta, por ejemplo `tags.Owner` |
| `tagged` | `Yes` o `No` |
| `discovered_via` | Qué API encontró el recurso |
| `source` | De dónde viene la fila: `service-api`, `tagging-api` o `billing` |
| `sources` | Todas las fuentes que informaron del recurso, unidas con `+`, por ejemplo `service-api+tagging-api` |
| `detail_level` | `full` si la API propia del servicio describió el recurso; `identity` si solo se conoce su identidad (ARN y etiquetas) |
| `raw_data.<Name>` | Un valor de la respuesta de la API de AWS, por ejemplo `raw_data.VolumeType` |

InvenTag sustituye por `***REDACTED***` los valores de los campos que suelen
contener secretos antes de escribir cualquier informe. Por ejemplo, los valores
de las variables de entorno de Lambda, los datos de usuario de EC2, los valores
de los parámetros de CloudFormation y las contraseñas de las conexiones de Glue.
Los nombres se conservan, así que sigues viendo que la variable existe. Un
secreto en un campo que no está en la lista de InvenTag, como una descripción o
una etiqueta, no se reconoce.

Los valores que faltan se dejan en blanco. Para ver todos los campos que tienen
tus recursos, establece `excel.include_all_fields: true` y mira las columnas
adicionales.

## Mensajes de validación {#validation-messages}

`inventag templates validate <file>` y cada ejecución con `--template`
imprimen los problemas así:

```text
<file>:<line>: <field>: <what is wrong>
```

Por ejemplo, una plantilla con `header_fill: blue`, usada en una ejecución:

```text title="Salida"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

Y un nombre de plantilla mal escrito:

```text title="Salida"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

Cuando una plantilla usa `extends` con otra, los problemas se informan en el
archivo que los contiene.

## Códigos de salida {#exit-codes}

| Comando | Código | Significado |
|---|---|---|
| `templates validate` | 0 | Todos los archivos son válidos |
| `templates validate` | 1 | Al menos un archivo tiene un problema |
| `templates init` | 1 | El archivo de salida ya existe (usa `--force`) o la plantilla no es válida |
| `templates init` | 2 | El nombre o la extensión de salida no está permitido |
| `inventag --template ...` | 1 | Una plantilla no es válida o la ejecución falló |
| `inventag --template ...` | 3 | Se escribieron los informes, pero hay recursos que incumplen la política de etiquetas y `fail_on_tag_violations` es `true` |
| `inventag --template ...` | 5 | Se escribieron los informes, pero una cuenta falló o se analizó solo en parte, y pasaste `--fail-on-account-error` |
| `inventag --template ...` | 6 | No se encontró ningún recurso y pasaste `--fail-if-empty` |
