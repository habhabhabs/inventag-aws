"""Latency, counting and fault injection for tests and the benchmark (moto only).

``inject_latency(ms, ...)`` makes every AWS request that moto answers wait
``ms`` milliseconds first, and records each request. The wait happens
*outside* moto's lock (see ``tests/moto_serial.py``), so threads that call AWS
at the same time wait at the same time, as against the real network. Without
that, moto would answer one request at a time and a parallel scan could not be
faster than a serial one.

What it gives
    * the delay, per request attempt (an SDK retry waits again);
    * ``per_operation={"s3:GetBucketLocation": 120}`` for a delay of its own;
    * ``throttle={"sqs:ListQueues": 2}``: the first 2 attempts of each such
      request get a ``Throttling`` answer, the next one passes; ``None`` means
      every attempt is throttled;
    * ``faults={"sts:AssumeRole": "AccessDenied"}``: every attempt of that
      operation gets that error code;
    * ``requests`` (one record per attempt), ``total_requests``,
      ``peak_in_flight``, ``calls_by_operation()``.

Faults are chosen by service and operation name, never by "after N calls": the
result must not depend on which thread comes first. A service is written as
boto3 names it (``resourcegroupstaggingapi``) or as botocore's event names it
(``resource-groups-tagging-api``); case and hyphens do not matter.

Nothing here is imported by ``inventag/``. It loads ``moto_serial.py`` from the
folder of this file, so a benchmark that imports ``inventag`` from another
checkout (``--inventag-root``) still uses this harness.
"""

import importlib.util
import threading
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
from xml.sax.saxutils import escape

from botocore.awsrequest import AWSResponse
from moto.core.botocore_stubber import BotocoreStubber, MockRawResponse

THROTTLE_CODE = "Throttling"


def _load_moto_serial():
    path = Path(__file__).with_name("moto_serial.py")
    spec = importlib.util.spec_from_file_location("_inventag_moto_serial", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _norm(service: str) -> str:
    return service.replace("-", "").replace("_", "").lower()


def _key(service: str, operation: str) -> str:
    return f"{_norm(service)}:{operation}"


def _normalise_map(mapping: Optional[dict]) -> dict:
    out = {}
    for name, value in (mapping or {}).items():
        service, _, operation = name.partition(":")
        out[_key(service, operation)] = value
    return out


@dataclass(frozen=True)
class RequestRecord:
    """One request attempt as the SDK sent it."""

    service: (
        str  # botocore event name of the service, e.g. "resource-groups-tagging-api"
    )
    operation: str  # e.g. "ListQueues"
    attempt: int  # 1 for the first try
    thread: str
    started: float  # time.monotonic() when the attempt reached the harness
    ended: float
    injected: Optional[str]  # error code the harness answered with, or None

    @property
    def name(self) -> str:
        return f"{self.service}:{self.operation}"


# ------------------------------------------------------------ error answers
_PROTOCOLS: Dict[str, str] = {}


def _protocol_of(service_id: str) -> str:
    """Wire protocol of a service, from botocore's own service model."""
    if not _PROTOCOLS:
        import botocore.session

        session = botocore.session.get_session()
        loader = session.get_component("data_loader")
        for name in loader.list_available_services("service-2"):
            model = session.get_service_model(name)
            _PROTOCOLS[_norm(model.service_id.hyphenize())] = model.resolved_protocol
    return _PROTOCOLS[_norm(service_id)]


def _cbor_text(text: str) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) < 24:
        head = bytes([0x60 | len(raw)])
    elif len(raw) < 256:
        head = bytes([0x78, len(raw)])
    else:
        head = bytes([0x79]) + len(raw).to_bytes(2, "big")
    return head + raw


def _cbor_map(items: Dict[str, str]) -> bytes:
    out = bytes([0xA0 | len(items)])
    for name, value in items.items():
        out += _cbor_text(name) + _cbor_text(value)
    return out


