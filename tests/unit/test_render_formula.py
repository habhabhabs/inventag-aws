"""B4: ``scripts/packaging/render_formula.py`` and the formula template.

The formula (``packaging/homebrew-tap/Formula/inventag.rb``) is a template.
The script fills in the version and the three checksums from the
``SHA256SUMS`` file of a release. The archive names are the ones that
``.github/workflows/package.yml`` and ``scripts/packaging/build_binary.sh``
write: ``inventag-<version>-darwin-arm64.tar.gz``, ``-linux-x86_64`` and
``-linux-arm64``. There is no Homebrew on the machines that run these tests, so
the formula is checked by ``ruby -c`` (when ruby exists) and by reading its text.
"""

import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "packaging" / "render_formula.py"
TEMPLATE = ROOT / "packaging" / "homebrew-tap" / "Formula" / "inventag.rb"
INSTALL_PAGE = (
    "https://habhabhabs.github.io/inventag-aws/docs/getting-started/installation"
)
VERSION = "9.8.7"  # a test value, not a release
ARCHIVES = {
    "darwin-arm64": f"inventag-{VERSION}-darwin-arm64.tar.gz",
    "linux-x86_64": f"inventag-{VERSION}-linux-x86_64.tar.gz",
    "linux-arm64": f"inventag-{VERSION}-linux-arm64.tar.gz",
}
OTHER_FILES = [
    f"inventag-{VERSION}-darwin-arm64.THIRD-PARTY-LICENSES.txt",
    f"inventag-{VERSION}-linux-x86_64.THIRD-PARTY-LICENSES.txt",
    f"inventag_{VERSION}_amd64.deb",
    f"inventag_{VERSION}_arm64.deb",
    f"inventag-{VERSION}-1.x86_64.rpm",
    f"inventag-{VERSION}-1.aarch64.rpm",
    f"inventag-{VERSION}-linux-x86_64.cdx.json",
]


