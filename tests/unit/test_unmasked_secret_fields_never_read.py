"""The 21 secret fields the deny-list does not mask never reach an output.

The sweep of the botocore models (tests/unit/test_secret_field_sweep.py, T-11)
lists 21 fields that AWS documents as secrets or tokens and that
``inventag/security/secret_values.py`` does not mask (``PreSharedKey``,
``WebIdentityToken``, ``SecretToken`` ...). A field matters only if InvenTag
calls an operation whose response holds it. This file shows it does not:

1. A full CLI run under moto (Excel, Word, state snapshot, log file, console)
   with Cost Explorer answering that every service of the 21 fields has spend,
   so the billing-driven dynamic discovery runs for them. Every API call is
   recorded; a call to one of the 21 operations would get a response holding a
   planted value. None of them is called and no planted value is in any file.
   A control field planted in a response that IS read shows the scan finds a
   value that gets through.
2. The generic operation pickers (dynamic discovery, its sequential fallback,
   the intelligent engine) never pick one of the 21 operations, or pick one
   that has required parameters (it is called without any, so botocore
   rejects it before a request is sent).

The pickers choose by position in the installed botocore's operation list,
so a boto3 upgrade can change what they pick: these tests then fail.
Not verified against a real AWS account: what each response holds at run time.
"""

import io
import logging
import os
import zipfile

import boto3
import botocore.client
import pytest
from botocore.awsrequest import AWSResponse

from tests.integration.templating.test_report_templates import run_inventag

# name: (service, operation, path of the field in the response).
# Every operation of an installed-botocore model that returns the field and
# that the read-only guard allows.
FIELDS = {
    "presharedkey": [
        (
            "ec2",
            "DescribeVpnConnections",
            "VpnConnections.[].Options.TunnelOptions.[].PreSharedKey",
        ),
        (
            "securityhub",
            "GetFindings",
            "Findings.[].Resources.[].Details.AwsEc2VpnConnection.Options"
            ".TunnelOptions.[].PreSharedKey",
        ),
    ],
    "authkey": [
        ("directconnect", "DescribeVirtualInterfaces", "virtualInterfaces.[].authKey")
    ],
    "passphrase": [
        ("ivs", "BatchGetChannel", "channels.[].srt.passphrase"),
        ("ivs", "GetChannel", "channel.srt.passphrase"),
        ("ivs", "GetStreamSession", "streamSession.channel.srt.passphrase"),
    ],
    "secret": [("codebuild", "BatchGetProjects", "projects.[].webhook.secret")],
    "secrettoken": [
        (
            "codepipeline",
            "ListWebhooks",
            "webhooks.[].definition.authenticationConfiguration.SecretToken",
        )
    ],
    "webidentitytoken": [("sts", "GetWebIdentityToken", "WebIdentityToken")],
    "jwttoken": [
        (
            "datazone",
            "GetConnection",
            "physicalEndpoints.[].glueConnection.authenticationConfiguration"
            ".oAuth2Properties.oAuth2Credentials.jwtToken",
        ),
        (
            "datazone",
            "ListConnections",
            "items.[].physicalEndpoints.[].glueConnection"
            ".authenticationConfiguration.oAuth2Properties.oAuth2Credentials"
            ".jwtToken",
        ),
    ],
    "playergatewaytoken": [
        (
            "gamelift",
            "GetPlayerConnectionDetails",
            "PlayerConnectionDetails.[].PlayerGatewayToken",
        )
    ],
    "devicetoken": [
        (
            "chime-sdk-identity",
            "DescribeAppInstanceUserEndpoint",
            "AppInstanceUserEndpoint.EndpointAttributes.DeviceToken",
        )
    ],
    "voipdevicetoken": [
        (
            "chime-sdk-identity",
            "DescribeAppInstanceUserEndpoint",
            "AppInstanceUserEndpoint.EndpointAttributes.VoipDeviceToken",
        )
    ],
    "tokenvalue": [
        (
            "ec2",
            "DescribeIpamExternalResourceVerificationTokens",
            "IpamExternalResourceVerificationTokens.[].TokenValue",
        )
    ],
    "billingtoken": [("managedblockchain", "GetAccessor", "Accessor.BillingToken")],
    "tasktoken": [("stepfunctions", "GetActivityTask", "taskToken")],
    "callbacktoken": [
        (
            "sagemaker",
            "ListPipelineExecutionSteps",
            "PipelineExecutionSteps.[].Metadata.Callback.CallbackToken",
        )
    ],
    "workunittoken": [
        ("lakeformation", "GetWorkUnits", "WorkUnitRanges.[].WorkUnitToken")
    ],
    "registrationtoken": [
        (
            "marketplace-agreement",
            "GetAgreementEntitlements",
            "agreementEntitlements.[].registrationToken",
        )
    ],
    "exporttoken": [("payment-cryptography", "GetParametersForExport", "ExportToken")],
    "importtoken": [("payment-cryptography", "GetParametersForImport", "ImportToken")],
    "purchasetoken": [
        (
            "ec2",
            "DescribeScheduledInstanceAvailability",
            "ScheduledInstanceAvailabilitySet.[].PurchaseToken",
        )
    ],
    "offertoken": [
        ("bedrock", "ListFoundationModelAgreementOffers", "offers.[].offerToken")
    ],
    "accesskey": [("datasync", "DescribeLocationObjectStorage", "AccessKey")],
}
TARGETS = {(s, o): (name, p) for name, rows in FIELDS.items() for s, o, p in rows}
SERVICES = sorted({s for s, _ in TARGETS})

