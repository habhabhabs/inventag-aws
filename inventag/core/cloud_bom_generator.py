#!/usr/bin/env python3
"""
CloudBOMGenerator - Main Multi-Account Orchestrator

Main orchestrator that coordinates comprehensive resource discovery, compliance checking,
and BOM document generation across multiple AWS accounts with parallel processing
and centralized credential management.

Features:
- Account context detection using aws sts get-caller-identity for each account
- Multi-account credential management with file-based and prompt-based input
- Cross-account role assumption support for centralized scanning
- Comprehensive resource discovery across multiple AWS accounts in parallel
- Account-specific error handling and graceful failure recovery
- Account consolidation logic for unified BOM document generation
"""

import dataclasses
import logging
import re
import boto3
from botocore.config import Config as BotoConfig
import json
import os
import sys
import yaml
import getpass
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import FIRST_COMPLETED, wait
import threading
import time
import weakref
from pathlib import Path
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
)

# Import InvenTag components
from ..discovery import AWSResourceInventory
from ..discovery.aws_clients import enable_client_cache, reset_client_cache
from ..discovery.coverage import DETAIL_SOURCE, EMPTY, FAILED_OUTCOMES, OK
from ..discovery.regions import discover_regions
from . import cost_requests
from .daemon_pool import DaemonThreadPool
from .limiter import DEFAULT_LIMIT, InFlightLimiter
from .log_context import account_log_context
from ..compliance import ComprehensiveTagComplianceChecker
from ..finops import checks as finops_checks
from ..finops import cost_allocation
from ..reporting import BOMConverter, BOMDataProcessor, BOMProcessingConfig
from ..state import StateManager, DeltaDetector, ChangelogGenerator
from ..security.arn import (
    InvalidRoleError,
    build_role_arn,
    is_valid_account_id,
    partition_from_arn,
    validate_role_arn,
)
from ..security import permissions_report
from ..security.read_only_guard import get_installed_guard
from ..security.redaction import redact, register_secrets
from ..security.secret_values import mask_secret_values
from .._version import __version__

from ..state.partial_results import PartialResultStore, make_run_key
from ..reporting.safe_save import save_atomically
from ..security.safe_output import ensure_private_dir


def _coverage_of(context) -> List[Dict[str, Any]]:
    """The coverage entries of an account context (none if it has no list)."""
    entries = getattr(context, "coverage", None)
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


# AWS error codes that say the account's session is no longer valid. A listing
# that ends with one of them means the session expired during the scan: the
# account was read only in part.
_EXPIRED_SESSION_CODES = frozenset(
    {"ExpiredToken", "ExpiredTokenException", "RequestExpired"}
)


# At most this many service/region items in one "Not read" note.
_NOT_READ_LIMIT = 10
# The error code of a listing whose service the endpoint does not know (moto
# answers it for every service it does not implement). Nothing can be read
# there, so it is not reported as "not read".
_NO_SUCH_SERVICE_CODE = "404"


# Cost Explorer is optional and it is the first call of an account. With
# botocore's limits (60 s to connect, 60 s to read, up to 10 attempts) one slow
# answer can use a short --account-processing-timeout completely, and the
# account is then lost before any listing runs (A-24). Below this limit the
# Cost Explorer client of the account gets at most a tenth of it.
_CE_BOUND_BELOW_SECONDS = 1200
_CE_ATTEMPTS = 2
_CE_STEP_FLOOR_SECONDS = 5.0
# Error names of a Cost Explorer call that did not answer in time.
_TIMEOUT_ERRORS = frozenset({"ReadTimeoutError", "ConnectTimeoutError"})


def _cost_explorer_config(limit_seconds) -> Optional[BotoConfig]:
    """Client settings for Cost Explorer under a short account limit, else
    None (botocore's own settings, as before)."""
    try:
        limit = float(limit_seconds)
    except (TypeError, ValueError):
        return None
    if limit <= 0 or limit >= _CE_BOUND_BELOW_SECONDS:
        return None
    # Each attempt: limit/40 to connect and limit/40 to read, but at least
    # _CE_STEP_FLOOR_SECONDS for each. The floor keeps a slow but working
    # answer (seconds) readable under a short limit; botocore's own defaults
    # are 60 s for each step. Cost Explorer is read twice per account
    # (inventory, then comprehensive discovery), two attempts each: at the
    # shortest allowed limit (60 s) a hung endpoint costs 4 x 5 s = 20 s, a
    # third of the limit, so the listings still run (A-24).
    per_step = max(_CE_STEP_FLOOR_SECONDS, limit / (2 * _CE_ATTEMPTS * 10))
    settings = {"connect_timeout": per_step, "read_timeout": per_step}
    if not (os.environ.get("AWS_RETRY_MODE") or os.environ.get("AWS_MAX_ATTEMPTS")):
        settings["retries"] = {"mode": "standard", "total_max_attempts": _CE_ATTEMPTS}
    return BotoConfig(**settings)


def _bound_cost_explorer(session, config: Optional[BotoConfig]):
    """Give the Cost Explorer clients created from ``session`` the settings
    ``config``. Returns a function that undoes it."""
    if config is None or session is None or not hasattr(session, "client"):
        return lambda: None
    original = session.client

    def client(service_name, *args, **kwargs):
        if service_name == "ce":
            given = kwargs.get("config")
            kwargs["config"] = given.merge(config) if given is not None else config
        return original(service_name, *args, **kwargs)

    session.client = client

    def restore():
        try:
            del session.client
        except AttributeError:
            pass

    return restore


def _known_regions(session) -> set:
    """Every region the installed botocore knows (all partitions); empty if
    that cannot be read, so that no region is called unknown by mistake."""
    try:
        regions = set()
        for partition in session.get_available_partitions():
            regions.update(session.get_available_regions("ec2", partition))
        return regions
    except Exception:
        return set()


def _mfa_serial_without_terminal(session) -> Optional[str]:
    """The profile's ``mfa_serial`` when an MFA code would be asked for and
    stdin is not a terminal (nobody can type it), else None."""
    try:
        serial = session._session.get_scoped_config().get("mfa_serial")
    except Exception:
        return None
    if not isinstance(serial, str) or not serial:
        return None
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            return None
    except (ValueError, OSError):
        pass
    return str(serial)


def mfa_without_terminal_message(profile: str, account_id: str, serial: str) -> str:
    """One cause, one next step (A-11, A-65)."""
    return (
        f"Profile {profile!r} for account {account_id} needs an MFA code, and "
        "there is no terminal to type it in. Get temporary credentials first, "
        f"for example with aws sts get-session-token --serial-number {serial} "
        "--token-code <code>, and use a profile without mfa_serial."
    )


def _expired_listings(context) -> int:
    """How many listings of an account failed because its session expired."""
    return sum(
        1
        for entry in _coverage_of(context)
        if str(entry.get("error_code", "")) in _EXPIRED_SESSION_CODES
    )


# Every generator in this process (one per run), so that SIGTERM and Ctrl-C
# can stop them all (stop_running_scans).
_RUNS: "weakref.WeakSet" = weakref.WeakSet()
_RUNS_LOCK = threading.Lock()


def stop_running_scans() -> None:
    """Stop every run in this process: every request waiting for a slot ends
    at once, no new AWS request starts, and detail calls not started do not
    start (Ctrl-C, after the stack has unwound: this takes locks)."""
    with _RUNS_LOCK:
        runs = list(_RUNS)
    for run in runs:
        run.stop()


def request_stop_of_running_scans() -> None:
    """The SIGTERM handler's stop: no new AWS request starts in any run of
    this process. It takes no lock, wakes nobody and shuts no pool down: the
    handler runs on the main thread, which may hold any of those locks, and
    the process ends by the signal a moment later. Every detail call is an
    AWS request, so the limiter's flag stops those too."""
    for run in _snapshot(_RUNS):
        run.request_stop()


def _snapshot(items) -> list:
    """A copy of a set that another thread may change, taken without a lock.
    When the copy keeps failing, nothing is returned: the caller's stop is
    then left to the process ending."""
    for _ in range(3):
        try:
            return list(items)
        except RuntimeError:  # silent-ok: changed size during the copy; try again
            continue
    return []


class AccountSessionError(Exception):
    """Raised when explicitly configured credentials for an account do not work.

    ``assume_role_error_code`` is the AWS error code when the cause was a
    refused ``sts:AssumeRole`` of the account's role ARN (else "").
    """

    def __init__(self, message: str, *, assume_role_error_code: str = ""):
        super().__init__(message)
        self.assume_role_error_code = assume_role_error_code


