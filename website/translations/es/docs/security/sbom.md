---
title: Lista de materiales de software
description: Qué incluye la lista de materiales de software (SBOM) de InvenTag, cómo se genera y cómo comprobar las dependencias que instalas.
sidebar_position: 3
---

# Lista de materiales de software

**Para quién es:** revisores de seguridad y de compras que necesitan saber de
qué está hecho InvenTag.

**Qué sabrás después de leerlo:** qué archivos SBOM existen, cómo se crean y
cómo generar uno para tu propia instalación.

## Qué genera la compilación de la documentación {#what-the-documentation-build-generates}

Cada vez que se despliega el sitio de documentación, la compilación genera
archivos SBOM del repositorio y de sus dependencias y los publica con el sitio:

| Archivos | Qué listan | Formato |
|---|---|---|
| SBOM del repositorio | Todo lo que Syft encuentra en el repositorio | Syft JSON, CycloneDX JSON y SPDX JSON |
| Python, a partir de `requirements.txt` | Las versiones mínimas que declara InvenTag | CycloneDX JSON y XML |
| Python, a partir de una instalación nueva | Las versiones que realmente se instalaron | CycloneDX JSON y una lista de `pip freeze` |
| Sitio web de la documentación | Los paquetes de Node.js usados para compilar este sitio | CycloneDX JSON |

No verificado contra un runner de GitHub Actions: los archivos SBOM que publica la compilación de la documentación; esta página se lee del archivo de flujo de trabajo.

La misma compilación añade a esta sección una página resumen, **Software Bill
of Materials (SBOM)**, por lo que aparece en el sitio publicado pero no en una
compilación local.

Las dependencias de Python se declaran con versiones mínimas, no fijadas
exactamente, así que el archivo de versiones instaladas es el que muestra lo
que obtiene una instalación real el día de la compilación.

## Genera un SBOM para tu propia instalación {#produce-an-sbom-for-your-own-installation}

```bash title="Terminal"
pip install inventag-aws cyclonedx-bom
cyclonedx-py environment --output-format json --output-file inventag-sbom.json
```

No verificado contra la versión de cyclonedx-bom que instales: las opciones de `cyclonedx-py environment`.

Ejecútalo en el entorno virtual donde instalaste InvenTag, para que el archivo
liste exactamente lo que ejecutas.

## Vigila las vulnerabilidades {#keep-an-eye-on-vulnerabilities}

Un flujo de trabajo programado analiza las dependencias en busca de
vulnerabilidades conocidas. Lee
[Cómo se comprueban las dependencias](./index.md#how-dependencies-are-checked)
para saber qué se ejecuta y qué hace fallar la compilación, y
[Después de un incidente en la cadena de suministro](./index.md#after-a-supply-chain-incident)
si crees que algo se vio comprometido.
