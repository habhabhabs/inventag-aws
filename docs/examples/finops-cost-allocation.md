---
title: "Example: FinOps cost-allocation tags"
description: Find which AWS resources lack the CostCenter, Owner, Project and Environment tags that cost-allocation reports depend on, with InvenTag's finops-cost-report template.
sidebar_position: 5
---

# Example: FinOps cost-allocation tags

**Goal:** a report for the FinOps or finance team that shows, per resource,
whether the cost-allocation tags are there and valid.

**You need:** read-only credentials. Tags only show up in AWS cost reports
after you activate them as cost allocation tags in the AWS Billing and Cost
Management console. InvenTag shows which resources carry them; it does not
calculate costs.

## Template

`finops-cost-report` (a report template) shows CostCenter, Owner, Project and
Environment as fixed columns and turns on the `finops-cost-allocation` tag
policy:

| Tag key | Rule in `finops-cost-allocation` |
|---|---|
| `CostCenter` | `CC-` and four digits, for example `CC-1234` |
| `Owner` | Any value |
| `Project` | Any value |
| `Environment` | `prod`, `staging`, `dev`, `test` or `sandbox` |

If your cost centres look different, adapt the policy and keep the report:

```yaml
# .inventag/templates/our-cost-tags.yaml
format_version: 1
kind: tag-policy
name: our-cost-tags
description: Our cost centres are five-digit numbers
extends: finops-cost-allocation
spec:
  required_tags:
    - key: CostCenter
      pattern: "[0-9]{5}"
```

## Command

```bash
./inventag.sh --template finops-cost-report --create-excel --create-word --account-regions us-east-1
# with your own policy:
./inventag.sh --template finops-cost-report --template our-cost-tags --create-excel
```

## Expected output

Sample data from an offline run of the first command:

```text
Wrote bom_output/tag_compliance_20261112_130926.json
Wrote bom_output/multi_account_bom_20261112_130926.docx
Wrote bom_output/multi_account_bom_20261112_130926.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

The Tag Compliance sheet in the sample includes rows like these:

| Service | Type | Resource | Status | Missing tags | Problems |
|---|---|---|---|---|---|
| S3 | Bucket | acme-data-lake | Non-compliant | Project | |
| S3 | Bucket | acme-reports | Non-compliant | | CostCenter: '1234' does not match CC-[0-9]{4}; Environment: 'Production' is not one of prod, staging, dev, test, sandbox |
| S3 | Bucket | acme-app-logs | Compliant | | |

Below the table, the "Policy rules" block counts how many resources miss
each tag.

## Next steps

- Send the Word document to budget owners. Its Tag compliance section lists
  the non-compliant resources.
- Track progress weekly: [Run InvenTag in CI/CD](../guides/run-in-ci.md).
