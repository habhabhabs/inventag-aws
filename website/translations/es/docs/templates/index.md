---
title: Plantillas
description: Reutiliza diseños de informe, políticas de etiquetas y ajustes de ejecución en InvenTag con pequeñas plantillas YAML que puedes listar, copiar, adaptar y validar.
sidebar_position: 1
---

# Plantillas

**Para quién es:** cualquiera que ejecute InvenTag más de una vez y quiera el
mismo diseño de informe, las mismas reglas de etiquetas o los mismos ajustes de
análisis cada vez.

**Qué podrás hacer después de leerlo:** elegir una plantilla integrada, usarla
con `--template` y saber cuándo conviene crear la tuya.

## Qué es una plantilla {#what-a-template-is}

Una plantilla es un archivo YAML corto que le indica a InvenTag cómo hacer una
parte de una ejecución. Hay tres tipos:

| Tipo | Controla | Ejemplo integrado |
|---|---|---|
| `report` | Cómo se ven el libro de Excel y el documento de Word: título, colores, columnas, qué hojas y secciones aparecen | `standard-bom`, `executive-summary` |
| `tag-policy` | Qué etiquetas debe tener cada recurso y qué valores se permiten | `finops-cost-allocation`, `security-baseline` |
| `config` | Qué analizar y qué producir: cuentas, regiones, archivos de salida y qué informe y qué política de etiquetas usar | `single-account`, `org-multi-account`, `ci-pipeline` |

InvenTag incluye ocho [plantillas integradas](./catalogue.md). Puedes copiar
cualquiera de ellas en tu proyecto y [adaptarla](./adapt-a-template.md).

## Usar una plantilla {#use-a-template}

Añade `--template` a una ejecución normal. Puedes indicar un nombre o la ruta de
un archivo:

```bash
inventag --template executive-summary --create-word
inventag --template ./my-templates/acme-bom.yaml --create-excel
```

Repite `--template` para combinar una plantilla de cada tipo:

```bash
inventag --template standard-bom --template security-baseline --create-excel
```

Unas pocas reglas deciden qué prevalece cuando los ajustes se solapan:

1. **Las opciones que escribes prevalecen.** Si una plantilla de configuración
   dice `outputs: [excel]` y tú también escribes `--create-word`, obtienes los
   dos archivos.
2. **Una plantilla en la línea de comandos prevalece sobre una referencia
   dentro de otra plantilla.** `--template security-baseline` sustituye la
   política de etiquetas que nombra `finops-cost-report`.
3. **Sin una plantilla de informe, InvenTag usa `standard-bom`.**

Las ejecuciones sin `--template` usan el diseño de informe original.

## Qué añade una política de etiquetas a tus informes {#what-a-tag-policy-adds-to-your-reports}

Cuando hay una política de etiquetas activa, InvenTag revisa cada recurso dentro
del alcance y añade:

- una hoja **Tag Compliance** en el libro, con una fila por recurso, que indica
  qué falta o qué es incorrecto;
- una sección **Tag compliance** en el documento de Word;
- un archivo `tag_compliance_<timestamp>.json` que puedes usar en scripts o CI;
- un resumen de una línea en el terminal.

Salida de ejemplo de una ejecución sin conexión con `--template finops-cost-report`
(datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

Una plantilla de configuración puede establecer `fail_on_tag_violations: true`
para que InvenTag termine con el código 3 cuando algo incumpla la política. La
plantilla integrada `ci-pipeline` lo hace.

## Dónde busca InvenTag las plantillas {#where-inventag-looks-for-templates}

Cuando indicas un nombre, InvenTag revisa estas carpetas en orden y usa la
primera coincidencia:

1. Cada carpeta de la variable de entorno `INVENTAG_TEMPLATE_PATH` (separa las
   carpetas con `:` en Linux y macOS, y con `;` en Windows).
2. `.inventag/templates/` en la carpeta desde la que ejecutas InvenTag (tu
   proyecto).
3. `~/.config/inventag/templates/` (o `$XDG_CONFIG_HOME/inventag/templates/`).
4. Las plantillas integradas.

Así, un archivo llamado `.inventag/templates/standard-bom.yaml` sustituye la
plantilla integrada `standard-bom` en ese proyecto. Aun así, puede basarse en la
original con `extends: standard-bom`. Ejecuta `inventag templates list` para ver
qué se encuentra y desde dónde.

## Seguro por diseño {#safe-by-design}

Las plantillas son datos simples:

- InvenTag las lee con un cargador de YAML seguro. Se rechazan las etiquetas
  YAML que crean objetos de Python, como `!!python/object`.
- Las plantillas no pueden ejecutar código, evaluar expresiones ni descargar
  nada de internet.
- Las referencias a archivos dentro de una plantilla (`extends`, `tag_policy`,
  `report_template`, `logo`) deben ser rutas relativas que permanezcan dentro de
  la carpeta de la plantilla.
- Las plantillas de configuración no pueden contener claves de acceso. Usa
  `profile_name` o `role_arn`.
- Los valores de AWS que empiezan por `=` se escriben en Excel como texto, de
  modo que el valor de una etiqueta no puede convertirse en una fórmula de hoja
  de cálculo.

## Próximos pasos {#next-steps}

- [Plantillas integradas](./catalogue.md): qué produce cada una.
- [Adaptar una plantilla](./adapt-a-template.md): copiar, editar, validar,
  ejecutar.
- [Referencia de plantillas](./reference.md): todos los campos.
- [Ejemplos](../examples/index.md): recetas completas que usan plantillas.