# Cost Explorer names whose billing code is a client name of these services.
BILLED = [
    "AWS Direct Connect",
    "AWS CodePipeline",
    "AWS CodeBuild",
    "Amazon SageMaker",
    "AWS Security Hub",
    "Amazon GameLift",
    "AWS DataSync",
    "AWS Lake Formation",
    "Amazon Bedrock",
    "AWS Step Functions",
    "Amazon Managed Blockchain",
    "Amazon DataZone",
    "Amazon Elastic Compute Cloud - Compute",
    "Amazon Interactive Video Service",
    "AWS Payment Cryptography",
]
# Answered by moto; every other call to a service above gets an empty answer.
MOTO_SERVICES = {"ec2", "sts", "codebuild", "codepipeline", "stepfunctions"}

CONTROL = "N1-CONTROL-VALUE-5e1b"


def planted(name):
    return f"N1-PLANTED-{name}-7f3a"


def build(path, value):
    """``{"A": [{"B": value, "Id": ..., "Name": ...}]}`` for ``A.[].B``.

    Each list item also gets an ``Id`` and a ``Name``, so discovery would keep
    it as a row if the operation were ever called."""
    head, _, rest = path.partition(".")
    if head == "[]":
        return [{**build(rest, value), "Id": "n1-item", "Name": "n1-item"}]
    return {head: build(rest, value) if rest else value}


class Recorder:
    """Records every API call that gets past parameter validation."""

    def __init__(self):
        self.calls = []

    def __call__(self, model, params, **_):
        service = model.service_model.service_name
        operation = model.name
        self.calls.append((service, operation))
        if (service, operation) in TARGETS:
            name, path = TARGETS[(service, operation)]
            return ok(build(path, planted(name)))
        if (service, operation) == ("ce", "GetCostAndUsage"):
            groups = [
                {
                    "Keys": [b],
                    "Metrics": {
                        "BlendedCost": {"Amount": "12.5", "Unit": "USD"},
                        "UsageQuantity": {"Amount": "3", "Unit": "N/A"},
                    },
                }
                for b in BILLED
            ]
            return ok({"ResultsByTime": [{"Groups": groups}]})
        if (service, operation) == ("codepipeline", "ListPipelines"):
            # Control: a value under a name the deny-list does not know, in a
            # response InvenTag reads. It must be found in the outputs.
            return ok({"pipelines": [{"name": "p1", "Note": CONTROL}]})
        if service in SERVICES and service not in MOTO_SERVICES:
            return ok({})
        return None


def ok(parsed):
    return AWSResponse("https://stub", 200, {}, None), parsed


