---
title: Référence des modèles
description: Chaque champ d’un modèle InvenTag - rapport, politique d’étiquetage et configuration - avec les types, les valeurs par défaut et le rôle de chacun.
sidebar_position: 4
---

# Référence des modèles

**À qui s’adresse cette page :** vous écrivez ou relisez un modèle et avez besoin du nom,
du type ou de la valeur par défaut exacts d’un champ.

**Ce que vous saurez faire après lecture :** écrire n’importe quel modèle sans deviner, et
lire les erreurs de validation en toute confiance.

## Structure du fichier {#file-layout}

Chaque modèle est un fichier YAML avec les mêmes champs de premier niveau :

```yaml
format_version: 1          # optional; 1 is the only version
kind: report               # report | tag-policy | config
name: acme-bom             # lower-case letters, digits and hyphens
description: One sentence shown by 'templates list'
extends: standard-bom      # optional: a template name or a relative path
spec:                      # the settings for this kind
  title: Acme Cloud Inventory
```

- Les fichiers se terminent par `.yaml` ou `.yml` et doivent être du texte UTF-8, de 256 Kio
  au plus. Un fichier donné par chemin peut aussi être du JSON (`.json`), par
  exemple `--template ./my.json`. Les modèles cherchés par nom dans les dossiers
  de recherche doivent être `.yaml` ou `.yml`, et `templates init` écrit du
  `.yaml`.
- Le nom du fichier doit correspondre à `name` (`acme-bom.yaml` a `name: acme-bom`).
  Les recherches par nom utilisent le nom du fichier.
- Les champs inconnus sont des erreurs : les fautes de frappe ne passent donc jamais en silence.
- Les clés en double sont des erreurs.
- Mettez les ID de compte et les couleurs hexadécimales entre guillemets (`"012345678901"`,
  `"1F3A5F"`) pour que YAML les conserve comme du texte.

## Références à d’autres fichiers {#references-to-other-files}

`extends`, `tag_policy`, `report_template` et `logo` peuvent pointer vers un autre
fichier :

