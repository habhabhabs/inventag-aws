---
title: Contrôles FinOps
description: Six contrôles FinOps fixes sur les ressources trouvées par une analyse, sans autre appel AWS, et une lecture facultative des dépenses du mois dernier par service, compte lié et balise de répartition des coûts depuis Cost Explorer.
sidebar_position: 10
---

# Contrôles FinOps

**À qui s’adresse cette page :** vous suivez les dépenses cloud et voulez une
liste de ressources à examiner, faite à partir de l’inventaire que vous avez
déjà.

**Ce que vous saurez faire après la lecture :** exécuter les six contrôles
FinOps, lire la feuille `FinOps` et savoir ce que les contrôles ne peuvent pas
voir.

## Exécuter les contrôles {#run-the-checks}

```bash
inventag --create-excel --finops-checks
```

L’option est désactivée par défaut. Avec elle, InvenTag exécute six contrôles
fixes sur les ressources trouvées par l’analyse et ajoute une feuille nommée
`FinOps` en dernière feuille du rapport Excel.

- Les contrôles lisent uniquement les lignes que l’analyse a déjà. Ils ne font
  aucun autre appel AWS et n’exigent aucune autre permission. La protection en
  lecture seule voit les mêmes appels avec et sans l’option.
- Les contrôles ne changent rien dans un compte.
- Les résultats ne changent pas le code de sortie : une exécution avec des
  résultats `fail` se termine comme sans eux.
- Sans l’option, les contrôles ne s’exécutent pas : le rapport n’a pas de
  feuille `FinOps`, et les autres feuilles et le texte de la console sont les
  mêmes qu’avec l’option.

## Les six contrôles {#the-six-checks}

| Identifiant | Ressources | Résultat `fail` quand |
|---|---|---|
| `FIN-001` | Volumes EBS | le `State` du volume est `available` (non attaché) |
| `FIN-002` | Adresses IP Elastic | l’adresse n’a pas d’`AssociationId` |
| `FIN-003` | Instantanés EBS du compte analysé | le `StartTime` de l’instantané précède de plus de 90 jours le début de l’exécution |
| `FIN-004` | Instances EC2 | l’état de l’instance est `stopped` |
| `FIN-005` | Équilibreurs de charge | aucun groupe cible du même compte et de la même région ne le nomme (feuille `ELBV2`), ou il ne liste aucune instance (équilibreurs de charge classiques, feuille `ELB`) |
| `FIN-006` | Chaque ressource dans la portée de la politique de balises intégrée `finops-cost-allocation` | une clé de cette politique manque : `CostCenter`, `Owner`, `Project` ou `Environment` |

Les 90 jours de `FIN-003` sont fixes ; aucune option ne les change.

`FIN-006` utilise le même contrôle que la politique de balises
`finops-cost-allocation` (voir
[Vérifier les balises avec une politique](check-tag-compliance.md)), mais ne
cherche que les clés manquantes. Une clé dont la valeur n’est pas permise par
la politique n’est pas un résultat de `FIN-006`. Les clés de balise sont
sensibles à la casse : `owner` ne compte pas comme `Owner`. Les lignes qui
viennent uniquement de Cost Explorer (source `billing`) ne sont pas
contrôlées.

## Résultats {#results}

Chaque contrôle donne l’un de trois résultats pour chaque ressource :

- `fail` : le contrôle a observé ce que dit le tableau. La ressource est
  listée.
- `not_evaluated` : les données dont le contrôle a besoin manquent. La
  ressource est listée avec une raison.
- `pass` : la ressource est comptée, pas listée.

Une lacune dans les données n’est jamais un pass. Les raisons sont :

| Raison | Signification |
|---|---|
| `identity_only` | La ressource n’est connue que par l’API Resource Groups Tagging, donc le champ que lit le contrôle n’est pas sur sa ligne. |
| `field_missing` | Le champ que lit le contrôle n’est pas sur la ligne. Pour `FIN-003`, aussi quand l’exécution n’a pas d’heure de début. |
| `tags_not_read` | `FIN-006` uniquement : une clé manque et la liste de l’API Tagging de cette région a échoué pendant cette exécution. Pour une ressource globale, tout échec d’une liste de l’API Tagging du compte compte. |
| `listing_not_read` | Une liste dont le contrôle a besoin a échoué pendant cette exécution. Chaque contrôle qui a besoin de cette liste a une ligne pour elle et sa région : une liste `ec2` en échec donne quatre lignes (`FIN-001`, `FIN-003`, `FIN-004`, `FIN-006`). |

## La feuille FinOps {#the-finops-sheet}

La première ligne de la feuille dit : « These are observations from the
inventory. A resource listed here may be intended. » (ce sont des
observations de l’inventaire ; une ressource listée ici peut être voulue).

