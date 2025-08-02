#!/usr/bin/env python3
"""
Unit tests for CredentialManager - Multi-Account Credential Management

Tests for the secure credential management system for multiple AWS accounts.
"""

import pytest
import json
import yaml
import tempfile
import boto3
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, timezone
from pathlib import Path
from botocore.exceptions import ClientError

from inventag.core.credential_manager import (
    CredentialManager,
    CredentialValidationResult,
    SecureCredentialFile
)
from inventag.core.cloud_bom_generator import AccountCredentials


class TestCredentialValidationResult:
    """Test CredentialValidationResult data class."""
    
    def test_credential_validation_result_creation(self):
        """Test creating CredentialValidationResult."""
        result = CredentialValidationResult(
            is_valid=True,
            account_id="123456789012",
            account_alias="test-account",
            user_arn="arn:aws:iam::123456789012:user/test"
        )
        
        assert result.is_valid is True
        assert result.account_id == "123456789012"
        assert result.account_alias == "test-account"
        assert result.user_arn == "arn:aws:iam::123456789012:user/test"
        assert result.accessible_regions == []
        assert result.available_services == []
        assert result.error_message == ""
        assert result.validation_timestamp == ""
        assert result.permissions_summary == {}


class TestSecureCredentialFile:
    """Test SecureCredentialFile data class."""
    
    def test_secure_credential_file_creation(self):
        """Test creating SecureCredentialFile."""
        file_data = SecureCredentialFile(
            encrypted=True,
            accounts=[{"account_id": "123456789012"}],
            global_config={"test": "config"}
        )
        
        assert file_data.version == "1.0"
        assert file_data.encrypted is True
        assert len(file_data.accounts) == 1
        assert file_data.global_config == {"test": "config"}
        assert file_data.metadata == {}


