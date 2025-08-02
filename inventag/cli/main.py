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
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# InvenTag imports
from ..core import (
    CloudBOMGenerator, 
    MultiAccountConfig, 
    AccountCredentials,
    CredentialManager
)
from ..reporting import BOMProcessingConfig
from .config_validator import ConfigValidator
from .logging_setup import setup_logging, LoggingContext


def create_parser() -> argparse.ArgumentParser:
    """Create comprehensive argument parser for InvenTag CLI."""
    
    parser = argparse.ArgumentParser(
        prog='inventag',
        description='InvenTag - Comprehensive AWS Cloud Governance Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate BOM for single account using default credentials
  inventag --create-excel --create-word
  
  # Multi-account BOM generation from file
  inventag --accounts-file accounts.json --create-excel --s3-bucket my-bucket
  
  # Interactive multi-account setup
  inventag --accounts-prompt --create-word --create-excel --verbose
  
  # Cross-account role assumption
  inventag --cross-account-role InvenTagRole --account-regions us-east-1,us-west-2
  
  # CI/CD integration with S3 upload
  inventag --accounts-file accounts.json --create-excel --s3-bucket reports-bucket --s3-key-prefix bom-reports/
  
  # Debug mode with comprehensive logging
  inventag --debug --log-file inventag-debug.log --create-excel
        """
    )
    
    # Account specification options
    account_group = parser.add_argument_group('Account Configuration')
    account_group.add_argument(
        '--accounts-file',
        type=str,
        help='Path to accounts configuration file (JSON/YAML) containing account credentials and settings'
    )
    account_group.add_argument(
        '--accounts-prompt',
        action='store_true',
        help='Interactively prompt for account credentials and configuration'
    )
    account_group.add_argument(
        '--cross-account-role',
        type=str,
        help='Cross-account role name to assume for multi-account scanning (requires appropriate permissions)'
    )
    
    # Format-specific options
    format_group = parser.add_argument_group('Output Format Options')
    format_group.add_argument(
        '--create-word',
        action='store_true',
        help='Generate professional Word document BOM report'
    )
    format_group.add_argument(
        '--create-excel',
        action='store_true',
        help='Generate comprehensive Excel workbook BOM report'
    )
    format_group.add_argument(
        '--create-google-docs',
        action='store_true',
        help='Generate Google Docs/Sheets BOM report (requires Google API credentials)'
    )
    
    # S3 upload options for CI/CD
    s3_group = parser.add_argument_group('S3 Upload Options (CI/CD Integration)')
    s3_group.add_argument(
        '--s3-bucket',
        type=str,
        help='S3 bucket name for uploading generated BOM documents'
    )
    s3_group.add_argument(
        '--s3-key-prefix',
        type=str,
        help='S3 key prefix for organizing uploaded documents (default: bom-reports/)'
    )
    s3_group.add_argument(
        '--s3-encryption',
        choices=['AES256', 'aws:kms'],
        default='AES256',
        help='S3 server-side encryption method (default: AES256)'
    )
    s3_group.add_argument(
        '--s3-kms-key-id',
        type=str,
        help='KMS key ID for S3 encryption (required if --s3-encryption is aws:kms)'
    )
    
    # Account-specific configuration overrides
    override_group = parser.add_argument_group('Account-Specific Configuration Overrides')
    override_group.add_argument(
        '--account-regions',
        type=str,
        help='Comma-separated list of AWS regions to scan (overrides account-specific settings)'
    )
    override_group.add_argument(
        '--account-services',
        type=str,
        help='Comma-separated list of AWS services to include (empty means all services)'
    )
    override_group.add_argument(
        '--account-tags',
        type=str,
        help='JSON string of tag filters to apply across all accounts'
    )
    
    # Parallel processing options
    parallel_group = parser.add_argument_group('Parallel Processing Options')
    parallel_group.add_argument(
        '--max-concurrent-accounts',
        type=int,
        default=4,
        help='Maximum number of accounts to process concurrently (default: 4)'
    )
    parallel_group.add_argument(
        '--account-processing-timeout',
        type=int,
        default=1800,
        help='Timeout in seconds for processing each account (default: 1800)'
    )
    parallel_group.add_argument(
        '--disable-parallel-processing',
        action='store_true',
        help='Disable parallel account processing (process accounts sequentially)'
    )
    
    # Configuration file options
    config_group = parser.add_argument_group('Configuration Files')
    config_group.add_argument(
        '--service-descriptions',
        type=str,
        help='Path to service descriptions configuration file (YAML/JSON)'
    )
    config_group.add_argument(
        '--tag-mappings',
        type=str,
        help='Path to tag mappings configuration file (YAML/JSON)'
    )
    config_group.add_argument(
        '--bom-config',
        type=str,
        help='Path to BOM processing configuration file (YAML/JSON)'
    )
    config_group.add_argument(
        '--validate-config',
        action='store_true',
        help='Validate configuration files and exit (no BOM generation)'
    )
    
    # Output and state management
    output_group = parser.add_argument_group('Output and State Management')
    output_group.add_argument(
        '--output-directory',
        type=str,
        default='bom_output',
        help='Directory for output files (default: bom_output)'
    )
    output_group.add_argument(
        '--enable-state-management',
        action='store_true',
        default=True,
        help='Enable state management for change tracking (default: enabled)'
    )
    output_group.add_argument(
        '--disable-state-management',
        action='store_true',
        help='Disable state management and change tracking'
    )
    output_group.add_argument(
        '--enable-delta-detection',
        action='store_true',
        default=True,
        help='Enable delta detection for change analysis (default: enabled)'
    )
    output_group.add_argument(
        '--disable-delta-detection',
        action='store_true',
        help='Disable delta detection'
    )
    output_group.add_argument(
        '--generate-changelog',
        action='store_true',
        default=True,
        help='Generate changelog for detected changes (default: enabled)'
    )
    output_group.add_argument(
        '--per-account-reports',
        action='store_true',
        help='Generate separate BOM reports for each account (in addition to consolidated report)'
    )
    
    # Logging and debug options
    logging_group = parser.add_argument_group('Logging and Debug Options')
    logging_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging (INFO level)'
    )
    logging_group.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging (DEBUG level) with detailed AWS API calls'
    )
    logging_group.add_argument(
        '--log-file',
        type=str,
        help='Path to log file for persistent logging'
    )
    logging_group.add_argument(
        '--disable-account-logging',
        action='store_true',
        help='Disable account-specific logging prefixes'
    )
    
    # Credential validation options
    cred_group = parser.add_argument_group('Credential Validation')
    cred_group.add_argument(
        '--validate-credentials',
        action='store_true',
        help='Validate all account credentials before processing and exit'
    )
    cred_group.add_argument(
        '--credential-timeout',
        type=int,
        default=30,
        help='Timeout in seconds for credential validation (default: 30)'
    )
    
    return parser


def load_configuration_file(file_path: str, config_type: str) -> Dict[str, Any]:
    """Load and validate configuration file."""
    logger = logging.getLogger(__name__)
    validator = ConfigValidator()
    
    if config_type == 'accounts':
        result = validator.validate_accounts_file(file_path)
    elif config_type == 'service_descriptions':
        result = validator.validate_service_descriptions_file(file_path)
    elif config_type == 'tag_mappings':
        result = validator.validate_tag_mappings_file(file_path)
    else:
        # Generic file loading
        try:
            path = Path(file_path)
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
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
    
    logger.info("Interactive account setup - Enter account details (press Enter with empty account_id to finish)")
    
    while True:
        print("\n--- Account Configuration ---")
        account_id = input("Account ID (or press Enter to finish): ").strip()
        
        if not account_id:
            break
        
        account_name = input(f"Account Name (optional): ").strip() or account_id
        
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
        regions_input = input("Regions (comma-separated, default: us-east-1): ").strip()
        if regions_input:
            account.regions = [r.strip() for r in regions_input.split(',')]
        
        services_input = input("Services to include (comma-separated, empty for all): ").strip()
        if services_input:
            account.services = [s.strip() for s in services_input.split(',')]
        
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
        accounts_config = load_configuration_file(args.accounts_file, 'accounts')
        
        for account_data in accounts_config['accounts']:
            account = AccountCredentials(
                account_id=account_data['account_id'],
                account_name=account_data.get('account_name', account_data['account_id']),
                access_key_id=account_data.get('access_key_id'),
                secret_access_key=account_data.get('secret_access_key'),
                session_token=account_data.get('session_token'),
                profile_name=account_data.get('profile_name'),
                role_arn=account_data.get('role_arn'),
                external_id=account_data.get('external_id'),
                regions=account_data.get('regions', ['us-east-1']),
                services=account_data.get('services', []),
                tags=account_data.get('tags', {})
            )
            accounts.append(account)
        
        # Apply global settings from file
        settings = accounts_config.get('settings', {})
        max_concurrent = settings.get('max_concurrent_accounts', args.max_concurrent_accounts)
        timeout = settings.get('account_processing_timeout', args.account_processing_timeout)
        output_dir = settings.get('output_directory', args.output_directory)
        
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
            role_arn=args.cross_account_role
        )
        accounts = [account]
        max_concurrent = args.max_concurrent_accounts
        timeout = args.account_processing_timeout
        output_dir = args.output_directory
        
    else:
        logger.info("Using default AWS credentials")
        # Use default credentials
        account = AccountCredentials(
            account_id="default",
            account_name="Default AWS Account"
        )
        accounts = [account]
        max_concurrent = args.max_concurrent_accounts
        timeout = args.account_processing_timeout
        output_dir = args.output_directory
    
    # Apply CLI overrides
    if args.account_regions:
        regions = [r.strip() for r in args.account_regions.split(',')]
        for account in accounts:
            account.regions = regions
    
    if args.account_services:
        services = [s.strip() for s in args.account_services.split(',')]
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
    bom_config = BOMProcessingConfig()
    
    if args.service_descriptions:
        service_desc_config = load_configuration_file(args.service_descriptions, 'service_descriptions')
        bom_config.service_descriptions = service_desc_config
    
    if args.tag_mappings:
        tag_mappings_config = load_configuration_file(args.tag_mappings, 'tag_mappings')
        bom_config.tag_mappings = tag_mappings_config
    
    if args.bom_config:
        bom_file_config = load_configuration_file(args.bom_config, 'bom_config')
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
        enable_state_management=args.enable_state_management and not args.disable_state_management,
        enable_delta_detection=args.enable_delta_detection and not args.disable_delta_detection,
        enable_changelog_generation=args.generate_changelog,
        bom_processing_config=bom_config,
        output_directory=output_dir,
        credential_validation_timeout=args.credential_timeout
    )
    
    return config


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
                    account, 
                    timeout=config.credential_validation_timeout
                )
                
                if result.is_valid:
                    logger.info(f"✓ Credentials valid - Account: {result.account_id}, User: {result.user_arn}")
                else:
                    logger.error(f"✗ Credential validation failed: {result.error_message}")
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
        account_specific=not args.disable_account_logging
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
        # Create multi-account configuration
        config = create_multi_account_config(args)
        
        logger.info(f"Configured {len(config.accounts)} account(s) for processing")
        
        # Configuration validation mode
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
            output_formats.append('word')
        if args.create_excel:
            output_formats.append('excel')
        if args.create_google_docs:
            output_formats.append('google_docs')
        
        if not output_formats:
            logger.warning("No output formats specified. Defaulting to Excel format.")
            output_formats = ['excel']
        
        # Configure S3 upload if specified
        s3_config = None
        if args.s3_bucket:
            from ..core.cicd_integration import S3UploadConfig
            key_prefix = args.s3_key_prefix or 'bom-reports/'
            s3_config = S3UploadConfig(
                bucket_name=args.s3_bucket,
                key_prefix=key_prefix,
                encryption=args.s3_encryption,
                kms_key_id=args.s3_kms_key_id
            )
            logger.info(f"S3 upload configured: s3://{args.s3_bucket}/{key_prefix}")
        
        # Create and run BOM generator
        logger.info("Initializing CloudBOMGenerator...")
        generator = CloudBOMGenerator(config)
        
        logger.info("Starting BOM generation process...")
        start_time = datetime.now()
        
        # Generate BOM documents
        results = generator.generate_comprehensive_bom(
            output_formats=output_formats,
            s3_upload_config=s3_config
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Report results
        logger.info(f"BOM generation completed in {processing_time:.2f} seconds")
        
        if results.success:
            logger.info("✓ BOM generation successful")
            logger.info(f"Generated documents: {len(results.generated_files)}")
            
            for file_path in results.generated_files:
                logger.info(f"  - {file_path}")
            
            if results.s3_uploads:
                logger.info(f"S3 uploads: {len(results.s3_uploads)}")
                for s3_key in results.s3_uploads:
                    logger.info(f"  - s3://{args.s3_bucket}/{s3_key}")
            
            if results.processing_summary:
                summary = results.processing_summary
                logger.info(f"Processing summary:")
                logger.info(f"  - Total accounts: {summary.get('total_accounts', 0)}")
                logger.info(f"  - Total resources: {summary.get('total_resources', 0)}")
                logger.info(f"  - Compliant resources: {summary.get('compliant_resources', 0)}")
                logger.info(f"  - Compliance percentage: {summary.get('compliance_percentage', 0):.1f}%")
        
        else:
            logger.error("✗ BOM generation failed")
            if results.error_message:
                logger.error(f"Error: {results.error_message}")
            
            if results.account_errors:
                logger.error("Account-specific errors:")
                for account_id, error in results.account_errors.items():
                    logger.error(f"  - {account_id}: {error}")
            
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


if __name__ == '__main__':
    main()