"""A3 (plan 2.1, 2.4, 2.5): per-resource detail calls run in the account's
detail pool; the answers are written back by the resource's index.

Interleavings are forced with barriers and events, never with sleeps. Faults
are chosen by operation, not by "after N calls".
"""

import logging
import threading
from unittest import mock

from botocore.exceptions import ClientError

from inventag.discovery.comprehensive_discovery import ComprehensiveAWSDiscovery

R = "eu-west-1"
R2 = "eu-west-2"
ACCOUNT = "111122223333"
WAIT = 10  # an upper bound for a test that would otherwise hang, never a pause


def _row(service, rtype, rid, region=R):
    return {
        "service": service,
        "resource_type": rtype,
        "resource_id": rid,
        "region": region,
        "arn": f"arn:aws:{service.lower()}:{region}:{ACCOUNT}:x/{rid}",
        "raw_data": {},
    }


def _disc(rows, client_for):
    disc = ComprehensiveAWSDiscovery(
        session=mock.MagicMock(), regions=[R, R2], enable_billing_validation=False
    )
    disc.coverage.account_id = ACCOUNT
    disc.resources = rows
    disc._client = client_for
    return disc


def _error(code):
    return ClientError({"Error": {"Code": code, "Message": "secret-detail"}}, "Op")


class LambdaClient:
    """``get_function_configuration`` with a hook that runs inside the call."""

    def __init__(self, hook=None):
        self.hook = hook
        self.names = []
        self._lock = threading.Lock()

    def get_function_configuration(self, FunctionName):
        with self._lock:
            self.names.append(FunctionName)
        if self.hook:
            self.hook(FunctionName)
        return {
            "FunctionName": FunctionName,
            "Runtime": "python3.12",
            "MemorySize": 128,
            "Timeout": 3,
            "ResponseMetadata": {},
        }


def _functions(count, region=R):
    return [_row("LAMBDA", "Function", f"f{i:02d}", region) for i in range(count)]


def test_four_calls_are_in_flight_together_and_never_more_for_one_service_region():
    rows = _functions(12)
    meet = threading.Barrier(4, timeout=WAIT)
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}

    def hook(name):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        meet.wait()  # four calls must be inside at the same time
        with lock:
            state["now"] -= 1

    client = LambdaClient(hook)
    disc = _disc(rows, lambda *a, **k: client)
    disc._enhance_lambda_functions()
    assert state["peak"] == 4
    assert all(r["raw_data"].get("runtime") == "python3.12" for r in rows)


def test_the_detail_pool_has_eight_daemon_workers():
    sizes = []
    disc = _disc(_functions(2), lambda *a, **k: LambdaClient())
    real = disc._make_pool

    def make(workers):
        sizes.append(workers)
        return real(workers)

    with mock.patch.object(disc, "_make_pool", side_effect=make):
        disc._enhance_lambda_functions()
    assert sizes == [8]


def test_two_regions_run_at_the_same_time():
    """The cap is per service and region: two regions give up to eight calls."""
    rows = _functions(4, R) + _functions(4, R2)
    meet = threading.Barrier(8, timeout=WAIT)
    client = LambdaClient(lambda name: meet.wait())
    disc = _disc(rows, lambda *a, **k: client)
    disc._enhance_lambda_functions()
    assert all(r["raw_data"].get("runtime") == "python3.12" for r in rows)


def test_each_answer_lands_on_its_own_resource_whatever_the_finishing_order():
    rows = _functions(8)
    done = {r["resource_id"]: threading.Event() for r in rows}
    ids = [r["resource_id"] for r in rows]

    def hook(name):
        # the first four finish in reverse order of submission
        i = ids.index(name)
        if i < 3:
            assert done[ids[i + 1]].wait(WAIT)

    class Client(LambdaClient):
        def get_function_configuration(self, FunctionName):
            try:
                return super().get_function_configuration(FunctionName)
            finally:
                done[FunctionName].set()

    client = Client(hook)
    disc = _disc(rows, lambda *a, **k: client)
    disc._enhance_lambda_functions()
    for row in rows:
        assert row["raw_data"]["boto3_config"]["FunctionName"] == row["resource_id"]


