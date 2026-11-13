---
title: Tests
description: How InvenTag is tested - what the suite covers, what it cannot prove, how to run it, and which Python versions CI runs it on.
sidebar_position: 2
---

# Tests

**Who this is for:** anyone deciding how far to trust InvenTag, and anyone
changing the code.

**What you will know after reading:** what the tests cover, what they do not,
and how to run them yourself.

## What runs, and where

The suite has about 1,300 tests. Every one of them uses
[moto](https://github.com/getmoto/moto), which imitates AWS in memory, so the
tests run offline and cost nothing. Nine performance benchmarks are kept out of
the normal run and start only when you ask for them.

CI runs the suite on Python 3.11, 3.12, 3.13, 3.14 and 3.15, plus lint,
integration and basic security jobs, on every push and pull request.

**No test runs against a real AWS account.** Where a result depends on how
real AWS behaves, [Feature status](../getting-started/status.md) says so.

## Run the tests yourself

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Run the benchmarks with `pytest -m performance`. Set up the full development
environment: [Contribute to InvenTag](../development/CONTRIBUTING.md).

## What else is checked

- **The documentation site** is built in CI. The build fails on a broken link,
  and an accessibility check runs on the built pages.
- **Dependencies** are scanned for known vulnerabilities. See
  [Security](./index.md#how-dependencies-are-checked) and the
  [software bill of materials](./sbom.md).
