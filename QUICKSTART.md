# InvenTag quick start

The full, maintained version of this page is
[docs/getting-started/quick-start.md](docs/getting-started/quick-start.md)
(also on the [docs site](https://habhabhabs.github.io/inventag-aws/docs/getting-started/quick-start)).
The short version:

```bash
# 1. install (Python 3.11 or later)
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. check credentials (any boto3 credential source: profile, SSO, env vars)
./inventag.sh --validate-credentials

# 3. first report, limited to two regions to keep it quick
./inventag.sh --create-excel --account-regions us-east-1,ap-southeast-1 --verbose
#    -> bom_output/multi_account_bom_<timestamp>.xlsx

# 4. several accounts
./inventag.sh --accounts-file accounts.json --create-excel --create-word
```

Before you rely on it:

- Use a **read-only** IAM identity: [Set up read-only access](docs/guides/read-only-access.md)
  and [IAM permissions](docs/reference/iam-permissions.md).
- By default, discovery made two Cost Explorer requests for each account in our
  offline test. AWS bills each request. Add `--no-billing-validation` to make no Cost
  Explorer request.
- `--create-google-docs`, `--per-account-reports`, `--compliance-standard`,
  `--risk-threshold` and `--disable-production-safety` are not implemented.
  The CLI stops with exit code `2` if you use one of them. See
  [Current status](docs/getting-started/status.md).
- Keep `us-east-1` in `--account-regions`: S3, IAM, CloudFront and Route 53 are
  scanned only from there.
- On Windows use `inventag.bat` instead of `./inventag.sh`.
