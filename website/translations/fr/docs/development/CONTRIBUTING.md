---
title: Contribuer à InvenTag
description: Mettez en place un environnement de développement pour InvenTag, lancez les tests et les linters, construisez le site de documentation et ouvrez une pull request.
sidebar_position: 1
---

# Contribuer à InvenTag

**À qui s’adresse cette page :** vous voulez corriger un bogue, ajouter une fonctionnalité ou améliorer la documentation.

**Ce que vous saurez faire après lecture :** installer le code, lancer les vérifications que le
projet utilise et ouvrir une pull request facile à relire.

## Avant de commencer {#before-you-start}

1. Cherchez une [issue](https://github.com/habhabhabs/inventag-aws/issues) existante.
   S’il n’y en a pas, ouvrez-en une et décrivez la modification.
2. Pour une modification importante, attendez la réponse d’un mainteneur avant d’écrire beaucoup
   de code.

## Installation {#set-up}

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # includes moto
pip install -e .          # optional: gives you the `inventag` command
git checkout -b fix/short-description
```

Préfixes de branche : `feat/`, `fix/`, `docs/`, `refactor/`, `test/`.

## Lancer les vérifications {#run-the-checks}

```bash
black --check scripts/ inventag/
flake8 scripts/ inventag/ --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

La CI lance les mêmes commandes `black --check` et `flake8`, puis les tests sur
Python 3.11, 3.12, 3.13, 3.14 et 3.15. La suite complète (`python -m pytest -q`) prend
environ deux minutes, réussit sur `main` (1315 réussis, 9 benchmarks de performance
désélectionnés) et ne nécessite aucun compte AWS : tous les tests utilisent moto. Une modification doit la
garder au vert. Ne lancez les benchmarks que sur demande : `python -m pytest -m performance`.
Lancez `pip-audit -r requirements.txt` lorsque vous modifiez une dépendance ; la CI échoue sur un
nouvel avis de sécurité.

**Ne lancez jamais les tests par accident sur un vrai compte AWS.** Désactivez
`AWS_PROFILE` et les vraies clés, ou utilisez moto.

## Travailler sur les modèles {#work-on-templates}

- Les modèles intégrés se trouvent dans `inventag/templating/builtin/`. Chacun nécessite un
  test dans `tests/integration/templating/` qui le génère.
- Le format des modèles est décrit une seule fois, dans
  `inventag/templating/schema.py`. Après l’avoir modifié, régénérez la référence de la
  documentation : `python -m inventag.templating.reference --write`. Un test unitaire
  échoue si vous l’oubliez.
- Les exemples de sortie des pages de documentation proviennent de
  `scripts/docs/generate_example_outputs.py`, qui exécute la vraie CLI sur
  moto. Après un changement de comportement, lancez `pip install pillow` et
  `python scripts/docs/generate_example_outputs.py`, puis validez le résultat.
  `--check` indique si les pages sont obsolètes. Les images nécessitent
  LibreOffice (`soffice`) et `pdftoppm`.

## Travailler sur la documentation {#work-on-the-docs}

La documentation est composée de fichiers Markdown dans `docs/`, publiés avec Docusaurus depuis
`website/`.

```bash
cd website
npm ci
npm run build          # fails on broken links and missing SEO metadata
npm run check:links    # checks links in the built site
npm run start          # local preview at http://localhost:3000/inventag-aws/
```

Règles de rédaction :

- Chaque page a un `title` et une `description` uniques dans son front matter et
  exactement un titre `#`.
- Commencez par indiquer à qui s’adresse la page et ce que le lecteur saura faire.
- Phrases courtes, voix active, mots simples. Expliquez tout jargon.
- Chaque commande, option et sortie doit correspondre au code. Exécutez-la avant de l’écrire,
  et signalez les sorties d’exemple comme des données d’exemple.
- Pas de chiffres inventés, pas de superlatifs, pas d’affirmations de conformité ou
  de certification.
- Des titres dans l’ordre, des tableaux avec lignes d’en-tête, un texte alternatif sur les images, et aucun
  sens porté uniquement par un emoji ou une couleur.

La barre latérale est générée à partir des dossiers et du fichier
`_category_.json` de chaque dossier.

## Valider et ouvrir une pull request {#commit-and-open-a-pull-request}

Utilisez les [Conventional Commits](https://www.conventionalcommits.org/) :

```text
feat(templates): add landscape option for Word reports
fix(discovery): include EC2 instances in comprehensive discovery
docs: explain tag policy scopes
```

Dans la pull request, indiquez ce qui a changé, comment vous l’avez testé et quelle documentation vous
avez mise à jour. Mettez à jour [l’état des fonctionnalités](../getting-started/status.md) lorsque vous corrigez ou
ajoutez une fonctionnalité.

## Étapes suivantes {#next-steps}

- [Comment le code s’articule](./architecture.md)
- [Sécurité](../security/index.md)
