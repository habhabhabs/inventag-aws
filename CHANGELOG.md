# Changelog

This file lists the changes in each InvenTag release. Update it in the same
commit as the change. Put new entries in the "Unreleased" section.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The version numbers follow [Semantic Versioning](https://semver.org/).
A patch release may add an opt-in flag and additive output when a run without
the flag is unchanged; the changelog lists it under Added.

## [Unreleased]

### Added

- `--create-html`: writes the report as one static HTML file,
  `multi_account_bom_<timestamp>.html` (with `--per-account-reports`,
  `<account-id>_bom_<timestamp>.html`), next to the other reports. It holds a
  summary (resources by service and by region, run notes), one closed section
  of resources for each service with the columns of the default Excel sheet
  and the same secret masking, the tag compliance summary of a tag policy,
  the network and security tables, the FinOps and FinOps costs tables when
  their flags are on, and the coverage and denied permissions. Every value is
  escaped; the file has no JavaScript, loads nothing from outside it and
  carries a Content-Security-Policy; it is written whole and private to the
  user, and uploaded with `--s3-bucket` (with no content type, as the other
  reports). Text-direction and C1 control characters are removed
  from every value, so a name cannot show reversed. `--create-html` alone writes HTML
  only. With `--template`, the HTML file has the default layout and one
  warning says so. `--excel-template` with `--create-html` alone stops with
  exit code 2. The run prints `Data exported to <path>` for the HTML file, as
  for the Excel file. In the accounts table, `Read in part` is `Yes` for an
  account that stopped early or has a listing that was not read (the
  accounts the run notes name). The flag also appears in `--help`, in the
  usage line and in `inventag completion`, and `inventag selftest` counts one
  more module (112). A run without `--create-html` is otherwise unchanged.

## [v1.5.0] - 2026-11-26

### Added

- `inventag policy validate`, `list`, `schema`, `test`, `check`, `explain` and
  `lock`: governance as code on a saved state snapshot. A policy file
  (`kind: policy`), a policy set (`kind: policy-set`), a waivers file
  (`kind: waivers`) and a policy test (`kind: policy-test`) say what a
  resource must look like; InvenTag reads and reports, and a policy has no
  action. The commands make no AWS call and need no credentials. A row whose
  data was not read is `not_evaluated`, never a pass. `policy check` prints
  text by default and writes a file only for a format you name; it exits with
  0 unless you give `--fail-on` or `--fail-on-not-evaluated`. `--set` on
  `list`, `check` and `explain` uses a shipped set. Shell completion knows the
  new words.
- `--policy PATH` (repeatable), `--policy-waivers FILE`, `--policy-fail-on
  SEVERITY` and `--policy-format LIST` on a scan: the policies are checked on
  the run's state snapshot after the scan, a summary is printed (the counts of each policy, the fails by
  severity and the first 10 findings; `-v` prints every finding) and
  `policy_findings_<timestamp>.json` is written. They work with `--template`.
  An invalid policy stops the run with exit code 1 before any AWS call;
  `--disable-state-management` with `--policy` stops it with exit code 2.
- Exit codes 7 and 8. 7: a policy finding failed at or above the severity of
  `--policy-fail-on` (scan) or `--fail-on` (`inventag policy check`). 8: only
  `inventag policy check --fail-on-not-evaluated`, when something could not be
  evaluated; 8 wins over 7. Codes 0 to 6 and their order are unchanged; on a
  scan 7 comes only when 5, 6, 3 and 4 do not apply. On a scan, the last line of the
  summary and `summary.exit_code` give the code the scan exits with (0, 3, 4,
  5, 6 or 7).
- The files `policy_findings_<timestamp>.json`, `.sarif`, `.xml` (JUnit) and
  `.md`, and a JSON Schema for the JSON file packaged with InvenTag
  (`urn:inventag:schema:policy-findings:1`). A value of a resource field is
  shown only with `--show-values`; masked values stay masked, and SARIF and
  JUnit never carry a value.
- Shipped policy sets: `finops-checks`, `tagging-standard`, `region-allowlist`,
  `naming`, `encryption-at-rest` and `public-exposure`.
- `scope.filters` in tag policies: the entries are the filters of a policy. A
  resource they leave out is out of scope; a resource they cannot decide is
  counted as not evaluated and is not checked. The JSON, the console line, the
  workbook and the Word document show the count, and only when the policy has
  filters.
- `jmespath` is now a direct dependency (it was already installed with
  botocore).

### Changed

- `--finops-checks` and `--policy` work with `--template`. `--finops-checks`
  with `--template` runs the shipped `finops-checks` set on the state snapshot
  and writes `policy_findings_<timestamp>.json`; it no longer prints the
  v1.4.2 warning that the checks do not run. The `FinOps` sheet of a run
  without `--template` is unchanged, byte for byte.
- The cost trend of `--enable-cost-analysis` reads each account's bill with
  that account's credentials: at most 2 Cost Explorer requests for each
  account (was: at most 1 for the whole run, with the first account's
  credentials). Most accounts make 1. Figures of multi-account runs change.
  Services are found by their billing names, so S3, SQS and SNS get a trend,
  and EC2's figure no longer includes ECR or other services whose billing name
  contains "EC2". `EC2 - Other` is a separate billing name and is not in
  EC2's row. Two full months are compared. The billed amounts show the unit
  Cost Explorer returns. A failed trend request is one warning.
- The Cost Explorer count line is a warning on every run that calls Cost
  Explorer, default runs included (it was a warning only with
  `--enable-cost-analysis`).
- `inventag` with no option now prints the help page and exits with code 2.
  It starts no scan and makes no AWS call. Before, it scanned with your
  current credentials and wrote an Excel report. Add `--create-excel` to get
  that run: `inventag --create-excel`.
- `-vv` (or `--verbose` twice) now gives debug output, the same as `--debug`.
  Before, `-vv` equalled `-v`. `-v`, `--verbose`, `-d` and `--debug` are
  unchanged. So `-v` gives INFO output and `-vv` gives DEBUG output.
- The meaning of exit code 2 now includes a run with no option.
- The CI/CD guide and its example workflows now use `-vv` (debug output) for
  CI/CD runs, and so do `examples/github_actions_cicd_example.yml` and
  `examples/aws_codebuild_buildspec.yml`. Debug output holds account IDs,
  ARNs, IP addresses, tag values and the AWS SDK's full request and response
  bodies; secrets are masked. In a public repository the job log is public, so
  use `-v` there. The two example files no longer write a log file, upload it
  as an artifact or copy it to S3.

- `inventag.finops.checks.run_checks()` still accepts its `policy` argument
  and ignores it: FIN-006 always uses the keys of the built-in tag policy
  `finops-cost-allocation` (in v1.4.3 a Python caller could pass another tag
  policy).

- Log lines carry no billing data and no value from a scanned resource (CodeQL
  "clear-text logging"): no log line names a resource, a bucket, a table, an
  ARN, an account of a cost trend or a service from billing, and no line
  shows a billed amount, a count of billed services or the billing period.
  The changed lines: "Billing analysis: read the services with usage from
  Cost Explorer." (before: a count, the total spend and the start date, then
  the ten top-spending services with `-v`); "Some services have billing usage
  but no discovered resources (they may have untagged resources)." (before:
  a count, then one warning per service with its spend); "Some services have
  discovered resources but no recent billing (free tier or no recent usage)."
  (before: one `-v` line per service); "Comprehensive discovery complete.
  Found N unique resources across M services." (the billing-validated count
  is gone); "📊 Services with primary resources were found." (before: the
  list); the "BILLING vs DISCOVERY ANALYSIS" block of `-v` is one line, and
  "💸 Some services with billing usage have no discovered resources." is its
  warning (before: one row per service, a completeness summary and a
  detection rate); targeted discovery logs no service and its failures are
  one warning, "Targeted discovery failed for N services (ERROR TYPES)". The
  Pricing warning of `--enable-cost-analysis` ends after "Estimates for it
  will be missing." (before: the first resource type and the error text).
  Warnings about one resource name the error type, not the resource or the
  error text: "Cost estimation failed for a resource (ERROR TYPE)", "Failed
  to enrich a resource (ERROR TYPE)", "Failed to process a resource (ERROR
  TYPE)", "Failed to get details for an S3 bucket (ERROR TYPE)" and the same
  for a DynamoDB table, a tagged resource, a description or a tag mapping.
  The three cost trend warnings say "an account" instead of the account ID.
  The debug lines of S3 bucket regions, Pricing and CloudWatch failures and
  resource details give the AWS error code or the exception type. The debug
  line "Cost Explorer detail" still holds AWS's error text (as the
  troubleshooting page shows).

### Removed

- The per-resource cost trend entries of `cost_analysis["cost_trends"]` (a
  service total divided by the number of resources, with `resource_id`). The
  entries are now one for each account and service, with `account_id`,
  `billing_names` and `resource_count`, and the Cost Analysis sheet shows one
  row for each account and service with a column `Billing names counted`
  (before, no sheet showed the trend).
