---
title: Nomenclature logicielle (SBOM)
description: Ce que liste la nomenclature logicielle (SBOM) d’InvenTag, comment elle est générée et comment vérifier les dépendances que vous installez.
sidebar_position: 3
---

# Nomenclature logicielle (SBOM)

**À qui s’adresse cette page :** aux évaluateurs de sécurité et d’achats qui ont besoin de savoir de quoi
InvenTag est fait.

**Ce que vous saurez après lecture :** quels fichiers SBOM existent, comment ils sont
produits et comment en générer un pour votre propre installation.

## Ce que génère la construction de la documentation {#what-the-documentation-build-generates}

Chaque fois que le site de documentation est déployé, la construction génère des fichiers SBOM
pour le dépôt et ses dépendances et les publie avec le site :

| Fichiers | Ce qu’ils listent | Format |
|---|---|---|
| SBOM du dépôt | Tout ce que Syft trouve dans le dépôt | Syft JSON, CycloneDX JSON et SPDX JSON |
| Python, depuis `requirements.txt` | Les versions minimales qu’InvenTag déclare | CycloneDX JSON et XML |
| Python, depuis une installation neuve | Les versions réellement installées | CycloneDX JSON et une liste `pip freeze` |
| Site web de documentation | Les paquets Node.js utilisés pour construire ce site | CycloneDX JSON |

Non vérifié sur un runner GitHub Actions : les fichiers SBOM que publie la construction de la documentation ; cette page est lue dans le fichier de workflow.

Une page de synthèse, **Software Bill of Materials (SBOM)**, est ajoutée à cette
section par la même construction ; elle apparaît donc sur le site en ligne mais pas dans une
construction locale.

Les dépendances Python sont déclarées avec des versions minimales, et non des versions exactes ;
le fichier des versions installées est donc celui qui montre ce qu’obtient une vraie installation
le jour de la construction.

## Produire un SBOM pour votre propre installation {#produce-an-sbom-for-your-own-installation}

```bash title="Terminal"
pip install inventag-aws cyclonedx-bom
cyclonedx-py environment --output-format json --output-file inventag-sbom.json
```

Non vérifié sur la version de cyclonedx-bom que vous installez : les options de `cyclonedx-py environment`.

Lancez-le dans l’environnement virtuel où vous avez installé InvenTag, afin que le fichier
liste exactement ce que vous exécutez.

## Surveiller les vulnérabilités {#keep-an-eye-on-vulnerabilities}

Un workflow planifié analyse les dépendances à la recherche de vulnérabilités connues. Lisez
[Comment les dépendances sont vérifiées](./index.md#how-dependencies-are-checked) pour savoir
ce qui s’exécute et ce qui fait échouer la construction, et
[Après un incident de chaîne d’approvisionnement](./index.md#after-a-supply-chain-incident) si
vous pensez que quelque chose a été compromis.
