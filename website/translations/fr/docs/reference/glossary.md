---
title: Glossaire
description: Le sens simple des termes de la documentation d’InvenTag, du fichier de comptes et de l’ARN à la politique d’étiquetage et à la protection en lecture seule.
sidebar_position: 6
---

# Glossaire

**À qui s’adresse cette page :** toute personne qui rencontre un mot inconnu dans cette documentation.

La documentation emploie chacun des termes ci-dessous dans un seul sens.

| Terme | Signification |
|---|---|
| **Fichier de comptes** | Un fichier YAML ou JSON, transmis avec `--accounts-file`, qui liste les comptes AWS à analyser. Voir [Fichiers de configuration](./configuration-files.md#accounts-file). |
| **ARN** | Amazon Resource Name : l’identifiant unique qu’AWS attribue à une ressource, par exemple `arn:aws:s3:::acme-app-logs`. |
| **Compte AWS** | Un compte AWS, identifié par un ID de compte à 12 chiffres tel que `123456789012`. |
| **BOM** | Bill of materials, la nomenclature : la liste des ressources qu’InvenTag écrit dans Excel ou Word. |
| **Conforme** | Une ressource qui possède toutes les étiquettes qu’exige une politique d’étiquetage, avec des valeurs autorisées. |
| **Modèle de configuration** | Un modèle avec `kind: config` : quels comptes et régions analyser, quels fichiers écrire, et quels modèle de rapport et politique d’étiquetage utiliser. |
| **Cost Explorer** | Le service AWS qui rend compte des dépenses. InvenTag l’appelle pour repérer les services qui génèrent des dépenses ; AWS facture chaque requête. |
| **Chaîne d’identifiants** | L’ordre dans lequel les outils AWS cherchent des identifiants : variables d’environnement, puis profils, puis rôles IAM. |
| **Code de sortie** | Le nombre qu’une commande renvoie à la fin de son exécution. `0` signifie succès ; InvenTag utilise `1` pour les erreurs, `2` pour les options non valides ou incompatibles, `3` pour les violations de la politique d’étiquetage, `4` pour les règles de groupe de sécurité au niveau de `--risk-threshold` ou au-dessus, `5` pour un compte qui n’a pas pu être analysé entièrement (avec `--fail-on-account-error`) et `6` quand il n’y a rien à signaler (avec `--fail-if-empty`). Si plusieurs codes s’appliquent, le 5 passe en premier, puis le 6, puis le 3, puis le 4. Voir [Codes de sortie](./cli.md#exit-codes). |
| **IAM** | AWS Identity and Access Management : les utilisateurs, les rôles et les politiques qui définissent ce qu’ils peuvent faire. |
| **IAM Identity Center** | Le service AWS d’authentification unique (SSO) pour les comptes AWS. Il s’appelait AWS SSO. |
| **Rôle IAM** | Une identité dotée d’autorisations que d’autres identités peuvent assumer pour une courte durée. |
| **moto** | Une bibliothèque Python qui imite AWS sur votre ordinateur. Les exemples de sortie de la documentation proviennent d’exécutions sur moto. |
| **OIDC** | OpenID Connect : permet à un système d’intégration continue tel que GitHub Actions ou GitLab CI/CD d’obtenir des identifiants AWS de courte durée sans clés stockées. |
| **Hors périmètre** | Une ressource qu’une politique d’étiquetage ne vérifie pas, en raison de ses paramètres `scope`. |
| **Protection en lecture seule** | La partie d’InvenTag qui vérifie chaque appel AWS avant son envoi et bloque tout ce qui n’est pas une lecture. Toujours active. |
| **Région** | Un emplacement géographique AWS, écrit sous la forme d’un code tel que `us-east-1` ou `eu-west-1`. |
| **Modèle de rapport** | Un modèle avec `kind: report` : le titre, les couleurs, les colonnes, les feuilles et les sections des fichiers Excel et Word. |
| **Données d’exemple** | Sortie d’exécutions d’InvenTag sur moto, avec des comptes et des ressources fictifs. Utilisées dans ces pages. |
| **Instantané** | Un fichier JSON dans `bom_output/state/` qui enregistre ce qu’une exécution a trouvé, afin de pouvoir comparer les exécutions. |
| **Étiquette** | Une clé et une valeur attachées à une ressource AWS, par exemple `Owner=platform`. Les clés sont sensibles à la casse. |
| **Politique d’étiquetage** | Un modèle avec `kind: tag-policy` : les étiquettes que les ressources doivent avoir et les valeurs autorisées. |
| **Modèle** | Un petit fichier YAML qui contrôle une partie d’une exécution : un modèle de rapport, une politique d’étiquetage ou un modèle de configuration. Voir [Modèles](../templates/index.md). |
| **Limitation de débit (throttling)** | AWS qui ralentit ou refuse des requêtes parce que trop d’entre elles arrivent en même temps. |
