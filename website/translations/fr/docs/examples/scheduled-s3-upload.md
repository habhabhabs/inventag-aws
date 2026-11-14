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
  chiffrés. Sa ressource est
  `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*` : remplacez le nom du bucket,
  et notez qu’elle ne couvre que les clés qui commencent par `bom-reports/`. C’est
  aussi la valeur par défaut de `--s3-key-prefix`. Avec un autre préfixe, modifiez
  la ressource ;
- un planificateur : cron, une planification CI ou équivalent.

## Commande {#command}

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ \
  --audit-output audit.json
```

- `--s3-bucket` envoie chaque rapport écrit par l’exécution. Les envois utilisent le chiffrement
  côté serveur (`AES256` par défaut ; utilisez `--s3-encryption aws:kms` et
  `--s3-kms-key-id` pour une clé KMS). `--s3-kms-key-id` ne fonctionne qu’avec
  `--s3-encryption aws:kms` ; sans elle, l’exécution s’arrête avec le code de
  sortie 2. Avec `aws:kms` et sans ID de clé, S3 utilise la clé gérée par AWS
  `aws/s3`.
- Chaque fichier est placé sous `<prefix><UTC timestamp>/<file name>`, de sorte que les exécutions ne
  s’écrasent pas. Le fichier JSON de conformité des étiquettes est envoyé aussi, lorsqu’il
  en existe un.
- Si un envoi échoue, l’exécution se termine avec le code 1, ce qui alerte un planificateur. Les
  rapports restent sur votre disque.
- `--audit-output` écrit une liste JSON de chaque opération AWS appelée par l’exécution.
  Cela fonctionne avec ou sans S3.

## Sortie {#output}

Issue d’une exécution hors ligne sur un AWS simulé (données d’exemple) :

```text title="Sortie"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

Ce qui est arrivé dans le bucket :

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090100.xlsx
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
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ >> /var/log/inventag.log 2>&1
```

Dans GitHub Actions, ajoutez les options `--s3-bucket` à l’étape d’exécution décrite dans
[Exécuter InvenTag en CI/CD](../guides/run-in-ci.md).

### GitLab CI/CD {#gitlab-cicd}

Non vérifié sur un runner GitLab ni sur un vrai compte AWS : ce pipeline n’a pas été exécuté sur GitLab. Son YAML et sa ligne de commande `inventag` sont contrôlés lors de la construction de la documentation. Son job a été exécuté en local avec gitlab-ci-local 4.77.1 (avec un substitut de rsync) contre un AWS simulé, avec un jeton factice.

Ce job exécute la commande ci-dessus selon une planification de pipeline, envoie les rapports vers votre bucket et garde une copie comme artefacts du job. Avant de l’utiliser :

- Créez le rôle auquel GitLab se connecte et la variable CI/CD `AWS_ROLE_ARN`, comme décrit dans [Exécuter InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Cette même section explique comment créer la planification du pipeline.
- Ajoutez deux autres variables CI/CD : `INVENTAG_REPORTS_BUCKET` (le nom du bucket) et `INVENTAG_KMS_KEY_ID` (l’ID de la clé KMS). Aucune n’est un secret.
- Donnez au rôle l’instruction `OptionalS3ReportUpload` de `config/defaults/iam-policy-read-only.json`, avec le nom de votre bucket à la place de `YOUR-REPORTS-BUCKET-NAME`. Sa ressource est `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*` : gardez donc `--s3-key-prefix bom-reports/` ou modifiez la ressource. Avec `aws:kms`, le rôle a aussi besoin de `kms:GenerateDataKey` sur la clé ([Autorisations IAM](../reference/iam-permissions.md)).

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

Les lignes que tous les exemples GitLab ont en commun sont expliquées dans [Exécuter InvenTag en CI/CD](../guides/run-in-ci.md#gitlab-cicd). Ce tableau couvre ce qui est propre à cet exemple.

| Élément | Ce qu’il fait |
|---|---|
| `- \|` avec `\` en fin de ligne | Une seule commande shell écrite sur cinq lignes ([GitLab : script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/` | Envoie chaque rapport de l’exécution vers `<prefix><UTC timestamp>/<file name>`. Le nom du bucket vient d’une variable CI/CD. `bom-reports/` est aussi la valeur par défaut. Il est écrit explicitement parce que la politique publiée n’autorise `s3:PutObject` que sur `YOUR-REPORTS-BUCKET-NAME/bom-reports/*`. Si un envoi échoue, l’exécution se termine avec le code 1 et le job échoue ([GitLab : script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID"` | La règle KMS de cette page : `--s3-kms-key-id` ne fonctionne qu’avec `--s3-encryption aws:kms` ; sans elle, l’exécution s’arrête avec le code de sortie 2. Avec `aws:kms` et sans ID de clé, S3 utilise la clé gérée par AWS `aws/s3`. Sans KMS, supprimez cette ligne : les envois utilisent alors `AES256`. Le rôle a besoin de `kms:GenerateDataKey` sur la clé. |
| `--fail-on-account-error --fail-if-empty` | Code de sortie 5 lorsqu’un compte n’a pas pu être analysé ; code de sortie 6 lorsqu’aucune ressource n’a été trouvée. Tout code de sortie autre que 0 fait échouer le job ([GitLab : script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--audit-output bom_output/audit.json` | Écrit la liste des opérations AWS de l’exécution dans le dossier des artefacts. |
| `artifacts:` avec `expire_in: 1 week` | Une seconde copie dans GitLab, aussi lorsque l’envoi a échoué ([`when`](https://docs.gitlab.com/ci/yaml/#artifactswhen), [`expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in)). Facultatif. |

Éléments que l’exécution locale n’a pas couverts :

- Non vérifié sur GitLab ni sur AWS : l’émission du jeton d’ID par GitLab et son acceptation par AWS pour le rôle, avec les conditions de la politique d’approbation sur `aud` et `sub`.
- Non vérifié sur GitLab : `image`, `timeout` et `expire_in` (gitlab-ci-local les ignore).
- Non vérifié sur une planification de pipeline GitLab : l’exécution locale a défini l’origine du pipeline à la main.
- Non vérifié sur AWS : les autorisations S3 et KMS pour l’envoi, avec un vrai bucket et une vraie clé.

## Étapes suivantes {#next-steps}

- Ajoutez une règle de cycle de vie S3 au bucket si vous voulez que les anciens rapports soient supprimés
  au bout d’un certain temps. InvenTag ne modifie pas les règles de cycle de vie de votre bucket.
- Conservez le dossier `state/` entre les exécutions si vous voulez un historique :
  [Suivre les changements entre les exécutions](../guides/track-changes.md).