class TestCredentialManager:
    """Test CredentialManager main functionality."""
    
    @pytest.fixture
    def credential_manager(self):
        """CredentialManager instance for testing."""
        return CredentialManager(use_keyring=False)  # Disable keyring for testing
    
    @pytest.fixture
    def sample_credentials(self):
        """Sample account credentials for testing."""
        return [
            AccountCredentials(
                account_id="123456789012",
                account_name="Test Account 1",
                profile_name="test-profile-1"
            ),
            AccountCredentials(
                account_id="123456789013",
                account_name="Test Account 2",
                access_key_id="AKIATEST",
                secret_access_key="secret"
            )
        ]
    
    def test_initialization(self, credential_manager):
        """Test CredentialManager initialization."""
        assert credential_manager.credential_file is None
        assert credential_manager.encryption_password is None
        assert credential_manager.use_keyring is False
        assert credential_manager._cached_credentials == {}
        assert credential_manager._validation_cache == {}
    
    def test_initialization_with_file(self):
        """Test CredentialManager initialization with credential file."""
        manager = CredentialManager(
            credential_file="/path/to/creds.json",
            encryption_password="test123",
            use_keyring=True
        )
        
        assert manager.credential_file == Path("/path/to/creds.json")
        assert manager.encryption_password == "test123"
        assert manager.use_keyring is True
    
    def test_serialize_account_credentials_basic(self, credential_manager):
        """Test serializing account credentials without keyring."""
        credentials = AccountCredentials(
            account_id="123456789012",
            account_name="Test Account",
            profile_name="test-profile"
        )
        
        serialized = credential_manager._serialize_account_credentials(credentials)
        
        assert serialized["account_id"] == "123456789012"
        assert serialized["account_name"] == "Test Account"
        assert serialized["profile_name"] == "test-profile"
        assert "use_keyring" not in serialized
    
    @patch('inventag.core.credential_manager.keyring')
    def test_serialize_account_credentials_with_keyring(self, mock_keyring):
        """Test serializing account credentials with keyring."""
        manager = CredentialManager(use_keyring=True)
        
        credentials = AccountCredentials(
            account_id="123456789012",
            account_name="Test Account",
            access_key_id="AKIATEST",
            secret_access_key="secret",
            session_token="token"
        )
        
        serialized = manager._serialize_account_credentials(credentials)
        
        # Verify keyring calls
        mock_keyring.set_password.assert_any_call(
            "inventag", 
            "inventag_account_123456789012", 
            "secret"
        )
        mock_keyring.set_password.assert_any_call(
            "inventag", 
            "inventag_account_123456789012_token", 
            "token"
        )
        
        # Verify serialized data
        assert serialized["account_id"] == "123456789012"
        assert serialized["use_keyring"] is True
        assert serialized["secret_access_key"] is None
        assert serialized["session_token"] is None
    
    @patch('inventag.core.credential_manager.keyring')
    def test_load_from_keyring(self, mock_keyring, credential_manager):
        """Test loading sensitive data from keyring."""
        mock_keyring.get_password.side_effect = lambda service, key: {
            "inventag_account_123456789012": "secret_from_keyring",
            "inventag_account_123456789012_token": "token_from_keyring"
        }.get(key)
        
        account_data = {
            "account_id": "123456789012",
            "account_name": "Test Account",
            "use_keyring": True,
            "secret_access_key": None,
            "session_token": None
        }
        
        loaded_data = credential_manager._load_from_keyring(account_data)
        
        assert loaded_data["secret_access_key"] == "secret_from_keyring"
        assert loaded_data["session_token"] == "token_from_keyring"
        assert "use_keyring" not in loaded_data
    
    def test_create_session_from_credentials_profile(self, credential_manager):
        """Test creating session from profile credentials."""
        credentials = AccountCredentials(
            account_id="123456789012",
            profile_name="test-profile"
        )
        
        with patch('inventag.core.credential_manager.boto3.Session') as mock_session:
            session = credential_manager._create_session_from_credentials(credentials)
            
            mock_session.assert_called_once_with(profile_name="test-profile")
            assert session == mock_session.return_value
    
    def test_create_session_from_credentials_access_keys(self, credential_manager):
        """Test creating session from access keys."""
        credentials = AccountCredentials(
            account_id="123456789012",
            access_key_id="AKIATEST",
            secret_access_key="secret",
            session_token="token"
        )
        
        with patch('inventag.core.credential_manager.boto3.Session') as mock_session:
            session = credential_manager._create_session_from_credentials(credentials)
            
            mock_session.assert_called_once_with(
                aws_access_key_id="AKIATEST",
                aws_secret_access_key="secret",
                aws_session_token="token"
            )
            assert session == mock_session.return_value
    
    @patch('inventag.core.credential_manager.boto3.Session')
    def test_create_session_from_credentials_role_assumption(self, mock_session_class, credential_manager):
        """Test creating session with role assumption."""
        # Mock default session and STS
        mock_default_session = Mock()
        mock_sts = Mock()
        mock_default_session.client.return_value = mock_sts
        
        # Mock assume role response
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'AKIAASSUMED',
                'SecretAccessKey': 'assumed_secret',
                'SessionToken': 'assumed_token'
            }
        }
        
        # Mock assumed session
        mock_assumed_session = Mock()
        
        mock_session_class.side_effect = [mock_default_session, mock_assumed_session]
        
        credentials = AccountCredentials(
            account_id="123456789012",
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="external123"
        )
        
        session = credential_manager._create_session_from_credentials(credentials)
        
        # Verify assume role call
        mock_sts.assume_role.assert_called_once()
        call_args = mock_sts.assume_role.call_args[1]
        assert call_args['RoleArn'] == "arn:aws:iam::123456789012:role/TestRole"
        assert call_args['ExternalId'] == "external123"
        assert 'RoleSessionName' in call_args
        
        # Verify assumed session creation
        assert mock_session_class.call_count == 2
        second_call = mock_session_class.call_args_list[1]
        assert second_call[1]['aws_access_key_id'] == 'AKIAASSUMED'
        assert second_call[1]['aws_secret_access_key'] == 'assumed_secret'
        assert second_call[1]['aws_session_token'] == 'assumed_token'
        
        assert session == mock_assumed_session
    
    def test_test_region_accessibility(self, credential_manager):
        """Test testing region accessibility."""
        mock_session = Mock()
        mock_ec2_us_east = Mock()
        mock_ec2_us_west = Mock()
        
        # us-east-1 is accessible
        mock_ec2_us_east.describe_regions.return_value = {}
        
        # us-west-2 throws access denied
        mock_ec2_us_west.describe_regions.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'DescribeRegions'
        )
        
        mock_session.client.side_effect = [mock_ec2_us_east, mock_ec2_us_west]
        
        accessible = credential_manager._test_region_accessibility(
            mock_session, 
            ["us-east-1", "us-west-2"]
        )
        
        assert accessible == ["us-east-1"]
    
    def test_test_service_availability(self, credential_manager):
        """Test testing service availability."""
        mock_session = Mock()
        
        # Mock clients
        mock_ec2 = Mock()
        mock_s3 = Mock()
        mock_iam = Mock()
        
        # EC2 works
        mock_ec2.describe_regions.return_value = {}
        
        # S3 works
        mock_s3.list_buckets.return_value = {}
        
        # IAM throws access denied (but service is available)
        mock_iam.get_user.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'GetUser'
        )
        
        mock_session.client.side_effect = [mock_ec2, mock_s3, mock_iam]
        
        available = credential_manager._test_service_availability(
            mock_session,
            ['ec2', 's3', 'iam']
        )
        
        assert set(available) == {'ec2', 's3', 'iam'}
    
    def test_generate_permissions_summary(self, credential_manager):
        """Test generating permissions summary."""
        mock_session = Mock()
        
        # Mock successful IAM access
        mock_iam = Mock()
        mock_iam.get_user.return_value = {}
        
        # Mock successful EC2 access
        mock_ec2 = Mock()
        mock_ec2.describe_regions.return_value = {}
        
        # Mock failed S3 access
        mock_s3 = Mock()
        mock_s3.list_buckets.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'ListBuckets'
        )
        
        # Mock successful Config access
        mock_config = Mock()
        mock_config.describe_configuration_recorders.return_value = {}
        
        # Mock failed Resource Groups access
        mock_rg = Mock()
        mock_rg.list_groups.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'ListGroups'
        )
        
        mock_session.client.side_effect = [mock_iam, mock_ec2, mock_s3, mock_config, mock_rg]
        
        summary = credential_manager._generate_permissions_summary(mock_session)
        
        assert summary["iam_access"] is True
        assert summary["ec2_access"] is True
        assert summary["s3_access"] is False
        assert summary["config_access"] is True
        assert summary["resource_groups_access"] is False
        assert summary["read_only_confirmed"] is True  # EC2 + Config access
    
    @patch('inventag.core.credential_manager.boto3.Session')
    def test_validate_account_credentials_success(self, mock_session_class, credential_manager):
        """Test successful credential validation."""
        # Mock session and clients
        mock_session = Mock()
        mock_sts = Mock()
        mock_iam = Mock()
        mock_ec2 = Mock()
        mock_s3 = Mock()
        mock_config = Mock()
        mock_rg = Mock()
        
        mock_session.client.side_effect = lambda service, **kwargs: {
            'sts': mock_sts,
            'iam': mock_iam,
            'ec2': mock_ec2,
            's3': mock_s3,
            'config': mock_config,
            'resource-groups': mock_rg
        }[service]
        
        # Mock STS response
        mock_sts.get_caller_identity.return_value = {
            'Account': '123456789012',
            'UserId': 'AIDATEST',
            'Arn': 'arn:aws:iam::123456789012:user/test'
        }
        
        # Mock IAM response
        mock_iam.list_account_aliases.return_value = {
            'AccountAliases': ['test-account']
        }
        mock_iam.get_user.return_value = {}
        
        # Mock EC2 response for region testing
        mock_ec2.describe_regions.return_value = {}
        
        # Mock S3 response for service testing
        mock_s3.list_buckets.return_value = {}
        
        # Mock Config response for permissions summary
        mock_config.describe_configuration_recorders.return_value = {}
        
        # Mock Resource Groups response for permissions summary
        mock_rg.list_groups.return_value = {}
        
        mock_session_class.return_value = mock_session
        
        credentials = AccountCredentials(
            account_id="123456789012",
            profile_name="test-profile",
            regions=["us-east-1"]
        )
        
        with patch.object(credential_manager, '_create_session_from_credentials', return_value=mock_session):
            result = credential_manager.validate_account_credentials(credentials)
        
        assert result.is_valid is True
        assert result.account_id == "123456789012"
        assert result.account_alias == "test-account"
        assert result.user_arn == "arn:aws:iam::123456789012:user/test"
        assert result.error_message == ""
        assert "us-east-1" in result.accessible_regions
    
    def test_validate_account_credentials_account_mismatch(self, credential_manager):
        """Test credential validation with account ID mismatch."""
        mock_session = Mock()
        mock_sts = Mock()
        mock_session.client.return_value = mock_sts
        
        # Mock STS response with different account ID
        mock_sts.get_caller_identity.return_value = {
            'Account': '999999999999',  # Different account
            'UserId': 'AIDATEST',
            'Arn': 'arn:aws:iam::999999999999:user/test'
        }
        
        credentials = AccountCredentials(
            account_id="123456789012",
            profile_name="test-profile"
        )
        
        with patch.object(credential_manager, '_create_session_from_credentials', return_value=mock_session):
            result = credential_manager.validate_account_credentials(credentials)
        
        assert result.is_valid is False
        assert "Account ID mismatch" in result.error_message
        assert result.account_id == "999999999999"
    
    def test_validate_account_credentials_failure(self, credential_manager):
        """Test credential validation failure."""
        credentials = AccountCredentials(
            account_id="123456789012",
            profile_name="invalid-profile"
        )
        
        with patch.object(credential_manager, '_create_session_from_credentials', 
                         side_effect=Exception("Invalid credentials")):
            result = credential_manager.validate_account_credentials(credentials)
        
        assert result.is_valid is False
        assert result.error_message == "Invalid credentials"
    
    def test_create_secure_credential_file_unencrypted(self, credential_manager, sample_credentials, tmp_path):
        """Test creating unencrypted credential file."""
        output_file = tmp_path / "credentials.json"
        
        created_file = credential_manager.create_secure_credential_file(
            sample_credentials,
            str(output_file),
            encrypt=False
        )
        
        assert created_file == str(output_file)
        assert output_file.exists()
        
        # Verify file content
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        assert data["version"] == "1.0"
        assert data["encrypted"] is False
        assert len(data["accounts"]) == 2
        assert data["accounts"][0]["account_id"] == "123456789012"
        assert data["accounts"][1]["account_id"] == "123456789013"
    
    def test_create_secure_credential_file_yaml(self, credential_manager, sample_credentials, tmp_path):
        """Test creating YAML credential file."""
        output_file = tmp_path / "credentials.yaml"
        
        created_file = credential_manager.create_secure_credential_file(
            sample_credentials,
            str(output_file),
            encrypt=False
        )
        
        assert created_file == str(output_file)
        assert output_file.exists()
        
        # Verify file content
        with open(output_file, 'r') as f:
            data = yaml.safe_load(f)
        
        assert data["version"] == "1.0"
        assert data["encrypted"] is False
        assert len(data["accounts"]) == 2
    
    @patch('inventag.core.credential_manager.getpass.getpass')
    def test_create_secure_credential_file_encrypted(self, mock_getpass, credential_manager, sample_credentials, tmp_path):
        """Test creating encrypted credential file."""
        mock_getpass.side_effect = ["password123", "password123"]  # Password and confirmation
        
        output_file = tmp_path / "credentials.json"
        
        created_file = credential_manager.create_secure_credential_file(
            sample_credentials,
            str(output_file),
            encrypt=True
        )
        
        assert created_file == str(output_file)
        assert output_file.exists()
        
        # Verify file is encrypted
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        assert data["encrypted"] is True
        assert "salt" in data
        assert "data" in data
        assert "accounts" not in data  # Should be encrypted
    
    def test_load_credential_file_unencrypted(self, credential_manager, sample_credentials, tmp_path):
        """Test loading unencrypted credential file."""
        # Create test file
        output_file = tmp_path / "credentials.json"
        credential_manager.create_secure_credential_file(
            sample_credentials,
            str(output_file),
            encrypt=False
        )
        
        # Load credentials
        loaded_credentials = credential_manager.load_credential_file(str(output_file))
        
        assert len(loaded_credentials) == 2
        assert loaded_credentials[0].account_id == "123456789012"
        assert loaded_credentials[1].account_id == "123456789013"
        
        # Verify caching
        assert len(credential_manager._cached_credentials) == 2
        assert "123456789012" in credential_manager._cached_credentials
        assert "123456789013" in credential_manager._cached_credentials
    
    def test_load_credential_file_not_found(self, credential_manager):
        """Test loading non-existent credential file."""
        with pytest.raises(FileNotFoundError):
            credential_manager.load_credential_file("nonexistent.json")
    
    @patch('inventag.core.credential_manager.getpass.getpass')
    def test_load_credential_file_encrypted(self, mock_getpass, credential_manager, sample_credentials, tmp_path):
        """Test loading encrypted credential file."""
        # Create encrypted file
        mock_getpass.side_effect = ["password123", "password123", "password123"]  # Create + load
        
        output_file = tmp_path / "credentials.json"
        credential_manager.create_secure_credential_file(
            sample_credentials,
            str(output_file),
            encrypt=True
        )
        
        # Load credentials
        loaded_credentials = credential_manager.load_credential_file(str(output_file))
        
        assert len(loaded_credentials) == 2
        assert loaded_credentials[0].account_id == "123456789012"
        assert loaded_credentials[1].account_id == "123456789013"
    
    def test_clear_credential_cache(self, credential_manager):
        """Test clearing credential cache."""
        # Add some cached data
        credential_manager._cached_credentials["test"] = Mock()
        credential_manager._validation_cache["test"] = Mock()
        
        credential_manager.clear_credential_cache()
        
        assert credential_manager._cached_credentials == {}
        assert credential_manager._validation_cache == {}
    
    def test_list_cached_accounts(self, credential_manager):
        """Test listing cached account IDs."""
        # Add some cached credentials
        credential_manager._cached_credentials["123456789012"] = Mock()
        credential_manager._cached_credentials["123456789013"] = Mock()
        
        cached_accounts = credential_manager.list_cached_accounts()
        
        assert set(cached_accounts) == {"123456789012", "123456789013"}
    
    def test_get_cached_credentials(self, credential_manager, sample_credentials):
        """Test getting cached credentials."""
        # Cache some credentials
        credential_manager._cached_credentials["123456789012"] = sample_credentials[0]
        
        cached_creds = credential_manager.get_cached_credentials("123456789012")
        assert cached_creds == sample_credentials[0]
        
        # Test non-existent account
        assert credential_manager.get_cached_credentials("999999999999") is None
    
    @patch('inventag.core.credential_manager.keyring')
    def test_remove_from_keyring(self, mock_keyring, credential_manager):
        """Test removing credentials from keyring."""
        manager = CredentialManager(use_keyring=True)
        
        manager.remove_from_keyring("123456789012")
        
        mock_keyring.delete_password.assert_any_call(
            "inventag", 
            "inventag_account_123456789012"
        )
        mock_keyring.delete_password.assert_any_call(
            "inventag", 
            "inventag_account_123456789012_token"
        )


