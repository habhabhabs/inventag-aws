---
title: Résoudre les problèmes courants
description: Les erreurs d’InvenTag les plus fréquentes - identifiants, autorisations, régions, limitation de débit, modèles et fichiers de configuration - avec les vrais messages et la façon de les corriger.
sidebar_position: 8
---

# Résoudre les problèmes courants

**À qui s’adresse cette page :** quelque chose s’est mal passé et vous voulez la correction la plus rapide.

**Ce que vous saurez faire après lecture :** reconnaître le message que vous voyez et corriger
sa cause.

Les messages ci-dessous sont de vraies sorties d’InvenTag issues d’exécutions hors ligne (données d’exemple).
Lorsqu’une erreur AWS ne peut pas être produite hors ligne, comme un jeton expiré, nous avons
simulé la réponse d’erreur exacte d’AWS et enregistré la façon dont InvenTag l’a signalée.
Ces blocs sont marqués « simulated AWS error response ».

Ajoutez `--verbose` pour voir chaque étape, ou `--debug` pour voir chaque appel AWS. Les journaux de débogage
masquent les secrets, mais considérez-les comme sensibles.

## Identifiants {#credentials}

### Aucun identifiant trouvé {#no-credentials-found}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ No AWS credentials found!
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Set AWS environment variables:
inventag.cli.main - ERROR -       export AWS_ACCESS_KEY_ID=your-key
inventag.cli.main - ERROR -       export AWS_SECRET_ACCESS_KEY=your-secret
inventag.cli.main - ERROR -    3. Use IAM roles if running on EC2/ECS/Lambda
inventag.cli.main - ERROR -    4. Use --accounts-prompt for interactive setup
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**Correction :** connectez-vous, par exemple avec `aws sso login --profile my-readonly` et
`export AWS_PROFILE=my-readonly`, puis vérifiez avec
`aws sts get-caller-identity`.

### Identifiants expirés ou non valides {#expired-or-invalid-credentials}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ AWS credential validation failed!
inventag.cli.main - ERROR -    Issue: Invalid or expired security token
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Check if your access keys are correct
inventag.cli.main - ERROR -    3. If using temporary credentials, they may have expired
inventag.cli.main - ERROR -    4. If using AWS SSO, run 'aws sso login'
inventag.cli.main - ERROR -
inventag.cli.main - ERROR - 💡 Quick diagnostic commands:
inventag.cli.main - ERROR -    aws configure list          # Show current config
inventag.cli.main - ERROR -    aws sts get-caller-identity # Test credentials
inventag.cli.main - ERROR -    aws configure               # Set up new credentials
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**Correction :** connectez-vous de nouveau (`aws sso login --profile <name>`), ou renouvelez vos
clés temporaires. Si vous utilisez des clés d’accès, vérifiez-les avec `aws configure list`.

### Un rôle ne peut pas être assumé {#a-role-cannot-be-assumed}

**Ce que vous voyez :** ceci dans le journal, et un rapport où le compte est absent :

```text
inventag.core.cloud_bom_generator.CloudBOMGenerator - ERROR - Failed to establish context for account 999999999999: Role assumption failed for account 999999999999: An error occurred (AccessDenied) when calling the AssumeRole operation: ...
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Skipping account 999999999999 due to invalid session
```

Si d’autres comptes ont fonctionné, InvenTag écrit tout de même leur rapport et **se termine avec le
code 0**. Si tous les comptes échouent, il se termine avec le code 1. (Texte des messages issu d’une
exécution hors ligne avec une erreur AWS simulée.)

**Correction :** vérifiez l’ARN du rôle, et vérifiez que la politique d’approbation du rôle autorise
votre identité. InvenTag ne se rabat pas sur d’autres identifiants ; ce
compte est donc ignoré tant que le problème n’est pas résolu.

