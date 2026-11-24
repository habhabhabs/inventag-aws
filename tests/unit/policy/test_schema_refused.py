"""Files the loader must refuse (spec 7.1 V1 to V15, 9.6 V16 to V19), and the
limits of spec 2. Each message is ``file:line: field: problem``."""

import datetime as dt
import textwrap

import pytest

from inventag.policy import loader
from inventag.policy.schema import PolicyError

NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)

GOOD_CHECK = "check: [{type: value, key: raw_data.StorageEncrypted, value: true}]"


def write(folder, name, text):
    path = folder / name
    path.write_text(textwrap.dedent(text).lstrip())
    return path


def policy(folder, name="p.yaml", spec_lines=None, pid="RDS-001", check=GOOD_CHECK):
    lines = spec_lines or [f"id: {pid}", "severity: high", check]
    body = "\n".join("  " + line for line in lines)
    return write(
        folder,
        name,
        f"format_version: 1\nkind: policy\nname: {name[:-5]}\nspec:\n{body}\n",
    )


def refused(paths, root=None):
    with pytest.raises(PolicyError) as caught:
        loader.load(paths, root=root)
    return str(caught.value)


def refused_waivers(paths):
    with pytest.raises(PolicyError) as caught:
        loader.load_waivers(paths, NOW)
    return str(caught.value)


def test_a_good_file_loads(tmp_path):
    loaded = loader.load([policy(tmp_path)], root=tmp_path)
    (p,) = loaded.policies
    assert (p.id, p.severity, p.version, p.file) == ("RDS-001", "high", 1, "p.yaml")


def test_v1_actions(tmp_path):
    text = refused(
        [
            policy(
                tmp_path,
                spec_lines=[
                    "id: RDS-001",
                    "severity: high",
                    GOOD_CHECK,
                    "actions: [stop]",
                ],
            )
        ]
    )
    assert "InvenTag never changes resources; a policy has no actions." in text
    assert "p.yaml:8: spec.actions:" in text


@pytest.mark.parametrize("field", ["mode", "notify", "remediate"])
def test_the_other_action_fields(tmp_path, field):
    text = refused(
        [
            policy(
                tmp_path,
                spec_lines=["id: RDS-001", "severity: high", GOOD_CHECK, f"{field}: x"],
            )
        ]
    )
    assert "a policy has no actions" in text


def test_v2_id(tmp_path):
    assert "id must look like ABC-001" in refused([policy(tmp_path, pid="rds-1")])


def test_v3_duplicate_id(tmp_path):
    a = policy(tmp_path, "a.yaml")
    b = policy(tmp_path, "b.yaml")
    text = refused([a, b], root=tmp_path)
    assert "id RDS-001 is also used in a.yaml" in text


def test_v4_unknown_operator(tmp_path):
    text = refused(
        [
            policy(
                tmp_path,
                check="check: [{type: value, key: raw_data.X, op: matches, value: 1}]",
            )
        ]
    )
    assert "unknown operator 'matches'" in text
    assert (
        "eq, ne, gt, ge, lt, le, in, not-in, contains, glob, regex, regex-case" in text
    )


def test_v5_bad_regex(tmp_path):
    text = refused(
        [
            policy(
                tmp_path,
                check="check: [{type: value, key: resource_name, op: regex, value: '('}]",
            )
        ]
    )
    assert "not a valid regular expression" in text


def test_v6_in_needs_a_list(tmp_path):
    text = refused(
        [
            policy(
                tmp_path,
                check="check: [{type: value, key: tags.Env, op: in, value: prod}]",
            )
        ]
    )
    assert "'in' needs a list" in text


def test_v7_empty_check(tmp_path):
    assert "at least one check is needed" in refused(
        [policy(tmp_path, check="check: []")]
    )


def waiver_file(folder, entry):
    return write(
        folder,
        "w.yaml",
        "format_version: 1\nkind: waivers\nname: w\nspec:\n  waivers:\n"
        + "".join(
            f"    {'-' if i == 0 else ' '} {line}\n" for i, line in enumerate(entry)
        ),
    )


BASE_WAIVER = [
    "policy: RDS-001",
    'resource: "arn:aws:rds:eu-west-1:111111111111:db:db-orders"',
    'reason: "Migration to an encrypted instance."',
    "approved_by: platform-lead",
]


