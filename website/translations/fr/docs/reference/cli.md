---
title: Référence de la ligne de commande
description: Chaque commande et option d’InvenTag, ce qu’elle fait dans la version actuelle et sa valeur par défaut, vérifiées avec inventag --help.
sidebar_position: 1
---

# Référence de la ligne de commande

**À qui s’adresse cette page :** vous avez besoin du nom exact ou du comportement d’une option.

**Ce que vous saurez faire après lecture :** construire n’importe quelle ligne de commande
InvenTag et savoir quelles options fonctionnent aujourd’hui.

Cette page correspond à `inventag --help` de la version que décrit cette version
de la documentation. Exécutez `inventag --help` pour voir les options de la version
installée chez vous. La colonne **État**
indique ce que nous avons observé en exécutant l’option hors ligne sur un AWS simulé.
« Non retesté » signifie que nous ne l’avons pas exécutée pour cette page. Les détails
se trouvent sur la page [État des fonctionnalités](../getting-started/status.md).

## Commandes {#commands}

```text
inventag [flags]                       run a scan and write reports
inventag templates list [--kind K] [--all]
inventag templates show NAME|PATH [--resolved]
inventag templates init NAME|PATH --output FILE|FOLDER [--name NAME] [--extend] [--force]
inventag templates validate NAME|PATH [NAME|PATH ...]
```

La commande `inventag` fonctionne de la même façon sous Linux, macOS et Windows.
`templates` doit être le premier mot après le nom du programme.

## Modèles {#templates}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--template NAME\|PATH` | aucun | Fonctionne | Utilise un modèle. À répéter pour un modèle de rapport, un modèle de politique d’étiquetage et un modèle de configuration. Voir [Modèles](../templates/index.md). |

### Sous-commandes `templates` {#templates-subcommands}

| Commande | Ce qu’elle fait |
|---|---|
| `templates list` | Liste les modèles avec leur type, leur source et leur description, ainsi que les dossiers parcourus. `--kind report\|tag-policy\|config` filtre ; `--all` affiche aussi les modèles masqués par un modèle du même nom. |
| `templates show NAME` | Affiche le fichier. `--resolved` affiche le résultat après `extends` et les valeurs par défaut. |
| `templates init NAME --output PATH` | Copie un modèle dans votre projet. `--extend` écrit un court fichier qui hérite du modèle ; `--name` définit le nom ; `--force` écrase. |
| `templates validate NAME\|PATH ...` | Vérifie les fichiers et les modèles auxquels ils font référence. Code de sortie 0 si tout est valide, 1 sinon. |

## Comptes {#accounts}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--accounts-file FILE` | aucun | Fonctionne | Lit les comptes depuis un fichier JSON ou YAML. Voir [Fichiers de configuration](./configuration-files.md#accounts-file). |
| `--accounts-prompt` | désactivé | Fonctionne | Demande les comptes et les identifiants de manière interactive. |
| `--cross-account-role ARN\|NAME` | aucun | Fonctionne | Un ARN de rôle complet est assumé directement. Un nom de rôle est combiné avec chaque ID de compte de `--accounts-file`. Un nom sans `--accounts-file` s’arrête avec le code de sortie 2. |

