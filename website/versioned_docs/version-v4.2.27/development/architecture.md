---
title: How the code fits together
description: A map of InvenTag's Python package - CLI, multi-account orchestration, discovery, processing, templates, reporting and state - for contributors.
sidebar_position: 2
slug: /architecture/core-module-integration
---

# How the code fits together

**Who this is for:** contributors who want to find their way around the code.

**What you will know after reading:** which module does what during a run,
and where to start for a change.

## The path of one run

```text
inventag_cli.py
  -> inventag/cli/main.py              parse flags, validate, set up logging
       -> templating/runner.py         only with --template: load templates,
                                       apply a config template to the flags
  -> core/cloud_bom_generator.py       CloudBOMGenerator
       1. sessions per account         profiles, keys or sts:AssumeRole
       2. discovery per account        discovery/inventory.py and friends
       3. consolidation                one list of resource dictionaries
       4. documents                    reporting/bom_processor.py, then
                                       reporting/converter.py (default) or
                                       templating/render_excel.py and
                                       render_word.py (with --template)
       5. state                        state/ snapshots and changelog
```

## Packages

| Package | Responsibility | Start with |
|---|---|---|
| `inventag/cli/` | Flags, configuration validation, logging | `main.py`, `config_validator.py` |
| `inventag/core/` | Multi-account orchestration and credentials | `cloud_bom_generator.py` |
| `inventag/discovery/` | Finding resources: per-service API calls, the Tagging API, Cost Explorer | `inventory.py`, `comprehensive_discovery.py` |
| `inventag/reporting/` | Normalising resources and writing the default Excel and Word files | `bom_processor.py`, `converter.py` |
| `inventag/templating/` | Template loading, validation, inheritance, tag-policy checks and template-driven Excel and Word output | `schema.py`, `registry.py`, `runner.py` |
| `inventag/state/` | Snapshots, differences and changelogs | `state_manager.py` |
| `inventag/compliance/` | Library classes for tag checks and safety; mostly not used by the CLI today | `checker.py` |

## The resource dictionary

Everything between discovery and output passes around plain dictionaries,
one per resource. The fields that templates and reports rely on are listed in
the [Template reference](../templates/reference.md#resource-fields-you-can-use-as-columns).
Keep them stable: renaming one breaks people's templates.

## How templates hook in

`templating/runner.py` defines `TemplatedCloudBOMGenerator`, a subclass of
`CloudBOMGenerator` that replaces only the document step. The rest of a run,
including discovery, credentials and state, is unchanged. Without
`--template`, the original classes are used and the output is exactly as
before.

## Known gaps worth fixing

These are tracked on [Feature status](../getting-started/status.md). Each is a
good first contribution:

- `reporting/bom_processor.py` calls `apply_mappings_to_resource` and
  `apply_description_to_resource`, which don't exist (the real methods take a
  list), so tag mappings and service descriptions are never applied.
- `--validate-credentials` passes a `timeout` argument that
  `CredentialManager.validate_account_credentials()` does not accept.
- The changelog compares the newest snapshot with itself.
- Network and security analysis results are computed but not written to the
  reports.

Older design notes, which may be out of date, are kept in the repository under
`development/docs-archive/`. They are not published on this site.
