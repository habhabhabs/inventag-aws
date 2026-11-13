---
title: Cómo encaja el código
description: Un mapa del paquete de Python de InvenTag (CLI, orquestación de varias cuentas, descubrimiento, procesamiento, plantillas, informes y estado) para quienes contribuyen.
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
| `inventag/compliance/` | Clases de biblioteca para comprobaciones de etiquetas y seguridad; hoy la CLI casi no las usa | `checker.py` |
| `inventag/security/` | La protección de solo lectura, la lista de políticas de IAM, la redacción de registros, los archivos de salida seguros | `read_only_guard.py`, `iam_policy.py` |

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
cambia. Sin `--template` se usan las clases originales y la salida es
exactamente la de antes.

## Carencias conocidas que merece la pena corregir {#known-gaps-worth-fixing}

Están registradas en el [Estado de las funciones](../getting-started/status.md)
y en la lista "Open work" de `CHANGELOG.md`. Cada una es una buena primera
contribución:

- `discovery/arn_utils.py` es el único lugar que construye y compara ARN
  (`build_arn`, `normalize_arn`, `ResourceArnIndex`). `inventory.py` y
  `comprehensive_discovery.py` lo usan los dos. Las etiquetas de la Resource
  Groups Tagging API se asocian por ARN normalizado y, si no, por servicio,
  región e ID.
- Los servicios globales (IAM, la lista de S3, CloudFront, Route 53 y los
  certificados de ACM de CloudFront) se ejecutan una vez por cuenta desde
  `us-east-1` y llevan la región `global`.
- La búsqueda de regiones de `cloud_bom_generator.py` recurre a cuatro regiones
  cuando `DescribeRegions` falla. `discovery/inventory.py` tiene otra lista de
  respaldo, de catorce.
- Una `description` personalizada en un archivo de descripciones de servicios se
  ignora para los servicios que tienen una plantilla integrada (S3, EC2, RDS,
  Lambda, VPC).
- `--enable-cost-analysis` llama a Cost Explorer incluso con
  `--no-billing-validation`.
- Una cuenta fallida no cambia el código de salida.
- Estos módulos no están en la ruta de la CLI: `reporting/template_framework.py`,
  `branding_system.py`, `word_builder.py`, `excel_builder.py`,
  `document_generator.py` y `configuration_manager.py`.

Las notas de diseño antiguas se eliminaron del repositorio. Usa las páginas de este sitio.
