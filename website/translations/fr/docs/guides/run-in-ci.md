---
title: Exécuter InvenTag en CI/CD
description: Exécutez InvenTag selon un calendrier dans GitHub Actions avec des identifiants OIDC de courte durée, gardez les rapports et faites échouer le job si besoin.
sidebar_position: 7
---

# Exécuter InvenTag en CI/CD

**À qui s’adresse cette page :** vous voulez un inventaire selon un calendrier, ou un pipeline qui
échoue lorsque des ressources ne sont pas correctement étiquetées.

**Ce que vous saurez faire après lecture :** mettre en place un workflow GitHub Actions qui exécute
InvenTag avec des identifiants de courte durée et conserve les rapports.

## Les éléments {#the-pieces}

1. **Des identifiants sans clés stockées.** Utilisez OpenID Connect (OIDC) : GitHub
   prouve l’identité du workflow, et AWS lui accorde une session de rôle temporaire. Aucune
   clé d’accès ne se trouve dans les secrets de votre dépôt.
2. **Un modèle de configuration** avec vos régions, vos sorties et votre politique d’étiquetage. Le modèle
   intégré `ci-pipeline` est un bon point de départ.
3. **Un artefact** pour conserver `bom_output/`.

## 1. Laisser GitHub assumer un rôle en lecture seule {#1-let-github-assume-a-read-only-role}

Dans AWS, ajoutez GitHub comme fournisseur d’identité OIDC
(`token.actions.githubusercontent.com`) et créez un rôle avec la politique en lecture seule
de [Configurer un accès en lecture seule](./read-only-access.md). Limitez sa politique
d’approbation à votre dépôt et à votre branche. Le guide AWS
[Use IAM roles to connect GitHub Actions to actions in AWS](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)
détaille la procédure.

## 2. Ajouter un modèle de configuration à votre dépôt {#2-add-a-config-template-to-your-repository}

```bash
inventag templates init ci-pipeline --output .inventag/templates/nightly.yaml
```

Définissez vos régions et votre politique d’étiquetage, puis validez le fichier dans le dépôt.

## 3. Ajouter le workflow {#3-add-the-workflow}

```yaml
# .github/workflows/inventory.yml
name: AWS inventory
on:
  schedule:
    - cron: "17 2 * * 1-5"   # 02:17 UTC on weekdays
  workflow_dispatch:

permissions:
  contents: read
  id-token: write            # needed for OIDC

jobs:
  inventory:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.12"
      - run: pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
      - uses: aws-actions/configure-aws-credentials@<full-commit-SHA> # pin the current release
        with:
          role-to-assume: arn:aws:iam::123456789012:role/InvenTagGitHubReadOnly
          aws-region: us-east-1
      - name: Run InvenTag
        run: inventag --template nightly --fail-on-account-error --fail-if-empty
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()          # keep the reports even when the tag check fails
        with:
          name: inventory
          path: bom_output/
          retention-days: 30
```

Épinglez chaque action sur un SHA de commit complet, avec la version en commentaire. Cela
vous protège si une balise est déplacée vers du code malveillant. Les SHA ci-dessus pour
`checkout`, `setup-python` et `upload-artifact` sont ceux qu’utilisent les propres workflows
de ce dépôt. Pour `aws-actions/configure-aws-credentials`, cherchez le
SHA de sa version actuelle sur sa page de versions GitHub : nous n’en avons vérifié aucun
pour cette page. Mettez à jour les SHA lorsque vous mettez à jour les versions.

InvenTag s’exécute depuis le dossier de votre dépôt ; `.inventag/templates/nightly.yaml`
est donc trouvé par son nom.

Sans les deux options de code de sortie, le job réussit même si un compte n’a pas pu être analysé ou si rien n’a été trouvé.
`--fail-on-account-error` fait échouer le job avec le code 5 dans le premier cas, et `--fail-if-empty` avec le code 6 dans le second.
Les rapports sont quand même écrits, l’étape des artefacts peut donc les conserver.

## Ce qui se passe en cas de violation {#what-happens-on-a-violation}

Avec `fail_on_tag_violations: true`, InvenTag écrit d’abord tous les rapports, puis
se termine avec le code 3. Le job échoue, et l’artefact contient toujours le fichier Excel
et `tag_compliance_<timestamp>.json` avec chaque ressource non conforme.

Exemple de sortie de `inventag --template ci-pipeline` d’une exécution hors ligne
(données d’exemple) :

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
Tag policy violations found and fail_on_tag_violations is true (exit code 3).
```

```bash title="Terminal"
echo $?
```

```text title="Sortie"
3
```

## Codes de sortie {#exit-codes}

| Code de sortie | Signification |
|---|---|
| 0 | Rapports écrits, aucune violation d’étiquette (ou aucune politique bloquante). Aussi quand un compte a échoué ou que rien n’a été trouvé, sauf si vous passez les options des codes 5 et 6 |
| 1 | Erreur : modèle ou fichier de configuration invalide, identifiants, échec de tous les comptes, format de rapport impossible à écrire, ou échec d’un téléversement S3 |
| 2 | Options invalides ou en conflit, par exemple `--accounts-file` avec `--accounts-prompt`, ou `--compliance-standard` (non implémentée). Rien n’est analysé |
| 3 | Rapports écrits, violations de la politique d’étiquetage trouvées (`fail_on_tag_violations: true`) |
| 4 | Rapports écrits, une règle de groupe de sécurité ouverte à Internet atteint ou dépasse `--risk-threshold` |
| 5 | Rapports écrits, un compte n’a pas pu être analysé, ou seulement en partie (`--fail-on-account-error`) |
| 6 | Aucune ressource à signaler (`--fail-if-empty`) |

Si plusieurs codes s’appliquent, le 5 passe en premier, puis le 6, puis le 3, puis le 4, car les données derrière un résultat d’étiquettes ou de risque sont incomplètes quand un compte manque.
Des rapports sont écrits pour les codes 3, 4 et 5. Avec le code 6, une exécution avec `--template` écrit un rapport qui ne liste aucune ressource, et une exécution sans elle n’écrit aucun fichier.

## Rester prudent {#keep-it-safe}

- Évitez `--debug` en CI. Les secrets sont masqués dans les journaux de débogage, mais ces journaux sont
  longs et décrivent tout de même vos comptes.
- Pour conserver les rapports dans S3 plutôt que (ou en plus) des artefacts, ajoutez
  `--s3-bucket` et accordez `s3:PutObject` sur ce bucket. Voir
  [Téléverser les rapports vers S3 selon un calendrier](../examples/scheduled-s3-upload.md).
- Gardez le rôle en lecture seule et limité au dépôt et à la branche qui en ont
  besoin.
- Épinglez InvenTag sur une version publiée (`inventag-aws==%INVENTAG_VERSION%`), pas sur la dernière version. Augmentez le numéro quand vous choisissez de mettre à jour.

## Étapes suivantes {#next-steps}

- [Exemple : appliquer une politique d’étiquetage en CI](../examples/tag-policy-in-ci.md)
- [Suivre les changements entre deux exécutions](./track-changes.md)
