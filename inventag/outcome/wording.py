"""What each issue says: "what happened", "Instead: ..." and "More: <URL>".

One table for every category (:data:`CATEGORY_WORDING`), with more exact
entries per scope, per phase and per error code. :func:`apply` fills an
issue's ``message``, ``next_step`` and ``more`` after issues are merged, so
the text can say "in 17 regions".

Rules (design 5.5):

* Every category has an entry, every rendered issue has a non-empty
  ``Instead:`` and a ``More:`` URL to a page that exists (tests pin both).
* The message says what is missing from the result, not only what failed.
* The IAM action in a permission message comes from the inverse of
  :data:`inventag.security.iam_policy.READ_ONLY_ACTIONS`; when the pair is not
  there the text says "the read permission for <service> <Operation>". An
  action name is never built by gluing strings.
* Three hints are read from AWS's message and only add a sentence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional, Tuple

from .model import Category, Issue, Scope

C = Category

#: Base of every "More:" URL (the docs site).
DOCS = "https://habhabhabs.github.io/inventag-aws/docs/"
ISSUES_URL = "https://github.com/habhabhabs/inventag-aws/issues"


def docs_url(path: str) -> str:
    return DOCS + path


TROUBLESHOOTING = "guides/troubleshooting"
URL_CREDENTIALS = docs_url(TROUBLESHOOTING + "#expired-or-invalid-credentials")
URL_NO_CREDENTIALS = docs_url(TROUBLESHOOTING + "#no-credentials-found")
URL_ASSUME_ROLE = docs_url(TROUBLESHOOTING + "#a-role-cannot-be-assumed")
URL_IAM = docs_url("reference/iam-permissions")
URL_COST_EXPLORER = docs_url(TROUBLESHOOTING + "#cost-explorer-access-denied")
URL_REGION = docs_url(TROUBLESHOOTING + "#a-region-is-not-enabled-for-the-account")
URL_THROTTLING = docs_url(TROUBLESHOOTING + "#throttling")
URL_GUARD = docs_url(TROUBLESHOOTING + "#blocked-by-the-read-only-guard")
URL_STILL_STUCK = docs_url(TROUBLESHOOTING + "#still-stuck")
URL_WHAT_IS_FOUND = docs_url(
    "getting-started/status#what-inventag-finds-and-what-it-does-not"
)
URL_RUN_GOES_WRONG = docs_url("getting-started/status#when-a-run-goes-wrong")
URL_CLI = docs_url("reference/cli")
URL_S3 = docs_url("reference/cli#s3-upload")
URL_EXIT_CODES = docs_url("reference/cli#exit-codes")
URL_OUTPUTS = docs_url("reference/outputs")


@dataclass(frozen=True)
class Wording:
    """Templates. ``None`` means: take it from the less exact entry."""

    what: Optional[str] = None
    instead: Optional[str] = None
    more: Optional[str] = None


_REPORT_IT = f"Run again with --debug and report it with this line at {ISSUES_URL}."

#: One entry per category: the fallback for every scope, phase and code.
CATEGORY_WORDING: Dict[Category, Wording] = {
    C.CREDENTIALS: Wording(
        "The AWS credentials{for_account} are missing, invalid or expired",
        "Sign in again (aws sso login --profile <name>) or refresh your temporary "
        "keys, then run the same command again.",
        URL_CREDENTIALS,
    ),
    C.PERMISSION_DENIED: Wording(
        "No permission for {service}{where}, so its resources there are not in "
        "the report",
        "Add {action} to the role, or leave the service out with --account-services.",
        URL_IAM,
    ),
    C.NOT_ENABLED: Wording(
        "{service} is not enabled or subscribed{where}; there was nothing to read",
        "Nothing to do if you do not use {service}. To read it, enable it for the "
        "account; to stop trying, leave it out with --account-services.",
        URL_WHAT_IS_FOUND,
    ),
    C.NOT_AVAILABLE: Wording(
        "{service} is not available{where}; there was nothing to read",
        "Nothing to do. If {service} is new, upgrade boto3; to stop trying, leave "
        "it out with --account-services.",
        URL_WHAT_IS_FOUND,
    ),
    C.NOT_FOUND: Wording(
        "{count} {service} resource(s) changed or were deleted during the scan; "
        "they are in the report with the fields from the listing",
        "Nothing to do: the next scan shows the current state.",
        URL_RUN_GOES_WRONG,
    ),
    C.THROTTLED: Wording(
        "AWS throttled {service}{where} and the retries were used up; its "
        "resources there may be missing",
        "Run again later or with --max-concurrent-accounts 1, or scan fewer "
        "regions with --account-regions.",
        URL_THROTTLING,
    ),
    C.TIMEOUT: Wording(
        "{service}{where} did not finish within the time limit; its resources "
        "there may be missing",
        "Give each account more time with --account-processing-timeout 3600, or "
        "scan fewer regions with --account-regions.",
        URL_THROTTLING,
    ),
    C.NETWORK: Wording(
        "Could not connect to AWS for {service}{where}; its resources there may "
        "be missing",
        "Check the network, the proxy (HTTPS_PROXY) and TLS settings (AWS_CA_BUNDLE "
        "for a private certificate authority); test with: aws sts "
        "get-caller-identity.",
        URL_RUN_GOES_WRONG,
    ),
    C.SERVICE_ERROR: Wording(
        "AWS returned an error for {service}{where}; its resources there may be "
        "missing",
        f"Run again later. If it repeats, report it with this line at {ISSUES_URL}.",
        URL_STILL_STUCK,
    ),
    C.GUARD_BLOCK: Wording(
        "The read-only guard blocked {operation} for {service}, so {service} was not "
        "read. This is a defect in InvenTag, not in your account; nothing was "
        "changed",
        f"Report it with the file from --audit-output at {ISSUES_URL}.",
        URL_GUARD,
    ),
    C.INVALID_INPUT: Wording(
        "A value given for this run is not valid",
        "Check the options and files you passed (inventag --help lists the "
        "options; inventag --validate-config-only checks a configuration without "
        "scanning).",
        URL_CLI,
    ),
    C.OUTPUT_FAILURE: Wording(
        "The {service} output could not be written",
        "Check that the output folder exists, is writable and has free space, and "
        "that the file is not open in another program; then run again.",
        URL_OUTPUTS,
    ),
    C.CANCELLED: Wording(
        "The run was stopped before it finished",
        "Run the same command with --resume to continue; finished accounts are "
        "reused.",
        URL_EXIT_CODES,
    ),
    C.INTERNAL_ERROR: Wording(
        "An unexpected error occurred in InvenTag{for_service}; this is a defect",
        _REPORT_IT,
        URL_STILL_STUCK,
    ),
}

#: More exact entries per (scope, category).
SCOPE_WORDING: Dict[Tuple[Scope, Category], Wording] = {
    (Scope.RESOURCE, C.PERMISSION_DENIED): Wording(
        "Details of {count} {service} resource(s) could not be read; they are in "
        "the report with the fields from the listing",
        "Add {action} to the role to see the missing fields.",
    ),
    (Scope.RESOURCE, C.THROTTLED): Wording(
        "Details of {count} {service} resource(s) could not be read (throttled); "
        "they are in the report with the fields from the listing",
    ),
    (Scope.RESOURCE, C.TIMEOUT): Wording(
        "Details of {count} {service} resource(s) were not read (time limit); they "
        "are in the report with the fields from the listing",
    ),
    (Scope.RESOURCE, C.SERVICE_ERROR): Wording(
        "Details of {count} {service} resource(s) could not be read; they are in "
        "the report with the fields from the listing",
    ),
    (Scope.RESOURCE, C.INTERNAL_ERROR): Wording(
        "Details of {count} {service} resource(s) could not be read (InvenTag did "
        "not understand the response); they are in the report with the fields "
        "from the listing",
    ),
    (Scope.REGION, C.PERMISSION_DENIED): Wording(
        "No permission to check region {region} for account {account}; it was not "
        "scanned",
        "Add {action} to the role, or remove the region from --account-regions.",
    ),
    (Scope.REGION, C.NOT_ENABLED): Wording(
        "Region {region} is not enabled for account {account}; it was not scanned",
        "Enable the region in AWS (Account settings, AWS Regions), or remove it "
        "from --account-regions.",
        URL_REGION,
    ),
    (Scope.REGION, C.NETWORK): Wording(
        "Could not connect to AWS in region {region}; it was not scanned",
    ),
    (Scope.REGION, C.TIMEOUT): Wording(
        "Region {region} did not answer in time; it was not scanned",
    ),
    (Scope.REGION, C.SERVICE_ERROR): Wording(
        "AWS returned an error when region {region} was checked; it was not scanned",
    ),
    (Scope.ACCOUNT, C.PERMISSION_DENIED): Wording(
        "No permission to read account {account}; it is not in the report",
        "Attach the read-only policy to the role and run again.",
    ),
    (Scope.ACCOUNT, C.TIMEOUT): Wording(
        "Account {account} did not finish within the time limit "
        "(--account-processing-timeout); resources found before the limit are in "
        "the report, others may be missing",
        "Give the account more time with --account-processing-timeout 3600, or "
        "scan fewer regions with --account-regions.",
    ),
    (Scope.ACCOUNT, C.NOT_ENABLED): Wording(
        "Account {account} is not active or not signed up for AWS; it is not in "
        "the report",
        "Check the account's status in AWS Organizations, and leave it out of the "
        "accounts file until it is active.",
    ),
    (Scope.ACCOUNT, C.NETWORK): Wording(
        "Could not connect to AWS for account {account}; it is not in the report",
    ),
    (Scope.ACCOUNT, C.INTERNAL_ERROR): Wording(
        "The scan of account {account} stopped with an unexpected error in "
        "InvenTag; it is not in the report",
    ),
    (Scope.ACCOUNT, C.CANCELLED): Wording(
        "Account {account} was not scanned: the run was stopped",
    ),
    (Scope.OUTPUT, C.GUARD_BLOCK): Wording(
        "The read-only guard blocked {operation} during the {service} output, so it "
        "was not written. This is a defect in InvenTag; nothing was changed",
    ),
    (Scope.OUTPUT, C.PERMISSION_DENIED): Wording(
        "No permission to write the {service} output",
        "Check that the identity may write where the output goes (for --s3-bucket: "
        "s3:PutObject on the bucket, and kms:GenerateDataKey with "
        "--s3-kms-key-id).",
        URL_S3,
    ),
    (Scope.OUTPUT, C.NETWORK): Wording(
        "Could not connect to write the {service} output",
    ),
    (Scope.OUTPUT, C.INTERNAL_ERROR): Wording(
        "The {service} output was not written because of an unexpected error in "
        "InvenTag; this is a defect",
    ),
    (Scope.RUN, C.PERMISSION_DENIED): Wording(
        "No permission for a call the run needs",
        "Attach the read-only policy to the identity and run again.",
    ),
    (Scope.RUN, C.NETWORK): Wording(
        "Could not connect to AWS",
    ),
}

#: More exact entries per (phase, category). Win over scope entries.
PHASE_WORDING: Dict[Tuple[str, Category], Wording] = {
    ("assume_role", C.PERMISSION_DENIED): Wording(
        "Could not assume the role in account {account}",
        "Check the role name or ARN, the role's trust policy, the external ID and "
        "any SCP; test with: aws sts assume-role --role-arn <arn> "
        "--role-session-name test.",
        URL_ASSUME_ROLE,
    ),
    ("assume_role", C.CREDENTIALS): Wording(
        "Could not assume the role in account {account}: the credentials used to "
        "reach it are missing, invalid or expired",
        None,
        URL_ASSUME_ROLE,
    ),
    ("assume_role", C.INVALID_INPUT): Wording(
        "The role ARN or session values for account {account} are not valid",
        "Check the role ARN in the accounts file or in --cross-account-role.",
        URL_ASSUME_ROLE,
    ),
    ("billing", C.PERMISSION_DENIED): Wording(
        "No permission for Cost Explorer; the run continues without billing data",
        "Add ce:GetCostAndUsage to the role, or pass --no-billing-validation to "
        "make no Cost Explorer calls.",
        URL_COST_EXPLORER,
    ),
    ("billing", C.NOT_ENABLED): Wording(
        "Cost Explorer is not enabled or has no data yet; the run continues without "
        "billing data",
        "Enable Cost Explorer in the AWS Billing console (data appears after about "
        "a day), or pass --no-billing-validation to make no Cost Explorer calls.",
        URL_COST_EXPLORER,
    ),
    ("billing", C.THROTTLED): Wording(
        "AWS throttled Cost Explorer; the run continues without billing data",
        "Run again later, or pass --no-billing-validation to make no Cost Explorer "
        "calls.",
        URL_COST_EXPLORER,
    ),
    ("upload", C.INVALID_INPUT): Wording(
        "The S3 bucket, its region or the KMS key given for the upload is not valid; "
        "nothing was uploaded",
        "Check --s3-bucket and --s3-kms-key-id; test with: aws s3api head-bucket "
        "--bucket <name>.",
        URL_S3,
    ),
    ("state", C.OUTPUT_FAILURE): Wording(
        "The state snapshot could not be saved; the next run cannot compare with "
        "this one",
    ),
}

#: More exact entries per error code. Win over everything.
CODE_WORDING: Dict[str, Wording] = {
    "NoCredentialsError": Wording(
        "No AWS credentials were found",
        "Sign in with aws sso login --profile <name>, or set AWS_PROFILE, then run "
        "again.",
        URL_NO_CREDENTIALS,
    ),
    "ProfileNotFound": Wording(
        "The AWS profile named for this run does not exist",
        "Check the profile name with aws configure list-profiles.",
        URL_NO_CREDENTIALS,
    ),
    "ExpiredToken": Wording(
        "The session for account {account} expired during the scan; resources "
        "after that point are not in the report",
        "Sign in again and run the same command with --resume; for long scans use "
        "a session that lasts longer than the scan.",
        URL_CREDENTIALS,
    ),
    "MfaPromptWithoutTerminal": Wording(
        "The AWS profile asks for an MFA code, but there is no terminal to type it in",
        "Get a session first (aws sts get-session-token, or aws sso login) and use "
        "that profile, or run InvenTag in a terminal.",
        URL_CREDENTIALS,
    ),
    "InvalidRegionError": Wording(
        "A region name is not known to the installed boto3",
        "Check the names in --account-regions (for example eu-west-1), or upgrade "
        "boto3.",
        URL_CLI,
    ),
    "ENOSPC": Wording(
        "The {service} output could not be written: the disk is full",
        "Free space in the output folder or pass another --output-directory, then "
        "run again.",
    ),
}
CODE_WORDING["ExpiredTokenException"] = CODE_WORDING["ExpiredToken"]
CODE_WORDING["RequestExpired"] = CODE_WORDING["ExpiredToken"]
CODE_WORDING["UnknownRegionError"] = CODE_WORDING["InvalidRegionError"]
CODE_WORDING["NoRegionError"] = Wording(
    "No AWS region is set for this run",
    "Pass --account-regions, or set AWS_DEFAULT_REGION.",
    URL_CLI,
)

#: Hints read from AWS's message (lower case). Each only adds a sentence.
SCP_HINT = (
    "service control policy",
    "A service control policy of your AWS Organization denies this; ask its "
    "administrator, or leave the service or region out.",
)
EXPLICIT_DENY_HINT = (
    "explicit deny",
    "A policy denies this explicitly; ask the owner of that policy.",
)

_ACTIONS: Optional[Dict[Tuple[str, str], str]] = None


def iam_action(service: str, operation: str) -> Optional[str]:
    """The IAM action for a botocore service and operation, if InvenTag lists it."""
    global _ACTIONS
    if _ACTIONS is None:
        from inventag.security.iam_policy import READ_ONLY_ACTIONS

        _ACTIONS = {pair: action for action, pair in READ_ONLY_ACTIONS.items()}
    return _ACTIONS.get((service, operation))


def _action_text(issue: Issue) -> str:
    action = iam_action(issue.service, issue.operation)
    if action:
        return action
    if issue.operation:
        return f"the read permission for {issue.service} {issue.operation}"
    if issue.service:
        return f"the read permissions for {issue.service}"
    return "the read permission"


def _where(issue: Issue) -> str:
    regions = [r for r in issue.regions if r]
    if not regions and issue.region:
        regions = [issue.region]
    if len(regions) == 1:
        return "" if regions[0] == "global" else f" in {regions[0]}"
    if len(regions) > 1:
        return f" in {len(regions)} regions"
    return ""


def wording_for(issue: Issue) -> Wording:
    """The resolved templates for ``issue`` (code, phase, scope, category)."""
    chain = [
        CODE_WORDING.get(issue.code),
        PHASE_WORDING.get((issue.phase, issue.category)),
        SCOPE_WORDING.get((issue.scope, issue.category)),
        CATEGORY_WORDING[issue.category],
    ]
    what = instead = more = None
    for entry in chain:
        if entry is None:
            continue
        what = what if what is not None else entry.what
        instead = instead if instead is not None else entry.instead
        more = more if more is not None else entry.more
    return Wording(what, instead, more)


def _fields(issue: Issue) -> Dict[str, str]:
    return {
        "service": issue.service or "a service",
        "operation": issue.operation or "a call",
        "account": issue.account or "(unknown)",
        "region": issue.region or (issue.regions[0] if issue.regions else "(unknown)"),
        "where": _where(issue),
        "count": str(issue.count),
        "action": _action_text(issue),
        "for_account": f" for account {issue.account}" if issue.account else "",
        "for_service": f" while reading {issue.service}" if issue.service else "",
    }


def _suffix(issue: Issue) -> str:
    if issue.operation and issue.code:
        return f" ({issue.operation}: {issue.code})"
    if issue.code:
        return f" ({issue.code})"
    return ""


def render_texts(issue: Issue) -> Tuple[str, str, str]:
    """(message, next_step, more) for ``issue``."""
    w = wording_for(issue)
    fields = _fields(issue)
    message = w.what.format(**fields) + _suffix(issue)
    next_step = w.instead.format(**fields)
    if issue.category is C.PERMISSION_DENIED and issue.aws_message:
        lowered = issue.aws_message.lower()
        for phrase, sentence in (SCP_HINT, EXPLICIT_DENY_HINT):
            if phrase in lowered:
                next_step = f"{sentence} {next_step}"
                break
    return message, next_step, w.more


def apply(issue: Issue) -> Issue:
    """``issue`` with ``message``, ``next_step`` and ``more`` filled where empty."""
    message, next_step, more = render_texts(issue)
    return replace(
        issue,
        message=issue.message or message,
        next_step=issue.next_step or next_step,
        more=issue.more or more,
    )
