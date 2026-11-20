"""The build files of the packaged formats (work order B2, plan section 3.4).

These tests read the files; they do not build anything. The build itself is run
by ``scripts/packaging/build_binary.sh`` and recorded in the B2 report.
"""

from __future__ import annotations

import importlib.util
import json
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


def _version_lines(base: Path):
    """Lines under ``base`` that hold a version number, as path:line: text."""
    found = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            for n, line in enumerate(path.read_text("utf-8").splitlines(), 1):
                if VERSION_RX.search(line):
                    found.append(f"{path.relative_to(base.parent)}:{n}: {line.strip()}")
    return found


def test_no_version_number_under_packaging():
    """The version exists only in inventag/_version.py (plan 3.4)."""
    found = _version_lines(PACKAGING)
    assert not found, "version numbers under packaging/:\n" + "\n".join(found)


def test_the_version_check_skips_bytecode_left_by_a_build(tmp_path):
    # A PyInstaller build leaves hooks/__pycache__/*.pyc under packaging/; they
    # are not tracked files (architect review of B3, ruling 4 (c)).
    hooks = tmp_path / "packaging" / "hooks"
    (hooks / "__pycache__").mkdir(parents=True)
    (hooks / "__pycache__" / "hook-x.cpython-312.pyc").write_bytes(b"\xff\xfe 1.2.3")
    (hooks / "stray.pyc").write_bytes(b"\xff\xfe 1.2.3")
    (hooks / "hook-x.py").write_text("name = 'x'\n", encoding="utf-8")
    assert _version_lines(tmp_path / "packaging") == []
    (hooks / "hook-x.py").write_text("version = '1.2.3'\n", encoding="utf-8")
    assert _version_lines(tmp_path / "packaging") == [
        "packaging/hooks/hook-x.py:1: version = '1.2.3'"
    ]


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


class _SpecRun:
    """Run inventag.spec with stand-ins for PyInstaller's build classes: what
    the spec hands to COLLECT, without PyInstaller."""

    def __init__(self, binaries, datas):
        self.binaries, self.datas = binaries, datas
        self.collected = None

    def run(self, monkeypatch, plat):
        import types

        hooks = types.ModuleType("PyInstaller.utils.hooks")
        hooks.copy_metadata = lambda name: [("keyring.dist-info", "/m", "DATA")]
        for name in ("PyInstaller", "PyInstaller.utils"):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
        monkeypatch.setattr(sys, "platform", plat)
        run = self

        class Analysis:
            def __init__(self, *args, **kwargs):
                self.binaries = list(run.binaries)
                self.datas = list(run.datas)
                self.pure, self.scripts = [], []

        def collect(*args, **kwargs):
            run.collected = args

        spec = PACKAGING / "pyinstaller" / "inventag.spec"
        exec(
            compile(spec.read_text("utf-8"), str(spec), "exec"),
            {
                "SPECPATH": str(spec.parent),
                "Analysis": Analysis,
                "PYZ": lambda *a, **k: None,
                "EXE": lambda *a, **k: None,
                "COLLECT": collect,
            },
        )
        _exe, binaries, datas = self.collected
        return binaries, datas


LXML_TOC = [
    ("lxml/etree.cpython-312-darwin.so", "/v/lxml/etree.cpython-312-darwin.so"),
    ("lxml/html/diff.cpython-312-darwin.so", "/v/lxml/html/diff.cpython-312-darwin.so"),
]
OTHER_TOC = [
    ("yaml/_yaml.cpython-312-darwin.so", "/v/yaml/_yaml.cpython-312-darwin.so"),
    ("python3.12/lib-dynload/_json.cpython-312-darwin.so", "/f/_json.so"),
]


def test_on_macos_the_spec_collects_lxml_modules_as_unprocessed_data(monkeypatch):
    # architect-package-dryrun-5.md ruling 1: on macOS PyInstaller thins,
    # re-paths and re-signs every collected binary, so lxml's modules go in
    # as data files at the same paths: copied unchanged, byte check as on Linux.
    binaries = [(d, s, "EXTENSION") for d, s in LXML_TOC + OTHER_TOC]
    got_bin, got_data = _SpecRun(binaries, []).run(monkeypatch, "darwin")
    assert [b for b in got_bin if b[0].startswith("lxml/")] == []
    assert [b[0] for b in got_bin] == [d for d, _ in OTHER_TOC]
    assert [d for d in got_data if d[0].startswith("lxml/")] == [
        (d, s, "DATA") for d, s in LXML_TOC
    ]


def test_on_linux_the_spec_hands_lxml_to_pyinstaller_as_before(monkeypatch):
    binaries = [(d, s, "EXTENSION") for d, s in LXML_TOC + OTHER_TOC]
    got_bin, got_data = _SpecRun(binaries, []).run(monkeypatch, "linux")
    assert got_bin == binaries
    assert [d for d in got_data if d[0].startswith("lxml/")] == []


