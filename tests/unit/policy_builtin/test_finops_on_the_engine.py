"""``inventag/finops/checks.py`` is a caller of the engine (plan decision 3)."""

import datetime as dt

from inventag.finops import checks
from inventag.policy import engine
from tests.unit.finops import golden_cases

NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)


def test_run_checks_evaluates_the_finops_checks_set_through_the_engine(monkeypatch):
    calls = []
    real = engine.evaluate

    def spy(snapshot, policies, *args, **kwargs):
        calls.append(sorted(p.id for p in policies))
        return real(snapshot, policies, *args, **kwargs)

    monkeypatch.setattr(engine, "evaluate", spy)
    rows, units, started = golden_cases.cases()["fin1 state available"]
    checks.run_checks(rows, units, started)
    assert calls == [[f"FIN-00{i}" for i in range(1, 7)]]


def test_the_judging_code_of_v1_4_3_is_gone_from_checks_py():
    for name in ("_JUDGES", "_volume", "_address", "_snapshot", "_lb_v2", "_context"):
        assert not hasattr(checks, name), name


def test_the_engine_result_and_the_sheet_result_agree_on_the_counts():
    rows, units, started = golden_cases.cases()["scenario 007"]
    out = checks.run_checks(rows, units, started or NOW)
    by_policy = {}
    for f in out["findings"]:
        by_policy.setdefault(f["policy"], []).append(f["result"])
    for line in out["summary"]:
        mine = by_policy.get(line["policy"], [])
        assert line["fail"] == mine.count("fail")
        assert line["not_evaluated"] == mine.count("not_evaluated")
