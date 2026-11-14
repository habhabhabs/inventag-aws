"""Unit tests for the pure parts of scripts/docs/run_gitlab_examples_locally.py.

No gitlab-ci-local, rsync or moto server is needed: these cover the YAML
rewrite, the parsing of gitlab-ci-local's output and the expected job status.
"""

import importlib.util
import sys
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parents[2] / "scripts" / "docs"
sys.path.insert(0, str(_DIR))
_spec = importlib.util.spec_from_file_location(
    "run_gitlab_examples_locally", _DIR / "run_gitlab_examples_locally.py"
)
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

BLOCK = """\
stages:
  - inventory

inventory:
  stage: inventory
  id_tokens:
    AWS_ID_TOKEN:
      aud: sts.amazonaws.com
  script:
    - printf '%s' "$AWS_ID_TOKEN" > "$AWS_WEB_IDENTITY_TOKEN_FILE"
    - pip install "inventag-aws==%INVENTAG_VERSION%"
    - inventag --template nightly --fail-on-account-error --fail-if-empty
  allow_failure:
    exit_codes: [3]
"""


def test_pip_install_of_the_release_is_replaced_by_the_local_install():
    doc = runner.rewrite_install(yaml.safe_load(BLOCK), "/py -m pip install /repo")
    script = doc["inventory"]["script"]
    assert script[1] == "/py -m pip install /repo"
    assert script[0].startswith("printf") and script[2].startswith("inventag ")


def test_install_rewrite_keeps_valid_yaml_when_the_command_starts_with_a_quote():
    doc = runner.rewrite_install(yaml.safe_load(BLOCK), '"/a b/py" -m pip install x')
    again = yaml.safe_load(yaml.safe_dump(doc, sort_keys=False))
    assert again["inventory"]["script"][1] == '"/a b/py" -m pip install x'


def test_install_rewrite_covers_unpinned_extras_and_python_dash_m_forms():
    for line in (
        "pip install inventag-aws",
        "python3 -m pip install --upgrade 'inventag-aws[google]>=1.2'",
    ):
        doc = runner.rewrite_install({"j": {"script": [line]}}, "LOCAL")
        assert doc["j"]["script"] == ["LOCAL"]


def test_other_pip_installs_are_left_alone():
    doc = runner.rewrite_install({"j": {"script": ["pip install boto3"]}}, "LOCAL")
    assert doc["j"]["script"] == ["pip install boto3"]


def test_template_names_and_id_token_names_are_found():
    assert runner.template_names(BLOCK) == ["nightly"]
    assert runner.id_token_names(yaml.safe_load(BLOCK)) == ["AWS_ID_TOKEN"]


GCL_OUTPUT = """\
inventory finished in 33 s  FAIL 3 \n\
report    finished in 20 ms
warned    finished in 2.02 s  WARN 3 \n\
 PASS  report
 WARN  warned  pre_script
 FAIL  inventory
"""


def test_job_results_are_read_from_each_job_line_not_the_process_status():
    assert runner.parse_results(GCL_OUTPUT) == [
        runner.JobResult("report", "PASS", 0),
        runner.JobResult("warned", "WARN", 3),
        runner.JobResult("inventory", "FAIL", 3),
    ]


def test_expected_status_follows_gitlab_allow_failure_rules():
    job = yaml.safe_load(BLOCK)["inventory"]
    assert runner.expected_label(job, 0) == "PASS"
    assert runner.expected_label(job, 3) == "WARN"
    assert runner.expected_label(job, 4) == "FAIL"
    assert runner.expected_label({}, 3) == "FAIL"
    assert runner.expected_label({"allow_failure": True}, 1) == "WARN"
    assert runner.expected_label({"allow_failure": {"exit_codes": 5}}, 5) == "WARN"


def test_missing_gitlab_ci_local_is_reported_for_a_clean_skip():
    assert any("gitlab-ci-local" in m for m in runner.missing_prerequisites(None))


