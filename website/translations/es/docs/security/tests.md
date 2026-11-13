---
title: Pruebas
description: Cómo se prueba InvenTag - qué cubre el conjunto de pruebas, qué no puede demostrar, cómo ejecutarlo y en qué versiones de Python lo ejecuta CI.
sidebar_position: 2
---

# Pruebas

**Para quién es:** cualquiera que decida hasta qué punto confiar en InvenTag y
cualquiera que cambie el código.

**Qué sabrás después de leerlo:** qué cubren las pruebas, qué no cubren y cómo
ejecutarlas tú mismo.

## Qué se ejecuta y dónde {#what-runs-and-where}

El conjunto tiene 1.389 pruebas (1.398 con los nueve benchmarks). Todas usan
[moto](https://github.com/getmoto/moto), que imita AWS en memoria, así que las
pruebas se ejecutan sin conexión y no cuestan nada. Nueve benchmarks de
rendimiento quedan fuera de la ejecución normal y solo se inician cuando los
pides.

CI ejecuta el conjunto en Python 3.11, 3.12, 3.13, 3.14 y 3.15, además de
trabajos de lint, integración y seguridad básica, en cada push y pull request.

**Ninguna prueba se ejecuta contra una cuenta de AWS real.** Cuando un
resultado depende de cómo se comporta AWS real, [Estado de las funciones](../getting-started/status.md)
lo indica.

## Con qué se prueba cada función {#what-each-feature-is-tested-with}

Cada fila se comprueba sin conexión contra AWS simulado (moto), o contra
clientes de Google simulados en las filas de Google. La API Resource Groups
Tagging de moto es la referencia para los ARN y las etiquetas.

| Función | Pruebas |
|---|---|
| Recursos en una o varias cuentas, una cuenta fallida nombrada en el informe y en el resumen de la ejecución | `tests/integration/test_status_validation.py`, `tests/unit/test_cli_security.py` |
| Informes de Excel y Word, orden estable de hojas y filas, columnas de etiquetas | `tests/integration/test_status_validation.py`, `tests/unit/test_bom_converter.py` |
| Plantillas de informe, comprobaciones de política de etiquetas, código de salida 3 | `tests/integration/test_status_validation.py`, `tests/unit/templating/` |
| Filtros (`--account-regions`, `--account-services`, `--account-tags`) en todas las rutas | `tests/integration/test_status_validation.py`, `tests/unit/test_global_services.py` |
| ARN reales y asociación de etiquetas para cada servicio, sin duplicados | `tests/unit/test_arn_and_tags.py` |
| Servicios globales para `eu-west-1` solo, todas las regiones y una lista con `us-east-1` | `tests/unit/test_global_services.py` |
| Hojas de red y seguridad, `--risk-threshold` (código de salida 4) | `tests/integration/test_status_validation.py` |
| `--enable-cost-analysis` y su hoja | `tests/integration/test_status_validation.py` |
| `--per-account-reports`, `--accounts-prompt`, `--credential-timeout`, `--disable-account-logging` | `tests/integration/test_status_validation.py` |
| Advertencia de `--bom-config`, `--validate-config-only` sin llamadas a AWS, una advertencia por servicio denegado | `tests/integration/test_status_validation.py` |
| Informe de cambios entre ejecuciones, instantáneas | `tests/integration/test_status_validation.py`, `tests/unit/test_changelog_generator.py` |
| Protección de solo lectura, auditoría, `--validate-operations`, subida a S3, archivos privados | `tests/unit/test_cli_security.py`, `tests/unit/test_security_read_only_guard.py` |
| Ocultación de secretos, incluidos los de Google | `tests/unit/test_security_redaction.py`, `tests/unit/test_google_output.py` |
| Salida a Google Sheets y Docs (clientes de Google simulados) | `tests/unit/test_google_output.py` |

## Ejecuta las pruebas tú mismo {#run-the-tests-yourself}

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Ejecuta los benchmarks con `pytest -m performance`. Para configurar el entorno
de desarrollo completo: [Contribuir a InvenTag](../development/CONTRIBUTING.md).

## Qué más se comprueba {#what-else-is-checked}

- **El sitio de documentación** se compila en CI. La compilación falla ante un
  enlace roto y se ejecuta una comprobación de accesibilidad sobre las páginas
  compiladas.
- **Las dependencias** se analizan en busca de vulnerabilidades conocidas.
  Consulta [Seguridad](./index.md#how-dependencies-are-checked) y la
  [lista de materiales de software](./sbom.md).
