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
| `ce:GetCostAndUsage` | Encuentra servicios con gasto | **AWS cobra por solicitud.** En nuestra prueba sin conexión, una ejecución hizo dos por cada cuenta. Si se deniega, el descubrimiento continúa sin datos de facturación. `--no-billing-validation` detiene las llamadas, y entonces puedes omitir este permiso. |
| `List*`, `Describe*`, `Get*` de cada servicio que quieras en el informe | Descubrimiento por servicio | Por ejemplo `s3:ListAllMyBuckets`, `s3:GetBucketTagging`, `lambda:ListFunctions`, `dynamodb:ListTables`. La política administrada de AWS `ReadOnlyAccess` los cubre. |

## Qué necesitan algunas funciones {#what-some-features-need}

| Función | Permiso adicional |
|---|---|
| Analizar otras cuentas mediante un rol | `sts:AssumeRole` sobre esos roles, y una política de confianza en cada cuenta que permita tu identidad |
| `--enable-cost-analysis` | `pricing:GetProducts` y `cloudwatch:GetMetricStatistics` (ambos están en la política del repositorio) |
| `--s3-bucket` | `s3:PutObject` sobre ese bucket (y `kms:GenerateDataKey` sobre la clave si usas `aws:kms`) |

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

v1.2.0 añadió estas 17 acciones para los servicios nuevos y la alternativa de regiones:
`account:ListRegions`, `appsync:ListGraphqlApis`, `athena:ListWorkGroups`, `autoscaling:DescribeAutoScalingGroups`, `backup:ListBackupVaults`, `cognito-idp:ListUserPools`, `ec2:DescribeNetworkInterfaces`, `ecr:DescribeRepositories`, `elasticbeanstalk:DescribeApplications`, `elasticbeanstalk:DescribeEnvironments`, `elasticfilesystem:DescribeFileSystems`, `elasticmapreduce:ListClusters`, `es:ListDomainNames`, `firehose:ListDeliveryStreams`, `kafka:ListClustersV2`, `redshift-serverless:ListNamespaces`, `redshift-serverless:ListWorkgroups`.

Su instrucción `OptionalS3ReportUpload` permite `s3:PutObject`, pero solo con
cifrado del lado del servidor. Pon el nombre de tu bucket en lugar de
`YOUR-REPORTS-BUCKET-NAME`, o quita la instrucción si no usas
`--s3-bucket`.

## Comprueba una política {#check-a-policy}

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Los dos primeros deberían ser `allowed`, y `s3:PutObject` debería estar denegado.
