"""v1.5.0 P9: guard and masking carry-over (register rows A-74, A-75, A-76).

A-74  log redaction masks a LIST value under a secret field name.
A-75  ``finspace-data`` credential operations (botocore 1.35.0 only) are denied.
A-76  operations a newer SDK adds that are not plain reads are denied by name;
      ``IssuedToken`` and ``SecretValue`` are masked; a sweep looks for the
      members the SDK marks sensitive whose name ends in Token, Url or URL.

Not verified against a real AWS response: what any of these fields holds at
run time. The sweep reads the botocore models only.
"""

import json

import botocore.session
import pytest

from inventag.security.read_only_guard import ReadOnlyGuard
from inventag.security.redaction import REDACTED, redact
from inventag.security.secret_values import MASK, is_secret_key, mask_resource

# ---------------------------------------------------------------- A-74

LISTS = [
    '{"passphrase": ["x-secret-1"]}',
    '{"Password": ["y-secret-2"]}',
    "{'passphrase': ['x-secret-1']}",
    '{"passphrase": [ "x-secret-1" , "x-secret-3" ]}',
    '{"passphrase": [["x-secret-1"], ["x-secret-3"]]}',
    '{"passphrase": [{"a": "x-secret-1"}]}',
    '{"passphrase": ["x]-secret-1", "x-secret-3"]}',
    # JSON kept as text inside a JSON string (a debug-log response body)
    r'{"Body": "{\"passphrase\": [\"x-secret-1\"], \"Name\": \"n\"}"}',
    r'{"Body": "{\"Password\": [[\"x-secret-1\"], [\"x-secret-3\"]]}"}',
    r'{"Body": "{\"passphrase\": [\"x]-secret-1\"]}"}',
    # two levels of escaping
    r'{"Body": "{\"Inner\": \"{\\\"passphrase\\\": [\\\"x-secret-1\\\"]}\"}"}',
]


@pytest.mark.parametrize("text", LISTS)
def test_a_list_value_under_a_secret_name_is_masked(text):
    out = redact(text)
    assert "secret-1" not in out and "secret-3" not in out
    assert REDACTED in out


def test_the_register_probe_of_a_74():
    out = redact(
        '{"passphrase": ["x-secret-1"], "Password": ["y-secret-2"], "token": "z"}'
    )
    assert "x-secret-1" not in out and "y-secret-2" not in out
    assert out.count(REDACTED) == 3


def test_what_follows_a_masked_list_is_kept():
    out = redact('{"passphrase": ["x-secret-1"], "Name": "keep-me", "Ids": ["a", "b"]}')
    assert '"Name": "keep-me"' in out and '"Ids": ["a", "b"]' in out
    out = redact(
        r'{"Body": "{\"passphrase\": [\"x-secret-1\"], \"Name\": \"keep-me\"}"}'
    )
    assert "keep-me" in out


def test_a_masked_body_is_still_json():
    body = json.dumps({"passphrase": ["x-secret-1"], "Name": "n"})
    out = redact(json.dumps({"Body": body}))
    assert json.loads(json.loads(out)["Body"])["Name"] == "n"


def test_lists_under_other_names_and_empty_lists_are_kept():
    text = '{"Subnets": ["subnet-1"], "passphrase": [], "Groups": [["g"]]}'
    assert redact(text) == text


def test_an_unterminated_list_is_masked_to_the_end():
    out = redact('{"passphrase": ["x-secret-1", "x-secret-3"')
    assert "secret-1" not in out and "secret-3" not in out


def test_masking_a_list_twice_changes_nothing():
    once = redact('{"passphrase": ["x-secret-1"]}')
    assert redact(once) == once


# ---------------------------------------------------------------- A-75

FINSPACE = [
    ("finspace-data", "GetProgrammaticAccessCredentials"),
    ("finspace-data", "GetExternalDataViewAccessDetails"),
]


@pytest.mark.parametrize("service,operation", FINSPACE)
def test_finspace_data_credential_operations_are_denied(service, operation):
    allowed, reason = ReadOnlyGuard().evaluate(service, operation)
    assert not allowed and "secrets" in reason


# ---------------------------------------------------------------- A-76

NEW_DENIED = [
    ("cognito-idp", "GetDerivedToken"),
    ("wellarchitected", "GetAgentOrganizationalReportData"),
    ("partnercentral-marketing", "GetCampaignAssetExportTask"),
    ("partnercentral-selling", "GetCustomerAccountBulkJobReportUrl"),
    ("partnercentral-selling", "GetOpportunityBulkJobReportUrl"),
]


@pytest.mark.parametrize("service,operation", NEW_DENIED)
def test_token_and_url_operations_are_denied_by_name(service, operation):
    allowed, reason = ReadOnlyGuard().evaluate(service, operation)
    assert not allowed and "secrets" in reason


