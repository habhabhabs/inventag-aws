---
title: Software bill of materials
description: What the InvenTag software bill of materials (SBOM) lists, how it is generated, and how to check the dependencies you install.
sidebar_position: 3
---

# Software bill of materials

**Who this is for:** security and procurement reviewers who need to know what
InvenTag is made of.

**What you will know after reading:** which SBOM files exist, how they are
made, and how to produce one for your own installation.

## What the documentation build generates

Each time the documentation site is deployed, the build generates SBOM files
for the repository and its dependencies and publishes them with the site:

| Files | What they list | Format |
|---|---|---|
| Repository SBOM | Everything Syft finds in the repository | Syft JSON, CycloneDX JSON and SPDX JSON |
| Python, from `requirements.txt` | The minimum versions InvenTag declares | CycloneDX JSON and XML |
| Python, from a fresh install | The versions that were actually installed | CycloneDX JSON and a `pip freeze` list |
| Documentation website | The Node.js packages used to build this site | CycloneDX JSON |

Not verified against a GitHub Actions runner: the SBOM files the documentation build publishes; this page is read from the workflow file.

A summary page, **Software Bill of Materials (SBOM)**, is added to this
section by the same build, so it appears on the live site but not in a local
build.

The Python dependencies are declared with minimum versions, not exact pins, so
the installed-versions file is the one that shows what a real install gets on
the day of the build.

## Produce an SBOM for your own installation

```bash title="Terminal"
pip install inventag-aws cyclonedx-bom
cyclonedx-py environment --output-format json --output-file inventag-sbom.json
```

Not verified against the cyclonedx-bom release you install: the cyclonedx-py environment options.

Run it in the virtual environment where you installed InvenTag, so the file
lists exactly what you run.

## Keep an eye on vulnerabilities

A scheduled workflow scans the dependencies for known vulnerabilities. Read
[How dependencies are checked](./index.md#how-dependencies-are-checked) for
what runs and what fails the build, and
[After a supply-chain incident](./index.md#after-a-supply-chain-incident) if
you think something was compromised.
