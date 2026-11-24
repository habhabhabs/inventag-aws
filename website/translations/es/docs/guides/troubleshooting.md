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

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ No AWS credentials found!
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Set AWS environment variables:
inventag.cli.main - ERROR -       export AWS_ACCESS_KEY_ID=your-key
inventag.cli.main - ERROR -       export AWS_SECRET_ACCESS_KEY=your-secret
inventag.cli.main - ERROR -    3. Use IAM roles if running on EC2/ECS/Lambda
inventag.cli.main - ERROR -    4. Use --accounts-prompt for interactive setup
inventag.cli.main - ERROR -    5. If you use AWS SSO, run 'aws sso login --profile <name>' and set AWS_PROFILE=<name>, or name the profile in an accounts file
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

**Solución:** inicia sesión, por ejemplo con `aws sso login --profile my-readonly` y
`export AWS_PROFILE=my-readonly`, y comprueba con
`aws sts get-caller-identity`.

No verificado contra la AWS CLI: los comandos de esta solución.

### Credenciales caducadas o no válidas {#expired-or-invalid-credentials}

```text title="Salida (simulated AWS error response)"
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
```

```bash title="Terminal"
echo $?
```

```text title="Salida (simulated AWS error response)"
1
```

**Solución:** vuelve a iniciar sesión (`aws sso login --profile <name>`), o renueva tus
claves temporales. Si usas claves de acceso, compruébalas con `aws configure list`.

No verificado contra la AWS CLI: los comandos de esta solución.

Con un perfil de IAM Identity Center (SSO) cuyo inicio de sesión ha caducado, la ejecución se detiene con el código de salida 1 y un mensaje que nombra `aws sso login --profile <name>`. No muestra ningún traceback.

No verificado contra AWS IAM Identity Center: el mensaje de un token caducado.

### No se puede asumir un rol {#a-role-cannot-be-assumed}

**Lo que ves:** esto en el registro, y un informe en el que falta la cuenta:

```text
inventag.core.cloud_bom_generator.CloudBOMGenerator - ERROR - Failed to establish context for account 999999999999: Role assumption failed for account 999999999999: An error occurred (AccessDenied) when calling the AssumeRole operation: ...
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Skipping account 999999999999 due to invalid session
```

Si otras cuentas funcionaron, InvenTag escribe igualmente su informe y **termina con el código 0**, o con el código 5 si pasas `--fail-on-account-error`. La hoja `Summary` y el informe de Word tienen una sección «Run notes» (notas de la ejecución) que nombra la cuenta, y el registro termina con esta lista:

```text
1 of 2 account(s) finished and were saved. Run the same command with --resume within 24 hours to scan only the other 1.
1 account(s) were not scanned, or only partly. The report does not include them:
  - 222222222222 (Dev): Context establishment failed: Role assumption failed for account 222222222222: ...
```

Si todas las cuentas fallan, termina con el código 1 y no escribe ningún informe: `Resource discovery failed for all 1 configured account(s); no report was generated`. (Texto del mensaje de una ejecución sin conexión con un error de AWS simulado.)

**Solución:** comprueba el ARN del rol y que la política de confianza del rol permita
tu identidad. InvenTag no analiza la cuenta con credenciales que pertenezcan a otra cuenta, así que esa cuenta se omite hasta que el rol funcione. Después ejecuta el mismo comando con `--resume` para analizar solo las cuentas que faltan.

### Un perfil que necesita un código MFA, sin terminal {#a-profile-that-needs-an-mfa-code-without-a-terminal}

Cuando el perfil (el predeterminado, o uno nombrado en un archivo de cuentas) tiene
`mfa_serial` e InvenTag se ejecuta sin terminal (un trabajo de CI, una tubería, una
tarea programada), la ejecución se detiene en el acto con un mensaje en lugar de
esperar el código. Para las credenciales predeterminadas:

```text
❌ Profile 'mfa1' needs an MFA code, and there is no terminal to type it.
   Run InvenTag in a terminal, or get temporary credentials first and set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_SESSION_TOKEN:
   aws sts get-session-token --serial-number <MFA device ARN> --token-code <code>
```

