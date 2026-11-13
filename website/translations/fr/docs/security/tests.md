---
title: Tests
description: "Comment InvenTag est testé : ce que couvre la suite, ce qu’elle ne peut pas prouver, comment l’exécuter et sur quelles versions de Python la CI l’exécute."
sidebar_position: 2
---

# Tests

**À qui s’adresse cette page :** à toute personne qui décide de la confiance à accorder à InvenTag, et à toute personne qui
modifie le code.

**Ce que vous saurez après lecture :** ce que couvrent les tests, ce qu’ils ne couvrent pas
et comment les exécuter vous-même.

## Ce qui s’exécute, et où {#what-runs-and-where}

La suite compte 1 389 tests (1 398 avec les neuf benchmarks). Aucun n’appelle le
vrai AWS : les tests qui ont besoin d’AWS utilisent [moto](https://github.com/getmoto/moto),
qui imite AWS en mémoire, ou des clients simulés, avec de faux identifiants. Les
tests s’exécutent hors ligne et ne coûtent rien. Neuf benchmarks de performance sont exclus de
l’exécution normale et ne démarrent que si vous les demandez.

La CI exécute la suite sur Python 3.11, 3.12, 3.13, 3.14 et 3.15, ainsi que des jobs de lint,
d’intégration et de sécurité de base, à chaque push sur `main` ou `develop` et à
chaque pull request vers `main`.

**Aucun test ne s’exécute sur un vrai compte AWS.** Lorsqu’un résultat dépend du comportement du
vrai AWS, l’[état des fonctionnalités](../getting-started/status.md) le précise.

## Avec quoi chaque fonctionnalité est testée {#what-each-feature-is-tested-with}

Chaque ligne est vérifiée hors ligne sur un AWS simulé (moto), ou sur des clients Google simulés
pour les lignes Google. L’API Resource Groups Tagging de moto sert de
référence pour les ARN et les étiquettes.

| Fonctionnalité | Tests |
|---|---|
| Ressources dans un ou plusieurs comptes, compte en échec nommé dans le rapport et le résumé d’exécution | `tests/integration/test_status_validation.py`, `tests/unit/test_cli_security.py` |
| Rapports Excel et Word, ordre stable des feuilles et des lignes, colonnes d’étiquettes | `tests/integration/test_status_validation.py`, `tests/test_bom_converter.py` |
| Modèles de rapport, vérifications de politique d’étiquetage, code de sortie 3 | `tests/integration/test_status_validation.py`, `tests/unit/templating/` |
| Filtres (`--account-regions`, `--account-services`, `--account-tags`) sur chaque chemin | `tests/integration/test_status_validation.py`, `tests/unit/test_global_services.py` |
| ARN réels et association des étiquettes pour chaque service, sans doublons | `tests/unit/test_arn_and_tags.py` |
| Services globaux pour `eu-west-1` seule, toutes les régions et une liste avec `us-east-1` | `tests/unit/test_global_services.py` |
| Feuilles réseau et sécurité, `--risk-threshold` (code de sortie 4) | `tests/integration/test_status_validation.py` |
| `--enable-cost-analysis` et sa feuille | `tests/integration/test_status_validation.py` |
| `--per-account-reports`, `--accounts-prompt`, `--credential-timeout`, `--disable-account-logging` | `tests/integration/test_status_validation.py` |
| Avertissement `--bom-config`, `--validate-config-only` sans appels AWS, un avertissement par service refusé | `tests/integration/test_status_validation.py` |
| Rapport de changements entre exécutions, instantanés | `tests/integration/test_status_validation.py`, `tests/unit/test_changelog_generator.py` |
| Protection en lecture seule, audit, `--validate-operations`, téléversement S3, fichiers privés | `tests/unit/test_cli_security.py`, `tests/unit/test_security_read_only_guard.py` |
| Masquage des secrets, y compris les secrets Google | `tests/unit/test_security_redaction.py`, `tests/unit/test_google_output.py` |
| Sortie Google Sheets et Docs (clients Google simulés) | `tests/unit/test_google_output.py` |

## Exécuter les tests vous-même {#run-the-tests-yourself}

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Lancez les benchmarks avec `pytest -m performance`. Pour configurer l’environnement de
développement complet : [Contribuer à InvenTag](../development/CONTRIBUTING.md).

## Ce qui est vérifié par ailleurs {#what-else-is-checked}

- **Le site de documentation** est construit en CI. La construction échoue sur un lien cassé,
  et une vérification d’accessibilité s’exécute sur les pages construites.
- **Les dépendances** sont analysées à la recherche de vulnérabilités connues. Voir
  [Sécurité](./index.md#how-dependencies-are-checked) et la
  [nomenclature logicielle](./sbom.md).
