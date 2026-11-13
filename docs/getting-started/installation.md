---
title: Install InvenTag
description: Install InvenTag from GitHub into a Python virtual environment, connect your AWS credentials and check that everything works.
sidebar_position: 2
---

# Install InvenTag

**Who this is for:** anyone setting up InvenTag on a laptop, a server or a CI
runner.

**What you can do after reading:** run `./inventag.sh --help` and confirm that
InvenTag can reach your AWS account.

## What you need

- **Python 3.11 or later.** Python 3.10 stopped getting security fixes in
  October 2026. Check your version with `python3 --version`.
- **Git**, to download the code.
- **AWS credentials** for a read-only identity. The
  [AWS Command Line Interface (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  is optional, but it is the easiest way to set them up.

InvenTag is not on PyPI (the Python Package Index) yet. The repository
builds a package named `inventag-aws`, but we found no published release, so
install it from the GitHub repository.

## Download and install

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
./inventag.sh --help               # Windows: inventag.bat --help
```

`inventag.sh` and `inventag.bat` look for Python 3.11 or later and run
`inventag_cli.py`. You can also run `python inventag_cli.py --help` directly.
If you want an `inventag` command on your path, run `pip install .` in the
cloned folder.

To use a fixed release instead of the newest code, check out its tag, for
example `git checkout v5.0.0`. The
[releases page](https://github.com/habhabhabs/inventag-aws/releases) lists
every release. Upgrading from v4? Read
[Upgrade from v4 to v5](./upgrade-to-v5.md) first.

## Connect your AWS credentials

InvenTag uses the standard AWS credential chain, so any of these work:

```bash title="Terminal"
aws sso login --profile my-readonly     # IAM Identity Center (recommended)
export AWS_PROFILE=my-readonly

aws configure                           # long-lived access keys (avoid if you can)
```

Prefer short-lived credentials, such as IAM Identity Center or an assumed
role, over access keys stored on disk.

## Check that it works

```bash title="Terminal"
./inventag.sh --validate-credentials --verbose
```

Exit code 0 means InvenTag could sign in. With `--verbose` you also see the
steps. Sample output from an offline run against mocked AWS (sample data):

<!-- BEGIN EXAMPLE OUTPUT: validate-credentials -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
$ echo $?
0
```

<!-- END EXAMPLE OUTPUT: validate-credentials -->

If the credentials don't work, InvenTag says why and suggests a fix. See
[Fix common problems](../guides/troubleshooting.md#credentials).

## Give InvenTag read-only permissions

Before your first real scan, give the identity a read-only policy:
[Set up read-only access](../guides/read-only-access.md).

## Install for development

```bash title="Terminal"
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

The [contributing guide](../development/CONTRIBUTING.md) explains the full test
suite.

## Fix install problems

| What you see | What to do |
|---|---|
| `Error: No suitable Python interpreter found.` or `InvenTag requires Python 3.11 or later` | Install Python 3.11 or later and check that `python3 --version` works. |
| `Permission denied: ./inventag.sh` | Run `chmod +x inventag.sh`. |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt` again. |
| `No AWS credentials found!` | Run `aws sso login` or `aws configure`, or set `AWS_PROFILE`. |

## Next step

[Generate your first report](./quick-start.md)
