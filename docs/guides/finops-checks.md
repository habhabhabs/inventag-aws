---
title: FinOps checks
description: Six fixed FinOps checks on the resources a scan finds, with no further AWS call, and an opt-in read of last month's spend by service, linked account and cost allocation tag from Cost Explorer.
sidebar_position: 10
---

# FinOps checks

**Who this is for:** you look after cloud spend and want a list of resources
to look at, made from the inventory you already have.

**What you can do after reading:** run the six FinOps checks, read the
`FinOps` sheet, and know what the checks cannot see.

## Run the checks

```bash
inventag --create-excel --finops-checks
```

The flag is off by default. With it, InvenTag runs six fixed checks on the
resources the scan found, and adds a sheet named `FinOps` as the last sheet
of the Excel report.

- The checks read only the rows the scan already has. They make no further
  AWS call and need no further permission. The read-only guard sees the same
  calls with and without the flag.
- The checks change nothing in an account.
- The findings do not change the exit code: a run with `fail` results exits
  as it would without them.
- Without the flag, the checks do not run: the report has no `FinOps` sheet,
  and the other sheets and the console text are the same as with the flag.

## The six checks

| Check ID | Resources | Result `fail` when |
|---|---|---|
| `FIN-001` | EBS volumes | the volume's `State` is `available` (no attachment) |
| `FIN-002` | Elastic IP addresses | the address has no `AssociationId` |
| `FIN-003` | EBS snapshots owned by the scanned account | the snapshot's `StartTime` is more than 90 days before the run started |
| `FIN-004` | EC2 instances | the instance state is `stopped` |
| `FIN-005` | Load balancers | no target group of the same account and region names it (`ELBV2` sheet), or it lists no instance (classic load balancers, `ELB` sheet) |
| `FIN-006` | Every resource in the scope of the built-in `finops-cost-allocation` tag policy | a key of that policy is missing: `CostCenter`, `Owner`, `Project` or `Environment` |

The 90 days of `FIN-003` is fixed; there is no option to change it.

`FIN-006` uses the same check as the `finops-cost-allocation` tag policy (see
[Check tag compliance](check-tag-compliance.md)), but it looks only for
missing keys. A key whose value the policy does not allow is not a `FIN-006`
finding. Tag keys are case-sensitive: `owner` does not count as `Owner`. Rows
that come only from Cost Explorer (source `billing`) are not checked.

## Results

Each check gives one of three results for each resource:

- `fail`: the check observed what the table says. The resource is listed.
- `not_evaluated`: the data the check needs is not there. The resource is
  listed with a reason.
- `pass`: the resource is counted, not listed.

A gap in the data is never a pass. The reasons are:

| Reason | Meaning |
|---|---|
| `identity_only` | The resource is known only from the Resource Groups Tagging API, so the field the check reads is not on its row. |
| `field_missing` | The field the check reads is not on the row. For `FIN-003`, also when the run has no start time. |
| `tags_not_read` | `FIN-006` only: a key is missing and the Tagging API listing of that region failed in this run. For a global resource, any failed Tagging API listing of the account counts. |
| `listing_not_read` | A listing the check needs failed in this run. Each check that needs that listing gets one line for it and its region: one failed `ec2` listing gives four lines (`FIN-001`, `FIN-003`, `FIN-004`, `FIN-006`). |

## The FinOps sheet

The first line of the sheet says: "These are observations from the
inventory. A resource listed here may be intended."

Then the listed results, with these columns: `Check ID`, `Check`, `Result`,
`Reason`, `Account`, `Region`, `Service`, `Resource Type`, `Resource ID`,
`Name`, `Observed`. Rows are sorted by check ID, account, region and resource
ID. `Observed` states what the check saw, for example "no attachment",
"started 2026-05-02", "state stopped" or "missing: CostCenter, Owner". Nothing
else from the API answer is copied into the sheet.

After the listed results comes a table with one row per check and the counts
`Fail`, `Not evaluated` and `Pass`.

A sample, made by the docs generator from a mocked AWS account:

<!-- BEGIN EXAMPLE OUTPUT: finops-checks-sheet -->

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `FinOps`

`FinOps` sheet:

> These are observations from the inventory. A ...  

| Check ID | Check | Result | Reason | Account | Region | Service | Resource Type | Resource ID | Name | Observed |
|---|---|---|---|---|---|---|---|---|---|---|
| FIN-001 | EBS volume with no attachment | fail |  | 123456789012 | us-east-1 | EC2 | Volume | vol-57d5df4cfc9884b48 | acme-build-cache | no attachment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | global | IAM | Role | acme-orders-api-role |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | VPC | NetworkAcl | acl-3118daa9d5cc099a7 |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | missing: Project |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-inventory-reports | acme-inventory-reports | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-new-bucket | acme-new-bucket | missing: CostCenter, Owner, Project, Environment |

<!-- END EXAMPLE OUTPUT: finops-checks-sheet -->

With `--per-account-reports`, the report of each account lists only that
account's results.

With `--template`, the checks do not run: InvenTag prints a warning and
writes no `FinOps` sheet.

## The `finops_checks` result

The command line writes the results only as the `FinOps` sheet. In Python,
`CloudBOMGenerator.generate_multi_account_bom()` returns them under the key
`finops_checks`, and a JSON report written with the `json` output format has
the same key in its `metadata`. The key holds:

- `schema_version`: `1`.
- `summary`: one entry per check, with `policy` (the check ID), `check`,
  `fail`, `not_evaluated` and `pass`.
