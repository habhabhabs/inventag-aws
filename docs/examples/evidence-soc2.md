---
title: "Example: check tag evidence before a SOC 2 scoping conversation"
description: Find AWS resources with no recorded SOC 2 scope, system name, provisioning method or criticality tag, with InvenTag's evidence-soc2 tag-policy template.
sidebar_position: 10
---

# Example: check tag evidence before a SOC 2 scoping conversation

:::note

This checks tag evidence only. Tag values are stated by the resource owner and
InvenTag does not verify them. A passing result does not mean the account
meets SOC 2.

:::

**Goal:** before you talk to an auditor or a customer about which systems are
in scope for SOC 2, list the resources that have no recorded scope, system
name, provisioning method or criticality.

**You need:** read-only credentials. InvenTag reads tags; it does not assess
controls.

## Template

The built-in `evidence-soc2` tag policy starts from `security-baseline`
(`Owner`, `Environment` and `DataClassification`) and adds four tags:

| Tag key | Rule |
|---|---|
| `Soc2Scope` | `in-scope` or `out-of-scope` |
| `SystemName` | Any text that is not empty |
| `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual` or `other` |
| `Criticality` | `high`, `medium` or `low` |

It covers every resource type except KMS aliases. See the
[template catalogue](../templates/catalogue.md#evidence-soc2) for what it can
and cannot show.

## Command

```bash title="Terminal"
inventag --template evidence-soc2 --create-excel --account-regions us-east-1
```

## Output

The sample account has four buckets, a DynamoDB table and a queue, tagged in
different ways, plus the default resources every account has.

<!-- BEGIN EXAMPLE OUTPUT: evidence-soc2-console -->

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'evidence-soc2': 2 of 18 resources compliant (11.1%), 16 non-compliant, 14 out of scope.
```

<!-- END EXAMPLE OUTPUT: evidence-soc2-console -->

The 14 resources out of scope are KMS aliases. Of the 16 resources that are
missing something, 12 are default resources nobody tagged (the default VPC
with its subnets, route table, network ACL and security group, an Athena
workgroup and the default event bus). The status column only says whether the
resource has every tag in the template with an allowed value.

<!-- BEGIN EXAMPLE OUTPUT: evidence-soc2-excel -->

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EVENTS`, `KMS`, `S3`, `SQS`, `VPC`, `Tag Compliance`

`Tag Compliance` sheet, first rows:

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | arn:aws:s3:::acme-data-lake | Non-compliant | Criticality |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-reports | arn:aws:s3:::acme-reports | Non-compliant |  | Soc2Scope: 'yes' is not one of in-scope, out-... |
| 123456789012 | us-east-1 | S3 | Bucket | acme-scratch | arn:aws:s3:::acme-scratch | Non-compliant | Owner, Environment, DataClassification, Soc2S... |  |
| 123456789012 | us-east-1 | SQS | Queue | acme-jobs | arn:aws:sqs:us-east-1:123456789012:acme-jobs | Non-compliant | DataClassification, Soc2Scope, SystemName, Cr... |  |
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Compliant |  |  |
| 123456789012 | us-east-1 | S3 | Bucket | acme-app-logs | arn:aws:s3:::acme-app-logs | Compliant |  |  |

<!-- END EXAMPLE OUTPUT: evidence-soc2-excel -->

What the rows say:

- `acme-data-lake` has no `Criticality` tag.
- `acme-reports` has `Soc2Scope` set to `yes`, which is not one of the allowed
  values.
- `acme-scratch` has no tags.
- `acme-jobs` has `Owner`, `Environment` and `ManagedBy`, but no
  `DataClassification`, `Soc2Scope`, `SystemName` or `Criticality`.
- `acme-app-logs` has every tag with an allowed value.
- `acme-orders` is marked `out-of-scope` by its owner and still has every tag.
  The check is that the answer is recorded, not what the answer is.

To see which tag is missing most often, read the summary in the JSON file:

<!-- BEGIN EXAMPLE OUTPUT: evidence-soc2-json -->

```json title="tag_compliance_20261112_090000.json (summary, two fields)"
{
  "missing_by_key": {
    "Owner": 13,
    "Environment": 13,
    "DataClassification": 14,
    "Soc2Scope": 14,
    "SystemName": 14,
    "ManagedBy": 13,
    "Criticality": 15
  },
  "invalid_by_key": {
    "Owner": 0,
    "Environment": 0,
    "DataClassification": 0,
    "Soc2Scope": 1,
    "SystemName": 0,
    "ManagedBy": 0,
    "Criticality": 0
  }
}
```

<!-- END EXAMPLE OUTPUT: evidence-soc2-json -->

## What this does not tell you

- It does not tell you that the scope is right, that a control exists or
  works, or what an auditor would test.
- It does not check that `ManagedBy` is true. Compare it with the
  `aws:cloudformation:*` tags AWS adds.
- A tag that is present only means the owner wrote something.

## Next steps

- Tag the default resources, or narrow the policy so they are not checked:
  copy `evidence-soc2` into your project and set `spec.scope.services`, as in
  [Security tagging review](./security-review.md#next-steps).
- Start in report-only mode in CI: [Enforce a tag policy in CI](./tag-policy-in-ci.md).
- Write your own rules: [Check tags against a policy](../guides/check-tag-compliance.md#write-your-own-policy).
