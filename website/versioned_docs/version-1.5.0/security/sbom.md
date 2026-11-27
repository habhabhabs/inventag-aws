---
title: Software bill of materials
description: What the InvenTag software bill of materials (SBOM) lists, how it is generated, and how to check the dependencies you install.
sidebar_position: 3
---

# Software bill of materials

**Who this is for:** security and procurement reviewers who need to know what
InvenTag is made of.

**What you will know after reading:** which SBOM files exist, how they are
made, how to check a release file, and how to produce an SBOM for your own
installation.

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

## What a release carries

Each release has packaged builds: executable archives, `.deb` and `.rpm`
packages. The release workflow makes the files below for them. See
[Install InvenTag](../getting-started/installation.md#choose-how-to-install)
for the builds.

| File | What it holds |
|---|---|
| `inventag-<version>-<os>-<cpu>.tar.gz`, `inventag_<version>_<cpu>.deb`, `inventag-<version>-1.<cpu>.rpm` | The packaged builds |
| One `.cdx.json` file for each of those files, for example `inventag_<version>_amd64.deb.cdx.json` | The SBOM of that file: its Python packages and C libraries, with name, version and license |
| `inventag-<version>-<os>-<cpu>.THIRD-PARTY-LICENSES.txt` | The notices file: the license text of each carried component |
| `inventag-<version>-<os>-<cpu>.components.json` | The list of components that the SBOM and the notices file are made from |
| `inventag-<version>-linux-<cpu>.build-image.txt` | The record of the Linux build system: its release and the versions of the libraries that the build carries |
| `SHA256SUMS` | The SHA-256 checksum of every other file of the release |

The SBOM files use the CycloneDX format, version 1.5, in JSON. The workflow
writes them from the build, so they list what is in the file and not what a
`requirements.txt` allows.

Not verified against the CycloneDX schema: that the SBOM files pass a validator.

Not verified against GitHub: that the release carries these files. The test runs so
far attach nothing to a release, and the first release run with these files is
not made yet.

### Check a release file

The release workflow signs the files with no key of ours. It gives `SHA256SUMS`
to GitHub's `actions/attest` step. That step writes a build attestation in the
name of the workflow. To check a file with the GitHub CLI:

```bash title="Terminal"
gh attestation verify inventag_1.5.0_amd64.deb \
  --repo habhabhabs/inventag-aws \
  --signer-workflow habhabhabs/inventag-aws/.github/workflows/package.yml
```

`--repo` names the repository. `--signer-workflow` makes the check fail when a
different workflow file made the attestation.

To check a checksum, see
[Check the download](../getting-started/installation.md#check-the-download).

Not verified against GitHub: `gh attestation verify` with these flags on a
release file. The flags are read from `gh attestation verify --help`. The test
runs make no attestation. The first real attestation is made by the first
release run, and that run is not made yet.

### Licenses in the packaged builds

InvenTag is under the MIT license. The packaged builds also carry the files of
other projects. The notices file lists them with their license texts.

The executable archives, the `.deb` and the `.rpm` carry GNU libiconv, a
library under the GNU Lesser General Public License (LGPL) version 2.1. The
Homebrew formula installs the same archive, so it carries
it too. The libiconv code is inside the extension modules of lxml. InvenTag
needs lxml to write Word files. The lxml project builds those modules and links
libiconv into them. In the archive, the `.deb` and the `.rpm`, InvenTag carries
the lxml files without a change: the build compares each file byte for byte
with the file in the wheel of the lock.

- A pip, pipx or uv install does not carry libiconv in a file of InvenTag. Your
  installer downloads lxml's own wheel from the Python Package Index.
- The notices file is `THIRD-PARTY-LICENSES.txt`: `inventag/THIRD-PARTY-LICENSES.txt`
  in the archive, and `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` and
  `/opt/inventag/THIRD-PARTY-LICENSES.txt` in the `.deb` and the `.rpm`. The
  release also lists it as a file of its own for each system. It holds the full
  text of the LGPL 2.1.
- The source of the library is at the addresses that the notices file names.
  In this release: libiconv 1.18 at <https://www.gnu.org/software/libiconv/>
  and <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>, and lxml
  6.1.3 at <https://github.com/lxml/lxml>. The release workflow requests both
  libiconv addresses before it signs the files, and stops if one does not answer.
- InvenTag makes no written offer to send the source. If an address does not
  work, open an issue at <https://github.com/habhabhabs/inventag-aws/issues>.
- The lxml modules are separate files in the installation directory. You can
  replace them with your own build of lxml of the same version. The folder is
  `inventag/_internal/lxml/` in the archive and `/opt/inventag/_internal/lxml/`
  for the `.deb` and the `.rpm`. On macOS, sign a module again after you
  replace it: `codesign -s - --force <file>`.

Not verified against your own lxml build: that a module that you build works in
place of the bundled one.

Not verified against a Homebrew install: that Homebrew leaves the lxml files
unchanged.

Not verified against GNU's servers: that the two libiconv addresses keep
answering. The workflow fetched both on the day of its test run.

This section is not legal advice.

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
