<p align="center">
  <img src="website/static/img/logo-wordmark.svg#gh-light-mode-only" alt="InvenTag" width="366" height="96">
  <img src="website/static/img/logo-wordmark-dark.svg#gh-dark-mode-only" alt="InvenTag" width="366" height="96">
</p>

<p align="center">
  <strong>Find out what is running in your AWS accounts, check it is tagged properly, and hand over an Excel or Word bill of materials.</strong>
</p>

[![Automated Release](https://github.com/habhabhabs/inventag-aws/workflows/Automated%20Release/badge.svg)](https://github.com/habhabhabs/inventag-aws/actions)
[![Documentation](https://github.com/habhabhabs/inventag-aws/workflows/Documentation%20Deployment/badge.svg)](https://habhabhabs.github.io/inventag-aws/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
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

Use a read-only IAM identity. Discovery calls Cost Explorer, which AWS bills per
request. Details: [Installation](https://habhabhabs.github.io/inventag-aws/docs/getting-started/installation).

## What it does

- **Discovery** across accounts and regions through the Resource Groups Tagging
  API, per-service `List*`/`Describe*`/`Get*` calls and Cost Explorer billing data.
- **Bill of materials** as an Excel workbook (`--create-excel`) and/or Word
  document (`--create-word`), with your own tag columns (`--tag-mappings`) and
  service descriptions (`--service-descriptions`).
- **Several accounts** from a file (`--accounts-file`), interactively
  (`--accounts-prompt`) or through an assumed role (`--cross-account-role`),
  processed in parallel.
- **Change tracking**: each run saves a snapshot in `bom_output/state/`; the
  next run reports what was added, removed or changed.
- **Optional sheets** for networks (`--enable-network-analysis`) and security
  groups (`--enable-security-analysis`).
- **Tag-policy checks** (required tags, allowed values) with
  `scripts/legacy/tag_compliance_checker.py --config policy.yaml`.

### Not there yet

Some flags are accepted but have no effect today: `--s3-bucket` (and the other
`--s3-*` flags), `--create-google-docs`, and the production-safety flags
(`--enforce-read-only`, `--compliance-standard`, `--audit-output`, …).
`--compliance-standard soc2` does not make anything SOC 2 compliant. The full
list is in [Current status and known limitations](https://habhabhabs.github.io/inventag-aws/docs/getting-started/status).

## More examples

```bash
# Several accounts, Excel + Word, your own tag columns
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml \
  --service-descriptions config/defaults/services/service_descriptions_example.yaml

# Assume a read-only role (pass the full role ARN; a bare role name fails today)
./inventag.sh --cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --create-excel --enable-network-analysis --enable-security-analysis

# Faster runs: fewer regions, more accounts in parallel
./inventag.sh --accounts-file accounts.json --create-excel \
  --account-regions us-east-1,ap-southeast-1 --max-concurrent-accounts 8
```

Every flag: [CLI user guide](https://habhabhabs.github.io/inventag-aws/docs/user-guides/cli-user-guide).

## Documentation

| Section | Link |
|---|---|
| Quick start | [docs/getting-started/quick-start.md](docs/getting-started/quick-start.md) |
| Current status and known limitations | [docs/getting-started/status.md](docs/getting-started/status.md) |
| CLI user guide | [docs/user-guides/cli-user-guide.md](docs/user-guides/cli-user-guide.md) |
| Configuration examples | [docs/user-guides/configuration-examples.md](docs/user-guides/configuration-examples.md) |
| Permissions and production safety | [docs/user-guides/production-safety.md](docs/user-guides/production-safety.md) |
| Architecture | [docs/architecture/core-module-integration.md](docs/architecture/core-module-integration.md) |
| Contributing | [docs/development/CONTRIBUTING.md](docs/development/CONTRIBUTING.md) |

The same Markdown files are published as the documentation site (Docusaurus,
in `website/`). Brand assets (logo, favicon, social card) and the script that
regenerates them live in [`website/brand/`](website/brand/README.md).

## Project layout

```text
inventag-aws/
├── inventag_cli.py              # CLI entry point (inventag.sh / inventag.bat wrap it)
├── inventag/                    # Python package: cli, core, discovery, compliance, reporting, state
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
