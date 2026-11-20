"""W2 of reports/v14-plan-readonlyaccess.md: say exactly which IAM action was missing.

Part 1: ``iam_policy.action_for`` and the table of what ``ReadOnlyAccess`` does and does not
include. Part 2: ``inventag/security/permissions_report.py`` (pure: what the run saw in, a
sorted list and the run-notes lines out), with the golden text of the notes.

The fixture of the AWS managed policy (``tests/data/aws-managed/ReadOnlyAccess.json``) is
PROVISIONAL until the raw copy replaces it (``SOURCE.json`` says how). Not verified against
real AWS.
"""

import boto3
import pytest
from moto import mock_aws

from inventag.security.iam_policy import (
    LEDGER_CLIENT_SERVICES,
    NOT_IN_READONLYACCESS,
    READ_ONLY_ACTIONS,
    action_for,
    all_policy_actions,
    in_readonlyaccess,
)
from tests.policy_sim import matches_any, read_only_access_actions

GATEWAY = "apigateway:GET"


# ------------------------------------------------------------------------ action_for
@pytest.mark.parametrize(
    "service, operation, action",
    [
        # botocore names, as the guard and the ledger's detail records write them
        ("ec2", "DescribeVpcs", "ec2:DescribeVpcs"),
        ("lambda", "GetFunctionConfiguration", "lambda:GetFunctionConfiguration"),
        ("s3", "GetBucketLocation", "s3:GetBucketLocation"),
        ("resourcegroupstaggingapi", "GetResources", "tag:GetResources"),
        ("ce", "GetCostAndUsage", "ce:GetCostAndUsage"),
        ("pricing", "GetProducts", "pricing:GetProducts"),
        ("cloudwatch", "GetMetricStatistics", "cloudwatch:GetMetricStatistics"),
        # an IAM action whose name differs from the API name
        ("s3", "ListBuckets", "s3:ListAllMyBuckets"),
        ("s3", "GetBucketEncryption", "s3:GetEncryptionConfiguration"),
        ("stepfunctions", "ListStateMachines", "states:ListStateMachines"),
        ("efs", "DescribeFileSystems", "elasticfilesystem:DescribeFileSystems"),
        ("emr", "ListClusters", "elasticmapreduce:ListClusters"),
        ("opensearch", "ListDomainNames", "es:ListDomainNames"),
        # the ledger's snake_case operation names (the table writes them that way)
        ("ec2", "describe_vpcs", "ec2:DescribeVpcs"),
        ("s3", "list_buckets", "s3:ListAllMyBuckets"),
        ("kafka", "list_clusters_v2", "kafka:ListClustersV2"),
        # the ledger's service keys that are not botocore names
        ("vpc", "describe_subnets", "ec2:DescribeSubnets"),
        ("msk", "list_clusters_v2", "kafka:ListClustersV2"),
        ("cognito", "list_user_pools", "cognito-idp:ListUserPools"),
        ("wafv2-cloudfront", "list_web_acls", "wafv2:ListWebACLs"),
        # the classic and the v2 load balancer API share one IAM action
        (
            "elb",
            "describe_load_balancers",
            "elasticloadbalancing:DescribeLoadBalancers",
        ),
        ("elbv2", "DescribeTargetGroups", "elasticloadbalancing:DescribeTargetGroups"),
        # API Gateway authorises by HTTP verb
        ("apigateway", "get_rest_apis", GATEWAY),
        ("apigatewayv2", "GetApis", GATEWAY),
        # what is not in the policy file, and that ReadOnlyAccess may or may not include
        ("sts", "GetCallerIdentity", "sts:GetCallerIdentity"),
        ("sts", "AssumeRole", "sts:AssumeRole"),
        ("s3", "PutObject", "s3:PutObject"),
    ],
)
def test_action_for_names_the_iam_action_of_a_call(service, operation, action):
    assert action_for(service, operation) == action


@pytest.mark.parametrize(
    "service, operation",
    [
        (
            "iam",
            "GetAccountSummary",
        ),  # a real operation that InvenTag has no action for
        ("lambda", "delete_function"),  # a write: never an action of InvenTag
        ("ec2", "NoSuchOperation"),
        ("nosuchservice", "ListThings"),
        ("ec2", ""),  # a ledger entry that names a service but no operation
        ("", "DescribeVpcs"),
        ("ec2", None),
    ],
)
def test_action_for_is_none_when_the_action_is_not_known_and_never_guessed(
    service, operation
):
    assert action_for(service, operation) is None


