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
| `ec2:DescribeRegions` | Liste les régions activées et vérifie chaque région que vous analysez | La vérification s’exécute pour chaque région, même avec `--account-regions`. Une région qui échoue à cette vérification est ignorée avec un avertissement. |
| `tag:GetResources` | Trouve les ressources étiquetées (API Resource Groups Tagging) | Le préfixe IAM est `tag`, et non `resourcegroupstaggingapi`. |
| `ce:GetCostAndUsage` | Repère les services qui génèrent des dépenses | **AWS facture chaque requête.** Lors de notre test hors ligne, une exécution en a effectué deux par compte. En cas de refus, la découverte continue sans données de facturation. `--no-billing-validation` arrête ces appels, et vous pouvez alors omettre cette autorisation. |
| `List*`, `Describe*`, `Get*` pour chaque service que vous voulez dans le rapport | Découverte par service | Par exemple `s3:ListAllMyBuckets`, `s3:GetBucketTagging`, `lambda:ListFunctions`, `dynamodb:ListTables`. La politique gérée AWS `ReadOnlyAccess` les couvre. |

## Ce dont certaines fonctionnalités ont besoin {#what-some-features-need}

| Fonctionnalité | Autorisation supplémentaire |
|---|---|
| Analyse d’autres comptes via un rôle | `sts:AssumeRole` sur ces rôles, et une politique d’approbation dans chaque compte qui autorise votre identité |
| `--enable-cost-analysis` | `pricing:GetProducts` et `cloudwatch:GetMetricStatistics` (les deux figurent dans la politique du dépôt) |
| `--s3-bucket` | `s3:PutObject` sur ce bucket (et `kms:GenerateDataKey` sur la clé si vous utilisez `aws:kms`) |

## Ce dont InvenTag n’a jamais besoin {#what-inventag-never-needs}

Toute action d’écriture, de création, de suppression ou d’étiquetage, hormis `s3:PutObject` sur un bucket
de rapports si vous téléversez des rapports. Si une personne chargée de la relecture en trouve une autre dans
votre politique InvenTag, supprimez-la. La protection en lecture seule d’InvenTag bloque de toute façon ces
appels. Deux fonctions de bibliothèque du code peuvent écrire dans
AWS lorsqu’elles sont appelées depuis votre propre code Python (la CLI ne les appelle pas) ; voir
[État des fonctionnalités](../getting-started/status.md#security-notes).

## La politique du dépôt {#the-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` est générée à partir d’une liste explicite
de 106 actions de lecture dans le code (`inventag/security/iam_policy.py`), si bien qu’elle
correspond à ce qu’InvenTag appelle. Elle inclut `tag:GetResources`,
`ce:GetCostAndUsage`, `pricing:GetProducts` et
`lambda:GetFunctionConfiguration`.

Son instruction `OptionalS3ReportUpload` autorise `s3:PutObject`, mais uniquement avec
un chiffrement côté serveur. Remplacez `YOUR-REPORTS-BUCKET-NAME` par le nom de votre bucket,
ou supprimez l’instruction si vous n’utilisez pas
`--s3-bucket`.

## Vérifier une politique {#check-a-policy}

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names tag:GetResources ce:GetCostAndUsage s3:PutObject \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

Les deux premières doivent être `allowed`, et `s3:PutObject` doit être refusée.
