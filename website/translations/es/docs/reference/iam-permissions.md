---
title: Permisos de IAM
description: Los permisos de AWS IAM que usa InvenTag, por qué se necesita cada uno, cuáles cuestan dinero y qué funciones requieren permisos adicionales.
sidebar_position: 3
---

# Permisos de IAM

**Para quién es:** revisas o escribes la política de IAM de InvenTag.

**Qué podrás hacer después de leerlo:** conceder exactamente lo que InvenTag necesita y
explicar cada permiso a un revisor.

Para la configuración paso a paso, consulta [Configura el acceso de solo lectura](../guides/read-only-access.md).

## Qué necesita cada ejecución {#what-every-run-needs}

| Permiso | Por qué | Notas |
|---|---|---|
| `sts:GetCallerIdentity` | Averigua a qué cuenta pertenecen las credenciales | AWS lo permite a todas las identidades; no necesitas concederlo. |
| `ec2:DescribeRegions` | Lista las regiones habilitadas y comprueba cada región que analizas | La comprobación se ejecuta para cada región, incluso con `--account-regions`. Una región que no la supera se omite con una advertencia. Si la llamada se deniega en todas las regiones, se analizan todas. |
| `account:ListRegions` | Lista las regiones habilitadas cuando `ec2:DescribeRegions` falla | No se llama cuando `ec2:DescribeRegions` funciona. |
| `tag:GetResources` | Encuentra recursos etiquetados (API Resource Groups Tagging) | El prefijo de IAM es `tag`, no `resourcegroupstaggingapi`. |
| `ce:GetCostAndUsage` | Encuentra servicios con gasto | **AWS cobra por solicitud.** Consulta los [precios de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/). Solicitudes a Cost Explorer en una ejecución: como máximo una por cada cuenta cuando la validación de facturación está activada (el valor predeterminado), y como máximo una más para toda la ejecución con `--enable-cost-analysis`. Una ejecución de una sola cuenta con ambas hace como máximo 2; con `--no-billing-validation` hace como máximo 1. Una solicitud limitada (throttled) se reintenta, hasta 10 intentos en total, y cada reintento es una solicitud más. AWS cobra cada solicitud. Si se deniega, el descubrimiento continúa sin datos de facturación. `--no-billing-validation` detiene las llamadas, y entonces puedes omitir este permiso. |
| `List*`, `Describe*`, `Get*` de cada servicio que quieras en el informe | Descubrimiento por servicio | Por ejemplo `s3:ListAllMyBuckets`, `s3:GetBucketTagging`, `lambda:ListFunctions`, `dynamodb:ListTables`. La política administrada de AWS `ReadOnlyAccess` los cubre. |

No verificado contra AWS real: `GetCallerIdentity` no necesita ningún permiso, el prefijo de IAM de la API Tagging es `tag`, y `ReadOnlyAccess` cubre las acciones List, Describe y Get.

No verificado contra AWS real: el número de solicitudes que AWS factura, y si AWS factura un reintento.

## Qué necesitan algunas funciones {#what-some-features-need}

| Función | Permiso adicional |
|---|---|
| Analizar otras cuentas mediante un rol | `sts:AssumeRole` sobre esos roles, y una política de confianza en cada cuenta que permita tu identidad |
| `--enable-cost-analysis` | `pricing:GetProducts` y `cloudwatch:GetMetricStatistics` (ambos están en la política del repositorio). También hace como máximo una solicitud `ce:GetCostAndUsage` más para toda la ejecución. |
| `--finops-cost-allocation` | `ce:ListCostAllocationTags` (en la política del repositorio) y `ce:GetCostAndUsage`. Como máximo 7 solicitudes a Cost Explorer por cuenta, cada una con las credenciales propias de esa cuenta. |
| `--s3-bucket` | `s3:PutObject` sobre ese bucket (y `kms:GenerateDataKey` sobre la clave si usas `aws:kms`) |

No verificado contra AWS real: estos son los únicos permisos adicionales que necesitan la asunción de roles, el análisis de costes y la carga.

