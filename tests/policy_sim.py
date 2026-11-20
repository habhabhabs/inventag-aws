"""A policy simulator for tests: run InvenTag as an identity that holds only some IAM actions.

``allow_only(actions)`` installs a botocore ``before-call`` hook on every client created
while it is active. The hook maps each call to the IAM action that AWS would check, and
answers an AWS ``AccessDenied`` (or the service's own denied code) when no pattern of the
allow-list matches. Nothing is guessed:

* The mapping is ``inventag.security.iam_policy.READ_ONLY_ACTIONS`` reversed (the IAM
  action that each service operation is authorised by), plus the few actions InvenTag's
  policy file does not list (``EXTRA_ACTIONS`` below, each with the reason).
* A call that has no mapping is recorded in ``unmapped`` and ``assert_all_mapped()`` fails
  the test and names the operation. This is the completeness check the repository lacked:
  ``test_security_iam_policy.py`` proves that each policy action is a real operation, and
  this proves that each operation InvenTag calls has an action.

The hook is registered with ``register_last``, so it runs after the read-only guard
(``inventag.security.read_only_guard``) whatever the order of installation. A call that the
guard refuses never reaches the policy: the guard's own error is what the caller sees.

What it proves: what InvenTag does when the calls AWS would refuse are refused. What it
does not prove: that AWS refuses exactly these calls. The allow-list is only as good as the
policy text it is written from (see ``tests/data/aws-managed/SOURCE.json``).
"""

import json
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import botocore.session
from botocore.awsrequest import AWSResponse

from inventag.security.iam_policy import READ_ONLY_ACTIONS

DATA_DIR = Path(__file__).resolve().parent / "data" / "aws-managed"

# Operations InvenTag calls whose IAM action is not a key of READ_ONLY_ACTIONS.
# (service, operation) -> IAM action. Each line says why it is not in the policy file.
EXTRA_ACTIONS: Dict[Tuple[str, str], str] = {
    # The policy file lists one action for both load balancer APIs
    # (see the comment in iam_policy.py); the classic API is called as well.
    ("elb", "DescribeLoadBalancers"): "elasticloadbalancing:DescribeLoadBalancers",
    ("elb", "DescribeTags"): "elasticloadbalancing:DescribeTags",
    # Identity calls: not part of the policy file ("sts:GetCallerIdentity needs no
    # permission"; sts:AssumeRole belongs on the scanning identity).
    ("sts", "GetCallerIdentity"): "sts:GetCallerIdentity",
    ("sts", "AssumeRole"): "sts:AssumeRole",
    ("sts", "GetSessionToken"): "sts:GetSessionToken",
    # The report upload (--s3-bucket); the optional statement of iam_policy.py.
    ("s3", "PutObject"): "s3:PutObject",
    ("s3", "CreateMultipartUpload"): "s3:PutObject",
    ("s3", "UploadPart"): "s3:PutObject",
    ("s3", "CompleteMultipartUpload"): "s3:PutObject",
    # The KMS data key an upload with --s3-kms-key-id needs (not called by InvenTag
    # itself: S3 calls KMS on the caller's behalf, and only a real AWS refuses it).
    ("kms", "GenerateDataKey"): "kms:GenerateDataKey",
}

# API Gateway authorises by HTTP verb: every Get* operation is ``apigateway:GET``.
_APIGATEWAY_SERVICES = ("apigateway", "apigatewayv2")

_REVERSED: Dict[Tuple[str, str], str] = {
    target: action for action, target in READ_ONLY_ACTIONS.items()
}
_REVERSED.update(EXTRA_ACTIONS)


def iam_action_for(service: str, operation: str) -> Optional[str]:
    """The IAM action AWS checks for ``service.operation``, or None when it is not known."""
    if service in _APIGATEWAY_SERVICES and operation.startswith("Get"):
        return "apigateway:GET"
    return _REVERSED.get((service, operation))


def _pattern_regex(pattern: str) -> "re.Pattern[str]":
    """IAM wildcard (``*`` and ``?``) to a regular expression; case-insensitive."""
    body = "".join(
        ".*" if ch == "*" else "." if ch == "?" else re.escape(ch) for ch in pattern
    )
    return re.compile(f"^{body}$", re.IGNORECASE)


def matches_any(action: str, patterns: Iterable[str]) -> bool:
    return any(_pattern_regex(p).match(action) for p in patterns)


def load_policy_actions(path: Path) -> List[str]:
    """The ``Action`` patterns an IAM policy document allows.

    Reads the shape of ``aws iam get-policy-version ... --query PolicyVersion.Document``:
    ``Statement`` entries with ``Effect: Allow`` and ``Action``. A document this loader
    cannot read faithfully (a Deny, ``NotAction``, a ``Condition``, a resource other than
    ``*``) raises, so a real copy of a policy is never read as something it is not.
    """
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    statements = document["Statement"]
    if isinstance(statements, dict):
        statements = [statements]
    actions: List[str] = []
    for statement in statements:
        for unsupported in ("NotAction", "NotResource", "Condition"):
            if unsupported in statement:
                raise ValueError(
                    f"{path}: {unsupported} is not supported by policy_sim"
                )
        if statement.get("Effect") != "Allow":
            raise ValueError(f"{path}: only Allow statements are supported")
        resource = statement.get("Resource", "*")
        if resource not in ("*", ["*"]):
            raise ValueError(f"{path}: only Resource '*' is supported")
        value = statement["Action"]
        actions.extend([value] if isinstance(value, str) else value)
    return actions


