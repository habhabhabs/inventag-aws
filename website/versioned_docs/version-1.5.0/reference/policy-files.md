---
title: Policy files
description: Every field of an InvenTag policy, policy set, waivers and policy test file, the check types, filter operators, limits, and the findings file.
sidebar_position: 7
---

# Policy files

**Who this is for:** you are writing or reviewing a policy and need the exact
name, type or meaning of a field.

**What you can do after reading:** write any policy, set, waiver or fixture
without guessing, and read the errors of `inventag policy validate`.

This page was written by hand from the schema in `inventag/policy/schema.py`;
there is no generator for it. A test checks that every field name, check type,
operator, value type, special word, severity, reason, placeholder and limit
that the code defines is on this page. The same list is printed by
`inventag policy schema`, and one field by `inventag policy schema FIELD`.
For a guided start, see [Governance as code](../guides/governance-as-code.md).

## File layout

Every file has the same top-level fields:

```yaml
format_version: 1      # 1 is the only version
kind: policy           # policy | policy-set | waivers | policy-test
name: rds-storage-encrypted
description: One sentence (optional)
spec:                  # the settings of this kind
  id: RDS-001
```

- `format_version`, `kind`, `name` and `spec` are required. `description` is
  optional text.
- `name` uses lower-case letters, digits and hyphens, at most 63 characters.
- A file can hold several documents separated by `---`.
- Unknown fields are errors, and so are duplicate keys.
- Put account IDs in quotes (`"111111111111"`) so YAML keeps them as text.
- The fields `actions`, `mode`, `notify` and `remediate` are refused: "InvenTag
  never changes resources; a policy has no actions."
- An error is written as `file:line: field: problem`.

### Limits

| Limit | Value |
|---|---|
| File size | 256 KiB |
| Policies in one run | 500 |
| Entries in `check` | 20 |
| Entries in one `and`, `or` or `not` | 20 |
| Nesting depth of `and`, `or`, `not` | 5 |
| Length of a `key` | 200 characters |
| Length of a pattern | 200 characters |
| Length of a found text compared with `glob`, `regex`, `regex-case`, `name-pattern` or a tag `pattern` | 4096 characters (longer: not evaluated, `value_too_long`) |
| Length of `message` | 300 characters |
| Entries in `references` | 10 |
| Related rows per account and region | 50000 |
| Days a waiver may run ahead | 366 |
| Levels of lists and mappings in one file | 50 |
| Set files reached through set files | 10 |
| Depth of `include` between policy sets | 10 |

YAML aliases (`&a` and `*a`) are refused, and no environment variable is
expanded.

A pattern that repeats a group holding another repeat or a `|`, such as
`(a+)+`, `(a|a)+` or `(.*a){20}`, is refused: it can take very long to match a
value from a scanned account. The pattern is also checked when a
`required-tags` check reads a tag policy with `policy:`. Two repeats with
nothing fixed between them (`a*a*`, `.*.*`) and a repeat of a group whose
length varies (`(a{1,50}){1,50}`, `(a?){30}`) are refused too. The check is
not complete: repeats with a fixed character between them (`.*x.*x.*x.*=`) or
many optional characters in a row are accepted and can still be slow, so keep
patterns short and anchored.

## `kind: policy`

| Field (under `spec`) | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `id` | text | yes | | Stable identity: capital letters and digits (2 to 8), a hyphen, 3 to 5 digits, for example `RDS-001`. Unique in a run. |
| `severity` | `info`, `low`, `medium`, `high`, `critical` | yes | | `info` is the lowest. |
| `version` | whole number, 1 or more | no | 1 | Raise it when the meaning changes. Written into the `policies` list of the findings file and into the SARIF rule. |
| `resource` | mapping | no | all rows | Which rows the policy looks at. |
| `require` | list of keys | no | none | Keys that must be on a selected row. |
| `check` | list, 1 to 20 entries | yes | | Every entry must hold. |
| `message` | text | no | built from the check | Text of a finding. |
| `references` | list of text | no | none | URLs or text. The first URL is the SARIF help address. |
| `enabled` | true or false | no | true | `false`: the policy is listed in the findings file with all counts 0 and is not evaluated. |

