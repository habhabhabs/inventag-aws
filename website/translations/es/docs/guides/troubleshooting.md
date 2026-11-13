---
title: Soluciona los problemas más comunes
description: Los errores más comunes de InvenTag (credenciales, permisos, regiones, limitación, plantillas y configuración), con los mensajes reales y cómo solucionarlos.
sidebar_position: 8
---

# Soluciona los problemas más comunes

**Para quién es:** algo ha salido mal y quieres la solución más rápida.

**Qué podrás hacer después de leerlo:** reconocer el mensaje que ves y corregir su
causa.

Los mensajes de abajo son salida real de InvenTag de ejecuciones sin conexión (datos de ejemplo).
Cuando un error de AWS no se puede producir sin conexión, como un token caducado, simulamos la
respuesta de error exacta de AWS y registramos cómo la notificó InvenTag.
Esos bloques se marcan como «simulated AWS error response».

Añade `--verbose` para ver cada paso, o `--debug` para ver cada llamada a AWS. Los registros de
depuración enmascaran los secretos, pero trátalos como información sensible.

## Credenciales {#credentials}

### No se encuentran credenciales {#no-credentials-found}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ No AWS credentials found!
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Set AWS environment variables:
inventag.cli.main - ERROR -       export AWS_ACCESS_KEY_ID=your-key
inventag.cli.main - ERROR -       export AWS_SECRET_ACCESS_KEY=your-secret
inventag.cli.main - ERROR -    3. Use IAM roles if running on EC2/ECS/Lambda
inventag.cli.main - ERROR -    4. Use --accounts-prompt for interactive setup
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**Solución:** inicia sesión, por ejemplo con `aws sso login --profile my-readonly` y
`export AWS_PROFILE=my-readonly`, y comprueba con
`aws sts get-caller-identity`.

### Credenciales caducadas o no válidas {#expired-or-invalid-credentials}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ AWS credential validation failed!
inventag.cli.main - ERROR -    Issue: Invalid or expired security token
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Check if your access keys are correct
inventag.cli.main - ERROR -    3. If using temporary credentials, they may have expired
inventag.cli.main - ERROR -    4. If using AWS SSO, run 'aws sso login'
inventag.cli.main - ERROR -
inventag.cli.main - ERROR - 💡 Quick diagnostic commands:
inventag.cli.main - ERROR -    aws configure list          # Show current config
inventag.cli.main - ERROR -    aws sts get-caller-identity # Test credentials
inventag.cli.main - ERROR -    aws configure               # Set up new credentials
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**Solución:** vuelve a iniciar sesión (`aws sso login --profile <name>`), o renueva tus
claves temporales. Si usas claves de acceso, compruébalas con `aws configure list`.

### No se puede asumir un rol {#a-role-cannot-be-assumed}

**Lo que ves:** esto en el registro, y un informe en el que falta la cuenta:

```text
inventag.core.cloud_bom_generator.CloudBOMGenerator - ERROR - Failed to establish context for account 999999999999: Role assumption failed for account 999999999999: An error occurred (AccessDenied) when calling the AssumeRole operation: ...
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Skipping account 999999999999 due to invalid session
```

Si otras cuentas funcionaron, InvenTag escribe igualmente su informe y **termina con el
código 0**. Si todas las cuentas fallan, termina con el código 1. (Texto del mensaje de una
ejecución sin conexión con un error de AWS simulado.)

**Solución:** comprueba el ARN del rol y que la política de confianza del rol permita
tu identidad. InvenTag no recurre a otras credenciales, así que esa
cuenta se omite hasta que funcione.

