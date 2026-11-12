"""Tag-policy evaluation, the ``templates`` command and config application."""

import io
import logging

import pytest
import yaml

from inventag.cli.main import create_parser
from inventag.templating import cli as templates_cli
from inventag.templating.errors import TemplateError
from inventag.templating.runner import (
    apply_config,
    explicit_dests,
    load_templates,
)
from inventag.templating.tag_policy import check_value, evaluate

from .conftest import write


def test_finops_policy_on_sample_data(registry, sample_resources):
    report = evaluate(sample_resources, registry.resolve("finops-cost-allocation"))
    by_name = {f.resource.get("resource_name"): f for f in report.findings}
    assert by_name["acme-app-logs"].compliant
    reports = by_name["acme-reports"]
    assert not reports.missing
    assert any("'1234' does not match" in r for r in reports.invalid)
    assert any("'Production' is not one of" in r for r in reports.invalid)
    assert by_name["acme-data-lake"].missing == ["Project"]
    assert report.out_of_scope == 14  # KMS aliases are excluded
    assert report.checked + report.out_of_scope == len(sample_resources)


def test_allowed_values_case_handling():
    rule = {"key": "Environment", "allowed_values": ["prod"], "case_sensitive": False}
    assert check_value(rule, "PROD") is None
    assert check_value(dict(rule, case_sensitive=True), "PROD")
    assert check_value(
        {"key": "CC", "pattern": "CC-[0-9]{4}"}, "CC-12345"
    )  # full match


def test_key_with_wrong_case_is_explained(registry):
    policy = registry.resolve("security-baseline")
    report = evaluate(
        [{"service": "S3", "resource_type": "Bucket", "tags": {"owner": "x"}}], policy
    )
    finding = report.findings[0]
    assert "Owner" in finding.missing
    assert any("tag keys are case-sensitive" in r for r in finding.invalid)


def test_tags_as_aws_list_are_understood(registry):
    policy = registry.resolve("security-baseline")
    tags = [
        {"Key": "Owner", "Value": "a"},
        {"Key": "Environment", "Value": "dev"},
        {"Key": "DataClassification", "Value": "internal"},
    ]
    report = evaluate(
        [{"service": "EC2", "resource_type": "Instance", "tags": tags}], policy
    )
    assert report.compliant == 1


def test_scope_services_filter(registry, user_dir, sample_resources):
    path = write(
        user_dir / "s3only.yaml",
        "kind: tag-policy\nname: s3only\nextends: security-baseline\n"
        "spec:\n  scope:\n    services: [s3]\n",
    )
    report = evaluate(sample_resources, registry.resolve(str(path)))
    assert {f.resource["service"] for f in report.findings} == {"S3"}


# --------------------------------------------------------------- templates CLI


