---
title: Nomenclature logicielle (SBOM)
description: Ce que liste la nomenclature logicielle (SBOM) d’InvenTag, comment elle est générée et comment vérifier les dépendances que vous installez.
sidebar_position: 3
---

# Nomenclature logicielle (SBOM)

**À qui s’adresse cette page :** aux évaluateurs de sécurité et d’achats qui ont besoin de savoir de quoi
InvenTag est fait.

**Ce que vous saurez après lecture :** quels fichiers SBOM existent, comment ils sont
produits, comment vérifier un fichier de publication et comment générer un SBOM
pour votre propre installation.

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

## Ce que contient une publication {#what-a-release-carries}

Chaque publication a des versions empaquetées : des archives de l’exécutable et
des paquets `.deb` et `.rpm`. Le workflow de publication crée pour elles les
fichiers ci-dessous. Voir
[Installer InvenTag](../getting-started/installation.md#choose-how-to-install)
pour les versions empaquetées.

| Fichier | Ce qu’il contient |
|---|---|
| `inventag-<version>-<os>-<cpu>.tar.gz`, `inventag_<version>_<cpu>.deb`, `inventag-<version>-1.<cpu>.rpm` | Les versions empaquetées |
| Un fichier `.cdx.json` pour chacun de ces fichiers, par exemple `inventag_<version>_amd64.deb.cdx.json` | Le SBOM de ce fichier : ses paquets Python et ses bibliothèques C, avec nom, version et licence |
| `inventag-<version>-<os>-<cpu>.THIRD-PARTY-LICENSES.txt` | Le fichier de mentions : le texte de licence de chaque composant embarqué |
| `inventag-<version>-<os>-<cpu>.components.json` | La liste des composants à partir de laquelle sont créés le SBOM et le fichier de mentions |
| `inventag-<version>-linux-<cpu>.build-image.txt` | Le relevé du système de construction Linux : sa version et les versions des bibliothèques que la construction embarque |
| `SHA256SUMS` | La somme de contrôle SHA-256 de chacun des autres fichiers de la publication |

Les fichiers SBOM utilisent le format CycloneDX, version 1.5, en JSON. Le workflow
les écrit à partir de la construction, donc ils listent ce qui se trouve dans le
fichier et non ce qu’un `requirements.txt` autorise.

Non vérifié sur le schéma CycloneDX : que les fichiers SBOM passent un validateur.

Non vérifié sur GitHub : que la publication contienne ces fichiers. Les exécutions de test jusqu’ici ne joignent rien à une publication, et la première exécution de publication avec ces fichiers n’a pas encore eu lieu.

### Vérifier un fichier de publication {#check-a-release-file}

Le workflow de publication signe les fichiers sans clé qui nous appartienne. Il
donne `SHA256SUMS` à l’étape `actions/attest` de GitHub. Cette étape écrit une
attestation de construction au nom du workflow. Pour vérifier un fichier avec la
CLI GitHub :

```bash title="Terminal"
gh attestation verify inventag_%INVENTAG_VERSION%_amd64.deb --repo habhabhabs/inventag-aws
```

Pour vérifier une somme de contrôle, voir
[Vérifier le téléchargement](../getting-started/installation.md#check-the-download).

Non vérifié sur GitHub : `gh attestation verify` sur un fichier de publication. Les exécutions de test ne créent aucune attestation. La première attestation réelle est créée par la première exécution de publication, et cette exécution n’a pas encore eu lieu.

### Licences dans les versions empaquetées {#licenses-in-the-packaged-builds}

InvenTag est sous licence MIT. Les versions empaquetées embarquent aussi des
fichiers d’autres projets. Le fichier de mentions les liste avec le texte de leurs
licences.

Les archives de l’exécutable, le `.deb` et le `.rpm` embarquent GNU libiconv, une
bibliothèque sous la licence publique générale limitée de GNU (LGPL) version 2.1.
La formule Homebrew prévue installe la même archive, donc elle l’embarque aussi.
Le code de libiconv se trouve dans les modules d’extension de lxml. InvenTag a
besoin de lxml pour écrire des fichiers Word. Le projet lxml construit ces modules
et y lie libiconv. InvenTag embarque les fichiers de lxml sans modification : la
construction compare chaque fichier octet par octet avec le fichier du wheel du lock.

- Une installation avec pip, pipx ou uv ne contient pas libiconv dans un fichier
  d’InvenTag. Votre installateur télécharge le wheel propre de lxml depuis le Python
  Package Index.
- Le fichier de mentions est `THIRD-PARTY-LICENSES.txt` : `inventag/THIRD-PARTY-LICENSES.txt`
  dans l’archive autonome, et `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` et
  `/opt/inventag/THIRD-PARTY-LICENSES.txt` dans le `.deb` et le `.rpm`. La
  publication le liste aussi comme un fichier à part pour chaque système. Il
  contient le texte complet de la LGPL 2.1.
- Le code source de la bibliothèque se trouve aux adresses que nomme le fichier de
  mentions. Dans cette publication : libiconv 1.18 sur <https://www.gnu.org/software/libiconv/>
  et <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>, et lxml 6.1.3 sur
  <https://github.com/lxml/lxml>. Le workflow de publication demande les deux
  adresses de libiconv avant de signer les fichiers, et s’arrête si l’une ne répond pas.
- InvenTag ne fait aucune offre écrite d’envoyer le code source. Si une adresse ne
  fonctionne pas, ouvrez un ticket sur
  <https://github.com/habhabhabs/inventag-aws/issues>.
- Les modules de lxml sont des fichiers séparés dans le répertoire d’installation.
  Vous pouvez les remplacer par votre propre build de lxml de la même version. Le
  dossier est `inventag/_internal/lxml/` dans l’archive autonome et
  `/opt/inventag/_internal/lxml/` pour le `.deb` et le `.rpm`. Sous macOS, signez de
  nouveau un module après l’avoir remplacé : `codesign -s - --force <file>`.

Non vérifié sur votre propre build de lxml : qu’un module que vous construisez fonctionne à la place du module inclus.

Non vérifié sur les serveurs de GNU : que les deux adresses de libiconv continuent de répondre. Le workflow a obtenu les deux le jour de son exécution de test.

Cette section ne constitue pas un avis juridique.

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
