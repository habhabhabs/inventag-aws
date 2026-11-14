---
title: "Ejemplo: subir informes a S3 de forma programada"
description: Sube los informes de Excel cifrados de InvenTag a un bucket de S3 tras cada ejecución programada, con una auditoría de cada llamada a AWS de la ejecución.
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
  cifradas. Su recurso es
  `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`: sustituye el nombre del bucket
  y ten en cuenta que solo cubre las claves que empiezan por `bom-reports/`. Ese es
  también el valor predeterminado de `--s3-key-prefix`. Si usas otro prefijo, cambia
  el recurso;
- un programador: cron, una programación de CI o similar.

## Comando {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ \
  --audit-output audit.json
```

- `--s3-bucket` sube todos los informes que escribió la ejecución. Las subidas
  usan cifrado en el servidor (`AES256` de forma predeterminada; usa
  `--s3-encryption aws:kms` y `--s3-kms-key-id` para una clave de KMS).
  `--s3-kms-key-id` solo funciona con `--s3-encryption aws:kms`; sin ella la
  ejecución se detiene con el código de salida 2. Con `aws:kms` y sin ID de clave,
  S3 usa la clave administrada por AWS `aws/s3`.
- Cada archivo va a `<prefix><UTC timestamp>/<file name>`, de modo que las
  ejecuciones no se sobrescriben entre sí. El archivo JSON de cumplimiento de
  etiquetas también se sube, cuando existe.
- Si falla una subida, la ejecución termina con el código 1, para que lo
  detecte un programador. Los informes siguen en tu disco.
- `--audit-output` escribe una lista JSON de todas las operaciones de AWS a las
  que llamó la ejecución. Funciona con S3 o sin él.

## Salida {#output}

De una ejecución sin conexión contra AWS simulado (datos de ejemplo):

```text title="Salida"
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

`blocked_calls` es 0: la ejecución solo hizo llamadas de lectura.

## Prográmalo {#schedule-it}

Con cron, cada día laborable a las 02:17:

```text title="crontab -e"
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ >> /var/log/inventag.log 2>&1
```

En GitHub Actions, añade las opciones `--s3-bucket` al paso de ejecución de
[Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md).

### GitLab CI/CD {#gitlab-cicd}

No verificado contra un runner de GitLab ni una cuenta real de AWS: este pipeline no se ha ejecutado en GitLab. Su YAML y su línea de comandos `inventag` se comprueban cuando se compila la documentación. Su job se ejecutó en local con gitlab-ci-local 4.77.1 (con un sustituto de rsync) contra un AWS simulado, con un token ficticio.

Este job ejecuta el comando de arriba en una programación de pipelines, sube los informes a tu bucket y conserva una copia como artefactos del job. Antes de usarlo:

- Crea el rol con el que GitLab inicia sesión y la variable de CI/CD `AWS_ROLE_ARN`, como se describe en [Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Esa misma sección explica cómo crear la programación del pipeline.
- Añade dos variables de CI/CD más: `INVENTAG_REPORTS_BUCKET` (el nombre del bucket) y `INVENTAG_KMS_KEY_ID` (el ID de la clave de KMS). Ninguna es un secreto.
- Da al rol la declaración `OptionalS3ReportUpload` de `config/defaults/iam-policy-read-only.json`, con el nombre de tu bucket en lugar de `YOUR-REPORTS-BUCKET-NAME`. Su recurso es `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`, así que conserva `--s3-key-prefix bom-reports/` o cambia el recurso. Con `aws:kms`, el rol también necesita `kms:GenerateDataKey` sobre la clave ([Permisos de IAM](../reference/iam-permissions.md)).

```yaml
# .gitlab-ci.yml
stages:
  - inventory

inventory-to-s3:
  stage: inventory
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
  timeout: 2 hours                            # the ID token expires with the job
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: sts.amazonaws.com
  variables:
    AWS_DEFAULT_REGION: us-east-1
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"   # pin a release
    - export AWS_WEB_IDENTITY_TOKEN_FILE="$(mktemp)"
    - printf '%s' "$GITLAB_OIDC_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    # --s3-kms-key-id works only together with --s3-encryption aws:kms.
    # Without KMS, delete that line: uploads then use AES256.
    - |
      inventag --template standard-bom --create-excel --account-regions us-east-1 \
        --s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/ \
        --s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID" \
        --audit-output bom_output/audit.json \
        --fail-on-account-error --fail-if-empty
  artifacts:
    when: always                              # a copy in GitLab, also when the upload fails
    paths:
      - bom_output/
    expire_in: 1 week
```

Las líneas que comparten todos los ejemplos de GitLab se explican en [Ejecutar InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Esta tabla cubre lo que es propio de este ejemplo.

| Parte | Qué hace |
|---|---|
| `- \|` con `\` al final de las líneas | Un solo comando de shell escrito en cinco líneas ([GitLab: script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/` | Sube todos los informes de la ejecución a `<prefix><UTC timestamp>/<file name>`. El nombre del bucket viene de una variable de CI/CD. `bom-reports/` es también el valor predeterminado. Se escribe de forma explícita porque la política publicada solo permite `s3:PutObject` sobre `YOUR-REPORTS-BUCKET-NAME/bom-reports/*`. Si falla una subida, la ejecución termina con el código 1 y el job falla ([GitLab: script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID"` | La regla de KMS de esta página: `--s3-kms-key-id` solo funciona con `--s3-encryption aws:kms`; sin ella la ejecución se detiene con el código de salida 2. Con `aws:kms` y sin ID de clave, S3 usa la clave administrada por AWS `aws/s3`. Sin KMS, borra esta línea: las subidas usan entonces `AES256`. El rol necesita `kms:GenerateDataKey` sobre la clave. |
| `--fail-on-account-error --fail-if-empty` | Código de salida 5 cuando no se pudo analizar una cuenta; código de salida 6 cuando no se encontró ningún recurso. Cualquier código de salida distinto de 0 hace fallar el job ([GitLab: script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--audit-output bom_output/audit.json` | Escribe la lista de operaciones de AWS de la ejecución en la carpeta de artefactos. |
| `artifacts:` con `expire_in: 1 week` | Una segunda copia en GitLab, también cuando falló la subida ([`when`](https://docs.gitlab.com/ci/yaml/#artifactswhen), [`expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in)). Opcional. |

Partes que la ejecución local no cubrió:

- No verificado contra GitLab ni AWS: que GitLab emita el token de ID y que AWS lo acepte para el rol, con las condiciones de la política de confianza sobre `aud` y `sub`.
- No verificado contra GitLab: `image`, `timeout` y `expire_in` (gitlab-ci-local los ignora).
- No verificado contra una programación de pipelines de GitLab: la ejecución local fijó a mano el origen del pipeline.
- No verificado contra AWS: los permisos de S3 y KMS para la subida, con un bucket y una clave reales.

## Siguientes pasos {#next-steps}

- Añade una regla de ciclo de vida de S3 al bucket si quieres que los informes
  antiguos se eliminen pasado un tiempo. InvenTag no modifica las reglas de
  ciclo de vida de tu bucket.
- Conserva la carpeta `state/` entre ejecuciones si quieres historial:
  [Seguir los cambios entre ejecuciones](../guides/track-changes.md).
