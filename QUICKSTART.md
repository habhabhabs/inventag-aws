# InvenTag quick start

The full, maintained version of this page is
[docs/getting-started/quick-start.md](docs/getting-started/quick-start.md)
(also on the [docs site](https://habhabhabs.github.io/inventag-aws/docs/getting-started/quick-start)).
The short version:

```bash
# 1. install (Python 3.11 or later)
python3 -m venv .venv && source .venv/bin/activate
pip install inventag-aws

# 2. check credentials (any boto3 credential source: profile, SSO, env vars)
inventag --validate-credentials

# 3. first report, limited to two regions to keep it quick
inventag --create-excel --account-regions us-east-1,ap-southeast-1 --verbose
#    -> bom_output/multi_account_bom_<timestamp>.xlsx

# 4. several accounts
inventag --accounts-file accounts.json --create-excel --create-word
```

To run from a clone of the repository instead, use `git clone
https://github.com/habhabhabs/inventag-aws.git`, then `pip install -e .` inside it.

Before you rely on it:

- Use a **read-only** IAM identity: [Set up read-only access](docs/guides/read-only-access.md)
  and [IAM permissions](docs/reference/iam-permissions.md).
- By default, discovery made two Cost Explorer requests for each account in our
  offline test. AWS bills each request. Add `--no-billing-validation` to make no Cost
  Explorer request.
- `--compliance-standard` and `--disable-production-safety` are not implemented.
  The CLI stops with exit code `2` if you use one of them. See
  [Current status](docs/getting-started/status.md).
- The `inventag` command works the same on Linux, macOS and Windows.
