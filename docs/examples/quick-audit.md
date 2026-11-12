---
title: "Example: quick audit of one account"
description: Produce an Excel and Word inventory of the AWS account you are signed in to with InvenTag's single-account config template.
sidebar_position: 2
---

# Example: quick audit of one account

**Goal:** a readable inventory of one account, in Excel and Word, in a few
minutes.

**You need:** credentials for the account, for example
`aws sso login --profile prod-readonly` and `export AWS_PROFILE=prod-readonly`.

## Template

The built-in `single-account` config template scans `us-east-1` and writes
both files with the `standard-bom` layout. Copy it and set your regions:

```bash
./inventag.sh templates init single-account --output .inventag/templates/audit.yaml
```

```yaml
format_version: 1
kind: config
name: audit
description: Scan the account of your current credentials and write Excel and Word reports.
spec:
  regions: [us-east-1, eu-west-1]   # the regions you use
  outputs: [excel, word]
  output_directory: bom_output
  report_template: standard-bom
```

## Command

```bash
./inventag.sh templates validate audit
./inventag.sh --template audit
```

## Expected output

Sample data from an offline run (one region):

```text
Wrote bom_output/multi_account_bom_20261112_130938.docx
Wrote bom_output/multi_account_bom_20261112_130938.xlsx
```

The workbook has a Summary sheet and one sheet per service. In the sample:
`DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`. The Summary
sheet starts like this:

| Service | Resources | Share |
|---|---|---|
| DYNAMODB | 1 | 2.8% |
| EC2 | 4 | 11.1% |
| KMS | 14 | 38.9% |
| S3 | 4 | 11.1% |
| VPC | 10 | 27.8% |

## Next steps

- Add a tag check: `./inventag.sh --template audit --template security-baseline`.
- Run it every week: [Run InvenTag in CI/CD](../guides/run-in-ci.md).
