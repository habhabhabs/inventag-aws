---
title: Instalar InvenTag
description: Elige cómo instalar InvenTag (pipx, un archivo independiente, un paquete .deb o .rpm, Homebrew o pip), conecta tus credenciales de AWS y comprueba que todo funciona.
sidebar_position: 2
---

# Instalar InvenTag

**Para quién es:** cualquiera que vaya a configurar InvenTag en un portátil, un servidor o un
ejecutor de CI.

**Qué podrás hacer después de leerlo:** elegir un método de instalación, instalar
InvenTag, actualizarlo y quitarlo, y confirmar que InvenTag llega a tu cuenta de AWS.

## Qué necesitas {#what-you-need}

- **Python 3.11 o posterior**, para los métodos pipx, pip y código fuente. Python 3.10
  dejó de recibir correcciones de seguridad en octubre de 2026. Consulta el
  [estado de las versiones de Python](https://devguide.python.org/versions/).
  Comprueba tu versión con `python3 --version`. El archivo independiente, el
  `.deb` y el `.rpm` traen su propio Python. No necesitan Python en tu equipo.
- **Credenciales de AWS** de una identidad de solo lectura. La
  [interfaz de línea de comandos de AWS (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  es opcional, pero es la forma más fácil de configurarlas.

## Elegir cómo instalar {#choose-how-to-install}

| Método | Úsalo cuando | Qué necesita tu equipo | Sistemas |
|---|---|---|---|
| [pipx](#install-with-pipx-recommended) (primera opción) | Tienes Python 3.11 o posterior. Quieres un comando para instalar y otro para actualizar. | Python 3.11 o posterior y pipx | Cualquier sistema con Python |
| [Archivo independiente](#install-the-standalone-archive) (`.tar.gz`) | El equipo no tiene Python, o quieres una copia que no necesite gestor de paquetes. | Nada | Linux x86_64 y arm64 (glibc 2.34 o posterior). macOS arm64 (Apple silicon). |
| [Paquete `.deb`](#install-the-deb-package) | Debian, Ubuntu y sistemas que usan `dpkg`. | Nada | Linux x86_64 y arm64 (glibc 2.34 o posterior) |
| [Paquete `.rpm`](#install-the-rpm-package) | Fedora, la familia RHEL y Amazon Linux. | Nada | Linux x86_64 y arm64 (glibc 2.34 o posterior) |
| [Homebrew](#install-with-homebrew) | macOS o Linux con Homebrew. Aún no está publicado. | Homebrew | Consulta la sección |
| [pip en un entorno virtual](#install-with-pip-in-a-virtual-environment) | Quieres InvenTag dentro de un entorno de proyecto. | Python 3.11 o posterior | Cualquier sistema con Python |
| [Desde el código fuente](#install-from-source) | Quieres el código más reciente sin publicar, o modificas InvenTag. | Python 3.11 o posterior y Git | Cualquier sistema con Python |

### Sistemas que admite cada compilación empaquetada {#systems-that-each-packaged-build-supports}

- El ejecutable, el `.deb` y el `.rpm` para Linux necesitan glibc 2.34 o posterior.
  Los sistemas Linux de la tabla siguiente la cumplen.
  En un sistema más antiguo, por ejemplo RHEL, AlmaLinux y Rocky Linux 8,
  Debian 11, Ubuntu 20.04 o Amazon Linux 2, usa pipx si el sistema tiene
  Python 3.11 o posterior.
- No hay ejecutable para los Mac con Intel: una biblioteca que InvenTag necesita
  (cryptography, desde la versión 50) no publica una compilación ya hecha para ellos.
- El ejecutable de macOS es solo para Apple silicon (arm64). El registro de
  compilación indica que sus archivos necesitan macOS 11.0 o posterior.
- Alpine y otros sistemas que usan musl no son compatibles con el ejecutable.
  Usa pipx.
- Windows no tiene compilación empaquetada.

No verificado contra un Mac con Intel: `pipx install inventag-aws`, que tiene que compilar esa biblioteca y necesita una cadena de herramientas de Rust.

No verificado contra sistemas con una glibc anterior a 2.34: el ejecutable, el `.deb` y el `.rpm`.

No verificado contra Alpine ni otros sistemas musl: el ejecutable; usa pipx.

No verificado contra Windows: ningún método de instalación.

No verificado contra un Mac con macOS 11.0: el ejecutable. El número sale del registro de compilación, no de una ejecución en esa versión.

### Qué se probó {#what-was-tested}

El flujo de trabajo de la versión compila cada formato y luego lo instala en un
sistema limpio. En los sistemas Linux x86_64 y en macOS ejecuta
`inventag --version` e `inventag selftest`, comprueba la página de manual y los
archivos de autocompletado, analiza un AWS simulado, quita el paquete y comprueba
que no queda ningún archivo del paquete. Estos sistemas lo superaron:

| Sistema | Formato | CPU |
|---|---|---|
| Ubuntu 22.04 | `.deb` | x86_64 |
| Ubuntu 24.04 | `.deb` | x86_64 |
| Debian 12 | `.deb` y archivo independiente | x86_64 |
| Debian 12 | `.deb` (instalar, versión, selftest, quitar) | arm64 |
| Fedora (la versión actual el día de la prueba) | `.rpm` | x86_64 |
| Rocky Linux 9 | `.rpm` y archivo independiente | x86_64 |
| Rocky Linux 9 | `.rpm` (instalar, versión, selftest, quitar) | arm64 |
| AlmaLinux 9 (el sistema de compilación, glibc 2.34) | `.rpm` | x86_64 |
| Amazon Linux 2023 | `.rpm` | x86_64 |
| macOS 15 en un runner de GitHub | archivo independiente | arm64 |
| Ubuntu 24.04 | pipx, desde el wheel creado a partir de la etiqueta (instalar, versión, selftest, quitar) | x86_64 |

No verificado contra AWS real: un análisis desde una compilación empaquetada; la prueba analiza un AWS simulado.

No verificado contra un sistema Linux arm64 limpio: el archivo independiente. La compilación ejecutó `inventag selftest` sobre él y ninguna otra prueba lo descomprimió.

No verificado contra GitHub: que la versión incluya los archivos de esta página. Las ejecuciones de prueba hasta ahora no adjuntan nada a una versión, y la primera ejecución de versión con estos archivos aún no se ha hecho.

## Instalar con pipx (recomendado) {#install-with-pipx-recommended}

[pipx](https://pipx.pypa.io/) instala InvenTag en su propio entorno oculto y pone
el comando `inventag` en tu PATH. Nunca tienes que activar nada. El paquete en el
Python Package Index es [`inventag-aws`](https://pypi.org/project/inventag-aws/).
Instala pipx primero. Usa la forma que sugiera tu sistema. Consulta la
documentación de pipx.

```bash title="Terminal"
pipx install inventag-aws
inventag --version
inventag selftest
```

`inventag selftest` comprueba, sin conexión, que esta copia de InvenTag funciona.
No hace ninguna llamada a AWS, no abre ninguna conexión de red y no necesita
credenciales. El código de salida 0 significa que todas las comprobaciones
pasaron. El código de salida 1 significa que una comprobación falló.

`uv tool install inventag-aws` da el mismo resultado si usas
[uv](https://docs.astral.sh/uv/).

- **Actualizar:** `pipx upgrade inventag-aws`. Para instalar una versión
  concreta, fíjala: `pipx install inventag-aws==%INVENTAG_VERSION%`.
- **Desinstalar:** `pipx uninstall inventag-aws`. Esto quita el programa. No
  quita tus informes e instantáneas de `bom_output/`.
- **Autocompletado:** `inventag completion bash`, `inventag completion zsh` e
  `inventag completion fish` imprimen un script de autocompletado. Consulta
  [Autocompletado del intérprete](#shell-completion).
- **Página de manual:** este método no instala ninguna. Usa `inventag --help`.

No verificado contra pipx: los comandos de actualización y de fijación de versión.

## Instalar el archivo independiente {#install-the-standalone-archive}

El archivo contiene un solo directorio, `inventag`. Contiene el programa, su
propio Python y sus bibliotecas. La versión tiene un archivo para cada sistema:

- `inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz`
- `inventag-%INVENTAG_VERSION%-linux-arm64.tar.gz`
- `inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz` (macOS, Apple silicon)

Ejecuta `uname -m` para ver tu CPU. Linux muestra `x86_64` o `aarch64`. Usa el
archivo arm64 para `aarch64`. Descarga el archivo y `SHA256SUMS` desde la
[página de versiones](https://github.com/habhabhabs/inventag-aws/releases), o con
la CLI de GitHub:

```bash title="Terminal"
gh release download v%INVENTAG_VERSION% --repo habhabhabs/inventag-aws \
  --pattern 'inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz' --pattern SHA256SUMS
```

[Comprueba la descarga](#check-the-download) antes de descomprimirla. Después, en
Linux:

```bash title="Terminal"
sudo tar -xzf inventag-%INVENTAG_VERSION%-linux-x86_64.tar.gz -C /opt
sudo ln -s /opt/inventag/inventag /usr/local/bin/inventag
inventag --version
inventag selftest
```

En macOS, descomprime el archivo en una carpeta que elijas y ejecuta el programa
con su ruta. La prueba lo hizo así. No creó un enlace en el PATH.

```bash title="Terminal"
mkdir -p "$HOME/inventag-install"
tar -xzf inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz -C "$HOME/inventag-install"
"$HOME/inventag-install/inventag/inventag" --version
```

Apple no ha notarizado el ejecutable de macOS. macOS puede bloquear un archivo
que descargó un navegador.

No verificado contra macOS fuera de un runner de GitHub: la instalación con Homebrew y el comportamiento de Gatekeeper.

- **Actualizar:** quita el directorio antiguo y descomprime el archivo nuevo en el
  mismo lugar.
- **Desinstalar (Linux):** `sudo rm -rf /opt/inventag` y
  `sudo rm /usr/local/bin/inventag`. En macOS, borra la carpeta que
  descomprimiste.
- **Autocompletado:** el directorio contiene los scripts en `share/completions/`:
  `inventag.bash`, `_inventag` (zsh) e `inventag.fish`. Consulta
  [Autocompletado del intérprete](#shell-completion).
- **Página de manual:** el directorio contiene la página en
  `share/man/man1/inventag.1`. Léela con
  `man /opt/inventag/share/man/man1/inventag.1`.

No verificado contra las herramientas man de cada sistema: que `man` muestre la página. La prueba leyó el archivo de la página y comprobó su cabecera y su línea de nombre.

No verificado contra un sistema que tenga un InvenTag anterior en el mismo lugar: los pasos de actualización.

## Instalar el paquete .deb {#install-the-deb-package}

Usa el `.deb` en Debian, Ubuntu y sistemas que usan `dpkg`. El nombre del archivo es
`inventag_%INVENTAG_VERSION%_amd64.deb` para x86_64 y
`inventag_%INVENTAG_VERSION%_arm64.deb` para arm64. Descarga el archivo y
[compruébalo](#check-the-download). Después ejecuta:

```bash title="Terminal"
sudo dpkg -i inventag_%INVENTAG_VERSION%_amd64.deb
inventag --version
inventag selftest
```

El paquete pone el programa en `/opt/inventag/` y un enlace en
`/usr/bin/inventag`. También instala la página de manual, los archivos de
autocompletado y los archivos de licencia en `/usr/share/doc/inventag/`. El
paquete no tiene script de instalación.

- **Actualizar:** instala el `.deb` más nuevo con `sudo dpkg -i`.
- **Desinstalar:** `sudo dpkg -r inventag`. La prueba comprobó que no queda
  ningún archivo del paquete.
- **Autocompletado:** el paquete instala los archivos para bash, zsh y fish.
  Consulta [Autocompletado del intérprete](#shell-completion).
- **Página de manual:** `man inventag`. El archivo es
  `/usr/share/man/man1/inventag.1.gz`.

No verificado contra un sistema que tenga un paquete InvenTag anterior: la actualización.

No verificado contra las herramientas man de cada sistema: que `man inventag` muestre la página. La prueba leyó el archivo de la página y comprobó su cabecera y su línea de nombre.

## Instalar el paquete .rpm {#install-the-rpm-package}

Usa el `.rpm` en Fedora, la familia RHEL y Amazon Linux. El nombre del archivo es
`inventag-%INVENTAG_VERSION%-1.x86_64.rpm` para x86_64 y
`inventag-%INVENTAG_VERSION%-1.aarch64.rpm` para arm64. Descarga el archivo y
[compruébalo](#check-the-download). Después ejecuta:

```bash title="Terminal"
sudo dnf install ./inventag-%INVENTAG_VERSION%-1.x86_64.rpm
inventag --version
inventag selftest
```

El paquete pone el programa en `/opt/inventag/` y un enlace en
`/usr/bin/inventag`. También instala la página de manual, los archivos de
autocompletado y los archivos de licencia en `/usr/share/doc/inventag/`.

- **Actualizar:** instala el `.rpm` más nuevo con `sudo dnf install`.
- **Desinstalar:** `sudo dnf remove inventag`. La prueba comprobó que no queda
  ningún archivo del paquete.
- **Autocompletado:** el paquete instala los archivos para bash, zsh y fish.
  Consulta [Autocompletado del intérprete](#shell-completion).
- **Página de manual:** `man inventag`. El archivo es
  `/usr/share/man/man1/inventag.1.gz`.

No verificado contra un sistema que tenga un paquete InvenTag anterior: la actualización.

No verificado contra las herramientas man de cada sistema: que `man inventag` muestre la página. La prueba leyó el archivo de la página y comprobó su cabecera y su línea de nombre.

## Instalar con Homebrew {#install-with-homebrew}

El propietario del proyecto crea el tap de Homebrew. El tap aún no está
publicado, así que el comando siguiente no funciona hoy:

```bash title="Terminal"
brew install habhabhabs/inventag/inventag
```

El plan es una fórmula que instale el ejecutable desde el archivo de la versión.
Es para macOS arm64 y las dos CPU de Linux. No es para los Mac con Intel.
La fórmula aún no está escrita. Esta página no indica qué archivos de
autocompletado ni qué página de manual instala. Hasta entonces, usa
[Autocompletado del intérprete](#shell-completion) e `inventag --help`.

- **Actualizar:** `brew upgrade inventag`.
- **Desinstalar:** `brew uninstall inventag`.

No verificado contra macOS fuera de un runner de GitHub: la instalación con Homebrew y el comportamiento de Gatekeeper.

## Instalar con pip en un entorno virtual {#install-with-pip-in-a-virtual-environment}

InvenTag no necesita un entorno virtual. Un entorno virtual mantiene sus
dependencias (boto3, openpyxl y otras) separadas de tus demás herramientas de
Python. Muchos sistemas actuales (Debian, Ubuntu, Python de Homebrew) rechazan
`pip install` en el Python del sistema con el error «externally-managed-environment».
Las dos opciones que funcionan en esos sistemas son un entorno virtual o
[pipx](#install-with-pipx-recommended).

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

No verificado contra Debian, Ubuntu ni Homebrew: el error externally-managed-environment y las dos formas de evitarlo.

Con esto tienes el comando `inventag` que usa esta documentación. Las plantillas
de informe vienen incluidas en el paquete.

- **Actualizar:** `pip install --upgrade inventag-aws`. Para instalar una versión
  concreta, fíjala: `pip install inventag-aws==%INVENTAG_VERSION%`.
- **Desinstalar:** `pip uninstall inventag-aws`.
- **Autocompletado y página de manual:** igual que con [pipx](#install-with-pipx-recommended).

No verificado contra pip: los comandos de actualización, de fijación de versión y de desinstalación.

## Instalar desde el código fuente {#install-from-source}

Úsalo si quieres el código más reciente sin publicar o piensas modificar InvenTag.

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
inventag --help
```

`pip install -e .` instala las dependencias de `requirements.txt` y un comando
`inventag` que ejecuta tu copia del código fuente, así que tus cambios en el código
se aplican sin reinstalar. También puedes ejecutar `python inventag_cli.py --help`
directamente después de `pip install -r requirements.txt`.

La raíz del repositorio también contiene dos scripts de lanzamiento, `inventag.sh` e
`inventag.bat`. Usa en su lugar el comando `inventag`. Los scripts de lanzamiento no forman parte del
paquete instalado y ninguna prueba los ejecuta.

Para usar desde el código fuente una versión fija en lugar del código más reciente, descarga su etiqueta, por
ejemplo `git checkout v%INVENTAG_VERSION%`. La
[página de versiones](https://github.com/habhabhabs/inventag-aws/releases) lista
todas las versiones.

## Autocompletado del intérprete {#shell-completion}

`inventag completion bash`, `inventag completion zsh` e `inventag completion fish`
imprimen un script de autocompletado. El comando solo lee sus propias opciones.
No hace ninguna llamada a AWS y no abre ninguna conexión de red. Un nombre de
intérprete desconocido termina con el código de salida 2.

```bash title="Terminal"
source <(inventag completion bash)                                    # bash, this session
inventag completion zsh > "${fpath[1]}/_inventag"                     # zsh
inventag completion fish > ~/.config/fish/completions/inventag.fish  # fish
```

El `.deb` y el `.rpm` instalan los tres scripts por ti:

| Intérprete | `.deb` | `.rpm` |
|---|---|---|
| bash | `/usr/share/bash-completion/completions/inventag` | `/usr/share/bash-completion/completions/inventag` |
| zsh | `/usr/share/zsh/vendor-completions/_inventag` | `/usr/share/zsh/site-functions/_inventag` |
| fish | `/usr/share/fish/vendor_completions.d/inventag.fish` | `/usr/share/fish/vendor_completions.d/inventag.fish` |

No verificado contra cada configuración de intérprete: que un intérprete nuevo cargue estos archivos por sí solo. La prueba cargó cada archivo a mano en bash, zsh y fish. No cargó el archivo de fish en Rocky Linux 9, AlmaLinux 9 ni Amazon Linux 2023.

## Comprobar la descarga {#check-the-download}

Cada versión lista todos sus archivos en `SHA256SUMS`. Una suma de comprobación
muestra que el archivo está completo. No muestra quién lo creó. Una atestación de
compilación sí.

En Linux, pon el archivo y `SHA256SUMS` en una carpeta y ejecuta:

```bash title="Terminal"
sha256sum --check --ignore-missing SHA256SUMS
```

En macOS, imprime la suma de comprobación de tu archivo y compárala a simple vista
con la línea de `SHA256SUMS`:

```bash title="Terminal"
shasum -a 256 inventag-%INVENTAG_VERSION%-darwin-arm64.tar.gz
grep darwin-arm64.tar.gz SHA256SUMS
```

El flujo de trabajo de la versión firma los archivos sin una clave nuestra. Entrega
`SHA256SUMS` al paso `actions/attest` de GitHub. Ese paso escribe una atestación de
compilación en nombre del flujo de trabajo. Para comprobar un archivo, usa la CLI
de GitHub:

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb --repo habhabhabs/inventag-aws
```

No verificado contra GitHub: `gh attestation verify` sobre un archivo de una versión. Las ejecuciones de prueba no crean ninguna atestación. La primera atestación real la crea la primera ejecución de versión, y esa ejecución aún no se ha hecho.

Cada `.tar.gz`, `.deb` y `.rpm` tiene además un SBOM, con el nombre del archivo
más `.cdx.json`. Consulta [Lista de materiales de software](../security/sbom.md).

## Licencias en las compilaciones empaquetadas {#licenses-in-packaged-builds}

InvenTag usa la licencia MIT. Los archivos del ejecutable, el
`.deb` y el `.rpm` incluyen GNU libiconv, una biblioteca bajo la Licencia Pública
General Reducida de GNU (LGPL) versión 2.1. La fórmula de Homebrew prevista
instala el mismo archivo, así que también la incluye. El código de libiconv está
dentro de los módulos de extensión de lxml. InvenTag necesita lxml para escribir
archivos de Word. El proyecto lxml crea esos módulos y enlaza libiconv en ellos.
InvenTag incluye los archivos de lxml sin cambios.

- Una instalación con pip, pipx o uv no incluye libiconv en ningún archivo de
  InvenTag. Tu instalador descarga el wheel propio de lxml desde el Python
  Package Index.
- El archivo de avisos es `THIRD-PARTY-LICENSES.txt`. Nombra cada componente
  incluido, su licencia y el texto de su licencia. Contiene el texto completo de
  la LGPL 2.1. La versión tiene un archivo de avisos para cada sistema, llamado
  `inventag-%INVENTAG_VERSION%-<os>-<cpu>.THIRD-PARTY-LICENSES.txt`.
  El mismo archivo está dentro del paquete:
  - archivo independiente: `inventag/THIRD-PARTY-LICENSES.txt`
  - `.deb` y `.rpm`: `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` y
    `/opt/inventag/THIRD-PARTY-LICENSES.txt`
- El archivo de avisos nombra la versión de libiconv y los lugares del código
  fuente. En esta versión nombra libiconv 1.18 dentro de lxml 6.1.3:
  - libiconv: <https://www.gnu.org/software/libiconv/> y
    <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>
  - lxml: <https://github.com/lxml/lxml>
- InvenTag no hace ninguna oferta escrita de enviar el código fuente. Las
  direcciones anteriores son el código fuente. Si una dirección no funciona, abre
  una incidencia en <https://github.com/habhabhabs/inventag-aws/issues>.
- Los módulos de lxml son archivos separados en el directorio de instalación.
  Puedes reemplazarlos por tu propia compilación de lxml de la misma versión. La
  carpeta es `inventag/_internal/lxml/` en el archivo independiente y
  `/opt/inventag/_internal/lxml/` para el `.deb` y el `.rpm`. En macOS, vuelve a
  firmar un módulo después de reemplazarlo: `codesign -s - --force <file>`.

No verificado contra tu propia compilación de lxml: que un módulo que compiles funcione en lugar del incluido.

No verificado contra macOS fuera de un runner de GitHub: la instalación con Homebrew y el comportamiento de Gatekeeper.

Esta página no es asesoramiento legal.

## Conectar tus credenciales de AWS {#connect-your-aws-credentials}

InvenTag usa la cadena estándar de credenciales de AWS, así que sirve cualquiera de estas:

Con IAM Identity Center (recomendado):

```bash title="Terminal"
aws sso login --profile my-readonly
export AWS_PROFILE=my-readonly
```

Con claves de acceso de larga duración (evítalas si puedes):

```bash title="Terminal"
aws configure
```

No verificado contra la AWS CLI: los comandos de inicio de sesión de esta sección.

Prefiere credenciales de corta duración, como IAM Identity Center o un rol
asumido, en lugar de claves de acceso guardadas en disco.

## Comprobar que funciona {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

El código de salida 0 significa que InvenTag pudo iniciar sesión. Con `--verbose` también ves los
pasos. Salida de ejemplo de una ejecución sin conexión contra AWS simulado (datos de ejemplo):

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
0
```

Si faltan las credenciales, o el token de seguridad no es válido o ha caducado, InvenTag explica por qué y sugiere una solución. Consulta
[Solucionar problemas comunes](../guides/troubleshooting.md#credentials).

## Dar a InvenTag permisos de solo lectura {#give-inventag-read-only-permissions}

Antes de tu primer análisis real, dale a la identidad una política de solo lectura:
[Configurar el acceso de solo lectura](../guides/read-only-access.md).

## Actualizar desde v1.1.x {#upgrade-from-v11x}

Lo que notarás después de `pip install --upgrade inventag-aws`:

- **Los valores secretos se ocultan.** Los valores de los campos que suelen
  contener secretos, como las variables de entorno de Lambda, pasan a ser
  `***REDACTED***` en informes, instantáneas y registros. La primera ejecución
  después de actualizar informa una vez de esos recursos como cambiados. Los
  informes y las instantáneas de versiones anteriores pueden contener todavía
  esos valores: bórralos o restringe su acceso.
- **Columnas nuevas.** Cada hoja de servicio tiene las columnas `source`,
  `sources` y `detail_level`. Consulta [Archivos de salida](../reference/outputs.md).
- **Más servicios y más llamadas a la API.** InvenTag lista 22 servicios más,
  lo que añade hojas, filas y llamadas. La política del repositorio tiene 17
  acciones de lectura nuevas (y ya no incluye `cloudtrail:LookupEvents`); sin ellas, cada listado denegado es una
  advertencia, y esos recursos se encuentran mediante la API Tagging como antes, si tienen etiquetas. El primer informe de cambios después de actualizar muestra los recursos de los servicios que ahora se listan como añadidos, aunque ya existían. Consulta [Permisos de IAM](../reference/iam-permissions.md).
- **Archivos más estrictos.** Un archivo de ajustes vacío, una clave escrita dos
  veces o un valor de `--bom-config` de tipo incorrecto detienen la ejecución
  con el código de salida 1.
- **Las opciones incompatibles se detienen con el código de salida 2**, por
  ejemplo `--accounts-file` con `--accounts-prompt`, o `--s3-kms-key-id` sin
  `--s3-encryption aws:kms`.
- **El límite de tiempo es por cuenta**, contado desde que empieza su análisis.
  Una cuenta que se queda sin tiempo conserva los recursos que encontró y
  cuenta como fallida.
- **Los códigos de salida predeterminados no cambian.** Los códigos 5 y 6 son
  nuevos y solo aparecen con `--fail-on-account-error` y `--fail-if-empty`. Un
  formato de informe que no se puede escribir termina con el código 1.
- **Los nombres de servicio y de hoja se mantienen.** Los recursos que v1.1.4
  encontraba solo mediante la API Tagging conservan su nombre de servicio y su
  hoja (por ejemplo `ELASTICFILESYSTEM`, `STATES`, `COGNITO-IDP`,
  `ELASTICMAPREDUCE`, `KAFKA`, `ES`). Sus filas tienen ahora los detalles de la
  API del servicio, y la columna ID de los secretos de Secrets Manager y los
  clústeres de MSK contiene el nombre en lugar de la última parte del ARN.

La lista completa está en el
[registro de cambios](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md).

## Instalar para desarrollo {#install-for-development}

```bash title="Terminal"
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

La [guía de contribución](../development/CONTRIBUTING.md) explica el conjunto
completo de pruebas.

## Solucionar problemas de instalación {#fix-install-problems}

| Qué ves | Qué hacer |
|---|---|
| `Error: No suitable Python interpreter found.` o `InvenTag requires Python 3.11 or later` | Instala Python 3.11 o posterior y comprueba que `python3 --version` funciona. |
| `inventag: command not found` | Activa el entorno virtual donde ejecutaste `pip install inventag-aws`, o ejecuta `python -m pip show inventag-aws` para comprobar que está instalado. Si usas el archivo independiente, crea el enlace desde `/opt/inventag/inventag` a una carpeta de tu PATH, o ejecuta el programa con su ruta completa. |
| `ModuleNotFoundError` | Activa el entorno virtual y vuelve a ejecutar `pip install -r requirements.txt`. |
| `inventag selftest` falla | Instala InvenTag de nuevo, o descarga la versión de nuevo, y ejecuta `inventag selftest` otra vez. Si vuelve a fallar, abre una incidencia en <https://github.com/habhabhabs/inventag-aws/issues> y añade la salida. |
| `No AWS credentials found!` | Ejecuta `aws sso login` o `aws configure`, o define `AWS_PROFILE`. |

No verificado contra la AWS CLI: los comandos de la columna «Qué hacer».

## Siguiente paso {#next-step}

[Inicio rápido](./quick-start.md)
