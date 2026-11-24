"""P3: writers for policy_findings_<ts>.{json,sarif,xml,md} and the text form
(spec 3.3 and 3.4). The goldens are in golden/outputs/."""

import copy
import json
import os
import re
import stat
import xml.etree.ElementTree as ET
from pathlib import Path

import jsonschema
import pytest

from inventag.policy import engine
from inventag.policy.outputs import (
    FORMATS,
    file_stem,
    findings_schema,
    render,
    sarif_schema,
    write,
)

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden"
OUT = GOLDEN / "outputs"
RESULTS = {
    "ex05": "result-ex05-s1.json",
    "ex09-ex10": "result-ex09-ex10-s1.json",
    "fin005": "result-fin005-s2.json",
}
EXT = {"json": "json", "sarif": "sarif", "xml": "xml", "md": "md", "text": "txt"}
SECRET = "hunter2-SECRET-VALUE"


def load(name):
    return json.loads((GOLDEN / RESULTS[name]).read_text())


def hostile():
    """A hand-built result with every result kind and hostile resource names."""
    result = load("ex09-ex10")
    evil = "web]\x1b[31m(http://x)|<b>\x07]]>&\"'\nline2"
    base = {
        "account": "111111111111",
        "region": "us-east-1",
        "service": "EC2",
        "resource_type": "Instance",
        "severity": "high",
        "policy": "EC2-002",
    }
    result["findings"] = [
        dict(
            base,
            result="fail",
            resource="arn:aws:ec2:us-east-1:111111111111:instance/" + evil,
            name=evil,
            message="EC2-002: condition not met: raw_data.Password",
            details=[
                {
                    "check": 0,
                    "key": "raw_data.Password",
                    "problem": "condition not met",
                    "type": "value",
                    "value": SECRET,
                },
                {
                    "check": 1,
                    "key": "raw_data.InstanceType",
                    "problem": "condition not met",
                    "type": "value",
                    "value": "m5.24xlarge",
                },
            ],
        ),
        dict(
            base,
            result="waived",
            resource="arn:aws:ec2:us-east-1:111111111111:instance/i-0w",
            name="i-0w",
            message="EC2-002: condition not met: tag:Owner",
            waiver={
                "reason": "legacy",
                "approved_by": "a@b.c",
                "expires": "2027-01-01",
                "file": "waivers.yaml",
            },
        ),
        dict(
            base,
            result="not_evaluated",
            severity="low",
            policy="EC2-003",
            resource="arn:aws:ec2:us-east-1:111111111111:instance/i-0n",
            name="i-0n",
            reason="tags_not_read",
            message="EC2-003: not evaluated (tags_not_read)",
        ),
    ]
    result["not_evaluated_units"] = [
        {
            "policy": "EC2-002",
            "account": "111111111111",
            "service": "EC2",
            "region": "eu-west-1",
            "reason": "listing_not_read",
            "outcome": "access_denied",
        }
    ]
    result["unused_waivers"] = [
        {
            "policy": "EC2-002",
            "resource": "arn:x",
            "expires": "2027-01-01",
            "why": "no match",
            "file": "waivers.yaml",
        }
    ]
    for policy in result["policies"]:
        policy["counts"] = {
            "pass": 0,
            "fail": 1 if policy["id"] == "EC2-002" else 0,
            "waived": 1 if policy["id"] == "EC2-002" else 0,
            "not_evaluated": 1 if policy["id"] == "EC2-003" else 0,
            "out_of_scope": 0,
        }
    return result


# ------------------------------------------------------------------ module
def test_formats_are_the_four_files_and_text():
    assert tuple(FORMATS) == ("json", "sarif", "xml", "md")


def test_file_stem_is_the_snapshot_timestamp_not_the_clock():
    assert file_stem(load("ex05")) == "policy_findings_20261120_000000"


@pytest.mark.parametrize(
    "stamp", ["../../etc/x", "a/b\\c", "2026-11-20", "", "x" * 500, "\x00\n"]
)
def test_file_stem_is_safe_for_any_timestamp(stamp):
    result = load("ex05")
    result["snapshot"]["timestamp"] = stamp
    stem = file_stem(result)
    assert re.fullmatch(r"policy_findings_[A-Za-z0-9._-]{1,100}", stem), stem
    assert ".." not in stem


