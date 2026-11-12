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
                /Get, Cost                   network/security  + change report
                Explorer                     sheets (optional)
```

1. **Credentials.** The default AWS credential chain, a named profile, keys
   from an accounts file, or a role assumed with `--cross-account-role`.
2. **Discovery.** For each account and region: the Resource Groups Tagging API,
   per-service `List*`/`Describe*`/`Get*` calls, and Cost Explorer
   `GetCostAndUsage` to spot services that have spend but no tagged resources.
3. **Enrichment and processing.** Service-specific attributes, your tag
   mappings and service descriptions, optional network and security analysis.
4. **Output.** `bom_output/multi_account_bom_<timestamp>.xlsx` / `.docx`, and
   a snapshot in `bom_output/state/` that the next run compares against.

## What it writes, and where

- Files in the output directory (default `bom_output/`). That's it for the
  normal CLI run.
- It does **not** create, change or delete AWS resources during discovery. It
  also doesn't *enforce* that at runtime, so run it with a read-only IAM policy:
  [Permissions and production safety](../user-guides/production-safety.md).
- Cost Explorer API requests are billed by AWS.

## What it is not

- Not a compliance certification tool. Flags like `--compliance-standard soc2`
  are accepted but currently unused; InvenTag can collect evidence (an
  inventory, tag coverage), not assess SOC 2, PCI DSS, HIPAA or GDPR.
- Not affiliated with AWS.
- Not finished: [Current status and known limitations](./status.md) lists the
  flags that parse but do nothing yet.

## Next

- [Installation](./installation.md)
- [Quick start](./quick-start.md)
- [CLI user guide](../user-guides/cli-user-guide.md)