def test_the_neighbours_of_the_new_denials_stay_allowed():
    guard = ReadOnlyGuard()
    for service, operation in [
        ("cognito-idp", "DescribeUserPool"),
        ("cognito-idp", "ListUsers"),
        ("wellarchitected", "GetWorkload"),
        ("partnercentral-selling", "GetOpportunity"),
        ("partnercentral-marketing", "ListCampaigns"),
    ]:
        assert guard.evaluate(service, operation)[0], (service, operation)


@pytest.mark.parametrize("name", ["IssuedToken", "SecretValue", "issued_token"])
def test_issued_token_and_secret_value_are_masked(name):
    assert is_secret_key(name)
    masked, count = mask_resource({"Thing": {name: "planted-p9-secret"}})
    assert masked["Thing"][name] == MASK and count == 1
    assert "planted-p9-secret" not in redact('{"%s": "planted-p9-secret"}' % name)


def test_the_guard_docstring_defines_the_three_classes():
    from inventag.security import read_only_guard

    doc = read_only_guard.__doc__
    assert "issues a token or credentials" in doc
    assert "returns a presigned URL" in doc
    assert "returns customer content" in doc
    assert "follows the SDK" in doc


# Sweep: an allowed operation whose answer has a member that the SDK marks
# sensitive and whose name ends in Token, Url or URL. Each is either masked by
# the deny-list of inventag.security.secret_values, a pagination token, or in
# the reviewed list below with the reason. Reviewed against the SDK's
# documentation strings, not against real responses.
_REVIEWED_LINK = "reviewed: a link to a page or record, no credential in it"
_REVIEWED_SETTING = "reviewed: a configured endpoint, a setting"
_BARE_URL = (
    "reviewed: bare name `Url`; masking by name would hide harmless fields; "
    "InvenTag does not call the operation (stated limit)"
)
REVIEWED = {
    "account:GetContactInformation:WebsiteUrl": _REVIEWED_LINK,
    "identitystore:DescribeUser:ProfileUrl": _REVIEWED_LINK,
    "identitystore:ListUsers:ProfileUrl": _REVIEWED_LINK,
    "sesv2:GetAccount:WebsiteURL": _REVIEWED_LINK,
    "workdocs:SearchResources:WebUrl": _REVIEWED_LINK,
    "devicefarm:GetJob:testDetailsUrl": _REVIEWED_LINK,
    "devicefarm:ListJobs:testDetailsUrl": _REVIEWED_LINK,
    "devicefarm:GetRun:jobDetailsUrl": _REVIEWED_LINK,
    "devicefarm:ListRuns:jobDetailsUrl": _REVIEWED_LINK,
    "partnercentral-selling:GetCustomerAccount:WebsiteUrl": _REVIEWED_LINK,
    "partnercentral-selling:GetEngagement:WebsiteUrl": _REVIEWED_LINK,
    "partnercentral-selling:GetEngagementInvitation:WebsiteUrl": _REVIEWED_LINK,
    "partnercentral-selling:GetOpportunity:WebsiteUrl": _REVIEWED_LINK,
    "partnercentral-selling:GetResourceSnapshot:WebsiteUrl": _REVIEWED_LINK,
    "partnercentral-selling:ListOpportunities:WebsiteUrl": _REVIEWED_LINK,
    "partnercentral-selling:SearchEngagements:WebsiteUrl": _REVIEWED_LINK,
    "firehose:DescribeDeliveryStream:AccountUrl": _REVIEWED_SETTING,
    "firehose:DescribeDeliveryStream:Url": _REVIEWED_SETTING,
    "inspector2:GetCodeSecurityIntegration:instanceUrl": _REVIEWED_SETTING,
    "quicksight:DescribeOAuthClientApplication:OAuthAuthorizationEndpointUrl": _REVIEWED_SETTING,
    "quicksight:DescribeOAuthClientApplication:OAuthTokenEndpointUrl": _REVIEWED_SETTING,
    "eventbridgev2:DescribeEventSource:WebhookUrl": _REVIEWED_SETTING,
    "qconnect:GetMessageTemplate:imageIconUrl": _REVIEWED_LINK,
    "qconnect:GetMessageTemplate:imageUrl": _REVIEWED_LINK,
    "qconnect:GetMessageTemplate:mediaUrl": _REVIEWED_LINK,
    "qconnect:GetMessageTemplate:smallImageIconUrl": _REVIEWED_LINK,
    "qconnect:GetNextMessage:sourceURL": _REVIEWED_LINK,
    "qconnect:ListMessages:sourceURL": _REVIEWED_LINK,
    "chime-sdk-media-pipelines:GetMediaPipeline:Url": _BARE_URL,
    "ec2:DescribeImportImageTasks:Url": _BARE_URL,
    "ec2:DescribeImportSnapshotTasks:Url": _BARE_URL,
}