def digest(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def sums_text(skip=(), extra=()) -> str:
    """A SHA256SUMS file as ``sha256sum`` writes it: sorted by name, two spaces."""
    names = sorted([*ARCHIVES.values(), *OTHER_FILES])
    lines = [f"{digest(n)}  {n}" for n in names if n not in skip]
    lines.extend(extra)
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def rf():
    spec = importlib.util.spec_from_file_location("_b4_render_formula", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def rendered(rf):
    return rf.render(TEMPLATE.read_text("utf-8"), VERSION, sums_text())


# --------------------------------------------------------------- the render
def test_the_version_and_three_checksums_are_filled_in(rendered):
    assert f'version "{VERSION}"' in rendered
    for key, name in ARCHIVES.items():
        assert digest(name) in rendered, key
    assert rendered.count("sha256 ") == 3
    assert "{{" not in rendered and "}}" not in rendered


def test_each_checksum_sits_under_the_url_of_its_own_archive(rendered):
    pairs = re.findall(
        r'url ".*?/inventag-#\{version\}-([a-z0-9_-]+)\.tar\.gz"\s+sha256 "([0-9a-f]{64})"',
        rendered,
    )
    assert dict(pairs) == {key: digest(name) for key, name in ARCHIVES.items()}


def test_the_urls_point_at_the_github_release_of_this_repository(rendered):
    base = "https://github.com/habhabhabs/inventag-aws/releases/download/v#{version}/"
    urls = re.findall(r'url "([^"]+)"', rendered)
    assert len(urls) == 3
    assert all(u.startswith(base) for u in urls)


def test_other_files_in_the_sums_are_ignored(rf):
    only_archives = "".join(f"{digest(n)}  {n}\n" for n in sorted(ARCHIVES.values()))
    template = TEMPLATE.read_text("utf-8")
    assert rf.render(template, VERSION, only_archives) == rf.render(
        template, VERSION, sums_text()
    )


def test_the_render_is_the_same_every_time(rf):
    template = TEMPLATE.read_text("utf-8")
    assert rf.render(template, VERSION, sums_text()) == rf.render(
        template, VERSION, sums_text()
    )


def test_a_leading_v_of_a_tag_is_accepted(rf):
    template = TEMPLATE.read_text("utf-8")
    assert rf.render(template, "v" + VERSION, sums_text()) == rf.render(
        template, VERSION, sums_text()
    )


@pytest.mark.parametrize(
    "bad", ["", "1.4", "1.4.0.1", "1.4.x", "v", "latest", "1.4.0 "]
)
def test_a_version_that_is_not_x_y_z_is_refused(rf, bad):
    with pytest.raises(rf.RenderError, match="version"):
        rf.render(TEMPLATE.read_text("utf-8"), bad, sums_text())


# ------------------------------------------------------ the checksum file
@pytest.mark.parametrize("key", sorted(ARCHIVES))
def test_a_missing_checksum_line_is_named(rf, key):
    name = ARCHIVES[key]
    with pytest.raises(rf.RenderError) as err:
        rf.render(TEMPLATE.read_text("utf-8"), VERSION, sums_text(skip={name}))
    assert name in str(err.value)
    assert "no checksum" in str(err.value)


def test_an_empty_sums_file_is_refused(rf):
    with pytest.raises(rf.RenderError, match="no checksum"):
        rf.render(TEMPLATE.read_text("utf-8"), VERSION, "")


def test_a_checksum_for_another_version_does_not_count(rf):
    other = sums_text().replace(VERSION, "9.8.6")
    with pytest.raises(rf.RenderError, match="no checksum"):
        rf.render(TEMPLATE.read_text("utf-8"), VERSION, other)


def test_a_duplicated_line_is_refused_even_when_both_agree(rf):
    name = ARCHIVES["linux-arm64"]
    extra = [f"{digest(name)}  {name}"]
    with pytest.raises(rf.RenderError) as err:
        rf.render(TEMPLATE.read_text("utf-8"), VERSION, sums_text(extra=extra))
    assert "more than once" in str(err.value) and name in str(err.value)


def test_a_duplicated_line_with_another_checksum_is_refused(rf):
    name = ARCHIVES["darwin-arm64"]
    extra = [f"{'0' * 64}  {name}"]
    with pytest.raises(rf.RenderError, match="more than once"):
        rf.render(TEMPLATE.read_text("utf-8"), VERSION, sums_text(extra=extra))


@pytest.mark.parametrize(
    "line",
    [
        "abc123  inventag-9.8.7-linux-arm64.tar.gz",  # too short
        ("g" * 64) + "  inventag-9.8.7-linux-arm64.tar.gz",  # not hex
        ("A" * 64)
        + "  inventag-9.8.7-linux-arm64.tar.gz",  # sha256sum writes lower case
        ("a" * 65) + "  inventag-9.8.7-linux-arm64.tar.gz",  # too long
        ("a" * 64) + " inventag-9.8.7-linux-arm64.tar.gz",  # one space
        ("a" * 64) + "inventag-9.8.7-linux-arm64.tar.gz",  # no space
        ("a" * 64) + "  ",  # no name
        "inventag-9.8.7-linux-arm64.tar.gz",  # no checksum
        ("a" * 64) + "  ./inventag-9.8.7-linux-arm64.tar.gz",  # a path
        ("a" * 64) + "  dist/inventag-9.8.7-linux-arm64.tar.gz",  # a path
    ],
)
def test_a_malformed_line_is_refused_with_its_line_number(rf, line):
    text = sums_text()
    count = len(text.splitlines())
    with pytest.raises(rf.RenderError) as err:
        rf.render(TEMPLATE.read_text("utf-8"), VERSION, text + line + "\n")
    assert f"line {count + 1}" in str(err.value)
    assert "malformed" in str(err.value)


def test_a_binary_mode_line_is_read(rf):
    text = sums_text().replace(
        f"{digest(ARCHIVES['linux-arm64'])}  ", f"{digest(ARCHIVES['linux-arm64'])} *"
    )
    assert digest(ARCHIVES["linux-arm64"]) in rf.render(
        TEMPLATE.read_text("utf-8"), VERSION, text
    )


def test_blank_lines_and_windows_line_ends_are_read(rf):
    text = "\n" + sums_text().replace("\n", "\r\n") + "\r\n\r\n"
    assert VERSION in rf.render(TEMPLATE.read_text("utf-8"), VERSION, text)


def test_a_template_with_an_unknown_placeholder_is_refused(rf):
    template = TEMPLATE.read_text("utf-8") + "# {{SOMETHING_NEW}}\n"
    with pytest.raises(rf.RenderError, match="SOMETHING_NEW"):
        rf.render(template, VERSION, sums_text())


# ---------------------------------------------------------- the command line
def run_cli(rf, tmp_path, capsys, sums, *extra, version=VERSION):
    sums_file = tmp_path / "SHA256SUMS"
    sums_file.write_text(sums, "utf-8")
    code = rf.main(["--version", version, "--sums", str(sums_file), *extra])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_the_command_prints_the_formula_and_exits_0(rf, tmp_path, capsys):
    code, out, err = run_cli(rf, tmp_path, capsys, sums_text())
    assert code == 0
    assert err == ""
    assert "\nclass Inventag < Formula\n" in out


def test_the_command_writes_the_output_file(rf, tmp_path, capsys):
    target = tmp_path / "Formula" / "inventag.rb"
    code, out, err = run_cli(rf, tmp_path, capsys, sums_text(), "--output", str(target))
    assert (code, out, err) == (0, "", "")
    assert "\nclass Inventag < Formula\n" in target.read_text("utf-8")
    assert list(target.parent.iterdir()) == [target]  # no temporary file left


def test_a_bad_sums_file_gives_a_plain_message_and_exit_2(rf, tmp_path, capsys):
    target = tmp_path / "inventag.rb"
    code, out, err = run_cli(
        rf,
        tmp_path,
        capsys,
        sums_text(skip={ARCHIVES["linux-x86_64"]}),
        "--output",
        str(target),
    )
    assert code == 2
    assert out == ""
    assert err.startswith("render_formula: ")
    assert ARCHIVES["linux-x86_64"] in err
    assert "Traceback" not in err and err.count("\n") == 1
    assert not target.exists()


def test_a_failed_render_keeps_the_old_output_file(rf, tmp_path, capsys):
    target = tmp_path / "inventag.rb"
    target.write_text("old\n", "utf-8")
    code, _, _ = run_cli(rf, tmp_path, capsys, "", "--output", str(target))
    assert code == 2
    assert target.read_text("utf-8") == "old\n"


def test_a_missing_sums_file_gives_a_plain_message_and_exit_2(rf, tmp_path, capsys):
    code = rf.main(["--version", VERSION, "--sums", str(tmp_path / "nope")])
    err = capsys.readouterr().err
    assert code == 2
    assert err.startswith("render_formula: ") and "nope" in err
    assert "Traceback" not in err


def test_a_bad_version_on_the_command_line_exits_2(rf, tmp_path, capsys):
    code, _, err = run_cli(rf, tmp_path, capsys, sums_text(), version="1.4")
    assert code == 2 and "version" in err


def test_the_script_runs_as_a_program(tmp_path):
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(sums_text(), "utf-8")
    done = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--version", VERSION, "--sums", str(sums)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert f'version "{VERSION}"' in done.stdout


# ------------------------------------------------------------ the template
def test_the_template_holds_no_version_number():
    # The version exists only in inventag/_version.py (plan 3.4).
    text = TEMPLATE.read_text("utf-8")
    assert not re.search(r"(?<![\w.])v?\d+\.\d+\.\d+(?![\w.])", text)


def test_the_template_has_the_four_placeholders():
    text = TEMPLATE.read_text("utf-8")
    assert set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", text)) == {
        "VERSION",
        "SHA256_DARWIN_ARM64",
        "SHA256_LINUX_X86_64",
        "SHA256_LINUX_ARM64",
    }


def test_the_formula_has_the_licence_and_the_three_targets(rendered):
    assert 'license "MIT"' in rendered
    assert "class Inventag < Formula" in rendered
    macos = rendered.split("on_macos do", 1)[1].split("on_linux do", 1)[0]
    linux = rendered.split("on_linux do", 1)[1].split("def install", 1)[0]
    assert "darwin-arm64" in macos and "darwin-x86_64" not in macos
    assert "linux-x86_64" in linux and "linux-arm64" in linux
    assert "darwin-x86_64" not in rendered  # there is no Intel Mac archive


def test_an_intel_mac_gets_a_plain_message_with_the_install_page(rendered):
    assert "There is no executable for Intel Macs" in rendered
    assert INSTALL_PAGE in rendered
    install = rendered.split("def install", 1)[1].split("test do", 1)[0]
    guard = install.split("libexec.install", 1)[0]
    assert "odie" in guard and "Hardware::CPU.intel?" in guard and "OS.mac?" in guard


def test_the_tree_goes_to_libexec_with_a_link_in_bin(rendered):
    assert 'libexec.install Dir["*"]' in rendered
    assert 'bin.install_symlink libexec/"inventag"' in rendered


def test_the_completions_and_the_man_page_come_from_the_archive(rendered):
    # The archive paths of scripts/packaging/build_binary.sh.
    assert 'libexec/"share/completions/inventag.bash"' in rendered
    assert 'libexec/"share/completions/_inventag"' in rendered
    assert 'libexec/"share/completions/inventag.fish"' in rendered
    assert 'libexec/"share/man/man1/inventag.1"' in rendered
    assert "bash_completion.install" in rendered
    assert "zsh_completion.install" in rendered
    assert "fish_completion.install" in rendered
    assert "man1.install" in rendered


def test_the_test_block_runs_the_version_and_the_selftest(rendered):
    block = rendered.split("test do", 1)[1]
    assert '"#{bin}/inventag --version"' in block
    assert "selftest" in block


def test_the_formula_needs_no_python_and_does_no_network_in_the_install_step(rendered):
    assert "depends_on" not in rendered
    assert "python" not in rendered.lower().replace("pyinstaller", "")
    install = rendered.split("def install", 1)[1].split("test do", 1)[0]
    for word in ("curl", "wget", "pip", "resource", "system ", "http", "git "):
        assert word not in install.replace(INSTALL_PAGE, ""), word


def test_the_formula_names_the_bundled_libiconv_and_its_notices(rendered):
    assert "libiconv" in rendered and "LGPL-2.1" in rendered
    assert "THIRD-PARTY-LICENSES.txt" in rendered


def test_the_formula_follows_the_homebrew_text_rules(rendered):
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
    assert "\t" not in rendered
    assert not [ln for ln in rendered.splitlines() if ln != ln.rstrip()]
    desc = re.search(r'^\s*desc "([^"]+)"', rendered, re.M).group(1)
    assert len(desc) <= 80 and not desc.endswith(".")
    assert not re.match(r"(?i)(a|an|the)\s", desc)
    assert "inventag" not in desc.lower().split()[0]
    order = [
        rendered.index(k) for k in ('desc "', 'homepage "', 'version "', 'license "')
    ]
    assert order == sorted(order)


@pytest.mark.skipif(
    shutil.which("ruby") is None, reason="ruby is not installed on this machine"
)
def test_the_rendered_formula_and_the_template_pass_ruby_c(rendered, tmp_path):
    for name, text in (
        ("rendered.rb", rendered),
        ("template.rb", TEMPLATE.read_text("utf-8")),
    ):
        path = tmp_path / name
        path.write_text(text, "utf-8")
        done = subprocess.run(
            [shutil.which("ruby"), "-c", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stderr
        assert "Syntax OK" in done.stdout
