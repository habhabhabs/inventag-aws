"""Run ``python -m inventag ARGS`` in a child process, inside moto, with faults.

Used where a test needs a real process: signals, the exit of a process with a
hung worker, the real ``python -m`` entry point.

    INVENTAG_REGRESSION_SPEC  JSON from ``faults.faults_to_json``
    INVENTAG_REGRESSION_SEED  comma separated names from ``estates.SEEDS``
    INVENTAG_REGRESSION_HIT   path of a file created when a slow fault starts
    INVENTAG_REGRESSION_LIMITS JSON: account_timeout, grace, poll
"""

import json
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.environ.update(
    AWS_ACCESS_KEY_ID="testing",
    AWS_SECRET_ACCESS_KEY="testing",
    AWS_DEFAULT_REGION="us-east-1",
    AWS_EC2_METADATA_DISABLED="true",
    MOTO_EC2_LOAD_DEFAULT_AMIS="false",
)
os.environ.pop("AWS_PROFILE", None)

from moto import mock_aws  # noqa: E402

from tests.regression import estates  # noqa: E402
from tests.regression.faults import FaultInjector, faults_from_json  # noqa: E402


def main():
    # A parent that runs in the background (nohup, CI) can leave SIGINT ignored, and
    # Python then does not turn it into KeyboardInterrupt. Ask for the default.
    import signal

    signal.signal(signal.SIGINT, signal.default_int_handler)
    faults, accounts = faults_from_json(
        os.environ.get("INVENTAG_REGRESSION_SPEC", "{}")
    )
    seeds = [
        s for s in os.environ.get("INVENTAG_REGRESSION_SEED", "estate").split(",") if s
    ]
    limits = json.loads(os.environ.get("INVENTAG_REGRESSION_LIMITS", "{}"))
    hit = os.environ.get("INVENTAG_REGRESSION_HIT")
    # moto and the injector stay active until the process is gone (no ``with`` block).
    # After a signal, worker threads are still running and Python waits for them at exit;
    # if moto were switched off first, those calls would go to the real AWS endpoints and
    # the process would take a minute to give up on a host without network.
    mock_aws().start()
    # import moto's service modules before any thread starts
    import boto3

    boto3.client("lambda", region_name="us-east-1").list_functions()
    estates.seed(seeds)
    if limits:
        from inventag.core import cloud_bom_generator as cbg

        original = cbg.CloudBOMGenerator.__init__

        def patched(self, config, *a, **k):
            if limits.get("account_timeout"):
                config.account_processing_timeout = limits["account_timeout"]
            original(self, config, *a, **k)
            if limits.get("grace") is not None:
                self._abandon_grace_seconds = limits["grace"]
            if limits.get("poll"):
                self._poll_seconds = limits["poll"]

        cbg.CloudBOMGenerator.__init__ = patched
    injector = FaultInjector(faults, accounts).__enter__()
    injector.hit_file = hit
    injector.arm()
    sys.argv = ["inventag", *sys.argv[1:]]
    runpy.run_module("inventag", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
