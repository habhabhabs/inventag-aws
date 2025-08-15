#!/usr/bin/env python3
"""
Tests for AWS Resource Inventory functionality
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.discovery import AWSResourceInventory


class TestAWSResourceInventory:
    """Test cases for AWSResourceInventory class"""

    def test_logger_initialization(self):
        """Test that logger is properly initialized"""
        with patch("boto3.Session"):
            inventory = AWSResourceInventory()
            assert hasattr(inventory, "logger")
            assert inventory.logger is not None

    def test_init_with_regions(self):
        """Test initialization with specific regions"""
        test_regions = ["us-east-1", "us-west-2"]
        with patch("boto3.Session"):
            inventory = AWSResourceInventory(regions=test_regions)
            assert inventory.regions == test_regions

    @patch("boto3.Session")
    def test_init_without_regions(self, mock_session):
        """Test initialization without regions (should get all regions)"""
        # Mock the EC2 client and describe_regions response
        mock_ec2 = Mock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [{"RegionName": "us-east-1"}, {"RegionName": "us-west-2"}]
        }
        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory()
        assert "us-east-1" in inventory.regions
        assert "us-west-2" in inventory.regions

    @patch("boto3.Session")
    def test_get_available_regions_fallback(self, mock_session):
        """Test fallback when getting regions fails"""
        # Mock the EC2 client to raise an exception
        mock_ec2 = Mock()
        mock_ec2.describe_regions.side_effect = Exception("Access denied")
        mock_session.return_value.client.return_value = mock_ec2

        inventory = AWSResourceInventory()
        # Should fall back to default regions
        assert "us-east-1" in inventory.regions
        assert "ap-southeast-1" in inventory.regions

    def test_setup_logging_fallback(self):
        """Test logging setup with fallback"""
        with patch("boto3.Session"):
            with patch("logging.basicConfig", side_effect=Exception("Logging failed")):
                inventory = AWSResourceInventory()
                # Should still have a logger even if setup fails
                assert hasattr(inventory, "logger")
                assert inventory.logger is not None

    @patch("boto3.Session")
    def test_discover_resources_empty(self, mock_session):
        """Test resource discovery with no resources"""
        # Mock all AWS clients to return empty results
        mock_clients = {}
        for service in [
            "ec2",
            "s3",
            "rds",
            "lambda",
            "iam",
            "cloudformation",
            "ecs",
            "eks",
            "cloudwatch",
        ]:
            mock_clients[service] = Mock()

        # Configure EC2 mock responses
        mock_clients["ec2"].describe_instances.return_value = {"Reservations": []}
        mock_clients["ec2"].describe_volumes.return_value = {"Volumes": []}
        mock_clients["ec2"].describe_security_groups.return_value = {"SecurityGroups": []}
        mock_clients["ec2"].describe_vpcs.return_value = {"Vpcs": []}
        mock_clients["ec2"].describe_subnets.return_value = {"Subnets": []}

        # Configure other service mocks
        mock_clients["s3"].list_buckets.return_value = {"Buckets": []}
        mock_clients["rds"].describe_db_instances.return_value = {"DBInstances": []}
        mock_clients["lambda"].list_functions.return_value = {"Functions": []}
        mock_clients["iam"].list_roles.return_value = {"Roles": []}
        mock_clients["iam"].list_users.return_value = {"Users": []}
        mock_clients["cloudformation"].list_stacks.return_value = {"StackSummaries": []}
        mock_clients["ecs"].list_clusters.return_value = {"clusterArns": []}
        mock_clients["eks"].list_clusters.return_value = {"clusters": []}
        mock_clients["cloudwatch"].describe_alarms.return_value = {"MetricAlarms": []}

        def mock_client(service_name, **kwargs):
            return mock_clients.get(service_name, Mock())

        mock_session.return_value.client.side_effect = mock_client

        inventory = AWSResourceInventory(regions=["us-east-1"])
        resources = inventory.discover_resources()

        assert isinstance(resources, list)
        assert len(resources) == 0

    def test_get_tag_value(self):
        """Test tag value extraction"""
        with patch("boto3.Session"):
            inventory = AWSResourceInventory()

            tags = [
                {"Key": "Name", "Value": "test-resource"},
                {"Key": "Environment", "Value": "production"},
            ]

            assert inventory._get_tag_value(tags, "Name") == "test-resource"
            assert inventory._get_tag_value(tags, "Environment") == "production"
            assert inventory._get_tag_value(tags, "NonExistent") is None

    @patch("boto3.Session")
    def test_save_to_file_json(self, mock_session):
        """Test saving resources to JSON file"""
        inventory = AWSResourceInventory()
        inventory.resources = [{"service": "EC2", "type": "Instance", "id": "i-123"}]

        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            inventory.save_to_file("test.json", "json")

            mock_open.assert_called_once_with("test.json", "w")
            mock_file.write.assert_called()

    @patch("boto3.Session")
    def test_save_to_file_yaml(self, mock_session):
        """Test saving resources to YAML file"""
        inventory = AWSResourceInventory()
        inventory.resources = [{"service": "EC2", "type": "Instance", "id": "i-123"}]

        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            inventory.save_to_file("test.yaml", "yaml")

            mock_open.assert_called_once_with("test.yaml", "w")

    @patch("boto3.Session")
    def test_save_to_file_invalid_format(self, mock_session):
        """Test saving with invalid format raises error"""
        inventory = AWSResourceInventory()
        inventory.resources = [{"service": "EC2", "type": "Instance", "id": "i-123"}]

        with pytest.raises(ValueError, match="Format must be 'json' or 'yaml'"):
            inventory.save_to_file("test.txt", "txt")


if __name__ == "__main__":
    pytest.main([__file__])
