---
title: Installation
description: Install InvenTag, set up AWS credentials and a read-only IAM policy.
sidebar_position: 2
---

# Installation

## Requirements

- **Python 3.8+.** CI runs a version matrix; day-to-day development happens on
  current Python 3 releases.
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

`inventag.sh` / `inventag.bat` look for a Python 3.8+ interpreter and run
`inventag_cli.py`. You can also call it directly: `python3 inventag_cli.py --help`.

To pin a release instead of `main`, check out a tag, e.g. `git checkout v4.2.26`
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

Give InvenTag a **read-only** identity. Nothing in the CLI enforces read-only
behaviour at runtime, so the IAM policy is your real safety net
([details](../user-guides/production-safety.md)).

The simplest setup is the AWS managed `ReadOnlyAccess` policy **plus** this
small policy for the two things it may not cover (the Tagging API and Cost
Explorer):

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
- `ce:GetCostAndUsage`: finds services with spend. **Billed per request by AWS.**
- `ec2:DescribeRegions`: region auto-discovery.
- `pricing:GetProducts`: only used by `--enable-cost-analysis`.

Without `ReadOnlyAccess`, discovery still runs but service-specific details
(e.g. S3 encryption, Lambda VPC config) come back empty where a `Describe*`
call is denied. The repo also ships a narrower example policy at
`config/defaults/iam-policy-read-only.json`; note that it does **not** include
`ce:GetCostAndUsage` or `pricing:GetProducts`.

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
| `No suitable Python interpreter found` | Install Python 3.8+ and make sure `python3 --version` works |
| `Permission denied: ./inventag.sh` | `chmod +x inventag.sh` |
| `Unable to locate credentials` | `aws sts get-caller-identity`; set `AWS_PROFILE` or log in with `aws sso login` |
| `AccessDenied` for `ce:GetCostAndUsage` | Add the extras policy above, or ignore: discovery continues without billing data |
| `ModuleNotFoundError` | Activate the virtualenv and re-run `pip install -r requirements.txt` |

More: [Troubleshooting guide](../user-guides/troubleshooting-guide.md).

## Next

[Quick start](./quick-start.md)