## Sortie {#output}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--create-excel` | activé si aucune autre option de sortie | Fonctionne | Écrit `multi_account_bom_<timestamp>.xlsx`. |
| `--create-word` | désactivé | Fonctionne | Écrit `multi_account_bom_<timestamp>.docx`. |
| `--create-google-docs` | désactivé | Fonctionne (clients simulés uniquement) | Crée le rapport Word sous forme de Google Doc. Nécessite le module complémentaire Google (`pip install "inventag-aws[google]"`). Voir [Google Sheets et Docs](../guides/google-sheets-and-docs.md). |
| `--create-google-sheets` | désactivé | Fonctionne (clients simulés uniquement) | Crée le rapport Excel sous forme de feuille de calcul Google Sheets. |
| `--google-credentials FILE` | aucun | Fonctionne (clients simulés uniquement) | Fichier de clé de compte de service. Sans lui, les identifiants par défaut de l’application (Application Default Credentials) sont utilisés. |
| `--google-oauth-client FILE` | aucun | Fonctionne (clients simulés uniquement) | Fichier de client OAuth ; vous vous connectez dans le navigateur. |
| `--google-folder-id ID` | aucun | Fonctionne (clients simulés uniquement) | Dossier Drive pour les fichiers. |
| `--google-share-with EMAIL` | aucun | Fonctionne (clients simulés uniquement) | Partage avec cette adresse. À répéter pour en ajouter d’autres. |
| `--google-share-role ROLE` | `reader` | Fonctionne (clients simulés uniquement) | `reader`, `commenter` ou `writer`. |
| `--google-share-anyone` | désactivé | Fonctionne (clients simulés uniquement) | Toute personne disposant du lien peut lire. Sans cette option, les fichiers sont privés. |
| `--google-title TITLE` | nom daté | Fonctionne (clients simulés uniquement) | Titre des fichiers Google. |
| `--output-directory DIR` | `bom_output` | Fonctionne | Dossier de tous les fichiers de sortie. |
| `--per-account-reports` | désactivé | Fonctionne | Un fichier `<account-id>_bom_<timestamp>` par compte au lieu d’un rapport consolidé. |

## Ce qu’il faut analyser {#what-to-scan}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--account-regions LIST` | toutes les régions activées | Fonctionne | Codes de région séparés par des virgules, par exemple `us-east-1,eu-west-1`. IAM, la liste des buckets S3, CloudFront et Route 53 sont toujours lus une seule fois depuis `us-east-1` ; vous n’avez donc pas besoin de l’indiquer. |
| `--account-services LIST` | tous | Fonctionne | Noms de services séparés par des virgules qui sont conservés dans le rapport, comparés à la colonne Service, par exemple `EC2,S3`. |
| `--account-tags JSON` | aucun | Fonctionne | Filtre d’étiquettes, par exemple `'{"Environment":"prod"}'`. Seules les ressources portant ces étiquettes sont conservées. |
| `--fallback-display auto\|always\|never` | `auto` | Fonctionne | Indique s’il faut afficher les ressources trouvées uniquement par l’API Resource Groups Tagging. `auto` ne les affiche que pour les services dont leur propre code de découverte n’a donné aucun résultat. |
| `--hide-fallback-resources` | désactivé | Non retesté | Identique à `--fallback-display never`. Obsolète. |

## Analyse {#analysis}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--enable-network-analysis` | désactivé | Fonctionne | Ajoute une feuille `Network Analysis` au rapport Excel lorsque des VPC sont trouvés. N’ajoute rien avec `--template`. Voir [Analyse du réseau et de la sécurité](../guides/network-and-security-analysis.md). |
| `--enable-security-analysis` | désactivé | Fonctionne | Ajoute une feuille `Security Analysis` au rapport Excel lorsque des groupes de sécurité sont trouvés. N’ajoute rien avec `--template`. |
| `--enable-cost-analysis` | désactivé | Fonctionne | Ajoute une feuille Cost Analysis (et les quatre colonnes `forgotten_analysis.*`) au classeur par défaut. Effectue des appels supplémentaires à Cost Explorer, Pricing et CloudWatch, y compris avec `--no-billing-validation`. Nécessite `pricing:GetProducts` et `cloudwatch:GetMetricStatistics`. Les coûts sont des estimations de l’API AWS Pricing, pas votre facture. |
| `--billing-validation`, `--no-billing-validation` | activé | Fonctionne | Utilise Cost Explorer pendant la découverte pour repérer les services qui génèrent des dépenses. AWS facture chaque requête Cost Explorer. `--no-billing-validation` arrête ces appels. |

