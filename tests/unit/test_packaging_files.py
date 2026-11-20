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
    "source in the table; add the upstream text under scripts/packaging/licenses/ "
    "(first line: its address, version or commit, and date)"
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
] + [f"_internal/python3.12/lib-dynload/{m}.cpython-312-darwin.so" for m in DARWIN_DYNLOAD]


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


def test_the_darwin_table_has_no_row_for_the_python_framework_yet(tpl):
    rows = tpl.TABLES["darwin"]
    assert [f for f in DARWIN_FRAMEWORK_FILES if tpl.match_row(f, rows)] == []
