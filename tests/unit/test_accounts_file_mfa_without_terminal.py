"""An accounts-file entry whose profile needs an MFA code, run with no
terminal (A-11, A-65, accounts-file part; senior C did the single-profile
path).

v1.2.x: closed stdin gave "Password input may be echoed" and an empty
reason ("EOFError"); an idle pipe made the run wait for ever. Now the account
fails at once with a message that names the profile and the
`aws sts get-session-token` way. Exit code 1 when no account could be used,
as before.

Child processes (a real stdin is needed); each has a hard timeout so that
no test can wait on input.
"""

import json
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
"""


def child(tmp_path, stdin):
    (tmp_path / "aws-config").write_text(CONFIG)
    (tmp_path / "accounts.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "123456789012",
                        "profile_name": "mfa1",
                        "regions": ["us-east-1"],
                    }
                ]
            }
        )
    )
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(REPO),
        "HOME": str(tmp_path),
        "AWS_CONFIG_FILE": str(tmp_path / "aws-config"),
        "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "none"),
        "AWS_EC2_METADATA_DISABLED": "true",
        # no network: a call that is made fails at once, not after a wait
        "AWS_ENDPOINT_URL_STS": "http://127.0.0.1:9",
        "AWS_ENDPOINT_URL": "http://127.0.0.1:9",
    }
    log = tmp_path / "out.txt"
    with open(log, "w") as sink:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "inventag",
                "--accounts-file",
                "accounts.json",
                "--create-excel",
            ],
            stdin=stdin,
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


WANTED = (
    "Profile 'mfa1' for account 123456789012 needs an MFA code, and there is "
    "no terminal to type it in. Get temporary credentials first, for example "
    "with aws sts get-session-token --serial-number "
    "arn:aws:iam::123456789012:mfa/me --token-code <code>, and use a profile "
    "without mfa_serial."
)


@pytest.mark.parametrize("stdin", [subprocess.DEVNULL, subprocess.PIPE])
def test_an_mfa_profile_entry_fails_at_once_with_a_message(tmp_path, stdin):
    code, out = child(tmp_path, stdin)
    assert code == 1, out  # no account could be used: 1, as before
    assert WANTED in out, out
    assert "Password input may be echoed" not in out
