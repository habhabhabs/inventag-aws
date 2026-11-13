"""classify(): one row per entry of the mapping tables of design section 1.2.

The expected tables are written out here, not read from the module, so a
change to a table in the code is a change to this file too (invariant I13).
"""

import concurrent.futures
import importlib
import socket
import ssl

import botocore.exceptions as bexc
import pytest
from botocore.retries.standard import ThrottledRetryableChecker

from inventag.outcome.model import RETRYABLE, Category, Scope
from tests.unit.outcome.helpers import bare, client_error

# The module, not the function of the same name that inventag.outcome exports.
cl = importlib.import_module("inventag.outcome.classify")

C = Category

# Table C (design 1.2), category -> codes; NOT_FOUND codes are resource scope.
TABLE_C = {
    C.CREDENTIALS: [
        "ExpiredTokenException",
        "UnrecognizedClientException",
        "MissingAuthenticationToken",
        "InvalidToken",
        "InvalidIdentityToken",
        "IDPCommunicationError",
        "IDPRejectedClaim",
        "InvalidGrantException",
        "UnauthorizedClientException",
        "ExpiredToken",
        "RequestExpired",
        "InvalidClientTokenId",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "IncompleteSignature",
        "InvalidSignatureException",
        "AuthFailure",
        "TokenRefreshRequired",
    ],
    C.PERMISSION_DENIED: [
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
        "UnauthorizedException",
        "AuthorizationError",
        "AuthorizationErrorException",
        "NotAuthorizedException",
        "AccessDeniedFault",
        "ForbiddenException",
        "KMSAccessDeniedException",
        "OrganizationAccessDeniedException",
        "Forbidden",
        "403",
        "KMS.AccessDeniedException",
        "UnauthorizedAccess",
    ],
    C.NOT_ENABLED: [
        "OptInRequiredException",
        "SubscriptionRequiredException",
        "RegionDisabledException",
        "AWSOrganizationsNotInUseException",
        "PendingVerification",
        "OptInRequired",
        "NotSignedUp",
        "AllAccessDisabled",
        "AccountProblem",
        "Blocked",
    ],
    C.NOT_AVAILABLE: [
        "UnsupportedOperation",
        "UnsupportedOperationException",
        "InvalidAction",
        "UnknownOperationException",
    ],
    C.NOT_FOUND: [
        "ResourceNotFoundException",
        "NoSuchEntity",
        "NoSuchBucket",
        "NotFoundException",
        "404",
    ],
    C.THROTTLED: [
        "ThrottlingException",
        "ThrottledException",
        "TooManyRequestsException",
        "RequestLimitExceeded",
        "RequestThrottled",
        "RequestThrottledException",
        "ProvisionedThroughputExceededException",
        "LimitExceededException",
        "TransactionInProgressException",
        "PriorRequestNotComplete",
        "EC2ThrottledException",
        "Throttling",
        "SlowDown",
        "BandwidthLimitExceeded",
    ],
    C.TIMEOUT: [
        "RequestTimeout",
        "RequestTimeoutException",
        "DependencyTimeoutException",
    ],
    C.SERVICE_ERROR: [
        "InternalFailure",
        "InternalError",
        "InternalServerError",
        "InternalServerException",
        "InternalServiceError",
        "InternalServiceException",
        "ServiceUnavailable",
        "ServiceUnavailableException",
        "ServiceFailure",
        "ServiceException",
        "ServerException",
        "KMSInternalException",
        "InvalidNextToken",
        "InvalidNextTokenException",
        "ExpiredNextTokenException",
        "PaginationTokenExpiredException",
        "InvalidPaginationToken",
    ],
    C.INTERNAL_ERROR: [
        "ValidationException",
        "ValidationError",
        "InvalidParameterValue",
        "InvalidParameter",
        "InvalidParameterException",
        "InvalidParameterCombination",
        "MissingParameter",
        "InvalidArgument",
        "InvalidInput",
        "InvalidRequest",
        "InvalidRequestException",
        "MalformedQueryString",
        "SerializationException",
    ],
}
TABLE_C_ROWS = [(code, cat) for cat, codes in TABLE_C.items() for code in codes]