## Fichiers de configuration {#configuration-files}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--tag-mappings FILE` | aucun | Fonctionne | Ajoute une colonne nommée par correspondance. Voir [Fichiers de configuration](./configuration-files.md#tag-mappings). |
| `--service-descriptions FILE` | aucun | Partiel | Ajoute une colonne `service_description`. Une description intégrée l’emporte pour S3, EC2, RDS, Lambda et VPC, sauf si l’entrée indique un `template`. Voir [Fichiers de configuration](./configuration-files.md#service-descriptions). |
| `--bom-config FILE` | aucun | Fonctionne | Définit des champs de la configuration de traitement de la nomenclature (BOM) à partir d’un fichier YAML ou JSON. Les autres clés sont ignorées, avec un avertissement qui les nomme. |
| `--validate-config` | désactivé | Fonctionne | Charge et vérifie la configuration, puis s’arrête. |
| `--validate-config-only` | désactivé | Fonctionne | Vérifie uniquement les fichiers que vous indiquez, puis s’arrête. N’effectue aucun appel AWS. |

## Fichiers de mise en page des rapports {#report-layout-files}

Ces options changent la mise en page des rapports Excel et Word par défaut avec
un fichier YAML ou JSON. Voir [Fichiers de mise en page pour un rapport](../templates/layout-flags.md).

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--word-template PATH` | aucun | Fonctionne | Fichier de mise en page du rapport Word. Nécessite `--create-word` ; sans elle, l’exécution s’arrête avec le code de sortie 2. |
| `--excel-template PATH` | aucun | Fonctionne | Fichier de mise en page du rapport Excel. Avec `--create-word` seul, l’exécution s’arrête avec le code de sortie 2. |
| `--print-default-template word\|excel` | aucun | Fonctionne | Affiche le fichier de mise en page par défaut de ce format, puis quitte avec le code 0. |
| `--validate-templates` | désactivé | Fonctionne | Vérifie les fichiers donnés avec `--word-template` et `--excel-template`, puis quitte. Aucun appel à AWS. Sans l’une de ces options : code de sortie 2. |

## Traitement parallèle {#parallel-processing}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--max-concurrent-accounts N` | `4` | Fonctionne | Nombre de comptes analysés en même temps. |
| `--account-processing-timeout SECONDS` | `1800` | Fonctionne | Durée accordée par compte (au moins 60). |
| `--disable-parallel-processing` | désactivé | Fonctionne | Analyse un compte à la fois. |

## État et suivi des changements {#state-and-change-tracking}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--enable-state-management` | activé | Fonctionne | Enregistre un instantané dans `<output>/state/`. |
| `--disable-state-management` | désactivé | Fonctionne | N’enregistre ni instantanés ni journaux des changements. |
| `--enable-delta-detection` / `--disable-delta-detection` | activé | Fonctionne | Compare le nouvel instantané au précédent. `--disable-delta-detection` n’écrit aucun rapport des changements. |
| `--generate-changelog`, `--no-generate-changelog` | activé | Fonctionne | Écrit `changelog_<timestamp>.md` à partir de la deuxième exécution. `--no-generate-changelog` l’en empêche. |

## Journalisation {#logging}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--verbose`, `-v` | désactivé | Fonctionne | Affiche chaque étape. |
| `--debug`, `-d` | désactivé | Fonctionne | Affiche chaque requête AWS. Les secrets sont masqués. |
| `--log-file FILE` | aucun | Fonctionne | Écrit aussi un journal détaillé dans ce fichier. |
| `--disable-account-logging` | désactivé | Fonctionne | Ne préfixe pas les lignes du journal avec le compte. |

## Identifiants {#credentials}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--validate-credentials` | désactivé | Fonctionne | Vérifie les identifiants de chaque compte, puis s’arrête (0 si tous fonctionnent, 1 sinon). |
| `--credential-timeout SECONDS` | `30` | Fonctionne | Délai d’attente de chaque vérification d’identifiants. |
| `--skip-credential-validation` | désactivé | Fonctionne | Ignore la vérification des identifiants au début d’une exécution. |

## Protection en lecture seule et audit {#read-only-guard-and-audit}

La protection en lecture seule est toujours active. Elle bloque tout appel AWS qui n’est pas
une lecture, ainsi que les lectures qui renvoient des secrets ou des données.

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--audit-output FILE` | aucun | Fonctionne | Écrit une liste JSON de chaque opération AWS appelée pendant l’exécution, autorisée ou bloquée. |
| `--validate-operations SERVICE:OPERATION ...` | aucun | Fonctionne | Vérifie des opérations par rapport à la protection, puis s’arrête (0 si toutes sont autorisées, 1 sinon). |
| `--enforce-read-only`, `--security-validation`, `--enable-production-safety` | activé | Sans effet | Conservées pour que les anciennes commandes fonctionnent encore. La protection est toujours active. |
| `--disable-production-safety` | désactivé | S’arrête avec le code de sortie 2 | La protection ne peut pas être désactivée. |
| `--compliance-standard ...` | aucun | S’arrête avec le code de sortie 2 | Non implémentée : une norme ne peut pas être vérifiée à partir d’un inventaire. Utilisez un modèle de politique d’étiquetage. |
| `--risk-threshold LEVEL` | aucun | Fonctionne | Avec `--enable-security-analysis` : code de sortie 4 si une règle de groupe de sécurité atteint ou dépasse `LOW`, `MEDIUM`, `HIGH` ou `CRITICAL`. Sans `--enable-security-analysis` : code de sortie 2. |

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

Ce qu’affichent les options qui s’arrêtent avec le code de sortie 2 :

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)

$ inventag --risk-threshold HIGH
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## Téléversement vers S3 {#s3-upload}

| Option | Par défaut | État | Ce qu’elle fait |
|---|---|---|---|
| `--s3-bucket BUCKET` | aucun | Fonctionne | Téléverse dans ce bucket chaque fichier écrit pendant l’exécution (Excel, Word et JSON de conformité des étiquettes). L’exécution se termine avec le code 1 si un téléversement échoue. Nécessite `s3:PutObject`. |
| `--s3-key-prefix PREFIX` | `bom-reports/` | Fonctionne | Dossier (préfixe de clé) dans le bucket. Les fichiers sont placés sous `<prefix><UTC timestamp>/`. |
| `--s3-encryption AES256\|aws:kms` | `AES256` | Fonctionne | Chiffrement côté serveur des fichiers téléversés. |
| `--s3-kms-key-id KEY` | aucun | Fonctionne | Clé KMS pour `aws:kms`. |

Voir [Téléverser des rapports vers S3 selon un calendrier](../examples/scheduled-s3-upload.md).

## Codes de sortie {#exit-codes}

| Code | Signification |
|---|---|
| 0 | Succès. Vaut aussi 0 lorsque certains comptes ont échoué mais que d’autres ont fonctionné, et lorsqu’aucune ressource n’a été trouvée (aucun rapport n’est écrit). Voir [État des fonctionnalités](../getting-started/status.md#when-a-run-goes-wrong). |
| 1 | Une erreur : arguments, configuration ou modèle non valides, échec des identifiants, échec de tous les comptes, échec d’un téléversement S3, ou format de rapport impossible à écrire |
| 2 | Ligne de commande non valide : options inconnues ou mal formées, options non implémentées, options Google incorrectes, option de fichier de mise en page sans le rapport dont elle a besoin, ou nom de rôle sans `--accounts-file` |
| 3 | Rapports écrits, mais un modèle de configuration avec `fail_on_tag_violations: true` a trouvé des violations de la politique d’étiquetage |
| 4 | Rapports écrits, mais `--risk-threshold` a trouvé une règle de groupe de sécurité égale ou supérieure à ce niveau |
