---
title: Cómo encaja el código
description: Un mapa del paquete de Python de InvenTag (CLI, varias cuentas, descubrimiento, procesamiento, plantillas, informes y estado) para quienes contribuyen.
sidebar_position: 2
slug: /architecture/core-module-integration
---

# Cómo encaja el código

**Para quién es:** quienes contribuyen y quieren orientarse en el código.

**Qué sabrás después de leerlo:** qué módulo hace qué durante una ejecución y
por dónde empezar para un cambio.

## El recorrido de una ejecución {#the-path-of-one-run}

```text
inventag_cli.py
  -> inventag/cli/main.py              parse flags, validate, set up logging
       -> templating/runner.py         only with --template: load templates,
                                       apply a config template to the flags
  -> core/cloud_bom_generator.py       CloudBOMGenerator
       1. sessions per account         profiles, keys or sts:AssumeRole
       2. discovery per account        discovery/inventory.py and friends
       3. consolidation                one list of resource dictionaries
       4. documents                    reporting/bom_processor.py, then
                                       reporting/converter.py (default) or
                                       templating/render_excel.py and
                                       render_word.py (with --template)
       5. state                        state/ snapshots and changelog
```

## Paquetes {#packages}

| Paquete | Responsabilidad | Empieza por |
|---|---|---|
| `inventag/cli/` | Opciones, validación de la configuración, registro | `main.py`, `config_validator.py` |
| `inventag/core/` | Orquestación de varias cuentas y credenciales | `cloud_bom_generator.py` |
| `inventag/discovery/` | Búsqueda de recursos: llamadas a la API por servicio, la Tagging API, Cost Explorer | `inventory.py`, `comprehensive_discovery.py` |
| `inventag/reporting/` | Normalización de recursos y escritura de los archivos de Excel y Word predeterminados | `bom_processor.py`, `converter.py` |
| `inventag/templating/` | Carga de plantillas, validación, herencia, comprobaciones de políticas de etiquetas y salida de Excel y Word dirigida por plantillas | `schema.py`, `registry.py`, `runner.py` |
| `inventag/state/` | Instantáneas, diferencias y registros de cambios | `state_manager.py` |
| `inventag/compliance/` | Clases de biblioteca para comprobaciones de etiquetas y seguridad. La ruta de la política de etiquetas usa `checker.py`; la CLI no usa las demás clases | `checker.py` |
| `inventag/security/` | La protección de solo lectura, la lista de políticas de IAM, la redacción de registros, los archivos de salida seguros | `read_only_guard.py`, `iam_policy.py` |

## Módulos compartidos {#shared-modules}

Cada uno de estos módulos es el único lugar que decide su tema. Cambia el
comportamiento ahí, no en una copia.

| Módulo | Decide |
|---|---|
| `inventag/exit_codes.py` | Los códigos de salida (0 a 6) |
| `inventag/security/secret_values.py` | Qué valores de campo son secretos y pasan a ser `***REDACTED***` |
| `inventag/discovery/regions.py` | Qué regiones analiza una ejecución y la región principal de cada partición |
| `inventag/discovery/aws_clients.py` | Los ajustes de reintento de los clientes de AWS |
| `inventag/discovery/coverage.py` | Cómo terminó cada llamada de listado, por servicio y región |
| `inventag/reporting/settings_loader.py` | Cómo se leen y comprueban los archivos de ajustes |
| `inventag/reporting/safe_save.py` | Escribir un informe en un archivo temporal y moverlo a su sitio |
| `inventag/state/partial_results.py` | Guardar y reutilizar las cuentas terminadas para `--resume` |

## El diccionario de recurso {#the-resource-dictionary}

Todo lo que ocurre entre el descubrimiento y la salida circula en diccionarios
simples, uno por recurso. Los campos en los que se apoyan las plantillas y los
informes están enumerados en la
[Referencia de plantillas](../templates/reference.md#resource-fields-you-can-use-as-columns).
Mantenlos estables: renombrar uno rompe las plantillas de la gente.

## Cómo se integran las plantillas {#how-templates-hook-in}

`templating/runner.py` define `TemplatedCloudBOMGenerator`, una subclase de
`CloudBOMGenerator` que sustituye solo el paso de los documentos. El resto de
la ejecución, incluidos el descubrimiento, las credenciales y el estado, no
cambia. Sin `--template` se usan las clases originales.

## Carencias conocidas que merece la pena corregir {#known-gaps-worth-fixing}

Los límites que ve el usuario están en el [Estado de las funciones](../getting-started/status.md).
Estas son las carencias del código. Cada una es una buena primera contribución:

- `discovery/arn_utils.py` es el único lugar que construye y compara ARN
  (`build_arn`, `normalize_arn`, `ResourceArnIndex`). `inventory.py` y
  `comprehensive_discovery.py` lo usan. Las etiquetas de la API Resource Groups
  Tagging se emparejan por ARN normalizado y después por servicio, región e ID.
- Los servicios globales (IAM, lista de S3, CloudFront, Route 53, WAF para
  CloudFront, certificados de ACM de CloudFront) se ejecutan una vez por cuenta
  desde la región principal de la partición y llevan la región `global`.
- `discovery/inventory.py` todavía tiene una lista fija de catorce regiones, que
  solo se usa cuando quien llama a la biblioteca no indica regiones.
- `--enable-cost-analysis` llama a Cost Explorer incluso con
  `--no-billing-validation`.
- Una cuenta fallida no cambia el código de salida, salvo que pases
  `--fail-on-account-error` (salida 5).
- El análisis de red y de seguridad se ejecuta dos veces en una ejecución (en el
  procesador de la BOM y en el conversor), así que sus llamadas a AWS se hacen dos veces.
- La CLI no llama a estos módulos: `reporting/template_framework.py`,
  `branding_system.py`, `word_builder.py`, `excel_builder.py`,
  `document_generator.py` y `configuration_manager.py`, además de
  `discovery/enhanced_readonly_discovery.py`. `reporting/template_framework.py`
  y `reporting/document_generator.py` se importan cuando arranca la CLI.

Las notas de diseño antiguas se eliminaron del repositorio. Usa las páginas de este sitio.
