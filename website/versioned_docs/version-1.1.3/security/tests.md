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

The suite has 1,389 tests (1,398 with the nine benchmarks). Every one of them uses
[moto](https://github.com/getmoto/moto), which imitates AWS in memory, so the
tests run offline and cost nothing. Nine performance benchmarks are kept out of
the normal run and start only when you ask for them.

CI runs the suite on Python 3.11, 3.12, 3.13, 3.14 and 3.15, plus lint,
integration and basic security jobs, on every push and pull request.

**No test runs against a real AWS account.** Where a result depends on how
real AWS behaves, [Feature status](../getting-started/status.md) says so.

## What each feature is tested with

Each row is checked offline against mocked AWS (moto), or against mocked Google
clients for the Google rows. The moto Resource Groups Tagging API is the
reference for ARNs and tags.

| Feature | Tests |
|---|---|
| Resources in one or more accounts, a failed account named in the report and run summary | `tests/integration/test_status_validation.py`, `tests/unit/test_cli_security.py` |
| Excel and Word reports, stable sheet and row order, tag columns | `tests/integration/test_status_validation.py`, `tests/unit/test_bom_converter.py` |
| Report templates, tag-policy checks, exit code 3 | `tests/integration/test_status_validation.py`, `tests/unit/templating/` |
| Filters (`--account-regions`, `--account-services`, `--account-tags`) on every path | `tests/integration/test_status_validation.py`, `tests/unit/test_global_services.py` |
| Real ARNs and tag matching for each service, no duplicates | `tests/unit/test_arn_and_tags.py` |
| Global services for `eu-west-1` alone, all regions and a list with `us-east-1` | `tests/unit/test_global_services.py` |
| Network and security sheets, `--risk-threshold` (exit code 4) | `tests/integration/test_status_validation.py` |
| `--enable-cost-analysis` and its sheet | `tests/integration/test_status_validation.py` |
| `--per-account-reports`, `--accounts-prompt`, `--credential-timeout`, `--disable-account-logging` | `tests/integration/test_status_validation.py` |
| `--bom-config` warning, `--validate-config-only` without AWS calls, one warning per denied service | `tests/integration/test_status_validation.py` |
| Change report between runs, snapshots | `tests/integration/test_status_validation.py`, `tests/unit/test_changelog_generator.py` |
| Read-only guard, audit, `--validate-operations`, S3 upload, private files | `tests/unit/test_cli_security.py`, `tests/unit/test_security_read_only_guard.py` |
| Redaction of secrets, including Google secrets | `tests/unit/test_security_redaction.py`, `tests/unit/test_google_output.py` |
| Google Sheets and Docs output (mocked Google clients) | `tests/unit/test_google_output.py` |

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
