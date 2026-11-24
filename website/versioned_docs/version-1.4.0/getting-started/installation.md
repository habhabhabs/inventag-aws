---
title: Install InvenTag
description: Choose how to install InvenTag (pipx, a standalone archive, a .deb or .rpm package, Homebrew or pip), connect your AWS credentials and check that everything works.
sidebar_position: 2
---

# Install InvenTag

**Who this is for:** anyone setting up InvenTag on a laptop, a server or a CI
runner.

**What you can do after reading:** choose an install method, install InvenTag,
upgrade it and remove it, and confirm that InvenTag can reach your AWS
account.

## What you need

- **Python 3.11 or later**, for the pipx, pip and source methods. Python 3.10
  stopped getting security fixes in October 2026. See
  [Python release status](https://devguide.python.org/versions/).
  Check your version with `python3 --version`. The standalone archive, the
  `.deb` and the `.rpm` bring their own Python. They need no Python on your
  machine.
- **AWS credentials** for a read-only identity. The
  [AWS Command Line Interface (AWS CLI)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  is optional, but it is the easiest way to set them up.

## Choose how to install

| Method | Use it when | Needs on your machine | Systems |
|---|---|---|---|
| [pipx](#install-with-pipx-recommended) (first choice) | You have Python 3.11 or later. You want one command to install and one to upgrade. | Python 3.11 or later and pipx | Any system with Python |
| [Standalone archive](#install-the-standalone-archive) (`.tar.gz`) | The machine has no Python, or you want a copy that needs no package manager. | Nothing | Linux x86_64 and arm64 (glibc 2.34 or later). macOS arm64 (Apple silicon). |
| [`.deb` package](#install-the-deb-package) | Debian, Ubuntu and systems that use `dpkg`. | Nothing | Linux x86_64 and arm64 (glibc 2.34 or later) |
| [`.rpm` package](#install-the-rpm-package) | Fedora, the RHEL family and Amazon Linux. | Nothing | Linux x86_64 and arm64 (glibc 2.34 or later) |
| [Homebrew](#install-with-homebrew) | macOS or Linux with Homebrew. Not published yet. | Homebrew | See the section |
| [pip in a virtual environment](#install-with-pip-in-a-virtual-environment) | You want InvenTag inside a project environment. | Python 3.11 or later | Any system with Python |
| [From source](#install-from-source) | You want the newest unreleased code, or you change InvenTag. | Python 3.11 or later and Git | Any system with Python |

### Systems that each packaged build supports

- The executable, the `.deb` and the `.rpm` for Linux need glibc 2.34 or later.
  The Linux systems in the table below meet this. On an older system, for example RHEL, AlmaLinux and Rocky Linux 8,
  Debian 11, Ubuntu 20.04 or Amazon Linux 2, use pipx if the system has Python
  3.11 or later.
- There is no executable for Intel Macs: a library InvenTag needs
  (cryptography, from version 50) publishes no ready-made build for them.
- The macOS executable is for Apple silicon (arm64) only. The build record
  states that its files need macOS 11.0 or later.
- Alpine and other systems that use musl are not supported by the executable.
  Use pipx.
- Windows has no packaged build.

Not verified against an Intel Mac: `pipx install inventag-aws`, which has to
compile that library and needs a Rust toolchain.

Not verified against systems with a glibc older than 2.34: the executable, the
`.deb` and the `.rpm`.

Not verified against Alpine or other musl systems: the executable; use pipx.

Not verified against Windows: any install method.

Not verified against a Mac with macOS 11.0: the executable. The number comes
from the build record, not from a run on that version.

### What was tested

The release workflow builds each format and then installs it on a fresh
system. Each kind of job does this:

- **Linux x86_64:** installs the package or unpacks the archive, runs
  `inventag --version` and `inventag selftest`, reads the man page file, loads
  the completion files, scans a simulated AWS, removes the package and checks
  that no file of the package is left.
- **Linux arm64:** installs the `.deb` on Debian 12 and the `.rpm` on Rocky
  Linux 9, runs `inventag --version` and `inventag selftest`, removes the
  package and checks that `inventag` is gone from the PATH. It does not check
  the man page, the completion files or a scan, and it does not check that no
  file of the package is left.
- **macOS arm64:** unpacks the archive into a temporary folder, runs
  `inventag --version` and `inventag selftest`, reads the man page file, checks
  the bash and zsh completion files for syntax with `bash -n` and `zsh -n`
  (nothing is loaded, and the fish file is not checked), scans a simulated AWS
  and deletes the temporary folder.
- **pipx on Ubuntu 24.04:** installs the wheel built from the tag, runs
  `inventag --version` and `inventag selftest`, removes it and checks that
  `inventag` is gone from the PATH.

These systems passed:

| System | Format | CPU |
|---|---|---|
| Ubuntu 22.04 | `.deb` | x86_64 |
| Ubuntu 24.04 | `.deb` | x86_64 |
| Debian 12 | `.deb` and archive | x86_64 |
| Debian 12 | `.deb` (install, version, selftest, remove) | arm64 |
| Fedora (the current release on the test day) | `.rpm` | x86_64 |
| Rocky Linux 9 | `.rpm` and archive | x86_64 |
| Rocky Linux 9 | `.rpm` (install, version, selftest, remove) | arm64 |
| AlmaLinux 9 (the build system, glibc 2.34) | `.rpm` | x86_64 |
| Amazon Linux 2023 | `.rpm` | x86_64 |
| macOS 15 on a GitHub runner | archive | arm64 |
| Ubuntu 24.04 | pipx, from the wheel built from the tag (install, version, selftest, remove) | x86_64 |

Not verified against real AWS: a scan from a packaged build; the smoke test
scans a simulated AWS.

Not verified against a fresh Linux arm64 system: the archive. The build ran
`inventag selftest` on it, and no other test unpacked it.

Not verified against GitHub: that the release carries the files of this page. The
test runs so far attach nothing to a release, and the first release run with
these files is not made yet.

## Install with pipx (recommended)

[pipx](https://pipx.pypa.io/) installs InvenTag in its own hidden environment
and puts the `inventag` command on your PATH. You never activate anything. The
package on the Python Package Index is
[`inventag-aws`](https://pypi.org/project/inventag-aws/). Install pipx first.
Use the way that your system suggests. See the pipx documentation.

```bash title="Terminal"
pipx install inventag-aws
inventag --version
inventag selftest
```

`inventag selftest` checks, offline, that this copy of InvenTag works. It
makes no AWS call, opens no network connection and needs no credentials. Exit
code 0 means that every check passed. Exit code 1 means that a check failed.

If you use [uv](https://docs.astral.sh/uv/), the command is
`uv tool install inventag-aws`.

- **Upgrade:** `pipx upgrade inventag-aws`. To install one release, pin it:
  `pipx install inventag-aws==1.4.0`.
- **Uninstall:** `pipx uninstall inventag-aws`. This removes the program. It
  does not remove your reports and snapshots in `bom_output/`.
- **Completion:** `inventag completion bash`, `inventag completion zsh` and
  `inventag completion fish` print a completion script. See
  [Shell completion](#shell-completion).
- **Man page:** this method installs none. Use `inventag --help`.

Not verified against pipx: the upgrade and the pin commands.

Not verified against uv: that `uv tool install inventag-aws` gives a working
`inventag` and `inventag selftest`, and the upgrade and uninstall commands.

## Install the standalone archive

The archive holds one directory, `inventag`. It holds the program, its own
Python and its libraries. The release has one archive for each system:

- `inventag-1.4.0-linux-x86_64.tar.gz`
- `inventag-1.4.0-linux-arm64.tar.gz`
- `inventag-1.4.0-darwin-arm64.tar.gz` (macOS, Apple silicon)

Run `uname -m` to see your CPU. Linux prints `x86_64` or `aarch64`. Use the
arm64 archive for `aarch64`. Download the archive and `SHA256SUMS` from the
[releases page](https://github.com/habhabhabs/inventag-aws/releases), or with
the GitHub CLI:

```bash title="Terminal"
gh release download v1.4.0 --repo habhabhabs/inventag-aws \
  --pattern 'inventag-1.4.0-linux-x86_64.tar.gz' --pattern SHA256SUMS
```

[Check the download](#check-the-download) before you unpack it. Then, on
Linux:

```bash title="Terminal"
sudo tar -xzf inventag-1.4.0-linux-x86_64.tar.gz -C /opt
sudo ln -s /opt/inventag/inventag /usr/local/bin/inventag
inventag --version
inventag selftest
```

On macOS, unpack the archive into a folder that you choose and run the program
by its path. The test did this. It did not make a link on the PATH.

```bash title="Terminal"
mkdir -p "$HOME/inventag-install"
tar -xzf inventag-1.4.0-darwin-arm64.tar.gz -C "$HOME/inventag-install"
"$HOME/inventag-install/inventag/inventag" --version
```

The macOS executable is not notarized by Apple. macOS can block a file that a
browser downloaded.

Not verified against macOS outside a GitHub runner: the Homebrew install and
Gatekeeper's behavior.

- **Upgrade:** remove the old directory, then unpack the new archive in the same
  place.
- **Uninstall (Linux):** `sudo rm -rf /opt/inventag` and
  `sudo rm /usr/local/bin/inventag`. On macOS, delete the folder that you
  unpacked.
- **Completion:** the directory holds the scripts in `share/completions/`:
  `inventag.bash`, `_inventag` (zsh) and `inventag.fish`. See
  [Shell completion](#shell-completion).
- **Man page:** the directory holds the page in `share/man/man1/inventag.1`.
  Read it with `man /opt/inventag/share/man/man1/inventag.1`.

Not verified against the man tools of every system: that `man` shows the page.
The test read the page file and checked its header and name line.

Not verified against a system that has an older InvenTag in the same place: the
upgrade steps.

## Install the .deb package

Use the `.deb` on Debian, Ubuntu and systems that use `dpkg`. The file name is
`inventag_1.4.0_amd64.deb` for x86_64 and
`inventag_1.4.0_arm64.deb` for arm64. Download the file and
[check it](#check-the-download). Then run:

```bash title="Terminal"
sudo dpkg -i inventag_1.4.0_amd64.deb
inventag --version
inventag selftest
```

The package puts the program in `/opt/inventag/` and a link in
`/usr/bin/inventag`. It also installs the man page, the completion files and
the license files in `/usr/share/doc/inventag/`. The package has no install
script.

- **Upgrade:** install the newer `.deb` with `sudo dpkg -i`.
- **Uninstall:** `sudo dpkg -r inventag`. On x86_64, the test checked that no
  file of the package is left. On arm64, it checked only that `inventag` is gone
  from the PATH.
- **Completion:** the package installs the files for bash, zsh and fish. See
  [Shell completion](#shell-completion).
- **Man page:** `man inventag`. The file is
  `/usr/share/man/man1/inventag.1.gz`.

Not verified against a system that has an older InvenTag package: the upgrade.

Not verified against the man tools of every system: that `man inventag` shows
the page. The test read the page file and checked its header and name line.

## Install the .rpm package

Use the `.rpm` on Fedora, the RHEL family and Amazon Linux. The file name is
`inventag-1.4.0-1.x86_64.rpm` for x86_64 and
`inventag-1.4.0-1.aarch64.rpm` for arm64. Download the file and
[check it](#check-the-download). Then run:

```bash title="Terminal"
sudo dnf install ./inventag-1.4.0-1.x86_64.rpm
inventag --version
inventag selftest
```

The package puts the program in `/opt/inventag/` and a link in
`/usr/bin/inventag`. It also installs the man page, the completion files and
the license files in `/usr/share/doc/inventag/`.

- **Upgrade:** install the newer `.rpm` with `sudo dnf install`.
- **Uninstall:** `sudo dnf remove inventag`. On x86_64, the test checked that no
  file of the package is left. On arm64, it checked only that `inventag` is gone
  from the PATH.
- **Completion:** the package installs the files for bash, zsh and fish. See
  [Shell completion](#shell-completion).
- **Man page:** `man inventag`. The file is
  `/usr/share/man/man1/inventag.1.gz`.

Not verified against a system that has an older InvenTag package: the upgrade.

Not verified against the man tools of every system: that `man inventag` shows
the page. The test read the page file and checked its header and name line.

## Install with Homebrew

The project owner creates the Homebrew tap. The tap is not published yet, so
the command below does not work today:

```bash title="Terminal"
brew install habhabhabs/inventag/inventag
```

The formula is written. It is in the repository, in
`packaging/homebrew-tap/Formula/inventag.rb`, and
`scripts/packaging/render_formula.py` fills it in from the `SHA256SUMS` of a
release. It installs the executable from the release archive, the man page and
the completion files for bash, zsh and fish. It is for macOS arm64 and the two
Linux CPUs. It is not for Intel Macs: on one, the install stops with a message.

- **Upgrade:** `brew upgrade inventag`.
- **Uninstall:** `brew uninstall inventag`.

Not verified against Homebrew: the formula. `brew install`, `brew audit`,
`brew style` and `brew test` have not run on it. The upgrade and uninstall
commands have not run.

Not verified against an Intel Mac: the message that the install shows there.

Not verified against macOS outside a GitHub runner: the Homebrew install and
Gatekeeper's behavior.

## Install with pip in a virtual environment

InvenTag does not need a virtual environment. A virtual environment keeps its
dependencies (boto3, openpyxl and others) away from your other Python tools.
Many current systems (Debian, Ubuntu, Homebrew Python) refuse `pip install`
into the system Python with an "externally-managed-environment" error. The two
options that work on those systems are a virtual environment or
[pipx](#install-with-pipx-recommended).

```bash title="Terminal"
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install inventag-aws
inventag --help
```

Not verified against Debian, Ubuntu or Homebrew: the externally-managed-environment error and the two ways around it.

This gives you the `inventag` command that these docs use. The report
templates are included in the package.

- **Upgrade:** `pip install --upgrade inventag-aws`. To install one release,
  pin it: `pip install inventag-aws==1.4.0`.
- **Uninstall:** `pip uninstall inventag-aws`.
- **Completion and man page:** as for [pipx](#install-with-pipx-recommended).

Not verified against pip: the upgrade, pin and uninstall commands.

## Install from source

Use this if you want the newest unreleased code or you plan to change InvenTag.

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
inventag --help
```

`pip install -e .` installs the dependencies from `requirements.txt` and an
`inventag` command that runs your source checkout, so your code changes take
effect without a reinstall. You can also run `python inventag_cli.py --help`
directly after `pip install -r requirements.txt`.

The repository root also holds two launcher scripts, `inventag.sh` and
`inventag.bat`. Use the `inventag` command instead. The launchers are not part
of the installed package, and no test runs them.

To use a fixed release from source instead of the newest code, check out its tag, for
example `git checkout v1.4.0`. The
[releases page](https://github.com/habhabhabs/inventag-aws/releases) lists
every release.

## Shell completion

`inventag completion bash`, `inventag completion zsh` and
`inventag completion fish` print a completion script. The command reads only
its own options. It makes no AWS call and opens no network connection. An
unknown shell name stops with exit code 2.

```bash title="Terminal"
source <(inventag completion bash)                                    # bash, this session
inventag completion zsh > "${fpath[1]}/_inventag"                     # zsh
inventag completion fish > ~/.config/fish/completions/inventag.fish  # fish
```

The `.deb` and the `.rpm` install the three scripts for you:

| Shell | `.deb` | `.rpm` |
|---|---|---|
| bash | `/usr/share/bash-completion/completions/inventag` | `/usr/share/bash-completion/completions/inventag` |
| zsh | `/usr/share/zsh/vendor-completions/_inventag` | `/usr/share/zsh/site-functions/_inventag` |
| fish | `/usr/share/fish/vendor_completions.d/inventag.fish` | `/usr/share/fish/vendor_completions.d/inventag.fish` |

Not verified against each shell setup: that a new shell loads these files by
itself. The test loaded each file by hand in bash, zsh and fish. It did not
load the fish file on Rocky Linux 9, AlmaLinux 9 and Amazon Linux 2023.

## Check the download

Each release lists every file in `SHA256SUMS`. A checksum shows that the file
is whole. It does not show who made it. A build attestation does.

On Linux, put the file and `SHA256SUMS` in one folder and run:

```bash title="Terminal"
sha256sum --check --ignore-missing SHA256SUMS
```

On macOS, print the checksum of your file and compare it by eye with the line
in `SHA256SUMS`:

```bash title="Terminal"
shasum -a 256 inventag-1.4.0-darwin-arm64.tar.gz
grep darwin-arm64.tar.gz SHA256SUMS
```

The release workflow signs the files without a key of ours. It gives
`SHA256SUMS` to GitHub's `actions/attest` step. That step writes a build
attestation in the name of the workflow. To check a file, use the GitHub CLI:

```bash title="Terminal"
gh attestation verify inventag_1.4.0_amd64.deb \
  --repo habhabhabs/inventag-aws \
  --signer-workflow habhabhabs/inventag-aws/.github/workflows/package.yml
```

`--repo` names the repository. `--signer-workflow` makes the check fail when a
different workflow file made the attestation.

Not verified against GitHub: `gh attestation verify` with these flags on a
release file. The flags are read from `gh attestation verify --help`. The test
runs make no attestation. The first real attestation is made by the first
release run, and that run is not made yet.

Each `.tar.gz`, `.deb` and `.rpm` also has an SBOM, named like the file with
`.cdx.json` added. See [Software bill of materials](../security/sbom.md).

## Licenses in packaged builds

InvenTag is under the MIT license. The executable archives, the `.deb` and the
`.rpm` carry GNU libiconv, a library under the GNU Lesser General Public
License (LGPL) version 2.1. The Homebrew formula (not published yet) installs
the same archive, so it carries it too. The libiconv code is inside the
extension modules of lxml. InvenTag needs lxml to write Word files. The lxml
project builds those modules and links libiconv into them. In the archive, the
`.deb` and the `.rpm`, InvenTag carries the lxml files without a change.

- A pip, pipx or uv install does not carry libiconv in a file of InvenTag. Your
  installer downloads lxml's own wheel from the Python Package Index.
- The notices file is `THIRD-PARTY-LICENSES.txt`. It names each carried
  component, its license and its license text. It holds the full text of the
  LGPL 2.1. The release has one notices file for each system, named
  `inventag-1.4.0-<os>-<cpu>.THIRD-PARTY-LICENSES.txt`.
  The same file is inside the package:
  - archive: `inventag/THIRD-PARTY-LICENSES.txt`
  - `.deb` and `.rpm`: `/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt` and
    `/opt/inventag/THIRD-PARTY-LICENSES.txt`
- The notices file names the libiconv version and the places of the source. In
  this release it names libiconv 1.18 inside lxml 6.1.3:
  - libiconv: <https://www.gnu.org/software/libiconv/> and
    <https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz>
  - lxml: <https://github.com/lxml/lxml>
- InvenTag makes no written offer to send the source. The addresses above are
  the source. If an address does not work, open an issue at
  <https://github.com/habhabhabs/inventag-aws/issues>.
- The lxml modules are separate files in the installation directory. You can
  replace them with your own build of lxml of the same version. The folder is
  `inventag/_internal/lxml/` in the archive and `/opt/inventag/_internal/lxml/`
  for the `.deb` and the `.rpm`. On macOS, sign a module again after you
  replace it: `codesign -s - --force <file>`.

Not verified against your own lxml build: that a module that you build works in
place of the bundled one.

Not verified against a Homebrew install: that Homebrew leaves the lxml files
unchanged.

Not verified against macOS outside a GitHub runner: the Homebrew install and
Gatekeeper's behavior.

This page is not legal advice.

## Connect your AWS credentials

InvenTag uses the standard AWS credential chain, so any of these work:

With IAM Identity Center (recommended):

```bash title="Terminal"
aws sso login --profile my-readonly
export AWS_PROFILE=my-readonly
```

With long-lived access keys (avoid if you can):

```bash title="Terminal"
aws configure
```

Not verified against the AWS CLI: the sign-in commands in this section.

Prefer short-lived credentials, such as IAM Identity Center or an assumed
role, over access keys stored on disk.

## Check that it works

```bash title="Terminal"
inventag --validate-credentials --verbose
```

Exit code 0 means InvenTag could sign in. With `--verbose` you also see the
steps. Sample output from an offline run against mocked AWS (sample data):

<!-- BEGIN EXAMPLE OUTPUT: validate-credentials -->

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - INFO - 🔐 Validating AWS credentials...
inventag.cli.main - INFO - ✅ AWS credentials are valid!
inventag.cli.main - INFO - Using default AWS credentials
inventag.cli.main - INFO - Validating credentials for all accounts...
inventag.cli.main - INFO - Validating credentials for account: AWS Account 123456789012 (moto)
inventag.core.credential_manager.CredentialManager - INFO - Validating credentials for account 123456789012
inventag.core.credential_manager.CredentialManager - INFO - Successfully validated credentials for account 123456789012
inventag.cli.main - INFO - ✓ All account credentials are valid
```

```bash title="Terminal"
echo $?
```

```text title="Output"
0
```

<!-- END EXAMPLE OUTPUT: validate-credentials -->

If the credentials are missing, or the security token is not valid or has
expired, InvenTag says why and suggests a fix. See
[Fix common problems](../guides/troubleshooting.md#credentials).

## Give InvenTag read-only permissions

Before your first real scan, give the identity a read-only policy:
[Set up read-only access](../guides/read-only-access.md).

## Upgrade from v1.1.x

What you will notice after `pip install --upgrade inventag-aws`:

- **Secret values are masked.** Values of fields that often hold secrets,
  such as Lambda environment variables, become `***REDACTED***` in reports,
  snapshots and logs. The first run after the upgrade reports those resources
  as changed once. Reports and snapshots from earlier versions may still hold
  such values: delete or restrict them.
- **New columns.** Every service sheet has `source`, `sources` and
  `detail_level` columns. See [Output files](../reference/outputs.md).
- **More services and more API calls.** InvenTag lists 22 more services,
  which adds sheets, rows and calls. The repository policy has 17 new read
  actions (and no longer lists `cloudtrail:LookupEvents`); without them, each denied listing is a warning, and those resources are found through the Tagging API as before, when they are tagged. The first change report after the upgrade shows the resources of the newly listed services as added, although they existed before. See
  [IAM permissions](../reference/iam-permissions.md).
- **Stricter files.** An empty settings file, a key written twice or a
  `--bom-config` value of the wrong type stops the run with exit code 1.
- **Conflicting options stop with exit code 2**, for example `--accounts-file`
  with `--accounts-prompt`, or `--s3-kms-key-id` without
  `--s3-encryption aws:kms`.
- **The time limit is per account**, counted from when its scan starts. An
  account that runs out of time keeps the resources it found and counts as
  failed.
- **The default exit codes are the same.** Codes 5 and 6 are new and only
  with `--fail-on-account-error` and `--fail-if-empty`. A report format that
  cannot be written exits with code 1.
- **Service and sheet names stay.** Resources that v1.1.4 found only through
  the Tagging API keep their service name and sheet (for example
  `ELASTICFILESYSTEM`, `STATES`, `COGNITO-IDP`, `ELASTICMAPREDUCE`, `KAFKA`,
  `ES`). Their rows now carry the details of the service API, and the ID column
  of Secrets Manager secrets and MSK clusters holds the name instead of the last
  part of the ARN.

The full list is in the
[changelog](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md).

## Install for development

```bash title="Terminal"
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

The [contributing guide](../development/CONTRIBUTING.md) explains the full test
suite.

## Fix install problems

| What you see | What to do |
|---|---|
| `Error: No suitable Python interpreter found.` or `InvenTag requires Python 3.11 or later` | Install Python 3.11 or later and check that `python3 --version` works. |
| `inventag: command not found` | Activate the virtual environment where you ran `pip install inventag-aws`, or run `python -m pip show inventag-aws` to check it is installed. If you use the archive, make the link from `/opt/inventag/inventag` into a folder on your PATH, or run the program by its full path. |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt` again. |
| `inventag selftest` fails | Install InvenTag again, or download the release again, and run `inventag selftest` again. If it fails again, open an issue at <https://github.com/habhabhabs/inventag-aws/issues> and add the output. |
| `No AWS credentials found!` | Run `aws sso login` or `aws configure`, or set `AWS_PROFILE`. |

Not verified against the AWS CLI: the commands in the What to do column.

## Next step

[Quick start](./quick-start.md)
