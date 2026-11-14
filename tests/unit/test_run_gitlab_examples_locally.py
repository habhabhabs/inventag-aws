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
