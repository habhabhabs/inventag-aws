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

Donnez `--accounts-file` ou `--accounts-prompt`, pas les deux. Un ARN de rôle complet dans `--cross-account-role` désigne un seul compte, il ne peut donc pas aller avec l’un ou l’autre. Ces deux erreurs arrêtent l’exécution avec le code de sortie 2.

## Choisir les régions {#choose-the-regions}

```bash
inventag --account-regions us-east-1,eu-west-1 --create-excel
```

Sans `--account-regions`, InvenTag demande à EC2 quelles régions sont activées dans
le compte et les analyse toutes. C’est complet mais lent. Si `ec2:DescribeRegions`
échoue, InvenTag interroge `account:ListRegions`. Si cela échoue aussi, il journalise
un avertissement et essaie toutes les régions de la partition que connaît votre AWS SDK.
Les régions que le compte n’a pas activées échouent à la vérification d’accès et sont
ignorées. Utilisez `--account-regions` pour choisir vous-même les régions.

Une région dont la vérification d’accès échoue est ignorée avec un avertissement. Si la vérification
échoue dans toutes les régions, parce que l’identité n’a pas `ec2:DescribeRegions`, InvenTag ne peut pas
savoir lesquelles fonctionnent et les analyse toutes.

### Services globaux {#global-services}

Vous n’avez pas besoin d’ajouter la région d’origine à la liste. Quel que soit le choix de régions,
InvenTag lit une fois les services globaux de chaque compte, depuis la région d’origine de la partition :
`us-east-1` dans la partition standard, `cn-north-1` en Chine et `us-gov-west-1` dans GovCloud.
Ce sont IAM, la liste des buckets S3, CloudFront, Route 53 et les certificats ACM utilisés par
CloudFront. Si la région d’origine figure dans votre liste, ils ne sont pas lus deux fois.

- `--account-services` et `--account-tags` s’y appliquent comme à n’importe quelle autre
  ressource. Avec `--account-services ec2`, aucune ressource IAM n’est lue.
- Les ressources IAM, CloudFront et Route 53 affichent `global` dans la colonne de région.
  Un bucket S3 affiche sa propre région, par exemple `eu-west-1`.
- Leurs étiquettes proviennent de l’API Resource Groups Tagging dans la région d’origine, où
  AWS conserve les étiquettes des ressources globales.
- Des tests hors ligne couvrent `eu-west-1` seule, toutes les régions, et une liste qui inclut
  `us-east-1`. La réponse du vrai AWS n’est pas testée.

### Services {#services}

InvenTag dispose de ses propres appels de listage en lecture seule pour 46 services AWS. Les ressources des autres services n’apparaissent que si l’API Resource Groups Tagging les renvoie.
Voir [État des fonctionnalités](../getting-started/status.md).

### Limitation de débit et appels en échec {#throttling-and-failed-calls}

InvenTag réessaie un appel limité jusqu’à 10 fois au total (le mode de nouvelles tentatives
« standard » de l’AWS SDK). Si vous définissez `AWS_RETRY_MODE` ou `AWS_MAX_ATTEMPTS`, vos valeurs sont utilisées.
Un listage qui échoue encore est journalisé comme avertissement pour ce service et cette région :
`<service> <operation> in <region> failed (<error>); its resources there may be incomplete.`
La sortie JSON enregistre comment chaque listage s’est terminé. Une autorisation refusée n’est journalisée qu’une fois par service.

## Limite de temps et comptes en parallèle {#time-limit-and-parallel-accounts}

InvenTag analyse jusqu’à quatre comptes à la fois. Modifiez cela avec `--max-concurrent-accounts`
(au moins 1), ou utilisez `--disable-parallel-processing` pour analyser un compte à la fois.

Chaque compte dispose de `--account-processing-timeout` secondes (1800 par défaut, au moins 60),
comptées à partir du début de l’analyse de ce compte. La découverte s’arrête un peu avant,
de 300 secondes ou de 20 % de la limite, selon la plus petite des deux valeurs, afin que les étiquettes, les détails et la facturation puissent encore être lus.