### Un nombre de rol sin archivo de cuentas {#a-role-name-without-an-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
$ echo $?
2
```

**Solución:** pasa el ARN completo del rol, o añade `--accounts-file` con los ID
de cuenta.

## Permisos {#permissions}

### Acceso denegado a Cost Explorer {#cost-explorer-access-denied}

InvenTag continúa sin datos de facturación y la ejecución termina bien, por lo que el problema
es fácil de pasar por alto. Solo se ve con `--debug`:

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0

$ # the same run with --debug, lines that mention AccessDeniedException
Cost Explorer data is not available, so billing checks are skipped: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

**Solución:** añade `ce:GetCostAndUsage` a la política, o acepta que faltan
los datos de facturación.

### Un servicio o una columna está vacío {#a-service-or-column-is-empty}

**Causa:** la identidad no tiene un permiso `List*`, `Describe*` o `Get*` para
ese servicio. El descubrimiento continúa sin él y no imprime ningún mensaje. El error
de AWS se registra solo en el nivel de depuración, donde es difícil de encontrar en la larga
salida. Ejecuta la llamada equivalente de la AWS CLI con la misma identidad para comprobarlo.

**Solución:** usa la política de `config/defaults/iam-policy-read-only.json`, que
cubre todas las llamadas que hace InvenTag. Consulta [Permisos de IAM](../reference/iam-permissions.md).

### Bloqueado por la protección de solo lectura {#blocked-by-the-read-only-guard}

**Lo que ves:** `Read-only guard blocked <service>:<Operation>` en el registro,
y un error que empieza por `Blocked AWS operation <service>:<Operation>`.

**Causa:** una llamada que no es de lectura llegó a la protección. InvenTag
no hace esas llamadas por sí mismo, así que normalmente se trata de código personalizado o de un complemento.

**Solución:** comprueba de qué operación se trataba con
`inventag --validate-operations <service>:<Operation>`. La protección no se puede
desactivar.

## Regiones {#regions}

### Una región no está habilitada para la cuenta {#a-region-is-not-enabled-for-the-account}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0
```

La ejecución continúa con las regiones que funcionan.

**Solución:** quita la región de `--account-regions`, o habilítala para la
cuenta en la consola de AWS (Account settings, AWS Regions).

## Limitación de solicitudes (throttling) {#throttling}

Cuando llegan demasiadas solicitudes a la vez, AWS las ralentiza. El SDK de AWS
(kit de desarrollo de software) reintenta automáticamente. No hemos probado cómo
notifica InvenTag una limitación que persiste después de los reintentos.

**Solución:** analiza menos cuentas a la vez (`--max-concurrent-accounts 2`), analiza
menos regiones, o da más tiempo a las cuentas grandes
(`--account-processing-timeout 3600`).

## Plantillas y archivos de configuración {#templates-and-configuration-files}

### Plantilla no válida {#invalid-template}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
$ echo $?
1
```

**Solución:** corrige el campo de la línea indicada. Ejecuta
`inventag templates validate <file>` para comprobar sin analizar.

### Nombre de plantilla desconocido {#unknown-template-name}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
$ echo $?
1
```

**Solución:** comprueba la ortografía con `inventag templates list`. Las plantillas
del proyecto deben estar en `.inventag/templates/` en la carpeta desde la que ejecutas.

### Archivo de cuentas no válido {#invalid-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

**Solución:** pon los ID de cuenta entre comillas (`account_id: "123456789012"`), y da a
cada cuenta `profile_name`, `role_arn` o claves de acceso.

### Otros mensajes de plantillas {#other-template-messages}

| El mensaje contiene | Solución |
|---|---|
| `did you mean '...'?` | Corrige la ortografía en la línea indicada. |
| `Put account IDs in quotes` | Escribe `account_id: "012345678901"`. |
| `must stay inside the template's folder` | Mueve el archivo referenciado junto a la plantilla, o a una subcarpeta. |
| `templates must not contain credentials` | Quita las claves de acceso; usa `profile_name` o `role_arn`. |
| `--template given two report templates` | Indica como máximo una plantilla de cada tipo. |

## Opciones que detienen la ejecución {#flags-that-stop-the-run}

Dos opciones se aceptan pero detienen la ejecución con código de salida 2 y un mensaje que empieza por el nombre de la opción. `--compliance-standard` dice que aún no está implementada. `--disable-production-safety` dice que la protección de solo lectura no se puede desactivar. Consulta
[Estado de las funciones y limitaciones conocidas](../getting-started/status.md).

