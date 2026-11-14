#!/usr/bin/env python3
"""
InvenTag CLI - Comprehensive Command Line Interface

Multi-account AWS cloud governance platform with BOM generation,
compliance checking, and advanced reporting capabilities.
"""

import argparse
import getpass
import re
import sys
import json
import yaml
import logging
import boto3
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError

# InvenTag imports
from ..core import (
    CloudBOMGenerator,
    MultiAccountConfig,
    AccountCredentials,
    CredentialManager,
)
from ..reporting import BOMProcessingConfig
from ..reporting.report_template import (
    FORMATS as TEMPLATE_FORMATS,
    TemplateValidationError,
    default_template_text,
    load_report_template,
)
from .config_validator import ConfigValidator
from .logging_setup import setup_logging, LoggingContext
from . import safety
from .._version import __version__
from ..security.arn import (
    InvalidRoleError,
    account_id_from_role_arn,
    is_role_arn,
    validate_role_arn,
    validate_role_name,
)
from ..reporting.settings_loader import (
    SettingsFileError,
    read_bom_settings,
    valid_bom_setting_names,
)
from ..templating.runner import (
    add_template_arguments,
    bom_result_is_empty,
    prepare_template_run,
)

# Exit code for a template file that is not valid (same code as other
# configuration files that are not valid).
EXIT_INVALID_TEMPLATE = 1

# Exit codes: the one list is inventag/exit_codes.py (0 success, 1 error,
# 2 invalid options, 3 tag policy violations, 4 risk threshold, and the
# opt-in 5 --fail-on-account-error and 6 --fail-if-empty).
from ..exit_codes import (  # noqa: E402
    EXIT_ACCOUNT_FAILED,
    EXIT_NO_RESOURCES,
    EXIT_RISK_THRESHOLD,
)


def _limit_or_none(text: str) -> Optional[int]:
    """argparse type: a whole number >= 0, or 'none'. 0 and 'none' mean no limit."""
    if str(text).strip().lower() == "none":
        return None
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a whole number or 'none', got {text!r}"
        )
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more, got {value}")
    return value or None


def _validate_specific_configs(args, logger, check_credentials=True):
    """Validate only the configuration files specified in CLI arguments."""
    validator = ConfigValidator()
    all_valid = True

    # Validate tag mappings if specified
    if args.tag_mappings:
        logger.info(f"Validating tag mappings: {args.tag_mappings}")
        result = validator.validate_tag_mappings_file(args.tag_mappings)
        if result.is_valid:
            logger.info("✅ Tag mappings configuration is valid")
        else:
            logger.error("❌ Tag mappings configuration is invalid:")
            for error in result.errors:
                logger.error(f"   - {error}")
            all_valid = False

    # Validate service descriptions if specified
    if args.service_descriptions:
        logger.info(f"Validating service descriptions: {args.service_descriptions}")
        result = validator.validate_service_descriptions_file(args.service_descriptions)
        if result.is_valid:
            logger.info("✅ Service descriptions configuration is valid")
        else:
            logger.error("❌ Service descriptions configuration is invalid:")
            for error in result.errors:
                logger.error(f"   - {error}")
            all_valid = False

    # Validate accounts file if specified
    if args.accounts_file:
        logger.info(f"Validating accounts file: {args.accounts_file}")
        result = validator.validate_accounts_file(args.accounts_file)
        if result.is_valid:
            logger.info("✅ Accounts configuration is valid")
        else:
            logger.error("❌ Accounts configuration is invalid:")
            for error in result.errors:
                logger.error(f"   - {error}")
            all_valid = False

    if all_valid:
        logger.info("🎉 All specified configuration files are valid!")

        # Also validate AWS credentials if not skipped
        if check_credentials and not args.skip_credential_validation:
            logger.info("🔐 Also checking AWS credentials...")
            if validate_aws_credentials_early(args.credential_timeout):
                logger.info("🎉 AWS credentials are also valid!")
            else:
                logger.error(
                    "❌ Configuration files are valid but AWS credentials have issues"
                )
                sys.exit(1)
    else:
        logger.error("❌ Some configuration files have validation errors")
        sys.exit(1)


def get_all_aws_regions(session: Optional[boto3.Session] = None) -> List[str]:
    """Get all available AWS regions with fallback."""
    try:
        session = session or boto3.Session()
        ec2 = session.client("ec2", region_name="us-east-1")
        regions = ec2.describe_regions()["Regions"]
        region_list = [region["RegionName"] for region in regions]
        logger = logging.getLogger(__name__)
        logger.info(f"Auto-discovered {len(region_list)} AWS regions")
        return region_list
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to auto-discover regions: {e}")
        logger.info("Falling back to default regions")
        # Common regions fallback
        return ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]


