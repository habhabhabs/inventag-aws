---
title: "Example: upload reports to S3 on a schedule"
description: Upload InvenTag's encrypted Excel reports to an S3 bucket after every scheduled run, with an audit of every AWS call the run made.
sidebar_position: 9
---

# Example: upload reports to S3 on a schedule

**Goal:** every scheduled run puts its reports in an S3 bucket, encrypted,
with a record of every AWS call it made.

**You need:**

- a bucket for reports, for example `acme-inventory-reports`;
- `s3:PutObject` on that bucket for the identity that runs InvenTag. The
  `OptionalS3ReportUpload` statement in
  `config/defaults/iam-policy-read-only.json` does this, and it only allows
  encrypted uploads. Its resource is
  `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`: replace the bucket name,
  and note that it covers only keys that start with `bom-reports/`. That is
  also the default of `--s3-key-prefix`. For another prefix, change the
  resource;

  Not verified against real AWS: the statement allows the upload only with server-side encryption.

- a scheduler: cron, a CI schedule or similar.

## Command

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ \
  --audit-output audit.json
```

- `--s3-bucket` uploads every report the run wrote. Uploads use server-side
  encryption (`AES256` by default; use `--s3-encryption aws:kms` and
  `--s3-kms-key-id` for a KMS key). `--s3-kms-key-id` works only with
  `--s3-encryption aws:kms`; without it the run stops with exit code 2. With
  `aws:kms` and no key ID, S3 uses the AWS managed key `aws/s3`.

  Not verified against AWS: that S3 uses the AWS managed key `aws/s3` when `aws:kms` has no key ID.

- Each file goes to `<prefix><UTC timestamp>/<file name>`, so runs do not
  overwrite each other. The tag-compliance JSON file is uploaded too, when
  there is one.
- If an upload fails, the run exits with code 1, so a scheduler notices. The
  reports are still on your disk.
- `--audit-output` writes a JSON list of every AWS operation the run called.
  It works with or without S3.

## Output

From an offline run against mocked AWS (sample data):

<!-- BEGIN EXAMPLE OUTPUT: s3-console -->

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: s3-console -->

What arrived in the bucket:

<!-- BEGIN EXAMPLE OUTPUT: s3-keys -->

```text title="Objects in s3://acme-inventory-reports"
bom-reports/20261112_090000/multi_account_bom_20261112_090100.xlsx
```

<!-- END EXAMPLE OUTPUT: s3-keys -->

The audit file (excerpt):

<!-- BEGIN EXAMPLE OUTPUT: audit-json -->

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

<!-- END EXAMPLE OUTPUT: audit-json -->

`blocked_calls` is 0: InvenTag blocked no call. Apart from the report upload
(`PutObject`), the run made only read calls.

## Schedule it

With cron, every weekday at 02:17:

```text title="crontab -e"
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix bom-reports/ >> /var/log/inventag.log 2>&1
```

Not verified against cron: the schedule line. The path `/opt/inventag-aws` is an example.

In GitHub Actions, add the `--s3-bucket` options to the run step in
[Run InvenTag in CI/CD](../guides/run-in-ci.md).

### GitLab CI/CD

Not verified against a GitLab runner or a real AWS account: this pipeline has not run on GitLab. Its YAML and its `inventag` command line are checked when the docs are built. Its job ran locally with gitlab-ci-local 4.77.1 (with a stand-in for rsync) against mocked AWS, with a dummy token.

This job runs the command above on a pipeline schedule, uploads the reports to your bucket and keeps a copy as job artifacts. Before you use it:

- Create the role that GitLab signs in to and the CI/CD variable `AWS_ROLE_ARN`, as described in [Run InvenTag in CI/CD](../guides/run-in-ci.md#gitlab-cicd). The same section explains how to create the pipeline schedule.
- Add two more CI/CD variables: `INVENTAG_REPORTS_BUCKET` (the bucket name) and `INVENTAG_KMS_KEY_ID` (the KMS key ID). Neither is a secret.
- Give the role the `OptionalS3ReportUpload` statement from `config/defaults/iam-policy-read-only.json`, with your bucket name in place of `YOUR-REPORTS-BUCKET-NAME`. Its resource is `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`, so keep `--s3-key-prefix bom-reports/` or change the resource. With `aws:kms`, the role also needs `kms:GenerateDataKey` on the key ([IAM permissions](../reference/iam-permissions.md)).

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

The lines that every GitLab example shares are explained in [Run InvenTag in CI/CD](../guides/run-in-ci.md#gitlab-cicd). This table covers what is specific to this example.

| Part | What it does |
|---|---|
| `- \|` with `\` at the end of the lines | One shell command written over five lines ([GitLab: script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-key-prefix bom-reports/` | Uploads every report of the run to `<prefix><UTC timestamp>/<file name>`. The bucket name comes from a CI/CD variable. `bom-reports/` is also the default. It is written out because the published policy allows `s3:PutObject` only on `YOUR-REPORTS-BUCKET-NAME/bom-reports/*`. If an upload fails, the run exits with code 1 and the job fails ([GitLab: script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--s3-encryption aws:kms --s3-kms-key-id "$INVENTAG_KMS_KEY_ID"` | The KMS rule of this page: `--s3-kms-key-id` works only with `--s3-encryption aws:kms`; without it the run stops with exit code 2. With `aws:kms` and no key ID, S3 uses the AWS managed key `aws/s3`. Without KMS, delete this line: uploads then use `AES256`. The role needs `kms:GenerateDataKey` on the key. |
| `--fail-on-account-error --fail-if-empty` | Exit code 5 when an account could not be scanned; exit code 6 when no resources were found. Any exit code other than 0 fails the job ([GitLab: script](https://docs.gitlab.com/ci/yaml/script/)). |
| `--audit-output bom_output/audit.json` | Writes the list of AWS operations of the run into the artifact folder. |
| `artifacts:` with `expire_in: 1 week` | A second copy in GitLab, also when the upload failed ([`when`](https://docs.gitlab.com/ci/yaml/#artifactswhen), [`expire_in`](https://docs.gitlab.com/ci/yaml/#artifactsexpire_in)). Optional. |

Parts that the local run did not cover:

- Not verified against GitLab or AWS: GitLab issuing the ID token and AWS accepting it for the role, with the trust policy conditions on `aud` and `sub`.
- Not verified against GitLab: `image`, `timeout` and `expire_in` (gitlab-ci-local ignores them).
- Not verified against a GitLab pipeline schedule: the local run set the pipeline source by hand.
- Not verified against AWS: the S3 and KMS permissions for the upload, with a real bucket and key.
- Not verified against AWS: that S3 uses the AWS managed key `aws/s3` when `aws:kms` has no key ID.

## Next steps

- Add an S3 lifecycle rule to the bucket if you want old reports deleted
  after a while. InvenTag does not change your bucket's lifecycle rules.
- Keep the `state/` folder between runs if you want history:
  [Track changes between runs](../guides/track-changes.md).
