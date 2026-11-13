"""Fault injection for the failure matrix.

``FaultInjector`` replaces ``BaseClient._make_api_call`` and raises the real
``botocore`` exception that AWS would produce (``ClientError`` with a real error
code and HTTP status, ``EndpointConnectionError``, ``ReadTimeoutError``), or
sleeps, or edits the answer. It sits above botocore's own retry loop, so one
injected error is one failed call (a test must not wait for ten retries).

Everything here is data plus one patch, so the same rules can be sent to a child
process as JSON (see ``child.py``).

Rules are checked in order; the first rule that matches decides. A rule matches
on service name (botocore's, for example ``sqs``), operation (``ListQueues``),
region, the access key of the session (this is how one account of several is
picked), and the n-th call of that (service, operation, key, region).
"""

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import botocore.client
import botocore.exceptions as bex

# Real error codes, with the HTTP status AWS uses for them. Tests name the code,
# the status follows.
STATUS = {
    "AccessDenied": 403,
    "AccessDeniedException": 403,
    "UnauthorizedOperation": 403,
    "AuthorizationError": 403,
    "OptInRequired": 403,
    "SubscriptionRequiredException": 400,
    "InvalidClientTokenId": 403,
    "ExpiredToken": 400,
    "ExpiredTokenException": 400,
    "Throttling": 400,
    "ThrottlingException": 400,
    "RequestLimitExceeded": 503,
    "TooManyRequestsException": 429,
    "LimitExceededException": 400,
    "DataUnavailableException": 400,
    "InternalError": 500,
    "ServiceUnavailable": 503,
    "NoSuchBucket": 404,
    "NoSuchEntity": 404,
}

# Raised instead of a ClientError (no HTTP answer at all).
RAISE_KINDS = ("EndpointConnectionError", "ConnectTimeout", "ReadTimeout")


@dataclass
class Fault:
    service: Optional[str] = None  # None: any service
    op: Optional[Any] = None  # operation name, or a list of names; None: any
    region: Optional[str] = None
    key: Optional[str] = None  # access key id of the calling session
    call: Optional[int] = None  # n-th call (1-based) of (service, op, key, region)
    not_services: Tuple[str, ...] = ()
    not_ops: Tuple[str, ...] = ()
    # what happens (combine ``sleep`` with one of the others)
    error: Optional[str] = None  # real AWS error code
    status: Optional[int] = None
    message: Optional[str] = None
    raise_kind: Optional[str] = None  # one of RAISE_KINDS
    sleep: float = 0.0
    replace: Optional[Dict[str, Any]] = None  # use this answer instead of AWS's
    drop: Optional[str] = None  # remove this key from AWS's answer

    def matches(self, service, op, region, key, n) -> bool:
        if self.service not in (None, service) or service in self.not_services:
            return False
        if isinstance(self.op, (list, tuple)):
            if op not in self.op:
                return False
        elif self.op not in (None, op):
            return False
        if op in self.not_ops:
            return False
        return (
            self.region in (None, region)
            and self.key in (None, key)
            and self.call in (None, n)
        )


def deny_everything(error="AccessDenied", keep=("sts",), key=None) -> Fault:
    """Every call fails except the identity check, the region list and ``keep``."""
    return Fault(
        not_services=tuple(keep),
        not_ops=("DescribeRegions",),
        error=error,
        key=key,
    )


def _client_error(fault: Fault, operation: str) -> bex.ClientError:
    code = fault.error
    return bex.ClientError(
        {
            "Error": {"Code": code, "Message": fault.message or f"{code} (injected)"},
            "ResponseMetadata": {"HTTPStatusCode": fault.status or STATUS.get(code, 400)},
        },
        operation,
    )


