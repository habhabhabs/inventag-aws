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
import yaml
import getpass
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import threading
import time
from pathlib import Path
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
)

# Import InvenTag components
from ..discovery import AWSResourceInventory
from ..discovery.coverage import EMPTY, FAILED_OUTCOMES, OK
from ..discovery.regions import discover_regions
from .log_context import account_log_context
from ..compliance import ComprehensiveTagComplianceChecker
from ..reporting import BOMConverter, BOMDataProcessor, BOMProcessingConfig
from ..state import StateManager, DeltaDetector, ChangelogGenerator
from ..security.arn import (
    InvalidRoleError,
    build_role_arn,
    is_valid_account_id,
    partition_from_arn,
    validate_role_arn,
)
from ..security.redaction import register_secrets
from ..security.secret_values import mask_secret_values
from .._version import __version__

from ..state.partial_results import PartialResultStore, make_run_key
from ..security.safe_output import (
    ensure_private_dir,
    open_private,
)


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


def _expired_listings(context) -> int:
    """How many listings of an account failed because its session expired."""
    return sum(
        1
        for entry in _coverage_of(context)
        if str(entry.get("error_code", "")) in _EXPIRED_SESSION_CODES
    )


class AccountSessionError(Exception):
    """Raised when explicitly configured credentials for an account do not work."""


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
        """The main thread gave up on this account: refuse its further calls."""
        self.expired = True
        self.abandoned = True
        if self.abandoned_at is None:
            self.abandoned_at = time.monotonic()

    def attach(self, session) -> None:
        events = getattr(session, "events", None)
        if events is not None:
            events.register("before-call", self.before_call, unique_id=self.UNIQUE_ID)

    def detach(self, session) -> None:
        self.active = False
        self.finished_at = self._clock()
        events = getattr(session, "events", None)
        if events is not None:
            events.unregister("before-call", unique_id=self.UNIQUE_ID)


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


