---
title: Autorisations IAM
description: "Les autorisations AWS IAM d’InvenTag : pourquoi chacune est nécessaire, lesquelles coûtent de l’argent et quelles fonctionnalités en exigent d’autres."
sidebar_position: 3
---

# Autorisations IAM

**À qui s’adresse cette page :** vous examinez ou rédigez la politique IAM d’InvenTag.

**Ce que vous saurez faire après lecture :** accorder exactement ce dont InvenTag a besoin et
expliquer chaque autorisation à une personne chargée de la relecture.

Pour une configuration pas à pas, voir [Configurer un accès en lecture seule](../guides/read-only-access.md).

## Ce dont chaque exécution a besoin {#what-every-run-needs}

| Autorisation | Pourquoi | Remarques |
|---|---|---|
| `sts:GetCallerIdentity` | Détermine à quel compte appartiennent les identifiants | AWS l’autorise pour toutes les identités ; vous n’avez pas besoin de l’accorder. |
| `ec2:DescribeRegions` | Liste les régions activées et vérifie chaque région que vous analysez | La vérification s’exécute pour chaque région, même avec `--account-regions`. Une région qui échoue à cette vérification est ignorée avec un avertissement. Si l’appel est refusé dans toutes les régions, toutes les régions sont analysées. |
| `account:ListRegions` | Liste les régions activées quand `ec2:DescribeRegions` échoue | N’est pas appelé quand `ec2:DescribeRegions` fonctionne. |
| `tag:GetResources` | Trouve les ressources étiquetées (API Resource Groups Tagging) | Le préfixe IAM est `tag`, et non `resourcegroupstaggingapi`. |
| `ce:GetCostAndUsage` | Repère les services qui génèrent des dépenses | **AWS facture chaque requête.** Voir les [tarifs de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/). Requêtes Cost Explorer d’une exécution : au plus une par compte quand la validation de facturation est active (par défaut), et au plus une de plus pour toute l’exécution avec `--enable-cost-analysis`. Une exécution sur un seul compte avec les deux en fait au plus 2 ; avec `--no-billing-validation`, elle en fait au plus 1. Une requête limitée (throttled) est réessayée, jusqu’à 10 tentatives en tout, et chaque nouvel essai est une requête de plus. AWS facture chaque requête. En cas de refus, la découverte continue sans données de facturation. `--no-billing-validation` arrête ces appels, et vous pouvez alors omettre cette autorisation. |
| `List*`, `Describe*`, `Get*` pour chaque service que vous voulez dans le rapport | Découverte par service | Par exemple `s3:ListAllMyBuckets`, `s3:GetBucketTagging`, `lambda:ListFunctions`, `dynamodb:ListTables`. La politique gérée AWS `ReadOnlyAccess` les couvre. |

Non vérifié sur un vrai AWS : `GetCallerIdentity` ne nécessite aucune autorisation, le préfixe IAM de l’API Tagging est `tag`, et `ReadOnlyAccess` couvre les actions List, Describe et Get.

Non vérifié sur un vrai AWS : le nombre de requêtes qu’AWS facture, et si AWS facture un nouvel essai.

## Ce dont certaines fonctionnalités ont besoin {#what-some-features-need}

| Fonctionnalité | Autorisation supplémentaire |
|---|---|
| Analyse d’autres comptes via un rôle | `sts:AssumeRole` sur ces rôles, et une politique d’approbation dans chaque compte qui autorise votre identité |
| `--enable-cost-analysis` | `pricing:GetProducts` et `cloudwatch:GetMetricStatistics` (les deux figurent dans la politique du dépôt). Il fait aussi au plus une requête `ce:GetCostAndUsage` de plus pour toute l’exécution. |
| `--s3-bucket` | `s3:PutObject` sur ce bucket (et `kms:GenerateDataKey` sur la clé si vous utilisez `aws:kms`) |

Non vérifié sur un vrai AWS : ce sont les seules autorisations supplémentaires dont ont besoin l’assomption de rôle, l’analyse des coûts et le téléversement.

