#!/usr/bin/env python3
"""
Unit tests for CloudBOMGenerator - Multi-Account Orchestrator

Tests for the main orchestrator that coordinates comprehensive resource discovery,
compliance checking, and BOM document generation across multiple AWS accounts.
"""

import pytest
import boto3
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path

from inventag.core.cloud_bom_generator import (
    CloudBOMGenerator,
    MultiAccountConfig,
    AccountCredentials,
    AccountContext,
)
from inventag.reporting.bom_processor import BOMProcessingConfig


class TestAccountCredentials:
    """Test AccountCredentials data class."""

    def test_account_credentials_creation(self):
        """Test creating AccountCredentials with minimal data."""
        creds = AccountCredentials(account_id="123456789012", account_name="Test Account")

        assert creds.account_id == "123456789012"
        assert creds.account_name == "Test Account"
        assert creds.regions == ["us-east-1"]  # Default
        assert creds.services == []  # Default empty means all services
        assert creds.tags == {}  # Default empty

    def test_account_credentials_with_all_fields(self):
        """Test creating AccountCredentials with all fields."""
        creds = AccountCredentials(
            account_id="123456789012",
            account_name="Test Account",
            access_key_id="AKIATEST",
            secret_access_key="secret",
            session_token="token",
            profile_name="test-profile",
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="external123",
            regions=["us-east-1", "us-west-2"],
            services=["EC2", "S3"],
            tags={"Environment": "test"},
        )

        assert creds.account_id == "123456789012"
        assert creds.account_name == "Test Account"
        assert creds.access_key_id == "AKIATEST"
        assert creds.secret_access_key == "secret"
        assert creds.session_token == "token"
        assert creds.profile_name == "test-profile"
        assert creds.role_arn == "arn:aws:iam::123456789012:role/TestRole"
        assert creds.external_id == "external123"
        assert creds.regions == ["us-east-1", "us-west-2"]
        assert creds.services == ["EC2", "S3"]
        assert creds.tags == {"Environment": "test"}


class TestAccountContext:
    """Test AccountContext data class."""

    def test_account_context_creation(self):
        """Test creating AccountContext."""
        creds = AccountCredentials(account_id="123456789012")
        session = Mock(spec=boto3.Session)
        caller_identity = {"Account": "123456789012", "UserId": "test"}

        context = AccountContext(
            credentials=creds, session=session, caller_identity=caller_identity
        )

        assert context.credentials == creds
        assert context.session == session
        assert context.caller_identity == caller_identity
        assert context.accessible_regions == []
        assert context.discovered_services == []
        assert context.processing_errors == []
        assert context.processing_warnings == []
        assert context.resource_count == 0
        assert context.processing_time_seconds == 0.0


class TestMultiAccountConfig:
    """Test MultiAccountConfig data class."""

    def test_multi_account_config_defaults(self):
        """Test MultiAccountConfig with default values."""
        config = MultiAccountConfig()

        assert config.accounts == []
        assert config.cross_account_role_name == "InvenTagCrossAccountRole"
        assert config.parallel_account_processing is True
        assert config.max_concurrent_accounts == 4
        assert config.account_processing_timeout == 1800
        assert config.consolidate_accounts is True
        assert config.generate_per_account_reports is False
        assert config.enable_state_management is True
        assert config.enable_delta_detection is True
        assert config.enable_changelog_generation is True
        assert isinstance(config.bom_processing_config, BOMProcessingConfig)
        assert config.output_directory == "bom_output"
        assert config.credential_validation_timeout == 30

    def test_multi_account_config_with_accounts(self):
        """Test MultiAccountConfig with accounts."""
        accounts = [
            AccountCredentials(account_id="123456789012", account_name="Account 1"),
            AccountCredentials(account_id="123456789013", account_name="Account 2"),
        ]

        config = MultiAccountConfig(
            accounts=accounts,
            parallel_account_processing=False,
            max_concurrent_accounts=2,
        )

        assert len(config.accounts) == 2
        assert config.accounts[0].account_id == "123456789012"
        assert config.accounts[1].account_id == "123456789013"
        assert config.parallel_account_processing is False
        assert config.max_concurrent_accounts == 2


