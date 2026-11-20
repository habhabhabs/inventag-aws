"""Run ``python -m inventag`` in a child process, inside moto, with a fixed clock.

    python tests/concurrency/_child.py SPEC.json [inventag arguments ...]

``SPEC.json`` (written by ``tests/concurrency/harness.py``):

    regions, accounts, scale   the estate (``scripts/benchmark_scan.py`` builder)
    latency_ms, per_operation, throttle, faults   see ``tests/latency.py``
    frozen                     ISO time every clock read of the run returns; the
                               clock then never moves, so durations are 0.0
    gate                       {"service:Operation": "<fifo path>"}: the first
                               request of that operation tells the parent through
                               the FIFO and then waits (``hold_seconds``) until the
                               process is told to stop; used for signal tests
    account_order              configured order of the accounts, 1-based, e.g. [3, 1, 2]
    holds                      rules that stop one request until an event (below)
    fake_sdk_backoff           true (default): the SDK's wait between retries is
                               recorded in the stats, not slept
    stats                      path of a JSON file for requests, peak in flight
    moto_seed                  seed for moto's id generator (stable resource ids)

Holds (``spec["holds"]``, a list of rules, each with a ``name``):

    {"name": ..., "match": M, "until": M2, "count": N, "timeout": S}
        the FIRST request that matches M waits until N requests that match M2
        have started (``count`` defaults to 1), or S seconds pass. The stats file
        says per rule whether it ended by ``"event"`` or by ``"timeout"``.
    {"name": ..., "meet": [M, M2], "timeout": S}
        the first request of M and the first request of M2 wait for each other,
        then both go on (a barrier of two).

    M is {"service": "ec2", "operation": "DescribeVpcs", "account": "first" |
    "other", "region": "eu-west-1"}; every key is optional. "first" is the
    account of the default credentials (the first account of the run).

The fixed clock is installed before ``inventag``, openpyxl or python-docx are
imported, so every ``from datetime import datetime`` sees the fixed class. Only
wall-clock readers are replaced (``time.time``, ``datetime.now/utcnow/today``,
``time.localtime/gmtime`` without argument). ``time.monotonic`` is real, so
waits and deadlines still work.
"""

import atexit
import datetime as _dt
import importlib.util
import json
import os
import random
import signal
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class _At:
    """A callable that is not a function, so ``logging`` (which stores
    ``time.localtime`` as a class attribute) does not bind it as a method."""

    def __init__(self, real, epoch):
        self.real, self.epoch = real, epoch

    def __call__(self, secs=None):
        return self.real(self.epoch if secs is None else secs)


def install_fixed_clock(iso: str) -> None:
    fixed = _dt.datetime.fromisoformat(iso)
    if fixed.tzinfo is None:
        fixed = fixed.replace(tzinfo=_dt.timezone.utc)
    epoch = fixed.timestamp()
    real_localtime, real_gmtime = time.localtime, time.gmtime

    class FixedDate(_dt.date):
        @classmethod
        def today(cls):
            return cls.fromtimestamp(epoch)

    class FixedDateTime(_dt.datetime, FixedDate):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(epoch, tz)

        @classmethod
        def utcnow(cls):
            return cls.fromtimestamp(epoch, _dt.timezone.utc).replace(tzinfo=None)

        @classmethod
        def today(cls):
            return cls.fromtimestamp(epoch)

    _dt.datetime = FixedDateTime
    _dt.date = FixedDate
    time.time = lambda: epoch
    time.time_ns = lambda: int(epoch * 1_000_000_000)
    time.localtime = _At(real_localtime, epoch)
    time.gmtime = _At(real_gmtime, epoch)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _no_sdk_sleep(record) -> None:
    """The SDK waits between the attempts of a retried request (``time.sleep`` in
    ``botocore/endpoint.py``). Record the wait instead of sitting through it: the
    tests look at what the SDK decided, not at the clock."""
    import botocore.endpoint

    real = time

    class NoSleep:
        @staticmethod
        def sleep(seconds):
            record.append(seconds)

        def __getattr__(self, name):
            return getattr(real, name)

    botocore.endpoint.time = NoSleep()


