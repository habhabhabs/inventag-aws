---
title: Contrôles FinOps
description: Six contrôles FinOps fixes sur les ressources trouvées par une analyse (volumes non attachés, adresses non associées, anciens instantanés, instances arrêtées, équilibreurs de charge sans cible, balises de répartition des coûts manquantes), sans autre appel AWS.
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
- L’option ne change pas le code de sortie.
- Une exécution sans l’option écrit le même rapport qu’avant.

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
| `field_missing` | Le champ que lit le contrôle n’est pas sur la ligne. |
| `tags_not_read` | `FIN-006` uniquement : une clé manque et la liste de l’API Tagging de cette région a échoué pendant cette exécution. Pour une ressource globale, tout échec d’une liste de l’API Tagging du compte compte. |
| `units_not_read` | Une liste dont le contrôle a besoin a échoué pendant cette exécution. La feuille a une ligne par liste et par région. |

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