def test_action_for_agrees_with_the_policy_file_for_every_action_in_it():
    for action, (service, operation) in READ_ONLY_ACTIONS.items():
        # the one action that two APIs share is answered by either
        assert action_for(service, operation) == action


def _discovery_table():
    """The discovery table of a ComprehensiveAWSDiscovery: key -> its configuration."""
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    with mock_aws():
        discovery = ComprehensiveAWSDiscovery(
            session=boto3.Session(region_name="us-east-1"), regions=["us-east-1"]
        )
        return discovery, discovery.service_discovery_patterns


def test_every_entry_of_the_discovery_table_maps_to_an_action_of_the_policy_file():
    """Ledger key and operation of each table entry give an action InvenTag's policy lists."""
    from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

    _, table = _discovery_table()
    assert len(table) > 40, "the discovery table was not read"
    policy = set(all_policy_actions())
    unmapped = []
    for key, config in sorted(table.items()):
        for operation_config in config["operations"]:
            spec = ComprehensiveAWSDiscovery._op_spec(operation_config)
            operations = [spec["op"]]
            if spec.get("per_parent"):
                operations.append(spec["per_parent"]["op"])
            for operation in operations:
                action = action_for(key, operation)
                if action not in policy:
                    unmapped.append((key, operation, action))
    assert not unmapped, (
        "table entries whose IAM action is unknown or not in READ_ONLY_ACTIONS: "
        f"{unmapped}"
    )


def test_the_ledger_services_that_are_not_botocore_names_are_exactly_those_of_the_table():
    """LEDGER_CLIENT_SERVICES holds every key whose client differs, and nothing else."""
    _, table = _discovery_table()
    different = {
        key: config["client_service"]
        for key, config in table.items()
        if config.get("client_service", key) != key
    }
    assert LEDGER_CLIENT_SERVICES == different


# ------------------------------------------------------------- what ReadOnlyAccess has
def test_the_three_actions_that_readonlyaccess_does_not_include_are_the_planned_three():
    assert set(NOT_IN_READONLYACCESS) == {
        "sts:AssumeRole",
        "s3:PutObject",
        "kms:GenerateDataKey",
    }
    for action, feature in NOT_IN_READONLYACCESS.items():
        assert feature and feature == feature.strip()
        assert in_readonlyaccess(action) is False


def test_provisional_the_table_agrees_with_the_readonlyaccess_fixture():
    """``in_readonlyaccess`` says what the fixture says, for every action InvenTag knows."""
    allow = read_only_access_actions()
    known = set(all_policy_actions()) | {"sts:GetCallerIdentity"}
    for action in sorted(known):
        assert in_readonlyaccess(action) is True, action
        assert matches_any(action, allow), f"the fixture does not grant {action}"
    for action in sorted(NOT_IN_READONLYACCESS):
        assert not matches_any(action, allow), f"the fixture grants {action}"


def test_in_readonlyaccess_does_not_answer_for_an_action_it_has_not_checked():
    assert in_readonlyaccess("newservice:ListThings") is None
    assert in_readonlyaccess("") is None


# ============================================================== permissions_report
import copy  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import socket  # noqa: E402

from inventag.security import permissions_report as pr  # noqa: E402

ACCOUNT = "123456789012"
OTHER = "222222222222"
DENIED = "AccessDenied"


def ledger(service, operation, source="service-api", region="us-east-1", **kw):
    """One coverage entry as ``CoverageEntry.to_dict`` writes it."""
    entry = {
        "account_id": ACCOUNT,
        "region": region,
        "source": source,
        "service": service,
        "resource_type": "",
        "operation": operation,
        "outcome": "denied",
        "count": 0,
        "error_code": DENIED,
        "seconds": 0.0,
    }
    entry.update(kw)
    return entry


def detail(service, operation, **kw):
    return ledger(service, operation, source="service-api-detail", **kw)


def line(entry):
    return {k: entry[k] for k in ("account", "action", "kind")}


def test_a_listing_a_detail_call_the_tagging_api_and_billing_are_named_by_their_action():
    found = pr.build(
        coverage=[
            ledger("ec2", "DescribeVpcs"),
            detail("s3", "GetBucketLocation"),
            ledger("resourcegroupstaggingapi", "GetResources", source="tagging-api"),
            ledger("ce", "GetCostAndUsage", source="billing", region="global"),
        ]
    )
    assert [(e["action"], e["kind"]) for e in found] == [
        ("ce:GetCostAndUsage", "billing"),
        ("ec2:DescribeVpcs", "listing"),
        ("s3:GetBucketLocation", "detail"),
        ("tag:GetResources", "tagging"),
    ]
    assert found[1] == {
        "account": ACCOUNT,
        "action": "ec2:DescribeVpcs",
        "service": "ec2",
        "operation": "DescribeVpcs",
        "regions": ["us-east-1"],
        "kind": "listing",
    }


