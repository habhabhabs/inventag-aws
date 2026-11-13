"""I5: no secret value reaches any of the four renderings.

Secrets are planted in AWS error messages and in the text of exceptions, in
the forms the shared deny-list (inventag.security.secret_values) and the log
redaction know, and as bare values (registered, and unregistered).
"""

import json
import logging

import pytest
from botocore.exceptions import ProxyConnectionError

from inventag.outcome import render
from inventag.outcome.classify import classify, clean_aws_message
from inventag.outcome.model import AccountOutcome, Scope, State
from inventag.outcome.reduce import reduce_run
from inventag.security import redaction
from inventag.security.secret_values import MASK, is_secret_key
from tests.unit.outcome.helpers import client_error

ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
SESSION_KEY_ID = "ASIAQWERTYUIOPASDFGH"
SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
SESSION_TOKEN = "IQoJb3JpZ2luX2VjEJr//////////wEaCXVzLWVhc3QtMSJHMEUCIQD7example"
SIGNATURE = "fe5f80f77d5fa3beca038a248ff027d0445342fe2855ddc963176630326f1024"
PROXY_PASSWORD = "Pr0xyPassw0rd"
DB_PASSWORD = "hunter2-db-password-value"
REGISTERED = "accounts-file-secret-0001"
SECRETS = [
    ACCESS_KEY_ID,
    SESSION_KEY_ID,
    SECRET_KEY,
    SESSION_TOKEN,
    SIGNATURE,
    PROXY_PASSWORD,
    DB_PASSWORD,
    REGISTERED,
]

PLANTED_MESSAGES = [
    f"Access key {ACCESS_KEY_ID} with secret {SECRET_KEY} is not valid",
    f"The security token {SESSION_TOKEN} included in the request is expired",
    f"Request https://sqs.amazonaws.com/?X-Amz-Signature={SIGNATURE}&X-Amz-Credential="
    f"{SESSION_KEY_ID}/20261113/us-east-1/sqs/aws4_request failed",
    f"proxy http://user:{PROXY_PASSWORD}@proxy.local:3128 refused",
    f'{{"MasterUserPassword": "{DB_PASSWORD}", "SecretAccessKey": "{SECRET_KEY}"}}',
    f"<SessionToken>{SESSION_TOKEN}</SessionToken> {REGISTERED}",
    f"aws_secret_access_key='{SECRET_KEY}' Encoded authorization failure message: "
    f"{SESSION_TOKEN}",
]


@pytest.fixture(autouse=True)
def _registered_secret():
    redaction.register_secret(REGISTERED)
    yield
    redaction.clear_registered_secrets()


def test_the_deny_list_and_the_redaction_agree_on_the_mask():
    assert MASK == redaction.REDACTED
    assert is_secret_key("MasterUserPassword") and is_secret_key("SecretAccessKey")


@pytest.mark.parametrize("message", PLANTED_MESSAGES)
def test_clean_aws_message_removes_every_planted_secret(message):
    cleaned = clean_aws_message(message)
    for secret in SECRETS:
        assert secret not in cleaned, (secret, cleaned)


def test_arns_and_plain_text_survive_cleaning():
    text = (
        "User: arn:aws:sts::222222222222:assumed-role/InvenTagCrossAccountRole/"
        "InvenTag-222222222222 is not authorized to perform: sqs:ListQueues"
    )
    assert clean_aws_message(text) == text


class _LeakyError(Exception):
    def __str__(self):
        return " ".join(SECRETS)


def _issues():
    issues = []
    for i, message in enumerate(PLANTED_MESSAGES):
        issues.append(
            classify(
                client_error("AccessDenied" if i % 2 else "ExpiredToken", message),
                scope=Scope.SERVICE if i % 2 else Scope.ACCOUNT,
                account="222222222222",
                region="us-east-1",
                service=f"svc{i}",
                operation="ListThings",
            )
        )
    proxy = ProxyConnectionError(
        proxy_url=f"http://user:{PROXY_PASSWORD}@proxy.local:3128", error="refused"
    )
    issues.append(classify(proxy, scope=Scope.REGION, account="222222222222"))
    issues.append(classify(_LeakyError(), scope=Scope.RUN))
    issues.append(
        classify(OSError(13, SECRET_KEY), scope=Scope.OUTPUT, service="excel")
    )
    return issues


def test_no_secret_in_any_rendering():
    issues = _issues()
    outcome = reduce_run(
        [AccountOutcome("222222222222", "dev", State.PARTIAL, account_issue=True)],
        issues=issues,
        resources_reported=1,
    )
    logger = logging.getLogger("inventag.test.secrets")
    texts = []
    for account in outcome.accounts:
        texts += [t for _, t in render.log_account(account, outcome.issues, logger)]
    texts += [t for _, t in render.log_run(outcome, logger)]
    texts += render.summary_lines(outcome)
    block = render.report_block(outcome)
    texts += [block.status_line] + block.notes + [str(r) for r in block.rows]
    texts.append(json.dumps(render.summary_json(outcome)))
    texts += [repr(i) for i in outcome.issues]
    everything = "\n".join(texts)
    assert "AccessDenied" in everything  # the renderings are not empty
    for secret in SECRETS:
        assert secret not in everything, secret