- `inventag.core.cost_requests.trend_note()`: the CLI no longer writes its run
  note ("Cost trend: read once, with the credentials of account ..."), because
  each account's cost trend now uses that account's own credentials. A Python
  caller that gives `CostAnalyzer.analyze_cost_trends()` the rows of several
  accounts without `account_sessions` gets one warning from `CostAnalyzer`
  instead.

### Security

- The read-only guard now refuses these operations by name (each one issues a
  token, credentials, a signed URL or a session, or returns customer content):
  `cognito-idp:GetDerivedToken`,
  `wellarchitected:GetAgentOrganizationalReportData`,
  `partnercentral-marketing:GetCampaignAssetExportTask`,
  `partnercentral-selling:GetCustomerAccountBulkJobReportUrl`,
  `partnercentral-selling:GetOpportunityBulkJobReportUrl`,
  `glue:GetDashboardUrl`, `gameliftstreams:GetStreamUrl`,
  `gameliftstreams:ListStreamUrls`, `quicksight:GetDashboardEmbedUrl`,
  `quicksight:GetSessionEmbedUrl`, `polly:GetVoice`,
  `opensearchmemory:GetMemory`, `opensearchmemory:SearchMemories`,
  `opensearchmemory:SearchEvents`, `connecthealth:GetMedicalCodingJob`,
  `finspace-data:GetProgrammaticAccessCredentials` and
  `finspace-data:GetExternalDataViewAccessDetails`. InvenTag calls none of
  them. `--validate-operations` now prints BLOCKED for them.
- Masked in reports, snapshots and logs: values of the fields `IssuedToken`,
  `SecretValue`, `ImportManifestUrl`, `S3ObjectUrl`, `authorizationUrl` and
  `OAuthAuthorizationUrl`. A secret that AWS returns as a list under a masked
  field name is now masked in debug output too. Still not masked: a secret
  inside a mapping under a masked field name, or in an XML list
  (`<member>` items), in debug output; a field named only `Url`.
- `policy.lock` now also lists every file in the policy folder that a set
  names by path (any suffix, also under `tests/`), and under `tag_policies`
  the SHA-256 of each tag policy that `required-tags` reads with `policy:`.
  Before, a changed file of either kind passed `lock --check` and
  `policy check --locked`. A lock written before this release fails the check
  when the folder has such a file: run `inventag policy lock` again.
- The SARIF file no longer quotes a tag value: a required-tags problem reads
  `KEY: value not allowed` there.
  The JSON, text and Markdown files still show it.
- `policy validate` refuses a `message` placeholder with a format spec or a
  conversion (`{name:>10}`, `{name!r}`); before, such a message passed and
  `policy check` could fail or run out of memory. A pattern that repeats a
  group holding another repeat or a `|` (`(a+)+`, `(a|a)+`) is refused. A
  found text longer than 4096 characters is not matched by `name-pattern` or a
  tag `pattern` (`value_too_long`), as for `regex`. A waiver `resource` with no
  literal character (`**`, `?*`, `[a-z]*`) is refused, as `*` was.
- A set file that names itself or another set file in a loop, a chain of more
  than 10 set files, or a file with more than 50 levels of lists and mappings
  is now an error with exit code 1 that names the problem; before, it ended
  with a `RecursionError` traceback.

## [v1.4.3] - 2026-11-24

### Added

- `--finops-cost-allocation` (off by default): for each account, with that
  account's own credentials, InvenTag reads last month's spend from Cost
  Explorer (metric `UnblendedCost`) by service, by linked account and by each
  key of the built-in `finops-cost-allocation` tag policy that
  `ListCostAllocationTags` shows as active. At most 7 Cost Explorer requests
  per account: 1 `ListCostAllocationTags`, 1 `GetCostAndUsage` by service, 1
  by linked account and 1 per active key (at most 4); a further page of an
  answer counts in the same 7 (at most 3 per grouping), and a table that needs
  more is marked incomplete. The SDK's retries of a throttled request add
  requests, and AWS charges for each. The run's one warning line before
  discovery names the most requests (`cost allocation: N`). The Excel report
  gets a last sheet `FinOps costs` with the amounts as AWS returns them, never
  per resource; spend without a tag key is the row `(no value)`. The result of
  `CloudBOMGenerator.generate_multi_account_bom()` and the metadata of a JSON
  report get the additive key `finops_costs`; the state snapshot gets the
  additive key `metadata.tags.cost_allocation` (tables only, no resource IDs;
  the snapshot stays 0600). `--no-cost-in-snapshot` leaves the figures out of
  the snapshot. Read from a management (payer) account, the linked-account and
  tag tables can name member accounts the run did not scan and their tag
  values (not verified against real AWS). The change report gets a block
  "Cost, previous run to this run", or one line that says why there is no
  comparison. A denied or failed request gives a run note and, when denied, a
  `Permissions:` line; the exit code does not change. After a denied or
  throttled `GetCostAndUsage` request, no further request is made for that
  account. With `--template`, no request is made and a warning says so. New
  IAM action: `ce:ListCostAllocationTags` (in `READ_ONLY_ACTIONS` and
  `config/defaults/iam-policy-read-only.json`; the policy now has 123 read
  actions). `MultiAccountConfig` gets the fields `finops_cost_allocation` and
  `cost_in_snapshot` at its end. Without the flag, the console text, the Excel
  sheets and the snapshot are as in v1.4.2 (compared on one mocked estate).
  Not verified against real AWS: what AWS bills; that tag keys are active as
  cost allocation tags only after activation in the billing account; what a
  member account sees compared with the payer account.

## [v1.4.2] - 2026-11-24

### Added

- `--finops-checks` (off by default): six fixed FinOps checks on the resources
  the scan found. `FIN-001` EBS volume with state `available`; `FIN-002`
  Elastic IP with no association; `FIN-003` EBS snapshot that started more
  than 90 days before the run; `FIN-004` EC2 instance in the `stopped` state;
  `FIN-005` load balancer that no target group names, or classic load balancer
  with no instance; `FIN-006` a missing key of the built-in
  `finops-cost-allocation` tag policy. Results are `fail`, `not_evaluated`
  (with a reason: `identity_only`, `field_missing`, `tags_not_read`,
  `listing_not_read`) and `pass`; a gap in the data is never a pass. The Excel
  report gets a last sheet `FinOps`; the result of
  `CloudBOMGenerator.generate_multi_account_bom()` and the metadata of a JSON
  report get the additive key `finops_checks`. The checks make no AWS call,
  need no new IAM action, and their findings never change the exit code.
  Without the flag the checks do not run; tests show the same other sheets,
  console text and AWS calls with and without the flag. With `--template`, the
  checks do not run and a warning says so. From the command line the result is
  in the Excel sheet only; there is no JSON file. `FIN-003` is `not_evaluated`
  when the run has no start time: the checks never read the clock. Not
  verified against real AWS: that the listings carry the fields each check
  needs on every account type. In Python, `MultiAccountConfig` gets the field
  `finops_checks` (default `False`) as its last field, so code that passes the
  other fields by position works as before.

## [v1.4.1] - 2026-11-24

### Added

- Packaging: after a release, the package workflow writes the new Homebrew
  formula to the tap `habhabhabs/homebrew-inventag` (job `publish-tap`). It
  runs only after the files are attached to the release and the formula
  install check passed. A failure there leaves the release, PyPI and the
  attached files as they are, and the job prints the steps to publish by hand.
  Homebrew installs InvenTag on Apple Silicon Macs and on Linux (x86_64 and
  arm64). Intel Macs are not supported. Not verified against GitHub: the job,
  until the first release run after v1.4.0.

### Changed

- With `--enable-cost-analysis`, the run says once, before discovery, how many
  Cost Explorer requests it will make at most (`Cost Explorer: up to N request(s)
  ...`), as a warning. Without that flag the line is at info level
  (`--verbose`).
- With `--enable-cost-analysis`, a Cost Explorer figure that cannot be read is
  now one warning per error type (`Cost analysis: the cost trend failed for
  some resources (<error>); those services have no trend.`). v1.4.0 logged it
  at debug level only.

### Fixed

- `--enable-cost-analysis` made one Cost Explorer request for each service
  that has resources (21 requests on a 21-service account), and AWS charges for
  each. Every request asked for the same two months, grouped by service. The
  cost trend now makes one request for the whole run and reads every service
  from it; the trend values do not change. Cost Explorer requests in one run:
  at most one for each account when billing validation is on (the default),
  and at most one more for the whole run with `--enable-cost-analysis`. A
  single-account run with both makes at most 2; with `--no-billing-validation`
  it makes at most 1. A throttled request is retried, up to 10 attempts in all,
  and each retry is one more request. AWS charges for each request. The
  `--help` of `--enable-cost-analysis` and the docs say the number. No new IAM
  action. Not verified against real AWS: the number of billed requests, and
  whether AWS bills a retry.
