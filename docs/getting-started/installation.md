---
title: Install InvenTag
description: Install InvenTag into a Python virtual environment, connect your AWS credentials and check that everything works.
sidebar_position: 2
---

# Install InvenTag

**Who this is for:** anyone setting up InvenTag on a laptop, a server or a CI
runner.

**What you can do after reading:** run `inventag --help` and confirm that
InvenTag can reach your AWS account.

## What you need

- **Python 3.11 or later.** Python 3.10 stopped getting security fixes in
  October 2026. Check your version with `python3 --version`.
- **pip**, which comes with Python. (Git is only needed to install from source.)
- **AWS credentials** for a read-only identity. The
  [AWS Command Line Interface (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  is optional, but it is the easiest way to set them up.

## Install with pip (recommended)

InvenTag is published on the Python Package Index as
[`inventag-aws`](https://pypi.org/project/inventag-aws/). A virtual
environment is the tidy way to install it, but InvenTag does not need one. It
is an ordinary Python package. A virtual environment keeps its dependencies
(boto3, openpyxl and others) away from your other Python tools, and many
current systems (Debian, Ubuntu, Homebrew Python) refuse `pip install` into the
system Python with an "externally-managed-environment" error. The two options
that work on those systems are a virtual environment, or `pipx`:

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

This gives you the `inventag` command that these docs use. The report
templates are included in the package.

To upgrade, run `pip install --upgrade inventag-aws`. To install a specific
release, pin it, for example `pip install inventag-aws==%INVENTAG_VERSION%`. Prefer to keep it out of your
project environments? `pipx install inventag-aws` installs it into its own
hidden environment and puts the `inventag` command on your PATH, so you never
activate anything. If your system allows it, a plain `pip install inventag-aws`
into your user or system Python works too.

## Install from source

Use this if you want the newest unreleased code or you plan to change InvenTag.

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
inventag --help
```

`pip install -e .` installs the dependencies from `requirements.txt` and an
`inventag` command that runs your source checkout, so your code changes take
effect without a reinstall. You can also run `python inventag_cli.py --help`
directly after `pip install -r requirements.txt`.

To use a fixed release from source instead of the newest code, check out its tag, for
example `git checkout v%INVENTAG_VERSION%`. The
[releases page](https://github.com/habhabhabs/inventag-aws/releases) lists
every release.

## Connect your AWS credentials

InvenTag uses the standard AWS credential chain, so any of these work:

With IAM Identity Center (recommended):

```bash title="Terminal"
aws sso login --profile my-readonly
export AWS_PROFILE=my-readonly
```

With long-lived access keys (avoid if you can):

```bash title="Terminal"
aws configure
```

Prefer short-lived credentials, such as IAM Identity Center or an assumed
role, over access keys stored on disk.

## Check that it works

```bash title="Terminal"
inventag --validate-credentials --verbose
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

## Upgrade from v1.1.x

What you will notice after `pip install --upgrade inventag-aws`:

- **Secret values are masked.** Values of fields that often hold secrets,
  such as Lambda environment variables, become `***REDACTED***` in reports,
  snapshots and logs. The first run after the upgrade reports those resources
  as changed once. Reports and snapshots from earlier versions may still hold
  such values: delete or restrict them.
- **New columns.** Every service sheet has `source`, `sources` and
  `detail_level` columns. See [Output files](../reference/outputs.md).
- **More services and more API calls.** InvenTag lists 22 more services,
  which adds sheets, rows and calls. The repository policy has 17 more read
  actions; without them, those services are skipped with a warning. See
  [IAM permissions](../reference/iam-permissions.md).
- **Stricter files.** An empty settings file, a key written twice or a
  `--bom-config` value of the wrong type stops the run with exit code 1.
- **Conflicting options stop with exit code 2**, for example `--accounts-file`
  with `--accounts-prompt`, or `--s3-kms-key-id` without
  `--s3-encryption aws:kms`.
- **The time limit is per account**, counted from when its scan starts. An
  account that runs out of time keeps the resources it found and counts as
  failed.
- **The default exit codes are the same.** Codes 5 and 6 are new and only
  with `--fail-on-account-error` and `--fail-if-empty`.

The full list is in the
[changelog](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md).

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
| `inventag: command not found` | Activate the virtual environment where you ran `pip install inventag-aws`, or run `python -m pip show inventag-aws` to check it is installed. |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt` again. |
| `No AWS credentials found!` | Run `aws sso login` or `aws configure`, or set `AWS_PROFILE`. |

## Next step

[Quick start](./quick-start.md)
