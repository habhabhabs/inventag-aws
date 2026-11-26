---
title: Governance as code
description: Write policies as YAML files, check them against a saved snapshot of a scan, waive known exceptions with an expiry date, and use the exit codes in CI. InvenTag reads; a policy never changes a resource.
sidebar_position: 11
---

# Governance as code

**Who this is for:** you own rules about your AWS estate (encryption on,
no open security groups, tags present) and want to write them down as files,
check them on every scan, and keep a record of the exceptions.

**What you can do after reading:** write a policy, test it, check a saved
snapshot, waive a known exception for a limited time, read the four results,
and use the exit codes in a pipeline.

## What a policy is, and is not

- A **policy** is a YAML file. It says which resources it looks at and what
  must be true of each one.
- A **policy set** is a file that names policies, so you can check them
  together. InvenTag ships some sets; see
  [Shipped policy sets](../reference/policy-sets.md).
- A **finding** is the result of one policy on one resource.
- InvenTag only reads. A policy has no action: a file with a field named
  `actions`, `mode`, `notify` or `remediate` is refused with "InvenTag never
  changes resources; a policy has no actions." Nothing in this feature changes
  a resource in an account.
- `inventag policy` makes no AWS call. It reads a snapshot file that an
  earlier scan wrote, so it needs no credentials.
- A finding says what InvenTag read in the inventory. It is an observation,
  not an audit opinion, and it does not say that anything meets a standard.

## The four results

| Result | Meaning |
|---|---|
| `pass` | The resource was checked and the condition holds. Counted, not listed. |
| `fail` | The resource was checked and the condition does not hold. |
| `waived` | The resource failed, and a waiver that has not expired covers it. |
| `not_evaluated` | InvenTag could not decide, and the finding says why. |

A gap is never a pass. If the data a policy needs is not in the snapshot, the
finding is `not_evaluated`. It is not counted as `pass` and not counted as
`fail`.

The reasons for `not_evaluated`:

| Reason | When |
|---|---|
| `identity_only` | The policy reads a field under `raw_data`, and the resource is known only from the Resource Groups Tagging API, so there is no `raw_data`. |
| `listing_not_read` | The policy needs a listing that failed in this run (for example the target groups of a load balancer). |
| `field_missing` | A key named in `require` is not on the row, or a `related` check could not decide because a related row lacks its key. |
| `tags_not_read` | The policy reads a tag, and the Tagging API listing of that account and region failed in this run. |
| `not_comparable` | `gt`, `ge`, `lt` or `le` met a value that is not a number. |
| `not_convertible` | `value_type` could not convert the value (for example `age` of a text that is not a date). |
| `value_too_long` | A text longer than 4096 characters met `glob`, `regex` or `regex-case`. |

When several reasons apply to one row, the first of `identity_only`,
`listing_not_read`, `field_missing`, `tags_not_read`, `not_comparable`,
`not_convertible`, `value_too_long` is the one written.

Besides row findings, the result lists **units not read**: a listing that
failed in the scan and that a policy could have selected rows from. The text
output prints them under "Units not read".

## Write and test a first policy

Save this as `.inventag/policies/rds-encrypted.yaml`, the folder that
`inventag policy` reads when you give no `--policies`:

```yaml
format_version: 1
kind: policy
name: rds-storage-encrypted
description: RDS instances have encrypted storage
spec:
  id: RDS-001
  severity: high
  resource:
    services: [RDS]
    resource_types: [DBInstance]
  require: [raw_data.StorageEncrypted]
  check:
    - {type: value, key: raw_data.StorageEncrypted, value: true}
```

- `id` is capital letters, a hyphen and 3 to 5 digits (`RDS-001`). It is
  unique in a run and is written into every finding.
- `severity` is `info`, `low`, `medium`, `high` or `critical`.
- `resource` says which rows the policy looks at. A row outside it is "out of
  scope": counted, not listed.
- `require` lists keys that must be on the row. A selected row without one is
  `not_evaluated` with `field_missing`, not `fail`.
- `check` is a list; every entry must hold.

Check the files for mistakes:

```bash
inventag policy validate .inventag/policies
```

```text title="Output"
OK    rds-encrypted.yaml (policy RDS-001)
1 policies, 0 sets, 0 waivers: no problems.
```

A mistake is reported as `file:line: field: problem`, and the command exits
with code 1 and evaluates nothing. [Policy files](../reference/policy-files.md)
lists every field.

### Write a fixture

A fixture is a small snapshot plus what you expect. Save this as
`.inventag/policies/tests/rds-storage-encrypted/basic.yaml`:

