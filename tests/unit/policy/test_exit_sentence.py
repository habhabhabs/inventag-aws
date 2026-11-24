"""Spec 11.3 (interim ruling): the exit sentence is the last line of the text
and Markdown forms. The caller passes ``fail_on`` and ``thresholds`` to
``render`` and ``write``; without them the sentence is left out."""

import json
from pathlib import Path

import pytest

from inventag.policy.outputs import render, write

GOLDEN = Path(__file__).resolve().parent / "golden"

NO_THRESHOLD = "Exit code 0: findings are reported; no threshold was set."
NOTHING_FAILED = "Exit code 0: nothing failed at severity high or higher."
ALL_EVALUATED = "Exit code 0: everything could be evaluated."
SEVEN = "Exit code 7: at least one finding failed at severity medium or higher."
EIGHT = "Exit code 8: some checks could not be evaluated."


def result(code):
    data = json.loads((GOLDEN / "result-ex05-s1.json").read_text())
    data["summary"]["exit_code"] = code
    return data


def last(text):
    return text.rstrip("\n").splitlines()[-1]


@pytest.mark.parametrize("fmt", ["text", "md"])
@pytest.mark.parametrize(
    "code, gates, sentence",
    [
        (0, {"thresholds": []}, NO_THRESHOLD),
        (0, {"fail_on": "high", "thresholds": ["fail_on"]}, NOTHING_FAILED),
        (0, {"fail_on": "high"}, NOTHING_FAILED),
        (0, {"thresholds": ["fail_on_not_evaluated"]}, ALL_EVALUATED),
        (
            0,
            {"fail_on": "high", "thresholds": ["fail_on", "fail_on_not_evaluated"]},
            NOTHING_FAILED + " " + ALL_EVALUATED,
        ),
        (
            0,
            {"fail_on": "high", "thresholds": ["fail_on_not_evaluated", "fail_on"]},
            NOTHING_FAILED + " " + ALL_EVALUATED,
        ),
        (7, {"fail_on": "medium", "thresholds": ["fail_on"]}, SEVEN),
        (8, {"thresholds": ["fail_on_not_evaluated"]}, EIGHT),
        (8, {"fail_on": "medium", "thresholds": ["fail_on_not_evaluated"]}, EIGHT),
    ],
)
def test_the_sentence_of_each_case(fmt, code, gates, sentence):
    text = render(result(code), fmt, **gates)
    assert last(text) == sentence
    # one line, the last; with both thresholds it holds both sentences
    assert [ln for ln in text.splitlines() if "Exit code" in ln] == [sentence]


@pytest.mark.parametrize("fmt", ["text", "md"])
def test_without_the_thresholds_the_sentence_is_left_out(fmt):
    text = render(result(7), fmt)
    assert "Exit code" not in text
    assert text.endswith("\n") and not text.endswith("\n\n")


@pytest.mark.parametrize("fmt", ["json", "sarif", "xml"])
def test_the_other_forms_never_carry_it(fmt):
    text = render(result(7), fmt, fail_on="medium", thresholds=["fail_on"])
    assert "Exit code" not in text


def test_a_code_7_without_fail_on_is_a_caller_error():
    with pytest.raises(ValueError, match="fail_on"):
        render(result(7), "text", thresholds=[])


def test_an_unknown_threshold_or_severity_is_refused():
    with pytest.raises(ValueError, match="threshold"):
        render(result(0), "text", thresholds=["fail_on_everything"])
    with pytest.raises(ValueError, match="severity"):
        render(result(0), "text", fail_on="urgent")


def test_write_passes_them_to_the_markdown_file(tmp_path):
    (path,) = write(
        result(7),
        tmp_path,
        formats=["md"],
        fail_on="medium",
        thresholds=["fail_on"],
    )
    assert last(path.read_text()) == SEVEN
    (path,) = write(result(7), tmp_path / "plain", formats=["md"])
    assert "Exit code" not in path.read_text()