Un compte qui manque de temps est signalé comme en échec, et les autres comptes sont conservés.
Les ressources qu’il a trouvées avant la limite restent dans le rapport, et les notes du rapport indiquent que le compte est incomplet.
Une ligne de journal d’une exécution hors ligne avec `--account-processing-timeout 60` (données d’exemple) :

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

Si aucun compte ne se termine, InvenTag écrit quand même le rapport avec ce qu’il a trouvé, journalise `No account finished within its time limit` et se termine avec le code 1.

## Reprendre après une exécution en échec {#continue-after-a-failed-run}

Quand certains comptes échouent, InvenTag enregistre ceux qui ont terminé dans `bom_output/state/partial/`.
Corrigez la cause, puis relancez la même commande avec `--resume`. InvenTag n’analyse que les comptes manquants :

```bash
inventag --accounts-file accounts.yaml --create-excel --resume
```

InvenTag ne réutilise un résultat enregistré que si la commande utilisait les mêmes comptes, régions, services et filtres,
et que le résultat n’est pas plus ancien que `--resume-max-age-hours` (24 par défaut, 168 au maximum).
Cela nécessite la gestion d’état : `--resume` avec `--disable-state-management` s’arrête donc avec le code de sortie 2.
Le journal indique `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)`, et les notes du rapport
listent chaque compte réutilisé avec son heure d’analyse. Sans `--resume`, un avertissement signale que des résultats enregistrés existent
et qu’ils sont analysés de nouveau. InvenTag supprime les résultats enregistrés après une exécution où tous les comptes se terminent.

## Choisir les fichiers de sortie {#choose-the-output-files}

| Option | Écrit |
|---|---|
| `--create-excel` | `multi_account_bom_<timestamp>.xlsx` |
| `--create-word` | `multi_account_bom_<timestamp>.docx` |
| `--template <name>` | Les mêmes fichiers, mis en page par un [modèle de rapport](../templates/index.md) |
| `--output-directory reports` | Écrit tout dans `reports/` au lieu de `bom_output/` |

Si vous ne donnez aucune option de sortie, InvenTag n’écrit que le fichier Excel. Si l’analyse ne trouve
aucune ressource, ou si vos filtres les écartent toutes, InvenTag n’écrit aucun fichier, journalise
`No resources to report (none found, or the filters removed all of them).` et se termine tout de même avec le code 0. Avec `--template`, il écrit un rapport qui ne liste aucune ressource. Ajoutez `--s3-bucket` pour téléverser aussi les fichiers : voir
[Téléverser les rapports vers S3 selon un calendrier](../examples/scheduled-s3-upload.md).

Exemple de sortie d’une exécution avec `--template standard-bom --create-excel
--create-word --account-regions us-east-1` (hors ligne, données d’exemple) :

```text title="Sortie"
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

Le code de sortie 0 signifie que les fichiers sont valides. Avec `--skip-credential-validation`, la première commande
n’effectue aucun appel AWS. Un fichier de comptes incorrect ressemble à ceci (données d’exemple) :

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

## Codes de sortie {#exit-codes}

InvenTag se termine avec le code 0 même si un compte a échoué ou si rien n’a été trouvé. Deux options changent cela. Avec le code 5, les rapports sont quand même écrits.

| Option | Code de sortie | Quand |
|---|---|---|
| `--fail-on-account-error` | 5 | Un compte n’a pas pu être analysé, ou seulement en partie |
| `--fail-if-empty` | 6 | Aucune ressource à signaler |

La liste complète est dans [Exécuter InvenTag en CI/CD](./run-in-ci.md#exit-codes).

## Étapes suivantes {#next-steps}

- [Analyser plusieurs comptes](./scan-multiple-accounts.md)
- [Vérifier les étiquettes selon une politique](./check-tag-compliance.md)
- [Référence de la CLI](../reference/cli.md)
