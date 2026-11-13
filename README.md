<p align="center">
  <img src="website/static/img/logo-wordmark.svg#gh-light-mode-only" alt="InvenTag" width="331" height="96">
  <img src="website/static/img/logo-wordmark-dark.svg#gh-dark-mode-only" alt="InvenTag" width="331" height="96">
</p>

<p align="center">
  <strong>Find out what is running in your AWS accounts, check it is tagged properly, and hand over an Excel or Word bill of materials.</strong>
</p>

[![Automated Release](https://github.com/habhabhabs/inventag-aws/workflows/Automated%20Release/badge.svg)](https://github.com/habhabhabs/inventag-aws/actions)
[![Documentation](https://github.com/habhabhabs/inventag-aws/workflows/Documentation%20Deployment/badge.svg)](https://habhabhabs.github.io/inventag-aws/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Docs:** <https://habhabhabs.github.io/inventag-aws/>

## Quick start

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

./inventag.sh --validate-credentials       # uses your current AWS credentials
./inventag.sh --create-excel --verbose     # -> bom_output/multi_account_bom_<timestamp>.xlsx
```

Python 3.11 or later is required. InvenTag is not on PyPI yet: install it from
this repository. Use a read-only IAM identity. By default, discovery made two
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
- **Templates** (`--template`, `./inventag.sh templates list`): built-in and your own
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
- **Upload to Amazon S3** (`--s3-bucket`) with server-side encryption.
- **Read-only guard**: the CLI blocks each AWS API call that is not a read
  operation. `--audit-output audit.json` writes a list of the calls.
- **Tag-policy checks** (required tags, allowed values) with a tag-policy
  template, for example `--template finops-cost-allocation`. Results go to a Tag
  Compliance sheet, a Word section and a JSON file, and a config template can
  fail a CI job (exit code 3).

### Limits

InvenTag has never been tested against a real AWS account; every test uses
mocked AWS. Global services (S3, IAM, CloudFront, Route 53) are scanned only if
`us-east-1` is among the regions. Tags on Lambda, RDS, DynamoDB, SQS and SNS
resources are not matched to the resource in our tests. One failed account does
not change the exit code. Read
[Current status and known limitations](https://habhabhabs.github.io/inventag-aws/docs/getting-started/status).

### Not implemented

These flags stop the CLI with an error message and exit code `2`:
`--create-google-docs`, `--per-account-reports`, `--compliance-standard`,
`--risk-threshold` and `--disable-production-safety`. InvenTag does not certify
compliance with SOC 2 or other standards. For the full list, see
[Current status and known limitations](https://habhabhabs.github.io/inventag-aws/docs/getting-started/status).

## More examples

```bash
# Several accounts, Excel + Word, your own tag columns
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml \
  --service-descriptions config/defaults/services/service_descriptions_example.yaml

# Assume a read-only role (full role ARN)
./inventag.sh --cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --create-excel

# Assume the same role name in each account of accounts.json
./inventag.sh --accounts-file accounts.json --cross-account-role InvenTagReadOnly \
  --create-excel

# Upload the reports to S3 (server-side encrypted)
./inventag.sh --create-excel --s3-bucket my-reports-bucket

# Faster runs: fewer regions, more accounts in parallel
./inventag.sh --accounts-file accounts.json --create-excel \
  --account-regions us-east-1,ap-southeast-1 --max-concurrent-accounts 8
```

Every flag: [Command-line reference](https://habhabhabs.github.io/inventag-aws/docs/reference/cli).

## Documentation

| Section | Link |
|---|---|
| Quick start | [docs/getting-started/quick-start.md](docs/getting-started/quick-start.md) |
| Current status and known limitations | [docs/getting-started/status.md](docs/getting-started/status.md) |
| Upgrade from v4 | [docs/getting-started/upgrade-to-v5.md](docs/getting-started/upgrade-to-v5.md) |
| Choose what to scan | [docs/guides/run-a-scan.md](docs/guides/run-a-scan.md) |
| Command-line reference | [docs/reference/cli.md](docs/reference/cli.md) |
| Configuration files | [docs/reference/configuration-files.md](docs/reference/configuration-files.md) |
| Templates | [docs/templates/index.md](docs/templates/index.md) |
| Read-only access and permissions | [docs/guides/read-only-access.md](docs/guides/read-only-access.md) |
| Architecture | [docs/development/architecture.md](docs/development/architecture.md) |
| Contributing | [docs/development/CONTRIBUTING.md](docs/development/CONTRIBUTING.md) |

The same Markdown files are published as the documentation site (Docusaurus,
in `website/`). Brand assets (logo, favicon, social card) and the script that
regenerates them live in [`website/brand/`](website/brand/README.md).

## Project layout

```text
inventag-aws/
├── inventag_cli.py              # CLI entry point (inventag.sh / inventag.bat wrap it)
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

MIT. See [LICENSE](LICENSE).

---

*AWS is a trademark of Amazon.com, Inc. or its affiliates. InvenTag is an
independent tool and is not affiliated with, endorsed by, or sponsored by
Amazon Web Services, Inc.*