Según la lista provisional con la que el proyecto hace sus pruebas, la política administrada de AWS `ReadOnlyAccess` incluye todas las acciones de la política del repositorio, pero no incluye `sts:AssumeRole`, `s3:PutObject` ni `kms:GenerateDataKey`. La lista es provisional hasta que el proyecto tenga una copia sin modificar de la política de AWS. No verificado contra AWS real: que la lista sea lo que `ReadOnlyAccess` permite hoy. Consulta [Ejecutar solo con ReadOnlyAccess](../guides/read-only-access.md#run-with-only-readonlyaccess).

`--finops-checks` no necesita ningún permiso adicional: las comprobaciones leen
las filas que el escaneo ya tiene y no hacen ninguna llamada a AWS.

## Cuando se rechaza una acción {#when-an-action-is-refused}

Cuando una ejecución no tiene permiso para usar una acción de IAM, las notas de la ejecución tienen una línea `Permissions:` por cada cuenta. La línea nombra cada acción y dice qué le falta al informe. El archivo de `--audit-output` tiene la misma lista en la clave `permissions_denied`. Una ejecución a la que no se le deniega nada no imprime ni escribe nada nuevo. Los campos y un ejemplo están en [Ejecutar solo con ReadOnlyAccess](../guides/read-only-access.md#the-permissions-line-and-permissions_denied).

## Lo que InvenTag nunca necesita {#what-inventag-never-needs}

Cualquier acción de escritura, creación, eliminación o etiquetado, salvo `s3:PutObject` en un
bucket de informes si subes informes. Si un revisor encuentra otra en tu
política de InvenTag, quítala. La protección de solo lectura de InvenTag bloquea de todos modos
esas llamadas. Dos funciones de biblioteca del código pueden escribir en
AWS cuando se llaman desde tu propio código Python (la CLI no las llama); consulta
[Estado de las funciones](../getting-started/status.md#security-notes).

## La política del repositorio {#the-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` se genera a partir de una lista explícita
de 123 acciones de lectura del código (`inventag/security/iam_policy.py`), así que
coincide con lo que InvenTag llama. Incluye `tag:GetResources`,
`ce:GetCostAndUsage`, `pricing:GetProducts` y
`lambda:GetFunctionConfiguration`. Una segunda instrucción permite `apigateway:GET`
solo en `/restapis`, `/domainnames` y `/usageplans`, así que no se pueden leer los
valores de las claves de API.

No verificado contra AWS real: `apigateway:GET` en estas tres rutas no devuelve valores de claves de API.

v1.2.0 añadió estas 17 acciones para los servicios nuevos y la alternativa de regiones:
`account:ListRegions`, `appsync:ListGraphqlApis`, `athena:ListWorkGroups`, `autoscaling:DescribeAutoScalingGroups`, `backup:ListBackupVaults`, `cognito-idp:ListUserPools`, `ec2:DescribeNetworkInterfaces`, `ecr:DescribeRepositories`, `elasticbeanstalk:DescribeApplications`, `elasticbeanstalk:DescribeEnvironments`, `elasticfilesystem:DescribeFileSystems`, `elasticmapreduce:ListClusters`, `es:ListDomainNames`, `firehose:ListDeliveryStreams`, `kafka:ListClustersV2`, `redshift-serverless:ListNamespaces`, `redshift-serverless:ListWorkgroups`. También
quitó `cloudtrail:LookupEvents`, que el comando `inventag` no llama.

Su instrucción `OptionalS3ReportUpload` permite `s3:PutObject`, pero solo con
cifrado del lado del servidor. Pon el nombre de tu bucket en lugar de
`YOUR-REPORTS-BUCKET-NAME`, o quita la instrucción si no usas
`--s3-bucket`. Si usas otro `--s3-key-prefix`, cambia también el recurso.

No verificado contra AWS real: que la instrucción permita la carga solo con cifrado del lado del servidor.

## Comprueba una política {#check-a-policy}

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Los dos primeros deberían ser `allowed`. `s3:PutObject` se permite solo si conservaste la instrucción `OptionalS3ReportUpload` con el nombre de tu bucket.

No verificado contra AWS real: la salida de `aws iam simulate-principal-policy` para esta política.
