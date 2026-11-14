---
title: Ce qu’est InvenTag
description: Ce que fait InvenTag en une exécution (trouver les ressources AWS, vérifier les étiquettes, écrire des rapports Excel et Word), ce qu’il écrit et ses limites.
sidebar_position: 1
---

# Ce qu’est InvenTag

**À qui s’adresse cette page :** à toute personne qui se demande si InvenTag convient à son travail.

**Ce que vous saurez après lecture :** ce que fait une exécution, ce qu’elle modifie (uniquement
des fichiers sur votre disque) et où se situent ses limites.

## Trois questions, un rapport {#three-questions-one-report}

InvenTag répond à trois questions sur vos comptes AWS :

1. **Qu’y a-t-il ?** Une liste de ressources sur l’ensemble des comptes et des régions.
2. **Est-ce bien étiqueté ?** Des colonnes d’étiquettes dans le rapport et, avec un
   [modèle de politique d’étiquetage](../templates/index.md), un contrôle des étiquettes
   obligatoires et des valeurs autorisées.
3. **Qu’est-ce qui a changé depuis la dernière fois ?** Chaque exécution enregistre un instantané afin de pouvoir
   comparer les exécutions. Voir [Suivre les changements entre deux exécutions](../guides/track-changes.md).

La réponse est une nomenclature (BOM) : un classeur Excel, un document Word,
ou les deux.

## Comment se déroule une exécution {#how-a-run-works}

```text
your AWS credentials
        |
        v
  1. find resources   --> List/Describe/Get calls per service,
        |                 the Resource Groups Tagging API, Cost Explorer
        v
  2. tidy             --> service names, IDs, tags
        |
        v
  3. check tags       --> only when a tag policy is active
        |
        v
  4. write files      --> bom_output/*.xlsx, *.docx, state/ snapshot
```

1. **Identifiants.** InvenTag utilise la chaîne d’identifiants AWS habituelle : un profil,
   des variables d’environnement, une session IAM Identity Center (SSO) ou un rôle IAM.
   Il peut aussi assumer un rôle dans d’autres comptes.

   Non vérifié sur AWS IAM Identity Center : la connexion avec une vraie session SSO.
2. **Découverte.** Pour chaque compte et chaque région, il appelle des interfaces de programmation
   d’applications (API) AWS en lecture seule. Par défaut, il appelle aussi `GetCostAndUsage` de
   Cost Explorer pour repérer les services qui génèrent des dépenses. AWS facture les requêtes à l’API
   Cost Explorer ; `--no-billing-validation` désactive ces appels.
   Consultez les [tarifs actuels de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
3. **Traitement.** Il uniformise les noms et identifiants de services et collecte les étiquettes.
4. **Sortie.** Il écrit les fichiers dans le dossier de sortie (`bom_output/` par défaut)
   et un instantané dans `bom_output/state/`.

## Ce qu’il modifie {#what-it-changes}

Des fichiers sur votre disque. La commande `inventag` ne fait que lire vos comptes AWS.
La seule exception est le téléversement de ses propres fichiers de rapport vers votre
compartiment S3, et seulement lorsque vous passez `--s3-bucket`. Avec une option Google,
elle crée aussi des fichiers dans votre Google Drive.

Une **protection en lecture seule** vérifie chaque appel AWS avant son envoi. Les appels qui
ne sont pas des lectures (`List`, `Describe`, `Get` et similaires) sont bloqués, de même que les lectures
qui renverraient des secrets ou le contenu de fichiers, comme lire la valeur d’un secret ou
télécharger un objet S3. Vous ne pouvez pas désactiver la protection.

Donnez tout de même à InvenTag une identité IAM en lecture seule. Deux filets de sécurité indépendants
valent mieux qu’un : [Configurer l’accès en lecture seule](../guides/read-only-access.md).

## Ce qu’il n’est pas {#what-it-is-not}

- **Pas un outil de conformité.** InvenTag peut recueillir des éléments de preuve, comme un
  inventaire et la couverture des étiquettes. Il n’évalue ni ne certifie la conformité à
  SOC 2, PCI DSS, HIPAA, RGPD ou tout autre référentiel.
- **Pas un outil de gestion des coûts.** Il liste les ressources et les étiquettes, et
  ne suit pas votre facture. L’option `--enable-cost-analysis` ajoute une feuille
  Cost Analysis avec des coûts mensuels estimés à partir de l’API AWS Pricing. Ce
  sont uniquement des estimations, pas votre facture.
- **Sans lien avec AWS.**
- **Pas complet.** Il dispose de son propre code de découverte pour 46 services AWS, pas pour
  tous, et n’a jamais été testé sur un compte AWS réel.
  [État des fonctionnalités](./status.md) en énumère les limites.

## Étapes suivantes {#next-steps}

- [Installer InvenTag](./installation.md)
- [Démarrage rapide](./quick-start.md)
