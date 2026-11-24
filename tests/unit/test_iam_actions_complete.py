"""Every action of InvenTag's policy is granted by the AWS managed policy ReadOnlyAccess.

W1 of reports/v14-plan-readonlyaccess.md, item 4. The allow-list read here is
``tests/data/aws-managed/ReadOnlyAccess.json``.

PROVISIONAL: that file is a list written by hand from the plan's table, not a copy of the
AWS policy (``SOURCE.json`` says what must replace it). Until it is replaced, a pass here
means "InvenTag's policy file is covered by the list the plan describes", nothing more.
Not verified against real AWS.
"""

import pytest

from inventag.security.iam_policy import (
    S3_UPLOAD_ACTIONS,
    all_policy_actions,
    build_read_only_policy,
    build_s3_upload_statement,
)
from tests.policy_sim import matches_any, read_only_access_actions

# What InvenTag can need that ReadOnlyAccess does not grant, and the feature each belongs to
# (plan section 1). A new entry here is a decision: it goes to the docs page as an extra.
KNOWN_NOT_IN_READONLYACCESS = {
    "sts:AssumeRole": "scanning other accounts through a role (--accounts-file, --cross-account-role)",
    "s3:PutObject": "uploading the reports (--s3-bucket)",
    "kms:GenerateDataKey": "uploading the reports with a KMS key (--s3-bucket with --s3-encryption aws:kms)",
}


def ungranted_actions(actions, allow):
    """The actions that no pattern of ``allow`` matches."""
    return sorted(a for a in set(actions) if not matches_any(a, allow))


def assert_granted_or_documented(
    actions, allow, documented=KNOWN_NOT_IN_READONLYACCESS
):
    """Fail, with what to do, for an action that is neither granted nor documented as an extra."""
    unknown = [a for a in ungranted_actions(actions, allow) if a not in documented]
    assert not unknown, (
        "InvenTag's policy lists action(s) that the ReadOnlyAccess fixture does not grant: "
        f"{', '.join(unknown)}. Either document each as an extra that ReadOnlyAccess does not "
        "include (add it to KNOWN_NOT_IN_READONLYACCESS in tests/unit/test_iam_actions_complete.py "
        "with the feature it belongs to, and to the IAM page), or do not call it. If the fixture "
        "is a raw copy of the AWS policy, tell the architect: AWS changed the policy."
    )


@pytest.fixture(scope="module")
def allow():
    return read_only_access_actions()


@pytest.fixture(scope="module")
def policy_actions():
    return all_policy_actions(build_read_only_policy())


def test_provisional_the_policy_file_has_the_123_read_actions_and_the_gateway_statement(
    policy_actions,
):
    assert (
        len(set(policy_actions)) == 124
    )  # 123 keys of READ_ONLY_ACTIONS + apigateway:GET
    assert "apigateway:GET" in policy_actions


def test_provisional_every_action_of_the_policy_file_is_granted_by_readonlyaccess(
    allow, policy_actions
):
    assert_granted_or_documented(policy_actions, allow)
    # none of them needs the documented extras: the policy file is covered as it stands
    assert ungranted_actions(policy_actions, allow) == []


@pytest.mark.parametrize("action", sorted(KNOWN_NOT_IN_READONLYACCESS))
def test_provisional_the_known_exception_is_not_granted_by_readonlyaccess(
    allow, action
):
    assert not matches_any(action, allow), (
        f"{action} is granted by the fixture, but the plan says ReadOnlyAccess does not "
        "include it: check the fixture and the plan before changing either."
    )


def test_provisional_the_upload_statement_needs_only_an_extra(allow):
    statement = build_s3_upload_statement("some-bucket")
    assert list(statement["Action"]) == list(S3_UPLOAD_ACTIONS)
    assert_granted_or_documented(statement["Action"], allow)
    assert ungranted_actions(statement["Action"], allow) == ["s3:PutObject"]


def test_provisional_the_policy_file_does_not_hold_an_extra(policy_actions):
    """The read-only policy file stays read-only: no extra of the table is in it."""
    assert not set(KNOWN_NOT_IN_READONLYACCESS) & set(policy_actions)


def test_provisional_a_new_action_that_the_fixture_does_not_grant_fails_and_says_what_to_do(
    allow, policy_actions
):
    new = "newservice:ListThings"
    with pytest.raises(AssertionError) as caught:
        assert_granted_or_documented([*policy_actions, new], allow)
    message = str(caught.value)
    assert new in message
    assert "KNOWN_NOT_IN_READONLYACCESS" in message
    assert "do not call it" in message
    # documenting it as an extra makes the check pass
    assert_granted_or_documented(
        [*policy_actions, new],
        allow,
        {**KNOWN_NOT_IN_READONLYACCESS, new: "a new feature"},
    )
