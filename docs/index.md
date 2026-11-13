---
title: InvenTag documentation
description: InvenTag is an open-source Python command-line tool that lists the resources in your AWS accounts, checks their tags and writes Excel and Word reports.
sidebar_position: 1
slug: /
---

# InvenTag documentation

InvenTag is a free, open-source (MIT) command-line tool written in Python.
You point it at one or more AWS accounts. It lists the resources it finds,
checks their tags, and writes the result as an Excel workbook and a Word
document that you can hand to someone who never opens the AWS console.

We call that list a **bill of materials (BOM)**: what you run, where it runs,
who owns it and how it is tagged.

![The InvenTag wordmark](/img/logo-wordmark.svg#gh-light-mode-only)![The InvenTag wordmark](/img/logo-wordmark-dark.svg#gh-dark-mode-only)

## Start here

| I want to... | Go to |
|---|---|
| Understand what InvenTag does and does not do | [What InvenTag is](./getting-started/introduction.md) |
| Install it | [Install InvenTag](./getting-started/installation.md) |
| Produce my first report in about ten minutes | [Generate your first report](./getting-started/quick-start.md) |
| Know which features work today | [Feature status and known limitations](./getting-started/status.md) |
| Upgrade from InvenTag v4 | [Upgrade from v4 to v5](./getting-started/upgrade-to-v5.md) |
| Reuse a report layout or a tag policy | [Templates](./templates/index.md) |
| Copy a ready-made recipe | [Examples](./examples/index.md) |
| Look up a flag, a file format or a permission | [Reference](./reference/cli.md) |
| Look up a word | [Glossary](./reference/glossary.md) |

## Try it

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./inventag.sh --template standard-bom --create-excel --account-regions us-east-1
```

InvenTag uses your current AWS credentials and writes the workbook to
`bom_output/`. Give it a read-only identity:
[Set up read-only access](./guides/read-only-access.md).

## Get help

- Report a bug or ask for a feature in
  [GitHub Issues](https://github.com/habhabhabs/inventag-aws/issues).
- Ask a question in
  [GitHub Discussions](https://github.com/habhabhabs/inventag-aws/discussions).
- Report a security problem as described on the [Security](./security/index.md)
  page.

InvenTag is released under the
[MIT licence](https://github.com/habhabhabs/inventag-aws/blob/main/LICENSE).

---

*AWS is a trademark of Amazon.com, Inc. or its affiliates. InvenTag is an
independent project and is not affiliated with, endorsed by, or sponsored by
Amazon Web Services.*