def read_only_access_actions() -> List[str]:
    """The allow-list of the ``ReadOnlyAccess`` fixture (PROVISIONAL until replaced)."""
    return load_policy_actions(DATA_DIR / "ReadOnlyAccess.json")


# Error code of each service family when an action is not allowed. The query and
# rest-xml services answer ``AccessDenied``; the json services ``AccessDeniedException``;
# EC2 and SNS have their own.
_OWN_DENIED_CODE = {"ec2": "UnauthorizedOperation", "sns": "AuthorizationError"}


def denied_code_for(service: str, protocol: str) -> str:
    if service in _OWN_DENIED_CODE:
        return _OWN_DENIED_CODE[service]
    if protocol in ("json", "rest-json", "smithy-rpc-v2-cbor"):
        return "AccessDeniedException"
    return "AccessDenied"


class PolicySim:
    """One simulated identity. Use ``allow_only`` to get one."""

    def __init__(self, allow: Iterable[str], deny: Iterable[str] = ()):
        self.allow = list(allow)
        self.deny = list(deny)
        self._lock = threading.Lock()
        self.seen: List[str] = []  # every IAM action seen, in call order
        self.denied: List[str] = []  # the actions that were denied, in call order
        self.denied_calls: List[Tuple[str, str, str]] = (
            []
        )  # (service, operation, action)
        self.unmapped: List[Tuple[str, str]] = []  # (service, operation)
        self._original_create_client = None

    # ----------------------------------------------------------------- decision
    def is_allowed(self, action: str) -> bool:
        """IAM's rule: an explicit Deny wins; otherwise an Allow is needed."""
        if matches_any(action, self.deny):
            return False
        return matches_any(action, self.allow)

    @property
    def seen_set(self) -> Set[str]:
        with self._lock:
            return set(self.seen)

    @property
    def denied_set(self) -> Set[str]:
        with self._lock:
            return set(self.denied)

    # --------------------------------------------------------------------- hook
    def _before_call(self, model=None, **kwargs):
        service = model.service_model.service_name
        operation = model.name
        action = iam_action_for(service, operation)
        if action is None:
            with self._lock:
                self.unmapped.append((service, operation))
            return None  # let it through; assert_all_mapped() fails the test
        allowed = self.is_allowed(action)
        with self._lock:
            self.seen.append(action)
            if not allowed:
                self.denied.append(action)
                self.denied_calls.append((service, operation, action))
        if allowed:
            return None
        code = denied_code_for(service, model.service_model.protocol)
        parsed = {
            "Error": {
                "Code": code,
                "Message": (
                    f"User: arn:aws:iam::123456789012:user/policy-sim is not authorized "
                    f"to perform: {action} (policy_sim)"
                ),
            },
            "ResponseMetadata": {"HTTPStatusCode": 403},
        }
        # Returning a response (instead of raising) lets botocore build the error the
        # way it does for a real answer, including the service's modelled exceptions.
        response = AWSResponse("https://policy-sim.invalid/", 403, {}, None)
        return response, parsed

    # ------------------------------------------------------------------- install
    def install(self) -> "PolicySim":
        original = botocore.session.Session.create_client
        self._original_create_client = original
        sim = self

        def create_client(session, *args, **kwargs):
            client = original(session, *args, **kwargs)
            client.meta.events.register_last(
                "before-call", sim._before_call, unique_id="inventag-policy-sim"
            )
            return client

        create_client.__wrapped__ = original
        botocore.session.Session.create_client = create_client
        return self

    def uninstall(self) -> None:
        if self._original_create_client is not None:
            botocore.session.Session.create_client = self._original_create_client
            self._original_create_client = None

    # -------------------------------------------------------------------- checks
    def assert_all_mapped(self) -> None:
        """Fail, naming each operation, when a call had no IAM action."""
        if self.unmapped:
            names = ", ".join(sorted({f"{s}.{o}" for s, o in self.unmapped}))
            raise AssertionError(
                f"AWS operation(s) with no IAM action in tests/policy_sim.py: {names}. "
                "Add the operation to READ_ONLY_ACTIONS (inventag/security/iam_policy.py) "
                "if InvenTag should list it in its policy, or to EXTRA_ACTIONS in "
                "tests/policy_sim.py with the reason."
            )


@contextmanager
def allow_only(actions: Iterable[str], deny: Iterable[str] = ()):
    """Run the block as an identity that holds only ``actions`` (IAM wildcards allowed).

    ``deny`` is a list of patterns that win over ``actions`` (an explicit Deny, which is
    how a test writes "ReadOnlyAccess minus these"). Yields the :class:`PolicySim`.
    Install it after the moto estate is seeded: only clients created inside the block are
    subject to it.
    """
    sim = PolicySim(actions, deny).install()
    try:
        yield sim
    finally:
        sim.uninstall()