- A run with several accounts and `--enable-cost-analysis` now says whose bill
  the cost trend read, as a warning and a run note: "Cost trend: read once,
  with the credentials of account <id>. Its figures are that account's Cost
  Explorer view, not each account's own." Reading each account's own bill is
  planned for v1.5.0.
- A SIGTERM that arrived while the process wrote to standard output could lose
  its "Terminated (SIGTERM)" line, or wait on that write. The line is now one
  write on each log stream's file descriptor, in the same format, so it is
  printed and the process ends by the signal with the same status. The first
  SIGTERM waits on a stalled reader of standard output; a second one ends the
  run.
- Packaging: a re-run of the release upload checked only for missing files, so
  a file of an earlier run with another name stayed beside the new
  `SHA256SUMS`. The upload now also fails on a file that is neither in this
  upload nor one of the two source archives, and names the command that
  deletes it. Not verified against GitHub: the check, until the first release
  run after v1.4.0.

## [v1.4.0] - 2026-11-21

### Added

- `--concurrency N` (1 to 256, default 64): the most AWS requests in flight at
  once for the whole run. `--concurrency 1` sends one request at a time. A
  value outside the range stops with exit code 2. `--max-concurrent-accounts 0`
  still exits with code 1, as in v1.3.x; changing it to 2 is on the list for
  v2.0.0. `spec.concurrency` sets the same limit in a config template; a value
  out of range there is a template error (exit code 1). Discovery, the network
  and security analyses and the per-resource detail calls share that limit. The
  run makes the same AWS calls as v1.3.1 and writes the same files in the same
  order whatever the value. Not verified against real AWS: any speed-up. The
  tests use a simulated AWS with a fixed delay per request.
- `inventag selftest`: an install check that makes no AWS call and opens no
  network connection. `inventag completion bash|zsh|fish` prints a shell
  completion script.
- When a run is not allowed to use an IAM action, the run notes have one
  "Permissions:" line for each account that names each action, what the report
  lacks because of it, and whether the AWS managed policy ReadOnlyAccess
  includes it. The line is also in the Summary sheet and the Word report. The
  result, the JSON report metadata and the `--audit-output` file get a
  `permissions_denied` list. A refused report upload (`s3:PutObject`) is named
  for "the identity that uploads the reports (the default credentials)", not
  for an account; its `permissions_denied` entry has an empty `account`. A run
  that was denied nothing prints and writes nothing new.
- Packaging: build files for a one-directory executable, a `.deb`, an `.rpm`
  and a container image; hash-pinned build locks; a licence check of every
  file in the bundle; `THIRD-PARTY-LICENSES.txt`; and a Homebrew formula in
  `packaging/homebrew-tap` that is not published. The package workflow builds
  them, runs install checks on fresh systems and attaches the files, `SHA256SUMS`,
  SBOMs and build attestations to a release. The version of a package comes
  only from `inventag/_version.py`. Not verified against GitHub: the first
  real release run and `gh attestation verify` on its files.

### Changed

- The credentials of the accounts are checked in parallel, up to
  `--max-concurrent-accounts`. The results keep the configured order. The
  regions of one account are still checked one after another.
- Log lines written by discovery worker threads carry the account name, like
  the other lines of that account.
- When a Permissions line is the only note of a run, it is printed under the
  header "Notes about this run:".
- Per-resource detail calls (S3, Lambda, RDS, CloudFormation and EKS) run in
  parallel, at most 4 at once for each service and region. The same calls are
  made.
- Rows with an equal ARN, service, type, id and region come out in a fixed
  order (a digest of the row).
- The network and security analyses read regions in sorted order and at the
  same time. Capacity warnings and recommendations are listed in one fixed
  order, not an order that varied with the Python hash seed. Cost estimates,
  the coverage ledger and the document generation results are also listed in a
  fixed order.

### Fixed

- The change report no longer lists a resource as modified when one of its
  detail calls (for example S3 `GetBucketLocation` or Lambda
  `GetFunctionConfiguration`) was denied, throttled or timed out in one of the
  two runs. The fields that call adds are not compared for the resources of
  that service and region, and the report names those units in one line. A
  snapshot records the units whose detail calls failed in
  `metadata.tags.details_not_read` (present only when one failed). (A-78)
- With several accounts scanned in parallel, rows and analysis sheets follow
  the configured account order, not the order in which the accounts finish. A
  resource found in a shared estate is credited to the first configured
  account. The snapshot lists its regions sorted.
- The account id was sometimes read twice when listings started together, and
  the "already warned" check could print one warning twice.
- SIGTERM could hang the process when the main thread held a lock that the
  signal handler needed. The handler now takes none of the run's locks: it stops
  new AWS requests, prints its line and ends by the signal.

### Library notes

- Threads on the same API now share one client, so they share one SDK retry
  quota (botocore `standard`: 500 units for each client, 5 for each throttling
  retry). The retry settings in your environment still apply. Cost Explorer
  clients are never shared.
- A second scan on the same boto3 session object starts with new clients, so
  it waits on its own time limit.

### Licences

- InvenTag stays under the MIT license. The packaged builds (the executable
  archives, the `.deb`, the `.rpm` and the Homebrew archive) carry GNU libiconv under the LGPL 2.1, linked into the extension
  modules of lxml. The lxml files are carried unchanged from the lxml wheel on
  PyPI and are separate files that you can replace. `THIRD-PARTY-LICENSES.txt`
  lists the components, the licence texts and the source addresses. A pip,
  pipx or uv install does not carry libiconv in a file of InvenTag. This is
  not legal advice.

## [v1.3.1] - 2026-11-20

### Security

- The read-only guard blocks 9 more operations: `sts:GetWebIdentityToken`,
  `sts:GetScopedCredentials` (new in botocore 1.44.7),
  `stepfunctions:GetActivityTask`, the four Lake Formation
  `GetTemporaryDataLocationCredentials`, `GetTemporaryGlueFunctionCredentials`,
  `GetTemporaryGluePartitionCredentials` and
  `GetTemporaryGlueTableCredentials` calls, and
  `payment-cryptography:GetParametersForImport` and `GetParametersForExport`.
  Their names start with `Get`, so the guard allowed them, but they issue a
  token, AWS credentials or key material, or take a task from an activity's
  queue. InvenTag never called them. For these 9 operations
  `--validate-operations` now prints BLOCKED and exits 1 (v1.3.0: ALLOWED,
  exit 0).
- The guard blocks `datazone:GetConnection` with `withSecret=true`, which
  returns the connection's credentials; without it the call is still allowed.
  `--validate-operations` prints "blocked when withSecret=true" for it.
  The parameter rules of the guard now also apply to presigned URLs.
- 18 more field names that AWS documents as secrets or tokens are masked
  (`***REDACTED***`) in reports, JSON output, snapshots, checkpoints and logs:
  `PreSharedKey`, `passphrase`, `SecretToken`, `WebIdentityToken`,
  `jwtToken`, `PlayerGatewayToken`, `DeviceToken`, `VoipDeviceToken`,
  `TokenValue`, `BillingToken`, `taskToken`, `CallbackToken`,
  `WorkUnitToken`, `registrationToken`, `ExportToken`, `ImportToken`,
  `PurchaseToken` and `offerToken`. InvenTag does not call the operations that
  return these fields. The names are also masked inside JSON text that
  InvenTag reads, such as an EventBridge event pattern. If one of your
  resources uses such a name there, its value now shows as `***REDACTED***`,
  and the first change report after the upgrade lists that resource as
  modified. The names `secret`, `authKey` and `AccessKey` are not added,
  because AWS also uses them for harmless fields.

## [v1.3.0] - 2026-11-19

### Changed

- `--account-services` and `services` in a config template now limit which
  services are scanned, not only which are reported. The report holds the
  same rows for the chosen services; the run makes fewer API calls and prints
  no warnings about other services. A service left out this way is not
  reported as removed in the change report, and the snapshot's coverage
  summary counts the listings left out as `out_of_scope` (decision 15).
- Discovery makes one Cost Explorer request per account (was two); billing
  validation and the spend column share the answer (decision 17). Billing
  validation now reads the same period as the spend column (from 30 days
  before the first day of the month to today, instead of the last 30 days), so
  a service billed only in that longer period now counts as billed: it gets a
  spend value and `billing_validated` true. The fields `cost_last_30_days` and
  `billing_cost_30d` of rows found through billing cover the same longer
  period; their names are unchanged. The `--verbose` billing line names the
  start of that period instead of "last 30 days".
- Snapshots record which listings were not read
  (`metadata.tags.units_not_read`: account, service, region, source and
  outcome; present only when a listing failed). The next change report leaves
  the resources of those listings out instead of showing them as added. The
  snapshot schema stays 1.1, and earlier versions read such a snapshot and
  ignore the key (decision 6). A change report made by an earlier version
  after a v1.3.0 run shows each EKS cluster as modified once (the cluster's
  VPC settings, recorded since this release).
