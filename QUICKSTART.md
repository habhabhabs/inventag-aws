# InvenTag quick start

The full, maintained version of this page is
[docs/getting-started/quick-start.md](docs/getting-started/quick-start.md)
(also on the [docs site](https://habhabhabs.github.io/inventag-aws/docs/getting-started/quick-start)).
The short version:

```bash
# 1. install (Python 3.8+)
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

- Use a **read-only** IAM identity: [IAM permissions](docs/getting-started/installation.md#iam-permissions).
- Discovery calls Cost Explorer, which AWS bills per request.
- `--s3-bucket`, `--create-google-docs` and the production-safety flags are
  accepted but do nothing yet: [Current status](docs/getting-started/status.md).
- On Windows use `inventag.bat` instead of `./inventag.sh`.
