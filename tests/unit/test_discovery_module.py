#!/usr/bin/env python3
"""
Unit Tests for inventag.discovery Module

This module provides comprehensive unit testing for the discovery module
with mock AWS responses and error handling scenarios.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import pytest
import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock, call
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from inventag.discovery import AWSResourceInventory
except ImportError:
    pytest.skip("Discovery module not available", allow_module_level=True)


class TestAWSResourceInventoryCore:
    """Test core functionality of AWSResourceInventory"""

    @pytest.fixture
    def mock_session(self):
        """Mock boto3 session"""
        with patch("boto3.Session") as mock:
            yield mock

    @pytest.fixture
    def inventory(self, mock_session):
        """Create inventory instance with mocked session"""
        return AWSResourceInventory(regions=["us-east-1"])

    def test_initialization_with_regions(self, mock_session):
        """Test initialization with specific regions"""
        regions = ["us-east-1", "us-west-2", "eu-west-1"]
        inventory = AWSResourceInventory(regions=regions)
        assert inventory.regions == regions

    def test_initialization_without_regions(self, mock_session):
        """Test initialization without regions gets all available regions"""
        # Mock EC2 client response
        mock_ec2 = Mock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "us-west-2"},
                {"RegionName": "eu-west-1"},
            ]
        }
        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory()
        assert "us-east-1" in inventory.regions
        assert "us-west-2" in inventory.regions
        assert "eu-west-1" in inventory.regions

    def test_initialization_region_discovery_failure(self, mock_session):
        """Test fallback when region discovery fails"""
        # Mock EC2 client to raise exception
        mock_ec2 = Mock()
        mock_ec2.describe_regions.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedOperation", "Message": "Access denied"}},
            "DescribeRegions",
        )
        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory()
        # Should fall back to default regions
        assert len(inventory.regions) > 0
        assert "us-east-1" in inventory.regions

    def test_logger_initialization(self, inventory):
        """Test that logger is properly initialized"""
        assert hasattr(inventory, "logger")
        assert inventory.logger is not None

    def test_resources_list_initialization(self, inventory):
        """Test that resources list is initialized"""
        assert hasattr(inventory, "resources")
        assert isinstance(inventory.resources, list)
        assert len(inventory.resources) == 0


class TestAWSResourceDiscovery:
    """Test AWS resource discovery functionality"""

    @pytest.fixture
    def mock_session(self):
        """Mock boto3 session with comprehensive service mocks"""
        with patch("boto3.Session") as mock_session:
            # Create mock clients for all services
            mock_clients = {
                "ec2": Mock(),
                "s3": Mock(),
                "rds": Mock(),
                "lambda": Mock(),
                "iam": Mock(),
                "cloudformation": Mock(),
                "ecs": Mock(),
                "eks": Mock(),
                "cloudwatch": Mock(),
                "dynamodb": Mock(),
                "sns": Mock(),
                "sqs": Mock(),
            }

            # Configure default empty responses
            self._configure_empty_responses(mock_clients)

            # Mock client factory
            def client_factory(service_name, **kwargs):
                return mock_clients.get(service_name, Mock())

            mock_session.return_value.client.side_effect = client_factory
            yield mock_session, mock_clients

    def _configure_empty_responses(self, mock_clients):
        """Configure empty responses for all service mocks"""
        # EC2 responses
        mock_clients["ec2"].describe_instances.return_value = {"Reservations": []}
        mock_clients["ec2"].describe_volumes.return_value = {"Volumes": []}
        mock_clients["ec2"].describe_security_groups.return_value = {"SecurityGroups": []}
        mock_clients["ec2"].describe_vpcs.return_value = {"Vpcs": []}
        mock_clients["ec2"].describe_subnets.return_value = {"Subnets": []}
        mock_clients["ec2"].describe_regions.return_value = {
            "Regions": [{"RegionName": "us-east-1"}]
        }

        # S3 responses
        mock_clients["s3"].list_buckets.return_value = {"Buckets": []}

        # RDS responses
        mock_clients["rds"].describe_db_instances.return_value = {"DBInstances": []}
        mock_clients["rds"].describe_db_clusters.return_value = {"DBClusters": []}

        # Lambda responses
        mock_clients["lambda"].list_functions.return_value = {"Functions": []}

        # IAM responses
        mock_clients["iam"].list_roles.return_value = {"Roles": []}
        mock_clients["iam"].list_users.return_value = {"Users": []}
        mock_clients["iam"].list_policies.return_value = {"Policies": []}

        # CloudFormation responses
        mock_clients["cloudformation"].list_stacks.return_value = {"StackSummaries": []}

        # ECS responses
        mock_clients["ecs"].list_clusters.return_value = {"clusterArns": []}

        # EKS responses
        mock_clients["eks"].list_clusters.return_value = {"clusters": []}

        # CloudWatch responses
        mock_clients["cloudwatch"].describe_alarms.return_value = {"MetricAlarms": []}

        # DynamoDB responses
        mock_clients["dynamodb"].list_tables.return_value = {"TableNames": []}

        # SNS responses
        mock_clients["sns"].list_topics.return_value = {"Topics": []}

        # SQS responses
        mock_clients["sqs"].list_queues.return_value = {"QueueUrls": []}

    def test_discover_resources_empty(self, mock_session):
        """Test resource discovery with no resources"""
        mock_session_obj, mock_clients = mock_session
        inventory = AWSResourceInventory(regions=["us-east-1"])

        resources = inventory.discover_resources()

        assert isinstance(resources, list)
        assert len(resources) == 0

    def test_discover_ec2_instances(self, mock_session):
        """Test EC2 instance discovery"""
        mock_session_obj, mock_clients = mock_session

        # Configure EC2 mock with sample instance
        mock_clients["ec2"].describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t3.micro",
                            "State": {"Name": "running"},
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "Tags": [
                                {"Key": "Name", "Value": "test-instance"},
                                {"Key": "Environment", "Value": "test"},
                            ],
                        }
                    ]
                }
            ]
        }

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()

        # Should find the EC2 instance
        ec2_instances = [r for r in resources if r["service"] == "EC2" and r["type"] == "Instance"]
        assert len(ec2_instances) == 1
        assert ec2_instances[0]["id"] == "i-1234567890abcdef0"
        assert ec2_instances[0]["name"] == "test-instance"

    def test_discover_s3_buckets(self, mock_session):
        """Test S3 bucket discovery"""
        mock_session_obj, mock_clients = mock_session

        # Configure S3 mock with sample bucket
        mock_clients["s3"].list_buckets.return_value = {
            "Buckets": [{"Name": "test-bucket", "CreationDate": "2023-01-01T00:00:00Z"}]
        }

        # Mock bucket tagging
        mock_clients["s3"].get_bucket_tagging.return_value = {
            "TagSet": [
                {"Key": "Environment", "Value": "test"},
                {"Key": "Owner", "Value": "data-team"},
            ]
        }

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()

        # Should find the S3 bucket
        s3_buckets = [r for r in resources if r["service"] == "S3" and r["type"] == "Bucket"]
        assert len(s3_buckets) == 1
        assert s3_buckets[0]["id"] == "test-bucket"
        assert s3_buckets[0]["name"] == "test-bucket"

    def test_discover_rds_instances(self, mock_session):
        """Test RDS instance discovery"""
        mock_session_obj, mock_clients = mock_session

        # Configure RDS mock with sample instance
        mock_clients["rds"].describe_db_instances.return_value = {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "test-db",
                    "DBInstanceClass": "db.t3.micro",
                    "Engine": "mysql",
                    "DBInstanceStatus": "available",
                    "AvailabilityZone": "us-east-1a",
                    "TagList": [
                        {"Key": "Environment", "Value": "test"},
                        {"Key": "Role", "Value": "database"},
                    ],
                }
            ]
        }

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()

        # Should find the RDS instance
        rds_instances = [
            r for r in resources if r["service"] == "RDS" and r["type"] == "DBInstance"
        ]
        assert len(rds_instances) == 1
        assert rds_instances[0]["id"] == "test-db"
        assert rds_instances[0]["name"] == "test-db"

    def test_discover_lambda_functions(self, mock_session):
        """Test Lambda function discovery"""
        mock_session_obj, mock_clients = mock_session

        # Configure Lambda mock with sample function
        mock_clients["lambda"].list_functions.return_value = {
            "Functions": [
                {
                    "FunctionName": "test-function",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                    "Runtime": "python3.9",
                    "Handler": "lambda_function.lambda_handler",
                }
            ]
        }

        # Mock function tags
        mock_clients["lambda"].list_tags.return_value = {
            "Tags": {"Environment": "test", "Owner": "dev-team"}
        }

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()

        # Should find the Lambda function
        lambda_functions = [
            r for r in resources if r["service"] == "Lambda" and r["type"] == "Function"
        ]
        assert len(lambda_functions) == 1
        assert lambda_functions[0]["id"] == "test-function"
        assert lambda_functions[0]["name"] == "test-function"


class TestErrorHandling:
    """Test error handling and graceful degradation"""

    @pytest.fixture
    def mock_session(self):
        """Mock boto3 session for error testing"""
        with patch("boto3.Session") as mock:
            yield mock

    def test_no_credentials_error(self, mock_session):
        """Test handling of NoCredentialsError"""
        mock_session.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            inventory = AWSResourceInventory(regions=["us-east-1"])

    def test_client_error_handling(self, mock_session):
        """Test handling of AWS ClientError"""
        mock_ec2 = Mock()
        mock_ec2.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedOperation", "Message": "Access denied"}},
            "DescribeInstances",
        )
        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory(regions=["us-east-1"])
        # Should handle error gracefully and continue
        resources = inventory.discover_resources()
        assert isinstance(resources, list)

    def test_service_unavailable_error(self, mock_session):
        """Test handling when service is unavailable"""
        mock_s3 = Mock()
        mock_s3.list_buckets.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ServiceUnavailable",
                    "Message": "Service temporarily unavailable",
                }
            },
            "ListBuckets",
        )
        mock_session.return_value.client.return_value = mock_s3

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()
        # Should continue despite service error
        assert isinstance(resources, list)

    def test_rate_limiting_error(self, mock_session):
        """Test handling of rate limiting"""
        mock_ec2 = Mock()
        mock_ec2.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "DescribeInstances",
        )
        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()
        # Should handle throttling gracefully
        assert isinstance(resources, list)

    def test_malformed_response_handling(self, mock_session):
        """Test handling of malformed API responses"""
        mock_ec2 = Mock()
        # Return malformed response
        mock_ec2.describe_instances.return_value = {"InvalidKey": "InvalidValue"}
        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()
        # Should handle malformed response gracefully
        assert isinstance(resources, list)


class TestUtilityMethods:
    """Test utility methods"""

    @pytest.fixture
    def inventory(self):
        """Create inventory instance for utility testing"""
        with patch("boto3.Session"):
            return AWSResourceInventory(regions=["us-east-1"])

    def test_get_tag_value(self, inventory):
        """Test tag value extraction"""
        tags = [
            {"Key": "Name", "Value": "test-resource"},
            {"Key": "Environment", "Value": "production"},
            {"Key": "Owner", "Value": "team-a"},
        ]

        assert inventory._get_tag_value(tags, "Name") == "test-resource"
        assert inventory._get_tag_value(tags, "Environment") == "production"
        assert inventory._get_tag_value(tags, "Owner") == "team-a"
        assert inventory._get_tag_value(tags, "NonExistent") is None

    def test_get_tag_value_empty_tags(self, inventory):
        """Test tag value extraction with empty tags"""
        assert inventory._get_tag_value([], "Name") is None
        assert inventory._get_tag_value(None, "Name") is None

    def test_save_to_file_json(self, inventory):
        """Test saving resources to JSON file"""
        inventory.resources = [
            {"service": "EC2", "type": "Instance", "id": "i-123", "name": "test"}
        ]

        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            inventory.save_to_file("test.json", "json")

            mock_open.assert_called_once_with("test.json", "w")
            mock_file.write.assert_called()

    def test_save_to_file_yaml(self, inventory):
        """Test saving resources to YAML file"""
        inventory.resources = [
            {"service": "EC2", "type": "Instance", "id": "i-123", "name": "test"}
        ]

        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            inventory.save_to_file("test.yaml", "yaml")

            mock_open.assert_called_once_with("test.yaml", "w")

    def test_save_to_file_invalid_format(self, inventory):
        """Test saving with invalid format"""
        inventory.resources = [{"service": "EC2", "type": "Instance", "id": "i-123"}]

        with pytest.raises(ValueError, match="Format must be 'json' or 'yaml'"):
            inventory.save_to_file("test.txt", "txt")


class TestPerformanceScenarios:
    """Test performance with large datasets"""

    @pytest.fixture
    def mock_session_large_dataset(self):
        """Mock session with large dataset responses"""
        with patch("boto3.Session") as mock_session:
            mock_ec2 = Mock()

            # Create large dataset (1000+ resources)
            large_reservations = []
            for i in range(100):  # 100 reservations with 10 instances each = 1000 instances
                instances = []
                for j in range(10):
                    instances.append(
                        {
                            "InstanceId": f"i-{i:03d}{j:03d}567890abcdef",
                            "InstanceType": "t3.micro",
                            "State": {"Name": "running"},
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "Tags": [
                                {"Key": "Name", "Value": f"instance-{i}-{j}"},
                                {"Key": "Environment", "Value": "test"},
                            ],
                        }
                    )
                large_reservations.append({"Instances": instances})

            mock_ec2.describe_instances.return_value = {"Reservations": large_reservations}
            mock_ec2.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

            # Configure other services with empty responses
            mock_ec2.describe_volumes.return_value = {"Volumes": []}
            mock_ec2.describe_security_groups.return_value = {"SecurityGroups": []}
            mock_ec2.describe_vpcs.return_value = {"Vpcs": []}
            mock_ec2.describe_subnets.return_value = {"Subnets": []}

            mock_session.return_value.client.return_value = mock_ec2
            yield mock_session

    def test_large_dataset_processing(self, mock_session_large_dataset):
        """Test processing of large dataset (1000+ resources)"""
        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()

        # Should handle 1000+ resources
        ec2_instances = [r for r in resources if r["service"] == "EC2" and r["type"] == "Instance"]
        assert len(ec2_instances) == 1000

        # Verify data integrity
        for i, instance in enumerate(ec2_instances):
            assert instance["service"] == "EC2"
            assert instance["type"] == "Instance"
            assert instance["id"].startswith("i-")
            assert "name" in instance


class TestSecurityValidation:
    """Test read-only operation enforcement"""

    @pytest.fixture
    def mock_session(self):
        """Mock session for security testing"""
        with patch("boto3.Session") as mock:
            yield mock

    def test_read_only_operations_only(self, mock_session):
        """Test that only read-only operations are used"""
        mock_clients = {}

        # Track all method calls
        called_methods = []

        def track_calls(service_name):
            mock_client = Mock()

            # Override __getattr__ to track method calls
            def track_method_call(method_name):
                called_methods.append(f"{service_name}.{method_name}")
                # Return a mock method that returns empty results
                mock_method = Mock()
                mock_method.return_value = {}
                return mock_method

            mock_client.__getattr__ = track_method_call
            return mock_client

        mock_session.return_value.client.side_effect = track_calls

        inventory = AWSResourceInventory(regions=["us-east-1"])
        inventory.discover_resources()

        # Verify only read-only operations were called
        read_only_patterns = ["describe_", "list_", "get_", "head_"]

        write_operations = [
            "create_",
            "delete_",
            "update_",
            "modify_",
            "put_",
            "post_",
            "terminate_",
            "stop_",
            "start_",
            "reboot_",
        ]

        for method_call in called_methods:
            method_name = method_call.split(".")[1].lower()

            # Should match read-only patterns
            is_read_only = any(pattern in method_name for pattern in read_only_patterns)

            # Should not match write operation patterns
            is_write_operation = any(pattern in method_name for pattern in write_operations)

            assert not is_write_operation, f"Write operation detected: {method_call}"

    def test_no_resource_modification(self, mock_session):
        """Test that no resources are modified during discovery"""
        # This test ensures the discovery process is truly read-only
        mock_ec2 = Mock()

        # Configure read-only responses
        mock_ec2.describe_instances.return_value = {"Reservations": []}
        mock_ec2.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

        # Ensure no write methods are available
        write_methods = [
            "create_instances",
            "terminate_instances",
            "stop_instances",
            "start_instances",
            "reboot_instances",
            "modify_instance_attribute",
        ]

        for method in write_methods:
            setattr(
                mock_ec2,
                method,
                Mock(side_effect=Exception(f"Write operation {method} not allowed")),
            )

        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()

        # Should complete without calling write methods
        assert isinstance(resources, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