def test_a_good_waiver_loads(tmp_path):
    (w,) = loader.load_waivers(
        [waiver_file(tmp_path, BASE_WAIVER + ["expires: 2026-12-31"])], NOW
    )
    assert w.expires == dt.date(2026, 12, 31)
    assert w.file == "w.yaml"


def test_v8_waiver_without_expires(tmp_path):
    assert "expires is required" in refused_waivers(
        [waiver_file(tmp_path, BASE_WAIVER)]
    )


def test_v9_waiver_for_every_resource(tmp_path):
    entry = [line for line in BASE_WAIVER if not line.startswith("resource")]
    entry += ['resource: "*"', "account: '111111111111'", "expires: 2026-12-31"]
    assert "a waiver cannot match every resource" in refused_waivers(
        [waiver_file(tmp_path, entry)]
    )


def test_v10_glob_without_account(tmp_path):
    entry = [line for line in BASE_WAIVER if not line.startswith("resource")]
    entry += ['resource: "arn:aws:ec2:us-east-1:*:instance/i-*"', "expires: 2026-12-31"]
    assert "account is required when resource has a wildcard" in refused_waivers(
        [waiver_file(tmp_path, entry)]
    )


def test_waiver_more_than_366_days_ahead(tmp_path):
    text = refused_waivers(
        [waiver_file(tmp_path, BASE_WAIVER + ["expires: 2027-11-22"])]
    )
    assert "at most 366 days after now" in text


def test_waiver_reason_length(tmp_path):
    entry = [line for line in BASE_WAIVER if not line.startswith("reason")]
    entry += ["reason: short", "expires: 2026-12-31"]
    assert "10 to 300 characters" in refused_waivers([waiver_file(tmp_path, entry)])


def test_v11_set_path_outside_the_folder(tmp_path):
    folder = tmp_path / "policies"
    folder.mkdir()
    s = write(
        folder,
        "s.yaml",
        'format_version: 1\nkind: policy-set\nname: s\nspec:\n  policies: ["../../etc/x.yaml"]\n',
    )
    text = refused([s], root=folder)
    assert "must stay inside the template's folder" in text


def test_v12_sets_include_each_other(tmp_path):
    a = write(
        tmp_path,
        "a.yaml",
        "format_version: 1\nkind: policy-set\nname: a\nspec:\n  include: [b]\n",
    )
    b = write(
        tmp_path,
        "b.yaml",
        "format_version: 1\nkind: policy-set\nname: b\nspec:\n  include: [a]\n",
    )
    text = refused([a, b], root=tmp_path)
    assert "policy sets include each other: a -> b -> a" in text


def test_v13_unknown_placeholder(tmp_path):
    lines = ["id: RDS-001", "severity: high", GOOD_CHECK, 'message: "{raw_data.Name}"']
    text = refused([policy(tmp_path, spec_lines=lines)])
    assert "unknown placeholder" in text
    assert (
        "{name}, {resource}, {account}, {region}, {service}, {resource_type}, {policy}"
        in text
    )


def test_v14_value_from(tmp_path):
    text = refused(
        [
            policy(
                tmp_path,
                check="check: [{type: value, key: raw_data.X, value_from: 'https://x'}]",
            )
        ]
    )
    assert "unknown field 'value_from'" in text


def test_v15_baseline_without_change(tmp_path):
    text = refused([policy(tmp_path, check="check: [{type: baseline, change: []}]")])
    assert "change needs at least one of added, removed, modified" in text


def test_v16_related_without_keys(tmp_path):
    text = refused(
        [
            policy(
                tmp_path,
                check="check: [{type: related, rows: {services: [ELBV2]}, listing: elbv2}]",
            )
        ]
    )
    assert "related needs rows, their_key and my_key" in text


def test_v17_related_expect(tmp_path):
    check = (
        "check: [{type: related, rows: {services: [ELBV2]}, their_key: raw_data.A, "
        "my_key: raw_data.B, listing: elbv2, expect: some}]"
    )
    assert "expect must be any or none" in refused([policy(tmp_path, check=check)])


def test_v18_related_rows_with_filters(tmp_path):
    check = (
        "check: [{type: related, rows: {services: [ELBV2], filters: [{'tag:A': present}]}, "
        "their_key: raw_data.A, my_key: raw_data.B, listing: elbv2}]"
    )
    assert "rows of a related check take no filters" in refused(
        [policy(tmp_path, check=check)]
    )


