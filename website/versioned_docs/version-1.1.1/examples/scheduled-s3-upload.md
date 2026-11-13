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
  encrypted uploads;
- a scheduler: cron, a CI schedule or similar.

## Command

```bash title="Terminal"
inventag --template standard-bom --create-excel --account-regions us-east-1 \
  --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ \
  --audit-output audit.json
```

- `--s3-bucket` uploads every report the run wrote. Uploads use server-side
  encryption (`AES256` by default; use `--s3-encryption aws:kms` and
  `--s3-kms-key-id` for a KMS key).
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

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: s3-console -->

What arrived in the bucket:

<!-- BEGIN EXAMPLE OUTPUT: s3-keys -->

```text title="Objects in s3://acme-inventory-reports"
inventag/20261112_090000/multi_account_bom_20261112_090100.xlsx
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

<!-- END EXAMPLE OUTPUT: audit-json -->

`blocked_calls` is 0: the run only made read calls.

## Schedule it

With cron, every weekday at 02:17:

```text title="crontab -e"
17 2 * * 1-5  cd /opt/inventag-aws && .venv/bin/python inventag_cli.py --template standard-bom --create-excel --s3-bucket acme-inventory-reports --s3-key-prefix inventag/ >> /var/log/inventag.log 2>&1
```

In GitHub Actions, add the `--s3-bucket` options to the run step in
[Run InvenTag in CI/CD](../guides/run-in-ci.md).

## Next steps

- Add an S3 lifecycle rule to the bucket if you want old reports deleted
  after a while. InvenTag does not change your bucket's lifecycle rules.
- Keep the `state/` folder between runs if you want history:
  [Track changes between runs](../guides/track-changes.md).
