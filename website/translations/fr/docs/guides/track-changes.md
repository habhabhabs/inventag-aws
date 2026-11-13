---
title: Suivre les changements entre deux exécutions
description: Comment InvenTag enregistre un instantané de chaque exécution dans bom_output/state, ce que contient le rapport de changements et les limites à connaître.
sidebar_position: 6
slug: /architecture/state-management
---

# Suivre les changements entre deux exécutions

**À qui s’adresse cette page :** vous exécutez InvenTag selon un calendrier et vous voulez savoir ce qui
a changé.

**Ce que vous saurez après lecture :** où les instantanés sont stockés, ce que contient le
rapport de changements et comment comparer vous-même des exécutions.

## Instantanés {#snapshots}

Chaque exécution enregistre ce qu’elle a trouvé dans le dossier de sortie. Après deux exécutions sur
un AWS simulé (données d’exemple) :

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

Chaque instantané contient toutes les ressources trouvées par l’exécution :

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

Conservez le dossier `state/` entre les exécutions, par exemple comme cache de CI ou dans un
bucket, si vous voulez un historique. Désactivez les instantanés avec
`--disable-state-management`.

## Le rapport de changements {#the-change-report}

À partir de la deuxième exécution, InvenTag compare le nouvel instantané à celui qui le précède
et écrit `changelog_<timestamp>.md` dans le dossier de sortie. La première exécution
n’a rien à comparer et n’écrit donc aucun rapport de changements.

Dans cet exemple, un bucket a été ajouté entre les deux exécutions. Le rapport de changements
le liste :

<details>
<summary>changelog_20261112_090100.md (30 premières lignes)</summary>

```markdown
# Multi-Account Infrastructure Changes

**Generated:** 2026-11-12T09:00:00+00:00

## State Comparison

- **from_state:** 20261112_090000
- **to_state:** 20261112_090100
- **comparison_timestamp:** 2026-11-12T09:00:00+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total Changes | 2 |
| Critical Changes | 0 |
| High Severity | 0 |
| Security Changes | 0 |
| Compliance Changes | 0 |
| Network Changes | 0 |

**Most Impacted Services:**
- S3: 1 changes
- ATHENA: 1 changes

## S3 Service Changes

Changes detected in S3 service resources

### New Bucket 'acme-new-bucket' was created in S3
```

</details>

Le rapport contient un tableau de synthèse, puis une section pour chaque service ayant
des changements. Chaque changement a un type (par exemple `added`), une gravité, la ressource et
son ARN.

À savoir :

- Il compare une exécution à celle qui la précède. Il ne compare pas avec une
  exécution plus ancienne que vous choisiriez.
- Il compare les ressources trouvées par chaque exécution. Utilisez les mêmes régions, services et
  filtres pour les deux exécutions, afin qu’un changement de périmètre ne soit pas pris pour un changement dans
  votre parc.
- `--no-generate-changelog` supprime le rapport mais conserve les instantanés.
  `--disable-delta-detection` le supprime aussi. `--disable-state-management`
  supprime les instantanés et les rapports.
- InvenTag supprime les instantanés de plus de 30 jours ou au-delà des 100
  plus récents. Un job planifié sur un runner neuf n’a aucun instantané antérieur ; conservez donc le
  dossier `state/` entre les exécutions.

## Comparer vous-même deux instantanés {#compare-two-snapshots-yourself}

Vous pouvez comparer deux instantanés quelconques, car chacun est un JSON avec une liste
`resources` :

```bash
python3 - <<'EOF'
import json, sys, glob
old, new = sorted(glob.glob("bom_output/state/state_*.json"))[-2:]
ids = lambda f: {r.get("arn") or r.get("id") for r in json.load(open(f))["resources"]}
a, b = ids(old), ids(new)
print("Added:", sorted(b - a))
print("Removed:", sorted(a - b))
EOF
```

Exemple de sortie après l’ajout d’un bucket entre deux exécutions (données d’exemple) :

```text title="Terminal"
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

## Étapes suivantes {#next-steps}

- [État des fonctionnalités et limites connues](../getting-started/status.md)
- [Exécuter InvenTag en CI/CD](./run-in-ci.md)
