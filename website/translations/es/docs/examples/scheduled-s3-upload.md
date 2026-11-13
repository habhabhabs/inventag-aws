---
title: "Ejemplo: subir informes a S3 de forma programada"
description: Sube los informes de Excel cifrados de InvenTag a un bucket de S3 después de cada ejecución programada, con una auditoría de cada llamada a AWS que hizo la ejecución.
sidebar_position: 9
---

# Ejemplo: subir informes a S3 de forma programada

**Objetivo:** que cada ejecución programada deje sus informes en un bucket de
S3, cifrados, con un registro de cada llamada a AWS que hizo.

**Necesitas:**

- un bucket para los informes, por ejemplo `acme-inventory-reports`;
- `s3:PutObject` sobre ese bucket para la identidad que ejecuta InvenTag. La
  declaración `OptionalS3ReportUpload` de
  `config/defaults/iam-policy-read-only.json` lo concede, y solo permite subidas
  cifradas;
- un programador: cron, una programación de CI o similar.

## Comando {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ \
  --audit-output audit.json
```

- `--s3-bucket` sube todos los informes que escribió la ejecución. Las subidas
  usan cifrado en el servidor (`AES256` de forma predeterminada; usa
  `--s3-encryption aws:kms` y `--s3-kms-key-id` para una clave de KMS).
- Cada archivo va a `<prefix><UTC timestamp>/<file name>`, de modo que las
  ejecuciones no se sobrescriben entre sí. El archivo JSON de cumplimiento de
  etiquetas también se sube, cuando existe.
- Si falla una subida, la ejecución termina con el código 1, para que lo
  detecte un programador. Los informes siguen en tu disco.
- `--audit-output` escribe una lista JSON de todas las operaciones de AWS a las
  que llamó la ejecución. Funciona con S3 o sin él.

## Salida {#output}

De una ejecución sin conexión contra AWS simulado (datos de ejemplo):

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

Lo que llegó al bucket:

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

El archivo de auditoría (extracto):

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
  "total_calls": 73,
  "allowed_calls": 73,
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
      "service": "ce",
      "operation": "GetCostAndUsage",
      "allowed": true,
      "count": 2
    },
    {
      "service": "cloudformation",
      "operation": "DescribeStacks",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudformation",
      "operation": "ListStackSets",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudfront",
      "operation": "ListDistributions",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

`blocked_calls` es 0: la ejecución solo hizo llamadas de lectura.

## Prográmalo {#schedule-it}

Con cron, cada día laborable a las 02:17:

```text title="crontab -e"
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ >> /var/log/inventag.log 2>&1
```

En GitHub Actions, añade las opciones `--s3-bucket` al paso de ejecución de
[Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md).

## Siguientes pasos {#next-steps}

- Añade una regla de ciclo de vida de S3 al bucket si quieres que los informes
  antiguos se eliminen pasado un tiempo. InvenTag no modifica las reglas de
  ciclo de vida de tu bucket.
- Conserva la carpeta `state/` entre ejecuciones si quieres historial:
  [Seguir los cambios entre ejecuciones](../guides/track-changes.md).