def touch_every_region(benchmark, regions, accounts) -> None:
    """Make moto create the EC2 backend (and its default VPC) of every region of
    every account now, in a fixed order, from one thread.

    moto builds a backend the first time something asks for it and draws the ids
    of its default VPC from one shared random source. If the scan is the first to
    ask, the ids depend on which thread asks first, and two runs of the same
    estate would differ in ids that no InvenTag code controls.
    """
    import boto3

    for index in range(1, accounts + 1):
        creds = {}
        if index > 1:
            assumed = boto3.client("sts", region_name=regions[0]).assume_role(
                RoleArn=benchmark.role_arn(benchmark.other_account_id(index)),
                RoleSessionName="touch",
            )["Credentials"]
            creds = dict(
                aws_access_key_id=assumed["AccessKeyId"],
                aws_secret_access_key=assumed["SecretAccessKey"],
                aws_session_token=assumed["SessionToken"],
            )
        for region in sorted(boto3.session.Session().get_available_regions("ec2")):
            boto3.client("ec2", region_name=region, **creds).describe_vpcs()
            # moto also creates the default KMS keys and the Athena work group of a
            # region on first use, with ids from the same shared random source
            for service, call in (
                ("kms", "list_keys"),
                ("athena", "list_work_groups"),
                ("events", "list_event_buses"),
                ("iam", "list_roles"),
            ):
                client = boto3.client(service, region_name=region, **creds)
                getattr(client, call)()


class Holds:
    """Stops chosen requests until an event, to force one interleaving.

    It wraps the moto stubber from outside the latency harness, so a held
    request is "in flight" for the SDK (and for a limiter that counts SDK
    sends) but not yet in the harness's own count.
    """

    def __init__(self, rules):
        # moto's ``mock_aws`` puts its own key into the environment; the account of
        # the default credentials is the one that signs with it
        self.first_key = os.environ.get("AWS_ACCESS_KEY_ID")
        self.rules = rules
        self.lock = threading.Condition()
        self.taken = {r["name"]: False for r in rules}
        self.started = {r["name"]: 0 for r in rules}
        self.outcome = {}
        self.meets = {
            r["name"]: threading.Barrier(2, timeout=r.get("timeout", 10.0))
            for r in rules
            if "meet" in r
        }
        self.meet_taken = {}

    def describe(self, event_name, request):
        _, _, rest = event_name.partition(".")
        service, _, operation = rest.partition(".")
        auth = request.headers.get("Authorization", "")
        if isinstance(auth, bytes):
            auth = auth.decode()
        key = auth.partition("Credential=")[2].partition("/")[0]
        host = request.url.split("//", 1)[-1].split("/", 1)[0]
        parts = host.split(".")
        region = parts[1] if len(parts) > 3 and "-" in parts[1] else None
        return {
            "service": service.replace("-", "").replace("_", "").lower(),
            "operation": operation,
            "account": "first" if key == self.first_key else "other",
            "region": region,
        }

    @staticmethod
    def matches(pattern, call):
        for field, wanted in pattern.items():
            if field == "service":
                wanted = wanted.replace("-", "").replace("_", "").lower()
            if call.get(field) != wanted:
                return False
        return True

    def before(self, event_name, request):
        call = self.describe(event_name, request)
        mine = None
        with self.lock:
            for rule in self.rules:
                name = rule["name"]
                if "until" in rule and self.matches(rule["until"], call):
                    self.started[name] += 1
                    self.lock.notify_all()
                if "match" in rule and self.matches(rule["match"], call):
                    if not self.taken[name]:
                        self.taken[name] = True
                        mine = rule
                if "meet" in rule:
                    for index, pattern in enumerate(rule["meet"]):
                        if self.matches(pattern, call) and (name, index) not in (
                            self.meet_taken
                        ):
                            self.meet_taken[(name, index)] = True
                            mine = rule
        if mine is None:
            return
        name = mine["name"]
        if "meet" in mine:
            try:
                self.meets[name].wait()
                self.outcome[name] = "event"
            except threading.BrokenBarrierError:
                self.outcome[name] = "timeout"
            return
        need = mine.get("count", 1)
        with self.lock:
            met = self.lock.wait_for(
                lambda: self.started[name] >= need, timeout=mine.get("timeout", 10.0)
            )
        self.outcome[name] = "event" if met else "timeout"


def install_holds(rules):
    from moto.core.botocore_stubber import BotocoreStubber

    holds = Holds(rules)
    inner = BotocoreStubber.__call__

    def patched(self, event_name, request, **kwargs):
        if self.enabled:
            holds.before(event_name, request)
        return inner(self, event_name, request, **kwargs)

    BotocoreStubber.__call__ = patched
    return holds


