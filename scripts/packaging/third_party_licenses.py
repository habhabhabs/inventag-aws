#!/usr/bin/env python3
"""Check the licences of a PyInstaller bundle and write THIRD-PARTY-LICENSES.txt.

Run it with the Python of the build environment, after PyInstaller:

    python scripts/packaging/third_party_licenses.py \
        --bundle dist/inventag --workpath build/inventag \
        --out dist/inventag/THIRD-PARTY-LICENSES.txt

Rules: plan section 3.4 and the architect's decision 1 of 20 Nov 2026
(/home/claude/audit/reports/architect-decisions-v14.md):

- Python packages: ``PACKAGE_LICENCES`` (MIT, MIT-0, BSD, Apache-2.0, PSF,
  MPL-2.0, ISC). Which packages were bundled is read from PyInstaller's tables
  of contents (``PYZ-00.toc``, ``COLLECT-00.toc``) and the packages' RECORD.
- Every shared library and extension module in the bundle (``*.so*``,
  ``*.dylib``) must match a row of ``TABLES[platform]``. A file with no row
  fails. A row names what the file carries: the package it belongs to, the
  system package it came from, CPython, and the C libraries linked into it.
- C libraries ("C libraries carried in the bundle") may also be Zlib,
  bzip2-1.0.6, 0BSD or public domain. GPL is accepted only for the exact files
  in ``NAMED_FILE_EXCEPTIONS``. Any other GPL, LGPL or AGPL item fails.
- ``--list-unmapped`` only lists every bundled binary with no row, with its
  source and owning packages; the check prints the same list first. A system
  with no table is checked against an empty one.
- The build Python is 3.12 (``BUILD_PYTHON``); any other version fails.
- No system C library (``libc``, ``libm``, ``libpthread``, ``ld-``), readline
  or gdbm may be in the bundle.
- OpenSSL must be version 3 or later (Apache-2.0).
- Every component needs its licence text; a missing text fails.

The output is sorted by component name and has no time stamp and no build
path, so the same bundle gives the same bytes. Exit 0 when the check passes,
1 otherwise; the file is written in both cases so the reasons can be read.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib.metadata as md
import os
import platform
import re
import subprocess
import sys
import sysconfig
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ------------------------------------------------------------------ policy
PACKAGE_LICENCES = frozenset(
    {
        "MIT",
        "MIT-0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "PSF-2.0",
        "MPL-2.0",
        "ISC",
    }
)
C_LIBRARY_LICENCES = PACKAGE_LICENCES | {
    "Zlib",
    "bzip2-1.0.6",
    "0BSD",
    "LicenseRef-public-domain",
}
GCC_EXCEPTION = "GPL-3.0-or-later WITH GCC-exception-3.1"
BOOTLOADER = "GPL-2.0-or-later WITH PyInstaller-Bootloader-exception"
# Exact file name -> the one licence with an exception it may carry.
NAMED_FILE_EXCEPTIONS = {
    "libgcc_s.so.1": GCC_EXCEPTION,
    "libstdc++.so.6": GCC_EXCEPTION,
    "libgomp.so.1": GCC_EXCEPTION,
}
FORBIDDEN_FILES = (
    "libreadline*",
    "libgdbm*",
    "libc.so*",
    "libm.so*",
    "libpthread*",
    "ld-*",
)
# Architect decision 2 (20 Nov 2026): the one LGPL item accepted, and where.
LXML_ICONV = "GNU libiconv, linked into lxml's extension modules"
LXML_ICONV_SPDX = "LGPL-2.1"
LXML_ICONV_FILES = "*/lxml/*.so"
LXML_PARAGRAPH = (
    "lxml's binary wheel, as published on PyPI under the project name lxml, "
    "is carried unmodified. Its extension modules ({files}) contain GNU "
    "libiconv under the GNU Lesser General Public License version 2.1, linked "
    "statically into those modules. The lxml modules are separate files in the "
    "installation directory. "
    "You can replace them with your own build of lxml of the same version."
)
LIBICONV_HOME = "https://www.gnu.org/software/libiconv/"
# How the version was read (architect ruling 2 of 20 Nov 2026, work order B2b).
LIBICONV_VERSION_FROM = "version read from the module's own symbol _libiconv_version"
LIBICONV_NO_VERSION = (
    "version not recorded: the lxml modules do not all hold the same symbol "
    "_libiconv_version"
)
LIBICONV_DOWNLOAD = "https://ftp.gnu.org/pub/gnu/libiconv/libiconv-{version}.tar.gz"
LXML_SOURCE = (
    "lxml {version} source (the Source address in its package metadata): {url}"
)
# Every executable is built with this Python (architect ruling 4 (b), B3 review):
# the table has rows only for what a 3.12 bundle carries.
BUILD_PYTHON = (3, 12)
COPYLEFT = re.compile(r"\b(A?GPL|LGPL)", re.IGNORECASE)

GCC_PARAGRAPH = (
    "{file} is part of GCC, the GNU Compiler Collection. It is licensed under "
    "the GNU General Public License version 3 or later with the GCC Runtime "
    "Library Exception, version 3.1, and is carried unmodified. The exception "
    "and the GPL version 3 follow."
)
BOOTLOADER_PARAGRAPH = (
    "The executable starts through PyInstaller's bootloader. PyInstaller is "
    "licensed under the GPL version 2 or later with a special exception that "
    "allows the use of the bootloader in programs under any licence. The "
    "texts follow."
)

# Distribution metadata that is not an SPDX expression. Each entry was read in
# the distribution's METADATA (License field or classifier).
METADATA_TO_SPDX = {
    "Apache License 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "MIT License": "MIT",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "Python Software Foundation License": "PSF-2.0",
    "ISC License (ISCL)": "ISC",
}
# When neither License-Expression nor License nor one classifier names it.
DISTRIBUTION_OVERRIDES = {
    # License "Dual License", classifiers BSD and Apache; its LICENSE file:
    # Apache-2.0 or BSD-3-Clause for changes since 2017, BSD-3-Clause before.
    "python-dateutil": "Apache-2.0 OR BSD-3-Clause",
    # No License field, classifier "BSD License"; LICENSE.txt: 3-clause text.
    "colorama": "BSD-3-Clause",
}


# ------------------------------------------------------------------ table
@dataclass(frozen=True)
class Carried:
    """A C library linked into a bundled file."""

    name: str
    spdx: str
    text: Tuple[str, ...]  # text sources, see Build.read_text
    version: str = ""  # version source, see Build.read_version; "" = not recorded
    # Present only when the bundled file holds this string (the library's
    # symbols): a wheel built without the library gets no such component.
    requires_strings: bytes = b""
    # Absent when the bundled file holds this string: the name of the library's
    # own file, which the module then loads instead of carrying a copy.
    loads_instead: bytes = b""
    notes: Tuple[str, ...] = ()
    urls: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Row:
    """Bundle files matching ``pattern`` (fnmatch on the path in the bundle)."""

    pattern: str
    origin: str  # "package": a Python package's file; "system": a system
    # package's library; "cpython": the build Python's own file
    spdx: str = ""  # for origin "system": the licence of the library
    carries: Tuple[Carried, ...] = ()
    extra_text: Tuple[str, ...] = ()  # more text sources (origin "system")
    # The bundled file must be byte-identical to the file of the hash-pinned
    # wheel (its RECORD hash): architect decision 2, condition 2.
    unmodified: bool = False


# Text sources: "dist:<package>:<file glob>", "pkgdoc" (the copyright file of
# the system package that owns the bundled file), "pkgdoc:<file>" (the
# copyright file of the system package that owns <file>), "path:<absolute>".
# Version sources: "sbom:<package>:<component>", "header:<package>:<file>:<macro>",
# "strings:<regex>" (read in the bundled file), "python:<expression>"
# (evaluated by the build Python), "pkg" (the system package version).
_LXML_TEXT = ("dist:lxml:*LICENSES.txt",)
_LXML_H = "header:lxml:lxml/includes/"
_LXML = (
    Carried(
        "libxml2 (in lxml)",
        "MIT",
        _LXML_TEXT,
        _LXML_H + "libxml/xmlversion.h:LIBXML_DOTTED_VERSION",
        requires_strings=b"xmlInitParser",
    ),
    Carried(
        "libxslt (in lxml)",
        "MIT",
        _LXML_TEXT,
        _LXML_H + "libxslt/xsltconfig.h:LIBXSLT_DOTTED_VERSION",
        requires_strings=b"xsltParseStylesheetDoc",
    ),
    Carried(
        "libexslt (in lxml)",
        "MIT",
        _LXML_TEXT,
        _LXML_H + "libexslt/exsltconfig.h:LIBEXSLT_DOTTED_VERSION",
        requires_strings=b"exsltRegisterAll",
    ),
    Carried(
        "zlib (in lxml)",
        "Zlib",
        _LXML_TEXT,
        _LXML_H + "extlibs/zlib.h:ZLIB_VERSION",
        requires_strings=b"inflateInit2_",
    ),
    Carried(
        LXML_ICONV,
        LXML_ICONV_SPDX,
        _LXML_TEXT + ("repo:scripts/packaging/licenses/LGPL-2.1.txt",),
        # Neither the wheel's notices nor lxml's headers name the version;
        # libiconv's own exported variable does: (major << 8) | minor.
        "elfsym:_libiconv_version",
        # One component for all modules, its addresses and notes: see
        # libiconv_component.
        requires_strings=b"libiconv_open",
    ),
)

LINUX_ROWS: Tuple[Row, ...] = (
    Row("inventag", "pyinstaller"),
    Row("_internal/lxml/*.so", "package", carries=_LXML, unmodified=True),
    Row(
        "_internal/cryptography/hazmat/bindings/_rust.abi3.so",
        "package",
        carries=(
            Carried(
                "OpenSSL (in cryptography)",
                "Apache-2.0",
                ("dist:cryptography:*LICENSE.APACHE",),
                "sbom:cryptography:openssl",
            ),
        ),
    ),
    Row(
        "_internal/yaml/_yaml*.so",
        "package",
        carries=(
            Carried(
                "libyaml (in PyYAML)",
                "MIT",
                # No verified source: the wheel's licence files hold only
                # PyYAML's text, and the repository has no sourced copy.
                (),
                "strings:^(0\\.2\\.[0-9]+)$",
            ),
        ),
    ),
    Row(
        "_internal/_cffi_backend*.so",
        "package",
        carries=(
            Carried(
                "libffi (in cffi)",
                "MIT",
                # No verified source: the wheel's licence files hold only
                # cffi's text, and the repository has no sourced copy.
                (),
                # Linked statically: the module defines ffi_prep_cif itself.
                requires_strings=b"ffi_prep_cif",
            ),
        ),
    ),
    Row("_internal/charset_normalizer/*.so", "package"),
    Row("_internal/psutil/*.so", "package"),
    Row("_internal/rpds/*.so", "package"),
    Row(
        "_internal/python3.*/lib-dynload/_decimal*.so",
        "cpython",
        carries=(
            Carried(
                "libmpdec (in CPython's _decimal)",
                "BSD-2-Clause",
                ("pkgdoc",),
                "python:decimal.__libmpdec_version__",
                # Dry run 3 (AlmaLinux 9) bundled libmpdec.so.3 as a file of its
                # own; a _decimal that names that file loads it.
                loads_instead=b"libmpdec.so",
            ),
        ),
    ),
    Row("_internal/python3.*/lib-dynload/*.so", "cpython"),
    Row("_internal/libpython3.*.so*", "cpython"),
    Row("_internal/libssl.so.3", "system", "Apache-2.0"),
    Row("_internal/libcrypto.so.3", "system", "Apache-2.0"),
    Row("_internal/libffi.so.*", "system", "MIT"),
    Row("_internal/libexpat.so.*", "system", "MIT"),
    Row("_internal/libz.so.*", "system", "Zlib"),
    Row("_internal/libbz2.so.*", "system", "bzip2-1.0.6"),
    # xz 5.4.x: liblzma is in the public domain (0BSD from xz 5.6.0 on).
    Row("_internal/liblzma.so.*", "system", "LicenseRef-public-domain"),
    Row(
        "_internal/libgcc_s.so.1",
        "system",
        GCC_EXCEPTION,
        extra_text=("repo:scripts/packaging/licenses/GPL-3.txt",),
    ),
)

# Only the Linux table exists, and its text sources were read on a Debian-family
# build host. The macOS bundle and the AlmaLinux 8 (rpm) build have not been
# read here: their first build prints every unmapped binary (unmapped_report)
# and fails; rows are written from that list and the libraries' own licence
# files, never from memory (architect ruling 4 (a), work order B2c).
TABLES: Dict[str, Tuple[Row, ...]] = {"linux": LINUX_ROWS}


# ------------------------------------------------------------------ model
@dataclass
class Component:
    name: str
    version: str
    spdx: str
    section: str  # "package", "c-library", "runtime"
    files: List[str] = field(default_factory=list)
    texts: List[Tuple[str, str]] = field(default_factory=list)  # (label, text)
    notes: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    version_from: str = ""  # how the version was read, when the file says so


def is_allowed(spdx: str, allowed: Iterable[str]) -> bool:
    """``A OR B``: one allowed choice is enough; ``A AND B``: all parts."""
    allowed = set(allowed)
    spdx = spdx.strip()
    if " OR " in spdx:
        return any(is_allowed(p, allowed) for p in _split(spdx, "OR"))
    if " AND " in spdx:
        return all(is_allowed(p, allowed) for p in _split(spdx, "AND"))
    return spdx.strip("()") in allowed


def _split(expr: str, word: str) -> List[str]:
    return [p.strip().strip("()").strip() for p in re.split(rf"\s+{word}\s+", expr)]


def licence_problems(comp: Component) -> List[str]:
    """Why a component's licence is refused; empty when it is accepted."""
    spdx = comp.spdx
    if comp.section == "runtime" and spdx in (BOOTLOADER, "PSF-2.0", "MIT"):
        return []
    if spdx == GCC_EXCEPTION:
        bad = [f for f in comp.files if NAMED_FILE_EXCEPTIONS.get(Path(f).name) != spdx]
        if comp.files and not bad:
            return []
        return [
            f"{comp.name}: {spdx} is accepted only for {', '.join(NAMED_FILE_EXCEPTIONS)}"
        ]
    if comp.name == LXML_ICONV and spdx == LXML_ICONV_SPDX:
        bad = [f for f in comp.files if not fnmatch.fnmatch(f, LXML_ICONV_FILES)]
        if comp.files and not bad:
            return []
        return [f"{comp.name}: {spdx} is accepted only for {LXML_ICONV_FILES}"]
    allowed = PACKAGE_LICENCES if comp.section == "package" else C_LIBRARY_LICENCES
    if COPYLEFT.search(spdx) and not is_allowed(spdx, allowed):
        return [f"{comp.name} {comp.version}: {spdx} (GPL, LGPL and AGPL are refused)"]
    if not is_allowed(spdx, allowed):
        return [f"{comp.name} {comp.version}: licence {spdx} is not in the allow-list"]
    return []


