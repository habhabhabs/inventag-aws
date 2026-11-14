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
everything an accounts file does, except that it cannot hold access keys
and each account needs `profile_name` or `role_arn`. It is validated more strictly, so prefer it for new setups.

All files can be YAML (`.yaml`, `.yml`) or JSON (`.json`). Check them without
scanning:

```bash
inventag --accounts-file accounts.yaml --tag-mappings tags.yaml \
  --validate-config-only --skip-credential-validation
```

This reads the files and makes no AWS call.

InvenTag reads these files as UTF-8, with or without a byte order mark. An
empty file, a key written twice or a top level that is not a mapping stops the
run with exit code 1 and a message that names the file.

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

An account can name one way to get credentials. An account with none uses your current credentials if they belong to that account; otherwise InvenTag tries to assume the role `InvenTagCrossAccountRole` (or the name given with `--cross-account-role`) in it.

| Field | Use |
|---|---|
| `profile_name` | An AWS CLI profile, for example an IAM Identity Center profile. |
| `role_arn` | A role InvenTag assumes from your current credentials. |
| `access_key_id` and `secret_access_key` (and optional `session_token`) | Keys written in the file. Avoid: anyone who can read the file has the keys. InvenTag warns when other users can read such a file. |

Values in `settings` override the matching command-line flags.

To use the same role name in every account, leave out `role_arn` and add
`--cross-account-role InvenTagReadOnly` to the command.

A broken accounts file stops the run before scanning. For example, an
unquoted account ID (sample data):

<!-- BEGIN EXAMPLE OUTPUT: error-bad-accounts -->

```text title="Output"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
```

```bash title="Terminal"
echo $?
```

```text title="Output"
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

The column appears in the default workbook (no `--template`). With
`--template` it does not appear, and a warning says so: use `tag_columns` in
the report template instead. With a layout file (`--excel-template`, `--word-template`), add the
column name to `extra_fields`.

Use the top-level key `tag_mappings` with a **list** of entries. InvenTag also
accepts the older layout, which uses each tag key as a top-level key with a
`column_name` value.

## Service descriptions

Used with `--service-descriptions`. It adds the `service_description` column
to the report. Without a file, InvenTag writes a built-in description, for
example `Amazon EC2 Instance (i-0abc1234def567890) in us-east-1`.

```yaml
service_descriptions:
  DYNAMODB:
    default:
      description: Application data table
  EC2:
    Volume:
      description: Block storage
      template: volume_text       # optional: a text with variables
templates:
  volume_text:
    template: "Disk {resource_id} in {region}"
```

The top-level key `service_descriptions` is required. Under each service,
each resource type (or `default`) needs a `description`. InvenTag does not check this when you validate or start a run. A file without the key is ignored, with an error in the log, and the built-in descriptions are used.

**Your entry replaces the built-in description**, for every service. An
entry with a `template` uses that template, defined under `templates`; an
entry without one uses its `description` as written (in the example,
`Application data table` for DynamoDB tables). A template can use
`{resource_id}`, `{resource_type}`, `{service}`, `{region}` and
`{account_id}`. Services with no entry in your file keep the built-in text.

If a template cannot be filled in, InvenTag logs a warning such as
`Failed to render template vpc_vpc: 'cidr_block'` and uses the built-in fallback text. For a template in your own file, it uses that entry's `description`.

## BOM processing configuration

Used with `--bom-config`. A YAML or JSON mapping whose keys are fields of the
BOM processing configuration, for example:

```yaml
enable_network_analysis: false
enable_parallel_processing: true
max_worker_threads: 4
```

Unknown keys are ignored with a warning that names them, so check the log for a
mistyped key. A value of the wrong type stops the run with exit code 1 and
names the key.
For example, `enable_network_analysis: true` adds the same sheet as
`--enable-network-analysis`. This file is for advanced tuning; most people never
need it.

## Next steps

- [Template reference](../templates/reference.md)
- [Scan several accounts](../guides/scan-multiple-accounts.md)
