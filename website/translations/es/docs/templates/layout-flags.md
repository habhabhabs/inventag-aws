---
title: Archivos de diseño para un informe
description: Cambia el título, las secciones, las hojas, las columnas, el encabezado y el pie de los informes BOM de Word y Excel con un archivo de plantilla YAML o JSON.
sidebar_position: 5
---

# Archivos de diseño para un informe

Esta página describe las opciones `--word-template` y `--excel-template`. Cada
opción recibe un archivo de diseño para un formato de informe. Para las
plantillas con nombre que eliges con `--template`, consulta
[Plantillas](./index.md).

Una plantilla de informe es un archivo YAML o JSON. La plantilla controla la
estructura del informe de Word o del informe de Excel. Pasa el archivo a la CLI
con `--word-template` o `--excel-template`.

Si no das ninguna plantilla, InvenTag usa la plantilla predeterminada integrada.
El informe tiene entonces la misma estructura que en las versiones sin
plantillas.

## Qué puede cambiar una plantilla {#what-a-template-can-change}

| Elemento | Informe de Word | Informe de Excel |
|---|---|---|
| Título y subtítulo | Sección de título del documento | Propiedades del libro y filas opcionales sobre la tabla de resumen |
| Nombre de la empresa | Valor de `{{ company_name }}` | Valor de `{{ company_name }}` y la propiedad de creador del libro |
| Logotipo | Archivo PNG o JPEG sobre el título | No disponible |
| Secciones u hojas | Qué secciones aparecen y su orden | Qué hojas aparecen y su orden |
| Columnas | Qué columnas aparecen, su orden, encabezado y ancho | Qué columnas aparecen, su orden, encabezado y ancho |
| Servicios | Qué servicios aparecen en las tablas de recursos y su orden | Qué servicios tienen una hoja y su orden |
| Encabezado y pie | Encabezado de página, pie de página, número de página | Encabezado de impresión y pie de impresión de cada hoja |
| Color de la fila de encabezado | No disponible | Color de relleno de la fila de encabezado |
| Texto libre | Encabezados y párrafos con variables | No disponible |

## Crear una plantilla {#make-a-template}

1. Imprime la plantilla predeterminada en un archivo.

   ```bash
   inventag --print-default-template word > my_word_template.yaml
   inventag --print-default-template excel > my_excel_template.json
   ```

