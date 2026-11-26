---
title: Fichiers de sortie
description: Chaque fichier qu’InvenTag écrit (rapports Excel et Word, JSON de conformité, instantanés, journaux des changements), avec noms, emplacements et contenus.
sidebar_position: 4
---

# Fichiers de sortie

**À qui s’adresse cette page :** vous traitez la sortie d’InvenTag dans des scripts, ou vous
expliquez les rapports à d’autres personnes.

**Ce que vous saurez après lecture :** le nom, l’emplacement et le contenu de chaque
fichier qu’InvenTag écrit.

Tout est placé dans le dossier de sortie : `bom_output/`, sauf si vous définissez
`--output-directory` ou `output_directory` dans un modèle de configuration. Les seuls
autres endroits où InvenTag écrit sont les fichiers que vous nommez (`--log-file`,
`--audit-output`, `templates init --output`), votre bucket S3 avec `--s3-bucket` et,
avec les options Google, votre Google Drive et, avec `--google-oauth-client`, un fichier
de jeton de connexion dans `~/.config/inventag/google-token.json`.

Les fichiers de sortie sont créés avec un accès en lecture et en écriture réservé à votre
utilisateur, et les nouveaux dossiers de sortie lui sont également privés.

Non vérifié sur Windows : fichiers et dossiers privés pour votre utilisateur.

Les exemples de cette page proviennent d’exécutions hors ligne sur un AWS simulé (données
d’exemple).

## Liste des fichiers {#file-list}

