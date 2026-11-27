---
title: Shipped policy sets
description: The six policy sets that ship with InvenTag, what each policy reads, which rules are not shipped and why.
sidebar_position: 8
---

# Shipped policy sets

**Who this is for:** you want to check a snapshot now, or you want a starting
point for your own policies.

**What you can do after reading:** pick a shipped set, know exactly which
fields it reads, and know which rules InvenTag does not ship and why.

```bash
inventag policy list --shipped
```

```text title="Output"
NAME                POLICIES
encryption-at-rest  4
finops-checks       6
naming              2
public-exposure     2
region-allowlist    1
tagging-standard    2
```

Use one with `--set NAME`:

```bash
inventag policy check --snapshot state/state_20261120_000000.json --set encryption-at-rest --fail-on high
```

- A set in the folder you give with `--policies` wins over a shipped set of
  the same name.
- Every policy has a stable ID, a severity and a version. The sets are part of
  the InvenTag package; a copy in your own folder is yours to change.
- A shipped policy reads only a field that a scan of test resources (moto) put
  on the row. It is **not verified against a real AWS account** that the field
  is on every resource of every account. A row without the field is
  `not_evaluated`, never a pass.
- Every policy ships with fixtures under `tests/` in its set's folder.

Findings are observations from the inventory, not an opinion on any standard.

## `finops-checks`

The six FinOps checks `FIN-001` to `FIN-006`, severity `low`. They are the
checks of `--finops-checks`. The table of what each reads, the promise that the
sheet is unchanged, and how `policy check` can differ are in
[Governance as code](../guides/governance-as-code.md#the-finops-checks-set).
The checks and the sheet are described in [FinOps checks](../guides/finops-checks.md).

## `tagging-standard`

| Policy | Severity | Selects | Reads | `fail` when |
|---|---|---|---|---|
| `TAG-001` `tag-owner-present` | low | every row except resource type `Alias` and rows from Cost Explorer | the tags | there is no `Owner` tag |
| `TAG-002` `tag-environment-allowed` | low | the same rows | the tags | there is no `Environment` tag, or its value is not one of `prod`, `staging`, `dev`, `test`, `sandbox` (not case-sensitive) |

When the Tagging API listing of the row's account and region failed, the row
is `not_evaluated` with `tags_not_read`. The files carry the comment "A
starting point: copy the set and change the keys and values to your own
conventions." The keys and values are examples, not a standard.

## `region-allowlist`

| Policy | Severity | Selects | Reads | `fail` when |
|---|---|---|---|---|
| `REG-001` `region-allowed` | medium | every row except rows from Cost Explorer | `region` | the region is not `ap-southeast-1`, `eu-west-1` or `us-east-1`; a `global` row passes |

The region list is an example. The file says: "A starting point: copy the set
and list the regions your organisation uses."

## `naming`

| Policy | Severity | Selects | Reads | `fail` when |
|---|---|---|---|---|
| `NAME-001` `name-instance-name-tag` | low | EC2 `Instance` | `tags.Name` | the tag is missing or does not match `[a-z][a-z0-9-]*` completely |
| `NAME-002` `name-security-group-not-wizard` | low | VPC `SecurityGroup` | `raw_data.GroupName` | the name starts with `launch-wizard-` |

## `encryption-at-rest`

| Policy | Severity | Selects | Reads | `fail` when |
|---|---|---|---|---|
| `ENC-001` `enc-volume-encrypted` | medium | EC2 `Volume` | `raw_data.Encrypted` | the value is not `true` |
| `ENC-002` `enc-snapshot-encrypted` | medium | EC2 `Snapshot` | `raw_data.Encrypted` | the value is not `true` |
| `ENC-003` `enc-rds-storage-encrypted` | high | RDS `DBInstance` | `raw_data.StorageEncrypted` | the value is not `true` |
| `ENC-004` `enc-efs-encrypted` | medium | ELASTICFILESYSTEM `FileSystem` | `raw_data.Encrypted` | the value is not `true` |

Each policy lists the field under `require`, so a row without it is
`not_evaluated` with `field_missing`, and a row known by identity only is
`not_evaluated` with `identity_only`.

**Not shipped, and why:** encryption of S3 buckets, SQS queues, SNS topics and
DynamoDB tables. A scan of test resources (moto) does not put the field a rule
would read on the row: `ServerSideEncryptionConfiguration` on an S3 bucket,
`Attributes` on an SQS queue, `KmsMasterKeyId` on an SNS topic, `SSEDescription`
on a DynamoDB table. A rule on a field the scan does not put on the row would
be `not_evaluated` for every resource, so it is not shipped. A test shows that
each of these keys is not on the scanned row, and fails if a shipped policy
reads one. Also not shipped: encryption of ECR repositories, because it is
always on, so it would never be a finding.

## `public-exposure`

| Policy | Severity | Selects | Reads | `fail` when |
|---|---|---|---|---|
| `PUB-001` `pub-rds-not-public` | high | RDS `DBInstance` | `raw_data.PubliclyAccessible` | the value is not `false` |
| `PUB-002` `pub-security-group-not-open` | high | VPC `SecurityGroup` | `raw_data.IpPermissions` | an inbound rule has the range `0.0.0.0/0` or `::/0` (any port) |

**Not shipped, and why:** S3 public access, because a scan of test resources
does not put `PublicAccessBlockConfiguration` on the bucket's row (checked by
the same test). Also not shipped: whether an EC2 instance has a public address,
or whether a load balancer is internet-facing. Both are on the row. They were
left out as a judgement: the field alone does not say whether it is a problem.
Also not shipped: the sharing of EBS snapshots and the rotation of KMS keys.
Not verified against a scan whether those two fields are on the row; the set's
author left them out.

## Run the fixtures of a set

`inventag policy test DIR` runs the fixtures under `DIR/tests/`. The fixtures
of all six shipped sets pass.