### Un nom de rôle sans fichier de comptes {#a-role-name-without-an-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
$ echo $?
2
```

**Correction :** transmettez l’ARN complet du rôle, ou ajoutez `--accounts-file` avec les ID
de compte.

## Autorisations {#permissions}

### Accès à Cost Explorer refusé {#cost-explorer-access-denied}

InvenTag continue sans données de facturation et l’exécution réussit ; le problème
passe donc facilement inaperçu. Il n’apparaît qu’avec `--debug` :

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0

$ # the same run with --debug, lines that mention AccessDeniedException
Cost Explorer data is not available, so billing checks are skipped: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

**Correction :** ajoutez `ce:GetCostAndUsage` à la politique, ou acceptez que les données
de facturation soient absentes.

### Un service ou une colonne est vide {#a-service-or-column-is-empty}

**Cause :** l’identité n’a pas d’autorisation `List*`, `Describe*` ou `Get*` pour
ce service. La découverte continue sans elle et n’affiche aucun message. L’erreur AWS
n’est consignée qu’au niveau de débogage, où elle est difficile à trouver dans la longue
sortie. Exécutez l’appel AWS CLI correspondant avec la même identité pour vérifier.

**Correction :** utilisez la politique de `config/defaults/iam-policy-read-only.json`, qui
couvre chaque appel qu’InvenTag effectue. Voir [Autorisations IAM](../reference/iam-permissions.md).

### Bloqué par la protection en lecture seule {#blocked-by-the-read-only-guard}

**Ce que vous voyez :** `Read-only guard blocked <service>:<Operation>` dans le journal,
et une erreur qui commence par `Blocked AWS operation <service>:<Operation>`.

**Cause :** un appel qui n’est pas une lecture a atteint la protection. InvenTag lui-même
n’effectue pas de tels appels ; il s’agit donc généralement de code personnalisé ou d’un module d’extension.

**Correction :** vérifiez de quelle opération il s’agit avec
`inventag --validate-operations <service>:<Operation>`. La protection ne peut pas être
désactivée.

## Régions {#regions}

### Une région n’est pas activée pour le compte {#a-region-is-not-enabled-for-the-account}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0
```

L’exécution continue avec les régions qui fonctionnent.

**Correction :** retirez la région de `--account-regions`, ou activez-la pour le
compte dans la console AWS (Account settings, AWS Regions).

## Limitation de débit {#throttling}

Lorsque trop de requêtes arrivent en même temps, AWS les ralentit. Le kit de développement
logiciel (SDK) AWS réessaie automatiquement. Nous n’avons pas testé la façon dont
InvenTag signale une limitation de débit qui persiste après les nouvelles tentatives.

**Correction :** analysez moins de comptes à la fois (`--max-concurrent-accounts 2`), analysez
moins de régions, ou accordez plus de temps aux gros comptes
(`--account-processing-timeout 3600`).

## Modèles et fichiers de configuration {#templates-and-configuration-files}

### Modèle non valide {#invalid-template}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
$ echo $?
1
```

**Correction :** corrigez le champ sur la ligne indiquée. Exécutez
`inventag templates validate <file>` pour vérifier sans lancer d’analyse.

### Nom de modèle inconnu {#unknown-template-name}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
$ echo $?
1
```

**Correction :** vérifiez l’orthographe avec `inventag templates list`. Les modèles de projet
doivent se trouver dans `.inventag/templates/`, dans le dossier d’où vous lancez la commande.

### Fichier de comptes non valide {#invalid-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

**Correction :** mettez les ID de compte entre guillemets (`account_id: "123456789012"`), et donnez à
chaque compte `profile_name`, `role_arn` ou des clés d’accès.

### Autres messages de modèle {#other-template-messages}

| Le message contient | Correction |
|---|---|
| `did you mean '...'?` | Corrigez l’orthographe sur la ligne indiquée. |
| `Put account IDs in quotes` | Écrivez `account_id: "012345678901"`. |
| `must stay inside the template's folder` | Déplacez le fichier référencé à côté du modèle, ou dans un sous-dossier. |
| `templates must not contain credentials` | Supprimez les clés d’accès ; utilisez `profile_name` ou `role_arn`. |
| `--template given two report templates` | Donnez au plus un modèle de chaque type. |

## Options qui arrêtent l’exécution {#flags-that-stop-the-run}

Deux options sont acceptées mais arrêtent l’exécution avec le code de sortie 2 et un message qui commence par le nom de l’option. `--compliance-standard` indique qu’elle n’est pas encore implémentée. `--disable-production-safety` indique que la protection en lecture seule ne peut pas être désactivée. Voir
[État des fonctionnalités et limites connues](../getting-started/status.md).

