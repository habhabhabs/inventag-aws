---
title: "Exemple : vérifier les preuves par les étiquettes avant une discussion sur le périmètre SOC 2"
description: Trouvez les ressources AWS sans étiquette de périmètre SOC 2, de nom de système, de méthode de provisionnement ou de criticité, avec le modèle evidence-soc2.
sidebar_position: 10
---

# Exemple : vérifier les preuves par les étiquettes avant une discussion sur le périmètre SOC 2

:::note

Ce contrôle ne porte que sur les preuves par les étiquettes. Les valeurs des
étiquettes sont déclarées par le propriétaire de la ressource et InvenTag ne les
vérifie pas. Un résultat positif ne signifie pas que le compte satisfait SOC 2.

:::

**Objectif :** avant de discuter avec un auditeur ou un client des systèmes qui
sont dans le périmètre SOC 2, lister les ressources qui n’ont ni périmètre, ni
nom de système, ni méthode de provisionnement, ni criticité enregistrés.

**Ce qu’il vous faut :** des identifiants en lecture seule. InvenTag lit les
étiquettes ; il n’évalue pas les contrôles.

## Modèle {#template}

La politique d’étiquetage intégrée `evidence-soc2` part de `security-baseline`
(`Owner`, `Environment` et `DataClassification`) et ajoute quatre étiquettes :

| Clé d’étiquette | Règle |
|---|---|
| `Soc2Scope` | `in-scope` ou `out-of-scope` |
| `SystemName` | N’importe quel texte non vide |
| `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual` ou `other` |
| `Criticality` | `high`, `medium` ou `low` |

Elle couvre tous les types de ressource sauf les alias KMS. Voir le
[catalogue des modèles](../templates/catalogue.md#evidence-soc2) pour ce
qu’elle peut montrer ou non.

## Commande {#command}

```bash title="Terminal"
inventag --template evidence-soc2 --create-excel --account-regions us-east-1
```

## Sortie {#output}

Le compte d’exemple a quatre buckets, une table DynamoDB et une file, étiquetés
de façons différentes, plus les ressources par défaut que tout compte possède.

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'evidence-soc2': 2 of 18 resources compliant (11.1%), 16 non-compliant, 14 out of scope.
```

Les 14 ressources hors périmètre sont des alias KMS. Parmi les 16 ressources
auxquelles il manque quelque chose, 12 sont des ressources par défaut que
personne n’a étiquetées (le VPC par défaut avec ses sous-réseaux, sa table de
routage, son ACL réseau et son groupe de sécurité, un groupe de travail Athena
et le bus d’événements par défaut). La colonne d’état indique seulement si la
ressource porte toutes les étiquettes du modèle avec une valeur autorisée.

**Feuilles :** `Summary`, `ATHENA`, `DYNAMODB`, `EVENTS`, `KMS`, `S3`, `SQS`, `VPC`, `Tag Compliance`

Feuille `Tag Compliance`, premières lignes :

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | arn:aws:s3:::acme-data-lake | Non-compliant | Criticality |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | arn:aws:s3:::acme-reports | Non-compliant |  | Soc2Scope: 'yes' is not one of in-scope, out-... |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | arn:aws:s3:::acme-scratch | Non-compliant | Owner, Environment, DataClassification, Soc2S... |  |
| 123456789012 | us-east-1 | SQS | Queue | acme-jobs | arn:aws:sqs:us-east-1:123456789012:acme-jobs | Non-compliant | DataClassification, Soc2Scope, SystemName, Cr... |  |
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Compliant |  |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | arn:aws:s3:::acme-app-logs | Compliant |  |  |

Ce que disent les lignes :

- `acme-data-lake` n’a pas l’étiquette `Criticality`.
- `acme-reports` a `Soc2Scope` à `yes`, qui n’est pas l’une des valeurs
  autorisées.
- `acme-scratch` n’a aucune étiquette.
- `acme-jobs` a `Owner`, `Environment` et `ManagedBy`, mais ni
  `DataClassification`, ni `Soc2Scope`, ni `SystemName`, ni `Criticality`.
- `acme-app-logs` a toutes les étiquettes avec une valeur autorisée.
- `acme-orders` est marquée `out-of-scope` par son propriétaire et porte
  pourtant toutes les étiquettes. Ce qui est vérifié, c’est que la réponse est
  enregistrée, pas ce qu’elle est.

Pour voir quelle étiquette manque le plus souvent, lisez le résumé du fichier
JSON :

```json title="tag_compliance_20261112_090000.json (summary, two fields)"
{
  "missing_by_key": {
    "Owner": 13,
    "Environment": 13,
    "DataClassification": 14,
    "Soc2Scope": 14,
    "SystemName": 14,
    "ManagedBy": 13,
    "Criticality": 15
  },
  "invalid_by_key": {
    "Owner": 0,
    "Environment": 0,
    "DataClassification": 0,
    "Soc2Scope": 1,
    "SystemName": 0,
    "ManagedBy": 0,
    "Criticality": 0
  }
}
```

## Ce que cela ne vous dit pas {#what-this-does-not-tell-you}

- Cela ne dit pas que le périmètre est le bon, qu’un contrôle existe ou
  fonctionne, ni ce qu’un auditeur testerait.
- Cela ne vérifie pas que `ManagedBy` est vrai. Comparez-le aux étiquettes
  `aws:cloudformation:*` qu’ajoute AWS.
- Une étiquette présente signifie seulement que le propriétaire a écrit
  quelque chose.

## Étapes suivantes {#next-steps}

- Étiquetez les ressources par défaut, ou réduisez la politique pour qu’elles
  ne soient pas vérifiées : copiez `evidence-soc2` dans votre projet et
  définissez `spec.scope.services`, comme dans
  [Exemple : revue de l’étiquetage de sécurité](./security-review.md#next-steps).
- Commencez en mode rapport seul dans la CI :
  [Exemple : appliquer une politique d’étiquetage en CI](./tag-policy-in-ci.md).
- Écrivez vos propres règles :
  [Vérifier les étiquettes selon une politique](../guides/check-tag-compliance.md#write-your-own-policy).
