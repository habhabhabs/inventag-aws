"""Let moto answer one request at a time (tests and the benchmark only).

InvenTag's discovery calls AWS from up to 15 threads. moto is not built for
that ("Moto is not designed for multithreaded access", moto FAQ). Seen on CI
(pull request #43, Python 3.15): describe_key_pairs in
moto/ec2/responses/key_pairs.py writes into the class-level dict
EC2BaseResponse.RESPONSE_KEY_PATH_TO_TRANSFORMER (via _include_in_response /
_exclude_from_response in moto/core/responses.py) while another thread's
response is written by moto/core/serialize.py AttributePicker.__call__, which
iterates that dict: "dictionary changed size during iteration", and the scan
loses that listing. moto's ECS responses do the same.

Real AWS has no such shared state, so the lock belongs in the test harness,
never in ``inventag/``. InvenTag's own threads still run in parallel; only
moto's handling of each request is serialised.
"""

import functools
import threading

from moto.core.botocore_stubber import BotocoreStubber

_LOCK = threading.RLock()


def serialize_moto_requests():
    """Wrap moto's request handler in a process-wide lock. Returns an undo."""
    original = BotocoreStubber.process_request
    if getattr(original, "_inventag_serialized", False):
        return lambda: None

    @functools.wraps(original)
    def process_request(self, request):
        with _LOCK:
            return original(self, request)

    process_request._inventag_serialized = True
    BotocoreStubber.process_request = process_request

    def undo():
        BotocoreStubber.process_request = original

    return undo
