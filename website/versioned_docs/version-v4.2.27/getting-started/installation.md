---
title: Install InvenTag
description: Install InvenTag from GitHub into a Python virtual environment, connect your AWS credentials and check that everything works.
sidebar_position: 2
---

# Install InvenTag

**Who this is for:** anyone setting up InvenTag on a laptop, a server or a CI
runner.

**What you can do after reading:** run `./inventag.sh --help` and confirm that
InvenTag can see your AWS account.

## What you need

- **Python 3.11 or later.** Python 3.10 reached end of life in October 2026,
  so use a supported version. Check yours with `python3 --version`.
- **Git**, to download the code.
- **AWS credentials** for a read-only identity. The
  [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  is optional, but it is the easiest way to set them up.

InvenTag is not on PyPI. You install it from the GitHub repository.

## Download and install

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
./inventag.sh --help               # Windows: inventag.bat --help
```

`inventag.sh` and `inventag.bat` find a Python interpreter and run
`inventag_cli.py`. You can also run `python inventag_cli.py --help` directly.

To use a fixed release instead of the latest code, check out a tag, for
example `git checkout v4.2.27`. All releases are listed on the
[releases page](https://github.com/habhabhabs/inventag-aws/releases).

## Connect your AWS credentials

InvenTag uses the standard AWS credential chain, so any of these work:

```bash
aws sso login --profile my-readonly     # IAM Identity Center (recommended)
export AWS_PROFILE=my-readonly

aws configure                           # long-lived access keys (avoid if you can)
```

Prefer short-lived credentials, such as IAM Identity Center or an assumed
role, over access keys stored on disk.

## Check that it works

```bash
aws sts get-caller-identity
```

This prints the account ID and the identity ARN that InvenTag will use. If it
fails, fix your credentials before you run InvenTag.

InvenTag also checks your credentials at the start of every run and explains
the most likely cause when they fail, such as an expired SSO session.

:::note
`./inventag.sh --validate-credentials` currently reports every account as
invalid because of a bug, even when the credentials work. Use
`aws sts get-caller-identity` until it is fixed. See
[Feature status](./status.md).
:::

## Give InvenTag read-only permissions

Before your first real scan, give the identity a read-only policy:
[Set up read-only access](../guides/read-only-access.md).

## Install for development

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/unit/templating tests/integration/templating
```

The [Contributing guide](../development/CONTRIBUTING.md) explains the full test
suite and its current state.

## Fix install problems

| What you see | What to do |
|---|---|
| `No suitable Python interpreter found` | Install Python 3.11 or later and check that `python3 --version` works. |
| `Permission denied: ./inventag.sh` | Run `chmod +x inventag.sh`. |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt` again. |
| `Unable to locate credentials` | Run `aws sts get-caller-identity`. Set `AWS_PROFILE` or run `aws sso login`. |

More help: [Fix common problems](../guides/troubleshooting.md).

## Next step

[Generate your first report](./quick-start.md)