# ------------------------------------------------------------------ schemas
def test_findings_schema_ships_with_a_urn_id():
    schema = findings_schema()
    assert schema["$id"].startswith("urn:")
    assert not re.match(r"https?:", schema["$id"])
    jsonschema.Draft202012Validator.check_schema(schema)


def test_findings_schema_file_is_in_the_package():
    import inventag.policy.outputs as pkg

    path = Path(pkg.__file__).parent / "schemas" / "policy-findings-1.json"
    assert json.loads(path.read_text()) == findings_schema()


def test_pyproject_ships_json_files_in_the_package():
    text = (HERE.parents[2] / "pyproject.toml").read_text()
    assert '"**/*.json"' in text


@pytest.mark.parametrize("name", sorted(RESULTS))
def test_json_output_validates_against_the_shipped_schema(name):
    jsonschema.validate(json.loads(render(load(name), "json")), findings_schema())


def test_hostile_result_validates_in_every_json_form():
    jsonschema.validate(json.loads(render(hostile(), "json")), findings_schema())


def test_schema_refuses_an_unknown_reason_and_a_missing_key():
    bad = load("ex09-ex10")
    bad["findings"][0]["reason"] = "because"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, findings_schema())
    bad = load("ex09-ex10")
    del bad["summary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, findings_schema())


def test_schema_accepts_the_two_reasons_of_amendment_1():
    result = load("ex09-ex10")
    for reason in ("field_missing", "listing_not_read"):
        result["findings"][2]["reason"] = reason
        jsonschema.validate(result, findings_schema())


def test_sarif_schema_is_our_own_and_has_no_remote_ref():
    schema = sarif_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    assert "http://" not in json.dumps(schema).replace("http://json-schema.org", "")
    assert schema["$id"].startswith("urn:")


# ------------------------------------------------------------------ json
@pytest.mark.parametrize("name", sorted(RESULTS))
def test_json_equals_the_engine_dump(name):
    result = load(name)
    assert render(result, "json") == engine.dumps(result)
    assert render(result, "json") == (GOLDEN / RESULTS[name]).read_text()


def test_json_is_byte_stable_and_does_not_change_its_input():
    result = hostile()
    before = copy.deepcopy(result)
    assert render(result, "json") == render(copy.deepcopy(result), "json")
    assert result == before


# ------------------------------------------------------------------ goldens
@pytest.mark.parametrize("fmt", ["sarif", "xml", "md", "text"])
@pytest.mark.parametrize("name", sorted(RESULTS))
def test_golden_output(name, fmt):
    expected = (OUT / f"{name}.{EXT[fmt]}").read_text()
    assert render(load(name), fmt) == expected


@pytest.mark.parametrize("fmt", ["sarif", "xml", "md", "text"])
def test_golden_of_the_hostile_result(fmt):
    expected = (OUT / f"hostile.{EXT[fmt]}").read_text()
    assert render(hostile(), fmt) == expected


@pytest.mark.parametrize("fmt", ["json", "sarif", "xml", "md", "text"])
def test_every_format_ends_with_one_newline_and_is_utf8(fmt):
    text = render(hostile(), fmt)
    assert text.endswith("\n") and not text.endswith("\n\n")
    text.encode("utf-8")


@pytest.mark.parametrize("fmt", ["json", "sarif", "xml", "md", "text"])
def test_no_clock_time_or_absolute_path_in_any_output(fmt):
    text = render(hostile(), fmt)
    assert not re.search(r"timestamp=|generatedAt|startTimeUtc|endTimeUtc", text)
    assert not re.search(r"(/home/|/tmp/|/Users/|[A-Z]:\\\\)", text)


# ------------------------------------------------------------------ SARIF
def sarif(result):
    return json.loads(render(result, "sarif"))


def test_sarif_validates_and_maps_as_in_spec_3_4():
    log = sarif(hostile())
    jsonschema.validate(log, sarif_schema())
    assert log["version"] == "2.1.0"
    assert len(log["runs"]) == 1
    driver = log["runs"][0]["tool"]["driver"]
    assert driver["name"] == "InvenTag"
    rule = driver["rules"][0]
    assert rule["id"] == "EC2-002"
    assert set(rule["properties"]) >= {"severity", "version", "sha256"}
    results = log["runs"][0]["results"]
    by = {(r["ruleId"], r["kind"]): r for r in results if "suppressions" not in r}
    fail = by[("EC2-002", "fail")]
    assert fail["level"] == "error"
    assert "suppressions" not in fail
    waived = [r for r in results if r.get("suppressions")][0]
    assert waived["suppressions"] == [{"kind": "external", "justification": "legacy"}]
    review = by[("EC2-003", "review")]
    assert review["level"] == "none"


@pytest.mark.parametrize(
    "severity,level",
    [
        ("critical", "error"),
        ("high", "error"),
        ("medium", "warning"),
        ("low", "note"),
        ("info", "note"),
    ],
)
def test_sarif_level_by_severity(severity, level):
    result = load("ex09-ex10")
    result["findings"][0]["severity"] = severity
    first = sarif(result)["runs"][0]["results"][0]
    assert first["kind"] == "fail" and first["level"] == level


def test_sarif_never_writes_pass():
    result = load("ex09-ex10")
    result["findings"][0]["result"] = "pass"
    kinds = {r["kind"] for r in sarif(result)["runs"][0]["results"]}
    assert "pass" not in kinds
    assert len(sarif(result)["runs"][0]["results"]) == 2


def test_sarif_location_and_fingerprint():
    import hashlib

    result = load("ex09-ex10")
    log = render(result, "sarif", policy_lines={"EC2-002": 4})
    first = json.loads(log)["runs"][0]["results"][0]
    loc = first["locations"][0]
    assert loc["physicalLocation"]["artifactLocation"]["uri"] == "policies/ex09.yaml"
    assert loc["physicalLocation"]["region"]["startLine"] == 4
    f = result["findings"][0]
    assert loc["logicalLocations"][0]["fullyQualifiedName"] == f["resource"]
    want = hashlib.sha256(
        f"{f['policy']}|{f['account']}|{f['resource']}".encode()
    ).hexdigest()
    assert first["partialFingerprints"] == {"inventag/v1": want}


def test_sarif_line_defaults_to_one_and_a_sarif_line_is_never_below_one():
    result = load("ex09-ex10")
    for policy in result["policies"]:  # the engine's line (P1c) taken away
        policy.pop("line", None)
    first = sarif(result)["runs"][0]["results"][0]
    assert first["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
    log = json.loads(render(result, "sarif", policy_lines={"EC2-002": 0}))
    assert (
        log["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"][
            "startLine"
        ]
        == 1
    )


def test_sarif_has_no_resource_values_even_with_show_values():
    text = render(hostile(), "sarif", show_values=True)
    assert SECRET not in text and "m5.24xlarge" not in text


# ------------------------------------------------------------------ JUnit
def junit(result):
    return ET.fromstring(render(result, "xml"))


def test_junit_one_suite_per_file_one_case_per_policy():
    root = junit(load("ex09-ex10"))
    suites = root.findall("testsuite")
    assert [s.get("name") for s in suites] == [
        "policies/ex09.yaml",
        "policies/ex10.yaml",
    ]
    for suite in suites:
        assert suite.get("time") == "0" and suite.get("timestamp") is None
        assert len(suite.findall("testcase")) == 1
        assert suite.find("testcase").get("time") == "0"


def test_junit_failure_skipped_and_pass():
    result = hostile()
    result["policies"][1]["file"] = "policies/ex10.yaml"
    root = junit(result)
    cases = {c.get("name"): c for c in root.iter("testcase")}
    assert cases["EC2-002"].find("failure") is not None
    assert cases["EC2-003"].find("skipped") is not None
    assert cases["EC2-003"].find("failure") is None
    result = load("ex09-ex10")
    result["findings"] = []
    result["policies"][0]["counts"].update(fail=0, not_evaluated=0)
    result["policies"][1]["counts"].update(fail=0, not_evaluated=0)
    for case in junit(result).iter("testcase"):
        assert list(case) == []


def test_junit_failure_text_lists_first_20_resources_and_the_count():
    result = load("ex09-ex10")
    base = result["findings"][0]
    result["findings"] = [
        dict(base, resource=f"arn:r{i:03d}", name=f"r{i:03d}") for i in range(25)
    ]
    result["policies"][0]["counts"]["fail"] = 25
    text = junit(result).find(".//failure").text
    assert "25" in text
    assert "arn:r019" in text and "arn:r020" not in text


def test_junit_survives_hostile_names_and_is_well_formed():
    text = render(hostile(), "xml")
    ET.fromstring(text)
    assert "\x07" not in text and "\x1b" not in text
    assert "<b>" not in text


def test_junit_has_no_values_even_with_show_values():
    text = render(hostile(), "xml", show_values=True)
    assert SECRET not in text and "m5.24xlarge" not in text


# ------------------------------------------------------------------ Markdown
def test_markdown_has_tables_and_the_exit_sentence():
    text = render(load("ex09-ex10"), "md")
    assert text.startswith("# ")
    assert "| Resource |" in text
    assert text.rstrip().splitlines()[-1].startswith("Exit code 8")


def test_markdown_caps_rows_per_policy_at_50():
    result = load("ex09-ex10")
    base = result["findings"][0]
    result["findings"] = [
        dict(base, resource=f"arn:r{i:03d}", name=f"r{i:03d}") for i in range(53)
    ]
    text = render(result, "md")
    assert "arn:r049" in text and "arn:r050" not in text
    assert "and 3 more" in text


def test_markdown_escapes_hostile_text():
    text = render(hostile(), "md")
    assert "](http://x)" not in text.replace("\\]", "")
    assert "<b>" not in text
    assert "\x1b" not in text and "\x07" not in text
    row = [ln for ln in text.splitlines() if "web" in ln and ln.startswith("|")]
    assert len(row) == 1 and "line2" in row[0]


# ------------------------------------------------------------------ text
def test_text_has_policy_lines_groups_and_last_sentence():
    lines = render(load("ex09-ex10"), "text").splitlines()
    assert any(ln.startswith("EC2-002") for ln in lines)
    assert lines[-1] == render(load("ex09-ex10"), "md").rstrip().splitlines()[-1]


@pytest.mark.parametrize("code", [0, 7, 8])
def test_the_last_line_names_the_exit_code(code):
    result = load("ex09-ex10")
    result["summary"]["exit_code"] = code
    for fmt in ("text", "md"):
        assert (
            render(result, fmt)
            .rstrip()
            .splitlines()[-1]
            .startswith(f"Exit code {code}")
        )


def test_text_has_no_terminal_control_characters():
    text = render(hostile(), "text")
    assert not re.search(r"[\x00-\x08\x0b-\x1f\x7f]", text)


# ------------------------------------------------------------------ values
@pytest.mark.parametrize("fmt", ["json", "sarif", "xml", "md", "text"])
def test_no_raw_value_without_show_values(fmt):
    text = render(hostile(), fmt)
    assert SECRET not in text and "m5.24xlarge" not in text


def test_the_writer_strips_a_value_the_engine_left_in():
    out = json.loads(render(hostile(), "json"))
    for finding in out["findings"]:
        for detail in finding.get("details", []):
            assert "value" not in detail


def test_show_values_shows_a_plain_value_in_json_md_text_only():
    for fmt in ("json", "md", "text"):
        assert "m5.24xlarge" in render(hostile(), fmt, show_values=True)


@pytest.mark.parametrize("fmt", ["json", "md", "text"])
def test_a_secret_key_stays_masked_with_show_values(fmt):
    text = render(hostile(), fmt, show_values=True)
    assert SECRET not in text
    assert "REDACTED" in text


def test_an_already_masked_value_stays_masked():
    result = hostile()
    result["findings"][0]["details"][0]["value"] = "***REDACTED***"
    for fmt in ("json", "md", "text"):
        text = render(result, fmt, show_values=True)
        assert "REDACTED" in text and SECRET not in text


def test_a_secret_nested_in_a_value_is_masked():
    result = hostile()
    result["findings"][0]["details"][1]["value"] = {"Password": SECRET, "a": 1}
    text = render(result, "json", show_values=True)
    assert SECRET not in text


def test_engine_result_without_show_values_has_no_value_end_to_end():
    out = render(load("ex05"), "json")
    assert '"value"' not in out


# ------------------------------------------------------------------ write
def test_write_makes_the_four_files_owner_only(tmp_path):
    paths = write(load("ex09-ex10"), tmp_path / "out")
    assert [p.name for p in paths] == [
        f"policy_findings_20261120_000000.{e}" for e in ("json", "sarif", "xml", "md")
    ]
    for path in paths:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "out").stat().st_mode) == 0o700
    assert paths[0].read_text() == render(load("ex09-ex10"), "json")