# Table D: (service, code, message) -> category
TABLE_D_ROWS = [
    ("stepfunctions", "InvalidToken", "", C.SERVICE_ERROR),
    ("sso", "UnauthorizedException", "", C.CREDENTIALS),
    ("ce", "DataUnavailableException", "", C.NOT_ENABLED),
    (
        "ce",
        "AccessDeniedException",
        "User is not enabled for cost explorer access",
        C.NOT_ENABLED,
    ),
]

# Table E: (phase, code) -> category
TABLE_E_ROWS = [
    ("region_check", "AuthFailure", C.NOT_ENABLED),
    ("region_check", "UnrecognizedClientException", C.NOT_ENABLED),
    ("region_check", "InvalidClientTokenId", C.NOT_ENABLED),
    ("assume_role", "ValidationError", C.INVALID_INPUT),
    ("assume_role", "MalformedPolicyDocument", C.INVALID_INPUT),
    ("upload", "NoSuchBucket", C.INVALID_INPUT),
    ("upload", "PermanentRedirect", C.INVALID_INPUT),
    ("upload", "AuthorizationHeaderMalformed", C.INVALID_INPUT),
    ("upload", "IllegalLocationConstraintException", C.INVALID_INPUT),
    ("upload", "KMS.NotFoundException", C.INVALID_INPUT),
]

# Table F: unknown code, by HTTP status
TABLE_F_ROWS = [
    (429, C.THROTTLED),
    (401, C.PERMISSION_DENIED),
    (403, C.PERMISSION_DENIED),
    (408, C.TIMEOUT),
    (400, C.SERVICE_ERROR),
    (500, C.SERVICE_ERROR),
    (503, C.SERVICE_ERROR),
]

# "Not found" pattern (resource scope)
NOT_FOUND_PATTERN_CODES = [
    "NoSuchKey",
    "NoSuchHostedZone",
    "DBInstanceNotFound",
    "ClusterNotFoundException",
    "CacheClusterNotFoundFault",
    "InvalidVpcID.NotFound",
]

# Table B: botocore class name -> category
TABLE_B = {
    C.CREDENTIALS: [
        "NoCredentialsError",
        "PartialCredentialsError",
        "CredentialRetrievalError",
        "UnknownCredentialError",
        "ProfileNotFound",
        "SSOError",
        "SSOTokenLoadError",
        "UnauthorizedSSOTokenError",
        "TokenRetrievalError",
        "NoAuthTokenError",
        "RefreshWithMFAUnsupportedError",
        "MetadataRetrievalError",
        "LoginError",
        "LoginRefreshRequired",
        "LoginTokenLoadError",
    ],
    C.TIMEOUT: ["ReadTimeoutError"],
    C.NETWORK: [
        "ConnectionError",
        "EndpointConnectionError",
        "ConnectTimeoutError",
        "SSLError",
        "ProxyConnectionError",
        "HTTPClientError",
        "ConnectionClosedError",
        "ResponseStreamingError",
        "IncompleteReadError",
    ],
    C.NOT_AVAILABLE: [
        "UnknownServiceError",
        "UnknownEndpointError",
        "ServiceNotInRegionError",
        "EndpointProviderError",
        "EndpointResolutionError",
    ],
    C.INVALID_INPUT: [
        "NoRegionError",
        "InvalidRegionError",
        "UnknownRegionError",
        "InvalidConfigError",
        "InfiniteLoopConfigError",
        "ConfigNotFound",
        "ConfigParseError",
        "InvalidProxiesConfigError",
        "InvalidIMDSEndpointError",
        "InvalidRetryConfigurationError",
        "MissingDependencyException",
    ],
    C.SERVICE_ERROR: ["PaginationError", "ChecksumError"],
    C.INTERNAL_ERROR: [
        "BotoCoreError",
        "ParamValidationError",
        "OperationNotPageableError",
        "UnknownClientMethodError",
    ],
}
TABLE_B_ROWS = [(name, cat) for cat, names in TABLE_B.items() for name in names]


@pytest.mark.parametrize("code,expected", TABLE_C_ROWS)
def test_table_c_aws_codes(code, expected):
    scope = Scope.RESOURCE if expected is C.NOT_FOUND else Scope.SERVICE
    issue = cl.classify(client_error(code), scope=scope, phase="listing", service="sqs")
    assert issue.category is expected
    assert issue.code == code
    assert issue.retryable == (expected in RETRYABLE)


def test_table_c_has_no_entry_missing_from_this_test():
    expected = {code for code, _ in TABLE_C_ROWS}
    assert set(cl.AWS_CODES) == expected


