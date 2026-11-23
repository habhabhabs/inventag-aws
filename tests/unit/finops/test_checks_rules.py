"""The FinOps checks on hand-made rows: each not_evaluated reason, the 90-day
border of FIN-003, the join of FIN-005, units not read, order and summary."""

import datetime as dt

import pytest

from inventag.finops import checks

RUN = dt.datetime(2026, 11, 21, 12, 0, tzinfo=dt.timezone.utc)
ACCOUNT = "111122223333"
REGION = "ap-southeast-1"
ALL_TAGS = {
    "CostCenter": "CC-1234",
    "Owner": "platform",
    "Project": "inventory",
    "Environment": "prod",
}


def make(service, rtype, rid, raw, *, tags=None, region=REGION, account=ACCOUNT):
    return {
        "service": service,
        "resource_type": rtype,
        "resource_id": rid,
        "resource_name": f"name-{rid}",
        "arn": f"arn:aws:ec2:{region}:{account}:thing/{rid}",
        "region": region,
        "account_id": account,
        "source_account_id": account,
        "tags": dict(ALL_TAGS if tags is None else tags),
        "raw_data": raw,
        "source": "service-api",
        "detail_level": "full",
    }


def identity_row(arn, rid, tags=None):
    parts = arn.split(":")
    return {
        "service": "EC2",
        "resource_type": "Unknown",
        "resource_id": rid,
        "resource_name": None,
        "arn": arn,
        "region": parts[3],
        "account_id": parts[4],
        "tags": dict(ALL_TAGS if tags is None else tags),
        "raw_data": {"arn": arn},
        "source": "tagging-api",
        "detail_level": "identity",
    }


def volume(rid, state="available", **kw):
    raw = {"VolumeId": rid, "Attachments": []}
    if state is not None:
        raw["State"] = state
    return make("EC2", "Volume", rid, raw, **kw)


def address(rid, association=None, **kw):
    raw = {"AllocationId": rid, "PublicIp": "198.51.100.7"}
    if association:
        raw["AssociationId"] = association
    return make("VPC", "ElasticIP", rid, raw, **kw)


def snapshot(rid, start, **kw):
    raw = {"SnapshotId": rid, "OwnerId": ACCOUNT}
    if start is not None:
        raw["StartTime"] = start
    return make("EC2", "Snapshot", rid, raw, **kw)


def instance(rid, state="stopped", **kw):
    raw = {"InstanceId": rid}
    if state is not None:
        raw["State"] = {"Code": 80, "Name": state}
    return make("EC2", "Instance", rid, raw, **kw)


def lb_v2(name, arn=None, **kw):
    raw = {"LoadBalancerName": name}
    if arn is not None:
        raw["LoadBalancerArn"] = arn
    return make("ELBV2", "LoadBalancerV2", name, raw, **kw)


def target_group(name, lb_arns, **kw):
    raw = {"TargetGroupName": name}
    if lb_arns is not None:
        raw["LoadBalancerArns"] = lb_arns
    return make("ELBV2", "TargetGroup", name, raw, **kw)


def classic(name, instances, **kw):
    raw = {"LoadBalancerName": name}
    if instances is not None:
        raw["Instances"] = instances
    return make("ELB", "LoadBalancer", name, raw, **kw)


def unit(service, region=REGION, source="service-api", outcome="denied"):
    return {
        "account": ACCOUNT,
        "service": service,
        "region": region,
        "source": source,
        "outcome": outcome,
    }


def run(rows, units=(), started=RUN):
    return checks.run_checks(list(rows), list(units), started)


def of(result, policy):
    return [f for f in result["findings"] if f["policy"] == policy]


def counts(result, policy):
    s = next(s for s in result["summary"] if s["policy"] == policy)
    return s["fail"], s["not_evaluated"], s["pass"]


# ------------------------------------------------------------------ shape
def test_six_checks_with_fixed_ids():
    assert list(checks.CHECKS) == [f"FIN-00{i}" for i in range(1, 7)]
    assert checks.SNAPSHOT_AGE_DAYS == 90


