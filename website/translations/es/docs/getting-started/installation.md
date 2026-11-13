---
title: Instalar InvenTag
description: Instala InvenTag en un entorno virtual de Python, conecta tus credenciales de AWS y comprueba que todo funciona.
sidebar_position: 2
---

# Instalar InvenTag

**Para quién es:** cualquiera que vaya a configurar InvenTag en un portátil, un servidor o un
ejecutor de CI.

**Qué podrás hacer después de leerlo:** ejecutar `inventag --help` y confirmar que
InvenTag llega a tu cuenta de AWS.

## Qué necesitas {#what-you-need}

- **Python 3.11 o posterior.** Python 3.10 dejó de recibir correcciones de seguridad en
  octubre de 2026. Comprueba tu versión con `python3 --version`.
- **pip**, que viene con Python. (Git solo hace falta para instalar desde el código fuente.)
- **Credenciales de AWS** de una identidad de solo lectura. La
  [interfaz de línea de comandos de AWS (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  es opcional, pero es la forma más fácil de configurarlas.

## Instalar con pip (recomendado) {#install-with-pip-recommended}

InvenTag se publica en el Python Package Index como
[`inventag-aws`](https://pypi.org/project/inventag-aws/). Un entorno virtual
es la forma ordenada de instalarlo, pero InvenTag no lo necesita. Es un paquete
de Python normal. Un entorno virtual mantiene sus dependencias
(boto3, openpyxl y otras) separadas de tus demás herramientas de Python, y muchos
sistemas actuales (Debian, Ubuntu, Python de Homebrew) rechazan `pip install` en el
Python del sistema con el error «externally-managed-environment». Las dos opciones
que funcionan en esos sistemas son un entorno virtual o `pipx`:

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

Con esto tienes el comando `inventag` que usa esta documentación. Las plantillas
de informe vienen incluidas en el paquete.

Para actualizar, ejecuta `pip install --upgrade inventag-aws`. Para instalar una versión
concreta, fíjala, por ejemplo `pip install inventag-aws==%INVENTAG_VERSION%`. ¿Prefieres mantenerlo fuera de los
entornos de tus proyectos? `pipx install inventag-aws` lo instala en su propio
entorno oculto y pone el comando `inventag` en tu PATH, así que nunca tienes que activar
nada. Si tu sistema lo permite, un simple `pip install inventag-aws`
en tu Python de usuario o del sistema también funciona.

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

Para usar desde el código fuente una versión fija en lugar del código más reciente, descarga su etiqueta, por
ejemplo `git checkout v%INVENTAG_VERSION%`. La
[página de versiones](https://github.com/habhabhabs/inventag-aws/releases) lista
todas las versiones.

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

Prefiere credenciales de corta duración, como IAM Identity Center o un rol
asumido, en lugar de claves de acceso guardadas en disco.

## Comprobar que funciona {#check-that-it-works}

```bash title="Terminal"
inventag --validate-credentials --verbose
```

El código de salida 0 significa que InvenTag pudo iniciar sesión. Con `--verbose` también ves los
pasos. Salida de ejemplo de una ejecución sin conexión contra AWS simulado (datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
$ echo $?
0
```

Si las credenciales no funcionan, InvenTag explica por qué y sugiere una solución. Consulta
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
  acciones de lectura más; sin ellas, esos servicios se omiten con una
  advertencia. Consulta [Permisos de IAM](../reference/iam-permissions.md).
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
  nuevos y solo aparecen con `--fail-on-account-error` y `--fail-if-empty`.

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
| `inventag: command not found` | Activa el entorno virtual donde ejecutaste `pip install inventag-aws`, o ejecuta `python -m pip show inventag-aws` para comprobar que está instalado. |
| `ModuleNotFoundError` | Activa el entorno virtual y vuelve a ejecutar `pip install -r requirements.txt`. |
| `No AWS credentials found!` | Ejecuta `aws sso login` o `aws configure`, o define `AWS_PROFILE`. |

## Siguiente paso {#next-step}

[Generar tu primer informe](./quick-start.md)
