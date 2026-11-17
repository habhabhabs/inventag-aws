"""An empty result names the filter that removed everything (A-20).

v1.2.1 said "No resources to report (none found, or the filters removed all
of them)" whatever the filters were (harness row F2). Now, when a service or
tag filter is set, the message names it. Without a filter the text is as
before. Exit code 0 (as before).
"""

import logging

from tests.unit.test_docs_claims_v120 import (  # noqa: F401 (fixtures)
    BASE,
    aws,
    empty_aws,
    logged,
    reports,
    run_cli,
)

ARGS = [*BASE, "--account-regions", "us-east-1", "--output-directory", "out"]


def test_the_service_filter_is_named(empty_aws, tmp_path, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    assert run_cli(*ARGS, "--account-services", "EC2") == 0
    assert reports(tmp_path / "out") == []
    assert (
        "No resources to report: none found with --account-services EC2 (from the "
        "command line or the accounts file). No report file was written; run "
        "without that filter to see every resource."
    ) in logged(caplog), logged(caplog)


def test_service_and_tag_filters_are_named(empty_aws, tmp_path, caplog):  # noqa: F811
    caplog.set_level(logging.INFO)
    code = run_cli(
        *ARGS, "--account-services", "EC2", "--account-tags", '{"Owner": "nobody"}'
    )
    assert code == 0
    assert (
        "No resources to report: none found with --account-services EC2 and "
        '--account-tags {"Owner": "nobody"} (from the command line or the '
        "accounts file). No report file was written; run without those filters "
        "to see every resource."
    ) in logged(caplog), logged(caplog)
