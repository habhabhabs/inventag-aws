"""v1.5.0 (plan section 0 and the P6 row): ``scope.filters`` in tag policies.

The entries are the policy language's filters (``type: value`` only). A row
the filters leave out is out of scope; a row they cannot decide is counted as
not evaluated, never as compliant or non-compliant. A policy without
``scope.filters`` gives what v1.4.3 gave.
"""

import datetime as dt
import logging

import pytest

from inventag.templating.errors import TemplateError
from inventag.templating.runner import load_templates
from inventag.templating.tag_policy import evaluate

from .conftest import write

NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
A = "111111111111"


def row(i, state=None, tags=None, region="us-east-1", raw=True):
    found = {
        "service": "EC2",
        "resource_type": "Instance",
        "resource_id": f"i-{i}",
        "resource_name": f"vm-{i}",
        "arn": f"arn:aws:ec2:{region}:{A}:instance/i-{i}",
        "region": region,
        "account_id": A,
        "tags": tags if tags is not None else {},
    }
    if raw:
        found["raw_data"] = {"State": {"Name": state}} if state else {}
    return found


def policy(user_dir, registry, scope, name="p"):
    write(
        user_dir / f"{name}.yaml",
        "format_version: 1\nkind: tag-policy\n"
        f"name: {name}\nspec:\n  required_tags:\n    - key: Owner\n"
        f"  scope:\n{scope}",
    )
    return registry.resolve(name)


RUNNING_ONLY = (
    "    services: [EC2]\n"
    "    filters:\n"
    "      - {key: raw_data.State.Name, op: eq, value: running}\n"
)


def test_filters_choose_the_rows_that_are_checked(user_dir, registry):
    rows = [row(1, "running"), row(2, "stopped"), row(3, "running", {"Owner": "a"})]
    report = evaluate(rows, policy(user_dir, registry, RUNNING_ONLY), now=NOW)
    assert [f.resource["resource_id"] for f in report.findings] == ["i-1", "i-3"]
    assert report.out_of_scope == 1
    assert report.not_evaluated == []
    assert (report.checked, report.compliant, report.non_compliant) == (2, 1, 1)


def test_a_row_the_filters_cannot_decide_is_counted_as_not_evaluated(
    user_dir, registry
):
    # an identity-only row (no raw_data) cannot say its state
    rows = [row(1, "running"), row(2, raw=False)]
    report = evaluate(rows, policy(user_dir, registry, RUNNING_ONLY), now=NOW)
    assert report.checked == 1
    assert report.out_of_scope == 0
    assert [(r["resource_id"], why) for r, why in report.not_evaluated] == [
        ("i-2", "identity_only")
    ]
    summary = report.to_dict()["summary"]
    assert summary["not_evaluated"] == 1
    assert summary["checked"] + summary["out_of_scope"] + 1 == len(rows)
    (entry,) = report.to_dict()["not_evaluated_resources"]
    assert entry["resource_id"] == "i-2"
    assert entry["reason"] == "identity_only"


def test_a_tag_filter_on_a_row_whose_tags_were_not_read_is_not_evaluated(
    user_dir, registry
):
    scope = "    filters:\n      - {key: 'tag:Team', op: eq, value: data}\n"
    units = [
        {
            "account": A,
            "service": "tagging",
            "region": "us-east-1",
            "source": "tagging-api",
            "outcome": "denied",
        }
    ]
    rows = [row(1, "running", {"Team": "data"}), row(2, "running", region="eu-west-1")]
    report = evaluate(
        rows, policy(user_dir, registry, scope), now=NOW, units_not_read=units
    )
    assert [(r["resource_id"], why) for r, why in report.not_evaluated] == [
        ("i-1", "tags_not_read")
    ]
    assert report.out_of_scope == 1  # eu-west-1: tags read, Team absent


def test_without_filters_the_report_is_the_v143_one(user_dir, registry):
    rows = [row(1, "running"), row(2, raw=False)]
    report = evaluate(rows, policy(user_dir, registry, "    services: [EC2]\n"))
    data = report.to_dict()
    assert "not_evaluated" not in data["summary"]
    assert "not_evaluated_resources" not in data
    assert report.checked == 2


def test_the_console_line_names_the_rows_not_evaluated(user_dir, registry, capsys):
    write(
        user_dir / "p.yaml",
        "format_version: 1\nkind: tag-policy\nname: p\nspec:\n"
        "  required_tags:\n    - key: Owner\n  scope:\n" + RUNNING_ONLY,
    )
    run = load_templates(["p"], registry)
    run.compliance = evaluate([row(1, "running"), row(2, raw=False)], run.policy)
    assert run.finish({}, logging.getLogger("t")) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "Tag policy 'p': 0 of 1 resources compliant (0.0%), 1 non-compliant, "
        "0 out of scope, 1 not evaluated (the scope's filters could not "
        "decide)."
    )


def test_the_console_line_without_filters_is_unchanged(user_dir, registry, capsys):
    write(
        user_dir / "p.yaml",
        "format_version: 1\nkind: tag-policy\nname: p\nspec:\n"
        "  required_tags:\n    - key: Owner\n",
    )
    run = load_templates(["p"], registry)
    run.compliance = evaluate([row(1, "running")], run.policy)
    assert run.finish({}, logging.getLogger("t")) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "Tag policy 'p': 0 of 1 resources compliant (0.0%), 1 non-compliant, "
        "0 out of scope."
    )


@pytest.mark.parametrize(
    "entry, message",
    [
        (
            "{type: required-tags, keys: [{key: Owner}]}",
            "filters take only type: value",
        ),
        ("{key: 'raw_data.[', op: eq, value: x}", "not a valid key"),
        ("just-text", "must be a mapping"),
    ],
)
def test_bad_filters_are_refused_with_their_path(user_dir, registry, entry, message):
    with pytest.raises(TemplateError) as error:
        policy(user_dir, registry, f"    filters:\n      - {entry}\n")
    text = str(error.value)
    assert message in text
    assert "spec.scope.filters[0]" in text


def test_filters_must_be_a_list(user_dir, registry):
    with pytest.raises(TemplateError) as error:
        policy(user_dir, registry, "    filters: {key: a, op: eq, value: b}\n")
    assert "spec.scope.filters" in str(error.value)
