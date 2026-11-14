"""Unit tests for scripts/docs/check_ci_examples.py (pure functions, no network).

Every GitLab rule has one passing and one failing YAML string. The rules and
their documentation links are in the checker next to each rule.
"""

import importlib.util
import json
import textwrap
from pathlib import Path

import yaml

_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "docs" / "check_ci_examples.py"
)
_spec = importlib.util.spec_from_file_location("check_ci_examples", _PATH)
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

BASE = """
stages: [build, test]
build:
  stage: build
  image: python:3.12-slim
  script:
    - echo build
"""


def _block(body, kind="gitlab"):
    return {"lang": "yaml", "info": "", "body": body, "line": 1, "kind": kind}


def problems(check_id, body, kind="gitlab"):
    """Messages that one named check reports for a YAML string."""
    body = textwrap.dedent(body)
    check = checker.CHECKS[check_id]
    return [m for _, m in check.run(yaml.safe_load(body), _block(body, kind))]


def passes(check_id, body, kind="gitlab"):
    return problems(check_id, body, kind) == []


# --- global keywords ------------------------------------------------------


def test_top_level_global_keywords_pass():
    assert passes("gitlab-top-level-keys", BASE + "default:\n  retry: 1\n")


def test_top_level_unknown_key_fails():
    found = problems("gitlab-top-level-keys", BASE + "deploy_target: prod\n")
    assert found and "deploy_target" in found[0]


def test_top_level_deprecated_global_image_fails():
    found = problems("gitlab-top-level-keys", "image: python:3.12\n" + BASE)
    assert found and "deprecated" in found[0] and "default" in found[0]


# --- reserved job names ---------------------------------------------------


def test_reserved_job_name_fails():
    found = problems("gitlab-reserved-job-names", "variables:\n  script: x\n")
    assert found and "variables" in found[0]
    found = problems("gitlab-reserved-job-names", "cache:\n  script: [x]\n")
    assert found and "cache" in found[0]


def test_reserved_names_as_global_keywords_pass():
    assert passes("gitlab-reserved-job-names", BASE + "variables:\n  A: b\n")


# --- job keywords ---------------------------------------------------------


def test_job_has_script_passes_and_missing_fails():
    assert passes("gitlab-job-has-script", BASE)
    found = problems("gitlab-job-has-script", "build:\n  stage: build\n")
    assert found and "build" in found[0]


def test_job_keywords_documented_pass():
    body = """
    job:
      script: [a]
      before_script: [b]
      after_script: [c]
      image: python:3.12
      stage: test
      rules: [{if: '$CI', when: always}]
      variables: {A: b}
      artifacts: {paths: [x]}
      cache: {paths: [y]}
      needs: []
      allow_failure: true
      id_tokens: {T: {aud: x}}
      retry: 1
      timeout: 1 hour
      environment: prod
      tags: [t]
      when: manual
      interruptible: true
      dependencies: []
    """
    assert passes("gitlab-job-keywords", body)


def test_job_keyword_unknown_fails():
    found = problems("gitlab-job-keywords", "job:\n  script: [a]\n  scripts: [b]\n")
    assert found and "scripts" in found[0]


def test_job_only_except_flagged_as_legacy():
    found = problems("gitlab-job-keywords", "job:\n  script: [a]\n  only: [main]\n")
    assert found and "only" in found[0] and "rules" in found[0]


def test_hidden_job_is_not_checked_for_keywords():
    assert passes("gitlab-job-keywords", ".tpl:\n  anything: 1\n")


# --- stages ---------------------------------------------------------------


def test_stage_declared_in_stages_passes():
    assert passes("gitlab-stage-declared", BASE)


def test_stage_not_declared_fails():
    found = problems(
        "gitlab-stage-declared", "stages: [build]\nj:\n  stage: deploy\n  script: [x]\n"
    )
    assert found and "deploy" in found[0]


