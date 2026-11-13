---
title: Seguridad
description: Cómo comunicar una vulnerabilidad en InvenTag, qué versiones de Python usar, cómo se revisan las dependencias y qué hacer tras un incidente de suministro.
sidebar_position: 1
---

# Seguridad

**Para quién es:** revisores de seguridad y cualquiera que ejecute InvenTag
contra cuentas de producción.

**Qué sabrás después de leerlo:** cómo comunicar un problema, cómo se comprueban
las dependencias de InvenTag y cómo limitar el daño si algo sale mal.

## Comunica una vulnerabilidad {#report-a-vulnerability}

Por favor, no pongas detalles de un exploit en un problema (issue) público.

Este repositorio todavía no tiene un archivo `SECURITY.md` ni la comunicación
privada de vulnerabilidades de GitHub configurada (comprobado en noviembre de
2026). Hasta que la tenga, abre un [problema (issue)](https://github.com/habhabhabs/inventag-aws/issues)
con el título "Security contact request", sin detalles técnicos, y pide a la
persona mantenedora un canal privado.

## Qué hace InvenTag con tus cuentas {#what-inventag-does-with-your-accounts}

- **Solo lee.** Una protección de solo lectura comprueba cada llamada a AWS
  antes de enviarla. Bloquea todo lo que no sea una lectura, y las lecturas que
  devuelven secretos o datos, como `secretsmanager:GetSecretValue`,
  `s3:GetObject`, `cloudformation:GetTemplate` o `ec2:GetLaunchTemplateData`.
  También bloquea operaciones permitidas cuando un parámetro pide un secreto
  (claves de API con `includeValue`, `ec2:DescribeInstanceAttribute` para
  `userData`), y comprueba las URL prefirmadas y los tokens de autenticación de
  bases de datos, que se firman sin llamar a AWS. También bloquea las lecturas
  que entregan una URL firmada, el cuerpo de un archivo o documento, la salida
  de un comando o una definición guardada con secretos (por ejemplo
  `ssm:GetDocument`, `ssm:GetCommandInvocation`, las exportaciones de API
  Gateway, las definiciones de Data Pipeline y los adjuntos de Support y
  Connect), y `cognito-identity:GetId`, que crea una identidad. Cada entrada de
  la lista de denegación se comprueba con la lista de operaciones del SDK de
  AWS. Siempre está activa.
- **El inicio de sesión sigue funcionando.** La protección deja que el SDK de
  AWS cambie un token de IAM Identity Center (SSO), de identidad web o de
  `aws login` por credenciales. Solo permite estas cuatro llamadas sin firmar:
  `sso:GetRoleCredentials`, `sso-oidc:CreateToken`,
  `sts:AssumeRoleWithWebIdentity` y `signin:CreateOAuth2Token`. Un cliente
  firmado que haga la misma llamada queda bloqueado.
- **Oculta los valores secretos de las respuestas permitidas.** Los valores de
  los campos que suelen contener secretos, como las variables de entorno de
  Lambda, los datos de usuario de EC2 o los valores de parámetros de
  CloudFormation, pasan a ser `***REDACTED***` en informes, instantáneas y
  registros. Los nombres se mantienen. Consulta
  [Estado de las funciones](../getting-started/status.md#what-inventag-finds-and-what-it-does-not).
- **No envía datos de uso.** InvenTag no tiene telemetría. La herramienta de
  línea de comandos solo se comunica con AWS. El asistente de CI opcional de la
  biblioteca de Python puede publicar en Slack, Microsoft Teams o un
  Prometheus Pushgateway, pero solo en las direcciones que configures tú.
- **Sus archivos son privados.** Los informes, las instantáneas y los registros
  se crean legibles solo para tu usuario.
- **Sus registros ocultan los secretos.** Los tokens de sesión, las claves, las
  firmas de solicitud y los valores ocultos indicados arriba se enmascaran,
  incluso con `--debug`.

Puedes comprobar lo que hizo una ejecución con `--audit-output audit.json`, y
lo que permite la protección con `--validate-operations`:

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

## Usa una versión de Python compatible {#use-a-supported-python-version}

Usa Python 3.11 o posterior. Python 3.10 y anteriores ya no reciben
correcciones de seguridad: 3.10 llegó al fin de su vida útil en octubre de 2026
([estado de las versiones de Python](https://devguide.python.org/versions/)).

## Cómo se comprueban las dependencias {#how-dependencies-are-checked}

| Qué | Cómo, en la rama `main` actual |
|---|---|
| Dependencias de Python | Listadas en `requirements.txt` con versiones mínimas (`>=`), no fijadas exactamente. Cada mínimo de seguridad nombra el aviso (advisory) que evita. Una instalación nueva obtiene las versiones coincidentes más recientes. |
| Herramientas de desarrollo | Listadas en `requirements-dev.txt` con versiones exactas (`==`) para las herramientas de pruebas y de lint, más versiones mínimas para sus dependencias. |
| Sitio web | Bloqueadas en `website/package-lock.json`. |
| Comprobación de dependencias en CI | El flujo de trabajo de CI ejecuta `pip-audit -r requirements.txt` y falla si encuentra algo. También ejecuta Bandit y `npm audit`, pero no falla por sus hallazgos. |
| Análisis programado | Un flujo de trabajo aparte se ejecuta en los push a `main` y `develop`, en las pull request a `main` y cada semana (domingos, 02:00 UTC). Ejecuta Bandit, Safety, pip-audit, `npm audit` y detect-secrets. Los hallazgos se comunican pero no hacen fallar ese flujo de trabajo. |
| Lista de materiales de software | La compilación de la documentación genera archivos SBOM de las dependencias de Python y del sitio web. |

Para comprobar tu propia instalación:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

La función de plantillas no añade dependencias nuevas. Usa PyYAML, openpyxl y
python-docx, que InvenTag ya necesita.

## Reduce el impacto si algo sale mal {#reduce-the-impact-if-something-goes-wrong}

InvenTag lee tus cuentas de AWS, así que las credenciales que le das importan
más que la propia herramienta.

- **Solo lectura, mínimo privilegio.** Da a InvenTag solo permisos de lectura:
  [Configurar el acceso de solo lectura](../guides/read-only-access.md).
- **Credenciales de corta duración.** Usa IAM Identity Center o un rol asumido,
  no claves de acceso en disco ni en secretos de CI. En GitHub Actions, usa
  OIDC.
- **Mantén los registros privados.** Los secretos se enmascaran en los
  registros, pero los registros aun así describen tus cuentas.
- **Fija lo que ejecutas.** Descarga una etiqueta de versión de InvenTag y fija
  las GitHub Actions a SHA de commit.

## Después de un incidente en la cadena de suministro {#after-a-supply-chain-incident}

Si una dependencia, una acción de CI o la máquina que ejecuta InvenTag pueden
haberse visto comprometidas:

1. **Revoca y rota** las credenciales que usó InvenTag: elimina las claves de
   acceso, revoca las sesiones de rol activas y cierra las sesiones de SSO.
2. **Revisa AWS CloudTrail** en busca de llamadas de esa identidad que InvenTag
   no haría, especialmente cualquiera que no sea `List`, `Describe` o `Get`.
3. **Comprueba que la política de IAM sigue siendo de solo lectura** y elimina
   cualquier extra.
4. **Reconstruye el entorno** a partir de un entorno virtual limpio:
   `pip install -r requirements.txt` y después ejecuta `pip-audit`.
5. **Trata los informes antiguos como sensibles.** Listan tus recursos y
   etiquetas.

## Las plantillas son datos, no código {#templates-are-data-not-code}

Las plantillas se leen con un cargador de YAML seguro, no pueden ejecutar
código ni descargar URL, solo pueden referenciar archivos dentro de su propia
carpeta y no pueden contener claves de acceso. Detalles:
[Plantillas](../templates/index.md#safe-by-design).
