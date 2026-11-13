---
title: Generate your first report
description: Scan one AWS account and region with InvenTag and open the Excel and Word bill-of-materials reports it writes, in about ten minutes.
sidebar_position: 3
---

# Generate your first report

**Who this is for:** you have [installed InvenTag](./installation.md) and have
read-only AWS credentials.

**What you can do after reading:** scan one account, open the Excel and Word
reports, and choose a clearer layout with a template.

All sample output on this page comes from an offline run against mocked AWS
(sample data). Account `123456789012` and the `acme-*` resources are made up.

## 1. Check which account you are in

```bash title="Terminal"
aws sts get-caller-identity
```

InvenTag scans the account these credentials belong to.

## 2. Scan one region

Start small. One region is quick and cheap.

```bash title="Terminal"
inventag --create-excel --create-word --account-regions us-east-1
```

- `--create-excel` and `--create-word` choose the files to write. Without
  either, you get Excel only.
- `--account-regions` limits the scan to the regions you list, separated by
  commas. Without it, InvenTag scans every region enabled in the account,
  which takes longer. IAM, the S3 bucket list, CloudFront and Route 53 are
  always read once from `us-east-1`, whichever regions you list.

At the end you see where the files went:

<!-- BEGIN EXAMPLE OUTPUT: quick-default-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Word document saved: bom_output/multi_account_bom_20261112_090000.docx
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: quick-default-console -->

The warning only says you didn't name an account, so InvenTag used your
current credentials. Add `--verbose` to see each step.

## 3. Open the reports

The Excel workbook has a **Summary** sheet and one sheet per service. Without
a template, each service sheet lists every field InvenTag found, so the
sheets are wide:

<!-- BEGIN EXAMPLE OUTPUT: quick-default-excel -->

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`

`S3` sheet, first rows:

| service | type | id | name | arn | account_id | source_account_id | source_account_name | ... |
|---|---|---|---|---|---|---|---|---|
| S3 | Bucket | acme-app-logs | acme-app-logs | arn:aws:s3:::acme-app-logs |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-data-lake | acme-data-lake | arn:aws:s3:::acme-data-lake |  | 123456789012 | AWS Account 123456789012 (moto) | ... |
| S3 | Bucket | acme-reports | acme-reports | arn:aws:s3:::acme-reports |  | 123456789012 | AWS Account 123456789012 (moto) | ... |

The sheet has 33 columns; the first 8 are shown.

<!-- END EXAMPLE OUTPUT: quick-default-excel -->

The Word document has a summary, a table of services and up to 50 resources
per service:

<!-- BEGIN EXAMPLE OUTPUT: quick-default-word -->

**Document outline:**

- **AWS Resource Inventory - BOM Report** (title)
- Executive Summary
  - Service Summary
- Detailed Resource Inventory
  - ATHENA Resources (1)
  - DYNAMODB Resources (1)
  - EC2 Resources (4)
  - EVENTS Resources (1)
  - IAM Resources (1)
  - KMS Resources (14)
  - LAMBDA Resources (1)
  - S3 Resources (4)
  - VPC Resources (10)
- Report Information

A table from the document:

| Service | Resource Count | Percentage |
|---|---|---|
| ATHENA | 1 | 2.7% |
| DYNAMODB | 1 | 2.7% |
| EC2 | 4 | 10.8% |
| EVENTS | 1 | 2.7% |

(9 rows in total; 4 shown.)

<!-- END EXAMPLE OUTPUT: quick-default-word -->

InvenTag also saves a snapshot of the run in `bom_output/state/`.

## 4. Choose a layout with a template

A [report template](../templates/index.md) gives you readable column names,
one column per tag, a frozen header row and filter buttons:

```bash title="Terminal"
inventag --template standard-bom --create-excel --create-word --account-regions us-east-1
```

<!-- BEGIN EXAMPLE OUTPUT: standard-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: standard-console -->

See what the result looks like in
[Built-in templates](../templates/catalogue.md#standard-bom).

## 5. Check your tags

Add a tag policy to see which resources are missing tags:

```bash title="Terminal"
inventag --template finops-cost-report --create-excel --create-word --account-regions us-east-1
```

<!-- BEGIN EXAMPLE OUTPUT: finops-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
redshift-serverless list_workgroups in us-east-1 failed (404); its resources there may be incomplete.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

<!-- END EXAMPLE OUTPUT: finops-console -->

The workbook now has a **Tag Compliance** sheet that lists what is missing on
each resource. More in [Check tags against a policy](../guides/check-tag-compliance.md).

## What a run costs

The read-only calls InvenTag makes are free. Cost Explorer
`GetCostAndUsage` calls are not: AWS charges per request, and a default run
makes two for each account in our offline test. See the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Add `--no-billing-validation` to make no Cost Explorer calls.

## Next steps

- [Feature status and known limitations](./status.md): read this before you
  rely on a flag.
- [Choose what to scan and what to produce](../guides/run-a-scan.md)
- [Examples](../examples/index.md): copy-paste recipes.
