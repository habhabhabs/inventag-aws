"""v1.3.1: 18 documented secret field names join the masking list.

The botocore sweep (T-11) found 21 field names that AWS documents as secrets
or tokens and that the deny-list did not mask. InvenTag never calls an
operation that returns one (proven by the n1 tests with a full moto run).
They are masked anyway, as defence in depth.

Three names are left out because they are broad: in an operation the guard
allows they also name a harmless field, which masking by name would hide
(``secret``: a Batch volume's secret reference; ``authKey``: the secret ARN
in a PCS Slurm configuration; ``AccessKey``: the key details of a GuardDuty
finding). They stay unmasked; InvenTag never reads the operations where
they hold a secret.
"""

import json

import pytest

from inventag.security.secret_values import MASK, is_secret_key, mask_resource

ADDED = {
    "PreSharedKey": "ec2:DescribeVpnConnections (VPN tunnel pre-shared key)",
    "passphrase": "ivs:GetChannel (SRT encryption passphrase)",
    "SecretToken": "codepipeline:ListWebhooks (GitHub HMAC secret)",
    "WebIdentityToken": "sts:GetWebIdentityToken",
    "jwtToken": "datazone:GetConnection (OAuth2 credentials)",
    "PlayerGatewayToken": "gamelift:GetPlayerConnectionDetails",
    "DeviceToken": "chime-sdk-identity:DescribeAppInstanceUserEndpoint",
    "VoipDeviceToken": "chime-sdk-identity:DescribeAppInstanceUserEndpoint",
    "TokenValue": "ec2:DescribeIpamExternalResourceVerificationTokens",
    "BillingToken": "managedblockchain:GetAccessor",
    "taskToken": "stepfunctions:GetActivityTask",
    "CallbackToken": "sagemaker:ListPipelineExecutionSteps",
    "WorkUnitToken": "lakeformation:GetWorkUnits",
    "registrationToken": "marketplace-agreement:GetAgreementEntitlements",
    "ExportToken": "payment-cryptography:GetParametersForExport",
    "ImportToken": "payment-cryptography:GetParametersForImport",
    "PurchaseToken": "ec2:DescribeScheduledInstanceAvailability",
    "offerToken": "bedrock:ListFoundationModelAgreementOffers",
}
LEFT_OUT = {
    "secret": {"secretName": "db-credentials", "optional": False},
    "authKey": {"secretArn": "arn:aws:secretsmanager:x", "secretVersion": "1"},
    "AccessKey": {"AccessKeyId": "AKIAEXAMPLE", "UserName": "u"},
}
VALUE = "v131-planted-secret-4c2d"


@pytest.mark.parametrize("name", sorted(ADDED))
def test_the_name_is_masked(name):
    assert is_secret_key(name)
    masked, count = mask_resource({"A": [{"Id": "x", name: VALUE}]})
    assert masked == {"A": [{"Id": "x", name: MASK}]} and count == 1


@pytest.mark.parametrize("name", sorted(ADDED))
def test_the_name_is_masked_inside_json_text(name):
    text = json.dumps({"Options": {name: VALUE}})
    masked, count = mask_resource({"Document": text})
    assert count == 1 and VALUE not in masked["Document"]


@pytest.mark.parametrize("name", sorted(ADDED))
def test_an_empty_value_stays(name):
    assert mask_resource({name: ""}) == ({name: ""}, 0)


@pytest.mark.parametrize("name", sorted(LEFT_OUT))
def test_a_broad_name_keeps_its_harmless_field(name):
    data = {"Thing": {name: LEFT_OUT[name]}}
    assert not is_secret_key(name)
    assert mask_resource(data) == (data, 0)


def test_the_documented_paths_are_masked():
    """The fields at the places the sweep found them."""
    vpn = {
        "VpnConnectionId": "vpn-1",
        "Options": {
            "TunnelOptions": [{"OutsideIpAddress": "x", "PreSharedKey": VALUE}]
        },
    }
    channel = {"arn": "a", "srt": {"endpoint": "e", "passphrase": VALUE}}
    webhook = {
        "definition": {
            "name": "w",
            "authenticationConfiguration": {"SecretToken": VALUE},
        }
    }
    for item in (vpn, channel, webhook):
        masked, count = mask_resource(item)
        assert count == 1 and VALUE not in json.dumps(masked)
