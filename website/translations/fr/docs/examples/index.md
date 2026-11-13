---
title: Exemples
description: Recettes InvenTag à copier-coller pour les tâches courantes, chacune avec la commande, le modèle et la sortie qu’elle produit, de l’audit rapide aux envois planifiés vers S3.
sidebar_position: 1
---

# Exemples

**À qui s’adresse cette page :** vous savez quelle tâche vous voulez accomplir et
cherchez une recette à copier.

**Ce que vous y trouvez :** pour chaque exemple, l’objectif, le modèle, la commande, la
sortie qu’elle produit et la suite à donner.

Toutes les sorties de ces pages proviennent d’une vraie exécution d’InvenTag sur un AWS
simulé ([moto](https://github.com/getmoto/moto)), pas d’un compte réel. Ce sont des
**données d’exemple** : les comptes (comme `123456789012`) et les ressources `acme-*`
sont fictifs, et vos noms et vos totaux seront différents. Les exemples sont
produits par `scripts/docs/generate_example_outputs.py`, ils correspondent donc au
code actuel.

| Exemple | Ce que vous obtenez |
|---|---|
| [Audit rapide d’un compte](./quick-audit.md) | Un inventaire Excel et Word du compte auquel vous êtes connecté |
| [Inventorier tous les comptes d’une organisation](./accounts-setup.md) | Un seul rapport couvrant plusieurs comptes, via un rôle en lecture seule dans chacun |
| [Appliquer une politique d’étiquetage en CI](./tag-policy-in-ci.md) | Une étape de pipeline qui échoue quand des ressources enfreignent vos règles d’étiquetage |
| [Étiquettes d’allocation des coûts FinOps](./finops-cost-allocation.md) | Un rapport indiquant quelles ressources portent les étiquettes dont vos rapports de coûts ont besoin |
| [Revue de l’étiquetage de sécurité](./security-review.md) | La couverture des étiquettes de propriétaire, d’environnement et de classification des données |
| [Rapport Word de direction à votre image](./branded-executive-report.md) | Un court rapport Word en paysage avec votre logo et vos couleurs |
| [Vos propres colonnes](./custom-columns.md) | Un classeur avec exactement les colonnes de votre choix, sur une seule feuille |
| [Envoyer les rapports vers S3 selon un calendrier](./scheduled-s3-upload.md) | Des rapports chiffrés dans un bucket S3 après chaque exécution |

Tous les exemples supposent que vous avez [installé InvenTag](../getting-started/installation.md)
et que vous êtes connecté avec une [identité en lecture seule](../guides/read-only-access.md).
