---
title: "Exemple : envoyer les rapports vers S3 selon un calendrier"
description: Envoyez les rapports Excel chiffrés d’InvenTag vers un bucket S3 après chaque exécution planifiée, avec un audit de chaque appel AWS effectué par l’exécution.
sidebar_position: 9
---

# Exemple : envoyer les rapports vers S3 selon un calendrier

**Objectif :** chaque exécution planifiée dépose ses rapports dans un bucket S3, chiffrés,
avec la trace de chaque appel AWS qu’elle a effectué.

**Ce qu’il vous faut :**

- un bucket pour les rapports, par exemple `acme-inventory-reports` ;
- `s3:PutObject` sur ce bucket pour l’identité qui exécute InvenTag. L’instruction
  `OptionalS3ReportUpload` de
  `config/defaults/iam-policy-read-only.json` s’en charge, et elle n’autorise que les envois
  chiffrés ;
- un planificateur : cron, une planification CI ou équivalent.

## Commande {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ \
  --audit-output audit.json
```

- `--s3-bucket` envoie chaque rapport écrit par l’exécution. Les envois utilisent le chiffrement
  côté serveur (`AES256` par défaut ; utilisez `--s3-encryption aws:kms` et
  `--s3-kms-key-id` pour une clé KMS).
- Chaque fichier est placé sous `<prefix><UTC timestamp>/<file name>`, de sorte que les exécutions ne
  s’écrasent pas. Le fichier JSON de conformité des étiquettes est envoyé aussi, lorsqu’il
  en existe un.
- Si un envoi échoue, l’exécution se termine avec le code 1, ce qui alerte un planificateur. Les
  rapports restent sur votre disque.
- `--audit-output` écrit une liste JSON de chaque opération AWS appelée par l’exécution.
  Cela fonctionne avec ou sans S3.

## Sortie {#output}

Issue d’une exécution hors ligne sur un AWS simulé (données d’exemple) :

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
workmail list_organizations in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

Ce qui est arrivé dans le bucket :

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

Le fichier d’audit (extrait) :

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
  "total_calls": 96,
  "allowed_calls": 96,
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

`blocked_calls` vaut 0 : l’exécution n’a effectué que des appels en lecture.

## Planifier l’exécution {#schedule-it}

Avec cron, chaque jour ouvré à 02:17 :

```text title="crontab -e"
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ >> /var/log/inventag.log 2>&1
```

Dans GitHub Actions, ajoutez les options `--s3-bucket` à l’étape d’exécution décrite dans
[Exécuter InvenTag en CI/CD](../guides/run-in-ci.md).

## Étapes suivantes {#next-steps}

- Ajoutez une règle de cycle de vie S3 au bucket si vous voulez que les anciens rapports soient supprimés
  au bout d’un certain temps. InvenTag ne modifie pas les règles de cycle de vie de votre bucket.
- Conservez le dossier `state/` entre les exécutions si vous voulez un historique :
  [Suivre les changements entre les exécutions](../guides/track-changes.md).