def openssl_problems(comp: Component) -> List[str]:
    if not comp.name.lower().startswith(("openssl", "libssl", "libcrypto")):
        return []
    major = re.match(r"\D*(\d+)\.", comp.version or "")
    if not major:
        return [
            f"{comp.name}: OpenSSL version not readable; version 3 or later is required"
        ]
    if int(major.group(1)) < 3:
        return [f"{comp.name} {comp.version}: OpenSSL before 3.0 is refused"]
    return []


def forbidden_problems(files: Sequence[str]) -> List[str]:
    return [
        f"{f}: this file must not be in the bundle"
        for f in files
        for pat in FORBIDDEN_FILES
        if fnmatch.fnmatch(Path(f).name, pat)
    ]


def match_row(rel: str, rows: Sequence[Row]) -> Optional[Row]:
    for row in rows:
        if fnmatch.fnmatch(rel, row.pattern):
            return row
    return None


def render(comps: Sequence[Component]) -> str:
    """THIRD-PARTY-LICENSES.txt: sorted, each identical text written once."""
    comps = sorted(comps, key=lambda c: (c.name.casefold(), c.version))
    sections = (
        ("package", "Python packages"),
        ("c-library", "C libraries carried in the bundle"),
        ("runtime", "Runtime: CPython and the PyInstaller bootloader"),
    )
    out = [
        "Third-party licences of the InvenTag executable",
        "",
        "InvenTag itself is under the MIT licence (LICENSE). The executable also",
        "carries the components below: name, version, licence (SPDX id), and the",
        "licence texts. Identical texts are written once and referred to.",
        "Not legal advice: this file lists what the build found and where the",
        "texts and sources are; it makes no statement about any licence.",
    ]
    for key, title in sections:
        part = [c for c in comps if c.section == key]
        if not part:
            continue
        out += ["", title, "-" * len(title)]
        for c in part:
            out.append(f"- {c.name} {c.version or '(version not recorded)'}: {c.spdx}")
            if c.version_from:
                out.append(f"    {c.version_from}")
            for u in c.urls:
                out.append(f"    source: {u}")
            for f in c.files:
                out.append(f"    file: {f}")
    seen: Dict[str, str] = {}
    for c in comps:
        out += ["", "=" * 78, f"{c.name} {c.version}".rstrip(), "=" * 78]
        out += [n for n in c.notes]
        for label, text in c.texts:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest in seen:
                out += ["", f"[{label}: the same text as under {seen[digest]} above]"]
                continue
            seen[digest] = f"{c.name}, {label}"
            out += ["", f"[{label}]", text.rstrip()]
    return "\n".join(out) + "\n"