```yaml
format_version: 1
kind: policy-test
name: rds-encrypted-basic
spec:
  policy: rds-storage-encrypted
  now: 2026-11-20
  resources:
    - {service: RDS, resource_type: DBInstance, resource_id: a,
       arn: "arn:aws:rds:eu-west-1:111111111111:db:a", region: eu-west-1,
       source_account_id: "111111111111", detail_level: full, tags: {},
       raw_data: {StorageEncrypted: true}}
    - {service: RDS, resource_type: DBInstance, resource_id: b,
       arn: "arn:aws:rds:eu-west-1:111111111111:db:b", region: eu-west-1,
       source_account_id: "111111111111", detail_level: full, tags: {},
       raw_data: {StorageEncrypted: false}}
    - {service: RDS, resource_type: DBInstance, resource_id: c,
       arn: "arn:aws:rds:eu-west-1:111111111111:db:c", region: eu-west-1,
       source_account_id: "111111111111", detail_level: identity, tags: {}}
    - {service: S3, resource_type: Bucket, resource_id: logs,
       arn: "arn:aws:s3:::logs", region: us-east-1,
       source_account_id: "111111111111", detail_level: full, tags: {},
       raw_data: {Name: logs}}
  expect:
    - {resource: "arn:aws:rds:eu-west-1:111111111111:db:a", result: pass}
    - {resource: "arn:aws:rds:eu-west-1:111111111111:db:b", result: fail}
    - {resource: "arn:aws:rds:eu-west-1:111111111111:db:c", result: not_evaluated, reason: identity_only}
    - {resource: "arn:aws:s3:::logs", result: out_of_scope}
```

```bash
inventag policy test .inventag/policies
```

```text title="Output"
PASS  rds-storage-encrypted/basic.yaml
1 fixtures, 0 failed.
```

Every row the policy selects must be named in `expect`, and a row you expect
to be left out is named with `result: out_of_scope`. A missing or extra line
fails the fixture, and the command exits with code 1. A fixture that sets
`units_not_read` must also give `expect_units`.

## Check a snapshot

A scan with state management on (the default) writes a snapshot to
`state/state_<timestamp>.json` in the output directory. Check it:

```bash
inventag policy check --snapshot state/state_20261120_000000.json --fail-on high
```

The examples below use the 10-resource snapshot of the repository's tests,
`tests/unit/policy/golden/s1.json`, copied to `s1.json`, and `--now
2026-11-20` so that the output does not depend on the day you read this page.

```bash
inventag policy check --snapshot s1.json --now 2026-11-20 --fail-on high
```

```text title="Output"
InvenTag policy findings
Snapshot: s1.json  now: 2026-11-20
Rows: 10  fail: 1  waived: 0  not evaluated: 0  pass: 1

RDS-001 [high] fail=1 waived=0 not_evaluated=0 pass=1 out_of_scope=8

RDS-001 (rds-encrypted.yaml)
  FAIL arn:aws:rds:eu-west-1:111111111111:db:db-orders
    RDS-001: condition not met: raw_data.StorageEncrypted
    - condition not met: raw_data.StorageEncrypted

Exit code 7: at least one finding failed at severity high or higher.
```

The exit code of this command was 7. The command reports the findings and
exits 0 unless you give `--fail-on` or `--fail-on-not-evaluated`.

`--now YYYY-MM-DD` sets the date of the run, used for the expiry of waivers and
for the `age` and `expiration` conversions. Without it, the date is today in
UTC. A value that is not a date (for example a time) is refused with exit code
2.

To see how one policy decided each row, use `explain`:

```bash
inventag policy explain RDS-001 --snapshot s1.json --now 2026-11-20 --resource arn:aws:rds:eu-west-1:111111111111:db:db-orders
```

```text title="Output"
RDS-001 (rds-storage-encrypted, high, version 1)
fail  arn:aws:rds:eu-west-1:111111111111:db:db-orders
      check 0 (value): condition not met: raw_data.StorageEncrypted
      trace:
        check and: false
          resource services: true
          resource resource_types: true
          check require raw_data.StorageEncrypted: true
          check value raw_data.StorageEncrypted: false
Rows: 1 selected, 0 not selected.
```

The trace shows which part of the policy was true, false or unknown, and
never a value from the resource.

### Not evaluated

The shipped `naming` set reads the `Name` tag of EC2 instances. In the same
snapshot the Tagging API listing of account `222222222222` in
`ap-southeast-1` failed, so the tags of the instance there were not read:

```bash
inventag policy check --snapshot s1.json --set naming --now 2026-11-20 --fail-on-not-evaluated
```

