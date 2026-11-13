---
title: "Démarrage rapide : générer votre premier rapport"
sidebar_label: Démarrage rapide
description: Analysez un compte et une région AWS avec InvenTag et ouvrez les rapports de nomenclature Excel et Word qu’il produit, en une dizaine de minutes.
sidebar_position: 3
---

# Démarrage rapide : générer votre premier rapport

**À qui s’adresse cette page :** vous avez [installé InvenTag](./installation.md) et vous disposez
d’identifiants AWS en lecture seule.

**Ce que vous saurez faire après lecture :** analyser un compte, ouvrir les rapports
Excel et Word, et choisir une mise en page plus claire avec un modèle.

Tous les exemples de sortie de cette page proviennent d’une exécution hors ligne sur un AWS
simulé (données d’exemple). Le compte `123456789012` et les ressources `acme-*` sont fictifs.

## 1. Vérifiez dans quel compte vous êtes {#1-check-which-account-you-are-in}

```bash title="Terminal"
aws sts get-caller-identity
```

InvenTag analyse le compte auquel appartiennent ces identifiants.

## 2. Analysez une région {#2-scan-one-region}

Commencez petit. Une région, c’est rapide et peu coûteux.

Cette commande ne fait que lire. Une protection intégrée bloque les appels qui
pourraient modifier votre compte ([configurer un accès en lecture seule](../guides/read-only-access.md)).
Par défaut, elle envoie aussi des requêtes Cost Explorer, qu’AWS facture ; ajoutez
`--no-billing-validation` pour les éviter ([ce que coûte une exécution](#what-a-run-costs)).

```bash title="Terminal"
inventag --create-excel --create-word --account-regions us-east-1
```

- `--create-excel` et `--create-word` choisissent les fichiers à écrire. Sans
  l’une ni l’autre, vous obtenez uniquement Excel.
- `--account-regions` limite l’analyse aux régions indiquées, séparées par des
  virgules. Sans cette option, InvenTag analyse toutes les régions activées dans le compte,
  ce qui prend plus de temps. IAM, la liste des buckets S3, CloudFront et Route 53 sont
  toujours lus une seule fois depuis `us-east-1`, quelles que soient les régions indiquées.

À la fin, vous voyez où les fichiers ont été écrits :

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Word document saved: bom_output/multi_account_bom_20261112_090000.docx
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

L’avertissement indique seulement que vous n’avez pas nommé de compte ; InvenTag a donc utilisé vos
identifiants actuels. Ajoutez `--verbose` pour voir chaque étape.

## 3. Ouvrez les rapports {#3-open-the-reports}

Le classeur Excel contient une feuille **Summary** et une feuille par service. Sans
modèle, chaque feuille de service liste tous les champs trouvés par InvenTag ; les
feuilles sont donc larges :

**Feuilles :** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`

Feuille `S3`, premières lignes :

| service | type | id | name | arn | account_id | source_account_id | source_account_name | ... |
|---|---|---|---|---|---|---|---|---|
| S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports |  | 123456789012 | AWS Account 123456789012 (moto) | ... |

La feuille compte 33 colonnes ; les 8 premières sont affichées.

Le document Word contient une synthèse, un tableau des services et jusqu’à 50 ressources
par service :

**Plan du document :**

- **AWS Resource Inventory - BOM Report** (titre)
- Executive Summary
  - Service Summary
- Detailed Resource Inventory
  - ATHENA Resources (1)
  - DYNAMODB Resources (1)
  - EC2 Resources (4)
  - EVENTS Resources (1)
  - IAM Resources (1)
  - KMS Resources (14)
  - LAMBDA Resources (1)
  - S3 Resources (4)
  - VPC Resources (10)
- Report Information

Un tableau du document :

| Service | Resource Count | Percentage |
|---|---|---|
| ATHENA | 1 | 2.7% |
| DYNAMODB | 1 | 2.7% |
| EC2 | 4 | 10.8% |
| EVENTS | 1 | 2.7% |

(9 lignes au total ; 4 affichées.)

InvenTag enregistre aussi un instantané de l’exécution dans `bom_output/state/`.

## 4. Choisissez une mise en page avec un modèle {#4-choose-a-layout-with-a-template}

Un [modèle de rapport](../templates/index.md) vous donne des noms de colonnes lisibles,
une colonne par étiquette, une ligne d’en-tête figée et des boutons de filtre :

```bash title="Terminal"
inventag --template standard-bom --create-excel --create-word --account-regions us-east-1
```

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

Voyez à quoi ressemble le résultat dans
[Modèles intégrés](../templates/catalogue.md#standard-bom).

## 5. Vérifiez vos étiquettes {#5-check-your-tags}

Ajoutez une politique d’étiquetage pour voir quelles ressources n’ont pas d’étiquettes :

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
```

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

Le classeur contient maintenant une feuille **Tag Compliance** qui liste ce qui manque sur
chaque ressource. Plus de détails dans [Vérifier les étiquettes selon une politique](../guides/check-tag-compliance.md).

## Ce que coûte une exécution {#what-a-run-costs}

Les appels en lecture seule d’InvenTag sont gratuits. Les appels
`GetCostAndUsage` de Cost Explorer ne le sont pas : AWS facture chaque requête, et une exécution
par défaut en fait deux par compte dans notre test hors ligne. Consultez les
[tarifs actuels de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Ajoutez `--no-billing-validation` pour ne faire aucun appel à Cost Explorer.

## Étapes suivantes {#next-steps}

- [État des fonctionnalités](./status.md) : à lire avant de
  vous fier à une option.
- [Choisir ce qu’il faut analyser et produire](../guides/run-a-scan.md)
- [Exemples](../examples/index.md) : recettes à copier-coller.