- `findings`: the listed results, with `policy`, `result`, `reason`,
  `account`, `region`, `service`, `resource_type`, `resource`, `name` and
  `message` (the `Observed` text).

Without the flag, the key is not there.

## Cost allocation from Cost Explorer

`--finops-cost-allocation` is a second flag, off by default and independent of
`--finops-checks` and `--enable-cost-analysis`. It reads last month's spend
from Cost Explorer for each account, with that account's own credentials, and
adds a sheet named `FinOps costs` as the last sheet of the Excel report.

```bash
inventag --create-excel --finops-cost-allocation
```

### Requests

For each account, in this order:

| Request | How many |
|---|---|
| `ListCostAllocationTags` for `CostCenter`, `Owner`, `Project` and `Environment` (the keys of the built-in `finops-cost-allocation` tag policy) | 1 |
| `GetCostAndUsage` grouped by service | 1 |
| `GetCostAndUsage` grouped by linked account | 1 |
| `GetCostAndUsage` grouped by each of those keys that is active as a cost allocation tag | 0 to 4 |

That is at most 7 requests for each account. A key that `ListCostAllocationTags`
shows as not active, or does not list, is not queried; its table says "not
active as a cost allocation tag" or "not found as a cost allocation tag". If
`ListCostAllocationTags` itself fails, all four keys are queried.

A further page of an answer (`NextPageToken`) is one more request. It comes out
of the same 7, at most 3 for each grouping. A table that needs more pages than
that is marked "incomplete".

Before discovery, the run prints one warning line with the most requests, for
example: `Cost Explorer: up to 7 request(s) in this run (billing validation: 0;
cost trend: 0; cost allocation: 7). AWS charges for each.` The read-only
guard's audit (`--audit-output`) never counts more requests of the feature than
that line says.

The SDK retries a throttled request, and each retry is one more request. AWS
charges for each Cost Explorer request: see
[Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
Not verified against real AWS: what AWS bills for these requests, retries and
`ListCostAllocationTags` included.

### The FinOps costs sheet

The sheet starts with a note: the amounts are as Cost Explorer returns them,
for each account, read with that account's own credentials, for the last full
month, and they are not costs of single resources. Then one row for each
account, grouping and value, with the columns `Account`, `Grouping`, `Value`,
`Amount`, `Currency`, `Metric`, `Period start`, `Period end` and `Status`.

- The period is the calendar month before the month in which the run started.
  `Period end` is the first day of the run's month.
- The metric is `UnblendedCost`. The amounts are the text AWS returns; InvenTag
  does not add, divide or round them.
- In a tag grouping, the value `(no value)` is the spend without that tag key.
- A table that could not be read has one row with its status, for example
  "not read: access denied". The run notes name it too, and a denied request
  gets a `Permissions:` line. The scan's result and the exit code stay as they
  would be without the flag.

With `--per-account-reports`, each account's report holds only that account's
tables. With `--template`, no request is made: InvenTag prints a warning and
writes no `FinOps costs` sheet.

### The `finops_costs` key, the snapshot and the change report

- In Python, the result of `CloudBOMGenerator.generate_multi_account_bom()` and
  the `metadata` of a JSON report have the key `finops_costs`: `schema_version`,
  `metric` and, for each account, the period, the request count, the status of
  each tag key and the tables.
- The state snapshot gets `metadata.tags.cost_allocation`: the tables only
  (totals by service, linked account and tag value; no resource IDs). The
  snapshot stays readable by its owner only (mode 0600).
  `--no-cost-in-snapshot` leaves the figures out of the snapshot; the sheet is
  still written. Without `--finops-cost-allocation` that flag changes nothing
  and a warning says so.
- Read from a management (payer) account, the linked-account table can list
  every member account of the organization with its spend, also accounts this
  run did not scan, and the tag tables hold their tag values (for example
  `Owner` names or e-mail addresses) as AWS returns them. These go into the
  sheet, the snapshot and the change report. Use `--no-cost-in-snapshot` to
  keep them out of the snapshot. Not verified against real AWS: what a payer
  account's answer holds.
- The change report gets a block "Cost, previous run to this run" when this run
  read cost allocation. It shows each value of the previous run and of this run
  side by side when the two snapshots hold different months. Otherwise one line
  says why there is no comparison: the previous snapshot has no figures, both
  runs read the same month, or `--no-cost-in-snapshot` was given.

### What it needs and what is not verified

The flag needs `ce:GetCostAndUsage` and `ce:ListCostAllocationTags`. Both are
in the repository policy (see [IAM permissions](../reference/iam-permissions.md)).

Not verified against real AWS:

- Tag keys show spend only after they are activated as cost allocation tags in
  the billing (payer) account.
- A member account of an organization may see less than the payer account, and
  `ListCostAllocationTags` may not answer from a member account.
- That the answers have the shape the tests use. The tests use answers shaped
  like Cost Explorer's, checked against the botocore service model.

## What the checks cannot see

- `FIN-004` gives no duration. The instance listing has no reliable stop
  time, so a stopped instance is listed however long it has been stopped.
- `FIN-005` does not read target health. A load balancer whose targets are
  all unhealthy is a pass. Reading target health would need a new AWS call.
- A resource listed here may be intended: for example, an instance stopped on
  purpose or a snapshot kept by a retention rule.
- The checks show no amounts of money.
- Not verified against real AWS: that the listings carry the fields each check
  needs on every account type.