def test_write_only_the_formats_asked(tmp_path):
    paths = write(load("ex05"), tmp_path, formats=("sarif",))
    assert [p.suffix for p in paths] == [".sarif"]
    assert sorted(os.listdir(tmp_path)) == [p.name for p in paths]


def test_write_refuses_an_unknown_format(tmp_path):
    with pytest.raises(ValueError, match="unknown format"):
        write(load("ex05"), tmp_path, formats=("html",))
    assert os.listdir(tmp_path) == []


def test_write_does_not_follow_a_planted_link(tmp_path):
    target = tmp_path / "victim.txt"
    target.write_text("keep")
    link = tmp_path / "policy_findings_20261120_000000.json"
    link.symlink_to(target)
    with pytest.raises(OSError):
        write(load("ex09-ex10"), tmp_path, formats=("json",))
    assert target.read_text() == "keep"


def test_write_masks_like_render(tmp_path):
    for path in write(hostile(), tmp_path):
        assert SECRET not in path.read_text()


# ------------------------------------------------------- amendment 2 (10.1, 10.2)
def with_superseded():
    result = hostile()
    result["unused_waivers"].append(
        {
            "policy": "EC2-002",
            "resource": "arn:y",
            "expires": "2026-12-31",
            "why": "superseded",
            "by": "waivers-b.yaml",
            "file": "waivers.yaml",
        }
    )
    result["not_evaluated_units"][0]["from"] = "baseline"
    return result