2. Edita el archivo. Consulta la [referencia de claves](#key-reference).

3. Valida el archivo. Este comando no hace ninguna llamada a AWS.

   ```bash
   inventag --validate-templates \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

   Si los archivos son válidos, la CLI imprime una línea `OK` por cada archivo
   y termina con el código de salida `0`.

4. Usa el archivo en una ejecución.

   ```bash
   inventag --create-word --create-excel \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

La CLI acepta las extensiones de nombre de archivo `.yaml`, `.yml` y `.json`
para los dos formatos. Los archivos de plantilla predeterminados también están
en el repositorio: `templates/default_word_template.yaml` y
`templates/default_excel_template.json`.

## Opciones de plantilla {#template-flags}

| Opción | Función |
|---|---|
| `--word-template PATH` | Plantilla del informe de Word. Esta opción necesita `--create-word`. |
| `--excel-template PATH` | Plantilla del informe de Excel. Esta opción necesita `--create-excel`. Sin ella, la CLI termina con el código de salida `2`. |
| `--print-default-template word` o `--print-default-template excel` | Imprime la plantilla predeterminada y termina con el código de salida `0`. |
| `--validate-templates` | Valida los archivos de `--word-template` y `--excel-template` y termina. Sin llamadas a AWS. |

## Ejemplos mínimos {#minimal-examples}

Esta plantilla de Word da un título, una tabla de recursos por cada servicio y
una tabla de resumen.

```yaml title="my_word_template.yaml"
template_version: "2.0"
format_type: word
document:
  title: "{{ company_name }} Cloud Inventory"
  subtitle: "Accounts: {{ account_ids }}"
branding:
  company_name: Example Corp
header_footer:
  header_text: "{{ company_name }} - Internal"
  footer_text: "Generated {{ generated_date }}"
  include_page_numbers: true
sections:
  - id: title
    content_type: title
  - id: inventory
    content_type: resources
    title: Resources
    service_title: "{{ service }} ({{ service_resource_count }})"
    columns:
      - field: name
        heading: Resource name
        width: 2.5
      - field: region
      - field: tags.Owner
        heading: Owner
  - id: summary
    content_type: service_summary
    title: "Summary of {{ total_resources }} resources"
```

Esta plantilla de Excel da una hoja con todos los recursos y después la hoja de
resumen.

```json title="my_excel_template.json"
{
  "template_version": "2.0",
  "format_type": "excel",
  "document": {"title": "{{ company_name }} inventory"},
  "branding": {"company_name": "Example Corp", "header_color": "1F4E78"},
  "sections": [
    {
      "id": "all_resources",
      "content_type": "resources",
      "group_by_service": false,
      "sheet_name": "All resources",
      "columns": [
        {"field": "service", "heading": "Service", "width": 14},
        {"field": "name", "heading": "Name"},
        {"field": "region", "heading": "Region"},
        {"field": "tags.Owner", "heading": "Owner"}
      ]
    },
    {
      "id": "summary",
      "content_type": "service_summary",
      "sheet_name": "Summary",
      "show_title": true
    }
  ]
}
```

## Variables {#variables}

Escribe una variable como `{{ name }}` en un valor de texto. InvenTag sustituye
la variable por su valor cuando escribe el informe.

| Variable | Valor |
|---|---|
| `{{ company_name }}` | El valor de `branding.company_name`. |
| `{{ document_title }}` | El valor de `document.title` después de la sustitución. |
| `{{ document_subtitle }}` | El valor de `document.subtitle` después de la sustitución. |
| `{{ generated_at }}` | Hora de generación en UTC, formato `YYYY-MM-DD HH:MM:SS`. |
| `{{ generated_date }}` | Fecha de generación en UTC, formato `YYYY-MM-DD`. |
| `{{ account_ids }}` | Los ID de cuenta del informe, ordenados y separados por una coma y un espacio. |
| `{{ account_count }}` | El número de ID de cuenta distintos del informe. |
| `{{ total_resources }}` | El número de recursos del informe. |
| `{{ service_count }}` | El número de servicios distintos del informe. |
| `{{ region_count }}` | El número de regiones distintas del informe. |

Estas variables solo son válidas en `service_title` y `truncation_note` de una
sección `resources` de Word:

| Variable | Valor |
|---|---|
| `{{ service }}` | El nombre del servicio de la tabla actual. |
| `{{ service_resource_count }}` | El número de recursos del servicio actual. |
| `{{ shown_resource_count }}` | El número de filas de la tabla actual. |

Puedes definir tus propias variables en `variables`:

```yaml
variables:
  classification: Internal
header_footer:
  footer_text: "Classification: {{ classification }}"
```

Reglas para las variables:

- El nombre de una variable solo tiene letras, dígitos y guiones bajos.
- El nombre de tu propia variable empieza por una letra minúscula y solo tiene
  letras minúsculas, dígitos y guiones bajos.
- No puedes usar el nombre de una variable integrada para tu propia variable.
- El valor de una variable es texto simple. Un valor no puede contener otra
  variable.
- `document.title` y `document.subtitle` no pueden usar `{{ document_title }}`
  ni `{{ document_subtitle }}`.
- Estas claves aceptan variables: `document.title`, `document.subtitle`,
  `header_footer.header_text`, `header_footer.footer_text` y las claves de
  sección `title`, `paragraphs`, `service_title` y `truncation_note`.
- Los encabezados de columna, los nombres de hoja y `branding.company_name` no
  aceptan variables.
- InvenTag no admite expresiones, filtros, condiciones, bucles ni inclusión de
  archivos. Por ejemplo, `{{ company_name | upper }}` es un error.
- InvenTag no sustituye variables en los datos de los recursos. Un nombre de
  recurso con el texto `{{ company_name }}` permanece sin cambios en el informe.

## Referencia de claves {#key-reference}

Una prueba en `tests/unit/test_template_system.py` comprueba que esta
referencia contiene cada clave del esquema de
`inventag/reporting/report_template.py`.

### Claves de nivel superior {#top-level-keys}

| Clave | Tipo | Formatos | Predeterminado | Descripción |
|---|---|---|---|---|
| `template_version` | cadena | Word y Excel | Necesaria | Versión del esquema. Debe ser `"2.0"`. |
| `format_type` | cadena | Word y Excel | Necesaria | `word` o `excel`. |
| `name` | cadena | Word y Excel | Vacío | Un nombre para la plantilla. No se muestra en el informe. |
| `description` | cadena | Word y Excel | Vacío | Una descripción. No se muestra en el informe. |
| `document` | mapeo | Word y Excel | Ver más abajo | Título y subtítulo. |
| `branding` | mapeo | Word y Excel | Ver más abajo | Nombre de la empresa, logotipo y color. |
| `variables` | mapeo | Word y Excel | Vacío | Tus propias variables: nombre a texto. |
| `extra_fields` | lista | Word y Excel | Vacío | Más nombres de campos de recurso que `columns` puede usar. Por ejemplo, una columna de tus asignaciones de etiquetas. |
| `header_footer` | mapeo | Word y Excel | Ver más abajo | Texto del encabezado y del pie. |
| `sections` | lista | Word y Excel | Necesaria | Las secciones (Word) u hojas (Excel), en el orden del informe. |

### `document` {#document}

| Clave | Tipo | Formatos | Predeterminado | Descripción |
|---|---|---|---|---|
| `title` | cadena | Word y Excel | Vacío | Word: el texto de la sección `title`. Excel: la propiedad de título del libro. |
| `subtitle` | cadena | Word y Excel | Vacío | Word: una línea bajo el título. Excel: la propiedad de asunto del libro. |

### `branding` {#branding}

| Clave | Tipo | Formatos | Predeterminado | Descripción |
|---|---|---|---|---|
| `company_name` | cadena | Word y Excel | Vacío | El valor de `{{ company_name }}`. Excel: también la propiedad de creador del libro. |
| `logo_path` | cadena | Word | Ninguno | Archivo PNG o JPEG que se muestra sobre el título. La ruta es relativa al archivo de plantilla y debe permanecer en su directorio. |
| `logo_width_inches` | número | Word | `1.5` | Ancho del logotipo, de 0,25 a 7. |
| `header_color` | cadena | Excel | `366092` | Color de relleno de la fila de encabezado, seis dígitos hexadecimales. |

### `header_footer` {#header_footer}

| Clave | Tipo | Formatos | Predeterminado | Descripción |
|---|---|---|---|---|
| `header_text` | cadena | Word y Excel | Vacío | Word: encabezado de página. Excel: encabezado de impresión de cada hoja. Máximo 255 caracteres. |
| `footer_text` | cadena | Word y Excel | Vacío | Word: pie de página. Excel: pie de impresión de cada hoja. Máximo 255 caracteres. |
| `include_page_numbers` | booleano | Word | `false` | Añade `Page <number>` al pie de página. |

El encabezado y el pie de impresión de Excel solo se muestran en la vista de
diseño de página y en papel.

### `sections` {#sections}

Cada entrada de `sections` es un mapeo. La clave `content_type` selecciona lo
que muestra la sección.

| `content_type` | Formatos | Función |
|---|---|---|
| `title` | Word | El título del documento, el subtítulo y el logotipo. |
| `text` | Word | Un encabezado opcional y una lista de párrafos. |
| `service_summary` | Word y Excel | Una fila por servicio: nombre, número de recursos, porcentaje. Una tabla en Word, una hoja en Excel. |
| `resources` | Word y Excel | Las tablas de recursos. Word: una tabla por servicio. Excel: una hoja por servicio o una hoja para todos los recursos. |
| `network_analysis` | Excel | La hoja de análisis de red. InvenTag la escribe solo si existen datos de análisis de red. |
| `security_analysis` | Excel | La hoja de análisis de seguridad. InvenTag la escribe solo si existen datos de análisis de seguridad. |
| `cost_analysis` | Excel | La hoja de análisis de costes. InvenTag la escribe solo si existen datos de análisis de costes (--enable-cost-analysis). |

Claves de sección:

| Clave | Tipo | Formatos | Tipos de sección | Predeterminado | Descripción |
|---|---|---|---|---|---|
| `id` | cadena | Word y Excel | Todos | Necesaria | Nombre único de la sección: letras minúsculas, dígitos y guiones bajos. |
| `content_type` | cadena | Word y Excel | Todos | Necesaria | Lo que muestra la sección. |
| `enabled` | booleano | Word y Excel | Todos | `true` | Establécela en `false` para omitir la sección. |
| `title` | cadena | Word | `text`, `service_summary`, `resources` | Vacío | Texto del encabezado de la sección. |
| `level` | entero | Word | `text`, `service_summary`, `resources` | `1` | Nivel de encabezado, de 1 a 3. Los encabezados de servicio usan el nivel siguiente. |
| `page_break_before` | booleano | Word | Todos | `false` | Empieza la sección en una página nueva. |
| `paragraphs` | lista | Word | `text` | Lista vacía | Los párrafos de una sección `text`. |
| `columns` | `auto` o lista | Word y Excel | `service_summary`, `resources` | `auto` | `auto` o una lista de columnas. Consulta [Columnas](#columns). |
| `table_style` | cadena | Word | `service_summary`, `resources` | `Light Grid Accent 1` para `service_summary`, `Light List Accent 1` para `resources` | Estilo de tabla de Word. |
| `services` | lista | Word y Excel | `resources` | Todos los servicios | Muestra solo estos servicios, en este orden. La comparación ignora mayúsculas, espacios y los prefijos `Amazon` y `AWS`. |
| `service_title` | cadena | Word | `resources` | `{{ service }} Resources ({{ service_resource_count }})` | Encabezado de cada tabla de servicio. |
| `max_rows` | entero | Word | `resources` | `50` | Número máximo de filas de cada tabla de servicio, de 1 a 100000. |
| `max_columns` | entero | Word | `resources` | `6` | Número máximo de columnas si `columns` es `auto`, de 1 a 100. |
| `truncation_note` | cadena | Word | `resources` | `Note: Showing first {{ shown_resource_count }} of {{ service_resource_count }} {{ service }} resources.` | Párrafo bajo una tabla que no muestra todos los recursos. |
| `page_break_after_service` | booleano | Word | `resources` | `true` | Empieza una página nueva después de cada tabla de servicio. |
| `sheet_name` | cadena | Excel | `service_summary`, `resources` | `Summary` para `service_summary` | Nombre de la hoja, de 1 a 31 caracteres. Necesaria en una sección `resources` con `group_by_service: false`. |
| `group_by_service` | booleano | Excel | `resources` | `true` | `true`: una hoja por servicio. `false`: una hoja para todos los recursos. |
| `show_title` | booleano | Excel | `service_summary` | `false` | Escribe el título y el subtítulo del documento sobre la tabla. |

Notas:

- Un documento de Word muestra las secciones en el orden de la lista.
- Un libro muestra las hojas en el orden de la lista.
- Con `group_by_service: true`, cada hoja tiene el nombre de su servicio.
- Una sección `resources` de Word ordena los servicios por nombre, salvo que
  indiques `services`.
- Los valores válidos de `table_style` son los estilos de tabla del documento de
  Word predeterminado. Algunos ejemplos son `Table Grid`, `Light List Accent 1`,
  `Light Grid Accent 1` y `Medium Shading 1 Accent 1`.

### Columnas {#columns}

La clave `columns` es `auto` o una lista. Cada entrada de la lista es un nombre
de campo o un mapeo con estas claves:

| Clave | Tipo | Formatos | Predeterminado | Descripción |
|---|---|---|---|---|
| `field` | cadena | Word y Excel | Necesaria | El campo que se muestra. |
| `heading` | cadena | Word y Excel | Ver más abajo | El encabezado de la columna. |
| `width` | número | Word y Excel | Automático | Ancho de la columna. Word: pulgadas, de 0,2 a 10. Excel: caracteres, de 1 a 255. |

Encabezados predeterminados:

- Word: el nombre del campo con espacios y mayúsculas. Por ejemplo,
  `source_account_id` pasa a ser `Source Account Id`.
- Excel: el nombre del campo.

Función de `auto`:

- Sección `resources` de Word: un máximo de `max_columns` campos por servicio.
  Los primeros campos son `name`, `id`, `type`, `region`, `compliance_status` y
  `tags`, si el servicio los tiene.
- Sección `resources` de Excel: todos los campos de los recursos de la hoja.
- Sección `service_summary`: `service`, `resource_count` y `percentage`.

Campos de una sección `service_summary`: `service`, `resource_count`,
`percentage`.

Campos de una sección `resources`:

| Grupo | Campos |
|---|---|
| Identidad | `service`, `type`, `id`, `name`, `arn` |
| Cuenta y ubicación | `account_id`, `source_account_id`, `source_account_name`, `account_name`, `region`, `availability_zone` |
| Detalles del recurso | `status`, `state`, `creation_date`, `created_time`, `launch_time`, `size`, `instance_type`, `storage_type`, `engine`, `engine_version`, `allocated_storage`, `storage_encrypted`, `multi_az`, `publicly_accessible`, `vpc_id`, `vpc_name`, `subnet_id`, `subnet_name`, `security_groups`, `security_group_ids` |
| Red | `vpc_cidr_block`, `vpc_total_ips`, `vpc_utilization_percentage`, `subnet_cidr_block`, `subnet_total_ips`, `subnet_utilization_percentage`, `subnet_is_public`, `subnet_availability_zone` |
| Seguridad | `security_risk_level`, `security_group_count`, `max_security_risk`, `inbound_rules_count`, `outbound_rules_count`, `associated_resources_count`, `has_permissive_rules`, `permissive_rules` |
| Costes | `estimated_monthly_cost`, `cost_breakdown`, `pricing_model`, `confidence_level`, `cost_optimization_opportunities`, `monthly_spend`, `service_monthly_spend`, `billing_validated` |
| Descubrimiento y cumplimiento | `compliance_status`, `compliance_score`, `discovery_timestamp`, `consolidation_timestamp`, `total_accounts_in_consolidation`, `discovered_at`, `discovered_via`, `priority`, `tagged`, `tags`, `service_description`, `resource_id`, `resource_name`, `resource_type` |
| Una etiqueta | `tags.<key>`, por ejemplo `tags.Owner` |
| Un atributo sin procesar de la API | `raw_data.<key>`, por ejemplo `raw_data.InstanceType` |
| Tus propios campos | Cada nombre de `extra_fields` |

Si un recurso no tiene un campo, la celda queda vacía. El campo `tags` muestra
todas las etiquetas de un recurso en una celda.

## Errores de validación {#validation-errors}

La CLI valida cada plantilla antes de la primera llamada a AWS. Si una plantilla
no es válida, la CLI imprime una línea por cada problema en la salida de error
estándar y termina con el código de salida `1`. Cada línea tiene este formato:

```text
inventag: error: <file>: <key path>: <reason>
```

Ejemplo:

```text
inventag: error: my_word_template.yaml: colour: unknown key. Allowed keys: template_version, format_type, name, description, document, branding, variables, extra_fields, header_footer, sections
inventag: error: my_word_template.yaml: sections[1].columns[2].field: unknown column 'owner_name'. Use a known field (for example service, type, id, name, region, account_id, tags), a tags.<key> field, or add the name to extra_fields
```

| Problema | Inicio del motivo |
|---|---|
| Una clave que el esquema no tiene | `unknown key. Allowed keys: ...` |
| Una clave del otro formato de informe | `this key is not valid in a Word template` o `this key is not valid in an Excel template` |
| Un valor de tipo incorrecto | `must be a string, but the value is integer` |
| Falta una clave necesaria | `missing key` |
| Un tipo de sección que no existe | `unknown section type 'cover_page' for a Word template. Allowed values: ...` |
| Una columna que no existe | `unknown column 'owner_name'` |
| Una variable que no existe | `unknown variable 'owner'. Allowed variables: ...` |
| Una expresión, un filtro o llaves anidadas | `malformed placeholder` |
| Dos secciones con el mismo `id` | `duplicate id 'summary'` |
| Una plantilla del formato incorrecto | `the file is a template for Excel reports, but this flag needs a template for Word reports` |
| Una plantilla antigua con `template_version: "1.0"` | `unsupported version '1.0'` |
| Una ruta de logotipo que sale del directorio de la plantilla | `the path must stay in the directory of the template file` |
| Un archivo que no es YAML ni JSON | `YAML syntax error at line ...` o `JSON syntax error at line ...` |
| Un archivo con otra extensión | `unsupported file type` |
| Un archivo demasiado grande | `The maximum is 262144 bytes` |

Códigos de salida de las opciones de plantilla:

| Código de salida | Condición |
|---|---|
| `0` | `--validate-templates` no encontró ningún problema, o `--print-default-template` imprimió la plantilla. |
| `1` | Un archivo de plantilla no es válido. |
| `2` | Error de uso. Por ejemplo, `--word-template` sin `--create-word`, o `--validate-templates` sin una opción de plantilla. |

## Límites {#limits}

| Elemento | Límite |
|---|---|
| Tamaño del archivo de plantilla | 262144 bytes (256 KiB) |
| Valor de texto | 2000 caracteres |
| Texto del encabezado y del pie | 255 caracteres |
| Secciones | 50 |
| Columnas en una sección | 100 |
| Párrafos en una sección `text` | 100 |
| Tus propias variables | 50 |
| Entradas en `extra_fields` | 200 |
| Tamaño del archivo de logotipo | 5242880 bytes (5 MiB) |
| Tipos de archivo de logotipo | `.png`, `.jpg`, `.jpeg` |
| Nombre de hoja de Excel | 31 caracteres, sin `[ ] : * ? / \` |

Otros límites:

- Una plantilla no puede cambiar las fuentes, los colores de los encabezados ni
  el tamaño de página del informe de Word.
- Una plantilla no puede cambiar las columnas de la hoja de análisis de red ni
  de la hoja de análisis de seguridad.
- Una plantilla no puede añadir una tabla de contenido, gráficos ni un logotipo
  al informe de Excel.
- Un estilo de tabla de Word debe ser un estilo del documento de Word
  predeterminado.
- Los scripts heredados de `scripts/legacy/` no tienen las opciones de
  plantilla.
- Las claves de configuración `templates`, `document_templates` y
  `default_template` de los ejemplos de configuración antiguos no tienen
  efecto. Solo `--word-template` y `--excel-template` seleccionan una plantilla.
- Los archivos de plantilla con `template_version: "1.0"` no son válidos. Las
  alpha builds anteriores a la 1.0.0 incluían esos archivos, pero la CLI no los leía.

## Seguridad de los archivos de plantilla {#safety-of-template-files}

- InvenTag lee YAML con `yaml.safe_load`. Un archivo YAML no puede ejecutar
  código.
- InvenTag no evalúa expresiones. La sustitución reemplaza solo los nombres de
  las tablas de [variables](#variables).
- InvenTag no sustituye variables en los datos de recursos procedentes de AWS.
- Una plantilla no puede incluir otro archivo. La única referencia a un archivo
  es `branding.logo_path`, y ese archivo debe estar en el directorio de la
  plantilla.
- El generador de Excel guarda cada valor como texto. Un valor que empieza por
  `=` no se ejecuta como fórmula.
