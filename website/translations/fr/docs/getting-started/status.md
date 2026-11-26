---
title: État des fonctionnalités et limites connues
sidebar_label: État des fonctionnalités
description: Quelles fonctionnalités d’InvenTag fonctionnent, lesquelles sont partielles, quelles options s’arrêtent sur erreur, et les limites, coûts et risques connus.
sidebar_position: 5
---

# État des fonctionnalités et limites connues

**À qui s’adresse cette page :** à toute personne sur le point de s’appuyer sur InvenTag pour un vrai travail.

**Ce que vous saurez après lecture :** quelles fonctionnalités marchent, où elles
s’arrêtent, quelles options s’arrêtent sur une erreur et que faire face à chaque limite.

Cette page est volontairement directe. Elle décrit la version actuelle ; le
[journal des modifications](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md) liste ce qui a changé dans chaque version. Chaque point ci-dessous est démontré par un test hors ligne ou une exécution sur un AWS simulé (moto). **Aucun test n’a été exécuté sur un compte AWS réel.** Lorsqu’un point dépend du comportement du vrai AWS, la page le dit. Si vous corrigez ou modifiez l’un d’eux, mettez à jour cette page dans la même demande de fusion (pull request).

## Ce qui est testé {#what-is-tested}

La page [Tests](../security/tests.md) liste les tests hors ligne sur un AWS simulé (moto) et ce que chacun vérifie. Une affirmation de cette documentation qu’aucun test ne démontre porte une note qui commence par « Non vérifié sur ».

## Options avec limites {#flags-with-a-limit}