D’après la liste provisoire avec laquelle le projet fait ses tests, la politique gérée AWS `ReadOnlyAccess` inclut toutes les actions de la politique du dépôt, mais elle n’inclut pas `sts:AssumeRole`, `s3:PutObject` ni `kms:GenerateDataKey`. La liste reste provisoire tant que le projet n’a pas une copie brute de la politique AWS. Non vérifié sur un vrai AWS : que la liste soit ce que `ReadOnlyAccess` autorise aujourd’hui. Voir [Exécuter avec ReadOnlyAccess seul](../guides/read-only-access.md#run-with-only-readonlyaccess).

`--finops-checks` n’exige aucune autre permission : les contrôles lisent les
lignes que l’analyse a déjà et ne font aucun appel AWS.

## Quand une action est refusée {#when-an-action-is-refused}

Quand une exécution n’a pas le droit d’utiliser une action IAM, les notes d’exécution ont une ligne `Permissions:` par compte. La ligne nomme chaque action et dit ce qui manque au rapport. Le fichier de `--audit-output` a la même liste dans la clé `permissions_denied`. Une exécution à laquelle rien n’est refusé n’affiche ni n’écrit rien de nouveau. Les champs et un exemple sont dans [Exécuter avec ReadOnlyAccess seul](../guides/read-only-access.md#the-permissions-line-and-permissions_denied).

## Ce dont InvenTag n’a jamais besoin {#what-inventag-never-needs}

Toute action d’écriture, de création, de suppression ou d’étiquetage, hormis `s3:PutObject` sur un bucket
de rapports si vous téléversez des rapports. Si une personne chargée de la relecture en trouve une autre dans
votre politique InvenTag, supprimez-la. La protection en lecture seule d’InvenTag bloque de toute façon ces
appels. Deux fonctions de bibliothèque du code peuvent écrire dans
AWS lorsqu’elles sont appelées depuis votre propre code Python (la CLI ne les appelle pas) ; voir
[État des fonctionnalités](../getting-started/status.md#security-notes).

## La politique du dépôt {#the-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` est générée à partir d’une liste explicite
de 122 actions de lecture dans le code (`inventag/security/iam_policy.py`), si bien qu’elle
correspond à ce qu’InvenTag appelle. Elle inclut `tag:GetResources`,
`ce:GetCostAndUsage`, `pricing:GetProducts` et
`lambda:GetFunctionConfiguration`. Une seconde instruction n’autorise `apigateway:GET`
que sur `/restapis`, `/domainnames` et `/usageplans`, si bien que les valeurs des clés
d’API ne peuvent pas être lues.

Non vérifié sur un vrai AWS : `apigateway:GET` sur ces trois chemins ne renvoie aucune valeur de clé d’API.

v1.2.0 a ajouté ces 17 actions pour les nouveaux services et le repli des régions :
`account:ListRegions`, `appsync:ListGraphqlApis`, `athena:ListWorkGroups`, `autoscaling:DescribeAutoScalingGroups`, `backup:ListBackupVaults`, `cognito-idp:ListUserPools`, `ec2:DescribeNetworkInterfaces`, `ecr:DescribeRepositories`, `elasticbeanstalk:DescribeApplications`, `elasticbeanstalk:DescribeEnvironments`, `elasticfilesystem:DescribeFileSystems`, `elasticmapreduce:ListClusters`, `es:ListDomainNames`, `firehose:ListDeliveryStreams`, `kafka:ListClustersV2`, `redshift-serverless:ListNamespaces`, `redshift-serverless:ListWorkgroups`. Elle a
aussi retiré `cloudtrail:LookupEvents`, que la commande `inventag` n’appelle pas.

Son instruction `OptionalS3ReportUpload` autorise `s3:PutObject`, mais uniquement avec
un chiffrement côté serveur. Remplacez `YOUR-REPORTS-BUCKET-NAME` par le nom de votre bucket,
ou supprimez l’instruction si vous n’utilisez pas
`--s3-bucket`. Si vous utilisez un autre `--s3-key-prefix`, modifiez aussi la ressource.

Non vérifié sur un vrai AWS : que l’instruction n’autorise le téléversement qu’avec le chiffrement côté serveur.

## Vérifier une politique {#check-a-policy}

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Les deux premières doivent être `allowed`. `s3:PutObject` n’est autorisée que si vous avez conservé l’instruction `OptionalS3ReportUpload` avec le nom de votre bucket.

Non vérifié sur un vrai AWS : la sortie de `aws iam simulate-principal-policy` pour cette politique.
