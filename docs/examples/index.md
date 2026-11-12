---
title: Examples
description: Copy-paste InvenTag recipes for common jobs - a quick audit, an organization-wide inventory, tag checks in CI, FinOps tags, branded reports and custom columns.
sidebar_position: 1
---

# Examples

**Who this is for:** you know the job you want done and want a recipe to
copy.

**What you get:** for each example, the goal, the template, the command, what
the output looks like, and what to do next.

Every sample output on these pages comes from a real InvenTag run against
mocked AWS ([moto](https://github.com/getmoto/moto)), not from a real account.
It is **sample data**: resource names, counts and timestamps will differ for
you. Long paths are shortened.

| Example | You will get |
|---|---|
| [Quick audit of one account](./quick-audit.md) | Excel and Word inventory of the account you are signed in to |
| [Inventory every account in an organization](./accounts-setup.md) | One report across many accounts, through a read-only role in each |
| [Enforce a tag policy in CI](./tag-policy-in-ci.md) | A pipeline that fails when resources break your tag rules |
| [FinOps cost-allocation tags](./finops-cost-allocation.md) | A report of which resources carry the tags your cost reports need |
| [Security tagging review](./security-review.md) | Owner, environment and data classification coverage for a review |
| [Branded executive Word report](./branded-executive-report.md) | A short landscape Word report with your logo and colours |
| [Your own columns](./custom-columns.md) | A workbook with exactly the columns you choose, on one sheet |

All examples assume you have [installed InvenTag](../getting-started/installation.md)
and are signed in with a [read-only identity](../guides/read-only-access.md).
