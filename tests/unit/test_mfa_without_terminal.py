"""A profile that needs an MFA code, with no terminal on stdin (A-11, A-65):
InvenTag stops at once with its own message and the `aws sts get-session-token`
way, never waits on input, and the stdlib line "Password input may be echoed"
does not appear. Exit code 1, as before. With a terminal the prompt works as
before (tests/unit/test_startup_failures_have_messages.py, pty test).

Child processes (a signal-free, input-free proof needs a real stdin); each has
a hard timeout so that no test can wait on input. About 3 s each."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

CONFIG = """\
[profile base]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = fake-secret-for-tests-only
region = us-east-1

[profile mfa1]
role_arn = arn:aws:iam::123456789012:role/reader
source_profile = base
mfa_serial = arn:aws:iam::123456789012:mfa/me
region = us-east-1

[profile plain]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = fake-secret-for-tests-only
region = us-east-1
"""


def child(tmp_path, profile, stdin):
    (tmp_path / "aws-config").write_text(CONFIG)
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(REPO),
        "HOME": str(tmp_path),
        "AWS_CONFIG_FILE": str(tmp_path / "aws-config"),
        "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "none"),
        "AWS_PROFILE": profile,
        "AWS_EC2_METADATA_DISABLED": "true",
        # no network: a call that is made fails at once, not after a wait
        "AWS_ENDPOINT_URL_STS": "http://127.0.0.1:9",
    }
    log = tmp_path / "out.txt"
    with open(log, "w") as sink:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "inventag",
                "--create-excel",
                "--account-regions",
                "us-east-1",
            ],
            stdin=stdin,  # an idle pipe stays open: nothing writes, nothing closes
            stdout=sink,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=tmp_path,
            start_new_session=True,  # no controlling terminal
            text=True,
        )
        try:
            proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail(f"the run waited on input:\n{log.read_text()}")
        finally:
            if proc.stdin:
                proc.stdin.close()
    return proc.returncode, log.read_text()


@pytest.mark.parametrize("stdin_kind", ["closed", "idle pipe"])
def test_mfa_profile_without_a_terminal_stops_at_once_with_the_message(
    tmp_path, stdin_kind
):
    stdin = subprocess.DEVNULL if stdin_kind == "closed" else subprocess.PIPE
    code, out = child(tmp_path, "mfa1", stdin)
    assert code == 1  # as in v1.2.1 for the closed-stdin case
    assert "Profile 'mfa1' needs an MFA code" in out
    assert "aws sts get-session-token" in out
    assert "Password input may be echoed" not in out
    assert "Traceback" not in out


def test_a_profile_without_mfa_is_not_stopped(tmp_path):
    code, out = child(tmp_path, "plain", subprocess.DEVNULL)
    assert "needs an MFA code" not in out
    assert "Password input may be echoed" not in out