| Fichier | Quand | Contenu |
|---|---|---|
| `multi_account_bom_<timestamp>.xlsx` | `--create-excel`, ou aucune option de sortie | Le rapport Excel |
| `multi_account_bom_<timestamp>.docx` | `--create-word` | Le rapport Word |
| `multi_account_bom_<timestamp>.html` | `--create-html` | Le rapport HTML. Voir [Rapport HTML](#html-report). |
| `<account-id>_bom_<timestamp>.xlsx`, `.docx` et `.html` | `--per-account-reports`, à la place des fichiers `multi_account_bom_*` | Un rapport pour chaque compte qui a des ressources |
| `tag_compliance_<timestamp>.json` | Une politique d’étiquetage est active | Résultats de la vérification des étiquettes |
| `state/state_<timestamp>.json` | Chaque exécution, sauf avec `--disable-state-management` | Instantané de chaque ressource trouvée, avec les valeurs secrètes masquées. `metadata.tags.coverage_summary` compte, par compte, comment les appels de listage se sont terminés (`ok`, `empty`, `denied`, `throttled`, `error`, `timeout`, et `out_of_scope` pour les services que `--account-services` a laissés de côté). `metadata.tags.units_not_read` liste les listages qui n’ont pas été lus (seulement quand l’un a échoué), et `metadata.tags.inventag_version` nomme la version d’InvenTag qui a écrit l’instantané. Les instantanés de plus de 30 jours, ou au-delà des 100 plus récents, sont supprimés (`--state-retention-days`, `--state-max-snapshots`). |
| `state/metadata.json` | Avec les instantanés | Index des instantanés : heure, compte, régions, nombre de ressources, somme de contrôle |
| `policy_findings_<timestamp>.json` | `--policy` (la valeur par défaut de `--policy-format`), `--finops-checks` avec `--template`, ou `inventag policy check --format json` | Le résultat de la vérification de politiques sur un instantané. Voir [Constats des politiques](#policy-findings). |
| `policy_findings_<timestamp>.sarif`, `.xml` et `.md` | `--policy-format sarif`, `junit` ou `markdown`, ou les mêmes mots dans `--format` de `inventag policy check` | Le même résultat en SARIF 2.1.0, JUnit XML et Markdown. `junit` écrit `.xml` et `markdown` écrit `.md`. |
| `changelog_<timestamp>.md` | Deuxième exécution et suivantes, sauf avec `--no-generate-changelog` ou `--disable-delta-detection` | Ce qui a été ajouté, supprimé ou modifié depuis l’instantané précédent. Voir [Suivre les changements](../guides/track-changes.md). |
| Le fichier que vous nommez avec `--audit-output` | Quand vous le demandez | Chaque opération AWS appelée pendant l’exécution |
| `state/partial/<key>/<account-id>.json` | Une exécution où certains comptes ont échoué | Résultats des comptes terminés, réutilisés par `--resume` et supprimés après une exécution complète |

`<timestamp>` s’écrit `YYYYMMDD_HHMMSS`. Les noms du rapport, du fichier Word, du journal des modifications et du fichier de conformité des étiquettes utilisent l’heure locale de votre ordinateur. L’instantané et le dossier S3 utilisent UTC. Le `<timestamp>` d’un fichier `policy_findings_` est l’heure enregistrée dans l’instantané vérifié (UTC), pas l’horloge de la vérification.

Le classeur par défaut a une colonne `raw_data.*` pour chaque champ de l’API, donc ses feuilles peuvent être larges. Un instantané est du JSON indenté et contient tout le `raw_data` de chaque ressource, donc il peut être volumineux. Aucune option n’omet les colonnes `raw_data.*` ni ne compresse un instantané ; les deux sont prévues pour une version ultérieure.

## Rapport Excel {#excel-report}

**Sans modèle**, le classeur contient :

- **Summary :** Service, Resource Count, Percentage, et un total.
- **Une feuille par service** (par exemple `EC2`, `S3`, `VPC`), triées par nom de
  service, avec chaque champ trouvé sur ses ressources, y compris les colonnes aplaties
  `raw_data.*` et `tags.*`. Un champ d’API qui est un dictionnaire indexé par des ID
  tient dans une seule cellule JSON. Les lignes sont triées par type, nom et ID.
  Chaque ligne a une colonne `source` (`service-api`, `tagging-api` ou `billing` :
  l’API qui l’a renvoyée), une colonne `sources` (toutes, jointes par `+`) et une
  colonne `detail_level` (`full` pour les lignes venant de l’API du service lui-même,
  `identity` pour les autres).
- Des feuilles **Network Analysis** et **Security Analysis**, uniquement avec
  `--enable-network-analysis` ou `--enable-security-analysis`.
- Une feuille **Cost Analysis**, uniquement avec `--enable-cost-analysis` : coûts
  mensuels estimés à partir de l’API AWS Pricing, pas votre facture, et un tableau
  du coût facturé par compte et par service, issu de Cost Explorer. Voir
  [Feuille Cost Analysis](#cost-analysis-sheet).
- Une feuille **FinOps**, la dernière, uniquement avec `--finops-checks` : voir
  [Feuille FinOps et clé `finops_checks`](#finops-sheet-and-the-finops_checks-key).

Les valeurs des champs qui contiennent souvent des secrets, comme les variables
d’environnement Lambda, les sorties de piles CloudFormation, les arguments des
déclencheurs Glue, les chaînes de connexion et les URL signées, apparaissent sous la forme `***REDACTED***` dans chaque
rapport, instantané et journal. Les noms des champs restent. Voir
[État des fonctionnalités](../getting-started/status.md#what-inventag-finds-and-what-it-does-not).

**Avec un modèle de rapport**, la mise en page suit le modèle :

- **Summary :** titre, heure de génération, nombre de comptes et de régions, un
  tableau Service / Resources / Share et, avec une politique d’étiquetage, les compteurs
  de conformité.
- **Feuilles de ressources :** une par service, ou une seule feuille avec `layout:
  single-sheet`. Les lignes d’en-tête sont mises en forme, figées et filtrables par défaut.
- **Tag Compliance** (avec une politique d’étiquetage) : une ligne par ressource dans le périmètre, puis
  un tableau de règles avec les nombres d’étiquettes manquantes et non valides.

Les noms de feuilles respectent les règles d’Excel : 31 caractères au plus, sans
`[ ] : * ? / \`. Les noms en double reçoivent un numéro. Les valeurs de cellule qui commencent par `=`
sont stockées comme du texte, jamais comme des formules. Les lignes sont triées par service, type,
nom et ID.

Des aperçus de chaque mise en page, réalisés à partir de vrais fichiers, se trouvent dans
[Modèles intégrés](../templates/catalogue.md).

## Feuille FinOps et clé `finops_checks` {#finops-sheet-and-the-finops_checks-key}

Avec `--finops-checks`, le classeur par défaut se termine par une feuille
`FinOps`. Sa première ligne est une note ; viennent ensuite les résultats
listés, avec les colonnes `Check ID`, `Check`, `Result`, `Reason`, `Account`,
`Region`, `Service`, `Resource Type`, `Resource ID`, `Name` et `Observed`,
triés par identifiant de contrôle, compte, région et identifiant de ressource.
Un tableau des nombres par contrôle (`Fail`, `Not evaluated`, `Pass`) suit.
Avec `--template`, aucune feuille `FinOps` n’est écrite.

La ligne de commande n’écrit aucun fichier JSON pour ces résultats. En Python,
le résultat de `CloudBOMGenerator.generate_multi_account_bom()` a la clé
`finops_checks`, tout comme le `metadata` d’un rapport JSON écrit avec le
format de sortie `json`. Sans l’option, la clé est absente. Les champs sont
décrits dans [Contrôles FinOps](../guides/finops-checks.md#the-finops_checks-result).

## Feuille FinOps costs et clé `finops_costs` {#finops-costs-sheet-and-the-finops_costs-key}

Avec `--finops-cost-allocation`, le classeur par défaut se termine par une
feuille `FinOps costs` (après la feuille `FinOps` quand les deux options sont
actives) : une note, puis une ligne par compte, regroupement et valeur, avec
les colonnes `Account`, `Grouping`, `Value`, `Amount`, `Currency`, `Metric`,
`Period start`, `Period end` et `Status`. Le résultat de
`CloudBOMGenerator.generate_multi_account_bom()` et le `metadata` d’un rapport
JSON ont la clé `finops_costs` ; l’instantané a `metadata.tags.cost_allocation`
(tableaux seulement, sauf avec `--no-cost-in-snapshot`). Voir
[Contrôles FinOps](../guides/finops-checks.md#cost-allocation-from-cost-explorer).
## Feuille Cost Analysis {#cost-analysis-sheet}

Avec `--enable-cost-analysis`, le classeur par défaut a une feuille `Cost Analysis`. Sa première ligne dit que les chiffres sont des estimations de l’API AWS Pricing et non votre facture. Les tableaux se suivent dans cet ordre : `Summary`, le coût mensuel estimé par service, les ressources les plus chères (les 50 premières), la tendance des coûts, les ressources peut-être oubliées et les recommandations. Tout tableau après `Summary` est omis quand il n’a aucune ligne.

Le tableau de tendance des coûts a pour titre « Billed cost by account and service, last two full months (Cost Explorer; a service total, not a resource's cost) ». Il a une ligne par compte et par service, issue de la facture Cost Explorer propre à ce compte, avec les colonnes :

| Colonne | Contenu |
|---|---|
| `Account` | L’ID de compte des ressources |
| `Service` | Le service tel que le rapport le nomme, par exemple `EC2` ou `S3` |
| `Resources` | Combien de ressources de ce service le compte a dans le rapport |
| `Earlier month` | Le plus ancien des deux mois complets avant l’exécution, sous la forme `YYYY-MM` |
| `Billed (USD)` (première) | Ce que Cost Explorer a facturé pour le service ce mois-là |
| `Later month` | Le mois le plus récent, sous la forme `YYYY-MM` |
| `Billed (USD)` (seconde) | Ce que Cost Explorer a facturé pour le service le mois le plus récent |
| `Change %` | La variation du mois précédent au mois le plus récent, arrondie à une décimale. Depuis une facture nulle, elle vaut 100 si le mois le plus récent est facturé, sinon 0 |
| `Direction` | `increasing` ou `decreasing`, ou `stable` quand la variation est inférieure à 5 pour cent dans un sens comme dans l’autre |
| `Billing names counted` | Les noms de service Cost Explorer additionnés dans cette ligne, séparés par des virgules |

Les colonnes de montants montrent l’unité renvoyée par Cost Explorer : `Billed (USD)` quand toutes les lignes ont la même unité, sinon `Billed (unit as returned)`, et chaque cellule se termine alors par son unité. Une ligne est un total du service dans le compte, pas le coût d’une ressource, et il n’est pas réparti entre les ressources. Le chiffre d’un service est la somme des noms de facturation indiqués dans sa ligne. `EC2 - Other` (volumes, passerelles NAT, transfert de données) est un nom de facturation distinct et n’est pas dans la ligne d’EC2 ; `Amazon EC2 Container Registry (ECR)` non plus. Un compte dont la requête de tendance a été refusée ou a échoué, ou qui n’a pas de session, n’a aucune ligne, et l’exécution le dit dans un avertissement. Les mois sont les deux mois complets avant l’exécution.

En Python, les mêmes lignes sont `cost_analysis["cost_trends"]` du résultat de `CloudBOMGenerator.generate_multi_account_bom()`. Chaque entrée a `account_id`, `service`, `billing_names`, `resource_count`, `previous_month`, `current_month`, `previous_monthly_cost`, `current_monthly_cost`, `cost_change_percentage`, `trend_direction`, `alert_triggered` et `unit`. Avant la v1.5.0, aucune feuille ne montrait la tendance ; chaque entrée de `cost_trends` nommait une ressource (`resource_id`) et contenait le total du service divisé par le nombre de ses ressources. Ces entrées n’existent plus : le code qui lit `resource_id` dans `cost_trends` doit lire une entrée par compte et par service. Voir [Contrôles FinOps](../guides/finops-checks.md#the-cost-trend-of---enable-cost-analysis).

Non vérifié sur un vrai AWS : les factures qu’un compte réel renvoie, y compris ce que voient un compte de gestion (payeur) et un compte membre.

## Constats des politiques {#policy-findings}

`inventag policy check`, `--policy` et `--finops-checks` avec `--template` écrivent le résultat de la vérification de politiques sur un instantané d’état dans des fichiers nommés `policy_findings_<timestamp>.<extension>` dans le répertoire de sortie (le dossier de `--output-directory` pour `inventag policy check`) :

| Extension | Format | Écrit pour |
|---|---|---|
| `.json` | Le résultat complet | `json` |
| `.sarif` | SARIF 2.1.0, pour les outils d’analyse de code | `sarif` |
| `.xml` | JUnit XML, un cas de test par politique | `junit` |
| `.md` | Tableaux Markdown, 50 lignes au plus par politique | `markdown` |

Une analyse écrit `.json` sauf si `--policy-format` dit autre chose. `inventag policy check` affiche du texte à l’écran et n’écrit aucun fichier sauf si `--format` en nomme un ; il n’écrit rien quand il se termine avec le code 1 ou 2. Sous Linux et macOS, seul leur propriétaire peut lire et écrire les fichiers (mode 0600), qu’ils viennent d’une analyse ou de `inventag policy check` ; un dossier qu’InvenTag crée pour eux a le mode 0700, et un dossier existant garde son mode.

Le fichier JSON a ces clés de premier niveau : `schema_version`, `inventag_version`, `now`, `snapshot`, `baseline`, `policies`, `summary`, `findings`, `not_evaluated_units`, `not_evaluated_policies` et `unused_waivers`. Les clés sont triées et le fichier se termine par un saut de ligne. Il ne contient ni nom d’hôte, ni nom d’utilisateur, ni chemin absolu, ni heure d’horloge : le même instantané et les mêmes politiques donnent les mêmes octets. Un JSON Schema pour ce fichier est fourni avec InvenTag (`inventag/policy/outputs/schemas/policy-findings-1.json`) ; son `$id` est le nom `urn:inventag:schema:policy-findings:1`, pas une adresse web.

- `findings` liste chaque ligne dont le résultat est `fail`, `waived` ou `not_evaluated`. Un `pass` et une ligne qu’une politique ne sélectionne pas (`out_of_scope`) sont comptés dans `summary` et dans le `counts` de chaque politique, sans être listés.
- Un constat `not_evaluated` a un `reason` : `identity_only`, `field_missing`, `tags_not_read`, `listing_not_read`, `not_comparable`, `not_convertible` ou `value_too_long`. Un trou dans les données n’est jamais une réussite.
- `not_evaluated_units` liste les listages de l’analyse qui n’ont pas été lus et dont une politique aurait eu besoin. `unused_waivers` liste les dérogations qui ne correspondaient à rien, avec `why` : `no match`, `expired`, `unknown policy` ou `superseded`.
- `summary.exit_code` vaut 0, 7 ou 8 avec `inventag policy check`. Lors d’une analyse, c’est le code de sortie de l’analyse : 0, 3, 4, 5, 6 ou 7 (5, 6, 3 et 4 passent avant 7), et la dernière ligne du texte dit la même chose.
- La valeur d’un champ de ressource n’est affichée qu’avec `--show-values`, et une valeur masquée reste masquée. SARIF et JUnit ne portent jamais de valeur.

Dans les formes texte et Markdown, la dernière ligne dit ce que signifie le code de sortie, par exemple `Exit code 7: at least one finding failed at severity high or higher.` Sans seuil, elle dit `Exit code 0: findings are reported; no threshold was set.` Voir [Codes de sortie](./cli.md#exit-codes).

Lors d’une analyse avec `--policy`, la dernière ligne donne le code de sortie de l’analyse : 7 quand un constat a échoué à la gravité de `--policy-fail-on` ou au-dessus (une analyse ne sort jamais avec 8 ; seul `inventag policy check` donne 8). 3, 4, 5 et 6 gardent leur sens et l’emportent quand ils s’appliquent ; la ligne est alors l’une de celles-ci :

- `Exit code 3: the template's tag policy found violations (fail_on_tag_violations); this code comes before the policy check's code.`
- `Exit code 4: a security group rule is at or above --risk-threshold; this code comes before the policy check's code.`
- `Exit code 5: an account could not be scanned (--fail-on-account-error); this code comes before the policy check's code.`
- `Exit code 6: no resources were found (--fail-if-empty); this code comes before the policy check's code.`

Non vérifié : comment GitHub code scanning affiche le fichier SARIF, ou comment GitLab affiche le fichier JUnit. Les tests comparent les fichiers à des fichiers de référence (golden), et le fichier SARIF à un schéma court fourni avec InvenTag, pas au schéma SARIF complet.

## Rapport Word {#word-report}

**Sans modèle :** un titre, une synthèse, un tableau des services, et
jusqu’à 50 ressources par service sur six colonnes : Name, Id, Type, Region, Tags et Service. Si aucune ressource du service n’a de nom, les colonnes sont Id, Type, Region, Tags, Service et Source Account Name.

**Avec un modèle de rapport :** les sections listées dans `word.sections`. Les tableaux
ont une ligne d’en-tête qui se répète sur chaque page et qui est signalée comme en-tête aux
lecteurs d’écran. Le logo, s’il y en a un, porte un texte alternatif.

## Rapport HTML {#html-report}

`--create-html` écrit le rapport sous la forme d’un seul fichier HTML
statique, `multi_account_bom_<timestamp>.html`, dans le dossier de sortie,
avec la même racine de nom que les fichiers Excel et Word de l’exécution. Avec
`--per-account-reports`, chaque compte a son propre
`<account-id>_bom_<timestamp>.html`. Ouvrez le fichier dans un navigateur web.

```bash
inventag --create-excel --create-html
```

- `--create-html` seule écrit uniquement le fichier HTML. Avec
  `--create-excel` ou `--create-word`, le fichier HTML est écrit en plus de ces
  rapports.
- Une exécution sans `--create-html` n’écrit aucun fichier HTML et ne change
  pas.
- Quand l’exécution ne trouve aucune ressource, aucun fichier HTML n’est
  écrit, comme pour les rapports Excel et Word.
- Avec `--s3-bucket`, le fichier HTML est envoyé avec les autres rapports.
  InvenTag l’envoie avec le type de contenu `text/html; charset=utf-8` ; les
  autres rapports sont envoyés comme avant, sans type de contenu. Non vérifié
  sur un vrai AWS : qu’un navigateur ouvre l’objet depuis S3 comme une page
  web.

**Ce que contient le fichier**, dans cet ordre :

- **Résumé :** les ressources par service (avec un total), les ressources par
  région et les notes de l’exécution.
- **Ressources par service :** une section fermée pour chaque service. Ouvrez
  une section pour voir son tableau. Chaque tableau a les mêmes colonnes et
  lignes que la feuille du service dans le rapport Excel par défaut, avec les
  valeurs secrètes masquées en `***REDACTED***` de la même façon.
- **Conformité des étiquettes :** le résumé d’une politique d’étiquetage,
  seulement quand l’exécution en a vérifié une (par exemple avec un modèle de
  politique d’étiquetage).
- **Analyse réseau** et **analyse de sécurité :** le tableau des VPC et le
  tableau des groupes de sécurité, seulement avec `--enable-network-analysis`
  ou `--enable-security-analysis`.
- **FinOps** et **FinOps costs :** les mêmes tableaux que les feuilles Excel,
  seulement avec `--finops-checks` ou `--finops-cost-allocation`.
- **Couverture et erreurs :** les comptes, la façon dont les appels de liste
  se sont terminés dans chaque compte (`ok`, `empty`, `denied` et les autres
  résultats), et les autorisations refusées. La colonne `Read in part` du
  tableau des comptes vaut `Yes` quand le compte s’est arrêté avant la fin de
  son analyse ou qu’une de ses listes n’a pas été lue : les mêmes comptes que
  nomme une note d’exécution « Not read in account ».

Le fichier ne contient pas les tableaux Cost Analysis de
`--enable-cost-analysis` ni les constats de `--policy` (ils sont dans
`policy_findings_<timestamp>.json`). Il n’a ni tri, ni filtre, ni graphique.

**Avec un modèle de rapport :** avec `--template`, le fichier HTML a la mise
en page décrite ci-dessus ; les sections du modèle s’appliquent seulement aux
rapports Excel et Word, et l’exécution affiche un avertissement qui le dit.
Avec `--word-template` ou `--excel-template`, le fichier HTML utilise le titre
du document, le nom de l’entreprise et le logo de ce modèle (le modèle Word
d’abord). Le logo doit être un fichier PNG ou JPEG ; il est intégré au
fichier. `--excel-template` avec `--create-html` seule s’arrête avec le code
de sortie 2, car aucun rapport Excel n’est écrit.

**Sécurité du fichier :**

- Chaque valeur de vos comptes (noms, étiquettes, paramètres) est échappée :
  un balisage dans une valeur d’étiquette s’affiche comme du texte et ne
  s’exécute jamais. Les caractères de direction du texte et de contrôle sont
  supprimés : une valeur ne peut pas s’afficher inversée ni réordonnée.
- Le fichier n’a pas de JavaScript et ne charge rien hors du fichier : aucun
  script, feuille de style, police ni image d’un autre site. Ses seuls liens
  mènent à des sections du même fichier. Sa seule image est le logo du modèle,
  intégré comme URI `data:`.
- Le fichier porte cette Content-Security-Policy, qui demande au navigateur de
  ne rien charger d’autre :
  `default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'`.
- Le fichier est écrit en entier ou pas du tout, et seul votre utilisateur
  peut le lire et l’écrire, comme les autres rapports.
- À cause de cette option, l’exécution n’écrit dans le journal aucune valeur
  de vos ressources.

:::warning Gardez le fichier HTML privé

Le fichier HTML contient des données de vos comptes AWS : noms de ressources,
ID, étiquettes et paramètres. Traitez-le comme le rapport Excel. Ne le
publiez pas sur un site web et ne le partagez pas plus largement que le
fichier Excel.

:::

Le fichier a des styles d’impression : ils masquent la table des matières et
demandent au navigateur de ne pas couper une ligne de tableau entre deux
pages. Non vérifié dans un navigateur : l’aspect et l’impression du fichier,
et si une section fermée s’imprime ouverte.

Les exemples ci-dessous viennent d’une exécution hors ligne sur un AWS simulé
(données d’exemple).

```html title="multi_account_bom_20261112_090000.html (first lines)"
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; style-src &#x27;unsafe-inline&#x27;; img-src data:; base-uri &#x27;none&#x27;; form-action &#x27;none&#x27;">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AWS Resource Inventory - BOM Report</title>
```

```text title="multi_account_bom_20261112_090000.html (outline)"
AWS Resource Inventory - BOM Report
  Contents
  Summary
      table: Resources by service
      table: Resources by region
  Resources by service
    ATHENA (1) (closed section)
      table: ATHENA resources
    DYNAMODB (1) (closed section)
      table: DYNAMODB resources
    EC2 (4) (closed section)
      table: EC2 resources
    EVENTS (1) (closed section)
      table: EVENTS resources
    IAM (1) (closed section)
      table: IAM resources
    KMS (14) (closed section)
      table: KMS resources
    LAMBDA (1) (closed section)
      table: LAMBDA resources
    S3 (6) (closed section)
      table: S3 resources
    VPC (10) (closed section)
      table: VPC resources
  Coverage and errors
      table: Accounts
      table: Listings by outcome
```

## JSON de conformité des étiquettes {#tag-compliance-json}

```json title="tag_compliance_20261112_090000.json (one resource shown)"
{
  "policy": "finops-cost-allocation",
  "description": "Requires CostCenter, Owner, Project and Environment so spend can be allocated.",
  "summary": {
    "checked": 23,
    "compliant": 1,
    "non_compliant": 22,
    "out_of_scope": 14,
    "percent_compliant": 4.3,
    "missing_by_key": {
      "CostCenter": 20,
      "Owner": 17,
      "Project": 21,
      "Environment": 17
    },
    "invalid_by_key": {
      "CostCenter": 1,
      "Owner": 0,
      "Project": 0,
      "Environment": 1
    }
  },
  "non_compliant_resources": [
    {
      "account": "123456789012",
      "service": "S3",
      "resource_type": "Bucket",
      "resource_id": "acme-reports",
      "arn": "arn:aws:s3:::acme-reports",
      "region": "us-east-1",
      "missing": [],
      "invalid": [
        "CostCenter: '1234' does not match CC-[0-9]{4}",
        "Environment: 'Production' is not one of prod, staging, dev, test, sandbox"
      ]
    }
  ]
}
```

## Instantanés {#snapshots}

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

```json title="state/state_<timestamp>.json (structure)"
{
  "top_level_keys": [
    "compliance_data",
    "metadata",
    "network_analysis",
    "resources",
    "security_analysis"
  ],
  "one_resource": {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "acme-app-logs",
    "arn": "arn:aws:s3:::acme-app-logs",
    "region": "us-east-1",
    "tags": {
      "Environment": "prod",
      "Owner": "platform",
      "CostCenter": "CC-1001",
      "Project": "storefront",
      "DataClassification": "internal"
    },
    "source_account_id": "123456789012"
  }
}
```

## JSON d’audit {#audit-json}

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 93,
  "allowed_calls": 93,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## Objets S3 {#s3-objects}

Avec `--s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/`, chaque exécution
place ses fichiers dans un dossier portant le nom de l’exécution :

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090000.xlsx
```

## Sortie du terminal {#terminal-output}

Sans `--verbose`, une exécution affiche les avertissements, les erreurs et les fichiers écrits. Avec
un modèle, chaque fichier est affiché sous la forme `Wrote <path>`, suivi d’un résumé d’une ligne de la
politique d’étiquetage lorsqu’une politique est active. Sans modèle, le rapport par défaut est affiché sous la forme `Data exported to <path>`, et avec `--create-html` le fichier HTML a sa propre ligne `Data exported to <path>`. Avec `--policy`, le résumé des politiques est toujours affiché ; la ligne `Policy findings: <path>` est journalisée au niveau INFO et n’apparaît qu’avec `--verbose`. Sans aucune option, `inventag` affiche la page d’aide et se termine avec le code 2.

## Codes de sortie {#exit-codes}

Voir [Référence de la ligne de commande](./cli.md#exit-codes).
