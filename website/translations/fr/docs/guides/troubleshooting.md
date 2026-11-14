---
title: Résoudre les problèmes courants
description: Les erreurs d’InvenTag les plus fréquentes (identifiants, autorisations, régions, limitation, modèles, configuration), avec les vrais messages et les solutions.
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

```text title="Sortie"
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
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
1
```

**Correction :** connectez-vous, par exemple avec `aws sso login --profile my-readonly` et
`export AWS_PROFILE=my-readonly`, puis vérifiez avec
`aws sts get-caller-identity`.

Non vérifié sur l’AWS CLI : les commandes de cette correction.

### Identifiants expirés ou non valides {#expired-or-invalid-credentials}

```text title="Sortie (simulated AWS error response)"
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
```

```bash title="Terminal"
echo $?
```

```text title="Sortie (simulated AWS error response)"
1
```

**Correction :** connectez-vous de nouveau (`aws sso login --profile <name>`), ou renouvelez vos
clés temporaires. Si vous utilisez des clés d’accès, vérifiez-les avec `aws configure list`.

Non vérifié sur l’AWS CLI : les commandes de cette correction.

### Un rôle ne peut pas être assumé {#a-role-cannot-be-assumed}

**Ce que vous voyez :** ceci dans le journal, et un rapport où le compte est absent :

```text
inventag.core.cloud_bom_generator.CloudBOMGenerator - ERROR - Failed to establish context for account 999999999999: Role assumption failed for account 999999999999: An error occurred (AccessDenied) when calling the AssumeRole operation: ...
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Skipping account 999999999999 due to invalid session
```

Si d’autres comptes ont fonctionné, InvenTag écrit tout de même leur rapport et **se termine avec le code 0**, ou avec le code 5 si vous passez `--fail-on-account-error`. La feuille `Summary` et le rapport Word ont une section « Run notes » (notes d’exécution) qui nomme le compte, et le journal se termine par cette liste :

```text
1 of 2 account(s) finished and were saved. Run the same command with --resume within 24 hours to scan only the other 1.
1 account(s) were not scanned, or only partly. The report does not include them:
  - 222222222222 (Dev): Context establishment failed: Role assumption failed for account 222222222222: ...
```

Si tous les comptes échouent, InvenTag se termine avec le code 1 et n’écrit aucun rapport : `Resource discovery failed for all 1 configured account(s); no report was generated`. (Texte des messages issu d’une exécution hors ligne avec une erreur AWS simulée.)

**Correction :** vérifiez l’ARN du rôle, et vérifiez que la politique d’approbation du rôle autorise
votre identité. InvenTag n’analyse pas le compte avec des identifiants appartenant à un autre compte ; ce compte est donc ignoré tant que le rôle ne fonctionne pas. Exécutez ensuite la même commande avec `--resume` pour n’analyser que les comptes manquants.

### Un nom de rôle sans fichier de comptes {#a-role-name-without-an-accounts-file}

```text title="Sortie"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
2
```

**Correction :** transmettez l’ARN complet du rôle, ou ajoutez `--accounts-file` avec les ID
de compte.

## Autorisations {#permissions}

### Accès à Cost Explorer refusé {#cost-explorer-access-denied}

InvenTag continue sans données de facturation et l’exécution réussit ; le problème
passe donc facilement inaperçu. Il n’apparaît qu’avec `--debug` :

```text title="Sortie (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

```bash title="Terminal"
echo $?
```

```text title="Sortie (simulated AWS error response)"
0
```

```bash title="Terminal"
# the same run with --debug, lines that mention AccessDeniedException
```

```text title="Sortie (simulated AWS error response)"
[AWS Account 123456789012 (moto)] inventag.discovery.inventory - WARNING - No permission for the Cost Explorer API (AccessDeniedException). Skipping billing validation; add ce:GetCostAndUsage or use --no-billing-validation.
[AWS Account 123456789012 (moto)] inventag.discovery.comprehensive_discovery - WARNING - Cost Explorer data is not available, so billing checks are skipped: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

**Correction :** ajoutez `ce:GetCostAndUsage` à la politique, ou acceptez que les données
de facturation soient absentes.

