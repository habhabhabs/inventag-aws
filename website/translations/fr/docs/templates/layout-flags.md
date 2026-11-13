---
title: Fichiers de mise en page pour un rapport
description: Modifiez le titre, les sections, les feuilles, les colonnes, l’en-tête et le pied de page des rapports BOM Word et Excel avec un fichier de modèle YAML ou JSON.
sidebar_position: 5
---

# Fichiers de mise en page pour un rapport

Cette page décrit les options `--word-template` et `--excel-template`. Chaque option
prend un fichier de mise en page pour un format de rapport. Pour les modèles nommés que vous
sélectionnez avec `--template`, voir [Modèles](./index.md).

Un modèle de rapport est un fichier YAML ou JSON. Le modèle contrôle la structure
du rapport Word ou du rapport Excel. Donnez le fichier à la CLI avec
`--word-template` ou `--excel-template`.

Si vous ne donnez aucun modèle, InvenTag utilise le modèle par défaut intégré. Le rapport
a alors la même structure que dans les versions sans modèles.

## Ce qu’un modèle peut changer {#what-a-template-can-change}

| Élément | Rapport Word | Rapport Excel |
|---|---|---|
| Titre et sous-titre | Section de titre du document | Propriétés du classeur, et lignes facultatives au-dessus du tableau de synthèse |
| Nom de l’entreprise | Valeur de `{{ company_name }}` | Valeur de `{{ company_name }}`, et propriété de créateur du classeur |
| Logo | Fichier PNG ou JPEG au-dessus du titre | Non disponible |
| Sections ou feuilles | Quelles sections apparaissent, et leur ordre | Quelles feuilles apparaissent, et leur ordre |
| Colonnes | Quelles colonnes apparaissent, leur ordre, leur titre et leur largeur | Quelles colonnes apparaissent, leur ordre, leur titre et leur largeur |
| Services | Quels services apparaissent dans les tableaux de ressources, et leur ordre | Quels services ont une feuille, et leur ordre |
| En-tête et pied de page | En-tête de page, pied de page, numéro de page | En-tête d’impression et pied de page d’impression de chaque feuille |
| Couleur de la ligne d’en-tête | Non disponible | Couleur de remplissage de la ligne d’en-tête |
| Texte libre | Titres et paragraphes avec variables | Non disponible |

## Créer un modèle {#make-a-template}

1. Écrivez le modèle par défaut dans un fichier.

   ```bash
   inventag --print-default-template word > my_word_template.yaml
   inventag --print-default-template excel > my_excel_template.json
   ```

