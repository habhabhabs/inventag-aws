---
title: Quick start
description: Install InvenTag and generate your first AWS bill of materials.
sidebar_position: 1
---

# Quick start

About ten minutes, most of it waiting for discovery.

## 1. Prerequisites

- Python 3.11 or later (`python3 --version`)
- AWS credentials that boto3 can find: `aws configure`, `aws sso login`,
  a named profile or `AWS_*` environment variables. The AWS CLI itself is
  optional; it's just the easiest way to set credentials up.
- A **read-only** IAM policy: see
  [Permissions](../user-guides/production-safety.md#iam-permissions).

## 2. Install

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
./inventag.sh --help               # Windows: inventag.bat --help
```

Check that your credentials work before scanning anything:

```bash
./inventag.sh --validate-credentials
```

## 3. Your first report

```bash
./inventag.sh --create-excel --verbose
```

This scans every enabled region of the account your default credentials point
to. To keep the first run short, limit the regions:

```bash
./inventag.sh --create-excel --account-regions us-east-1,ap-southeast-1
```

You get:

| File | What it is |
|---|---|
| `bom_output/multi_account_bom_<YYYYMMDD_HHMMSS>.xlsx` | The workbook: summary sheet plus one sheet per service |
| `bom_output/state/state_<timestamp>.json` | Snapshot used to report changes on the next run |

Add `--create-word` for a `.docx` version, and `--output-directory reports/`
to write somewhere else.

:::note Cost Explorer
By default, discovery makes two Cost Explorer `GetCostAndUsage` requests for
each account. AWS bills each request. Add `--no-billing-validation` to make no
Cost Explorer request. See [Current status](./status.md#costs).
:::

## 4. Several accounts

Create `accounts.json`:

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production",
      "profile_name": "prod",
      "regions": ["us-east-1", "eu-west-1"]
    },
    {
      "account_id": "123456789013",
      "account_name": "Development",
      "profile_name": "dev",
      "regions": ["ap-southeast-1", "ap-northeast-1"]
    }
  ]
}
```

An empty or missing `regions` list means "all regions". Then:

```bash
./inventag.sh --accounts-file accounts.json --create-excel --create-word
```

Accounts run four at a time; change it with `--max-concurrent-accounts`.
More options (access keys, role ARNs, per-account services):
[Account setup](../examples/accounts-setup.md).

## 5. Your own tag columns and descriptions

Tag mappings turn tags into named report columns. The file needs a top-level
`tag_mappings` list:

```yaml
# tag-mappings.yaml
tag_mappings:
  - tag: "Owner"
    name: "Resource Owner"
  - tag: "CostCenter"
    name: "Cost Center"
  - tag: "Environment"
    name: "Environment"
```

Service descriptions need a top-level `service_descriptions` key:

```yaml
# service-descriptions.yaml
service_descriptions:
  EC2:
    default:
      description: "Virtual servers"
    Instance:
      description: "Virtual machine instances"
  S3:
    default:
      description: "Object storage"
```

```bash
./inventag.sh --create-excel \
  --tag-mappings tag-mappings.yaml \
  --service-descriptions service-descriptions.yaml
```

Complete examples ship with the repo:
`config/defaults/mappings/tag_to_column_mappings_example.yaml` and
`config/defaults/services/service_descriptions_example.yaml`.

:::caution Validation is looser than loading
`--validate-config` currently accepts some layouts (for example a mapping
without the `tag_mappings` key) that the report generator then ignores with an
error in the log. Stick to the layouts above.
:::

## 6. Upload the reports to Amazon S3

```bash
./inventag.sh --create-excel --s3-bucket my-reports-bucket
```

The CLI uploads each report with server-side encryption. The default
credentials must have `s3:PutObject` on the bucket. See
[Current status](./status.md#s3-upload).

## 7. Tag-policy check

The tag-policy checker is a separate script today:

```bash
python3 scripts/legacy/tag_compliance_checker.py \
  --config config/defaults/compliance/tag_compliance_policy_example.yaml \
  --format excel --output compliance_report
```

## Useful commands

```bash
./inventag.sh --help                                   # every flag
./inventag.sh --accounts-file accounts.json --validate-config
./inventag.sh --cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly --create-excel
./inventag.sh --accounts-file accounts.json --cross-account-role InvenTagReadOnly --create-excel
./inventag.sh --create-excel --log-file inventag.log --verbose
./inventag.sh --create-excel --audit-output audit.json   # list of the AWS API calls
./inventag.sh --validate-operations ec2:DescribeInstances s3:PutObject
```

`--debug` writes a detailed log. InvenTag removes secret keys and session
tokens from the log, but the log shows account IDs, ARNs and resource names.
Do not publish it: [details](./status.md#security-notes).

## Next steps

- [Current status and known limitations](./status.md)
- [CLI user guide](../user-guides/cli-user-guide.md)
- [Configuration examples](../user-guides/configuration-examples.md)
- [Troubleshooting](../user-guides/troubleshooting-guide.md)
