#!/usr/bin/env python3
"""
CI/CD BOM Generation Script

Command-line script for automated multi-account BOM generation in CI/CD pipelines.
Supports S3 upload, compliance gates, notifications, and Prometheus metrics export.
"""

import argparse
import sys
import os
import json
import logging
from pathlib import Path
from typing import List, Optional

# Add the project root to the path so we can import inventag
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
from inventag.core.credential_manager import CredentialManager
from inventag.core.cicd_integration import (
    CICDIntegration,
    S3UploadConfig,
    ComplianceGateConfig,
    NotificationConfig,
    PrometheusConfig,
)


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="CI/CD BOM Generation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic multi-account BOM generation
  python cicd_bom_generation.py --accounts-file accounts.json --formats excel word

  # With S3 upload and notifications
  python cicd_bom_generation.py \\
    --accounts-file accounts.json \\
    --formats excel word json \\
    --s3-bucket my-compliance-bucket \\
    --s3-key-prefix bom-reports \\
    --slack-webhook https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

  # With compliance gate and Prometheus metrics
  python cicd_bom_generation.py \\
    --accounts-file accounts.json \\
    --formats excel \\
    --compliance-threshold 85 \\
    --fail-on-security-issues \\
    --prometheus-gateway http://prometheus-gateway:9091