def create_parser() -> argparse.ArgumentParser:
    """Create comprehensive argument parser for InvenTag CLI."""

    parser = argparse.ArgumentParser(
        prog="inventag",
        description="InvenTag - Comprehensive AWS Cloud Governance Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate BOM for single account using default credentials
  inventag --create-excel --create-word

  # Multi-account BOM generation from file
  inventag --accounts-file accounts.json --create-excel --s3-bucket my-bucket

  # Interactive multi-account setup
  inventag --accounts-prompt --create-word --create-excel --verbose

  # Assume one role ARN (auto-discovers all regions)
  inventag --cross-account-role arn:aws:iam::123456789012:role/InvenTagReadOnly

  # Same role name in every account listed in accounts.json
  inventag --accounts-file accounts.json --cross-account-role InvenTagReadOnly

  # CI/CD integration with S3 upload
  inventag --accounts-file accounts.json --create-excel --s3-bucket reports-bucket --s3-key-prefix bom-reports/

  # Debug mode with comprehensive logging
  inventag --debug --log-file inventag-debug.log --create-excel

  # Validate AWS credentials only
  inventag --validate-credentials

  # Templates: list them, then use one (see 'inventag templates --help')
  inventag templates list
  inventag --template executive-summary --create-word

  # Or edit the report structure file directly
  inventag --print-default-template word > my_word_template.yaml
  inventag --create-word --word-template my_word_template.yaml
        """,
    )

    # Account specification options
    account_group = parser.add_argument_group("Account Configuration")
    account_group.add_argument(
        "--accounts-file",
        type=str,
        help="Path to accounts configuration file (JSON/YAML) containing account credentials and settings",
    )
    account_group.add_argument(
        "--accounts-prompt",
        action="store_true",
        help="Interactively prompt for account credentials and configuration",
    )
    account_group.add_argument(
        "--cross-account-role",
        type=str,
        help=(
            "Role to assume. A full role ARN is assumed directly. A role name "
            "(optionally with path) is combined with each account ID from "
            "--accounts-file into arn:<partition>:iam::<account>:role/<name>"
        ),
    )

    # Format-specific options
    format_group = parser.add_argument_group("Output Format Options")
    format_group.add_argument(
        "--create-word",
        action="store_true",
        help="Generate professional Word document BOM report",
    )
    format_group.add_argument(
        "--create-excel",
        action="store_true",
        help="Generate comprehensive Excel workbook BOM report",
    )
    format_group.add_argument(
        "--create-google-docs",
        action="store_true",
        help=(
            "Create the Word report as a Google Doc (needs the Google extra: "
            'pip install "inventag-aws[google]")'
        ),
    )
    format_group.add_argument(
        "--create-google-sheets",
        action="store_true",
        help="Create the Excel report as a Google Sheets spreadsheet",
    )

    google_group = parser.add_argument_group("Google Sheets and Docs Options")
    google_group.add_argument(
        "--google-credentials",
        type=str,
        metavar="SERVICE_ACCOUNT.json",
        help=(
            "Service-account key file. Without it, Application Default "
            "Credentials are used"
        ),
    )
    google_group.add_argument(
        "--google-oauth-client",
        type=str,
        metavar="CLIENT_SECRET.json",
        help="Sign in as yourself in the browser, with this OAuth client file",
    )
    google_group.add_argument(
        "--google-folder-id",
        type=str,
        help="Put the files in this Google Drive folder (it must be shared with the account)",
    )
    google_group.add_argument(
        "--google-share-with",
        action="append",
        default=[],
        metavar="EMAIL",
        help="Share the files with this person (repeat for more people)",
    )
    google_group.add_argument(
        "--google-share-role",
        choices=["reader", "commenter", "writer"],
        default="reader",
        help="Access for --google-share-with (default: reader)",
    )
    google_group.add_argument(
        "--google-share-anyone",
        action="store_true",
        help="Make the files readable by anyone with the link. Off by default",
    )
    google_group.add_argument(
        "--google-title",
        type=str,
        help="Title of the Google files (default: InvenTag AWS inventory <date>)",
    )

    # Analysis options
    analysis_group = parser.add_argument_group("Analysis Options")
    analysis_group.add_argument(
        "--enable-network-analysis",
        action="store_true",
        help="Enable network analysis for VPC, subnets, and network security",
    )
    analysis_group.add_argument(
        "--enable-security-analysis",
        action="store_true",
        help="Enable security analysis for security groups, NACLs, and security posture",
    )
    analysis_group.add_argument(
        "--enable-cost-analysis",
        action="store_true",
        help="Enable cost analysis and optimization recommendations",
    )
    analysis_group.add_argument(
        "--fallback-display",
        choices=["auto", "always", "never"],
        default="auto",
        help=(
            "Control fallback resource display: 'auto' shows fallback only when "
            "no primary resources found for a service (recommended), 'always' shows "
            "all fallback resources for maximum visibility, 'never' hides all fallback"
        ),
    )
    analysis_group.add_argument(
        "--hide-fallback-resources",
        action="store_true",
        help=(
            "Legacy option: equivalent to --fallback-display=never "
            "(deprecated, use --fallback-display instead)"
        ),
    )

    # S3 upload options for CI/CD
    s3_group = parser.add_argument_group("S3 Upload Options (CI/CD Integration)")
    s3_group.add_argument(
        "--s3-bucket",
        type=str,
        help=(
            "Upload generated reports to this S3 bucket (server-side encrypted, "
            "using the default AWS credentials; needs s3:PutObject). The run "
            "fails if any upload fails"
        ),
    )
    s3_group.add_argument(
        "--s3-key-prefix",
        type=str,
        help="S3 key prefix for organizing uploaded documents (default: bom-reports/)",
    )
    s3_group.add_argument(
        "--s3-encryption",
        choices=["AES256", "aws:kms"],
        default="AES256",
        help="S3 server-side encryption method (default: AES256)",
    )
    s3_group.add_argument(
        "--s3-kms-key-id",
        type=str,
        help=(
            "KMS key for --s3-encryption aws:kms (default: the AWS managed key "
            "aws/s3). Needs --s3-encryption aws:kms"
        ),
    )

    # Account-specific configuration overrides
    override_group = parser.add_argument_group(
        "Account-Specific Configuration Overrides"
    )
    override_group.add_argument(
        "--account-regions",
        type=str,
        help="Comma-separated list of AWS regions to scan (default: auto-discover all regions)",
    )
    override_group.add_argument(
        "--account-services",
        type=str,
        help="Comma-separated list of AWS services to keep in the report, "
        "matched against the Service column (for example EC2,S3,RDS). "
        "Empty means all services",
    )
    override_group.add_argument(
        "--billing-validation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Cost Explorer during discovery to find services that have "
        "spend (default: enabled). AWS charges for each Cost Explorer API "
        "request; use --no-billing-validation to make no Cost Explorer calls",
    )
    override_group.add_argument(
        "--account-tags",
        type=str,
        help="JSON string of tag filters to apply across all accounts",
    )

    # Parallel processing options
    parallel_group = parser.add_argument_group("Parallel Processing Options")
    parallel_group.add_argument(
        "--max-concurrent-accounts",
        type=int,
        default=4,
        help="Maximum number of accounts to process concurrently (default: 4)",
    )
    parallel_group.add_argument(
        "--account-processing-timeout",
        type=int,
        default=1800,
        help="Timeout in seconds for processing each account (default: 1800)",
    )
    parallel_group.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Reuse the saved results of accounts that finished in an earlier run "
            "of the same command that did not complete (same accounts, regions, "
            "services and filters), and scan only the others. Off by default"
        ),
    )
    parallel_group.add_argument(
        "--resume-max-age-hours",
        type=float,
        default=24.0,
        help="With --resume, reuse saved results only up to this age "
        "(default: 24, at most 168)",
    )
    parallel_group.add_argument(
        "--disable-parallel-processing",
        action="store_true",
        help="Disable parallel account processing (process accounts sequentially)",
    )

    # Configuration file options
    config_group = parser.add_argument_group("Configuration Files")
    config_group.add_argument(
        "--service-descriptions",
        type=str,
        help="Path to service descriptions configuration file (YAML/JSON)",
    )
    config_group.add_argument(
        "--tag-mappings",
        type=str,
        help="Path to tag mappings configuration file (YAML/JSON)",
    )
    config_group.add_argument(
        "--bom-config",
        type=str,
        help="Path to BOM processing configuration file (YAML/JSON)",
    )
    config_group.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate all configuration files and exit (no BOM generation)",
    )
    config_group.add_argument(
        "--validate-config-only",
        action="store_true",
        help="Only validate specific config files without running full validation",
    )

    # Report templates
    template_group = parser.add_argument_group("Report Templates")
    template_group.add_argument(
        "--word-template",
        type=str,
        metavar="PATH",
        help="Template file (YAML or JSON) for the Word report: title, "
        "sections, columns, header and footer. Needs --create-word",
    )
    template_group.add_argument(
        "--excel-template",
        type=str,
        metavar="PATH",
        help="Template file (YAML or JSON) for the Excel report: sheets, "
        "columns, header color, header and footer",
    )
    template_group.add_argument(
        "--print-default-template",
        choices=list(TEMPLATE_FORMATS),
        help="Print the default template for the given format and exit. "
        "Redirect the output to a file to start your own template",
    )
    template_group.add_argument(
        "--validate-templates",
        action="store_true",
        help="Validate the files given with --word-template and "
        "--excel-template and exit (no AWS call)",
    )

    # Output and state management
    output_group = parser.add_argument_group("Output and State Management")
    output_group.add_argument(
        "--output-directory",
        type=str,
        default="bom_output",
        help="Directory for output files (default: bom_output)",
    )
    output_group.add_argument(
        "--enable-state-management",
        action="store_true",
        default=True,
        help="Enable state management for change tracking (default: enabled)",
    )
    output_group.add_argument(
        "--disable-state-management",
        action="store_true",
        help="Disable state management and change tracking",
    )
    output_group.add_argument(
        "--enable-delta-detection",
        action="store_true",
        default=True,
        help="Enable delta detection for change analysis (default: enabled)",
    )
    output_group.add_argument(
        "--disable-delta-detection", action="store_true", help="Disable delta detection"
    )
    output_group.add_argument(
        "--generate-changelog",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate a changelog for detected changes (default: enabled; "
        "use --no-generate-changelog to turn it off)",
    )
    output_group.add_argument(
        "--state-retention-days",
        type=_limit_or_none,
        default=30,
        metavar="N",
        help="Delete state snapshots older than N days when a run saves a new "
        "one (default 30). Use 0 or none to keep snapshots of any age",
    )
    output_group.add_argument(
        "--state-max-snapshots",
        type=_limit_or_none,
        default=100,
        metavar="N",
        help="Keep only the newest N state snapshots (default 100). Use 0 or "
        "none to keep every snapshot",
    )
    output_group.add_argument(
        "--per-account-reports",
        action="store_true",
        help=(
            "Write one report for each account (<account-id>_bom_<time>.xlsx) "
            "instead of one consolidated report"
        ),
    )

    exit_group = parser.add_argument_group("Exit Codes (opt-in)")
    exit_group.add_argument(
        "--fail-on-account-error",
        action="store_true",
        help=(
            f"Exit with code {EXIT_ACCOUNT_FAILED} when any account could not be "
            "scanned (the reports are still written). Without it, such a run "
            "exits with 0 unless every account failed"
        ),
    )
    exit_group.add_argument(
        "--fail-if-empty",
        action="store_true",
        help=(
            f"Exit with code {EXIT_NO_RESOURCES} when no resources were found or "
            "the filters removed all of them. Without it, such a run exits with 0"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"inventag {__version__}",
        help="Show the InvenTag version and exit",
    )

    # Logging and debug options
    logging_group = parser.add_argument_group("Logging and Debug Options")
    logging_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (INFO level)",
    )
    logging_group.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging (DEBUG level) with detailed AWS API calls",
    )
    logging_group.add_argument(
        "--log-file", type=str, help="Path to log file for persistent logging"
    )
    logging_group.add_argument(
        "--disable-account-logging",
        action="store_true",
        help="Disable account-specific logging prefixes",
    )

    # Credential validation options
    cred_group = parser.add_argument_group("Credential Validation")
    cred_group.add_argument(
        "--validate-credentials",
        action="store_true",
        help="Validate all account credentials before processing and exit",
    )
    cred_group.add_argument(
        "--credential-timeout",
        type=int,
        default=30,
        help="Timeout in seconds for credential validation (default: 30)",
    )
    cred_group.add_argument(
        "--skip-credential-validation",
        action="store_true",
        help="Skip early AWS credential validation (not recommended)",
    )

    # Production Safety and Security options
    safety_group = parser.add_argument_group("Production Safety and Security")
    safety_group.add_argument(
        "--enable-production-safety",
        action="store_true",
        default=True,
        help="Accepted for compatibility; the read-only guard is always on",
    )
    safety_group.add_argument(
        "--disable-production-safety",
        action="store_true",
        help="Not supported: exits with an error (the read-only guard cannot be disabled)",
    )
    safety_group.add_argument(
        "--enforce-read-only",
        action="store_true",
        default=True,
        help=(
            "Block every AWS API call that is not read-only (always on): only "
            "List/Describe/Get/Head/Lookup/Search/BatchGet operations, minus "
            "calls that return secrets or data, are allowed"
        ),
    )
    safety_group.add_argument(
        "--security-validation",
        action="store_true",
        default=True,
        help="Accepted for compatibility; same as --enforce-read-only (always on)",
    )
    safety_group.add_argument(
        "--compliance-standard",
        choices=["general", "soc2", "pci", "hipaa", "gdpr"],
        default=None,
        help="Not implemented yet: exits with an error if given",
    )
    safety_group.add_argument(
        "--risk-threshold",
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        default=None,
        help=(
            "Exit with code 4 if security analysis finds a security group rule "
            "at or above this risk level (needs --enable-security-analysis)"
        ),
    )
    safety_group.add_argument(
        "--audit-output",
        type=str,
        help=(
            "Write a JSON audit of every AWS API operation the run called "
            "(allowed and blocked) to this file"
        ),
    )
    safety_group.add_argument(
        "--validate-operations",
        type=str,
        nargs="+",
        help=(
            "Check service:Operation names (e.g. ec2:DescribeInstances) against "
            "the read-only guard and exit (0 if all allowed, 1 otherwise)"
        ),
    )

    add_template_arguments(parser)

    return parser


def load_configuration_file(file_path: str, config_type: str) -> Dict[str, Any]:
    """Load and validate configuration file."""
    logger = logging.getLogger(__name__)
    validator = ConfigValidator()

    if config_type == "accounts":
        result = validator.validate_accounts_file(file_path)
    elif config_type == "service_descriptions":
        result = validator.validate_service_descriptions_file(file_path)
    elif config_type == "tag_mappings":
        result = validator.validate_tag_mappings_file(file_path)
    else:
        # Generic file loading
        try:
            path = Path(file_path)
            with open(path, "r") as f:
                if path.suffix.lower() in [".yaml", ".yml"]:
                    config = yaml.safe_load(f)
                elif path.suffix.lower() == ".json":
                    config = json.load(f)
                else:
                    raise ValueError(f"Unsupported file format: {path.suffix}")
            return config
        except Exception as e:
            logger.error(f"Error loading {config_type} file {file_path}: {e}")
            sys.exit(1)

    if not result.is_valid:
        logger.error(f"Invalid {config_type} configuration:")
        for error in result.errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    if result.warnings:
        for warning in result.warnings:
            logger.warning(f"  - {warning}")

    return result.config


def create_accounts_from_prompt() -> List[AccountCredentials]:
    """Interactively prompt for account credentials."""
    logger = logging.getLogger(__name__)
    accounts = []

    logger.info(
        "Interactive account setup - Enter account details (press Enter with empty account_id to finish)"
    )

    while True:
        print("\n--- Account Configuration ---")
        account_id = input("Account ID (or press Enter to finish): ").strip()

        if not account_id:
            break

        account_name = input("Account Name (optional): ").strip() or account_id

        print("\nCredential Options:")
        print("1. AWS Profile")
        print("2. Access Keys")
        print("3. Cross-account Role ARN")

        cred_choice = input("Choose credential method (1-3): ").strip()

        account = AccountCredentials(account_id=account_id, account_name=account_name)

        if cred_choice == "1":
            profile_name = input("AWS Profile Name: ").strip()
            if profile_name:
                account.profile_name = profile_name
        elif cred_choice == "2":
            access_key = input("Access Key ID: ").strip()
            secret_key = getpass.getpass("Secret Access Key: ").strip()
            session_token = getpass.getpass("Session Token (optional): ").strip()

            if access_key and secret_key:
                account.access_key_id = access_key
                account.secret_access_key = secret_key
                if session_token:
                    account.session_token = session_token
        elif cred_choice == "3":
            role_arn = input("Role ARN: ").strip()
            external_id = input("External ID (optional): ").strip()

            if role_arn:
                account.role_arn = role_arn
                if external_id:
                    account.external_id = external_id

        # Optional settings
        regions_input = input(
            "Regions (comma-separated, empty for all regions): "
        ).strip()
        if regions_input:
            account.regions = [r.strip() for r in regions_input.split(",")]
        # Empty: the scan asks the account for its own enabled regions.

        services_input = input(
            "Services to include (comma-separated, empty for all): "
        ).strip()
        if services_input:
            account.services = [s.strip() for s in services_input.split(",")]

        accounts.append(account)
        logger.info(f"Added account: {account.account_name} ({account.account_id})")

    return accounts


def create_multi_account_config(args) -> MultiAccountConfig:
    """Create MultiAccountConfig from CLI arguments."""
    logger = logging.getLogger(__name__)

    # Load accounts
    accounts = []

    if args.accounts_file:
        logger.info(f"Loading accounts from file: {args.accounts_file}")
        accounts_config = load_configuration_file(args.accounts_file, "accounts")

        for account_data in accounts_config["accounts"]:
            account = AccountCredentials(
                account_id=account_data["account_id"],
                account_name=account_data.get(
                    "account_name", account_data["account_id"]
                ),
                access_key_id=account_data.get("access_key_id"),
                secret_access_key=account_data.get("secret_access_key"),
                session_token=account_data.get("session_token"),
                profile_name=account_data.get("profile_name"),
                role_arn=account_data.get("role_arn"),
                external_id=account_data.get("external_id"),
                # Empty: the scan asks each account for its own enabled regions.
                regions=account_data.get("regions") or [],
                services=account_data.get("services", []),
                tags=account_data.get("tags", {}),
            )
            accounts.append(account)

        # Apply global settings from file
        settings = accounts_config.get("settings", {})
        max_concurrent = settings.get(
            "max_concurrent_accounts", args.max_concurrent_accounts
        )
        timeout = settings.get(
            "account_processing_timeout", args.account_processing_timeout
        )
        output_dir = settings.get("output_directory", args.output_directory)

    elif args.accounts_prompt:
        logger.info("Starting interactive account setup")
        accounts = create_accounts_from_prompt()
        max_concurrent = args.max_concurrent_accounts
        timeout = args.account_processing_timeout
        output_dir = args.output_directory

    elif args.cross_account_role:
        role_arn = args.cross_account_role
        if not is_role_arn(role_arn):
            logger.error(
                "--cross-account-role was given a role name without --accounts-file. "
                "Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or "
                "list the target account IDs in --accounts-file."
            )
            sys.exit(2)
        account_id = account_id_from_role_arn(role_arn)
        logger.info(f"Using cross-account role: {role_arn}")
        account = AccountCredentials(
            account_id=account_id,
            account_name=f"AWS Account {account_id}",
            role_arn=role_arn,
        )
        accounts = [account]
        max_concurrent = args.max_concurrent_accounts
        timeout = args.account_processing_timeout
        output_dir = args.output_directory

    else:
        logger.info("Using default AWS credentials")
        # Use default credentials and discover actual account ID
        try:
            import boto3

            session = boto3.Session()
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            actual_account_id = identity.get("Account", "unknown")
            account_arn = identity.get("Arn", "")

            # Extract a more meaningful account name from ARN if possible
            if "assumed-role" in account_arn:
                # Extract role name from ARN like: arn:aws:sts::123456789012:assumed-role/RoleName/username
                try:
                    role_part = account_arn.split("assumed-role/")[1].split("/")[0]
                    account_name = f"AWS Account {actual_account_id} ({role_part})"
                except Exception:
                    account_name = f"AWS Account {actual_account_id}"
            elif "user" in account_arn:
                # Extract user name from ARN like: arn:aws:iam::123456789012:user/username
                try:
                    user_part = account_arn.split("user/")[1]
                    account_name = f"AWS Account {actual_account_id} ({user_part})"
                except Exception:
                    account_name = f"AWS Account {actual_account_id}"
            else:
                account_name = f"AWS Account {actual_account_id}"

            logger.info(f"Detected AWS account ID: {actual_account_id}")

        except Exception as e:
            logger.warning(f"Could not detect AWS account ID: {e}")
            actual_account_id = "default"
            account_name = "Default AWS Account"

        account = AccountCredentials(
            account_id=actual_account_id, account_name=account_name
        )
        accounts = [account]
        max_concurrent = args.max_concurrent_accounts
        timeout = args.account_processing_timeout
        output_dir = args.output_directory

    # Apply CLI overrides
    if args.account_regions:
        regions = [r.strip() for r in args.account_regions.split(",")]
        for account in accounts:
            account.regions = regions

    if args.account_services:
        services = [s.strip() for s in args.account_services.split(",")]
        for account in accounts:
            account.services = services

    if args.account_tags:
        try:
            tags = json.loads(args.account_tags)
            for account in accounts:
                account.tags.update(tags)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in --account-tags: {e}")
            sys.exit(1)

    # Create BOM processing config
    bom_config = BOMProcessingConfig(
        enable_network_analysis=getattr(args, "enable_network_analysis", False),
        enable_security_analysis=getattr(args, "enable_security_analysis", False),
        enable_cost_analysis=getattr(args, "enable_cost_analysis", False),
    )

    if args.service_descriptions:
        load_configuration_file(args.service_descriptions, "service_descriptions")
        bom_config.service_descriptions_config = args.service_descriptions

    if args.tag_mappings:
        load_configuration_file(args.tag_mappings, "tag_mappings")
        bom_config.tag_mappings_config = args.tag_mappings

    if args.bom_config:
        # Typed settings: wrong value types stop here with the key named,
        # instead of failing later in BOM processing.
        try:
            ignored = read_bom_settings(args.bom_config, bom_config)
        except SettingsFileError as e:
            logger.error(str(e))
            sys.exit(1)
        if ignored:
            logger.warning(
                f"--bom-config {args.bom_config}: ignored unknown key(s) "
                f"{', '.join(sorted(ignored))}. Valid keys: "
                f"{', '.join(valid_bom_setting_names())}"
            )

    # Create multi-account config
    config = MultiAccountConfig(
        accounts=accounts,
        cross_account_role_name=_cross_account_role_name(args),
        parallel_account_processing=not args.disable_parallel_processing,
        max_concurrent_accounts=max_concurrent,
        account_processing_timeout=timeout,
        consolidate_accounts=True,
        generate_per_account_reports=args.per_account_reports,
        enable_state_management=args.enable_state_management
        and not args.disable_state_management,
        enable_delta_detection=args.enable_delta_detection
        and not args.disable_delta_detection,
        enable_changelog_generation=args.generate_changelog,
        enable_billing_validation=getattr(args, "billing_validation", True),
        bom_processing_config=bom_config,
        output_directory=output_dir,
        credential_validation_timeout=args.credential_timeout,
        fallback_display_mode=(
            args.fallback_display if not args.hide_fallback_resources else "never"
        ),
        word_template=getattr(args, "loaded_templates", {}).get("word"),
        excel_template=getattr(args, "loaded_templates", {}).get("excel"),
        google_options=google_options_from_args(args),
        resume=args.resume,
        resume_max_age_hours=args.resume_max_age_hours,
        state_retention_days=args.state_retention_days,
        state_max_snapshots=args.state_max_snapshots,
    )

    return config


def google_options_from_args(args):
    """GoogleOptions from the command line, or None if no Google output is asked for."""
    from ..reporting.google_output import GoogleOptions

    if not (args.create_google_docs or args.create_google_sheets):
        return None
    return GoogleOptions(
        credentials_file=args.google_credentials,
        oauth_client_file=args.google_oauth_client,
        folder_id=args.google_folder_id,
        share_with=list(args.google_share_with or []),
        share_role=args.google_share_role,
        share_anyone=args.google_share_anyone,
        title=args.google_title,
        sheets=args.create_google_sheets,
        docs=args.create_google_docs,
    )


def _google_usage_errors(args) -> List[str]:
    """Google flag problems that can be found before any AWS or Google call."""
    from ..reporting.google_output import validate_options

    options = google_options_from_args(args)
    if options is None:
        # Share/credential flags without an output flag do nothing: say so.
        stray = [
            flag
            for flag, used in (
                ("--google-credentials", args.google_credentials),
                ("--google-oauth-client", args.google_oauth_client),
                ("--google-folder-id", args.google_folder_id),
                ("--google-share-with", args.google_share_with),
                ("--google-share-anyone", args.google_share_anyone),
                ("--google-title", args.google_title),
            )
            if used
        ]
        if stray:
            return [
                f"{', '.join(stray)}: needs --create-google-sheets or "
                "--create-google-docs"
            ]
        return []
    return [f"Google: {problem}" for problem in validate_options(options)]


RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _risk_threshold_errors(args) -> List[str]:
    if args.risk_threshold and not args.enable_security_analysis:
        return [
            "--risk-threshold: needs --enable-security-analysis, which produces "
            "the risk levels it checks."
        ]
    return []


def risk_findings_at_or_above(results: Dict[str, Any], threshold: str) -> List[Dict]:
    """Security group rules at or above ``threshold`` in the run results."""
    wanted = RISK_ORDER[threshold.lower()]
    findings = results.get("bom_generation", {}).get("security_risk_findings", [])
    return [
        item
        for item in findings
        if RISK_ORDER.get(str(item.get("risk_level", "")).lower(), 0) >= wanted
    ]


def _cross_account_role_name(args) -> str:
    """Role name applied per account (a full ARN is handled as a single account)."""
    if args.cross_account_role and not is_role_arn(args.cross_account_role):
        return args.cross_account_role
    return "InvenTagCrossAccountRole"


def _conflicting_flag_errors(args) -> List[str]:
    """Flags that cannot work together (one would be silently ignored)."""
    errors = []
    if args.accounts_file and args.accounts_prompt:
        errors.append(
            "--accounts-file and --accounts-prompt: give one of them, not both."
        )
    if (
        args.cross_account_role
        and is_role_arn(args.cross_account_role)
        and (args.accounts_file or args.accounts_prompt)
    ):
        errors.append(
            "--cross-account-role: a full role ARN names one account and cannot "
            "be combined with --accounts-file or --accounts-prompt. Give a role "
            "name to use in every account, or put role_arn in the accounts file."
        )
    if args.s3_kms_key_id and args.s3_encryption != "aws:kms":
        errors.append("--s3-kms-key-id: needs --s3-encryption aws:kms.")
    if args.resume and args.disable_state_management:
        errors.append(
            "--resume: needs state management (saved results live in the state "
            "folder); remove --disable-state-management."
        )
    return errors


def _validate_cross_account_role(args) -> Optional[str]:
    """Return an error message if --cross-account-role is malformed."""
    if not args.cross_account_role:
        return None
    try:
        if is_role_arn(args.cross_account_role):
            validate_role_arn(args.cross_account_role)
        else:
            validate_role_name(args.cross_account_role)
    except InvalidRoleError as e:
        return f"--cross-account-role: {e}"
    return None


def _template_usage_errors(args) -> List[str]:
    """Template flags that cannot have an effect with the other flags given."""
    errors = []
    validate_only = (
        args.validate_templates
        or args.validate_config
        or args.validate_config_only
        or args.validate_credentials
    )
    if args.validate_templates and not (args.word_template or args.excel_template):
        errors.append(
            "--validate-templates: give --word-template PATH or "
            "--excel-template PATH (or the two) to validate."
        )
    if validate_only:
        return errors
    if args.word_template and not args.create_word:
        errors.append(
            "--word-template: this flag needs --create-word. Without "
            "--create-word, InvenTag writes no Word report."
        )
    if args.excel_template and args.create_word and not args.create_excel:
        errors.append(
            "--excel-template: this flag needs --create-excel. With only "
            "--create-word, InvenTag writes no Excel report."
        )
    return errors


def load_report_templates(args) -> Tuple[Dict[str, Any], List[str]]:
    """Load and validate the template files named on the command line.

    Returns ``(templates, errors)``. ``templates`` maps ``"word"`` and
    ``"excel"`` to a ReportTemplate, with only the formats that were given.
    ``errors`` has one line for each problem in each file:
    ``<file>: <key path>: <reason>``.
    """
    templates: Dict[str, Any] = {}
    errors: List[str] = []
    for format_type in TEMPLATE_FORMATS:
        path = getattr(args, f"{format_type}_template", None)
        if not path:
            continue
        try:
            templates[format_type] = load_report_template(path, format_type)
        except TemplateValidationError as e:
            errors.extend(e.messages())
    return templates, errors


def _opt_in_exit_code(args, results: Dict[str, Any], logger) -> int:
    """Exit code for --fail-on-account-error / --fail-if-empty (0 = none).

    An account failure (incomplete data) takes precedence over an empty
    result, and both over tag-policy (3) and risk-threshold (4) findings.
    """
    if args.fail_on_account_error and results.get("failed_accounts"):
        logger.error(
            f"{len(results['failed_accounts'])} account(s) failed and "
            f"--fail-on-account-error is set (exit code {EXIT_ACCOUNT_FAILED})"
        )
        return EXIT_ACCOUNT_FAILED
    # One definition of "empty" for the default and the --template paths.
    if args.fail_if_empty and bom_result_is_empty(results):
        logger.error(
            "No resources in the report and --fail-if-empty is set "
            f"(exit code {EXIT_NO_RESOURCES})"
        )
        return EXIT_NO_RESOURCES
    return 0


def validate_aws_credentials_early(timeout: Optional[int] = None) -> bool:
    """
    Validate AWS credentials early before any BOM processing.
    Provides clear error messages for common credential issues.
    """
    logger = logging.getLogger(__name__)

    logger.info("🔐 Validating AWS credentials...")

    try:
        # Test default session first
        session = boto3.Session()
        if timeout:
            from botocore.config import Config

            sts = session.client(
                "sts",
                config=Config(
                    connect_timeout=timeout,
                    read_timeout=timeout,
                    retries={"max_attempts": 1},
                ),
            )
        else:
            sts = session.client("sts")

        # Try to get caller identity
        identity = sts.get_caller_identity()

        logger.info("✅ AWS credentials are valid!")
        logger.info(f"   Account: {identity.get('Account', 'Unknown')}")
        logger.info(f"   User/Role: {identity.get('Arn', 'Unknown')}")

        return True

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error("❌ AWS credential validation failed!")

        if error_code == "InvalidClientTokenId":
            logger.error("   Issue: Invalid or expired security token")
            logger.error("   Solutions:")
            logger.error("   1. Run 'aws configure' to set up credentials")
            logger.error("   2. Check if your access keys are correct")
            logger.error("   3. If using temporary credentials, they may have expired")
            logger.error("   4. If using AWS SSO, run 'aws sso login'")

        elif error_code == "SignatureDoesNotMatch":
            logger.error("   Issue: Invalid AWS Secret Access Key")
            logger.error("   Solutions:")
            logger.error("   1. Run 'aws configure' and double-check your secret key")
            logger.error("   2. Ensure no extra spaces in credentials")

        elif error_code == "AccessDenied":
            logger.error("   Issue: Credentials don't have sufficient permissions")
            logger.error("   Solutions:")
            logger.error("   1. Ensure your IAM user/role has read permissions")
            logger.error(
                "   2. Check the IAM policy in config/defaults/iam-policy-read-only.json"
            )

        elif error_code == "TokenRefreshRequired":
            logger.error("   Issue: AWS SSO token needs refresh")
            logger.error("   Solutions:")
            logger.error("   1. Run 'aws sso login --profile your-profile'")
            logger.error("   2. Set AWS_PROFILE environment variable")

        else:
            logger.error(f"   Error Code: {error_code}")
            logger.error(f"   Error Message: {error_message}")
            logger.error("   Solutions:")
            logger.error("   1. Run 'aws sts get-caller-identity' to test credentials")
            logger.error("   2. Check AWS CLI configuration with 'aws configure list'")

        logger.error("")
        logger.error("💡 Quick diagnostic commands:")
        logger.error("   aws configure list          # Show current config")
        logger.error("   aws sts get-caller-identity # Test credentials")
        logger.error("   aws configure               # Set up new credentials")

        return False

    except NoCredentialsError:
        logger.error("❌ No AWS credentials found!")
        logger.error("   Solutions:")
        logger.error("   1. Run 'aws configure' to set up credentials")
        logger.error("   2. Set AWS environment variables:")
        logger.error("      export AWS_ACCESS_KEY_ID=your-key")
        logger.error("      export AWS_SECRET_ACCESS_KEY=your-secret")
        logger.error("   3. Use IAM roles if running on EC2/ECS/Lambda")
        logger.error("   4. Use --accounts-prompt for interactive setup")

        return False

    except Exception as e:
        logger.error(f"❌ Unexpected error validating credentials: {e}")
        logger.error("   Try running 'aws sts get-caller-identity' manually")
        return False


def validate_credentials_only(config: MultiAccountConfig) -> bool:
    """Validate credentials for all accounts and exit."""
    logger = logging.getLogger(__name__)

    logger.info("Validating credentials for all accounts...")

    credential_manager = CredentialManager()
    all_valid = True

    for account in config.accounts:
        with LoggingContext(logger, account.account_id, account.account_name):
            logger.info(f"Validating credentials for account: {account.account_name}")

            try:
                result = credential_manager.validate_account_credentials(
                    account, timeout=config.credential_validation_timeout
                )

                if result.is_valid:
                    logger.info(
                        f"✓ Credentials valid - Account: {result.account_id}, User: {result.user_arn}"
                    )
                else:
                    logger.error(
                        f"✗ Credential validation failed: {result.error_message}"
                    )
                    all_valid = False

            except Exception as e:
                logger.error(f"✗ Unexpected error validating credentials: {e}")
                all_valid = False

    if all_valid:
        logger.info("✓ All account credentials are valid")
    else:
        logger.error("✗ Some account credentials are invalid")

    return all_valid


def main():
    """Main CLI entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "templates":
        from ..templating.cli import main as templates_main

        sys.exit(templates_main(sys.argv[2:]))

    parser = create_parser()
    args = parser.parse_args()

    # Fail loudly on flags that would otherwise be silently ignored.
    usage_errors = safety.unimplemented_flag_errors(args)
    role_error = _validate_cross_account_role(args)
    if role_error:
        usage_errors.append(role_error)
    usage_errors.extend(_conflicting_flag_errors(args))
    usage_errors.extend(_template_usage_errors(args))
    usage_errors.extend(_google_usage_errors(args))
    usage_errors.extend(_risk_threshold_errors(args))
    if usage_errors:
        for message in usage_errors:
            print(f"inventag: error: {message}", file=sys.stderr)
        sys.exit(safety.EXIT_NOT_IMPLEMENTED)

    if args.print_default_template:
        sys.stdout.write(default_template_text(args.print_default_template))
        sys.exit(0)

    # Templates are validated before any AWS call: a wrong template must not
    # cost a discovery run.
    args.loaded_templates, template_errors = load_report_templates(args)
    if template_errors:
        for message in template_errors:
            print(f"inventag: error: {message}", file=sys.stderr)
        sys.exit(EXIT_INVALID_TEMPLATE)
    if args.validate_templates:
        for format_type, template in args.loaded_templates.items():
            print(
                f"OK  {template.source} ({format_type} template, "
                f"{len(template.sections)} sections)"
            )
        sys.exit(0)

    # Owner-only files, redacted logs, and the read-only guard before any AWS call.
    safety.harden_process()

    if args.validate_operations:
        all_allowed, lines = safety.validate_operations(args.validate_operations)
        for line in lines:
            print(line)
        sys.exit(0 if all_allowed else 1)

    # Set up logging
    logger = setup_logging(
        verbose=args.verbose,
        debug=args.debug,
        log_file=args.log_file,
        account_specific=not args.disable_account_logging,
    )

    guard = safety.enable_read_only_guard()

    try:
        _run(args, logger)
    finally:
        if args.audit_output:
            path = safety.write_audit_output(guard, args.audit_output)
            logger.info(f"Wrote AWS API audit to {path}")


def _log_run_notes(results, logger):
    """Print the run notes of the result (what the reader of the report must
    know) as warnings, once each. Lines that the "not scanned" block above
    already printed are left out. A clean run has no notes and prints nothing."""
    failed = results.get("failed_accounts") or []
    printed = {
        f"{item['account_id']} ({item['account_name']}): "
        f"{'; '.join(item['errors'])[:300]}"
        for item in failed
    }
    pending = []
    for note in results.get("run_notes") or []:
        if note in printed:
            continue
        if failed and re.match(r"\d+ of \d+ account\(s\) (were|failed)", note):
            continue  # the header of the block printed above
        pending.append(note)
    if not pending:
        return
    logger.warning("Notes about this run:")
    for note in pending:
        logger.warning(f"  - {note}")


def _run(args, logger):
    """Validate arguments and run the requested CLI action."""
    logger.info("InvenTag CLI started")
    logger.debug(f"CLI arguments: {vars(args)}")

    template_run = prepare_template_run(args, sys.argv[1:], create_parser, logger)

    # Validate CLI arguments
    validator = ConfigValidator()
    validation_result = validator.validate_cli_arguments(args)

    if not validation_result.is_valid:
        logger.error("Invalid CLI arguments:")
        for error in validation_result.errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    if validation_result.warnings:
        for warning in validation_result.warnings:
            logger.warning(f"  - {warning}")

    if args.validate_config_only:
        # Reads the given files only. No AWS call is made, so it works offline.
        logger.info("Running configuration file validation only...")
        _validate_specific_configs(args, logger, check_credentials=False)
        logger.info(
            "No AWS call was made. Use --validate-credentials to test the credentials."
        )
        sys.exit(0)

    try:
        # Early AWS credential validation (unless skipped or using interactive prompt)
        if (
            not args.skip_credential_validation
            and not args.accounts_prompt
            and not args.accounts_file
        ):
            if not validate_aws_credentials_early(args.credential_timeout):
                logger.error("❌ Cannot proceed with invalid AWS credentials")
                logger.error(
                    "💡 Use --accounts-prompt for interactive credential setup"
                )
                logger.error(
                    "💡 Or use --skip-credential-validation to bypass this check"
                )
                sys.exit(1)

        # Create multi-account configuration
        config = create_multi_account_config(args)

        # Load the Google credentials now (a local step), so a wrong key file
        # stops the run before a long AWS scan, not after it.
        if config.google_options is not None and not (
            args.validate_credentials or args.validate_config
        ):
            from ..reporting import google_output

            try:
                config.google_options.credentials = google_output.load_credentials(
                    config.google_options
                )
            except google_output.GoogleOutputError as e:
                print(f"inventag: error: Google: {e}", file=sys.stderr)
                sys.exit(safety.EXIT_NOT_IMPLEMENTED)

        logger.info(f"Configured {len(config.accounts)} account(s) for processing")

        # Configuration validation modes
        if args.validate_config:
            logger.info("Configuration validation completed successfully")
            sys.exit(0)

        # Credential validation mode
        if args.validate_credentials:
            success = validate_credentials_only(config)
            sys.exit(0 if success else 1)

        # Determine output formats
        output_formats = []
        if args.create_word:
            output_formats.append("word")
        if args.create_excel:
            output_formats.append("excel")
        if args.create_google_docs or args.create_google_sheets:
            output_formats.append("google")

        if not output_formats:
            logger.warning("No output formats specified. Defaulting to Excel format.")
            output_formats = ["excel"]

        # Configure S3 upload if specified
        s3_config = None
        if args.s3_bucket:
            from ..core.cicd_integration import S3UploadConfig

            key_prefix = args.s3_key_prefix or "bom-reports/"
            s3_config = S3UploadConfig(
                bucket_name=args.s3_bucket,
                key_prefix=key_prefix,
                encryption=args.s3_encryption,
                kms_key_id=args.s3_kms_key_id,
            )
            logger.info(f"S3 upload configured: s3://{args.s3_bucket}/{key_prefix}")

        # Create and run BOM generator
        logger.info("Initializing CloudBOMGenerator...")
        if template_run:
            generator = template_run.create_generator(config)
        else:
            generator = CloudBOMGenerator(config)

        logger.info("Starting BOM generation process...")
        start_time = datetime.now()

        # Generate BOM documents
        results = generator.generate_comprehensive_bom(
            output_formats=output_formats, s3_upload_config=s3_config
        )

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        # Report results
        logger.info(f"BOM generation completed in {processing_time:.2f} seconds")

        if results.get("success", False):
            logger.info("✓ BOM generation successful")
            bom_results = results.get("bom_generation", {})
            generated_files = bom_results.get("generated_files", [])
            logger.info(f"Generated documents: {len(generated_files)}")

            for file_path in generated_files:
                logger.info(f"  - {file_path}")

            for item in bom_results.get("google", []):
                prefix = f"[{item['account_id']}] " if item.get("account_id") else ""
                if item.get("spreadsheet_url"):
                    print(f"Google Sheet: {prefix}{item['spreadsheet_url']}")
                if item.get("document_url"):
                    print(f"Google Doc: {prefix}{item['document_url']}")

            failed_accounts = results.get("failed_accounts", [])
            if failed_accounts:
                logger.warning(
                    f"{len(failed_accounts)} account(s) were not scanned, or only "
                    "partly. The report does not include them:"
                )
                for item in failed_accounts:
                    logger.warning(
                        f"  - {item['account_id']} ({item['account_name']}): "
                        f"{'; '.join(item['errors'])[:300]}"
                    )

            s3_uploads = bom_results.get("s3_uploads", [])
            if s3_uploads:
                logger.info(f"S3 uploads: {len(s3_uploads)}")
                for s3_key in s3_uploads:
                    logger.info(f"  - s3://{args.s3_bucket}/{s3_key}")

            processing_stats = results.get("processing_statistics", {})
            if processing_stats:
                logger.info("Processing summary:")
                logger.info(
                    f"  - Total accounts: {processing_stats.get('total_accounts', 0)}"
                )
                logger.info(
                    f"  - Total resources: {processing_stats.get('total_resources', 0)}"
                )
                logger.info(
                    f"  - Processing time: {processing_stats.get('processing_time_seconds', 0):.2f}s"
                )

            _log_run_notes(results, logger)

            opt_in_exit = _opt_in_exit_code(args, results, logger)

            if template_run:
                exit_code = template_run.finish(results, logger)
                if exit_code:
                    sys.exit(opt_in_exit or exit_code)

            if args.risk_threshold:
                findings = risk_findings_at_or_above(results, args.risk_threshold)
                if findings:
                    logger.error(
                        f"{len(findings)} security group rule(s) at or above "
                        f"risk level {args.risk_threshold}:"
                    )
                    for item in findings[:20]:
                        logger.error(
                            f"  - {item.get('group_id', '')}: {item.get('rule', '')} "
                            f"({item.get('risk_level', '')})"
                        )
                    sys.exit(opt_in_exit or EXIT_RISK_THRESHOLD)
                logger.info(
                    f"No security group rule at or above risk level {args.risk_threshold}"
                )

            if opt_in_exit:
                sys.exit(opt_in_exit)

        else:
            logger.error("✗ BOM generation failed")
            error_message = results.get("error")
            if error_message:
                logger.error(f"Error: {error_message}")
            for upload_error in results.get("bom_generation", {}).get(
                "s3_upload_errors", []
            ):
                logger.error(
                    f"  - S3 upload of {upload_error.get('file') or 'reports'} failed: "
                    f"{upload_error.get('error')}"
                )

            account_contexts = results.get("account_contexts", {})
            if any(ctx.get("error_count", 0) > 0 for ctx in account_contexts.values()):
                logger.error("Account-specific errors:")
                for account_id, ctx in account_contexts.items():
                    if ctx.get("error_count", 0) > 0:
                        logger.error(
                            f"  - {account_id}: {ctx.get('error_count', 0)} errors"
                        )

            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("BOM generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.debug:
            import traceback

            logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
