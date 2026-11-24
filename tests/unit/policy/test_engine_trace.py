"""P1c (spec Amendment 3, 11.2 and 11.5): policies[].line, the trace for
``policy explain``, and the loader's public path expansion."""

import datetime as dt
import json
from pathlib import Path

from inventag.policy import engine, loader

GOLDEN = Path(__file__).resolve().parent / "golden"
NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
A = "111111111111"
R3 = f"arn:aws:ec2:us-east-1:{A}:instance/i-0aaa"
R4 = f"arn:aws:ec2:us-east-1:{A}:instance/i-0bbb"
L2 = f"arn:aws:elasticloadbalancing:us-east-1:{A}:loadbalancer/app/old/2"


def run(policy, snap="s1.json", **options):
    loaded = loader.load([GOLDEN / "policies" / policy], root=GOLDEN)
    data = json.loads((GOLDEN / snap).read_text())
    return engine.evaluate(data, loaded.policies, now=NOW, include_pass=True, **options)


def finding(result, resource):
    (f,) = [f for f in result["findings"] if f["resource"] == resource]
    return f


def test_policies_carry_the_line_of_spec_id():
    (p,) = run("ex01.yaml")["policies"]
    assert p["line"] == 4  # "spec: {id: RDS-001, ..." is line 4 of ex01.yaml
    (p,) = run("fin-005.yaml", "s2.json")["policies"]
    text = (GOLDEN / "policies" / "fin-005.yaml").read_text().splitlines()
    assert text[p["line"] - 1].strip().startswith("id: FIN-005")


def test_without_trace_nothing_is_added():
    plain = run("ex02.yaml")
    off = run("ex02.yaml", trace=False)
    assert engine.dumps(plain) == engine.dumps(off)
    assert '"trace"' not in engine.dumps(plain)
    assert "out_of_scope_traces" not in plain


def test_the_trace_of_a_failed_row():
    f = finding(run("ex02.yaml", trace=True), R3)
    assert f["trace"] == [
        {"part": "resource", "kind": "services", "verdict": "true"},
        {"part": "resource", "kind": "resource_types", "verdict": "true"},
        {
            "part": "resource",
            "kind": "value",
            "key": "raw_data.State.Name",
            "verdict": "true",
        },
        {
            "part": "check",
            "kind": "value",
            "key": "raw_data.PublicIpAddress",
            "verdict": "false",
        },
    ]


def test_the_trace_holds_no_value_of_the_row():
    result = run("ex02.yaml", trace=True, trace_resources=[R4])
    traces = json.dumps(
        [f["trace"] for f in result["findings"]]
        + [e["trace"] for e in result["out_of_scope_traces"]]
    )
    for value in ("203.0.113.10", "running", "stopped", "t3.micro", "web-1"):
        assert value not in traces


def test_an_out_of_scope_row_asked_for_comes_back_with_its_trace():
    result = run("ex02.yaml", trace=True, trace_resources=[R4])
    (entry,) = result["out_of_scope_traces"]
    assert (entry["policy"], entry["resource"]) == ("EC2-001", R4)
    # the whole tree is given; the filter is the node that left the row out
    (selected,) = [
        n for n in entry["trace"] if n["part"] == "resource" and n["kind"] == "value"
    ]
    assert selected == {
        "part": "resource",
        "kind": "value",
        "key": "raw_data.State.Name",
        "verdict": "false",
    }
    # rows not asked for are not returned
    assert len(run("ex02.yaml", trace=True)["out_of_scope_traces"]) == 0


def test_the_trace_of_an_unknown_row_names_the_reason():
    f = finding(
        run("ex10.yaml", trace=True),
        "arn:aws:ec2:ap-southeast-1:222222222222:instance/i-0ccc",
    )
    assert f["trace"][-1] == {
        "part": "check",
        "kind": "value",
        "key": "tag:Owner",
        "verdict": "unknown",
        "reason": "tags_not_read",
    }


def test_the_trace_of_a_tree():
    f = finding(run("fin-005.yaml", "s2.json", trace=True), L2)
    (top,) = [n for n in f["trace"] if n["part"] == "check"]
    assert top["kind"] == "or" and top["verdict"] == "false"
    first, second = top["children"]
    assert [c["kind"] for c in first["children"]] == ["value", "require", "related"]
    assert [c["verdict"] for c in first["children"]] == ["true", "true", "false"]
    assert first["children"][2]["key"] == "raw_data.LoadBalancerArn"
    assert second["verdict"] == "false"


def test_the_loader_s_path_expansion_has_a_public_name():
    assert loader.expand_paths is loader._files