def test_an_empty_scan_gives_six_zero_summaries_and_no_finding():
    result = run([])
    assert result["schema_version"] == checks.SCHEMA_VERSION == 1
    assert result["findings"] == []
    assert [s["policy"] for s in result["summary"]] == list(checks.CHECKS)
    assert all(
        (s["fail"], s["not_evaluated"], s["pass"]) == (0, 0, 0)
        for s in result["summary"]
    )


def test_a_finding_has_the_fields_of_the_v15_finding():
    (finding,) = of(run([volume("vol-1")]), "FIN-001")
    assert finding == {
        "policy": "FIN-001",
        "result": "fail",
        "reason": "",
        "account": ACCOUNT,
        "region": REGION,
        "service": "EC2",
        "resource_type": "Volume",
        "resource": "vol-1",
        "name": "name-vol-1",
        "message": "no attachment",
    }


def test_the_checks_do_not_change_the_rows():
    import copy

    rows = [volume("vol-1"), instance("i-1"), lb_v2("lb", "arn:lb")]
    before = copy.deepcopy(rows)
    run(rows, [unit("ec2")])
    assert rows == before


# ---------------------------------------------------------------- FIN-001
def test_fin_001_in_use_volume_passes():
    result = run([volume("vol-1", "in-use")])
    assert of(result, "FIN-001") == []
    assert counts(result, "FIN-001") == (0, 0, 1)


def test_fin_001_volume_without_state_is_not_evaluated_field_missing():
    (finding,) = of(run([volume("vol-1", None)]), "FIN-001")
    assert (finding["result"], finding["reason"]) == ("not_evaluated", "field_missing")
    assert finding["message"] == "State is not on the row"


# ---------------------------------------------------------------- FIN-002
def test_fin_002_associated_address_passes_and_free_one_fails():
    result = run([address("eipalloc-1", "eipassoc-1"), address("eipalloc-2")])
    (finding,) = of(result, "FIN-002")
    assert finding["resource"] == "eipalloc-2"
    assert finding["message"] == "no association"
    assert counts(result, "FIN-002") == (1, 0, 1)


def test_fin_002_empty_association_is_no_association():
    raw = {"AllocationId": "eipalloc-3", "PublicIp": "x", "AssociationId": ""}
    (finding,) = of(run([make("VPC", "ElasticIP", "eipalloc-3", raw)]), "FIN-002")
    assert finding["result"] == "fail"


def test_fin_002_row_without_public_ip_is_not_evaluated():
    raw = {"AllocationId": "eipalloc-4"}
    (finding,) = of(run([make("VPC", "ElasticIP", "eipalloc-4", raw)]), "FIN-002")
    assert (finding["result"], finding["reason"]) == ("not_evaluated", "field_missing")
    assert finding["message"] == "PublicIp is not on the row"


# ---------------------------------------------------------------- FIN-003
@pytest.mark.parametrize(
    "age, result",
    [
        (dt.timedelta(days=90), "pass"),
        (dt.timedelta(days=90, seconds=1), "fail"),
        (dt.timedelta(days=89, hours=23), "pass"),
        (dt.timedelta(days=400), "fail"),
    ],
)
def test_fin_003_border_is_more_than_90_days_before_the_run_start(age, result):
    found = run([snapshot("snap-1", RUN - age)])
    listed = of(found, "FIN-003")
    if result == "pass":
        assert listed == []
        assert counts(found, "FIN-003") == (0, 0, 1)
    else:
        assert [f["result"] for f in listed] == ["fail"]
        assert listed[0]["message"] == f"started {(RUN - age):%Y-%m-%d}"


def test_fin_003_reads_a_start_time_as_text_too():
    text = (RUN - dt.timedelta(days=200)).isoformat()
    (finding,) = of(run([snapshot("snap-1", text)]), "FIN-003")
    assert finding["result"] == "fail"