- Snapshots record the InvenTag version that wrote them
  (`metadata.tags.inventag_version`). The first change report after an upgrade
  does not count a field that the new version reads for the first time as a
  change, and says in one line how many fields it left out; a real change to
  such a field in that window is not reported, once.
- The change report lists attribute changes in a fixed order, so two reports
  of the same change are identical (decision 11).
- A scan no longer starts the optimized discovery engine, whose result no
  report used. The progress line "🚀 Optimized intelligent resource discovery"
  and its `--verbose` lines ("Starting optimized AWS discovery ...",
  "Intelligent discovery found N resources ...") are gone.
- Library callers: `AWSResourceInventory.upload_to_s3` needs
  `allow_write=True`, and the uploaded object is encrypted (SSE-S3).
- Per-account reports (`--per-account-reports`) of every account, not only
  the first, get the network and security enrichment columns.
- EKS clusters make one `eks:DescribeCluster` call each, to record their VPC
  settings for the network analysis. The field adds no report column. The
  shipped read-only policy already allows the call.

### Fixed

- An account whose time limit ran out no longer keeps the process alive: a
  call or listing still waiting is cut off, and the run ends right after the
  report is written.
- An empty result under `--account-services` or `--account-tags` names the
  filter and says to run without it to see every resource. Without a filter
  the message is as before. Exit codes are unchanged.
- Run notes are masked like the log, so a secret in an error text does not
  reach the report or the run result.
- `--validate-credentials` gives the scan's verdict for an accounts-file entry
  without credentials in another account: it assumes the cross-account role
  there, also a role named with `--cross-account-role`.
- A profile that needs an MFA code, run with no terminal, stops at once with a
  message that names the profile and `aws sts get-session-token`, both for the
  default credentials and for an accounts-file entry, and in
  `--validate-credentials`. Before, the run waited for input that could not
  come, or printed a stray "Password input may be echoed" line. With a
  terminal, the code is asked for as before.
- The account check uses the STS endpoint of the scanned partition (GovCloud,
  China), and a region of another partition than the credentials' is named in
  a warning.
- The account's identity is looked up once per account, so repeated runs make
  the same number of `sts:GetCallerIdentity` calls.
- Two accounts that share one session object each keep their own time limit
  (library use).
- An account in which only some resources of the chosen services were read is
  named as partly read, not as "every listing denied", when
  `--account-services` is set.
- The change report says that an account was read only in part (for example,
  its session expired) instead of saying that it could not be scanned.
- When the Tagging API did not answer for a region, the change report no
  longer shows that region's resources as having changed tags.
- The change report lists related resources for snapshots written by the CLI
  (read from the AWS data, as the network and security analysis do), each
  related resource once; the Lambda, security group and Auto Scaling
  dependency patterns now apply.
- The consolidated report of a multi-account run analyses every account's
  network and security groups with that account's own credentials.
- Network analysis counts RDS and Aurora clusters through a DB subnet group of
  their own account, MSK clusters through their broker subnets and EKS
  clusters through their subnets. EFS file systems are still not counted.
- A subnet whose route table sends the two halves of the address space
  (`0.0.0.0/1` and `128.0.0.0/1`, or `::/1` and `8000::/1`) to an internet
  gateway counts as public.
- Discovery, the analyzers, the cost analysis, the report upload of the CLI and
  of the CI/CD integration, the compliance checker and the legacy scripts all
  create their AWS clients with the same retry settings (standard mode, 10
  tries; `AWS_RETRY_MODE` and `AWS_MAX_ATTEMPTS` win). The cost analysis no
  longer adds a second retry loop of its own.
- Failures that only the debug log knew about now give one warning per cause,
  in discovery and in the cost analysis (`--enable-cost-analysis`), where a
  cost that could not be worked out looked like no cost.
- `inventag --version` and every scan start faster: the unused compliance
  modules and `psutil` load only when first used. `ComplianceManager.close()`
  stops its monitoring thread.
- The help texts of `--billing-validation` and `--enable-cost-analysis` say
  that the two are independent.
- The template field reference says where an account's `account_name` appears,
  and that `spec.services` limits the scan.

## [v1.2.2] - 2026-11-19

### Fixed

- A slow Cost Explorer answer no longer costs a whole account when
  `--account-processing-timeout` is below 1200 seconds. Each Cost Explorer
  call then waits at most a fortieth of the limit, and at least 5 seconds, to
  connect and to read, with two attempts (instead of botocore's 60 seconds
  and up to ten attempts). If it does not answer in time, the account's
  resources are still listed and in the report, and a run note says that its
  billing data is missing. Such a run now exits with 0 (or 5 with
  `--fail-on-account-error` only if another account failed), where it exited
  with 1 or 5 because the account was lost. With the default limit nothing
  changes.
- After an account is given up at its time limit, its call under way is no
  longer retried, so the run ends sooner after the summary. A listing that
  hangs is still retried as before, so the process can stay alive until it
  ends.
- A snapshot that could not be saved, a snapshot list (`metadata.json`) that
  could not be updated, or a change report that failed is now named in the
  run notes, with the folder to check, and the console's completion line no
  longer calls such a run successful. The exit code is unchanged.
- An empty result with `--s3-bucket` says that there is nothing to upload and
  why, instead of "S3 upload failed". The exit code is still 1.
- A region in `--account-regions` (or the accounts file) whose region check
  fails and that the installed boto3 does not know is named once, with both
  possible causes (a misspelled name, or a region newer than boto3) and how to
  list the valid ones, instead of a raw error text. A run note says it was not
  scanned. A region that boto3 does not know but whose check passes is scanned
  as before. The exit code is unchanged.
