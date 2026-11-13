---
title: "Exemple : revue de l’étiquetage de sécurité"
description: Vérifiez que les ressources AWS ont les étiquettes Owner, Environment et DataClassification avant une revue de sécurité, avec la politique security-baseline.
sidebar_position: 6
---

# Exemple : revue de l’étiquetage de sécurité

**Objectif :** avant une revue de sécurité ou un exercice d’incident, trouver les ressources
sans propriétaire, sans environnement ou sans classification des données.

**Ce qu’il vous faut :** des identifiants en lecture seule.

Ce contrôle ne porte que sur les étiquettes. Il n’évalue pas le niveau de sécurité de la
configuration, et le réussir ne vous rend conforme à aucun référentiel.

## Modèle {#template}

La politique d’étiquetage intégrée `security-baseline` exige :

| Tag key | Règle |
|---|---|
| `Owner` | Toute valeur |
| `Environment` | `prod`, `staging`, `dev`, `test` ou `sandbox` |
| `DataClassification` | `public`, `internal`, `confidential` ou `restricted` |

## Commande {#command}

```bash title="Terminal"
inventag --template standard-bom --template security-baseline \
  --create-excel --create-word --account-regions us-east-1
```

## Sortie {#output}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'security-baseline': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

**Feuilles :** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

Feuille `Tag Compliance`, premières lignes :

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | Owner, Environment, DataClassification |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | Owner, Environment, DataClassification |  |

Filtrez la colonne « Missing tags » sur `Owner` pour trouver en premier les ressources sans propriétaire.

## Étapes suivantes {#next-steps}

- Convenez de propriétaires pour les ressources sans propriétaire, puis étiquetez-les dans votre
  code d’infrastructure.
- Limitez le contrôle aux seuls magasins de données :

```yaml title=".inventag/templates/data-stores.yaml"
format_version: 1
kind: tag-policy
name: data-stores
description: Classification on data stores only
extends: security-baseline
spec:
  scope:
    services: [S3, DYNAMODB, RDS]
```
