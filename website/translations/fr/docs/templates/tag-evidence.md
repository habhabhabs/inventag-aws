---
title: Modèles de preuve par les étiquettes
description: Ce que vérifient les cinq modèles de preuve (SOC 2, HIPAA, PCI DSS, RGPD, PDPA), ce qu’ils n’affirment jamais, les étiquettes et valeurs utilisées, et comment en copier un et changer son périmètre.
sidebar_position: 6
---

# Modèles de preuve par les étiquettes

**À qui s’adresse cette page :** vous préparez une discussion sur SOC 2, HIPAA, PCI DSS, le RGPD ou la PDPA et vous voulez savoir quelles ressources n’ont aucune réponse enregistrée aux questions par lesquelles cette discussion commence.

**Ce que vous saurez faire après lecture :** choisir le modèle de votre référentiel, lire correctement ses résultats et le copier pour l’adapter à vos propres étiquettes et types de ressource.

## Ce qu’ils vérifient {#what-they-check}

Chaque modèle est une politique d’étiquetage. Il vérifie que chaque ressource du périmètre porte les étiquettes que le modèle liste, avec une valeur de la liste autorisée ou de la forme autorisée. C’est tout. Les étiquettes sont la preuve : une trace, écrite par le propriétaire de la ressource, du périmètre, du type de données, de la conservation ou de l’emplacement.

Les cinq modèles figurent dans le [catalogue intégré](./catalogue.md#tag-evidence-templates). L’ensemble est `evidence-soc2`, `evidence-hipaa`, `evidence-pci-dss`, `evidence-gdpr` et `evidence-pdpa`.

## Ce qu’ils n’affirment jamais {#what-they-never-claim}

- Ils vérifient uniquement les preuves par les étiquettes. Ils n’évaluent ni les contrôles, ni les mesures de protection, ni la segmentation, ni la licéité, ni le consentement.
- Les valeurs des étiquettes sont déclarées par le propriétaire de la ressource. InvenTag ne peut pas les vérifier.
- Un résultat positif ne signifie pas que le compte satisfait SOC 2, HIPAA, PCI DSS, le RGPD ou la PDPA. Il signifie que les étiquettes sont là.
- InvenTag est en lecture seule. Il lit les étiquettes et écrit des rapports ; il ne modifie jamais une ressource.

Chaque modèle le dit dans sa description et dans l’en-tête de son fichier. Conservez la phrase « Checks tag evidence only; certifies nothing. » dans la description de tout modèle que vous copiez.

## Les étiquettes {#the-tags}

Les cinq vérifient aussi les trois étiquettes de `security-baseline` : `Owner` (n’importe quelle valeur), `Environment` (`prod`, `staging`, `dev`, `test`, `sandbox`) et `DataClassification` (`public`, `internal`, `confidential`, `restricted`). `evidence-hipaa` remplace la dernière règle et ajoute `phi`.

| Modèle | Clé d’étiquette | Valeurs autorisées |
|---|---|---|
| `evidence-soc2` | `Soc2Scope` | `in-scope`, `out-of-scope` |
|  | `SystemName` | N’importe quel texte non vide |
|  | `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual`, `other` |
|  | `Criticality` | `high`, `medium`, `low` |
| `evidence-hipaa` | `PHI` | `yes`, `no` |
|  | `DataClassification` | `public`, `internal`, `confidential`, `restricted`, `phi` |
|  | `RetentionPeriod` | Un nombre et `d` ou `y`, ou `indefinite` |
| `evidence-pci-dss` | `PciScope` | `cde`, `connected`, `out-of-scope` |
|  | `CardholderData` | `stores`, `processes`, `transmits`, `none` (une seule valeur) |
| `evidence-gdpr` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `ProcessingRecord` | De 1 à 64 lettres, chiffres, `.`, `_` ou `-` |
|  | `DataResidency` | `eu`, `uk`, `other` |
|  | `RetentionPeriod` | Un nombre et `d` ou `y`, ou `indefinite` |
| `evidence-pdpa` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `Purpose` | N’importe quel texte non vide |
|  | `RetentionPeriod` | Un nombre et `d` ou `y`, ou `indefinite` |
|  | `DataLocation` | `sg`, `overseas` |

`evidence-gdpr` et `evidence-pdpa` utilisent la même clé `PersonalData` et les mêmes valeurs. Si vous étiquetez une ressource pour l’un, l’étiquette sert déjà pour l’autre. Une exécution utilise un seul modèle ; lancez donc le contrôle deux fois pour voir les deux.

Une valeur d’étiquette peut contenir des lettres, des chiffres, des espaces et `_ . : / = + - @`. Toutes les valeurs ci-dessus conviennent.

## Copier un modèle et changer son périmètre {#copy-a-template-and-change-its-scope}

`evidence-soc2` regarde tous les types de ressource sauf les alias KMS. Les quatre autres listent les types de ressource qu’ils regardent. La liste appartient à tout le modèle : elle limite donc aussi les contrôles de `Owner`, `Environment` et `DataClassification`. Les ressources des autres types comptent comme hors périmètre, pas comme des échecs.

Pour voir exactement ce qu’un modèle vérifie, affichez-le après héritage :

```bash title="Terminal"
inventag templates show evidence-hipaa --resolved
```

Pour créer votre propre copie qui hérite de tout :

```bash title="Terminal"
inventag templates init evidence-soc2 --output .inventag/templates/our-soc2.yaml --extend
```

Pour vérifier moins de services, définissez `services` dans votre copie :

```yaml title=".inventag/templates/data-soc2.yaml"
format_version: 1
kind: tag-policy
name: data-soc2
description: SOC 2 tag evidence for data stores only. Checks tag evidence only; certifies nothing.
extends: evidence-soc2
spec:
  scope:
    services: [S3, DYNAMODB, SQS]
```

Pour vérifier plus de types de ressource, copiez la liste complète `resource_types` depuis `inventag templates show <name> --resolved` et ajoutez le type. Une liste dans votre copie remplace la liste héritée ; elle ne s’y ajoute pas. Utilisez la valeur de la colonne Type de votre rapport pour le nouveau type.

Validez la copie avant de l’utiliser, puis lancez-la :

```bash title="Terminal"
inventag templates validate data-soc2
inventag --template data-soc2 --create-excel
```

## Ce que le moteur ne peut pas exprimer {#what-the-engine-cannot-express}

- Un seul modèle de politique d’étiquetage par exécution.
- Pas de règle « seulement si ». Une ressource étiquetée `PersonalData=none` a quand même besoin d’une étiquette `ProcessingRecord`, avec la valeur `none`.
- Pas de recoupement entre étiquettes ni avec la région de la ressource. `PHI=no` avec `DataClassification=phi` n’est pas signalé, pas plus que `DataResidency=eu` sur une ressource d’une autre région.
- Les motifs respectent la casse : `7y` passe et `7Y` ne passe pas. Les listes de valeurs autorisées ignorent la casse.
- Le motif de `ProcessingRecord` ne vérifie que la forme de l’ID. Adaptez-le à votre propre format d’ID dans votre copie.

## Étapes suivantes {#next-steps}

- [Exemple : vérifier les preuves par les étiquettes avant une discussion sur le périmètre SOC 2](../examples/evidence-soc2.md)
- [Adapter un modèle](./adapt-a-template.md)
- [Vérifier les étiquettes selon une politique](../guides/check-tag-compliance.md)
