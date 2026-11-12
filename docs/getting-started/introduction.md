---
title: Introduction
description: What InvenTag does, how a run works, and what it is not.
sidebar_position: 0
---

# Introduction

InvenTag answers three questions about your AWS estate:

1. **What is there?** An inventory of resources across accounts and regions.
2. **Is it tagged properly?** Tag columns in the report, plus a tag-policy
   checker for required tags and allowed values.
3. **What changed since last time?** Snapshots and change reports between runs.

The answer comes back as a bill of materials (BOM): an Excel workbook and/or a
Word document you can hand to someone who will never open the AWS console.

## How a run works

```text
credentials ─► discovery ─► enrichment ─► BOM processing ─► Excel / Word
 (profile,      Tagging API,   service       tag columns,      bom_output/
  keys, role)   List/Describe  attributes    descriptions,     + state/ snapshot
                /Get, Cost                                     + change report
                Explorer                                       + S3 upload (optional)
```

1. **Credentials.** The default AWS credential chain, a named profile, keys
   from an accounts file, or a role assumed with `--cross-account-role`.
2. **Discovery.** For each account and region: the Resource Groups Tagging API,
   per-service `List*`/`Describe*`/`Get*` calls, and Cost Explorer
   `GetCostAndUsage` to spot services that have spend but no tagged resources.
   Use `--no-billing-validation` to make no Cost Explorer request.
3. **Enrichment and processing.** Service-specific attributes, your tag
   mappings and service descriptions.
4. **Output.** `bom_output/multi_account_bom_<timestamp>.xlsx` / `.docx`, and
   a snapshot in `bom_output/state/` that the next run compares against.
   With `--s3-bucket`, the CLI also uploads the reports to Amazon S3.

## What it writes, and where

- Files in the output directory (default `bom_output/`). The CLI creates
  these files with mode `0600`.
- With `--s3-bucket`, encrypted copies of the reports in your S3 bucket.
- The CLI does **not** create, change or delete AWS resources during
  discovery. A read-only guard blocks each AWS API call that is not a read
  operation. Also use a read-only IAM policy:
  [Permissions and production safety](../user-guides/production-safety.md).
- AWS bills each Cost Explorer API request. The default is two requests for
  each account in each run.

## What it is not

- Not a compliance certification tool. The `--compliance-standard` flag is
  not implemented and stops the CLI with exit code `2`. InvenTag can collect
  evidence (an inventory, tag coverage). It does not assess SOC 2, PCI DSS,
  HIPAA or GDPR.
- Not affiliated with AWS.
- Not finished: [Current status and known limitations](./status.md) lists the
  flags that are not implemented and the known defects.

## Next

- [Installation](./installation.md)
- [Quick start](./quick-start.md)
- [CLI user guide](../user-guides/cli-user-guide.md)
