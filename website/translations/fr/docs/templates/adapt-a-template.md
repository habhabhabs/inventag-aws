---
title: Adapter un modèle
description: Copiez un modèle InvenTag dans votre projet, ne modifiez que ce dont vous avez besoin, vérifiez-le avec templates validate et utilisez-le dans une exécution.
sidebar_position: 3
---

# Adapter un modèle

**À qui s’adresse cette page :** vous aimez un modèle intégré mais vous voulez votre propre titre,
vos couleurs, vos colonnes ou vos règles d’étiquetage.

**Ce que vous saurez faire après lecture :** créer votre propre modèle en quatre étapes :
`init`, modification, `validate`, exécution.

Les sorties ci-dessous proviennent d’exécutions hors ligne sur un AWS simulé (données d’exemple).
Votre dossier de projet apparaît sous la forme `~/acme-infra/`.

## 1. Copiez le modèle dans votre projet {#1-copy-the-template-into-your-project}

Lancez ceci dans votre dossier de projet :

```bash
inventag templates init standard-bom --output .inventag/templates/acme-bom.yaml --extend
```

```text title="Terminal"
Created .inventag/templates/acme-bom.yaml (kind: report, name: acme-bom).
Next: edit it, then run 'inventag templates validate .inventag/templates/acme-bom.yaml'.
```

Vous avez deux possibilités :

- **`--extend`** (utilisé ci-dessus) écrit un court fichier qui hérite de tout
  `standard-bom`. Vous n’ajoutez que ce que vous voulez changer, et vous bénéficiez
  gratuitement des améliorations du modèle intégré.
- **Sans `--extend`**, vous obtenez une copie complète avec tous ses commentaires. Utilisez-la
  lorsque vous voulez voir et maîtriser chaque paramètre.

Le nom du modèle vient du nom du fichier (`acme-bom.yaml` devient
`acme-bom`). Utilisez `--name` pour en choisir un autre, et `--force` pour remplacer
un fichier existant.

Comme le fichier se trouve dans `.inventag/templates/`, vous pouvez désormais le désigner par son nom
depuis ce projet.

## 2. Modifiez-le {#2-edit-it}

Le nouveau fichier ressemble à ceci :

```yaml title=".inventag/templates/acme-bom.yaml"
# Inherits everything from 'standard-bom'. Add only what you want to change.
# See: inventag templates show standard-bom --resolved
format_version: 1
kind: report
name: acme-bom
description: "Adapted from standard-bom"
extends: standard-bom
spec: {}
```

Remplacez `spec: {}` par vos modifications. Cette version place tout sur une seule
feuille, utilise un en-tête vert et affiche trois colonnes d’étiquettes :

```yaml
format_version: 1
kind: report
name: acme-bom
description: "Acme's inventory layout"
extends: standard-bom
spec:
  title: Acme Cloud Inventory
  company_name: Acme Ltd
  colors:
    header_fill: "0B5D1E"
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
```

Comment fonctionne l’héritage :

- **Les mappages fusionnent.** Définir `excel.layout` conserve tous les autres paramètres `excel`
  de `standard-bom`.
- **Les listes remplacent.** Si vous définissez `columns`, votre liste remplace celle
  dont vous héritez. Copiez les entrées que vous voulez conserver.
- **`null` réinitialise** une valeur à son défaut, par exemple `tag_policy: null`.
- **Les politiques d’étiquetage fusionnent `required_tags` par clé.** Une politique enfant peut modifier une
  étiquette, en ajouter une ou en retirer une avec `remove: true`, sans répéter le reste.

Pour voir le résultat final après héritage, lancez
`inventag templates show acme-bom --resolved`.

## 3. Validez-le {#3-validate-it}

```bash
inventag templates validate acme-bom
```

Vous pouvez aussi donner un chemin de fichier, par exemple
`inventag templates validate ./acme-bom.yaml`. Toute référence qui contient un
point ou une barre oblique est lue comme un chemin.

En cas de problème, vous obtenez le fichier, la ligne et une suggestion. Ici, le mot
`layout` a été mal saisi en `layuot` :

```text title="Terminal"
ERROR ~/acme-infra/.inventag/templates/acme-bom.yaml:13: spec.excel.layuot: unknown field 'layuot'; did you mean 'layout'? Allowed here: autofilter, freeze_header, include_all_fields, layout, max_column_width, single_sheet_name, summary_sheet, tag_compliance_sheet
(exit code 1)
```

Une fois corrigé :

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/acme-bom.yaml (report 'acme-bom')
```

`validate` se termine avec le code 0 lorsque tous les fichiers sont valides et 1 dans le cas contraire, vous pouvez donc
le lancer en CI. Il vérifie aussi que les modèles que vous référencez (par exemple une
`tag_policy`) existent et sont du bon type.

Votre modèle apparaît maintenant dans la liste :

```bash title="Terminal"
inventag templates list --kind report
```

```text title="Terminal"
NAME                KIND    SOURCE   DESCRIPTION
acme-bom            report  project  Acme's inventory layout
board-report        report  project  Branded summary for the leadership team
executive-summary   report  builtin  Short Word report with totals and tag compliance; Excel has one filterable sheet.
finops-cost-report  report  builtin  Standard layout with cost-allocation tag columns, checked against finops-cost-allocation.
network-review      report  project  Every field, for a network review
standard-bom        report  builtin  Summary plus one sheet per service, with readable columns and every tag as a column.
team-sheet          report  project  One sheet, our columns

Search order (first match wins):
  1. project  ~/acme-infra/.inventag/templates
  2. user     ~/.config/inventag/templates  (not created)
  3. builtin  ~/inventag-aws/inventag/templating/builtin
```

Le projet d’exemple contient aussi les autres modèles utilisés dans cette documentation.

## 4. Utilisez-le {#4-use-it}

```bash
inventag --template acme-bom --create-excel --account-regions us-east-1
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

**Feuilles :** `Summary`, `Resources`

Feuille `Resources`, premières lignes :

| Account | Region | Service | Type | Name | ID | ARN | Tag: Owner | Tag: CostCenter | Tag: Environment |
|---|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs | platform | CC-1001 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake | data | CC-2002 | prod |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports | finance | 1234 | Production |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | acme-scratch | arn:aws:s3:::acme-scratch |  |  |  |

La ligne d’en-tête est verte, comme défini dans le modèle.

## Partager des modèles avec votre équipe {#share-templates-with-your-team}

- **Un projet :** validez `.inventag/templates/` dans le dépôt du projet.
- **Tous les projets de votre machine :** placez les modèles dans
  `~/.config/inventag/templates/`.
- **Un dossier partagé ou une image CI :** définissez
  `INVENTAG_TEMPLATE_PATH=/opt/acme/inventag-templates`.

Si deux dossiers contiennent un modèle du même nom, le premier dans
l’[ordre de recherche](./index.md#where-inventag-looks-for-templates) l’emporte.
`inventag templates list --all` affiche aussi les modèles masqués.

## Étapes suivantes {#next-steps}

- [Référence des modèles](./reference.md) : tous les champs que vous pouvez définir.
- [Créer un rapport Word de direction à votre image](../examples/branded-executive-report.md) :
  ajoutez un logo.
