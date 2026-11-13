"""A map keyed by IDs (Secrets Manager SecretVersionsToStages) is one cell,
not one column per resource. Field-name maps (Lambda environment variable
names) keep their columns, as in v1.1.4."""

import json

import pytest

from inventag.reporting.converter import BOMConverter
from inventag.reporting.csv_builder import CSVBuilder
from inventag.reporting.data_keys import is_data_keyed
from inventag.reporting.excel_builder import ExcelWorkbookBuilder
from inventag.templating.columns import flatten

V1 = "3b1efbf6-5a4c-47d7-ba29-59c82ed7035d"
RAW = {
    "Name": "app/db",
    "SecretVersionsToStages": {
        V1: ["AWSCURRENT"],
        "7c9e6679-7425-40de-944b-e07fc1f90ae7": ["AWSPREVIOUS"],
    },
    "Environment": {"Variables": {"LOG_LEVEL": "info"}},
}


def _flatteners():
    yield BOMConverter.__new__(BOMConverter)._flatten_dict
    yield CSVBuilder.__new__(CSVBuilder)._flatten_dict
    yield ExcelWorkbookBuilder.__new__(ExcelWorkbookBuilder)._flatten_dict
    yield lambda d, parent_key="": flatten(d, parent_key)


@pytest.mark.parametrize("flat", list(_flatteners()))
def test_id_keyed_map_is_one_json_cell(flat):
    out = flat({"raw_data": RAW})
    assert not any(V1 in key for key in out)
    cell = out["raw_data.SecretVersionsToStages"]
    assert json.loads(cell)[V1] == ["AWSCURRENT"]
    assert out["raw_data.Environment.Variables.LOG_LEVEL"] == "info"
    assert out["raw_data.Name"] == "app/db"


@pytest.mark.parametrize(
    "keys,expected",
    [
        ({"LOG_LEVEL": 1, "DB_HOST": 2}, False),
        ({"Name": 1}, False),
        ({V1: 1}, True),
        ({"arn:aws:s3:::b": 1}, True),
        ({"0.0.0.0/0": 1}, True),
        ({"123": 1}, True),
        ({"a" * 0 + "0123456789abcdef0123": 1}, True),
    ],
)
def test_is_data_keyed(keys, expected):
    assert is_data_keyed(keys) is expected