def components_json(comps: Sequence[Component]) -> str:
    import json

    rows = []
    for c in sorted(comps, key=lambda c: (c.name.casefold(), c.version)):
        row = {
            "name": c.name,
            "version": c.version or "version not recorded",
            "licence": c.spdx,
            "section": c.section,
            "files": sorted(c.files),
        }
        if c.version_from:
            row["version_from"] = c.version_from
        rows.append(row)
    return json.dumps(rows, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------- reading a build
def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def spdx_of(name: str, metadata) -> Optional[str]:
    key = _canonical(name)
    if key in DISTRIBUTION_OVERRIDES:
        return DISTRIBUTION_OVERRIDES[key]
    if metadata.get("License-Expression"):
        return metadata["License-Expression"].strip()
    lic = (metadata.get("License") or "").strip()
    if lic and "\n" not in lic and len(lic) < 40:
        return METADATA_TO_SPDX.get(lic, lic)
    found = sorted(
        {
            METADATA_TO_SPDX.get(c.split("::")[-1].strip(), c.split("::")[-1].strip())
            for c in metadata.get_all("Classifier") or []
            if c.startswith("License ::")
        }
    )
    return found[0] if len(found) == 1 else None


def toc_sources(workpath: Path) -> List[str]:
    sources: List[str] = []
    for toc in ("PYZ-00.toc", "COLLECT-00.toc"):
        sources += _walk(ast.literal_eval((workpath / toc).read_text("utf-8")))
    return sorted(set(sources))


def _walk(node) -> List[str]:
    if (
        isinstance(node, tuple)
        and len(node) == 3
        and all(isinstance(x, str) or x is None for x in node)
    ):
        return [node[1]] if node[1] and os.path.isabs(node[1]) else []
    if isinstance(node, (list, tuple)):
        return [s for child in node for s in _walk(child)]
    return []


# ELF; Mach-O 32/64-bit in both byte orders; Mach-O universal ("fat").
BINARY_HEADERS = frozenset(
    {
        b"\x7fELF",
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
        b"\xca\xfe\xba\xbe",
    }
)


def _binary_header(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(4) in BINARY_HEADERS


class Build:
    """What the build environment and the bundle say. Kept apart for tests."""

    def __init__(self, bundle: Path, workpath: Path, repo_root: Path):
        self.bundle = bundle
        self.workpath = workpath
        self.repo_root = repo_root.resolve()
        self.index: Dict[str, md.Distribution] = {}
        for dist in md.distributions():
            for f in dist.files or []:
                self.index[str(Path(dist.locate_file(f)).resolve())] = dist

    # -- the bundle
    def binaries(self) -> List[str]:
        """Every shared library, extension module and executable: by name, and
        by an ELF or Mach-O header (a macOS bundle carries CPython as
        ``_internal/Python``, with no suffix)."""
        out = []
        for p in sorted(self.bundle.rglob("*")):
            if p.is_file() and (
                ".so" in p.name
                or p.suffix == ".dylib"
                or p == self.bundle / "inventag"
                or _binary_header(p)
            ):
                out.append(str(p.relative_to(self.bundle)))
        return out

    def file_path(self, rel: str) -> Path:
        return self.bundle / rel

    def bundled_distributions(self) -> List[md.Distribution]:
        found: Dict[str, md.Distribution] = {}
        for src in toc_sources(self.workpath):
            dist = self.index.get(str(Path(src).resolve()))
            if dist is not None:
                found[_canonical(dist.metadata["Name"])] = dist
        return [found[k] for k in sorted(found)]

    def contains(self, rel: str, needle: bytes) -> bool:
        return needle in self.file_path(rel).read_bytes()

    def same_as_wheel(self, rel: str) -> bool:
        """The bundled file has the sha256 its wheel's RECORD gives."""
        import base64

        dist = self.distribution_of_bundled(rel)
        inner = rel.split("_internal/", 1)[-1]
        for f in (dist.files or []) if dist else []:
            if str(f) == inner and f.hash is not None and f.hash.mode == "sha256":
                digest = hashlib.sha256(self.file_path(rel).read_bytes()).digest()
                return (
                    base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
                    == f.hash.value
                )
        return False

    def distribution_of_bundled(self, rel: str) -> Optional[md.Distribution]:
        inner = rel.split("_internal/", 1)[-1]
        for dist in md.distributions():
            for f in dist.files or []:
                if str(f) == inner:
                    return dist
        return None

    # -- system packages
    def source_of(self, rel: str) -> Optional[str]:
        """Path on the build system of a bundled binary (from the TOC)."""
        name = rel.split("_internal/", 1)[-1]
        for src in toc_sources(self.workpath):
            if src.endswith("/" + name) or Path(src).name == Path(name).name:
                if Path(src).name == Path(name).name:
                    return src
        return None

    def owning_package(self, path: str) -> Optional[Tuple[str, str]]:
        real = str(Path(path).resolve())
        for cmd in (["dpkg", "-S", real], ["rpm", "-qf", "--qf", "%{NAME}", real]):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, check=False)
            except FileNotFoundError:
                continue
            if r.returncode == 0 and r.stdout.strip():
                pkg = r.stdout.split(":")[0].strip()
                return pkg, self.package_version(pkg)
        return None

    def package_version(self, pkg: str) -> str:
        for cmd in (
            ["dpkg-query", "-W", "-f", "${Version}", pkg],
            ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", pkg],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, check=False)
            except FileNotFoundError:
                continue
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        return ""

    def package_doc(self, pkg: str) -> Optional[Tuple[str, str]]:
        for path in (
            Path("/usr/share/doc") / pkg / "copyright",
            *sorted(Path("/usr/share/licenses", pkg).glob("*")),
        ):
            if path.is_file():
                return f"{pkg}: {path.name}", path.read_text("utf-8", "replace")
        return None

    # -- sources of texts and versions
    def read_text(
        self, source: str, owner_file: Optional[str]
    ) -> Optional[Tuple[str, str]]:
        kind, _, arg = source.partition(":")
        if kind == "dist":
            pkg, _, pattern = arg.partition(":")
            dist = md.distribution(pkg)
            for f in sorted(dist.files or [], key=str):
                if fnmatch.fnmatch(str(f), pattern):
                    return f"{dist.metadata['Name']}: {Path(str(f)).name}", Path(
                        dist.locate_file(f)
                    ).read_text("utf-8", "replace")
            return None
        if kind == "pkgdoc":
            target = arg or owner_file
            owner = self.owning_package(target) if target else None
            return self.package_doc(owner[0]) if owner else None
        if kind == "repo":
            p = self.repo_root / arg
            return (p.name, p.read_text("utf-8", "replace")) if p.is_file() else None
        if kind == "path":
            p = Path(arg)
            return (p.name, p.read_text("utf-8", "replace")) if p.is_file() else None
        raise ValueError(f"unknown text source {source!r}")

    def read_version(self, source: str, rel: str, owner_file: Optional[str]) -> str:
        if not source:
            return ""
        kind, _, arg = source.partition(":")
        if kind == "sbom":
            import json

            pkg, _, name = arg.partition(":")
            dist = md.distribution(pkg)
            for f in dist.files or []:
                if "sboms/" in str(f) and str(f).endswith(".json"):
                    data = json.loads(Path(dist.locate_file(f)).read_text("utf-8"))
                    for c in data.get("components", []):
                        # pkg:generic is the C library; pkg:cargo/<name> is a
                        # Rust crate of the same name (the openssl bindings).
                        if c.get("name") == name and str(c.get("purl", "")).startswith(
                            "pkg:generic/"
                        ):
                            return str(c.get("version", ""))
            return ""
        if kind == "header":
            pkg, _, rest = arg.partition(":")
            fname, _, macro = rest.rpartition(":")
            path = Path(md.distribution(pkg).locate_file(fname))
            if path.is_file():
                m = re.search(
                    rf'#define\s+{macro}\s+"([^"]+)"', path.read_text("utf-8")
                )
                return m.group(1) if m else ""
            return ""
        if kind == "strings":
            data = self.file_path(rel).read_bytes()
            rx = re.compile(arg.encode())
            for chunk in re.findall(rb"[\x20-\x7e]{4,}", data):
                m = rx.match(chunk)
                if m:
                    return m.group(1).decode()
            return ""
        if kind == "python":
            import decimal  # noqa: F401  (the expressions name stdlib modules)

            module = arg.split(".")[0]
            return str(eval(arg, {module: __import__(module)}))  # table constant
        if kind == "elfsym":
            raw = elf_symbol_bytes(self.file_path(rel).read_bytes(), arg)
            if raw is None or len(raw) < 2:
                return ""
            value = int.from_bytes(raw, "little")
            return f"{value >> 8}.{value & 0xFF}"
        if kind == "pkg":
            owner = self.owning_package(owner_file) if owner_file else None
            return owner[1] if owner else ""
        raise ValueError(f"unknown version source {source!r}")


# ------------------------------------------------------------------ check
def collect(build: Build, rows: Sequence[Row]) -> Tuple[List[Component], List[str]]:
    problems: List[str] = []
    comps: Dict[str, Component] = {}

    def add(comp: Component) -> Component:
        key = f"{comp.name}\0{comp.version}"
        if key in comps:
            comps[key].files += [f for f in comp.files if f not in comps[key].files]
            return comps[key]
        comps[key] = comp
        return comp

    # Python packages, from what PyInstaller bundled.
    for dist in build.bundled_distributions():
        name = dist.metadata["Name"]
        if _canonical(name) in ("pyinstaller", "pyinstaller-hooks-contrib"):
            continue
        texts = [
            (
                f"{name}: {Path(str(f)).name}",
                Path(dist.locate_file(f)).read_text("utf-8", "replace"),
            )
            for f in sorted(dist.files or [], key=str)
            if re.search(r"(LICEN[CS]E|COPYING|NOTICE)", Path(str(f)).name, re.I)
        ]
        if not texts:
            problems.append(f"{name}: no licence text in its distribution")
        add(
            Component(
                name,
                dist.version,
                spdx_of(name, dist.metadata) or "UNKNOWN",
                "package",
                texts=texts,
                urls=_urls(dist.metadata),
            )
        )

    # Runtime: CPython and the bootloader.
    add(_cpython(problems))
    add(_bootloader(problems))

    # Every binary file of the bundle. libiconv's modules are gathered first and
    # become one component (architect ruling 2).
    iconv_versions: Dict[str, str] = {}
    iconv_texts: List[Tuple[str, str]] = []
    binaries = build.binaries()
    problems += forbidden_problems(binaries)
    for rel in binaries:
        row = match_row(rel, rows)
        if row is None:
            problems.append(f"{rel}: no row in the licence table")
            continue
        source = build.source_of(rel)
        if row.origin == "package" and build.distribution_of_bundled(rel) is None:
            problems.append(f"{rel}: the table says a package file, no package owns it")
        if row.unmodified and not build.same_as_wheel(rel):
            problems.append(f"{rel}: differs from the file in the hash-pinned wheel")
        if row.origin == "system":
            owner = build.owning_package(source) if source else None
            if owner is None:
                problems.append(f"{rel}: no system package owns {source}")
                continue
            texts = []
            for src in ("pkgdoc",) + row.extra_text:
                got = build.read_text(src, source)
                if got is None:
                    problems.append(f"{rel}: licence text not found ({src})")
                else:
                    texts.append(got)
            comp = add(
                Component(Path(rel).name, owner[1], row.spdx, "c-library", [rel], texts)
            )
            if row.spdx == GCC_EXCEPTION:
                comp.notes = [GCC_PARAGRAPH.format(file=Path(rel).name)]
        for carried in row.carries:
            if carried.requires_strings and not build.contains(
                rel, carried.requires_strings
            ):
                continue
            if carried.loads_instead and build.contains(rel, carried.loads_instead):
                continue
            got = [build.read_text(s, source) for s in carried.text]
            if not carried.text:
                problems.append(
                    f"{rel}: licence text of {carried.name}: no verified source in "
                    "the table; add the upstream text under "
                    "scripts/packaging/licenses/ (first line: its address, version "
                    "or commit, and date)"
                )
            elif any(g is None for g in got):
                problems.append(f"{rel}: licence text of {carried.name} not found")
            if carried.name == LXML_ICONV:
                iconv_versions[rel] = build.read_version(carried.version, rel, source)
                iconv_texts = iconv_texts or [g for g in got if g is not None]
                continue
            add(
                Component(
                    carried.name,
                    build.read_version(carried.version, rel, source),
                    carried.spdx,
                    "c-library",
                    [rel],
                    [g for g in got if g is not None],
                    urls=list(carried.urls),
                )
            )

    if iconv_versions:
        add(libiconv_component(iconv_versions, iconv_texts))
    out = sorted(comps.values(), key=lambda c: (c.name.casefold(), c.version))
    for comp in out:
        problems += licence_problems(comp)
        problems += openssl_problems(comp)
    return out, sorted(set(problems))


@dataclass(frozen=True)
class Unmapped:
    """A bundled binary with no row, and what the build says about it."""

    file: str
    source: str
    python_package: str
    system_package: str


def unmapped_files(build: Build, rows: Sequence[Row]) -> List[Unmapped]:
    """Every bundled binary with no row (architect ruling 4 (a)): one run
    gives the whole list a new table needs, never only the first file."""
    out = []
    for rel in build.binaries():
        if match_row(rel, rows) is not None:
            continue
        source = build.source_of(rel)
        dist = build.distribution_of_bundled(rel)
        owner = build.owning_package(source) if source else None
        out.append(
            Unmapped(
                rel,
                source or "not in PyInstaller's tables",
                f"{dist.metadata['Name']} {dist.version}" if dist else "none",
                f"{owner[0]} {owner[1]}".rstrip() if owner else "none found",
            )
        )
    return out


def unmapped_report(entries: Sequence[Unmapped], plat: str, python: str) -> str:
    out = [f"unmapped files: {len(entries)} (platform {plat}, Python {python})"]
    out += [
        f"UNMAPPED {e.file} | source: {e.source} | python package: "
        f"{e.python_package} | system package: {e.system_package}"
        for e in sorted(entries, key=lambda e: e.file)
    ]
    return "\n".join(out) + "\n"


def add_libiconv_note(comp: Component) -> None:
    """The libiconv paragraph and source addresses (architect decision 2).

    One function for every artefact that carries lxml's modules, so the
    words are the same everywhere.
    """
    names = ", ".join(sorted(Path(f).name for f in comp.files))
    comp.notes = [LXML_PARAGRAPH.format(files=names)]
    if comp.version:
        comp.urls.append(LIBICONV_DOWNLOAD.format(version=comp.version))
    lxml = _installed("lxml")
    if lxml is not None:
        comp.urls += [
            LXML_SOURCE.format(version=lxml.version, url=u)
            for u in _source_urls(lxml.metadata)
        ]


def libiconv_component(
    versions: Dict[str, str], texts: Sequence[Tuple[str, str]] = ()
) -> Component:
    """The one libiconv component for the lxml modules that carry it.

    ``versions`` maps each module (its path) to the version its own symbol
    gives, "" when it has none. The executable's notices and the container
    notice both build the component here. The version is recorded only when
    every module gives the same one; otherwise there is no version and no
    versioned download address, and the line that says how the version was
    read says why there is none.
    """
    found = set(versions.values())
    version = found.pop() if len(found) == 1 else ""
    comp = Component(
        LXML_ICONV,
        version,
        LXML_ICONV_SPDX,
        "c-library",
        sorted(versions),
        list(texts),
        urls=[LIBICONV_HOME],
        version_from=LIBICONV_VERSION_FROM if version else LIBICONV_NO_VERSION,
    )
    add_libiconv_note(comp)
    return comp


def _iconv_version(path: Path) -> str:
    """libiconv's version from its own symbol in the module, or ""."""
    raw = elf_symbol_bytes(Path(path).read_bytes(), "_libiconv_version")
    if raw is None or len(raw) < 2:
        return ""
    value = int.from_bytes(raw, "little")
    return f"{value >> 8}.{value & 0xFF}"


def libiconv_notice() -> str:
    """The libiconv notice of the container image (architect review F3).

    The image installs lxml's wheel as pip does, so the modules are found
    through the installed distribution. The paragraph and the addresses come
    from ``add_libiconv_note``, as in THIRD-PARTY-LICENSES.txt. If the modules
    do not name one version, the version is not recorded.
    """
    lxml = _installed("lxml")
    versions: Dict[str, str] = {}
    for f in sorted((lxml.files or []) if lxml else [], key=str):
        rel = str(f).replace(os.sep, "/")
        path = Path(lxml.locate_file(f))
        if not fnmatch.fnmatch(rel, "lxml/*.so"):
            continue
        if b"libiconv_open" not in path.read_bytes():
            continue
        versions[rel] = _iconv_version(path)
    out = [
        "GNU libiconv in lxml's extension modules (container image)",
        "",
        "Not legal advice: this file lists what the image build found and where",
        "the texts and sources are; it makes no statement about any licence.",
        "",
    ]
    if not versions:
        out.append("No lxml extension module in this image contains GNU libiconv.")
        return "\n".join(out) + "\n"
    comp = libiconv_component(versions)
    out.append(f"- {comp.name} {comp.version or '(version not recorded)'}: {comp.spdx}")
    out.append(f"    {comp.version_from}")
    out += [f"    source: {u}" for u in comp.urls]
    out += [f"    file: {f}" for f in comp.files]
    out += [""] + comp.notes
    out += [
        "",
        "The text of the GNU Lesser General Public License version 2.1 is in",
        "LGPL-2.1.txt in this directory.",
    ]
    return "\n".join(out) + "\n"


def elf_symbol_bytes(data: bytes, name: str) -> Optional[bytes]:
    """The bytes of a defined data symbol in a 64-bit little-endian ELF file."""
    import struct

    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return None
    (shoff,) = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3A)
    sections = [
        struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize)
        for i in range(shnum)
    ]
    for sh in sections:
        if sh[1] not in (2, 11):  # SHT_SYMTAB, SHT_DYNSYM
            continue
        strtab = sections[sh[6]]
        for off in range(sh[4], sh[4] + sh[5], 24):
            st_name, _info, _other, shndx, value, size = struct.unpack_from(
                "<IBBHQQ", data, off
            )
            start = strtab[4] + st_name
            if (
                data[start : data.index(b"\0", start)] != name.encode()
                or not 0 < shndx < shnum
            ):
                continue
            target = sections[shndx]
            if target[1] == 8:  # SHT_NOBITS: zero-initialised, no bytes in the file
                return None
            pos = target[4] + value - target[3]
            return data[pos : pos + size]
    return None


