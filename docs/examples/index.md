---
title: Examples
description: Copy-paste InvenTag recipes for common jobs, each with the command, the template and the output it produces - from a quick audit to S3 uploads on a schedule.
sidebar_position: 1
---

# Examples

**Who this is for:** you know the job you want done and want a recipe to
copy.

**What you get:** for each example, the goal, the template, the command, the
output it produces, and what to do next.

Every output on these pages comes from a real InvenTag run against mocked AWS
([moto](https://github.com/getmoto/moto)), not from a real account. It is
**sample data**: the accounts (such as `123456789012`) and the `acme-*`
resources are made up, and your names and counts will differ. The samples are
produced by `scripts/docs/generate_example_outputs.py`, so they match the
current code.

| Example | You will get |
|---|---|
| [Quick audit of one account](./quick-audit.md) | An Excel and Word inventory of the account you are signed in to |
| [Inventory every account in an organization](./accounts-setup.md) | One report across many accounts, through a read-only role in each |
| [Enforce a tag policy in CI](./tag-policy-in-ci.md) | A pipeline step that fails when resources break your tag rules |
| [FinOps cost-allocation tags](./finops-cost-allocation.md) | A report of which resources carry the tags your cost reports need |
| [Security tagging review](./security-review.md) | Owner, environment and data classification coverage |
| [Branded executive Word report](./branded-executive-report.md) | A short landscape Word report with your logo and colours |
| [Your own columns](./custom-columns.md) | A workbook with exactly the columns you choose, on one sheet |
| [Upload reports to S3 on a schedule](./scheduled-s3-upload.md) | Encrypted reports in an S3 bucket after every run |
| [Tag evidence before a SOC 2 scoping conversation](./evidence-soc2.md) | A list of resources with no recorded SOC 2 scope, system, provisioning method or criticality |

All examples assume you have [installed InvenTag](../getting-started/installation.md)
and are signed in with a [read-only identity](../guides/read-only-access.md).