Para una entrada de un archivo de cuentas, la cuenta falla con `Profile 'mfa1' for account
123456789012 needs an MFA code, and there is no terminal to type it in. ...`
y se analizan las demás cuentas. Código de salida 1 cuando no se pudo usar ninguna
cuenta. `--validate-credentials` comprueba lo mismo. Con un terminal, el código se
pide como antes. No verificado contra AWS real: un dispositivo MFA real.

**Solución:** ejecuta InvenTag en un terminal, o usa credenciales temporales de
`aws sts get-session-token`.

### Un nombre de rol sin archivo de cuentas {#a-role-name-without-an-accounts-file}

```text title="Salida"
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
2
```

**Solución:** pasa el ARN completo del rol, o añade `--accounts-file` con los ID
de cuenta.

## Permisos {#permissions}

### Acceso denegado a Cost Explorer {#cost-explorer-access-denied}

InvenTag continúa sin datos de facturación y la ejecución termina bien, por lo que el problema
es fácil de pasar por alto. Una ejecución normal muestra una advertencia que nombra la causa, y `--debug` añade el texto del error de AWS:

```text title="Salida (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Cost Explorer: up to 1 request(s) in this run (billing validation: 1; cost trend: 0). AWS charges for each.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
inventag - WARNING - Notes about this run:
inventag - WARNING -   - Permissions: 1 action(s) were not allowed for account 123456789012: ce:GetCostAndUsage. Effect: billing checks are skipped. All of them are in the AWS managed policy ReadOnlyAccess.
```

```bash title="Terminal"
echo $?
```

```text title="Salida (simulated AWS error response)"
0
```

```bash title="Terminal"
# the same run with --debug, lines that mention AccessDeniedException
```

