# Changelog

This file lists the changes in each InvenTag release. Update it in the same
commit as the change. Put new entries in the "Unreleased" section.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The version numbers follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
- An expired or missing IAM Identity Center (SSO) login stops the run with one
  message that names the profile and the command `aws sso login --profile
  <name>`. A profile that needs an MFA code, run with no terminal, stops with
  a message and the `aws sts get-session-token` command. Before, both ended in
  a traceback (and the MFA case with an empty message). Exit code 1, as
  before. With `--debug` the full traceback is still logged.
- `--audit-output`, `--log-file` and `--output-directory` with a path that
  cannot be written (for example a folder that is a file) stop the run at the
  start with one message that names the option and the path, before any AWS
  call. Before, the first two ended in a traceback and the third after the
  whole scan. Exit code 1, as before.
- When a run result carries notes for the reader, the console prints each as a
  warning after the summary (the lines the "not scanned" block already shows
  are not repeated). A run without notes prints nothing new.

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

[Unreleased]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.4...HEAD
[v1.1.4]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.3...v1.1.4
[v1.1.3]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.2...v1.1.3
[v1.1.2]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.1...v1.1.2
[v1.1.1]: https://github.com/habhabhabs/inventag-aws/compare/v1.1.0...v1.1.1
[v1.1.0]: https://github.com/habhabhabs/inventag-aws/compare/v1.0.2...v1.1.0
[v1.0.2]: https://github.com/habhabhabs/inventag-aws/compare/v1.0.1...v1.0.2
[v1.0.1]: https://github.com/habhabhabs/inventag-aws/compare/v1.0.0...v1.0.1
[v1.0.0]: https://github.com/habhabhabs/inventag-aws/releases/tag/v1.0.0
