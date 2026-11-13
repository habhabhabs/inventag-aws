---
title: Choisir ce qu’il faut analyser et produire
description: Choisissez les comptes, les régions et les fichiers de sortie d’une exécution InvenTag, conservez les journaux et décidez où les rapports sont écrits.
sidebar_position: 1
slug: /user-guides/cli-user-guide
---

# Choisir ce qu’il faut analyser et produire

**À qui s’adresse cette page :** vous avez déjà lancé InvenTag une fois et vous voulez contrôler ce qu’il
analyse et ce qu’il écrit.

**Ce que vous saurez faire après lecture :** choisir les comptes, les régions, les fichiers de sortie et la
journalisation d’une exécution. Pour toutes les options, voir la [référence de la CLI](../reference/cli.md).

La commande `inventag` fonctionne de la même façon sous Linux, macOS et Windows.

## Choisir les comptes {#choose-the-accounts}

| Vous voulez analyser... | Utilisez |
|---|---|
| Le compte de vos identifiants actuels | Rien de plus |
| Un autre compte, via un rôle | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly` (un ARN de rôle complet) |
| Plusieurs comptes | `--accounts-file accounts.yaml` ou un modèle de configuration : [Analyser plusieurs comptes](./scan-multiple-accounts.md) |
| Plusieurs comptes, avec le même nom de rôle dans chacun | `--accounts-file accounts.yaml --cross-account-role InvenTagReadOnly` |
| Des comptes saisis à la demande | `--accounts-prompt` |

## Choisir les régions {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

Sans `--account-regions`, InvenTag demande à EC2 quelles régions sont activées dans
le compte et les analyse toutes. C’est complet mais lent. Si cette recherche
échoue, InvenTag journalise un avertissement et n’analyse que `us-east-1`, `us-west-2`,
`eu-west-1` et `ap-southeast-1`.

Une région dont la vérification d’accès échoue est ignorée avec un avertissement.

### Services globaux {#global-services}

Vous n’avez pas besoin d’ajouter `us-east-1` à la liste. Quel que soit le choix de régions,
InvenTag lit une fois les services globaux de chaque compte, depuis `us-east-1` :
IAM, la liste des buckets S3, CloudFront, Route 53 et les certificats ACM utilisés par
CloudFront. Si `us-east-1` figure dans votre liste, ils ne sont pas lus deux fois.

- `--account-services` et `--account-tags` s’y appliquent comme à n’importe quelle autre
  ressource. Avec `--account-services ec2`, aucune ressource IAM n’est lue.
- Les ressources IAM, CloudFront et Route 53 affichent `global` dans la colonne de région.
  Un bucket S3 affiche sa propre région, par exemple `eu-west-1`.
- Leurs étiquettes proviennent de l’API Resource Groups Tagging dans `us-east-1`, où
  AWS conserve les étiquettes des ressources globales.
- Des tests hors ligne couvrent `eu-west-1` seule, toutes les régions, et une liste qui inclut
  `us-east-1`. La réponse du vrai AWS n’est pas testée.

## Choisir les fichiers de sortie {#choose-the-output-files}

| Option | Écrit |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | Les mêmes fichiers, mis en page par un [modèle de rapport](../templates/index.md) |
| `--output-directory reports` | Écrit tout dans `reports/` au lieu de `bom_output/` |

Si vous ne donnez aucune option de sortie, InvenTag n’écrit que le fichier Excel. Si l’analyse ne trouve
aucune ressource, ou si vos filtres les écartent toutes, InvenTag n’écrit aucun fichier et
se termine tout de même avec le code 0. Ajoutez `--s3-bucket` pour téléverser aussi les fichiers : voir
[Téléverser les rapports vers S3 selon un calendrier](../examples/scheduled-s3-upload.md).

Exemple de sortie d’une exécution avec `--template standard-bom --create-excel
--create-word --account-regions us-east-1` (hors ligne, données d’exemple) :

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

## Regrouper plusieurs réglages dans un seul fichier {#combine-several-settings-in-one-file}

Si vous lancez toujours InvenTag avec les mêmes réglages, placez-les dans un
[modèle de configuration](../templates/catalogue.md#config-templates) plutôt que de
les retaper :

```bash
inventag templates init single-account --output .inventag/templates/my-scan.yaml
# edit regions and outputs, then:
inventag --template my-scan
```

Les options que vous tapez l’emportent toujours sur le modèle.

## Voir ce qui se passe {#see-what-is-happening}

| Option | Affiche |
|---|---|
| (aucune) | Les avertissements, les erreurs et l’endroit où les fichiers ont été écrits. Les erreurs d’autorisation AWS pour des appels isolés ne sont pas affichées. |
| `--verbose` ou `-v` | Chaque étape de l’exécution |
| `--log-file run.log` | Écrit aussi un journal détaillé dans un fichier |
| `--debug` ou `-d` | Chaque requête AWS. Les secrets sont masqués, mais considérez le journal comme sensible. |
| `--audit-output audit.json` | Une liste JSON de chaque opération AWS appelée par l’exécution |

## Valider les fichiers de configuration sans analyser {#validate-configuration-files-without-scanning}

```bash title="Terminal"
inventag --accounts-file accounts.yaml --validate-config-only --skip-credential-validation
inventag templates validate my-scan
```

Le code de sortie 0 signifie que les fichiers sont valides. La première commande effectue quand même un appel
`ec2:DescribeRegions` pour lister les régions ; s’il échoue, elle journalise un avertissement et
continue. Un fichier de comptes incorrect ressemble à ceci (données d’exemple) :

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

## Étapes suivantes {#next-steps}

- [Analyser plusieurs comptes](./scan-multiple-accounts.md)
- [Vérifier les étiquettes selon une politique](./check-tag-compliance.md)
- [Référence de la CLI](../reference/cli.md)
