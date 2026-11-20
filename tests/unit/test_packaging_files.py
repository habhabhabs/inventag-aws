"""The build files of the packaged formats (work order B2, plan section 3.4).

These tests read the files; they do not build anything. The build itself is run
by ``scripts/packaging/build_binary.sh`` and recorded in the B2 report.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PACKAGING = ROOT / "packaging"
SCRIPTS = ROOT / "scripts" / "packaging"


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_b2_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tpl():
    return _load("third_party_licenses")


# ------------------------------------------------------------- the version
VERSION_RX = re.compile(r"(?<![\w.])v?\d+\.\d+\.\d+(?![\w.])")


def test_no_version_number_under_packaging():
    """The version exists only in inventag/_version.py (plan 3.4)."""
    found = []
    for path in sorted(PACKAGING.rglob("*")):
        if path.is_file():
            for n, line in enumerate(path.read_text("utf-8").splitlines(), 1):
                if VERSION_RX.search(line):
                    found.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not found, "version numbers under packaging/:\n" + "\n".join(found)


def test_the_version_check_would_see_a_version():
    assert VERSION_RX.search("version: 1.4.0")
    assert VERSION_RX.search("inventag-v1.4.0-linux")
    assert not VERSION_RX.search("python:3.13-slim")


# ------------------------------------------------------------------ locks
def _lock_entries(path: Path):
    entries = {}
    current = None
    for line in path.read_text("utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==(\S+)", line)
        if m:
            current = m.group(1).lower().replace("_", "-")
            entries[current] = {"version": m.group(2), "hashes": 0}
        elif current and line.strip().startswith("--hash=sha256:"):
            entries[current]["hashes"] += 1
        elif line and not line.startswith((" ", "#")):
            current = None
    return entries


@pytest.mark.parametrize(
    "name", ["requirements-lock.txt", "requirements-lock-build.txt"]
)
def test_lock_pins_every_package_with_hashes(name):
    entries = _lock_entries(ROOT / name)
    assert entries
    unhashed = [k for k, v in entries.items() if v["hashes"] == 0]
    assert not unhashed, f"{name}: no hash for {unhashed}"
    text = (ROOT / name).read_text("utf-8")
    assert "--require-hashes" in text  # the install line in the header


def test_runtime_lock_covers_requirements_txt():
    entries = _lock_entries(ROOT / "requirements-lock.txt")
    names = set()
    for line in (ROOT / "requirements.txt").read_text("utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            names.add(re.split(r"[<>=!~;\[ ]", line)[0].lower().replace("_", "-"))
    missing = sorted(names - set(entries))
    assert not missing, f"in requirements.txt, not in the lock: {missing}"


# ---------------------------------------------------------- PyInstaller
def test_spec_builds_one_directory_without_strip_or_upx():
    spec = (PACKAGING / "pyinstaller" / "inventag.spec").read_text("utf-8")
    assert "COLLECT(" in spec
    assert "exclude_binaries=True" in spec
    assert "upx=True" not in spec and "strip=True" not in spec
    for module in ("readline", "_gdbm", "_dbm"):
        assert f'"{module}"' in spec


def test_build_script_refuses_a_one_file_build():
    script = SCRIPTS / "build_binary.sh"
    result = subprocess.run(
        [
            "bash",
            str(script),
            "build",
            "/nonexistent-venv",
            "/nonexistent-work",
            "--onefile",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert "one-file" in result.stderr


def test_build_script_installs_only_from_the_hash_pinned_locks():
    text = (SCRIPTS / "build_binary.sh").read_text("utf-8")
    assert "--require-hashes" in text
    assert "--only-binary :all:" in text
    assert "requirements-lock.txt" in text and "requirements-lock-build.txt" in text
    result = subprocess.run(
        ["bash", "-n", str(SCRIPTS / "build_binary.sh")], timeout=60
    )
    assert result.returncode == 0


# ------------------------------------------------------------------- nfpm
@pytest.fixture(scope="module")
def nfpm():
    return yaml.safe_load((PACKAGING / "nfpm" / "nfpm.yaml").read_text("utf-8"))


def test_nfpm_takes_the_version_from_the_environment(nfpm):
    assert nfpm["version"] == "${INVENTAG_VERSION}"
    assert nfpm["arch"] == "${NFPM_ARCH}"


def test_nfpm_installs_to_the_planned_paths(nfpm):
    dst = {c["dst"]: c for c in nfpm["contents"]}
    assert dst["/opt/inventag"]["type"] == "tree"
    assert dst["/usr/bin/inventag"]["type"] == "symlink"
    assert dst["/usr/bin/inventag"]["src"] == "/opt/inventag/inventag"
    for path in (
        "/usr/share/man/man1/inventag.1.gz",
        "/usr/share/bash-completion/completions/inventag",
        "/usr/share/fish/vendor_completions.d/inventag.fish",
        "/usr/share/doc/inventag/LICENSE",
        "/usr/share/doc/inventag/THIRD-PARTY-LICENSES.txt",
    ):
        assert path in dst, path
    zsh = {
        c["dst"]: c.get("packager")
        for c in nfpm["contents"]
        if c["dst"].endswith("/_inventag")
    }
    assert zsh == {
        "/usr/share/zsh/vendor-completions/_inventag": "deb",
        "/usr/share/zsh/site-functions/_inventag": "rpm",
    }


def test_nfpm_has_no_maintainer_script(nfpm):
    assert "scripts" not in nfpm
    assert "scripts" not in (nfpm.get("overrides") or {}).get("deb", {})
    assert "scripts" not in (nfpm.get("overrides") or {}).get("rpm", {})


# ----------------------------------------------------------------- Docker
def test_dockerfile_runs_as_non_root_from_the_hash_pinned_lock():
    text = (PACKAGING / "docker" / "Dockerfile").read_text("utf-8")
    # Pinned by digest, given at build time; no default, so no unpinned build.
    assert re.search(r"^ARG PYTHON_DIGEST$", text, re.M)
    froms = re.findall(r"^FROM (\S+)", text, re.M)
    assert froms and all(f == "python:3.13-slim@${PYTHON_DIGEST}" for f in froms)
    assert "--require-hashes" in text and "requirements-lock.txt" in text
    users = re.findall(r"^USER\s+(\S+)", text, re.M)
    assert users and users[-1] not in ("root", "0")
    assert re.search(r'^ENTRYPOINT \["inventag"\]', text, re.M)


# -------------------------------------------------------------- man page
def test_manpage_is_generated_from_the_parser():
    gen = _load("gen_manpage")
    page = gen.render()
    assert page.startswith(".TH INVENTAG 1")
    assert "\\-\\-create\\-excel" in page
    assert ".SH EXIT STATUS" in page
    assert gen.render() == page  # same bytes every time


# ----------------------------------------------------- licence check rules
def _comp(tpl, name, spdx, section="c-library", files=(), version="1"):
    return tpl.Component(name, version, spdx, section, list(files))


def test_lgpl_is_accepted_only_for_libiconv_in_lxml(tpl):
    ok = _comp(
        tpl, tpl.LXML_ICONV, "LGPL-2.1", files=["_internal/lxml/etree.cpython-312.so"]
    )
    assert tpl.licence_problems(ok) == []
    elsewhere = _comp(
        tpl, tpl.LXML_ICONV, "LGPL-2.1", files=["_internal/libiconv.so.2"]
    )
    assert tpl.licence_problems(elsewhere)
    other = _comp(tpl, "libfoo", "LGPL-2.1", files=["_internal/lxml/etree.so"])
    assert tpl.licence_problems(other)
    package = _comp(tpl, "somepkg", "LGPL-3.0-or-later", section="package")
    assert tpl.licence_problems(package)


def test_gcc_exception_only_for_the_named_files(tpl):
    ok = _comp(
        tpl, "libgcc_s.so.1", tpl.GCC_EXCEPTION, files=["_internal/libgcc_s.so.1"]
    )
    assert tpl.licence_problems(ok) == []
    bad = _comp(tpl, "libother.so", tpl.GCC_EXCEPTION, files=["_internal/libother.so"])
    assert tpl.licence_problems(bad)
    gpl = _comp(
        tpl,
        "libreadline.so.8",
        "GPL-3.0-or-later",
        files=["_internal/libreadline.so.8"],
    )
    assert tpl.licence_problems(gpl)


def test_openssl_before_3_is_refused(tpl):
    assert tpl.openssl_problems(
        _comp(tpl, "OpenSSL (in x)", "Apache-2.0", version="1.1.1w")
    )
    assert tpl.openssl_problems(_comp(tpl, "OpenSSL (in x)", "Apache-2.0", version=""))
    assert (
        tpl.openssl_problems(
            _comp(tpl, "OpenSSL (in x)", "Apache-2.0", version="3.5.4")
        )
        == []
    )


def test_forbidden_system_libraries(tpl):
    found = tpl.forbidden_problems(
        ["_internal/libc.so.6", "_internal/libreadline.so.8", "_internal/libz.so.1"]
    )
    assert len(found) == 2


def test_spdx_or_and_and(tpl):
    assert tpl.is_allowed("Apache-2.0 OR BSD-3-Clause", tpl.PACKAGE_LICENCES)
    assert tpl.is_allowed("GPL-2.0-only OR MIT", tpl.PACKAGE_LICENCES)
    assert not tpl.is_allowed("MIT AND GPL-2.0-only", tpl.PACKAGE_LICENCES)


class _SampleBuild:
    """A bundle described by a table, without PyInstaller."""

    def __init__(self, files, strings, same):
        self.files, self.strings, self.same = files, strings, same

    def bundled_distributions(self):
        return []

    def binaries(self):
        return list(self.files)

    def source_of(self, rel):
        return None

    def distribution_of_bundled(self, rel):
        return object()

    def same_as_wheel(self, rel):
        return self.same

    def contains(self, rel, needle):
        return needle in self.strings

    def read_text(self, source, owner):
        return (source, f"text of {source}\n")

    def read_version(self, source, rel, owner):
        return "9.9" if source else ""


def _sample_rows(tpl):
    return (
        tpl.Row("inventag", "pyinstaller"),
        tpl.Row("_internal/lxml/*.so", "package", carries=tpl._LXML, unmodified=True),
    )


def test_notices_file_from_a_sample_table(tpl, monkeypatch):
    monkeypatch.setattr(
        tpl,
        "_cpython",
        lambda p: tpl.Component("CPython", "3.12.3", "PSF-2.0", "runtime"),
    )
    monkeypatch.setattr(
        tpl,
        "_bootloader",
        lambda p: tpl.Component(
            "PyInstaller bootloader", "6", tpl.BOOTLOADER, "runtime"
        ),
    )
    monkeypatch.setattr(tpl, "_installed", lambda name: None)
    build = _SampleBuild(
        [
            "inventag",
            "_internal/lxml/etree.cpython-312.so",
            "_internal/lxml/objectify.cpython-312.so",
        ],
        b"xmlInitParser libiconv_open inflateInit2_",
        same=True,
    )
    comps, problems = tpl.collect(build, _sample_rows(tpl))
    assert problems == []
    text = tpl.render(comps)
    assert text == tpl.render(list(reversed(comps)))  # sorted, same bytes
    iconv = next(c for c in comps if c.name == tpl.LXML_ICONV)
    assert iconv.spdx == "LGPL-2.1"
    assert iconv.version == "9.9"
    assert "libxslt (in lxml)" not in [c.name for c in comps]  # no symbols, no row
    assert "etree.cpython-312.so, objectify.cpython-312.so" in text
    assert (
        "You can replace them with your own build of lxml of the same version." in text
    )
    assert "Not legal advice" in text
    for word in ("complies", "satisfies", "meets", "compliant"):
        assert word not in text.lower()


def test_lxml_file_that_differs_from_the_wheel_fails(tpl, monkeypatch):
    monkeypatch.setattr(
        tpl, "_cpython", lambda p: tpl.Component("CPython", "3", "PSF-2.0", "runtime")
    )
    monkeypatch.setattr(
        tpl, "_bootloader", lambda p: tpl.Component("b", "6", tpl.BOOTLOADER, "runtime")
    )
    monkeypatch.setattr(tpl, "_installed", lambda name: None)
    build = _SampleBuild(["_internal/lxml/etree.so"], b"libiconv_open", same=False)
    _, problems = tpl.collect(build, _sample_rows(tpl))
    assert any("differs from the file in the hash-pinned wheel" in p for p in problems)


def test_a_bundled_file_without_a_row_fails(tpl, monkeypatch):
    monkeypatch.setattr(
        tpl, "_cpython", lambda p: tpl.Component("CPython", "3", "PSF-2.0", "runtime")
    )
    monkeypatch.setattr(
        tpl, "_bootloader", lambda p: tpl.Component("b", "6", tpl.BOOTLOADER, "runtime")
    )
    build = _SampleBuild(["_internal/libmystery.so.1"], b"", same=True)
    _, problems = tpl.collect(build, _sample_rows(tpl))
    assert problems == ["_internal/libmystery.so.1: no row in the licence table"]
