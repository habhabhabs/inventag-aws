---
title: Lista de materiales de software
description: Qué incluye la lista de materiales de software (SBOM) de InvenTag, cómo se genera y cómo comprobar las dependencias que instalas.
sidebar_position: 3
---

# Lista de materiales de software

**Para quién es:** revisores de seguridad y de compras que necesitan saber de
qué está hecho InvenTag.

**Qué sabrás después de leerlo:** qué archivos SBOM existen, cómo se crean,
cómo comprobar un archivo de la versión y cómo generar un SBOM para tu propia
instalación.

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

## Qué incluye una versión {#what-a-release-carries}

Cada versión tiene compilaciones empaquetadas: archivos independientes del
ejecutable y paquetes `.deb` y `.rpm`. El flujo de trabajo de la versión crea para
ellas los archivos siguientes. Consulta
[Instalar InvenTag](../getting-started/installation.md#choose-how-to-install)
para ver las compilaciones.

| Archivo | Qué contiene |
|---|---|
| `inventag-<version>-<os>-<cpu>.tar.gz`, `inventag_<version>_<cpu>.deb`, `inventag-<version>-1.<cpu>.rpm` | Las compilaciones empaquetadas |
| Un archivo `.cdx.json` por cada uno de esos archivos, por ejemplo `inventag_<version>_amd64.deb.cdx.json` | El SBOM de ese archivo: sus paquetes de Python y bibliotecas de C, con nombre, versión y licencia |
| `inventag-<version>-<os>-<cpu>.THIRD-PARTY-LICENSES.txt` | El archivo de avisos: el texto de licencia de cada componente incluido |
| `inventag-<version>-<os>-<cpu>.components.json` | La lista de componentes con la que se crean el SBOM y el archivo de avisos |
| `inventag-<version>-linux-<cpu>.build-image.txt` | El registro del sistema de compilación de Linux: su versión y las versiones de las bibliotecas que incluye la compilación |
| `SHA256SUMS` | La suma de comprobación SHA-256 de cada uno de los demás archivos de la versión |

Los archivos SBOM usan el formato CycloneDX, versión 1.5, en JSON. El flujo de
trabajo los escribe a partir de la compilación, así que listan lo que hay en el
archivo y no lo que permite un `requirements.txt`.

No verificado contra el esquema de CycloneDX: que los archivos SBOM pasen un validador.

No verificado contra GitHub: que la versión incluya estos archivos. Las ejecuciones de prueba hasta ahora no adjuntan nada a una versión, y la primera ejecución de versión con estos archivos aún no se ha hecho.

### Comprobar un archivo de la versión {#check-a-release-file}

El flujo de trabajo de la versión firma los archivos sin una clave nuestra. Entrega
`SHA256SUMS` al paso `actions/attest` de GitHub. Ese paso escribe una atestación
de compilación en nombre del flujo de trabajo. Para comprobar un archivo con la
CLI de GitHub:

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb \
  --repo habhabhabs/inventag-aws \
  --signer-workflow habhabhabs/inventag-aws/.github/workflows/package.yml
```

Para comprobar una suma de comprobación, consulta
[Comprobar la descarga](../getting-started/installation.md#check-the-download).

`--repo` nombra el repositorio. `--signer-workflow` hace que la comprobación falle
si otro archivo de flujo de trabajo creó la atestación.

No verificado contra GitHub: `gh attestation verify` con estas opciones sobre un
archivo de una versión. Las opciones se leen de `gh attestation verify --help`. Las ejecuciones de prueba no crean ninguna atestación. La primera atestación real la crea la primera ejecución de versión, y esa ejecución aún no se ha hecho.

### Licencias en las compilaciones empaquetadas {#licenses-in-the-packaged-builds}

InvenTag usa la licencia MIT. Las compilaciones empaquetadas incluyen además
archivos de otros proyectos. El archivo de avisos los lista con el texto de sus
licencias.

Los archivos del ejecutable, el `.deb` y el `.rpm` incluyen GNU libiconv, una
biblioteca bajo la Licencia Pública General Reducida de GNU (LGPL) versión 2.1. La
fórmula de Homebrew (aún no publicada) instala el mismo archivo, así que también
la incluye. El código de libiconv está dentro de los módulos de extensión de lxml.
InvenTag necesita lxml para escribir archivos de Word. El proyecto lxml crea esos
módulos y enlaza libiconv en ellos. En el archivo, el `.deb` y el `.rpm`, InvenTag
incluye los archivos de lxml sin cambios: la compilación compara cada archivo byte a byte con el archivo del wheel del lock.

- Una instalación con pip, pipx o uv no incluye libiconv en ningún archivo de
  InvenTag. Tu instalador descarga el wheel propio de lxml desde el Python Package
  Index.
- El archivo de avisos es `THIRD-PARTY-LICENSES.txt`: `inventag/THIRD-PARTY-LICENSES.txt`
  en el archivo independiente, y `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` y
  `/opt/inventag/THIRD-PARTY-LICENSES.txt` en el `.deb` y el `.rpm`. La versión
  también lo lista como un archivo propio para cada sistema. Contiene el texto
  completo de la LGPL 2.1.
- El código fuente de la biblioteca está en las direcciones que nombra el archivo
  de avisos. En esta versión: libiconv 1.18 en <https://www.gnu.org/software/libiconv/>
  y <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>, y lxml 6.1.3 en
  <https://github.com/lxml/lxml>. El flujo de trabajo de la versión solicita las dos
  direcciones de libiconv antes de firmar los archivos, y se detiene si una no
  responde.
- InvenTag no hace ninguna oferta escrita de enviar el código fuente. Si una
  dirección no funciona, abre una incidencia en
  <https://github.com/habhabhabs/inventag-aws/issues>.
- Los módulos de lxml son archivos separados en el directorio de instalación.
  Puedes reemplazarlos por tu propia compilación de lxml de la misma versión. La
  carpeta es `inventag/_internal/lxml/` en el archivo independiente y
  `/opt/inventag/_internal/lxml/` para el `.deb` y el `.rpm`. En macOS, vuelve a
  firmar un módulo después de reemplazarlo: `codesign -s - --force <file>`.

No verificado contra tu propia compilación de lxml: que un módulo que compiles funcione en lugar del incluido.

No verificado contra una instalación con Homebrew: que Homebrew deje sin cambios los archivos de lxml.

No verificado contra los servidores de GNU: que las dos direcciones de libiconv sigan respondiendo. El flujo de trabajo obtuvo ambas el día de su ejecución de prueba.

Esta sección no es asesoramiento legal.

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