Environment Variables:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY - AWS credentials
  INVENTAG_S3_BUCKET - Default S3 bucket name
  INVENTAG_SLACK_WEBHOOK - Default Slack webhook URL
  INVENTAG_TEAMS_WEBHOOK - Default Teams webhook URL
  PROMETHEUS_PUSH_GATEWAY_URL - Prometheus Push Gateway URL
  PROMETHEUS_JOB_NAME - Prometheus job name (default: inventag-bom)
  PROMETHEUS_INSTANCE_NAME - Prometheus instance name (default: default)
        """,
    )

    # Account configuration
    parser.add_argument(
        "--accounts-file",
        required=True,
        help="Path to accounts configuration file (JSON/YAML)",
    )

    parser.add_argument(
        "--accounts-prompt",
        action="store_true",
        help="Prompt for account credentials interactively",
    )

    # Output configuration
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["excel", "word", "json", "csv"],
        default=["excel"],
        help="Output formats to generate (default: excel)",
    )

    parser.add_argument(
        "--output-dir",
        default="./bom_output",
        help="Output directory for generated documents (default: ./bom_output)",
    )

    # S3 upload configuration
    parser.add_argument(
        "--s3-bucket",
        help="S3 bucket name for document upload (env: INVENTAG_S3_BUCKET)",
    )

    parser.add_argument(
        "--s3-key-prefix",
        default="inventag-bom",
        help="S3 key prefix for uploaded documents (default: inventag-bom)",
    )

    parser.add_argument(
        "--s3-region", default="us-east-1", help="S3 region (default: us-east-1)"
    )

    parser.add_argument(
        "--s3-encryption",
        choices=["AES256", "aws:kms"],
        default="AES256",
        help="S3 encryption method (default: AES256)",
    )

    parser.add_argument("--s3-kms-key-id", help="KMS key ID for aws:kms encryption")

    parser.add_argument(
        "--s3-public-read",
        action="store_true",
        help="Make S3 objects publicly readable",
    )

    parser.add_argument(
        "--s3-lifecycle-days",
        type=int,
        default=90,
        help="S3 lifecycle policy days (default: 90)",
    )

    # Compliance gate configuration
    parser.add_argument(
        "--compliance-threshold",
        type=float,
        default=80.0,
        help="Minimum compliance percentage threshold (default: 80.0)",
    )

    parser.add_argument(
        "--critical-violations-threshold",
        type=int,
        default=0,
        help="Maximum critical violations allowed (default: 0)",
    )

    parser.add_argument(
        "--required-tags", nargs="+", default=[], help="Required tags for compliance"
    )

    parser.add_argument(
        "--fail-on-security-issues",
        action="store_true",
        help="Fail pipeline on security issues",
    )

    parser.add_argument(
        "--fail-on-network-issues",
        action="store_true",
        help="Fail pipeline on network issues",
    )

    # Notification configuration
    parser.add_argument(
        "--slack-webhook",
        help="Slack webhook URL for notifications (env: INVENTAG_SLACK_WEBHOOK)",
    )

    parser.add_argument(
        "--teams-webhook",
        help="Teams webhook URL for notifications (env: INVENTAG_TEAMS_WEBHOOK)",
    )

    parser.add_argument(
        "--email-recipients",
        nargs="+",
        default=[],
        help="Email recipients for notifications",
    )

    parser.add_argument(
        "--notify-on-success",
        action="store_true",
        default=True,
        help="Send notifications on success (default: True)",
    )

    parser.add_argument(
        "--notify-on-failure",
        action="store_true",
        default=True,
        help="Send notifications on failure (default: True)",
    )

    # Prometheus configuration
    parser.add_argument(
        "--prometheus-gateway",
        help="Prometheus Push Gateway URL (env: PROMETHEUS_PUSH_GATEWAY_URL)",
    )

    parser.add_argument(
        "--prometheus-job",
        default="inventag-bom",
        help="Prometheus job name (default: inventag-bom)",
    )

    parser.add_argument(
        "--prometheus-instance",
        default="default",
        help="Prometheus instance name (default: default)",
    )

    # General options
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without actual execution",
    )

    parser.add_argument(
        "--fail-fast", action="store_true", help="Exit immediately on first error"
    )

    return parser.parse_args()


def load_accounts_configuration(args) -> MultiAccountConfig:
    """Load accounts configuration from file or prompt."""
    credential_manager = CredentialManager()

    if args.accounts_prompt:
        # Interactive credential prompting
        accounts = credential_manager.prompt_for_credentials()
    else:
        # Load from file
        if not Path(args.accounts_file).exists():
            raise FileNotFoundError(f"Accounts file not found: {args.accounts_file}")

        accounts = credential_manager.load_credential_file(args.accounts_file)

        # Enhance accounts with environment-specific credential handling
        accounts = _enhance_accounts_with_environment_credentials(accounts)

        # Validate that all accounts have some form of credentials
        _validate_account_credentials(accounts)

    return MultiAccountConfig(accounts=accounts)


def _enhance_accounts_with_environment_credentials(accounts):
    """Enhance account configurations with environment-specific credentials."""
    import os

    # Detect environment and apply appropriate credential strategy
    environment = _detect_environment()
    logger = logging.getLogger(__name__)

    logger.info(f"Detected environment: {environment}")

    if environment == "github_actions":
        return _apply_github_secrets_credentials(accounts)
    elif environment == "aws_codebuild":
        return _apply_aws_secrets_manager_credentials(accounts)
    elif environment == "local":
        # Local environment - credentials should be in the file or environment variables
        return _apply_local_environment_credentials(accounts)
    else:
        # Default - use credentials as provided in the file
        return accounts


def _detect_environment():
    """Detect the current execution environment."""
    import os

    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github_actions"
    elif os.environ.get("CODEBUILD_BUILD_ID"):
        return "aws_codebuild"
    elif os.environ.get("JENKINS_URL"):
        return "jenkins"
    elif os.environ.get("CI") == "true":
        return "generic_ci"
    else:
        return "local"


def _apply_github_secrets_credentials(accounts):
    """Apply GitHub Secrets-based credentials to accounts."""
    import os
    import re

    logger = logging.getLogger(__name__)
    logger.info("Applying GitHub Secrets credentials")

    for account in accounts:
        account_id = account.account_id
        account_name = account.account_name

        # Skip if account already has credentials
        if account.access_key_id or account.profile_name or account.role_arn:
            logger.info(
                f"Account {account_id} already has credentials configured, skipping GitHub Secrets"
            )
            continue

        # Try multiple environment variable naming patterns
        env_patterns = [
            # Pattern 1: AWS_ACCESS_KEY_ID_<ACCOUNT_ID>
            f"AWS_ACCESS_KEY_ID_{account_id}",
            # Pattern 2: AWS_ACCESS_KEY_ID_<ACCOUNT_NAME_UPPER>
            f"AWS_ACCESS_KEY_ID_{_sanitize_env_name(account_name).upper()}",
            # Pattern 3: <ACCOUNT_NAME_UPPER>_AWS_ACCESS_KEY_ID
            f"{_sanitize_env_name(account_name).upper()}_AWS_ACCESS_KEY_ID",
            # Pattern 4: AWS_ACCESS_KEY_ID_<ACCOUNT_ID_LAST_4>
            f"AWS_ACCESS_KEY_ID_{account_id[-4:]}",
        ]

        credentials_found = False
        for access_key_pattern in env_patterns:
            access_key = os.environ.get(access_key_pattern)
            if access_key:
                # Derive secret key and session token patterns
                secret_key_pattern = access_key_pattern.replace(
                    "ACCESS_KEY_ID", "SECRET_ACCESS_KEY"
                )
                session_token_pattern = access_key_pattern.replace(
                    "ACCESS_KEY_ID", "SESSION_TOKEN"
                )

                secret_key = os.environ.get(secret_key_pattern)
                session_token = os.environ.get(session_token_pattern)

                if secret_key:
                    account.access_key_id = access_key
                    account.secret_access_key = secret_key
                    if session_token:
                        account.session_token = session_token

                    logger.info(
                        f"Applied GitHub Secrets credentials for account {account_id} using pattern {access_key_pattern}"
                    )
                    credentials_found = True
                    break

        if not credentials_found:
            logger.warning(
                f"No GitHub Secrets credentials found for account {account_id} ({account_name}). "
                f"Expected environment variables like: AWS_ACCESS_KEY_ID_{account_id}, "
                f"AWS_ACCESS_KEY_ID_{_sanitize_env_name(account_name).upper()}, etc."
            )

    return accounts


def _sanitize_env_name(name):
    """Sanitize account name for use in environment variable names."""
    import re

    # Replace spaces and special characters with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9]", "_", name)
    # Remove multiple consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Remove leading/trailing underscores
    return sanitized.strip("_")


def _apply_aws_secrets_manager_credentials(accounts):
    """Apply AWS Secrets Manager-based credentials to accounts."""
    import os
    import boto3
    import json

    logger = logging.getLogger(__name__)
    logger.info("Applying AWS Secrets Manager credentials")

    # Initialize Secrets Manager client
    secrets_client = boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )

    for account in accounts:
        account_id = account.account_id
        account_name = account.account_name

        # Skip if account already has credentials
        if account.access_key_id or account.profile_name or account.role_arn:
            logger.info(
                f"Account {account_id} already has credentials configured, skipping Secrets Manager"
            )
            continue

        # Try multiple secret name patterns
        secret_patterns = [
            # Pattern 1: Environment variable override (highest priority)
            os.environ.get(
                f"INVENTAG_SECRET_{_sanitize_env_name(account_name).upper()}"
            ),
            os.environ.get(f"INVENTAG_SECRET_{account_id}"),
            # Pattern 2: Standard naming conventions
            f"inventag/credentials/{account_id}",
            f"inventag/credentials/{_sanitize_env_name(account_name).lower()}",
            f"inventag/{account_id}/credentials",
            f"inventag/{_sanitize_env_name(account_name).lower()}/credentials",
            # Pattern 3: Generic environment-based names
            f"inventag/credentials/{_guess_environment_from_name(account_name)}",
            # Pattern 4: Simple names
            f"inventag-{account_id}",
            f"inventag-{_sanitize_env_name(account_name).lower()}",
        ]

        # Remove None values and duplicates
        secret_patterns = list(dict.fromkeys([p for p in secret_patterns if p]))

        credentials_found = False
        for secret_name in secret_patterns:
            try:
                logger.debug(f"Trying secret: {secret_name} for account {account_id}")

                # Retrieve credentials from Secrets Manager
                response = secrets_client.get_secret_value(SecretId=secret_name)
                secret_data = json.loads(response["SecretString"])

                # Apply credentials
                if (
                    "aws_access_key_id" in secret_data
                    and "aws_secret_access_key" in secret_data
                ):
                    account.access_key_id = secret_data["aws_access_key_id"]
                    account.secret_access_key = secret_data["aws_secret_access_key"]
                    if "aws_session_token" in secret_data:
                        account.session_token = secret_data["aws_session_token"]

                    logger.info(
                        f"Applied AWS Secrets Manager credentials for account {account_id} from {secret_name}"
                    )
                    credentials_found = True
                    break
                else:
                    logger.warning(
                        f"Secret {secret_name} found but missing required keys (aws_access_key_id, aws_secret_access_key)"
                    )

            except secrets_client.exceptions.ResourceNotFoundException:
                logger.debug(f"Secret {secret_name} not found")
                continue
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve secret {secret_name} for account {account_id}: {e}"
                )
                continue

        if not credentials_found:
            logger.warning(
                f"No AWS Secrets Manager credentials found for account {account_id} ({account_name}). "
                f"Tried patterns: {secret_patterns[:3]}... "
                f"Consider setting INVENTAG_SECRET_{_sanitize_env_name(account_name).upper()} environment variable."
            )

    return accounts


def _guess_environment_from_name(account_name):
    """Guess environment type from account name."""
    name_lower = account_name.lower()
    if "prod" in name_lower:
        return "production"
    elif "stag" in name_lower:
        return "staging"
    elif "dev" in name_lower:
        return "development"
    elif "test" in name_lower:
        return "testing"
    elif "sandbox" in name_lower:
        return "sandbox"
    else:
        return _sanitize_env_name(account_name).lower()


def _apply_local_environment_credentials(accounts):
    """Apply local environment credentials to accounts."""
    import os

    logger = logging.getLogger(__name__)
    logger.info("Applying local environment credentials")

    # For local environment, check if global AWS credentials are available
    global_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    global_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    global_session_token = os.environ.get("AWS_SESSION_TOKEN")

    if global_access_key and global_secret_key:
        logger.info("Found global AWS credentials in environment variables")

        # Apply to accounts that don't have credentials specified
        for account in accounts:
            if (
                not account.access_key_id
                and not account.profile_name
                and not account.role_arn
            ):
                account.access_key_id = global_access_key
                account.secret_access_key = global_secret_key
                if global_session_token:
                    account.session_token = global_session_token
                logger.info(
                    f"Applied global environment credentials to account {account.account_id}"
                )

    return accounts


def _validate_account_credentials(accounts):
    """Validate that all accounts have some form of credentials configured."""
    logger = logging.getLogger(__name__)

    accounts_without_credentials = []

    for account in accounts:
        has_credentials = bool(
            account.access_key_id or account.profile_name or account.role_arn
        )

        if not has_credentials:
            accounts_without_credentials.append(account)

    if accounts_without_credentials:
        logger.error("The following accounts do not have credentials configured:")
        for account in accounts_without_credentials:
            logger.error(f"  - Account {account.account_id} ({account.account_name})")

        logger.error("\nCredential configuration options:")
        logger.error("1. Add credentials directly to the account configuration file")
        logger.error(
            "2. Set up AWS CLI profiles and specify profile_name in the config"
        )
        logger.error("3. Configure cross-account roles with role_arn in the config")
        logger.error("4. Set environment variables (GitHub Actions, CodeBuild, etc.)")
        logger.error("5. Use AWS Secrets Manager (CodeBuild environment)")

        environment = _detect_environment()
        if environment == "github_actions":
            logger.error("\nFor GitHub Actions, set up secrets like:")
            for account in accounts_without_credentials:
                logger.error(f"  - AWS_ACCESS_KEY_ID_{account.account_id}")
                logger.error(f"  - AWS_SECRET_ACCESS_KEY_{account.account_id}")
        elif environment == "aws_codebuild":
            logger.error("\nFor AWS CodeBuild, create secrets like:")
            for account in accounts_without_credentials:
                logger.error(f"  - inventag/credentials/{account.account_id}")

        raise ValueError(
            f"{len(accounts_without_credentials)} accounts are missing credentials. See log messages above for configuration options."
        )


def create_s3_config(args) -> Optional[S3UploadConfig]:
    """Create S3 upload configuration."""
    bucket_name = args.s3_bucket or os.environ.get("INVENTAG_S3_BUCKET")

    if not bucket_name:
        return None

    return S3UploadConfig(
        bucket_name=bucket_name,
        key_prefix=args.s3_key_prefix,
        region=args.s3_region,
        encryption=args.s3_encryption,
        kms_key_id=args.s3_kms_key_id,
        public_read=args.s3_public_read,
        lifecycle_days=args.s3_lifecycle_days,
    )


def create_compliance_config(args) -> ComplianceGateConfig:
    """Create compliance gate configuration."""
    return ComplianceGateConfig(
        minimum_compliance_percentage=args.compliance_threshold,
        critical_violations_threshold=args.critical_violations_threshold,
        required_tags=args.required_tags,
        fail_on_security_issues=args.fail_on_security_issues,
        fail_on_network_issues=args.fail_on_network_issues,
    )


def create_notification_config(args) -> NotificationConfig:
    """Create notification configuration."""
    slack_webhook = args.slack_webhook or os.environ.get("INVENTAG_SLACK_WEBHOOK")
    teams_webhook = args.teams_webhook or os.environ.get("INVENTAG_TEAMS_WEBHOOK")

    return NotificationConfig(
        slack_webhook_url=slack_webhook,
        teams_webhook_url=teams_webhook,
        email_recipients=args.email_recipients,
        notify_on_success=args.notify_on_success,
        notify_on_failure=args.notify_on_failure,
    )


def create_prometheus_config(args) -> PrometheusConfig:
    """Create Prometheus configuration."""
    gateway_url = args.prometheus_gateway or os.environ.get(
        "PROMETHEUS_PUSH_GATEWAY_URL"
    )

    return PrometheusConfig(
        push_gateway_url=gateway_url,
        job_name=args.prometheus_job,
        instance_name=args.prometheus_instance,
    )


def print_configuration_summary(
    args, s3_config, compliance_config, notification_config, prometheus_config
):
    """Print configuration summary."""
    print("\n" + "=" * 60)
    print("CI/CD BOM GENERATION CONFIGURATION")
    print("=" * 60)

    print(f"Accounts File: {args.accounts_file}")
    print(f"Output Formats: {', '.join(args.formats)}")
    print(f"Output Directory: {args.output_dir}")

    if s3_config:
        print(f"\nS3 Upload Configuration:")
        print(f"  Bucket: {s3_config.bucket_name}")
        print(f"  Key Prefix: {s3_config.key_prefix}")
        print(f"  Region: {s3_config.region}")
        print(f"  Encryption: {s3_config.encryption}")
        if s3_config.kms_key_id:
            print(f"  KMS Key ID: {s3_config.kms_key_id}")
        print(f"  Public Read: {s3_config.public_read}")
        print(f"  Lifecycle Days: {s3_config.lifecycle_days}")
    else:
        print("\nS3 Upload: Disabled")

    print(f"\nCompliance Gate Configuration:")
    print(f"  Minimum Compliance: {compliance_config.minimum_compliance_percentage}%")
    print(
        f"  Critical Violations Threshold: {compliance_config.critical_violations_threshold}"
    )
    print(f"  Required Tags: {compliance_config.required_tags}")
    print(f"  Fail on Security Issues: {compliance_config.fail_on_security_issues}")
    print(f"  Fail on Network Issues: {compliance_config.fail_on_network_issues}")

    print(f"\nNotification Configuration:")
    print(
        f"  Slack Webhook: {'Configured' if notification_config.slack_webhook_url else 'Not configured'}"
    )
    print(
        f"  Teams Webhook: {'Configured' if notification_config.teams_webhook_url else 'Not configured'}"
    )
    print(f"  Email Recipients: {len(notification_config.email_recipients)}")
    print(f"  Notify on Success: {notification_config.notify_on_success}")
    print(f"  Notify on Failure: {notification_config.notify_on_failure}")

    print(f"\nPrometheus Configuration:")
    print(
        f"  Push Gateway: {'Configured' if prometheus_config.push_gateway_url else 'Not configured'}"
    )
    print(f"  Job Name: {prometheus_config.job_name}")
    print(f"  Instance Name: {prometheus_config.instance_name}")

    print("=" * 60 + "\n")


def main():
    """Main execution function."""
    args = parse_arguments()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)
    logger.info("Starting CI/CD BOM generation")

    try:
        # Load configuration
        logger.info("Loading configuration...")

        accounts_config = load_accounts_configuration(args)
        s3_config = create_s3_config(args)
        compliance_config = create_compliance_config(args)
        notification_config = create_notification_config(args)
        prometheus_config = create_prometheus_config(args)

        # Print configuration summary
        if args.verbose:
            print_configuration_summary(
                args,
                s3_config,
                compliance_config,
                notification_config,
                prometheus_config,
            )

        # Dry run check
        if args.dry_run:
            logger.info("Dry run mode - configuration validated successfully")
            print("\n✅ Dry run completed successfully - configuration is valid")
            return 0

        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize BOM generator
        logger.info("Initializing BOM generator...")
        bom_generator = CloudBOMGenerator(accounts_config)

        # Initialize CI/CD integration
        logger.info("Initializing CI/CD integration...")
        cicd = CICDIntegration(
            s3_config=s3_config,
            compliance_gate_config=compliance_config,
            notification_config=notification_config,
            prometheus_config=prometheus_config,
        )

        # Execute pipeline integration
        logger.info("Executing CI/CD pipeline integration...")
        result = cicd.execute_pipeline_integration(
            bom_generator=bom_generator,
            output_formats=args.formats,
            upload_to_s3=bool(s3_config),
            send_notifications=True,
            export_metrics=True,
        )

        # Print results
        print("\n" + "=" * 60)
        print("EXECUTION RESULTS")
        print("=" * 60)

        print(f"Success: {'✅ YES' if result.success else '❌ NO'}")
        print(
            f"Compliance Gate: {'✅ PASSED' if result.compliance_gate_passed else '❌ FAILED'}"
        )
        print(f"Execution Time: {result.execution_time_seconds:.2f} seconds")
        print(f"Generated Documents: {len(result.generated_documents)}")
        print(f"S3 Uploads: {len(result.s3_uploads)}")
        print(f"Notifications Sent: {len(result.notifications_sent)}")

        if result.error_message:
            print(f"Error: {result.error_message}")

        if result.s3_uploads:
            print("\nS3 Document Links:")
            for format_type, url in result.s3_uploads.items():
                print(f"  {format_type.upper()}: {url}")

        if result.metrics:
            print(f"\nMetrics Summary:")
            print(f"  Total Resources: {result.metrics.total_resources}")
            print(f"  Compliant Resources: {result.metrics.compliant_resources}")
            print(
                f"  Compliance Percentage: {result.metrics.compliance_percentage:.1f}%"
            )
            print(f"  Total Accounts: {result.metrics.total_accounts}")
            print(f"  Successful Accounts: {result.metrics.successful_accounts}")
            print(f"  Failed Accounts: {result.metrics.failed_accounts}")

        print("=" * 60)

        # Exit with appropriate code
        if not result.success:
            logger.error("CI/CD pipeline execution failed")
            return 1
        elif not result.compliance_gate_passed:
            logger.error("Compliance gate failed")
            return 2
        else:
            logger.info("CI/CD pipeline execution completed successfully")
            return 0

    except KeyboardInterrupt:
        logger.info("Execution interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
