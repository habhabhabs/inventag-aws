---
title: Check tags against a policy
description: Check that your AWS resources carry the required tags with allowed values, using an InvenTag tag-policy template, and read the results.
sidebar_position: 4
slug: /architecture/tag-compliance
---

# Check tags against a policy

**Who this is for:** you own a tagging standard and want to know which
resources break it.

**What you can do after reading:** run a tag check, read the results, and
write your own policy.

## Run a check

Pick a built-in policy, or your own:

```bash
./inventag.sh --template finops-cost-allocation --create-excel --account-regions us-east-1
```

InvenTag scans as usual, then checks every resource in scope. Sample output
from an offline run with `--template finops-cost-report` (sample data):

<!-- BEGIN EXAMPLE OUTPUT: finops-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

<!-- END EXAMPLE OUTPUT: finops-console -->

## Read the results

| Where | What you get |
|---|---|
| Excel, **Tag Compliance** sheet | One row per resource in scope: account, region, service, type, resource, ARN, status, missing tags and other problems. Non-compliant rows come first. Below the table, each rule with how many resources miss it or have a wrong value. |
| Excel, **Summary** sheet | Counts: checked, compliant, non-compliant, out of scope, percentage. |
| Word, **Tag compliance** section | The same counts, the rules, and a table of non-compliant resources (up to 100 rows by default). |
| `tag_compliance_<timestamp>.json` | Counts per rule and every non-compliant resource, for scripts and CI. |

A resource is **compliant** when it has every required tag and every value
passes its rule. Problems are spelled out, for example:

- `CostCenter: '1234' does not match CC-[0-9]{4}` (wrong format)
- `Environment: 'Production' is not one of prod, staging, dev, test, sandbox`
- `Owner: found 'owner' instead (tag keys are case-sensitive)`

The Tag Compliance sheet in the same sample:

<!-- BEGIN EXAMPLE OUTPUT: finops-excel-compliance -->

**Sheets:** `Summary`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Tag Compliance`

`Tag Compliance` sheet, first rows:

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | acme-orders | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | us-east-1 | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

<!-- END EXAMPLE OUTPUT: finops-excel-compliance -->

The Word section:

<!-- BEGIN EXAMPLE OUTPUT: finops-word -->

**Document outline:**

- **Cost Allocation Tag Report** (title)
- Summary
- Tag compliance
  - Required tags
  - Non-compliant resources
- Resources by service
- About this report

A table from the document:

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| CostCenter | Matches: CC-[0-9]&#123;4&#125; | 19 | 1 |
| Owner | Any value | 18 | 0 |
| Project | Any value | 20 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 18 | 1 |

<!-- END EXAMPLE OUTPUT: finops-word -->

The `summary` part of the JSON file:

<!-- BEGIN EXAMPLE OUTPUT: finops-json-summary -->

```json title="summary"
{
  "checked": 22,
  "compliant": 1,
  "non_compliant": 21,
  "out_of_scope": 14,
  "percent_compliant": 4.5,
  "missing_by_key": {
    "CostCenter": 19,
    "Owner": 18,
    "Project": 20,
    "Environment": 18
  },
  "invalid_by_key": {
    "CostCenter": 1,
    "Owner": 0,
    "Project": 0,
    "Environment": 1
  }
}
```

<!-- END EXAMPLE OUTPUT: finops-json-summary -->

**Out of scope** resources are counted but not checked: the policy's `scope`
excludes them, for example KMS aliases, which cannot carry tags.

**Know this before you trust the numbers:** InvenTag matches tags from the
Resource Groups Tagging API to resources by ARN. For Lambda, RDS, DynamoDB,
SQS and SNS, the ARN InvenTag builds differs from the real one in our offline
tests, so their tags are not matched and they are reported as missing tags
even when they have them (in the sample above, the DynamoDB table). See
[Tags and ARNs](../getting-started/status.md#tags-and-arns).

## Write your own policy

Start from a built-in one and change only what differs:

```bash
./inventag.sh templates init finops-cost-allocation --output .inventag/templates/our-tags.yaml --extend
```

```yaml
format_version: 1
kind: tag-policy
name: our-tags
description: Our cost-allocation tags
extends: finops-cost-allocation
spec:
  required_tags:
    - key: Environment                 # replaces the inherited rule
      allowed_values: [production, staging, development]
    - key: Project                     # drops an inherited tag
      remove: true
    - key: DataClassification          # adds a new one
      allowed_values: [public, internal, confidential]
  scope:
    services: [EC2, S3, RDS, LAMBDA]   # only check these services
```

Rules for each tag:

- `allowed_values`: the value must be one of these. Case does not matter
  unless you set `case_sensitive: true`.
- `pattern`: the whole value must match this regular expression.
- Neither: any value is fine, as long as the tag exists.

Use either `allowed_values` or `pattern` for a tag, not both. All fields are
in the [template reference](../templates/reference.md).

## Fail a pipeline on violations

Add a config template with `fail_on_tag_violations: true`. InvenTag still
writes every report, then exits with code 3. See
[Enforce a tag policy in CI](../examples/tag-policy-in-ci.md).

## The older checker script

`scripts/legacy/tag_compliance_checker.py --config policy.yaml` predates
templates and has its own options (`--help` lists them). It is not covered by
this documentation. Prefer tag-policy templates.

## Next steps

- [Built-in tag policies](../templates/catalogue.md#tag-policy-templates)
- [Example: FinOps cost-allocation tags](../examples/finops-cost-allocation.md)
