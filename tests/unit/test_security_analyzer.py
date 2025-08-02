#!/usr/bin/env python3
"""
Unit tests for SecurityAnalyzer
Tests security group and NACL analysis algorithms and risk assessment.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from inventag.discovery.security_analyzer import (
    SecurityAnalyzer,
    SecurityGroupAnalysis,
    SecurityRule,
    NACLAnalysis,
    NACLRule,
    SecuritySummary
)


class TestSecurityAnalyzer(unittest.TestCase):
    """Test cases for SecurityAnalyzer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.analyzer = SecurityAnalyzer(session=self.mock_session)

    def test_init(self):
        """Test SecurityAnalyzer initialization."""
        self.assertEqual(self.analyzer.session, self.mock_session)
        self.assertEqual(self.analyzer.sg_cache, {})
        self.assertEqual(self.analyzer.nacl_cache, {})
        self.assertIn(22, self.analyzer.common_services)
        self.assertIn(443, self.analyzer.common_services)
        self.assertIn('0.0.0.0/0', self.analyzer.permissive_sources)

    def test_identify_common_service(self):
        """Test common service identification by port."""
        self.assertEqual(self.analyzer._identify_common_service(22), 'SSH')
        self.assertEqual(self.analyzer._identify_common_service(443), 'HTTPS')
        self.assertEqual(self.analyzer._identify_common_service(3306), 'MySQL')
        self.assertIsNone(self.analyzer._identify_common_service(12345))
        self.assertIsNone(self.analyzer._identify_common_service(None))

    def test_assess_rule_risk(self):
        """Test security rule risk assessment."""
        # Critical risk: permissive source with SSH
        self.assertEqual(
            self.analyzer._assess_rule_risk('0.0.0.0/0', 22, 'tcp'), 
            'critical'
        )
        
        # High risk: permissive source with well-known port
        self.assertEqual(
            self.analyzer._assess_rule_risk('0.0.0.0/0', 80, 'tcp'), 
            'high'
        )
        
        # Medium risk: permissive source with high port
        self.assertEqual(
            self.analyzer._assess_rule_risk('0.0.0.0/0', 8080, 'tcp'), 
            'medium'
        )
        
        # Medium risk: broad CIDR range
        self.assertEqual(
            self.analyzer._assess_rule_risk('10.0.0.0/8', 22, 'tcp'), 
            'medium'
        )
        
        # Low risk: specific IP
        self.assertEqual(
            self.analyzer._assess_rule_risk('10.0.1.100/32', 22, 'tcp'), 
            'low'
        )

    def test_extract_regions(self):
        """Test region extraction from resources."""
        resources = [
            {"region": "us-east-1", "service": "EC2"},
            {"region": "us-west-2", "service": "VPC"},
            {"region": "global", "service": "IAM"},  # Should be excluded
            {"region": "eu-west-1", "service": "EC2"},
            {"region": "us-east-1", "service": "VPC"},  # Duplicate
        ]
        
        regions = self.analyzer._extract_regions(resources)
        expected_regions = {"us-east-1", "us-west-2", "eu-west-1"}
        self.assertEqual(regions, expected_regions)

    def test_extract_security_group_ids(self):
        """Test security group ID extraction from resources."""
        # Test security_groups field with list of dicts
        resource1 = {
            "security_groups": [
                {"GroupId": "sg-12345", "GroupName": "web-sg"},
                {"GroupId": "sg-67890", "GroupName": "db-sg"}
            ]
        }
        result1 = self.analyzer._extract_security_group_ids(resource1)
        self.assertEqual(set(result1), {"sg-12345", "sg-67890"})
        
        # Test SecurityGroups field (AWS API format)
        resource2 = {
            "SecurityGroups": [
                {"GroupId": "sg-abcdef"},
                {"GroupId": "sg-fedcba"}
            ]
        }
        result2 = self.analyzer._extract_security_group_ids(resource2)
        self.assertEqual(set(result2), {"sg-abcdef", "sg-fedcba"})
        
        # Test security_group_ids field with list of strings
        resource3 = {
            "security_group_ids": ["sg-111111", "sg-222222"]
        }
        result3 = self.analyzer._extract_security_group_ids(resource3)
        self.assertEqual(set(result3), {"sg-111111", "sg-222222"})
        
        # Test no security groups
        resource4 = {"service": "EC2"}
        result4 = self.analyzer._extract_security_group_ids(resource4)
        self.assertEqual(result4, [])

    def test_parse_security_rule(self):
        """Test security rule parsing."""
        # Test rule with IP ranges
        rule_data = {
            "IpProtocol": "tcp",
            "FromPort": 80,
            "ToPort": 80,
            "IpRanges": [
                {"CidrIp": "0.0.0.0/0", "Description": "HTTP from anywhere"},
                {"CidrIp": "10.0.0.0/8", "Description": "HTTP from internal"}
            ]
        }
        
        rules = self.analyzer._parse_security_rule(rule_data, "inbound")
        
        self.assertEqual(len(rules), 2)
        
        # Check first rule (permissive)
        rule1 = rules[0]
        self.assertEqual(rule1.protocol, "tcp")
        self.assertEqual(rule1.port_range, "80")
        self.assertEqual(rule1.source_destination, "0.0.0.0/0")
        self.assertEqual(rule1.rule_type, "inbound")
        self.assertTrue(rule1.is_permissive)
        self.assertEqual(rule1.risk_assessment, "high")
        self.assertEqual(rule1.common_service, "HTTP")
        
        # Check second rule (internal)
        rule2 = rules[1]
        self.assertEqual(rule2.source_destination, "10.0.0.0/8")
        self.assertFalse(rule2.is_permissive)
        self.assertEqual(rule2.risk_assessment, "medium")

    def test_parse_security_rule_with_sg_reference(self):
        """Test security rule parsing with security group references."""
        rule_data = {
            "IpProtocol": "tcp",
            "FromPort": 3306,
            "ToPort": 3306,
            "UserIdGroupPairs": [
                {"GroupId": "sg-referenced", "Description": "MySQL from web tier"}
            ]
        }
        
        rules = self.analyzer._parse_security_rule(rule_data, "inbound")
        
        self.assertEqual(len(rules), 1)
        rule = rules[0]
        
        self.assertEqual(rule.protocol, "tcp")
        self.assertEqual(rule.port_range, "3306")
        self.assertEqual(rule.source_destination, "sg-sg-referenced")
        self.assertTrue(rule.references_security_group)
        self.assertEqual(rule.referenced_sg_id, "sg-referenced")
        self.assertEqual(rule.risk_assessment, "low")  # SG references are lower risk
        self.assertEqual(rule.common_service, "MySQL")

    def test_parse_security_rule_all_traffic(self):
        """Test parsing rule that allows all traffic."""
        rule_data = {
            "IpProtocol": "-1",
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
        }
        
        rules = self.analyzer._parse_security_rule(rule_data, "outbound")
        
        self.assertEqual(len(rules), 1)
        rule = rules[0]
        
        self.assertEqual(rule.protocol, "All")
        self.assertEqual(rule.port_range, "All")
        self.assertTrue(rule.is_permissive)
        self.assertEqual(rule.risk_assessment, "medium")  # All ports but not high-risk specific port

    def test_parse_nacl_rule(self):
        """Test NACL rule parsing."""
        entry = {
            "RuleNumber": 100,
            "Protocol": "6",  # TCP
            "RuleAction": "allow",
            "CidrBlock": "10.0.0.0/16",
            "PortRange": {"From": 80, "To": 80},
            "Egress": False
        }
        
        rule = self.analyzer._parse_nacl_rule(entry)
        
        self.assertEqual(rule.rule_number, 100)
        self.assertEqual(rule.protocol, "TCP")
        self.assertEqual(rule.rule_action, "allow")
        self.assertEqual(rule.port_range, "80")
        self.assertEqual(rule.cidr_block, "10.0.0.0/16")
        self.assertEqual(rule.rule_type, "inbound")
        self.assertEqual(rule.common_service, "HTTP")

    def test_parse_nacl_rule_all_traffic(self):
        """Test NACL rule parsing for all traffic."""
        entry = {
            "RuleNumber": 32767,
            "Protocol": "-1",
            "RuleAction": "deny",
            "CidrBlock": "0.0.0.0/0",
            "Egress": True
        }
        
        rule = self.analyzer._parse_nacl_rule(entry)
        
        self.assertEqual(rule.rule_number, 32767)
        self.assertEqual(rule.protocol, "All")
        self.assertEqual(rule.rule_action, "deny")
        self.assertEqual(rule.port_range, "All")
        self.assertEqual(rule.rule_type, "outbound")

    @patch('inventag.discovery.security_analyzer.logger')
    def test_cache_security_group_info(self, mock_logger):
        """Test security group information caching."""
        mock_ec2 = Mock()
        
        # Mock security group response
        sg_response = {
            'SecurityGroups': [
                {
                    'GroupId': 'sg-12345',
                    'GroupName': 'web-sg',
                    'Description': 'Web server security group',
                    'VpcId': 'vpc-12345',
                    'Tags': [{'Key': 'Name', 'Value': 'WebSG'}],
                    'IpPermissions': [
                        {
                            'IpProtocol': 'tcp',
                            'FromPort': 80,
                            'ToPort': 80,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP'}]
                        }
                    ],
                    'IpPermissionsEgress': [
                        {
                            'IpProtocol': '-1',
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_security_groups.return_value = sg_response
        self.mock_session.client.return_value = mock_ec2
        
        self.analyzer._cache_security_group_info("us-east-1")
        
        # Verify security group was cached
        self.assertIn('sg-12345', self.analyzer.sg_cache)
        sg_analysis = self.analyzer.sg_cache['sg-12345']
        
        self.assertEqual(sg_analysis.group_id, 'sg-12345')
        self.assertEqual(sg_analysis.group_name, 'web-sg')
        self.assertEqual(sg_analysis.description, 'Web server security group')
        self.assertEqual(sg_analysis.vpc_id, 'vpc-12345')
        self.assertEqual(len(sg_analysis.inbound_rules), 1)
        self.assertEqual(len(sg_analysis.outbound_rules), 1)
        
        # Check inbound rule
        inbound_rule = sg_analysis.inbound_rules[0]
        self.assertEqual(inbound_rule.protocol, 'tcp')
        self.assertEqual(inbound_rule.port_range, '80')
        self.assertTrue(inbound_rule.is_permissive)

    @patch('inventag.discovery.security_analyzer.logger')
    def test_cache_nacl_info(self, mock_logger):
        """Test NACL information caching."""
        mock_ec2 = Mock()
        
        # Mock NACL response
        nacl_response = {
            'NetworkAcls': [
                {
                    'NetworkAclId': 'acl-12345',
                    'IsDefault': True,
                    'VpcId': 'vpc-12345',
                    'Tags': [{'Key': 'Name', 'Value': 'default-nacl'}],
                    'Associations': [{'SubnetId': 'subnet-12345'}],
                    'Entries': [
                        {
                            'RuleNumber': 100,
                            'Protocol': '6',
                            'RuleAction': 'allow',
                            'CidrBlock': '10.0.0.0/16',
                            'PortRange': {'From': 80, 'To': 80},
                            'Egress': False
                        },
                        {
                            'RuleNumber': 32767,
                            'Protocol': '-1',
                            'RuleAction': 'deny',
                            'CidrBlock': '0.0.0.0/0',
                            'Egress': False
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_network_acls.return_value = nacl_response
        self.mock_session.client.return_value = mock_ec2
        
        self.analyzer._cache_nacl_info("us-east-1")
        
        # Verify NACL was cached
        self.assertIn('acl-12345', self.analyzer.nacl_cache)
        nacl_analysis = self.analyzer.nacl_cache['acl-12345']
        
        self.assertEqual(nacl_analysis.nacl_id, 'acl-12345')
        self.assertEqual(nacl_analysis.nacl_name, 'default-nacl')
        self.assertTrue(nacl_analysis.is_default)
        self.assertEqual(nacl_analysis.vpc_id, 'vpc-12345')
        self.assertEqual(nacl_analysis.associated_subnets, ['subnet-12345'])
        self.assertEqual(len(nacl_analysis.inbound_rules), 2)

    def test_map_resources_to_security_groups(self):
        """Test resource mapping to security groups."""
        # Set up security group cache
        sg_analysis = SecurityGroupAnalysis(
            group_id='sg-12345',
            group_name='web-sg',
            description='Web security group',
            vpc_id='vpc-12345'
        )
        self.analyzer.sg_cache['sg-12345'] = sg_analysis
        
        # Test resources
        resources = [
            {
                'id': 'i-12345',
                'service': 'EC2',
                'security_groups': [{'GroupId': 'sg-12345'}]
            },
            {
                'id': 'i-67890',
                'service': 'EC2',
                'security_groups': [{'GroupId': 'sg-12345'}]
            }
        ]
        
        # First call the internal mapping method to populate associated_resources
        self.analyzer._map_resources_to_security_groups(resources)
        
        # Then call the public method to get enriched resources
        enriched_resources = self.analyzer.map_resources_to_security_groups(resources)
        
        # Check enrichment
        resource1 = enriched_resources[0]
        self.assertIn('security_groups', resource1)
        self.assertEqual(len(resource1['security_groups']), 1)
        self.assertEqual(resource1['security_groups'][0]['id'], 'sg-12345')
        self.assertEqual(resource1['security_groups'][0]['name'], 'web-sg')
        
        # Check that resources were mapped to security group
        self.assertEqual(len(sg_analysis.associated_resources), 2)
        self.assertIn('i-12345', sg_analysis.associated_resources)
        self.assertIn('i-67890', sg_analysis.associated_resources)

    def test_assess_security_group_risks(self):
        """Test security group risk assessment."""
        # Create security group with high-risk rule
        sg_analysis = SecurityGroupAnalysis(
            group_id='sg-high-risk',
            group_name='high-risk-sg',
            description='High risk security group',
            vpc_id='vpc-12345'
        )
        
        # Add critical risk rule
        critical_rule = SecurityRule(
            protocol='tcp',
            port_range='22',
            source_destination='0.0.0.0/0',
            description='SSH from anywhere',
            rule_type='inbound',
            risk_assessment='critical',
            is_permissive=True
        )
        sg_analysis.inbound_rules.append(critical_rule)
        
        # Add low risk rule
        low_rule = SecurityRule(
            protocol='tcp',
            port_range='80',
            source_destination='10.0.0.0/16',
            description='HTTP from internal',
            rule_type='inbound',
            risk_assessment='low'
        )
        sg_analysis.inbound_rules.append(low_rule)
        
        self.analyzer.sg_cache['sg-high-risk'] = sg_analysis
        self.analyzer._assess_security_group_risks()
        
        # Should be assessed as critical due to the critical rule
        self.assertEqual(sg_analysis.risk_level, 'critical')

    def test_identify_overly_permissive_rules(self):
        """Test identification of overly permissive rules."""
        # Create security group with permissive rules
        sg_analysis = SecurityGroupAnalysis(
            group_id='sg-permissive',
            group_name='permissive-sg',
            description='Permissive security group',
            vpc_id='vpc-12345'
        )
        
        # Add permissive inbound rule
        permissive_rule = SecurityRule(
            protocol='tcp',
            port_range='22',
            source_destination='0.0.0.0/0',
            description='SSH from anywhere',
            rule_type='inbound',
            risk_assessment='critical',
            is_permissive=True,
            common_service='SSH'
        )
        sg_analysis.inbound_rules.append(permissive_rule)
        
        # Add non-permissive rule
        safe_rule = SecurityRule(
            protocol='tcp',
            port_range='80',
            source_destination='10.0.0.0/16',
            description='HTTP from internal',
            rule_type='inbound',
            risk_assessment='low'
        )
        sg_analysis.inbound_rules.append(safe_rule)
        
        sg_analysis_dict = {'sg-permissive': sg_analysis}
        risks = self.analyzer.identify_overly_permissive_rules(sg_analysis_dict)
        
        self.assertEqual(len(risks), 1)
        risk = risks[0]
        self.assertEqual(risk['security_group_id'], 'sg-permissive')
        self.assertEqual(risk['rule_type'], 'inbound')
        self.assertEqual(risk['protocol'], 'tcp')
        self.assertEqual(risk['port_range'], '22')
        self.assertEqual(risk['source'], '0.0.0.0/0')
        self.assertEqual(risk['risk_level'], 'critical')
        self.assertEqual(risk['common_service'], 'SSH')

    def test_find_circular_dependencies(self):
        """Test circular dependency detection."""
        # Create two security groups that reference each other
        sg1 = SecurityGroupAnalysis(
            group_id='sg-1',
            group_name='sg-1',
            description='Security group 1',
            vpc_id='vpc-12345',
            references_other_sgs=['sg-2']
        )
        
        sg2 = SecurityGroupAnalysis(
            group_id='sg-2',
            group_name='sg-2',
            description='Security group 2',
            vpc_id='vpc-12345',
            references_other_sgs=['sg-1']
        )
        
        sg_analysis = {'sg-1': sg1, 'sg-2': sg2}
        circular_deps = self.analyzer._find_circular_dependencies(sg_analysis)
        
        self.assertEqual(len(circular_deps), 1)
        self.assertIn(('sg-1', 'sg-2'), circular_deps)

    def test_generate_security_recommendations(self):
        """Test security recommendation generation."""
        # Create unused security group
        unused_sg = SecurityGroupAnalysis(
            group_id='sg-unused',
            group_name='unused-sg',
            description='Unused security group',
            vpc_id='vpc-12345',
            is_unused=True
        )
        
        # Create high-risk security group
        high_risk_sg = SecurityGroupAnalysis(
            group_id='sg-high-risk',
            group_name='high-risk-sg',
            description='High risk security group',
            vpc_id='vpc-12345',
            risk_level='critical'
        )
        
        # Create NACL with optimization recommendations
        nacl_analysis = NACLAnalysis(
            nacl_id='acl-12345',
            nacl_name='test-nacl',
            vpc_id='vpc-12345',
            is_default=False,
            optimization_recommendations=['Test recommendation']
        )
        
        sg_analysis = {'sg-unused': unused_sg, 'sg-high-risk': high_risk_sg}
        nacl_analysis_dict = {'acl-12345': nacl_analysis}
        
        recommendations = self.analyzer._generate_security_recommendations(
            sg_analysis, nacl_analysis_dict
        )
        
        self.assertEqual(len(recommendations), 3)
        self.assertIn('unused security groups', recommendations[0])
        self.assertIn('high-risk security groups', recommendations[1])
        self.assertIn('NACL rules', recommendations[2])

    def test_generate_security_summary(self):
        """Test security summary generation."""
        # Create test security group analysis
        sg1 = SecurityGroupAnalysis(
            group_id='sg-1',
            group_name='sg-1',
            description='Security group 1',
            vpc_id='vpc-12345',
            risk_level='high',
            associated_resources=['i-12345']
        )
        
        # Add permissive rule
        permissive_rule = SecurityRule(
            protocol='tcp',
            port_range='22',
            source_destination='0.0.0.0/0',
            description='SSH from anywhere',
            rule_type='inbound',
            risk_assessment='critical',
            is_permissive=True
        )
        sg1.inbound_rules.append(permissive_rule)
        
        sg2 = SecurityGroupAnalysis(
            group_id='sg-2',
            group_name='sg-2',
            description='Unused security group',
            vpc_id='vpc-12345',
            is_unused=True
        )
        
        # Create test NACL analysis
        nacl1 = NACLAnalysis(
            nacl_id='acl-1',
            nacl_name='nacl-1',
            vpc_id='vpc-12345',
            is_default=False,
            optimization_recommendations=['Test rec 1', 'Test rec 2']
        )
        
        analysis = {
            'security_groups': {'sg-1': sg1, 'sg-2': sg2},
            'nacls': {'acl-1': nacl1}
        }
        
        # Mock the methods that generate recommendations and find dependencies
        self.analyzer._generate_security_recommendations = Mock(return_value=['rec1', 'rec2'])
        self.analyzer._find_circular_dependencies = Mock(return_value=[('sg-1', 'sg-2')])
        
        summary = self.analyzer.generate_security_summary(analysis)
        
        self.assertEqual(summary.total_security_groups, 2)
        self.assertEqual(summary.overly_permissive_rules, 1)
        self.assertEqual(summary.unused_security_groups, 1)
        self.assertEqual(summary.high_risk_resources, ['i-12345'])
        self.assertEqual(summary.total_nacls, 1)
        self.assertEqual(summary.nacl_optimization_opportunities, 2)
        self.assertEqual(summary.circular_dependencies, [('sg-1', 'sg-2')])

    @patch('inventag.discovery.security_analyzer.logger')
    def test_analyze_security_groups_integration(self, mock_logger):
        """Test the main analyze_security_groups method integration."""
        # Mock the session and EC2 client
        mock_ec2 = Mock()
        self.mock_session.client.return_value = mock_ec2
        
        # Mock security group response
        mock_ec2.describe_security_groups.return_value = {
            'SecurityGroups': [{
                'GroupId': 'sg-12345',
                'GroupName': 'test-sg',
                'Description': 'Test security group',
                'VpcId': 'vpc-12345',
                'Tags': [{'Key': 'Name', 'Value': 'TestSG'}],
                'IpPermissions': [],
                'IpPermissionsEgress': []
            }]
        }
        
        # Test resources
        resources = [
            {
                'id': 'i-12345',
                'service': 'EC2',
                'region': 'us-east-1',
                'security_groups': [{'GroupId': 'sg-12345'}]
            }
        ]
        
        result = self.analyzer.analyze_security_groups(resources)
        
        # Verify results
        self.assertIn('sg-12345', result)
        sg_analysis = result['sg-12345']
        self.assertEqual(sg_analysis.group_name, 'test-sg')
        self.assertEqual(sg_analysis.associated_resources, ['i-12345'])


if __name__ == '__main__':
    unittest.main()