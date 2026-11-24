"""P6 (plan section 3): a run without the v1.5.0 flags gives what v1.4.3 gave.

The golden was made from the v1.4.3 sources with the same module (see
``v143_equality.py``); this test runs the module on the current sources. Five
runs on the FinOps moto estate: default, Word and Excel, ``--template
standard-bom``, ``--finops-checks`` and a tag-policy template. The cost-trend
changes of v1.5.0 (plan decisions 6 and 7) do not show here: the runs use
``--no-billing-validation`` and no cost analysis, so no Cost Explorer request
is planned; they are tested in ``tests/unit/test_cost_requests.py``.
"""

import json

import pytest

from tests.regression import v143_equality

pytestmark = pytest.mark.e2e


def test_runs_without_the_new_flags_equal_v143():
    expected = json.loads(v143_equality.GOLDEN.read_text())
    found = json.loads(json.dumps(v143_equality.fingerprint()))
    assert sorted(found) == sorted(expected)
    for scenario in expected:
        assert found[scenario]["exit_code"] == expected[scenario]["exit_code"]
        assert found[scenario]["console"] == expected[scenario]["console"], scenario
        assert sorted(found[scenario]["files"]) == sorted(
            expected[scenario]["files"]
        ), scenario
        for name, content in expected[scenario]["files"].items():
            assert found[scenario]["files"][name] == content, (scenario, name)
