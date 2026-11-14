---
title: Modèles
description: Réutilisez des mises en page de rapport, des politiques d’étiquetage et des paramètres d’exécution avec de petits modèles YAML à copier, adapter et valider.
sidebar_position: 1
---

# Modèles

**À qui s’adresse cette page :** à toute personne qui lance InvenTag plus d’une fois
et veut la même mise en page de rapport, les mêmes règles d’étiquetage ou les mêmes
paramètres d’analyse à chaque exécution.

**Ce que vous saurez faire après lecture :** choisir un modèle intégré, l’utiliser avec
`--template`, et savoir quand créer le vôtre.

## Ce qu’est un modèle {#what-a-template-is}

Un modèle est un court fichier YAML qui indique à InvenTag comment réaliser une partie
d’une exécution. Il en existe trois types :

| Type | Ce qu’il contrôle | Exemple intégré |
|---|---|---|
| `report` | L’aspect du classeur Excel et du document Word : titre, couleurs, colonnes, feuilles et sections présentes | `standard-bom`, `executive-summary` |
| `tag-policy` | Les étiquettes que chaque ressource doit porter, et les valeurs autorisées | `finops-cost-allocation`, `security-baseline` |
| `config` | Ce qu’il faut analyser et produire : comptes, régions, fichiers de sortie, ainsi que le rapport et la politique d’étiquetage à utiliser | `single-account`, `org-multi-account`, `ci-pipeline` |

InvenTag fournit huit [modèles intégrés](./catalogue.md). Vous pouvez copier n’importe
lequel dans votre projet et [l’adapter](./adapt-a-template.md).

## Utiliser un modèle {#use-a-template}

Ajoutez `--template` à une exécution normale. Vous pouvez donner un nom ou un chemin de fichier :

```bash
inventag --template executive-summary --create-word
inventag --template ./my-templates/acme-bom.yaml --create-excel
```

Répétez `--template` pour combiner un modèle de chaque type :

```bash
inventag --template standard-bom --template security-baseline --create-excel
```

Quelques règles déterminent ce qui l’emporte lorsque des paramètres se chevauchent :

1. **Les options que vous tapez l’emportent.** Si un modèle de configuration indique
   `outputs: [excel]` et que vous tapez `--create-word`, vous obtenez seulement le fichier Word :
   un `--create-excel` ou `--create-word` tapé remplace entièrement `outputs`.
2. **Un modèle donné en ligne de commande l’emporte sur une référence à l’intérieur d’un autre
   modèle.** `--template security-baseline` remplace la politique d’étiquetage que
   `finops-cost-report` désigne.
3. **Sans modèle de rapport, InvenTag utilise `standard-bom`.**

Les exécutions sans `--template` utilisent la mise en page d’origine du rapport.

`--tag-mappings` et `--service-descriptions` ajoutent des colonnes à cette mise
en page d’origine. Avec `--template`, un rapport n’affiche que les colonnes qu’il
liste ; ces colonnes n’apparaissent donc pas tant que vous ne les indiquez pas
sous `columns`, par exemple `- field: service_description`. InvenTag consigne un
avertissement qui nomme les colonnes manquantes. Voir la [liste des champs](./reference.md#resource-fields-you-can-use-as-columns).

## Ce qu’une politique d’étiquetage ajoute à vos rapports {#what-a-tag-policy-adds-to-your-reports}

Lorsqu’une politique d’étiquetage est active, InvenTag vérifie chaque ressource concernée et
ajoute :

- une feuille **Tag Compliance** dans le classeur, avec une ligne par ressource, indiquant ce
  qui manque ou ce qui est erroné ;
- une section **Tag compliance** dans le document Word ;
- un fichier `tag_compliance_<timestamp>.json` utilisable dans des scripts ou en CI ;
- un résumé d’une ligne dans le terminal.

Exemple de sortie d’une exécution hors ligne avec `--template finops-cost-report`
(données d’exemple) :

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

Un modèle de configuration peut définir `fail_on_tag_violations: true` pour qu’InvenTag se
termine avec le code 3 lorsqu’une ressource enfreint la politique. Le modèle intégré
`ci-pipeline` le fait.

Deux options facultatives ont leurs propres codes de sortie :
`--fail-on-account-error` se termine avec le code 5 quand un compte n’a pas pu
être analysé ou a dépassé son délai, et `--fail-if-empty` avec le code 6 quand aucune ressource n’a été
trouvée. Les deux l’emportent sur le code 3. Les rapports sont tout de même écrits.

## Où InvenTag cherche les modèles {#where-inventag-looks-for-templates}

Lorsque vous donnez un nom, InvenTag examine ces dossiers dans l’ordre et utilise la
première correspondance :

1. Chaque dossier de la variable d’environnement `INVENTAG_TEMPLATE_PATH` (séparez les
   dossiers par `:` sous Linux et macOS, par `;` sous Windows).
2. `.inventag/templates/` dans le dossier d’où vous lancez InvenTag (votre projet).
3. `~/.config/inventag/templates/` (ou `$XDG_CONFIG_HOME/inventag/templates/`).
4. Les modèles intégrés.

Non vérifié sur Windows : le séparateur `;` dans `INVENTAG_TEMPLATE_PATH`.

Ainsi, un fichier nommé `.inventag/templates/standard-bom.yaml` remplace le modèle intégré
`standard-bom` pour ce projet. Il peut toujours s’appuyer sur l’original avec
`extends: standard-bom`. Lancez `inventag templates list` pour voir ce qui est
trouvé et d’où cela provient.

## Sûr par conception {#safe-by-design}

Les modèles sont de simples données :

- InvenTag les lit avec un chargeur YAML sûr. Les balises YAML qui créent des objets Python,
  comme `!!python/object`, sont rejetées.
- Les modèles ne peuvent ni exécuter de code, ni évaluer d’expressions, ni récupérer quoi que ce
  soit sur Internet.
- Les références de fichiers à l’intérieur d’un modèle (`extends`, `tag_policy`,
  `report_template`, `logo`) doivent être des chemins relatifs qui restent dans le dossier du
  modèle.
- Les modèles de configuration ne peuvent pas contenir de clés d’accès. Utilisez `profile_name`
  ou `role_arn`.
- Les valeurs venant d’AWS qui commencent par `=` sont écrites dans Excel comme du texte ; une
  valeur d’étiquette ne peut donc pas devenir une formule de tableur.

## Étapes suivantes {#next-steps}

- [Modèles intégrés](./catalogue.md) : ce que chacun produit.
- [Adapter un modèle](./adapt-a-template.md) : copier, modifier, valider, exécuter.
- [Référence des modèles](./reference.md) : chaque champ.
- [Exemples](../examples/index.md) : des recettes complètes qui utilisent des modèles.
