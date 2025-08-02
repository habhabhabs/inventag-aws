#!/usr/bin/env python3
"""
Unit tests for NetworkAnalyzer
Tests VPC and subnet analysis algorithms and CIDR calculations.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import ipaddress
from inventag.discovery.network_analyzer import (
    NetworkAnalyzer, 
    VPCAnalysis, 
    SubnetAnalysis, 
    NetworkSummary
)


class TestNetworkAnalyzer(unittest.TestCase):
    """Test cases for NetworkAnalyzer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.analyzer = NetworkAnalyzer(session=self.mock_session)

    def test_init(self):
        """Test NetworkAnalyzer initialization."""
        self.assertEqual(self.analyzer.session, self.mock_session)
        self.assertEqual(self.analyzer.vpc_cache, {})
        self.assertEqual(self.analyzer.subnet_cache, {})
        self.assertEqual(self.analyzer.high_utilization_threshold, 80.0)
        self.assertEqual(self.analyzer.capacity_warning_threshold, 90.0)

    def test_calculate_cidr_ips(self):
        """Test CIDR IP calculation."""
        # Test /24 subnet (256 - 5 reserved = 251)
        self.assertEqual(self.analyzer._calculate_cidr_ips("10.0.1.0/24"), 251)
        
        # Test /16 subnet (65536 - 5 reserved = 65531)
        self.assertEqual(self.analyzer._calculate_cidr_ips("10.0.0.0/16"), 65531)
        
        # Test /28 subnet (16 - 5 reserved = 11)
        self.assertEqual(self.analyzer._calculate_cidr_ips("10.0.1.0/28"), 11)
        
        # Test invalid CIDR
        self.assertEqual(self.analyzer._calculate_cidr_ips("invalid"), 0)

    def test_extract_regions(self):
        """Test region extraction from resources."""
        resources = [
            {"region": "us-east-1", "service": "EC2"},
            {"region": "us-west-2", "service": "S3"},
            {"region": "global", "service": "IAM"},  # Should be excluded
            {"region": "eu-west-1", "service": "RDS"},
            {"region": "us-east-1", "service": "VPC"},  # Duplicate
        ]
        
        regions = self.analyzer._extract_regions(resources)
        expected_regions = {"us-east-1", "us-west-2", "eu-west-1"}
        self.assertEqual(regions, expected_regions)

    def test_extract_vpc_id(self):
        """Test VPC ID extraction from resources."""
        # Test direct vpc_id field
        resource1 = {"vpc_id": "vpc-12345"}
        self.assertEqual(self.analyzer._extract_vpc_id(resource1), "vpc-12345")
        
        # Test VpcId field
        resource2 = {"VpcId": "vpc-67890"}
        self.assertEqual(self.analyzer._extract_vpc_id(resource2), "vpc-67890")
        
        # Test vpc field
        resource3 = {"vpc": "vpc-abcdef"}
        self.assertEqual(self.analyzer._extract_vpc_id(resource3), "vpc-abcdef")
        
        # Test no VPC ID
        resource4 = {"service": "EC2"}
        self.assertIsNone(self.analyzer._extract_vpc_id(resource4))

    def test_extract_subnet_id(self):
        """Test subnet ID extraction from resources."""
        # Test direct subnet_id field
        resource1 = {"subnet_id": "subnet-12345"}
        self.assertEqual(self.analyzer._extract_subnet_id(resource1), "subnet-12345")
        
        # Test SubnetId field
        resource2 = {"SubnetId": "subnet-67890"}
        self.assertEqual(self.analyzer._extract_subnet_id(resource2), "subnet-67890")
        
        # Test subnet field
        resource3 = {"subnet": "subnet-abcdef"}
        self.assertEqual(self.analyzer._extract_subnet_id(resource3), "subnet-abcdef")
        
        # Test no subnet ID
        resource4 = {"service": "EC2"}
        self.assertIsNone(self.analyzer._extract_subnet_id(resource4))

    def test_get_tag_value(self):
        """Test tag value extraction."""
        tags = [
            {"Key": "Name", "Value": "test-vpc"},
            {"Key": "Environment", "Value": "production"},
            {"Key": "Owner", "Value": "team-a"}
        ]
        
        self.assertEqual(self.analyzer._get_tag_value(tags, "Name"), "test-vpc")
        self.assertEqual(self.analyzer._get_tag_value(tags, "Environment"), "production")
        self.assertIsNone(self.analyzer._get_tag_value(tags, "NonExistent"))
        self.assertIsNone(self.analyzer._get_tag_value([], "Name"))

    @patch('inventag.discovery.network_analyzer.logger')
    def test_cache_network_info_client_error(self, mock_logger):
        """Test network info caching with client error."""
        mock_ec2 = Mock()
        mock_ec2.describe_vpcs.side_effect = Exception("Access denied")
        mock_ec2.describe_subnets.side_effect = Exception("Access denied")
        mock_ec2.describe_internet_gateways.side_effect = Exception("Access denied")
        mock_ec2.describe_nat_gateways.side_effect = Exception("Access denied")
        mock_ec2.describe_vpc_endpoints.side_effect = Exception("Access denied")
        mock_ec2.describe_vpc_peering_connections.side_effect = Exception("Access denied")
        mock_ec2.describe_transit_gateway_attachments.side_effect = Exception("Access denied")
        self.mock_session.client.return_value = mock_ec2
        
        self.analyzer._cache_network_info("us-east-1")
        
        mock_logger.warning.assert_called()

    def test_cache_vpc_info(self):
        """Test VPC information caching."""
        mock_ec2 = Mock()
        
        # Mock VPC response
        vpc_response = {
            'Vpcs': [
                {
                    'VpcId': 'vpc-12345',
                    'CidrBlock': '10.0.0.0/16',
                    'Tags': [{'Key': 'Name', 'Value': 'test-vpc'}],
                    'CidrBlockAssociationSet': [
                        {
                            'CidrBlock': '10.0.0.0/16',
                            'CidrBlockState': {'State': 'associated'}
                        },
                        {
                            'CidrBlock': '10.1.0.0/16',
                            'CidrBlockState': {'State': 'associated'}
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_vpcs.return_value = vpc_response
        
        self.analyzer._cache_vpc_info(mock_ec2, "us-east-1")
        
        # Verify VPC was cached
        self.assertIn('vpc-12345', self.analyzer.vpc_cache)
        vpc_analysis = self.analyzer.vpc_cache['vpc-12345']
        
        self.assertEqual(vpc_analysis.vpc_id, 'vpc-12345')
        self.assertEqual(vpc_analysis.vpc_name, 'test-vpc')
        self.assertEqual(vpc_analysis.cidr_block, '10.0.0.0/16')
        self.assertEqual(len(vpc_analysis.cidr_blocks), 2)
        self.assertIn('10.0.0.0/16', vpc_analysis.cidr_blocks)
        self.assertIn('10.1.0.0/16', vpc_analysis.cidr_blocks)
        # Total IPs should be sum of both CIDR blocks (minus reserved)
        expected_ips = (65536 - 5) + (65536 - 5)  # Two /16 networks
        self.assertEqual(vpc_analysis.total_ips, expected_ips)

    def test_cache_subnet_info(self):
        """Test subnet information caching."""
        mock_ec2 = Mock()
        
        # Set up VPC cache first
        self.analyzer.vpc_cache['vpc-12345'] = VPCAnalysis(
            vpc_id='vpc-12345',
            vpc_name='test-vpc',
            cidr_block='10.0.0.0/16'
        )
        
        # Mock subnet response
        subnet_response = {
            'Subnets': [
                {
                    'SubnetId': 'subnet-12345',
                    'VpcId': 'vpc-12345',
                    'CidrBlock': '10.0.1.0/24',
                    'AvailabilityZone': 'us-east-1a',
                    'AvailableIpAddressCount': 200,
                    'Tags': [{'Key': 'Name', 'Value': 'test-subnet'}]
                }
            ]
        }
        mock_ec2.describe_subnets.return_value = subnet_response
        
        self.analyzer._cache_subnet_info(mock_ec2, "us-east-1")
        
        # Verify subnet was cached
        self.assertIn('subnet-12345', self.analyzer.subnet_cache)
        subnet_analysis = self.analyzer.subnet_cache['subnet-12345']
        
        self.assertEqual(subnet_analysis.subnet_id, 'subnet-12345')
        self.assertEqual(subnet_analysis.subnet_name, 'test-subnet')
        self.assertEqual(subnet_analysis.cidr_block, '10.0.1.0/24')
        self.assertEqual(subnet_analysis.availability_zone, 'us-east-1a')
        self.assertEqual(subnet_analysis.vpc_id, 'vpc-12345')
        self.assertEqual(subnet_analysis.total_ips, 251)  # 256 - 5 reserved
        self.assertEqual(subnet_analysis.available_ips, 200)
        
        # Check utilization calculation
        expected_utilization = ((251 - 200) / 251) * 100
        self.assertAlmostEqual(subnet_analysis.utilization_percentage, expected_utilization, places=2)
        
        # Verify subnet was added to VPC
        vpc_analysis = self.analyzer.vpc_cache['vpc-12345']
        self.assertEqual(len(vpc_analysis.subnets), 1)
        self.assertEqual(vpc_analysis.subnets[0].subnet_id, 'subnet-12345')

    def test_map_resources_to_network(self):
        """Test resource mapping to network context."""
        # Set up cache
        vpc_analysis = VPCAnalysis(
            vpc_id='vpc-12345',
            vpc_name='test-vpc',
            cidr_block='10.0.0.0/16',
            total_ips=65531,
            utilization_percentage=25.5
        )
        subnet_analysis = SubnetAnalysis(
            subnet_id='subnet-12345',
            subnet_name='test-subnet',
            cidr_block='10.0.1.0/24',
            availability_zone='us-east-1a',
            vpc_id='vpc-12345',
            total_ips=251,
            available_ips=200,
            utilization_percentage=20.3,
            is_public=True
        )
        
        self.analyzer.vpc_cache['vpc-12345'] = vpc_analysis
        self.analyzer.subnet_cache['subnet-12345'] = subnet_analysis
        
        # Test resources
        resources = [
            {
                'id': 'i-12345',
                'service': 'EC2',
                'type': 'Instance',
                'vpc_id': 'vpc-12345',
                'subnet_id': 'subnet-12345'
            },
            {
                'id': 'db-67890',
                'service': 'RDS',
                'type': 'DBInstance',
                'vpc_id': 'vpc-12345'
            }
        ]
        
        enriched_resources = self.analyzer.map_resources_to_network(resources)
        
        # Check first resource (has both VPC and subnet)
        resource1 = enriched_resources[0]
        self.assertEqual(resource1['vpc_name'], 'test-vpc')
        self.assertEqual(resource1['vpc_cidr_block'], '10.0.0.0/16')
        self.assertEqual(resource1['vpc_total_ips'], 65531)
        self.assertEqual(resource1['vpc_utilization_percentage'], 25.5)
        self.assertEqual(resource1['subnet_name'], 'test-subnet')
        self.assertEqual(resource1['subnet_cidr_block'], '10.0.1.0/24')
        self.assertEqual(resource1['subnet_total_ips'], 251)
        self.assertEqual(resource1['subnet_utilization_percentage'], 20.3)
        self.assertTrue(resource1['subnet_is_public'])
        
        # Check second resource (has only VPC)
        resource2 = enriched_resources[1]
        self.assertEqual(resource2['vpc_name'], 'test-vpc')
        self.assertNotIn('subnet_name', resource2)

    def test_generate_capacity_warnings(self):
        """Test capacity warning generation."""
        # Create VPC with high utilization
        high_util_vpc = VPCAnalysis(
            vpc_id='vpc-high',
            vpc_name='high-util-vpc',
            cidr_block='10.0.0.0/16',
            utilization_percentage=95.0
        )
        
        # Create subnet with high utilization
        high_util_subnet = SubnetAnalysis(
            subnet_id='subnet-high',
            subnet_name='high-util-subnet',
            cidr_block='10.0.1.0/24',
            availability_zone='us-east-1a',
            vpc_id='vpc-high',
            total_ips=251,
            available_ips=10,
            utilization_percentage=96.0
        )
        high_util_vpc.subnets = [high_util_subnet]
        
        # Create VPC with normal utilization
        normal_vpc = VPCAnalysis(
            vpc_id='vpc-normal',
            vpc_name='normal-vpc',
            cidr_block='10.1.0.0/16',
            utilization_percentage=50.0
        )
        
        vpc_analysis = {
            'vpc-high': high_util_vpc,
            'vpc-normal': normal_vpc
        }
        
        warnings = self.analyzer._generate_capacity_warnings(vpc_analysis)
        
        self.assertEqual(len(warnings), 2)  # VPC warning + subnet warning
        self.assertIn('high-util-vpc', warnings[0])
        self.assertIn('95.0%', warnings[0])
        self.assertIn('high-util-subnet', warnings[1])
        self.assertIn('96.0%', warnings[1])

    def test_generate_optimization_recommendations(self):
        """Test optimization recommendation generation."""
        # Create unused VPC
        unused_vpc = VPCAnalysis(
            vpc_id='vpc-unused',
            vpc_name='unused-vpc',
            cidr_block='10.0.0.0/16',
            associated_resources=[]  # No resources
        )
        
        # Create VPC with underutilized subnets
        underutil_vpc = VPCAnalysis(
            vpc_id='vpc-underutil',
            vpc_name='underutil-vpc',
            cidr_block='10.1.0.0/16',
            associated_resources=['i-12345']
        )
        
        # Add underutilized subnet
        underutil_subnet = SubnetAnalysis(
            subnet_id='subnet-underutil',
            subnet_name='underutil-subnet',
            cidr_block='10.1.1.0/24',
            availability_zone='us-east-1a',
            vpc_id='vpc-underutil',
            total_ips=251,
            available_ips=240,
            utilization_percentage=4.4,  # Very low utilization
            associated_resources=['i-12345']
        )
        underutil_vpc.subnets = [underutil_subnet]
        
        # Create VPC without NAT gateways but multiple subnets
        no_nat_vpc = VPCAnalysis(
            vpc_id='vpc-no-nat',
            vpc_name='no-nat-vpc',
            cidr_block='10.2.0.0/16',
            nat_gateways=[],  # No NAT gateways
            associated_resources=['i-67890']
        )
        
        # Add multiple subnets
        subnet1 = SubnetAnalysis(
            subnet_id='subnet-1',
            subnet_name='subnet-1',
            cidr_block='10.2.1.0/24',
            availability_zone='us-east-1a',
            vpc_id='vpc-no-nat',
            total_ips=251,
            available_ips=200,
            utilization_percentage=20.0
        )
        subnet2 = SubnetAnalysis(
            subnet_id='subnet-2',
            subnet_name='subnet-2',
            cidr_block='10.2.2.0/24',
            availability_zone='us-east-1b',
            vpc_id='vpc-no-nat',
            total_ips=251,
            available_ips=200,
            utilization_percentage=20.0
        )
        no_nat_vpc.subnets = [subnet1, subnet2]
        
        vpc_analysis = {
            'vpc-unused': unused_vpc,
            'vpc-underutil': underutil_vpc,
            'vpc-no-nat': no_nat_vpc
        }
        
        recommendations = self.analyzer._generate_optimization_recommendations(vpc_analysis)
        
        self.assertEqual(len(recommendations), 3)
        
        # Check unused VPC recommendation
        self.assertIn('unused-vpc', recommendations[0])
        self.assertIn('no associated resources', recommendations[0])
        
        # Check underutilized subnet recommendation
        self.assertIn('underutil-vpc', recommendations[1])
        self.assertIn('underutilized subnets', recommendations[1])
        
        # Check NAT gateway recommendation
        self.assertIn('no-nat-vpc', recommendations[2])
        self.assertIn('NAT gateways', recommendations[2])

    def test_generate_network_summary(self):
        """Test network summary generation."""
        # Create test VPC analysis
        vpc1 = VPCAnalysis(
            vpc_id='vpc-1',
            vpc_name='vpc-1',
            cidr_block='10.0.0.0/16',
            available_ips=60000,
            utilization_percentage=25.0
        )
        
        subnet1 = SubnetAnalysis(
            subnet_id='subnet-1',
            subnet_name='subnet-1',
            cidr_block='10.0.1.0/24',
            availability_zone='us-east-1a',
            vpc_id='vpc-1',
            total_ips=251,
            available_ips=200,
            utilization_percentage=20.3
        )
        
        subnet2 = SubnetAnalysis(
            subnet_id='subnet-2',
            subnet_name='subnet-2',
            cidr_block='10.0.2.0/24',
            availability_zone='us-east-1b',
            vpc_id='vpc-1',
            total_ips=251,
            available_ips=50,
            utilization_percentage=80.1  # Highest utilization
        )
        
        vpc1.subnets = [subnet1, subnet2]
        
        vpc2 = VPCAnalysis(
            vpc_id='vpc-2',
            vpc_name='vpc-2',
            cidr_block='10.1.0.0/16',
            available_ips=50000,
            utilization_percentage=15.0
        )
        
        vpc_analysis = {'vpc-1': vpc1, 'vpc-2': vpc2}
        
        # Mock the warning and recommendation methods
        self.analyzer._generate_capacity_warnings = Mock(return_value=['warning1', 'warning2'])
        self.analyzer._generate_optimization_recommendations = Mock(return_value=['rec1'])
        
        summary = self.analyzer.generate_network_summary(vpc_analysis)
        
        self.assertEqual(summary.total_vpcs, 2)
        self.assertEqual(summary.total_subnets, 2)  # Only vpc1 has subnets
        self.assertEqual(summary.total_available_ips, 110000)  # 60000 + 50000
        self.assertEqual(summary.highest_utilization_subnet, 'subnet-2 (subnet-2)')
        self.assertEqual(summary.highest_utilization_percentage, 80.1)
        self.assertEqual(summary.vpc_utilization_stats, {'vpc-1': 25.0, 'vpc-2': 15.0})
        self.assertEqual(summary.capacity_warnings, ['warning1', 'warning2'])
        self.assertEqual(summary.optimization_recommendations, ['rec1'])

    @patch('inventag.discovery.network_analyzer.logger')
    def test_analyze_vpc_resources_integration(self, mock_logger):
        """Test the main analyze_vpc_resources method integration."""
        # Mock the session and EC2 client
        mock_ec2 = Mock()
        self.mock_session.client.return_value = mock_ec2
        
        # Mock VPC response
        mock_ec2.describe_vpcs.return_value = {
            'Vpcs': [{
                'VpcId': 'vpc-12345',
                'CidrBlock': '10.0.0.0/16',
                'Tags': [{'Key': 'Name', 'Value': 'test-vpc'}]
            }]
        }
        
        # Mock subnet response
        mock_ec2.describe_subnets.return_value = {
            'Subnets': [{
                'SubnetId': 'subnet-12345',
                'VpcId': 'vpc-12345',
                'CidrBlock': '10.0.1.0/24',
                'AvailabilityZone': 'us-east-1a',
                'AvailableIpAddressCount': 200,
                'Tags': [{'Key': 'Name', 'Value': 'test-subnet'}]
            }]
        }
        
        # Mock other network components
        mock_ec2.describe_internet_gateways.return_value = {'InternetGateways': []}
        mock_ec2.describe_nat_gateways.return_value = {'NatGateways': []}
        mock_ec2.describe_vpc_endpoints.return_value = {'VpcEndpoints': []}
        mock_ec2.describe_vpc_peering_connections.return_value = {'VpcPeeringConnections': []}
        mock_ec2.describe_transit_gateway_attachments.return_value = {'TransitGatewayAttachments': []}
        
        # Test resources
        resources = [
            {
                'id': 'i-12345',
                'service': 'EC2',
                'region': 'us-east-1',
                'vpc_id': 'vpc-12345'
            }
        ]
        
        result = self.analyzer.analyze_vpc_resources(resources)
        
        # Verify results
        self.assertIn('vpc-12345', result)
        vpc_analysis = result['vpc-12345']
        self.assertEqual(vpc_analysis.vpc_name, 'test-vpc')
        self.assertEqual(len(vpc_analysis.subnets), 1)
        self.assertEqual(vpc_analysis.associated_resources, ['i-12345'])


if __name__ == '__main__':
    unittest.main()