def test_workers_do_not_write_the_resources():
    """Every write to a row's data happens on the thread that coordinates."""
    writers = set()

    class Spy(dict):
        def __setitem__(self, key, value):
            writers.add(threading.current_thread())
            super().__setitem__(key, value)

    rows = _functions(6)
    for row in rows:
        row["raw_data"] = Spy()
    disc = _disc(rows, lambda *a, **k: LambdaClient())
    disc._enhance_lambda_functions()
    assert writers == {threading.current_thread()}


def test_detail_failures_are_counted_by_operation_and_code_as_in_v1_3_0(caplog):
    rows = _functions(5) + _functions(3, R2)
    denied = {"f00", "f01", "f03"}

    class Client(LambdaClient):
        def __init__(self, region):
            super().__init__()
            self.region = region

        def get_function_configuration(self, FunctionName):
            if self.region == R and FunctionName in denied:
                raise _error("AccessDeniedException")
            if self.region == R2 and FunctionName == "f01":
                raise _error("ThrottlingException")
            return super().get_function_configuration(FunctionName)

    disc = _disc(rows, lambda service, region=None: Client(region))
    with caplog.at_level(logging.WARNING):
        disc._enhance_lambda_functions()
    entries = [
        (e["region"], e["operation"], e["outcome"], e["error_code"], e["count"])
        for e in disc.coverage.to_dict()
        if e["source"] == "service-api-detail"
    ]
    assert sorted(entries) == [
        (R, "GetFunctionConfiguration", "denied", "AccessDeniedException", 3),
        (R2, "GetFunctionConfiguration", "throttled", "ThrottlingException", 1),
    ]
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert [w.split(" could")[0] for w in warnings] == [
        f"Details of 3 lambda resource(s) in {R}",
        f"Details of 1 lambda resource(s) in {R2}",
    ]
    assert "secret-detail" not in caplog.text
    # the rows that could be read were read
    read = [r for r in rows if r["raw_data"].get("runtime")]
    assert len(read) == 4


def test_the_same_calls_are_made_as_one_by_one():
    """One call per resource, to the region the resource was listed in."""
    seen = []
    lock = threading.Lock()

    class Client(LambdaClient):
        def __init__(self, region):
            super().__init__()
            self.region = region

        def get_function_configuration(self, FunctionName):
            with lock:
                seen.append((self.region, FunctionName))
            return super().get_function_configuration(FunctionName)

    rows = _functions(5, R) + _functions(3, R2)
    disc = _disc(rows, lambda service, region=None: Client(region))
    disc._enhance_lambda_functions()
    assert sorted(seen) == sorted(
        [(R, f"f{i:02d}") for i in range(5)] + [(R2, f"f{i:02d}") for i in range(3)]
    )


def test_stopping_the_detail_calls_ends_the_queued_ones_and_keeps_the_rows():
    rows = _functions(12)
    inside = threading.Barrier(5, timeout=WAIT)  # four calls and the test
    release = threading.Event()
    client = LambdaClient(
        lambda name: (inside.wait(), release.wait(WAIT))  # type: ignore[func-returns-value]
    )
    disc = _disc(rows, lambda *a, **k: client)
    runner = threading.Thread(target=disc._enhance_lambda_functions)
    runner.start()
    inside.wait()
    disc.stop_detail_calls()
    release.set()
    runner.join(WAIT)
    assert not runner.is_alive()
    assert len(client.names) == 4  # the four in flight; the others never started
    assert len(disc.resources) == 12
    entries = [
        e for e in disc.coverage.to_dict() if e["source"] == "service-api-detail"
    ]
    assert sum(e["count"] for e in entries) == 8
