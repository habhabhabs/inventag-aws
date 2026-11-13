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
concreta, fíjala, por ejemplo `pip install inventag-aws==1.1.3`. ¿Prefieres mantenerlo fuera de los
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
ejemplo `git checkout v1.1.3`. La
[página de versiones](https://github.com/habhabhabs/inventag-aws/releases) lista
todas las versiones.

## Conectar tus credenciales de AWS {#connect-your-aws-credentials}

InvenTag usa la cadena estándar de credenciales de AWS, así que sirve cualquiera de estas:

```bash title="Terminal"
aws sso login --profile my-readonly     # IAM Identity Center (recommended)
export AWS_PROFILE=my-readonly

aws configure                           # long-lived access keys (avoid if you can)
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
