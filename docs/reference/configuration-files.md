---
title: Configuration files
description: The file formats InvenTag reads - accounts files, tag mappings and service descriptions - with the fields the loaders actually accept.
sidebar_position: 2
slug: /user-guides/configuration-examples
---

# Configuration files

**Who this is for:** you write or check InvenTag's configuration files by hand.

**What you can do after reading:** write an accounts file, a tag mappings file
and a service descriptions file that the loaders accept.

For templates (report layouts, tag policies, run settings), see the
[Template reference](../templates/reference.md). A config template can do
everything an accounts file does except hold access keys, and it is
validated more strictly, so prefer it for new setups.

All files can be YAML (`.yaml`, `.yml`) or JSON (`.json`). Check them without
scanning:

```bash
./inventag.sh --accounts-file accounts.yaml --tag-mappings tags.yaml \
  --validate-config-only --skip-credential-validation
```

## Accounts file

Used with `--accounts-file`.

```yaml
accounts:
  - account_id: "123456789012"         # required, in quotes
    account_name: Production           # optional, shown in reports
    role_arn: arn:aws:iam::123456789012:role/InvenTagReadOnly
    external_id: optional-external-id  # only if the trust policy needs it
    regions: [us-east-1, eu-west-1]    # optional; empty = every enabled region
    services: []                       # optional; empty = all services
  - account_id: "210987654321"
    account_name: Development
    profile_name: dev-readonly         # an AWS CLI profile instead of a role
settings:                              # optional
  max_concurrent_accounts: 4
  account_processing_timeout: 1800     # seconds, at least 60
  output_directory: bom_output
```

Each account needs **one** way to get credentials:

| Field | Use |
|---|---|
| `profile_name` | An AWS CLI profile, for example an IAM Identity Center profile. |
| `role_arn` | A role InvenTag assumes from your current credentials. |
| `access_key_id` and `secret_access_key` (and optional `session_token`) | Keys written in the file. Avoid: anyone who can read the file has the keys. |

Values in `settings` override the matching command-line flags.

To use the same role name in every account, leave out `role_arn` and add
`--cross-account-role InvenTagReadOnly` to the command.

A broken accounts file stops the run before scanning. For example, an
unquoted account ID (sample data):

<!-- BEGIN EXAMPLE OUTPUT: error-bad-accounts -->

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - Invalid accounts configuration:
inventag.cli.main - ERROR -   - Account 1: 'account_id' must be a non-empty string
$ echo $?
1
```

<!-- END EXAMPLE OUTPUT: error-bad-accounts -->

Ready-made examples are in the repository's
[`examples/`](https://github.com/habhabhabs/inventag-aws/tree/main/examples)
folder, for example `accounts_cross_account_roles.json` and
`accounts_with_profiles.json`.

## Tag mappings

Used with `--tag-mappings`. Each entry adds one named column to the report.
The column shows the tag value, or the default value if the resource does not
have the tag.

```yaml
tag_mappings:
  - tag: CostCenter          # required: the tag key
    name: Cost Center        # required: the column name
    default_value: Unknown   # optional: shown when the tag is missing
    description: Budget that pays for the resource
    required: false
    case_sensitive: false
```

Use the top-level key `tag_mappings` with a **list** of entries. InvenTag also
accepts the older layout, which uses each tag key as a top-level key with a
`column_name` value.

Example result for the entry above, on the EC2 sheet:

| service | type | id | Cost Center |
|---|---|---|---|
| EC2 | Instance | i-0abc1234def567890 | CC-1042 |
| EC2 | Volume | vol-0abc1234def567890 | Unknown |

## Service descriptions

Used with `--service-descriptions`. It adds the `service_description` column
to the report, for example `Amazon EC2 Instance (i-0abc1234def567890) in us-east-1`.

```yaml
service_descriptions:
  S3:
    Bucket:
      description: Object storage bucket
  EC2:
    Volume:
      description: Block storage volume
    default:
      description: Amazon EC2 resource
```

The top-level key `service_descriptions` is required. Under each service,
each resource type (or `default`) needs a `description`.

## BOM processing configuration

Used with `--bom-config`. A YAML or JSON mapping whose keys are fields of the
BOM processing configuration, for example:

```yaml
enable_network_analysis: false
enable_parallel_processing: true
max_worker_threads: 4
```

Unknown keys are ignored. This file is for advanced tuning; most people never
need it.

## Next steps

- [Template reference](../templates/reference.md)
- [Scan several accounts](../guides/scan-multiple-accounts.md)