@pytest.fixture
def recorder(monkeypatch):
    rec = Recorder()
    original = botocore.client.BaseClient._make_api_call

    def make_api_call(self, operation_name, api_params):
        self.meta.events.register_first(
            "before-call.*.*", rec, unique_id="n1-masking-recorder"
        )
        return original(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", make_api_call)
    return rec


@pytest.fixture
def account(monkeypatch):
    import moto

    for key in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    from inventag.security.read_only_guard import uninstall_global_guard

    uninstall_global_guard()
    with moto.mock_aws():
        role = boto3.client("iam").create_role(
            RoleName="r", AssumeRolePolicyDocument="{}"
        )["Role"]["Arn"]
        code = io.BytesIO()
        with zipfile.ZipFile(code, "w") as z:
            z.writestr("a.py", "def h(e, c): pass")
        boto3.client("lambda").create_function(
            FunctionName="fn",
            Runtime="python3.12",
            Role=role,
            Handler="a.h",
            Code={"ZipFile": code.getvalue()},
        )
        boto3.client("codebuild").create_project(
            name="cb",
            source={"type": "S3", "location": "bucket/src.zip"},
            artifacts={"type": "NO_ARTIFACTS"},
            environment={
                "type": "LINUX_CONTAINER",
                "image": "aws/codebuild/standard:7.0",
                "computeType": "BUILD_GENERAL1_SMALL",
            },
            serviceRole=role,
        )
        ec2 = boto3.client("ec2")
        gateway = ec2.create_customer_gateway(
            BgpAsn=65000, PublicIp="203.0.113.7", Type="ipsec.1"
        )["CustomerGateway"]["CustomerGatewayId"]
        vgw = ec2.create_vpn_gateway(Type="ipsec.1")["VpnGateway"]["VpnGatewayId"]
        ec2.create_vpn_connection(
            CustomerGatewayId=gateway, VpnGatewayId=vgw, Type="ipsec.1"
        )
        yield
    uninstall_global_guard()


def written(folder):
    """Text of every file under ``folder`` (Excel and Word unzipped)."""
    for root, _, files in os.walk(folder):
        for name in files:
            path = os.path.join(root, name)
            if name.endswith((".xlsx", ".docx")):
                with zipfile.ZipFile(path) as z:
                    yield path, b"".join(z.read(n) for n in z.namelist())
            else:
                with open(path, "rb") as handle:
                    yield path, handle.read()


@pytest.mark.parametrize("fallback", ["auto", "never"])
def test_a_full_run_never_calls_the_21_operations(
    account, recorder, monkeypatch, tmp_path, capsys, caplog, fallback
):
    caplog.set_level(logging.DEBUG)
    code = run_inventag(
        monkeypatch,
        tmp_path,
        "--create-excel",
        "--create-word",
        "--account-regions",
        "us-east-1",
        "--enable-state-management",
        "--log-file",
        str(tmp_path / "run.log"),
        # "never": no billing placeholder rows, so the dynamic discovery
        # probes every billed service without resources
        "--fallback-display",
        fallback,
    )
    assert code == 0
    called = set(recorder.calls)
    # The billing answer was read and drove the dynamic discovery
    assert ("ce", "GetCostAndUsage") in called
    if fallback == "never":
        probed = {s for s, _ in called}
        assert {"directconnect", "securityhub", "datasync", "gamelift"} <= probed
    assert not called & set(TARGETS), sorted(called & set(TARGETS))

    files = dict(written(tmp_path))
    assert any(p.endswith(".xlsx") for p in files)
    assert any(p.endswith(".docx") for p in files)
    assert any("state" in p and p.endswith(".json") for p in files)
    assert str(tmp_path / "run.log") in files
    console = capsys.readouterr()
    texts = {**files, "stdout": console.out.encode(), "stderr": console.err.encode()}
    texts["log records"] = caplog.text.encode()
    for name in FIELDS:
        assert [p for p, d in texts.items() if planted(name).encode() in d] == []
    # The scan finds a value that does get through (the control)
    assert [p for p, d in texts.items() if CONTROL.encode() in d]


def _session():
    return boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    )


def _required(service, operation):
    model = _session().client(service).meta.service_model
    shape = model.operation_model(operation).input_shape
    return list(shape.required_members) if shape else []


@pytest.mark.parametrize("service,operation", sorted(TARGETS))
def test_no_generic_picker_sends_one_of_the_21_operations(service, operation):
    from inventag.discovery.intelligent_discovery import IntelligentAWSDiscovery
    from inventag.discovery.inventory import AWSResourceInventory
    from inventag.discovery.optimized_dynamic_discovery import (
        OptimizedDynamicDiscovery,
    )

    session = _session()
    client = session.client(service)
    picked = []

    # Billing-driven dynamic discovery (the default CLI path)
    picked += OptimizedDynamicDiscovery(session=session)._get_optimized_operations(
        client, service
    )
    # Its sequential fallback
    inventory = AWSResourceInventory.__new__(AWSResourceInventory)
    inventory.session = session
    inventory.logger = logging.getLogger("n1-masking")
    inventory._call_operation_and_extract_resources = lambda c, op, *a: picked.append(
        op
    )
    mapped = inventory._get_service_client_name(service)
    if mapped:
        inventory._discover_service_dynamically(mapped, service, "us-east-1")
    # The intelligent engine (not run by the CLI; library use only)
    engine = IntelligentAWSDiscovery(session=session, regions=["us-east-1"])
    engine._discover_via_operation = lambda c, op, *a: picked.append(op) or []
    engine.discover_service(service)

    # Each picker calls without parameters: an operation with required
    # parameters is rejected by botocore before any request.
    assert operation not in picked or _required(service, operation)


def test_the_static_discovery_tables_do_not_name_the_21_operations():
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    engine = ComprehensiveAWSDiscovery(session=_session(), regions=["us-east-1"])
    listed = set()
    for key, config in engine.service_discovery_patterns.items():
        service = config.get("client_service", key)
        for op in config["operations"]:
            spec = engine._op_spec(op)
            name = "".join(part.title() for part in spec["op"].split("_"))
            listed.add((service, name))
    assert listed and not listed & set(TARGETS)


def test_the_planted_paths_are_the_model_paths():
    """A typo in a path would make the run test prove nothing."""
    for (service, operation), (name, path) in TARGETS.items():
        shape = _session().client(service).meta.service_model
        shape = shape.operation_model(operation).output_shape
        for part in path.split("."):
            shape = shape.member if part == "[]" else shape.members[part]
        assert shape.type_name in ("string", "blob"), (service, operation, name)
        assert "".join(c for c in part.lower() if c.isalnum()) == name
    assert len(FIELDS) == 21
    assert build("A.[].B", "v") == {
        "A": [{"B": "v", "Id": "n1-item", "Name": "n1-item"}]
    }
