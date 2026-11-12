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

```bash
./inventag.sh --template standard-bom --template security-baseline \
  --create-excel --create-word --account-regions us-east-1
```

## Expected output

Sample data from an offline run:

```text
Wrote bom_output/tag_compliance_20261112_130934.json
Wrote bom_output/multi_account_bom_20261112_130934.docx
Wrote bom_output/multi_account_bom_20261112_130934.xlsx
Tag policy 'security-baseline': 0 of 22 resources compliant (0.0%), 22 non-compliant, 14 out of scope.
```

None of the sample resources had a `DataClassification` tag, so none were
compliant. In the Tag Compliance sheet, filter the "Missing tags" column for
`Owner` to find unowned resources first.

## Next steps

- Agree owners for the unowned resources, then tag them in your
  infrastructure code.
- Narrow the check to data stores only:

```yaml
# .inventag/templates/data-stores.yaml
format_version: 1
kind: tag-policy
name: data-stores
description: Classification on data stores only
extends: security-baseline
spec:
  scope:
    services: [S3, DYNAMODB, RDS]
```
