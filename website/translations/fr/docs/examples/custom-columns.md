---
title: "Exemple : vos propres colonnes"
description: Choisissez exactement les colonnes et les colonnes d’étiquettes du rapport Excel d’InvenTag, dans l’ordre que vous voulez, sur une seule feuille filtrable.
sidebar_position: 8
---

# Exemple : vos propres colonnes

**Objectif :** une seule feuille avec les colonnes que votre équipe lit vraiment, dans l’ordre
de votre choix.

**Ce qu’il vous faut :** des identifiants en lecture seule.

## Modèle {#template}

```yaml title=".inventag/templates/team-sheet.yaml"
format_version: 1
kind: report
name: team-sheet
description: One sheet, our columns
extends: standard-bom
spec:
  title: Platform team inventory
  columns:
    - { field: source_account_id, header: Account }
    - { field: service, header: Service }
    - { field: resource_type, header: Type }
    - { field: resource_name, header: Name }
    - { field: region, header: Region }
    - { field: raw_data.VolumeType, header: Volume type }
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
    single_sheet_name: Inventory
```

- `columns` remplace entièrement la liste héritée ; énumérez donc toutes les colonnes que vous
  voulez.
- `tag_columns` ajoute une colonne par clé d’étiquette, après `columns`. Utilisez `all` pour
  toutes les étiquettes trouvées, ou `none`.
- `raw_data.<Name>` lit une valeur directement dans la réponse de l’API AWS. Elle est
  vide pour les ressources qui n’en disposent pas. Pour trouver les noms, lancez une fois avec
  `excel.include_all_fields: true`.

## Commande {#command}

```bash title="Terminal"
inventag templates validate team-sheet
inventag --template team-sheet --create-excel --account-regions us-east-1
```

## Sortie {#output}

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/team-sheet.yaml (report 'team-sheet')
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**Feuilles :** `Summary`, `Inventory`

Feuille `Inventory`, premières lignes :

| Account | Service | Type | Name | Region | Volume type | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | EC2 | Volume |  | us-east-1 | gp2 |  |  |  |
| 123456789012 | EC2 | Volume | acme-build-cache | us-east-1 | gp3 |  |  |  |
| 123456789012 | S3 | Bucket | acme-app-logs | us-east-1 |  | platform | CC-1001 | prod |
| 123456789012 | S3 | Bucket | acme-data-lake | us-east-1 |  | data | CC-2002 | prod |
| 123456789012 | S3 | Bucket | acme-reports | us-east-1 |  | finance | 1234 | Production |
| 123456789012 | S3 | Bucket | acme-scratch | us-east-1 |  |  |  |  |

![Feuille Inventory avec les colonnes choisies dans le modèle team-sheet : Account, Service, Type, Name, Region, Volume type et trois colonnes d’étiquettes (données d’exemple)](../assets/examples/img/team-sheet-inventory.png)

La ligne d’en-tête est figée et dotée de boutons de filtre.

## Mappages d’étiquettes et descriptions de services {#tag-mappings-and-service-descriptions}

`--tag-mappings` et `--service-descriptions` ajoutent des colonnes au classeur par
défaut. Avec `--template`, ils n’ajoutent rien ; utilisez donc `tag_columns` comme ci-dessus. Avec
un fichier de mise en page (`--excel-template` ou `--word-template`), indiquez la colonne mappée
sous `extra_fields`. Voir
[Fichiers de configuration](../reference/configuration-files.md#tag-mappings).

## Étapes suivantes {#next-steps}

- Tous les champs de colonne : [Référence des modèles](../templates/reference.md#resource-fields-you-can-use-as-columns).
