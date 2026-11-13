---
title: Ejemplos
description: Recetas de InvenTag para copiar y pegar en tareas habituales, cada una con el comando, la plantilla y la salida, desde una auditoría rápida hasta subidas a S3.
sidebar_position: 1
---

# Ejemplos

**Para quién es:** sabes qué tarea quieres resolver y buscas una receta que
copiar.

**Qué obtienes:** en cada ejemplo, el objetivo, la plantilla, el comando, la
salida que produce y qué hacer a continuación.

Toda la salida de estas páginas procede de una ejecución real de InvenTag contra AWS
simulado ([moto](https://github.com/getmoto/moto)), no de una cuenta real. Son
**datos de ejemplo**: las cuentas (como `123456789012`) y los recursos `acme-*`
son inventados, y tus nombres y cifras serán distintos. Las muestras las genera
`scripts/docs/generate_example_outputs.py`, así que coinciden con el código
actual.

| Ejemplo | Obtendrás |
|---|---|
| [Auditoría rápida de una cuenta](./quick-audit.md) | Un inventario en Excel y Word de la cuenta con la que has iniciado sesión |
| [Inventariar todas las cuentas de una organización](./accounts-setup.md) | Un informe de varias cuentas, mediante un rol de solo lectura en cada una |
| [Aplicar una política de etiquetas en CI](./tag-policy-in-ci.md) | Un paso de la canalización que falla cuando los recursos incumplen tus reglas de etiquetas |
| [Etiquetas de asignación de costes para FinOps](./finops-cost-allocation.md) | Un informe de qué recursos llevan las etiquetas que necesitan tus informes de costes |
| [Revisión de etiquetado de seguridad](./security-review.md) | Cobertura de propietario, entorno y clasificación de datos |
| [Informe ejecutivo de Word con tu marca](./branded-executive-report.md) | Un informe breve de Word en horizontal con tu logotipo y tus colores |
| [Tus propias columnas](./custom-columns.md) | Un libro con exactamente las columnas que elijas, en una sola hoja |
| [Subir informes a S3 de forma programada](./scheduled-s3-upload.md) | Informes cifrados en un bucket de S3 después de cada ejecución |

Todos los ejemplos suponen que has [instalado InvenTag](../getting-started/installation.md)
y que has iniciado sesión con una [identidad de solo lectura](../guides/read-only-access.md).
