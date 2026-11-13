---
title: Fichiers de sortie
description: Chaque fichier qu’InvenTag écrit - rapports Excel et Word, JSON de conformité des étiquettes, instantanés et journaux des changements - avec leurs noms, emplacements et contenus.
sidebar_position: 4
---

# Fichiers de sortie

**À qui s’adresse cette page :** vous traitez la sortie d’InvenTag dans des scripts, ou vous
expliquez les rapports à d’autres personnes.

**Ce que vous saurez après lecture :** le nom, l’emplacement et le contenu de chaque
fichier qu’InvenTag écrit.

Tout est placé dans le dossier de sortie : `bom_output/`, sauf si vous définissez
`--output-directory` ou `output_directory` dans un modèle de configuration. Les seuls
autres endroits où InvenTag écrit sont les fichiers que vous nommez (`--log-file`,
`--audit-output`) et, avec `--s3-bucket`, votre bucket S3.

Les fichiers de sortie sont créés avec un accès en lecture et en écriture réservé à votre
utilisateur, et les nouveaux dossiers de sortie lui sont également privés.

Les exemples de cette page proviennent d’exécutions hors ligne sur un AWS simulé (données
d’exemple).

## Liste des fichiers {#file-list}

| Fichier | Quand | Contenu |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`, ou aucune option de sortie | Le rapport Excel |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | Le rapport Word |
| `tag_compliance_<timestamp>.json` | Une politique d’étiquetage est active | Résultats de la vérification des étiquettes |
| `state/state_<timestamp>.json` | Chaque exécution, sauf avec `--disable-state-management` | Instantané de chaque ressource trouvée. Les instantanés de plus de 30 jours, ou au-delà des 100 plus récents, sont supprimés. |
| `state/metadata.json` | Avec les instantanés | Index des instantanés : heure, compte, régions, nombre de ressources, somme de contrôle |
| `changelog_<timestamp>.md` | Deuxième exécution et suivantes, sauf avec `--no-generate-changelog` ou `--disable-delta-detection` | Ce qui a été ajouté, supprimé ou modifié depuis l’instantané précédent. Voir [Suivre les changements](../guides/track-changes.md). |
| Le fichier que vous nommez avec `--audit-output` | Quand vous le demandez | Chaque opération AWS appelée pendant l’exécution |

`<timestamp>` s’écrit `YYYYMMDD_HHMMSS`.

## Rapport Excel {#excel-report}

**Sans modèle**, le classeur contient :

- **Summary :** Service, Resource Count, Percentage, et un total.
- **Une feuille par service** (par exemple `EC2`, `S3`, `VPC`), triées par nom de
  service, avec chaque champ trouvé sur ses ressources, y compris les colonnes aplaties
  `raw_data.*` et `tags.*`. Les lignes sont triées par type, nom et ID.
- Des feuilles **Network Analysis** et **Security Analysis**, uniquement avec
  `--enable-network-analysis` ou `--enable-security-analysis`.

**Avec un modèle de rapport**, la mise en page suit le modèle :

- **Summary :** titre, heure de génération, nombre de comptes et de régions, un
  tableau Service / Resources / Share et, avec une politique d’étiquetage, les compteurs
  de conformité.
- **Feuilles de ressources :** une par service, ou une seule feuille avec `layout:
  single-sheet`. Les lignes d’en-tête sont mises en forme, figées et filtrables par défaut.
- **Tag Compliance** (avec une politique d’étiquetage) : une ligne par ressource dans le périmètre, puis
  un tableau de règles avec les nombres d’étiquettes manquantes et non valides.

Les noms de feuilles respectent les règles d’Excel : 31 caractères au plus, sans
`[ ] : * ? / \`. Les noms en double reçoivent un numéro. Les valeurs de cellule qui commencent par `=`
sont stockées comme du texte, jamais comme des formules. Les lignes sont triées par service, type,
nom et ID.

Des aperçus de chaque mise en page, réalisés à partir de vrais fichiers, se trouvent dans
[Modèles intégrés](../templates/catalogue.md).

## Rapport Word {#word-report}

**Sans modèle :** un titre, une synthèse, un tableau des services, et
jusqu’à 50 ressources par service sur six colonnes.

**Avec un modèle de rapport :** les sections listées dans `word.sections`. Les tableaux
ont une ligne d’en-tête qui se répète sur chaque page et qui est signalée comme en-tête aux
lecteurs d’écran. Le logo, s’il y en a un, porte un texte alternatif.

## JSON de conformité des étiquettes {#tag-compliance-json}

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 22,
    "compliant": 1,
    "non_compliant": 21,
    "out_of_scope": 14,
    "percent_compliant": 4.5,
    "missing_by_key": {
      "CostCenter": 19,
      "Owner": 16,
      "Project": 20,
      "Environment": 16
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

## Instantanés {#snapshots}

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

```json title="state/state_<timestamp>.json (structure)"
{
  "top_level_keys": [
    "compliance_data",
    "metadata",
    "network_analysis",
    "resources",
    "security_analysis"
  ],
  "one_resource": {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "acme-app-logs",
    "arn": "arn:aws:s3:::acme-app-logs",
    "region": "us-east-1",
    "tags": {
      "Environment": "prod",
      "Owner": "platform",
      "CostCenter": "CC-1001",
      "Project": "storefront",
      "DataClassification": "internal"
    },
    "source_account_id": "123456789012"
  }
}
```

## JSON d’audit {#audit-json}

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
  "total_calls": 71,
  "allowed_calls": 71,
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
      "service": "ce",
      "operation": "GetCostAndUsage",
      "allowed": true,
      "count": 2
    },
    {
      "service": "cloudformation",
      "operation": "DescribeStacks",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudformation",
      "operation": "ListStackSets",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudfront",
      "operation": "ListDistributions",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## Objets S3 {#s3-objects}

Avec `--s3-bucket acme-inventory-reports --s3-key-prefix inventag/`, chaque exécution
place ses fichiers dans un dossier portant le nom de l’exécution :

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

## Sortie du terminal {#terminal-output}

Sans `--verbose`, une exécution affiche les avertissements, les erreurs et les fichiers écrits. Avec
un modèle, chaque fichier est affiché sous la forme `Wrote <path>`, suivi d’un résumé d’une ligne de la
politique d’étiquetage lorsqu’une politique est active.

## Codes de sortie {#exit-codes}

Voir [Référence de la ligne de commande](./cli.md#exit-codes).
