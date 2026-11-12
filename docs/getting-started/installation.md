---
title: Installation
description: Install InvenTag, set up AWS credentials and a read-only IAM policy.
sidebar_position: 2
---

# Installation

## Requirements

- **Python 3.11 or later.** CI tests Python 3.11, 3.12, 3.13 and 3.14.
- **Git**, to clone the repository.
- **AWS credentials** that boto3 can find. The AWS CLI is optional but the
  easiest way to set them up.

InvenTag is not published to PyPI; install it from the repository.

## Install from GitHub

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws

python3 -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

pip install -r requirements.txt
./inventag.sh --help             # Windows: inventag.bat --help
```

`inventag.sh` / `inventag.bat` look for a Python 3 interpreter and run
`inventag_cli.py`. You can also call it directly: `python3 inventag_cli.py --help`.

To pin a release instead of `main`, check out a tag, for example `git checkout v4.2.27`
([releases](https://github.com/habhabhabs/inventag-aws/releases)).

## AWS credentials

InvenTag uses the standard boto3 credential chain, so any of these work:

```bash
aws configure                    # long-lived keys in ~/.aws/credentials
aws sso login --profile my-sso   # IAM Identity Center; then export AWS_PROFILE=my-sso
export AWS_PROFILE=readonly      # any named profile
```

Prefer short-lived credentials (SSO or an assumed role) over access keys.
Then check them:

```bash
./inventag.sh --validate-credentials
```

## IAM permissions

Give InvenTag a **read-only** identity. The CLI has a read-only guard that
blocks each AWS API call that is not a read operation. The IAM policy is the
first layer of protection, and the guard is the second layer
([details](../user-guides/production-safety.md)).

### Option 1: the shipped least-privilege policy

Use `config/defaults/iam-policy-read-only.json`. This policy has three
statements:

| Statement ID | Content |
|---|---|
| `InvenTagReadOnlyDiscovery` | 106 read actions, each listed by name. No wildcard action. Includes `tag:GetResources`, `ce:GetCostAndUsage` and `pricing:GetProducts`. |
| `InvenTagApiGatewayMetadata` | `apigateway:GET` on REST APIs, domain names and usage plans only. |
| `OptionalS3ReportUpload` | `s3:PutObject` on `arn:aws:s3:::YOUR-REPORTS-BUCKET-NAME/bom-reports/*`, only with server-side encryption. |

If you use `--s3-bucket`, replace `YOUR-REPORTS-BUCKET-NAME` with the name of
your bucket. If you do not use `--s3-bucket`, remove the
`OptionalS3ReportUpload` statement.

The policy does not include `sts:AssumeRole`. If you use
`--cross-account-role`, give `sts:AssumeRole` to the identity that starts the
scan.

Discovery of a service that is not in the policy fails with `AccessDenied`.
The CLI then continues with the next service.

### Option 2: the AWS managed policy

Use the AWS managed `ReadOnlyAccess` policy **plus** this small policy for the
Tagging API and Cost Explorer. This option gives more permissions than
Option 1:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvenTagExtras",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "ce:GetCostAndUsage",
        "ec2:DescribeRegions",
        "pricing:GetProducts"
      ],
      "Resource": "*"
    }
  ]
}
```

- `tag:GetResources`: the Resource Groups Tagging API (IAM prefix `tag`).
- `ce:GetCostAndUsage`: finds services with spend. **AWS bills each request.**
  If you use `--no-billing-validation`, discovery does not use this action.
- `ec2:DescribeRegions`: region auto-discovery.
- `pricing:GetProducts`: only used by `--enable-cost-analysis`.

If you use `--s3-bucket`, also give `s3:PutObject` on the reports bucket to
the default credentials.

### IAM Identity Center (SSO)

Create a permission set with the `ReadOnlyAccess` managed policy and add the
JSON above as an inline policy, then assign it to the accounts you want to
scan. Console: *IAM Identity Center → Permission sets → Create*. CLI:

```bash
aws sso-admin create-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --name InvenTagReadOnly \
  --description "Read-only access for InvenTag"

aws sso-admin attach-managed-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

aws sso-admin put-inline-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --inline-policy file://inventag-extras.json
```

## Development install

```bash
pip install -r requirements.txt -r requirements-dev.txt
python3 -m pytest tests
```

See [Current status](./status.md#tests) for the state of the test suite.

## Troubleshooting

| Symptom | Try |
|---|---|
| `No suitable Python interpreter found` | Install Python 3.11 or later and make sure that `python3 --version` works |
| `Permission denied: ./inventag.sh` | `chmod +x inventag.sh` |
| `Unable to locate credentials` | `aws sts get-caller-identity`; set `AWS_PROFILE` or log in with `aws sso login` |
| `AccessDenied` for `ce:GetCostAndUsage` | Add the action to the policy, or add `--no-billing-validation`. Discovery continues without billing data. |
| `ModuleNotFoundError` | Activate the virtualenv and re-run `pip install -r requirements.txt` |

More: [Troubleshooting guide](../user-guides/troubleshooting-guide.md).

## Next

[Quick start](./quick-start.md)