def test_schema_accepts_superseded_with_by_and_a_baseline_unit():
    jsonschema.validate(
        json.loads(render(with_superseded(), "json")), findings_schema()
    )


def test_schema_refuses_an_unknown_why_and_a_non_string_by():
    result = with_superseded()
    result["unused_waivers"][-1]["why"] = "lost"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, findings_schema())
    result = with_superseded()
    result["unused_waivers"][-1]["by"] = 3
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, findings_schema())
    result = with_superseded()
    result["not_evaluated_units"][0]["from"] = "snapshot"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, findings_schema())


@pytest.mark.parametrize("fmt", ["sarif", "md", "text"])
def test_superseded_and_by_are_written(fmt):
    text = render(with_superseded(), fmt)
    assert "superseded" in text and "waivers-b.yaml" in text
    assert "baseline" in text


def test_sarif_with_superseded_still_validates():
    jsonschema.validate(sarif(with_superseded()), sarif_schema())


def test_junit_with_superseded_is_well_formed():
    ET.fromstring(render(with_superseded(), "xml"))


def test_golden_of_the_superseded_result():
    for fmt in ("sarif", "xml", "md", "text"):
        expected = (OUT / f"superseded.{EXT[fmt]}").read_text()
        assert render(with_superseded(), fmt) == expected


