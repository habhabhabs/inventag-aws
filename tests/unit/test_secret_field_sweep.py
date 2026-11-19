"""Sweep the botocore service models for secret-like field names (T-11).

The masking deny-list (``inventag/security/secret_values.py``) works by field
name. A boto3 upgrade can bring a new field that holds a secret and that the
list does not know. This test walks the output shapes of every operation the
read-only guard allows, in every service model of the installed botocore, and
collects the string and blob fields whose name looks like a secret (password,
secret, token, credential, key material...). A field the deny-list already
masks is fine. Every other one must be decided by a person:

``ALLOWED``
    the field is not a secret (a pagination or idempotency token, the ARN or
    name of a secret, a public certificate, a setting); the reason is written
    next to it.
``KNOWN_UNMASKED``
    the field IS documented as a secret or credential and the deny-list does not
    mask it today. Each is a row for the final patch (an application change, not
    made here). The test keeps the list honest: when the deny-list learns the
    name, the entry must be removed.

A new finding fails the test with its name, one operation and the field's AWS
documentation, so the decision can be made at once. The sweep is tied to the
installed botocore on purpose (the point is to see what an upgrade brings).
Not verified against a real AWS response: that a field holds a value at run
time; the sweep reads the models only.
"""

import re
from collections import defaultdict
from functools import lru_cache

import botocore.session
import pytest

from inventag.security.read_only_guard import ReadOnlyGuard
from inventag.security.secret_values import MASK, is_secret_key, mask_resource

_NORM = re.compile(r"[^a-z0-9]")

SECRET_LIKE = re.compile(
    r"(password|passwd|passphrase|secret|token|credential|privatekey|apikey|"
    r"accesskey|sessionkey|presigned|signedurl|connectionstring|keymaterial|"
    r"encryptionkey|sharedkey|signingkey|licensekey|bearer|authkey|authstring)"
)
# A name that ends like this names or points at something, it does not hold it.
REFERENCE_SUFFIX = re.compile(
    r"(arns?|ids?|names?|types?|status|source|count|enabled|length|versions?|"
    r"dates?|time|at|seconds|size|ms|age|jsonkey|keyid|keyarn|algorithm|"
    r"xpath|fields?)$"
)

PAGING = "pagination, idempotency, concurrency or update token: not a credential"
POINTER = "the ARN or name of a secret or parameter (or a key in it), not its value"
PUBLIC = "public certificate or public key material"
SETTING = "a setting, an endpoint or a type, not a secret value"

ALLOWED = {
    **{
        name: PAGING
        for name in (
            "blocktoken changetoken clientrequesttoken clienttoken conditionaltoken "
            "continuationtoken creationtoken firstblocktoken hooksrequesttoken "
            "idempotencytoken lastclientrequesttoken listupdatetoken locktoken "
            "nextchunktoken nextcontinuationtoken nextmessagetoken nextpagetoken "
            "nextpollconfigurationtoken nexttoken pagetoken paginationtoken "
            "policyupdatetoken portfoliosharetoken requesttoken resulttoken "
            "secondblocktoken sourceupdatetoken updatetoken uploadsequencetoken "
            "versiontoken viewversiontoken"
        ).split()
    },
    **{
        name: POINTER
        for name in (
            "cdnidentifiersecret certificatesecret credentialsparameter "
            "domainjoinserviceaccountsecret passwordparam secretkey "
            "secretstringkey secretsrole servicecredentialalias"
        ).split()
    },
    **{
        name: PUBLIC
        for name in (
            "publickeymaterial publicsigningkeyendpoint publicsigningkeyurl "
            "signingkeycertificate signingkeycertificatechain"
        ).split()
    },
    **{
        name: "the identifier of a KMS key or its provider, not key material"
        for name in (
            "defaultencryptionkey encryptionkey encryptionkeyprovider "
            "kmsencryptionkey parametersencryptionkey volumeencryptionkey "
            "keymaterialdescription keymaterialstate"
        ).split()
    },
    **{
        name: SETTING
        for name in (
            "actortokencontent apikeyheader apikeyselectionexpression "
            "credentialcompromise credentiallocation credentialprefix "
            "credentialprovider credentialprovideridentifier "
            "credentialprovidervendor credentialsscope forgotpasswordlink "
            "httptokens httptokensenforced idtoken instancerolecredentialsprovider "
            "japanesetokenizationdictionary loganomalytoken oauthtokenendpointurl "
            "pretokengeneration secretpolicy tokenendpoint "
            "tokenendpointauthenticationmethod tokenendpointauthenticationscheme "
            "tokenendpointurl tokenproviderurl tokenreference tokenrotation "
            "tokenstandard tokenstring tokenurl validationtokenhost "
            "verificationtoken"
        ).split()
    },
}

