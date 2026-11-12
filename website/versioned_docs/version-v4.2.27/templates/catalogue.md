---
title: Built-in templates
description: The eight templates that ship with InvenTag - three report layouts, two tag policies and three run configurations - and what each one produces.
sidebar_position: 2
---

# Built-in templates

**Who this is for:** anyone choosing a starting point.

**What you can do after reading:** pick the template that is closest to what
you need and know exactly what it will produce.

To print any of them, run `./inventag.sh templates show <name>`. To see the
result after inheritance and defaults, add `--resolved`.

## Report templates

| Name | Excel workbook | Word document |
|---|---|---|
| `standard-bom` | Summary sheet, then one sheet per service. Columns: Account, Region, Service, Type, Name, ID, ARN, then one column per tag key found on that sheet. Header row frozen, with filter buttons. | Cover, summary, resources by service, tag compliance (if a policy is active), one table per service (up to 50 rows each), about this report. |
| `executive-summary` | Summary sheet and one `Resources` sheet with every resource, no tag columns. | Cover, summary, resources by service, tag compliance (if a policy is active), about. No per-resource tables. |
| `finops-cost-report` | Like `standard-bom`, but the tag columns are fixed to CostCenter, Owner, Project and Environment, plus a Tag Compliance sheet. | Cover, summary, tag compliance, resources by service, about. |

`executive-summary` and `finops-cost-report` both `extends: standard-bom`, so
they only list what is different. `finops-cost-report` also turns on the
`finops-cost-allocation` tag policy.

The header colour in all three is dark blue (`1F3A5F`) with white text.

## Tag-policy templates

These are starting points. Change the keys and allowed values to match your
own tagging conventions before you enforce them.

### `finops-cost-allocation`

Checks the tags you need to split spend by team and project.

| Tag key | Rule |
|---|---|
| `CostCenter` | Must match `CC-` followed by four digits, for example `CC-1234` |
| `Owner` | Any value |
| `Project` | Any value |
| `Environment` | One of `prod`, `staging`, `dev`, `test`, `sandbox` (any case) |

KMS aliases are out of scope, because aliases cannot carry tags.

Tags only appear in AWS cost reports after you activate them as cost
allocation tags in the AWS Billing and Cost Management console. InvenTag
lists resources and tags; it does not calculate costs.

### `security-baseline`

Checks the tags that help during a security review or an incident: who owns
this, how sensitive is it, and is it production?

| Tag key | Rule |
|---|---|
| `Owner` | Any value |
| `Environment` | One of `prod`, `staging`, `dev`, `test`, `sandbox` (any case) |
| `DataClassification` | One of `public`, `internal`, `confidential`, `restricted` (any case) |

KMS aliases are out of scope. Passing this policy does not make anything
compliant with any security framework; it only tells you whether these tags
are present and valid.

## Config templates

| Name | Scans | Produces | Notes |
|---|---|---|---|
| `single-account` | The account of your current credentials, in `us-east-1` | Excel and Word, `standard-bom` layout | Change `regions` to the regions you use. |
| `org-multi-account` | Three example accounts, by assuming `InvenTagReadOnly` in each | Excel and Word, `standard-bom` layout, `finops-cost-allocation` policy | The account IDs are placeholders. InvenTag does not list your organization's accounts for you. |
| `ci-pipeline` | The account of the pipeline's credentials, in `us-east-1` | Excel and a tag-compliance JSON file | Exits with code 3 if a resource breaks the `finops-cost-allocation` policy. Scans accounts one at a time. |

`./inventag.sh templates validate org-multi-account` warns you while the
placeholder account IDs are still there.

## Sample output

These counts come from an offline run against mocked AWS (sample data), using
`./inventag.sh --template finops-cost-report --create-excel --create-word
--account-regions us-east-1`. Your numbers will differ.

```text
Wrote bom_output/tag_compliance_20261112_130926.json
Wrote bom_output/multi_account_bom_20261112_130926.docx
Wrote bom_output/multi_account_bom_20261112_130926.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

Workbook sheets: `Summary`, one sheet per service (`DYNAMODB`, `EC2`,
`EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC` in this sample), then
`Tag Compliance`.

## Next steps

- [Adapt a template](./adapt-a-template.md)
- [Template reference](./reference.md)
