"""Run ``python -m inventag <args>`` inside moto, in this (child) process.

Usage: python tests/e2e/_moto_runner.py [inventag arguments ...]

Seeds the estate from ``estate.py`` into moto's in-memory AWS, then runs the
package exactly as ``python -m inventag`` would. Used by the subprocess tests.
"""

import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))  # repository root: import this checkout

os.environ.update(
    AWS_ACCESS_KEY_ID="testing",
    AWS_SECRET_ACCESS_KEY="testing",
    AWS_DEFAULT_REGION="us-east-1",
    AWS_EC2_METADATA_DISABLED="true",
    # moto ships ~1300 default AMIs and snapshots; they only slow the scan down.
    MOTO_EC2_LOAD_DEFAULT_AMIS="false",
)
os.environ.pop("AWS_PROFILE", None)

from moto import mock_aws  # noqa: E402

from estate import seed_estate  # noqa: E402
from tests.moto_warmup import warm_moto_modules  # noqa: E402

if __name__ == "__main__":
    warm_moto_modules()  # no first-call import race between discovery threads
    with mock_aws():
        if os.environ.get("INVENTAG_E2E_EMPTY") != "1":
            seed_estate()
        sys.argv = ["inventag", *sys.argv[1:]]
        runpy.run_module("inventag", run_name="__main__", alter_sys=True)