SOURCE_LABELS = ("source", "source code", "repository", "code", "homepage", "home")


def _source_urls(metadata) -> List[str]:
    """Only the Project-URL labelled "Source"."""
    return sorted(
        e.partition(",")[2].strip()
        for e in metadata.get_all("Project-URL") or []
        if e.partition(",")[0].strip().lower() == "source"
    )


def _urls(metadata) -> List[str]:
    """Where the source is: the Home-page and the Project-URLs labelled so."""
    urls = []
    for entry in metadata.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in SOURCE_LABELS:
            urls.append(url.strip())
    if metadata.get("Home-page"):
        urls.append(metadata["Home-page"].strip())
    return sorted(set(urls))


def _installed(name: str) -> Optional[md.Distribution]:
    try:
        return md.distribution(name)
    except md.PackageNotFoundError:
        return None


def python_version_problems(version_info: Sequence[int]) -> List[str]:
    """The executable is built with Python 3.12 only (architect ruling 4 (b))."""
    if tuple(version_info[:2]) == BUILD_PYTHON:
        return []
    found = ".".join(str(n) for n in version_info[:3])
    want = ".".join(str(n) for n in BUILD_PYTHON)
    return [
        f"CPython {found}: the executable is built with Python {want} only; "
        f"create the build environment with python{want} "
        f"(build_binary.sh venv <dir> python{want}) and build again"
    ]