class TestCloudBOMGenerator:
    """Test CloudBOMGenerator main orchestrator."""

    @pytest.fixture
    def sample_accounts(self):
        """Sample account credentials for testing."""
        return [
            AccountCredentials(
                account_id="123456789012",
                account_name="Test Account 1",
                profile_name="test-profile-1",
            ),
            AccountCredentials(
                account_id="123456789013",
                account_name="Test Account 2",
                access_key_id="AKIATEST",
                secret_access_key="secret",
            ),
        ]

    @pytest.fixture
    def sample_config(self, sample_accounts):
        """Sample MultiAccountConfig for testing."""
        return MultiAccountConfig(
            accounts=sample_accounts,
            parallel_account_processing=False,  # Easier to test sequentially
            output_directory="test_output",
        )

    @pytest.fixture
    def generator(self, sample_config):
        """CloudBOMGenerator instance for testing."""
        with patch("inventag.core.cloud_bom_generator.Path.mkdir"):
            return CloudBOMGenerator(sample_config)

    def test_initialization(self, generator, sample_config):
        """Test CloudBOMGenerator initialization."""
        assert generator.config == sample_config
        assert generator.account_contexts == {}
        assert generator.consolidated_resources == []
        assert generator._processing_stats["total_accounts"] == 0
        assert generator._processing_stats["successful_accounts"] == 0
        assert generator._processing_stats["failed_accounts"] == 0

    @patch("inventag.core.cloud_bom_generator.boto3.Session")
    def test_create_account_session_with_profile(self, mock_session_class, generator):
        """Test creating session with AWS profile."""
        mock_session = Mock()
        mock_sts = Mock()
        mock_session.client.return_value = mock_sts
        mock_session_class.return_value = mock_session

        credentials = AccountCredentials(account_id="123456789012", profile_name="test-profile")

        session = generator._create_account_session(credentials)

        mock_session_class.assert_called_with(profile_name="test-profile")
        mock_session.client.assert_called_with("sts")
        mock_sts.get_caller_identity.assert_called_once()
        assert session == mock_session

    @patch("inventag.core.cloud_bom_generator.boto3.Session")
    def test_create_account_session_with_access_keys(self, mock_session_class, generator):
        """Test creating session with access keys."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        credentials = AccountCredentials(
            account_id="123456789012",
            access_key_id="AKIATEST",
            secret_access_key="secret",
            session_token="token",
        )

        session = generator._create_account_session(credentials)

        mock_session_class.assert_called_with(
            aws_access_key_id="AKIATEST",
            aws_secret_access_key="secret",
            aws_session_token="token",
        )
        assert session == mock_session

    @patch("inventag.core.cloud_bom_generator.boto3.Session")
    def test_create_account_session_with_role_assumption(self, mock_session_class, generator):
        """Test creating session with role assumption."""
        # Mock default session
        mock_default_session = Mock()
        mock_sts = Mock()
        mock_default_session.client.return_value = mock_sts

        # Mock assume role response
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIAASSUMED",
                "SecretAccessKey": "assumed_secret",
                "SessionToken": "assumed_token",
            }
        }

        # Mock assumed session
        mock_assumed_session = Mock()

        mock_session_class.side_effect = [mock_default_session, mock_assumed_session]

        credentials = AccountCredentials(
            account_id="123456789012",
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="external123",
        )

        session = generator._create_account_session(credentials)

        # Verify assume role call
        mock_sts.assume_role.assert_called_once()
        call_args = mock_sts.assume_role.call_args[1]
        assert call_args["RoleArn"] == "arn:aws:iam::123456789012:role/TestRole"
        assert call_args["ExternalId"] == "external123"
        assert "RoleSessionName" in call_args

        # Verify assumed session creation
        assert mock_session_class.call_count == 2
        second_call = mock_session_class.call_args_list[1]
        assert second_call[1]["aws_access_key_id"] == "AKIAASSUMED"
        assert second_call[1]["aws_secret_access_key"] == "assumed_secret"
        assert second_call[1]["aws_session_token"] == "assumed_token"

        assert session == mock_assumed_session

    def test_get_caller_identity(self, generator):
        """Test getting caller identity."""
        mock_session = Mock()
        mock_sts = Mock()
        mock_session.client.return_value = mock_sts

        mock_sts.get_caller_identity.return_value = {
            "UserId": "AIDATEST",
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
        }

        identity = generator._get_caller_identity(mock_session)

        assert identity["UserId"] == "AIDATEST"
        assert identity["Account"] == "123456789012"
        assert identity["Arn"] == "arn:aws:iam::123456789012:user/test"
        assert "retrieved_at" in identity

    def test_test_accessible_regions(self, generator):
        """Test testing accessible regions."""
        mock_session = Mock()
        mock_ec2_us_east = Mock()
        mock_ec2_us_west = Mock()

        # us-east-1 is accessible
        mock_ec2_us_east.describe_regions.return_value = {}

        # us-west-2 throws access denied
        from botocore.exceptions import ClientError

        mock_ec2_us_west.describe_regions.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "DescribeRegions"
        )

        mock_session.client.side_effect = [mock_ec2_us_east, mock_ec2_us_west]

        accessible = generator._test_accessible_regions(mock_session, ["us-east-1", "us-west-2"])

        assert accessible == ["us-east-1"]

    @patch("inventag.core.cloud_bom_generator.AWSResourceInventory")
    def test_discover_account_resources(self, mock_inventory_class, generator):
        """Test discovering resources for a single account."""
        # Mock inventory
        mock_inventory = Mock()
        mock_inventory.discover_all_resources.return_value = [
            {
                "id": "i-123456789",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
            },
            {
                "id": "bucket-test",
                "service": "S3",
                "type": "Bucket",
                "region": "us-east-1",
            },
        ]
        mock_inventory_class.return_value = mock_inventory

        # Create account context
        credentials = AccountCredentials(account_id="123456789012", account_name="Test Account")
        session = Mock()
        context = AccountContext(
            credentials=credentials,
            session=session,
            caller_identity={"Account": "123456789012"},
            accessible_regions=["us-east-1"],
        )

        resources = generator._discover_account_resources("123456789012", context)

        # Verify inventory initialization
        mock_inventory_class.assert_called_once_with(
            session=session,
            regions=["us-east-1"],
            services=None,  # Empty list becomes None for all services
            tag_filters={},
        )

        # Verify resources
        assert len(resources) == 2

        # Check that account context was added
        for resource in resources:
            assert resource["source_account_id"] == "123456789012"
            assert resource["source_account_name"] == "Test Account"
            assert "discovery_timestamp" in resource

        # Check context updates
        assert context.resource_count == 2
        assert context.processing_time_seconds > 0
        assert set(context.discovered_services) == {"EC2", "S3"}

    def test_consolidate_account_resources(self, generator):
        """Test consolidating resources from multiple accounts."""
        resources = [
            {
                "id": "i-123456789",
                "service": "EC2",
                "source_account_id": "123456789012",
                "source_account_name": "Account 1",
            },
            {
                "id": "bucket-test",
                "service": "S3",
                "source_account_id": "123456789013",
                "source_account_name": "Account 2",
            },
            {
                "id": "i-987654321",
                "service": "EC2",
                "source_account_id": "123456789012",
                "source_account_name": "Account 1",
            },
        ]

        consolidated = generator._consolidate_account_resources(resources)

        # Should return all resources with consolidation metadata
        assert len(consolidated) == 3

        for resource in consolidated:
            assert "consolidation_timestamp" in resource
            assert resource["total_accounts_in_consolidation"] == 2

        # Should update consolidated_resources attribute
        assert generator.consolidated_resources == consolidated

    @patch("inventag.core.cloud_bom_generator.ComprehensiveTagComplianceChecker")
    def test_run_compliance_analysis(self, mock_compliance_class, generator):
        """Test running compliance analysis."""
        # Setup account context with session
        session = Mock()
        context = AccountContext(
            credentials=AccountCredentials(account_id="123456789012"),
            session=session,
            caller_identity={},
        )
        generator.account_contexts["123456789012"] = context

        # Mock compliance checker
        mock_compliance = Mock()
        mock_compliance.check_resources_compliance.return_value = {
            "total_resources": 10,
            "compliant_resources": 8,
            "non_compliant_resources": 2,
        }
        mock_compliance_class.return_value = mock_compliance

        resources = [{"id": "test-resource"}]
        policies = {"test": "policy"}

        result = generator._run_compliance_analysis(resources, policies)

        # Verify compliance checker initialization
        mock_compliance_class.assert_called_once_with(session=session, policies=policies)

        # Verify compliance analysis
        mock_compliance.check_resources_compliance.assert_called_once_with(resources)

        # Check result structure
        assert result["total_resources"] == 10
        assert result["compliant_resources"] == 8
        assert result["non_compliant_resources"] == 2
        assert "multi_account_analysis" in result
        assert result["multi_account_analysis"]["total_accounts"] == 1

    def test_from_credentials_file_json(self, tmp_path):
        """Test creating CloudBOMGenerator from JSON credentials file."""
        # Create test credentials file
        credentials_data = {
            "accounts": [
                {
                    "account_id": "123456789012",
                    "account_name": "Test Account 1",
                    "profile_name": "test-profile-1",
                },
                {
                    "account_id": "123456789013",
                    "account_name": "Test Account 2",
                    "access_key_id": "AKIATEST",
                    "secret_access_key": "secret",
                },
            ],
            "config": {
                "parallel_account_processing": False,
                "max_concurrent_accounts": 2,
            },
        }

        credentials_file = tmp_path / "credentials.json"
        with open(credentials_file, "w") as f:
            json.dump(credentials_data, f)

        with patch("inventag.core.cloud_bom_generator.Path.mkdir"):
            generator = CloudBOMGenerator.from_credentials_file(str(credentials_file))

        assert len(generator.config.accounts) == 2
        assert generator.config.accounts[0].account_id == "123456789012"
        assert generator.config.accounts[1].account_id == "123456789013"
        assert generator.config.parallel_account_processing is False
        assert generator.config.max_concurrent_accounts == 2

    def test_from_credentials_file_yaml(self, tmp_path):
        """Test creating CloudBOMGenerator from YAML credentials file."""
        credentials_content = """