Viennent ensuite les résultats listés, avec ces colonnes : `Check ID`,
`Check`, `Result`, `Reason`, `Account`, `Region`, `Service`, `Resource Type`,
`Resource ID`, `Name`, `Observed`. Les lignes sont triées par identifiant de
contrôle, compte, région et identifiant de ressource. `Observed` indique ce
que le contrôle a vu, par exemple « no attachment », « started 2026-05-02 »,
« state stopped » ou « missing: CostCenter, Owner ». Rien d’autre de la
réponse de l’API n’est copié dans la feuille.

Après les résultats listés vient un tableau avec une ligne par contrôle et les
nombres `Fail`, `Not evaluated` et `Pass`.

Un exemple, produit par le générateur de la documentation à partir d’un
compte AWS simulé :

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `FinOps`

`FinOps` sheet:

> These are observations from the inventory. A ...  

| Check ID | Check | Result | Reason | Account | Region | Service | Resource Type | Resource ID | Name | Observed |
|---|---|---|---|---|---|---|---|---|---|---|
| FIN-001 | EBS volume with no attachment | fail |  | 123456789012 | us-east-1 | EC2 | Volume | vol-57d5df4cfc9884b48 | acme-build-cache | no attachment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | global | IAM | Role | acme-orders-api-role |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | VPC | NetworkAcl | acl-3118daa9d5cc099a7 |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | missing: Project |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-inventory-reports | acme-inventory-reports | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-new-bucket | acme-new-bucket | missing: CostCenter, Owner, Project, Environment |

Avec `--per-account-reports`, le rapport de chaque compte ne liste que les
résultats de ce compte.

Avec `--template`, les contrôles ne s’exécutent pas : InvenTag affiche un
avertissement et n’écrit aucune feuille `FinOps`.

## Le résultat `finops_checks` {#the-finops_checks-result}

La ligne de commande écrit les résultats uniquement sous forme de feuille
`FinOps`. En Python, `CloudBOMGenerator.generate_multi_account_bom()` les
renvoie sous la clé `finops_checks`, et un rapport JSON écrit avec le format
de sortie `json` a la même clé dans son `metadata`. La clé contient :

- `schema_version` : `1`.
- `summary` : une entrée par contrôle, avec `policy` (l’identifiant du
  contrôle), `check`, `fail`, `not_evaluated` et `pass`.
- `findings` : les résultats listés, avec `policy`, `result`, `reason`,
  `account`, `region`, `service`, `resource_type`, `resource`, `name` et
  `message` (le texte de `Observed`).

Sans l’option, la clé est absente.

## Répartition des coûts depuis Cost Explorer {#cost-allocation-from-cost-explorer}

`--finops-cost-allocation` est une seconde option, désactivée par défaut et
indépendante de `--finops-checks` et de `--enable-cost-analysis`. Elle lit les
dépenses du mois dernier dans Cost Explorer pour chaque compte, avec les
identifiants propres à ce compte, et ajoute une feuille nommée `FinOps costs`
en dernière feuille du rapport Excel.

```bash
inventag --create-excel --finops-cost-allocation
```

### Requêtes {#requests}

Pour chaque compte, dans cet ordre :

| Requête | Combien |
|---|---|
| `ListCostAllocationTags` pour `CostCenter`, `Owner`, `Project` et `Environment` (les clés de la politique de balises intégrée `finops-cost-allocation`) | 1 |
| `GetCostAndUsage` groupé par service | 1 |
| `GetCostAndUsage` groupé par compte lié | 1 |
| `GetCostAndUsage` groupé par chacune de ces clés qui est active comme balise de répartition des coûts | 0 à 4 |

Cela fait au plus 7 requêtes par compte. Une clé que `ListCostAllocationTags`
montre comme inactive, ou ne liste pas, n’est pas interrogée ; son tableau
indique « not active as a cost allocation tag » ou « not found as a cost
allocation tag ». Si `ListCostAllocationTags` lui-même échoue, les quatre clés
sont interrogées.

Une page supplémentaire d’une réponse (`NextPageToken`) est une requête de
plus. Elle est prise sur les mêmes 7, au plus 3 par regroupement. Un tableau
qui demande plus de pages est marqué « incomplete ».

Avant la découverte, l’exécution affiche une ligne d’avertissement avec le
nombre maximal de requêtes, par exemple : `Cost Explorer: up to 7 request(s) in
this run (billing validation: 0; cost trend: 0; cost allocation: 7). AWS
charges for each.` L’audit de la protection en lecture seule (`--audit-output`)
ne compte jamais plus de requêtes de l’option que ce que dit cette ligne.

