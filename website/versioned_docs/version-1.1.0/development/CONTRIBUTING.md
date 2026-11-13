---
title: Contribute to InvenTag
description: Set up a development environment for InvenTag, run the tests and linters, build the docs site, and open a pull request.
sidebar_position: 1
---

# Contribute to InvenTag

**Who this is for:** you want to fix a bug, add a feature or improve the docs.

**What you can do after reading:** set up the code, run the checks the
project uses, and open a pull request that is easy to review.

## Before you start

1. Look for an existing [issue](https://github.com/habhabhabs/inventag-aws/issues).
   If there is none, open one and describe the change.
2. For a large change, wait for a maintainer's reply before you write a lot
   of code.

## Set up

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # includes moto
pip install -e .          # optional: gives you the `inventag` command
git checkout -b fix/short-description
```

Branch prefixes: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`.

## Run the checks

```bash
black --check scripts/ inventag/
flake8 scripts/ inventag/ --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

CI runs the same `black --check` and `flake8` commands, then the tests on
Python 3.11, 3.12, 3.13, 3.14 and 3.15. The full suite (`python -m pytest -q`) takes
about two minutes, passes on `main` (1315 passed, 9 performance benchmarks
deselected) and needs no AWS account: every test uses moto. A change must keep
it green. Run the benchmarks only on request: `python -m pytest -m performance`.
Run `pip-audit -r requirements.txt` when you change a dependency; CI fails on a
new advisory.

**Never run tests against a real AWS account by accident.** Unset
`AWS_PROFILE` and real keys, or use moto.

## Work on templates

- Built-in templates live in `inventag/templating/builtin/`. Each one needs a
  test in `tests/integration/templating/` that renders it.
- The template format is described once, in
  `inventag/templating/schema.py`. After changing it, regenerate the docs
  reference: `python -m inventag.templating.reference --write`. A unit test
  fails if you forget.
- The sample outputs on the docs pages come from
  `scripts/docs/generate_example_outputs.py`, which runs the real CLI against
  moto. After a change in behaviour, run `pip install pillow` and
  `python scripts/docs/generate_example_outputs.py`, and commit the result.
  `--check` tells you whether the pages are stale. The pictures need
  LibreOffice (`soffice`) and `pdftoppm`.

## Work on the docs

The docs are Markdown files in `docs/`, published with Docusaurus from
`website/`.

```bash
cd website
npm ci
npm run build          # fails on broken links and missing SEO metadata
npm run check:links    # checks links in the built site
npm run start          # local preview at http://localhost:3000/inventag-aws/
```

Writing rules:

- Every page has a unique `title` and `description` in its front matter and
  exactly one `#` heading.
- Open with who the page is for and what the reader will be able to do.
- Short sentences, active voice, plain words. Explain any jargon.
- Every command, flag and output must match the code. Run it before you write
  it down, and label sample output as sample data.
- No invented numbers, no superlatives, no claims of compliance or
  certification.
- Headings in order, tables with header rows, alt text on images, and no
  meaning carried by emoji or colour alone.

The sidebar is generated from the folders and each folder's
`_category_.json`.

## Commit and open a pull request

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(templates): add landscape option for Word reports
fix(discovery): include EC2 instances in comprehensive discovery
docs: explain tag policy scopes
```

In the pull request, say what changed, how you tested it, and which docs you
updated. Update [Feature status](../getting-started/status.md) when you fix or
add a feature.

## Next steps

- [How the code fits together](./architecture.md)
- [Security](../security/index.md)