def _error_response(url: str, service_id: str, code: str, status: int) -> AWSResponse:
    protocol = _protocol_of(service_id)
    message = escape(f"{code} injected by tests/latency.py")
    headers = {}
    if protocol == "json":
        body = f'{{"__type": "{code}", "message": "{message}"}}'
        headers["Content-Type"] = "application/x-amz-json-1.1"
    elif protocol == "rest-json":
        body = f'{{"message": "{message}"}}'
        headers["Content-Type"] = "application/json"
        headers["x-amzn-ErrorType"] = code
    elif protocol == "smithy-rpc-v2-cbor":
        # A CBOR map of two text strings, written by hand: no encoder is needed.
        body = _cbor_map({"__type": code, "message": message})
        headers["Content-Type"] = "application/cbor"
        headers["smithy-protocol"] = "rpc-v2-cbor"
    elif protocol == "ec2":
        body = (
            f"<Response><Errors><Error><Code>{code}</Code><Message>{message}"
            "</Message></Error></Errors><RequestID>injected</RequestID></Response>"
        )
        headers["Content-Type"] = "text/xml"
    elif protocol == "rest-xml":
        body = (
            f"<Error><Code>{code}</Code><Message>{message}</Message>"
            "<RequestId>injected</RequestId></Error>"
        )
        headers["Content-Type"] = "application/xml"
    else:  # query
        body = (
            f"<ErrorResponse><Error><Type>Sender</Type><Code>{code}</Code>"
            f"<Message>{message}</Message></Error>"
            "<RequestId>injected</RequestId></ErrorResponse>"
        )
        headers["Content-Type"] = "text/xml"
    if isinstance(body, str):
        body = body.encode("utf-8")
    return AWSResponse(url, status, headers, MockRawResponse(body))


# ------------------------------------------------------------------ harness
class LatencyHarness:
    def __init__(self, ms, per_operation, throttle, faults, sleep, clock):
        self.default_seconds = ms / 1000.0
        self._per_operation = {
            k: v / 1000.0 for k, v in _normalise_map(per_operation).items()
        }
        self._throttle = _normalise_map(throttle)
        self._faults = _normalise_map(faults)
        self._sleep = sleep
        self._clock = clock
        self._lock = threading.Lock()
        self.requests: List[RequestRecord] = []
        self.in_flight = 0
        self.peak_in_flight = 0

    @property
    def total_requests(self) -> int:
        with self._lock:
            return len(self.requests)

    def calls_by_operation(self) -> Dict[str, int]:
        """Attempts per ``service:Operation`` (service as botocore's event names it,
        without hyphens, lower case: ``resourcegroupstaggingapi``)."""
        with self._lock:
            counts = Counter(_key(r.service, r.operation) for r in self.requests)
        return dict(sorted(counts.items()))

    def _injected_code(self, key: str, attempt: int) -> Optional[str]:
        if key in self._faults:
            return self._faults[key]
        if key in self._throttle:
            limit = self._throttle[key]
            if limit is None or attempt <= limit:
                return THROTTLE_CODE
        return None

    def handle(self, original, stubber, event_name, request, **kwargs):
        if not stubber.enabled:
            return original(stubber, event_name, request, **kwargs)
        _, _, rest = event_name.partition(".")
        service, _, operation = rest.partition(".")
        key = _key(service, operation)
        attempt = int(
            (getattr(request, "context", None) or {})
            .get("retries", {})
            .get("attempt", 1)
        )
        started = self._clock()
        with self._lock:
            self.in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        injected = None
        try:
            self._sleep(self._per_operation.get(key, self.default_seconds))
            injected = self._injected_code(key, attempt)
            if injected is not None:
                status = 400
                return _error_response(request.url, service, injected, status)
            return original(stubber, event_name, request, **kwargs)
        finally:
            ended = self._clock()
            with self._lock:
                self.in_flight -= 1
                self.requests.append(
                    RequestRecord(
                        service,
                        operation,
                        attempt,
                        threading.current_thread().name,
                        started,
                        ended,
                        injected,
                    )
                )


@contextmanager
def inject_latency(
    ms: float = 0,
    per_operation: Optional[dict] = None,
    throttle: Optional[dict] = None,
    faults: Optional[dict] = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
):
    """Delay, count and fault every request moto answers while the block runs.

    Use inside ``mock_aws()``. Yields a :class:`LatencyHarness`. Moto's own
    request handling stays serialised (``tests/moto_serial.py``) because moto
    is not thread safe; only the delay runs in parallel.
    """
    undo_serial = _load_moto_serial().serialize_moto_requests()
    harness = LatencyHarness(ms, per_operation, throttle, faults, sleep, clock)
    original = BotocoreStubber.__call__

    def patched(self, event_name, request, **kwargs):
        return harness.handle(original, self, event_name, request, **kwargs)

    BotocoreStubber.__call__ = patched
    try:
        yield harness
    finally:
        BotocoreStubber.__call__ = original
        undo_serial()