def main() -> None:
    # A parent that runs in the background (nohup, CI) can leave SIGINT ignored, and
    # Python then does not turn it into KeyboardInterrupt. Ask for the default.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    spec = json.loads(Path(sys.argv[1]).read_text())
    cli_args = sys.argv[2:]
    if spec.get("frozen"):
        install_fixed_clock(spec["frozen"])

    benchmark = _load("_a5_benchmark_scan", ROOT / "scripts" / "benchmark_scan.py")
    benchmark.prepare_environment()

    from moto import mock_aws
    from moto.moto_api._internal import mock_random

    from tests.latency import inject_latency
    from tests.moto_warmup import warm_moto_modules

    warm_moto_modules()
    regions = spec.get("regions", ["us-east-1"])
    accounts = spec.get("accounts", 1)
    counts = {
        name: max(0, round(default * spec.get("scale", 0.1)))
        for name, default in benchmark.DEFAULT_COUNTS.items()
    }
    counts.update(spec.get("counts", {}))
    out_dir = Path(spec["out"])
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(spec["work"])
    work.mkdir(parents=True, exist_ok=True)

    gates = dict(spec.get("gate") or {})
    per_operation = dict(spec.get("per_operation") or {})
    for name in gates:
        per_operation[name] = GATE_SECONDS * 1000  # milliseconds
    stop_waiting = threading.Event()  # set when the CLI call has returned

    def sleep(seconds: float) -> None:
        if seconds == GATE_SECONDS:
            # a gated request: announce it once, then hold until the run ends
            announce(spec, gates)
            stop_waiting.wait(spec.get("hold_seconds", 4.0))
        elif seconds > 0:
            time.sleep(seconds)  # the simulated network delay of one request

    # moto and the harness stay active until the process is gone (no ``with``
    # block): after a signal, worker threads still run and Python waits for them
    # at exit; with moto switched off first, those calls would go to the real AWS.
    mock_aws().start()
    mock_random.seed(spec.get("moto_seed", 1234))
    # boto3 fills in idempotency tokens (EC2 ``ClientToken``) with ``uuid.uuid4()``,
    # and they end up in the report: make them the same in every run, while the
    # estate is built (and only then; the scan itself keeps the real function)
    seeded = random.Random(spec.get("moto_seed", 1234))
    real_uuid4 = uuid.uuid4
    uuid.uuid4 = lambda: uuid.UUID(int=seeded.getrandbits(128), version=4)
    try:
        benchmark.seed_accounts(counts, regions, accounts)
        touch_every_region(benchmark, regions, accounts)
    finally:
        uuid.uuid4 = real_uuid4
    accounts_file = None
    if accounts > 1:
        accounts_file = benchmark.write_accounts_file(
            work / "accounts.json", regions, accounts
        )
        if spec.get("account_order"):
            # configured order of the accounts: 1-based positions, e.g. [3, 1, 2]
            data = json.loads(accounts_file.read_text())
            data["accounts"] = [data["accounts"][i - 1] for i in spec["account_order"]]
            accounts_file.write_text(json.dumps(data))
    argv = benchmark.scan_argv(
        out_dir,
        work / "audit.json",
        regions,
        accounts_file,
        None,
        analyses=spec.get("analyses", False),
    )
    argv = [a for a in argv if a != "--create-excel"]
    argv[1:1] = spec.get("formats", ["--create-excel"])
    argv += cli_args
    # kept in a name for the life of the process: a generator context manager
    # that is garbage collected runs its ``finally`` and undoes the patch
    keep_alive = inject_latency(
        spec.get("latency_ms", 0),
        per_operation=per_operation or None,
        throttle=spec.get("throttle"),
        faults=spec.get("faults"),
        sleep=sleep,
    )
    harness = keep_alive.__enter__()

    def write_stats():
        path = spec.get("stats")
        if path:
            Path(path).write_text(
                json.dumps(
                    {
                        "total": harness.total_requests,
                        "peak_in_flight": harness.peak_in_flight,
                        "calls": harness.calls_by_operation(),
                        "holds": dict(holds.outcome) if holds else {},
                        "sdk_backoffs": list(sdk_backoffs),
                        "records": [
                            [
                                r.service,
                                r.operation,
                                r.attempt,
                                r.injected,
                                r.started,
                                r.ended,
                                r.thread,
                            ]
                            for r in harness.requests
                        ],
                    },
                    sort_keys=True,
                )
            )

    holds = install_holds(spec["holds"]) if spec.get("holds") else None
    sdk_backoffs = []
    if spec.get("fake_sdk_backoff", True):
        _no_sdk_sleep(sdk_backoffs)
    atexit.register(write_stats)
    from inventag.cli.main import main as cli_main

    sys.argv = argv
    try:
        cli_main()
    finally:
        stop_waiting.set()  # a gated request ends when the CLI has finished


GATE_SECONDS = 777.0


def announce(spec, gates) -> None:
    """Tell the parent that a gated request started (a write into its FIFO)."""
    for path in set(gates.values()):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            continue  # nobody reads: the parent is not waiting
        try:
            os.write(fd, b"x")
        finally:
            os.close(fd)


if __name__ == "__main__":
    main()
