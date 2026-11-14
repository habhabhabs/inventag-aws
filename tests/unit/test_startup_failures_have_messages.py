"""Start-up failures end with a message, not a traceback (A-10, A-11, A-15).

Five cases: an expired IAM Identity Center (SSO) token, a profile that needs an
MFA code when nobody can type it, and an unusable path for ``--audit-output``,
``--log-file`` and ``--output-directory``. Every case keeps exit code 1, as in
v1.2.0.

The SSO and path cases run in this process, with no network (a spy records
any AWS call). The two MFA tests start a child process: botocore reads the
code through ``getpass``, which looks for a controlling terminal, and only a
child with its own session (or its own pty) is a stable test of that. Each
takes a few seconds (interpreter start); that is the reason for the slow form.
"""

import importlib
import logging
import os
import pty
import select
import subprocess
import sys
import time
import traceback
from pathlib import Path

import botocore.client
import pytest

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")
REPO = Path(__file__).resolve().parents[2]

CONFIG = """\
[profile sso1]
sso_start_url = https://example.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = Admin
region = us-east-1

[profile base]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = fake-secret-for-tests-only
region = us-east-1

[profile mfa1]
role_arn = arn:aws:iam::123456789012:role/reader
source_profile = base
mfa_serial = arn:aws:iam::123456789012:mfa/me
region = us-east-1
"""


@pytest.fixture
def env(monkeypatch, tmp_path):
    config = tmp_path / "aws-config"
    config.write_text(CONFIG)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


@pytest.fixture
def aws_calls(monkeypatch):
    """Record every AWS API call and make it fail at once (no network)."""
    calls = []

    def fake(self, operation_name, api_params):
        calls.append(operation_name)
        raise RuntimeError("no network in this test")

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", fake)
    return calls


def run_cli(capsys, *args):
    """Run main(); return (exit code, stdout + stderr). An exception that
    escapes main() is what a user sees as a traceback: it is added to the text
    and counted as exit code 1, which is what Python gives."""
    old_argv = sys.argv
    sys.argv = ["inventag", *args]
    code = 0
    extra = ""
    try:
        cli_main.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception:
        code = 1
        extra = traceback.format_exc()
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    return code, captured.out + captured.err + extra


# ------------------------------------------------------------------ A-10 SSO
def test_expired_sso_token_gives_one_message_with_the_login_command(
    env, capsys, monkeypatch
):
    monkeypatch.setenv("AWS_PROFILE", "sso1")
    code, text = run_cli(capsys, "--create-excel", "--account-regions", "us-east-1")
    assert code == 1
    assert "Traceback" not in text
    assert "aws sso login --profile sso1" in text


# ------------------------------------------------------------------ A-15 paths
@pytest.fixture
def a_file(env):
    path = env / "afile"
    path.write_text("not a folder")
    return path


@pytest.mark.parametrize(
    "option,value",
    [
        ("--audit-output", "afile/audit.json"),
        ("--log-file", "afile/inventag.log"),
        ("--output-directory", "afile/out"),
    ],
)
def test_unusable_path_is_refused_before_any_aws_call(
    env, a_file, aws_calls, capsys, option, value
):
    code, text = run_cli(
        capsys, "--create-excel", "--account-regions", "us-east-1", option, value
    )
    assert code == 1
    assert "Traceback" not in text
    assert option in text and "afile" in text
    assert aws_calls == []


# ------------------------------------------------------------------ A-11 MFA
def child_env(tmp_path):
    e = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("AWS_") and k != "PYTHONPATH"
    }
    e.update(
        HOME=str(tmp_path),
        AWS_CONFIG_FILE=str(tmp_path / "aws-config"),
        AWS_SHARED_CREDENTIALS_FILE=str(tmp_path / "no-creds"),
        AWS_PROFILE="mfa1",
        AWS_EC2_METADATA_DISABLED="true",
        PYTHONPATH=str(REPO),
    )
    return e


def test_mfa_profile_with_no_terminal_gives_a_message(env):
    """stdin closed and no controlling terminal: today EOFError and a
    traceback with an empty message."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "inventag",
            "--create-excel",
            "--account-regions",
            "us-east-1",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=child_env(env),
        cwd=env,
        start_new_session=True,
        timeout=120,
    )
    text = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "Traceback" not in text
    assert "mfa1" in text and "MFA" in text
    assert "aws sts get-session-token" in text


ASSUME_ROLE = """<AssumeRoleResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
<AssumeRoleResult><Credentials><AccessKeyId>ASIAEXAMPLE</AccessKeyId>
<SecretAccessKey>fake-secret</SecretAccessKey><SessionToken>fake-token</SessionToken>
<Expiration>2099-01-01T00:00:00Z</Expiration></Credentials>
<AssumedRoleUser><AssumedRoleId>AROAEXAMPLE:s</AssumedRoleId>
<Arn>arn:aws:sts::123456789012:assumed-role/reader/s</Arn></AssumedRoleUser>
</AssumeRoleResult></AssumeRoleResponse>"""

CALLER = """<GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
<GetCallerIdentityResult><Arn>arn:aws:sts::123456789012:assumed-role/reader/s</Arn>
<UserId>AROAEXAMPLE:s</UserId><Account>123456789012</Account>
</GetCallerIdentityResult></GetCallerIdentityResponse>"""


def test_mfa_prompt_still_works_on_a_terminal(env):
    """A child on a pty (a fake terminal) is asked for the code and sends it to
    STS. The STS endpoint is a stand-in HTTP server on localhost that records
    the request, so no real AWS call is made."""
    import fcntl
    import http.server
    import termios
    import threading

    bodies = []

    class Sts(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"])).decode()
            bodies.append(body)
            xml = ASSUME_ROLE if "Action=AssumeRole" in body else CALLER
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(xml)))
            self.end_headers()
            self.wfile.write(xml.encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Sts)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    master, slave = pty.openpty()
    try:
        environ = child_env(env)
        environ["AWS_ENDPOINT_URL_STS"] = f"http://127.0.0.1:{server.server_port}"
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "inventag",
                "--validate-credentials",
                "--create-excel",
                "--account-regions",
                "us-east-1",
            ],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=environ,
            cwd=env,
            start_new_session=True,
            preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
        )
        seen = b""
        asked = 0
        deadline = time.time() + 90
        while proc.poll() is None and time.time() < deadline:
            ready, _, _ = select.select([master], [], [], 0.5)
            if not ready:
                continue
            try:
                seen += os.read(master, 4096)
            except OSError:
                break
            if seen.count(b"MFA") > asked:
                asked = seen.count(b"MFA")
                os.write(master, b"123456\n")
        proc.wait(timeout=60)
    finally:
        os.close(master)
        os.close(slave)
        server.shutdown()
    text = seen.decode(errors="replace")
    assert asked >= 1, f"the MFA prompt did not appear:\n{text}"
    assert any("TokenCode=123456" in b for b in bodies), (bodies, text)
    assert "Traceback" not in text and "EOFError" not in text, text
