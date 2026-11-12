---
title: Generate your first report
description: Scan one AWS account and region with InvenTag and open the Excel and Word bill-of-materials reports it writes, in about ten minutes.
sidebar_position: 3
---

# Generate your first report

**Who this is for:** you have [installed InvenTag](./installation.md) and have
read-only AWS credentials.

**What you can do after reading:** scan one account, open the Excel and Word
reports, and choose a nicer layout with a template.

## 1. Check which account you are in

```bash
aws sts get-caller-identity
```

InvenTag scans the account these credentials belong to.

## 2. Scan one region

Start small: one region is quick and cheap.

```bash
./inventag.sh --create-excel --create-word --account-regions us-east-1
```

- `--create-excel` and `--create-word` choose the files to write. Without
  either, you get Excel only.
- `--account-regions` limits the scan to the regions you list, separated by
  commas. Without it, InvenTag scans every region enabled in the account,
  which takes longer.

While it runs you see progress messages. At the end you see where the files
went. Sample output from an offline run against mocked AWS (sample data):

```text
WARNING -   - No account specification method provided. Using default AWS credentials.
Word document saved: bom_output/multi_account_bom_20261112_125543.docx
Data exported to bom_output/multi_account_bom_20261112_125543.xlsx
```

The warning only says that you did not name an account, so InvenTag used your
current credentials. Add `--verbose` to see each step.

## 3. Open the reports

| File | What is in it |
|---|---|
| `bom_output/multi_account_bom_<timestamp>.xlsx` | A Summary sheet with resource counts per service, then one sheet per service with every field InvenTag found |
| `bom_output/multi_account_bom_<timestamp>.docx` | A summary, a table of services, and up to 50 resources per service |
| `bom_output/state/` | A snapshot of this run, used to compare runs later |

## 4. Choose a layout with a template

The default workbook includes every raw field, which makes wide sheets. A
[report template](../templates/index.md) gives you readable columns, one
column per tag, frozen headers and filters:

```bash
./inventag.sh --template standard-bom --create-excel --create-word --account-regions us-east-1
```

```text
Wrote bom_output/multi_account_bom_20261112_130917.docx
Wrote bom_output/multi_account_bom_20261112_130917.xlsx
```

Want to know whether your resources carry the right tags? Add a tag policy:

```bash
./inventag.sh --template standard-bom --template finops-cost-allocation \
  --create-excel --account-regions us-east-1
```

```text
Tag policy 'finops-cost-allocation': 1 of 22 resources compliant (4.5%), 21 non-compliant, 14 out of scope.
```

The workbook now has a Tag Compliance sheet listing what is missing on each
resource.

## What it cost

Each run makes read-only API calls, which are free, plus Cost Explorer
`GetCostAndUsage` requests, which AWS charges per request. Check the current
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

## Next steps

- [Feature status and known limitations](./status.md): read this before you
  rely on a flag.
- [Choose what to scan and what to produce](../guides/run-a-scan.md)
- [Examples](../examples/index.md): copy-paste recipes.
