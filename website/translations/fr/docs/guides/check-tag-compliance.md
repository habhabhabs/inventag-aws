---
title: Vérifier les étiquettes selon une politique
description: Vérifiez que vos ressources AWS portent les étiquettes requises avec des valeurs autorisées, via un modèle de politique d’étiquetage, et lisez les résultats.
sidebar_position: 4
slug: /architecture/tag-compliance
---

# Vérifier les étiquettes selon une politique

**À qui s’adresse cette page :** vous êtes responsable d’une norme d’étiquetage et vous voulez savoir
quelles ressources ne la respectent pas.

**Ce que vous saurez faire après lecture :** lancer une vérification des étiquettes, lire les résultats et
rédiger votre propre politique.

## Lancer une vérification {#run-a-check}

Choisissez une politique intégrée, ou la vôtre :

```bash
inventag --template finops-cost-allocation --create-excel --account-regions us-east-1
```

InvenTag analyse le compte comme d’habitude, puis vérifie chaque ressource concernée. Exemple de sortie
d’une exécution hors ligne avec `--template finops-cost-report` (données d’exemple) :

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

## Lire les résultats {#read-the-results}

| Où | Ce que vous obtenez |
|---|---|
| Excel, feuille **Tag Compliance** | Une ligne par ressource concernée : compte, région, service, type, ressource, ARN, statut, étiquettes manquantes et autres problèmes. Les lignes non conformes viennent en premier. Sous le tableau, chaque règle avec le nombre de ressources qui l’enfreignent ou qui ont une valeur incorrecte. |
| Excel, feuille **Summary** | Les totaux : vérifiées, conformes, non conformes, hors périmètre, pourcentage. |
| Word, section **Tag compliance** | Les mêmes totaux, les règles et un tableau des ressources non conformes (jusqu’à 100 lignes par défaut). |
| `tag_compliance_<timestamp>.json` | Les totaux par règle et chaque ressource non conforme, pour les scripts et la CI. |

Une ressource est **conforme** lorsqu’elle porte toutes les étiquettes requises et que chaque valeur
respecte sa règle. Les problèmes sont détaillés, par exemple :

- `CostCenter: '1234' does not match CC-[0-9]{4}` (format incorrect)
- `Environment: 'Production' is not one of prod, staging, dev, test, sandbox`
- `Owner: found 'owner' instead (tag keys are case-sensitive)`

La feuille Tag Compliance du même exemple :

**Feuilles :** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

Feuille `Tag Compliance`, premières lignes :

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

La section Word :

**Plan du document :**

- **Cost Allocation Tag Report** (titre)
- Summary
- Tag compliance
  - Required tags
  - Non-compliant resources
- Resources by service
- About this report

Un tableau du document :

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| CostCenter | Matches: CC-[0-9]&#123;4&#125; | 20 | 1 |
| Owner | Any value | 17 | 0 |
| Project | Any value | 21 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 17 | 1 |

La partie `summary` du fichier JSON :

```json title="summary"
{
  "checked": 23,
  "compliant": 1,
  "non_compliant": 22,
  "out_of_scope": 14,
  "percent_compliant": 4.3,
  "missing_by_key": {
    "CostCenter": 20,
    "Owner": 17,
    "Project": 21,
    "Environment": 17
  },
  "invalid_by_key": {
    "CostCenter": 1,
    "Owner": 0,
    "Project": 0,
    "Environment": 1
  }
}
```

Les ressources **hors périmètre** sont comptées mais pas vérifiées : le `scope` de la politique
les exclut, par exemple les alias KMS, qui ne peuvent pas porter d’étiquettes.

**À savoir avant de vous fier aux chiffres :** InvenTag associe les étiquettes de
l’API Resource Groups Tagging aux ressources par ARN, et se rabat sur le
service, la région et l’identifiant de la ressource lorsque l’ARN diffère. Des tests hors ligne avec moto
vérifient ce comportement pour chaque service doté de son propre code de découverte. AWS réel peut
répondre autrement : comparez donc quelques lignes de la colonne ARN avec la console avant
de vous appuyer sur le résultat d’une politique.

