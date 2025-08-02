#!/usr/bin/env python3
"""
Multi-Account Credential and Configuration Management

Secure credential management system for multiple AWS accounts with support for:
- Secure credential file format for multiple AWS accounts (JSON/YAML)
- Interactive credential prompt system for secure key input
- AWS profile-based authentication across accounts
- Cross-account role assumption with configurable role names
- Credential validation and account accessibility testing
- Account-specific configuration overrides (regions, services, tags)
"""

import logging
import json
import yaml
import getpass
import boto3
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
import keyring
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

from .cloud_bom_generator import AccountCredentials, AccountContext


@dataclass
class CredentialValidationResult:
    """Result of credential validation."""
    is_valid: bool
    account_id: str = ""
    account_alias: str = ""
    user_arn: str = ""
    accessible_regions: List[str] = field(default_factory=list)
    available_services: List[str] = field(default_factory=list)
    error_message: str = ""
    validation_timestamp: str = ""
    permissions_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecureCredentialFile:
    """Secure credential file structure."""
    version: str = "1.0"
    encrypted: bool = False
    accounts: List[Dict[str, Any]] = field(default_factory=list)
    global_config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CredentialManager:
    """
    Multi-account credential and configuration management system.
    
    Features:
    - Secure credential file format for multiple AWS accounts (JSON/YAML)
    - Interactive credential prompt system for secure key input
    - AWS profile-based authentication across accounts
    - Cross-account role assumption with configurable role names
    - Credential validation and account accessibility testing
    - Account-specific configuration overrides (regions, services, tags)
    """

    def __init__(self, 
                 credential_file: Optional[str] = None,
                 encryption_password: Optional[str] = None,
                 use_keyring: bool = True):
        """Initialize the credential manager."""
        self.logger = logging.getLogger(f"{__name__}.CredentialManager")
        self.credential_file = Path(credential_file) if credential_file else None
        self.encryption_password = encryption_password
        self.use_keyring = use_keyring
        
        # Encryption key for secure storage
        self._encryption_key: Optional[bytes] = None
        
        # Cached credentials
        self._cached_credentials: Dict[str, AccountCredentials] = {}
        self._validation_cache: Dict[str, CredentialValidationResult] = {}
        
        self.logger.info("Initialized CredentialManager")

    def create_secure_credential_file(self, 
                                    accounts: List[AccountCredentials],
                                    output_file: str,
                                    encrypt: bool = True,
                                    password: Optional[str] = None) -> str:
        """
        Create a secure credential file for multiple AWS accounts.
        
        Args:
            accounts: List of account credentials
            output_file: Path to output file
            encrypt: Whether to encrypt the file
            password: Encryption password (will prompt if not provided and encrypt=True)
            
        Returns:
            Path to created file
        """
        self.logger.info(f"Creating secure credential file: {output_file}")
        
        # Prepare credential data
        credential_data = SecureCredentialFile(
            encrypted=encrypt,
            accounts=[self._serialize_account_credentials(acc) for acc in accounts],
            metadata={
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "InvenTag CredentialManager",
                "total_accounts": len(accounts)
            }
        )
        
        output_path = Path(output_file)
        
        if encrypt:
            # Get encryption password
            if not password:
                password = getpass.getpass("Enter encryption password for credential file: ")
                confirm_password = getpass.getpass("Confirm encryption password: ")
                if password != confirm_password:
                    raise ValueError("Passwords do not match")
            
            # Encrypt and save
            encrypted_data = self._encrypt_credential_data(credential_data, password)
            
            with open(output_path, 'w') as f:
                if output_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.safe_dump(encrypted_data, f, default_flow_style=False)
                else:
                    json.dump(encrypted_data, f, indent=2)
        else:
            # Save unencrypted
            data = asdict(credential_data)
            
            with open(output_path, 'w') as f:
                if output_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.safe_dump(data, f, default_flow_style=False)
                else:
                    json.dump(data, f, indent=2)
        
        self.logger.info(f"Created credential file with {len(accounts)} accounts")
        return str(output_path)

    def load_credential_file(self, 
                           credential_file: str,
                           password: Optional[str] = None) -> List[AccountCredentials]:
        """
        Load credentials from a secure credential file.
        
        Args:
            credential_file: Path to credential file
            password: Decryption password (will prompt if needed)
            
        Returns:
            List of account credentials
        """
        self.logger.info(f"Loading credential file: {credential_file}")
        
        credential_path = Path(credential_file)
        if not credential_path.exists():
            raise FileNotFoundError(f"Credential file not found: {credential_file}")
        
        # Load file data
        with open(credential_path, 'r') as f:
            if credential_path.suffix.lower() in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        # Check if encrypted
        if data.get('encrypted', False):
            if not password:
                password = getpass.getpass("Enter decryption password: ")
            
            # Decrypt data
            credential_data = self._decrypt_credential_data(data, password)
        else:
            credential_data = SecureCredentialFile(**data)
        
        # Parse accounts
        accounts = []
        for account_data in credential_data.accounts:
            # Handle sensitive data from keyring if configured
            if self.use_keyring and account_data.get('use_keyring', False):
                account_data = self._load_from_keyring(account_data)
            
            accounts.append(AccountCredentials(**account_data))
        
        # Cache credentials
        for account in accounts:
            self._cached_credentials[account.account_id] = account
        
        self.logger.info(f"Loaded {len(accounts)} account credentials")
        return accounts

    def interactive_credential_setup(self, 
                                   save_to_file: Optional[str] = None,
                                   encrypt_file: bool = True) -> List[AccountCredentials]:
        """
        Interactive credential prompt system for secure key input.
        
        Args:
            save_to_file: Optional file to save credentials to
            encrypt_file: Whether to encrypt the saved file
            
        Returns:
            List of configured account credentials
        """
        print("\n" + "=" * 60)
        print("InvenTag Multi-Account Credential Setup")
        print("=" * 60)
        
        accounts = []
        
        while True:
            print(f"\n--- Configuring Account #{len(accounts) + 1} ---")
            
            # Basic account information
            account_id = self._prompt_with_validation(
                "Account ID (12 digits): ",
                lambda x: len(x) == 12 and x.isdigit(),
                "Account ID must be exactly 12 digits"
            )
            
            if not account_id:
                break
            
            account_name = input("Account Name (optional): ").strip()
            if not account_name:
                account_name = f"Account-{account_id}"
            
            # Authentication method selection
            print("\nAuthentication Methods:")
            print("1. AWS Profile (recommended)")
            print("2. Access Keys (will be encrypted)")
            print("3. Role ARN for assumption")
            print("4. Cross-account role (uses configured role name)")
            
            auth_method = self._prompt_with_validation(
                "Select authentication method (1-4): ",
                lambda x: x in ['1', '2', '3', '4'],
                "Please select 1, 2, 3, or 4"
            )
            
            credentials = AccountCredentials(
                account_id=account_id,
                account_name=account_name
            )
            
            # Configure authentication based on selection
            if auth_method == "1":
                credentials.profile_name = input("AWS Profile Name: ").strip()
                
            elif auth_method == "2":
                credentials.access_key_id = input("Access Key ID: ").strip()
                credentials.secret_access_key = getpass.getpass("Secret Access Key: ")
                
                session_token = getpass.getpass("Session Token (optional, press Enter to skip): ")
                if session_token:
                    credentials.session_token = session_token
                    
            elif auth_method == "3":
                credentials.role_arn = input("Role ARN: ").strip()
                
                external_id = input("External ID (optional, press Enter to skip): ").strip()
                if external_id:
                    credentials.external_id = external_id
                    
            # Method 4 uses default cross-account role configuration
            
            # Regional configuration
            print("\nRegional Configuration:")
            regions_input = input("Regions (comma-separated, default: us-east-1): ").strip()
            if regions_input:
                credentials.regions = [r.strip() for r in regions_input.split(",")]
            
            # Service filtering
            print("\nService Filtering (optional):")
            services_input = input("Specific services to scan (comma-separated, empty for all): ").strip()
            if services_input:
                credentials.services = [s.strip() for s in services_input.split(",")]
            
            # Tag filtering
            print("\nTag Filtering (optional):")
            while True:
                tag_key = input("Tag key (press Enter to finish): ").strip()
                if not tag_key:
                    break
                tag_value = input(f"Tag value for '{tag_key}': ").strip()
                credentials.tags[tag_key] = tag_value
            
            # Validate credentials
            print("\nValidating credentials...")
            validation_result = self.validate_account_credentials(credentials)
            
            if validation_result.is_valid:
                print(f"✓ Credentials validated successfully!")
                print(f"  Account: {validation_result.account_id}")
                print(f"  Accessible regions: {len(validation_result.accessible_regions)}")
                accounts.append(credentials)
            else:
                print(f"✗ Credential validation failed: {validation_result.error_message}")
                retry = input("Retry this account? (y/N): ").strip().lower()
                if retry not in ['y', 'yes']:
                    continue
                else:
                    # Don't add to accounts list, will retry
                    continue
            
            # Ask for next account
            continue_prompt = input("\nAdd another account? (y/N): ").strip().lower()
            if continue_prompt not in ['y', 'yes']:
                break
        
        if not accounts:
            print("No accounts configured.")
            return []
        
        print(f"\n✓ Successfully configured {len(accounts)} accounts")
        
        # Save to file if requested
        if save_to_file:
            try:
                self.create_secure_credential_file(
                    accounts, 
                    save_to_file, 
                    encrypt=encrypt_file
                )
                print(f"✓ Credentials saved to: {save_to_file}")
            except Exception as e:
                print(f"✗ Failed to save credentials: {e}")
        
        return accounts

    def validate_account_credentials(self, 
                                   credentials: AccountCredentials,
                                   test_regions: bool = True,
                                   test_services: bool = True) -> CredentialValidationResult:
        """
        Validate credentials and test account accessibility.
        
        Args:
            credentials: Account credentials to validate
            test_regions: Whether to test region accessibility
            test_services: Whether to test service availability
            
        Returns:
            Validation result with detailed information
        """
        self.logger.info(f"Validating credentials for account {credentials.account_id}")
        
        # Check cache first
        cache_key = f"{credentials.account_id}:{hash(str(credentials))}"
        if cache_key in self._validation_cache:
            cached_result = self._validation_cache[cache_key]
            # Return cached result if less than 5 minutes old
            if datetime.fromisoformat(cached_result.validation_timestamp.replace('Z', '+00:00')) > \
               datetime.now(timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=5):
                return cached_result
        
        result = CredentialValidationResult(
            is_valid=False,
            validation_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        try:
            # Create session
            session = self._create_session_from_credentials(credentials)
            
            # Test basic connectivity with STS
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            
            result.account_id = identity.get('Account', '')
            result.user_arn = identity.get('Arn', '')
            
            # Validate account ID matches
            if credentials.account_id != result.account_id:
                result.error_message = f"Account ID mismatch. Expected: {credentials.account_id}, Got: {result.account_id}"
                return result
            
            # Get account alias if available
            try:
                iam = session.client('iam')
                aliases = iam.list_account_aliases()
                if aliases.get('AccountAliases'):
                    result.account_alias = aliases['AccountAliases'][0]
            except ClientError:
                pass  # Account alias is optional
            
            # Test region accessibility
            if test_regions:
                result.accessible_regions = self._test_region_accessibility(
                    session, 
                    credentials.regions
                )
            
            # Test service availability
            if test_services:
                result.available_services = self._test_service_availability(
                    session,
                    credentials.services or ['ec2', 's3', 'iam']  # Test common services
                )
            
            # Generate permissions summary
            result.permissions_summary = self._generate_permissions_summary(session)
            
            result.is_valid = True
            self.logger.info(f"Successfully validated credentials for account {credentials.account_id}")
            
        except Exception as e:
            result.error_message = str(e)
            self.logger.warning(f"Credential validation failed for account {credentials.account_id}: {e}")
        
        # Cache result
        self._validation_cache[cache_key] = result
        
        return result

    def setup_cross_account_roles(self, 
                                accounts: List[AccountCredentials],
                                role_name: str = "InvenTagCrossAccountRole",
                                trusted_account_id: Optional[str] = None,
                                external_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Setup cross-account roles for centralized scanning.
        
        Args:
            accounts: List of target accounts
            role_name: Name of the cross-account role to create
            trusted_account_id: Account ID that can assume the role
            external_id: External ID for additional security
            
        Returns:
            Dictionary with setup results for each account
        """
        self.logger.info(f"Setting up cross-account roles: {role_name}")
        
        if not trusted_account_id:
            # Try to get current account ID
            try:
                session = boto3.Session()
                sts = session.client('sts')
                identity = sts.get_caller_identity()
                trusted_account_id = identity['Account']
            except Exception as e:
                raise ValueError(f"Could not determine trusted account ID: {e}")
        
        results = {}
        
        # IAM policy for InvenTag read-only access
        inventag_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:Describe*",
                        "s3:GetBucket*",
                        "s3:ListBucket*",
                        "iam:Get*",
                        "iam:List*",
                        "lambda:Get*",
                        "lambda:List*",
                        "rds:Describe*",
                        "cloudformation:Describe*",
                        "cloudformation:List*",
                        "resource-groups:*",
                        "config:*",
                        "tag:Get*",
                        "pricing:GetProducts"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        # Trust policy
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{trusted_account_id}:root"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        if external_id:
            trust_policy["Statement"][0]["Condition"] = {
                "StringEquals": {
                    "sts:ExternalId": external_id
                }
            }
        
        for credentials in accounts:
            try:
                self.logger.info(f"Setting up role in account {credentials.account_id}")
                
                # Create session for target account
                session = self._create_session_from_credentials(credentials)
                iam = session.client('iam')
                
                # Create role
                try:
                    iam.create_role(
                        RoleName=role_name,
                        AssumeRolePolicyDocument=json.dumps(trust_policy),
                        Description="InvenTag cross-account access role for BOM generation",
                        MaxSessionDuration=3600
                    )
                    self.logger.info(f"Created role {role_name} in account {credentials.account_id}")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'EntityAlreadyExists':
                        self.logger.info(f"Role {role_name} already exists in account {credentials.account_id}")
                    else:
                        raise
                
                # Create policy
                policy_name = f"{role_name}Policy"
                try:
                    policy_response = iam.create_policy(
                        PolicyName=policy_name,
                        PolicyDocument=json.dumps(inventag_policy),
                        Description="InvenTag read-only access policy"
                    )
                    policy_arn = policy_response['Policy']['Arn']
                except ClientError as e:
                    if e.response['Error']['Code'] == 'EntityAlreadyExists':
                        # Get existing policy ARN
                        policy_arn = f"arn:aws:iam::{credentials.account_id}:policy/{policy_name}"
                    else:
                        raise
                
                # Attach policy to role
                iam.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
                
                results[credentials.account_id] = {
                    "success": True,
                    "role_arn": f"arn:aws:iam::{credentials.account_id}:role/{role_name}",
                    "policy_arn": policy_arn,
                    "account_name": credentials.account_name
                }
                
            except Exception as e:
                self.logger.error(f"Failed to setup role in account {credentials.account_id}: {e}")
                results[credentials.account_id] = {
                    "success": False,
                    "error": str(e),
                    "account_name": credentials.account_name
                }
        
        return results

    def _serialize_account_credentials(self, credentials: AccountCredentials) -> Dict[str, Any]:
        """Serialize account credentials for storage."""
        data = asdict(credentials)
        
        # Handle sensitive data
        if self.use_keyring and credentials.secret_access_key:
            # Store sensitive data in keyring
            keyring_key = f"inventag_account_{credentials.account_id}"
            keyring.set_password("inventag", keyring_key, credentials.secret_access_key)
            
            # Mark as using keyring and remove sensitive data
            data['use_keyring'] = True
            data['secret_access_key'] = None
            if credentials.session_token:
                keyring.set_password("inventag", f"{keyring_key}_token", credentials.session_token)
                data['session_token'] = None
        
        return data

    def _load_from_keyring(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Load sensitive data from keyring."""
        account_id = account_data['account_id']
        keyring_key = f"inventag_account_{account_id}"
        
        # Load secret access key
        secret_key = keyring.get_password("inventag", keyring_key)
        if secret_key:
            account_data['secret_access_key'] = secret_key
        
        # Load session token if exists
        session_token = keyring.get_password("inventag", f"{keyring_key}_token")
        if session_token:
            account_data['session_token'] = session_token
        
        # Remove keyring flag
        account_data.pop('use_keyring', None)
        
        return account_data

    def _encrypt_credential_data(self, data: SecureCredentialFile, password: str) -> Dict[str, Any]:
        """Encrypt credential data with password."""
        # Generate key from password
        password_bytes = password.encode()
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        
        # Encrypt data
        fernet = Fernet(key)
        data_json = json.dumps(asdict(data))
        encrypted_data = fernet.encrypt(data_json.encode())
        
        return {
            "version": "1.0",
            "encrypted": True,
            "salt": base64.b64encode(salt).decode(),
            "data": base64.b64encode(encrypted_data).decode()
        }

    def _decrypt_credential_data(self, encrypted_data: Dict[str, Any], password: str) -> SecureCredentialFile:
        """Decrypt credential data with password."""
        # Derive key from password and salt
        password_bytes = password.encode()
        salt = base64.b64decode(encrypted_data['salt'])
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        
        # Decrypt data
        fernet = Fernet(key)
        encrypted_bytes = base64.b64decode(encrypted_data['data'])
        decrypted_data = fernet.decrypt(encrypted_bytes)
        
        # Parse JSON
        data_dict = json.loads(decrypted_data.decode())
        return SecureCredentialFile(**data_dict)

    def _create_session_from_credentials(self, credentials: AccountCredentials) -> boto3.Session:
        """Create boto3 session from credentials."""
        # Try profile first
        if credentials.profile_name:
            return boto3.Session(profile_name=credentials.profile_name)
        
        # Try direct credentials
        if credentials.access_key_id and credentials.secret_access_key:
            return boto3.Session(
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                aws_session_token=credentials.session_token
            )
        
        # Try role assumption
        if credentials.role_arn:
            default_session = boto3.Session()
            sts = default_session.client('sts')
            
            assume_role_kwargs = {
                'RoleArn': credentials.role_arn,
                'RoleSessionName': f'InvenTag-{credentials.account_id}-{int(datetime.now().timestamp())}'
            }
            
            if credentials.external_id:
                assume_role_kwargs['ExternalId'] = credentials.external_id
            
            response = sts.assume_role(**assume_role_kwargs)
            temp_credentials = response['Credentials']
            
            return boto3.Session(
                aws_access_key_id=temp_credentials['AccessKeyId'],
                aws_secret_access_key=temp_credentials['SecretAccessKey'],
                aws_session_token=temp_credentials['SessionToken']
            )
        
        # Fallback to default session
        return boto3.Session()

    def _test_region_accessibility(self, session: boto3.Session, regions: List[str]) -> List[str]:
        """Test which regions are accessible."""
        accessible_regions = []
        
        for region in regions:
            try:
                ec2 = session.client('ec2', region_name=region)
                ec2.describe_regions(RegionNames=[region])
                accessible_regions.append(region)
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') not in ['UnauthorizedOperation', 'AccessDenied']:
                    self.logger.warning(f"Region {region} test failed: {e}")
            except Exception as e:
                self.logger.warning(f"Region {region} test failed: {e}")
        
        return accessible_regions

    def _test_service_availability(self, session: boto3.Session, services: List[str]) -> List[str]:
        """Test which services are available."""
        available_services = []
        
        for service in services:
            try:
                client = session.client(service.lower())
                # Try a simple describe operation
                if service.lower() == 'ec2':
                    client.describe_regions()
                elif service.lower() == 's3':
                    client.list_buckets()
                elif service.lower() == 'iam':
                    client.get_user()
                else:
                    # Generic test - just creating client is often enough
                    pass
                
                available_services.append(service)
            except ClientError as e:
                # Some access denied errors are expected
                if e.response.get('Error', {}).get('Code') not in ['AccessDenied', 'UnauthorizedOperation']:
                    self.logger.debug(f"Service {service} test failed: {e}")
                else:
                    # Service is available but we don't have permissions for the test operation
                    available_services.append(service)
            except Exception as e:
                self.logger.debug(f"Service {service} test failed: {e}")
        
        return available_services

    def _generate_permissions_summary(self, session: boto3.Session) -> Dict[str, Any]:
        """Generate a summary of available permissions."""
        summary = {
            "iam_access": False,
            "ec2_access": False,
            "s3_access": False,
            "config_access": False,
            "resource_groups_access": False,
            "read_only_confirmed": False
        }
        
        # Test IAM access
        try:
            iam = session.client('iam')
            iam.get_user()
            summary["iam_access"] = True
        except ClientError:
            pass
        
        # Test EC2 access
        try:
            ec2 = session.client('ec2')
            ec2.describe_regions()
            summary["ec2_access"] = True
        except ClientError:
            pass
        
        # Test S3 access
        try:
            s3 = session.client('s3')
            s3.list_buckets()
            summary["s3_access"] = True
        except ClientError:
            pass
        
        # Test Config access
        try:
            config = session.client('config')
            config.describe_configuration_recorders()
            summary["config_access"] = True
        except ClientError:
            pass
        
        # Test Resource Groups access
        try:
            rg = session.client('resource-groups')
            rg.list_groups()
            summary["resource_groups_access"] = True
        except ClientError:
            pass
        
        # Determine if we have sufficient read-only access
        summary["read_only_confirmed"] = (
            summary["ec2_access"] and 
            (summary["config_access"] or summary["resource_groups_access"])
        )
        
        return summary

    def _prompt_with_validation(self, prompt: str, validator, error_message: str) -> str:
        """Prompt user with input validation."""
        while True:
            value = input(prompt).strip()
            if not value:
                return ""
            if validator(value):
                return value
            print(f"Error: {error_message}")

    def clear_credential_cache(self):
        """Clear cached credentials and validation results."""
        self._cached_credentials.clear()
        self._validation_cache.clear()
        self.logger.info("Cleared credential cache")

    def list_cached_accounts(self) -> List[str]:
        """List account IDs of cached credentials."""
        return list(self._cached_credentials.keys())

    def get_cached_credentials(self, account_id: str) -> Optional[AccountCredentials]:
        """Get cached credentials for an account."""
        return self._cached_credentials.get(account_id)

    def remove_from_keyring(self, account_id: str):
        """Remove account credentials from keyring."""
        if self.use_keyring:
            keyring_key = f"inventag_account_{account_id}"
            try:
                keyring.delete_password("inventag", keyring_key)
                keyring.delete_password("inventag", f"{keyring_key}_token")
                self.logger.info(f"Removed credentials for account {account_id} from keyring")
            except Exception as e:
                self.logger.warning(f"Failed to remove credentials from keyring: {e}")