# Changelog

This file lists the changes in each InvenTag release. Update it in the same
commit as the change. Put new entries in the "Unreleased" section.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The version numbers follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-11-13

First release under this version number.

### Added

- Read-only inventory of AWS resources across many accounts and regions, with
  the tags on each resource.
- Excel and Word Bill of Materials reports, report templates and tag-policy
  checks.
- Services that appear on the bill but have no discovered resources are listed
  as "Service (detected from billing)" with their 30-day cost.
  `--fallback-display never` turns this off.
- Install with `pip install inventag-aws` from PyPI and run the `inventag`
  command.

### Changed

- Tag enrichment reads the ResourceGroupsTagging API for all regions in
  parallel, with adaptive retries.
- When the default credentials already belong to the account being scanned,
  the default `InvenTagCrossAccountRole` is not tried.

[Unreleased]: https://github.com/habhabhabs/inventag-aws/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/habhabhabs/inventag-aws/releases/tag/v1.0.0