class ReportGenerationError(Exception):
    """Raised when a requested report format could not be written."""

    def __init__(self, message: str, bom_results: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.bom_results = bom_results or {}


class AccountTimeoutError(Exception):
    """Raised when an account's discovery runs past ``account_processing_timeout``.

    ``partial_resources`` holds what the account's scan found before the
    limit, when the scan returned at all (else ``None``).
    """

    def __init__(self, message: str = "", partial_resources=None):
        super().__init__(message)
        self.partial_resources = partial_resources


class _AccountDeadline:
    """One account's time limit (``account_processing_timeout``).

    The clock starts when the account's discovery starts, not when it is
    queued. Python cannot stop a running thread, so the limit is enforced in
    two ways:

    * a botocore ``before-call`` handler, registered on the account's session
      before discovery creates its clients, refuses every AWS call made after
      the deadline (:class:`AccountTimeoutError`), so the work winds down;
    * in parallel mode the main thread stops waiting for the account at the
      deadline (:meth:`abandon`), records it as failed and ignores whatever
      the worker returns later.
    """

    UNIQUE_ID = "inventag-account-deadline"

    def __init__(self, account_id: str, timeout_seconds: float, clock=time.monotonic):
        self.account_id = account_id
        self.timeout_seconds = timeout_seconds
        self._clock = clock
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.active = False
        self.expired = False
        self.abandoned = False
        self.abandoned_at: Optional[float] = None  # real time, for the grace period
        # Written by the worker, read by the main thread after the scan ends.
        self.coverage: List[Dict[str, Any]] = []
        self.unfinished_listings = 0  # discovery's own limit (coverage "timeout")
        # Called once when the account is abandoned (stop its detail calls).
        self._on_abandon: List[Any] = []
        self._abandon_lock = threading.Lock()

    def start(self) -> None:
        self.started_at = self._clock()
        self.active = True

    def past_deadline(self) -> bool:
        return (
            self.started_at is not None
            and self._clock() - self.started_at > self.timeout_seconds
        )

    def remaining(self) -> float:
        """Seconds left before the deadline (the full limit before start)."""
        if self.started_at is None:
            return float(self.timeout_seconds)
        return self.timeout_seconds - (self._clock() - self.started_at)

    def message(self, partial_count: Optional[int] = None) -> str:
        text = (
            f"timed out after {self.timeout_seconds:g} seconds "
            "(--account-processing-timeout); "
        )
        if partial_count:
            return text + (
                f"the {partial_count} resource(s) found before the limit are in "
                "the report, other resources of this account may be missing"
            )
        return text + "no results of this account are in the report"

    def before_call(self, **kwargs):
        if self.active and (self.abandoned or self.past_deadline()):
            self.expired = True
            raise AccountTimeoutError(
                f"Account {self.account_id} reached its time limit of "
                f"{self.timeout_seconds:g} seconds (--account-processing-timeout)"
            )

    def abandon(self) -> None:
        """The main thread gave up on this account: refuse its further calls
        and stop its detail calls."""
        self.expired = True
        with self._abandon_lock:
            first = not self.abandoned
            self.abandoned = True
            if self.abandoned_at is None:
                self.abandoned_at = time.monotonic()
            callbacks = list(self._on_abandon) if first else []
        for callback in callbacks:
            callback()

    def on_abandon(self, callback) -> None:
        """Call ``callback`` once when the account is abandoned (at once if
        it already is)."""
        with self._abandon_lock:
            if not self.abandoned:
                self._on_abandon.append(callback)
                return
        callback()

    def forget_on_abandon(self, callback) -> None:
        """Drop ``callback`` (its scan ended). The deadline lives as long as
        the session, so it must not keep a finished engine alive."""
        with self._abandon_lock:
            self._on_abandon = [c for c in self._on_abandon if c != callback]

    def _hook_id(self, event: str) -> str:
        return f"{self.UNIQUE_ID}-{event}-{id(self)}"

    def attach(self, session) -> None:
        events = getattr(session, "events", None)
        if events is not None:
            # One id per deadline: two accounts can share one session object
            # (library use), and botocore keeps only the first hook of an id.
            events.register(
                "before-call", self.before_call, unique_id=self._hook_id("call")
            )
            # Also before every retry attempt of a call already under way,
            # so a call does not go on for up to ten attempts after the limit.
            events.register(
                "before-send", self.before_call, unique_id=self._hook_id("send")
            )

    def detach(self, session) -> None:
        self.active = False
        self.finished_at = self._clock()
        events = getattr(session, "events", None)
        if events is not None:
            events.unregister("before-call", unique_id=self._hook_id("call"))
            events.unregister("before-send", unique_id=self._hook_id("send"))


@dataclass
class AccountCredentials:
    """Credentials for a single AWS account."""

    account_id: str
    account_name: str = ""
    access_key_id: Optional[str] = None
    # Secrets are excluded from repr() so they never end up in logs or errors.
    secret_access_key: Optional[str] = field(default=None, repr=False)
    session_token: Optional[str] = field(default=None, repr=False)
    profile_name: Optional[str] = None
    role_arn: Optional[str] = None
    external_id: Optional[str] = None
    regions: List[str] = field(
        default_factory=list
    )  # Empty list means auto-discover all regions
    services: List[str] = field(default_factory=list)  # Empty means all services
    tags: Dict[str, str] = field(default_factory=dict)  # Account-specific tag filters


@dataclass
class AccountContext:
    """Runtime context for an AWS account during processing."""

    credentials: AccountCredentials
    session: boto3.Session
    caller_identity: Dict[str, Any]
    accessible_regions: List[str] = field(default_factory=list)
    discovered_services: List[str] = field(default_factory=list)
    processing_errors: List[str] = field(default_factory=list)
    processing_warnings: List[str] = field(default_factory=list)
    resource_count: int = 0
    processing_time_seconds: float = 0.0
    # What discovery attempted and how each listing ended (coverage ledger
    # entries as dicts), and whether the account's results are incomplete
    # because it ran out of time.
    coverage: List[Dict[str, Any]] = field(default_factory=list)
    partial: bool = False
    # Regions dropped by the region access check (not scanned).
    skipped_regions: List[str] = field(default_factory=list)
    # AWS error code when the account's role could not be assumed (the
    # permissions summary reads it); "" otherwise.
    assume_role_error_code: str = ""


@dataclass
class MultiAccountConfig:
    """Configuration for multi-account BOM generation."""

    accounts: List[AccountCredentials] = field(default_factory=list)
    cross_account_role_name: str = "InvenTagCrossAccountRole"
    parallel_account_processing: bool = True
    max_concurrent_accounts: int = 4
    # Most AWS requests in flight at once for the whole run (--concurrency).
    concurrency: int = DEFAULT_LIMIT
    account_processing_timeout: int = 1800  # 30 minutes per account
    consolidate_accounts: bool = True
    generate_per_account_reports: bool = False
    enable_state_management: bool = True
    enable_delta_detection: bool = True
    enable_changelog_generation: bool = True
    # Cost Explorer lookups during discovery. AWS charges for each request.
    enable_billing_validation: bool = True
    bom_processing_config: BOMProcessingConfig = field(
        default_factory=BOMProcessingConfig
    )
    output_directory: str = "bom_output"
    credential_validation_timeout: int = 30
    hide_fallback_resources: bool = False  # Legacy, deprecated
    fallback_display_mode: str = "auto"  # "auto", "always", "never"
    # Validated report templates (inventag.reporting.report_template.ReportTemplate).
    # None means the built-in default structure.
    word_template: Optional[Any] = None
    excel_template: Optional[Any] = None
    # Google Sheets / Docs output (inventag.reporting.google_output.GoogleOptions).
    google_options: Optional[Any] = None
    # Account-level checkpoints. Finished accounts are saved under
    # <output>/state/partial/ while state management is on, and removed when a
    # run finishes with every account scanned. ``resume`` reuses them (opt-in).
    resume: bool = False
    resume_max_age_hours: float = 24.0
    # Snapshot retention (None = no limit for that rule).
    state_retention_days: Optional[int] = 30
    state_max_snapshots: Optional[int] = 100
    # --finops-checks: FIN-001 to FIN-006 on the rows the scan has (no AWS
    # call). Last, so callers that pass the fields by position still work.
    finops_checks: bool = False
    # --finops-cost-allocation: at most 7 Cost Explorer requests per account,
    # each with that account's own session; --no-cost-in-snapshot clears
    # cost_in_snapshot (the sheet is still written).
    finops_cost_allocation: bool = False
    cost_in_snapshot: bool = True


class CloudBOMGenerator:
    """
    Main orchestrator that coordinates comprehensive resource discovery, compliance checking,
    and BOM document generation across multiple AWS accounts.

    Features:
    - Account context detection using aws sts get-caller-identity for each account
    - Multi-account credential management with file-based and prompt-based input
    - Cross-account role assumption support for centralized scanning
    - Comprehensive resource discovery across multiple AWS accounts in parallel
    - Account-specific error handling and graceful failure recovery
    - Account consolidation logic for unified BOM document generation
    """

    def __init__(self, config: MultiAccountConfig):
        """Initialize the CloudBOMGenerator."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.CloudBOMGenerator")

        # Account contexts
        self.account_contexts: Dict[str, AccountContext] = {}
        self.consolidated_resources: List[Dict[str, Any]] = []
        # --finops-checks: the result for the whole run, and per account for
        # --per-account-reports (None when the flag is off).
        self._finops_result: Optional[Dict[str, Any]] = None
        self._finops_by_account: Dict[str, Dict[str, Any]] = {}
        # --finops-cost-allocation: every account's tables (None when off).
        self._finops_costs: Optional[Dict[str, Any]] = None

        # Processing state
        self._processing_lock = threading.Lock()
        # At most --concurrency AWS requests in flight for the whole run,
        # attached to each account's session for its scan (_scan_account).
        self.limiter = InFlightLimiter(config.concurrency)
        # Discovery engines of the accounts being scanned now (stop()).
        self._running_engines: set = set()
        self._engines_lock = threading.Lock()
        with _RUNS_LOCK:
            _RUNS.add(self)
        self._processing_stats = {
            "total_accounts": 0,
            "successful_accounts": 0,
            "failed_accounts": 0,
            "total_resources": 0,
            "processing_start_time": None,
            "processing_end_time": None,
        }

        # Initialize output directory (created owner-only if it does not exist)
        self.output_dir = ensure_private_dir(self.config.output_directory)
        self._default_identity: Optional[Dict[str, Any]] = None
        # Clock for the per-account time limit and how often the main thread
        # checks it (both replaceable in tests).
        self._clock = time.monotonic
        self._poll_seconds = 1.0
        # After an account's deadline its AWS calls are refused, so its worker
        # winds down quickly. The main thread waits this long (real seconds)
        # for it to return what it found; None = 10% of the limit, at most 30 s.
        self._abandon_grace_seconds: Optional[float] = None
        self._scan_local = threading.local()  # the deadline of this thread's scan
        self._checkpoints = None  # PartialResultStore, set per run
        self.reused_accounts: Dict[str, str] = {}  # account -> scanned at (UTC)
        # Run notes of the state stage (snapshot, index, change report; A-18).
        self._state_notes: List[str] = []
        # What the steps of the whole run were refused (permissions summary):
        # cost analysis, network analysis and the report upload.
        self._cost_denials: List[tuple] = []
        self._analysis_denials: List[tuple] = []
        self._upload_outcomes: List[Dict[str, Any]] = []
        # Region names botocore does not know (A-16): per account, the ones
        # that were not scanned; and the names already warned about.
        self._unknown_regions: Dict[str, List[str]] = {}
        self._warned_regions: set = set()
        self._warned_lock = threading.Lock()
        # The unknown regions of the region check that ran last on this
        # thread (the credential stage checks accounts in parallel).
        self._region_local = threading.local()
        # The default credentials' identity is looked up once per run.
        self._identity_lock = threading.RLock()
        # Read-only guard blocks counted before this run (blocked calls,
        # recorded entries), so only this run's blocks are reported.
        self._guard_start = (0, 0)

        self.logger.info(
            f"Initialized CloudBOMGenerator with {len(self.config.accounts)} accounts"
        )

    def generate_multi_account_bom(
        self,
        output_formats: List[str] = None,
        compliance_policies: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive BOM documents across multiple AWS accounts.

        Args:
            output_formats: List of output formats (word, excel, csv, json)
            compliance_policies: Tag compliance policies to apply

        Returns:
            Dictionary containing generation results and metadata
        """
        self.logger.info("Starting multi-account BOM generation")
        self._processing_stats["processing_start_time"] = datetime.now(timezone.utc)
        self._processing_stats["total_accounts"] = len(self.config.accounts)
        self._guard_start = self._guard_counts()

        try:
            # Step 1: Validate and establish account contexts
            self.logger.info("Validating account credentials and establishing contexts")
            account_contexts = self._establish_account_contexts()
            self._checkpoints = self._open_checkpoints(account_contexts)
            self._announce_cost_requests(account_contexts)

            # Step 2: Discover resources across all accounts
            self.logger.info("Starting resource discovery across all accounts")
            if self.config.parallel_account_processing:
                all_resources = self._parallel_account_discovery(account_contexts)
            else:
                all_resources = self._sequential_account_discovery(account_contexts)

            # A run in which no account could be scanned is a failure. An
            # empty report and an empty state snapshot would otherwise look
            # like every resource had been deleted.
            only_partial = False
            if (
                self.config.accounts
                and self._processing_stats["successful_accounts"] == 0
            ):
                if not any(
                    getattr(ctx, "partial", False) is True
                    for ctx in self.account_contexts.values()
                ):
                    raise AccountSessionError(
                        "Resource discovery failed for all "
                        f"{len(self.config.accounts)} configured account(s); "
                        "no report was generated"
                    )
                # Every account ran out of time, some with results: write a
                # report of what was found (it names the accounts), but the
                # run still fails and no snapshot is saved.
                only_partial = True

            for note in self._expired_session_notes():
                self.logger.error(note)
            for note in self._read_nothing_notes():
                self.logger.warning(note)
            for note in self._cost_trend_notes():
                self.logger.warning(note)

            # Step 3: Consolidate resources if configured
            if self.config.consolidate_accounts:
                self.logger.info("Consolidating resources from all accounts")
                consolidated_resources = self._consolidate_account_resources(
                    all_resources
                )
            else:
                consolidated_resources = all_resources

            finops = self._run_finops_checks(consolidated_resources)
            if self.config.finops_cost_allocation:
                self._finops_costs = self._read_cost_allocation()

            # Step 4: Process compliance checking if policies provided
            compliance_results = {}
            if compliance_policies:
                self.logger.info("Running compliance analysis across all resources")
                compliance_results = self._run_compliance_analysis(
                    consolidated_resources, compliance_policies
                )

            # Step 5: Generate BOM documents
            self.logger.info("Generating BOM documents")
            bom_results = self._generate_bom_documents(
                consolidated_resources,
                compliance_results,
                output_formats or ["excel", "word"],
            )

            # A requested report that could not be written fails the run.
            if not bom_results.get("success", True):
                raise ReportGenerationError(
                    bom_results.get("error") or "Report generation failed",
                    bom_results,
                )
            if only_partial:
                self._finish_checkpoints()
                raise ReportGenerationError(
                    "No account finished within its time limit "
                    "(--account-processing-timeout); the report lists only the "
                    "resources found before the limit",
                    bom_results,
                )

            # Step 6: Generate state management artifacts if enabled
            state_results = {}
            if self.config.enable_state_management:
                state_results = self._generate_state_artifacts(consolidated_resources)
                self._state_notes = self._notes_for_state(state_results)

            self._finish_checkpoints()

            self._log_guard_blocks()

            # Step 7: Compile final results
            self._processing_stats["processing_end_time"] = datetime.now(timezone.utc)
            processing_time = (
                self._processing_stats["processing_end_time"]
                - self._processing_stats["processing_start_time"]
            ).total_seconds()

            results = {
                "success": True,
                "processing_statistics": {
                    **self._processing_stats,
                    "processing_time_seconds": processing_time,
                    "total_resources": len(consolidated_resources),
                },
                "account_contexts": {
                    acc_id: {
                        "account_name": ctx.credentials.account_name,
                        "resource_count": ctx.resource_count,
                        "processing_time_seconds": ctx.processing_time_seconds,
                        "accessible_regions": ctx.accessible_regions,
                        "discovered_services": ctx.discovered_services,
                        "error_count": len(ctx.processing_errors),
                        "errors": list(ctx.processing_errors),
                        "warning_count": len(ctx.processing_warnings),
                    }
                    for acc_id, ctx in self.account_contexts.items()
                },
                "failed_accounts": self._failed_accounts(),
                "reused_accounts": dict(self.reused_accounts),
                # What the reader must know; printed once by the CLI.
                "run_notes": self._run_notes(),
                "bom_generation": bom_results,
                "compliance_analysis": compliance_results,
                "state_management": state_results,
                "output_directory": str(self.output_dir),
            }
            permissions = self._permissions_denied()
            if permissions:
                results["permissions_denied"] = permissions
            if finops is not None:
                results["finops_checks"] = finops
            if self._finops_costs is not None:
                results["finops_costs"] = self._finops_costs

            outcome = (
                "completed (the state stage had a problem: see the run notes)"
                if self._state_notes
                else "completed successfully"
            )
            self.logger.info(
                f"Multi-account BOM generation {outcome} in {processing_time:.2f}s. "
                f"Processed {len(consolidated_resources)} resources across "
                f"{self._processing_stats['successful_accounts']} accounts"
            )

            return results

        except Exception as e:
            self.logger.error(f"Multi-account BOM generation failed: {e}")
            self._log_guard_blocks()
            self._processing_stats["processing_end_time"] = datetime.now(timezone.utc)

            failure = {
                "success": False,
                "error": str(e),
                "failed_accounts": self._failed_accounts(),
                "run_notes": self._run_notes(),
                "processing_statistics": self._processing_stats,
                "account_contexts": {
                    acc_id: {
                        "account_name": ctx.credentials.account_name,
                        "error_count": len(ctx.processing_errors),
                        "errors": ctx.processing_errors,
                    }
                    for acc_id, ctx in self.account_contexts.items()
                },
            }
            if isinstance(e, ReportGenerationError):
                failure["bom_generation"] = e.bom_results
            permissions = self._permissions_denied()
            if permissions:
                failure["permissions_denied"] = permissions
            return failure

    def generate_comprehensive_bom(
        self,
        output_formats: List[str] = None,
        s3_upload_config: Optional[Any] = None,
        compliance_policies: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Alias for generate_multi_account_bom for backward compatibility.

        Args:
            output_formats: List of output formats (word, excel, csv, json)
            s3_upload_config: optional S3UploadConfig; when given, generated
                files are uploaded with server-side encryption and any upload
                failure makes the result unsuccessful
            compliance_policies: Tag compliance policies to apply

        Returns:
            Dictionary containing generation results and metadata
        """
        results = self.generate_multi_account_bom(
            output_formats=output_formats, compliance_policies=compliance_policies
        )

        if (
            s3_upload_config
            and results.get("success")
            and not (results.get("bom_generation") or {}).get("generated_files")
            and (results.get("bom_generation") or {}).get("total_resources") == 0
        ):
            # Nothing was written, so nothing failed to upload (A-29). The run
            # still ends with code 1 as in v1.2.1 (owner decision O3).
            from .s3_upload import normalize_key_prefix

            prefix = normalize_key_prefix(s3_upload_config.key_prefix)
            bom_results = results.setdefault("bom_generation", {})
            bom_results["s3_uploads"] = []
            bom_results["s3_upload_errors"] = []
            results["success"] = False
            results["error"] = (
                f"Nothing to upload to s3://{s3_upload_config.bucket_name}/"
                f"{prefix + '/' if prefix else ''}: the run wrote no report file "
                "because there are no resources to report."
            )
        elif s3_upload_config and results.get("success"):
            bom_results = results.setdefault("bom_generation", {})
            upload = self.upload_reports_to_s3(
                bom_results.get("generated_files", []), s3_upload_config
            )
            bom_results["s3_uploads"] = [item["key"] for item in upload["uploaded"]]
            bom_results["s3_upload_errors"] = upload["errors"]
            if upload["errors"]:
                results["success"] = False
                results["error"] = (
                    f"S3 upload failed for {len(upload['errors'])} file(s)"
                )
                self._add_upload_permissions(results, upload["errors"])
        elif s3_upload_config and "bom_generation" in results:
            # A failed report format returns the files written so far.
            from .s3_upload import skipped_upload_message

            self.logger.error(
                skipped_upload_message(
                    s3_upload_config.bucket_name, s3_upload_config.key_prefix
                )
            )

        return results

    def upload_reports_to_s3(
        self, files: List[str], s3_upload_config: Any
    ) -> Dict[str, Any]:
        """Upload generated report files to S3 with server-side encryption.

        Uses the default credential chain (the identity running InvenTag), not
        a scanned account's assumed role: the reports bucket normally lives in
        the account that runs the scan.
        """
        from .s3_upload import create_upload_client, upload_files

        if not files:
            return {"uploaded": [], "errors": [{"file": "", "error": "no files"}]}
        session = boto3.Session()
        s3_client = create_upload_client(
            session, getattr(s3_upload_config, "region", None) or None
        )
        try:
            return upload_files(
                s3_client,
                files,
                bucket=s3_upload_config.bucket_name,
                key_prefix=s3_upload_config.key_prefix,
                encryption=s3_upload_config.encryption,
                kms_key_id=getattr(s3_upload_config, "kms_key_id", None),
                storage_class=getattr(s3_upload_config, "storage_class", "STANDARD"),
                public_read=getattr(s3_upload_config, "public_read", False),
            )
        except Exception as e:
            self.logger.error(f"S3 upload failed: {e}")
            return {"uploaded": [], "errors": [{"file": "", "error": str(e)}]}

    def _coverage_summary(self) -> Dict[str, Dict[str, int]]:
        """Per account: how many listings ended ok, empty, denied, throttled,
        error or timeout (from the discovery coverage ledger)."""
        summary: Dict[str, Dict[str, int]] = {}
        for acc_id, ctx in self.account_contexts.items():
            counts: Dict[str, int] = {}
            for entry in _coverage_of(ctx):
                outcome = str(entry.get("outcome", ""))
                counts[outcome] = counts.get(outcome, 0) + 1
            if counts:
                summary[str(acc_id)] = counts
        return summary

    def _delta_scope(self) -> Dict[str, Any]:
        """What this run read, for the change report (A-05): the coverage
        ledger, and per account the regions and services it scanned."""
        return {
            "coverage": [
                entry
                for ctx in self.account_contexts.values()
                for entry in _coverage_of(ctx)
            ],
            "regions": {
                str(acc_id): list(
                    ctx.accessible_regions or ctx.credentials.regions or []
                )
                for acc_id, ctx in self.account_contexts.items()
            },
            "services": {
                str(acc_id): list(ctx.credentials.services or [])
                for acc_id, ctx in self.account_contexts.items()
            },
        }

    def _failed_accounts(self) -> List[Dict[str, Any]]:
        """Accounts that were not scanned (or only partly), with the reasons."""
        failed = []
        for acc_id, ctx in self.account_contexts.items():
            if ctx.session is None or ctx.processing_errors:
                failed.append(
                    {
                        "account_id": acc_id,
                        "account_name": ctx.credentials.account_name,
                        "errors": list(ctx.processing_errors)
                        or ["The AWS session could not be created."],
                    }
                )
        return failed

    def _accounts_with_expired_session(self) -> Dict[str, int]:
        """Accounts (not already failed) whose session expired during the
        scan, with the number of listings that failed because of it."""
        failed_ids = {item["account_id"] for item in self._failed_accounts()}
        expired = {}
        for acc_id, ctx in self.account_contexts.items():
            count = _expired_listings(ctx)
            if count and acc_id not in failed_ids:
                expired[acc_id] = count
        return expired

    def _expired_session_notes(self) -> List[str]:
        return [
            f"The session for account {acc_id} expired during the scan, so "
            f"{count} listing(s) were not read and this report is incomplete "
            "for that account."
            for acc_id, count in self._accounts_with_expired_session().items()
        ]

    def _accounts_without_service_apis(self) -> Dict[str, int]:
        """Accounts in which no service-API listing succeeded and at least
        one was denied or failed, with the number of resources the run still
        found for them (Tagging API rows). Failed accounts and accounts whose
        session expired are not included: they have their own note."""
        failed_ids = {item["account_id"] for item in self._failed_accounts()}
        failed_ids |= set(self._accounts_with_expired_session())
        accounts = {}
        for acc_id, ctx in self.account_contexts.items():
            if acc_id in failed_ids:
                continue
            entries = _coverage_of(ctx)
            if any(
                e.get("source") == "service-api"
                and (e.get("outcome") in (OK, EMPTY) or int(e.get("count") or 0) > 0)
                for e in entries
            ):
                continue
            if any(e.get("outcome") in FAILED_OUTCOMES for e in entries):
                accounts[acc_id] = int(getattr(ctx, "resource_count", 0) or 0)
        return accounts

    def _accounts_that_read_nothing(self) -> List[str]:
        """Accounts for which the run read nothing at all: every service
        listing denied or failed and no resource from any other source. They
        are left out of change tracking. An account the Tagging API still
        returned resources for is compared (the units whose listing failed
        are "not compared" by the change report)."""
        return [
            acc_id
            for acc_id, count in self._accounts_without_service_apis().items()
            if count == 0
        ]

    def _read_nothing_notes(self) -> List[str]:
        notes = []
        for acc_id, count in self._accounts_without_service_apis().items():
            if count == 0:
                notes.append(
                    f"Every service listing of account {acc_id} was denied or "
                    "failed, so nothing was read from its service APIs and it is "
                    "left out of change tracking."
                )
            else:
                notes.append(
                    f"Every service listing of account {acc_id} was denied or "
                    f"failed, so the report holds only the {count} resource(s) "
                    "the Tagging API returned, and the change report does not "
                    "compare the resources of the listings that failed."
                )
        return notes

    def _not_read_notes(self) -> List[str]:
        """Per account: the listings that were not read, grouped by service
        and region with the reasons, and the regions the access check
        skipped. Accounts that failed, read nothing or lost their session
        have their own note and are not listed again."""
        own_note = {item["account_id"] for item in self._failed_accounts()}
        own_note |= set(self._accounts_with_expired_session())
        own_note |= set(self._accounts_without_service_apis())
        notes = []
        for acc_id, ctx in self.account_contexts.items():
            if acc_id in own_note:
                continue
            reasons: Dict[tuple, set] = {}
            for e in _coverage_of(ctx):
                if e.get("source") not in ("service-api", "tagging-api"):
                    continue  # billing has its own warning and drops no row
                if e.get("outcome") not in FAILED_OUTCOMES:
                    continue
                if str(e.get("error_code", "")) == _NO_SUCH_SERVICE_CODE:
                    continue
                key = (str(e.get("service", "")), str(e.get("region", "")))
                reasons.setdefault(key, set()).add(str(e.get("outcome")))
            if reasons:
                items = [
                    f"{service} in {region} ({', '.join(sorted(why))})"
                    for (service, region), why in sorted(reasons.items())
                ]
                text = "; ".join(items[:_NOT_READ_LIMIT])
                if len(items) > _NOT_READ_LIMIT:
                    text += f", and {len(items) - _NOT_READ_LIMIT} more"
                notes.append(
                    f"Not read in account {acc_id}, so the report is partial "
                    f"there: {text}."
                )
            details = self._detail_note(acc_id, ctx)
            if details:
                notes.append(details)
            unknown = self._unknown_regions.get(str(acc_id)) or []
            if unknown:
                notes.append(
                    f"Regions not scanned in account {acc_id} because their region "
                    "check failed and the installed boto3 does not know them (a "
                    f"misspelled name, or a region newer than boto3): "
                    f"{', '.join(unknown)}."
                )
            skipped = getattr(ctx, "skipped_regions", None) or []
            if skipped:
                notes.append(
                    f"Regions skipped in account {acc_id} because the region "
                    f"check (ec2:DescribeRegions) was denied or failed there: "
                    f"{', '.join(skipped)}."
                )
        return notes

    @staticmethod
    def _detail_note(acc_id: str, ctx) -> Optional[str]:
        """Detail calls that failed (ledger source ``service-api-detail``,
        written by discovery since A-22): their rows are in the report with
        some fields missing. None when there is no such record."""
        groups: Dict[tuple, Dict[str, int]] = {}
        for e in _coverage_of(ctx):
            if e.get("source") != DETAIL_SOURCE:
                continue
            if e.get("outcome") not in FAILED_OUTCOMES:
                continue
            if str(e.get("error_code", "")) == _NO_SUCH_SERVICE_CODE:
                continue
            key = (
                str(e.get("service", "")),
                str(e.get("operation", "")),
                str(e.get("region", "")),
            )
            outcome = str(e.get("outcome"))
            counts = groups.setdefault(key, {})
            counts[outcome] = counts.get(outcome, 0) + int(e.get("count") or 0)
        if not groups:
            return None
        total = sum(sum(c.values()) for c in groups.values())
        items = [
            f"{service} {operation} in {region} ("
            + ", ".join(f"{o}, {n}" for o, n in sorted(counts.items()))
            + ")"
            for (service, operation, region), counts in sorted(groups.items())
        ]
        text = "; ".join(items[:_NOT_READ_LIMIT])
        if len(items) > _NOT_READ_LIMIT:
            text += f", and {len(items) - _NOT_READ_LIMIT} more"
        return (
            f"Details of {total} resource(s) in account {acc_id} could not be "
            f"read, so those rows have some fields missing: {text}."
        )

    def _units_not_read(self) -> List[Dict[str, str]]:
        """One entry per (account, service, region, source) whose service or
        Tagging API listing failed in this run; the worst outcome wins
        (timeout, throttled, error, denied). Billing, detail calls and the
        no-such-service code are not units."""
        rank = {"timeout": 0, "throttled": 1, "error": 2, "denied": 3}
        units: Dict[tuple, str] = {}
        for ctx in self.account_contexts.values():
            for e in _coverage_of(ctx):
                source = e.get("source")
                outcome = str(e.get("outcome", ""))
                if source not in ("service-api", "tagging-api"):
                    continue
                if outcome not in rank:
                    continue
                if str(e.get("error_code", "")) == _NO_SUCH_SERVICE_CODE:
                    continue
                key = (
                    str(e.get("account_id", "")),
                    str(e.get("service", "")),
                    str(e.get("region", "")),
                    str(source),
                )
                if key not in units or rank[outcome] < rank[units[key]]:
                    units[key] = outcome
        return [
            {
                "account": account,
                "service": service,
                "region": region,
                "source": source,
                "outcome": outcome,
            }
            for (account, service, region, source), outcome in sorted(units.items())
        ]

    def _details_not_read(self) -> List[Dict[str, str]]:
        """One entry per (account, service, region, resource type) whose
        detail call failed in this run (ledger source ``service-api-detail``);
        the worst outcome wins, as in ``_units_not_read``. The next change
        report does not compare the fields those calls add (A-78)."""
        rank = {"timeout": 0, "throttled": 1, "error": 2, "denied": 3}
        units: Dict[tuple, tuple] = {}
        for ctx in self.account_contexts.values():
            for e in _coverage_of(ctx):
                outcome = str(e.get("outcome", ""))
                if e.get("source") != DETAIL_SOURCE or outcome not in rank:
                    continue
                if str(e.get("error_code", "")) == _NO_SUCH_SERVICE_CODE:
                    continue
                key = (
                    str(e.get("account_id", "")),
                    str(e.get("service", "")),
                    str(e.get("region", "")),
                    str(e.get("resource_type", "")),
                )
                found = (str(e.get("operation", "")), outcome)
                if key not in units or rank[outcome] < rank[units[key][1]]:
                    units[key] = found
        return [
            {
                "account": account,
                "service": service,
                "region": region,
                "resource_type": resource_type,
                "operation": operation,
                "outcome": outcome,
            }
            for (account, service, region, resource_type), (
                operation,
                outcome,
            ) in sorted(units.items())
        ]

    def _filter_texts(self) -> List[str]:
        """The service and tag filters of this run, as the options that set
        them (A-20); empty when no filter is set."""
        services = sorted(
            {
                str(s)
                for ctx in self.account_contexts.values()
                for s in (ctx.credentials.services or [])
            }
        )
        tags: Dict[str, Any] = {}
        for ctx in self.account_contexts.values():
            tags.update(ctx.credentials.tags or {})
        texts = []
        if services:
            texts.append(f"--account-services {','.join(services)}")
        if tags:
            texts.append(f"--account-tags {json.dumps(tags, sort_keys=True)}")
        return texts

    def _notes_for_state(self, state: Dict[str, Any]) -> List[str]:
        """Run notes for a snapshot, an index or a change report that could
        not be made (A-18). A snapshot left out on purpose (nothing was read,
        A-01) has its own note."""
        if not isinstance(state, dict):
            return []
        state_dir = self.output_dir / "state"
        notes = []
        if state.get("state_saved") is False and state.get("error"):
            notes.append(
                f"The state snapshot was not saved ({state['error']}), so the next "
                "change report will compare with an older snapshot; check that "
                f"{state_dir} is writable."
            )
        if state.get("state_index_error"):
            notes.append(
                "The state snapshot was saved, but the list of snapshots could not "
                f"be updated ({state['state_index_error']}), so the next change "
                "report may compare with an older snapshot; check that "
                f"{state_dir} is writable."
            )
        delta = state.get("delta_detection")
        if isinstance(delta, dict) and delta.get("error"):
            notes.append(
                f"The change report could not be made ({delta['error']}); the "
                "snapshot of this run was saved."
            )
        return notes

    def _announce_cost_requests(self, account_contexts) -> None:
        """Say once, before discovery, how many Cost Explorer requests the run
        makes at most: AWS charges for each (architect F1 ruling 5). A warning
        only with --enable-cost-analysis; otherwise INFO, so a default run's
        console is what v1.4.0 printed (architect v1.4.1 ruling)."""
        cost_analysis = bool(self.config.bom_processing_config.enable_cost_analysis)
        allocation = bool(getattr(self.config, "finops_cost_allocation", False))
        count, parts = cost_requests.planned(
            len(account_contexts),
            bool(self.config.enable_billing_validation),
            cost_analysis,
            cost_allocation=allocation,
        )
        text = cost_requests.announcement(count, parts)
        if text:
            if cost_analysis or allocation:
                self.logger.warning(text)
            else:
                self.logger.info(text)

    def _cost_trend_notes(self) -> List[str]:
        """A-80: with several accounts, the cost trend reads one bill, with the
        credentials of the account the report processing uses."""
        if not self.config.bom_processing_config.enable_cost_analysis:
            return []
        if len(self.account_contexts) < 2:
            return []
        account = self._run_account()
        return [cost_requests.trend_note(account)] if account else []

    def _billing_timeout_notes(self) -> List[str]:
        """One note per account whose Cost Explorer call did not answer in
        time (A-24): its listings are in the report, its billing data is not."""
        failed_ids = {item["account_id"] for item in self._failed_accounts()}
        notes = []
        for acc_id, ctx in self.account_contexts.items():
            if acc_id in failed_ids:
                continue
            if any(
                e.get("source") == "billing"
                and str(e.get("error_code", "")) in _TIMEOUT_ERRORS
                for e in _coverage_of(ctx)
            ):
                notes.append(
                    f"Cost Explorer did not answer in time for account {acc_id}, "
                    "so its billing checks were skipped and services that only "
                    "billing shows are not listed for it."
                )
        return notes

    @staticmethod
    def _guard_audit() -> Optional[Dict[str, Any]]:
        guard = get_installed_guard()
        if guard is None:
            return None
        try:
            return guard.audit_report()
        except Exception:
            return None

    def _guard_counts(self) -> tuple:
        audit = self._guard_audit() or {}
        return (int(audit.get("blocked_calls", 0)), len(audit.get("blocked", [])))

    def _guard_block_notes(self) -> List[str]:
        """One note when the read-only guard blocked a call in this run: a
        blocked call is a defect in InvenTag, not in the user's account."""
        audit = self._guard_audit()
        if not audit:
            return []
        calls_before, entries_before = self._guard_start
        count = int(audit.get("blocked_calls", 0)) - calls_before
        if count <= 0:
            return []
        operations = sorted(
            {
                f"{b.get('service')}:{b.get('operation')}"
                for b in audit.get("blocked", [])[entries_before:]
            }
        )
        return [
            f"The read-only guard blocked {count} call(s) "
            f"({', '.join(operations)}); this is a defect in InvenTag, not in "
            "your account, so please report it."
        ]

    def _log_guard_blocks(self) -> None:
        for note in self._guard_block_notes():
            self.logger.error(note)

    def _run_account(self) -> str:
        """The account whose session the steps of the whole run use: the first
        with a session (as in ``_generate_bom_documents``)."""
        for acc_id, ctx in self.account_contexts.items():
            if ctx.session:
                return str(acc_id)
        return ""

    def _collect_run_denials(self, bom_processor) -> None:
        """Keep the calls the processor's steps were refused (cost analysis,
        the ElastiCache read of the network analysis) for the permissions
        summary. Main thread only, after processing."""
        cost = getattr(bom_processor, "cost_analyzer", None)
        if cost is not None:
            self._cost_denials = list(cost.permission_denials())
        analyzer = getattr(bom_processor, "network_analyzer", None)
        unread = getattr(analyzer, "unread_cache_regions", None) or {}
        self._analysis_denials = [
            ("elasticache", "DescribeCacheSubnetGroups", code, region)
            for region, code in sorted(unread.items())
        ]

    def _permissions_denied(self) -> List[Dict[str, Any]]:
        """The IAM actions this run was not allowed to use (empty when none):
        the ``permissions_denied`` key and the Permissions run notes."""
        return permissions_report.build(
            coverage=[
                entry
                for ctx in self.account_contexts.values()
                for entry in _coverage_of(ctx)
            ],
            account_failures=[
                {
                    "account_id": str(acc_id),
                    "error_code": getattr(ctx, "assume_role_error_code", ""),
                }
                for acc_id, ctx in self.account_contexts.items()
                if getattr(ctx, "assume_role_error_code", "")
            ],
            upload_outcomes=self._upload_outcomes,
            cost_denials=self._cost_denials,
            analysis_denials=self._analysis_denials,
            run_account=self._run_account(),
            allocation_denials=(
                cost_allocation.denials(self._finops_costs)
                if getattr(self, "_finops_costs", None) is not None
                else ()
            ),
        )

    def _add_upload_permissions(self, results: Dict[str, Any], errors) -> None:
        """After a failed report upload: add what the upload was refused to
        the result and, when AWS refused it, say so in the log (a failed run
        prints no run notes)."""
        self._upload_outcomes = list(errors)
        permissions = self._permissions_denied()
        if not any(e["kind"] == "upload" for e in permissions):
            return
        results["permissions_denied"] = permissions
        results["run_notes"] = self._run_notes()
        for note in permissions_report.notes(permissions):
            self.logger.warning(note)

    def _run_notes(self) -> List[str]:
        """Lines for the report: which accounts are missing and why, and
        which accounts come from an earlier, interrupted run (``--resume``)."""
        notes = []
        failed = self._failed_accounts()
        if failed:
            partial = [
                item
                for item in failed
                if getattr(
                    self.account_contexts.get(item["account_id"]), "partial", False
                )
                is True
            ]
            if len(partial) == len(failed):
                notes.append(
                    f"{len(failed)} of {len(self.account_contexts)} account(s) were "
                    "only partly scanned (time limit); the resources found are "
                    "included, others may be missing:"
                )
            elif partial:
                notes.append(
                    f"{len(failed)} of {len(self.account_contexts)} account(s) failed: "
                    f"{len(partial)} were only partly scanned (the resources found "
                    "are included), the others are not in this report:"
                )
            else:
                notes.append(
                    f"{len(failed)} of {len(self.account_contexts)} account(s) were "
                    "not scanned, so this report does not include them:"
                )
            for item in failed:
                reason = "; ".join(item["errors"])[:300]
                notes.append(f"{item['account_id']} ({item['account_name']}): {reason}")
        notes.extend(self._expired_session_notes())
        notes.extend(self._read_nothing_notes())
        notes.extend(self._not_read_notes())
        notes.extend(self._billing_timeout_notes())
        notes.extend(self._cost_trend_notes())
        costs = getattr(self, "_finops_costs", None)
        if costs is not None:
            notes.extend(cost_allocation.run_notes(costs))
        notes.extend(self._state_notes)
        notes.extend(self._guard_block_notes())
        notes.extend(permissions_report.notes(self._permissions_denied()))
        if self.reused_accounts:
            notes.append(
                f"{len(self.reused_accounts)} account(s) were not scanned again: "
                "their results come from an earlier run of the same command "
                "(--resume), scanned at:"
            )
            for account_id, scanned_at in sorted(self.reused_accounts.items()):
                notes.append(f"{account_id}: {scanned_at}")
        # The notes go into the report and the result as well as the log, and
        # some carry error texts: mask secrets as the log filter does (A-69).
        return [redact(note) for note in notes]

    # ------------------------------------------------------------ checkpoints
    def _checkpoint_scope(self, account_contexts: Dict[str, AccountContext]) -> Dict:
        """Everything that changes what a scan returns (not output options)."""
        return {
            "checkpoint_schema": 1,
            "inventag": ".".join(__version__.split(".")[:2]),
            "accounts": {
                str(account_id): {
                    "regions": sorted(
                        ctx.accessible_regions or ctx.credentials.regions or []
                    ),
                    "services": sorted(ctx.credentials.services or []),
                    "tags": dict(ctx.credentials.tags or {}),
                    "role_arn": ctx.credentials.role_arn or "",
                    "profile": ctx.credentials.profile_name or "",
                }
                for account_id, ctx in sorted(account_contexts.items())
            },
            "billing_validation": bool(self.config.enable_billing_validation),
            "fallback_display_mode": self.config.fallback_display_mode,
        }

    def _open_checkpoints(self, account_contexts: Dict[str, AccountContext]):
        if not self.config.enable_state_management:
            if self.config.resume:
                self.logger.warning(
                    "--resume has no effect: checkpoints need state management"
                )
            return None
        try:
            store = PartialResultStore(
                str(self.output_dir / "state"),
                make_run_key(self._checkpoint_scope(account_contexts)),
                max_age_hours=self.config.resume_max_age_hours,
            )
            if not self.config.resume:
                saved = store.completed_accounts()
                if saved:
                    self.logger.warning(
                        f"{len(saved)} account(s) have saved results from an "
                        "earlier run of this command that did not finish. They "
                        "are scanned again; add --resume to reuse them."
                    )
            return store
        except Exception as e:
            self.logger.warning(f"Checkpoints are off for this run: {e}")
            return None

    def _load_checkpoint(
        self, account_id: str, context: AccountContext
    ) -> Optional[List[Dict[str, Any]]]:
        """Saved resources for this account (``--resume`` only), else None."""
        if not self.config.resume or self._checkpoints is None:
            return None
        hit = self._checkpoints.load_account(account_id)
        if hit is None:
            self.logger.info(f"{account_id}: no usable saved result; scanning")
            return None
        scanned_at = hit.completed_at.strftime("%Y-%m-%d %H:%M UTC")
        self.logger.warning(
            f"{account_id}: reusing results scanned {scanned_at} (--resume)"
        )
        self.reused_accounts[str(account_id)] = scanned_at
        context.resource_count = len(hit.resources)
        context.discovered_services = list(
            set(r.get("service", "") for r in hit.resources)
        )
        self._processing_stats["successful_accounts"] += 1
        return hit.resources

    def _save_checkpoint(
        self,
        account_id: str,
        context: AccountContext,
        resources: List[Dict[str, Any]],
    ) -> None:
        """Save a completely scanned account (main thread only). An account
        whose session expired during the scan was read only in part: it is
        not saved, so ``--resume`` scans it again."""
        if (
            self._checkpoints is None
            or context.processing_errors
            or _expired_listings(context)
        ):
            return
        try:
            self._checkpoints.save_account(
                account_id, resources, list(context.accessible_regions)
            )
        except Exception as e:
            self.logger.warning(f"Could not save checkpoint for {account_id}: {e}")

    def _finish_checkpoints(self) -> None:
        """Remove checkpoints after a run with every account scanned; else
        tell the user how to resume."""
        if self._checkpoints is None:
            return
        failed = self._failed_accounts()
        failed_ids = {item["account_id"] for item in failed}
        # Accounts not saved although they did not fail: the session expired.
        not_saved = [
            acc_id
            for acc_id, ctx in self.account_contexts.items()
            if acc_id not in failed_ids and _expired_listings(ctx)
        ]
        if not failed and not not_saved:
            try:
                self._checkpoints.clear()
            except Exception as e:
                self.logger.warning(f"Could not remove checkpoints: {e}")
            return
        others = len(failed) + len(not_saved)
        saved = len(self.account_contexts) - others
        hours = self.config.resume_max_age_hours
        self.logger.warning(
            f"{saved} of {len(self.account_contexts)} account(s) finished and were "
            f"saved. Run the same command with --resume within {hours:g} hours "
            f"to scan only the other {others}."
        )

    @property
    def _last_unknown(self) -> List[str]:
        return getattr(self._region_local, "unknown", [])

    @_last_unknown.setter
    def _last_unknown(self, value: List[str]) -> None:
        self._region_local.unknown = value

    def _establish_account_contexts(self) -> Dict[str, AccountContext]:
        """Validate credentials and establish account contexts.

        Accounts are validated through an account pool (at most
        ``max_concurrent_accounts`` at once; one after the other with
        ``--disable-parallel-processing``). An account that needs a terminal
        (the SDK asks for an MFA code) is handled first, on this thread. The
        contexts are recorded here, in the configured order, whatever order
        the accounts finish in.
        """
        accounts = list(self.config.accounts)
        results: List[Any] = [None] * len(accounts)
        on_terminal = [i for i, c in enumerate(accounts) if self._needs_terminal(c)]
        for i in on_terminal:
            results[i] = self._establish_one(accounts[i])
        rest = [i for i in range(len(accounts)) if i not in on_terminal]
        if self.config.parallel_account_processing and len(rest) > 1:
            pool = DaemonThreadPool(self.config.max_concurrent_accounts)
            try:
                futures = [
                    (i, pool.submit(self._establish_one, accounts[i])) for i in rest
                ]
                for i, future in futures:
                    results[i] = future.result()
            finally:
                pool.shutdown(wait=False)
        else:
            for i in rest:
                results[i] = self._establish_one(accounts[i])

        account_contexts = {}
        for context, unknown in results:
            account_id = context.credentials.account_id
            if unknown:
                self._unknown_regions[str(account_id)] = unknown
            account_contexts[account_id] = context
            self.account_contexts[account_id] = context
        return account_contexts

    @staticmethod
    def _needs_terminal(credentials: AccountCredentials) -> bool:
        """True when the SDK will ask on the terminal for this account's MFA
        code: a profile with ``mfa_serial`` while stdin is a terminal."""
        if not credentials.profile_name:
            return False
        try:
            if sys.stdin is None or not sys.stdin.isatty():
                return False
            config = boto3.Session(
                profile_name=credentials.profile_name
            )._session.get_scoped_config()
        except Exception:
            return False
        serial = config.get("mfa_serial")
        return isinstance(serial, str) and bool(serial)

    def _establish_one(self, credentials: AccountCredentials):
        """One account's context and the region names botocore did not know
        (returned, not recorded: the caller records both in order)."""
        try:
            self.logger.info(
                f"Establishing context for account {credentials.account_id}"
            )

            # Create session
            session = self._create_account_session(credentials)

            # Get caller identity to validate credentials
            caller_identity = self._get_caller_identity(session)

            # Validate account ID matches. Scanning a different account
            # than the one configured would mislabel every resource in the
            # report, so a mismatch on a real account ID is fatal.
            actual_account_id = caller_identity.get("Account", "")
            if (
                is_valid_account_id(credentials.account_id)
                and credentials.account_id != actual_account_id
            ):
                raise AccountSessionError(
                    f"Credentials for account {credentials.account_id} "
                    f"resolved to account {actual_account_id}; refusing to "
                    "scan the wrong account. Check the profile, role ARN or "
                    "cross-account role for this account."
                )
            if credentials.account_id != actual_account_id:
                self.logger.warning(
                    f"Account ID mismatch for {credentials.account_id}. "
                    f"Actual: {actual_account_id}"
                )

                # If the original account_id was "default", update it with the real account ID
                if credentials.account_id == "default":
                    self.logger.info(
                        f"Updating account ID from 'default' to actual account ID: {actual_account_id}"
                    )
                    credentials.account_id = actual_account_id
                    # Also update account name to be more descriptive if it was generic
                    if credentials.account_name == "Default AWS Account":
                        caller_arn = caller_identity.get("Arn", "")
                        if "assumed-role" in caller_arn:
                            try:
                                role_part = caller_arn.split("assumed-role/")[1].split(
                                    "/"
                                )[0]
                                credentials.account_name = (
                                    f"AWS Account {actual_account_id} ({role_part})"
                                )
                            except Exception:
                                credentials.account_name = (
                                    f"AWS Account {actual_account_id}"
                                )
                        elif "user" in caller_arn:
                            try:
                                user_part = caller_arn.split("user/")[1]
                                credentials.account_name = (
                                    f"AWS Account {actual_account_id} ({user_part})"
                                )
                            except Exception:
                                credentials.account_name = (
                                    f"AWS Account {actual_account_id}"
                                )
                        else:
                            credentials.account_name = (
                                f"AWS Account {actual_account_id}"
                            )

            # Auto-discover regions if none specified: ec2:DescribeRegions,
            # then account:ListRegions, then every region of the partition
            # (inventag.discovery.regions; never a fixed short list).
            target_regions = credentials.regions
            if not target_regions:
                target_regions, source = discover_regions(session, self.logger)
                self.logger.info(
                    f"Auto-discovered {len(target_regions)} regions for "
                    f"account {credentials.account_id} (from {source})"
                )

            self._warn_other_partition_regions(
                session,
                credentials.account_id,
                caller_identity.get("Arn", ""),
                target_regions,
            )

            # Test accessible regions
            accessible_regions = self._test_accessible_regions(session, target_regions)

            # Create account context. With no accessible region at all,
            # discovery falls back to the target regions, so none is
            # skipped.
            context = AccountContext(
                credentials=credentials,
                session=session,
                caller_identity=caller_identity,
                accessible_regions=accessible_regions,
                skipped_regions=(
                    [
                        r
                        for r in target_regions
                        if r not in accessible_regions and r not in self._last_unknown
                    ]
                    if accessible_regions
                    else []
                ),
            )
            unknown = (
                list(self._last_unknown)
                if accessible_regions and self._last_unknown
                else []
            )

            self.logger.info(
                f"Successfully established context for account {credentials.account_id} "
                f"({credentials.account_name}) with {len(accessible_regions)} accessible regions"
            )
            return context, unknown

        except Exception as e:
            cause = str(e) or type(e).__name__
            self.logger.error(
                f"Failed to establish context for account {credentials.account_id}: {cause}"
            )
            # Create a failed context for tracking
            context = AccountContext(
                credentials=credentials,
                session=None,
                caller_identity={},
                processing_errors=[f"Context establishment failed: {cause}"],
                assume_role_error_code=getattr(e, "assume_role_error_code", ""),
            )
            return context, []

    def _create_account_session(self, credentials: AccountCredentials) -> boto3.Session:
        """Create a boto3 session for the given account credentials.

        Order: profile, explicit role ARN, access keys, configured cross-account
        role name, default credentials. If a profile or role ARN is configured
        and fails, this raises instead of silently falling back to the default
        credentials (which would scan a different account).
        """
        register_secrets([credentials.secret_access_key, credentials.session_token])

        if credentials.profile_name:
            try:
                session = self._limited_session(
                    credentials.account_id, profile_name=credentials.profile_name
                )
                serial = _mfa_serial_without_terminal(session)
                if serial:
                    raise AccountSessionError(
                        mfa_without_terminal_message(
                            credentials.profile_name, credentials.account_id, serial
                        )
                    )
                self._sts(session).get_caller_identity()
                return session
            except EOFError as e:
                # The SDK asked for an MFA code and stdin ended.
                raise AccountSessionError(
                    f"Profile {credentials.profile_name!r} for account "
                    f"{credentials.account_id} failed: {str(e) or type(e).__name__}"
                ) from e
            except (
                ProfileNotFound,
                NoCredentialsError,
                ClientError,
                BotoCoreError,
            ) as e:
                raise AccountSessionError(
                    f"Profile {credentials.profile_name!r} for account "
                    f"{credentials.account_id} failed: {e}"
                ) from e

        if credentials.role_arn:
            try:
                role_arn = validate_role_arn(credentials.role_arn)
                return self._assume_role_session(
                    role_arn, credentials.account_id, credentials.external_id
                )
            except (InvalidRoleError, ClientError, BotoCoreError) as e:
                raise AccountSessionError(
                    f"Role assumption failed for account {credentials.account_id}: {e}",
                    assume_role_error_code=(
                        str(e.response.get("Error", {}).get("Code") or "")
                        if isinstance(e, ClientError)
                        else ""
                    ),
                ) from e

        if credentials.access_key_id and credentials.secret_access_key:
            return self._limited_session(
                credentials.account_id,
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                aws_session_token=credentials.session_token,
            )

        # The default credentials already belong to this account: use them
        # directly instead of trying to assume a role in our own account.
        if (
            is_valid_account_id(credentials.account_id)
            and self.config.cross_account_role_name == "InvenTagCrossAccountRole"
            and self._default_caller_account() == str(credentials.account_id)
        ):
            return self._limited_session(credentials.account_id)

        if self.config.cross_account_role_name and is_valid_account_id(
            credentials.account_id
        ):
            role_arn = None
            try:
                role_arn = build_role_arn(
                    credentials.account_id,
                    self.config.cross_account_role_name,
                    partition=self._default_partition(),
                )
                return self._assume_role_session(
                    role_arn, credentials.account_id, credentials.external_id
                )
            except (InvalidRoleError, ClientError, BotoCoreError) as e:
                # One line per account at INFO, without the full AWS error text
                # (which repeats the caller ARN); the detail goes to DEBUG.
                code = (
                    e.response.get("Error", {}).get("Code", "error")
                    if isinstance(e, ClientError)
                    else type(e).__name__
                )
                self.logger.info(
                    f"Cross-account role not usable for account "
                    f"{credentials.account_id} ({code}); trying default credentials"
                )
                self.logger.debug(
                    f"Cross-account role {role_arn or self.config.cross_account_role_name}: {e}"
                )

        # Fallback to default session. _establish_account_contexts verifies
        # that it really belongs to the configured account.
        try:
            session = self._limited_session(credentials.account_id)
            self._sts(session).get_caller_identity()
            return session
        except Exception as e:
            raise AccountSessionError(
                f"Failed to create valid session for account {credentials.account_id}: {e}"
            ) from e

    def _limited_session(self, account_id, **kwargs) -> boto3.Session:
        """A new boto3 session with the run's limiter, before any client is
        made from it (clients copy the session's handlers when created). The
        account's scan puts the limiter on again with the account's deadline
        (:meth:`_attach_limiter`)."""
        session = boto3.Session(**kwargs)
        if getattr(session, "events", None) is not None:
            self.limiter.attach(session, str(account_id))
        return session

    def _assume_role_session(
        self, role_arn: str, account_id: str, external_id: Optional[str] = None
    ) -> boto3.Session:
        """Assume ``role_arn`` with the default credentials and return a session."""
        sts = self._sts(self._limited_session(account_id))
        session_label = "".join(
            ch if ch.isalnum() or ch in "+=,.@-" else "-" for ch in str(account_id)
        )
        kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": f"InvenTag-{session_label}-{int(datetime.now().timestamp())}"[
                :64
            ],
        }
        if external_id:
            kwargs["ExternalId"] = external_id
        response = sts.assume_role(**kwargs)
        temp = response["Credentials"]
        register_secrets([temp["SecretAccessKey"], temp["SessionToken"]])
        return self._limited_session(
            account_id,
            aws_access_key_id=temp["AccessKeyId"],
            aws_secret_access_key=temp["SecretAccessKey"],
            aws_session_token=temp["SessionToken"],
        )

    def _warn_other_partition_regions(
        self, session, account_id: str, identity_arn: str, regions: List[str]
    ) -> None:
        """Name each region of another partition than the credentials' (A-44).
        It is still tried, as before; it cannot work with these credentials."""
        own = partition_from_arn(identity_arn) if identity_arn else ""
        if not own:
            return
        for region in regions or []:
            try:
                other = session.get_partition_for_region(region)
            except Exception:
                continue
            if other and other != own:
                self.logger.warning(
                    f"Region '{region}' is in the {other} partition, but the "
                    f"credentials of account {account_id} are for the {own} "
                    "partition, so it cannot be scanned with them; scan it with "
                    "credentials of that partition."
                )

    def _identity_region(self, session) -> Optional[str]:
        """The region for STS identity checks (A-44): the session's own region,
        unless the scan's regions are in another partition (for example every
        configured region is in GovCloud while the default region is
        commercial); then the first configured region of that partition."""
        regions = [
            str(r)
            for account in (self.config.accounts or [])
            for r in (getattr(account, "regions", None) or [])
        ]
        if not regions:
            return None
        try:
            scan_partition = session.get_partition_for_region(regions[0])
            own = session.region_name
            if own and session.get_partition_for_region(own) == scan_partition:
                return None
        except Exception:
            return None
        return regions[0]

    def _sts(self, session):
        """STS client bounded by --credential-timeout (sign-in and role checks),
        in the scan's partition."""
        timeout = self.config.credential_validation_timeout
        region = self._identity_region(session)
        extra = {"region_name": region} if region else {}
        if not timeout:
            return session.client("sts", **extra)
        return session.client(
            "sts",
            **extra,
            config=BotoConfig(
                connect_timeout=timeout,
                read_timeout=timeout,
                retries={"max_attempts": 2},
            ),
        )

    def _default_caller_account(self) -> Optional[str]:
        """Account ID of the default credentials (looked up once per run)."""
        with self._identity_lock:
            if not hasattr(self, "_default_caller_account_id"):
                try:
                    self._default_caller_account_id = str(
                        self._sts(
                            self._limited_session("default")
                        ).get_caller_identity()["Account"]
                    )
                except Exception:
                    self._default_caller_account_id = None
            return self._default_caller_account_id

    def _default_partition(self) -> str:
        """Partition (aws, aws-cn, aws-us-gov...) of the default credentials."""
        with self._identity_lock:
            if self._default_identity is None:
                try:
                    self._default_identity = self._sts(
                        self._limited_session("default")
                    ).get_caller_identity()
                except Exception:
                    self._default_identity = {}
            return partition_from_arn(self._default_identity.get("Arn"))

    def _get_caller_identity(self, session: boto3.Session) -> Dict[str, Any]:
        """Get caller identity for account context detection."""
        try:
            # --credential-timeout bounds this call, so a wrong endpoint or a
            # blocked network fails quickly instead of hanging.
            timeout = self.config.credential_validation_timeout
            region = self._identity_region(session)
            sts = session.client(
                "sts",
                **({"region_name": region} if region else {}),
                config=BotoConfig(
                    connect_timeout=timeout,
                    read_timeout=timeout,
                    retries={"max_attempts": 1},
                ),
            )
            response = sts.get_caller_identity()

            return {
                "UserId": response.get("UserId", ""),
                "Account": response.get("Account", ""),
                "Arn": response.get("Arn", ""),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }

        except ClientError as e:
            raise Exception(f"Failed to get caller identity: {e}")

    def _test_accessible_regions(
        self, session: boto3.Session, target_regions: List[str]
    ) -> List[str]:
        """Test which regions are accessible for the account.

        The check is ``ec2:DescribeRegions`` in each region. A region where it
        is denied is skipped (for example an SCP that blocks the region). If it
        is denied in EVERY region, the policy simply lacks
        ``ec2:DescribeRegions``: the check cannot tell anything, so all regions
        are kept and their own calls show what is readable.
        """
        accessible_regions = []
        denied = []
        known = _known_regions(session)
        self._last_unknown = []

        for region in target_regions:
            try:
                # Test region accessibility with a simple EC2 describe call
                ec2 = session.client("ec2", region_name=region)
                ec2.describe_regions(RegionNames=[region])
                accessible_regions.append(region)

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ["UnauthorizedOperation", "AccessDenied"]:
                    self.logger.warning(f"No access to region {region}")
                    denied.append(region)
                elif not self._unknown_region_failed(region, known):
                    self.logger.warning(f"Region {region} test failed: {e}")
            except Exception as e:
                if not self._unknown_region_failed(region, known):
                    self.logger.warning(f"Region {region} test failed: {e}")

        if denied and not accessible_regions and len(denied) == len(target_regions):
            self.logger.warning(
                "ec2:DescribeRegions is denied in every region, so region access "
                f"cannot be checked; scanning all {len(denied)} regions."
            )
            return list(denied)
        return accessible_regions

    def _unknown_region_failed(self, region: str, known: set) -> bool:
        """For a region whose check failed: when the installed botocore does
        not know it either (a misspelled name, or a region newer than boto3),
        name it once with both causes and return True. A region botocore does
        not know but whose check passes is scanned as in v1.2.1."""
        if not known or region in known:
            return False
        self._last_unknown.append(region)
        with self._warned_lock:
            first = region not in self._warned_regions
            self._warned_regions.add(region)
        if first:
            self.logger.warning(
                f"Region '{region}' could not be checked and the installed boto3 "
                "does not know it: check its spelling in --account-regions or in "
                "the accounts file, or, if it is a new AWS region, upgrade boto3. "
                "To list the regions of your account, run: aws ec2 "
                "describe-regions --query 'Regions[].RegionName' --output text"
            )
        return True

    def _new_deadline(self, account_id: str) -> _AccountDeadline:
        return _AccountDeadline(
            account_id, self.config.account_processing_timeout, clock=self._clock
        )

    def _parallel_account_discovery(
        self, account_contexts: Dict[str, AccountContext]
    ) -> List[Dict[str, Any]]:
        """Discover resources across accounts in parallel.

        Each account has its own time limit, counted from when its scan
        starts. An account that runs out of time, or fails, is recorded as
        failed with the reason; every account that finished is kept. The main
        thread alone writes results into the account contexts and statistics,
        so a timed-out worker that returns late changes nothing.
        """
        self.logger.info(
            f"Starting parallel discovery across {len(account_contexts)} accounts"
        )

        all_resources: List[Dict[str, Any]] = []
        to_scan = self._accounts_to_scan(account_contexts, all_resources)
        if not to_scan:
            return all_resources

        deadlines = {
            account_id: self._new_deadline(account_id) for account_id in to_scan
        }
        # Rows per account, merged below in configured order (plan 2.4): the
        # order the accounts finish in must not show in the reports.
        found_by_account: Dict[str, List[Dict[str, Any]]] = {}
        executor = DaemonThreadPool(self.config.max_concurrent_accounts)
        try:
            future_to_account = {
                executor.submit(
                    self._scan_account,
                    account_id,
                    account_contexts[account_id],
                    deadlines[account_id],
                ): account_id
                for account_id in to_scan
            }
            pending = set(future_to_account)
            while pending:
                done, pending = wait(
                    pending,
                    timeout=self._poll_seconds,
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    account_id = future_to_account[future]
                    context = account_contexts[account_id]
                    try:
                        resources = future.result()
                    except Exception as e:
                        found_by_account[account_id] = self._record_account_failure(
                            account_id, context, e, deadlines[account_id]
                        )
                        continue
                    found_by_account[account_id] = self._record_account_success(
                        account_id, context, resources, deadlines[account_id]
                    )
                for future in list(pending):
                    account_id = future_to_account[future]
                    deadline = deadlines[account_id]
                    if not deadline.past_deadline():
                        continue
                    # Refuse the account's further AWS calls, then give the
                    # worker a short grace period to return what it found.
                    deadline.abandon()
                    if time.monotonic() - deadline.abandoned_at < self._grace(deadline):
                        continue
                    pending.discard(future)
                    self._record_account_failure(
                        account_id,
                        account_contexts[account_id],
                        AccountTimeoutError(deadline.message()),
                        deadline,
                    )
        finally:
            # Do not wait for abandoned workers: they can make no more AWS
            # calls, and their results are ignored.
            executor.shutdown(wait=False)
        for account_id in to_scan:
            all_resources.extend(found_by_account.get(account_id, []))

        self.logger.info(
            f"Parallel discovery completed. Total resources: {len(all_resources)}"
        )
        return all_resources

    def _sequential_account_discovery(
        self, account_contexts: Dict[str, AccountContext]
    ) -> List[Dict[str, Any]]:
        """Discover resources across accounts one after the other."""
        self.logger.info(
            f"Starting sequential discovery across {len(account_contexts)} accounts"
        )

        all_resources: List[Dict[str, Any]] = []
        for account_id in self._accounts_to_scan(account_contexts, all_resources):
            context = account_contexts[account_id]
            self.logger.info(f"Discovering resources for account {account_id}")
            deadline = self._new_deadline(account_id)
            try:
                resources = self._scan_account(account_id, context, deadline)
            except Exception as e:
                all_resources.extend(
                    self._record_account_failure(account_id, context, e, deadline)
                )
                continue
            all_resources.extend(
                self._record_account_success(account_id, context, resources, deadline)
            )

        self.logger.info(
            f"Sequential discovery completed. Total resources: {len(all_resources)}"
        )
        return all_resources

    def _accounts_to_scan(
        self,
        account_contexts: Dict[str, AccountContext],
        all_resources: List[Dict[str, Any]],
    ) -> List[str]:
        """Count accounts without a session as failed, reuse checkpoints
        (``--resume``), and return the accounts that still need a scan."""
        to_scan = []
        for account_id, context in account_contexts.items():
            if context.session is None:
                self.logger.warning(
                    f"Skipping account {account_id} due to invalid session"
                )
                self._processing_stats["failed_accounts"] += 1
                continue
            reused = self._load_checkpoint(account_id, context)
            if reused is not None:
                all_resources.extend(reused)
                continue
            to_scan.append(account_id)
        return to_scan

    def _record_account_success(
        self,
        account_id: str,
        context: AccountContext,
        resources: List[Dict[str, Any]],
        deadline: Optional[_AccountDeadline] = None,
    ) -> List[Dict[str, Any]]:
        if deadline is not None and deadline.started_at is not None:
            end = deadline.finished_at or self._clock()
            context.processing_time_seconds = max(end - deadline.started_at, 0.0)
        if deadline is not None:
            context.coverage = list(deadline.coverage)
            if deadline.unfinished_listings:
                # Discovery stopped at its share of the account's time limit:
                # keep what it found, but the account is incomplete.
                return self._record_account_failure(
                    account_id,
                    context,
                    AccountTimeoutError(
                        deadline.message(len(resources))
                        + f" ({deadline.unfinished_listings} service/region "
                        "listing(s) did not finish)",
                        partial_resources=resources,
                    ),
                    deadline,
                )
        context.resource_count = len(resources)
        context.discovered_services = list(set(r.get("service", "") for r in resources))
        self._processing_stats["successful_accounts"] += 1
        self.logger.info(
            f"Successfully discovered {len(resources)} resources from account "
            f"{account_id} in {context.processing_time_seconds:.2f}s"
        )
        self._save_checkpoint(account_id, context, resources)
        return resources

    def _record_account_failure(
        self,
        account_id: str,
        context: AccountContext,
        error: Exception,
        deadline: Optional[_AccountDeadline] = None,
    ) -> List[Dict[str, Any]]:
        """Record a failed account (main thread only).

        Returns the resources to keep: what a timed-out account found before
        its limit (the account still counts as failed), else nothing.
        """
        partial = getattr(error, "partial_resources", None) or []
        if deadline is not None:
            context.coverage = list(deadline.coverage)
        self.logger.error(
            f"Resource discovery failed for account {account_id}: {error}"
        )
        self._processing_stats["failed_accounts"] += 1
        context.processing_errors.append(f"Resource discovery failed: {error}")
        if partial:
            context.partial = True
            context.resource_count = len(partial)
            context.discovered_services = list(
                set(r.get("service", "") for r in partial)
            )
        return list(partial)

    def _grace(self, deadline: _AccountDeadline) -> float:
        if self._abandon_grace_seconds is not None:
            return self._abandon_grace_seconds
        return min(30.0, 0.1 * float(deadline.timeout_seconds))

    def _scan_account(
        self,
        account_id: str,
        context: AccountContext,
        deadline: Optional[_AccountDeadline] = None,
    ) -> List[Dict[str, Any]]:
        """Scan one account within its time limit. Writes nothing into
        ``context``: the caller records the result.

        Raises :class:`AccountTimeoutError` if the account ran out of time;
        what it found before the limit is in the error's ``partial_resources``.
        """
        deadline = deadline or self._new_deadline(account_id)
        deadline.start()
        deadline.attach(context.session)
        self._attach_limiter(context.session, account_id, deadline)
        unbound = _bound_cost_explorer(
            context.session, _cost_explorer_config(deadline.timeout_seconds)
        )
        try:
            with account_log_context(account_id, context.credentials.account_name):
                self._scan_local.deadline = deadline
                resources = self._discover_account_resources_inner(account_id, context)
        except AccountTimeoutError:
            deadline.expired = True
            resources = None
        finally:
            self._scan_local.deadline = None
            unbound()
            deadline.detach(context.session)
        if deadline.expired:
            raise AccountTimeoutError(
                deadline.message(len(resources) if resources else None),
                partial_resources=resources,
            )
        return resources

    def stop(self) -> None:
        """Stop this run (SIGTERM, Ctrl-C): the limiter starts no new AWS
        request, and running scans start no new detail call."""
        self.limiter.stop()
        with self._engines_lock:
            engines = list(self._running_engines)
        for engine in engines:
            engine.stop_detail_calls()

    def request_stop(self) -> None:
        """Lock-free form of :meth:`stop` (SIGTERM): the limiter refuses new
        requests; an engine that offers a lock-free stop of its detail calls
        (``request_detail_stop``) is asked for it."""
        self.limiter.request_stop()
        for engine in _snapshot(self._running_engines):
            request = getattr(engine, "request_detail_stop", None)
            if callable(request):
                request()

    def _track_engine(self, engine, deadline) -> bool:
        """Make ``engine``'s detail calls stop when the account is abandoned
        or the run is stopped. False when the engine has none to stop."""
        stop = getattr(engine, "stop_detail_calls", None)
        if not callable(stop):
            return False
        with self._engines_lock:
            self._running_engines.add(engine)
        if deadline is not None:
            deadline.on_abandon(stop)
        if self.limiter.stopped:
            stop()
        return True

    def _untrack_engine(self, engine, deadline) -> None:
        with self._engines_lock:
            self._running_engines.discard(engine)
        if deadline is not None:
            deadline.forget_on_abandon(engine.stop_detail_calls)

    def _attach_limiter(self, session, account_id: str, deadline) -> None:
        """Put the run's limiter on an account's session, after the read-only
        guard (installed on every client) and the account's deadline, then
        turn the session's client cache on. Clients copy the session's
        handlers when they are created, so this comes before discovery
        creates any. The limiter stays on the session after the scan (the
        analyses use it too); the deadline it waits on ends with the scan.
        The cache is emptied first: a client cached by an earlier scan of
        this session carries that scan's deadline (library use)."""
        if getattr(session, "events", None) is None:
            return
        account = str(account_id)
        # A second scan of the account (library use) gets its new deadline.
        self.limiter.detach(session, account)
        self.limiter.attach(session, account, deadline)
        reset_client_cache(session)
        enable_client_cache(session)

    def _discover_account_resources(
        self, account_id: str, context: AccountContext
    ) -> List[Dict[str, Any]]:
        """Scan one account within its time limit and record the result in
        ``context`` (success statistics only; failures are raised)."""
        deadline = self._new_deadline(account_id)
        resources = self._scan_account(account_id, context, deadline)
        return self._record_account_success(account_id, context, resources, deadline)

    @staticmethod
    def _coverage_entries(inventory, account_id: str) -> List[Dict[str, Any]]:
        """The discovery coverage ledger as a list of dicts (empty if none)."""
        ledger = getattr(inventory, "coverage", None)
        to_dict = getattr(ledger, "to_dict", None)
        if not callable(to_dict):
            return []
        try:
            entries = to_dict()
        except Exception:
            return []
        if not isinstance(entries, list):
            return []
        out = []
        for entry in entries:
            if isinstance(entry, dict):
                entry = dict(entry)
                if not entry.get("account_id"):
                    entry["account_id"] = str(account_id)
                out.append(entry)
        return out

    @staticmethod
    def _discovery_time_limit(deadline: Optional[_AccountDeadline]) -> float:
        """Seconds the service listings of an account may take.

        The per-account limit (``--account-processing-timeout``) is the one
        that applies. Discovery's own listing phase gets the time left minus
        a margin (20% of the limit, at most 300 s) for the steps that follow
        it (tags, details, billing), so that it stops by itself and keeps what
        it found instead of being cut off by the outer deadline.
        """
        if deadline is None:
            return 600.0
        limit = float(deadline.timeout_seconds)
        margin = min(300.0, 0.2 * limit)
        return max(deadline.remaining() - margin, 1.0)

    def _discover_account_resources_inner(
        self, account_id: str, context: AccountContext
    ) -> List[Dict[str, Any]]:
        """Discover one account's resources (no recording in ``context``).

        The account's deadline (set by :meth:`_scan_account` for this thread)
        decides discovery's own time limit and receives the coverage ledger.
        """
        deadline = getattr(self._scan_local, "deadline", None)
        regions_to_use = context.accessible_regions
        if not regions_to_use and not context.credentials.regions:
            regions_to_use, source = discover_regions(context.session, self.logger)
            self.logger.info(
                f"Auto-discovered {len(regions_to_use)} regions for account "
                f"{account_id} (from {source})"
            )
        elif not regions_to_use:
            regions_to_use = context.credentials.regions

        # Initialize resource inventory for this account
        inventory = AWSResourceInventory(
            session=context.session,
            regions=regions_to_use,
            services=context.credentials.services or None,  # None means all services
            tag_filters=context.credentials.tags,
            enable_billing_validation=self.config.enable_billing_validation,
            fallback_display_mode=self.config.fallback_display_mode,
            discovery_timeout=self._discovery_time_limit(deadline),
        )

        # The account was resolved when its context was made; discovery's
        # own lookup ran once per region thread, racing (A-70). Hand it over
        # (an inventory test double may have no engine).
        engine = getattr(inventory, "comprehensive_discovery", None)
        known_account = str((context.caller_identity or {}).get("Account") or "")
        if engine is not None and is_valid_account_id(known_account):
            engine._cached_account_id = known_account

        # Discover resources. Secret values that some read calls return
        # (Lambda environment variables, passwords in Describe output ...)
        # are removed here, before any report, snapshot or log sees them.
        # This is the second line: discovery already applied the same
        # deny-list (inventag.security.secret_values) at the source.
        tracked = engine is not None and self._track_engine(engine, deadline)
        try:
            found = inventory.discover_all_resources()
        finally:
            if tracked:
                self._untrack_engine(engine, deadline)
        resources = [mask_secret_values(resource) for resource in found]
        if deadline is not None:
            entries = self._coverage_entries(inventory, account_id)
            deadline.coverage = entries
            deadline.unfinished_listings = sum(
                1 for e in entries if e.get("outcome") == "timeout"
            )

        # Add account context to each resource
        # Use the account_id from credentials (which may have been updated from "default" to actual account ID)
        actual_account_id = context.credentials.account_id
        for resource in resources:
            resource["source_account_id"] = actual_account_id
            resource["source_account_name"] = context.credentials.account_name
            resource["discovery_timestamp"] = datetime.now(timezone.utc).isoformat()

        return resources

    def _consolidate_account_resources(
        self, all_resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Consolidate resources from multiple accounts into unified format."""
        self.logger.info(
            f"Consolidating {len(all_resources)} resources from multiple accounts"
        )

        # Group resources by account for analysis
        resources_by_account = {}
        for resource in all_resources:
            account_id = resource.get("source_account_id", "unknown")
            if account_id not in resources_by_account:
                resources_by_account[account_id] = []
            resources_by_account[account_id].append(resource)

        # Log consolidation statistics
        for account_id, resources in resources_by_account.items():
            account_name = (
                resources[0].get("source_account_name", "Unknown")
                if resources
                else "Unknown"
            )
            self.logger.info(
                f"Account {account_id} ({account_name}): {len(resources)} resources"
            )

        # Add consolidation metadata
        for resource in all_resources:
            resource["consolidation_timestamp"] = datetime.now(timezone.utc).isoformat()
            resource["total_accounts_in_consolidation"] = len(resources_by_account)

        self.consolidated_resources = all_resources
        return all_resources

    def _run_compliance_analysis(
        self, resources: List[Dict[str, Any]], compliance_policies: Dict
    ) -> Dict[str, Any]:
        """Run compliance analysis across all consolidated resources."""
        self.logger.info("Running compliance analysis across consolidated resources")

        try:
            # Use the first available session for compliance checking
            session = None
            for context in self.account_contexts.values():
                if context.session:
                    session = context.session
                    break

            if not session:
                raise Exception("No valid session available for compliance analysis")

            # Initialize compliance checker
            # The regions are passed so that the checker makes no AWS call:
            # it checks the resources it is given, it does not discover.
            regions = sorted(
                {
                    region
                    for ctx in self.account_contexts.values()
                    for region in ctx.accessible_regions
                }
            ) or ["us-east-1"]
            compliance_checker = ComprehensiveTagComplianceChecker(
                regions=regions, session=session, policy=compliance_policies
            )

            # Run compliance analysis
            compliance_results = compliance_checker.check_compliance(resources)

            # Add multi-account context to results
            compliance_results["multi_account_analysis"] = {
                "total_accounts": len(self.account_contexts),
                "accounts_analyzed": [
                    {
                        "account_id": acc_id,
                        "account_name": ctx.credentials.account_name,
                        "resource_count": ctx.resource_count,
                    }
                    for acc_id, ctx in self.account_contexts.items()
                ],
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            return compliance_results

        except Exception as e:
            self.logger.error(f"Compliance analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _generate_bom_documents(
        self,
        resources: List[Dict[str, Any]],
        compliance_results: Dict[str, Any],
        output_formats: List[str],
    ) -> Dict[str, Any]:
        """Generate BOM documents from consolidated resources."""
        self.logger.info(f"Generating BOM documents in formats: {output_formats}")

        try:
            # Use the first available session for BOM generation
            session = None
            for context in self.account_contexts.values():
                if context.session:
                    session = context.session
                    break

            if not session:
                raise Exception("No valid session available for BOM generation")

            # Initialize BOM processor
            # Every account's own session for the consolidated Network and
            # Security sheets (A-71).
            account_sessions = {
                str(acc_id): ctx.session
                for acc_id, ctx in self.account_contexts.items()
                if ctx.session is not None
            }
            bom_processor = BOMDataProcessor(
                config=self.config.bom_processing_config,
                session=session,
                account_sessions=account_sessions,
            )

            # Process inventory data into BOM format
            bom_data = bom_processor.process_inventory_data(resources)
            self._collect_run_denials(bom_processor)

            # Add multi-account metadata
            bom_data.generation_metadata.update(
                {
                    "multi_account_generation": True,
                    "total_accounts": len(self.account_contexts),
                    "successful_accounts": self._processing_stats[
                        "successful_accounts"
                    ],
                    "failed_accounts": self._processing_stats["failed_accounts"],
                    "account_summary": [
                        {
                            "account_id": acc_id,
                            "account_name": ctx.credentials.account_name,
                            "resource_count": ctx.resource_count,
                            "processing_time_seconds": ctx.processing_time_seconds,
                            "error_count": len(ctx.processing_errors),
                            "partial": getattr(ctx, "partial", False) is True,
                        }
                        for acc_id, ctx in self.account_contexts.items()
                    ],
                    # What discovery attempted and how each listing ended, for
                    # a Coverage sheet and for scripts (JSON output). Each row
                    # of a resource also says which API returned it ("source").
                    "coverage_summary": self._coverage_summary(),
                    "coverage": [
                        entry
                        for ctx in self.account_contexts.values()
                        for entry in _coverage_of(ctx)
                    ],
                }
            )

            permissions = self._permissions_denied()
            if permissions:
                bom_data.generation_metadata["permissions_denied"] = permissions
            if self._finops_result is not None:
                bom_data.generation_metadata["finops_checks"] = self._finops_result
            if self._finops_costs is not None:
                bom_data.generation_metadata["finops_costs"] = self._finops_costs

            # Add compliance results to BOM data
            if compliance_results:
                bom_data.compliance_summary = compliance_results

            # Initialize BOM converter
            bom_converter = BOMConverter(session=session)
            processing_config = self.config.bom_processing_config
            bom_converter.analyze_network = bool(
                getattr(processing_config, "enable_network_analysis", False)
            )
            bom_converter.analyze_security = bool(
                getattr(processing_config, "enable_security_analysis", False)
            )

            # Generate documents in requested formats
            generated_files = []
            format_errors = []
            google_urls: List[Dict[str, str]] = []
            notes = self._run_notes()
            # The processor's network analysis may have left out the
            # ElastiCache counts of a region (A-59); its sheet says so.
            analyzer = getattr(bom_processor, "network_analyzer", None)
            bom_converter.run_notes = notes + (
                analyzer.cache_group_notes() if analyzer is not None else []
            )
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for prefix, label, scope_data in self._report_scopes(bom_data):
                if label is None:
                    converter = bom_converter
                else:
                    # The account's own session reads its Network and Security
                    # sheets (A-58); the first session is only the fallback.
                    account = self.account_contexts.get(label)
                    converter = BOMConverter(
                        session=(account.session if account else None) or session
                    )
                    converter.analyze_network = bom_converter.analyze_network
                    converter.analyze_security = bom_converter.analyze_security
                    converter.run_notes = notes
                for format_type in output_formats:
                    fmt = format_type.lower()
                    try:
                        if fmt == "excel":
                            output_file = self.output_dir / f"{prefix}_{stamp}.xlsx"
                            converter.generate_excel_bom(
                                scope_data,
                                str(output_file),
                                template=self.config.excel_template,
                            )
                            generated_files.append(str(output_file))

                        elif fmt == "word":
                            output_file = self.output_dir / f"{prefix}_{stamp}.docx"
                            converter.generate_word_bom(
                                scope_data,
                                str(output_file),
                                template=self.config.word_template,
                            )
                            generated_files.append(str(output_file))

                        elif fmt == "csv":
                            output_file = self.output_dir / f"{prefix}_{stamp}.csv"
                            converter.generate_csv_bom(scope_data, str(output_file))
                            generated_files.append(str(output_file))

                        elif fmt == "json":
                            output_file = self.output_dir / f"{prefix}_{stamp}.json"
                            document = {
                                "resources": scope_data.resources,
                                "metadata": scope_data.generation_metadata,
                                "compliance_summary": scope_data.compliance_summary,
                                "network_analysis": scope_data.network_analysis,
                                "security_analysis": scope_data.security_analysis,
                            }

                            def write_json(temp_path, document=document):
                                with open(temp_path, "w") as f:
                                    json.dump(document, f, indent=2, default=str)

                            # Whole or not at all; an older file stays (A-14).
                            save_atomically(output_file, write_json)
                            generated_files.append(str(output_file))

                        elif fmt == "google":
                            if scope_data.resources:
                                google_urls.append(
                                    self._publish_to_google(
                                        converter, scope_data, label
                                    )
                                )

                    except Exception as e:
                        self.logger.error(
                            f"Failed to generate {format_type} format: {e}"
                        )
                        format_errors.append(f"{format_type}: {e}")

            # Exporters write nothing when there is no data; only report files
            # that exist (the S3 upload step reads this list).
            generated_files = [path for path in generated_files if os.path.isfile(path)]

            if not resources:
                if self._accounts_that_read_nothing() or (
                    self._accounts_with_expired_session()
                ):
                    self.logger.warning(
                        "No resources to report: nothing could be read (see the "
                        "messages above). No report file was written."
                    )
                elif self._filter_texts():
                    filters = self._filter_texts()
                    self.logger.warning(
                        "No resources to report: none found with "
                        f"{' and '.join(filters)} (from the command line or the "
                        "accounts file). No report file was written; run without "
                        f"{'that filter' if len(filters) == 1 else 'those filters'} "
                        "to see every resource."
                    )
                else:
                    self.logger.warning(
                        "No resources to report (none found, or the filters "
                        "removed all of them). No report file was written."
                    )

            if format_errors:
                # A requested report that could not be written is a failed run.
                return {
                    "success": False,
                    "error": "Could not write: " + "; ".join(format_errors),
                    "generated_files": generated_files,
                    "google": google_urls,
                    "total_resources": len(resources),
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }

            security = getattr(bom_data, "security_analysis", None)
            if not isinstance(security, dict):
                security = {}
            return {
                "success": True,
                "generated_files": generated_files,
                "google": google_urls,
                "security_risk_findings": [
                    {
                        "group_id": rule.get("group_id", ""),
                        "rule": rule.get("rule", ""),
                        "risk_level": rule.get("risk_level", ""),
                    }
                    for rule in (security.get("overly_permissive_rules") or [])
                    if isinstance(rule, dict)
                ],
                "total_resources": len(resources),
                "processing_statistics": bom_data.processing_statistics,
                "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            self.logger.error(f"BOM document generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _report_scopes(self, bom_data) -> List[tuple]:
        """(file prefix, account label, data) for each report to write.

        One consolidated report by default. With ``--per-account-reports``, one
        report for each account that has resources.
        """
        if not self.config.generate_per_account_reports:
            return [("multi_account_bom", None, bom_data)]
        by_account: Dict[str, List[Dict[str, Any]]] = {}
        for resource in bom_data.resources:
            by_account.setdefault(
                str(resource.get("source_account_id") or "unknown"), []
            ).append(resource)
        scopes = []
        for account_id, rows in sorted(by_account.items()):
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", account_id)
            scope = dataclasses.replace(bom_data, resources=rows)
            if getattr(self, "_finops_result", None) is not None:
                # Each account's report shows only that account's findings.
                scope.generation_metadata = {
                    **bom_data.generation_metadata,
                    "finops_checks": self._finops_by_account.get(account_id)
                    or self._finops_by_account.get(""),
                }
            costs = getattr(self, "_finops_costs", None)
            if costs is not None:
                # Each account's report shows only that account's tables.
                scope.generation_metadata = {
                    **scope.generation_metadata,
                    "finops_costs": cost_allocation.for_account(costs, account_id),
                }
            scopes.append((f"{safe}_bom", account_id, scope))
        return scopes

    def _read_cost_allocation(self) -> Dict[str, Any]:
        """``--finops-cost-allocation``: each scanned account's tables, read
        with that account's own session (never the first account's, A-80),
        in account order. A failure is kept as that account's tables; the
        run goes on."""
        started = self._processing_stats.get("processing_start_time")
        failed = {str(item["account_id"]) for item in self._failed_accounts()}
        accounts = []
        for account_id in sorted(self.account_contexts, key=str):
            ctx = self.account_contexts[account_id]
            if str(account_id) in failed or getattr(ctx, "session", None) is None:
                continue
            try:
                accounts.append(
                    cost_allocation.read_for_session(
                        ctx.session,
                        str(account_id),
                        list(getattr(ctx, "accessible_regions", None) or []),
                        started,
                    )
                )
            except Exception as error:  # the scan's result is kept
                self.logger.warning(
                    f"Cost allocation could not be read in account {account_id} "
                    f"({type(error).__name__}). Run with --debug for the detail."
                )
                self.logger.debug("Cost allocation failure", exc_info=error)
                accounts.append(
                    cost_allocation.failed_account(str(account_id), started, error)
                )
        return cost_allocation.result(accounts)

    def _run_finops_checks(self, resources: List[Dict[str, Any]]) -> Optional[Dict]:
        """FIN-001 to FIN-006 on the consolidated rows (``--finops-checks``).

        No AWS call: the checks read the rows, the listings not read and the
        run's start time. None when the flag is off.
        """
        if not self.config.finops_checks:
            return None
        # Never the clock: without a start time FIN-003 is not evaluated.
        started = self._processing_stats.get("processing_start_time")
        units = self._units_not_read()
        self._finops_result = finops_checks.run_checks(resources, units, started)
        if self.config.generate_per_account_reports:
            # One result per account for its own report ("" = no rows).
            by_account: Dict[str, List[Dict[str, Any]]] = {"": []}
            for row in resources:
                key = str(row.get("source_account_id") or "unknown")
                by_account.setdefault(key, []).append(row)
            self._finops_by_account = {
                account: finops_checks.run_checks(
                    rows,
                    [u for u in units if account and u.get("account") == account],
                    started,
                )
                for account, rows in by_account.items()
            }
        return self._finops_result

    def _publish_to_google(self, converter, scope_data, label) -> Dict[str, str]:
        """Create the Google Sheet and/or Doc for one report."""
        from ..reporting import google_output

        options = self.config.google_options
        if options is None:
            raise google_output.GoogleOutputError("No Google options were given.")
        if label is not None:
            options = dataclasses.replace(
                options, title=f"{options.resolved_title()} - {label}"
            )
        urls = google_output.publish(
            converter,
            scope_data,
            options,
            sheets_template=self.config.excel_template,
            docs_template=self.config.word_template,
        )
        if label is not None:
            urls["account_id"] = label
        return urls

    def _generate_state_artifacts(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate state management artifacts for change tracking."""
        if not self.config.enable_state_management:
            return {}

        self.logger.info("Generating state management artifacts")

        try:
            # Initialize state manager
            state_manager = StateManager(
                state_dir=str(self.output_dir / "state"),
                retention_days=self.config.state_retention_days,
                max_snapshots=self.config.state_max_snapshots,
            )

            # Save current state
            # Sorted: the order must not follow the hash seed (plan 2.4).
            all_regions = sorted(
                set(
                    region
                    for ctx in self.account_contexts.values()
                    for region in ctx.accessible_regions
                )
            )
            primary_account = next(iter(self.account_contexts.keys()), "multi-account")
            failed_ids = {item["account_id"] for item in self._failed_accounts()}
            # An account that read nothing, or whose session expired during
            # the scan, is not a baseline: it is left out of the comparison
            # like a failed one.
            incomplete = set(self._accounts_that_read_nothing())
            incomplete |= set(self._accounts_with_expired_session())
            failed_ids |= incomplete
            if (
                incomplete
                and not resources
                and set(self.account_contexts) <= failed_ids
            ):
                self.logger.warning(
                    "No state snapshot was saved: nothing was read in this run. "
                    "The next change report compares with the last saved one."
                )
                return {"state_saved": False, "reason": "nothing was read"}

            snapshot_tags = {
                "multi_account": True,
                "total_accounts": len(self.account_contexts),
                "generation_type": "multi_account_bom",
                "reused_accounts": dict(self.reused_accounts),
                # Listing outcomes per account (ok, empty, denied,
                # throttled, error, timeout): how complete the snapshot is.
                "coverage_summary": self._coverage_summary(),
            }
            # The units this run did not read (decision 6, additive key): the
            # next change report does not call their resources "added" (A-05,
            # A-68). Only when there are any, so a clean snapshot is as before.
            units = self._units_not_read()
            if units:
                snapshot_tags["units_not_read"] = units
            # The units whose detail calls failed (A-78, additive key): the
            # next change report does not compare the fields they add.
            details = self._details_not_read()
            if details:
                snapshot_tags["details_not_read"] = details
            # --finops-cost-allocation (additive key): the tables only, no
            # resource IDs; left out with --no-cost-in-snapshot.
            if self._finops_costs is not None and self.config.cost_in_snapshot:
                snapshot_tags["cost_allocation"] = cost_allocation.snapshot_totals(
                    self._finops_costs
                )

            state_id = state_manager.save_state(
                resources=resources,
                account_id=primary_account,
                regions=all_regions,
                discovery_method="multi-account",
                tags=snapshot_tags,
                # Accounts that failed (or were only partly scanned) are left
                # out of the next comparison instead of showing every resource
                # in them as removed.
                accounts_scanned=sorted(
                    acc_id
                    for acc_id in self.account_contexts
                    if acc_id not in failed_ids
                ),
                accounts_failed=sorted(failed_ids),
            )

            results = {
                "state_saved": True,
                "state_id": state_id,
                "state_directory": str(self.output_dir / "state"),
            }
            # The snapshot is saved, but the index that lists it is not: the
            # next run may compare with an older snapshot (A-18).
            index_error = getattr(state_manager, "last_index_error", None)
            if index_error:
                results["state_index_error"] = index_error

            # Generate delta detection if enabled
            if self.config.enable_delta_detection:
                try:
                    delta_detector = DeltaDetector()
                    # The newest earlier snapshot that can be read; corrupt
                    # or newer-format ones are skipped with a warning.
                    previous_state_id, problems = state_manager.find_previous_state(
                        state_id
                    )
                    for problem in problems:
                        self.logger.warning(f"Skipped unreadable snapshot {problem}")

                    if previous_state_id is not None:
                        # The current run's scope (A-05): what this run did
                        # not read is not compared instead of removed.
                        delta_results = delta_detector.detect_changes_by_state_id(
                            state_manager,
                            previous_state_id,
                            state_id,
                            current_run=self._delta_scope(),
                        )
                        summary = getattr(delta_results, "summary", None) or {}
                        changed = sum(
                            int(summary.get(key, 0) or 0)
                            for key in (
                                "added_count",
                                "removed_count",
                                "modified_count",
                            )
                        )

                        results["delta_detection"] = {
                            "changes_detected": changed > 0,
                            "previous_state_id": previous_state_id,
                            "current_state_id": state_id,
                            "summary": delta_results,
                        }

                        # Generate changelog if enabled
                        if self.config.enable_changelog_generation:
                            changelog_generator = ChangelogGenerator(
                                output_dir=str(self.output_dir / "changelogs")
                            )
                            changelog_file = (
                                self.output_dir
                                / f"changelog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                            )

                            changelog = changelog_generator.generate_changelog(
                                delta_results,
                                title="Multi-Account Infrastructure Changes",
                            )

                            # Write changelog to file: whole or not at all (A-14)
                            cost_lines = self._cost_change_lines(
                                state_manager, previous_state_id, snapshot_tags
                            )

                            def write_changelog(
                                temp_path, changelog=changelog, cost_lines=cost_lines
                            ):
                                text = changelog.to_markdown()
                                if cost_lines:
                                    text = text + "\n" + "\n".join(cost_lines)
                                with open(temp_path, "w") as f:
                                    f.write(text)

                            save_atomically(changelog_file, write_changelog)

                            results["changelog_generated"] = True
                            results["changelog_file"] = str(changelog_file)
                    else:
                        results["delta_detection"] = {
                            "changes_detected": False,
                            "reason": "No previous state available for comparison",
                        }

                except Exception as e:
                    self.logger.warning(f"Delta detection failed: {e}")
                    results["delta_detection"] = {
                        "changes_detected": False,
                        "error": str(e),
                    }

            return results

        except Exception as e:
            self.logger.error(f"State artifact generation failed: {e}")
            return {"state_saved": False, "error": str(e)}

    def _cost_change_lines(self, state_manager, previous_state_id, tags) -> List[str]:
        """The cost block of the change report (only with --finops-cost-allocation)."""
        if self._finops_costs is None:
            return []
        previous = None
        try:
            snapshot = state_manager.load_state(previous_state_id)
            previous_tags = getattr(snapshot.metadata, "tags", None) or {}
            previous = previous_tags.get("cost_allocation")
        except Exception:  # silent-ok: the block then says the previous has none
            previous = None
        return cost_allocation.change_lines(
            previous,
            tags.get("cost_allocation"),
            opted_out=not self.config.cost_in_snapshot,
        )

    @classmethod
    def from_credentials_file(
        cls, credentials_file: str, **kwargs
    ) -> "CloudBOMGenerator":
        """Create CloudBOMGenerator from a credentials file."""
        credentials_path = Path(credentials_file)

        if not credentials_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {credentials_file}")

        # Load credentials based on file extension
        if credentials_path.suffix.lower() in [".yaml", ".yml"]:
            with open(credentials_path, "r") as f:
                data = yaml.safe_load(f)
        elif credentials_path.suffix.lower() == ".json":
            with open(credentials_path, "r") as f:
                data = json.load(f)
        else:
            raise ValueError(
                f"Unsupported credentials file format: {credentials_path.suffix}"
            )

        # Parse accounts
        accounts = []
        for account_data in data.get("accounts", []):
            accounts.append(AccountCredentials(**account_data))

        # Create config
        config_data = data.get("config", {})
        config_data.update(kwargs)
        config_data["accounts"] = accounts

        config = MultiAccountConfig(**config_data)

        return cls(config)

    @classmethod
    def from_interactive_prompt(cls, **kwargs) -> "CloudBOMGenerator":
        """Create CloudBOMGenerator from interactive credential prompts."""
        print("InvenTag Multi-Account BOM Generator Setup")
        print("=" * 50)

        accounts = []

        while True:
            print(f"\nConfiguring Account #{len(accounts) + 1}")
            print("-" * 30)

            account_id = input("Account ID: ").strip()
            if not account_id:
                break

            account_name = input("Account Name (optional): ").strip()

            # Authentication method
            print("\nAuthentication method:")
            print("1. AWS Profile")
            print("2. Access Keys")
            print("3. Role ARN")
            print("4. Cross-account role (will use configured role name)")

            auth_method = input("Select method (1-4): ").strip()

            credentials = AccountCredentials(
                account_id=account_id,
                account_name=account_name or f"Account-{account_id}",
            )

            if auth_method == "1":
                credentials.profile_name = input("AWS Profile Name: ").strip()
            elif auth_method == "2":
                credentials.access_key_id = input("Access Key ID: ").strip()
                credentials.secret_access_key = getpass.getpass("Secret Access Key: ")
                session_token = getpass.getpass("Session Token (optional): ")
                if session_token:
                    credentials.session_token = session_token
            elif auth_method == "3":
                credentials.role_arn = input("Role ARN: ").strip()
                external_id = input("External ID (optional): ").strip()
                if external_id:
                    credentials.external_id = external_id
            # Method 4 uses default cross-account role

            # Regions
            regions_input = input(
                "Regions (comma-separated, empty for all regions): "
            ).strip()
            if regions_input:
                credentials.regions = [r.strip() for r in regions_input.split(",")]
            # If empty, regions will remain empty list and auto-discovery will happen later

            accounts.append(credentials)

            continue_prompt = input("\nAdd another account? (y/N): ").strip().lower()
            if continue_prompt not in ["y", "yes"]:
                break

        if not accounts:
            raise ValueError("No accounts configured")

        # Create config
        config = MultiAccountConfig(accounts=accounts, **kwargs)

        return cls(config)
