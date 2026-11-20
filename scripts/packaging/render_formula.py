#!/usr/bin/env python3
"""Render the Homebrew formula of the tap from a version and a SHA256SUMS file.

A release-time tool (plan 3.4, work order B4); it is not part of the package.

    python scripts/packaging/render_formula.py --version 1.4.0 \\
        --sums SHA256SUMS --output Formula/inventag.rb

The template is ``packaging/homebrew-tap/Formula/inventag.rb``. It holds four
``{{...}}`` values: the version and the checksums of the three archives that
``.github/workflows/package.yml`` attaches to a release:

    inventag-<version>-darwin-arm64.tar.gz
    inventag-<version>-linux-x86_64.tar.gz
    inventag-<version>-linux-arm64.tar.gz

``SHA256SUMS`` is the file the workflow's provenance job writes with
``sha256sum``: ``<64 lower-case hex>  <file name>``, one file per line. Lines for
other files (packages, notices, SBOMs) are read and ignored. The script stops
with a plain message and exit 2 when a line is malformed, when any file name is
listed twice, or when one of the three archives has no line. No network, no
clock, nothing written when it stops.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = ROOT / "packaging" / "homebrew-tap" / "Formula" / "inventag.rb"

# placeholder -> archive suffix after "inventag-<version>-"
ARCHIVES = {
    "SHA256_DARWIN_ARM64": "darwin-arm64.tar.gz",
    "SHA256_LINUX_X86_64": "linux-x86_64.tar.gz",
    "SHA256_LINUX_ARM64": "linux-arm64.tar.gz",
}
VERSION_RX = re.compile(r"\d+\.\d+\.\d+")
LINE_RX = re.compile(r"^([0-9a-f]{64}) [ *]([^\s/\\]+)$")
PLACEHOLDER_RX = re.compile(r"\{\{([A-Za-z0-9_]*)\}\}")


class RenderError(Exception):
    """A plain message for the person who runs the script."""


def clean_version(version: str) -> str:
    """The bare number; one leading ``v`` (a tag) is accepted."""
    bare = version[1:] if version.startswith("v") else version
    if not VERSION_RX.fullmatch(bare):
        raise RenderError(
            f"version {version!r} is not of the form X.Y.Z (a leading v is allowed)"
        )
    return bare


def parse_sums(text: str) -> Dict[str, str]:
    """Map file name to checksum; stop on a malformed or repeated line."""
    found: Dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        match = LINE_RX.match(line)
        if not match:
            raise RenderError(
                f"SHA256SUMS line {number} is malformed: expected 64 lower-case "
                "hex digits, two spaces and a file name without a folder"
            )
        checksum, name = match.groups()
        if name in found:
            raise RenderError(f"SHA256SUMS lists {name} more than once")
        found[name] = checksum
    return found


def render(template: str, version: str, sums: str) -> str:
    """The formula text. Raises RenderError; never returns a half-filled file."""
    bare = clean_version(version)
    listed = parse_sums(sums)
    values = {"VERSION": bare}
    for key, suffix in ARCHIVES.items():
        name = f"inventag-{bare}-{suffix}"
        if name not in listed:
            raise RenderError(f"SHA256SUMS has no checksum line for {name}")
        values[key] = listed[name]

    def fill(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key not in values:
            raise RenderError(f"the template has an unknown placeholder {{{{{key}}}}}")
        return values[key]

    return PLACEHOLDER_RX.sub(fill, template)


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="render_formula.py",
        description="Render the Homebrew formula from a version and a SHA256SUMS file.",
    )
    parser.add_argument("--version", required=True, help="X.Y.Z, or the tag vX.Y.Z")
    parser.add_argument(
        "--sums", required=True, help="the SHA256SUMS file of the release"
    )
    parser.add_argument(
        "--template", default=str(DEFAULT_TEMPLATE), help="the formula template"
    )
    parser.add_argument("--output", help="write here (default: standard output)")
    args = parser.parse_args(argv)
    try:
        try:
            sums = Path(args.sums).read_text(encoding="utf-8")
            template = Path(args.template).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            name = getattr(exc, "filename", None) or args.sums
            raise RenderError(f"cannot read {name}: {type(exc).__name__}") from exc
        text = render(template, args.version, sums)
        if args.output:
            write_atomic(Path(args.output), text)
        else:
            sys.stdout.write(text)
    except RenderError as exc:
        print(f"render_formula: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