## Code de sortie 3 {#exit-code-3}

Ce n’est pas une erreur d’InvenTag. Une politique d’étiquetage a trouvé des violations et le modèle
de configuration contient `fail_on_tag_violations: true`. Ouvrez la feuille Tag Compliance ou
le fichier JSON pour voir quelles ressources sont concernées.

## Les rapports semblent incorrects {#reports-look-wrong}

| Ce que vous voyez | Cause et correction |
|---|---|
| Des feuilles très larges avec des colonnes `raw_data.*` | C’est la mise en page par défaut. Utilisez `--template standard-bom`. |
| Les colonnes de correspondance d’étiquettes sont absentes | Les correspondances d’étiquettes n’ajoutent des colonnes qu’au classeur par défaut. Avec `--template`, utilisez `tag_columns`. Voir [Fichiers de configuration](../reference/configuration-files.md#tag-mappings). |
| Une description de service personnalisée est ignorée | S3, EC2, RDS, Lambda et VPC ont des descriptions intégrées qui l’emportent, sauf si votre entrée indique un `template`. Voir [Fichiers de configuration](../reference/configuration-files.md#service-descriptions). |
| Aucune feuille réseau ni sécurité | Ajoutez `--enable-network-analysis` ou `--enable-security-analysis`, et vérifiez que l’analyse a trouvé des VPC ou des groupes de sécurité. Ces options n’ajoutent rien avec `--template`. Voir [Analyse du réseau et de la sécurité](./network-and-security-analysis.md). |
| Des ressources IAM, S3, CloudFront ou Route 53 sont absentes | `--account-services` ou `--account-tags` les a retirées, ou l’identité n’a pas l’autorisation (cherchez un avertissement par service dans le journal). La liste des régions n’a pas d’importance : les services globaux sont toujours lus depuis `us-east-1`. |
| Une ressource n’affiche aucune étiquette, ou apparaît deux fois | Exécutez avec `--debug` et comparez la colonne ARN avec l’ARN dans la console AWS. Signalez toute différence dans un problème (issue), avec le service et le type de ressource. |
| Aucun fichier de rapport, et le code de sortie est 0 | L’analyse n’a rien trouvé, ou `--account-services` ou `--account-tags` a tout retiré. Cherchez `No resources to report` dans le journal. |
| Un compte est absent du rapport | Ses identifiants ou son rôle ont échoué. Voir [Un rôle ne peut pas être assumé](#a-role-cannot-be-assumed). |
| Le rapport des changements est absent | La première exécution n’en écrit aucun. Il faut aussi que la gestion de l’état et la détection des différences soient activées. Voir [Suivre les changements entre les exécutions](./track-changes.md). |
| Un autre utilisateur ne peut pas ouvrir `bom_output/` | Les fichiers de sortie sont privés pour l’utilisateur qui a exécuté InvenTag. Partagez-les volontairement. |

## Du bruit que vous pouvez ignorer {#noise-you-can-ignore}

Certains messages ressemblent à des erreurs mais ne changent rien à votre rapport.

| Message | Pourquoi vous pouvez l’ignorer |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'`` (avec `--service-descriptions`) | Le modèle de description VPC attend un champ que la ressource n’a pas. Le rapport n’est pas affecté. |
| `No account specification method provided. Using default AWS credentials.` | Vous n’avez désigné aucun compte ; InvenTag a donc utilisé vos identifiants actuels. C’est le cas normal. |
| `Cross-account role ... not usable ... trying default credentials` | InvenTag a essayé le nom de rôle par défaut, n’a pas pu l’assumer et a continué avec vos propres identifiants. Le message est consigné une fois par compte. |

## Problèmes d’installation {#install-problems}

Voir [Installer InvenTag](../getting-started/installation.md#fix-install-problems).

## Toujours bloqué ? {#still-stuck}

Ouvrez un [problème (issue)](https://github.com/habhabhabs/inventag-aws/issues) avec la
commande exécutée, la version (`python -m pip show inventag-aws`, ou `git describe --tags` dans un clone) et le message. Retirez
les ID et les noms de compte que vous ne voulez pas partager. Ne collez jamais d’identifiants.