def test_the_ledger_key_and_the_snake_case_operation_are_shown_as_the_botocore_names():
    found = pr.build(coverage=[ledger("msk", "list_clusters_v2")])
    assert found == [
        {
            "account": ACCOUNT,
            "action": "kafka:ListClustersV2",
            "service": "kafka",
            "operation": "ListClustersV2",
            "regions": ["us-east-1"],
            "kind": "listing",
        }
    ]


def test_regions_are_merged_and_sorted_and_a_repeated_denial_is_one_entry():
    found = pr.build(
        coverage=[
            ledger("ec2", "DescribeVpcs", region="us-west-2"),
            ledger("ec2", "DescribeVpcs", region="eu-west-1"),
            ledger("ec2", "DescribeVpcs", region="us-west-2"),
            ledger("vpc", "describe_vpcs", region="global"),
        ]
    )
    assert len(found) == 1
    assert found[0]["regions"] == ["eu-west-1", "global", "us-west-2"]


def test_an_operation_with_no_known_action_is_shown_by_its_api_name_and_has_no_action():
    found = pr.build(
        coverage=[
            ledger("newservice", "ListThings"),
            ledger("ec2", ""),  # a client that could not be made: no operation
        ]
    )
    assert [(e["action"], e["service"], e["operation"]) for e in found] == [
        (None, "ec2", ""),
        (None, "newservice", "ListThings"),
    ]


@pytest.mark.parametrize(
    "entry",
    [
        ledger("ec2", "DescribeVpcs", outcome="ok"),
        ledger("ec2", "DescribeVpcs", outcome="empty"),
        ledger("ec2", "DescribeVpcs", outcome="throttled", error_code="Throttling"),
        ledger("ec2", "DescribeVpcs", outcome="error", error_code="InternalError"),
        ledger("ec2", "DescribeVpcs", outcome="timeout", error_code=""),
        ledger("ec2", "DescribeVpcs", outcome="out_of_scope", error_code=""),
        # Cost Explorer that is not switched on is not a missing permission
        ledger("ce", "GetCostAndUsage", source="billing", error_code="OptInRequired"),
    ],
)
def test_only_a_denied_call_that_is_a_missing_permission_is_listed(entry):
    assert pr.build(coverage=[entry]) == []


def test_a_role_that_could_not_be_assumed_is_sts_assumerole_and_other_failures_are_not():
    found = pr.build(
        account_failures=[
            {"account_id": OTHER, "error_code": DENIED},
            {"account_id": "333333333333", "error_code": "InvalidClientTokenId"},
            {"account_id": "444444444444", "error_code": ""},
        ]
    )
    assert found == [
        {
            "account": OTHER,
            "action": "sts:AssumeRole",
            "service": "sts",
            "operation": "AssumeRole",
            "regions": [],
            "kind": "role",
        }
    ]


def test_an_upload_that_was_denied_is_s3_putobject_once_for_the_run_account():
    found = pr.build(
        upload_outcomes=[
            {"error_code": DENIED},
            {"error_code": DENIED},
            {"error_code": "NoSuchBucket"},
            {"error_code": ""},
        ],
        run_account=ACCOUNT,
    )
    assert [(e["account"], e["action"], e["kind"]) for e in found] == [
        (ACCOUNT, "s3:PutObject", "upload")
    ]


def test_the_cost_analysis_denials_are_pricing_billing_or_analysis_by_service():
    found = pr.build(
        cost_denials=[
            ("pricing", "GetProducts", DENIED),
            ("cloudwatch", "GetMetricStatistics", "AccessDeniedException"),
            ("ce", "GetCostAndUsage", DENIED),
            ("pricing", "GetProducts", "OptInRequired"),
            ("pricing", "GetProducts", "Throttling"),
        ],
        run_account=ACCOUNT,
    )
    assert [(e["action"], e["kind"]) for e in found] == [
        ("ce:GetCostAndUsage", "billing"),
        ("cloudwatch:GetMetricStatistics", "analysis"),
        ("pricing:GetProducts", "pricing"),
    ]
    assert {e["account"] for e in found} == {ACCOUNT}