@dataclass
class MultiAccountConfig:
    """Configuration for multi-account BOM generation."""

    accounts: List[AccountCredentials] = field(default_factory=list)
    cross_account_role_name: str = "InvenTagCrossAccountRole"
    parallel_account_processing: bool = True
    max_concurrent_accounts: int = 4
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

        # Processing state
        self._processing_lock = threading.Lock()
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

        try:
            # Step 1: Validate and establish account contexts
            self.logger.info("Validating account credentials and establishing contexts")
            account_contexts = self._establish_account_contexts()
            self._checkpoints = self._open_checkpoints(account_contexts)

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

            for note in self._read_nothing_notes():
                self.logger.warning(note)

            # Step 3: Consolidate resources if configured
            if self.config.consolidate_accounts:
                self.logger.info("Consolidating resources from all accounts")
                consolidated_resources = self._consolidate_account_resources(
                    all_resources
                )
            else:
                consolidated_resources = all_resources

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

            self._finish_checkpoints()

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
                "bom_generation": bom_results,
                "compliance_analysis": compliance_results,
                "state_management": state_results,
                "output_directory": str(self.output_dir),
            }

            self.logger.info(
                f"Multi-account BOM generation completed successfully in {processing_time:.2f}s. "
                f"Processed {len(consolidated_resources)} resources across "
                f"{self._processing_stats['successful_accounts']} accounts"
            )

            return results

        except Exception as e:
            self.logger.error(f"Multi-account BOM generation failed: {e}")
            self._processing_stats["processing_end_time"] = datetime.now(timezone.utc)

            failure = {
                "success": False,
                "error": str(e),
                "failed_accounts": self._failed_accounts(),
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

        if s3_upload_config and results.get("success"):
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

        return results

    def upload_reports_to_s3(
        self, files: List[str], s3_upload_config: Any
    ) -> Dict[str, Any]:
        """Upload generated report files to S3 with server-side encryption.

        Uses the default credential chain (the identity running InvenTag), not
        a scanned account's assumed role: the reports bucket normally lives in
        the account that runs the scan.
        """
        from .s3_upload import upload_files

        if not files:
            return {"uploaded": [], "errors": [{"file": "", "error": "no files"}]}
        session = boto3.Session()
        s3_client = session.client(
            "s3", region_name=getattr(s3_upload_config, "region", None) or None
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

    def _accounts_that_read_nothing(self) -> List[str]:
        """Accounts in which no service-API listing succeeded and at least
        one was denied or failed (rows of the Tagging API alone do not
        count). Failed accounts are not included: they are reported as
        failed."""
        failed_ids = {item["account_id"] for item in self._failed_accounts()}
        accounts = []
        for acc_id, ctx in self.account_contexts.items():
            if acc_id in failed_ids:
                continue
            entries = _coverage_of(ctx)
            if any(
                e.get("source") == "service-api" and e.get("outcome") in (OK, EMPTY)
                for e in entries
            ):
                continue
            if any(e.get("outcome") in FAILED_OUTCOMES for e in entries):
                accounts.append(acc_id)
        return accounts

    def _read_nothing_notes(self) -> List[str]:
        return [
            f"Account {acc_id}: every service listing was denied or failed; "
            "nothing was read from its service APIs. It is left out of change "
            "tracking."
            for acc_id in self._accounts_that_read_nothing()
        ]

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
        notes.extend(self._read_nothing_notes())
        if self.reused_accounts:
            notes.append(
                f"{len(self.reused_accounts)} account(s) were not scanned again: "
                "their results come from an earlier run of the same command "
                "(--resume), scanned at:"
            )
            for account_id, scanned_at in sorted(self.reused_accounts.items()):
                notes.append(f"{account_id}: {scanned_at}")
        return notes

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

    def _establish_account_contexts(self) -> Dict[str, AccountContext]:
        """Validate credentials and establish account contexts."""
        account_contexts = {}

        for credentials in self.config.accounts:
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
                                    role_part = caller_arn.split("assumed-role/")[
                                        1
                                    ].split("/")[0]
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

                # Test accessible regions
                accessible_regions = self._test_accessible_regions(
                    session, target_regions
                )

                # Create account context
                context = AccountContext(
                    credentials=credentials,
                    session=session,
                    caller_identity=caller_identity,
                    accessible_regions=accessible_regions,
                )

                account_contexts[credentials.account_id] = context
                self.account_contexts[credentials.account_id] = context

                self.logger.info(
                    f"Successfully established context for account {credentials.account_id} "
                    f"({credentials.account_name}) with {len(accessible_regions)} accessible regions"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to establish context for account {credentials.account_id}: {e}"
                )
                # Create a failed context for tracking
                context = AccountContext(
                    credentials=credentials,
                    session=None,
                    caller_identity={},
                    processing_errors=[f"Context establishment failed: {e}"],
                )
                account_contexts[credentials.account_id] = context
                self.account_contexts[credentials.account_id] = context

        return account_contexts

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
                session = boto3.Session(profile_name=credentials.profile_name)
                self._sts(session).get_caller_identity()
                return session
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
                    f"Role assumption failed for account {credentials.account_id}: {e}"
                ) from e

        if credentials.access_key_id and credentials.secret_access_key:
            return boto3.Session(
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
            return boto3.Session()

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
            session = boto3.Session()
            self._sts(session).get_caller_identity()
            return session
        except Exception as e:
            raise AccountSessionError(
                f"Failed to create valid session for account {credentials.account_id}: {e}"
            ) from e

    def _assume_role_session(
        self, role_arn: str, account_id: str, external_id: Optional[str] = None
    ) -> boto3.Session:
        """Assume ``role_arn`` with the default credentials and return a session."""
        sts = self._sts(boto3.Session())
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
        return boto3.Session(
            aws_access_key_id=temp["AccessKeyId"],
            aws_secret_access_key=temp["SecretAccessKey"],
            aws_session_token=temp["SessionToken"],
        )

    def _sts(self, session):
        """STS client bounded by --credential-timeout (sign-in and role checks)."""
        timeout = self.config.credential_validation_timeout
        if not timeout:
            return session.client("sts")
        return session.client(
            "sts",
            config=BotoConfig(
                connect_timeout=timeout,
                read_timeout=timeout,
                retries={"max_attempts": 2},
            ),
        )

    def _default_caller_account(self) -> Optional[str]:
        """Account ID of the default credentials (looked up once per run)."""
        if not hasattr(self, "_default_caller_account_id"):
            try:
                self._default_caller_account_id = str(
                    self._sts(boto3.Session()).get_caller_identity()["Account"]
                )
            except Exception:
                self._default_caller_account_id = None
        return self._default_caller_account_id

    def _default_partition(self) -> str:
        """Partition (aws, aws-cn, aws-us-gov...) of the default credentials."""
        if self._default_identity is None:
            try:
                self._default_identity = self._sts(
                    boto3.Session()
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
            sts = session.client(
                "sts",
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
                else:
                    self.logger.warning(f"Region {region} test failed: {e}")
            except Exception as e:
                self.logger.warning(f"Region {region} test failed: {e}")

        if denied and not accessible_regions and len(denied) == len(target_regions):
            self.logger.warning(
                "ec2:DescribeRegions is denied in every region, so region access "
                f"cannot be checked; scanning all {len(denied)} regions."
            )
            return list(denied)
        return accessible_regions

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
        executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_accounts)
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
                        all_resources.extend(
                            self._record_account_failure(
                                account_id, context, e, deadlines[account_id]
                            )
                        )
                        continue
                    all_resources.extend(
                        self._record_account_success(
                            account_id, context, resources, deadlines[account_id]
                        )
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
        try:
            with account_log_context(account_id, context.credentials.account_name):
                self._scan_local.deadline = deadline
                resources = self._discover_account_resources_inner(account_id, context)
        except AccountTimeoutError:
            deadline.expired = True
            resources = None
        finally:
            self._scan_local.deadline = None
            deadline.detach(context.session)
        if deadline.expired:
            raise AccountTimeoutError(
                deadline.message(len(resources) if resources else None),
                partial_resources=resources,
            )
        return resources

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

        # Discover resources. Secret values that some read calls return
        # (Lambda environment variables, passwords in Describe output ...)
        # are removed here, before any report, snapshot or log sees them.
        # This is the second line: discovery already applied the same
        # deny-list (inventag.security.secret_values) at the source.
        resources = [
            mask_secret_values(resource)
            for resource in inventory.discover_all_resources()
        ]
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
            bom_processor = BOMDataProcessor(
                config=self.config.bom_processing_config, session=session
            )

            # Process inventory data into BOM format
            bom_data = bom_processor.process_inventory_data(resources)

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
            bom_converter.run_notes = notes
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for prefix, label, scope_data in self._report_scopes(bom_data):
                if label is None:
                    converter = bom_converter
                else:
                    converter = BOMConverter(session=session)
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
                            with open_private(output_file, "w") as f:
                                json.dump(
                                    {
                                        "resources": scope_data.resources,
                                        "metadata": scope_data.generation_metadata,
                                        "compliance_summary": scope_data.compliance_summary,
                                        "network_analysis": scope_data.network_analysis,
                                        "security_analysis": scope_data.security_analysis,
                                    },
                                    f,
                                    indent=2,
                                    default=str,
                                )
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
                self.logger.warning(
                    "No resources to report (none found, or the filters removed "
                    "all of them). No report file was written."
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
            scopes.append(
                (
                    f"{safe}_bom",
                    account_id,
                    dataclasses.replace(bom_data, resources=rows),
                )
            )
        return scopes

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
            all_regions = list(
                set(
                    region
                    for ctx in self.account_contexts.values()
                    for region in ctx.accessible_regions
                )
            )
            primary_account = next(iter(self.account_contexts.keys()), "multi-account")
            failed_ids = {item["account_id"] for item in self._failed_accounts()}
            # An account that read nothing is not a baseline: it is left out
            # of the comparison like a failed one.
            read_nothing = set(self._accounts_that_read_nothing())
            failed_ids |= read_nothing
            if (
                read_nothing
                and not resources
                and set(self.account_contexts) <= failed_ids
            ):
                self.logger.warning(
                    "No state snapshot was saved: nothing was read in this run. "
                    "The next change report compares with the last saved one."
                )
                return {"state_saved": False, "reason": "nothing was read"}

            state_id = state_manager.save_state(
                resources=resources,
                account_id=primary_account,
                regions=all_regions,
                discovery_method="multi-account",
                tags={
                    "multi_account": True,
                    "total_accounts": len(self.account_contexts),
                    "generation_type": "multi_account_bom",
                    "reused_accounts": dict(self.reused_accounts),
                    # Listing outcomes per account (ok, empty, denied,
                    # throttled, error, timeout): how complete the snapshot is.
                    "coverage_summary": self._coverage_summary(),
                },
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
                        delta_results = delta_detector.detect_changes_by_state_id(
                            state_manager, previous_state_id, state_id
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

                            # Write changelog to file
                            with open_private(changelog_file, "w") as f:
                                f.write(changelog.to_markdown())

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