class FaultInjector:
    """Patch ``BaseClient._make_api_call``. Use as a context manager."""

    def __init__(self, faults=(), accounts: Optional[Dict[str, str]] = None):
        self.faults: List[Fault] = list(faults)
        # access key id -> account id answered by sts:GetCallerIdentity
        self.accounts = dict(accounts or {})
        self.calls: List[Dict[str, Any]] = []
        self.armed = False
        self._counts: Dict[tuple, int] = {}
        self._lock = threading.Lock()
        self._original = None
        self.hit_file = None  # created when a slow fault starts (signal tests wait for it)

    # -- arming: seed AWS first, then switch the faults on ----------------
    def arm(self):
        with self._lock:
            self._counts.clear()
            self.calls.clear()
        self.armed = True

    def __enter__(self):
        self._original = botocore.client.BaseClient._make_api_call
        injector = self
        original = self._original

        def patched(client, operation_name, api_params):
            if not injector.armed:
                return original(client, operation_name, api_params)
            service = client.meta.service_model.service_name
            region = client.meta.region_name
            creds = client._request_signer._credentials
            key = getattr(creds, "access_key", None)
            with injector._lock:
                k = (service, operation_name, key, region)
                injector._counts[k] = injector._counts.get(k, 0) + 1
                n = injector._counts[k]
            record = {"service": service, "op": operation_name, "region": region, "key": key, "n": n}
            for fault in injector.faults:
                if not fault.matches(service, operation_name, region, key, n):
                    continue
                if fault.sleep:
                    if injector.hit_file:
                        open(injector.hit_file, "w").write("hit")
                    time.sleep(fault.sleep)
                if fault.raise_kind:
                    injector._record(record, "raise:" + fault.raise_kind)
                    url = f"https://{service}.{region}.amazonaws.com/"
                    if fault.raise_kind == "EndpointConnectionError":
                        raise bex.EndpointConnectionError(endpoint_url=url)
                    if fault.raise_kind == "ConnectTimeout":
                        raise bex.ConnectTimeoutError(endpoint_url=url)
                    raise bex.ReadTimeoutError(endpoint_url=url)
                if fault.error:
                    injector._record(record, "error:" + fault.error)
                    raise _client_error(fault, operation_name)
                if fault.drop or fault.replace is not None:
                    answer = original(client, operation_name, api_params)
                    if fault.drop:
                        answer.pop(fault.drop, None)
                    if fault.replace is not None:
                        answer = dict(fault.replace)
                        answer.setdefault("ResponseMetadata", {"HTTPStatusCode": 200})
                    injector._record(record, "changed")
                    return answer
                break  # sleep only: go on to the real call
            if service == "sts" and operation_name == "GetCallerIdentity" and key in injector.accounts:
                account = injector.accounts[key]
                injector._record(record, "canned")
                return {
                    "UserId": "AIDAPROBE",
                    "Account": account,
                    "Arn": f"arn:aws:iam::{account}:user/probe",
                    "ResponseMetadata": {"HTTPStatusCode": 200},
                }
            injector._record(record, "pass")
            return original(client, operation_name, api_params)

        botocore.client.BaseClient._make_api_call = patched
        return self

    def __exit__(self, *exc):
        botocore.client.BaseClient._make_api_call = self._original
        self.armed = False

    def _record(self, record, result):
        with self._lock:
            self.calls.append(dict(record, result=result))

    # -- questions a test asks afterwards --------------------------------
    def count(self, service: str, op: Optional[str] = None) -> int:
        return sum(
            1
            for c in self.calls
            if c["service"] == service and (op is None or c["op"] == op)
        )


def faults_to_json(faults, accounts=None) -> str:
    return json.dumps({"faults": [asdict(f) for f in faults], "accounts": accounts or {}})


def faults_from_json(text: str) -> Tuple[List[Fault], Dict[str, str]]:
    data = json.loads(text or "{}")
    faults = []
    for item in data.get("faults", []):
        item["not_services"] = tuple(item.get("not_services") or ())
        item["not_ops"] = tuple(item.get("not_ops") or ())
        faults.append(Fault(**item))
    return faults, data.get("accounts", {})