@pytest.mark.parametrize("service,code,message,expected", TABLE_D_ROWS)
def test_table_d_service_codes(service, code, message, expected):
    issue = cl.classify(
        client_error(code, message),
        scope=Scope.SERVICE,
        phase="billing",
        service=service,
    )
    assert issue.category is expected


def test_table_d_ce_access_denied_without_the_text_is_a_permission_problem():
    issue = cl.classify(
        client_error("AccessDeniedException", "not authorized to perform ce:Get"),
        scope=Scope.SERVICE,
        phase="billing",
        service="ce",
    )
    assert issue.category is C.PERMISSION_DENIED


def test_table_d_invalid_token_elsewhere_is_credentials():
    issue = cl.classify(client_error("InvalidToken"), scope=Scope.SERVICE, service="s3")
    assert issue.category is C.CREDENTIALS


def test_table_d_has_no_entry_missing_from_this_test():
    assert set(cl.SERVICE_CODES) == {(s, c) for s, c, m, _ in TABLE_D_ROWS if not m}


@pytest.mark.parametrize("phase,code,expected", TABLE_E_ROWS)
def test_table_e_phase_codes(phase, code, expected):
    scope = Scope.OUTPUT if phase == "upload" else Scope.ACCOUNT
    if phase == "region_check":
        scope = Scope.REGION
    issue = cl.classify(client_error(code), scope=scope, phase=phase, service="x")
    assert issue.category is expected


def test_table_e_has_no_entry_missing_from_this_test():
    assert set(cl.PHASE_CODES) == {(p, c) for p, c, _ in TABLE_E_ROWS}


def test_table_e_wins_over_table_c():
    # AuthFailure is a credential error everywhere but in the region check.
    listing = cl.classify(client_error("AuthFailure"), scope=Scope.SERVICE)
    check = cl.classify(
        client_error("AuthFailure"), scope=Scope.REGION, phase="region_check"
    )
    assert listing.category is C.CREDENTIALS
    assert check.category is C.NOT_ENABLED


@pytest.mark.parametrize("status,expected", TABLE_F_ROWS)
def test_table_f_unknown_code_by_http_status(status, expected):
    issue = cl.classify(
        client_error("SomethingNobodyKnows", status=status), scope=Scope.SERVICE
    )
    assert issue.category is expected
    assert issue.code == "SomethingNobodyKnows"


def test_table_f_has_no_entry_missing_from_this_test():
    assert set(cl.HTTP_STATUS) == {
        s for s, c in TABLE_F_ROWS if c is not C.SERVICE_ERROR
    }


def test_client_error_without_code_keeps_the_status():
    issue = cl.classify(client_error("", status=503), scope=Scope.SERVICE)
    assert issue.category is C.SERVICE_ERROR
    assert issue.code == "503"


@pytest.mark.parametrize("code", NOT_FOUND_PATTERN_CODES)
def test_not_found_pattern_at_resource_scope(code):
    issue = cl.classify(client_error(code), scope=Scope.RESOURCE, phase="detail")
    assert issue.category is C.NOT_FOUND


@pytest.mark.parametrize("scope", [Scope.SERVICE, Scope.REGION, Scope.ACCOUNT])
@pytest.mark.parametrize("code", ["ResourceNotFoundException", "NoSuchKey", "404"])
def test_not_found_outside_resource_scope_is_a_service_error(scope, code):
    assert cl.classify(client_error(code), scope=scope).category is C.SERVICE_ERROR


@pytest.mark.parametrize("name,expected", TABLE_B_ROWS)
def test_table_b_botocore_classes(name, expected):
    klass = getattr(bexc, name, None)
    if klass is None:  # pragma: no cover - older botocore
        pytest.skip(f"botocore has no {name}")
    issue = cl.classify(bare(klass), scope=Scope.SERVICE)
    assert issue.category is expected
    assert issue.code == name


def test_table_b_has_no_entry_missing_from_this_test():
    assert set(cl.BOTOCORE_CLASSES) == {n for n, c in TABLE_B_ROWS} - {
        "ParamValidationError",
        "OperationNotPageableError",
        "UnknownClientMethodError",
    }