# --- work folder names ----------------------------------------------------


def test_two_pages_with_a_block_on_the_same_line_get_different_work_folders():
    a = runner.work_name({"path": "docs/guides/a.md", "line": 12})
    b = runner.work_name({"path": "docs/guides/b.md", "line": 12})
    c = runner.work_name({"path": "docs/guides/a.md", "line": 40})
    assert len({a, b, c}) == 3


def test_work_folder_names_differ_when_slugs_of_two_paths_are_equal():
    a = runner.work_name({"path": "docs/a-b/c.md", "line": 3})
    b = runner.work_name({"path": "docs/a/b-c.md", "line": 3})
    assert a != b


def test_work_folder_name_is_one_safe_path_segment():
    name = runner.work_name({"path": "docs/a b/ü.md", "line": 3})
    assert "/" not in name and " " not in name and name.isascii()


# --- pipeline source ------------------------------------------------------

MR_BLOCK = """\
stages: [check]
a:
  stage: check
  script: [x]
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
b:
  stage: check
  script: [x]
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event" && $CI_MERGE_REQUEST_ID'
"""

SCHEDULE_BLOCK = """\
j:
  script: [x]
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
"""


def test_a_block_whose_jobs_need_merge_request_event_runs_as_a_merge_request():
    doc = yaml.safe_load(MR_BLOCK)
    assert runner.choose_pipeline_source(doc, None) == (
        "merge_request_event",
        "from the block's rules",
    )


def test_a_scheduled_block_runs_as_a_schedule():
    doc = yaml.safe_load(SCHEDULE_BLOCK)
    assert runner.choose_pipeline_source(doc, None)[0] == "schedule"


def test_the_source_that_lets_most_jobs_run_wins():
    doc = yaml.safe_load(SCHEDULE_BLOCK)
    doc["k"] = {
        "script": ["x"],
        "rules": [{"if": '$CI_PIPELINE_SOURCE == "web"'}],
    }
    doc["l"] = {
        "script": ["x"],
        "rules": [{"if": '$CI_PIPELINE_SOURCE == "web"'}],
    }
    assert runner.choose_pipeline_source(doc, None)[0] == "web"


def test_a_block_without_source_rules_runs_as_a_push_pipeline():
    doc = {"j": {"script": ["x"]}}
    assert runner.choose_pipeline_source(doc, None) == (
        "push",
        "default: no rule names a source",
    )


def test_the_override_wins_and_is_named_as_such():
    doc = yaml.safe_load(MR_BLOCK)
    assert runner.choose_pipeline_source(doc, "web") == ("web", "override")


# --- project CI/CD variables ---------------------------------------------


def test_the_dummy_defaults_cover_exactly_the_variables_the_examples_keep_out_of_yaml():
    assert set(runner.DUMMY_PROJECT_VARIABLES) == {
        "AWS_ROLE_ARN",
        "INVENTAG_REPORTS_BUCKET",
        "INVENTAG_KMS_KEY_ID",
    }


def test_every_dummy_default_is_passed_even_when_the_yaml_never_names_it():
    # AWS_ROLE_ARN is read by the AWS SDK, so no example mentions it.
    assert runner.project_variables({}) == runner.DUMMY_PROJECT_VARIABLES


def test_a_variable_given_on_the_command_line_beats_the_default_and_is_added():
    got = runner.project_variables({"AWS_ROLE_ARN": "mine", "OTHER": "1"})
    assert got["AWS_ROLE_ARN"] == "mine" and got["OTHER"] == "1"
    assert got["INVENTAG_REPORTS_BUCKET"] == "inventag-docs-reports"


def test_variable_arguments_split_at_the_first_equals_sign():
    assert runner.parse_variable_args(["A=b", "C=d=e", "E="]) == {
        "A": "b",
        "C": "d=e",
        "E": "",
    }


