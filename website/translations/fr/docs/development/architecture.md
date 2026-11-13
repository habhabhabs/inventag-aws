---
title: Comment le code s’articule
description: Une carte du package Python d’InvenTag (CLI, orchestration multi-comptes, découverte, traitement, modèles, rapports et état) pour les contributeurs.
sidebar_position: 2
slug: /architecture/core-module-integration
---

# Comment le code s’articule

**À qui s’adresse cette page :** les contributeurs qui veulent s’orienter dans le code.

**Ce que vous saurez après lecture :** quel module fait quoi pendant une exécution,
et par où commencer pour une modification.

## Le parcours d’une exécution {#the-path-of-one-run}

```text
inventag_cli.py
  -> inventag/cli/main.py              parse flags, validate, set up logging
       -> templating/runner.py         only with --template: load templates,
                                       apply a config template to the flags
  -> core/cloud_bom_generator.py       CloudBOMGenerator
       1. sessions per account         profiles, keys or sts:AssumeRole
       2. discovery per account        discovery/inventory.py and friends
       3. consolidation                one list of resource dictionaries
       4. documents                    reporting/bom_processor.py, then
                                       reporting/converter.py (default) or
                                       templating/render_excel.py and
                                       render_word.py (with --template)
       5. state                        state/ snapshots and changelog
```

## Packages {#packages}

| Package | Responsabilité | Point de départ |
|---|---|---|
| `inventag/cli/` | Options, validation de la configuration, journalisation | `main.py`, `config_validator.py` |
| `inventag/core/` | Orchestration multi-comptes et identifiants | `cloud_bom_generator.py` |
| `inventag/discovery/` | Recherche des ressources : appels d’API par service, Tagging API, Cost Explorer | `inventory.py`, `comprehensive_discovery.py` |
| `inventag/reporting/` | Normalisation des ressources et écriture des fichiers Excel et Word par défaut | `bom_processor.py`, `converter.py` |
| `inventag/templating/` | Chargement des modèles, validation, héritage, contrôles des politiques d’étiquetage et sortie Excel et Word pilotée par les modèles | `schema.py`, `registry.py`, `runner.py` |
| `inventag/state/` | Instantanés, différences et journaux des modifications | `state_manager.py` |
| `inventag/compliance/` | Classes de bibliothèque pour les contrôles d’étiquettes et la sécurité ; la plupart ne sont pas utilisées par la CLI aujourd’hui | `checker.py` |
| `inventag/security/` | La protection en lecture seule, la liste des politiques IAM, la rédaction des journaux, les fichiers de sortie sûrs | `read_only_guard.py`, `iam_policy.py` |

## Le dictionnaire de ressource {#the-resource-dictionary}

Tout ce qui se trouve entre la découverte et la sortie circule sous forme de dictionnaires simples,
un par ressource. Les champs sur lesquels s’appuient les modèles et les rapports sont listés dans
la [Référence des modèles](../templates/reference.md#resource-fields-you-can-use-as-columns).
Gardez-les stables : en renommer un casse les modèles des utilisateurs.

## Comment les modèles s’intègrent {#how-templates-hook-in}

`templating/runner.py` définit `TemplatedCloudBOMGenerator`, une sous-classe de
`CloudBOMGenerator` qui ne remplace que l’étape de génération des documents. Le reste d’une exécution,
y compris la découverte, les identifiants et l’état, reste inchangé. Sans
`--template`, les classes d’origine sont utilisées et la sortie est exactement la même
qu’avant.

## Lacunes connues à corriger {#known-gaps-worth-fixing}

Elles sont suivies sur [l’état des fonctionnalités](../getting-started/status.md) et dans la liste
« Open work » de `CHANGELOG.md`. Chacune est une bonne première contribution :

- `discovery/arn_utils.py` est l’unique endroit qui construit et compare les ARN
  (`build_arn`, `normalize_arn`, `ResourceArnIndex`). `inventory.py` et
  `comprehensive_discovery.py` l’utilisent tous deux. Les étiquettes de la Resource Groups
  Tagging API sont associées par ARN normalisé, puis par service, région et ID.
- Les services globaux (IAM, liste S3, CloudFront, Route 53, certificats ACM de
  CloudFront) s’exécutent une fois par compte depuis `us-east-1` et portent la région
  `global`.
- La recherche des régions dans `cloud_bom_generator.py` se rabat sur quatre régions lorsque
  `DescribeRegions` échoue. `discovery/inventory.py` a une autre liste de repli
  de quatorze régions.
- Une `description` personnalisée dans un fichier de descriptions de services est ignorée pour les
  services qui ont un modèle intégré (S3, EC2, RDS, Lambda, VPC).
- `--enable-cost-analysis` appelle Cost Explorer même avec
  `--no-billing-validation`.
- L’échec d’un compte ne modifie pas le code de sortie.
- Ces modules ne sont pas sur le chemin de la CLI : `reporting/template_framework.py`,
  `branding_system.py`, `word_builder.py`, `excel_builder.py`,
  `document_generator.py` et `configuration_manager.py`.

Les anciennes notes de conception ont été retirées du dépôt. Utilisez les pages de ce site.
