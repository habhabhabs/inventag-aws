#!/usr/bin/env python3
"""
InvenTag CLI - Comprehensive Command Line Interface

Multi-account AWS cloud governance platform with BOM generation,
compliance checking, and advanced reporting capabilities.
"""

import argparse
import sys
import json
import yaml
import logging
import boto3
from pathlib import Path
from typing import Dict, List, Any, Optional
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
from .config_validator import ConfigValidator
from .logging_setup import setup_logging, LoggingContext


def _validate_specific_configs(args, logger):
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
        if not args.skip_credential_validation:
            logger.info("🔐 Also checking AWS credentials...")
            if validate_aws_credentials_early():
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

  # Cross-account role assumption (auto-discovers all regions)
  inventag --cross-account-role InvenTagRole

  # CI/CD integration with S3 upload
  inventag --accounts-file accounts.json --create-excel --s3-bucket reports-bucket --s3-key-prefix bom-reports/

  # Debug mode with comprehensive logging
  inventag --debug --log-file inventag-debug.log --create-excel

  # Validate AWS credentials only
  inventag --validate-credentials
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
        help="Cross-account role name to assume for multi-account scanning (requires appropriate permissions)",
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
        help="Generate Google Docs/Sheets BOM report (requires Google API credentials)",
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
        help="S3 bucket name for uploading generated BOM documents",
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
        help="KMS key ID for S3 encryption (required if --s3-encryption is aws:kms)",
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
        help="Comma-separated list of AWS services to include (empty means all services)",
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
        action="store_true",
        default=True,
        help="Generate changelog for detected changes (default: enabled)",
    )
    output_group.add_argument(
        "--per-account-reports",
        action="store_true",
        help="Generate separate BOM reports for each account (in addition to consolidated report)",
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
        help="Enable production safety monitoring and validation (default: enabled)",
    )
    safety_group.add_argument(
        "--disable-production-safety",
        action="store_true",
        help="Disable production safety monitoring (not recommended for production use)",
    )
    safety_group.add_argument(
        "--enforce-read-only",
        action="store_true",
        default=True,
        help="Enforce read-only operations only for security (default: enabled)",
    )
    safety_group.add_argument(
        "--security-validation",
        action="store_true",
        default=True,
        help="Enable security validation for all AWS operations (default: enabled)",
    )
    safety_group.add_argument(
        "--compliance-standard",
        choices=["general", "soc2", "pci", "hipaa", "gdpr"],
        default="general",
        help="Compliance standard to enforce (default: general)",
    )
    safety_group.add_argument(
        "--risk-threshold",
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        default="MEDIUM",
        help="Risk threshold for operation blocking (default: MEDIUM)",
    )
    safety_group.add_argument(
        "--audit-output",
        type=str,
        help="Path to security audit report output file",
    )
    safety_group.add_argument(
        "--validate-operations",
        type=str,
        nargs="+",
        help="Validate specific AWS operations (format: service:operation)",
    )

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
            secret_key = input("Secret Access Key: ").strip()
            session_token = input("Session Token (optional): ").strip()

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
        else:
            # Auto-discover all regions
            account.regions = get_all_aws_regions()

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
                regions=account_data.get("regions") or get_all_aws_regions(),
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
        logger.info(f"Using cross-account role: {args.cross_account_role}")
        # Create a single account entry for cross-account role
        account = AccountCredentials(
            account_id="cross-account",
            account_name="Cross-Account Role",
            role_arn=args.cross_account_role,
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
        bom_file_config = load_configuration_file(args.bom_config, "bom_config")
        # Update bom_config with file settings
        for key, value in bom_file_config.items():
            if hasattr(bom_config, key):
                setattr(bom_config, key, value)

    # Create multi-account config
    config = MultiAccountConfig(
        accounts=accounts,
        cross_account_role_name=args.cross_account_role or "InvenTagCrossAccountRole",
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
        bom_processing_config=bom_config,
        output_directory=output_dir,
        credential_validation_timeout=args.credential_timeout,
        fallback_display_mode=(
            args.fallback_display if not args.hide_fallback_resources else "never"
        ),
    )

    return config


def validate_aws_credentials_early() -> bool:
    """
    Validate AWS credentials early before any BOM processing.
    Provides clear error messages for common credential issues.
    """
    logger = logging.getLogger(__name__)

    logger.info("🔐 Validating AWS credentials...")

    try:
        # Test default session first
        session = boto3.Session()
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
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    logger = setup_logging(
        verbose=args.verbose,
        debug=args.debug,
        log_file=args.log_file,
        account_specific=not args.disable_account_logging,
    )

    logger.info("InvenTag CLI started")
    logger.debug(f"CLI arguments: {vars(args)}")

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

    try:
        # Early AWS credential validation (unless skipped or using interactive prompt)
        if (
            not args.skip_credential_validation
            and not args.accounts_prompt
            and not args.accounts_file
        ):
            if not validate_aws_credentials_early():
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

        logger.info(f"Configured {len(config.accounts)} account(s) for processing")

        # Configuration validation modes
        if args.validate_config_only:
            logger.info("Running configuration file validation only...")
            _validate_specific_configs(args, logger)
            sys.exit(0)

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
        if args.create_google_docs:
            output_formats.append("google_docs")

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

        else:
            logger.error("✗ BOM generation failed")
            error_message = results.get("error")
            if error_message:
                logger.error(f"Error: {error_message}")

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