def test_fin_003_naive_start_time_counts_as_utc():
    naive = (RUN - dt.timedelta(days=91)).replace(tzinfo=None)
    (finding,) = of(run([snapshot("snap-1", naive)]), "FIN-003")
    assert finding["result"] == "fail"


@pytest.mark.parametrize("start", [None, "not a time", 12])
def test_fin_003_missing_or_unreadable_start_time_is_not_evaluated(start):
    (finding,) = of(run([snapshot("snap-1", start)]), "FIN-003")
    assert (finding["result"], finding["reason"]) == ("not_evaluated", "field_missing")
    assert finding["message"] == "StartTime is not on the row"


def test_fin_003_uses_the_start_time_it_is_given_not_the_clock():
    old = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
    result = run([snapshot("snap-1", old)], started=old + dt.timedelta(days=10))
    assert of(result, "FIN-003") == []


def test_run_start_without_a_time_zone_is_refused():
    with pytest.raises(ValueError):
        run([], started=RUN.replace(tzinfo=None))


# ---------------------------------------------------------------- FIN-004
def test_fin_004_running_passes_stopped_fails_stopping_passes():
    result = run(
        [instance("i-1", "running"), instance("i-2"), instance("i-3", "stopping")]
    )
    (finding,) = of(result, "FIN-004")
    assert (finding["resource"], finding["message"]) == ("i-2", "state stopped")
    assert counts(result, "FIN-004") == (1, 0, 2)


def test_fin_004_instance_without_state_is_not_evaluated():
    (finding,) = of(run([instance("i-1", None)]), "FIN-004")
    assert (finding["reason"], finding["message"]) == (
        "field_missing",
        "State is not on the row",
    )


# ---------------------------------------------------------------- FIN-005
def test_fin_005_v2_named_by_a_target_group_passes():
    rows = [lb_v2("a", "arn:a"), lb_v2("b", "arn:b"), target_group("tg", ["arn:a"])]
    result = run(rows)
    (finding,) = of(result, "FIN-005")
    assert (finding["resource"], finding["message"]) == (
        "b",
        "no target group names it",
    )
    assert counts(result, "FIN-005") == (1, 0, 1)


def test_fin_005_target_group_of_another_region_does_not_count():
    rows = [
        lb_v2("a", "arn:a"),
        target_group("tg", ["arn:a"], region="eu-west-1"),
    ]
    (finding,) = of(run(rows), "FIN-005")
    assert finding["result"] == "fail"


def test_fin_005_v2_without_its_arn_is_not_evaluated():
    (finding,) = of(run([lb_v2("a")]), "FIN-005")
    assert (finding["reason"], finding["message"]) == (
        "field_missing",
        "LoadBalancerArn is not on the row",
    )


def test_fin_005_target_group_without_its_list_makes_unnamed_v2_not_evaluated():
    rows = [lb_v2("a", "arn:a"), lb_v2("b", "arn:b"), target_group("tg", None)]
    result = run(rows)
    by = {f["resource"]: f for f in of(result, "FIN-005")}
    assert set(by) == {"a", "b"}
    for f in by.values():
        assert (f["result"], f["reason"]) == ("not_evaluated", "field_missing")
        assert f["message"] == "LoadBalancerArns is not on a target group row"


def test_fin_005_classic():
    rows = [
        classic("c1", [{"InstanceId": "i-1"}]),
        classic("c2", []),
        classic("c3", None),
    ]
    by = {f["resource"]: f for f in of(run(rows), "FIN-005")}
    assert by["c2"]["result"] == "fail"
    assert by["c2"]["message"] == "lists no instance"
    assert (by["c3"]["reason"], by["c3"]["message"]) == (
        "field_missing",
        "Instances is not on the row",
    )
    assert "c1" not in by


def test_fin_005_v2_in_a_region_whose_elbv2_listing_failed_is_not_evaluated():
    rows = [lb_v2("a", "arn:a")]
    found = of(run(rows, [unit("elbv2")]), "FIN-005")
    by_reason = sorted((f["resource"], f["reason"]) for f in found)
    assert by_reason == [("", "listing_not_read"), ("a", "listing_not_read")]


