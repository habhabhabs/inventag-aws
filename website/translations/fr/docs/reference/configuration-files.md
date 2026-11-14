---
title: Fichiers de configuration
description: Les formats de fichiers qu’InvenTag lit (comptes, correspondances d’étiquettes, descriptions de services) et les champs que les chargeurs acceptent réellement.
sidebar_position: 2
slug: /user-guides/configuration-examples
---

# Fichiers de configuration

**À qui s’adresse cette page :** vous écrivez ou vérifiez à la main les fichiers de configuration d’InvenTag.

**Ce que vous saurez faire après lecture :** écrire un fichier de comptes, un fichier de
correspondances d’étiquettes et un fichier de descriptions de services que les chargeurs acceptent.

Pour les modèles (mises en page de rapport, politiques d’étiquetage, paramètres d’exécution), voir la
[Référence des modèles](../templates/reference.md). Un modèle de configuration peut faire
tout ce que fait un fichier de comptes, sauf contenir des clés d’accès, et il est
validé plus strictement ; préférez-le donc pour les nouvelles installations.

Tous les fichiers peuvent être en YAML (`.yaml`, `.yml`) ou en JSON (`.json`). Vérifiez-les sans
lancer d’analyse :

```bash
inventag --accounts-file accounts.yaml --tag-mappings tags.yaml \
  --validate-config-only --skip-credential-validation
```

Cette commande lit les fichiers et n’effectue aucun appel à AWS.

InvenTag lit ces fichiers en UTF-8, avec ou sans marque d’ordre des octets. Un
fichier vide, une clé écrite deux fois ou un niveau supérieur qui n’est pas un
dictionnaire arrêtent l’exécution avec le code de sortie 1 et un message qui nomme le fichier.

## Fichier de comptes {#accounts-file}

Utilisé avec `--accounts-file`.

```yaml
accounts:
  - account_id: "123456789012"         # required, in quotes
    account_name: Production           # optional, shown in reports
    role_arn: arn:aws:iam::123456789012:role/InvenTagReadOnly
    external_id: optional-external-id  # only if the trust policy needs it
    regions: [us-east-1, eu-west-1]    # optional; empty = every enabled region
    services: []                       # optional; empty = all services
  - account_id: "210987654321"
    account_name: Development
    profile_name: dev-readonly         # an AWS CLI profile instead of a role
settings:                              # optional
  max_concurrent_accounts: 4
  account_processing_timeout: 1800     # seconds, at least 60
  output_directory: bom_output
```

Un compte peut indiquer une façon d’obtenir des identifiants. Un compte qui n’en indique aucune utilise vos identifiants actuels s’ils appartiennent à ce compte ; sinon, InvenTag essaie d’assumer dans ce compte le rôle `InvenTagCrossAccountRole` (ou le nom donné avec `--cross-account-role`).

| Champ | Utilisation |
|---|---|
| `profile_name` | Un profil AWS CLI, par exemple un profil IAM Identity Center. |
| `role_arn` | Un rôle qu’InvenTag assume à partir de vos identifiants actuels. |
| `access_key_id` et `secret_access_key` (et `session_token` en option) | Des clés écrites dans le fichier. À éviter : toute personne qui peut lire le fichier possède les clés. InvenTag avertit quand d’autres utilisateurs peuvent lire un tel fichier. |

Les valeurs de `settings` remplacent les options de ligne de commande correspondantes.

Pour utiliser le même nom de rôle dans chaque compte, omettez `role_arn` et ajoutez
`--cross-account-role InvenTagReadOnly` à la commande.

Un fichier de comptes incorrect arrête l’exécution avant l’analyse. Par exemple, un ID de compte
sans guillemets (données d’exemple) :

```text title="Sortie"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
1
```

Des exemples prêts à l’emploi se trouvent dans le dossier
[`examples/`](https://github.com/habhabhabs/inventag-aws/tree/main/examples)
du dépôt, par exemple `accounts_cross_account_roles.json` et
`accounts_with_profiles.json`.

## Correspondances d’étiquettes {#tag-mappings}

Utilisé avec `--tag-mappings`. Chaque entrée ajoute une colonne nommée au rapport.
La colonne affiche la valeur de l’étiquette, ou la valeur par défaut si la ressource ne
porte pas l’étiquette.

```yaml
tag_mappings:
  - tag: CostCenter          # required: the tag key
    name: Cost Center        # required: the column name
    default_value: Unknown   # optional: shown when the tag is missing
    description: Budget that pays for the resource
    required: false
    case_sensitive: false
```

La colonne apparaît dans le classeur par défaut (sans `--template`). Avec
`--template`, elle n’apparaît pas, et un avertissement le signale : utilisez plutôt `tag_columns` dans le modèle de
rapport. Avec un fichier de mise en page (`--excel-template`, `--word-template`), ajoutez le
nom de la colonne à `extra_fields`.

Utilisez la clé de premier niveau `tag_mappings` avec une **liste** d’entrées. InvenTag accepte aussi
l’ancienne disposition, qui utilise chaque clé d’étiquette comme clé de premier niveau avec une
valeur `column_name`.

## Descriptions de services {#service-descriptions}

Utilisé avec `--service-descriptions`. Ajoute la colonne `service_description`
au rapport. Sans fichier, InvenTag écrit une description intégrée, par
exemple `Amazon EC2 Instance (i-0abc1234def567890) in us-east-1`.

```yaml
service_descriptions:
  DYNAMODB:
    default:
      description: Application data table
  EC2:
    Volume:
      description: Block storage
      template: volume_text       # optional: a text with variables
templates:
  volume_text:
    template: "Disk {resource_id} in {region}"
```

La clé de premier niveau `service_descriptions` est obligatoire. Sous chaque service,
chaque type de ressource (ou `default`) a besoin d’une `description`. InvenTag ne vérifie pas cela quand vous validez ou lancez une exécution. Un fichier sans cette clé est ignoré, avec une erreur dans le journal, et les descriptions intégrées sont utilisées.

**Votre entrée remplace la description intégrée**, pour tous les services. Une
entrée avec un `template` utilise ce modèle, défini sous `templates` ; une entrée
sans modèle utilise sa `description` telle quelle (dans l’exemple,
`Application data table` pour les tables DynamoDB). Un modèle peut utiliser
`{resource_id}`, `{resource_type}`, `{service}`, `{region}` et `{account_id}`.
Les services sans entrée dans votre fichier gardent le texte intégré.

Si un modèle ne peut pas être rempli, InvenTag consigne un avertissement tel que
`Failed to render template vpc_vpc: 'cidr_block'` et utilise le texte de repli intégré. Pour un modèle de votre propre fichier, il utilise la `description` de cette entrée.

## Configuration de traitement de la nomenclature {#bom-processing-configuration}

Utilisé avec `--bom-config`. Un mappage YAML ou JSON dont les clés sont des champs de la
configuration de traitement de la nomenclature (BOM), par exemple :

```yaml
enable_network_analysis: false
enable_parallel_processing: true
max_worker_threads: 4
```

Les clés inconnues sont ignorées avec un avertissement qui les nomme ; vérifiez donc le journal
pour repérer une clé mal orthographiée. Une valeur du mauvais type arrête l’exécution avec le
code de sortie 1 et nomme la clé.
Par exemple, `enable_network_analysis: true` ajoute la même feuille que
`--enable-network-analysis`. Ce fichier sert au réglage avancé ; la plupart des gens n’en
ont jamais besoin.

## Étapes suivantes {#next-steps}

- [Référence des modèles](../templates/reference.md)
- [Analyser plusieurs comptes](../guides/scan-multiple-accounts.md)