`message` replaces the text of a finding. It may use the placeholders `{name}`, `{resource}`, `{account}`,
`{region}`, `{service}`, `{resource_type}` and `{policy}`. Another placeholder,
or a placeholder with a format spec or a conversion (such as `{name:>10}` or
`{name!r}`), is an error.

`require` lists keys (see below). A selected row on which one is absent is
`not_evaluated` with `field_missing`; on a row known by identity only, a key
under `raw_data` gives `identity_only`. Without `require`, an absent key in an
`ne` comparison is true.

### `resource`

| Field | Meaning |
|---|---|
| `services` | The row's `service` label, for example `RDS`, `EC2`, `VPC`. Not case-sensitive. Empty or absent: any. |
| `resource_types` | The row's `resource_type`. Not case-sensitive. |
| `exclude_resource_types` | Removed after `services` and `resource_types`. |
| `regions` | The row's `region`. `global` must be named to select global rows when the list is given. |
| `accounts` | 12-digit account IDs. |
| `filters` | A list of filter entries; all must hold. |
| `listings` | Discovery service keys of the listings that give this policy's rows, for example `ec2`. Where given, they decide which failed listings count as units not read for this policy. |

`services`, `resource_types`, `exclude_resource_types`, `regions` and
`accounts` are plain tests. A row is selected when they hold and `filters` is
true. When `filters` cannot be decided, the row is `not_evaluated`. Otherwise
the row is out of scope: counted, not listed.

## Keys and filter entries