2. Modifiez le fichier. Voir la [référence des clés](#key-reference).

3. Validez le fichier. Cette commande ne fait aucun appel AWS.

   ```bash
   inventag --validate-templates \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

   Si les fichiers sont valides, la CLI affiche une ligne `OK` par fichier et
   s’arrête avec le code de sortie `0`.

4. Utilisez le fichier dans une exécution.

   ```bash
   inventag --create-word --create-excel \
     --word-template my_word_template.yaml \
     --excel-template my_excel_template.json
   ```

La CLI accepte les extensions de nom de fichier `.yaml`, `.yml` et `.json` pour les
deux formats. Les fichiers de modèle par défaut se trouvent aussi dans le dépôt :
`templates/default_word_template.yaml` et
`templates/default_excel_template.json`.

## Options de modèle {#template-flags}

| Option | Fonction |
|---|---|
| `--word-template PATH` | Modèle du rapport Word. Cette option nécessite `--create-word`. |
| `--excel-template PATH` | Modèle du rapport Excel. Cette option nécessite `--create-excel`. Sans elle, la CLI s’arrête avec le code de sortie `2`. |
| `--print-default-template word` ou `--print-default-template excel` | Affiche le modèle par défaut et s’arrête avec le code de sortie `0`. |
| `--validate-templates` | Valide les fichiers de `--word-template` et `--excel-template`, puis s’arrête. Aucun appel AWS. |

## Exemples minimaux {#minimal-examples}

Ce modèle Word donne un titre, un tableau de ressources par service et un
tableau de synthèse.

```yaml title="my_word_template.yaml"
template_version: "2.0"
format_type: word
document:
  title: "{{ company_name }} Cloud Inventory"
  subtitle: "Accounts: {{ account_ids }}"
branding:
  company_name: Example Corp
header_footer:
  header_text: "{{ company_name }} - Internal"
  footer_text: "Generated {{ generated_date }}"
  include_page_numbers: true
sections:
  - id: title
    content_type: title
  - id: inventory
    content_type: resources
    title: Resources
    service_title: "{{ service }} ({{ service_resource_count }})"
    columns:
      - field: name
        heading: Resource name
        width: 2.5
      - field: region
      - field: tags.Owner
        heading: Owner
  - id: summary
    content_type: service_summary
    title: "Summary of {{ total_resources }} resources"
```

Ce modèle Excel donne une feuille avec toutes les ressources, puis la feuille de
synthèse.

```json title="my_excel_template.json"
{
  "template_version": "2.0",
  "format_type": "excel",
  "document": {"title": "{{ company_name }} inventory"},
  "branding": {"company_name": "Example Corp", "header_color": "1F4E78"},
  "sections": [
    {
      "id": "all_resources",
      "content_type": "resources",
      "group_by_service": false,
      "sheet_name": "All resources",
      "columns": [
        {"field": "service", "heading": "Service", "width": 14},
        {"field": "name", "heading": "Name"},
        {"field": "region", "heading": "Region"},
        {"field": "tags.Owner", "heading": "Owner"}
      ]
    },
    {
      "id": "summary",
      "content_type": "service_summary",
      "sheet_name": "Summary",
      "show_title": true
    }
  ]
}
```

## Variables {#variables}

Écrivez une variable sous la forme `{{ name }}` dans une valeur de texte. InvenTag remplace la
variable par sa valeur lorsqu’il écrit le rapport.

| Variable | Valeur |
|---|---|
| `{{ company_name }}` | La valeur de `branding.company_name`. |
| `{{ document_title }}` | La valeur de `document.title` après substitution. |
| `{{ document_subtitle }}` | La valeur de `document.subtitle` après substitution. |
| `{{ generated_at }}` | Heure de génération en UTC, au format `YYYY-MM-DD HH:MM:SS`. |
| `{{ generated_date }}` | Date de génération en UTC, au format `YYYY-MM-DD`. |
| `{{ account_ids }}` | Les ID de compte du rapport, triés, séparés par une virgule et une espace. |
| `{{ account_count }}` | Le nombre d’ID de compte différents dans le rapport. |
| `{{ total_resources }}` | Le nombre de ressources dans le rapport. |
| `{{ service_count }}` | Le nombre de services différents dans le rapport. |
| `{{ region_count }}` | Le nombre de régions différentes dans le rapport. |

Ces variables ne sont valides que dans `service_title` et `truncation_note` d’une section
Word `resources` :

| Variable | Valeur |
|---|---|
| `{{ service }}` | Le nom du service du tableau en cours. |
| `{{ service_resource_count }}` | Le nombre de ressources du service en cours. |
| `{{ shown_resource_count }}` | Le nombre de lignes du tableau en cours. |

Vous pouvez définir vos propres variables sous `variables` :

```yaml
variables:
  classification: Internal
header_footer:
  footer_text: "Classification: {{ classification }}"
```

Règles pour les variables :

- Un nom de variable ne contient que des lettres, des chiffres et des tirets bas.
- Le nom de votre propre variable commence par une lettre minuscule et ne contient que des
  lettres minuscules, des chiffres et des tirets bas.
- Vous ne pouvez pas utiliser le nom d’une variable intégrée pour votre propre variable.
- La valeur d’une variable est du texte brut. Une valeur ne peut pas contenir une autre variable.
- `document.title` et `document.subtitle` ne peuvent pas utiliser `{{ document_title }}`
  ni `{{ document_subtitle }}`.
- Ces clés acceptent des variables : `document.title`, `document.subtitle`,
  `header_footer.header_text`, `header_footer.footer_text`, et les clés de section
  `title`, `paragraphs`, `service_title` et `truncation_note`.
- Les titres de colonnes, les noms de feuilles et `branding.company_name` n’acceptent pas
  de variables.
- InvenTag ne prend en charge ni les expressions, ni les filtres, ni les conditions, ni les
  boucles, ni l’inclusion de fichiers. Par exemple, `{{ company_name | upper }}` est une erreur.
- InvenTag ne remplace pas les variables dans les données des ressources. Un nom de ressource
  contenant le texte `{{ company_name }}` reste inchangé dans le rapport.

## Référence des clés {#key-reference}

Un test dans `tests/unit/test_template_system.py` vérifie que cette référence
contient chaque clé du schéma de `inventag/reporting/report_template.py`.

### Clés de premier niveau {#top-level-keys}

| Clé | Type | Formats | Par défaut | Description |
|---|---|---|---|---|
| `template_version` | chaîne | Word et Excel | Obligatoire | Version du schéma. Doit être `"2.0"`. |
| `format_type` | chaîne | Word et Excel | Obligatoire | `word` ou `excel`. |
| `name` | chaîne | Word et Excel | Vide | Un nom pour le modèle. Non affiché dans le rapport. |
| `description` | chaîne | Word et Excel | Vide | Une description. Non affichée dans le rapport. |
| `document` | mapping | Word et Excel | Voir ci-dessous | Titre et sous-titre. |
| `branding` | mapping | Word et Excel | Voir ci-dessous | Nom de l’entreprise, logo et couleur. |
| `variables` | mapping | Word et Excel | Vide | Vos propres variables : nom vers texte. |
| `extra_fields` | liste | Word et Excel | Vide | Noms de champs de ressource supplémentaires que `columns` peut utiliser. Par exemple, une colonne issue de vos correspondances d’étiquettes. |
| `header_footer` | mapping | Word et Excel | Voir ci-dessous | Texte de l’en-tête et du pied de page. |
| `sections` | liste | Word et Excel | Obligatoire | Les sections (Word) ou les feuilles (Excel), dans l’ordre du rapport. |

### `document` {#document}

| Clé | Type | Formats | Par défaut | Description |
|---|---|---|---|---|
| `title` | chaîne | Word et Excel | Vide | Word : le texte de la section `title`. Excel : la propriété de titre du classeur. |
| `subtitle` | chaîne | Word et Excel | Vide | Word : une ligne sous le titre. Excel : la propriété d’objet du classeur. |

### `branding` {#branding}

| Clé | Type | Formats | Par défaut | Description |
|---|---|---|---|---|
| `company_name` | chaîne | Word et Excel | Vide | La valeur de `{{ company_name }}`. Excel : aussi la propriété de créateur du classeur. |
| `logo_path` | chaîne | Word | Aucun | Fichier PNG ou JPEG affiché au-dessus du titre. Le chemin est relatif au fichier de modèle et doit rester dans son répertoire. |
| `logo_width_inches` | nombre | Word | `1.5` | Largeur du logo, de 0,25 à 7. |
| `header_color` | chaîne | Excel | `366092` | Couleur de remplissage de la ligne d’en-tête, six chiffres hexadécimaux. |

### `header_footer` {#header_footer}

| Clé | Type | Formats | Par défaut | Description |
|---|---|---|---|---|
| `header_text` | chaîne | Word et Excel | Vide | Word : en-tête de page. Excel : en-tête d’impression de chaque feuille. 255 caractères au maximum. |
| `footer_text` | chaîne | Word et Excel | Vide | Word : pied de page. Excel : pied de page d’impression de chaque feuille. 255 caractères au maximum. |
| `include_page_numbers` | booléen | Word | `false` | Ajoute `Page <number>` au pied de page. |

L’en-tête et le pied de page d’impression Excel ne s’affichent que dans la vue Mise en page et
sur papier.

### `sections` {#sections}

Chaque entrée de `sections` est un mapping. La clé `content_type` sélectionne ce que la
section affiche.

| `content_type` | Formats | Fonction |
|---|---|---|
| `title` | Word | Le titre du document, le sous-titre et le logo. |
| `text` | Word | Un titre facultatif et une liste de paragraphes. |
| `service_summary` | Word et Excel | Une ligne par service : nom, nombre de ressources, pourcentage. Un tableau dans Word, une feuille dans Excel. |
| `resources` | Word et Excel | Les tableaux de ressources. Word : un tableau par service. Excel : une feuille par service, ou une feuille pour toutes les ressources. |
| `network_analysis` | Excel | La feuille d’analyse réseau. InvenTag ne l’écrit que si des données d’analyse réseau existent. |
| `security_analysis` | Excel | La feuille d’analyse de sécurité. InvenTag ne l’écrit que si des données d’analyse de sécurité existent. |
| `cost_analysis` | Excel | La feuille d’analyse des coûts. InvenTag ne l’écrit que si des données d’analyse des coûts existent (--enable-cost-analysis). |

Clés de section :

| Clé | Type | Formats | Types de section | Par défaut | Description |
|---|---|---|---|---|---|
| `id` | chaîne | Word et Excel | Tous | Obligatoire | Nom unique de la section : lettres minuscules, chiffres et tirets bas. |
| `content_type` | chaîne | Word et Excel | Tous | Obligatoire | Ce que la section affiche. |
| `enabled` | booléen | Word et Excel | Tous | `true` | Définissez `false` pour omettre la section. |
| `title` | chaîne | Word | `text`, `service_summary`, `resources` | Vide | Texte du titre de la section. |
| `level` | entier | Word | `text`, `service_summary`, `resources` | `1` | Niveau de titre, de 1 à 3. Les titres de service utilisent le niveau suivant. |
| `page_break_before` | booléen | Word | Tous | `false` | Commence la section sur une nouvelle page. |
| `paragraphs` | liste | Word | `text` | Liste vide | Les paragraphes d’une section `text`. |
| `columns` | `auto` ou liste | Word et Excel | `service_summary`, `resources` | `auto` | `auto`, ou une liste de colonnes. Voir [Colonnes](#columns). |
| `table_style` | chaîne | Word | `service_summary`, `resources` | `Light Grid Accent 1` pour `service_summary`, `Light List Accent 1` pour `resources` | Style de tableau Word. |
| `services` | liste | Word et Excel | `resources` | Tous les services | Affiche uniquement ces services, dans cet ordre. La comparaison ignore la casse, les espaces et les préfixes `Amazon` et `AWS`. |
| `service_title` | chaîne | Word | `resources` | `{{ service }} Resources ({{ service_resource_count }})` | Titre de chaque tableau de service. |
| `max_rows` | entier | Word | `resources` | `50` | Nombre maximal de lignes dans chaque tableau de service, de 1 à 100000. |
| `max_columns` | entier | Word | `resources` | `6` | Nombre maximal de colonnes si `columns` vaut `auto`, de 1 à 100. |
| `truncation_note` | chaîne | Word | `resources` | `Note: Showing first {{ shown_resource_count }} of {{ service_resource_count }} {{ service }} resources.` | Paragraphe sous un tableau qui n’affiche pas toutes les ressources. InvenTag ajoute un second paragraphe qui indique combien de ressources ne sont pas listées et que le rapport Excel les liste toutes. |
| `page_break_after_service` | booléen | Word | `resources` | `true` | Commence une nouvelle page après chaque tableau de service. |
| `sheet_name` | chaîne | Excel | `service_summary`, `resources` | `Summary` pour `service_summary` | Nom de la feuille, de 1 à 31 caractères. Obligatoire pour une section `resources` avec `group_by_service: false`. |
| `group_by_service` | booléen | Excel | `resources` | `true` | `true` : une feuille par service. `false` : une feuille pour toutes les ressources. |
| `show_title` | booléen | Excel | `service_summary` | `false` | Écrit le titre et le sous-titre du document au-dessus du tableau. |

Remarques :

- Un document Word affiche les sections dans l’ordre de la liste.
- Un classeur affiche les feuilles dans l’ordre de la liste.
- Avec `group_by_service: true`, chaque feuille porte le nom de son service. Si
  Excel n’accepte pas un nom, InvenTag le modifie : les caractères interdits par
  Excel deviennent `-`, un nom de plus de 31 caractères est coupé et `History`
  devient `History (2)`. Le journal nomme chaque feuille modifiée.
- Une section Word `resources` trie les services par nom, sauf si vous donnez
  `services`.
- Les valeurs valides pour `table_style` sont les styles de tableau du document Word par
  défaut. Par exemple `Table Grid`, `Light List Accent 1`,
  `Light Grid Accent 1` et `Medium Shading 1 Accent 1`.

### Colonnes {#columns}

La clé `columns` vaut `auto` ou une liste. Chaque entrée de la liste est un nom de champ, ou
un mapping avec ces clés :

| Clé | Type | Formats | Par défaut | Description |
|---|---|---|---|---|
| `field` | chaîne | Word et Excel | Obligatoire | Le champ à afficher. |
| `heading` | chaîne | Word et Excel | Voir ci-dessous | Le titre de la colonne. |
| `width` | nombre | Word et Excel | Automatique | Largeur de la colonne. Word : pouces, de 0,2 à 10. Excel : caractères, de 1 à 255. |

Titres par défaut :

- Word : le nom du champ avec des espaces et des majuscules. Par exemple,
  `source_account_id` devient `Source Account Id`.
- Excel : le nom du champ.

Fonction de `auto` :

- Section Word `resources` : au maximum `max_columns` champs par
  service. Les premiers champs sont `name`, `id`, `type`, `region`,
  `compliance_status` et `tags`, si le service les possède.
- Section Excel `resources` : tous les champs des ressources de la feuille.
- Section `service_summary` : `service`, `resource_count` et `percentage`.

Champs d’une section `service_summary` : `service`, `resource_count`,
`percentage`.

Champs d’une section `resources` :

| Groupe | Champs |
|---|---|
| Identité | `service`, `type`, `id`, `name`, `arn` |
| Compte et emplacement | `account_id`, `source_account_id`, `source_account_name`, `account_name`, `region`, `availability_zone` |
| Détails de la ressource | `status`, `state`, `creation_date`, `created_time`, `launch_time`, `size`, `instance_type`, `storage_type`, `engine`, `engine_version`, `allocated_storage`, `storage_encrypted`, `multi_az`, `publicly_accessible`, `vpc_id`, `vpc_name`, `subnet_id`, `subnet_name`, `security_groups`, `security_group_ids` |
| Réseau | `vpc_cidr_block`, `vpc_total_ips`, `vpc_utilization_percentage`, `subnet_cidr_block`, `subnet_total_ips`, `subnet_utilization_percentage`, `subnet_is_public`, `subnet_availability_zone` |
| Sécurité | `security_risk_level`, `security_group_count`, `max_security_risk`, `inbound_rules_count`, `outbound_rules_count`, `associated_resources_count`, `has_permissive_rules`, `permissive_rules` |
| Coûts | `estimated_monthly_cost`, `cost_breakdown`, `pricing_model`, `confidence_level`, `cost_optimization_opportunities`, `monthly_spend`, `service_monthly_spend`, `billing_validated` |
| Découverte et conformité | `compliance_status`, `compliance_score`, `discovery_timestamp`, `consolidation_timestamp`, `total_accounts_in_consolidation`, `discovered_at`, `discovered_via`, `priority`, `tagged`, `tags`, `service_description`, `resource_id`, `resource_name`, `resource_type` |
| Une étiquette | `tags.<key>`, par exemple `tags.Owner` |
| Un attribut brut de l’API | `raw_data.<key>`, par exemple `raw_data.InstanceType` |
| Vos propres champs | Chaque nom de `extra_fields`. Les champs de provenance `source`, `sources` et `detail_level` ne figurent pas dans les listes ci-dessus ; ajoutez-les sous `extra_fields` pour les utiliser comme colonnes. |

Si une ressource n’a pas un champ, la cellule est vide. Le champ `tags` affiche toutes les
étiquettes d’une ressource dans une seule cellule.

## Erreurs de validation {#validation-errors}

La CLI valide chaque modèle avant le premier appel AWS. Si un modèle n’est pas valide, la CLI
affiche une ligne par problème sur la sortie d’erreur standard et s’arrête avec le code de
sortie `1`. Chaque ligne a ce format :

```text
inventag: error: <file>: <key path>: <reason>
```

Exemple :

```text
inventag: error: my_word_template.yaml: colour: unknown key. Allowed keys: template_version, format_type, name, description, document, branding, variables, extra_fields, header_footer, sections
inventag: error: my_word_template.yaml: sections[1].columns[2].field: unknown column 'owner_name'. Use a known field (for example service, type, id, name, region, account_id, tags), a tags.<key> field, or add the name to extra_fields
```

| Problème | Début du motif |
|---|---|
| Une clé que le schéma n’a pas | `unknown key. Allowed keys: ...` |
| Une clé de l’autre format de rapport | `this key is not valid in a Word template` ou `this key is not valid in an Excel template` |
| Une valeur du mauvais type | `must be a string, but the value is integer` |
| Une clé obligatoire est absente | `missing key` |
| Un type de section qui n’existe pas | `unknown section type 'cover_page' for a Word template. Allowed values: ...` |
| Une colonne qui n’existe pas | `unknown column 'owner_name'` |
| Une variable qui n’existe pas | `unknown variable 'owner'. Allowed variables: ...` |
| Une expression, un filtre ou des accolades imbriquées | `malformed placeholder` |
| Deux sections avec le même `id` | `duplicate id 'summary'` |
| Un modèle du mauvais format | `the file is a template for Excel reports, but this flag needs a template for Word reports` |
| Un ancien modèle avec `template_version: "1.0"` | `unsupported version '1.0'` |
| Un chemin de logo qui sort du répertoire du modèle | `the path must stay in the directory of the template file` |
| Un fichier qui n’est ni YAML ni JSON | `YAML syntax error at line ...` ou `JSON syntax error at line ...` |
| Une clé écrite deux fois dans le même mappage | `duplicate key 'name'` |
| Un fichier avec une autre extension | `unsupported file type` |
| Un fichier trop volumineux | `The maximum is 262144 bytes` |

Codes de sortie des options de modèle :

| Code de sortie | Condition |
|---|---|
| `0` | `--validate-templates` n’a trouvé aucun problème, ou `--print-default-template` a affiché le modèle. |
| `1` | Un fichier de modèle n’est pas valide. |
| `2` | Erreur d’utilisation. Par exemple, `--word-template` sans `--create-word`, ou `--validate-templates` sans option de modèle. |

## Limites {#limits}

| Élément | Limite |
|---|---|
| Taille du fichier de modèle | 262144 octets (256 Kio) |
| Valeur de texte | 2000 caractères |
| Texte d’en-tête et texte de pied de page | 255 caractères |
| Sections | 50 |
| Colonnes dans une section | 100 |
| Paragraphes dans une section `text` | 100 |
| Vos propres variables | 50 |
| Entrées dans `extra_fields` | 200 |
| Taille du fichier de logo | 5242880 octets (5 Mio) |
| Types de fichier de logo | `.png`, `.jpg`, `.jpeg` |
| Nom de feuille Excel | 31 caractères, sans `[ ] : * ? / \` |

Autres limites :

- Un modèle ne peut pas changer les polices, les couleurs de titre ni la taille de page du
  rapport Word.
- Un modèle ne peut pas changer les colonnes de la feuille d’analyse réseau ni de la feuille
  d’analyse de sécurité.
- Un modèle ne peut pas ajouter de table des matières, de graphiques ni de logo dans le
  rapport Excel.
- Un style de tableau Word doit être un style du document Word par défaut.
- Les scripts hérités de `scripts/legacy/` n’ont pas les options de modèle.
- Les clés de configuration `templates`, `document_templates` et
  `default_template` dans d’anciens exemples de configuration n’ont aucun effet. Seules
  `--word-template` et `--excel-template` sélectionnent un modèle.
- Les fichiers de modèle avec `template_version: "1.0"` ne sont pas valides. Les alpha builds
  antérieures à v1.0.0 fournissaient de tels fichiers, mais la CLI ne les lisait pas.

## Sécurité des fichiers de modèle {#safety-of-template-files}

- InvenTag lit le YAML avec `yaml.safe_load`. Un fichier YAML ne peut pas exécuter de code.
- InvenTag n’évalue pas d’expressions. La substitution ne remplace que les noms des tableaux de
  [variables](#variables).
- InvenTag ne remplace pas les variables dans les données de ressources venant d’AWS.
- Un modèle ne peut pas inclure un autre fichier. La seule référence de fichier est
  `branding.logo_path`, et ce fichier doit se trouver dans le répertoire du modèle.
- InvenTag remplace par `***REDACTED***` les valeurs des champs qui contiennent
  souvent des secrets, comme les variables d’environnement Lambda, les données
  utilisateur EC2 et les valeurs de paramètres CloudFormation, avant d’écrire un
  rapport. Un secret dans un champ de texte libre n’est pas reconnu.
- Le générateur Excel stocke chaque valeur comme du texte. Une valeur qui commence par `=`
  ne s’exécute pas comme une formule.