def run_cli(argv, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("INVENTAG_TEMPLATE_PATH", raising=False)
    out, err = io.StringIO(), io.StringIO()
    code = templates_cli.main(argv, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_list(monkeypatch, tmp_path):
    code, out, _ = run_cli(["list"], monkeypatch, tmp_path)
    assert code == 0
    for name in ("standard-bom", "finops-cost-allocation", "ci-pipeline"):
        assert name in out
    assert "Search order" in out
    code, out, _ = run_cli(["list", "--kind", "tag-policy"], monkeypatch, tmp_path)
    assert "standard-bom" not in out and "security-baseline" in out


def test_show_and_resolved(monkeypatch, tmp_path):
    code, out, _ = run_cli(["show", "executive-summary"], monkeypatch, tmp_path)
    assert code == 0 and "extends: standard-bom" in out
    code, out, _ = run_cli(
        ["show", "executive-summary", "--resolved"], monkeypatch, tmp_path
    )
    data = yaml.safe_load(out)
    assert data["spec"]["excel"]["layout"] == "single-sheet"
    assert "extends" not in data


def test_init_copy_keeps_comments_and_validates(monkeypatch, tmp_path):
    code, out, err = run_cli(
        ["init", "standard-bom", "--output", ".inventag/templates/acme-bom.yaml"],
        monkeypatch,
        tmp_path,
    )
    assert code == 0, err
    text = (tmp_path / ".inventag/templates/acme-bom.yaml").read_text()
    assert "name: acme-bom" in text and "# Standard BOM" in text
    code, out, _ = run_cli(["validate", "acme-bom"], monkeypatch, tmp_path)
    assert code == 0 and "OK" in out
    code, out, _ = run_cli(["list"], monkeypatch, tmp_path)
    assert "acme-bom" in out and "project" in out


def test_init_extend_and_refuse_overwrite(monkeypatch, tmp_path):
    args = ["init", "finops-cost-allocation", "--output", "policy.yaml", "--extend"]
    code, _, err = run_cli(args, monkeypatch, tmp_path)
    assert code == 0, err
    data = yaml.safe_load((tmp_path / "policy.yaml").read_text())
    assert data["extends"] == "finops-cost-allocation" and data["name"] == "policy"
    code, _, err = run_cli(args, monkeypatch, tmp_path)
    assert code == 1 and "--force" in err
    code, _, _ = run_cli(args + ["--force"], monkeypatch, tmp_path)
    assert code == 0


def test_init_of_child_writes_resolved_copy(monkeypatch, tmp_path):
    code, _, err = run_cli(
        ["init", "executive-summary", "-o", "exec.yaml"], monkeypatch, tmp_path
    )
    assert code == 0, err
    data = yaml.safe_load((tmp_path / "exec.yaml").read_text())
    assert "extends" not in data and data["spec"]["excel"]["layout"] == "single-sheet"


def test_init_rejects_bad_names(monkeypatch, tmp_path):
    code, _, err = run_cli(
        ["init", "standard-bom", "-o", "x.txt"], monkeypatch, tmp_path
    )
    assert code == 2


def test_validate_reports_errors_with_line(monkeypatch, tmp_path):
    write(
        tmp_path / "bad.yaml",
        "kind: report\nname: bad\nspec:\n  colors:\n    header_fill: red\n",
    )
    code, out, _ = run_cli(["validate", "bad.yaml"], monkeypatch, tmp_path)
    assert code == 1
    assert "bad.yaml:5: spec.colors.header_fill" in out


def test_validate_checks_references(monkeypatch, tmp_path):
    write(
        tmp_path / "r.yaml",
        "kind: report\nname: r\nspec:\n  tag_policy: standard-bom\n",
    )
    code, out, _ = run_cli(["validate", "r.yaml"], monkeypatch, tmp_path)
    assert code == 1 and "a tag-policy template is needed" in out


def test_validate_warns_on_placeholder_accounts(monkeypatch, tmp_path):
    code, out, _ = run_cli(["validate", "org-multi-account"], monkeypatch, tmp_path)
    assert code == 0 and "look like placeholders" in out


# ------------------------------------------------------- --template behaviour


def test_two_templates_of_same_kind_rejected(registry):
    with pytest.raises(TemplateError, match="two report templates"):
        load_templates(["standard-bom", "executive-summary"], registry)


def test_report_brings_its_policy_and_cli_policy_wins(registry):
    run = load_templates(["finops-cost-report"], registry)
    assert run.policy.name == "finops-cost-allocation"
    run = load_templates(["finops-cost-report", "security-baseline"], registry)
    assert run.policy.name == "security-baseline"


def test_policy_alone_uses_standard_report(registry):
    run = load_templates(["security-baseline"], registry)
    assert run.report.name == "standard-bom"


def test_config_applies_unless_flag_typed(registry):
    parser = create_parser()
    argv = ["--template", "ci-pipeline", "--output-directory", "mine"]
    args = parser.parse_args(argv)
    run = load_templates(args.template, registry)
    apply_config(run, args, explicit_dests(create_parser, argv), logging.getLogger("t"))
    assert args.output_directory == "mine"  # typed flag wins
    assert args.account_regions == "us-east-1"
    assert args.create_excel and not args.create_word
    assert args.disable_parallel_processing is True
    assert run.fail_on_violations


def test_config_accounts_become_private_temp_file(registry):
    import os
    import stat

    args = create_parser().parse_args(["--template", "org-multi-account"])
    run = load_templates(args.template, registry)
    apply_config(run, args, set(), logging.getLogger("t"))
    try:
        mode = stat.S_IMODE(os.stat(args.accounts_file).st_mode)
        assert mode & 0o077 == 0
        data = yaml.safe_load(open(args.accounts_file))
        assert data["accounts"][0]["role_arn"].endswith(":role/InvenTagReadOnly")
        assert data["accounts"][0]["regions"] == ["us-east-1"]
    finally:
        run.cleanup()
    assert not os.path.exists(args.accounts_file)


def test_finish_exit_codes(registry, sample_resources, capsys):
    run = load_templates(["ci-pipeline"], registry)
    run.compliance = evaluate(sample_resources, run.policy)
    assert (
        run.finish({"bom_generation": {"generated_files": []}}, logging.getLogger("t"))
        == 3
    )
    run.config.spec["fail_on_tag_violations"] = False
    assert run.finish({}, logging.getLogger("t")) == 0
    assert "Tag policy 'finops-cost-allocation'" in capsys.readouterr().out


def test_template_flag_is_repeatable():
    args = create_parser().parse_args(["--template", "a", "--template", "b"])
    assert args.template == ["a", "b"]
