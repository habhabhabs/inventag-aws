---
title: Tag evidence templates
description: What the five evidence tag-policy templates check (SOC 2, HIPAA, PCI DSS, GDPR, PDPA), what they never claim, the tags and values they use, and how to copy one and change its scope.
sidebar_position: 6
---

# Tag evidence templates

**Who this is for:** you are preparing for a conversation about SOC 2, HIPAA,
PCI DSS, GDPR or PDPA and want to know which resources have no recorded
answer to the questions that conversation starts with.

**What you can do after reading:** pick the template for your framework, read
its results correctly, and copy it to fit your own tags and resource types.

## What they check

Each template is a tag policy. It checks that every resource in scope has the
tags the template lists, with a value from the allowed list or in the allowed
shape. That is all. The tags are the evidence: a record, written by the
resource owner, of scope, data type, retention or location.

The five templates are in the
[built-in catalogue](./catalogue.md#tag-evidence-templates). The whole set is
`evidence-soc2`, `evidence-hipaa`, `evidence-pci-dss`, `evidence-gdpr` and
`evidence-pdpa`.

## What they never claim

- They check tag evidence only. They do not assess controls, safeguards,
  segmentation, lawfulness or consent.
- Tag values are stated by the resource owner. InvenTag cannot verify them.
- A passing result does not mean the account meets SOC 2, HIPAA, PCI DSS, GDPR
  or PDPA. It means the tags are there.
- InvenTag is read-only. It reads tags and writes reports; it never changes a
  resource.

Every template says this in its description and in the header of its file.
Keep the sentence "Checks tag evidence only; certifies nothing." in the
description of any template you copy.

## The tags

All five also check the three tags from `security-baseline`: `Owner` (any
value), `Environment` (`prod`, `staging`, `dev`, `test`, `sandbox`) and
`DataClassification` (`public`, `internal`, `confidential`, `restricted`).
`evidence-hipaa` replaces the last rule and adds `phi`.

| Template | Tag key | Allowed values |
|---|---|---|
| `evidence-soc2` | `Soc2Scope` | `in-scope`, `out-of-scope` |
| | `SystemName` | Any text that is not empty |
| | `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual`, `other` |
| | `Criticality` | `high`, `medium`, `low` |
| `evidence-hipaa` | `PHI` | `yes`, `no` |
| | `DataClassification` | `public`, `internal`, `confidential`, `restricted`, `phi` |
| | `RetentionPeriod` | A number and `d` or `y`, or `indefinite` |
| `evidence-pci-dss` | `PciScope` | `cde`, `connected`, `out-of-scope` |
| | `CardholderData` | `stores`, `processes`, `transmits`, `none` (one value) |
| `evidence-gdpr` | `PersonalData` | `none`, `personal`, `special-category` |
| | `ProcessingRecord` | 1 to 64 letters, digits, `.`, `_` or `-` |
| | `DataResidency` | `eu`, `uk`, `other` |
| | `RetentionPeriod` | A number and `d` or `y`, or `indefinite` |
| `evidence-pdpa` | `PersonalData` | `none`, `personal`, `special-category` |
| | `Purpose` | Any text that is not empty |
| | `RetentionPeriod` | A number and `d` or `y`, or `indefinite` |
| | `DataLocation` | `sg`, `overseas` |

`evidence-gdpr` and `evidence-pdpa` use the same `PersonalData` key and the
same values. If you tag a resource for one, the tag already works for the
other. A run uses one template, so run the check twice to see both.

A tag value may contain letters, digits, spaces and `_ . : / = + - @`. The
values above all fit.

## Copy a template and change its scope

`evidence-soc2` looks at every resource type except KMS aliases. The other
four list the resource types they look at. The list belongs to the whole
template, so it also limits the `Owner`, `Environment` and `DataClassification`
checks. Resources of other types count as out of scope, not as failures.

To see exactly what a template checks, print it after inheritance:

```bash title="Terminal"
inventag templates show evidence-hipaa --resolved
```

To make your own copy that inherits everything:

```bash title="Terminal"
inventag templates init evidence-soc2 --output .inventag/templates/our-soc2.yaml --extend
```

To check fewer services, set `services` in your copy:

```yaml title=".inventag/templates/data-soc2.yaml"
format_version: 1
kind: tag-policy
name: data-soc2
description: SOC 2 tag evidence for data stores only. Checks tag evidence only; certifies nothing.
extends: evidence-soc2
spec:
  scope:
    services: [S3, DYNAMODB, SQS]
```

To check more resource types, copy the whole `resource_types` list from
`inventag templates show <name> --resolved` and add the type. A list in your
copy replaces the inherited list; it does not add to it. Use the value in the
Type column of your report for the new type.

Check a copy before you use it, then run it:

```bash title="Terminal"
inventag templates validate data-soc2
inventag --template data-soc2 --create-excel
```

## What the engine cannot express

- One tag-policy template per run.
- No "only if" rules. A resource tagged `PersonalData=none` still needs a
  `ProcessingRecord` tag, with the value `none`.
- No cross-checks between tags or against the resource's region. `PHI=no` with
  `DataClassification=phi` is not flagged, and neither is `DataResidency=eu` on
  a resource in another region.
- Patterns match the exact case: `7y` passes and `7Y` does not. Allowed-value
  lists ignore case.
- The pattern for `ProcessingRecord` only checks the shape of the ID. Change
  it to your own ID format in your copy.

## Next steps

- [Example: check tag evidence before a SOC 2 scoping conversation](../examples/evidence-soc2.md)
- [Adapt a template](./adapt-a-template.md)
- [Check tags against a policy](../guides/check-tag-compliance.md)