```text title="Output"
InvenTag policy findings
Snapshot: s1.json  now: 2026-11-20
Rows: 10  fail: 2  waived: 0  not evaluated: 1  pass: 1

NAME-001 [low] fail=1 waived=0 not_evaluated=1 pass=1 out_of_scope=7
NAME-002 [low] fail=1 waived=0 not_evaluated=0 pass=0 out_of_scope=9

NAME-001 (naming/name-001.yaml)
  FAIL arn:aws:ec2:us-east-1:111111111111:instance/i-0bbb
    NAME-001: pattern not matched: tags.Name
    - pattern not matched: tags.Name
  NOT EVALUATED arn:aws:ec2:ap-southeast-1:222222222222:instance/i-0ccc
    NAME-001: not evaluated (tags_not_read)

NAME-002 (naming/name-002.yaml)
  FAIL arn:aws:ec2:ap-southeast-3:222222222222:security-group/sg-0ddd
    NAME-002: pattern not matched: raw_data.GroupName
    - pattern not matched: raw_data.GroupName

Exit code 8: some checks could not be evaluated.
```

The exit code of this command was 8. The instance whose tags were not read is
not counted as a pass and not counted as a fail.

## Waive a known exception

A waiver turns a `fail` into `waived` for a limited time. Save it outside the
policy folder, for example as `waivers/waivers.yaml`:

```yaml
format_version: 1
kind: waivers
name: waivers
spec:
  waivers:
    - policy: RDS-001
      resource: "arn:aws:rds:eu-west-1:111111111111:db:db-orders"
      reason: "Migration to an encrypted instance is planned for Q1."
      approved_by: "platform-lead"
      expires: 2026-12-31
```

```bash
inventag policy check --snapshot s1.json --waivers waivers/waivers.yaml --now 2026-11-20 --fail-on high
```

```text title="Output"
InvenTag policy findings
Snapshot: s1.json  now: 2026-11-20
Rows: 10  fail: 0  waived: 1  not evaluated: 0  pass: 1

RDS-001 [high] fail=0 waived=1 not_evaluated=0 pass=1 out_of_scope=8

RDS-001 (rds-encrypted.yaml)
  WAIVED arn:aws:rds:eu-west-1:111111111111:db:db-orders
    RDS-001: condition not met: raw_data.StorageEncrypted
    waiver: Migration to an encrypted instance is planned for Q1. (approved by platform-lead, expires 2026-12-31)
    - condition not met: raw_data.StorageEncrypted

Exit code 0: nothing failed at severity high or higher.
```

The exit code of this command was 0: a waived finding never changes the exit
code.

- A waiver needs `policy`, `resource`, `reason` (10 to 300 characters),
  `approved_by` and `expires`. `account` is required when `resource` has a
  `*` or `?`. A resource with no literal character, such as `*`, `**`, `?*` or
  `[a-z]*`, is refused.
- `expires` is a date, `YYYY-MM-DD`. The waiver applies through the end of
  that UTC day. A date more than 366 days after the run's date is refused.
- A waiver changes only a `fail`. It never changes a `pass` or a
  `not_evaluated`.
- When an expired waiver matches a failing row, the row stays `fail` and its
  finding carries `waiver_expired`. A waiver that changed no finding is listed
  in `unused_waivers` with the reason `no match`, `expired`, `unknown policy`
  or `superseded`.

A waivers file may sit inside the folder given to `--policies`: `list`,
`check` and `explain` skip it when they load policies. Its waivers apply only
when you name the file with `--waivers`.

## Compare with an older snapshot

A `baseline` check reports what changed between two snapshots. Give the older
one with `--baseline`:

```yaml
format_version: 1
kind: policy
name: no-new-resources
spec:
  id: DRF-001
  severity: medium
  check:
    - {type: baseline, change: [added, removed]}
```

```bash
inventag policy check --snapshot s1.json --baseline s0.json --policies drift.yaml --now 2026-11-20 --fail-on medium
```

```text title="Output"
InvenTag policy findings
Snapshot: s1.json  now: 2026-11-20
Rows: 10  fail: 4  waived: 0  not evaluated: 0  pass: 7

DRF-001 [medium] fail=4 waived=0 not_evaluated=0 pass=7 out_of_scope=0

DRF-001 (drift.yaml)
  FAIL arn:aws:s3:::public-site-assets
    DRF-001: added
    - added
  FAIL arn:aws:ec2:us-east-1:111111111111:instance/i-0bbb
    DRF-001: added
    - added
  FAIL arn:aws:s3:::old-exports
    DRF-001: removed
    - removed
  FAIL arn:aws:ec2:ap-southeast-1:222222222222:instance/i-0ccc
    DRF-001: added
    - added

Units not read:
  DRF-001 111111111111 lambda eu-west-1: throttled

Exit code 7: at least one finding failed at severity medium or higher.
```

