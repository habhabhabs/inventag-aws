"""An abandoned account's worker does not keep the process alive (A-25, A1).

The generator ignores whatever an abandoned worker returns. Its worker
threads came from a ThreadPoolExecutor, which the interpreter joins at
exit, so a worker still waiting on a network call kept the process alive
after the summary (harness row B10). The account workers are now daemon
threads. Deterministic: the hung worker waits on an event, the clock is fake.
"""

import threading
from unittest.mock import patch

from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
from tests.unit.test_account_time_limit_and_failures import (  # noqa: F401
    FakeClock,
    _contexts,
    aws,
)


class Hanging:
    clock = None
    started = None
    release = None
    threads = []

    def __init__(self, session, regions, **kwargs):
        self.session = session

    def discover_all_resources(self):
        if getattr(self.session, "_hang", False):
            Hanging.threads.append(threading.current_thread())
            Hanging.started.set()
            Hanging.clock.now += 10_000  # past the limit
            Hanging.release.wait(10)
            return []
        return [{"id": "ok", "service": "EC2", "type": "Instance"}]


def test_the_worker_of_an_abandoned_account_is_a_daemon_thread(
    aws, tmp_path  # noqa: F811
):
    clock = FakeClock()
    Hanging.clock = clock
    Hanging.started = threading.Event()
    Hanging.release = threading.Event()
    Hanging.threads = []
    generator = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[], output_directory=str(tmp_path), account_processing_timeout=60
        )
    )
    generator._clock = clock
    generator._poll_seconds = 0.01
    generator._abandon_grace_seconds = 0.05
    contexts = _contexts(["111111111111", "222222222222"])
    contexts["222222222222"].session._hang = True
    generator.account_contexts.update(contexts)
    try:
        with patch("inventag.core.cloud_bom_generator.AWSResourceInventory", Hanging):
            resources = generator._parallel_account_discovery(contexts)
        assert Hanging.started.is_set()
        assert [r["id"] for r in resources] == ["ok"]
        hung = Hanging.threads[0]
        assert hung.is_alive()  # still waiting: abandoned, not finished
        assert hung.daemon, "the interpreter would wait for this thread at exit"
    finally:
        Hanging.release.set()