accounts:
  - account_id: "123456789012"
    account_name: "Test Account 1"
    profile_name: "test-profile-1"
  - account_id: "123456789013"
    account_name: "Test Account 2"
    access_key_id: "AKIATEST"
    secret_access_key: "secret"

config:
  parallel_account_processing: false
  max_concurrent_accounts: 2
"""

        credentials_file = tmp_path / "credentials.yaml"
        with open(credentials_file, "w") as f:
            f.write(credentials_content)

        with patch("inventag.core.cloud_bom_generator.Path.mkdir"):
            generator = CloudBOMGenerator.from_credentials_file(str(credentials_file))

        assert len(generator.config.accounts) == 2
        assert generator.config.accounts[0].account_id == "123456789012"
        assert generator.config.accounts[1].account_id == "123456789013"
        assert generator.config.parallel_account_processing is False
        assert generator.config.max_concurrent_accounts == 2

    def test_from_credentials_file_not_found(self):
        """Test error when credentials file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            CloudBOMGenerator.from_credentials_file("nonexistent.json")

    def test_from_credentials_file_unsupported_format(self, tmp_path):
        """Test error with unsupported file format."""
        credentials_file = tmp_path / "credentials.txt"
        credentials_file.write_text("invalid format")

        with pytest.raises(ValueError, match="Unsupported credentials file format"):
            CloudBOMGenerator.from_credentials_file(str(credentials_file))