- `change` is a non-empty list of `added`, `removed` and `modified`. A
  `baseline` entry must be a top-level entry of `check`.
- A resource whose listing failed in the newer snapshot is not reported as
  removed; the failed listing is under "Units not read".
- Without `--baseline`, the policy gives no row finding, and the result file
  lists the policy in `not_evaluated_policies` with the reason `no_baseline`.

## Policy sets and severity overrides

A `kind: policy-set` file names policies, by their `name` or by a path
relative to the file, and can `include` other sets:

```yaml
format_version: 1
kind: policy-set
name: team-baseline
spec:
  policies: [rds-storage-encrypted]
  include: [naming]
  severity_overrides:
    NAME-001: medium
```

`--set NAME` on `list`, `check` and `explain` uses one set: a set found in
the paths you gave first, then a shipped set. `inventag policy list --shipped`
lists the shipped sets. A policy reached twice is evaluated once, and a cycle
of `include` is an error. A severity override is recorded in the result as
`severity_overridden_by`.

## Pin the policy files with `policy.lock`

```bash
inventag policy lock .inventag/policies
```

writes `.inventag/policies/policy.lock`: a JSON file that lists the SHA-256 of
every policy, policy-set and waivers file in the folder. A `tests/` folder is
left out. It also lists every other file a set names by path, and the rules of
each tag policy that a `required-tags` check names with `policy:`.

```bash
inventag policy lock --check .inventag/policies
```

exits with code 1 when a listed file changed, is missing, or an unlisted file
of these kinds exists, and names each file. When the lock is current it prints
`policy.lock is current.` and exits with code 0. `inventag policy check
--locked` refuses to evaluate in the same cases (exit code 1). With
`--locked`, a `--waivers` file must be inside the policy folder and listed in
`policy.lock`. A missing or invalid `policy.lock` is an error (exit code 1).

## Output files

`--format` takes a comma-separated list of `text`, `json`, `sarif`, `junit`
and `markdown`; the default is `text`. `text` goes to the screen. The others
are written to `--output-directory` (default: the current folder):

| `--format` | File |
|---|---|
| `json` | `policy_findings_<timestamp>.json` |
| `sarif` | `policy_findings_<timestamp>.sarif` |
| `junit` | `policy_findings_<timestamp>.xml` |
| `markdown` | `policy_findings_<timestamp>.md` |

- `<timestamp>` is the timestamp of the snapshot (`20261120_000000`), not the
  time of the run. The same snapshot, policies and `--now` give the same bytes.
- The files are written for exit codes 0, 7 and 8. Nothing is written for
  exit codes 1 and 2.
- On Linux and macOS the files are readable and writable by their owner only
  (mode 0600), as the files of a scan; a folder InvenTag creates for them is
  mode 0700. An existing folder keeps its mode.
- The JSON file follows a schema that ships in the package:
  `inventag/policy/outputs/schemas/policy-findings-1.json`. Its `$id` is the
  URN `urn:inventag:schema:policy-findings:1`, not a web address.
- The SARIF file lists one rule per policy. `fail` is `error` for `critical`
  and `high`, `warning` for `medium`, `note` for `low` and `info`.
- The JUnit file has one test suite per policy file and one test case per
  policy. A policy with a `fail` is a failure; one with no `fail` and something
  not evaluated is skipped.

Not verified against GitHub code scanning or GitLab: how either one displays
the SARIF or the JUnit file.

### Values in findings

A finding does not show the value that failed a check. `--show-values` adds it
to the text, Markdown and JSON output:

```text title="Output"
  FAIL arn:aws:rds:eu-west-1:111111111111:db:db-orders
    RDS-001: condition not met: raw_data.StorageEncrypted
    - condition not met: raw_data.StorageEncrypted (value: false)
```

SARIF and JUnit never carry a value, with or without the option. A value that
a scan masked stays `***REDACTED***` in every format.

## Exit codes

| Code | When |
|---|---|
| 0 | The snapshot was evaluated and no code below applies. |
| 1 | A policy, set, waivers, lock or snapshot file is not valid or cannot be read. Nothing is evaluated. |
| 2 | Options are invalid or conflict. |
| 7 | `--fail-on SEVERITY` is given and at least one `fail` has that severity or a higher one. |
| 8 | `--fail-on-not-evaluated` is given and something could not be evaluated: a `not_evaluated` finding, a unit not read, or a policy not evaluated. |

