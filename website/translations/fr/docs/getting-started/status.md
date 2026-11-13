---
title: État des fonctionnalités et limites connues
description: Quelles fonctionnalités d’InvenTag fonctionnent, lesquelles sont partielles, quelles options s’arrêtent sur erreur, et les limites, coûts et risques connus.
sidebar_position: 5
---

# État des fonctionnalités et limites connues

**À qui s’adresse cette page :** à toute personne sur le point de s’appuyer sur InvenTag pour un vrai travail.

**Ce que vous saurez après lecture :** quelles fonctionnalités marchent, où elles
s’arrêtent, quelles options s’arrêtent sur une erreur et que faire face à chaque limite.

Cette page est volontairement directe. Elle décrit la version actuelle ; le
[journal des modifications](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md) liste ce qui a changé dans chaque version. Nous avons
vérifié chaque point en exécutant le code hors ligne sur un AWS simulé (moto), ou en
lisant le chemin du code. **Aucun test n’a été exécuté sur un compte AWS réel.** Lorsqu’un
point ci-dessous dépend du comportement du vrai AWS, la page le dit. Si vous corrigez ou
modifiez l’un d’eux, mettez à jour cette page dans la même demande de fusion (pull request).

## Ce qui est testé {#what-is-tested}

Chaque fonctionnalité a un test hors ligne sur un AWS simulé (moto). La liste des tests
et ce que chacun vérifie se trouvent sur la page [Tests](../security/tests.md).

## Options avec limites {#flags-with-a-limit}