def test_a_variable_argument_without_a_name_and_equals_sign_is_refused():
    for bad in ("NOEQUALS", "=value"):
        try:
            runner.parse_variable_args([bad])
        except ValueError as exc:
            assert "NAME=VALUE" in str(exc)
        else:
            raise AssertionError(bad)


def test_the_variables_file_is_read_back_by_yaml_with_every_value_a_string(tmp_path):
    path = tmp_path / "vars.yml"
    runner.write_variables_file(path, {"A": "1", "B": "x: y"})
    assert yaml.safe_load(path.read_text()) == {"A": "1", "B": "x: y"}


# --- one build, no concurrent builds -------------------------------------

TWO_JOBS = """\
stages: [check]
a:
  stage: check
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"
    - inventag --template x
b:
  stage: check
  script:
    - pip install "inventag-aws==%INVENTAG_VERSION%"
    - inventag --template y
"""


def test_no_job_installs_or_builds_the_package_the_pipeline_installs_it_once():
    doc = runner.rewrite_install(yaml.safe_load(TWO_JOBS), runner.PREINSTALLED_NOTE)
    for job in ("a", "b"):
        assert not any("pip install" in line for line in doc[job]["script"])
        assert doc[job]["script"][0] == runner.PREINSTALLED_NOTE


def test_the_install_comes_from_the_built_wheel_not_the_source_folder(tmp_path):
    argv = runner.install_argv("/py", tmp_path / "site", tmp_path / "x-1-py3.whl")
    assert argv[:4] == ["/py", "-m", "pip", "install"]
    assert str(tmp_path / "x-1-py3.whl") in argv
    assert str(runner.REPO) not in argv
    assert "--no-deps" in argv and "--target" in argv


def test_the_wheel_is_found_in_its_folder_and_a_missing_wheel_is_an_error(tmp_path):
    (tmp_path / "inventag_aws-1.2.0-py3-none-any.whl").write_text("")
    assert runner.find_wheel(tmp_path).name.startswith("inventag_aws-")
    empty = tmp_path / "empty"
    empty.mkdir()
    try:
        runner.find_wheel(empty)
    except RuntimeError as exc:
        assert "wheel" in str(exc)
    else:
        raise AssertionError("no error")


# --- fixtures -------------------------------------------------------------

S3_CMD = (
    'inventag --s3-bucket "$INVENTAG_REPORTS_BUCKET" --s3-encryption aws:kms '
    '--s3-kms-key-id "$INVENTAG_KMS_KEY_ID"'
)


def test_an_upload_example_needs_a_bucket_and_a_kms_key_and_nothing_else():
    assert runner.fixtures_needed(S3_CMD) == ["reports bucket", "KMS key"]


def test_a_bucket_example_without_kms_needs_no_key():
    assert runner.fixtures_needed("inventag --s3-bucket b") == ["reports bucket"]


def test_a_multi_account_example_needs_the_accounts_file():
    cmd = "inventag --accounts-file accounts.yaml --resume"
    assert runner.fixtures_needed(cmd) == ["accounts file"]


def test_an_example_that_needs_nothing_gets_no_fixture():
    assert runner.fixtures_needed("inventag --template nightly") == []


def test_the_bucket_name_comes_from_the_variable_or_the_literal():
    given = {"INVENTAG_REPORTS_BUCKET": "from-var"}
    assert runner.bucket_name(S3_CMD, given) == "from-var"
    assert runner.bucket_name("inventag --s3-bucket ${INVENTAG_REPORTS_BUCKET}", given)
    assert runner.bucket_name("inventag --s3-bucket literal-b", {}) == "literal-b"


def test_the_accounts_file_is_written_where_the_command_reads_it(tmp_path):
    cmd = "inventag --accounts-file config/accounts.yaml --resume"
    runner.apply_fixtures(["accounts file"], cmd, tmp_path, "http://unused", {})
    data = yaml.safe_load((tmp_path / "config" / "accounts.yaml").read_text())
    assert [a["account_id"] for a in data["accounts"]] == [
        "111111111111",
        "222222222222",
    ]
