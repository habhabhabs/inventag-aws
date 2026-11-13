---
title: "Exemple : rapport Word de direction à votre image"
description: Produisez un court rapport Word en paysage avec votre logo, vos couleurs et une synthèse de conformité des étiquettes, à l’aide d’un modèle de rapport InvenTag.
sidebar_position: 7
---

# Exemple : rapport Word de direction à votre image

**Objectif :** un court document Word pour la direction, avec votre logo et vos couleurs :
totaux, services et conformité des étiquettes, sans tableaux par ressource.

**Ce qu’il vous faut :** des identifiants en lecture seule et un logo au format PNG, JPEG, GIF ou BMP.
Word ne peut pas intégrer de logos SVG.

## Modèle {#template}

Placez le logo à côté du modèle, dans le même dossier ou dans un sous-dossier :

```text title="Project layout"
.inventag/templates/
  board-report.yaml
  brand/
    acme-logo.png
```

```yaml title=".inventag/templates/board-report.yaml"
format_version: 1
kind: report
name: board-report
description: Branded summary for the leadership team
extends: executive-summary
spec:
  title: Cloud Estate Summary
  subtitle: Quarterly review
  company_name: Acme Ltd
  logo: brand/acme-logo.png
  logo_alt_text: Acme Ltd logo        # read by screen readers
  colors:
    header_fill: "4B2E83"             # 10.4:1 contrast with white text
  tag_policy: security-baseline
  word:
    orientation: landscape
```

## Commande {#command}

```bash title="Terminal"
inventag templates validate board-report
inventag --template board-report --create-word --account-regions us-east-1
```

## Sortie {#output}

```text title="Terminal"
OK    ~/acme-infra/.inventag/templates/board-report.yaml (report 'board-report')
```

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Tag policy 'security-baseline': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

**Plan du document :**

- **Cloud Estate Summary** (titre)
- Summary
- Resources by service
- Tag compliance
  - Required tags
  - Non-compliant resources
- About this report

Un tableau du document :

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| Owner | Any value | 17 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 17 | 1 |
| DataClassification | One of: public, internal, confidential, restr... | 22 | 0 |

![Première page du rapport Word en paysage à votre image : un logo carré violet, le titre Cloud Estate Summary, Quarterly review, Prepared for Acme Ltd et la liste de synthèse (données d’exemple)](../assets/examples/img/board-report-word-page1.png)

[Télécharger l’exemple de rapport Word](pathname:///inventag-aws/downloads/board-report-sample.docx) (38 Ko, données d’exemple)

Si le logo est introuvable, ou s’il n’est pas dans un format d’image pris en charge par Word, l’exécution
s’arrête avant l’analyse :

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   ~/acme-infra/.inventag/templates/board-report.yaml:10: spec.logo: logo file not found: ~/acme-infra/.inventag/templates/brand/acme-logo.png
$ echo $?
1
```

## Étapes suivantes {#next-steps}

- Gardez des couleurs lisibles : choisissez pour l’en-tête une couleur dont le rapport de contraste avec
  le texte d’en-tête est d’au moins 4,5:1.
- Ajoutez l’inventaire complet sous forme de fichier Excel :
  `inventag --template board-report --create-word --create-excel`.