def test_v19_empty_require(tmp_path):
    lines = ["id: RDS-001", "severity: high", "require: []", GOOD_CHECK]
    assert "require needs at least one key" in refused(
        [policy(tmp_path, spec_lines=lines)]
    )


def test_v19_require_key_that_does_not_parse(tmp_path):
    lines = ["id: RDS-001", "severity: high", "require: ['raw_data.[']", GOOD_CHECK]
    text = refused([policy(tmp_path, spec_lines=lines)])
    assert "spec.require.0" in text and "not a valid key" in text


# ----------------------------------------------------------------- limits
def test_file_size_limit(tmp_path):
    path = policy(tmp_path)
    path.write_text(path.read_text() + "#" * (256 * 1024))
    assert "larger than 256 KiB" in refused([path])


def test_aliases_are_refused(tmp_path):
    path = write(
        tmp_path,
        "p.yaml",
        """
        format_version: 1
        kind: policy
        name: p
        spec:
          id: RDS-001
          severity: high
          resource: &r {services: [RDS]}
          check: [{type: value, key: raw_data.X, value: *r}]
        """,
    )
    assert "YAML aliases are not allowed" in refused([path])


def test_more_than_500_policies(tmp_path):
    docs = "\n---\n".join(
        f"format_version: 1\nkind: policy\nname: p{i}\nspec:\n  id: RDS-{i:03d}\n  severity: low\n  {GOOD_CHECK}"
        for i in range(501)
    )
    path = write(tmp_path, "many.yaml", docs)
    assert "at most 500 policies" in refused([path])


def test_several_documents_in_one_file(tmp_path):
    docs = "\n---\n".join(
        f"format_version: 1\nkind: policy\nname: p{i}\nspec:\n  id: RDS-00{i}\n  severity: low\n  {GOOD_CHECK}"
        for i in range(1, 4)
    )
    loaded = loader.load([write(tmp_path, "three.yaml", docs)], root=tmp_path)
    assert [p.id for p in loaded.policies] == ["RDS-001", "RDS-002", "RDS-003"]


def test_check_and_group_limits(tmp_path):
    many = ", ".join(["{type: value, key: raw_data.X, value: 1}"] * 21)
    assert "at most 20" in refused([policy(tmp_path, check=f"check: [{many}]")])
    deep = "{type: value, key: raw_data.X, value: 1}"
    for _ in range(6):
        deep = "{and: [" + deep + "]}"
    assert "nested more than 5" in refused([policy(tmp_path, check=f"check: [{deep}]")])


def test_key_and_pattern_length(tmp_path):
    key = "raw_data." + "a" * 200
    assert "at most 200 characters" in refused(
        [policy(tmp_path, check=f"check: [{{type: value, key: {key}, value: 1}}]")]
    )
    pattern = "a" * 201
    check = f"check: [{{type: name-pattern, pattern: '{pattern}'}}]"
    assert "at most 200 characters" in refused([policy(tmp_path, check=check)])


def test_no_environment_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("INVENTAG_TEST_VALUE", "secret")
    path = policy(
        tmp_path,
        check="check: [{type: value, key: tags.Env, value: '${INVENTAG_TEST_VALUE}'}]",
    )
    (p,) = loader.load([path], root=tmp_path).policies
    assert p.check[0]["value"] == "${INVENTAG_TEST_VALUE}"


def test_the_error_names_file_and_line(tmp_path):
    text = refused([policy(tmp_path, pid="rds-1")])
    assert text.startswith("p.yaml:5: spec.id: ")


@pytest.mark.parametrize("group", ["and", "or", "not"])
def test_v20_a_nested_baseline_entry(tmp_path, group):
    check = f"check: [{{{group}: [{{type: baseline, change: [added]}}]}}]"
    text = refused([policy(tmp_path, check=check)])
    assert "a baseline check must be a top-level entry of check" in text


def test_a_top_level_baseline_entry_loads(tmp_path):
    check = "check: [{type: baseline, change: [added]}, {'tag:Owner': present}]"
    (p,) = loader.load([policy(tmp_path, check=check)], root=tmp_path).policies
    assert p.check[0]["type"] == "baseline"
