"""The scenario table of the failure regression suite.

One entry per scenario ID of ``failure-regression-plan.md`` (sections 3 and 7,
ranges expanded), exactly once, plus a few extra rows whose ID starts with
``S1-`` for gaps found while probing that the plan has no ID for.

Every entry says where its test lives (``runner``):

``matrix``        a row of ``test_failure_matrix.py`` (tier 2, the whole CLI against moto)
``tier1``         a pure-function test in ``tests/unit/outcome/`` (WP-F1a), not written yet
``tier2``         a tier 2 row the plan lists but this package does not implement yet
``tier1+tier2``   both of the above
``existing``      covered by a test that already exists (``where`` names it)
``none``          nothing to test

Rows with ``runner == "matrix"`` also carry the injection and two sets of checks:

``current``  what v1.2.0 does today: exit code, files, messages. ALWAYS asserted; the row
             must pass. It records the behaviour, right or wrong.
``target``   what the accepted plan wants later (decisions O1 to O12). Data only: it is
             never asserted and nothing is xfail. ``wp`` names the work package that
             would make it true. ``code`` and ``issue_keys`` complete the target (exit
             code and ``run_summary.json`` issue keys). Setting ``INVENTAG_REGRESSION_DUMP``
             writes, per row, what the run did and which target checks do not hold.
``skip``     a reason: the row's current behaviour cannot be made deterministic, so the
             row is skipped (never xfail).

When a fix lands, change the row's ``current`` to the new behaviour (the test fails first
and shows the change) and drop ``wp``.

Checks are tuples, see ``checks.py``. ``code`` is the exit code under the accepted
decisions. ``issue_keys`` are keys of ``run_summary.json`` issues, written
``category`` or ``category:service`` (categories of failure-model-design.md 1.1).
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Optional, Tuple

from tests.regression.faults import Fault


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    runner: str
    owner: str
    where: str
    today: str  # the plan's "today" cell
    source: str = ""  # "run" or "code": how S1 established today's behaviour
    # --- matrix rows only -------------------------------------------------
    seed: Tuple[str, ...] = ("estate",)
    args: Tuple[str, ...] = ()
    billing: bool = False  # False adds --no-billing-validation
    accounts: Tuple[str, ...] = ()  # keys of ACCOUNTS; empty: default credentials
    faults: Tuple[Fault, ...] = ()
    limits: Dict[str, Any] = field(default_factory=dict)  # account_timeout, grace, poll
    later_runs: Tuple[Dict[str, Any], ...] = ()  # dict(args=..., faults=..., seed=...)
    process: str = "in"  # "in" (this process) or "child" (real process)
    signal: Optional[str] = None  # "SIGINT" or "SIGTERM" sent when a slow fault starts
    slow: bool = False
    skip: str = ""  # reason the row cannot run deterministically; "" = it runs
    current: Tuple[tuple, ...] = ()  # asserted: what v1.2.0 does today
    target: Tuple[tuple, ...] = ()  # data only: what the plan wants
    code: int = 0  # target exit code
    issue_keys: Tuple[str, ...] = ()  # target run_summary.json issues
    wp: str = ""  # work package that makes the target true; "" = true today

    def target_checks(self):
        checks = list(self.target)
        if not any(c[0] == "code" for c in checks):
            checks.insert(0, ("code", self.code))
        return checks + [("issue", key) for key in self.issue_keys]


def _row(id, title, runner, owner, where, today):
    return Scenario(id, title, runner, owner, where, today)


# Accounts of a multi-account scenario. The access key picks the account in the
# fault injector, and sts:GetCallerIdentity answers the account id.
ACCOUNTS = {
    "A": ("111111111111", "AKIAREGRESSION000001"),
    "B": ("222222222222", "AKIAREGRESSION000002"),
    "C": ("333333333333", "AKIAREGRESSION000003"),
}

# moto is never empty (default VPC, KMS keys): "nothing found" needs a filter.
EMPTY_ARGS = ("--account-services", "SQS")

PLAN = [
    _row(
        "A1",
        "No credentials at all",
        "tier2",
        "S2 / WP-F1a",
        "tier 2 ::A1",
        "exit 1; solutions listed; no aws sso login/AWS_PROFILE (V S2)",
    ),
    _row(
        "A2",
        "SSO token expired at start",
        "tier2",
        "S2 / WP-F1a",
        "tier 2 ::A2",
        "exit 1 after two botocore tracebacks; generic text (V S2)",
    ),
    _row(
        "A3",
        "Session token expires in the middle of a scan (`ExpiredToken`)",
        "tier2",
        "S1 gate (WP-F2), classify (WP-F1a)",
        "tier 2 ::A3",
        "ExpiredToken: one warning per service, account successful, exit 0 (V S2, T6)",
    ),
    _row(
        "A4",
        "Assume-role denied for one account (wrong external ID, trust policy, SCP)",
        "tier2",
        "S2 / WP-F1a",
        "tier 2 ::A4",
        "P1 holds; reason text internal (V S2)",
    ),
    _row(
        "A5",
        "MFA required and not supplied",
        "tier2",
        "S2 / WP-F2",
        "tier 2 ::A5",
        "MFA without TTY: EOFError, empty message, hang risk (V S2)",
    ),
    _row(
        "A6",
        "Accounts file: malformed, duplicate account IDs, a profile that does not exist, plain access keys with wrong secret",
        "tier2",
        "S2 / WP-E",
        "tier 2 ::A6",
        "invalid file exit 1, decided to stay 1 with file:line: key:; duplicate IDs silent (V S2)",
    ),
    _row(
        "A7",
        "`--credential-timeout` reached",
        "tier1+tier2",
        "S2 / WP-F1a",
        "tier 1 classify + tier 2 ::A7",
        "timeout only on the early check; generic text (R S2)",
    ),
    _row(
        "A8",
        "Credentials valid but for a different account than the file says",
        "tier2",
        "S2",
        "tier 2 ::A8",
        "refused, account failed (V S2) — decided: keep",
    ),
    _row(
        "A9",
        "SSO and web-identity sign-in under the read-only guard",
        "none",
        "—",
        "n/a",
        "early check skipped with --accounts-file (S2)",
    ),
    _row(
        "A10",
        "Credential-looking error from one region only (opt-in region not enabled)",
        "tier1+tier2",
        "S2 / WP-F2",
        "tier 1 + tier 2 ::A10",
        "(architect) region-only credential-looking error",
    ),
    _row(
        "A11",
        "Assumed-role session (1 hour by default) shorter than the scan",
        "tier2",
        "lead / WP-C3",
        "tier 2 ::A11, unit test_refreshable_role_sessions.py",
        "assumed-role session 1 h, static (R lead)",
    ),
    _row(
        "A12",
        "Guard: adversarial attempts to call a write operation",
        "existing",
        "lead",
        "tests/unit/test_read_only_guard_adversarial.py",
        "SSO / web-identity sign-in under the guard: fixed (V lead, e90e4d0)",
    ),
    _row(
        "B1",
        "1 of N accounts fails",
        "tier2",
        "lead / WP-F1a",
        "tier 2 ::B1",
        "one failed account: exit 0, named in log, summary, default workbook; not with --template (V T8)",
    ),
    _row(
        "B2",
        "All accounts fail",
        "tier2",
        "lead / WP-F1a",
        "tier 2 ::B2",
        'all failed: exit 1, no report, summary "N errors" without cause (V S2 F01)',
    ),
    _row(
        "B3",
        "One account exceeds the per-account timeout",
        "tier2",
        "lead / WP-F2",
        "tier 2 ::B3",
        "timed out: failed, partial kept and flagged (R integration)",
    ),
    _row(
        "B4",
        "Timeout of an account while its results are being merged",
        "tier1",
        "lead / WP-F2",
        "tier 1 (fake clock) ::B4",
        "timeout during merge: main thread alone merges (R)",
    ),
    _row(
        "B5",
        "`--resume` after B1 or B3",
        "tier2",
        "lead / WP-F2",
        "tier 2 ::B5",
        "--resume reuses finished accounts; stale/changed scope rescanned (V lead tests, a23d5cb)",
    ),
    _row(
        "B6",
        "Same account listed twice",
        "tier2",
        "S2 / WP-E (validator)",
        "tier 2 ::B6",
        'same account twice: one scan, "2 accounts", no warning (V L)',
    ),
    _row(
        "B7",
        "Suspended or closed account",
        "tier1",
        "S2 / WP-F1a",
        "tier 1 ::B7",
        "suspended/closed account: generic error text (R; not probed)",
    ),
    _row(
        "B8",
        "`--resume` reuses an account that had issues",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::B8",
        "(architect) resume of an account that had issues",
    ),
    _row(
        "B9",
        "Worker finishes at the instant of the deadline",
        "tier1",
        "lead / WP-F2",
        "tier 1 ::B9",
        "(architect) worker done at the deadline instant",
    ),
    _row(
        "B10",
        "A worker hangs in a call after its account was abandoned",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::B10",
        "(architect) hung worker after abandon",
    ),
    _row(
        "B11",
        "Timeout clock is per account, not shared by all accounts",
        "existing",
        "lead",
        "tests/unit/test_account_time_limit_and_failures.py",
        "shared timeout clock for all accounts: fixed (V lead tests)",
    ),
    _row(
        "B12",
        "An abandoned worker writes nothing after the main thread moved on",
        "existing",
        "lead",
        "same",
        "abandoned worker writes nothing (I15): fixed (V lead tests)",
    ),
    _row(
        "C1",
        "`ec2:DescribeRegions` denied",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::C1",
        "fallback to all regions; warning lacks the list (V S2)",
    ),
    _row(
        "C2",
        "A listed region is not enabled for the account (opt-in region)",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::C2",
        "AuthFailure warning, region skipped, not in report (V S2)",
    ),
    _row(
        "C3",
        "A region name that does not exist in `--account-regions`",
        "tier2",
        "S2 / WP-E",
        "tier 2 ::C3",
        "region typo: exit 0, KeyError text (V S2)",
    ),
    _row(
        "C4",
        "Region endpoint unreachable (timeout, DNS)",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::C4",
        "unreachable region skipped, summary silent (V S2)",
    ),
    _row(
        "C5",
        "A service control policy denies `us-east-1` (common in regulated organisations)",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::C5",
        "SCP on us-east-1: one line per global service; report silent (V S2)",
    ),
    _row(
        "C6",
        "GovCloud or China partition",
        "tier2",
        "lead / WP-F2",
        "tier 2 ::C6",
        "GovCloud: only STS identity uses the env region (V S2, partial)",
    ),
    _row(
        "C7",
        "Every region fails its access check",
        "tier2",
        "lead / WP-F2",
        "tier 2 ::C7",
        "no region answered: report still written, exit 0 (V S2, T12)",
    ),
    _row(
        "C8",
        "Region names are checked against the installed boto3 (validation)",
        "tier2",
        "S2 / WP-E",
        "tier 2 ::C8",
        "(S2) other-partition region not checked (R)",
    ),
    _row(
        "C9",
        "A region dropped by the access check",
        "tier2",
        "lead / WP-F2",
        "tier 2 ::C9",
        "(architect) dropped region only in one log line (R T11)",
    ),
    _row(
        "C10",
        "One service's endpoint cannot be reached in a region where others work",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::C10",
        "(architect) one service endpoint unreachable",
    ),
    _row(
        "D1",
        "`AccessDenied` on a list call",
        "tier2",
        "S1 / WP-F1b",
        "tier 2 ::D1",
        "denied list call: one line per service, not in --log-file, not in report (V T1)",
    ),
    _row(
        "D2",
        "`AccessDenied` on a describe call for ONE resource (for example one KMS key, one bucket's tagging)",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::D2",
        "denied describe for one resource: DEBUG only (R T20)",
    ),
    _row(
        "D3",
        "Throttling (`Throttling`, `RequestLimitExceeded`, `TooManyRequestsException`)",
        "tier2",
        "S1 / WP-F1b, S3 / WP-F2",
        "tier 2 ::D3",
        'throttled: exit 0, account scanned, next change log says "deleted" (V T5)',
    ),
    _row(
        "D4",
        "Pagination token expires or a later page fails",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::D4",
        "later page fails: earlier pages kept? (R; not probed)",
    ),
    _row(
        "D5",
        "Service not available in the region (endpoint does not exist, `UnknownEndpoint`)",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::D5",
        "missing endpoint: engine skips unlisted regions (R cd.py:863-896)",
    ),
    _row(
        "D6",
        "Service needs opt-in or a subscription (`OptInRequired`, `SubscriptionRequiredException`)",
        "tier1+tier2",
        "S1 / WP-F1b",
        "tier 1 + tier 2 ::D6",
        "OptInRequired worded as missing permission (V T4)",
    ),
    _row(
        "D7",
        "Unexpected response shape (missing key)",
        "tier1",
        "S1 / WP-F2",
        "tier 1 ::D7",
        "unexpected shape: DEBUG (R)",
    ),
    _row(
        "D8",
        "Tagging API denied but service calls work (and the reverse)",
        "tier2",
        "S1 / WP-F2",
        "tier 2 ::D8",
        'Tagging API denied: one warning; report produced (V L "denied")',
    ),
    _row(
        "D9",
        "More than one page everywhere (for example >1000 SQS queues)",
        "existing",
        "S1",
        "existing two-page test",
        ">1000 SQS queues: fixed on integration (99fc0e0)",
    ),
    _row(
        "D10",
        "A resource is deleted between list and describe (`NotFound`)",
        "tier1+tier2",
        "S1 / WP-F2 (D14 S3)",
        "tier 1 + tier 2 ::D10..D16",
        "(architect) not found, unknown code, detail throttled, per-parent partial, unreadable in one of two runs, Tagging denied twice, KMS policy",
    ),
    _row(
        "D11",
        "AWS returns an error code InvenTag does not know",
        "tier1+tier2",
        "S1 / WP-F2 (D14 S3)",
        "tier 1 + tier 2 ::D10..D16",
        "(architect) not found, unknown code, detail throttled, per-parent partial, unreadable in one of two runs, Tagging denied twice, KMS policy",
    ),
    _row(
        "D12",
        "A detail call is throttled or denied for N resources",
        "tier1+tier2",
        "S1 / WP-F2 (D14 S3)",
        "tier 1 + tier 2 ::D10..D16",
        "(architect) not found, unknown code, detail throttled, per-parent partial, unreadable in one of two runs, Tagging denied twice, KMS policy",
    ),
    _row(
        "D13",
        "Per-parent listing: one parent fails (ECS services of cluster 3 of 5)",
        "tier1+tier2",
        "S1 / WP-F2 (D14 S3)",
        "tier 1 + tier 2 ::D10..D16",
        "(architect) not found, unknown code, detail throttled, per-parent partial, unreadable in one of two runs, Tagging denied twice, KMS policy",
    ),
    _row(
        "D14",
        "A service is unreadable in exactly one of two consecutive runs",
        "tier1+tier2",
        "S1 / WP-F2 (D14 S3)",
        "tier 1 + tier 2 ::D10..D16",
        "(architect) not found, unknown code, detail throttled, per-parent partial, unreadable in one of two runs, Tagging denied twice, KMS policy",
    ),
    _row(
        "D15",
        "The Tagging API is denied in both runs",
        "tier1+tier2",
        "S1 / WP-F2 (D14 S3)",
        "tier 1 + tier 2 ::D10..D16",
        "(architect) not found, unknown code, detail throttled, per-parent partial, unreadable in one of two runs, Tagging denied twice, KMS policy",
    ),
    _row(
        "D16",
        "A describe call fails because of a KMS key policy (`KMSAccessDeniedException`)",
        "tier1+tier2",
        "S1 / WP-F2 (D14 S3)",
        "tier 1 + tier 2 ::D10..D16",
        "(architect) not found, unknown code, detail throttled, per-parent partial, unreadable in one of two runs, Tagging denied twice, KMS policy",
    ),
    _row(
        "E1",
        "Cost Explorer `AccessDenied`",
        "tier2",
        "S1 / WP-F1b",
        "tier 2 ::E1",
        "Cost Explorer denied: one warning, continues (R, page)",
    ),
    _row(
        "E2",
        "Cost Explorer not enabled for the account (`DataUnavailableException` or similar)",
        "tier1",
        "S1 / WP-F1b",
        "tier 1 ::E2,E6,E7",
        "not enabled / no data: same text as denied (R)",
    ),
    _row(
        "E6",
        'Cost Explorer not enabled (`AccessDeniedException` with the "not enabled" message)',
        "tier1",
        "S1 / WP-F1b",
        "tier 1 ::E2,E6,E7",
        "not enabled / no data: same text as denied (R)",
    ),
    _row(
        "E7",
        "Cost Explorer has no data yet (`DataUnavailableException`)",
        "tier1",
        "S1 / WP-F1b",
        "tier 1 ::E2,E6,E7",
        "not enabled / no data: same text as denied (R)",
    ),
    _row(
        "E3",
        "Cost Explorer throttled",
        "tier2",
        "S1 / WP-F1b",
        "tier 2 ::E3",
        "throttled: botocore retries, then warning (R)",
    ),
    _row(
        "E4",
        "`--no-billing-validation`",
        "existing",
        "S1",
        "tests/e2e/test_cli_billing_and_fallback.py",
        "--no-billing-validation: zero CE calls (V existing e2e test)",
    ),
    _row(
        "E5",
        "`--enable-cost-analysis`: Pricing API denied, throttled, or no price found",
        "tier1",
        "S1 / WP-F3",
        "tier 1 ::E5",
        "Pricing denied/throttled/no price: per-run cache, one warning per key (R pricing fix)",
    ),
    _row(
        "F1",
        "Account truly has no resources",
        "tier2",
        "S3 / WP-F1a",
        "tier 2 ::F1",
        "no report, warning, exit 0; --template writes an empty report (V T2)",
    ),
    _row(
        "F2",
        "Filters removed everything",
        "tier2",
        "S2 / WP-F1a",
        "tier 2 ::F2",
        "filters removed all: same warning, filter not named (R)",
    ),
    _row(
        "F3",
        "Nothing found BECAUSE everything was denied (D1 on every service)",
        "tier2",
        "lead / WP-F1a",
        "tier 2 ::F3",
        'all denied: exit 0, "no resources", snapshot saved (V L, T2)',
    ),
    _row(
        "F4",
        "Empty result with `--s3-bucket`",
        "tier2",
        "lead / WP-F1a",
        "tier 2 ::F4",
        "empty + --s3-bucket: exit 1 (V T10)",
    ),
    _row(
        "F5",
        "Empty result with `--template` and a tag policy with `fail_on_tag_violations`",
        "tier2",
        "S3 / WP-F1a",
        "tier 2 ::F5",
        "empty + tag policy with fail gate (R)",
    ),
    _row(
        "F6",
        "Resources found, all removed by filters",
        "tier1",
        "S2 / WP-F1a",
        "tier 1 ::F6",
        "all removed by filters: message (R)",
    ),
    _row(
        "G1",
        "Code path attempts a write call",
        "tier2",
        "S3 / WP-F1a",
        "tier 2 ::G1",
        "block inside a listing: swallowed, exit 0, nothing in report (V T3); at account level: account failed (V L)",
    ),
    _row(
        "G2",
        "Guard blocks a read that returns secrets (`GetSecretValue`, `GetObject`)",
        "tier1",
        "S3 / WP-F1a",
        "tier 1 ::G2",
        "secret read blocked: same path as G1 (R)",
    ),
    _row(
        "G3",
        "Clients created in worker threads, with assumed roles, and by libraries",
        "existing",
        "lead",
        "tests/unit/test_read_only_guard_adversarial.py",
        "threads, assumed roles, libraries guarded (V lead tests)",
    ),
    _row(
        "G4",
        "The explicit, allowed writes (S3 upload of reports, state files on local disk)",
        "existing",
        "S3",
        "tests/unit/test_security_s3_upload.py",
        "only PutObject on the upload client; lifecycle needs opt-in (V lead/S3 tests)",
    ),
    _row(
        "G5",
        "A guard block swallowed by an `except` somewhere",
        "tier1",
        "S3 / WP-F1a",
        "tier 1 ::G5",
        "(architect) swallowed block still counted by the guard (R T21)",
    ),
    _row(
        "G6",
        "A guard block during an output step",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::G6",
        "(architect) block during an output step",
    ),
    _row("H1", "Output folder missing", "tier2", "—", "tier 2 ::H1", "created (V S2)"),
    _row(
        "H2",
        "Output folder not writable, read-only file system, disk full",
        "tier2",
        "S2 / WP-E",
        "tier 2 ::H2",
        "not writable: catch-all after the scan (V S2)",
    ),
    _row(
        "H3",
        "Target file is open in Excel or Word (Windows lock)",
        "tier2",
        "S2 / WP-E",
        "tier 2 ::H3 (win32 only)",
        "Windows lock: Permission denied without path (R S2)",
    ),
    _row(
        "H4",
        "One of several formats fails (Word fails, Excel fine)",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::H4",
        "other formats written on the default path; with --template one failure stops the rest (V S2, R T17)",
    ),
    _row(
        "H5",
        "Illegal characters, very long values, formula-like values, `None` service",
        "existing",
        "—",
        "existing robustness tests",
        "fixed in this cycle",
    ),
    _row(
        "H6",
        "Very large inventory (50,000 resources)",
        "existing",
        "—",
        "scripts/benchmark_scan.py",
        "not in the failure matrix (architect 9.2): benchmark script",
    ),
    _row(
        "H7",
        "Template not found or invalid",
        "tier2",
        "S2",
        "tier 2 ::H7",
        "template invalid exit 1 with file:line (V S2) — decided: stays 1",
    ),
    _row(
        "H8",
        "Output folder or file problems found before the scan starts",
        "tier2",
        "S2 / WP-E",
        "tier 2 ::H8",
        "--audit-output/--log-file unwritable: traceback (V S2)",
    ),
    _row(
        "H9",
        "One format written, a later one fails",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::H9..H11",
        "(architect) later format fails; non-atomic JSON/changelog/audit (R T16); Google with template skipped (R T18)",
    ),
    _row(
        "H10",
        "Interrupt or failure while writing the JSON output, change log, tag-compliance JSON or audit file",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::H9..H11",
        "(architect) later format fails; non-atomic JSON/changelog/audit (R T16); Google with template skipped (R T18)",
    ),
    _row(
        "H11",
        "`--template` with a Google output",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::H9..H11",
        "(architect) later format fails; non-atomic JSON/changelog/audit (R T16); Google with template skipped (R T18)",
    ),
    _row(
        "I1",
        "S3 upload: bucket missing, access denied, KMS key denied, wrong region",
        "tier2",
        "S3 / WP-F1a",
        "tier 2 ::I1",
        "S3 failure: exit 1, message printed twice (V S2 F07)",
    ),
    _row(
        "I2",
        "S3 upload of several files, one fails",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::I2",
        "several files, one fails: per-file errors collected (R s3_upload.upload_files)",
    ),
    _row(
        "I3",
        "Google: libraries missing",
        "tier2",
        "—",
        "tier 2 ::I3",
        "Google libs missing: exit 2 with install command (V S2)",
    ),
    _row(
        "I4",
        "Google: sign-in fails, API not enabled, quota exceeded, Sheets written but Docs fails",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::I4 (mocked)",
        "Google failures: mocked clients only; T18 for templates (R)",
    ),
    _row(
        "J1",
        "Previous snapshot corrupt or from an older schema",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::J1",
        "corrupt previous snapshot: find_previous_state skips it with a reason (R state layer)",
    ),
    _row(
        "J2",
        "State folder not writable",
        "tier2",
        "S3 / WP-F1a",
        "tier 2 ::J2",
        "state folder unusable: one ERROR, exit 0 (V T9)",
    ),
    _row(
        "J3",
        "An account failed in this run or the previous one",
        "tier2",
        "S3 / WP-F2",
        "tier 2 ::J3",
        "failed account excluded from comparison (state layer, account level)",
    ),
    _row(
        "J4",
        "Two runs at the same time in one folder",
        "tier1",
        "S3",
        "tier 1 ::J4",
        "concurrent runs: no-overwrite snapshots; reports same-second collision (R)",
    ),
    _row(
        "J5",
        "A run that read nothing (or filtered everything) saves no snapshot",
        "tier2",
        "lead / WP-F1a",
        "tier 2 ::J5",
        "snapshot saved after an all-denied run (V L, T2)",
    ),
    _row(
        "J6",
        "Same as D14 for a region, and for the Tagging API unit",
        "tier2",
        "S3 / WP-F2, lead (J7)",
        "tier 2 ::J6..J8",
        '(architect) unit-level "Not compared"; no snapshot without a complete/partial account; checkpoint write failure',
    ),
    _row(
        "J7",
        "No account complete or partial",
        "tier2",
        "S3 / WP-F2, lead (J7)",
        "tier 2 ::J6..J8",
        '(architect) unit-level "Not compared"; no snapshot without a complete/partial account; checkpoint write failure',
    ),
    _row(
        "J8",
        "A checkpoint cannot be written",
        "tier2",
        "S3 / WP-F2, lead (J7)",
        "tier 2 ::J6..J8",
        '(architect) unit-level "Not compared"; no snapshot without a complete/partial account; checkpoint write failure',
    ),
    _row(
        "K1",
        "Ctrl-C (SIGINT) during discovery, during report writing",
        "tier2",
        "S2 / WP-F1a",
        "tier 2 ::K1",
        "Ctrl-C exit 1, message at INFO (V S2, L, T7)",
    ),
    _row(
        "K2",
        "SIGTERM from a CI runner timeout",
        "tier2",
        "S2 / WP-F1a",
        "tier 2 ::K2",
        "SIGTERM killed, no message (V S2)",
    ),
    _row(
        "K3",
        "No network, DNS failure, corporate proxy, TLS interception with a private CA",
        "tier1+tier2",
        "S2 / WP-F1a",
        "tier 1 + tier 2 ::K3",
        "no network at start: generic text, bounded (V S2)",
    ),
    _row(
        "K4",
        "Unexpected exception anywhere",
        "tier2",
        "S2 / WP-E",
        "tier 2 ::K4",
        "unexpected: Unexpected error: <text> (V S2)",
    ),
    _row(
        "K5",
        "Exception inside a worker thread",
        "tier2",
        "lead / WP-F1a",
        "tier 2 ::K5",
        "worker exception = account failure (V S2)",
    ),
    _row(
        "K6",
        "Log file location not writable",
        "tier2",
        "S2 / WP-F2",
        "tier 2 ::K6",
        "log file not writable: traceback (V S2)",
    ),
    _row(
        "K7",
        "A second Ctrl-C during the shutdown",
        "tier2",
        "S2 / WP-F2",
        "tier 2 ::K7..K10",
        "(architect) second Ctrl-C, SIGTERM during write, signal during upload, closed stdout",
    ),
    _row(
        "K8",
        "SIGTERM while a report is being written",
        "tier2",
        "S2 / WP-F2",
        "tier 2 ::K7..K10",
        "(architect) second Ctrl-C, SIGTERM during write, signal during upload, closed stdout",
    ),
    _row(
        "K9",
        "A signal during the S3 upload",
        "tier2",
        "S2 / WP-F2",
        "tier 2 ::K7..K10",
        "(architect) second Ctrl-C, SIGTERM during write, signal during upload, closed stdout",
    ),
    _row(
        "K10",
        "stdout or stderr closed (`inventag ... \\| head`)",
        "tier2",
        "S2 / WP-F2",
        "tier 2 ::K7..K10",
        "(architect) second Ctrl-C, SIGTERM during write, signal during upload, closed stdout",
    ),
]

A = "A"
STS_B_DENIED = Fault(
    service="sts",
    op="GetCallerIdentity",
    key=ACCOUNTS["B"][1],
    error="InvalidClientTokenId",
    message="The security token included in the request is invalid.",
)
SLOW_B = Fault(service="ec2", op="DescribeVpcs", key=ACCOUNTS["B"][1], sleep=40.0)
# a whole scan of one account takes about 8 s here, so the limit must be well above that
SHORT = {"account_timeout": 20, "grace": 1, "poll": 0.2}
ONE_SERVICE = ("--account-services", "SQS")
NO_RESOURCES = "No resources to report (none found, or the filters removed all of them). No report file was written."
NOTHING_READ = "No resources to report: nothing could be read (see the messages above). No report file was written."

# What a row overrides on its plan entry. ``source`` is "run" when S1 executed the
# scenario against moto (evidence under audit/extra/s1-failure-probes), "code" when
# it was read in the code only.
MATRIX: Dict[str, Dict[str, Any]] = {
    "A3": dict(
        source="run",
        faults=(
            Fault(
                not_services=("sts",),
                not_ops=("DescribeRegions",),
                error="ExpiredToken",
            ),
        ),
        # fix/track-a (A-02, A-01): the expired session is named, no 0-resource
        # snapshot, and the message no longer blames the filters
        current=(
            ("code", 0),
            ("out", "failed (ExpiredToken)"),
            ("out", "expired during the scan"),
            ("out", NOTHING_READ),
            ("no_out", "none found, or the filters removed"),
            ("report", False),
            ("snapshot_zero", False),
        ),
        code=1,
        issue_keys=("credentials",),
        target=(("code", 1),),
        wp="WP-F1a",
    ),
    "B1": dict(
        source="run",
        accounts=("A", "B"),
        args=ONE_SERVICE,
        faults=(STS_B_DENIED,),
        current=(
            ("code", 0),
            ("out", "Failed to establish context for account 222222222222"),
            ("out", "were not scanned"),
            ("report", True),
            ("report_text", "were not scanned"),
        ),
        issue_keys=("credentials",),
        target=(("code", 0),),
        wp="WP-F1a",
    ),
    "B2": dict(
        source="run",
        accounts=("A", "B"),
        args=ONE_SERVICE,
        faults=(
            Fault(service="sts", op="GetCallerIdentity", error="InvalidClientTokenId"),
        ),
        current=(
            ("code", 1),
            ("report", False),
            ("out", "Resource discovery failed for all 2 configured account(s)"),
            ("not", ("summary_has_cause", "InvalidClientTokenId")),
        ),
        code=1,
        target=(("code", 1), ("summary_has_cause", "InvalidClientTokenId")),
        wp="WP-F1a",
    ),
    "B3": dict(
        source="run",
        slow=True,  # 20 s: the limit has to be above the time of a whole scan (about 8 s)
        accounts=("A", "B"),
        args=("--account-services", "VPC,SQS"),
        faults=(SLOW_B,),
        limits=SHORT,
        # How many of B's rows were found before the limit depends on the load of the host
        # (about 2 on a quiet one), so only the message's start is pinned, not its tail.
        current=(
            ("code", 0),
            ("report", True),
            (
                "out_regex",
                r"account 222222222222: timed out after 20 seconds \(--account-processing-timeout\)",
            ),
            ("report_text", "222222222222"),
        ),
        issue_keys=("timeout",),
        target=(("code", 0),),
        wp="WP-F2",
    ),
    "B5": dict(
        source="run",
        slow=True,  # 30 s: B3 plus a second run
        accounts=("A", "B"),
        args=("--account-services", "VPC,SQS"),
        faults=(SLOW_B,),
        limits=SHORT,
        later_runs=(dict(args=("--resume",), faults=()),),
        current=(
            ("code", 0),
            ("out", "reusing results"),
            ("report", True),
            ("out", "Account 222222222222 left out of the comparison"),
        ),
        target=(("code", 0), ("out", "reusing results"), ("report", True)),
    ),
    "B6": dict(
        source="run",
        accounts=("A", "A"),
        args=ONE_SERVICE,
        current=(
            ("code", 0),
            ("report", True),
            ("rows", "SQS", 1),
            ("not", ("out_regex", r"(?i)listed twice|duplicate|more than once")),
        ),
        target=(
            ("code", 0),
            ("out_regex", r"(?i)listed twice|duplicate|more than once"),
            ("no_out", "Configured 2 account"),
        ),
        wp="WP-E",
    ),
    "B10": dict(
        source="run",
        slow=True,
        process="child",
        accounts=("A", "B"),
        args=("--account-services", "VPC"),
        faults=(
            Fault(service="ec2", op="DescribeVpcs", key=ACCOUNTS["B"][1], sleep=40.0),
        ),
        limits=SHORT,
        # the process is kept alive by the hung call: it ends long after the report is written
        current=(
            ("code", 0),
            ("report", True),
            ("out_regex", r"account 222222222222: timed out after 20 seconds"),
            ("exit_after_report_at_least", 8.0),
        ),
        target=(("code", 0), ("exit_within_after_summary", 12.0)),
        wp="WP-F2",
    ),
    "D1": dict(
        source="run",
        faults=(
            Fault(
                service="sqs",
                op="ListQueues",
                error="AccessDenied",
                message="not authorized to perform: sqs:ListQueues",
            ),
        ),
        args=("--log-file", "{out}/inventag.log"),
        # the plan said the line is not in --log-file; in v1.2.0 it is (also in a real child process)
        current=(
            ("code", 0),
            ("report", True),
            ("out", "No permission for sqs"),
            ("log_file", "No permission for sqs"),
        ),
        issue_keys=("permission_denied:sqs",),
        target=(("log_file", "No permission for sqs"),),
        wp="WP-F1b",
    ),
    "D3": dict(
        source="run",
        faults=(Fault(service="sqs", op="ListQueues", error="Throttling"),),
        current=(
            ("code", 0),
            ("report", True),
            ("out", "sqs list_queues in us-east-1 failed (Throttling)"),
            # fix/track-a (A-28): the report's Run notes name the listing
            ("report_text", "throttl"),
        ),
        issue_keys=("throttled:sqs",),
        target=(("report_text", "throttl"),),
        wp="WP-F1b",
    ),
    "D4": dict(
        source="run",
        seed=("empty", "ddb105"),
        args=("--account-services", "DYNAMODB"),
        faults=(
            Fault(
                service="dynamodb", op="ListTables", call=2, error="ThrottlingException"
            ),
        ),
        current=(
            ("code", 0),
            ("out", "dynamodb list_tables in us-east-1 failed (ThrottlingException)"),
            ("rows", "DYNAMODB", 100),
            # fix/track-a (A-28): the report's Run notes say it is partial
            ("report_text", "partial"),
        ),
        issue_keys=("throttled:dynamodb",),
        target=(("report_text", "partial"),),
        wp="WP-F2",
    ),
    "D6": dict(
        source="run",
        faults=(
            Fault(
                service="sqs",
                op="ListQueues",
                error="OptInRequired",
                message="The AWS Access Key Id needs a subscription for the service",
            ),
        ),
        current=(
            ("code", 0),
            ("report", True),
            (
                "out",
                "No permission for sqs (list_queues in us-east-1: OptInRequired). Resources of sqs are skipped; add the read permission",
            ),
        ),
        issue_keys=("not_enabled:sqs",),
        target=(("no_out", "add the read permission"),),
        wp="WP-F1b",
    ),
    "D7": dict(
        source="run",
        faults=(Fault(service="sqs", op="ListQueues", replace={"QueueUrls": "oops"}),),
        current=(("code", 0), ("report", True), ("row", "oops")),
        issue_keys=("internal_error:sqs",),
        target=(("no_row", "oops"),),
        wp="WP-F2",
    ),
    "D8": dict(
        source="run",
        faults=(
            Fault(
                service="resourcegroupstaggingapi",
                op="GetResources",
                error="AccessDeniedException",
            ),
        ),
        current=(
            ("code", 0),
            ("out", "ResourceGroupsTagging enrichment failed"),
            ("report", True),
        ),
        issue_keys=("permission_denied:resourcegroupstaggingapi",),
        target=(("report", True),),
        wp="WP-F2",
    ),
    "E1": dict(
        source="run",
        billing=True,
        args=ONE_SERVICE,
        faults=(
            Fault(service="ce", op="GetCostAndUsage", error="AccessDeniedException"),
        ),
        current=(
            ("code", 0),
            ("out", "No permission for the Cost Explorer API"),
            ("report", True),
            ("lines_with", "Cost Explorer", 2),
        ),
        issue_keys=("permission_denied:ce",),
        target=(("lines_with", "Cost Explorer", 1),),
        wp="WP-F1b",
    ),
    "E3": dict(
        source="run",
        billing=True,
        args=ONE_SERVICE,
        faults=(
            Fault(service="ce", op="GetCostAndUsage", error="ThrottlingException"),
        ),
        current=(
            ("code", 0),
            ("out", "Cost Explorer API failed"),
            ("report", True),
            ("lines_with", "Cost Explorer", 2),
        ),
        issue_keys=("throttled:ce",),
        target=(("lines_with", "Cost Explorer", 1),),
        wp="WP-F1b",
    ),
    "F1": dict(
        source="run",
        seed=("empty",),
        args=EMPTY_ARGS,
        current=(
            ("code", 0),
            ("report", False),
            ("out", NO_RESOURCES),
            ("snapshot_zero", True),
            ("not", ("summary", "empty", True)),
        ),
        target=(("code", 0), ("report", False), ("summary", "empty", True)),
        wp="WP-F1a",
    ),
    "F2": dict(
        source="run",
        args=("--account-services", "EC2"),
        current=(
            ("code", 0),
            ("report", False),
            ("out", NO_RESOURCES),
            ("not", ("out_regex", r"No resources.*(EC2|--account-services)")),
        ),
        target=(("out_regex", r"No resources.*(EC2|--account-services)"),),
        wp="WP-F1a",
    ),
    "F3": dict(
        source="run",
        faults=(
            Fault(
                not_services=("sts",),
                not_ops=("DescribeRegions",),
                error="AccessDenied",
            ),
        ),
        # fix/track-a (A-01): the account is named, no 0-resource snapshot, and the
        # message no longer blames the filters
        current=(
            ("code", 0),
            ("report", False),
            ("out", "No permission for vpc"),
            ("out", "Every service listing of account 123456789012"),
            ("out", NOTHING_READ),
            ("no_out", "none found, or the filters removed"),
            ("snapshot_zero", False),
        ),
        code=1,
        issue_keys=("permission_denied",),
        target=(("code", 1),),
        wp="WP-F1a",
    ),
    "F4": dict(
        source="run",
        seed=("empty", "upload_bucket"),
        args=EMPTY_ARGS + ("--s3-bucket", "regression-upload"),
        current=(
            ("code", 1),
            ("report", False),
            ("out", NO_RESOURCES),
            ("out", "S3 upload failed for 1 file(s)"),
        ),
        target=(("code", 0), ("out", "nothing was uploaded")),
        wp="WP-F1a",
    ),
    "F5": dict(
        source="run",
        seed=("empty",),
        args=EMPTY_ARGS + ("--template", "ci-pipeline"),
        current=(
            ("code", 0),
            ("report", True),
            ("out", "0 of 0 resources compliant (100.0%)"),
        ),
        target=(("no_out", "(100.0%)"),),
        wp="WP-F1a",
    ),
    "J5": dict(
        source="run",
        args=("--account-services", "EC2"),
        current=(("code", 0), ("report", False), ("snapshot_zero", True)),
        target=(("snapshot_zero", False),),
        wp="WP-F1a",
    ),
    "K1": dict(
        source="code",
        process="child",
        signal="SIGINT",
        slow=True,  # 14 to 22 s: after Ctrl-C the scan runs on
        faults=(Fault(service="ec2", op="DescribeVpcs", sleep=6.0),),
        args=("--account-services", "VPC"),
        current=(("code", 1), ("report", False)),
        code=130,
        target=(("code", 130),),
        wp="WP-F1a",
    ),
    "K2": dict(
        source="code",
        process="child",
        signal="SIGTERM",
        faults=(Fault(service="ec2", op="DescribeVpcs", sleep=6.0),),
        args=("--account-services", "VPC"),
        # killed by the signal: no handler, so Python reports -15, not 143
        current=(("code", -15), ("report", False)),
        code=143,
        target=(("code", 143),),
        wp="WP-F1a",
    ),
}

# Gaps found while probing that the plan has no ID for. Same fields as above.
EXTRA = [
    Scenario(
        "S1-F1-template-writes-an-empty-report",
        "Empty result with --template writes a report; without it no file is written (O7: no report on both paths)",
        "matrix",
        "S3 / WP-F1a",
        "tests/regression/test_failure_matrix.py",
        "F1t: workbook written, 'Accounts: 0 Regions: 0'",
        source="run",
        seed=("empty",),
        args=EMPTY_ARGS + ("--template", "standard-bom"),
        current=(("code", 0),),
        target=(("report", False),),
        wp="WP-F1a",
    ),
    Scenario(
        "S1-E-cost-analysis-calls-cost-explorer",
        "--no-billing-validation with --enable-cost-analysis still calls Cost Explorer (AWS charges per request)",
        "matrix",
        "S1 / WP-F3",
        "tests/regression/test_failure_matrix.py",
        "E4b: 8 GetCostAndUsage calls with both flags",
        source="run",
        args=ONE_SERVICE + ("--enable-cost-analysis",),
        current=(("code", 0),),
        target=(("ce_calls", 0),),
        wp="unassigned: needs an owner decision",
    ),
    Scenario(
        "S1-F-tagging-counts-as-a-listing",
        "Every service call denied, Tagging API fine: the account counts as read (5 fallback rows), exit 0",
        "matrix",
        "lead / WP-F1a",
        "tests/regression/test_failure_matrix.py",
        "F3a: success, 5 fallback rows, snapshot saved; the 'no successful listing' rule must count service-api only",
        source="run",
        faults=(
            Fault(
                not_services=("sts", "resourcegroupstaggingapi"),
                not_ops=("DescribeRegions",),
                error="AccessDenied",
            ),
        ),
        current=(
            ("code", 0),
            ("report", True),
            ("out", "No permission for vpc"),
            ("not", ("out", NO_RESOURCES)),
            # fix/track-a (A-01): the report's Run notes name the account
            ("report_text", "Every service listing of account 123456789012"),
        ),
        code=1,
        issue_keys=("permission_denied",),
        target=(("code", 1),),
        wp="WP-F1a",
    ),
]

ROWS = []
for _row_ in PLAN:
    _extra = MATRIX.get(_row_.id)
    if _extra:
        _row_ = replace(_row_, runner="matrix", **_extra)
    ROWS.append(_row_)
ROWS.extend(EXTRA)
BY_ID = {row.id: row for row in ROWS}
MATRIX_ROWS = [row for row in ROWS if row.runner == "matrix"]