- A failed Cost Explorer read prints one warning that says billing data is
  missing, why, and the next step (before: up to three lines, and "not
  enabled" asked for a permission). A Cost Explorer call that did not answer
  in time says so, in the words of the run note, instead of blaming the
  network.
- A listing that AWS answers with `OptInRequired` says the service needs an
  opt-in. A service with several listings (for example ECS) no longer says
  all its resources are skipped when only one listing was denied.
- Detail calls that failed (a bucket's location, a Lambda function's
  configuration, RDS, CloudFormation stacks, CloudFront certificates) and
  clients that could not be created are recorded in the coverage list, warned
  about once, and named in the run notes with how many resources have fields
  missing. "Nothing configured" answers are not reported. Such a failure does
  not make a resource "not compared" in the change report.
- An answer in the wrong form no longer makes a false row (for example a row
  named `oops`); the unreadable items are skipped with one warning and the
  good items are kept. That listing counts as failed: a run note says the
  report is partial for that service and region, and the change report does
  not compare it. An item without an ID that InvenTag knows, which was
  dropped without a word, now gives the same warning.
- With `--template`, a report format that cannot be written no longer stops
  the other formats; the failed format is named in one error line and in the
  run notes of the files that were written. A tag compliance JSON that cannot
  be written is one error line too, and the report formats are still written.
  The exit code is unchanged (1).
- Ctrl-C and SIGTERM print one visible line that says what was written. The
  exit status is unchanged.
- With `--resume`, a reused account is named once on the console.
- With `--per-account-reports`, each account's Network and Security sheets are
  read with that account's own credentials, not the first account's. With
  network or security analysis, the service sheets of each account (EC2, VPC
  and others) now also get the network and security columns that a
  single-account run already has.
- Network analysis counts an ElastiCache cluster in its VPC and in each subnet
  of its subnet group (it reads `elasticache:DescribeCacheSubnetGroups`,
  already in the read-only policy), and no longer counts an RDS DB subnet
  group as a resource of its VPC and subnets. A cluster is matched only to a
  subnet group of its own account. If the subnet groups of a region cannot be
  read, the Network Analysis sheet is written as before without those
  clusters, with one warning and a run note.
- The legacy tag compliance checker and the legacy inventory script allow the
  read-only guard's upload exception only for the bucket you name, not for any
  bucket on that client.
- These files are now written whole or not at all, so a failed write keeps the
  older file of the same name and leaves no temporary file: the JSON output,
  the change log, `--audit-output`, the tag compliance JSON of a template run,
  the credential file of the credential manager, the CI/CD artifacts and
  metrics file, the generation report, the CSV report, saved configuration
  and template files, and the checker's plain-text report. A new file gets
  the mode it got before, and a file that is written again keeps its mode.
  An `--audit-output` path that is a symlink or a named pipe is handled as
  before (a symlink is refused with exit code 1; a pipe receives the JSON).

### Changed

- A run without an output flag, and the warning list of `--validate-config`
  and `--validate-config-only`, no longer show "No output format specified.
  Use --create-word or --create-excel". The line that says Excel is the
  default stays.
- The help text of `--fail-on-account-error` says that exit code 5 covers an
  account that could not be scanned or ran out of time.
- The template field reference corrects five descriptions that the code
  contradicted (tag description, Word column width, company name, logo alt
  text, tag policy precedence).

## [v1.2.1] - 2026-11-15

### Fixed

- `--resume` no longer reuses an account whose session expired during the
  scan (`ExpiredToken`, `ExpiredTokenException`, `RequestExpired`). Such an
  account was read only in part, so it is not saved under `state/partial/`
  and the next run with `--resume` scans it again. The resume hint counts it
  among the accounts still to scan. A listing that is only denied still lets
  the account be saved.
- An account for which a run read nothing (every service listing denied or
  failed, and no resource from the Tagging API either) no longer becomes the
  baseline of the change report. The snapshot lists it under
  `accounts_failed`, so the next run neither reports its resources as removed
  nor, after it, as added. The report's Run notes and one warning name the
  account. A run in which nothing was read saves no snapshot, and its message
  says "nothing could be read" instead of "none found, or the filters removed
  all of them". When every service listing is denied but the Tagging API
  returns resources, the account is compared as before (a deleted tagged
  resource shows as removed, a changed tag as modified); a note says the
  report holds only what the Tagging API returned, and resources whose
  listing failed are not compared. Exit codes are unchanged.
- A session that expires during the scan is now visible: the report's Run
  notes say the account is incomplete and how many listings were not read,
  one error line names the account, and the snapshot lists it under
  `accounts_failed`, so the next change report does not show its unread
  resources as removed. The exit code stays 0, also with
  `--fail-on-account-error`.
- The report's Run notes name what was not read: the listings that were
  denied, throttled or failed, grouped by service and region with the reason
  ("Not read in account 123456789012, so the report is partial there:
  dynamodb in us-east-1 (throttled)", at most ten, then "and N more"), and
  the regions the region check skipped. Before, only the log said so and the
  Summary sheet showed 100.0 %. A run with no such listing shows no note, as
  before.
- A call blocked by the read-only guard is no longer hidden behind a
  successful run. The run notes name each blocked operation and say that it
  is a defect in InvenTag, not in your account, to be reported; one error
  line says the same, also for a block while the state snapshot is saved.
  The exit code is unchanged.
- The console prints the run notes after the summary, each once, as
  warnings. A note that already appeared as a log line of the run (an
  expired session, an account that read nothing, a guard block) and the
  accounts the "not scanned" block lists are not repeated. A run without
  notes prints nothing new.
- Reports made with `--template` name the accounts that were not scanned, or
  only partly, and the reason: "Run notes" lines at the end of the Summary
  sheet (Excel) and the Summary section (Word), the same lines as the default
  report. A template with `summary_sheet: false` gets the Summary sheet when
  there are notes. A run with nothing to report gives the same files as
  before.
- The change report no longer shows resources as removed when this run
  could not read them: a resource whose service listing was denied,
  throttled or failed in this run, or that lies in a region or service this
  run did not scan, is counted under `resources_not_compared` instead. A
  resource the Tagging API returned before is still compared when the Tagging
  API read its region in this run. A run that read everything gives the same
  report as before.
- A previous snapshot whose `resources` holds entries that are not objects is
  skipped with the file named (before: "'str' object has no attribute
  'get'"). A previous snapshot in an older format (such as one written by
  v1.1.4) gives one warning that the change report may list format
  differences.
- Change tracking is faster when many resources change. The search for
  related resources looked at the whole new snapshot once for every changed
  EC2, RDS, S3 or VPC resource, so its time grew with the square of the
  estate (about 3 seconds for 1,600 changed resources, 4 times more when the
  estate doubled). It now uses a lookup built once per comparison (0.1
  seconds for the same run). The change report and the changelog are the
  same as before.
- An expired or missing IAM Identity Center (SSO) login stops the run with
  one message that names the profile and the command `aws sso login
  --profile <name>`. A profile that needs an MFA code, run with no terminal,
  stops with a message and the `aws sts get-session-token` command. Before,
  both ended in a traceback (and the MFA case with an empty message). Exit
  code 1, as before. With `--debug` the full traceback is still logged.
- `--audit-output`, `--log-file` and `--output-directory` with a path that
  cannot be written (for example a folder that is a file) stop the run at
  the start with one message that names the option and the path, before any
  AWS call. Before, the first two ended in a traceback and the third after
  the whole scan. Exit code 1, as before.
- An account that could not be reached because of an error without a
  message (for example an MFA prompt with no terminal, in an
  `--accounts-file` run) is reported with the error's type instead of an
  empty reason.
- A scan no longer raises one hidden error for each resource in the BOM
  processor (it called a service enrichment method that does not exist).
  Service attribute enrichment has never run; reports are unchanged. If a
  `--bom-config` file sets `enable_service_enrichment: true`, one warning
  says the setting has no effect in this version.
- Network analysis counts a resource in every subnet its data names, and
  reads the subnets of load balancers. On the "Network Analysis" sheet, the
  "Associated Resources" column of the subnet table was too low for a
  resource in several subnets (a Lambda function, an RDS instance) and
  missed application and network load balancers; those numbers rise. VPC
  counts, the resource rows and the change report do not change.
- With `--enable-network-analysis` or `--enable-security-analysis`, the
  analysis calls (the `ec2:Describe*` reads of VPCs, subnets, route tables,
  gateways, network interfaces and security groups) are made once per run
  instead of twice. The reports are the same.
- S3 upload says what happened. After a run with a failed file, one line
  names the files that were uploaded and the files that failed, or says that
  no file was uploaded. A `PermanentRedirect` error from S3 carries a hint to
  set `AWS_DEFAULT_REGION` to the bucket's region. When a report format
  failed, so nothing is uploaded, the log says so and that the files written
  are in the output folder (before, the upload was skipped without a word).
  When the Google Doc fails after the Google Sheet was created, the error
  names the Sheet URL. Exit codes and uploads are unchanged.
- The read-only guard allows the upload of reports only to the bucket named
  with `--s3-bucket`, not to any bucket on the uploader's client. A call to
  another bucket is blocked; no call that was blocked before is allowed now.

### Changed

- Clearer messages, no change of exit codes: the credential check names
  `aws sso login --profile <name>` and `AWS_PROFILE`, tells network and
  timeout failures apart (network, `HTTPS_PROXY`, `--credential-timeout`)
  and names the error type; the "all accounts failed" summary gives the
  cause per account; an unexpected error names its type and says to run with
  `--debug`; the accounts file warns about a second entry for one account ID
  and about unknown keys (a typo such as `profil_name`), also with
  `--validate-config-only`;
  `--compliance-standard` and `--disable-production-safety` (still exit 2)
  say what to do instead. The accounts examples in `examples/` hold only keys
  InvenTag reads, so they load without a warning.
- `inventag --validate-operations` shows, for an operation that is allowed
  by name but blocked with a parameter that returns secrets, the parameter
  (for example `ALLOWED  ec2:DescribeInstanceAttribute (...); blocked when
  Attribute=userdata`). The line still starts with ALLOWED and the exit code
  does not change. Other lines are unchanged.
- `--validate-config-only` reads the `--bom-config` file the way a run does:
  a wrong value gives one warning that names the file and the key and says
  that a real run stops with exit code 1 on this file. The exit code of the
  validation mode stays 0, as before. Unknown keys are a warning too. A
  service descriptions file that the run would ignore (no top-level
  `service_descriptions` key, or an entry without `description`) gets a
  warning that says so; exit codes do not change.
- The template field reference describes `spec.services` as it works: it
  limits the services in the report, while the scan still reads every
  service, so warnings about other services can appear.

## [v1.2.0] - 2026-11-14

### Upgrade notes

- The new listings need more read-only IAM actions (see
  `config/defaults/iam-policy-read-only.json`). With a v1.1.4 policy the run
  still works: each denied listing is a warning, and those resources are found
  through the Tagging API as before, when they are tagged.
- The first change report after the upgrade compares with a v1.1.4 snapshot.
  Resources of the newly listed services show as added, although they existed
  before. Values that are now masked (`***REDACTED***`) show as changed.
- Exit codes 5 and 6 are opt-in (`--fail-on-account-error`,
  `--fail-if-empty`). Conflicting options now stop with exit code 2, and a
  report format that cannot be written exits with code 1 (see "Changed").
- Resources that v1.1.4 found only through the Tagging API keep their service
  name and sheet (for example `ELASTICFILESYSTEM`, `STATES`, `COGNITO-IDP`,
  `ELASTICMAPREDUCE`, `KAFKA`, `ES`). Their rows now carry the details of the
  service API, and the ID column of Secrets Manager secrets and MSK clusters
  holds the name instead of the last part of the ARN.

### Added

- InvenTag lists 22 more services with their own read-only calls: ElastiCache,
  Redshift, Redshift Serverless, OpenSearch, EFS, ECR, Step Functions, Kinesis,
  Firehose, Secrets Manager (names only, through `ListSecrets`), Systems
  Manager parameters (names only, through `DescribeParameters`), Auto Scaling
  groups, Backup vaults, Cognito user pools, CodeBuild projects, CodePipeline,
  Athena workgroups, EMR, MSK, AppSync, Elastic Beanstalk and WAF web ACLs.
  The read-only IAM policy file lists the new actions.
- Every row has a `source` column (`service-api`, `tagging-api` or `billing`),
  a `sources` column and a `detail_level` column, so you can see which API
  returned it.
- The JSON output and the state snapshot record what discovery attempted and
  how each listing call ended (ok, empty, denied, throttled, error or timeout).
- `--resume` reuses the results of accounts that finished in an earlier run of
  the same command that did not complete, and scans only the others.
  `--resume-max-age-hours` sets how old those results may be (default 24).
  After a run with failed accounts, the finished accounts are saved under
  `<output directory>/state/partial/`; a run where every account finished
  removes them.
- `--state-retention-days` and `--state-max-snapshots` set how many state
  snapshots are kept (defaults 30 days and 100 snapshots; `0` or `none` keeps
  all).
- `--fail-on-account-error` makes the run exit with code 5 when an account
  could not be scanned completely. `--fail-if-empty` makes it exit with code 6
  when there is nothing to report. Without these flags the exit codes are as
  before.
- When `ec2:DescribeRegions` fails, InvenTag reads the enabled regions with
  `account:ListRegions`, and then tries every region of the partition, instead
  of four fixed regions. China and GovCloud accounts use their own home
  regions for global services, Cost Explorer and the Tagging API. When
  `ec2:DescribeRegions` is denied in every region, every region is scanned
  (before, none were).

### Changed

- `--account-processing-timeout` is a limit per account, counted from when
  that account's scan starts. An account that runs out of time is reported as
  failed and the other accounts are kept. The resources it found before the
  limit stay in the report, and the report says the account is incomplete.
  Discovery's own listing limit follows this setting instead of a fixed 10
  minutes. If every account failed but some found resources before their
  limit, the reports are written, no snapshot is saved, and the run exits
  with code 1.
- A failed listing call (throttled after the retries, or any error other than
  access denied) is logged as a warning for that service and region, instead
  of looking like "no resources". Throttled calls are retried up to 10 times
  (standard retry mode); `AWS_RETRY_MODE` and `AWS_MAX_ATTEMPTS` override this.
- A report format that cannot be written makes the run exit with code 1.
- Excel sheet names are made valid and unique (characters Excel does not allow
  become `-`, a repeated name gets ` (2)`); the log names each changed sheet.
- Reports are written to a temporary file and moved into place, so a failed
  save leaves no partial file and keeps the previous report.
- Word tables that are cut say how many resources are not listed and that the
  Excel report lists all of them.
- Change tracking treats lists as unordered, except lists whose order is
  configuration (Lambda layers, Auto Scaling termination policies, CloudFront
  cache behaviors), and ignores fields that change on every run (discovery
  route, cost figures, usage counters). A resource that one run found only
  through the Tagging API and the other through its service API is compared
  by its tags only. Accounts that
  failed in either of the two runs are left out of the comparison, and the
  change report names them.
- Conflicting options now stop with exit code 2: `--accounts-file` with
  `--accounts-prompt`, a full role ARN in `--cross-account-role` with an
  accounts file, `--s3-kms-key-id` without `--s3-encryption aws:kms`, and
  `--resume` with `--disable-state-management`.
- `--bom-config` checks the type of each value and stops with exit code 1
  naming the key. Accounts files, tag-mapping files, service-description files
  and `--bom-config` are read as UTF-8 with or without a byte order mark, and
  a key written twice is an error.
- With `--enable-network-analysis` or `--enable-security-analysis`, the
  resource sheets of EC2, VPC, load balancers and RDS get the network columns
  (`vpc_id`, `subnet_id`, `security_groups`, `max_security_risk` ...), because
  the analysis now reads the IDs from the API data.
- An API field that is a map keyed by IDs (for example Secrets Manager
  `SecretVersionsToStages`) is one JSON cell, not one column per ID.
- Every log line is printed once, and warnings from discovery (for example a
  failed listing) use the normal log format and are written to `--log-file`.
- With `--template`, a warning says when the columns added by `--tag-mappings`
  or `--service-descriptions` are not shown by the template.
- A description in a `--service-descriptions` file replaces the built-in one,
  also for S3, EC2, RDS, Lambda and VPC.
- The development script `scripts/development/cicd_bom_generation.py` no
  longer changes the bucket's lifecycle rules by default
  (`--s3-lifecycle-days` defaults to 0).

### Fixed

- Network analysis: a subnet is public only when its route table sends
  `0.0.0.0/0` or `::/0` to an internet gateway (before, every subnet of a VPC
  with an internet gateway was public). Lists of VPCs, subnets and gateways
  are read page by page. IPv6-only subnets no longer stop the analysis.
  Resources are counted in their VPC, subnet and security group.
- Security analysis: port ranges, all-traffic rules and ICMP are rated
  correctly (for example 20-25 open to the internet is critical). Outbound
  rules are rated low. A group counts as unused only when no network interface
  uses it.
- Discovery lists every page of every call, ECS services in every cluster,
  WorkMail organizations, and SQS queues beyond 1,000 per region. Lambda, RDS
  and CloudFormation details are read in the resource's own region.
- A resource whose name starts with `vpc-`, `sg-` or similar is no longer moved
  to the VPC service unless it is an EC2 resource.
- No row is added for a resource that no API returned (the "AI prediction"
  code was removed).
- The `monthly_spend` column shows the billed amount of the service, like
  `service_monthly_spend` (it was always 0.0).
- Resources with the same ID in two accounts are no longer merged into one.
- IAM Identity Center (SSO) and web-identity profiles work under the read-only
  guard.
- `--credential-timeout` also applies to AssumeRole and the identity checks.
- State snapshots are written atomically, a corrupt snapshot is skipped with a
  message, and two runs in the same folder no longer overwrite each other.
- The older tag compliance checker script ignores `aws:` system tags, says
  which policy fields it does not enforce, and fills the compliance status
  column of its BOM. Its `--s3-bucket` upload still works.
- Library use of `CloudBOMGenerator` with `compliance_policies` runs the tag
  check instead of failing.

### Security

- Values that often hold secrets are replaced by `***REDACTED***` in reports,
  JSON output, state snapshots, resume checkpoints and logs: Lambda and App
  Runner environment variables, ECS and CodeBuild environment values, EC2 user
  data, CloudFormation parameter values, Glue job arguments and connection
  properties, passwords, client secrets, tokens and private keys. The names
  stay. Secrets in other fields (descriptions, tags, free text) are not
  recognised. Reports and snapshots written by earlier versions may contain
  such values: delete or restrict old `bom_output/` folders and shared copies.
  The first run after the upgrade shows changed values in the change report.
  Also masked: Glue trigger and job-run arguments, CloudFormation output
  values, stack set template bodies, connection strings, tokens (including
  access, refresh and join tokens), presigned and other signed URLs,
  activation codes, and secret fields inside JSON text.
- The read-only guard blocks more calls that return secrets or contents (for
  example `cloudformation:GetTemplate`, Athena query results,
  `ec2:GetLaunchTemplateData`, API keys with their values), checks presigned
  URLs and database auth tokens, and blocks `ec2:DescribeInstanceAttribute`
  for user data. It also blocks reads whose purpose is a signed URL, a file or
  document body, command output or a stored definition with secrets (for
  example SSM `GetDocument` and `GetCommandInvocation`, API Gateway exports,
  Data Pipeline definitions), and `cognito-identity:GetId`, which creates an
  identity. Operations that InvenTag chooses by name at run time are checked
  against the same rules, also when InvenTag is used as a library.
- The older scripts in `scripts/legacy/` run under the read-only guard, write
  owner-only files and redact their logs. The legacy inventory script uploads
  with `--s3-bucket` through a client that can only call `PutObject`, with
  SSE-S3.
- The read-only IAM policy no longer includes `cloudtrail:LookupEvents` (no
  code calls it, and it returns request parameters). It lists 122 read
  actions.
- `CredentialManager.setup_cross_account_roles()` and the S3 lifecycle helper
  write to AWS only when called with an explicit opt-in
  (`allow_iam_writes=True`, `allow_bucket_writes=True`); the read-only guard
  still blocks them in a CLI run.
- A warning is printed when an accounts file that holds access keys can be
  read by other users.

## [v1.1.4] - 2026-11-13

### Added

- `inventag --version` prints the installed version. `python -m inventag` runs
  the same command as `inventag`.

### Added (documentation site)

- The documentation site is also available in Traditional Chinese, Spanish
  and French, and has a read-aloud button.

### Fixed

- `--enable-cost-analysis`: a Pricing API lookup is made once per distinct
  service and filter set, and its result, including "no price" and a failed
  call, is reused for the rest of the run. Before, failed lookups were repeated
  for every resource. A throttled lookup is retried once before it counts as
  failed. Each failure reason is logged once at WARNING level.
- `--enable-cost-analysis`: each EC2 instance type, EBS volume type, RDS class
  and engine, and S3 storage class gets its own price. Before, they shared the
  first price looked up for that resource type in that region.
- `--enable-cost-analysis` with `--cross-account-role` or an accounts file:
  Pricing API calls use the same session as the other cost calls (the first
  scanned account's credentials). Before, they used the default credentials,
  so they failed when the machine had none.
- `jsonschema` is a declared dependency. The schema checks in
  `inventag/reporting/configuration_manager.py` need it; a clean install did
  not have it, so they reported "jsonschema library not available" instead of
  checking.

## [v1.1.3] - 2026-11-13

### Changed

- The documentation site is available in English and Simplified Chinese, with
  a language dropdown, translated interface text and translated key pages. The
  page tree is in the menu, and the docs column lines up with the navbar and
  footer.

## [v1.1.2] - 2026-11-13

### Fixed

- Documentation versions: the v1.0.2 snapshot is added, a stray
  `docs/index.md` is removed, and a release archives the docs of the right
  previous release.

### Changed

- The desktop sidebar uses the same two-level menu as the phone. A menu button
  replaces the collapse arrow.

## [v1.1.1] - 2026-11-13

### Fixed

- The search palette passes the type check. The docs archive step starts from
  an empty folder so renamed files are not duplicated.

### Changed

- The sample downloads on the documentation site are regenerated with real
  ARNs and corrected tag matching.
- The phone menu is a full-screen sheet. Nothing from the page navbar shows
  beside it.
- The docs for release v1.1.0 are archived.

## [v1.1.0] - 2026-11-13

### Added

- Google Sheets and Google Docs output: `--create-google-sheets` and
  `--create-google-docs` write the Excel and Word reports as Google files.
  Install with `pip install "inventag-aws[google]"`. New flags:
  `--google-credentials`, `--google-oauth-client`, `--google-folder-id`,
  `--google-share-with` (repeatable), `--google-share-role`,
  `--google-share-anyone` and `--google-title`. Files are private unless you
  share them, and Google credentials are masked in logs. Tested only with
  mocked Google clients. See `docs/guides/google-sheets-and-docs.md`.
- `--per-account-reports` writes one workbook or document for each account.
- `--risk-threshold LEVEL` (with `--enable-security-analysis`) exits with code
  4 when a security group rule is at or above that level.
- `--enable-cost-analysis` adds a Cost Analysis sheet.
- The report and the run summary name each account that failed, with the
  reason.
- Global services (IAM, S3 bucket list, CloudFront, Route 53, ACM certificates
  of CloudFront) are read once per account from `us-east-1` for any region
  choice. Their region column says `global`; S3 buckets keep their region.

### Fixed

- ARNs are the real AWS ARNs for Lambda, RDS, DynamoDB, SQS, SNS, the VPC
  family (`arn:aws:ec2`), EC2 snapshots, NAT gateways, Elastic IPs, key pairs,
  load balancers, EKS, Glue, API Gateway, Route 53 and KMS aliases. Tags from
  the Resource Groups Tagging API now reach these resources, and
  `--fallback-display always` no longer lists a resource twice.
- Resources were missed or mis-read for Glue crawlers, RDS clusters, snapshots,
  subnet groups and parameter groups, application load balancers, target
  groups, Elastic IPs and organizations.
- Permission-denied and Cost Explorer-denied reasons are logged once per
  service at WARNING level.
- `--bom-config` warns about keys it ignores.
- `--validate-config-only` makes no AWS call.
- `--accounts-prompt`, `--credential-timeout` and `--disable-account-logging`
  work and are tested.
- No empty `bom_output/changelogs/` folder is created.
- Google secrets are masked in logs.
- Report generation no longer fails at the end when there is no security
  analysis result.

### Changed

- `--compliance-standard` and `--disable-production-safety` still stop with
  exit code 2. The status page no longer carries a feature table; the test list
  is in `docs/security/tests.md`.

### Changed (documentation site)

- New look for the docs: numbered step badges, callout cards, "Where to next"
  tiles on every page, icons on the sidebar sections and top links, and a
  search palette (press Ctrl or Cmd + K, or `/`).
- The theme button switches between light and dark only. The first visit
  follows your system setting.
- "Last updated" no longer shows an author name.
- The Security section is now "Security and tests" and holds the Tests and
  Software bill of materials pages. "Noise you can ignore" moved to
  "Fix common problems".

### Added (documentation site)

- The documentation site has a version dropdown. It lists the current version
  and the archived v1.0.1 and v1.0.0 docs. A new minor or major release
  archives the previous release's docs from its git tag.

### Changed (release process)

- Every push to `main` is released as a patch version automatically. Use
  `Release-As: minor` or `Release-As: major` in the commit message, a
  `release:minor` or `release:major` pull request label, or the manual
  workflow for a bigger bump.

## [v1.0.2] - 2026-11-13

### Fixed

- The example screenshots on the documentation site show as images. Four
  pages displayed the raw `<img src={require(...)}>` text instead.

### Changed

- The install pages say that a virtual environment is optional and give
  `pipx` and plain `pip` as alternatives.

## [v1.0.1] - 2026-11-13

### Added

- Python 3.15 is supported. CI runs the tests on 3.11, 3.12, 3.13, 3.14 and
  3.15.

### Fixed

- `colorama` is a dependency again. `scripts/legacy/` imports it.

## [v1.0.0] - 2026-11-13

First numbered release. It includes everything from the alpha builds below,
plus these changes.

### Added

- A service that appears on the bill but has no discovered resources is now
  listed as "Service (detected from billing)" with its last-30-day cost, so a
  used service no longer disappears from the report. `--fallback-display never`
  turns this off.

### Changed

- Tag enrichment reads the ResourceGroupsTagging API for all regions in
  parallel (up to 8 at a time, with adaptive retries). It ran one region at a
  time before.
- Billing and discovery service names are compared with the same name rules,
  so `AMAZONCLOUDWATCH`, `KEYMANAGEMENTSERVICE` and `CLOUDWATCHEVENTS` are no
  longer reported as missing next to `CLOUDWATCH`, `KMS` and `EVENTS`.
- Services billed at $0.00 are no longer probed in every region; they are
  listed from billing instead.
- When the default credentials already belong to the account being scanned,
  the default `InvenTagCrossAccountRole` is not tried, and a failed role
  attempt is logged as one short line per account.

## Alpha builds

Everything below shipped under the version numbers v5.1.0 and v5.0.0 (and the
v4.x versions before them). Those versions are now called alpha builds and are no longer
published. The entries are kept as they were written.

## Alpha build v5.1.0 - 2026-11-13

### Added

- InvenTag is installed with `pip install inventag-aws` from PyPI and run with
  the `inventag` command. The README, docs, website and examples now start with
  pip, and every example uses `inventag` instead of `./inventag.sh`.
- Pushing a new version to `main` publishes it to PyPI.
- Links to the PyPI page in the README, docs and website footer.

### Fixed

- The README logo and links show correctly on the PyPI page.

### Fixed

- The Excel and Word reports now list services in name order and sort the rows
  of each service. Before, the order followed the order in which parallel
  discovery finished, so two runs on the same estate could give different
  sheet and row order.
- Several links in `README.md`, `config/README.md` and `examples/README.md`
  pointed at pages that no longer exist.

### Changed

- Every page in `docs/` was checked against the code of v5.0.0 and corrected.
  The page "Feature status and known limitations" lists the limits found:
  global services are scanned only from `us-east-1`, tags on Lambda, RDS,
  DynamoDB, SQS and SNS resources are not matched because the built ARN
  differs from the real one, one failed account does not change the exit
  code, and others.
- The sample outputs in the docs are generated again from the current code.
  `scripts/docs/generate_example_outputs.py` now gives the same IDs and
  timestamps on every run, and `--check` works without rendering pictures.
- `README.md`, `QUICKSTART.md` and the website landing page say Python 3.11 or
  later, and describe tag-policy templates and the change report as they work
  today.

### Open work

These items are not done. A contributor can start any of them.

- Resources of Lambda, RDS, DynamoDB, SQS, SNS and VPC get an ARN that InvenTag
  builds and that differs from the real ARN. Tags from the Resource Groups
  Tagging API are matched by ARN, so these resources lose their tags and a tag
  policy reports them as missing tags. With `--fallback-display always`, they
  appear twice.
- Global services (S3, IAM, CloudFront, Route 53) are scanned only if
  `us-east-1` is in the region list.
- A run in which some accounts fail exits with code 0, and the report does not
  say which accounts are missing.
- The analysis flags `--enable-network-analysis` and `--enable-security-analysis`
  add no sheets with `--template`.
- `--tag-mappings` and `--service-descriptions` add columns only to the default
  workbook, not with `--template`.
- A custom description in a service-descriptions file is ignored for S3, EC2,
  RDS, Lambda and VPC unless the entry names a `template`.
- There are two template mechanisms: named templates (`--template`,
  `inventag/templating/`) and layout files (`--word-template`,
  `--excel-template`, `inventag/reporting/report_template.py`). Merge them
  into one.
- `inventag/discovery/intelligent_discovery.py` logs
  `'OptimizedAWSDiscovery' object has no attribute '_snake_case'` at debug level
  for each operation. The results of the run are not affected.
- AWS API calls are not checked against the current AWS documentation for
  deprecated or renamed operations.
- `cloud_bom_generator.py` falls back to four regions when `DescribeRegions`
  fails. `inventory.py` has a different fallback list of fourteen regions.
- `--bom-config` applies only the `BOMProcessingConfig` field names. It ignores
  the other documented keys without a message.
- `--enable-cost-analysis` calls Cost Explorer, also with
  `--no-billing-validation`.
- `--s3-kms-key-id` is optional with `--s3-encryption aws:kms`. The help text
  says that it is necessary.
- `--validate-config` and `--validate-config-only` call AWS (credential check
  and `DescribeRegions`) unless you add `--skip-credential-validation`, and
  `--validate-config-only` still makes the `DescribeRegions` call.
- With `--verbose` or `--debug`, some log lines (from `inventag.discovery`)
  show twice.
- A second run creates an empty `bom_output/changelogs/` folder.
- These modules are not on the CLI path: `reporting/template_framework.py`,
  `branding_system.py`, `word_builder.py`, `excel_builder.py`,
  `document_generator.py`, `configuration_manager.py`.
- No test runs against a real AWS account. All tests use `moto`.

## Alpha build v5.0.0 - 2026-11-12

### Breaking changes

- Python 3.11 is the minimum version. The CLI stops with a message on an
  older version. CI does the tests on Python 3.11, 3.12, 3.13 and 3.14.
- `--create-google-docs`, `--per-account-reports`, `--compliance-standard`,
  `--risk-threshold` and `--disable-production-safety` stop the CLI with exit
  code 2. These flags did nothing before.
- `--account-services` and `--account-tags` filter the full result. Before,
  resources from most discovery paths were not filtered.
- Template files with `template_version: "1.0"` are rejected. Use
  `--print-default-template word` or `--print-default-template excel` to get a
  version 2.0 file.
- A report format that the CLI cannot write makes the run fail with exit
  code 1. Before, the run reported success.
- Dependency minimums are higher. See `requirements.txt`.

### Added

- Named templates for reports, tag policies and run configurations
  (`inventag/templating/`): `inventag templates list`, `show`, `init` and
  `validate`, and `--template NAME|PATH`. A template can build on a different
  template with `extends`. See `docs/templates/`.
- Layout files for one Word or Excel report: `--word-template`,
  `--excel-template`, `--print-default-template`, `--validate-templates`.
  See `docs/templates/layout-flags.md`.
- The documentation has a new structure: Get started, Guides, Templates,
  Examples, Reference, Security and Contributing. The old page addresses
  still work.
- `--no-generate-changelog` stops the change report.
- `--no-billing-validation` stops all Cost Explorer calls during discovery.
- `--validate-operations` and `--audit-output` for the read-only guard.
- Upload of reports to Amazon S3 with `--s3-bucket`. Server-side encryption
  is always on.
- `pyproject.toml`. The package name is `inventag-aws` and the command is
  `inventag`.
- The release workflow can publish to PyPI through Trusted Publishing. See
  "Release process" below.
- Every push to `main` starts a patch release. Add a line `Release-As: minor`
  or `Release-As: major` to the commit message for a bigger bump. Put
  `[skip release]` in the message to publish nothing.
- Website: `npm run check:a11y` does accessibility checks (axe-core, WCAG 2.1
  A and AA) at four screen widths in the light theme and the dark theme. The
  docs workflow runs it after the build.
- `CHANGELOG.md` (this file).

### Fixed

- EC2 instances were absent from reports. The discovery code read the
  reservation, which has no instance ID, and dropped the instances in it.
- Resources from the default discovery path had no `type`, `id` and `name`
  values. Reports, snapshots and de-duplication read these keys.
- `--enable-network-analysis` and `--enable-security-analysis` added nothing
  to the Excel report. They now add the `Network Analysis` sheet and the
  `Security Analysis` sheet.
- The CLI made one `sts:GetCallerIdentity` call for each resource without an
  ARN. It now makes one call for each discovery object.
- If the filters removed all resources, the log showed a report path that did
  not exist. The CLI now writes a warning and lists only files that exist.
- `--tag-mappings` and `--service-descriptions` were loaded and then not
  applied. They now add their columns to the report. The older flat layout of
  the tag-mappings file is accepted again.
- `--cross-account-role` accepts a role name or a full role ARN.
- The S3 lifecycle rule is merged into the existing rules of the bucket. It
  is off by default (`lifecycle_days` is 0).
- `--debug` logs no longer contain secret keys, session tokens or request
  signatures.
- `inventag.__version__` showed `1.0.0`. It now shows the release version.
- The test suite passes: 1315 passed, 9 deselected (performance benchmarks).
  Before, 122 tests failed and 47 had errors.
- CI: a test failure now makes the job fail. The `|| true` is removed.

### Security

- The read-only guard blocks each AWS call that is not a read operation.
- `pip-audit` reports no known vulnerabilities for `requirements.txt` and
  `requirements-dev.txt` on 2026-11-12. The minimum versions of
  `cryptography`, `requests`, `urllib3`, `certifi`, `idna` and `lxml` are
  raised. Each line in `requirements.txt` gives the advisory ID.
- Report files, snapshots and logs are created with owner-only permissions.
- GitHub Actions are pinned to commit SHAs. Workflow tokens have the minimum
  permissions.

### Changed

- Website cookie banner: the two choices are "Just the essentials" and "Allow
  analytics". The two buttons have the same style and a visible border.
  Analytics loads only after the visitor selects "Allow analytics".
- `datetime.utcnow()` is replaced with timezone-aware time
  (`inventag/timeutil.py`).

## Release process

1. Put the changes on `main`. Make sure that the "Unreleased" section is
   correct.
2. The release starts by itself. A push to `main` is a patch release unless
   you choose another bump:
   - Add a line `Release-As: major` (or `minor`) to the commit message of the
     commit that you push to `main`. Put `[skip release]` in the message to
     skip the release.
   - Run the "Automated Release" workflow manually and select the bump type.
   - Merge a pull request that has a `release:major`, `release:minor` or
     `release:patch` label.
3. The workflow updates `version.json` and `inventag/_version.py`, creates the
   tag and creates the GitHub release.
4. If the repository variable `PYPI_PUBLISH` is `true`, the workflow builds
   the package and publishes it to PyPI.

One-time setup for PyPI:

1. On pypi.org, add a trusted publisher for the project `inventag-aws`:
   owner `habhabhabs`, repository `inventag-aws`, workflow `release.yml`,
   environment `pypi`.
2. In the GitHub repository settings, create the environment `pypi`.
3. In the GitHub repository settings, set the variable `PYPI_PUBLISH` to
   `true`.

[Unreleased]: https://github.com/habhabhabs/inventag-aws/compare/v1.5.0...HEAD
[v1.5.0]: https://github.com/habhabhabs/inventag-aws/compare/v1.4.3...v1.5.0
[v1.4.3]: https://github.com/habhabhabs/inventag-aws/compare/v1.4.2...v1.4.3
[v1.4.2]: https://github.com/habhabhabs/inventag-aws/compare/v1.4.1...v1.4.2
[v1.4.1]: https://github.com/habhabhabs/inventag-aws/compare/v1.4.0...v1.4.1
[v1.4.0]: https://github.com/habhabhabs/inventag-aws/compare/v1.3.1...v1.4.0
[v1.3.1]: https://github.com/habhabhabs/inventag-aws/compare/v1.3.0...v1.3.1
[v1.3.0]: https://github.com/habhabhabs/inventag-aws/compare/v1.2.2...v1.3.0
[v1.2.2]: https://github.com/habhabhabs/inventag-aws/compare/v1.2.1...v1.2.2
[v1.2.1]: https://github.com/habhabhabs/inventag-aws/compare/v1.2.0...v1.2.1
[v1.2.0]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.4...v1.2.0
[v1.1.4]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.3...v1.1.4
[v1.1.3]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.2...v1.1.3
[v1.1.2]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.1...v1.1.2
[v1.1.1]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.0...v1.1.1
[v1.1.0]: https://github.com/habhabhabs/inventag-aws/compare/v1.0.2...v1.1.0
[v1.0.2]: https://github.com/habhabhabs/inventag-aws/compare/v1.0.1...v1.0.2
[v1.0.1]: https://github.com/habhabhabs/inventag-aws/compare/v1.0.0...v1.0.1
[v1.0.0]: https://github.com/habhabhabs/inventag-aws/releases/tag/v1.0.0
