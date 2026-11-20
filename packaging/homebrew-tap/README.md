# homebrew-inventag

The Homebrew tap of [InvenTag](https://github.com/habhabhabs/inventag-aws), a
read-only AWS inventory, tag check and BOM report tool.

## Install

```bash
brew install habhabhabs/inventag/inventag
inventag --version
inventag selftest
```

`brew install` with the full name taps this repository first. To tap it by
hand: `brew tap habhabhabs/inventag`.

## Which computers

| System | CPU | Supported |
| --- | --- | --- |
| macOS | Apple Silicon (arm64) | yes |
| macOS | Intel | no |
| Linux | x86_64 | yes |
| Linux | arm64 | yes |

There is no executable for an Intel Mac: a library InvenTag needs
(cryptography) publishes no ready-made build for it. On an Intel Mac,
`brew install` stops with a message that points to the install page. Other ways
to install are on
https://habhabhabs.github.io/inventag-aws/docs/getting-started/installation

## What the formula installs

The formula installs the executable that the release workflow of InvenTag
builds. It is a directory with its own runtime, so no Python is needed on the
computer. Nothing is compiled. The only download is the release archive, and
Homebrew checks it against the checksum written in the formula.

- The directory goes to `libexec`, and `inventag` in `bin` is a link into it.
- The shell completions (bash, zsh, fish) and the man page come from the same
  archive.
- `brew test` runs `inventag --version` and `inventag selftest`. The selftest
  makes no AWS call and opens no network connection.
- InvenTag does not check for updates. Use `brew upgrade inventag`.

Uninstall with `brew uninstall inventag`. Remove the tap with
`brew untap habhabhabs/inventag`.

## Licence

InvenTag is MIT licensed. The macOS and Linux executables that this tap
installs also bundle GNU libiconv inside the extension modules of lxml. libiconv
is licensed under LGPL-2.1. The source address of libiconv
(https://www.gnu.org/software/libiconv/) and the notices for every bundled
library are in the file `THIRD-PARTY-LICENSES.txt`. It is inside the archive and
after an install it is at `$(brew --prefix inventag)/libexec/THIRD-PARTY-LICENSES.txt`.
Installing with pip, pipx or uv does not redistribute libiconv. This is a
description of what is bundled and not legal advice.

## How this repository is made

`Formula/inventag.rb` is written by `scripts/packaging/render_formula.py` in the
InvenTag repository from the `SHA256SUMS` file of a release. Do not edit it by
hand: the next release writes it again. Report problems with the formula or with
InvenTag at https://github.com/habhabhabs/inventag-aws/issues.

The checks of this repository (`.github/workflows/ci.yml`) install the formula,
then compare the sha256 of every `lxml/*.so` in the installed `libexec` with the
file in the release archive, and fail on any difference. Not verified against a
Homebrew install: that Homebrew leaves the lxml files unchanged.

Not verified against macOS outside a GitHub runner: the Homebrew install, and
Gatekeeper's behaviour for an executable that Homebrew installs.
