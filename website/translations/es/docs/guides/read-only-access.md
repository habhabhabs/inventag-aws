---
title: Configurar el acceso de solo lectura
description: Da a InvenTag una identidad de AWS de solo lectura y mínimo privilegio con IAM Identity Center o un rol de IAM, y comprueba que no puede cambiar nada.
sidebar_position: 2
slug: /user-guides/production-safety
---

# Configurar el acceso de solo lectura

**Para quién es:** quien crea la identidad de AWS con la que se ejecuta
InvenTag.

**Qué podrás hacer después de leerlo:** crear una identidad de solo lectura
para InvenTag y confirmar que no puede cambiar tus recursos.

## Por qué importa {#why-this-matters}

InvenTag solo necesita acceso de lectura, más `s3:PutObject` si subes informes con `--s3-bucket`. Tiene su propia protección de solo lectura, que
bloquea toda llamada a AWS que no sea de lectura antes de enviarla. Tu política
de IAM es una segunda red de seguridad, independiente: si un error llegara a
saltarse la protección, AWS seguiría rechazando la llamada. No des a InvenTag
nada más de lo que necesita.

No verificado contra AWS real: que una política de IAM de solo lectura rechace una llamada que se salta la protección.

## Opción 1: ReadOnlyAccess administrada por AWS más tres extras (la más sencilla) {#option-1-aws-managed-readonlyaccess-plus-three-extras-simplest}

