"""``inventag selftest``: an offline check that an installed copy of InvenTag works.

It is the smoke test of every packaged format (wheel, executable, .deb, .rpm,
Homebrew formula). It must make no AWS call and open no socket, leave nothing
behind, and say in one line per check what it found.
"""

import io
import re
import socket
import tempfile
from pathlib import Path

import boto3
import botocore.client
import botocore.httpsession
import pytest

from inventag.cli import selftest
from inventag.security.read_only_guard import get_installed_guard

REPO = Path(__file__).resolve().parents[2]

CHECK_NAMES = [
    "python",
    "packages",
    "ca-bundle",
    "modules",
    "templates",
    "botocore",
    "read-only-guard",
    "reports",
]


def run(argv=()):
    out, err = io.StringIO(), io.StringIO()
    code = selftest.main(list(argv), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------- a real run


def test_a_healthy_install_passes_every_check_and_exits_0():
    code, out, err = run()
    assert code == 0, out + err
    assert err == ""
    lines = out.splitlines()
    assert re.fullmatch(
        r"inventag selftest v\d+\.\d+\.\d+\S* on Python 3\.\d+", lines[0]
    )
    names = [line.split()[1] for line in lines[1:-1]]
    assert names == CHECK_NAMES
    assert all(line.startswith("ok   ") for line in lines[1:-1]), out
    assert lines[-1] == (
        f"selftest passed: {len(CHECK_NAMES)} checks. "
        "No AWS call was made and no network connection was opened."
    )


def test_selftest_opens_no_socket_and_makes_no_aws_call(monkeypatch):
    seen = []

    def forbid(name):
        def refuse(*args, **kwargs):
            seen.append(name)
            raise AssertionError(f"selftest used the network: {name}")

        return refuse

    monkeypatch.setattr(socket.socket, "__init__", forbid("socket.socket()"))
    monkeypatch.setattr(socket.socket, "connect", forbid("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", forbid("connect_ex"))
    monkeypatch.setattr(socket, "create_connection", forbid("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", forbid("getaddrinfo"))
    monkeypatch.setattr(
        botocore.client.BaseClient, "_make_api_call", forbid("AWS API call")
    )
    monkeypatch.setattr(
        botocore.httpsession.URLLib3Session, "send", forbid("HTTP request")
    )

    code, out, err = run()

    assert seen == []
    assert code == 0, out + err


def test_selftest_leaves_nothing_behind_and_does_not_change_the_process(
    tmp_path, monkeypatch
):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    monkeypatch.chdir(cwd)
    guard_before = get_installed_guard()
    session_create_client = boto3.session.Session.client

    code, out, err = run()

    assert code == 0, out + err
    assert list(scratch.iterdir()) == []
    assert list(cwd.iterdir()) == []
    assert get_installed_guard() is guard_before
    assert boto3.session.Session.client is session_create_client


def test_the_reports_check_writes_a_workbook_and_a_document_it_can_read_back(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    written = []
    real = tempfile.TemporaryDirectory

    class Spy(real):
        def cleanup(self):
            written.extend(sorted(p.name for p in Path(self.name).iterdir()))
            super().cleanup()

    monkeypatch.setattr(tempfile, "TemporaryDirectory", Spy)

    code, out, err = run()

    assert code == 0, out + err
    assert any(name.endswith(".xlsx") for name in written), written
    assert any(name.endswith(".docx") for name in written), written
    assert list(tmp_path.iterdir()) == []


# ------------------------------------------------- the list of runtime packages


def test_every_package_in_requirements_is_checked_by_selftest():
    aliases = {"python-docx": "docx", "pyyaml": "yaml"}
    wanted = set()
    for line in (REPO / "requirements.txt").read_text().splitlines():
        match = re.match(r"([A-Za-z0-9_.-]+)", line.split("#")[0].strip())
        if match:
            name = match.group(1).lower()
            wanted.add(aliases.get(name, name.replace("-", "_")))
    checked = {name.split(".")[0] for name in selftest.RUNTIME_PACKAGES}
    assert wanted <= checked, sorted(wanted - checked)


# ---------------------------------------------------------- failure messages


def fake_checks(*checks):
    return list(checks)


def test_the_output_format_is_stable(monkeypatch):
    def fine():
        return "3 things found"

    def broken():
        raise selftest.CheckFailed("the file x.yaml is missing from the install")

    def surprising():
        raise ValueError("secret-token-abc123 in a long botocore message " * 20)

    monkeypatch.setattr(
        selftest, "version_line", lambda: "inventag selftest v9.9.9 on Python 3.99"
    )
    out, err = io.StringIO(), io.StringIO()
    code = selftest.run_checks(
        [("one", fine), ("two", broken), ("three", surprising)], out=out, err=err
    )

    assert code == 1
    assert out.getvalue() == (
        "inventag selftest v9.9.9 on Python 3.99\n"
        "ok   one              3 things found\n"
        "FAIL two              the file x.yaml is missing from the install\n"
        "FAIL three            unexpected error (ValueError)\n"
    )
    assert err.getvalue() == (
        "selftest failed: 2 of 3 checks failed. "
        "Install inventag-aws again (or download the release again) and run "
        "'inventag selftest' again. If it fails again, report the output above at "
        "https://github.com/habhabhabs/inventag-aws/issues.\n"
    )
    assert "secret-token" not in out.getvalue() + err.getvalue()


def test_a_broken_check_exits_1_and_the_others_still_run(monkeypatch):
    def boom():
        raise selftest.CheckFailed("the service list is empty")

    original = dict(selftest.CHECKS)
    monkeypatch.setattr(
        selftest,
        "CHECKS",
        [(n, boom if n == "botocore" else f) for n, f in original.items()],
    )

    code, out, err = run()

    assert code == 1
    assert "FAIL botocore" in out
    assert "the service list is empty" in out
    assert out.count("\nok   ") == len(CHECK_NAMES) - 1
    assert err.startswith("selftest failed: 1 of 8 checks failed.")


def test_a_missing_package_is_named_without_the_exception_text(monkeypatch):
    real_import = selftest.importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError(
                "libpsutil.so: cannot open shared object file /home/x/.secret"
            )
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(selftest.importlib, "import_module", fake_import)

    code, out, err = run()

    assert code == 1
    line = next(l for l in out.splitlines() if l.startswith("FAIL packages"))
    assert "psutil" in line
    assert ".secret" not in out + err


def test_a_missing_template_file_is_reported(monkeypatch, tmp_path):
    from inventag.templating import registry

    (tmp_path / "x.yaml").write_text("not: a template\n")
    monkeypatch.setattr(registry, "BUILTIN_DIR", tmp_path)

    code, out, err = run()

    assert code == 1
    assert any(l.startswith("FAIL templates") for l in out.splitlines()), out


def test_a_guard_that_allows_a_write_fails_the_guard_check(monkeypatch):
    from inventag.security import read_only_guard

    monkeypatch.setattr(
        read_only_guard.ReadOnlyGuard,
        "evaluate",
        lambda self, *a, **k: (True, "allowed"),
    )

    code, out, err = run()

    assert code == 1
    line = next(l for l in out.splitlines() if l.startswith("FAIL read-only-guard"))
    assert "ec2:RunInstances" in line


# ------------------------------------------------------------------ arguments


def test_help_exits_0_and_says_it_is_offline(capsys):
    with pytest.raises(SystemExit) as stop:
        selftest.main(["--help"])
    assert stop.value.code == 0
    text = capsys.readouterr().out
    assert "inventag selftest" in text
    assert "no AWS call" in text


def test_an_unknown_argument_exits_2(capsys):
    with pytest.raises(SystemExit) as stop:
        selftest.main(["--bogus"])
    assert stop.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