def _cpython(
    problems: List[str], version_info: Optional[Sequence[int]] = None
) -> Component:
    if version_info is None:
        version_info = sys.version_info
    problems += python_version_problems(version_info)
    texts = []
    for base in (sysconfig.get_paths()["stdlib"], sys.base_prefix):
        path = Path(base) / "LICENSE.txt"
        if path.is_file():
            texts = [("CPython: LICENSE.txt", path.read_text("utf-8", "replace"))]
            break
    if not texts:
        problems.append("CPython: LICENSE.txt of the build Python not found")
    return Component(
        "CPython",
        ".".join(str(n) for n in version_info[:3]),
        "PSF-2.0",
        "runtime",
        texts=texts,
        urls=["https://docs.python.org/3/license.html"],
    )


def _bootloader(problems: List[str]) -> Component:
    try:
        dist = md.distribution("pyinstaller")
    except md.PackageNotFoundError:
        problems.append("PyInstaller is not installed in the build environment")
        return Component("PyInstaller bootloader", "", BOOTLOADER, "runtime")
    texts = [
        (
            f"PyInstaller: {Path(str(f)).name}",
            Path(dist.locate_file(f)).read_text("utf-8", "replace"),
        )
        for f in sorted(dist.files or [], key=str)
        if re.search(r"(COPYING|LICEN[CS]E)", Path(str(f)).name, re.I)
    ]
    if not texts:
        problems.append("PyInstaller: licence text not found")
    return Component(
        "PyInstaller bootloader",
        dist.version,
        BOOTLOADER,
        "runtime",
        texts=texts,
        notes=[BOOTLOADER_PARAGRAPH],
        urls=_urls(dist.metadata),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--bundle", type=Path, help="dist/inventag")
    parser.add_argument("--workpath", type=Path, help="build/inventag")
    parser.add_argument("--out", type=Path, help="THIRD-PARTY-LICENSES.txt")
    parser.add_argument(
        "--list-unmapped",
        action="store_true",
        help="only list every bundled binary with no row in the table, with its "
        "source and owning packages; exit 1 when there is one (the licence check "
        "prints the same list first)",
    )
    parser.add_argument(
        "--lxml-notice",
        action="store_true",
        help="write only the libiconv notice for the installed lxml (container "
        "image); --bundle and --workpath are not used",
    )
    parser.add_argument(
        "--components-json",
        type=Path,
        help="also write the components (name, version, licence, files) as JSON, "
        "for the per-artefact SBOM",
    )
    parser.add_argument("--platform", default=sys.platform.rstrip("0123456789"))
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    ns = parser.parse_args(argv)
    if ns.out is None and not ns.list_unmapped:
        parser.error("--out is required")
    if ns.lxml_notice:
        ns.out.write_text(libiconv_notice(), encoding="utf-8")
        print(f"libiconv notice written to {ns.out}")
        return 0
    if ns.bundle is None or ns.workpath is None:
        parser.error("--bundle and --workpath are required")
    # A system without a table is checked against an empty one, so the list
    # below names every binary of its first build.
    rows = TABLES.get(ns.platform, ())
    build = Build(ns.bundle, ns.workpath, ns.repo_root)
    entries = unmapped_files(build, rows)
    report = unmapped_report(entries, ns.platform, platform.python_version())
    print(report, end="", flush=True)  # before any stderr line in a CI log
    if ns.list_unmapped:
        return 1 if entries else 0
    comps, problems = collect(build, rows)
    if ns.platform not in TABLES:
        problems.insert(0, f"no licence table for {ns.platform}")
    ns.out.write_text(render(comps), encoding="utf-8")
    if ns.components_json:
        ns.components_json.write_text(components_json(comps), encoding="utf-8")
    print(f"{len(comps)} components written to {ns.out}")
    for p in problems:
        print(f"LICENCE CHECK: {p}", file=sys.stderr)
    print("licence check: " + ("FAIL" if problems else "pass"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
