"""When the Google Doc fails after the Sheet was created, the run names the
Sheet by its URL. Fake Google clients only (nothing here runs against real
Google). Exit codes stay as in v1.2.0."""

import pytest

from inventag.reporting import google_output as go

from tests.unit.test_google_output import (  # noqa: F401
    RESOURCES,
    FakeApi,
    aws,
    converter,
    fake_services,
    run_cli,
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/SID/edit"


def docs_disabled(kwargs):
    raise RuntimeError("Google Docs API has not been used in project 1")


def services_with_docs_failing(log):
    services = fake_services(log)
    services["docs"] = FakeApi(log, {"documents.create": docs_disabled})
    return services


def test_doc_failure_after_the_sheet_names_the_sheet():
    options = go.GoogleOptions(sheets=True, docs=True)
    with pytest.raises(go.GoogleOutputError) as caught:
        go.publish(
            converter(), RESOURCES, options, services=services_with_docs_failing([])
        )
    text = str(caught.value)
    assert "Google Docs API has not been used" in text  # the reason is kept
    assert f"The Google Sheet was created and is complete: {SHEET_URL}" in text


def test_doc_failure_without_a_sheet_adds_nothing():
    options = go.GoogleOptions(docs=True)
    with pytest.raises(go.GoogleOutputError) as caught:
        go.publish(
            converter(), RESOURCES, options, services=services_with_docs_failing([])
        )
    assert "Google Sheet" not in str(caught.value)


def test_sheet_failure_stays_as_it_is():
    class Boom(FakeApi):
        def _execute(self):
            raise RuntimeError("quota exceeded for project")

    services = fake_services([])
    services["sheets"] = Boom([], {})
    with pytest.raises(go.GoogleOutputError, match="Google API call failed") as caught:
        go.publish(
            converter(),
            RESOURCES,
            go.GoogleOptions(sheets=True, docs=True),
            services=services,
        )
    assert "Google Sheet was created" not in str(caught.value)


def test_i4d_run_prints_the_sheet_url_and_still_exits_1(
    aws, monkeypatch, capsys  # noqa: F811
):
    monkeypatch.setattr(go, "load_credentials", lambda options: object())
    monkeypatch.setattr(
        go, "build_services", lambda creds: services_with_docs_failing([])
    )
    code = run_cli(
        "--account-regions",
        "us-east-1",
        "--account-services",
        "s3",
        "--no-billing-validation",
        "--create-google-sheets",
        "--create-google-docs",
    )
    captured = capsys.readouterr()
    assert code == 1
    assert SHEET_URL in captured.err + captured.out