1. Asocia la política administrada por AWS `ReadOnlyAccess`.
2. Añade esta política insertada para las llamadas que `ReadOnlyAccess` puede
   no cubrir:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvenTagExtras",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "ce:GetCostAndUsage",
        "ec2:DescribeRegions"
      ],
      "Resource": "*"
    }
  ]
}
```

| Acción | Por qué la necesita InvenTag |
|---|---|
| `tag:GetResources` | Encuentra los recursos etiquetados mediante la API Resource Groups Tagging (su prefijo de IAM es `tag`). |
| `ce:GetCostAndUsage` | Encuentra los servicios que tienen gasto. |
| `ec2:DescribeRegions` | Lista las regiones habilitadas en la cuenta. |

AWS cobra por cada solicitud de Cost Explorer: consulta los [precios de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

InvenTag también llama a `account:ListRegions`, pero solo cuando `ec2:DescribeRegions` falla, para leer las regiones habilitadas.
Añádela si quieres ese respaldo.

Añade `pricing:GetProducts` solo si usas `--enable-cost-analysis` (también
llama a `cloudwatch:GetMetricStatistics`, que `ReadOnlyAccess` cubre), y
`s3:PutObject` en tu bucket de informes si usas `--s3-bucket`.

Añade `ce:ListCostAllocationTags` si usas `--finops-cost-allocation`. No
verificado contra AWS real: si `ReadOnlyAccess` la cubre.

Para ejecutar solo con `ReadOnlyAccess`, consulta [Ejecutar solo con ReadOnlyAccess](#run-with-only-readonlyaccess).

`ReadOnlyAccess` es amplia: puede leer datos como los listados de objetos de S3
y parte de la configuración que InvenTag nunca consulta. Si eso es demasiado
para tu organización, usa la opción 2.

No verificado contra AWS: qué permite hoy la política administrada `ReadOnlyAccess` y cuáles de estas llamadas cubre.

## Opción 2: la política más acotada del repositorio {#option-2-the-narrower-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` lista 123 acciones de lectura
concretas, entre ellas `tag:GetResources`, `ce:GetCostAndUsage` y
`pricing:GetProducts`, y `apigateway:GET` solo para metadatos de API (no claves de API). Se genera a partir de la misma lista que usa el código,
así que coincide con lo que InvenTag llama. Incluye las acciones de los servicios que InvenTag lista con sus propias llamadas,
y `ec2:DescribeRouteTables` y `ec2:DescribeNetworkInterfaces` para el
[análisis de red y seguridad](./network-and-security-analysis.md#permissions).
Si copiaste una versión antigua del archivo, cópialo de nuevo. Una acción que falte no detiene la ejecución, pero falta ese servicio o detalle.

No verificado contra AWS real: que la instrucción `apigateway:GET` mantenga fuera de alcance los valores de las claves de API.

Su instrucción `OptionalS3ReportUpload` permite `s3:PutObject` con cifrado del
lado del servidor, para `--s3-bucket`. Sustituye `YOUR-REPORTS-BUCKET-NAME` por
tu bucket, o elimina la instrucción si no subes informes.

No verificado contra AWS real: que la instrucción permita la carga solo con cifrado del lado del servidor.

Cuando falta una acción de listado, InvenTag registra una advertencia para ese servicio y continúa sin sus recursos:

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Cuando falta una acción para un detalle de un recurso, el descubrimiento continúa y deja ese detalle vacío.

## Ejecutar solo con ReadOnlyAccess {#run-with-only-readonlyaccess}

Puedes adjuntar a la identidad solo la política administrada de AWS `ReadOnlyAccess` y no añadir nada más. Esta sección dice qué funciona, qué no funciona y qué imprime InvenTag cuando AWS rechaza una acción.

La lista de políticas de esta sección es PROVISIONAL. El proyecto prueba InvenTag con una lista de las acciones de `ReadOnlyAccess` que escribió a mano a partir de la página de referencia de AWS (versión de la política v192, 13 de noviembre de 2026). La lista sigue siendo provisional hasta que el proyecto tenga una copia sin modificar de la política de AWS. No verificado contra AWS real: que la lista sea lo que `ReadOnlyAccess` permite hoy, y un análisis con solo `ReadOnlyAccess` adjunta.

### Qué funciona {#what-works}

Según la lista provisional, `ReadOnlyAccess` incluye las 123 acciones de lectura de `config/defaults/iam-policy-read-only.json` y `apigateway:GET`. Entre ellas están `tag:GetResources`, `ce:GetCostAndUsage` y `ec2:DescribeRegions`, así que los tres extras de la opción 1 son una salvaguarda y no una necesidad.

En las pruebas, un análisis de una cuenta con solo estas acciones termina con el código 0. AWS no rechaza ninguna llamada. El registro no tiene la advertencia `No permission for`, y cada recurso que creó la prueba está en el informe. Esto se cumple con `--create-excel --create-word`, y también cuando añades `--enable-network-analysis`, `--enable-security-analysis`, `--enable-cost-analysis` y la validación de facturación.

### Tres acciones que ReadOnlyAccess no incluye {#three-actions-that-readonlyaccess-does-not-include}

| Acción | Solo se necesita para | Qué pasa sin ella |
|---|---|---|
| `sts:AssumeRole` | Analizar otras cuentas mediante un rol (`role_arn` o `--cross-account-role`) | Esa cuenta falla. InvenTag analiza las demás cuentas. La ejecución termina con el código 0, o con el código 5 si pasas `--fail-on-account-error`. |
| `s3:PutObject` | Subir los informes con `--s3-bucket` | La subida falla y los informes se quedan en la carpeta de salida local. La ejecución termina con el código 1. |
| `kms:GenerateDataKey` | Subir los informes con `--s3-encryption aws:kms` y una clave KMS | No probado. |

No verificado contra AWS real: que un `kms:GenerateDataKey` rechazado detenga la subida, y qué acción nombra entonces S3. Con un AWS simulado, la subida fallida se nombra solo como `s3:PutObject`.

### Qué más puede rechazar una llamada {#what-else-can-refuse-a-call}

Una identidad con `ReadOnlyAccess` todavía puede recibir un rechazo. Estas son las causas que InvenTag no puede distinguir entre sí:

- una política de control de servicios o un límite de permisos
- la política de un recurso, por ejemplo la política de una clave KMS o la de un bucket
- una región o un servicio que no está habilitado en la cuenta
- una versión posterior de `ReadOnlyAccess`, porque AWS cambia la política

No verificado contra AWS real: estas causas, y cuáles de ellas AWS informa como acceso denegado.

La política del repositorio de la opción 2 es la elección con menos derechos. `ReadOnlyAccess` es más amplia de lo que InvenTag necesita, por ejemplo `s3:Get*`. La protección de solo lectura sigue rechazando las llamadas que devuelven el contenido de objetos o secretos, sea cual sea lo que permita la política.

### Cuando se rechaza una acción {#when-an-action-is-refused}

Ninguna acción rechazada detiene la ejecución. Esto es lo que hace la ejecución:

| Rechazada | Qué hace la ejecución |
|---|---|
| `sts:AssumeRole` para una cuenta | La cuenta falla con su motivo. Las demás cuentas se analizan. |
| `ec2:DescribeRegions` | InvenTag pregunta a `account:ListRegions`. Si también falla, analiza todas las regiones. |
| Un listado de un servicio | Una advertencia para el servicio. Las notas de la ejecución dicen `Not read`. El siguiente informe de cambios deja fuera ese listado. |
| Una llamada de detalle de un recurso | La fila se queda y el detalle está vacío. Una nota de la ejecución cuenta los recursos. |
| `tag:GetResources` | Una advertencia. El análisis sigue con los listados de los servicios. |
| `ce:GetCostAndUsage` | Una advertencia. Se omiten las comprobaciones de facturación. |
| `pricing:GetProducts` con `--enable-cost-analysis` | Una advertencia. Faltan las estimaciones de costes. |
| `s3:PutObject` con `--s3-bucket` | La subida falla. Código de salida 1. |

Cuando solo se permite `sts:GetCallerIdentity`, la ejecución termina. No escribe ningún informe ni ninguna instantánea, y el registro dice `No resources to report: nothing could be read`. El código de salida es 0. Con `--fail-on-account-error`, una cuenta cuyos listados se rechazaron todos sigue contando como analizada y la ejecución termina con el código 0. Para que un trabajo de CI falle cuando no se pudo leer nada, añade `--fail-if-empty`.

### La línea Permissions y permissions_denied {#the-permissions-line-and-permissions_denied}

Cuando una ejecución no tiene permiso para usar una acción de IAM, las notas de la ejecución tienen una línea por cada cuenta. La línea está en la consola y en las «Run notes» del informe de Excel. Nombra cada acción, dice qué le falta al informe y dice si `ReadOnlyAccess` incluye la acción. Una ejecución a la que no se le deniega nada no imprime esa línea. Esta es la línea de un rol que no se puede asumir (ejemplo de una ejecución sin conexión):

```text
Permissions: 1 action(s) were not allowed for account 222222222222: sts:AssumeRole. Effect: the account was not scanned. sts:AssumeRole is not in ReadOnlyAccess; it is needed only for scanning other accounts through a role.
```

La línea tiene palabras propias de InvenTag. No tiene texto del error de AWS. Una llamada de la que InvenTag no conoce la acción de IAM se nombra por su nombre de API, con las palabras `(IAM action not known to InvenTag)`.

La subida de los informes con `--s3-bucket` usa las credenciales predeterminadas, no las de una cuenta analizada. Cuando S3 la rechaza, la línea no nombra ninguna cuenta. Nombra la identidad que sube los informes (ejemplo de las pruebas):

```text
Permissions: 1 action(s) were not allowed for the identity that uploads the reports (the default credentials): s3:PutObject. Effect: the reports were not uploaded. s3:PutObject is not in ReadOnlyAccess; it is needed only for uploading the reports (--s3-bucket).
```

Con `--audit-output`, el archivo también tiene la clave `permissions_denied`. La clave solo está cuando se denegó algo. Cada entrada tiene estos campos:

```json
{
  "permissions_denied": [
    {
      "account": "123456789012",
      "action": "s3:GetBucketLocation",
      "service": "s3",
      "operation": "GetBucketLocation",
      "regions": ["us-east-1"],
      "kind": "detail"
    }
  ]
}
```

| Campo | Significado |
|---|---|
| `account` | El ID de la cuenta. Vacío para el tipo `upload`: la subida usa las credenciales predeterminadas, no las de una cuenta analizada. |
| `action` | La acción de IAM, o `null` cuando InvenTag no la conoce. |
| `service`, `operation` | Los nombres de API de AWS de la llamada rechazada. |
| `regions` | Las regiones en las que se rechazó la llamada. Vacío en una entrada sin región, por ejemplo el tipo `role`. |
| `kind` | `role`, `listing`, `detail`, `tagging`, `billing`, `pricing`, `analysis` o `upload`. |

La lista está ordenada por cuenta y acción. InvenTag no hace ninguna llamada extra a AWS para construirla. No verificado contra AWS real: las acciones nombradas son las de las tablas propias de InvenTag, y un rechazo por una política de control de servicios o por un límite de permisos también se muestra como la acción.

La línea no nombra `ec2:DescribeRegions` ni `account:ListRegions`. Consulta [Estado de las funciones](../getting-started/status.md#when-a-run-goes-wrong).

## Qué bloquea la protección de solo lectura {#what-the-read-only-guard-blocks}

InvenTag comprueba cada llamada a AWS del proceso antes de enviarla. Solo permite operaciones cuyo nombre empieza por `List`, `Describe`, `Get`, `Head`,
`Lookup`, `Search` o `BatchGet`, más `sts:AssumeRole` para llegar a otras cuentas. No se puede desactivar.

Algunas operaciones parecen lecturas pero devuelven secretos o datos de clientes. La protección también las bloquea, de modo que una política amplia no pueda exponerlos a través de InvenTag.
Ejemplos: `secretsmanager:GetSecretValue`, `ssm:GetParameter`, `s3:GetObject`, `dynamodb:GetItem`, `lambda:GetFunction` (devuelve un enlace de descarga del código),
`cloudformation:GetTemplate`, `ec2:GetLaunchTemplateData`, `glue:GetConnection` y los resultados de consultas de Athena.
También bloquea las claves de API con sus valores y `ec2:DescribeInstanceAttribute` para los datos de usuario, y comprueba las URL prefirmadas y los tokens de autenticación de bases de datos con las mismas reglas.
La protección conoce las operaciones por su nombre. Una operación que añade un SDK de AWS más nuevo se permite cuando su nombre empieza como una lectura, hasta que una versión de InvenTag la nombra. Comprueba un nombre con `inventag --validate-operations <service>:<Operation>`. Cuando la respuesta depende de un parámetro, nombra la regla: `apigateway:GetApiKeys` muestra `ALLOWED` con `blocked when includeValues=true`, y `ec2:DescribeInstanceAttribute` muestra `ALLOWED` con `blocked when Attribute=userdata`. La protección bloquea estas llamadas solo cuando se hacen con ese parámetro.

Los perfiles de IAM Identity Center (SSO) y de identidad web funcionan con la protección activa. La protección deja que el paso de inicio de sesión cambie un token por credenciales, y nada más.

No verificado contra AWS IAM Identity Center: el inicio de sesión con un perfil real de SSO o de identidad web.

Dos funciones de la biblioteca de Python pueden escribir en AWS cuando las llamas desde tu propio código. El comando `inventag` nunca las llama, y la protección las bloquea en una ejecución del comando.
`CredentialManager.setup_cross_account_roles()` crea roles de IAM y solo se ejecuta con `allow_iam_writes=True`.
La función auxiliar de ciclo de vida de S3 cambia las reglas del bucket y solo se ejecuta con `allow_bucket_writes=True`.

## Con IAM Identity Center (SSO) {#with-iam-identity-center-sso}

Crea un conjunto de permisos que contenga la política y asígnalo a cada cuenta
que quieras analizar:

```bash
aws sso-admin create-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --name InvenTagReadOnly \
  --description "Read-only access for InvenTag"

aws sso-admin attach-managed-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

aws sso-admin put-inline-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --inline-policy file://inventag-extras.json
```

No verificado contra AWS real: los comandos `aws sso-admin` y el conjunto de permisos que crean.

No verificado contra AWS: qué permite hoy la política administrada `ReadOnlyAccess` y cuáles de estas llamadas cubre.

Después inicia sesión con `aws sso login --profile <profile>` y ejecuta
InvenTag con `AWS_PROFILE=<profile>`.

No verificado contra la AWS CLI: los comandos de inicio de sesión de esta sección.

## Con un rol de IAM en cada cuenta {#with-an-iam-role-in-each-account}

Para análisis de muchas cuentas, crea un rol con el mismo nombre, por ejemplo
`InvenTagReadOnly`, en cada cuenta. Asocia la política y deja que solo tu
identidad de análisis lo asuma. Una política de confianza para eso se ve así:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::999999999999:role/InvenTagScanner" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Sustituye `999999999999:role/InvenTagScanner` por la identidad que ejecuta
InvenTag. La propia identidad de análisis solo necesita `sts:AssumeRole` sobre
esos roles.

No verificado contra AWS real: que la política de confianza y `sts:AssumeRole` bastan por sí solas para el análisis.

## Comprueba que no puede escribir {#check-that-it-cannot-write}

Usa el simulador de políticas de IAM para confirmar que se deniega una
escritura:

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Ambas deberían mostrar `implicitDeny` o `explicitDeny`.

No verificado contra AWS real: el resultado del simulador de políticas para estas dos acciones.

También puedes preguntar a la protección de InvenTag qué operaciones
permitiría (ejemplo de salida de una ejecución sin conexión):

```text title="Salida"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
```

```bash title="Terminal"
echo $?
```

```text title="Salida"
1
```

Para ver qué llamó una ejecución real, añade `--audit-output audit.json`. Un
extracto de una ejecución sin conexión (datos de ejemplo):

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 96,
  "allowed_calls": 96,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## Después de un incidente de seguridad {#after-a-security-incident}

Si sospechas que tus credenciales o una dependencia se vieron comprometidas,
rota o revoca las credenciales que usó InvenTag, revisa AWS CloudTrail en busca
de llamadas inesperadas de esa identidad y mantén la identidad de solo lectura.
Más información en la página de [Seguridad](../security/index.md).

## Siguientes pasos {#next-steps}

- [Referencia de permisos de IAM](../reference/iam-permissions.md)
- [Analizar varias cuentas](./scan-multiple-accounts.md)