A **key** is a [JMESPath](https://jmespath.org/) expression over the row,
at most 200 characters, checked when the file is loaded. A row has these
fields: `service`, `resource_type`, `resource_id`, `resource_name`, `arn`,
`region`, `account_id`, `source_account_id`, `tags`, `raw_data`,
`detail_level` (`full` or `identity`) and `sources`. `raw_data` is the answer
of the listing call, with secret values masked. `tags.Owner` and `tag:Owner`
read a tag. A key with no result is **absent**.

Filter entries are used in `resource.filters` and in `check`:

```yaml
- "tag:Owner": present
- "tag:Environment": prod
- type: value
  key: raw_data.State.Name
  op: eq
  value: running
  value_type: integer
- and: [ ... ]
- or: [ ... ]
- not: [ ... ]
```

- `"tag:Owner": present` is the short form of `{type: value, key: tags.Owner,
  value: present}`.
- `and`, `or` and `not` hold 1 to 20 entries and must be the only field of
  their entry. `not` is true when the `and` of its entries is false.
- In `resource.filters` only `type: value` entries, the short form and
  `and`, `or`, `not` are allowed.

### Operators (`op`)

The default is `eq`. The meanings follow the value filter of Cloud Custodian
for this subset.

| `op` | True when | Example: found value, `value`, result |
|---|---|---|
| `eq` | equal. Texts are compared exactly, booleans and numbers by value. A text never equals a number. | `abc`, `abc`: true |
| `ne` | not equal | `abc`, `xyz`: true |
| `gt`, `ge`, `lt`, `le` | numeric comparison; both sides must be numbers | `5`, `3` with `gt`: true |
| `in` | the found value is a member of the list `value` | `a`, `[a, b]`: true |
| `not-in` | the found value is not a member of the list `value` | `c`, `[a, b]`: true |
| `contains` | the found value is a list or text that contains `value` | `hello`, `ell`: true |
| `glob` | `fnmatch.fnmatchcase(found, value)`; the found value must be text | `web-1`, `web-*`: true |
| `regex` | `re.match(value, found, re.IGNORECASE)`: ignores case, anchored at the start only | `Prod`, `prod`: true |
| `regex-case` | `re.match(value, found)`: case-sensitive | `Prod`, `prod`: false |

`in` and `not-in` need a list as `value`. Patterns are checked when the file
is loaded.

### Special values

With `eq` (the default), `value` may be one of four words:

| Word | True when |
|---|---|
| `absent` | the key has no result, or the result is null |
| `present` | the key has a result that is not null |
| `empty` | the key is absent, or the result is an empty text, list or mapping |
| `not-null` | the same as `present` |

To compare with one of these words as text, write `value_type: text`. A masked
value is the text `***REDACTED***` and counts as `present`.

### `value_type`

| `value_type` | The found value is converted to | `value` is |
|---|---|---|
| none | itself | as it is |
| `integer` | `int()` of a number or a text of digits | a whole number |
| `size` | the length of a list, mapping or text | a whole number |
| `normalize` | a text, stripped and lower-cased (both sides) | a text or a list |
| `age` | the days from the found date to now, a number with fractions | a number of days |
| `expiration` | the days from now to the found date, a number with fractions | a number of days |
| `text` | a text; switches the special words off | a text |

A date is ISO 8601 with or without a time and zone (no zone means UTC), or
epoch seconds as a number. `now` is the date given by `--now` (00:00:00 UTC)
or today. A value that cannot be converted gives `not_evaluated` with
`not_convertible`.

### Three values

Every entry is true, false or unknown. `and`, `or` and `not` follow Kleene's
rules: false and unknown is false; true or unknown is true; not unknown is
unknown. An unknown entry makes the finding `not_evaluated`, with the first
reason that applies from this list: `identity_only`, `listing_not_read`,
`field_missing`, `tags_not_read`, `not_comparable`, `not_convertible`,
`value_too_long`.

## Check types

`check` is a list. The verdict for a row is the Kleene `and` of its entries.

| `type` | Fields | True when |
|---|---|---|
| `value` | `key` (required), `op`, `value`, `value_type` | the entry is true (see above) |
| `required-tags` | `keys`, or `policy` with `use_scope` and `missing_only` | every key is present and its value passes |
| `allowed-regions` | `regions` (required), `allow_global` | the row's region is in the list, or is `global` and `allow_global` is true (default) |
| `name-pattern` | `pattern` (required), `field` | the field's value matches the pattern completely (`re.fullmatch`, case-sensitive). An absent field is false. |
| `baseline` | `change`, `attributes` | see below |
| `related` | `rows`, `their_key`, `my_key`, `listing`, `expect` | see below |
| `require` | `keys` | every key is present (an absent key gives `not_evaluated`, `field_missing`) |

### `required-tags`

`keys` is a list of `{key, allowed_values, case_sensitive, pattern}`. Only
`key` is required. Tag keys are case-sensitive. A present key passes when its
value is one of `allowed_values` (not case-sensitive unless `case_sensitive`
is true) and the whole value matches `pattern`, where these are given. Instead
of `keys`, `policy: NAME` uses the `required_tags` of a tag policy, and then:

- `use_scope: true` also applies the tag policy's own `scope` (default
  false);
- `missing_only: true` fails a row only for missing keys: a present key with a
  value outside `allowed_values` or `pattern` passes (default false).

`use_scope` and `missing_only` need `policy`. Give either `keys` or `policy`,
not both. When the tags of the row's account and region were not read, the
entry is unknown with `tags_not_read`.

### `name-pattern`

`field` is `name` by default, or a key such as `tags.Name` or
`raw_data.GroupName`. A key under `raw_data` on a row known by identity only
gives `identity_only`.

### `baseline`

Needs `--baseline FILE`, an older snapshot. `change` is a non-empty list of
`added`, `removed` and `modified`; `attributes` (keys) goes only with
`modified` and limits which differences count. A `baseline` entry must be a
top-level entry of `check`. A row of the snapshot with none of the listed
changes passes. Rows are paired with the same identity rule as the change
report.

### `related`

For "this row is named by another row", for example a load balancer and its
target groups:

```yaml
- type: related
  rows: {services: [ELBV2], resource_types: [TargetGroup]}
  their_key: raw_data.LoadBalancerArns   # on the other row: a text or a list of texts
  my_key: raw_data.LoadBalancerArn       # on this row: a text
  listing: elbv2                         # the listing that gives the other rows
  expect: any                            # any | none
```