```text title="Salida (simulated AWS error response)"
[AWS Account 123456789012 (moto)] inventag.discovery.inventory - WARNING - Cost Explorer was denied (AccessDeniedException), so billing data is missing and billing checks are skipped. Allow ce:GetCostAndUsage for this role.
[AWS Account 123456789012 (moto)] inventag.discovery.inventory - DEBUG - Cost Explorer detail: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
[AWS Account 123456789012 (moto)] inventag.discovery.comprehensive_discovery - DEBUG - Cost Explorer detail: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

La línea `Permissions:` de las notas de la ejecución nombra la acción rechazada. Consulta [Las notas de la ejecución tienen una línea Permissions](#the-run-notes-have-a-permissions-line).

**Solución:** añade `ce:GetCostAndUsage` a la política, o acepta que faltan
los datos de facturación.

### Un servicio o una columna está vacío {#a-service-or-column-is-empty}

**Causa:** la identidad no tiene un permiso `List*`, `Describe*` o `Get*` para
ese servicio. Con una llamada de listado, InvenTag registra una advertencia para el servicio y continúa sin sus recursos:

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Con una llamada que completa un detalle de un recurso (la ubicación de un bucket, la configuración de una función), el descubrimiento conserva el recurso, deja ese detalle vacío y lo dice en las «Run notes» (notas de la ejecución) del informe:

```text
Details of 5 resource(s) in account 111111111111 could not be read, so those rows have some fields missing: lambda GetFunctionConfiguration in us-east-1 (throttled, 2); s3 GetBucketLocation in us-east-1 (denied, 3).
```

El error de AWS se registra en el nivel de depuración. Ejecuta la llamada equivalente de la AWS CLI con la misma identidad para comprobarlo.

**Solución:** usa la política de `config/defaults/iam-policy-read-only.json`, que
cubre todas las llamadas que hace InvenTag. Consulta [Permisos de IAM](../reference/iam-permissions.md).

### Las notas de la ejecución tienen una línea Permissions {#the-run-notes-have-a-permissions-line}

**Qué ves:** una línea que empieza por `Permissions:` en las notas de la ejecución. Aparece en la consola al final de la ejecución y en las «Run notes» del informe de Excel. Hay una línea por cada cuenta que no tuvo permiso para usar una acción de IAM. Una ejecución a la que no se le denegó nada no imprime esa línea. Esta es una línea de una ejecución sin conexión con una política a la que le faltan cinco acciones (datos de ejemplo):

```text
Permissions: 5 action(s) were not allowed for account 123456789012: ce:GetCostAndUsage, lambda:GetFunctionConfiguration, pricing:GetProducts, s3:GetBucketLocation, tag:GetResources. Effect: some rows lack details; tags from the Tagging API are missing; billing checks are skipped; cost estimates are missing. All of them are in the AWS managed policy ReadOnlyAccess.
```

La línea nombra cada acción, en orden. Después de `Effect:` dice qué le falta al informe. La última frase dice si la política administrada de AWS `ReadOnlyAccess` incluye las acciones. Una llamada de la que InvenTag no conoce la acción de IAM se nombra por su nombre de API, con `(IAM action not known to InvenTag)`.

**Causa:** la identidad no puede usar esas acciones. InvenTag solo ve que AWS rechazó la llamada. No puede saber si la rechazó la política de la identidad, una política de control de servicios o un límite de permisos.

No verificado contra AWS real: las acciones nombradas son las de las tablas propias de InvenTag, y un rechazo por una política de control de servicios o por un límite de permisos también se muestra como la acción.

**Solución:** añade las acciones nombradas a la política, o acepta que al informe le falte lo que dice el texto de `Effect`. La misma lista está en la clave `permissions_denied` del archivo de `--audit-output`. Consulta [Ejecutar solo con ReadOnlyAccess](./read-only-access.md#run-with-only-readonlyaccess).

### Bloqueado por la protección de solo lectura {#blocked-by-the-read-only-guard}

**Lo que ves:** `Read-only guard blocked <service>:<Operation>` en el registro,
y un error que empieza por `Blocked AWS operation <service>:<Operation>`.

**Causa:** una llamada que no es de lectura, o una lectura que devuelve secretos o datos de clientes (por ejemplo `cloudformation:GetTemplate` o `ssm:GetParameter`), llegó a la protección. Esto no debería ocurrir en una ejecución normal. Si ocurre, InvenTag registra una línea de error que nombra la operación bloqueada y dice que es un defecto de InvenTag (las «Run notes» del informe también lo dicen si el bloqueo ocurrió durante el análisis), y la ejecución sigue terminando con el código 0. Abre un issue con el nombre de la operación. Consulta [Qué bloquea la protección de solo lectura](./read-only-access.md#what-the-read-only-guard-blocks).

**Solución:** comprueba de qué operación se trataba con
`inventag --validate-operations <service>:<Operation>`. La protección no se puede
desactivar.

## Regiones {#regions}

### Una región no está habilitada para la cuenta {#a-region-is-not-enabled-for-the-account}

```text title="Salida (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Cost Explorer: up to 1 request(s) in this run (billing validation: 1; cost trend: 0). AWS charges for each.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
inventag - WARNING - Notes about this run:
inventag - WARNING -   - Regions skipped in account 123456789012 because the region check (ec2:DescribeRegions) was denied or failed there: ap-east-1.
```

```bash title="Terminal"
echo $?
```

```text title="Salida (simulated AWS error response)"
0
```

La ejecución continúa con las regiones que funcionan.

**Solución:** quita la región de `--account-regions`, o habilítala para la
cuenta en la consola de AWS (Account settings, AWS Regions).

No verificado contra AWS real: la ruta de la consola para habilitar una región.

### Un nombre de región mal escrito {#a-region-name-is-misspelled}

Un nombre de región que no pasa la comprobación de región y que el boto3 instalado no conoce, como `us-east-9` en `--account-regions`, se nombra una sola vez con el comando que lista las regiones válidas:

```text
Region 'us-east-9' could not be checked and the installed boto3 does not know it: check its spelling in --account-regions or in the accounts file, or, if it is a new AWS region, upgrade boto3. To list the regions of your account, run: aws ec2 describe-regions --query 'Regions[].RegionName' --output text
```

La ejecución termina con el código 0. Cuando otras regiones funcionan, se analizan, y las «Run notes» dicen `Regions not scanned in account 123456789012 because their region check failed and the installed boto3 does not know them (a misspelled name, or a region newer than boto3): us-east-9.` Una región que boto3 no conoce pero a la que AWS responde se analiza.

**Solución:** corrige el nombre de la región.

### Una región de otra partición {#a-region-of-another-partition}

Una región de China (`cn-`) o GovCloud (`us-gov-`) en `--account-regions` con
credenciales de la partición comercial (o al revés) se nombra una vez:

```text
Region 'cn-north-1' is in the aws-cn partition, but the credentials of account 123456789012 are for the aws partition, so it cannot be scanned with them; scan it with credentials of that partition.
```

La región se intenta igualmente, y la ejecución termina con el código 0. La
comprobación de la cuenta (`sts:GetCallerIdentity`) usa el endpoint de STS de la
partición analizada. No verificado contra AWS real: credenciales de GovCloud y de China.

**Solución:** analiza esa región en una ejecución aparte con credenciales de su
partición.

### No se puede leer la lista de regiones {#the-list-of-regions-cannot-be-read}

Si `ec2:DescribeRegions` falla, InvenTag consulta `account:ListRegions` y después prueba todas las regiones de la partición:

```text
ec2:DescribeRegions failed (An error occurred (UnauthorizedOperation) when calling the DescribeRegions operation: ...); trying account:ListRegions instead.
account:ListRegions failed (An error occurred (AccessDeniedException) when calling the ListRegions operation: ...).
Could not read the account's enabled regions. Trying all 34 regions of the aws partition known to botocore; regions the account has not enabled will fail the access check and be skipped. Use --account-regions to choose.
```

La comprobación de acceso de cada región también usa `ec2:DescribeRegions`. Si se deniega en todas las regiones, InvenTag no puede saber cuáles funcionan:

```text
ec2:DescribeRegions is denied in every region, so region access cannot be checked; scanning all 34 regions.
```

El número de regiones procede del AWS SDK instalado (botocore) y cambia con su versión.

**Solución:** permite `ec2:DescribeRegions`, o indica las regiones con `--account-regions`.

## Limitación de solicitudes (throttling) {#throttling}

Cuando llegan demasiadas solicitudes a la vez, AWS las ralentiza. El SDK de AWS
(kit de desarrollo de software) reintenta automáticamente, hasta 10 intentos en total.
Si un listado sigue fallando después, InvenTag registra una advertencia para el servicio y la región, y sus recursos allí pueden faltar en el informe:

```text
sqs list_queues in us-east-1 failed (ThrottlingException); its resources there may be incomplete.
```

**Solución:** envía menos solicitudes a la vez (`--concurrency 16`), analiza menos cuentas a la vez (`--max-concurrent-accounts 2`), analiza
menos regiones, o da más tiempo a las cuentas grandes
(`--account-processing-timeout 3600`).

InvenTag también baja su propio límite para un servicio y una región después de una respuesta de limitación. Consulta [Concurrencia](./run-a-scan.md#when-aws-throttles).

No verificado contra AWS real: que menos solicitudes, cuentas o regiones a la vez reduzcan la limitación de solicitudes.

## Límites de tiempo y resultados parciales {#time-limits-and-partial-results}

### Una cuenta se queda sin tiempo {#an-account-runs-out-of-time}

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

La cuenta cuenta como fallida, pero los recursos encontrados antes del límite están en el informe, y las «Run notes» nombran la cuenta. Las demás cuentas se conservan. Si ninguna cuenta termina, InvenTag escribe el informe igualmente, registra `No account finished within its time limit (--account-processing-timeout)` y termina con el código 1. (Texto del mensaje de una ejecución sin conexión con un límite de 60 segundos.)

Una solicitud que espera un lugar libre bajo `--concurrency` cuenta para el límite de tiempo.

**Solución:** sube `--account-processing-timeout` (valor predeterminado 1800), analiza menos regiones o servicios, o analiza menos cuentas a la vez. Ejecuta el mismo comando con `--resume` para analizar solo las cuentas que no terminaron.

### Un Cost Explorer lento {#a-slow-cost-explorer}

Con `--account-processing-timeout` por debajo de 1200 segundos, cada llamada a Cost Explorer espera como máximo una cuadragésima parte del límite, y al menos 5 segundos, para conectar y para leer, con dos intentos. Si no responde a tiempo, la cuenta se analiza igualmente y sus recursos están en el informe. Las «Run notes» dicen:

```text
Cost Explorer did not answer in time for account 123456789012, so its billing checks were skipped and services that only billing shows are not listed for it.
```

**Solución:** añade `--no-billing-validation` para no hacer llamadas a Cost Explorer, o fija `--account-processing-timeout` en 1200 o más.

### La ejecución se detiene con Ctrl-C o SIGTERM {#the-run-is-stopped-with-ctrl-c-or-sigterm}

Ctrl-C y SIGTERM imprimen cada uno una línea que dice qué se escribió:

```text
Stopped by the user (Ctrl-C). No report was written.
Terminated (SIGTERM). No report was written.
```

Después de la señal no empieza ninguna solicitud nueva a AWS, y una solicitud que espera un lugar libre termina de inmediato. Si ya se había escrito un archivo de informe, la línea dice `1 report file(s) already written stay in <output folder>.` en su lugar. Ctrl-C termina con el código 1. SIGTERM termina el proceso con la propia señal después de la línea.

### No se reutilizan los resultados guardados {#saved-results-are-not-reused}

| Mensaje | Significado |
|---|---|
| `1 account(s) have saved results from an earlier run of this command that did not finish. They are scanned again; add --resume to reuse them.` | Los resultados guardados existen, pero no pasaste `--resume`. |
| `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)` | Se reutiliza el resultado guardado. Las notas del informe indican la cuenta y la hora del análisis. |
| `inventag: error: --resume: needs state management ...` | La gestión de estado está desactivada. `--resume` con `--disable-state-management` se detiene con el código de salida 2. |

InvenTag reutiliza un resultado guardado solo cuando el comando tiene las mismas cuentas, regiones, servicios y filtros, y el resultado tiene como máximo `--resume-max-age-hours` de antigüedad (24 de forma predeterminada, 168 como máximo). Si no, vuelve a analizar la cuenta.

## Plantillas y archivos de configuración {#templates-and-configuration-files}

### Plantilla no válida {#invalid-template}

```text title="Salida"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