def test_the_spec_is_tracked_and_not_ignored():
    # .gitignore ignores *.spec (PyInstaller writes one per build); the
    # project's own spec is the exception, so a change to it is never lost.
    spec = "packaging/pyinstaller/inventag.spec"
    tracked = subprocess.run(
        ["git", "ls-files", spec],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tracked.stdout.strip() != ""
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", spec],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 1, f"{spec} matches a rule in .gitignore"


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
def test_build_script_keeps_the_macos_build_record_as_a_file():
    # architect-package-dryrun-5.md ruling 2: the licence check writes the
    # build record (OS links, lowest macOS version) next to components.json.
    text = (SCRIPTS / "build_binary.sh").read_text("utf-8")
    call = text[text.index("third_party_licenses.py") :].split("\n\n")[0]
    assert '--build-record "$work/build-record-macos.txt"' in call
    result = subprocess.run(
        ["bash", "-n", str(SCRIPTS / "build_binary.sh")], timeout=60
    )
    assert result.returncode == 0


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


def test_dockerfile_puts_the_libiconv_notice_next_to_the_lgpl_text():
    # Architect review F3: the image carries the same paragraph as the
    # executable, written by the notices script, not typed by hand.
    text = (PACKAGING / "docker" / "Dockerfile").read_text("utf-8")
    assert re.search(
        r"COPY scripts/packaging/third_party_licenses\.py "
        r"/src/scripts/packaging/third_party_licenses\.py",
        text,
    )
    assert re.search(
        r"/opt/inventag/bin/python /src/scripts/packaging/third_party_licenses\.py "
        r"\\\s*--lxml-notice --out /src/LIBICONV-IN-LXML\.txt",
        text,
    )
    assert re.search(
        r"^COPY --from=build /src/LIBICONV-IN-LXML\.txt "
        r"/usr/share/doc/inventag/LIBICONV-IN-LXML\.txt$",
        text,
        re.M,
    )
    assert re.search(r"/usr/share/doc/inventag/LGPL-2\.1\.txt$", text, re.M)


class _FakeLxml:
    """An installed lxml distribution with three extension modules."""

    version = "6.1.3"

    def __init__(self, root: Path):
        self.root = root
        self.metadata = {"Name": "lxml"}
        lxml = root / "lxml"
        lxml.mkdir()
        for name in ("etree", "objectify"):
            (lxml / f"{name}.cpython-313-x86_64-linux-gnu.so").write_bytes(
                b"\0libiconv_open\0"
            )
        (lxml / "_elementpath.cpython-313-x86_64-linux-gnu.so").write_bytes(b"\0")
        (lxml / "__init__.py").write_text("")
        self.files = sorted(p.relative_to(root) for p in lxml.iterdir())

    def locate_file(self, f):
        return self.root / f


def test_container_notice_has_the_executables_paragraph(tpl, tmp_path, monkeypatch):
    lxml = _FakeLxml(tmp_path)
    monkeypatch.setattr(tpl, "_installed", lambda name: lxml)
    monkeypatch.setattr(tpl, "_source_urls", lambda metadata: [])
    monkeypatch.setattr(tpl, "_iconv_version", lambda path: "1.18")
    text = tpl.libiconv_notice()
    files = "etree.cpython-313-x86_64-linux-gnu.so, objectify.cpython-313-x86_64-linux-gnu.so"
    assert tpl.LXML_PARAGRAPH.format(files=files) in text
    assert "_elementpath" not in text
    assert f"- {tpl.LXML_ICONV} 1.18: LGPL-2.1" in text
    assert tpl.LIBICONV_DOWNLOAD.format(version="1.18") in text
    assert "LGPL-2.1.txt" in text
    assert "Not legal advice" in text
    for word in ("complies", "satisfies", "meets", "compliant"):
        assert word not in text.lower()
    out = tmp_path / "notice.txt"
    assert tpl.main(["--lxml-notice", "--out", str(out)]) == 0
    assert out.read_text("utf-8") == text


def test_container_notice_records_no_version_when_the_modules_disagree(
    tpl, tmp_path, monkeypatch
):
    lxml = _FakeLxml(tmp_path)
    monkeypatch.setattr(tpl, "_installed", lambda name: lxml)
    monkeypatch.setattr(tpl, "_source_urls", lambda metadata: [])
    versions = {"etree": "1.18", "objectify": "1.17"}
    monkeypatch.setattr(
        tpl, "_iconv_version", lambda path: versions[Path(path).name.split(".")[0]]
    )
    text = tpl.libiconv_notice()
    assert f"- {tpl.LXML_ICONV} (version not recorded): LGPL-2.1" in text
    assert "libiconv-1.1" not in text  # no versioned tarball address
    assert "https://www.gnu.org/software/libiconv/" in text


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


LXML_GOLDEN = (
    "lxml's binary wheel, as published on PyPI under the project name lxml, "
    "is carried unmodified. Its extension modules (etree.cpython-312.so, "
    "objectify.cpython-312.so) contain GNU libiconv under the GNU Lesser "
    "General Public License version 2.1, linked statically into those "
    "modules. The lxml modules are separate files in the installation "
    "directory. You can replace them with your own build of lxml of the same "
    "version."
)


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
    assert LXML_GOLDEN in text
    assert (
        "You can replace them with your own build of lxml of the same version." in text
    )
    assert "Not legal advice" in text
    for word in ("complies", "satisfies", "meets", "compliant"):
        assert word not in text.lower()


def test_the_lxml_paragraph_says_only_what_is_proven(tpl):
    # Architect review F1: who built the wheel is not proven, so the paragraph
    # names where it was published, not who built it.
    files = "etree.cpython-312.so, objectify.cpython-312.so"
    assert tpl.LXML_PARAGRAPH.format(files=files) == LXML_GOLDEN
    for words in ("built by", "by that build", "lxml project"):
        assert words not in tpl.LXML_PARAGRAPH


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


# ------------------------------------- libiconv's version (B2b, ruling 2)
ETREE = "_internal/lxml/etree.cpython-312.so"
OBJECTIFY = "_internal/lxml/objectify.cpython-312.so"


class _IconvBuild(_SampleBuild):
    """lxml modules whose ``_libiconv_version`` symbol gives ``versions[rel]``
    ("" = the module has no such symbol)."""

    def __init__(self, versions):
        super().__init__(list(versions), b"libiconv_open", same=True)
        self.versions = versions

    def read_version(self, source, rel, owner):
        if source == "elfsym:_libiconv_version":
            return self.versions[rel]
        return ""


def _collect_iconv(tpl, monkeypatch, versions):
    monkeypatch.setattr(
        tpl, "_cpython", lambda p: tpl.Component("CPython", "3", "PSF-2.0", "runtime")
    )
    monkeypatch.setattr(
        tpl, "_bootloader", lambda p: tpl.Component("b", "6", tpl.BOOTLOADER, "runtime")
    )
    monkeypatch.setattr(tpl, "_installed", lambda name: None)
    comps, problems = tpl.collect(_IconvBuild(versions), _sample_rows(tpl))
    assert problems == []
    return comps


def test_two_lxml_modules_with_different_libiconv_versions_give_one_component(
    tpl, monkeypatch
):
    comps = _collect_iconv(tpl, monkeypatch, {ETREE: "1.18", OBJECTIFY: "1.17"})
    iconv = [c for c in comps if c.name == tpl.LXML_ICONV]
    assert len(iconv) == 1
    assert iconv[0].version == ""
    assert iconv[0].files == [ETREE, OBJECTIFY]
    text = tpl.render(comps)
    assert f"- {tpl.LXML_ICONV} (version not recorded): LGPL-2.1" in text
    assert "libiconv-1.1" not in text  # no versioned tarball address
    assert "https://www.gnu.org/software/libiconv/" in text
    assert "etree.cpython-312.so, objectify.cpython-312.so" in text
    rows = [
        r for r in json.loads(tpl.components_json(comps)) if "libiconv" in r["name"]
    ]
    assert len(rows) == 1 and rows[0]["version"] == "version not recorded"
    assert rows[0]["files"] == [ETREE, OBJECTIFY]


# ------------------------------------------------------------- smoke scan
def _audit(**over):
    report = {
        "read_only_enforced": True,
        "allowed_prefixes": ["Describe", "List", "Get"],
        "total_calls": 3,
        "allowed_calls": 3,
        "blocked_calls": 0,
        "blocked": [],
        "operations": [
            {
                "service": "ec2",
                "operation": "DescribeInstances",
                "allowed": True,
                "count": 1,
            },
            {"service": "s3", "operation": "ListBuckets", "allowed": True, "count": 1},
            {
                "service": "s3",
                "operation": "GetBucketLocation",
                "allowed": True,
                "count": 1,
            },
        ],
    }
    report.update(over)
    return report


def test_smoke_scan_accepts_a_clean_audit():
    assert _load("smoke_scan").check_audit(_audit()) == []


def test_smoke_scan_refuses_blocked_or_write_calls():
    smoke = _load("smoke_scan")
    assert smoke.check_audit(_audit(blocked_calls=1, allowed_calls=2))
    assert smoke.check_audit(_audit(read_only_enforced=False))
    write = _audit()
    write["operations"].append(
        {"service": "ec2", "operation": "RunInstances", "allowed": True, "count": 1}
    )
    assert any("RunInstances" in p for p in smoke.check_audit(write))
    assert smoke.check_audit(_audit(operations=[])) and smoke.check_audit(
        _audit(total_calls=0)
    )


NOT_RECORDED_LINE = (
    "    version not recorded: the lxml modules do not all hold the same "
    "symbol _libiconv_version"
)


@pytest.mark.parametrize(
    "versions",
    [{ETREE: "1.18", OBJECTIFY: ""}, {ETREE: "", OBJECTIFY: ""}],
    ids=["one-module-without-the-symbol", "no-module-with-the-symbol"],
)
def test_a_module_without_the_libiconv_symbol_gives_no_version(
    tpl, monkeypatch, versions
):
    comps = _collect_iconv(tpl, monkeypatch, versions)
    iconv = [c for c in comps if c.name == tpl.LXML_ICONV]
    assert len(iconv) == 1
    assert iconv[0].version == ""
    assert iconv[0].files == [ETREE, OBJECTIFY]
    text = tpl.render(comps)
    assert f"- {tpl.LXML_ICONV} (version not recorded): LGPL-2.1" in text
    assert NOT_RECORDED_LINE + "\n" in text
    assert "libiconv-1.1" not in text
    assert "https://www.gnu.org/software/libiconv/" in text


READ_FROM = "version read from the module's own symbol _libiconv_version"


RESIGN_GOLDEN = (
    "After replacing a module on macOS, sign it again "
    "(`codesign -s - --force <file>`)."
)


@pytest.mark.parametrize(
    "module, resign",
    [
        ("etree.cpython-312-darwin.so", True),
        ("etree.cpython-312-x86_64-linux-gnu.so", False),
    ],
    ids=["macos", "linux"],
)
def test_the_replace_sentence_adds_signing_only_for_macos_modules(
    tpl, monkeypatch, module, resign
):
    # architect-package-dryrun-5.md ruling 1: the macOS notices add one line.
    monkeypatch.setattr(tpl, "_installed", lambda name: None)
    comp = tpl.libiconv_component({f"_internal/lxml/{module}": "1.17"})
    assert comp.notes[0] == tpl.LXML_PARAGRAPH.format(files=module)
    assert comp.notes[1:] == ([RESIGN_GOLDEN] if resign else [])


def test_the_libiconv_lines_say_how_the_version_was_read(tpl, monkeypatch):
    comps = _collect_iconv(tpl, monkeypatch, {ETREE: "1.18", OBJECTIFY: "1.18"})
    text = tpl.render(comps)
    head = f"- {tpl.LXML_ICONV} 1.18: LGPL-2.1\n    {READ_FROM}\n"
    assert head in text
    assert text.count(READ_FROM) == 1  # only the libiconv component says it
    assert tpl.LIBICONV_DOWNLOAD.format(version="1.18") in text
    rows = json.loads(tpl.components_json(comps))
    iconv = [r for r in rows if r["name"] == tpl.LXML_ICONV]
    assert iconv == [
        {
            "files": [ETREE, OBJECTIFY],
            "licence": "LGPL-2.1",
            "name": tpl.LXML_ICONV,
            "section": "c-library",
            "version": "1.18",
            "version_from": READ_FROM,
        }
    ]
    assert all("version_from" not in r for r in rows if r["name"] != tpl.LXML_ICONV)


def test_the_container_notice_says_how_the_version_was_read(tpl, tmp_path, monkeypatch):
    lxml = _FakeLxml(tmp_path)
    monkeypatch.setattr(tpl, "_installed", lambda name: lxml)
    monkeypatch.setattr(tpl, "_source_urls", lambda metadata: [])
    monkeypatch.setattr(tpl, "_iconv_version", lambda path: "1.18")
    text = tpl.libiconv_notice()
    assert f"- {tpl.LXML_ICONV} 1.18: LGPL-2.1\n    {READ_FROM}\n" in text
    monkeypatch.setattr(tpl, "_iconv_version", lambda path: "")
    text = tpl.libiconv_notice()
    assert f"(version not recorded): LGPL-2.1\n{NOT_RECORDED_LINE}\n" in text


# ------------------------------------------- Python 3.12 only (B2c, ruling 4 (b))
PY313_GOLDEN = (
    "CPython 3.13.18: the executable is built with Python 3.12 only; create the "
    "build environment with python3.12 (build_binary.sh venv <dir> python3.12) "
    "and build again"
)


def test_a_build_with_python_other_than_3_12_is_refused(tpl):
    assert tpl.python_version_problems((3, 13, 18)) == [PY313_GOLDEN]
    assert tpl.python_version_problems((3, 11, 9))[0].startswith("CPython 3.11.9: ")
    assert tpl.python_version_problems((3, 12, 3)) == []


def test_the_check_of_the_build_python_reaches_the_problems(tpl):
    problems = []
    comp = tpl._cpython(problems, version_info=(3, 13, 18))
    assert PY313_GOLDEN in problems
    assert comp.version == "3.13.18"
    problems = []
    tpl._cpython(problems, version_info=(3, 12, 3))
    assert not [p for p in problems if "3.12 only" in p]


# ------------------------------------ files without a row (B2c, ruling 4 (a))
MACHO_64 = b"\xcf\xfa\xed\xfe"  # Mach-O 64-bit, little-endian
FRAMEWORK = "/Library/Frameworks/Python.framework/Versions/3.12"


def _fake_bundle(tmp_path):
    """A macOS-like bundle and PyInstaller's tables, without PyInstaller."""
    bundle, work = tmp_path / "dist" / "inventag", tmp_path / "build"
    (bundle / "_internal").mkdir(parents=True)
    work.mkdir()
    (bundle / "inventag").write_bytes(MACHO_64 + b"\0" * 12)
    (bundle / "_internal" / "Python").write_bytes(MACHO_64 + b"\0" * 12)
    (bundle / "_internal" / "libssl.3.dylib").write_bytes(MACHO_64 + b"\0" * 12)
    (bundle / "_internal" / "base_library.zip").write_bytes(b"PK\3\4")
    (bundle / "_internal" / "notes.txt").write_text("text\n", encoding="utf-8")
    toc = [
        ("Python", f"{FRAMEWORK}/Python", "BINARY"),
        ("libssl.3.dylib", f"{FRAMEWORK}/lib/libssl.3.dylib", "BINARY"),
    ]
    (work / "PYZ-00.toc").write_text("[]", encoding="utf-8")
    (work / "COLLECT-00.toc").write_text(repr(toc), encoding="utf-8")
    return bundle, work


def test_binaries_are_found_by_their_header_not_only_their_name(tpl, tmp_path):
    # A macOS bundle carries CPython as "_internal/Python": no .so, no .dylib.
    bundle, work = _fake_bundle(tmp_path)
    (bundle / "_internal" / "tool").write_bytes(b"\x7fELF" + b"\0" * 12)
    build = tpl.Build(bundle, work, ROOT)
    assert build.binaries() == [
        "_internal/Python",
        "_internal/libssl.3.dylib",
        "_internal/tool",
        "inventag",
    ]


class _OwnedBuild(_SampleBuild):
    """Sample bundle whose files have a source, a Python package and a
    system package."""

    class _Dist:
        def __init__(self, name, version):
            self.metadata, self.version = {"Name": name}, version

    def __init__(self, files, sources, dists, owners):
        super().__init__(files, b"", same=True)
        self.sources, self.dists, self.owners = sources, dists, owners

    def source_of(self, rel):
        return self.sources.get(rel)

    def distribution_of_bundled(self, rel):
        d = self.dists.get(rel)
        return self._Dist(*d) if d else None

    def owning_package(self, path):
        return self.owners.get(path)

    def package_licence(self, pkg):
        return None

    def linked_libraries(self, rel):
        return []


UNMAPPED_GOLDEN = [
    "unmapped files: 3 (platform linux, Python 3.12.3)",
    "UNMAPPED _internal/libuuid.so.1 | source: /usr/lib/x86_64-linux-gnu/"
    "libuuid.so.1 | python package: none | system package: libuuid1 2.39",
    "UNMAPPED _internal/mystery/_m.so | source: /venv/mystery/_m.so | python "
    "package: mystery 1.0 | system package: none found",
    "UNMAPPED _internal/zz.so | source: not in PyInstaller's tables | python "
    "package: none | system package: none found",
]


def test_list_unmapped_names_each_file_its_source_and_owners(tpl):
    uuid = "/usr/lib/x86_64-linux-gnu/libuuid.so.1"
    build = _OwnedBuild(
        [
            "inventag",
            "_internal/zz.so",
            "_internal/mystery/_m.so",
            "_internal/lxml/etree.so",
            "_internal/libuuid.so.1",
        ],
        {
            "_internal/libuuid.so.1": uuid,
            "_internal/mystery/_m.so": "/venv/mystery/_m.so",
        },
        {"_internal/mystery/_m.so": ("mystery", "1.0")},
        {uuid: ("libuuid1", "2.39")},
    )
    entries = tpl.unmapped_files(build, _sample_rows(tpl))
    text = tpl.unmapped_report(entries, "linux", "3.12.3")
    assert text.splitlines() == UNMAPPED_GOLDEN
    assert tpl.unmapped_report([], "linux", "3.12.3") == (
        "unmapped files: 0 (platform linux, Python 3.12.3)\n"
    )


def _expected_fake_listing(tpl):
    # A platform with no table (darwin has one since B2d): every binary.
    return [
        f"unmapped files: 3 (platform freebsd, Python {tpl.platform.python_version()})",
        f"UNMAPPED _internal/Python | source: {FRAMEWORK}/Python | python package: "
        "none | system package: none found",
        f"UNMAPPED _internal/libssl.3.dylib | source: {FRAMEWORK}/lib/libssl.3.dylib"
        " | python package: none | system package: none found",
        "UNMAPPED inventag | source: not in PyInstaller's tables | python package: "
        "none | system package: none found",
    ]


def test_list_unmapped_mode_works_on_a_platform_without_a_table(tpl, tmp_path, capsys):
    bundle, work = _fake_bundle(tmp_path)
    args = ["--bundle", str(bundle), "--workpath", str(work), "--list-unmapped"]
    code = tpl.main(args + ["--platform", "freebsd"])
    out = capsys.readouterr().out
    assert code == 1
    assert out.splitlines() == _expected_fake_listing(tpl)
    assert not (bundle / "THIRD-PARTY-LICENSES.txt").exists()  # lists only


def test_the_licence_check_prints_the_unmapped_list_first(tpl, tmp_path, capsys):
    # The first dry run on a new system (macOS, AlmaLinux) prints every file
    # that needs a row in one run (architect ruling 4 (a)): the check, which
    # build_binary.sh runs right after PyInstaller, starts with the list.
    bundle, work = _fake_bundle(tmp_path)
    out_file = tmp_path / "THIRD-PARTY-LICENSES.txt"
    args = ["--bundle", str(bundle), "--workpath", str(work), "--out", str(out_file)]
    code = tpl.main(args + ["--platform", "freebsd"])
    captured = capsys.readouterr()
    expected = _expected_fake_listing(tpl)
    assert code == 1
    assert captured.out.splitlines()[: len(expected)] == expected
    assert captured.out.splitlines()[-1] == "licence check: FAIL"
    assert "LICENCE CHECK: no licence table for freebsd" in captured.err
    assert "LICENCE CHECK: _internal/Python: no row in the licence table" in (
        captured.err
    )
    assert out_file.is_file()


def test_the_unmapped_list_comes_first_in_a_build_log(tpl, tmp_path):
    # A CI log merges stdout and stderr through a pipe: the list must be
    # written out before the first LICENCE CHECK line.
    bundle, work = _fake_bundle(tmp_path)
    args = ["--bundle", str(bundle), "--workpath", str(work)]
    args += ["--out", str(tmp_path / "T.txt"), "--platform", "freebsd"]
    run = subprocess.run(
        [sys.executable, str(SCRIPTS / "third_party_licenses.py"), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    lines = run.stdout.splitlines()
    assert run.returncode == 1
    assert lines[:4] == _expected_fake_listing(tpl)


# ------------------- licence-text sources (B2d, architect dry-run ruling 4)
NO_SOURCE_GOLDEN = (
    "_internal/yaml/_yaml.so: licence text of libyaml (in PyYAML): no verified "
    "source in the table; store the upstream text unchanged under "
    "scripts/packaging/licenses/ and its address, tag, sha256 and date in "
    "SOURCES.json"
)


def _no_runtime(tpl, monkeypatch):
    monkeypatch.setattr(
        tpl, "_cpython", lambda p: tpl.Component("CPython", "3", "PSF-2.0", "runtime")
    )
    monkeypatch.setattr(
        tpl, "_bootloader", lambda p: tpl.Component("b", "6", tpl.BOOTLOADER, "runtime")
    )
    monkeypatch.setattr(tpl, "_installed", lambda name: None)


def test_no_text_of_a_wheel_library_comes_from_the_build_systems_packages(tpl):
    # A library inside a wheel: the text comes from the wheel's own licence
    # files or from a sourced copy in the repository, never from the build
    # system's package folder (that describes the system's library).
    for plat, rows in tpl.TABLES.items():
        for row in rows:
            if row.origin != "package":
                continue
            for carried in row.carries:
                for source in carried.text:
                    assert source.startswith(("dist:", "repo:")), (
                        plat,
                        row.pattern,
                        carried.name,
                        source,
                    )


def test_a_carried_library_without_a_verified_text_source_fails(tpl, monkeypatch):
    _no_runtime(tpl, monkeypatch)
    rows = (
        tpl.Row(
            "_internal/yaml/_yaml*.so",
            "package",
            carries=(tpl.Carried("libyaml (in PyYAML)", "MIT", ()),),
        ),
    )
    build = _SampleBuild(["_internal/yaml/_yaml.so"], b"", same=True)
    _, problems = tpl.collect(build, rows)
    assert problems == [NO_SOURCE_GOLDEN]


# ------------------- libmpdec: inside _decimal or a separate library (B2d)
DECIMAL = "_internal/python3.12/lib-dynload/_decimal.cpython-312-x86_64-linux-gnu.so"
MPDEC_IN_DECIMAL = "libmpdec (in CPython's _decimal)"


@pytest.mark.parametrize(
    "strings, carried",
    [(b"mpd_qadd", True), (b"libmpdec.so.3\0mpd_qadd", False)],
    ids=["linked-in", "linked-to-libmpdec.so"],
)
def test_decimal_carries_libmpdec_only_when_it_does_not_load_the_library(
    tpl, monkeypatch, strings, carried
):
    # AlmaLinux 9 (dry run 3): _decimal loads the system's libmpdec.so.3,
    # which is a file of its own in the bundle, so _decimal carries no copy.
    _no_runtime(tpl, monkeypatch)
    build = _SampleBuild([DECIMAL], strings, same=True)
    comps, _ = tpl.collect(build, tpl.LINUX_ROWS)
    assert (MPDEC_IN_DECIMAL in [c.name for c in comps]) is carried


# ------------------------- the darwin table (B2d, macOS arm64, dry run 3)
# Every binary of the macOS arm64 bundle in dry run 3 (pull request #51, at
# 757a837), as its `--list-unmapped` list printed it, with the owner it named.
DARWIN_WHEEL_FILES = {
    "_internal/_cffi_backend.cpython-312-darwin.so": "cffi",
    "_internal/charset_normalizer/cd.cpython-312-darwin.so": "charset-normalizer",
    "_internal/charset_normalizer/md.cpython-312-darwin.so": "charset-normalizer",
    "_internal/cryptography/hazmat/bindings/_rust.abi3.so": "cryptography",
    "_internal/lxml/_elementpath.cpython-312-darwin.so": "lxml",
    "_internal/lxml/builder.cpython-312-darwin.so": "lxml",
    "_internal/lxml/etree.cpython-312-darwin.so": "lxml",
    "_internal/lxml/html/_difflib.cpython-312-darwin.so": "lxml",
    "_internal/lxml/html/diff.cpython-312-darwin.so": "lxml",
    "_internal/lxml/objectify.cpython-312-darwin.so": "lxml",
    "_internal/lxml/sax.cpython-312-darwin.so": "lxml",
    "_internal/psutil/_psutil_osx.abi3.so": "psutil",
    "_internal/rpds/rpds.cpython-312-darwin.so": "rpds-py",
    "_internal/yaml/_yaml.cpython-312-darwin.so": "PyYAML",
}
# Files of the build's Python.framework (python.org build from setup-python):
# no verified licence source yet, so no row (gaps in the B2d report).
DARWIN_DYNLOAD = (
    "_asyncio _bisect _blake2 _bz2 _codecs_cn _codecs_hk _codecs_iso2022 "
    "_codecs_jp _codecs_kr _codecs_tw _contextvars _csv _ctypes _datetime "
    "_decimal _elementtree _hashlib _heapq _json _lzma _md5 _multibytecodec "
    "_multiprocessing _opcode _pickle _posixshmem _posixsubprocess _queue "
    "_random _scproxy _sha1 _sha2 _sha3 _socket _ssl _statistics _struct _uuid "
    "array binascii fcntl grp math mmap pyexpat resource select termios "
    "unicodedata zlib"
).split()
DARWIN_FRAMEWORK_FILES = [
    "_internal/Python",
    "_internal/Python.framework/Python",
    "_internal/Python.framework/Versions/3.12/Python",
    "_internal/libcrypto.3.dylib",
    "_internal/libssl.3.dylib",
] + [
    f"_internal/python3.12/lib-dynload/{m}.cpython-312-darwin.so"
    for m in DARWIN_DYNLOAD
]


def test_the_darwin_table_maps_the_wheel_files_of_dry_run_3(tpl):
    rows = tpl.TABLES["darwin"]
    assert len(DARWIN_WHEEL_FILES) + len(DARWIN_FRAMEWORK_FILES) + 1 == 70
    assert tpl.match_row("inventag", rows).origin == "pyinstaller"
    for rel in DARWIN_WHEEL_FILES:
        row = tpl.match_row(rel, rows)
        assert row is not None and row.origin == "package", rel
    # The same carried libraries as on Linux, found by the same strings.
    lxml = tpl.match_row("_internal/lxml/etree.cpython-312-darwin.so", rows)
    assert lxml.carries == tpl._LXML and lxml.unmodified
    rust = tpl.match_row("_internal/cryptography/hazmat/bindings/_rust.abi3.so", rows)
    assert [c.name for c in rust.carries] == ["OpenSSL (in cryptography)"]
    for rel, name in (
        ("_internal/yaml/_yaml.cpython-312-darwin.so", "libyaml (in PyYAML)"),
        ("_internal/_cffi_backend.cpython-312-darwin.so", "libffi (in cffi)"),
    ):
        assert [c.name for c in tpl.match_row(rel, rows).carries] == [name]


# ------------- evidence for the next rows in the unmapped list (B2d)
class _EvidenceBuild(_OwnedBuild):
    def __init__(self, files, sources, owners, licences, linked):
        super().__init__(files, sources, {}, owners)
        self.licences, self.linked = licences, linked

    def package_licence(self, pkg):
        return self.licences.get(pkg)

    def linked_libraries(self, rel):
        return self.linked.get(rel, [])


EVIDENCE_GOLDEN = [
    "unmapped files: 2 (platform linux, Python 3.12.16)",
    "UNMAPPED _internal/Python | source: /fw/Python | python package: none | "
    "system package: none found",
    "    linked: /usr/lib/libSystem.B.dylib, @rpath/libssl.3.dylib",
    "UNMAPPED _internal/libmpdec.so.3 | source: /lib64/libmpdec.so.3 | python "
    "package: none | system package: mpdecimal 2.5.1-3.el9",
    "    licence of mpdecimal: SAMPLE-LICENCE | licence files: "
    "/usr/share/licenses/mpdecimal/A.txt, /usr/share/licenses/mpdecimal/B.txt",
]


def test_the_unmapped_list_prints_the_evidence_a_row_needs(tpl):
    # The system package's own licence field and licence files (rpm), and
    # what a file links (macOS): what a row is written from in the next round.
    mpdec = "/lib64/libmpdec.so.3"
    build = _EvidenceBuild(
        ["_internal/libmpdec.so.3", "_internal/Python"],
        {"_internal/libmpdec.so.3": mpdec, "_internal/Python": "/fw/Python"},
        {mpdec: ("mpdecimal", "2.5.1-3.el9")},
        {
            "mpdecimal": (
                "SAMPLE-LICENCE",
                [
                    "/usr/share/licenses/mpdecimal/B.txt",
                    "/usr/share/licenses/mpdecimal/A.txt",
                ],
            )
        },
        {"_internal/Python": ["/usr/lib/libSystem.B.dylib", "@rpath/libssl.3.dylib"]},
    )
    entries = tpl.unmapped_files(build, ())
    text = tpl.unmapped_report(entries, "linux", "3.12.16")
    assert text.splitlines() == EVIDENCE_GOLDEN


def test_rpm_licence_files_are_the_paths_rpm_prints(tpl):
    assert tpl.licence_file_lines(
        "/usr/share/licenses/x/LICENSE\n/usr/share/licenses/x/COPYING\n"
    ) == ["/usr/share/licenses/x/COPYING", "/usr/share/licenses/x/LICENSE"]
    assert tpl.licence_file_lines("(contains no files)\n") == []


def test_otool_output_gives_the_linked_libraries(tpl):
    out = (
        "/b/_ssl.so (architecture x86_64):\n"
        "\t@rpath/libssl.3.dylib (compatibility version 3.0.0, current version 3.0.0)\n"
        "\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current "
        "version 1351.0.0)\n"
        "/b/_ssl.so (architecture arm64):\n"
        "\t@rpath/libssl.3.dylib (compatibility version 3.0.0, current version 3.0.0)\n"
    )
    assert tpl.otool_libraries(out) == [
        "/usr/lib/libSystem.B.dylib",
        "@rpath/libssl.3.dylib",
    ]


# --------------- sourced licence texts (B2e, architect dry-run-3 ruling 1)
LICENSES = SCRIPTS / "licenses"
UPSTREAM_KEYS = {
    "component",
    "repository",
    "tag",
    "commit",
    "address",
    "http_status",
    "sha256",
    "bytes",
    "fetched",
}


def _sources():
    return json.loads((LICENSES / "SOURCES.json").read_text("utf-8"))


def test_every_licence_text_has_a_source_entry_with_its_sha256():
    import hashlib

    entries = _sources()["files"]
    on_disk = sorted(p.name for p in LICENSES.iterdir() if p.name != "SOURCES.json")
    assert sorted(entries) == on_disk
    for name, entry in entries.items():
        data = (LICENSES / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], name
        assert len(data) == entry["bytes"], name


def test_upstream_texts_come_from_the_projects_repository_at_a_release_tag():
    # Ruling 1, condition 2: the project's own repository, at a release tag;
    # not a mirror, a package site or the default branch.
    upstream = {n: e for n, e in _sources()["files"].items() if "repository" in e}
    assert set(upstream) >= {"libyaml-License", "libffi-LICENSE"}
    for name, entry in upstream.items():
        assert UPSTREAM_KEYS <= set(entry), name
        repo = entry["repository"]
        assert repo.startswith("https://github.com/"), name
        slug = repo.removeprefix("https://github.com/")
        assert entry["address"].startswith(
            f"https://raw.githubusercontent.com/{slug}/refs/tags/{entry['tag']}/"
        ), name
        assert entry["http_status"] == 200, name
        assert re.fullmatch(r"[0-9a-f]{40}", entry["commit"]), name
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", entry["fetched"]), name
    # The wheel names libyaml's version (the module holds "0.2.5"): that tag.
    assert upstream["libyaml-License"]["tag"] == "0.2.5"


YAML_TEXT = "repo:scripts/packaging/licenses/libyaml-License"
FFI_TEXT = "repo:scripts/packaging/licenses/libffi-LICENSE"


@pytest.mark.parametrize(
    "plat, suffix", [("linux", "x86_64-linux-gnu"), ("darwin", "darwin")]
)
def test_libyaml_and_libffi_texts_are_the_sourced_upstream_files(tpl, plat, suffix):
    rows = tpl.TABLES[plat]
    for rel, name, text in (
        (
            f"_internal/yaml/_yaml.cpython-312-{suffix}.so",
            "libyaml (in PyYAML)",
            YAML_TEXT,
        ),
        (
            f"_internal/_cffi_backend.cpython-312-{suffix}.so",
            "libffi (in cffi)",
            FFI_TEXT,
        ),
    ):
        (carried,) = [c for c in tpl.match_row(rel, rows).carries if c.name == name]
        assert carried.text == (text,), (plat, name)
    (ffi,) = tpl.match_row(
        f"_internal/_cffi_backend.cpython-312-{suffix}.so", rows
    ).carries
    assert ffi.version == ""  # the wheel does not say which libffi: not recorded


def test_every_repository_text_of_the_tables_has_a_source_entry(tpl):
    entries = _sources()["files"]
    used = set()
    for rows in tpl.TABLES.values():
        for row in rows:
            sources = list(row.extra_text) + [s for c in row.carries for s in c.text]
            used |= {s for s in sources if s.startswith("repo:")}
    assert used
    for source in sorted(used):
        path = ROOT / source.removeprefix("repo:")
        assert path.is_file(), source
        assert path.parent == LICENSES and path.name in entries, source


def test_a_sourced_text_is_labelled_with_its_upstream_address(tpl, tmp_path):
    bundle, work = _fake_bundle(tmp_path)
    build = tpl.Build(bundle, work, ROOT)
    label, text = build.read_text(YAML_TEXT, None)
    address = _sources()["files"]["libyaml-License"]["address"]
    assert label == f"libyaml-License (from {address})"
    assert text == (LICENSES / "libyaml-License").read_text("utf-8")
    # A text without an upstream record keeps its file name as the label.
    label, _ = build.read_text("repo:scripts/packaging/licenses/GPL-3.txt", None)
    assert label == "GPL-3.txt"


# ------------- rpm rows: libmpdec.so.3 and libuuid.so.1 (B2e, ruling 2)
BSD_HEAD = (
    "Redistribution and use in source and binary forms, with or without\n"
    "modification, are permitted provided that the following conditions\n"
    "are met:\n"
    "1. Redistributions of source code must retain the above copyright\n"
    "   notice, this list of conditions and the following disclaimer.\n"
    "2. Redistributions in binary form must reproduce the above copyright\n"
    "   notice, this list of conditions and the following disclaimer in the\n"
    "   documentation and/or other materials provided with the distribution.\n"
)
BSD_THIRD = (
    "3. Neither the name of the copyright holder nor the names of its\n"
    "   contributors may be used to endorse or promote products derived from\n"
    "   this software without specific prior written permission.\n"
)
MPDEC_FILE = "/usr/share/licenses/mpdecimal/LICENSE.txt"
UUID_FILES = [
    "/usr/share/licenses/libuuid/COPYING",
    "/usr/share/licenses/libuuid/COPYING.BSD-3-Clause",
]
RPM_TEXTS = {
    MPDEC_FILE: "Copyright (c) 2008-2020 Sample\n\n" + BSD_HEAD,
    UUID_FILES[0]: "This library is free software; see COPYING.BSD-3-Clause.\n",
    UUID_FILES[1]: "Copyright (c) Sample\n\n" + BSD_HEAD + BSD_THIRD,
}


class _RpmBuild(_SampleBuild):
    """Two system libraries of AlmaLinux 9 packages, as dry run 4 printed them."""

    def __init__(self, licences, texts, versions=None):
        files = ["_internal/libmpdec.so.3", "_internal/libuuid.so.1"]
        super().__init__(files, b"", same=True)
        self.licences, self.texts = licences, texts
        self.versions = versions or {
            "mpdecimal": "2.5.1-3.el9",
            "libuuid": "2.37.4-28.el9_9.1",
        }

    def source_of(self, rel):
        return "/lib64/" + Path(rel).name

    def owning_package(self, path):
        pkg = {"libmpdec.so.3": "mpdecimal", "libuuid.so.1": "libuuid"}[Path(path).name]
        return pkg, self.versions[pkg]

    def package_licence(self, pkg):
        return self.licences.get(pkg)

    def read_text(self, source, owner):
        kind, _, arg = source.partition(":")
        if kind == "path":
            return (Path(arg).name, self.texts[arg]) if arg in self.texts else None
        return super().read_text(source, owner)


RPM_LICENCES = {
    "mpdecimal": ("BSD", [MPDEC_FILE]),
    "libuuid": ("BSD", UUID_FILES),
}


def _rpm_collect(tpl, monkeypatch, licences=None, texts=None, versions=None):
    _no_runtime(tpl, monkeypatch)
    build = _RpmBuild(
        RPM_LICENCES if licences is None else licences,
        RPM_TEXTS if texts is None else texts,
        versions,
    )
    comps, problems = tpl.collect(build, tpl.LINUX_ROWS)
    return {c.name: c for c in comps}, problems


def test_rpm_rows_read_version_and_licence_id_from_the_package(tpl, monkeypatch):
    comps, problems = _rpm_collect(tpl, monkeypatch)
    assert problems == []
    mpdec, uuid = comps["libmpdec.so.3"], comps["libuuid.so.1"]
    assert (mpdec.version, mpdec.spdx, mpdec.section) == (
        "2.5.1-3.el9",
        "BSD-2-Clause",
        "c-library",
    )
    assert (uuid.version, uuid.spdx) == ("2.37.4-28.el9_9.1", "BSD-3-Clause")
    assert [label for label, _ in mpdec.texts] == ["mpdecimal: LICENSE.txt"]
    assert [label for label, _ in uuid.texts] == [
        "libuuid: COPYING",
        "libuuid: COPYING.BSD-3-Clause",
    ]
    assert uuid.texts[1][1] == RPM_TEXTS[UUID_FILES[1]]
    assert mpdec.notes == [
        "From the system package mpdecimal 2.5.1-3.el9 (rpm licence field: BSD); "
        "licence id read from " + MPDEC_FILE
    ]
    assert mpdec.files == ["_internal/libmpdec.so.3"]


def test_rpm_versions_and_ids_are_read_never_typed(tpl, monkeypatch):
    texts = dict(RPM_TEXTS)
    texts[MPDEC_FILE] = BSD_HEAD + BSD_THIRD
    comps, problems = _rpm_collect(
        tpl,
        monkeypatch,
        texts=texts,
        versions={"mpdecimal": "9.9-1.el9", "libuuid": "8.8-1.el9"},
    )
    assert problems == []
    assert comps["libmpdec.so.3"].spdx == "BSD-3-Clause"
    assert comps["libmpdec.so.3"].version == "9.9-1.el9"
    assert comps["libuuid.so.1"].version == "8.8-1.el9"


ARCHITECT = "goes to the architect (ruling 2), not into a row"


@pytest.mark.parametrize(
    "licences, texts, expected",
    [
        (
            {**RPM_LICENCES, "mpdecimal": ("LGPLv2+", [MPDEC_FILE])},
            RPM_TEXTS,
            f"_internal/libmpdec.so.3: licence field of mpdecimal is LGPLv2+: GPL or "
            f"LGPL {ARCHITECT}",
        ),
        (
            RPM_LICENCES,
            {**RPM_TEXTS, UUID_FILES[0]: "GNU Lesser General Public License 2.1\n"},
            f"_internal/libuuid.so.1: licence file {UUID_FILES[0]} of libuuid names "
            f"the GPL or LGPL: {ARCHITECT}",
        ),
        (
            {**RPM_LICENCES, "mpdecimal": ("BSD", [])},
            RPM_TEXTS,
            "_internal/libmpdec.so.3: mpdecimal lists no licence file "
            "(rpm -q --licensefiles)",
        ),
        (
            RPM_LICENCES,
            {k: v for k, v in RPM_TEXTS.items() if k != MPDEC_FILE},
            f"_internal/libmpdec.so.3: licence file {MPDEC_FILE} of mpdecimal not "
            "found",
        ),
        (
            RPM_LICENCES,
            {**RPM_TEXTS, MPDEC_FILE: "Some other licence.\n"},
            "_internal/libmpdec.so.3: the licence files of mpdecimal are not a BSD "
            "text this row accepts (BSD-2-Clause, BSD-3-Clause)",
        ),
        (
            {**RPM_LICENCES, "mpdecimal": ("MIT", [MPDEC_FILE])},
            RPM_TEXTS,
            "_internal/libmpdec.so.3: licence field of mpdecimal is MIT; its "
            "licence files say BSD-2-Clause",
        ),
        (
            {"libuuid": RPM_LICENCES["libuuid"]},
            RPM_TEXTS,
            "_internal/libmpdec.so.3: licence field and files of mpdecimal not "
            "readable (rpm)",
        ),
    ],
    ids=[
        "lgpl-field",
        "lgpl-in-a-file",
        "no-licence-file",
        "file-missing",
        "not-bsd",
        "field-and-file-disagree",
        "no-rpm",
    ],
)
def test_rpm_rows_fail_without_their_evidence(
    tpl, monkeypatch, licences, texts, expected
):
    _, problems = _rpm_collect(tpl, monkeypatch, licences, texts)
    assert expected in problems


# ---------------- macOS: the Python framework's files (B2e, ruling 3)
DYNLOAD = "_internal/python3.12/lib-dynload/"
LIBSYSTEM = "/usr/lib/libSystem.B.dylib"


def test_the_darwin_table_maps_every_file_of_dry_run_4(tpl):
    # Dry run 4 (macOS arm64, Python 3.12.10) listed the same 55 framework
    # files as dry run 3; each now has a row, decided per file at build time.
    rows = tpl.TABLES["darwin"]
    for rel in DARWIN_FRAMEWORK_FILES:
        row = tpl.match_row(rel, rows)
        assert row is not None, rel
        assert row.in_build_python and row.links, rel
    for rel in DARWIN_FRAMEWORK_FILES[:3]:
        assert tpl.match_row(rel, rows).origin == "cpython"
    for rel in ("_internal/libssl.3.dylib", "_internal/libcrypto.3.dylib"):
        row = tpl.match_row(rel, rows)
        assert row.origin == "framework"
        (openssl,) = row.carries
        assert openssl.name == "OpenSSL (in the Python.framework)"
        assert openssl.spdx == "Apache-2.0"
        assert openssl.text == ("repo:scripts/packaging/licenses/openssl-LICENSE.txt",)
        assert openssl.version.startswith("python:ssl.OPENSSL_VERSION")
    for m in DARWIN_DYNLOAD:
        row = tpl.match_row(f"{DYNLOAD}{m}.cpython-312-darwin.so", rows)
        assert row.origin == "cpython" and row.exports == ("_PyInit_{module}",), m
    # Linux keeps its rows: no link or symbol check there.
    assert all(not r.links and not r.exports for r in tpl.TABLES["linux"])


# A thin 64-bit Mach-O with LC_SYMTAB, built by hand: (name, n_type, n_sect).
def _macho(symbols):
    import struct

    strtab = b"\0"
    nlist = b""
    for name, n_type, n_sect in symbols:
        nlist += struct.pack("<IBBHQ", len(strtab), n_type, n_sect, 0, 0)
        strtab += name.encode() + b"\0"
    header_size, cmd_size = 32, 24
    symoff = header_size + cmd_size
    stroff = symoff + len(nlist)
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 0, 8, 1, cmd_size, 0, 0)
    symtab = struct.pack(
        "<IIIIII", 0x2, cmd_size, symoff, len(symbols), stroff, len(strtab)
    )
    return header + symtab + nlist + strtab


def _fat(*slices):
    import struct

    offset = 4096
    head = struct.pack(">II", 0xCAFEBABE, len(slices))
    body = b""
    for i, data in enumerate(slices):
        head += struct.pack(
            ">iiIII", 0x0100000C + i, 0, offset + len(body), len(data), 12
        )
        body += data
    return head + b"\0" * (offset - len(head)) + body


SAMPLE_SYMBOLS = [
    ("_PyInit__json", 0x0F, 1),  # N_SECT | N_EXT: defined, exported
    ("_scanner_helper", 0x0E, 1),  # N_SECT, not external: local
    ("_hidden_helper", 0x1F, 1),  # N_PEXT: private external
    ("_malloc", 0x01, 0),  # N_UNDF | N_EXT: undefined
    ("debug_stab", 0x24, 1),  # a debugging entry (N_STAB bits)
]


def test_macho_defined_symbols_are_the_exported_definitions(tpl):
    assert tpl.macho_defined_symbols(_macho(SAMPLE_SYMBOLS)) == ["_PyInit__json"]
    fat = _fat(_macho(SAMPLE_SYMBOLS), _macho([("_Hacl_x", 0x0F, 1)]))
    assert tpl.macho_defined_symbols(fat) == ["_Hacl_x", "_PyInit__json"]
    assert tpl.macho_defined_symbols(b"\x7fELF" + b"\0" * 60) is None
    assert tpl.macho_defined_symbols(b"\xcf\xfa\xed\xfe" + b"\0" * 4) is None


class _DarwinBuild(_SampleBuild):
    """Framework files of a macOS bundle: what otool -L and the symbol table
    of each say, without a Mac."""

    def __init__(self, files):
        super().__init__(list(files), b"", same=True)
        self.info = files

    def source_of(self, rel):
        default = FRAMEWORK + "/" + rel.split("_internal/", 1)[1]
        return self.info[rel].get("source", default)

    def python_prefix(self):
        return FRAMEWORK

    def distribution_of_bundled(self, rel):
        return None

    def contains(self, rel, needle):
        return needle in self.info[rel].get("strings", b"")

    def linked_libraries(self, rel):
        return self.info[rel].get("links", [LIBSYSTEM])

    def defined_symbols(self, rel):
        name = Path(rel).name.split(".")[0]
        return self.info[rel].get("symbols", [f"_PyInit_{name}"])

    def min_os(self, rel, arch):
        return self.info[rel].get("minos")


def _dyn(m):
    return f"{DYNLOAD}{m}.cpython-312-darwin.so"


def _darwin_collect(tpl, monkeypatch, files):
    _no_runtime(tpl, monkeypatch)
    comps, problems = tpl.collect(_DarwinBuild(files), tpl.TABLES["darwin"])
    return {c.name: c for c in comps}, problems


SSL_LINKS = [LIBSYSTEM, "@rpath/libcrypto.3.dylib", "@rpath/libssl.3.dylib"]


def test_cpython_files_that_carry_and_link_nothing_else_pass(tpl, monkeypatch):
    comps, problems = _darwin_collect(
        tpl,
        monkeypatch,
        {
            "_internal/Python": {
                "links": [
                    "/System/Library/Frameworks/CoreFoundation.framework/Versions/A/"
                    "CoreFoundation",
                    LIBSYSTEM,
                    "@rpath/Python",
                ]
            },
            _dyn("_json"): {},
            _dyn("_ssl"): {"links": SSL_LINKS},
            "_internal/libssl.3.dylib": {"links": SSL_LINKS},
            "_internal/libcrypto.3.dylib": {
                "links": [LIBSYSTEM, "@rpath/libcrypto.3.dylib"]
            },
        },
    )
    assert problems == []
    openssl = comps["OpenSSL (in the Python.framework)"]
    assert (openssl.version, openssl.spdx) == ("9.9", "Apache-2.0")
    assert openssl.files == ["_internal/libssl.3.dylib", "_internal/libcrypto.3.dylib"]
    assert set(comps) == {"CPython", "b", "OpenSSL (in the Python.framework)"}


THIRD_PARTY = "a third-party library inside needs its own row (architect ruling 3.2)"


@pytest.mark.parametrize(
    "files, expected",
    [
        (
            {
                _dyn("_sha2"): {
                    "symbols": ["_Hacl_Hash_SHA2_digest_256", "_PyInit__sha2"]
                }
            },
            f"{_dyn('_sha2')}: defines symbols outside CPython's module init "
            f"(_Hacl_Hash_SHA2_digest_256): {THIRD_PARTY}",
        ),
        (
            {_dyn("zlib"): {"links": [LIBSYSTEM, "/opt/homebrew/lib/libz.1.dylib"]}},
            f"{_dyn('zlib')}: links /opt/homebrew/lib/libz.1.dylib, an absolute "
            "path outside the bundle and outside /usr/lib/ and /System/Library/: "
            "a user's Mac need not have it (architect-package-dryrun-5.md ruling 2)",
        ),
        (
            {_dyn("_ssl"): {"links": SSL_LINKS}},
            f"{_dyn('_ssl')}: links @rpath/libcrypto.3.dylib, which does not "
            "resolve to a bundled file with a row (architect-package-dryrun-5.md "
            "ruling 2)",
        ),
        (
            {_dyn("_json"): {"symbols": None}},
            f"{_dyn('_json')}: defined symbols not readable (Mach-O symbol table); "
            "the row needs them (architect ruling 3.1)",
        ),
        (
            {_dyn("_json"): {"links": []}},
            f"{_dyn('_json')}: linked libraries not readable (otool -L); the row "
            "needs them (architect ruling 3.1)",
        ),
        (
            {_dyn("_json"): {"source": "/opt/homebrew/lib/_json.so"}},
            f"{_dyn('_json')}: comes from /opt/homebrew/lib/_json.so, not from the "
            f"build Python at {FRAMEWORK}",
        ),
    ],
    ids=[
        "third-party-symbols",
        "links-a-library-outside-the-bundle",
        "links-a-file-not-in-the-bundle",
        "symbols-unreadable",
        "links-unreadable",
        "not-from-the-build-python",
    ],
)
def test_a_framework_file_is_cpython_only_with_proof(tpl, monkeypatch, files, expected):
    _, problems = _darwin_collect(tpl, monkeypatch, files)
    assert expected in problems


def test_libraries_inside_framework_modules_get_their_own_rows(tpl, monkeypatch):
    comps, problems = _darwin_collect(
        tpl,
        monkeypatch,
        {
            _dyn("_decimal"): {
                "strings": b"_mpd_qadd",
                "symbols": ["_PyInit__decimal", "_mpd_qadd"],
            },
            _dyn("pyexpat"): {
                "strings": b"_XML_ParserCreate",
                "symbols": ["_PyInit_pyexpat", "_XML_ParserCreate"],
            },
            _dyn("_lzma"): {
                "strings": b"_lzma_code",
                "symbols": ["_PyInit__lzma", "_lzma_code"],
            },
        },
    )
    expat = comps["expat (in CPython's pyexpat)"]
    assert (expat.spdx, expat.version, expat.files) == ("MIT", "9.9", [_dyn("pyexpat")])
    assert expat.texts == [
        (
            "repo:scripts/packaging/licenses/expat-COPYING",
            "text of repo:scripts/packaging/licenses/expat-COPYING\n",
        )
    ]
    # libmpdec: no verified text and no licence id from evidence yet: it fails
    # by name (B2f: upstream's address was refused by the network proxy).
    assert sorted(problems) == [
        f"{_dyn('_decimal')}: licence text of libmpdec (in CPython's _decimal): no "
        "verified source in the table; store the upstream text unchanged under "
        "scripts/packaging/licenses/ and its address, tag, sha256 and date in "
        "SOURCES.json",
        "libmpdec (in CPython's _decimal) 9.9: licence NOASSERTION is not in the "
        "allow-list",
    ]


def test_a_module_that_loads_the_library_carries_no_copy(tpl, monkeypatch):
    comps, problems = _darwin_collect(
        tpl,
        monkeypatch,
        {
            _dyn("_decimal"): {
                "strings": b"_mpd_qadd libmpdec.4.dylib",
                "links": [LIBSYSTEM, "@rpath/libmpdec.4.dylib"],
            }
        },
    )
    assert "libmpdec (in CPython's _decimal)" not in comps
    assert any("links @rpath/libmpdec.4.dylib" in p for p in problems)


# ------------- macOS links to OS libraries (architect-package-dryrun-5.md ruling 2)
OS_LINKS = {
    _dyn("zlib"): {"links": [LIBSYSTEM, "/usr/lib/libz.1.dylib"]},
    _dyn("binascii"): {"links": [LIBSYSTEM, "/usr/lib/libz.1.dylib"]},
    _dyn("_bz2"): {"links": [LIBSYSTEM, "/usr/lib/libbz2.1.0.dylib"]},
    _dyn("_ctypes"): {"links": [LIBSYSTEM, "/usr/lib/libffi.dylib"]},
    _dyn("_scproxy"): {
        "links": [
            LIBSYSTEM,
            "/System/Library/Frameworks/SystemConfiguration.framework/Versions/A/"
            "SystemConfiguration",
        ]
    },
}


def test_links_to_os_libraries_need_no_row(tpl, monkeypatch):
    # Run 5 failed on exactly these four modules; the libraries are part of
    # macOS and are not carried, so they need no row.
    _, problems = _darwin_collect(tpl, monkeypatch, OS_LINKS)
    assert problems == []


@pytest.mark.parametrize(
    "lib",
    [
        "/opt/homebrew/lib/libz.1.dylib",
        "/usr/local/lib/libffi.8.dylib",
        "/Library/Frameworks/Python.framework/Versions/3.12/lib/libssl.3.dylib",
        "/Users/runner/hostedtoolcache/Python/3.12.10/arm64/lib/libz.dylib",
        "/usr/lib/../../opt/homebrew/lib/libz.dylib",
        "/usr/libexec/x.dylib",
    ],
)
def test_any_other_absolute_link_fails_the_build(tpl, monkeypatch, lib):
    _, problems = _darwin_collect(
        tpl, monkeypatch, {_dyn("zlib"): {"links": [LIBSYSTEM, lib]}}
    )
    assert problems == [
        f"{_dyn('zlib')}: links {lib}, an absolute path outside the bundle and "
        "outside /usr/lib/ and /System/Library/: a user's Mac need not have it "
        "(architect-package-dryrun-5.md ruling 2)"
    ]


@pytest.mark.parametrize(
    "lib, ok",
    [
        ("@rpath/libssl.3.dylib", True),
        ("@loader_path/../../libssl.3.dylib", True),
        ("@executable_path/_internal/libssl.3.dylib", True),
        ("@loader_path/libssl.3.dylib", False),
        ("@rpath/libmissing.dylib", False),
        ("@executable_path/../outside.dylib", False),
    ],
)
def test_relative_links_must_resolve_to_a_bundled_file_with_a_row(
    tpl, monkeypatch, lib, ok
):
    files = {
        _dyn("_ssl"): {"links": [LIBSYSTEM, lib]},
        "_internal/libssl.3.dylib": {"links": [LIBSYSTEM, "@rpath/libssl.3.dylib"]},
    }
    _, problems = _darwin_collect(tpl, monkeypatch, files)
    unresolved = (
        f"{_dyn('_ssl')}: links {lib}, which does not resolve to a bundled file "
        "with a row (architect-package-dryrun-5.md ruling 2)"
    )
    assert (unresolved not in problems) is ok
    assert [p for p in problems if p != unresolved] == []


def test_every_darwin_file_has_its_links_checked_also_wheel_files(tpl, monkeypatch):
    # The rule covers every file of the bundle: also lxml's unprocessed modules
    # and the other wheels' modules (ruling 1: they must link OS libraries only).
    assert all(r.links == tpl.DARWIN_SYSTEM_LINKS for r in tpl.TABLES["darwin"])
    assert tpl.DARWIN_SYSTEM_LINKS == ("/usr/lib/*", "/System/Library/*")
    etree = "_internal/lxml/etree.cpython-312-darwin.so"
    _no_runtime(tpl, monkeypatch)
    build = _DarwinBuild(
        {etree: {"links": [LIBSYSTEM, "/opt/homebrew/lib/libxml2.2.dylib"]}}
    )
    build.distribution_of_bundled = lambda rel: object()
    _, problems = tpl.collect(build, tpl.TABLES["darwin"])
    assert problems == [
        f"{etree}: links /opt/homebrew/lib/libxml2.2.dylib, an absolute path "
        "outside the bundle and outside /usr/lib/ and /System/Library/: a user's "
        "Mac need not have it (architect-package-dryrun-5.md ruling 2)"
    ]


def test_the_build_record_lists_os_links_and_the_lowest_macos_version(tpl):
    files = dict(OS_LINKS)
    files[_dyn("zlib")] = dict(OS_LINKS[_dyn("zlib")], minos=(11, 0, 0))
    files[_dyn("_ctypes")] = dict(OS_LINKS[_dyn("_ctypes")], minos=(10, 13, 0))
    files["_internal/lxml/etree.cpython-312-darwin.so"] = {"minos": (11, 0, 0)}
    files["_internal/libssl.3.dylib"] = {
        "links": [LIBSYSTEM, "@rpath/libssl.3.dylib"],
        "minos": (12, 3, 1),
    }
    record = tpl.build_record(_DarwinBuild(files), tpl.TABLES["darwin"], "arm64")
    sc = (
        "/System/Library/Frameworks/SystemConfiguration.framework/Versions/A/"
        "SystemConfiguration"
    )
    links = [
        (_dyn("_bz2"), "/usr/lib/libbz2.1.0.dylib"),
        (_dyn("_bz2"), LIBSYSTEM),
        (_dyn("_ctypes"), "/usr/lib/libffi.dylib"),
        (_dyn("_ctypes"), LIBSYSTEM),
        (_dyn("_scproxy"), sc),
        (_dyn("_scproxy"), LIBSYSTEM),
        (_dyn("binascii"), "/usr/lib/libz.1.dylib"),
        (_dyn("binascii"), LIBSYSTEM),
        (_dyn("zlib"), "/usr/lib/libz.1.dylib"),
        (_dyn("zlib"), LIBSYSTEM),
        ("_internal/lxml/etree.cpython-312-darwin.so", LIBSYSTEM),
        ("_internal/libssl.3.dylib", LIBSYSTEM),
    ]
    assert record == sorted(
        f"system library (not carried): {rel} -> {lib}" for rel, lib in links
    ) + [
        "lowest macOS version the files state: 12.3.1 (the highest minos over 4 "
        "files that state one, arm64; from _internal/libssl.3.dylib)"
    ]
    assert not any("@rpath" in line for line in record)


def test_the_build_record_says_when_no_file_states_a_macos_version(tpl):
    record = tpl.build_record(
        _DarwinBuild({_dyn("_json"): {}}), tpl.TABLES["darwin"], "arm64"
    )
    assert record == [
        f"system library (not carried): {_dyn('_json')} -> {LIBSYSTEM}",
        "lowest macOS version the files state: not recorded (no file states one)",
    ]


def _macho_version(cmd, version, cputype=0x0100000C):
    import struct

    if cmd == 0x32:  # LC_BUILD_VERSION: platform, minos, sdk, ntools
        body = struct.pack("<IIIIII", cmd, 24, 1, version, 0, 0)
    else:  # LC_VERSION_MIN_MACOSX: version, sdk
        body = struct.pack("<IIII", cmd, 16, version, 0)
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, cputype, 0, 8, 1, len(body), 0, 0)
    return header + body


def test_macho_minos_is_read_from_the_load_commands(tpl):
    assert tpl.macho_minos(_macho_version(0x32, 0x000B0000), "arm64") == (11, 0, 0)
    assert tpl.macho_minos(_macho_version(0x24, 0x000A0D00), "arm64") == (10, 13, 0)
    assert tpl.macho_minos(_macho_version(0x32, 0x000C0301), "arm64") == (12, 3, 1)
    assert tpl.macho_minos(_macho(SAMPLE_SYMBOLS), "arm64") is None
    assert tpl.macho_minos(b"\x7fELF" + b"\0" * 60, "arm64") is None
    # A universal file: the slice of the build's architecture.
    import struct

    x86 = _macho_version(0x32, 0x000A0D00, 0x01000007)
    arm = _macho_version(0x32, 0x000B0000, 0x0100000C)
    offset = 4096
    head = struct.pack(">II", 0xCAFEBABE, 2)
    head += struct.pack(">iiIII", 0x01000007, 3, offset, len(x86), 12)
    head += struct.pack(">iiIII", 0x0100000C, 0, offset + len(x86), len(arm), 12)
    fat = head + b"\0" * (offset - len(head)) + x86 + arm
    assert tpl.macho_minos(fat, "arm64") == (11, 0, 0)
    assert tpl.macho_minos(fat, "x86_64") == (10, 13, 0)


def test_the_licence_check_prints_and_writes_the_build_record(
    tpl, tmp_path, capsys, monkeypatch
):
    monkeypatch.setattr(
        tpl, "build_record", lambda build, rows, arch: ["line one", "line two"]
    )
    bundle, work = _fake_bundle(tmp_path)
    record = tmp_path / "build-record.txt"
    args = ["--bundle", str(bundle), "--workpath", str(work)]
    args += ["--out", str(tmp_path / "T.txt"), "--build-record", str(record)]
    tpl.main(args + ["--platform", "darwin"])
    out = capsys.readouterr().out
    assert "BUILD RECORD: line one\nBUILD RECORD: line two\n" in out
    assert record.read_text("utf-8") == "line one\nline two\n"
    # Linux: no link rule, no record lines; its output stays as it was.
    tpl.main(args[:-2] + ["--platform", "linux"])
    assert "BUILD RECORD" not in capsys.readouterr().out


# ------------- liblzma on macOS (architect-package-dryrun-5.md ruling 3)
XZ_REPO = "https://github.com/tukaani-project/xz"
XZ_TEXTS = (
    "repo:scripts/packaging/licenses/xz-COPYING",
    "repo:scripts/packaging/licenses/xz-COPYING.0BSD",
)


def test_the_xz_texts_are_upstreams_files_at_one_release_tag():
    entries = _sources()["files"]
    copying, bsd0 = entries["xz-COPYING"], entries["xz-COPYING.0BSD"]
    for entry in (copying, bsd0):
        assert entry["repository"] == XZ_REPO
    assert (copying["tag"], copying["commit"]) == (bsd0["tag"], bsd0["commit"])
    assert copying["tag"] == "v5.8.4"
    # The licence id for that version is the file's own statement.
    text = " ".join((LICENSES / "xz-COPYING").read_text("utf-8").split())
    assert "liblzma is under the BSD Zero Clause License (0BSD)." in text


def test_the_liblzma_row_carries_both_texts_and_reads_its_version(tpl):
    row = tpl.match_row(_dyn("_lzma"), tpl.TABLES["darwin"])
    (lzma,) = row.carries
    assert lzma.name == "liblzma (in CPython's _lzma)"
    assert lzma.text == XZ_TEXTS
    assert lzma.spdx == "LicenseRef-public-domain OR 0BSD"
    assert lzma.version == "strings:^(5\\.[0-9]+\\.[0-9]+)$"
    assert lzma.spdx_by_version == (("5.8.4", "0BSD"),)


class _LzmaBuild(_DarwinBuild):
    def __init__(self, version):
        super().__init__(
            {
                _dyn("_lzma"): {
                    "strings": b"_lzma_code",
                    "symbols": ["_PyInit__lzma", "_lzma_code"],
                }
            }
        )
        self.version = version

    def read_version(self, source, rel, owner):
        return self.version if source.startswith("strings:") else "9.9"


@pytest.mark.parametrize(
    "version, spdx, version_from",
    [
        (
            "",
            "LicenseRef-public-domain OR 0BSD",
            "licence depends on the version, which the build could not read",
        ),
        (
            "5.8.4",
            "0BSD",
            "version read from the module; licence as the stored licence file of "
            "that version states",
        ),
        (
            "5.4.6",
            "LicenseRef-public-domain OR 0BSD",
            "version read from the module; no stored licence file states the "
            "licence of that version (they are of 5.8.4), so both ids stay",
        ),
    ],
    ids=["no-version", "version-of-the-stored-file", "other-version"],
)
def test_liblzma_licence_is_chosen_by_its_version_only_with_evidence(
    tpl, monkeypatch, version, spdx, version_from
):
    _no_runtime(tpl, monkeypatch)
    comps, problems = tpl.collect(_LzmaBuild(version), tpl.TABLES["darwin"])
    assert problems == []
    (lzma,) = [c for c in comps if c.name == "liblzma (in CPython's _lzma)"]
    assert (lzma.version, lzma.spdx, lzma.version_from) == (
        version,
        spdx,
        version_from,
    )
    assert [label for label, _ in lzma.texts] == list(XZ_TEXTS)


PIN_GOLDEN = (
    "CPython 3.12.11: the darwin rows were written from the files of Python "
    "3.12.10 (dry run 4); build with python-version 3.12.10 (architect ruling 3.4)"
)


def test_the_macos_build_python_is_pinned_to_the_patch_version_of_dry_run_4(tpl):
    assert tpl.PINNED_PYTHON == {"darwin": (3, 12, 10)}
    assert tpl.pinned_python_problems("darwin", (3, 12, 11, "final", 0)) == [PIN_GOLDEN]
    assert tpl.pinned_python_problems("darwin", (3, 12, 10, "final", 0)) == []
    assert tpl.pinned_python_problems("linux", (3, 12, 16, "final", 0)) == []


def test_the_licence_check_reports_the_python_pin(tpl, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(tpl, "pinned_python_problems", lambda plat, v: [f"pin {plat}"])
    bundle, work = _fake_bundle(tmp_path)
    args = ["--bundle", str(bundle), "--workpath", str(work)]
    args += ["--out", str(tmp_path / "T.txt"), "--platform", "freebsd"]
    assert tpl.main(args) == 1
    assert "LICENCE CHECK: pin freebsd" in capsys.readouterr().err
