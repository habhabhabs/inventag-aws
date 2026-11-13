---
title: État des fonctionnalités et limites connues
description: Quelles fonctionnalités d’InvenTag marchent dans la version actuelle, lesquelles sont partielles, quelles options s’arrêtent sur une erreur, et les limites, coûts et risques à connaître avant de vous y fier.
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
| `--service-descriptions` | Les descriptions personnalisées fonctionnent pour les services pour lesquels InvenTag n’a pas de description intégrée. Pour les ressources S3, EC2, RDS, Lambda et VPC, la description intégrée l’emporte, sauf si votre entrée indique aussi un `template`. Voir [Fichiers de configuration](../reference/configuration-files.md#service-descriptions). |
| `--enable-cost-analysis` | Ajoute une feuille Cost Analysis et les quatre colonnes `forgotten_analysis.*`. Les coûts sont des estimations de l’API AWS Pricing, pas votre facture. Elle effectue de nombreux appels supplémentaires à Cost Explorer, Pricing et CloudWatch. Voir [Coûts](#costs). |
| `--compliance-standard` | S’arrête avec le code de sortie 2. Une norme telle que SOC 2 ne peut pas être vérifiée à partir d’un inventaire, et une option qui n’afficherait qu’une étiquette vous induirait en erreur. Utilisez un modèle de politique d’étiquetage. |
| `--create-google-docs`, `--create-google-sheets` | Ne fonctionnent qu’avec des clients Google simulés. Voir [Google Sheets et Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Conservées pour que les anciennes commandes fonctionnent encore. La protection en lecture seule est toujours active. |
| `--disable-production-safety` | S’arrête avec le code de sortie 2. La protection ne peut pas être désactivée. |

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

## Ce qu’InvenTag trouve, et ce qu’il ne trouve pas {#what-inventag-finds-and-what-it-does-not}

- **Services dotés de leur propre code de découverte (24) :** VPC (VPC, sous-réseaux,
  groupes de sécurité, passerelles Internet et NAT, tables de routage, ACL réseau,
  adresses IP Elastic), EC2 (instances, volumes, instantanés, paires de clés), S3,
  RDS, Lambda, ELB, ELBv2, IAM, CloudFront, Route 53, KMS, CloudWatch, ECS,
  EKS, SNS, SQS, DynamoDB, API Gateway, Glue, WorkMail, CloudFormation, ACM,
  CloudTrail et EventBridge.
- **Tout le reste** ne peut apparaître que si l’API Resource Groups Tagging
  le renvoie. Cette API liste les ressources qui ont, ou ont eu un jour, des étiquettes ; les
  ressources non étiquetées de tout autre service sont donc absentes. Avec
  `--fallback-display auto` (valeur par défaut), ces ressources ne sont affichées que pour
  les services sans résultat issu de leur propre code de découverte. Utilisez
  `--fallback-display always` pour toutes les afficher.
- **Non collecté :** secrets, paramètres, contenu des objets ou toute autre donnée.
  La protection en lecture seule bloque ces appels.
- **Les services globaux** (IAM, la liste des buckets S3, CloudFront, Route 53 et
  les certificats ACM utilisés par CloudFront) sont lus une fois par compte depuis
  `us-east-1`, quelles que soient les régions choisies. Leur colonne de région indique `global` ;
  un bucket S3 conserve sa propre région. Voir [Lancer une analyse](../guides/run-a-scan.md).
- **Régions.** Sans `--account-regions`, InvenTag demande à EC2 les régions
  activées dans le compte. Si cet appel échoue, il consigne un avertissement et n’analyse que
  `us-east-1`, `us-west-2`, `eu-west-1` et `ap-southeast-1`. Une région qui
  échoue au contrôle d’accès est ignorée avec un avertissement, et l’exécution réussit quand même.

## Quand une exécution tourne mal {#when-a-run-goes-wrong}

- **Un compte échoue, les autres fonctionnent :** l’exécution se termine avec le code 0. Le
  résumé d’exécution et le rapport indiquent chaque compte en échec et la raison.
  Si tous les comptes échouent, l’exécution se termine avec le code 1.
- **Aucune ressource trouvée, ou les filtres les ont toutes écartées :** InvenTag n’écrit
  aucun rapport, consigne un avertissement et se termine avec le code 0. Vérifiez l’existence du fichier
  dans vos scripts.
- **Un service pour lequel vous n’avez pas l’autorisation :** InvenTag ignore cet appel, consigne un
  avertissement pour le service avec la raison, et poursuit. Les ressources de ce
  service peuvent quand même apparaître si l’API Resource Groups Tagging les renvoie.
- **Accès à Cost Explorer refusé :** l’exécution se poursuit sans données de facturation et
  consigne un avertissement.
- **Un appel bloqué par la protection en lecture seule** lève une erreur qui nomme
  l’opération. La CLI ne fait pas elle-même de tels appels.
- **Un échec de téléversement S3** fait se terminer toute l’exécution avec le code 1, une fois
  les rapports écrits en local.
- **Un format de rapport en échec** fait se terminer l’exécution avec le code 1.

## Coûts {#costs}

Par défaut, la découverte appelle l’API `GetCostAndUsage` de Cost Explorer. Dans notre
test hors ligne, elle a fait deux requêtes par compte. AWS facture chaque requête
Cost Explorer. Consultez les
[tarifs actuels de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` arrête ces appels. Le rapport n’a alors aucune donnée de
  facturation à comparer.
- `--enable-cost-analysis` fait davantage d’appels à Cost Explorer même avec
  `--no-billing-validation` (cinq à huit de plus par compte dans nos tests hors ligne, selon les ressources trouvées), ainsi que
  des appels à Pricing et CloudWatch.

Les autres appels sont gratuits, mais les grands comptes impliquent de nombreuses requêtes et une possible
limitation de débit (AWS ralentit vos requêtes).

## Performances et limites {#performance-and-limits}

- InvenTag n’a pas de mesures de performance sur des comptes réels. Analyser toutes les régions
  d’un grand compte est lent : un ensemble d’appels par service et par région.
- Les comptes sont analysés quatre à la fois par défaut. Chaque compte dispose de 1 800 secondes
  (30 minutes). Une exécution ne reprend pas ; si elle s’arrête, relancez-la.
- Les noms de feuilles Excel sont tronqués à 31 caractères. Les tableaux Word affichent jusqu’à 50
  ressources par service par défaut (`max_rows`).
- Lorsqu’une exécution enregistre un instantané, InvenTag supprime dans `bom_output/state/`
  les instantanés de plus de 30 jours ou au-delà des 100 plus récents. Gardez une copie si vous avez besoin
  d’un historique plus long.

## Notes de sécurité {#security-notes}

- **Utilisez quand même une identité IAM en lecture seule.** La protection bloque les appels d’écriture, et
  votre politique IAM (Identity and Access Management) est un second filet de sécurité
  indépendant. Voir [Configurer l’accès en lecture seule](../guides/read-only-access.md).
- **Les journaux de débogage sont expurgés** par défaut : les jetons de session, les clés et les signatures
  sont masqués. Considérez tout de même les journaux de débogage comme sensibles.
- **Deux fonctions de la bibliothèque écrivent dans AWS** lorsqu’elles sont appelées depuis votre propre code
  Python (la CLI ne les appelle pas) : `CredentialManager.setup_cross_account_roles()`
  crée des rôles IAM, et l’assistant S3 peut modifier les règles de cycle de vie d’un bucket
  (désactivé par défaut, et il fusionne avec les règles existantes).

## Tests et nomenclature logicielle {#tests-and-the-software-bill-of-materials}

La suite de tests et l’inventaire des dépendances ont leurs propres pages :
[Tests](../security/tests.md) et
[Nomenclature logicielle](../security/sbom.md).