def test_an_analysis_denial_names_its_region():
    found = pr.build(
        analysis_denials=[
            ("elasticache", "DescribeCacheSubnetGroups", DENIED, "us-east-1"),
            ("elasticache", "DescribeCacheSubnetGroups", DENIED, "eu-west-1"),
        ],
        run_account=ACCOUNT,
    )
    assert found == [
        {
            "account": ACCOUNT,
            "action": "elasticache:DescribeCacheSubnetGroups",
            "service": "elasticache",
            "operation": "DescribeCacheSubnetGroups",
            "regions": ["eu-west-1", "us-east-1"],
            "kind": "analysis",
        }
    ]


def test_a_run_time_listing_of_a_billed_service_is_the_optional_kind():
    found = pr.build(
        coverage=[ledger("kendra", "list_indices", source=pr.OPTIONAL_SOURCE)]
    )
    assert [(e["kind"], e["action"]) for e in found] == [("optional", None)]


def test_the_same_action_from_two_sources_is_one_entry_per_account_and_kind():
    found = pr.build(
        coverage=[ledger("ce", "GetCostAndUsage", source="billing", region="global")],
        cost_denials=[("ce", "GetCostAndUsage", DENIED)],
        run_account=ACCOUNT,
    )
    assert len(found) == 1 and found[0]["regions"] == ["global"]


def _everything():
    return dict(
        coverage=[
            ledger("ec2", "DescribeVpcs", region="us-west-2"),
            ledger("ec2", "DescribeVpcs", region="eu-west-1"),
            ledger("lambda", "list_functions", account_id=OTHER),
            detail("s3", "GetBucketLocation"),
            detail("lambda", "GetFunctionConfiguration", account_id=OTHER),
            ledger("resourcegroupstaggingapi", "GetResources", source="tagging-api"),
            ledger("newservice", "ListThings"),
        ],
        account_failures=[{"account_id": "333333333333", "error_code": DENIED}],
        upload_outcomes=[{"error_code": DENIED}],
        cost_denials=[("pricing", "GetProducts", DENIED)],
        analysis_denials=[("elasticache", "DescribeCacheSubnetGroups", DENIED, "x-1")],
        run_account=ACCOUNT,
    )


def test_the_list_is_sorted_and_does_not_depend_on_the_order_of_the_input():
    reference = pr.build(**_everything())
    keys = [(e["account"], e["action"] is None, e["action"] or "") for e in reference]
    assert keys == sorted(keys)
    rng = random.Random(7)
    for _ in range(5):
        data = _everything()
        for name in ("coverage", "account_failures", "upload_outcomes"):
            rng.shuffle(data[name])
        assert pr.build(**data) == reference


def test_build_changes_nothing_it_is_given_and_makes_no_network_call(monkeypatch):
    data = _everything()
    before = copy.deepcopy(data)

    def refuse(*args, **kwargs):
        raise AssertionError("permissions_report.build opened a socket")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    first = pr.build(**data)
    assert data == before
    assert pr.build(**data) == first


def test_the_result_is_plain_json_with_the_six_keys_and_no_error_text():
    data = _everything()
    data["upload_outcomes"] = [
        {
            "error_code": DENIED,
            "error": "User: arn:aws:iam::123456789012:user/x is not authorized to perform: s3:PutObject",
        }
    ]
    data["coverage"][0]["error"] = "An error occurred (AccessDenied) when calling"
    found = pr.build(**data)
    for entry in found:
        assert list(entry) == [
            "account",
            "action",
            "service",
            "operation",
            "regions",
            "kind",
        ]
        assert entry["kind"] in pr.KINDS
    text = json.dumps(found) + "\n".join(pr.notes(found))
    assert json.loads(json.dumps(found)) == found
    for forbidden in ("User:", "not authorized", "An error occurred", "arn:aws"):
        assert forbidden not in text


def test_the_kinds_are_the_planned_nine():
    assert set(pr.KINDS) == {
        "listing",
        "detail",
        "tagging",
        "billing",
        "pricing",
        "analysis",
        "role",
        "upload",
        "optional",
    }


# --------------------------------------------------------------------- run notes
IN = "All of them are in the AWS managed policy ReadOnlyAccess."


