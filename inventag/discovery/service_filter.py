"""
Service and tag filters applied to discovery results.

``--account-services`` and ``--account-tags`` used to be honoured by only one
discovery path (the Resource Groups Tagging API). Every other path added its
resources unfiltered, so a "filtered" report still listed other services.

The functions here filter the final resource list, so the result is the same
whichever path found a resource.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Set

# Different discovery paths name the same service differently (boto3 client
# name, ARN service code, Cost Explorer name, display name). Map the variants
# to one key. Keys and values are already in canonical form (see _squash).
_ALIASES = {
    "elbv2": "elb",
    "elasticloadbalancing": "elb",
    "elasticloadbalancingv2": "elb",
    "elasticloadbalancer": "elb",
    "apigatewayv2": "apigateway",
    "wafv2": "waf",
    "wafregional": "waf",
    "systemsmanager": "ssm",
    "keymanagementservice": "kms",
    "cloudwatchevents": "events",
    "eventbridge": "events",
    "cloudwatchlogs": "logs",
    "cognitoidp": "cognito",
    "cognitoidentity": "cognito",
    "states": "stepfunctions",
    "sfn": "stepfunctions",
    "es": "elasticsearch",
    "docdb": "documentdb",
    "simplestorageservice": "s3",
    "elasticcomputecloud": "ec2",
    "relationaldatabaseservice": "rds",
    "simplenotificationservice": "sns",
    "simplequeueservice": "sqs",
    "certificatemanager": "acm",
    "elasticcontainerservice": "ecs",
    "elastickubernetesservice": "eks",
    "elasticcontainerregistry": "ecr",
    "elasticfilesystem": "efs",
    "elasticblockstore": "ebs",
    "identityandaccessmanagement": "iam",
}

_PREFIX_RE = re.compile(r"^(amazon|aws)(?=.)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")


def _squash(name: str) -> str:
    return _NON_ALNUM_RE.sub("", name.lower())


def canonical_service(name: Optional[str]) -> str:
    """Return a comparison key for a service name.

    ``"Route 53"``, ``"route53"`` and ``"Amazon Route 53"`` give the same key.
    """
    if not name:
        return ""
    key = _squash(str(name))
    key = _ALIASES.get(key, key)
    stripped = _PREFIX_RE.sub("", key)
    return _ALIASES.get(stripped, stripped)


def canonical_service_set(services: Optional[Iterable[str]]) -> Set[str]:
    """Canonical keys for a list of service names; empty entries are dropped."""
    return {key for key in (canonical_service(s) for s in services or []) if key}


def service_matches(name: Optional[str], allowed: Set[str]) -> bool:
    """True if ``name`` is in ``allowed`` (a set from canonical_service_set).

    An empty ``allowed`` set means "no filter".
    """
    return not allowed or canonical_service(name) in allowed


def tags_match(tags: Optional[Dict[str, Any]], tag_filters: Dict[str, Any]) -> bool:
    """True if ``tags`` satisfies every filter.

    A filter value can be a string (exact match) or a list (any of). Any other
    value only requires the tag key to be present.
    """
    if not tag_filters:
        return True
    tags = tags if isinstance(tags, dict) else {}
    for key, wanted in tag_filters.items():
        if key not in tags:
            return False
        if isinstance(wanted, str) and tags[key] != wanted:
            return False
        if isinstance(wanted, (list, tuple, set)) and tags[key] not in wanted:
            return False
    return True


def filter_resources(
    resources: List[Dict[str, Any]],
    services: Optional[Iterable[str]] = None,
    tag_filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Keep the resources that match the service list and the tag filters."""
    allowed = canonical_service_set(services)
    tag_filters = tag_filters or {}
    if not allowed and not tag_filters:
        return resources
    return [
        r
        for r in resources
        if service_matches(r.get("service"), allowed)
        and tags_match(r.get("tags"), tag_filters)
    ]
