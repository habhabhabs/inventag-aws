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

InvenTag solo necesita leer. Tiene su propia protección de solo lectura, que
bloquea toda llamada a AWS que no sea de lectura antes de enviarla. Tu política
de IAM es una segunda red de seguridad, independiente: si un error llegara a
saltarse la protección, AWS seguiría rechazando la llamada. No des a InvenTag
nada más de lo que necesita.

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
| `ce:GetCostAndUsage` | Encuentra los servicios que tienen gasto. AWS cobra por solicitud. |
| `ec2:DescribeRegions` | Lista las regiones habilitadas en la cuenta. |

InvenTag también llama a `account:ListRegions`, pero solo cuando `ec2:DescribeRegions` falla, para leer las regiones habilitadas.
Añádela si quieres ese respaldo.

Añade `pricing:GetProducts` solo si usas `--enable-cost-analysis` (también
llama a `cloudwatch:GetMetricStatistics`, que `ReadOnlyAccess` cubre), y
`s3:PutObject` en tu bucket de informes si usas `--s3-bucket`.

`ReadOnlyAccess` es amplia: puede leer datos como los listados de objetos de S3
y parte de la configuración que InvenTag nunca consulta. Si eso es demasiado
para tu organización, usa la opción 2.

## Opción 2: la política más acotada del repositorio {#option-2-the-narrower-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` lista 122 acciones de lectura
concretas, entre ellas `tag:GetResources`, `ce:GetCostAndUsage` y
`pricing:GetProducts`, y `apigateway:GET` solo para metadatos de API (no claves de API). Se genera a partir de la misma lista que usa el código,
así que coincide con lo que InvenTag llama. Incluye las acciones de los servicios que InvenTag lista con sus propias llamadas,
y `ec2:DescribeRouteTables` y `ec2:DescribeNetworkInterfaces` para el
[análisis de red y seguridad](./network-and-security-analysis.md#permissions).
Si copiaste una versión antigua del archivo, cópialo de nuevo. Una acción que falte no detiene la ejecución, pero falta ese servicio o detalle.

Su instrucción `OptionalS3ReportUpload` permite `s3:PutObject` con cifrado del
lado del servidor, para `--s3-bucket`. Sustituye `YOUR-REPORTS-BUCKET-NAME` por
tu bucket, o elimina la instrucción si no subes informes.

Cuando falta una acción de listado, InvenTag registra una advertencia para ese servicio y continúa sin sus recursos:

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Cuando falta una acción para un detalle de un recurso, el descubrimiento continúa y deja ese detalle vacío.

## Qué bloquea la protección de solo lectura {#what-the-read-only-guard-blocks}

InvenTag comprueba cada llamada a AWS del proceso antes de enviarla. Solo permite operaciones cuyo nombre empieza por `List`, `Describe`, `Get`, `Head`,
`Lookup`, `Search` o `BatchGet`, más `sts:AssumeRole` para llegar a otras cuentas. No se puede desactivar.

Algunas operaciones parecen lecturas pero devuelven secretos o datos de clientes. La protección también las bloquea, de modo que una política amplia no pueda exponerlos a través de InvenTag.
Ejemplos: `secretsmanager:GetSecretValue`, `ssm:GetParameter`, `s3:GetObject`, `dynamodb:GetItem`, `lambda:GetFunction` (devuelve un enlace de descarga del código),
`cloudformation:GetTemplate`, `ec2:GetLaunchTemplateData`, `glue:GetConnection` y los resultados de consultas de Athena.
También bloquea las claves de API con sus valores y `ec2:DescribeInstanceAttribute` para los datos de usuario, y comprueba las URL prefirmadas y los tokens de autenticación de bases de datos con las mismas reglas.
Comprueba un nombre con `inventag --validate-operations <service>:<Operation>`.

Los perfiles de IAM Identity Center (SSO) y de identidad web funcionan con la protección activa. La protección deja que el paso de inicio de sesión cambie un token por credenciales, y nada más.

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

Después inicia sesión con `aws sso login --profile <profile>` y ejecuta
InvenTag con `AWS_PROFILE=<profile>`.

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