| Option | Ce qui se passe réellement |
|---|---|
| `--enable-cost-analysis` | Ajoute une feuille Cost Analysis et les quatre colonnes `forgotten_analysis.*`, avec des estimations de l’API AWS Pricing qui ne sont pas votre facture, et effectue des appels supplémentaires à Cost Explorer, Pricing et CloudWatch (voir [Coûts](#costs)). |
| `--compliance-standard` | S’arrête avec le code de sortie 2, car une norme telle que SOC 2 ne peut pas être vérifiée à partir d’un inventaire ; utilisez plutôt un modèle de politique d’étiquetage. |
| `--create-google-docs`, `--create-google-sheets` | Ne fonctionnent qu’avec des clients Google simulés. Voir [Google Sheets et Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--finops-cost-allocation` | Testée avec des réponses Cost Explorer ayant la forme de celles d’AWS, pas sur un vrai AWS. Les clés de balise ne montrent des dépenses qu’après leur activation comme balises de répartition des coûts dans le compte de facturation, et un compte membre peut voir moins que le compte payeur (non vérifié). Voir [Répartition des coûts](../guides/finops-checks.md#cost-allocation-from-cost-explorer). |
| `--finops-checks` | `FIN-004` liste une instance arrêtée quelle que soit la durée de l’arrêt, car la liste des instances n’a pas d’heure d’arrêt fiable. `FIN-005` ne lit pas l’état de santé des cibles : un équilibreur de charge dont toutes les cibles sont en mauvaise santé donne un pass. Avec `--template`, aucune feuille n’est écrite : les contrôles s’exécutent sur l’instantané d’état et leurs constats sont écrits dans `policy_findings_<timestamp>.json`. Sans `--template`, le résultat n’est que dans la feuille Excel ; il n’y a pas de fichier JSON. Voir [Contrôles FinOps](../guides/finops-checks.md#what-the-checks-cannot-see). |
| `--policy`, `--policy-waivers`, `--policy-fail-on`, `--policy-format`, `inventag policy` | Testé hors ligne, avec des comptes simulés et des instantanés écrits à la main, pas sur un vrai AWS. Une politique lit les champs qu’une analyse met sur une ligne ; elle ne peut donc pas juger un champ que l’analyse ne montre pas. Une ligne dont les données n’ont pas été lues est `not_evaluated`, jamais une réussite. Une analyse se termine au plus avec le code 7 pour une politique ; seul `inventag policy check` se termine avec le code 8. Voir les [sous-commandes de `policy`](../reference/cli.md#policy-subcommands) et les [constats des politiques](../reference/outputs.md#policy-findings). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Conservées pour que les anciennes commandes fonctionnent encore. La protection en lecture seule est toujours active. |
| `--disable-production-safety` | S’arrête avec le code de sortie 2, car la protection en lecture seule ne peut pas être désactivée. |

```bash title="Terminal"
inventag --create-google-docs
```

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)
```

```bash title="Terminal"
inventag --risk-threshold HIGH
```

```text title="Sortie"
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)
```

```bash title="Terminal"
inventag --compliance-standard soc2
```

```text title="Sortie"
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour. InvenTag does not assess compliance. To check your tags against a built-in baseline, run: inventag --template security-baseline --create-excel
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="Sortie"
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked. Remove this option; nothing else is needed. To see which calls are allowed, run: inventag --validate-operations ec2:DescribeInstances
(exit code 2)
```

## Ce qu’InvenTag trouve, et ce qu’il ne trouve pas {#what-inventag-finds-and-what-it-does-not}

- **Services avec leur propre code de découverte (46) :** VPC (VPC, sous-réseaux,
  groupes de sécurité, passerelles Internet et NAT, tables de routage, ACL réseau,
  adresses IP Elastic), EC2 (instances, volumes, instantanés, paires de clés), S3,
  RDS, Lambda, ELB, ELBv2, IAM, CloudFront, Route 53, KMS, CloudWatch, ECS
  (clusters, et les services de chaque cluster), EKS, SNS, SQS, DynamoDB,
  API Gateway, Glue, WorkMail, CloudFormation, ACM, CloudTrail, EventBridge,
  ElastiCache, Redshift, Redshift Serverless, OpenSearch, EFS, ECR, Step
  Functions, Kinesis, Firehose, Secrets Manager (noms seulement), paramètres
  Systems Manager (noms seulement), groupes Auto Scaling, coffres Backup, groupes
  d’utilisateurs Cognito, CodeBuild, CodePipeline, groupes de travail Athena, EMR,
  MSK, AppSync, Elastic Beanstalk et ACL web WAF.
- **Tout le reste** n’apparaît que lorsque l’API Resource Groups Tagging le
  renvoie, donc les ressources sans étiquette de tout autre service sont
  absentes. Avec `--fallback-display auto` (la valeur par défaut), ces
  ressources ne sont affichées que pour les services qui n’ont aucun résultat
  de leur propre code de découverte ; `--fallback-display always` les affiche
  toutes.
- **Non collecté :** valeurs secrètes, valeurs de paramètres, contenu d’objets
  ou toute autre donnée, car la protection en lecture seule bloque les appels
  qui les renvoient.
- **Les valeurs secrètes des réponses autorisées sont masquées.** Certains appels
  de lecture renvoient un secret à côté d’un paramètre. Les valeurs des champs qui
  contiennent souvent des secrets sont remplacées par `***REDACTED***` dans les
  rapports, la sortie JSON, les instantanés d’état, les points de reprise et les
  journaux : variables d’environnement Lambda et App Runner, valeurs
  d’environnement ECS et CodeBuild, données utilisateur EC2, valeurs des
  paramètres CloudFormation, valeurs de sortie des piles et corps de modèle des
  ensembles de piles, arguments des tâches, déclencheurs et exécutions de tâches
  Glue et propriétés de connexion, arguments des tâches EMR on EKS, codes
  d’activation WorkSpaces Thin Client, portefeuilles de certificats DMS, chaînes
  de connexion, URL signées, de téléchargement et de téléversement, jetons
  Splunk HEC, Grafana et de jonction, et tout champ nommé comme password,
  secret, token, access ou refresh token, private key ou credentials, y compris
  dans du texte JSON. Les noms restent.
- **Les secrets des autres champs ne sont pas détectés :** un secret dans une
  description, une étiquette, un autre champ de texte libre ou un champ que AWS
  ajoutera plus tard est copié tel quel dans les rapports, car le masquage se
  fait d’après le nom du champ.
- **Les étiquettes sont affichées telles quelles**, même quand une clé
  d’étiquette ressemble à un secret, comme `password`.
- **Les rapports et instantanés écrits par des versions antérieures à v1.2.0
  peuvent contenir des valeurs secrètes**, donc supprimez ou restreignez les
  anciens dossiers `bom_output/` et les copies partagées.
- **Les services globaux** (IAM, la liste des compartiments S3, CloudFront,
  Route 53, les ACL web WAF pour CloudFront et les certificats ACM utilisés par
  CloudFront) sont lus une fois par compte depuis `us-east-1` (`cn-north-1` en
  Chine, `us-gov-west-1` dans GovCloud), quelles que soient les régions choisies.
  Leur colonne de région indique `global` ; un compartiment S3 garde sa propre
  région. Voir [Lancer une analyse](../guides/run-a-scan.md).
- **Régions.** Sans `--account-regions`, InvenTag demande à EC2 les régions
  activées dans le compte. Si `ec2:DescribeRegions` échoue, il interroge
  `account:ListRegions` ; si cela échoue aussi, il essaie toutes les régions de la
  partition et ignore celles qui échouent au contrôle d’accès. Une région qui
  échoue à son contrôle d’accès est ignorée avec un avertissement, et l’exécution
  réussit quand même.

## Quand une exécution tourne mal {#when-a-run-goes-wrong}

- **Un compte échoue, les autres fonctionnent :** l’exécution se termine avec le
  code 0, ou avec le code 5 si vous passez `--fail-on-account-error`.
- **Tous les comptes échouent :** l’exécution se termine avec le code 1, y compris
  avec `--fail-on-account-error`, et n’écrit aucun rapport, sauf si les comptes ont
  dépassé leur délai : le rapport montre alors ce qui a été trouvé.
- **Un compte dépasse son temps :** il compte comme en échec, et les ressources
  trouvées avant la limite restent dans le rapport. Un appel encore en attente
  quand le compte est abandonné n’est pas relancé et ne garde pas le processus
  actif : l’exécution se termine juste après l’écriture du rapport. Non vérifié
  sur un vrai AWS : un vrai point de terminaison bloqué (le test bloque un appel
  dans moto).
- **Aucune ressource trouvée, ou les filtres les ont toutes retirées :**
  InvenTag n’écrit aucun rapport sans `--template` et un rapport vide avec
  `--template`, et se termine avec le code 0 sauf si vous passez
  `--fail-if-empty` (code 6).
- **Une politique d’étiquetage sans aucune ressource dans son périmètre**
  signale `0 of 0 resources compliant (100.0%)`, alors que rien n’a été vérifié.
- **Un service pour lequel vous n’avez pas de permission** est ignoré avec un
  avertissement, et ses ressources n’apparaissent que si l’API Resource Groups
  Tagging les renvoie.
- **Un listage qui échoue pour une autre raison** (limité après les nouvelles
  tentatives, ou une erreur) est un avertissement et un compte dans l’instantané
  (`metadata.tags.coverage_summary`).
- **Tous les appels d’un compte refusés :** le compte ne compte pas comme en
  échec, et l’exécution se termine avec le code 0. Avec `--fail-on-account-error`,
  un compte dont tous les listages ont été refusés compte quand même comme
  analysé, et l’exécution se termine avec le code 0. Pour qu’un job de CI échoue
  quand rien n’a pu être lu, ajoutez `--fail-if-empty`.
- **Une exécution qui n’a pas eu le droit d’utiliser une action IAM** affiche une
  ligne `Permissions:` par compte dans les notes d’exécution, une pour l’identité qui envoie les rapports quand l’envoi a été refusé, et écrit la liste
  `permissions_denied` dans le fichier de `--audit-output` (voir
  [Exécuter avec ReadOnlyAccess seul](../guides/read-only-access.md#run-with-only-readonlyaccess)).
  La ligne ne nomme pas `ec2:DescribeRegions` ni `account:ListRegions`, et un
  envoi avec une clé KMS qui échoue est nommé seulement `s3:PutObject`.

  Non vérifié sur un vrai AWS : quelle action S3 nomme quand un envoi avec une
  clé KMS est refusé.
- **Le premier rapport de changements après une mise à jour depuis v1.1.4**
  liste les ressources des services nouvellement couverts comme ajoutées, alors
  qu’elles existaient déjà.
- **Une session qui expire pendant l’analyse** laisse un rapport qui ne contient
  que ce qui a été lu avant l’expiration, et l’exécution se termine avec le
  code 0, y compris avec `--fail-on-account-error`.

  Non vérifié sur un vrai AWS : le code d’erreur que renvoie AWS quand une session expire.

- **Une session déjà expirée au début de l’analyse** ne donne aucun fichier de
  rapport et le code 0.
- **Accès refusé ou limité à Cost Explorer :** l’exécution continue sans données de
  facturation et affiche un avertissement qui nomme la cause. Le texte de l’erreur AWS
  ne s’affiche qu’avec `--debug` ou `-vv`.
- **Avec `--account-processing-timeout` inférieur à 1200 secondes,** chaque appel à
  Cost Explorer attend au plus un quarantième de la limite, et au moins 5 secondes,
  pour se connecter et pour lire, avec deux tentatives. S’il ne répond pas à temps, le compte est
  quand même analysé et une note d’exécution indique que ses données de facturation
  manquent. Non vérifié sur un vrai AWS : un Cost Explorer lent se termine par un
  délai dépassé dans cette limite.
- **Un appel bloqué par la protection en lecture seule** dans un listage ignore
  ce listage avec une ligne d’erreur, et l’exécution se termine quand même avec
  le code 0.
- **Un téléversement S3 en échec** fait se terminer toute l’exécution avec le
  code 1, après l’écriture locale des rapports.
- **Un format de rapport en échec** fait se terminer l’exécution avec le code 1
  et ne téléverse rien vers S3, pas même les formats qui ont été écrits.
- **Un instantané qui ne peut pas être enregistré** (ou une liste d’instantanés ou un
  rapport de changements qui échoue) est nommé dans une note après le résumé de
  l’exécution, avec le dossier à vérifier, et l’exécution se termine quand même avec
  le code 0.
- **La sortie Google avec `--template`** est ignorée, et l’exécution se termine
  avec le code 0.
- **Certaines valeurs non valides s’arrêtent avec le code de sortie 1, pas 2,**
  par exemple `--max-concurrent-accounts 0` ou `--account-processing-timeout 0`.
  Une valeur de `--concurrency` hors de 1 à 256 s’arrête avec le code de sortie 2.
- **Les valeurs du bloc `settings` d’un fichier de comptes remplacent les
  options de ligne de commande correspondantes**, par exemple
  `max_concurrent_accounts`.
- **Un résultat vide avec `--s3-bucket`** fait se terminer l’exécution avec le
  code 1 et dit `Nothing to upload to s3://<bucket>/<prefix>/: the run wrote no
  report file because there are no resources to report.`, y compris avec
  `--fail-if-empty`.
- **Un nom de région mal saisi dans `--account-regions`** est nommé une seule fois,
  avec la commande qui liste les régions valides, et l’exécution se termine avec le
  code 0. Quand d’autres régions fonctionnent, le rapport est écrit sans elle et une
  note d’exécution le dit.
- **Une deuxième entrée avec le même ID de compte** dans un fichier de comptes
  est ignorée avec un avertissement, donc ses régions ne sont pas analysées.
- **Deux exécutions qui utilisent en même temps le même dossier de sortie** ne
  sont pas empêchées.
- **`--validate-config-only` avec un fichier `--bom-config` dont une valeur est erronée** affiche un avertissement et se termine avec le code 0, alors que la vraie exécution s’arrête avec le code de sortie 1.
- **Un fichier de descriptions de services sans la clé de premier niveau `service_descriptions`** passe `--validate-config-only` avec un avertissement et le code 0, et l’exécution l’ignore avec une erreur dans le journal et utilise les descriptions intégrées.
- **`inventag --validate-operations` affiche `apigateway:GetApiKeys` et `ec2:DescribeInstanceAttribute` comme ALLOWED**, chacun avec la règle qu’applique la protection (`blocked when includeValues=true`, `blocked when Attribute=userdata`), et se termine avec le code 0, car la protection ne les bloque que lorsqu’ils sont appelés avec ce paramètre.

## Coûts {#costs}

Par défaut, la découverte appelle l’API `GetCostAndUsage` de Cost Explorer une fois
par compte. La requête couvre la période allant de 30 jours avant le premier
jour du mois en cours jusqu’à aujourd’hui ; la validation de facturation et la
colonne de dépenses la lisent toutes deux, donc un service facturé seulement
dans cette période compte comme facturé. AWS facture chaque requête
Cost Explorer : consultez les
[tarifs actuels de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

Requêtes Cost Explorer d’une exécution : au plus une par compte pour la validation de facturation (active par défaut), et avec `--enable-cost-analysis` au plus 2 de plus par compte pour la tendance des coûts, chacune lue avec les identifiants propres à ce compte. Une exécution sur un seul compte avec les deux en fait au plus 3 ; avec `--no-billing-validation`, elle en fait au plus 2. Une requête limitée (throttled) est réessayée, jusqu’à 10 tentatives en tout, et chaque nouvel essai est une requête de plus. AWS facture chaque requête. Avant la découverte, toute exécution qui appelle Cost Explorer indique ce nombre, sans les nouveaux essais, sous forme d’avertissement. Par exemple `Cost Explorer: up to 3 request(s) in this run (billing validation: 1; cost trend: 2). AWS charges for each.`

- `--no-billing-validation` arrête ces appels, et le rapport n’a alors aucune
  donnée de facturation à comparer.
- `--enable-cost-analysis` appelle aussi Cost Explorer, même avec `--no-billing-validation`. Il fait aussi des appels à Pricing et CloudWatch, dont le nombre dépend de vos ressources. Chaque recherche de prix distincte n’est faite qu’une fois puis réutilisée ; le nombre d’appels à Pricing augmente donc avec le nombre de types et de tailles de ressources différents, pas avec le nombre de ressources.
- La tendance des coûts lit la facture de chaque compte avec les identifiants de ce compte, et compare les deux mois complets avant l’exécution. La première requête suffit pour un compte dont la réponse tient sur une page (non vérifié sur un vrai AWS) ; une seconde requête lit une page de plus de la réponse. Si la réponse a plus de pages que cela, un avertissement par compte dit que les services des pages suivantes n’ont pas de tendance. Un compte dont la requête a été refusée ou a échoué n’a pas de tendance, et l’exécution le dit dans un avertissement.
- Un service est trouvé dans la facture par son nom de facturation : S3, SQS et SNS ont donc une tendance, et le chiffre d’EC2 n’inclut pas ECR. `EC2 - Other` (volumes, passerelles NAT, transfert de données) est un nom de facturation distinct et n’est pas dans le chiffre d’EC2. Le chiffre d’un service est un total du compte et du service, montré une fois dans la feuille Cost Analysis ; ce n’est pas le coût d’une ressource et il n’est pas réparti entre les ressources. Voir la [feuille Cost Analysis](../reference/outputs.md#cost-analysis-sheet).
- Avant la v1.5.0, la tendance lisait une seule facture avec les identifiants du premier compte, pour les ressources de tous les comptes, et le résultat avait une entrée par ressource (`cost_analysis["cost_trends"]` ; aucune feuille ne la montrait). Les chiffres de ces exécutions ne sont pas comparables avec ceux-ci.

Non vérifié sur un vrai AWS : les estimations de coûts de `--enable-cost-analysis`.

Non vérifié sur un vrai AWS : le nombre de requêtes qu’AWS facture, et si AWS facture un nouvel essai.

InvenTag relance un appel limité jusqu’à 10 fois (mode de nouvelle tentative
standard) ; `AWS_RETRY_MODE` et `AWS_MAX_ATTEMPTS` modifient ce réglage.

## Performances et limites {#performance-and-limits}

- InvenTag n’a pas de chiffres de performance pour des comptes réels, et une
  analyse fait un ensemble d’appels par service et par région.
- Sur moto (dans le processus, donc sans temps réseau),
  `scripts/benchmark_scan.py --scale 60` a analysé 10 948 ressources dans une
  région avec 2 053 appels d’API : 1 200 appels `s3:GetBucketLocation` (un par
  compartiment), 600 appels `lambda:GetFunctionConfiguration` (un par fonction),
  150 appels à l’API Resource Groups Tagging et 103 autres appels. Pour des
  comptes réels, le chiffre utile est le nombre d’appels.
- Par défaut, quatre comptes sont analysés en même temps
  (`--max-concurrent-accounts`). Chaque compte dispose de 1800 secondes à partir
  du début de son analyse (`--account-processing-timeout`).
- Une exécution a au plus 64 requêtes AWS en cours (`--concurrency`), au plus 16
  pour un compte et au plus 4 pour un service dans une région d’un compte. Après
  une réponse de limitation, InvenTag baisse la limite de ce service et de cette
  région. Voir [Concurrence](../guides/run-a-scan.md#concurrency).

  Non vérifié sur un vrai AWS : toute accélération due aux requêtes en parallèle,
  et le comportement de la limite de requêtes et de la pause après une réponse de
  limitation avec les limites de débit réelles d’AWS.
- L’ordre des lignes du journal et leurs horodatages peuvent changer d’une
  exécution à l’autre. Les fichiers ne dépendent pas du minutage des threads.
- Quand certains comptes échouent, les résultats des comptes terminés sont
  enregistrés. Relancez la même commande avec `--resume` dans les 24 heures
  (`--resume-max-age-hours`) pour n’analyser que les autres.
- Les noms de feuille Excel sont coupés à 31 caractères, les caractères que
  Excel n’autorise pas deviennent `-`, un nom répété reçoit ` (2)`, et le
  journal nomme chaque feuille modifiée.
- Les tableaux Word affichent jusqu’à 50 ressources par service par défaut
  (`max_rows`).
- Quand une exécution enregistre un instantané, InvenTag supprime les instantanés
  de `bom_output/state/` de plus de 30 jours ou au-delà des 100 plus récents.
  L’instantané qui vient d’être écrit et celui avec lequel il est comparé ne sont
  jamais supprimés. Modifiez ces limites avec `--state-retention-days` et
  `--state-max-snapshots`, ou gardez tout avec `none`.
- L’analyse réseau ne compte pas un système de fichiers EFS comme ressource associée d’un VPC ou d’un sous-réseau : ses cibles de montage exigent `elasticfilesystem:DescribeMountTargets`, que la politique en lecture seule n’accorde pas.
- L’enrichissement des attributs de service (`enable_service_enrichment` dans
  les réglages de la BOM) ne s’exécute pas ; les rapports contiennent les champs
  que renvoie la découverte.
- Dans un rapport de modèle, la colonne Name est vide quand AWS ne renvoie ni
  champ `Name` ni étiquette `Name` pour la ressource ; la colonne ID l’identifie.
  Pour les fonctions Lambda, les rôles IAM et les alias KMS, un rapport de modèle
  affiche l’ID comme nom.

- Sur un Mac Intel, `pip install inventag-aws` compile la bibliothèque cryptography, car cryptography ne publie pas de version précompilée pour les Mac Intel à partir de la version 50. Cela demande une chaîne d’outils Rust.

  Non vérifié sur un Mac Intel : `pip install inventag-aws`.

## Notes de sécurité {#security-notes}

- **Utilisez quand même une identité IAM en lecture seule.** La protection bloque
  les appels d’écriture, et votre politique IAM (Identity and Access Management)
  est un second filet de sécurité indépendant. Voir
  [Configurer un accès en lecture seule](../guides/read-only-access.md).
- **Les journaux de débogage sont caviardés** par défaut : jetons de session,
  clés, signatures et les valeurs secrètes listées plus haut sont masqués. Traitez
  quand même les journaux de débogage comme sensibles. Avec `--debug` ou `-vv`, un secret qu’AWS renvoie dans un dictionnaire sous le nom d’un champ masqué, ou sous forme de liste XML (éléments `<member>`), peut apparaître dans le fichier journal.
- Quelques réponses d’AWS contiennent une URL dans un champ nommé seulement `Url` ; InvenTag n’appelle pas ces opérations et ne masque pas ce nom de champ.
- **La protection en lecture seule connaît les opérations par leur nom.** Une
  opération qu’ajoute un SDK AWS plus récent est autorisée quand son nom commence
  comme une lecture, jusqu’à ce qu’une version d’InvenTag la nomme. Voir
  [Sécurité](../security/index.md).
- **Deux fonctions de la bibliothèque peuvent écrire dans AWS** lorsqu’elles sont
  appelées depuis votre propre code Python (la CLI ne les appelle pas) :
  `CredentialManager.setup_cross_account_roles()` ne s’exécute qu’avec
  `allow_iam_writes=True`, et l’assistant de cycle de vie S3 qu’avec
  `allow_bucket_writes=True`. La protection en lecture seule bloque les deux dans
  une exécution de la CLI.
- **Utiliser `CloudBOMGenerator` depuis votre propre code Python** n’installe pas
  la protection en lecture seule. Seule la commande `inventag` le fait.
- **Un modèle de configuration peut fixer le dossier de sortie ainsi que les
  comptes et rôles à analyser.** N’utilisez que des modèles de confiance.
- **Les sessions de rôle assumé ne sont pas renouvelées**, donc l’analyse d’un
  compte qui dépasse la durée de la session rencontre un jeton expiré.

  Non vérifié sur un vrai AWS : les sessions de rôle assumé durent une heure.
- **La MFA ne fonctionne que par les profils AWS** (`mfa_serial`), pas pour les
  entrées `role_arn` d’un fichier de comptes.

  Non vérifié sur un vrai dispositif MFA : la MFA par un profil AWS avec `mfa_serial`.

## Tests et nomenclature logicielle {#tests-and-the-software-bill-of-materials}

La suite de tests et l’inventaire des dépendances ont leurs propres pages :
[Tests](../security/tests.md) et
[Nomenclature logicielle](../security/sbom.md).
