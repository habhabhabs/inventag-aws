---
title: "Example: security tagging review"
description: Check that AWS resources carry Owner, Environment and DataClassification tags before a security review, with InvenTag's security-baseline tag policy.
sidebar_position: 6
---

# Example: security tagging review

**Goal:** before a security review or an incident exercise, find resources
with no owner, no environment or no data classification.

**You need:** read-only credentials.

This checks tags only. It does not assess how securely anything is
configured, and passing it does not make you compliant with any framework.

## Template

The built-in `security-baseline` tag policy requires:

| Tag key | Rule |
|---|---|
| `Owner` | Any value |
| `Environment` | `prod`, `staging`, `dev`, `test` or `sandbox` |
| `DataClassification` | `public`, `internal`, `confidential` or `restricted` |

## Command

```bash title="Terminal"
inventag --template standard-bom --template security-baseline \
  --create-excel --create-word --account-regions us-east-1
```

## Output

<!-- BEGIN EXAMPLE OUTPUT: security-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'security-baseline': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

<!-- END EXAMPLE OUTPUT: security-console -->

<!-- BEGIN EXAMPLE OUTPUT: security-excel-compliance -->

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

`Tag Compliance` sheet, first rows:

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | Owner, Environment, DataClassification |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | Owner, Environment, DataClassification |  |

<!-- END EXAMPLE OUTPUT: security-excel-compliance -->

Filter the "Missing tags" column for `Owner` to find unowned resources first.

## Next steps

- Agree owners for the unowned resources, then tag them in your
  infrastructure code.
- Narrow the check to data stores only:

```yaml title=".inventag/templates/data-stores.yaml"
format_version: 1
kind: tag-policy
name: data-stores
description: Classification on data stores only
extends: security-baseline
spec:
  scope:
    services: [S3, DYNAMODB, RDS]
```