def _members(shape, seen=frozenset(), depth=0):
    if depth > 12:
        return
    if shape.type_name == "structure":
        if shape.name in seen:
            return
        for name, member in shape.members.items():
            yield name, member
            yield from _members(member, seen | {shape.name}, depth + 1)
    elif shape.type_name == "list":
        yield from _members(shape.member, seen, depth + 1)
    elif shape.type_name == "map":
        yield from _members(shape.value, seen, depth + 1)


def sensitive_token_and_url_members():
    """``service:Operation:Member`` of every allowed operation's answer."""
    session = botocore.session.get_session()
    guard = ReadOnlyGuard()
    found = set()
    for service in session.get_available_services():
        model = session.get_service_model(service)
        for operation in model.operation_names:
            if not guard.evaluate(service, operation)[0]:
                continue
            output = model.operation_model(operation).output_shape
            if output is None:
                continue
            for name, member in _members(output):
                if not name.endswith(("Token", "Url", "URL")):
                    continue
                if not member.metadata.get("sensitive"):
                    continue
                if name.lower() == "nexttoken" or is_secret_key(name):
                    continue
                found.add(f"{service}:{operation}:{name}")
    return found


def test_every_sensitive_token_or_url_member_is_masked_or_reviewed():
    """A new one fails with its operation and the next step."""
    undecided = sorted(sensitive_token_and_url_members() - set(REVIEWED))
    installed = botocore.__version__
    assert not undecided, (
        f"botocore {installed}: allowed operations answer with a member the SDK "
        "marks sensitive and whose name ends in Token, Url or URL, and neither "
        "the guard denies the operation nor the deny-list masks the member:\n  "
        + "\n  ".join(undecided)
        + "\nAdd the operation to DENIED_OPERATIONS, the member to "
        "SECRET_VALUE_KEYS, or the member to REVIEWED with a reason "
        "(register A-76; tests/unit/test_v150_p9_carryover.py)."
    )


def test_every_reviewed_entry_has_a_reason_and_is_still_unmasked():
    for key, reason in REVIEWED.items():
        assert reason.startswith("reviewed:"), key
        assert not is_secret_key(key.rsplit(":", 1)[1]), key


def test_a_member_that_is_not_reviewed_is_undecided():
    planted = sensitive_token_and_url_members() | {"x:GetThing:ThingUrl"}
    assert "x:GetThing:ThingUrl" in planted - set(REVIEWED)


# ---------------------------------------------------------------- P9b rulings

SESSION_URL_DENIED = [
    ("glue", "GetDashboardUrl"),
    ("gameliftstreams", "GetStreamUrl"),
    ("gameliftstreams", "ListStreamUrls"),
    ("quicksight", "GetDashboardEmbedUrl"),
    ("quicksight", "GetSessionEmbedUrl"),
]
CUSTOMER_DATA_DENIED = [
    ("polly", "GetVoice"),
    ("opensearchmemory", "GetMemory"),
    ("opensearchmemory", "SearchMemories"),
    ("opensearchmemory", "SearchEvents"),
    ("connecthealth", "GetMedicalCodingJob"),
]


@pytest.mark.parametrize("service,operation", SESSION_URL_DENIED + CUSTOMER_DATA_DENIED)
def test_session_url_and_customer_data_operations_are_denied(service, operation):
    allowed, reason = ReadOnlyGuard().evaluate(service, operation)
    assert not allowed and "secrets" in reason


def test_the_neighbours_of_the_p9b_denials_stay_allowed():
    guard = ReadOnlyGuard()
    for service, operation in [
        ("glue", "GetDatabase"),
        ("quicksight", "DescribeDashboard"),
        ("gameliftstreams", "GetApplication"),
        ("polly", "DescribeVoices"),
        ("connecthealth", "ListDatasets"),
        ("opensearchmemory", "ListSpaces"),
    ]:
        assert guard.evaluate(service, operation)[0], (service, operation)


@pytest.mark.parametrize(
    "name",
    ["ImportManifestUrl", "S3ObjectUrl", "authorizationUrl", "OAuthAuthorizationUrl"],
)
def test_the_four_distinctive_url_names_are_masked(name):
    assert is_secret_key(name)
    masked, count = mask_resource({"Thing": {name: "https://x.example/?sig=p9"}})
    assert masked["Thing"][name] == MASK and count == 1
    assert "sig=p9" not in redact('{"%s": "https://x.example/?sig=p9"}' % name)


def test_the_bare_names_stay_unmasked():
    for name in ["Url", "url", "QueueUrl", "EmbedUrl", "StreamUrl"]:
        assert not is_secret_key(name), name