# ----------------------------------------------------------- identity_only
@pytest.mark.parametrize(
    "policy, arn",
    [
        ("FIN-001", f"arn:aws:ec2:{REGION}:{ACCOUNT}:volume/vol-9"),
        ("FIN-002", f"arn:aws:ec2:{REGION}:{ACCOUNT}:elastic-ip/eipalloc-9"),
        ("FIN-003", f"arn:aws:ec2:{REGION}:{ACCOUNT}:snapshot/snap-9"),
        ("FIN-004", f"arn:aws:ec2:{REGION}:{ACCOUNT}:instance/i-9"),
        (
            "FIN-005",
            f"arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:loadbalancer/app/x/1",
        ),
        (
            "FIN-005",
            f"arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:loadbalancer/classic-x",
        ),
    ],
)
def test_a_row_known_by_identity_only_is_not_evaluated(policy, arn):
    result = run([identity_row(arn, "r-9")])
    (finding,) = of(result, policy)
    assert (finding["result"], finding["reason"]) == ("not_evaluated", "identity_only")
    assert finding["message"] == "known by identity only (Tagging API)"
    assert counts(result, policy) == (0, 1, 0)


def test_an_identity_row_of_another_kind_is_in_no_resource_check():
    arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:queue-1"
    result = run([identity_row(arn, "queue-1")])
    for policy in ("FIN-001", "FIN-002", "FIN-003", "FIN-004", "FIN-005"):
        assert counts(result, policy) == (0, 0, 0)
    assert counts(result, "FIN-006") == (0, 0, 1)


# ---------------------------------------------------------- listing_not_read
@pytest.mark.parametrize(
    "service, policies",
    [
        ("ec2", ["FIN-001", "FIN-003", "FIN-004", "FIN-006"]),
        ("vpc", ["FIN-002", "FIN-006"]),
        ("elb", ["FIN-005", "FIN-006"]),
        ("elbv2", ["FIN-005", "FIN-006"]),
        ("s3", ["FIN-006"]),
    ],
)
def test_a_listing_not_read_gives_one_line_per_unit_and_check(service, policies):
    result = run([], [unit(service), unit(service, region="eu-west-1")])
    lines = [f for f in result["findings"] if f["reason"] == "listing_not_read"]
    assert sorted({f["policy"] for f in lines}) == policies
    for policy in policies:
        mine = [f for f in lines if f["policy"] == policy]
        assert [f["region"] for f in mine] == [REGION, "eu-west-1"]
        for f in mine:
            assert f["result"] == "not_evaluated"
            assert (f["service"], f["resource"], f["resource_type"]) == (
                service,
                "",
                "",
            )
            assert (
                f["message"] == f"{service} listing in {f['region']} not read (denied)"
            )
        assert counts(result, policy)[1] == 2


def test_a_failed_tagging_listing_is_a_unit_line_of_fin_006_only():
    result = run([], [unit("resourcegroupstaggingapi", source="tagging-api")])
    assert [f["policy"] for f in result["findings"]] == ["FIN-006"]
    assert result["findings"][0]["message"] == (
        f"resourcegroupstaggingapi listing in {REGION} not read (denied)"
    )


# ---------------------------------------------------------- FIN-006 tags
def test_fin_006_missing_keys_in_policy_order():
    row = volume("vol-1", "in-use", tags={"Owner": "x", "Name": "n"})
    (finding,) = of(run([row]), "FIN-006")
    assert finding["result"] == "fail"
    assert finding["message"] == "missing: CostCenter, Project, Environment"


def test_fin_006_a_wrong_value_is_not_a_missing_key():
    row = volume("vol-1", "in-use", tags={**ALL_TAGS, "Environment": "qa"})
    result = run([row])
    assert of(result, "FIN-006") == []
    assert counts(result, "FIN-006") == (0, 0, 1)