Le SDK relance une requête limitée, et chaque relance est une requête de plus.
AWS facture chaque requête Cost Explorer : voir les
[tarifs de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Non vérifié sur un vrai AWS : ce qu’AWS facture pour ces requêtes, relances et
`ListCostAllocationTags` compris.

### La feuille FinOps costs {#the-finops-costs-sheet}

La feuille commence par une note : les montants sont ceux que renvoie Cost
Explorer, pour chaque compte, lus avec les identifiants propres à ce compte,
pour le dernier mois complet, et ce ne sont pas des coûts de ressources
isolées. Vient ensuite une ligne par compte, regroupement et valeur, avec les
colonnes `Account`, `Grouping`, `Value`, `Amount`, `Currency`, `Metric`,
`Period start`, `Period end` et `Status`.

- La période est le mois civil qui précède le mois où l’exécution a commencé.
  `Period end` est le premier jour du mois de l’exécution.
- La métrique est `UnblendedCost`. Les montants sont le texte que renvoie AWS ;
  InvenTag ne les additionne pas, ne les divise pas et ne les arrondit pas.
- Dans un regroupement par balise, la valeur `(no value)` est la dépense sans
  cette clé de balise.
- Un tableau qui n’a pas pu être lu a une ligne avec son état, par exemple
  « not read: access denied ». Les notes de l’exécution le nomment aussi, et
  une requête refusée donne une ligne `Permissions:`. Le résultat de l’analyse
  et le code de sortie restent ceux qu’ils seraient sans l’option.

Avec `--per-account-reports`, le rapport de chaque compte ne contient que les
tableaux de ce compte. Avec `--template`, aucune requête n’est faite : InvenTag
affiche un avertissement et n’écrit aucune feuille `FinOps costs`.

### La clé `finops_costs`, l’instantané et le rapport de changements {#the-finops_costs-key-the-snapshot-and-the-change-report}

- En Python, le résultat de `CloudBOMGenerator.generate_multi_account_bom()` et
  le `metadata` d’un rapport JSON ont la clé `finops_costs` : `schema_version`,
  `metric` et, pour chaque compte, la période, le nombre de requêtes, l’état de
  chaque clé de balise et les tableaux.
- L’instantané d’état reçoit `metadata.tags.cost_allocation` : les tableaux
  seulement (totaux par service, compte lié et valeur de balise ; aucun
  identifiant de ressource). L’instantané reste lisible par son seul
  propriétaire (mode 0600). `--no-cost-in-snapshot` laisse les chiffres hors de
  l’instantané ; la feuille est quand même écrite. Sans
  `--finops-cost-allocation`, cette option ne change rien et un avertissement
  le dit.
- Lu depuis un compte de gestion (payeur), le tableau par compte lié peut
  lister tous les comptes membres de l’organisation avec leurs dépenses, y
  compris des comptes que cette exécution n’a pas analysés, et les tableaux par
  balise contiennent leurs valeurs de balise (par exemple des noms ou des
  adresses e-mail de `Owner`) telles qu’AWS les renvoie. Elles vont dans la
  feuille, l’instantané et le rapport de changements. Utilisez
  `--no-cost-in-snapshot` pour les garder hors de l’instantané. Non vérifié sur
  un vrai AWS : ce que contient la réponse d’un compte payeur.
- Le rapport de changements reçoit un bloc « Cost, previous run to this run »
  quand cette exécution a lu la répartition des coûts. Il montre côte à côte
  chaque valeur de l’exécution précédente et de celle-ci quand les deux
  instantanés contiennent des mois différents. Sinon, une ligne dit pourquoi il
  n’y a pas de comparaison : l’instantané précédent n’a pas de chiffres, les
  deux exécutions ont lu le même mois, ou `--no-cost-in-snapshot` a été donné.

### Ce qu’elle exige et ce qui n’est pas vérifié {#what-it-needs-and-what-is-not-verified}

L’option exige `ce:GetCostAndUsage` et `ce:ListCostAllocationTags`. Les deux
figurent dans la politique du dépôt (voir
[Permissions IAM](../reference/iam-permissions.md)).

Non vérifié sur un vrai AWS :

- Les clés de balise ne montrent des dépenses qu’après leur activation comme
  balises de répartition des coûts dans le compte de facturation (payeur).
- Un compte membre d’une organisation peut voir moins que le compte payeur, et
  `ListCostAllocationTags` peut ne pas répondre depuis un compte membre.
- Que les réponses aient la forme qu’utilisent les tests. Les tests utilisent
  des réponses ayant la forme de celles de Cost Explorer, vérifiées par rapport
  au modèle de service de botocore.

## Ce que les contrôles ne peuvent pas voir {#what-the-checks-cannot-see}

- `FIN-004` ne donne aucune durée. La liste des instances n’a pas d’heure
  d’arrêt fiable, donc une instance arrêtée est listée quelle que soit la
  durée de l’arrêt.
- `FIN-005` ne lit pas l’état de santé des cibles. Un équilibreur de charge
  dont toutes les cibles sont en mauvaise santé donne un pass. Lire l’état de
  santé des cibles demanderait un nouvel appel AWS.
- Une ressource listée ici peut être voulue : par exemple une instance arrêtée
  exprès ou un instantané gardé par une règle de rétention.
- Les contrôles ne montrent aucun montant d’argent.
- Non vérifié sur un vrai AWS : que les listes portent les champs dont chaque
  contrôle a besoin, pour tous les types de compte.