def test_default_stages_apply_without_stages_key():
    assert passes("gitlab-stage-declared", "j:\n  stage: deploy\n  script: [x]\n")
    found = problems("gitlab-stage-declared", "j:\n  stage: ship\n  script: [x]\n")
    assert found and "ship" in found[0]


def test_job_without_stage_needs_test_stage_when_stages_is_set():
    found = problems("gitlab-stage-declared", "stages: [build]\nj:\n  script: [x]\n")
    assert found and "test" in found[0]


# --- needs ----------------------------------------------------------------


def test_needs_existing_jobs_pass():
    body = BASE + "t:\n  stage: test\n  script: [x]\n  needs: [build, {job: build}]\n"
    assert passes("gitlab-needs-exist", body)


def test_needs_unknown_job_fails():
    body = BASE + "t:\n  stage: test\n  script: [x]\n  needs: [nope]\n"
    found = problems("gitlab-needs-exist", body)
    assert found and "nope" in found[0]
    body = BASE + "t:\n  stage: test\n  script: [x]\n  needs: [{job: nope}]\n"
    assert problems("gitlab-needs-exist", body)


def test_needs_optional_and_cross_project_are_not_checked():
    body = BASE + (
        "t:\n  script: [x]\n  needs:\n    - {job: nope, optional: true}\n"
        "    - {project: g/p, job: other, ref: main, artifacts: true}\n"
    )
    assert passes("gitlab-needs-exist", body)


# --- rules ----------------------------------------------------------------


def test_rules_documented_keys_pass():
    body = """
    j:
      script: [x]
      rules:
        - if: '$CI_PIPELINE_SOURCE == "schedule"'
          when: always
          allow_failure: true
          variables: {A: b}
        - changes: [docs/**]
          needs: [a]
          interruptible: true
        - exists: [x]
    """
    assert passes("gitlab-rules-keys", body)


def test_rules_unknown_key_fails():
    found = problems(
        "gitlab-rules-keys", "j:\n  script: [x]\n  rules:\n    - if: a\n      foo: b\n"
    )
    assert found and "`foo`" in found[0]


def test_rules_entry_needs_if_changes_exists_or_when():
    found = problems(
        "gitlab-rules-keys", "j:\n  script: [x]\n  rules:\n    - variables: {A: b}\n"
    )
    assert found and "at least one" in found[0]


def test_rules_when_value_must_be_documented():
    found = problems(
        "gitlab-rules-keys", "j:\n  script: [x]\n  rules:\n    - when: sometimes\n"
    )
    assert found and "sometimes" in found[0]


# --- allow_failure --------------------------------------------------------


def test_allow_failure_bool_and_exit_codes_pass():
    for value in ("true", "false", "{exit_codes: 3}", "{exit_codes: [3, 4]}"):
        assert passes(
            "gitlab-allow-failure", f"j:\n  script: [x]\n  allow_failure: {value}\n"
        )


def test_allow_failure_wrong_shapes_fail():
    for value in ('"yes"', "{exit_codes: three}", "{exit_codes: [3, x]}", "{codes: 3}"):
        body = f"j:\n  script: [x]\n  allow_failure: {value}\n"
        assert problems("gitlab-allow-failure", body), value


# --- artifacts ------------------------------------------------------------


def test_artifacts_when_and_expire_in_pass():
    body = "j:\n  script: [x]\n  artifacts:\n    when: always\n    expire_in: 30 days\n"
    assert passes("gitlab-artifacts", body)
    assert passes("gitlab-artifacts", body.replace("30 days", "'42'"))


def test_artifacts_bad_when_and_non_string_expire_in_fail():
    body = "j:\n  script: [x]\n  artifacts:\n    when: sometimes\n"
    assert problems("gitlab-artifacts", body)
    body = "j:\n  script: [x]\n  artifacts:\n    expire_in: 30\n"
    found = problems("gitlab-artifacts", body)
    assert found and "expire_in" in found[0]


# --- id_tokens ------------------------------------------------------------