### Un service ou une colonne est vide {#a-service-or-column-is-empty}

**Cause :** l’identité n’a pas d’autorisation `List*`, `Describe*` ou `Get*` pour
ce service. Pour un appel de liste, InvenTag consigne un avertissement pour le service et continue sans ses ressources :

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

Pour un appel qui complète un détail d’une ressource, la découverte continue sans message et laisse ce détail vide. L’erreur AWS n’est consignée qu’au niveau de débogage. Exécutez l’appel AWS CLI correspondant avec la même identité pour vérifier.

**Correction :** utilisez la politique de `config/defaults/iam-policy-read-only.json`, qui
couvre chaque appel qu’InvenTag effectue. Voir [Autorisations IAM](../reference/iam-permissions.md).

### Bloqué par la protection en lecture seule {#blocked-by-the-read-only-guard}

**Ce que vous voyez :** `Read-only guard blocked <service>:<Operation>` dans le journal,
et une erreur qui commence par `Blocked AWS operation <service>:<Operation>`.

**Cause :** un appel qui n’est pas une lecture, ou une lecture qui renvoie des secrets ou des données de clients (par exemple `cloudformation:GetTemplate` ou `ssm:GetParameter`), a atteint la protection. Cela ne devrait pas arriver lors d’une exécution normale. Si c’est le cas, ouvrez un ticket (issue) avec le nom de l’opération. Voir [Ce que bloque la protection en lecture seule](./read-only-access.md#what-the-read-only-guard-blocks).

**Correction :** vérifiez de quelle opération il s’agit avec
`inventag --validate-operations <service>:<Operation>`. La protection ne peut pas être
désactivée.

## Régions {#regions}

### Une région n’est pas activée pour le compte {#a-region-is-not-enabled-for-the-account}

```text title="Sortie (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

```bash title="Terminal"
echo $?
```

```text title="Sortie (simulated AWS error response)"
0
```

L’exécution continue avec les régions qui fonctionnent.

**Correction :** retirez la région de `--account-regions`, ou activez-la pour le
compte dans la console AWS (Account settings, AWS Regions).

Non vérifié sur un vrai AWS : le chemin dans la console pour activer une région.

### La liste des régions ne peut pas être lue {#the-list-of-regions-cannot-be-read}

Si `ec2:DescribeRegions` échoue, InvenTag interroge `account:ListRegions`, puis essaie toutes les régions de la partition :

```text
ec2:DescribeRegions failed (An error occurred (UnauthorizedOperation) when calling the DescribeRegions operation: ...); trying account:ListRegions instead.
account:ListRegions failed (An error occurred (AccessDeniedException) when calling the ListRegions operation: ...).
Could not read the account's enabled regions. Trying all 34 regions of the aws partition known to botocore; regions the account has not enabled will fail the access check and be skipped. Use --account-regions to choose.
```

La vérification d’accès de chaque région utilise aussi `ec2:DescribeRegions`. Si elle est refusée dans toutes les régions, InvenTag ne peut pas savoir lesquelles fonctionnent :

```text
ec2:DescribeRegions is denied in every region, so region access cannot be checked; scanning all 34 regions.
```

Le nombre de régions provient de l’AWS SDK installé (botocore) et change avec sa version.

**Correction :** autorisez `ec2:DescribeRegions`, ou nommez les régions avec `--account-regions`.

## Limitation de débit {#throttling}

Lorsque trop de requêtes arrivent en même temps, AWS les ralentit. Le kit de développement
logiciel (SDK) AWS réessaie automatiquement, jusqu’à 10 tentatives au total.
Si une liste échoue encore après cela, InvenTag consigne un avertissement pour le service et la région, et ses ressources à cet endroit peuvent manquer dans le rapport :

```text
sqs list_queues in us-east-1 failed (ThrottlingException); its resources there may be incomplete.
```

**Correction :** analysez moins de comptes à la fois (`--max-concurrent-accounts 2`), analysez
moins de régions, ou accordez plus de temps aux gros comptes
(`--account-processing-timeout 3600`).

Non vérifié sur un vrai AWS : que moins de comptes ou de régions à la fois réduisent la limitation des requêtes.

## Limites de temps et résultats partiels {#time-limits-and-partial-results}

### Un compte manque de temps {#an-account-runs-out-of-time}

```text
Resource discovery failed for account 123456789012: timed out after 60 seconds (--account-processing-timeout); the 1302 resource(s) found before the limit are in the report, other resources of this account may be missing (45 service/region listing(s) did not finish)
```

Le compte compte comme échoué, mais les ressources trouvées avant la limite sont dans le rapport, et les « Run notes » nomment le compte. Les autres comptes sont conservés. Si aucun compte ne se termine, InvenTag écrit quand même le rapport, consigne `No account finished within its time limit (--account-processing-timeout)` et se termine avec le code 1. (Texte des messages issu d’une exécution hors ligne avec une limite de 60 secondes.)

**Correction :** augmentez `--account-processing-timeout` (1800 par défaut), analysez moins de régions ou de services, ou analysez moins de comptes à la fois. Exécutez la même commande avec `--resume` pour n’analyser que les comptes qui ne se sont pas terminés.

### Les résultats enregistrés ne sont pas réutilisés {#saved-results-are-not-reused}

| Message | Signification |
|---|---|
| `1 account(s) have saved results from an earlier run of this command that did not finish. They are scanned again; add --resume to reuse them.` | Les résultats enregistrés existent, mais vous n’avez pas passé `--resume`. |
| `123456789012: reusing results scanned 2026-11-14 06:13 UTC (--resume)` | Le résultat enregistré est réutilisé. Les notes du rapport indiquent le compte et l’heure de l’analyse. |
| `inventag: error: --resume: needs state management ...` | La gestion de l’état est désactivée. `--resume` avec `--disable-state-management` s’arrête avec le code de sortie 2. |

InvenTag ne réutilise un résultat enregistré que si la commande a les mêmes comptes, régions, services et filtres, et si le résultat a au plus `--resume-max-age-hours` (24 par défaut, 168 au maximum). Sinon, il analyse de nouveau le compte.

## Modèles et fichiers de configuration {#templates-and-configuration-files}

### Modèle non valide {#invalid-template}

```text title="Sortie"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
1
```

**Correction :** corrigez le champ sur la ligne indiquée. Exécutez
`inventag templates validate <file>` pour vérifier sans lancer d’analyse.

### Nom de modèle inconnu {#unknown-template-name}

```text title="Sortie"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
1
```

**Correction :** vérifiez l’orthographe avec `inventag templates list`. Les modèles de projet
doivent se trouver dans `.inventag/templates/`, dans le dossier d’où vous lancez la commande.

### Fichier de comptes non valide {#invalid-accounts-file}

```text title="Sortie"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
1
```

**Correction :** mettez les ID de compte entre guillemets (`account_id: "123456789012"`), et donnez à
chaque compte `profile_name`, `role_arn` ou des clés d’accès.

Le fichier lui-même peut aussi être incorrect. Chacun de ces cas s’arrête avec le code de sortie 1 :

| Le message contient | Cause |
|---|---|
| `the file is empty` | Le fichier n’a aucun contenu. |
| `duplicate key 'accounts'` | Une clé est écrite deux fois. Le message donne la ligne, par exemple `accounts file accounts.yaml:3: duplicate key 'accounts'`. |
| `the top level must be a mapping of key: value pairs, but the file holds a list` | Le fichier commence par une liste. Placez la liste sous `accounts:`. |
| `unsupported file type '.txt'. Use .json, .yaml or .yml` | Le nom du fichier a une autre extension. |
| `the file is ... bytes; the maximum is 1048576 bytes` | Le fichier dépasse 1 Mio. |
| `Accounts file not found` | Le chemin est incorrect. |

InvenTag avertit lorsqu’un fichier contenant `secret_access_key` ou `session_token` peut être lu par d’autres utilisateurs : `<file> contains secret access keys and other users can read it (mode 0644). Run: chmod 600 <file>.`

### Autres messages de modèle {#other-template-messages}

| Le message contient | Correction |
|---|---|
| `did you mean '...'?` | Corrigez l’orthographe sur la ligne indiquée. |
| `Put account IDs in quotes` | Écrivez `account_id: "012345678901"`. |
| `must stay inside the template's folder` | Déplacez le fichier référencé à côté du modèle, ou dans un sous-dossier. |
| `templates must not contain credentials` | Supprimez les clés d’accès ; utilisez `profile_name` ou `role_arn`. |
| `--template given two report templates` | Donnez au plus un modèle de chaque type. |

## Options qui arrêtent l’exécution {#flags-that-stop-the-run}

Certaines options arrêtent l’exécution avec le code de sortie 2 et un message `inventag: error: ...` avant toute analyse :

- `--compliance-standard` indique qu’elle n’est pas encore implémentée.
- `--disable-production-safety` indique que la protection en lecture seule ne peut pas être désactivée.
- Des options qui ne peuvent pas fonctionner ensemble :

```text
inventag: error: --accounts-file and --accounts-prompt: give one of them, not both.
inventag: error: --cross-account-role: a full role ARN names one account and cannot be combined with --accounts-file or --accounts-prompt. Give a role name to use in every account, or put role_arn in the accounts file.
inventag: error: --s3-kms-key-id: needs --s3-encryption aws:kms.
inventag: error: --resume: needs state management (saved results live in the state folder); remove --disable-state-management.
```

Une valeur hors limites arrête l’exécution avec le code de sortie 1 et nomme l’option : `--max-concurrent-accounts must be a positive integer`, `--account-processing-timeout must be at least 60 seconds`, `--resume-max-age-hours must be above 0 and at most 168`. Une valeur qui n’est pas un nombre pour `--state-retention-days` ou `--state-max-snapshots` arrête l’exécution avec le code de sortie 2 : `expected a whole number or 'none'`.

Voir [État des fonctionnalités](../getting-started/status.md).

## Code de sortie 3 {#exit-code-3}

Ce n’est pas une erreur d’InvenTag. Une politique d’étiquetage a trouvé des violations et le modèle
de configuration contient `fail_on_tag_violations: true`. Ouvrez la feuille Tag Compliance ou
le fichier JSON pour voir quelles ressources sont concernées.

## Codes de sortie 4, 5 et 6 {#exit-codes-4-5-and-6}

Ils n’existent que si vous les demandez.

- **4 :** une règle de groupe de sécurité ouverte à internet atteint ou dépasse `--risk-threshold`. Le journal liste les règles. Voir [Analyse du réseau et de la sécurité](./network-and-security-analysis.md#fail-a-pipeline-on-risky-rules).
- **5 :** `--fail-on-account-error` est activé et un compte n’a pas pu être analysé ou a dépassé son délai. Le journal indique `N account(s) failed and --fail-on-account-error is set (exit code 5)`.
- **6 :** `--fail-if-empty` est activé et il n’y a rien à rapporter. Le journal indique `No resources in the report and --fail-if-empty is set (exit code 6)`.

Les rapports sont écrits d’abord. Si plusieurs cas s’appliquent, le 5 passe en premier, puis le 6, puis le 3 et le 4. Voir [Exécuter InvenTag en CI/CD](./run-in-ci.md#exit-codes).

## Les rapports semblent incorrects {#reports-look-wrong}

| Ce que vous voyez | Cause et correction |
|---|---|
| Des feuilles très larges avec des colonnes `raw_data.*` | C’est la mise en page par défaut. Utilisez `--template standard-bom`. |
| Les colonnes de correspondance d’étiquettes sont absentes | Les correspondances d’étiquettes n’ajoutent des colonnes qu’au classeur par défaut. Avec `--template`, utilisez `tag_columns`. Voir [Fichiers de configuration](../reference/configuration-files.md#tag-mappings). |
| Une description de service personnalisée est ignorée | Votre entrée remplace la description intégrée ; les services sans entrée dans votre fichier gardent le texte intégré. Voir [Fichiers de configuration](../reference/configuration-files.md#service-descriptions). |
| Aucune feuille réseau ni sécurité | Ajoutez `--enable-network-analysis` ou `--enable-security-analysis`, et vérifiez que l’analyse a trouvé des VPC ou des groupes de sécurité. Ces options n’ajoutent rien avec `--template`. Voir [Analyse du réseau et de la sécurité](./network-and-security-analysis.md). |
| Des ressources IAM, S3, CloudFront ou Route 53 sont absentes | `--account-services` ou `--account-tags` les a retirées, ou l’identité n’a pas l’autorisation (cherchez un avertissement par service dans le journal). La liste des régions n’a pas d’importance : les services globaux sont toujours lus depuis la région principale (`us-east-1`, ou `cn-north-1` en Chine et `us-gov-west-1` dans GovCloud). |
| Une ressource n’affiche aucune étiquette, ou apparaît deux fois | Exécutez avec `--debug` et comparez la colonne ARN avec l’ARN dans la console AWS. Signalez toute différence dans un problème (issue), avec le service et le type de ressource. |
| Aucun fichier de rapport, et le code de sortie est 0 | L’analyse n’a rien trouvé, ou `--account-services` ou `--account-tags` a tout retiré. Cherchez `No resources to report` dans le journal. Avec `--template`, InvenTag écrit un rapport qui ne liste aucune ressource. |
| Un compte est absent du rapport | Ses identifiants ou son rôle ont échoué, ou il a manqué de temps. Les « Run notes » de la feuille `Summary` le nomment. Voir [Un rôle ne peut pas être assumé](#a-role-cannot-be-assumed) et [Un compte manque de temps](#an-account-runs-out-of-time). |
| Le rapport des changements est absent | La première exécution n’en écrit aucun. Il faut aussi que la gestion de l’état et la détection des différences soient activées. Voir [Suivre les changements entre les exécutions](./track-changes.md). |
| `Skipped unreadable snapshot 20261113_222847: Snapshot ... is corrupt or truncated (...). The file was not changed or deleted` | Le dernier instantané est endommagé, donc InvenTag compare avec le précédent. Le fichier reste dans `state/`. Supprimez-le si vous n’en avez pas besoin. |
| `Account 222222222222 left out of the comparison: the previous run could not scan it` | L’une des deux exécutions n’a pas pu analyser ce compte. Le rapport des changements le nomme sous `accounts_not_compared`. |
| `Excel sheet name 'x' is not allowed or is already used; the sheet is called 'y'` | Excel n’autorise pas certains caractères dans les noms de feuille (ils deviennent `-`), et les noms doivent être uniques et de 31 caractères au plus. Le rapport reste complet. |
| Un autre utilisateur ne peut pas ouvrir `bom_output/` | Les fichiers de sortie sont privés pour l’utilisateur qui a exécuté InvenTag. Partagez-les volontairement. |

Non vérifié sur Microsoft Excel : les règles des noms de feuille.

## Du bruit que vous pouvez ignorer {#noise-you-can-ignore}

Certains messages ressemblent à des erreurs mais ne changent rien à votre rapport.

| Message | Pourquoi vous pouvez l’ignorer |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'`` (avec `--service-descriptions`) | Le modèle de description VPC attend un champ que la ressource n’a pas. Le rapport n’est pas affecté. |
| `No account specification method provided. Using default AWS credentials.` | Vous n’avez désigné aucun compte ; InvenTag a donc utilisé vos identifiants actuels. C’est le cas normal. |
| `Cross-account role not usable for account ... trying default credentials` | InvenTag n’a pas pu assumer le rôle dans ce compte et a essayé vos propres identifiants. Il ne les utilise que s’ils appartiennent à ce compte ; sinon le compte est ignoré. Le message est consigné une fois par compte, et seulement avec `--verbose`. |

## Problèmes d’installation {#install-problems}

Voir [Installer InvenTag](../getting-started/installation.md#fix-install-problems).

## Toujours bloqué ? {#still-stuck}

Ouvrez un [problème (issue)](https://github.com/habhabhabs/inventag-aws/issues) avec la
commande exécutée, la version (`inventag --version`) et le message. Retirez
les ID et les noms de compte que vous ne voulez pas partager. Ne collez jamais d’identifiants.