- **Un nom** (`standard-bom`) est recherché dans les
  [dossiers de recherche](./index.md#where-inventag-looks-for-templates).
- **Un chemin relatif** (`./policies/strict.yaml`) est relatif au modèle qui le contient, et
  doit rester dans le dossier de ce modèle. Un `..` qui sort du dossier, les chemins absolus,
  `~` et les URL sont rejetés.

## Référence des champs {#field-reference}

Cette section est générée à partir du code
(`python -m inventag.templating.reference --write`) ; elle correspond donc toujours à ce que
le validateur accepte.

### Champs présents dans tous les modèles {#fields-in-every-template}

| Champ | Type | Par défaut | Rôle |
|---|---|---|---|
| `format_version` | nombre entier (min 1, max 1) | `1` | Version du format de modèle. Seule la version `1` existe aujourd’hui. |
| `kind` | l’une de `report`, `tag-policy`, `config` | obligatoire | Ce que le modèle contrôle : `report`, `tag-policy` ou `config`. |
| `name` | nom de modèle | obligatoire | Lettres minuscules, chiffres et traits d’union. Doit correspondre au nom du fichier (`my-report.yaml` a `name: my-report`). |
| `description` | texte | vide | Une phrase affichée par `templates list`. |
| `extends` | nom de modèle ou chemin relatif | non défini | Modèle dont hériter, par nom ou par chemin relatif. Doit être du même type. |
| `spec` | mapping | obligatoire | Les paramètres pour ce type (voir ci-dessous). |

### Modèles de rapport (`kind: report`) {#report-templates-kind-report}

| Champ | Type | Par défaut | Rôle |
|---|---|---|---|
| `spec.title` | texte | `AWS Resource Inventory` | Titre du rapport, utilisé sur la couverture Word et sur la feuille de synthèse Excel. |
| `spec.subtitle` | texte | vide | Ligne facultative sous le titre. |
| `spec.company_name` | texte | vide | Nom de l’organisation affiché sur la couverture et enregistré dans les propriétés du fichier. |
| `spec.colors` | mapping | voir ci-dessous | Couleurs d’en-tête sous forme de valeurs hexadécimales à six chiffres (avec ou sans `#`). |
| `spec.logo` | chemin de fichier relatif | non défini | Image affichée sur la couverture Word (PNG, JPEG, GIF ou BMP). Le chemin est relatif au fichier de modèle et doit rester dans son dossier. |
| `spec.logo_alt_text` | texte | vide | Texte alternatif du logo, lu par les lecteurs d’écran. Par défaut `<company_name> logo`. |
| `spec.columns` | liste de mappings | voir le modèle intégré `standard-bom` | Colonnes des tableaux de ressources, dans l’ordre. |
| `spec.tag_columns` | `all`, `none` ou liste de clés d’étiquettes | `all` | Colonnes supplémentaires, une par clé d’étiquette, ajoutées après `columns`. Soit une liste de clés d’étiquettes, soit `all` pour toutes les clés d’étiquettes trouvées sur les ressources de ce tableau, soit `none`. |
| `spec.tag_policy` | nom de modèle ou chemin relatif | non défini | Politique d’étiquetage à vérifier, par nom ou par chemin relatif. Un `--template` avec une politique d’étiquetage en ligne de commande est prioritaire. |
| `spec.excel` | mapping | voir ci-dessous | Mise en page du classeur Excel. |
| `spec.word` | mapping | voir ci-dessous | Mise en page du document Word. |
| `spec.colors.header_fill` | couleur hexadécimale | `1F3A5F` | Arrière-plan des lignes d’en-tête des tableaux. |
| `spec.colors.header_text` | couleur hexadécimale | `FFFFFF` | Couleur du texte des lignes d’en-tête des tableaux. |
| `spec.columns[].field` | texte | obligatoire | Champ de ressource à afficher. Utilisez des points pour les valeurs imbriquées : `tags.Owner` est l’étiquette `Owner`, `raw_data.InstanceType` est une valeur de la réponse de l’API AWS. |
| `spec.columns[].header` | texte | non défini | Titre de la colonne. Par défaut, le nom du champ en langage courant (`resource_name` devient `Resource name`). |
| `spec.columns[].width` | nombre entier (min 4, max 120) | non défini | Largeur de colonne Excel en caractères. Par défaut, une largeur adaptée au contenu, plafonnée par `excel.max_column_width`. |
| `spec.excel.summary_sheet` | true ou false | `true` | Ajoute une feuille Summary avec le nombre de ressources par service. |
| `spec.excel.layout` | l’une de `per-service`, `single-sheet` | `per-service` | `per-service` place chaque service sur sa propre feuille. `single-sheet` place toutes les ressources sur une seule feuille avec une colonne Service. |
| `spec.excel.single_sheet_name` | texte | `Resources` | Nom de la feuille lorsque `layout` vaut `single-sheet`. |
| `spec.excel.include_all_fields` | true ou false | `false` | Ajoute aussi tous les autres champs trouvés sur les ressources, après les colonnes listées. Utile pour les audits ; produit des feuilles larges. |
| `spec.excel.freeze_header` | true ou false | `true` | Garde la ligne d’en-tête visible pendant le défilement. |
| `spec.excel.autofilter` | true ou false | `true` | Ajoute des boutons de filtre à la ligne d’en-tête. |
| `spec.excel.max_column_width` | nombre entier (min 10, max 120) | `50` | Limite supérieure des largeurs de colonne automatiques, en caractères. |
| `spec.excel.tag_compliance_sheet` | true ou false | `true` | Ajoute une feuille Tag Compliance lorsqu’une politique d’étiquetage est active. |
| `spec.word.orientation` | l’une de `portrait`, `landscape` | `portrait` | Orientation de la page. |
| `spec.word.sections` | liste de valeurs parmi `cover`, `summary`, `service-summary`, `tag-compliance`, `service-tables`, `about` | `["cover", "summary", "service-summary", "tag-compliance", "service-tables", "about"]` | Sections à inclure, dans l’ordre. Choisissez parmi : `cover`, `summary`, `service-summary`, `tag-compliance`, `service-tables`, `about`. `tag-compliance` est ignorée lorsqu’aucune politique d’étiquetage n’est active. |
| `spec.word.columns` | liste de mappings | non défini | Colonnes des tableaux par service. Par défaut, les `max_columns` premières entrées de `columns`. Les colonnes d’étiquettes ne sont pas ajoutées. |
| `spec.word.max_columns` | nombre entier (min 1, max 12) | `6` | Nombre de `columns` à utiliser lorsque `word.columns` n’est pas défini. Les tableaux Word deviennent difficiles à lire au-delà de six ou sept colonnes. |
| `spec.word.max_rows_per_service` | nombre entier (min 1, max 10000) | `50` | Lignes affichées par tableau de service. Une note indique combien ont été omises. |
| `spec.word.max_noncompliant_rows` | nombre entier (min 1, max 10000) | `100` | Lignes affichées dans le tableau des ressources non conformes. |
| `spec.word.columns[].field` | texte | obligatoire | Champ de ressource à afficher. Utilisez des points pour les valeurs imbriquées : `tags.Owner` est l’étiquette `Owner`, `raw_data.InstanceType` est une valeur de la réponse de l’API AWS. |
| `spec.word.columns[].header` | texte | non défini | Titre de la colonne. Par défaut, le nom du champ en langage courant (`resource_name` devient `Resource name`). |
| `spec.word.columns[].width` | nombre entier (min 4, max 120) | non défini | Largeur de colonne Excel en caractères. Par défaut, une largeur adaptée au contenu, plafonnée par `excel.max_column_width`. |

### Modèles de politique d’étiquetage (`kind: tag-policy`) {#tag-policy-templates-kind-tag-policy}

| Champ | Type | Par défaut | Rôle |
|---|---|---|---|
| `spec.required_tags` | liste de mappings | obligatoire | Étiquettes que les ressources concernées doivent avoir. Lorsqu’un modèle `extends` un autre, les entrées sont fusionnées par `key` : la même clé remplace, les nouvelles clés sont ajoutées, et `remove: true` en supprime une. |
| `spec.scope` | mapping | voir ci-dessous | Ressources auxquelles la politique s’applique. Les ressources hors périmètre sont comptées mais non vérifiées. |
| `spec.required_tags[].key` | texte | obligatoire | Clé d’étiquette. Les clés d’étiquettes AWS respectent la casse : `costcenter` ne satisfait donc pas `CostCenter`. |
| `spec.required_tags[].description` | texte | vide | Pourquoi l’étiquette existe. Affichée dans les rapports. |
| `spec.required_tags[].allowed_values` | liste de textes | non défini | Si défini, la valeur de l’étiquette doit être l’une d’elles. |
| `spec.required_tags[].case_sensitive` | true ou false | `false` | Compare `allowed_values` en respectant la casse. |
| `spec.required_tags[].pattern` | expression régulière | non défini | Si défini, toute la valeur de l’étiquette doit correspondre à cette expression régulière (syntaxe Python). |
| `spec.required_tags[].remove` | true ou false | `false` | Dans un modèle qui `extends` un autre, retire cette étiquette de la liste héritée. |
| `spec.scope.services` | liste de textes | `[]` | Ne vérifie que ces services (tels qu’affichés dans le rapport, par exemple `EC2`, `S3`). Vide signifie tous les services. |
| `spec.scope.resource_types` | liste de textes | `[]` | Ne vérifie que ces types de ressources (par exemple `Bucket`, `Instance`). Vide signifie tous les types. |
| `spec.scope.exclude_resource_types` | liste de textes | `[]` | Ne vérifie jamais ces types de ressources, par exemple les types qui ne peuvent pas porter d’étiquettes. |

### Modèles de configuration (`kind: config`) {#config-templates-kind-config}

| Champ | Type | Par défaut | Rôle |
|---|---|---|---|
| `spec.accounts` | liste de mappings | non défini | Comptes à analyser. Omettez-le pour analyser le compte de vos identifiants AWS actuels. Chaque compte nécessite `profile_name` ou `role_arn`. |
| `spec.regions` | liste de textes | non défini | Régions à analyser (`--account-regions`). Omettez-le pour analyser toutes les régions activées. |
| `spec.services` | liste de textes | non défini | Services à inclure (`--account-services`). Actuellement appliqué dans un seul chemin de découverte ; d’autres services peuvent donc encore apparaître. |
| `spec.outputs` | liste de valeurs parmi `excel`, `word` | `["excel"]` | Fichiers à produire (`--create-excel`, `--create-word`). |
| `spec.output_directory` | texte | `bom_output` | Dossier des rapports (`--output-directory`). |
| `spec.report_template` | nom de modèle ou chemin relatif | `standard-bom` | Modèle de rapport à utiliser, par nom ou par chemin relatif. |
| `spec.tag_policy` | nom de modèle ou chemin relatif | non défini | Politique d’étiquetage à vérifier, par nom ou par chemin relatif. |
| `spec.fail_on_tag_violations` | true ou false | `false` | Se termine avec le code 3 après l’écriture des rapports si une ressource concernée enfreint la politique d’étiquetage. Nécessite `tag_policy`. |
| `spec.max_concurrent_accounts` | nombre entier (min 1, max 64) | `4` | Comptes analysés en même temps (`--max-concurrent-accounts`). |
| `spec.account_processing_timeout` | nombre entier (min 60) | `1800` | Secondes allouées par compte (`--account-processing-timeout`). |
| `spec.parallel_processing` | true ou false | `true` | Analyse les comptes en parallèle. `false` équivaut à `--disable-parallel-processing`. |
| `spec.accounts[].account_id` | texte | obligatoire | ID de compte AWS à 12 chiffres, entre guillemets pour que YAML conserve les zéros initiaux. |
| `spec.accounts[].account_name` | texte | vide | Nom convivial utilisé dans les rapports. |
| `spec.accounts[].profile_name` | texte | non défini | Profil AWS CLI à utiliser pour ce compte. |
| `spec.accounts[].role_arn` | texte | non défini | Rôle IAM à assumer dans ce compte, sous forme d’ARN complet. |
| `spec.accounts[].external_id` | texte | non défini | ID externe exigé par la politique de confiance du rôle. |
| `spec.accounts[].regions` | liste de textes | non défini | Régions à analyser dans ce compte. Remplace `spec.regions`. |
| `spec.accounts[].services` | liste de textes | non défini | Services à analyser dans ce compte. |

## Champs de ressource utilisables comme colonnes {#resource-fields-you-can-use-as-columns}

Le `field` d’une colonne lit une valeur sur chaque ressource. Ces champs sont présents sur les
ressources d’une exécution normale :

| Champ | Contenu |
|---|---|
| `service` | Nom du service tel qu’affiché dans le rapport, par exemple `S3`, `EC2`, `VPC` |
| `resource_type` | Par exemple `Bucket`, `Volume`, `Subnet` |
| `resource_name` | Nom, lorsque la ressource en a un |
| `resource_id` | L’ID de la ressource |
| `arn` | Amazon Resource Name, lorsqu’il est connu |
| `region` | Code de la région |
| `source_account_id` | Compte dans lequel la ressource a été trouvée |
| `source_account_name` | Le `account_name` que vous avez donné à ce compte |
| `tags` | Toutes les étiquettes, écrites sous la forme `Key=Value, Key=Value` |
| `tags.<Key>` | La valeur d’une étiquette, par exemple `tags.Owner` |
| `tagged` | `Yes` ou `No` |
| `discovered_via` | L’API qui a trouvé la ressource |
| `source` | D’où vient la ligne : `service-api`, `tagging-api` ou `billing` |
| `sources` | Toutes les sources qui ont signalé la ressource, jointes par `+`, par exemple `service-api+tagging-api` |
| `detail_level` | `full` quand l’API du service a décrit la ressource, `identity` quand seule son identité (ARN et étiquettes) est connue |
| `raw_data.<Name>` | Une valeur de la réponse de l’API AWS, par exemple `raw_data.VolumeType` |

InvenTag remplace par `***REDACTED***` les valeurs des champs qui contiennent
souvent des secrets avant d’écrire un rapport. Par exemple, les valeurs des
variables d’environnement Lambda, les données utilisateur EC2, les valeurs des
paramètres CloudFormation et les mots de passe des connexions Glue. Les noms
restent, vous voyez donc que la variable existe. Un secret placé dans un champ
absent de la liste d’InvenTag, comme une description ou une étiquette, n’est
pas reconnu.

Les valeurs manquantes sont laissées vides. Pour voir tous les champs de vos ressources,
définissez `excel.include_all_fields: true` et regardez les colonnes supplémentaires.

## Messages de validation {#validation-messages}

`inventag templates validate <file>` et chaque exécution avec `--template`
affichent les problèmes sous cette forme :

```text
<file>:<line>: <field>: <what is wrong>
```

Par exemple, un modèle avec `header_fill: blue`, utilisé dans une exécution :

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
$ echo $?
1
```

Et un nom de modèle mal orthographié :

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
$ echo $?
1
```

Lorsqu’un modèle `extends` un autre, les problèmes sont signalés dans le fichier qui les
contient.

## Codes de sortie {#exit-codes}

| Commande | Code | Signification |
|---|---|---|
| `templates validate` | 0 | Tous les fichiers sont valides |
| `templates validate` | 1 | Au moins un fichier pose problème |
| `templates init` | 1 | Le fichier de sortie existe (utilisez `--force`) ou le modèle est invalide |
| `templates init` | 2 | Le nom ou l’extension du fichier de sortie n’est pas autorisé |
| `inventag --template ...` | 1 | Un modèle est invalide, ou l’exécution a échoué |
| `inventag --template ...` | 3 | Les rapports ont été écrits, mais des ressources enfreignent la politique d’étiquetage et `fail_on_tag_violations` vaut `true` |
| `inventag --template ...` | 5 | Les rapports ont été écrits, mais un compte a échoué ou n’a été analysé qu’en partie, et vous avez passé `--fail-on-account-error` |
| `inventag --template ...` | 6 | Aucune ressource n’a été trouvée et vous avez passé `--fail-if-empty` |