def test_id_tokens_aud_string_or_list_passes():
    for aud in ("sts.amazonaws.com", "[a, b]"):
        body = f"j:\n  script: [x]\n  id_tokens:\n    T:\n      aud: {aud}\n"
        assert passes("gitlab-id-tokens", body)


def test_id_tokens_missing_or_wrong_aud_fails():
    assert problems("gitlab-id-tokens", "j:\n  script: [x]\n  id_tokens:\n    T: {}\n")
    body = "j:\n  script: [x]\n  id_tokens:\n    T:\n      aud: 5\n"
    assert problems("gitlab-id-tokens", body)
    body = "default:\n  id_tokens:\n    T:\n      x: 1\n"
    assert problems("gitlab-id-tokens", body)


# --- retry, timeout, when -------------------------------------------------


def test_retry_shapes_pass():
    for value in (
        "0",
        "2",
        "{max: 2, when: runner_system_failure}",
        "{max: 1, when: [script_failure, api_failure]}",
    ):
        assert passes("gitlab-retry", f"j:\n  script: [x]\n  retry: {value}\n"), value


def test_retry_shapes_fail():
    for value in ("3", '"2"', "{max: 5}", "{max: 1, when: nonsense}", "{count: 1}"):
        assert problems("gitlab-retry", f"j:\n  script: [x]\n  retry: {value}\n"), value


def test_timeout_string_passes_and_number_fails():
    assert passes(
        "gitlab-timeout", "j:\n  script: [x]\n  timeout: 3 hours 30 minutes\n"
    )
    found = problems("gitlab-timeout", "j:\n  script: [x]\n  timeout: 3600\n")
    assert found and "timeout" in found[0]


def test_job_when_documented_values_pass_and_never_fails():
    assert passes("gitlab-when", "j:\n  script: [x]\n  when: manual\n")
    found = problems("gitlab-when", "j:\n  script: [x]\n  when: never\n")
    assert found and "never" in found[0]


# --- InvenTag policy ------------------------------------------------------


def test_aws_secret_literal_in_variables_fails_and_reference_passes():
    ok = BASE + "variables:\n  AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY\n"
    assert passes("inventag-no-literal-aws-secrets", ok)
    bad = BASE + "variables:\n  AWS_SECRET_ACCESS_KEY: abcd1234\n"
    found = problems("inventag-no-literal-aws-secrets", bad)
    assert found and "AWS_SECRET_ACCESS_KEY" in found[0]


def test_aws_secret_literal_in_job_and_map_variables_fails():
    body = (
        "j:\n  script: [x]\n  variables:\n    AWS_ACCESS_KEY_ID:\n"
        "      value: literal\n      description: d\n"
    )
    assert problems("inventag-no-literal-aws-secrets", body)
    body = "j:\n  script: [x]\n  variables:\n    OTHER: AKIAABCDEFGHIJKLMNOP\n"
    assert problems("inventag-no-literal-aws-secrets", body)
    assert passes(
        "inventag-no-literal-aws-secrets",
        "j:\n  script: [x]\n  variables:\n    AWS_REGION: us-east-1\n",
    )


def test_python_image_pinned_to_minor_passes():
    for image in ("python:3.12", "python:3.12-slim", "python:3.12.4-slim"):
        assert passes(
            "inventag-python-image-pinned", f"j:\n  script: [x]\n  image: {image}\n"
        )
    assert passes(
        "inventag-python-image-pinned", "j:\n  script: [x]\n  image: alpine:3.20\n"
    )
    assert passes(
        "inventag-python-image-pinned",
        "default:\n  image:\n    name: python:3.12\n",
    )


def test_python_image_unpinned_fails():
    for image in ("python:latest", "python:3", "python", "python:3-slim"):
        body = f"j:\n  script: [x]\n  image: {image}\n"
        assert problems("inventag-python-image-pinned", body), image
    assert problems("inventag-python-image-pinned", "image: python:3\n")