8 wins over 7. `pass` and `waived` never change the code. Without
`--fail-on` and `--fail-on-not-evaluated` the command exits 0.

The last line of the text and Markdown output says which code the run exits
with:

| Exit | Last line |
|---|---|
| 0, no threshold given | `Exit code 0: findings are reported; no threshold was set.` |
| 0, `--fail-on S` | `Exit code 0: nothing failed at severity S or higher.` |
| 0, `--fail-on-not-evaluated` only | `Exit code 0: everything could be evaluated.` |
| 0, both | The two sentences above, in that order, joined by one space. |
| 7 | `Exit code 7: at least one finding failed at severity S or higher.` |
| 8 | `Exit code 8: some checks could not be evaluated.` |

## Check on a scan

```bash
inventag --create-excel --policy .inventag/policies --policy-fail-on high
```

`--policy PATH` (repeatable), `--policy-waivers FILE`, `--policy-fail-on
SEVERITY` and `--policy-format LIST` check the policies against the snapshot
of the run, after the scan. A summary goes to the screen and
`policy_findings_<timestamp>.json` to the output directory. The summary is
always printed. The line `Policy findings: <path>` is logged at INFO level, so
it shows only with `--verbose`. See
[the CLI reference](../reference/cli.md#policies).

- Exit codes 5, 6, 3 and 4 keep their order and come first. Code 7 follows
  only when none of them applies.
- A scan never exits with code 8: there is no option on a scan for it. Only
  `inventag policy check` gives it.
- `--policy` works together with `--template`.
- An invalid policy stops the scan with exit code 1 before any AWS call.

## Tag policies: `scope.filters`

A tag-policy template can limit the resources it checks with
`spec.scope.filters`, written like the `filters` of a policy. A resource the
filters leave out is out of scope. A resource the filters cannot decide (for
example a tag filter on a resource whose tags were not read) is **not
evaluated**: it is counted as such and it is not checked, and it is never
counted as meeting the policy. The JSON, the console line, the workbook and
the Word document name the number of such resources, and only when the policy
has filters. See the [template reference](../templates/reference.md).

## The `finops-checks` set

`--finops-checks` and the shipped set `finops-checks` are the six FinOps
checks, `FIN-001` to `FIN-006`, written as six policies of severity `low`.

| Policy | Reads | `fail` when |
|---|---|---|
| `FIN-001` | EC2 `Volume`: `raw_data.State` | `State` is `available` (no attachment) |
| `FIN-002` | VPC `ElasticIP`: `raw_data.PublicIp`, `raw_data.AssociationId` | `AssociationId` is absent or empty |
| `FIN-003` | EC2 `Snapshot`: `raw_data.StartTime` | the snapshot is more than 90 days old |
| `FIN-004` | EC2 `Instance`: `raw_data.State.Name` | the state is `stopped` |
| `FIN-005` | ELBV2 `LoadBalancerV2` and ELB `LoadBalancer`: `raw_data.LoadBalancerArn`, `raw_data.Instances`, and the `LoadBalancerArns` of the target groups | no target group of the same account and region names a v2 load balancer, or a classic load balancer lists no instance |
| `FIN-006` | every row except rows from Cost Explorer: the tags | a key of the built-in `finops-cost-allocation` tag policy is missing |

The checks and the sheet are described in [FinOps checks](finops-checks.md).

**The sheet is byte for byte the one of v1.4.3.** `--finops-checks` runs this
set through the policy engine, and a golden test keeps the sheet and the
`finops_checks` key equal to what v1.4.3 wrote for the same rows. The golden
file was made from the v1.4.3 code, before the change, and holds 304 cases.
This promise is about `--finops-checks`. It is not a promise about
`inventag policy check --set finops-checks`.

**`policy check` can differ from the sheet.** The sheet keeps the v1.4.3
rules; `inventag policy check` follows the policy rules of this page. For
example, take a snapshot with a v2 load balancer that a target group names,
and a failed listing of the classic `elb` service in the same account and
region. The sheet lists no finding for the load balancer. `policy check
--set finops-checks` lists it as `not_evaluated` with `listing_not_read`.
Not verified against every case: other differences may exist, because the
golden test compares only the sheet with v1.4.3.

With `--template`, `--finops-checks` adds no sheet. It runs the set on the
run's snapshot and writes the findings to `policy_findings_<timestamp>.json`.

## What is not verified

- Not verified against a real AWS account: that every field a policy reads is
  on every resource type of every account. The shipped sets were checked on
  resources created in a test double (moto) only.
- Not verified against GitHub or GitLab: how they show the SARIF or JUnit file.
