---
title: "Example: inventory every account in an organization"
description: Scan every account in an AWS Organization in one InvenTag run by assuming a read-only role in each, and get one consolidated report.
sidebar_position: 3
---

# Example: inventory every account in an organization

**Goal:** one report that covers all your accounts, with an Account column
and a tag check.

**You need:**

- a role with the same name (here `InvenTagReadOnly`) in every account, with a
  [read-only policy](../guides/read-only-access.md#with-an-iam-role-in-each-account);
- credentials for an identity that may assume those roles, for example in the
  management account or a delegated security account.

## Template

List your accounts:

```bash
aws organizations list-accounts --query "Accounts[?Status=='ACTIVE'].[Id,Name]" --output text
```

Copy the built-in template and replace the placeholder accounts:

```bash
./inventag.sh templates init org-multi-account --output .inventag/templates/our-org.yaml
```

```yaml
format_version: 1
kind: config
name: our-org
description: Every active account, read-only
spec:
  accounts:
    - account_id: "111111111111"
      account_name: Production
      role_arn: arn:aws:iam::111111111111:role/InvenTagReadOnly
    - account_id: "222222222222"
      account_name: Staging
      role_arn: arn:aws:iam::222222222222:role/InvenTagReadOnly
    - account_id: "333333333333"
      account_name: Shared services
      role_arn: arn:aws:iam::333333333333:role/InvenTagReadOnly
  regions: [us-east-1]
  outputs: [excel, word]
  report_template: standard-bom
  tag_policy: finops-cost-allocation
  max_concurrent_accounts: 4
```

## Command

```bash
./inventag.sh templates validate our-org
./inventag.sh --template our-org
```

While the placeholder IDs are still there, `validate` warns you:

```text
WARNING ~/acme-infra/.inventag/templates/our-org.yaml: account IDs 111111111111, 222222222222, 333333333333 look like placeholders; replace them with your own
```

## Expected output

Sample data from an offline run with the three placeholder accounts (the
mocked accounts only contain default resources):

```text
Wrote bom_output/tag_compliance_20261112_130944.json
Wrote bom_output/multi_account_bom_20261112_130944.docx
Wrote bom_output/multi_account_bom_20261112_130944.xlsx
Tag policy 'finops-cost-allocation': 0 of 33 resources compliant (0.0%), 33 non-compliant, 42 out of scope.
```

The Summary sheet says `Accounts: 3   Regions: 1`. Every resource row has its
account ID in the Account column, so you can filter by account.

## Next steps

- If an account fails, InvenTag logs the error and reports the others. Run
  with `--verbose` to see why, usually the role's trust policy.
- [Scan several accounts](../guides/scan-multiple-accounts.md) explains the
  tuning options.