def test_allow_failure_exit_codes_for_inventag_must_be_documented_codes():
    ok = "j:\n  script: [inventag --template nightly]\n  allow_failure:\n    exit_codes: [3, 4]\n"
    assert passes("inventag-allow-failure-exit-codes", ok)
    bad = ok.replace("[3, 4]", "[1, 3]")
    found = problems("inventag-allow-failure-exit-codes", bad)
    assert found and "1" in found[0]
    other = "j:\n  script: [make]\n  allow_failure:\n    exit_codes: [1]\n"
    assert passes("inventag-allow-failure-exit-codes", other)


# --- commands and GitHub side ---------------------------------------------


def test_inventag_command_in_gitlab_script_is_parsed():
    ok = "j:\n  script:\n    - inventag --template nightly\n"
    assert passes("inventag-commands-parse", ok)
    found = problems("inventag-commands-parse", ok + "    - inventag --no-such-flag\n")
    assert found and "--no-such-flag" in found[0]


GITHUB_OK = """
on: push
permissions:
  id-token: write
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def test_github_pinned_uses_passes_and_branch_fails():
    assert passes("github-action-pins", GITHUB_OK, "github")
    found = problems("github-action-pins", GITHUB_OK.replace("@v4", "@main"), "github")
    assert found and "main" in found[0]


def test_github_job_structure_and_oidc():
    assert passes("github-job-structure", GITHUB_OK, "github")
    assert problems(
        "github-job-structure", GITHUB_OK.replace("runs-on", "run-on"), "github"
    )
    no_perm = GITHUB_OK.replace("permissions:\n  id-token: write\n", "")
    body = no_perm + "      - run: echo role-to-assume\n"
    assert problems("github-oidc-permissions", body, "github")
    assert passes(
        "github-oidc-permissions",
        GITHUB_OK + "      - run: echo role-to-assume\n",
        "github",
    )


# --- optional schema layer ------------------------------------------------

TINY_SCHEMA = {
    "type": "object",
    "properties": {"stages": {"type": "array", "items": {"type": "string"}}},
}


def test_schema_layer_reports_violation_and_accepts_valid(tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps(TINY_SCHEMA))
    check = checker.schema_check(schema)
    good = _block("stages: [a]\n")
    bad = _block("stages: 5\n")
    assert check.run({"stages": ["a"]}, good) == []
    found = check.run({"stages": 5}, bad)
    assert found and "stages" in found[0][1]


def test_schema_check_absent_file_means_no_layer(tmp_path):
    assert checker.schema_check(tmp_path / "missing.json") is None


# --- evidence report and the known finding --------------------------------


def _write_doc(tmp_path, body, name="page.md"):
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / name).write_text("# t\n\n```yaml\n# .gitlab-ci.yml\n" + body + "```\n")
    return docs


def test_report_lists_block_id_file_line_and_passed_checks(tmp_path, capsys):
    docs = _write_doc(tmp_path, BASE)
    code = checker.main(["--docs", str(docs), "--report"])
    out = capsys.readouterr().out
    assert code == 0
    assert "docs/page.md:4" in out and "[gitlab]" in out
    assert "PASS gitlab-stage-declared" in out
    assert "https://docs.gitlab.com/ci/yaml/" in out
    assert "FAIL" not in out


def test_report_shows_failed_check(tmp_path, capsys):
    docs = _write_doc(tmp_path, BASE + "t:\n  stage: ship\n  script: [x]\n")
    assert checker.main(["--docs", str(docs), "--report"]) == 1
    out = capsys.readouterr().out
    assert "FAIL gitlab-stage-declared" in out


def test_known_finding_placeholder_sha_is_still_reported(tmp_path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    body = GITHUB_OK.replace(
        "actions/checkout@v4", "aws-actions/configure-aws-credentials@<full-commit-SHA>"
    )
    (docs / "run-in-ci.md").write_text(
        "```yaml\n# .github/workflows/x.yml\n" + body + "```\n"
    )
    assert checker.main(["--docs", str(docs)]) == 1
    out = capsys.readouterr().out
    assert "run-in-ci.md:11" in out and "configure-aws-credentials" in out
