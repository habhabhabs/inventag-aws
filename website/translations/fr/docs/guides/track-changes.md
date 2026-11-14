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

La partie `metadata` d’un instantané enregistre la version de l’instantané (`1.1` ; les fichiers de version `1.0` se chargent encore),
`accounts_scanned` et `accounts_failed`. Les valeurs de champs qui contiennent souvent des secrets, comme les variables d’environnement Lambda,
les mots de passe, les jetons et les clés privées, sont remplacées par `***REDACTED***` ; les noms restent. La liste complète, qui couvre aussi les sorties de piles CloudFormation, les arguments des déclencheurs Glue, les chaînes de connexion et les URL signées, se trouve dans [État des fonctionnalités](../getting-started/status.md#what-inventag-finds-and-what-it-does-not).
Un changement de l’une de ces valeurs n’est pas signalé. Les instantanés des versions antérieures peuvent encore contenir ces valeurs :
supprimez ou restreignez les anciens dossiers `bom_output/`. La première exécution après la mise à jour affiche les valeurs masquées comme modifiées.

Conservez le dossier `state/` entre les exécutions, par exemple comme cache de CI ou dans un
bucket, si vous voulez un historique. Désactivez les instantanés avec
`--disable-state-management`. Le dossier `state/partial/` contient les résultats de comptes enregistrés pour
[`--resume`](./run-a-scan.md#continue-after-a-failed-run). Il ne fait pas partie de l’historique.

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
- Si un compte n’a pas pu être analysé ou a dépassé son délai dans l’une des deux exécutions, ses ressources sont exclues de la comparaison.
  Sinon, toutes apparaîtraient comme ajoutées ou supprimées. Le rapport de changements nomme le compte dans sa section State Comparison (`accounts_not_compared`). Un compte dont la session a expiré en cours d’analyse est comparé comme s’il était complet.
- InvenTag compare les listes sans tenir compte de l’ordre : déplacer des éléments dans une liste n’est donc pas un changement, sauf pour les couches Lambda, les politiques de résiliation Auto Scaling et les comportements de cache CloudFront, dont l’ordre fait partie de la configuration.
  Il ignore aussi les champs qui changent à chaque exécution : la voie de découverte, les chiffres de coût et les compteurs d’utilisation
  comme `ItemCount`, `ApproximateNumberOfMessages` ou la taille EFS.
- Quand une exécution enregistre un instantané, InvenTag supprime ceux de plus de 30 jours ou au-delà des 100 plus récents.
  Modifiez les limites avec `--state-retention-days N` et `--state-max-snapshots N` ; `0` ou `none` désactive une limite.
  L’instantané qui vient d’être écrit et celui auquel il est comparé ne sont jamais supprimés : `--state-max-snapshots 1` laisse donc deux fichiers.
  InvenTag ne supprime que les fichiers `state_<timestamp>.json` qu’il a écrits lui-même. Un job planifié sur un runner neuf
  n’a aucun instantané antérieur ; conservez donc le dossier `state/` entre les exécutions.

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

```text title="Sortie"
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

## Étapes suivantes {#next-steps}

- [État des fonctionnalités](../getting-started/status.md)
- [Exécuter InvenTag en CI/CD](./run-in-ci.md)
