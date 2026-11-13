<p align="center">
  <img src="https://raw.githubusercontent.com/habhabhabs/inventag-aws/main/website/static/img/logo-wordmark-readme.png" alt="InvenTag" width="331" height="96">
</p>

<p align="center">
  <strong>Find out what is running in your AWS accounts, check it is tagged properly, and hand over an Excel or Word bill of materials.</strong>
</p>

[![Automated Release](https://github.com/habhabhabs/inventag-aws/workflows/Automated%20Release/badge.svg)](https://github.com/habhabhabs/inventag-aws/actions)
[![Documentation](https://github.com/habhabhabs/inventag-aws/workflows/Documentation%20Deployment/badge.svg)](https://habhabhabs.github.io/inventag-aws/)
[![PyPI](https://img.shields.io/pypi/v/inventag-aws.svg)](https://pypi.org/project/inventag-aws/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/habhabhabs/inventag-aws/blob/main/LICENSE)

**Install:** `pip install inventag-aws` ([PyPI](https://pypi.org/project/inventag-aws/))  
**Docs:** <https://habhabhabs.github.io/inventag-aws/>

## Quick start

Install from [PyPI](https://pypi.org/project/inventag-aws/) with pip:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install inventag-aws

inventag --validate-credentials       # uses your current AWS credentials
inventag --create-excel --verbose     # -> bom_output/multi_account_bom_<timestamp>.xlsx
```

A virtual environment is optional. `pipx install inventag-aws` gives you the
same `inventag` command without activating anything, and plain
`pip install inventag-aws` works wherever your Python allows it (newer Linux and
Homebrew Pythons refuse system-wide installs). To upgrade later, run
`pip install --upgrade inventag-aws`. To work on the code
or run the newest unreleased version, install from source instead:

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
inventag --validate-credentials
```

Python 3.11 or later is required. Use a read-only IAM identity. By default, discovery made two
Cost Explorer requests for each account in our offline test, and AWS bills each
request. Add `--no-billing-validation` to make no Cost Explorer request.
Details:
[Installation](https://habhabhabs.github.io/inventag-aws/docs/getting-started/installation).

## What it does

- **Discovery** across accounts and regions through the Resource Groups Tagging
  API, per-service `List*`/`Describe*`/`Get*` calls (24 services have their own
  discovery code) and Cost Explorer billing data.
- **Bill of materials** as an Excel workbook (`--create-excel`) and/or Word
  document (`--create-word`), with your own tag columns (`--tag-mappings`) and
  service descriptions (`--service-descriptions`).
- **Templates** (`--template`, `inventag templates list`): built-in and your own
  report layouts, tag policies and run settings.
- **Layout files** (`--word-template`, `--excel-template`): a YAML or JSON
  file selects the title, the sections or sheets, the columns, and the header
  and footer text.
- **Several accounts** from a file (`--accounts-file`), interactively
  (`--accounts-prompt`) or through an assumed role (`--cross-account-role`),
  processed in parallel.
- **Change tracking**: each run saves a snapshot in `bom_output/state/`; from
  the second run on, InvenTag writes a change report (`changelog_<timestamp>.md`)
  of what was added, removed or changed.
- **Google Sheets and Docs** (`--create-google-sheets`, `--create-google-docs`;
  install `inventag-aws[google]`): the same Excel and Word reports as Google
  files, private unless you share them.
- **Global services** (IAM, S3 bucket list, CloudFront, Route 53) are read once
  per account from `us-east-1`, whichever regions you choose.
- **Upload to Amazon S3** (`--s3-bucket`) with server-side encryption.
- **Read-only guard**: the CLI blocks each AWS API call that is not a read
  operation. `--audit-output audit.json` writes a list of the calls.
- **Tag-policy checks** (required tags, allowed values) with a tag-policy
  template, for example `--template finops-cost-allocation`. Results go to a Tag
  Compliance sheet, a Word section and a JSON file, and a config template can
  fail a CI job (exit code 3).

### Limits

InvenTag has never been tested against a real AWS account; every test uses
mocked AWS. Google Sheets and Docs output has been tested only against mocked Google
clients. One failed account does not change the exit code, but the report
and the run summary name it. Read
[Current status and known limitations](https://habhabhabs.github.io/inventag-aws/docs/getting-started/status).

### Not implemented

These flags stop the CLI with an error message and exit code `2`:
`--compliance-standard` and `--disable-production-safety`. InvenTag does not certify
compliance with SOC 2 or other standards. For the full list, see
[Current status and known limitations](https://habhabhabs.github.io/inventag-aws/docs/getting-started/status).

## More examples

```bash
# Several accounts, Excel + Word, your own tag columns
inventag --accounts-file accounts.json \
  --create-excel --create-word \
  --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml \
  --service-descriptions config/defaults/services/service_descriptions_example.yaml

# Assume a read-only role (full role ARN)
inventag --cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --create-excel

# Assume the same role name in each account of accounts.json
inventag --accounts-file accounts.json --cross-account-role InvenTagReadOnly \
  --create-excel

# Upload the reports to S3 (server-side encrypted)
inventag --create-excel --s3-bucket my-reports-bucket

# Faster runs: fewer regions, more accounts in parallel
inventag --accounts-file accounts.json --create-excel \
  --account-regions us-east-1,ap-southeast-1 --max-concurrent-accounts 8
```

Every flag: [Command-line reference](https://habhabhabs.github.io/inventag-aws/docs/reference/cli).

## Documentation

| Section | Link |
|---|---|
| Quick start | [docs/getting-started/quick-start.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/getting-started/quick-start.md) |
| Current status and known limitations | [docs/getting-started/status.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/getting-started/status.md) |
| Choose what to scan | [docs/guides/run-a-scan.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/guides/run-a-scan.md) |
| Command-line reference | [docs/reference/cli.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/reference/cli.md) |
| Configuration files | [docs/reference/configuration-files.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/reference/configuration-files.md) |
| Templates | [docs/templates/index.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/templates/index.md) |
| Google Sheets and Docs output | [docs/guides/google-sheets-and-docs.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/guides/google-sheets-and-docs.md) |
| Read-only access and permissions | [docs/guides/read-only-access.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/guides/read-only-access.md) |
| Architecture | [docs/development/architecture.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/development/architecture.md) |
| Contributing | [docs/development/CONTRIBUTING.md](https://github.com/habhabhabs/inventag-aws/blob/main/docs/development/CONTRIBUTING.md) |

The same Markdown files are published as the documentation site (Docusaurus,
in `website/`). Brand assets (logo, favicon, social card) and the script that
regenerates them live in [`website/brand/`](https://github.com/habhabhabs/inventag-aws/blob/main/website/brand/README.md).

## Project layout

```text
inventag-aws/
├── inventag_cli.py              # CLI entry point (the `inventag` command runs it)
├── inventag/                    # Python package: cli, core, discovery, reporting, templating, state, security
├── scripts/legacy/              # standalone scripts (inventory, tag compliance, BOM converter)
├── config/                      # example configs, IAM policy, JSON schemas
├── examples/                    # account files and CI examples
├── docs/                        # documentation (Markdown)
├── website/                     # Docusaurus site, brand assets
└── tests/
```

## Support

- [Issues](https://github.com/habhabhabs/inventag-aws/issues): bugs and feature requests
- [Discussions](https://github.com/habhabhabs/inventag-aws/discussions): questions

## License

MIT. See [LICENSE](https://github.com/habhabhabs/inventag-aws/blob/main/LICENSE).

---

*AWS is a trademark of Amazon.com, Inc. or its affiliates. InvenTag is an
independent tool and is not affiliated with, endorsed by, or sponsored by
Amazon Web Services, Inc.*