def test_read_timeout_is_tested_before_http_client_error():
    assert issubclass(bexc.ReadTimeoutError, bexc.HTTPClientError)
    issue = cl.classify(bare(bexc.ReadTimeoutError), scope=Scope.SERVICE)
    assert issue.category is C.TIMEOUT


def test_every_table_b_class_exists_in_installed_botocore():
    missing = [n for n, _ in TABLE_B_ROWS if not hasattr(bexc, n)]
    assert missing == []


def test_throttled_set_covers_botocore_retry_table():
    """A botocore upgrade that adds a throttle code fails here, not in a run."""
    botocore_codes = set(ThrottledRetryableChecker._THROTTLED_ERROR_CODES)
    ours = {code for code, cat in cl.AWS_CODES.items() if cat is C.THROTTLED}
    assert botocore_codes <= ours


# Table G: Python built-ins
TABLE_G_ROWS = [
    (KeyboardInterrupt(), Scope.RUN, "", C.CANCELLED, "KeyboardInterrupt"),
    (ssl.SSLError(1, "x"), Scope.SERVICE, "", C.NETWORK, "SSLError"),
    (socket.gaierror(-2, "x"), Scope.SERVICE, "", C.NETWORK, "gaierror"),
    (ConnectionRefusedError(), Scope.SERVICE, "", C.NETWORK, "ConnectionRefusedError"),
    (TimeoutError(), Scope.SERVICE, "", C.TIMEOUT, "TimeoutError"),
    (concurrent.futures.TimeoutError(), Scope.ACCOUNT, "", C.TIMEOUT, "TimeoutError"),
    (
        EOFError(),
        Scope.ACCOUNT,
        "credentials",
        C.CREDENTIALS,
        "MfaPromptWithoutTerminal",
    ),
    (
        EOFError(),
        Scope.ACCOUNT,
        "assume_role",
        C.CREDENTIALS,
        "MfaPromptWithoutTerminal",
    ),
    (EOFError(), Scope.ACCOUNT, "listing", C.INTERNAL_ERROR, "EOFError"),
    (OSError(28, "No space"), Scope.OUTPUT, "report", C.OUTPUT_FAILURE, "ENOSPC"),
    (PermissionError(13, "x"), Scope.OUTPUT, "report", C.OUTPUT_FAILURE, "EACCES"),
    (OSError(30, "x"), Scope.OUTPUT, "state", C.OUTPUT_FAILURE, "EROFS"),
    (FileNotFoundError(2, "x"), Scope.OUTPUT, "report", C.OUTPUT_FAILURE, "ENOENT"),
    (OSError("no errno"), Scope.OUTPUT, "report", C.OUTPUT_FAILURE, "OSError"),
    (OSError(28, "x"), Scope.SERVICE, "listing", C.INTERNAL_ERROR, "OSError"),
    (KeyError("x"), Scope.SERVICE, "", C.INTERNAL_ERROR, "KeyError"),
    (TypeError("x"), Scope.SERVICE, "", C.INTERNAL_ERROR, "TypeError"),
    (AttributeError("x"), Scope.SERVICE, "", C.INTERNAL_ERROR, "AttributeError"),
]


@pytest.mark.parametrize("exc,scope,phase,expected,code", TABLE_G_ROWS)
def test_table_g_builtins(exc, scope, phase, expected, code):
    issue = cl.classify(exc, scope=scope, phase=phase)
    assert issue.category is expected
    assert issue.code == code


# InvenTag's own exceptions (real classes, as they are at ed91cd6)
def _own_exceptions():
    from inventag.core.cloud_bom_generator import (
        AccountSessionError,
        AccountTimeoutError,
        ReportGenerationError,
    )
    from inventag.core.s3_upload import S3UploadError
    from inventag.reporting.google_output import GoogleOutputError
    from inventag.reporting.report_template import TemplateValidationError
    from inventag.reporting.settings_loader import SettingsFileError
    from inventag.security.arn import InvalidRoleError
    from inventag.security.read_only_guard import ReadOnlyViolationError
    from inventag.templating.errors import TemplateError, TemplateNotFoundError

    return [
        (ReadOnlyViolationError("sqs", "CreateQueue", "not read-only"), C.GUARD_BLOCK),
        (AccountTimeoutError("late"), C.TIMEOUT),
        (bare(TemplateError), C.INVALID_INPUT),
        (bare(TemplateNotFoundError), C.INVALID_INPUT),
        (bare(TemplateValidationError), C.INVALID_INPUT),
        (bare(SettingsFileError), C.INVALID_INPUT),
        (InvalidRoleError("x"), C.INVALID_INPUT),
        (bare(S3UploadError), C.INVALID_INPUT),
        (ReportGenerationError("x"), C.OUTPUT_FAILURE),
        (GoogleOutputError("x"), C.OUTPUT_FAILURE),
        (AccountSessionError("x"), C.CREDENTIALS),
    ]