# ------------------------------------------------- amendment 3 (11.2): policies[].line
def with_lines():
    """The result as the engine will give it once policies[] carries `line`
    (P1c); faked here until then."""
    result = load("ex09-ex10")
    for policy, line in zip(result["policies"], (4, 9)):
        policy["line"] = line
    return result


def start_lines(log):
    return {
        r["ruleId"]: r["locations"][0]["physicalLocation"]["region"]["startLine"]
        for r in log["runs"][0]["results"]
    }


def test_sarif_reads_the_line_from_the_result():
    assert start_lines(sarif(with_lines())) == {"EC2-002": 4, "EC2-003": 9}


def test_policy_lines_argument_overrides_the_result():
    log = json.loads(render(with_lines(), "sarif", policy_lines={"EC2-002": 7}))
    assert start_lines(log) == {"EC2-002": 7, "EC2-003": 9}


def test_a_missing_or_bad_line_gives_one():
    result = with_lines()
    del result["policies"][0]["line"]
    result["policies"][1]["line"] = 0
    assert start_lines(sarif(result)) == {"EC2-002": 1, "EC2-003": 1}


def test_findings_schema_accepts_line_and_refuses_zero():
    jsonschema.validate(with_lines(), findings_schema())
    bad = with_lines()
    bad["policies"][0]["line"] = 0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, findings_schema())


def test_json_shows_line():
    out = json.loads(render(with_lines(), "json"))
    assert [p["line"] for p in out["policies"]] == [4, 9]


def test_golden_sarif_with_lines():
    expected = (OUT / "lines.sarif").read_text()
    assert render(with_lines(), "sarif") == expected
