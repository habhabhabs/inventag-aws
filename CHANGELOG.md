# Changelog

This file lists the changes in each InvenTag release. Update it in the same
commit as the change. Put new entries in the "Unreleased" section.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The version numbers follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- The Excel and Word reports now list services in name order and sort the rows
  of each service. Before, the order followed the order in which parallel
  discovery finished, so two runs on the same estate could give different
  sheet and row order.
- Several links in `README.md`, `config/README.md` and `examples/README.md`
  pointed at pages that no longer exist.

### Changed

- Every page in `docs/` was checked against the code of 5.0.0 and corrected.
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

## [5.0.0] - 2026-11-12

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
- A direct push to `main` starts a release if the commit message has a line
  `Release-As: patch`, `Release-As: minor` or `Release-As: major`.
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
2. Start a release with one of these methods:
   - Add a line `Release-As: major` (or `minor`, or `patch`) to the commit
     message of the last commit that you push to `main`.
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

[Unreleased]: https://github.com/habhabhabs/inventag-aws/compare/v5.0.0...HEAD
[5.0.0]: https://github.com/habhabhabs/inventag-aws/compare/v4.2.27...v5.0.0