def test_fin_006_wrong_case_key_counts_as_missing():
    tags = {k: v for k, v in ALL_TAGS.items() if k != "Owner"}
    tags["owner"] = "x"
    (finding,) = of(run([volume("vol-1", "in-use", tags=tags)]), "FIN-006")
    assert finding["message"] == "missing: Owner"


def test_fin_006_tags_not_read_when_the_tagging_listing_of_the_region_failed():
    rows = [
        volume("vol-1", "in-use", tags={}),
        volume("vol-2", "in-use"),
        volume("vol-3", "in-use", tags={}, region="eu-west-1"),
    ]
    tagging = unit("resourcegroupstaggingapi", source="tagging-api")
    result = run(rows, [tagging])
    by = {f["resource"]: f for f in of(result, "FIN-006")}
    assert (by["vol-1"]["result"], by["vol-1"]["reason"]) == (
        "not_evaluated",
        "tags_not_read",
    )
    assert by["vol-1"]["message"] == f"tags of {REGION} not read in this run"
    assert "vol-2" not in by  # every key is there: the data proves it
    assert by["vol-3"]["result"] == "fail"  # its region's tags were read


def test_fin_006_global_row_is_tags_not_read_when_any_tagging_listing_failed():
    row = make("IAM", "Role", "role-1", {}, tags={}, region="global")
    tagging = unit("resourcegroupstaggingapi", region="us-east-1", source="tagging-api")
    (finding,) = [f for f in of(run([row], [tagging]), "FIN-006") if f["resource"]]
    assert finding["reason"] == "tags_not_read"


def test_fin_006_follows_the_policy_scope_and_skips_billing_rows():
    alias = make("KMS", "Alias", "alias/x", {}, tags={})
    billing = make("EC2", "Unknown", "billing-1", {}, tags={})
    billing["source"] = "billing"
    billing["detail_level"] = "identity"
    result = run([alias, billing])
    assert counts(result, "FIN-006") == (0, 0, 0)


def test_fin_006_reads_tags_given_as_a_list():
    row = volume("vol-1", "in-use", tags={})
    row["tags"] = [{"Key": k, "Value": v} for k, v in ALL_TAGS.items()]
    assert of(run([row]), "FIN-006") == []


# ------------------------------------------------------------ order
def test_findings_are_sorted_by_check_account_region_resource():
    rows = [
        volume("vol-b", tags={}),
        volume("vol-a", tags={}, region="eu-west-1"),
        volume("vol-c", tags={}, account="000000000000"),
        instance("i-1", tags={}),
    ]
    result = run(rows)
    keys = [
        (f["policy"], f["account"], f["region"], f["resource"])
        for f in result["findings"]
    ]
    assert keys == sorted(keys)
    assert run(list(reversed(rows))) == result


def test_the_output_has_no_value_from_raw_data_beyond_the_stated_facts():
    raw_secret = "s3cr3t-value"
    row = volume("vol-1", tags={})
    row["raw_data"]["KmsKeyId"] = raw_secret
    row["raw_data"]["Description"] = raw_secret
    text = repr(run([row]))
    assert raw_secret not in text


def test_the_reason_for_an_unread_listing_is_listing_not_read():
    result = run([lb_v2("a", "arn:a")], [unit("elbv2")])
    reasons = {f["reason"] for f in result["findings"]}
    assert reasons == {"listing_not_read"}
    assert "units_not_read" not in repr(result)


def test_without_a_run_start_time_fin_003_is_not_evaluated_and_others_run():
    rows = [snapshot("snap-1", RUN - dt.timedelta(days=400)), volume("vol-1")]
    result = checks.run_checks(rows, [], None)
    (snap,) = of(result, "FIN-003")
    assert (snap["result"], snap["reason"], snap["message"]) == (
        "not_evaluated",
        "field_missing",
        "the run has no start time",
    )
    assert [f["result"] for f in of(result, "FIN-001")] == ["fail"]