# Documented by AWS as a secret, a credential or a token that authorises a call;
# not masked by the deny-list today. Each name: one operation that returns it,
# and what the botocore documentation says. Rows for the final patch.
KNOWN_UNMASKED = {
    "presharedkey": "ec2:DescribeVpnConnections: the pre-shared key (PSK) of a VPN tunnel",
    "authkey": "directconnect:DescribeVirtualInterfaces: the authentication key for BGP",
    "passphrase": "ivs:GetChannel: auto-generated passphrase to enable encryption (SRT)",
    "secret": "codebuild:BatchGetProjects: the secret token of the repository webhook",
    "secrettoken": "codepipeline:ListWebhooks: the GitHub HMAC secret token",
    "webidentitytoken": "sts:GetWebIdentityToken: a signed JSON Web Token of the caller",
    "jwttoken": "datazone:GetConnection: the jwt token of the connection",
    "playergatewaytoken": "gamelift:GetPlayerConnectionDetails: access token a game client sends",
    "devicetoken": "chime-sdk-identity:DescribeAppInstanceUserEndpoint: push device token",
    "voipdevicetoken": "chime-sdk-identity:DescribeAppInstanceUserEndpoint: VOIP device token",
    "tokenvalue": "ec2:DescribeIpamExternalResourceVerificationTokens: token value",
    "billingtoken": "managedblockchain:GetAccessor: token used when making calls to the network",
    "tasktoken": "stepfunctions:GetActivityTask: token that authorises SendTaskSuccess and others",
    "callbacktoken": "sagemaker:ListPipelineExecutionSteps: pipeline token from the SQS queue",
    "workunittoken": "lakeformation:GetWorkUnits: a work token used to query the execution service",
    "registrationtoken": "marketplace-agreement:GetAgreementEntitlements: short-lived registration token",
    "exporttoken": "payment-cryptography:GetParametersForExport: token to initiate key export",
    "importtoken": "payment-cryptography:GetParametersForImport: token to initiate key import",
    "purchasetoken": "ec2:DescribeScheduledInstanceAvailability: the purchase token (two hours)",
    "offertoken": "bedrock:ListFoundationModelAgreementOffers: 'Offer token.' (the documentation does not say more)",
    "accesskey": "datasync:DescribeLocationObjectStorage: the access key to authenticate with object storage",
}


@lru_cache(maxsize=1)
def sweep():
    """``{normalised name: {"ops": [...], "sensitive": bool, "doc": str}}`` of
    the unmasked, secret-like string or blob fields of allowed operations."""
    session = botocore.session.get_session()
    guard = ReadOnlyGuard()
    found = defaultdict(lambda: {"ops": set(), "sensitive": False, "doc": ""})

    def walk(shape, seen):
        kind = shape.type_name
        if kind == "structure":
            if shape.name in seen:
                return
            seen = seen | {shape.name}
            for name, member in shape.members.items():
                yield name, member
                yield from walk(member, seen)
        elif kind == "list":
            yield from walk(shape.member, seen)
        elif kind == "map":
            yield from walk(shape.key, seen)
            yield from walk(shape.value, seen)

    for service in session.get_available_services():
        model = session.get_service_model(service)
        for operation in model.operation_names:
            if not guard.evaluate(service, operation)[0]:
                continue
            output = model.operation_model(operation).output_shape
            if output is None:
                continue
            for name, member in walk(output, frozenset()):
                norm = _NORM.sub("", name.lower())
                if member.type_name not in ("string", "blob"):
                    continue
                if not SECRET_LIKE.search(norm) or REFERENCE_SUFFIX.search(norm):
                    continue
                if is_secret_key(name):
                    continue
                entry = found[norm]
                entry["ops"].add(f"{service}:{operation}")
                entry["sensitive"] = entry["sensitive"] or bool(
                    member.metadata.get("sensitive")
                )
                if not entry["doc"]:
                    text = re.sub(r"<[^>]+>", "", member.documentation or "")
                    entry["doc"] = " ".join(text.split())[:200]
    return dict(found)


def test_every_secret_like_field_is_decided():
    undecided = {
        name: info
        for name, info in sweep().items()
        if name not in ALLOWED and name not in KNOWN_UNMASKED
    }
    report = "\n".join(
        f"  {name}: {sorted(info['ops'])[0]} (AWS marks it sensitive: "
        f"{info['sensitive']}) {info['doc']!r}"
        for name, info in sorted(undecided.items())
    )
    assert not undecided, (
        "Secret-like fields the deny-list does not mask and the sweep has no "
        "decision for. Add each to ALLOWED (with the reason) or to KNOWN_UNMASKED "
        "(and report it as a row for the patch):\n" + report
    )


def test_a_name_is_not_in_both_lists():
    assert not set(ALLOWED) & set(KNOWN_UNMASKED)


@pytest.mark.parametrize("name", sorted(KNOWN_UNMASKED))
def test_a_known_unmasked_field_is_still_unmasked(name):
    """When the deny-list learns the name, remove it from KNOWN_UNMASKED."""
    assert not is_secret_key(name), f"{name} is masked now: remove it from the list"
    value = "planted-sweep-secret-91c2"
    masked, count = mask_resource({"Thing": {name: value}})
    assert masked["Thing"][name] == value and count == 0
    assert MASK not in str(masked)


@pytest.mark.parametrize("name", sorted(KNOWN_UNMASKED))
def test_a_known_unmasked_field_is_still_returned_by_an_allowed_operation(name):
    """The entries are findings of the installed botocore, not guesses."""
    found = sweep()
    if name not in found:
        pytest.skip(f"{name} is not in this botocore's models")
    assert found[name]["ops"]


def test_the_sweep_sees_the_models_and_the_known_masked_names():
    session = botocore.session.get_session()
    assert len(session.get_available_services()) > 300
    for name in ("SecretAccessKey", "MasterUserPassword", "ParameterValue"):
        assert is_secret_key(name)
    assert "nexttoken" in sweep()