class TestCredentialManagerIntegration:
    """Integration tests for CredentialManager."""
    
    @patch('inventag.core.credential_manager.input')
    @patch('inventag.core.credential_manager.getpass.getpass')
    @patch.object(CredentialManager, 'validate_account_credentials')
    def test_interactive_credential_setup_success(self, mock_validate, mock_getpass, mock_input):
        """Test successful interactive credential setup."""
        # Mock user inputs
        mock_input.side_effect = [
            "123456789012",  # Account ID
            "Test Account",  # Account name
            "1",  # Auth method (profile)
            "test-profile",  # Profile name
            "",  # Regions (default)
            "",  # Services (all)
            "",  # Tag key (finish)
            "n"  # No more accounts
        ]
        
        # Mock validation success
        mock_validate.return_value = CredentialValidationResult(
            is_valid=True,
            account_id="123456789012"
        )
        
        manager = CredentialManager(use_keyring=False)
        
        accounts = manager.interactive_credential_setup()
        
        assert len(accounts) == 1
        assert accounts[0].account_id == "123456789012"
        assert accounts[0].account_name == "Test Account"
        assert accounts[0].profile_name == "test-profile"
    
    @patch('inventag.core.credential_manager.input')
    @patch('inventag.core.credential_manager.getpass.getpass')
    @patch.object(CredentialManager, 'validate_account_credentials')
    def test_interactive_credential_setup_validation_failure(self, mock_validate, mock_getpass, mock_input):
        """Test interactive setup with validation failure."""
        # Mock user inputs
        mock_input.side_effect = [
            "123456789012",  # Account ID
            "Test Account",  # Account name
            "1",  # Auth method (profile)
            "invalid-profile",  # Profile name
            "",  # Regions (default)
            "",  # Services (all)
            "",  # Tag key (finish)
            "n",  # Don't retry
            ""   # No more accounts (empty account ID)
        ]
        
        # Mock validation failure
        mock_validate.return_value = CredentialValidationResult(
            is_valid=False,
            error_message="Invalid profile"
        )
        
        manager = CredentialManager(use_keyring=False)
        
        accounts = manager.interactive_credential_setup()
        
        assert len(accounts) == 0


if __name__ == "__main__":
    pytest.main([__file__])