@pytest.mark.parametrize("index", range(11))
def test_own_exceptions(index):
    exc, expected = _own_exceptions()[index]
    assert cl.classify(exc, scope=Scope.ACCOUNT).category is expected
    assert cl.classify(exc, scope=Scope.ACCOUNT).code == type(exc).__name__


def test_own_exception_names_are_all_listed():
    names = {type(e).__name__ for e, _ in _own_exceptions()}
    assert names | {"BudgetExceeded", "RunCancelled"} == set(cl.OWN_CLASS_CATEGORIES)


def test_class_attribute_wins_over_the_name_table():
    class AccountStopped(Exception):
        inventag_category = "credentials"

    class RunCancelled(BaseException):
        inventag_category = "cancelled"

    assert cl.classify(AccountStopped(), scope=Scope.ACCOUNT).category is C.CREDENTIALS
    assert cl.classify(RunCancelled(), scope=Scope.RUN).category is C.CANCELLED


def test_name_table_ignores_classes_outside_inventag():
    class ReadOnlyViolationError(Exception):
        pass

    issue = cl.classify(ReadOnlyViolationError(), scope=Scope.SERVICE)
    assert issue.category is C.INTERNAL_ERROR


def test_account_session_error_is_classified_by_its_cause():
    from inventag.core.cloud_bom_generator import AccountSessionError

    try:
        try:
            raise client_error("AccessDenied", "not authorized to assume")
        except Exception as cause:
            raise AccountSessionError("could not") from cause
    except AccountSessionError as exc:
        issue = cl.classify(exc, scope=Scope.ACCOUNT, account="222222222222")
    assert issue.category is C.PERMISSION_DENIED
    assert issue.phase == "credentials"
    assert issue.code == "AccessDenied"
    assert issue.account == "222222222222"


def test_context_fields_are_kept():
    issue = cl.classify(
        client_error("AccessDenied"),
        scope=Scope.RESOURCE,
        phase="detail",
        account="111111111111",
        region="eu-west-1",
        service="s3",
        operation="GetBucketLocation",
        resource="my-bucket",
    )
    assert (issue.account, issue.region, issue.service, issue.operation) == (
        "111111111111",
        "eu-west-1",
        "s3",
        "GetBucketLocation",
    )
    assert issue.regions == ("eu-west-1",)
    assert issue.examples == ("my-bucket",)
    assert issue.message == ""  # wording comes after merging


def test_str_of_the_exception_is_never_stored():
    class Leaky(Exception):
        def __str__(self):
            return "SECRET-TEXT-FROM-STR"

    issue = cl.classify(Leaky(), scope=Scope.SERVICE)
    assert "SECRET-TEXT-FROM-STR" not in repr(issue)


def test_aws_message_is_cleaned_and_cut():
    message = (
        "User: arn:aws:sts::222222222222:assumed-role/InvenTagRole/s is not "
        "authorized   to perform: sqs:ListQueues "
        + "x" * 400
        + " Encoded authorization failure message: abcdef"
    )
    issue = cl.classify(client_error("AccessDenied", message), scope=Scope.SERVICE)
    assert issue.aws_message.startswith(
        "User: arn:aws:sts::222222222222:assumed-role/InvenTagRole/s is not "
        "authorized to"
    )
    assert len(issue.aws_message) <= 300
    assert "Encoded authorization" not in issue.aws_message


def test_code_is_limited_to_safe_characters():
    issue = cl.classify(client_error("Bad Code\n<script>"), scope=Scope.SERVICE)
    assert issue.code == "BadCodescript"


def test_issue_is_frozen_and_validates_its_category():
    issue = cl.classify(client_error("AccessDenied"), scope="service")
    with pytest.raises(Exception):
        issue.category = C.TIMEOUT
    with pytest.raises(ValueError):
        cl.Issue(scope=Scope.SERVICE, category="no_such_category")
