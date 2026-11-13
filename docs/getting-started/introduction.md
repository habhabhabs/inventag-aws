---
title: What InvenTag is
description: What InvenTag does in one run - find AWS resources, check tags, write Excel and Word reports - what it writes, and what it is not.
sidebar_position: 1
---

# What InvenTag is

**Who this is for:** anyone deciding whether InvenTag fits their job.

**What you will know after reading:** what a run does, what it changes (only
files on your disk), and where its limits are.

## Three questions, one report

InvenTag answers three questions about your AWS accounts:

1. **What is there?** A list of resources across accounts and regions.
2. **Is it tagged properly?** Tag columns in the report and, with a
   [tag-policy template](../templates/index.md), a check of required tags and
   allowed values.
3. **What changed since last time?** Each run saves a snapshot so runs can be
   compared. See [Track changes between runs](../guides/track-changes.md).

The answer is a bill of materials (BOM): an Excel workbook, a Word document,
or both.

## How a run works

```text
your AWS credentials
        |
        v
  1. find resources   --> List/Describe/Get calls per service,
        |                 the Resource Groups Tagging API, Cost Explorer
        v
  2. tidy and enrich  --> service names, IDs, tags
        |
        v
  3. check tags       --> only when a tag policy is active
        |
        v
  4. write files      --> bom_output/*.xlsx, *.docx, state/ snapshot
```

1. **Credentials.** InvenTag uses the normal AWS credential chain: a profile,
   environment variables, an IAM Identity Center (SSO) session or an IAM role.
   It can also assume a role in other accounts.
2. **Discovery.** For each account and region it calls read-only AWS
   application programming interfaces (APIs). By default it also calls Cost
   Explorer `GetCostAndUsage` to spot services that have spend. AWS charges for
   Cost Explorer API requests; `--no-billing-validation` turns the calls off.
3. **Processing.** It standardises service names and IDs and collects tags.
4. **Output.** It writes files to the output folder (`bom_output/` by default)
   and a snapshot to `bom_output/state/`.

## What it changes

Only files on your disk. InvenTag reads your AWS accounts; it never changes
them.

A **read-only guard** checks every AWS call before it is sent. Calls that
are not reads (`List`, `Describe`, `Get` and similar) are blocked, and so are
reads that would return secrets or file contents, such as reading a secret
value or downloading an S3 object. You cannot switch the guard off.

Still give InvenTag a read-only IAM identity. Two independent safety nets are
better than one: [Set up read-only access](../guides/read-only-access.md).

## What it is not

- **Not a compliance tool.** InvenTag can collect evidence, such as an
  inventory and tag coverage. It does not assess or certify compliance with
  SOC 2, PCI DSS, HIPAA, GDPR or any other framework.
- **Not a cost-management tool.** It lists resources and tags, and does not
  track your bill. The optional `--enable-cost-analysis` flag adds a Cost
  Analysis sheet with estimated monthly costs from the AWS Pricing API. These
  are estimates only, not your invoice.
- **Not affiliated with AWS.**
- **Not complete.** It has its own discovery code for 46 AWS services, not
  every service, and it has never been tested against a real AWS account.
  [Feature status and known limitations](./status.md) lists the limits.

## Next steps

- [Install InvenTag](./installation.md)
- [Generate your first report](./quick-start.md)