| Option | Ce qui se passe réellement |
|---|---|
| `--enable-cost-analysis` | Ajoute une feuille Cost Analysis et les quatre colonnes `forgotten_analysis.*`. Les coûts sont des estimations de l’API AWS Pricing, pas votre facture. Elle effectue des appels supplémentaires à Cost Explorer, Pricing et CloudWatch. Voir [Coûts](#costs). |
| `--compliance-standard` | S’arrête avec le code de sortie 2. Une norme telle que SOC 2 ne peut pas être vérifiée à partir d’un inventaire, et une option qui n’afficherait qu’une étiquette vous induirait en erreur. Utilisez un modèle de politique d’étiquetage. |
| `--create-google-docs`, `--create-google-sheets` | Ne fonctionnent qu’avec des clients Google simulés. Voir [Google Sheets et Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Conservées pour que les anciennes commandes fonctionnent encore. La protection en lecture seule est toujours active. |
| `--disable-production-safety` | S’arrête avec le code de sortie 2. La protection ne peut pas être désactivée. |

```text title="Terminal"
$ inventag --create-google-docs
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
- **Tout le reste** ne peut apparaître que si l’API Resource Groups Tagging le
  renvoie. Cette API liste les ressources qui ont, ou ont eu, des étiquettes ; les
  ressources sans étiquette des autres services manquent donc. Avec
  `--fallback-display auto` (la valeur par défaut), ces ressources ne sont
  affichées que pour les services sans résultat de leur propre code de découverte.
  Utilisez `--fallback-display always` pour les afficher toutes.
- **Non collecté :** valeurs secrètes, valeurs de paramètres, contenu des objets
  ou toute autre donnée. La protection en lecture seule bloque les appels qui les
  renvoient.
- **Les valeurs secrètes des réponses autorisées sont masquées.** Certains appels
  de lecture renvoient un secret à côté d’un paramètre. Les valeurs des champs qui
  contiennent souvent des secrets sont remplacées par `***REDACTED***` dans les
  rapports, la sortie JSON, les instantanés d’état, les points de reprise et les
  journaux : variables d’environnement Lambda et App Runner, valeurs
  d’environnement ECS et CodeBuild, données utilisateur EC2, valeurs des
  paramètres et des sorties CloudFormation, arguments des tâches et déclencheurs
  Glue et propriétés de connexion, et tout champ nommé comme password, secret,
  token, private key ou credentials. Les noms restent.
- **Les secrets dans d’autres champs ne sont pas trouvés.** InvenTag se fie au
  nom du champ : un secret dans une description, une étiquette ou un autre champ
  de texte libre n’est pas masqué.
- **Les rapports et instantanés écrits par les versions antérieures à v1.2.0
  peuvent contenir des valeurs secrètes.** Supprimez ou restreignez les anciens
  dossiers `bom_output/` et les copies partagées.
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
  code 0, ou avec le code 5 si vous passez `--fail-on-account-error`. Le résumé de
  l’exécution et le rapport par défaut nomment chaque compte en échec et la
  raison ; un rapport fait avec `--template` ne le fait pas. Si tous
  les comptes échouent, l’exécution se termine avec le code 1.
- **Un compte dépasse son temps :** il compte comme en échec. Les ressources
  trouvées avant la limite restent dans le rapport, et le rapport par défaut
  indique que le compte est incomplet.
- **Aucune ressource trouvée, ou les filtres les ont toutes retirées :** sans
  `--template`, InvenTag n’écrit aucun rapport, consigne un avertissement et se
  termine avec le code 0. Avec `--template`, il écrit un rapport vide.
  `--fail-if-empty` fait se terminer les deux cas avec le code 6.
- **Un service pour lequel vous n’avez pas de permission :** InvenTag ignore cet
  appel, consigne un avertissement pour le service avec la raison, et continue.
  Les ressources de ce service peuvent quand même apparaître si l’API Resource
  Groups Tagging les renvoie.
- **Un listage qui échoue pour une autre raison** (limité après les nouvelles
  tentatives, ou une erreur) est consigné comme avertissement pour ce service et
  cette région, et compté dans l’instantané d’état (`metadata.tags.coverage_summary`).
- **Tous les appels d’un compte refusés :** le compte ne compte pas comme en
  échec. L’exécution se termine avec le code 0 sans ressource à signaler, et
  l’instantané enregistré fait que l’exécution suivante signale toutes les
  ressources de ce compte comme supprimées.
- **Un service dont le listage a été limité ou a échoué avec une erreur** lors
  d’une exécution apparaît comme supprimé dans le rapport de changements suivant.
- **Une session qui expire pendant l’analyse :** l’exécution se termine avec le
  code 0 et le rapport semble complet.
- **Un jeton IAM Identity Center (SSO) expiré** arrête l’exécution avec une trace
  d’appels Python au lieu d’un message. Relancez `aws sso login`.
- **Les avertissements de la découverte** s’affichent dans la console mais ne
  sont pas écrits dans le fichier de `--log-file`.
- **Accès refusé à Cost Explorer :** l’exécution continue sans données de
  facturation et consigne un avertissement.
- **Un appel bloqué par la protection en lecture seule** est consigné comme une
  erreur qui nomme l’opération. S’il survient dans un listage, ce listage est
  ignoré et l’exécution continue avec le code de sortie 0. La CLI ne fait pas de
  tels appels elle-même.
- **Un téléversement S3 en échec** fait se terminer toute l’exécution avec le
  code 1, après l’écriture locale des rapports.
- **Un format de rapport en échec** fait se terminer l’exécution avec le code 1,
  et rien n’est téléversé vers S3, pas même les formats qui ont été écrits.
- **Un instantané qui ne peut pas être enregistré** est consigné comme une
  erreur, et l’exécution se termine quand même avec le code 0.
- **La sortie Google avec `--template`** est ignorée, et l’exécution se termine
  avec le code 0.
- **Certaines valeurs non valides s’arrêtent avec le code de sortie 1, pas 2,**
  par exemple `--max-concurrent-accounts 0` ou `--account-processing-timeout 0`.
- **Les valeurs du bloc `settings` d’un fichier de comptes remplacent les
  options de ligne de commande correspondantes**, par exemple
  `max_concurrent_accounts`.

## Coûts {#costs}

Par défaut, la découverte appelle l’API `GetCostAndUsage` de Cost Explorer. Dans notre
test hors ligne, elle a fait deux requêtes par compte. AWS facture chaque requête
Cost Explorer. Consultez les
[tarifs actuels de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` arrête ces appels. Le rapport n’a alors aucune donnée de
  facturation à comparer.
- `--enable-cost-analysis` fait davantage d’appels, même avec
  `--no-billing-validation`. Dans notre test hors ligne (un compte, `us-east-1`),
  elle a fait 5 appels à Cost Explorer, 3 à Pricing et 2 à CloudWatch. Les
  estimations donnent un prix à chaque type d’instance (et à chaque autre taille
  ou classe) séparément. Chaque recherche de prix distincte n’est faite qu’une fois
  puis réutilisée ; le nombre d’appels à Pricing augmente donc avec le nombre de
  types et de tailles de ressources différents, pas avec le nombre de ressources.

Les autres appels sont gratuits, mais les grands comptes impliquent de nombreuses requêtes et une possible
limitation de débit (AWS ralentit vos requêtes). InvenTag relance un appel limité jusqu’à 10 fois
(mode de nouvelle tentative standard) ; `AWS_RETRY_MODE` et `AWS_MAX_ATTEMPTS` modifient ce réglage.

## Performances et limites {#performance-and-limits}

- InvenTag n’a pas de chiffres de performance pour des comptes réels. Analyser
  toutes les régions d’un grand compte est lent : un jeu d’appels par service et
  par région.
- Sur moto (dans le processus, donc sans temps réseau),
  `scripts/benchmark_scan.py` a analysé 9 547 ressources dans une région avec
  2 027 appels d’API. Pour des comptes réels, le chiffre utile est le nombre
  d’appels : environ 60 appels fixes par région, plus un appel par compartiment S3
  et par fonction Lambda, plus une page de l’API Tagging par tranche de
  100 ressources étiquetées.
- Par défaut, quatre comptes sont analysés en même temps
  (`--max-concurrent-accounts`). Chaque compte dispose de 1800 secondes à partir
  du début de son analyse (`--account-processing-timeout`).
- Quand certains comptes échouent, les résultats des comptes terminés sont
  enregistrés. Relancez la même commande avec `--resume` dans les 24 heures
  (`--resume-max-age-hours`) pour n’analyser que les autres.
- Les noms de feuille Excel sont limités à 31 caractères : les noms plus longs
  sont coupés, les caractères qu’Excel n’accepte pas deviennent `-`, un nom
  répété reçoit ` (2)`, et le journal nomme chaque feuille modifiée. Les tableaux
  Word affichent jusqu’à 50 ressources par service par défaut (`max_rows`).
- Quand une exécution enregistre un instantané, InvenTag supprime les instantanés
  de `bom_output/state/` de plus de 30 jours ou au-delà des 100 plus récents.
  L’instantané qui vient d’être écrit et celui avec lequel il est comparé ne sont
  jamais supprimés. Modifiez ces limites avec `--state-retention-days` et
  `--state-max-snapshots`, ou gardez tout avec `none`.
- Avec `--enable-network-analysis` ou `--enable-security-analysis`, les appels de
  l’analyse sont faits deux fois dans une même exécution.

## Notes de sécurité {#security-notes}

- **Utilisez quand même une identité IAM en lecture seule.** La protection bloque
  les appels d’écriture, et votre politique IAM (Identity and Access Management)
  est un second filet de sécurité indépendant. Voir
  [Configurer un accès en lecture seule](../guides/read-only-access.md).
- **Les journaux de débogage sont caviardés** par défaut : jetons de session,
  clés, signatures et les valeurs secrètes listées plus haut sont masqués. Traitez
  quand même les journaux de débogage comme sensibles.
- **Deux fonctions de la bibliothèque peuvent écrire dans AWS** lorsqu’elles sont
  appelées depuis votre propre code Python (la CLI ne les appelle pas) :
  `CredentialManager.setup_cross_account_roles()` ne s’exécute qu’avec
  `allow_iam_writes=True`, et l’assistant de cycle de vie S3 qu’avec
  `allow_bucket_writes=True`. La protection en lecture seule bloque les deux dans
  une exécution de la CLI.
- **Utiliser `CloudBOMGenerator` depuis votre propre code Python** n’installe pas
  la protection en lecture seule. Seule la commande `inventag` le fait.

## Tests et nomenclature logicielle {#tests-and-the-software-bill-of-materials}

La suite de tests et l’inventaire des dépendances ont leurs propres pages :
[Tests](../security/tests.md) et
[Nomenclature logicielle](../security/sbom.md).
