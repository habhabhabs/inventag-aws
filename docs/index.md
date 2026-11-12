---
title: InvenTag documentation
description: InvenTag is an open-source Python CLI that inventories AWS resources across accounts, checks tag compliance and writes Excel/Word bill-of-materials reports.
sidebar_position: 1
---

# InvenTag

![InvenTag](/img/logo-wordmark.svg#gh-light-mode-only)![InvenTag](/img/logo-wordmark-dark.svg#gh-dark-mode-only)

InvenTag is an open-source (MIT) Python command-line tool. Point it at one or
more AWS accounts and it will:

- **find your resources** through the Resource Groups Tagging API, per-service
  `List*`/`Describe*`/`Get*` calls and Cost Explorer billing data;
- **write a bill of materials (BOM)** as an Excel workbook and/or a Word
  document, with your own tag columns and service descriptions;
- **remember what it saw**, so the next run can tell you what was added,
  removed or changed;
- **upload the reports** to Amazon S3 with server-side encryption
  (`--s3-bucket`).

The CLI blocks each AWS API call that is not a read operation.

Tag-policy checks (required tags, allowed values) run through a separate
script today: see [Tag compliance](./architecture/tag-compliance.md).

:::info Before you rely on it
Some CLI flags are not implemented and stop the CLI with exit code `2`
(for example `--create-google-docs` and `--compliance-standard`).
For the full list, see
[Current status and known limitations](./getting-started/status.md).
:::

## Try it

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# uses your current AWS credentials (profile, env vars or SSO session)
./inventag.sh --create-excel --verbose
```

The workbook is written to `bom_output/multi_account_bom_<timestamp>.xlsx`.
Full walkthrough: [Quick start](./getting-started/quick-start.md).

## Where to go next

| If you want to… | Read |
|---|---|
| Install it and run your first report | [Installation](./getting-started/installation.md), [Quick start](./getting-started/quick-start.md) |
| Know what works today and what does not | [Current status and known limitations](./getting-started/status.md) |
| See every CLI flag | [CLI user guide](./user-guides/cli-user-guide.md) |
| Scan several accounts | [Account setup](./examples/accounts-setup.md) |
| Map tags to report columns | [Configuration examples](./user-guides/configuration-examples.md) |
| Set up IAM permissions safely | [Permissions and production safety](./user-guides/production-safety.md) |
| Fix an error | [Troubleshooting](./user-guides/troubleshooting-guide.md) |
| Understand the code | [Core module integration](./architecture/core-module-integration.md) |
| Contribute | [Contributing](./development/CONTRIBUTING.md) |

## Project layout

```text
inventag-aws/
├── inventag_cli.py              # CLI entry point
├── inventag.sh / inventag.bat   # wrappers that find a Python 3 interpreter
├── inventag/                    # Python package
│   ├── cli/                     # argument parsing, config validation, logging
│   ├── core/                    # multi-account orchestration, credentials
│   ├── discovery/               # resource discovery
│   ├── compliance/              # tag compliance and safety helpers
│   ├── reporting/               # Excel/Word/CSV builders
│   └── state/                   # snapshots, deltas, changelogs
├── scripts/legacy/              # standalone scripts (inventory, tag compliance, BOM converter)
├── config/                      # example configs, IAM policy, JSON schemas
├── examples/                    # account files and CI examples
├── docs/                        # these docs (also rendered on GitHub)
├── website/                     # Docusaurus site and brand assets
└── tests/
```

## Support

- [Issues](https://github.com/habhabhabs/inventag-aws/issues) for bugs and feature requests
- [Discussions](https://github.com/habhabhabs/inventag-aws/discussions) for questions

MIT licence: see [LICENSE](https://github.com/habhabhabs/inventag-aws/blob/main/LICENSE).

---

*AWS is a trademark of Amazon.com, Inc. or its affiliates. InvenTag is an
independent project and is not affiliated with, endorsed by, or sponsored by
Amazon Web Services.*