## Rédiger votre propre politique {#write-your-own-policy}

Partez d’une politique intégrée et ne modifiez que ce qui diffère :

```bash
inventag templates init finops-cost-allocation --output .inventag/templates/our-tags.yaml --extend
```

```yaml
format_version: 1
kind: tag-policy
name: our-tags
description: Our cost-allocation tags
extends: finops-cost-allocation
spec:
  required_tags:
    - key: Environment                 # replaces the inherited rule
      allowed_values: [production, staging, development]
    - key: Project                     # drops an inherited tag
      remove: true
    - key: DataClassification          # adds a new one
      allowed_values: [public, internal, confidential]
  scope:
    services: [EC2, S3, RDS, LAMBDA]   # only check these services
```

Règles pour chaque étiquette :

- `allowed_values` : la valeur doit figurer dans cette liste. La casse n’a pas d’importance
  sauf si vous définissez `case_sensitive: true`.
- `pattern` : la valeur entière doit correspondre à cette expression régulière.
- Ni l’un ni l’autre : toute valeur convient, tant que l’étiquette existe.

Utilisez soit `allowed_values`, soit `pattern` pour une étiquette, pas les deux. Tous les champs sont
décrits dans la [référence des modèles](../templates/reference.md).

## Preuves par les étiquettes pour une discussion sur un référentiel {#tag-evidence-for-a-framework-conversation}

Cinq politiques intégrées partent de `security-baseline` et ajoutent les étiquettes qui alimentent une discussion sur SOC 2, HIPAA, PCI DSS, le RGPD ou la PDPA ; par exemple `inventag --template evidence-soc2 --create-excel`. Elles vérifient uniquement les preuves par les étiquettes, les valeurs sont déclarées par le propriétaire de la ressource et un résultat positif ne signifie pas que le compte satisfait l’un de ces référentiels. Voir [Modèles de preuve par les étiquettes](../templates/tag-evidence.md).

## Faire échouer un pipeline en cas de violation {#fail-a-pipeline-on-violations}

Ajoutez un modèle de configuration avec `fail_on_tag_violations: true`. InvenTag écrit quand même tous
les rapports, puis se termine avec le code 3. Si vous passez aussi `--fail-on-account-error` ou `--fail-if-empty` et que l’une des deux conditions se vérifie,
le code de sortie est 5 ou 6 à la place, car les données sont incomplètes. Voir
[Appliquer une politique d’étiquetage en CI](../examples/tag-policy-in-ci.md).

## L’ancien script de vérification {#the-older-checker-script}

`scripts/legacy/tag_compliance_checker.py --config policy.yaml` est antérieur aux
modèles et possède ses propres options (`--help` les liste). Il vérifie seulement que les clés d’étiquette obligatoires existent. Il n’applique ni `allowed_values`, ni `pattern`, ni aucun autre champ de son fichier de politique :
il journalise un avertissement et les liste dans `summary.ignored_policy_fields` de son rapport. Il ignore les étiquettes dont la clé commence par `aws:`,
car AWS les crée : une ressource qui n’a que des étiquettes `aws:` compte donc comme non étiquetée, et une clé d’étiquette obligatoire qui commence par `aws:` est une erreur.
Au-delà, il n’est pas couvert par cette documentation. Préférez les modèles de politique d’étiquetage.

Les anciens scripts de `scripts/legacy/` s’exécutent sous la protection en lecture seule et écrivent
des fichiers réservés à leur propriétaire. `aws_resource_inventory.py --s3-bucket` téléverse avec le
chiffrement SSE-S3.

## Étapes suivantes {#next-steps}

- [Politiques d’étiquetage intégrées](../templates/catalogue.md#tag-policy-templates)
- [Exemple : étiquettes d’allocation des coûts FinOps](../examples/finops-cost-allocation.md)