**Solución:** corrige el campo de la línea indicada. Ejecuta
`inventag templates validate <file>` para comprobar sin analizar.

### Nombre de plantilla desconocido {#unknown-template-name}

```text title="Salida"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

**Solución:** comprueba la ortografía con `inventag templates list`. Las plantillas
del proyecto deben estar en `.inventag/templates/` en la carpeta desde la que ejecutas.

### Archivo de cuentas no válido {#invalid-accounts-file}

```text title="Salida"
inventag - WARNING -    - Account 1: no credentials given; InvenTag will assume the --cross-account-role role (default InvenTagCrossAccountRole) in this account, or use the default credentials only if they belong to this account
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

**Solución:** pon los ID de cuenta entre comillas (`account_id: "123456789012"`), y da a
cada cuenta `profile_name`, `role_arn` o claves de acceso.

El propio archivo también puede estar mal. Cada uno de estos casos se detiene con el código de salida 1:

| El mensaje contiene | Causa |
|---|---|
| `the file is empty` | El archivo no tiene contenido. |
| `duplicate key 'accounts'` | Una clave está escrita dos veces. El mensaje indica la línea, por ejemplo `accounts file accounts.yaml:3: duplicate key 'accounts'`. |
| `the top level must be a mapping of key: value pairs, but the file holds a list` | El archivo empieza con una lista. Pon la lista bajo `accounts:`. |
| `unsupported file type '.txt'. Use .json, .yaml or .yml` | El nombre del archivo tiene otra extensión. |
| `the file is ... bytes; the maximum is 1048576 bytes` | El archivo supera 1 MiB. |
| `Accounts file not found` | La ruta es incorrecta. |

