"""Fixtures of the concurrency tests: one scan is run once per distinct request.

A scan costs about 15 to 25 s (moto start-up and the estate), so every test asks
``scans(...)`` and equal requests share one run for the whole session.
"""

import json

import pytest

from tests.concurrency import harness


@pytest.fixture(scope="session")
def scans(tmp_path_factory):
    cache = {}

    def get(args=(), seed="0", **spec) -> harness.Scan:
        key = json.dumps([list(args), seed, spec], sort_keys=True)
        if key not in cache:
            tmp = tmp_path_factory.mktemp("scan")
            cache[key] = harness.run_scan(tmp, args, hash_seed=seed, **spec)
        return cache[key]

    return get