def test_golden_notes_of_a_scan_that_lost_reads_that_readonlyaccess_includes():
    found = pr.build(
        coverage=[
            ledger("resourcegroupstaggingapi", "GetResources", source="tagging-api"),
            ledger("ce", "GetCostAndUsage", source="billing", region="global"),
            detail("s3", "GetBucketLocation"),
            detail("lambda", "GetFunctionConfiguration"),
        ],
        cost_denials=[("pricing", "GetProducts", DENIED)],
        run_account=ACCOUNT,
    )
    assert pr.notes(found) == [
        "Permissions: 5 action(s) were not allowed for account 123456789012: "
        "ce:GetCostAndUsage, lambda:GetFunctionConfiguration, pricing:GetProducts, "
        "s3:GetBucketLocation, tag:GetResources. "
        "Effect: some rows lack details; tags from the Tagging API are missing; "
        "billing checks are skipped; cost estimates are missing. " + IN
    ]


def test_golden_notes_of_a_role_that_could_not_be_assumed():
    found = pr.build(account_failures=[{"account_id": OTHER, "error_code": DENIED}])
    assert pr.notes(found) == [
        "Permissions: 1 action(s) were not allowed for account 222222222222: "
        "sts:AssumeRole. Effect: the account was not scanned. "
        "sts:AssumeRole is not in ReadOnlyAccess; it is needed only for "
        "scanning other accounts through a role."
    ]


def test_golden_notes_of_a_report_upload_that_was_denied():
    found = pr.build(upload_outcomes=[{"error_code": DENIED}], run_account=ACCOUNT)
    assert pr.notes(found) == [
        "Permissions: 1 action(s) were not allowed for account 123456789012: "
        "s3:PutObject. Effect: the reports were not uploaded. "
        "s3:PutObject is not in ReadOnlyAccess; it is needed only for "
        "uploading the reports (--s3-bucket)."
    ]


def test_golden_notes_that_mix_an_action_readonlyaccess_includes_with_one_it_does_not():
    found = pr.build(
        coverage=[ledger("s3", "ListBuckets")],
        upload_outcomes=[{"error_code": DENIED}],
        run_account=ACCOUNT,
    )
    assert pr.notes(found) == [
        "Permissions: 2 action(s) were not allowed for account 123456789012: "
        "s3:ListAllMyBuckets, s3:PutObject. "
        "Effect: resources of some services are missing; the reports were not uploaded. "
        "s3:PutObject is not in ReadOnlyAccess; it is needed only for "
        "uploading the reports (--s3-bucket). "
        "The other actions that InvenTag knows are in the AWS managed policy ReadOnlyAccess."
    ]


def test_golden_notes_name_an_unknown_call_by_its_api_name_and_say_so():
    found = pr.build(coverage=[ledger("newservice", "ListThings"), ledger("ec2", "")])
    assert pr.notes(found) == [
        "Permissions: 2 action(s) were not allowed for account 123456789012: "
        "ec2 (IAM action not known to InvenTag), "
        "newservice ListThings (IAM action not known to InvenTag). "
        "Effect: resources of some services are missing."
    ]


def test_golden_notes_with_known_and_unknown_calls_do_not_claim_that_all_are_included():
    found = pr.build(
        coverage=[ledger("ec2", "DescribeVpcs"), ledger("newservice", "ListThings")]
    )
    assert pr.notes(found) == [
        "Permissions: 2 action(s) were not allowed for account 123456789012: "
        "ec2:DescribeVpcs, newservice ListThings (IAM action not known to InvenTag). "
        "Effect: resources of some services are missing. "
        "The other actions that InvenTag knows are in the AWS managed policy ReadOnlyAccess."
    ]


def test_golden_notes_have_one_line_per_account_sorted_by_account():
    found = pr.build(
        coverage=[
            ledger("lambda", "ListFunctions", account_id=OTHER),
            ledger("ec2", "DescribeVpcs"),
        ]
    )
    assert pr.notes(found) == [
        "Permissions: 1 action(s) were not allowed for account 123456789012: "
        "ec2:DescribeVpcs. Effect: resources of some services are missing. " + IN,
        "Permissions: 1 action(s) were not allowed for account 222222222222: "
        "lambda:ListFunctions. Effect: resources of some services are missing. " + IN,
    ]


def test_golden_notes_of_a_denial_that_names_no_account_say_this_run():
    found = pr.build(upload_outcomes=[{"error_code": DENIED}])
    assert pr.notes(found)[0].startswith(
        "Permissions: 1 action(s) were not allowed for this run: s3:PutObject."
    )


def test_a_clean_run_has_no_entries_and_no_notes():
    found = pr.build(
        coverage=[ledger("ec2", "DescribeVpcs", outcome="ok", error_code="")],
        run_account=ACCOUNT,
    )
    assert found == [] and pr.notes(found) == []
    assert pr.build() == [] and pr.notes([]) == []