InvenTag advierte cuando otros usuarios pueden leer un archivo con `secret_access_key` o `session_token`: `<file> contains secret access keys and other users can read it (mode 0644). Run: chmod 600 <file>.`

### Otros mensajes de plantillas {#other-template-messages}

| El mensaje contiene | Solución |
|---|---|
| `did you mean '...'?` | Corrige la ortografía en la línea indicada. |
| `Put account IDs in quotes` | Escribe `account_id: "012345678901"`. |
| `must stay inside the template's folder` | Mueve el archivo referenciado junto a la plantilla, o a una subcarpeta. |
| `templates must not contain credentials` | Quita las claves de acceso; usa `profile_name` o `role_arn`. |
| `--template given two report templates` | Indica como máximo una plantilla de cada tipo. |

## Opciones que detienen la ejecución {#flags-that-stop-the-run}

Algunas opciones detienen la ejecución con el código de salida 2 y un mensaje `inventag: error: ...` antes de analizar nada:

- `--compliance-standard` dice que aún no está implementada.
- `--disable-production-safety` dice que la protección de solo lectura no se puede desactivar.
- Opciones que no pueden funcionar juntas:

```text
inventag: error: --accounts-file and --accounts-prompt: give one of them, not both.
inventag: error: --cross-account-role: a full role ARN names one account and cannot be combined with --accounts-file or --accounts-prompt. Give a role name to use in every account, or put role_arn in the accounts file.
inventag: error: --s3-kms-key-id: needs --s3-encryption aws:kms.
inventag: error: --resume: needs state management (saved results live in the state folder); remove --disable-state-management.
```