class TestCloudBOMGeneratorIntegration:
    """Integration tests for CloudBOMGenerator."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        mocks = {}
        with patch(
            "inventag.core.cloud_bom_generator.AWSResourceInventory"
        ) as mock_inventory, patch(
            "inventag.core.cloud_bom_generator.ComprehensiveTagComplianceChecker"
        ) as mock_compliance, patch(
            "inventag.core.cloud_bom_generator.BOMConverter"
        ) as mock_converter, patch(
            "inventag.core.cloud_bom_generator.BOMDataProcessor"
        ) as mock_processor, patch(
            "inventag.core.cloud_bom_generator.StateManager"
        ) as mock_state, patch(
            "inventag.core.cloud_bom_generator.DeltaDetector"
        ) as mock_delta, patch(
            "inventag.core.cloud_bom_generator.ChangelogGenerator"
        ) as mock_changelog:

            mocks["AWSResourceInventory"] = mock_inventory
            mocks["ComprehensiveTagComplianceChecker"] = mock_compliance
            mocks["BOMConverter"] = mock_converter
            mocks["BOMDataProcessor"] = mock_processor
            mocks["StateManager"] = mock_state
            mocks["DeltaDetector"] = mock_delta
            mocks["ChangelogGenerator"] = mock_changelog
            yield mocks

    @patch("inventag.core.cloud_bom_generator.Path.mkdir")
    def test_generate_multi_account_bom_success(self, mock_mkdir, mock_dependencies):
        """Test successful multi-account BOM generation."""
        # Setup
        accounts = [
            AccountCredentials(
                account_id="123456789012",
                account_name="Test Account",
                profile_name="test-profile",
            )
        ]
        config = MultiAccountConfig(accounts=accounts, parallel_account_processing=False)

        generator = CloudBOMGenerator(config)

        # Mock session creation and validation
        mock_session = Mock()
        mock_sts = Mock()
        mock_session.client.return_value = mock_sts
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "UserId": "test",
            "Arn": "test",
        }

        # Mock EC2 for region testing
        mock_ec2 = Mock()
        mock_ec2.describe_regions.return_value = {}

        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "ec2": mock_ec2,
        }[service]

        # Mock resource discovery
        mock_inventory = mock_dependencies["AWSResourceInventory"].return_value
        mock_inventory.discover_all_resources.return_value = [
            {
                "id": "i-123456789",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
            }
        ]

        # Mock BOM processing
        mock_bom_processor = mock_dependencies["BOMDataProcessor"].return_value
        mock_bom_data = Mock()
        mock_bom_data.resources = [{"id": "i-123456789"}]
        mock_bom_data.generation_metadata = {}
        mock_bom_data.processing_statistics = {}
        mock_bom_data.compliance_summary = {}
        mock_bom_processor.process_inventory_data.return_value = mock_bom_data

        # Mock BOM converter
        mock_bom_converter = mock_dependencies["BOMConverter"].return_value

        with patch.object(generator, "_create_account_session", return_value=mock_session):
            result = generator.generate_multi_account_bom(
                output_formats=["excel"], compliance_policies=None
            )

        # Verify success
        assert result["success"] is True
        assert result["processing_statistics"]["total_accounts"] == 1
        assert result["processing_statistics"]["successful_accounts"] == 1
        assert result["processing_statistics"]["failed_accounts"] == 0

        # Verify BOM generation was called
        mock_bom_converter.generate_excel_bom.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
