---
title: "Exemple : étiquettes d’allocation des coûts FinOps"
description: Trouvez les ressources AWS sans les étiquettes CostCenter, Owner, Project et Environment dont dépendent les rapports de coûts, avec finops-cost-report.
sidebar_position: 5
---

# Exemple : étiquettes d’allocation des coûts FinOps

**Objectif :** un rapport pour l’équipe FinOps (gestion financière du cloud) ou la
finance, qui indique, ressource par ressource, si les étiquettes d’allocation des coûts sont présentes
et valides.

**Ce qu’il vous faut :** des identifiants en lecture seule. Les étiquettes n’apparaissent dans les rapports
de coûts AWS qu’après les avoir activées comme étiquettes d’allocation des coûts dans la console AWS Billing and Cost
Management. InvenTag indique quelles ressources les portent ; il ne
calcule pas les coûts.

## Modèle {#template}

`finops-cost-report` (un modèle de rapport) affiche CostCenter, Owner, Project et
Environment sous forme de colonnes et active la politique d’étiquetage `finops-cost-allocation` :

| Tag key | Règle dans `finops-cost-allocation` |
|---|---|
| `CostCenter` | `CC-` suivi de quatre chiffres, par exemple `CC-1234` |
| `Owner` | Toute valeur |
| `Project` | Toute valeur |
| `Environment` | `prod`, `staging`, `dev`, `test` ou `sandbox` |

Si vos centres de coûts ont un autre format, adaptez la politique et conservez le rapport :

```yaml title=".inventag/templates/our-cost-tags.yaml"
format_version: 1
kind: tag-policy
name: our-cost-tags
description: Our cost centres are five-digit numbers
extends: finops-cost-allocation
spec:
  required_tags:
    - key: CostCenter
      pattern: "[0-9]{5}"
```

## Commande {#command}

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
# with your own policy:
inventag --template finops-cost-report --template our-cost-tags --create-excel
```

## Sortie {#output}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

**Feuilles :** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

Feuille `Tag Compliance`, premières lignes :

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

![Feuille Tag Compliance : une ligne par ressource avec compte, région, service, type, ressource, ARN, statut, étiquettes manquantes et problèmes, suivie du tableau des règles de la politique (données d’exemple)](../assets/examples/img/finops-tag-compliance-sheet.png)

La section Tag compliance du document Word :

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

Le fichier JSON :

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
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
  },
  "non_compliant_resources": [
    {
      "account": "123456789012",
      "service": "S3",
      "resource_type": "Bucket",
      "resource_id": "acme-reports",
      "arn": "arn:aws:s3:::acme-reports",
      "region": "us-east-1",
      "missing": [],
      "invalid": [
        "CostCenter: '1234' does not match CC-[0-9]{4}",
        "Environment: 'Production' is not one of prod, staging, dev, test, sandbox"
      ]
    }
  ]
}
```

[Télécharger l’exemple de JSON de conformité des étiquettes](pathname:///inventag-aws/downloads/tag-compliance-sample.json) (9 Ko, données d’exemple)

## Étapes suivantes {#next-steps}

- Envoyez le document Word aux responsables budgétaires. Sa section Tag compliance liste
  les ressources non conformes.
- Suivez les progrès chaque semaine : [Exécuter InvenTag en CI/CD](../guides/run-in-ci.md).