## Código de salida 3 {#exit-code-3}

No es un error de InvenTag. Una política de etiquetas encontró infracciones y la plantilla
de configuración tiene `fail_on_tag_violations: true`. Abre la hoja Tag Compliance o
el archivo JSON para ver qué recursos.

## Los informes se ven mal {#reports-look-wrong}

| Lo que ves | Causa y solución |
|---|---|
| Hojas muy anchas con columnas `raw_data.*` | Ese es el diseño predeterminado. Usa `--template standard-bom`. |
| Faltan las columnas de asignación de etiquetas | Las asignaciones de etiquetas añaden columnas solo al libro predeterminado. Con `--template`, usa `tag_columns`. Consulta [Archivos de configuración](../reference/configuration-files.md#tag-mappings). |
| Se ignora una descripción de servicio personalizada | S3, EC2, RDS, Lambda y VPC tienen descripciones integradas que prevalecen salvo que tu entrada indique un `template`. Consulta [Archivos de configuración](../reference/configuration-files.md#service-descriptions). |
| No hay hojas de red ni de seguridad | Añade `--enable-network-analysis` o `--enable-security-analysis`, y asegúrate de que el análisis encontró VPC o grupos de seguridad. Las opciones no añaden nada con `--template`. Consulta [Análisis de red y seguridad](./network-and-security-analysis.md). |
| Faltan recursos de IAM, S3, CloudFront o Route 53 | `--account-services` o `--account-tags` los quitaron, o la identidad no tiene el permiso (busca una advertencia por servicio en el registro). La lista de regiones no importa: los servicios globales siempre se leen desde `us-east-1`. |
| Un recurso no muestra etiquetas, o aparece dos veces | Ejecuta con `--debug` y compara la columna ARN con el ARN de la consola de AWS. Notifica una discrepancia como problema (issue) indicando el servicio y el tipo de recurso. |
| No hay archivo de informe y el código de salida es 0 | El análisis no encontró nada, o `--account-services` o `--account-tags` lo quitaron todo. Busca `No resources to report` en el registro. |
| Falta una cuenta en el informe | Fallaron sus credenciales o su rol. Consulta [No se puede asumir un rol](#a-role-cannot-be-assumed). |
| Falta el informe de cambios | La primera ejecución no escribe ninguno. Además, necesita que la gestión de estado y la detección de diferencias estén activadas. Consulta [Sigue los cambios entre ejecuciones](./track-changes.md). |
| Otro usuario no puede abrir `bom_output/` | Los archivos de salida son privados para el usuario que ejecutó InvenTag. Compártelos de forma deliberada. |

## Ruido que puedes ignorar {#noise-you-can-ignore}

Algunos mensajes parecen errores pero no cambian nada en tu informe.

| Mensaje | Por qué puedes ignorarlo |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'`` (con `--service-descriptions`) | La plantilla de descripción de VPC quiere un campo que el recurso no tiene. El informe no se ve afectado. |
| `No account specification method provided. Using default AWS credentials.` | No indicaste ninguna cuenta, así que InvenTag usó tus credenciales actuales. Es el caso normal. |
| `Cross-account role ... not usable ... trying default credentials` | InvenTag probó el nombre de rol predeterminado, no pudo asumirlo y continuó con tus propias credenciales. Se registra una vez por cuenta. |

## Problemas de instalación {#install-problems}

Consulta [Instala InvenTag](../getting-started/installation.md#fix-install-problems).

## ¿Sigues atascado? {#still-stuck}

Abre un [problema (issue)](https://github.com/habhabhabs/inventag-aws/issues) con el
comando que ejecutaste, la versión (`python -m pip show inventag-aws`, o `git describe --tags` en un clon) y el mensaje. Quita los
ID y nombres de cuenta que no quieras compartir. No pegues nunca credenciales.