`rows` takes the fields of `resource` without `filters`. Only rows of the same
account and region are looked at. `expect: any` is true when at least one row
names this one, `expect: none` when no row does. It is unknown with
`field_missing` when `my_key` is absent, or when no row names this one and a
related row lacks `their_key`, and with `listing_not_read` when the listing
failed in this run.

## `kind: policy-set`

| Field (under `spec`) | Meaning |
|---|---|
| `policies` | A policy `name`, or a path relative to the file that stays inside the policy folder. A set file that a chain of set files reaches again is an error that names the chain. |
| `include` | Names of other sets. A cycle is an error that names the cycle. |
| `severity_overrides` | A mapping of policy id to severity. Written into the result as `severity_overridden_by`. |

A policy reached twice is evaluated once.

## `kind: waivers`

`spec.waivers` is a list. Each entry:

| Field | Required | Meaning |
|---|---|---|
| `policy` | yes | A policy id. An id that is not among the loaded policies leaves the waiver unused, `unknown policy`. |
| `resource` | yes | Compared with the row's ARN, or `service/resource_type/resource_id` when it has no ARN. Exact, or a pattern when it contains `*` or `?`. A pattern with no literal character, such as `*`, `**`, `?*` or `[a-z]*`, is refused: a waiver cannot match every resource. |
| `account` | with `*` or `?` | The row's 12-digit account ID must equal it. |
| `reason` | yes | 10 to 300 characters. |
| `approved_by` | yes | Text. |
| `expires` | yes | `YYYY-MM-DD`. Valid through the end of that UTC day, at most 366 days after the run's date. |

## `kind: policy-test`

A fixture lives under `tests/<policy name>/` next to the policy. Under `spec`:
`policy` (the policy name), `now`, `resources` (rows, as in a snapshot),
`expect`, and optionally `units_not_read`, `baseline_resources`, `waivers`
and `expect_units`. `expect` has one entry for every row the policy selects:
`{resource, result}` with `result` one of `pass`, `fail`, `waived`,
`not_evaluated` or `out_of_scope`, and `reason` only with `not_evaluated`.
`expect_units` entries are `{account, service, region}` and optionally
`from: baseline`.

## `policy.lock`

A JSON file in the policy folder, written by `inventag policy lock`:
`{"files": {<relative path>: <sha256>}, "format_version": 1, "kind": "lock"}`,
keys sorted. It lists every policy, policy-set and waivers file; a `tests/`
folder is left out. It also lists every other file in the folder that a set
names by path, whatever its suffix and also under `tests/`. When a policy uses
`required-tags` with `policy: NAME`, the key `tag_policies` holds the SHA-256
of that tag policy's rules and scope as InvenTag resolves them. A change of the
tag policy (in `INVENTAG_TEMPLATE_PATH`, `.inventag/templates/`,
`~/.config/inventag/templates/` or a new InvenTag version) then also fails the
check; run `inventag policy lock` again after such a change.

## The findings file

`policy_findings_<timestamp>.json` has these top-level keys, sorted:
`baseline`, `findings`, `inventag_version`, `not_evaluated_policies`,
`not_evaluated_units`, `now`, `policies`, `schema_version`, `snapshot`,
`summary`, `unused_waivers`. `findings` lists `fail`, `waived` and
`not_evaluated`; `pass` rows are only counted. The schema ships in the package
as `inventag/policy/outputs/schemas/policy-findings-1.json`
(`$id` `urn:inventag:schema:policy-findings:1`). File paths in the result are
relative to the folder you gave, with `/`. No host name, user name, absolute
path or clock time is written.

## Editor schema

`inventag policy schema --json` prints a JSON Schema (draft 2020-12, `$id`
`urn:inventag:policy-file:1`) for the file headers and the fields of the four
kinds `policy`, `policy-set`, `waivers` and `policy-test`. It is looser than the validator,
which is the authority: entries of `check` are typed only by `type`.