Un valor fuera de rango se detiene con el código de salida 1 y nombra la opción: `--max-concurrent-accounts must be a positive integer`, `--account-processing-timeout must be at least 60 seconds`, `--resume-max-age-hours must be above 0 and at most 168`. Un valor que no es un número en `--state-retention-days` o `--state-max-snapshots` se detiene con el código de salida 2: `expected a whole number or 'none'`.

Un valor de `--concurrency` que no es un número entero de 1 a 256 se detiene con el código de salida 2: `inventag: error: argument --concurrency: must be a whole number from 1 to 256, not '0'`.

Una ruta de `--audit-output`, `--log-file` o `--output-directory` en la que no se puede escribir detiene la ejecución al principio, antes de cualquier llamada a AWS, con un mensaje que nombra la opción y el código de salida 1.

Consulta [Estado de las funciones](../getting-started/status.md).

## Código de salida 3 {#exit-code-3}

No es un error de InvenTag. Una política de etiquetas encontró infracciones y la plantilla
de configuración tiene `fail_on_tag_violations: true`. Abre la hoja Tag Compliance o
el archivo JSON para ver qué recursos.

## Códigos de salida 4, 5 y 6 {#exit-codes-4-5-and-6}

Existen solo cuando los pides.

- **4:** una regla de grupo de seguridad abierta a internet está en `--risk-threshold` o por encima. El registro lista las reglas. Consulta [Análisis de red y seguridad](./network-and-security-analysis.md#fail-a-pipeline-on-risky-rules).
- **5:** `--fail-on-account-error` está activado y una cuenta no se pudo analizar o se quedó sin tiempo. El registro dice `N account(s) failed and --fail-on-account-error is set (exit code 5)`.
- **6:** `--fail-if-empty` está activado y no hay nada que informar. El registro dice `No resources in the report and --fail-if-empty is set (exit code 6)`.

Los informes se escriben primero. Si se aplica más de uno, el 5 va primero, después el 6, y luego el 3 y el 4. Consulta [Ejecuta InvenTag en CI/CD](./run-in-ci.md#exit-codes).

## Los informes se ven mal {#reports-look-wrong}

| Lo que ves | Causa y solución |
|---|---|
| Hojas muy anchas con columnas `raw_data.*` | Ese es el diseño predeterminado. Usa `--template standard-bom`. |
| Faltan las columnas de asignación de etiquetas | Las asignaciones de etiquetas añaden columnas solo al libro predeterminado. Con `--template`, usa `tag_columns`. Consulta [Archivos de configuración](../reference/configuration-files.md#tag-mappings). |
| Se ignora una descripción de servicio personalizada | Tu entrada reemplaza la descripción integrada; los servicios sin entrada en tu archivo conservan el texto integrado. Consulta [Archivos de configuración](../reference/configuration-files.md#service-descriptions). |
| No hay hojas de red ni de seguridad | Añade `--enable-network-analysis` o `--enable-security-analysis`, y asegúrate de que el análisis encontró VPC o grupos de seguridad. Las opciones no añaden nada con `--template`. Consulta [Análisis de red y seguridad](./network-and-security-analysis.md). |
| Faltan recursos de IAM, S3, CloudFront o Route 53 | `--account-services` o `--account-tags` los quitaron, o la identidad no tiene el permiso (busca una advertencia por servicio en el registro). La lista de regiones no importa: los servicios globales siempre se leen desde la región principal (`us-east-1`, o `cn-north-1` en China y `us-gov-west-1` en GovCloud). |
| Un recurso no muestra etiquetas, o aparece dos veces | Ejecuta con `--debug` y compara la columna ARN con el ARN de la consola de AWS. Notifica una discrepancia como problema (issue) indicando el servicio y el tipo de recurso. |
| No hay archivo de informe y el código de salida es 0 | El análisis no encontró nada, o `--account-services` o `--account-tags` lo quitaron todo. Busca `No resources to report` en el registro. Con `--template`, InvenTag escribe un informe que no lista ningún recurso. |
| Falta una cuenta en el informe | Fallaron sus credenciales o su rol, o se quedó sin tiempo. Las «Run notes» de la hoja `Summary` la nombran. Consulta [No se puede asumir un rol](#a-role-cannot-be-assumed) y [Una cuenta se queda sin tiempo](#an-account-runs-out-of-time). |
| Falta el informe de cambios | La primera ejecución no escribe ninguno. Además, necesita que la gestión de estado y la detección de diferencias estén activadas. Consulta [Sigue los cambios entre ejecuciones](./track-changes.md). |
| `Skipped unreadable snapshot 20261113_222847: Snapshot ... is corrupt or truncated (...). The file was not changed or deleted` | La última instantánea está dañada, así que InvenTag compara con la anterior. El archivo se queda en `state/`. Bórralo si no lo necesitas. |
| `Account 222222222222 left out of the comparison: the previous run could not scan it` | Una de las dos ejecuciones no pudo analizar esa cuenta. El informe de cambios la nombra en `accounts_not_compared`. |
| `Excel sheet name 'x' is not allowed or is already used; the sheet is called 'y'` | Excel no permite algunos caracteres en los nombres de hoja (se convierten en `-`), y los nombres deben ser únicos y de 31 caracteres como máximo. El informe sigue completo. |
| `Nothing to upload to s3://<bucket>/<prefix>/: the run wrote no report file because there are no resources to report.` | Se pasó `--s3-bucket`, pero el análisis no encontró recursos, o los filtros los quitaron todos, así que no se escribió ningún archivo. La ejecución termina con el código 1. Comprueba el análisis con la fila «No hay archivo de informe» de arriba. |
| `Reports written; the state snapshot or the change report had a problem (see the notes below)` | La instantánea de estado o su lista no se pudo guardar, o el informe de cambios falló. Las notas después del resumen nombran el problema y la carpeta que hay que revisar. La ejecución termina con el código 0. |
| Con `--template`, falta un formato de informe | Un formato que no se puede escribir no detiene el otro formato. El registro nombra el formato que falló, las «Run notes» del archivo escrito lo dicen, y la ejecución termina con el código 1. |
| Otro usuario no puede abrir `bom_output/` | Los archivos de salida son privados para el usuario que ejecutó InvenTag. Compártelos de forma deliberada. |

No verificado contra Microsoft Excel: las reglas de los nombres de hoja.

## Ruido que puedes ignorar {#noise-you-can-ignore}

Algunos mensajes parecen errores pero no cambian nada en tu informe.

| Mensaje | Por qué puedes ignorarlo |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'`` (con `--service-descriptions`) | La plantilla de descripción de VPC quiere un campo que el recurso no tiene. El informe no se ve afectado. |
| `No account specification method provided. Using default AWS credentials.` | No indicaste ninguna cuenta, así que InvenTag usó tus credenciales actuales. Es el caso normal. |
| `Cross-account role not usable for account ... trying default credentials` | InvenTag no pudo asumir el rol en esa cuenta e intentó con tus propias credenciales. Las usa solo si pertenecen a esa cuenta; si no, la cuenta se omite. Se registra una vez por cuenta, y solo con `--verbose`. |

## Problemas de instalación {#install-problems}

Consulta [Instala InvenTag](../getting-started/installation.md#fix-install-problems).

## ¿Sigues atascado? {#still-stuck}

Abre un [problema (issue)](https://github.com/habhabhabs/inventag-aws/issues) con el
comando que ejecutaste, la versión (`inventag --version`) y el mensaje. Quita los
ID y nombres de cuenta que no quieras compartir. No pegues nunca credenciales.
