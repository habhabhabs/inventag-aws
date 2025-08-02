#!/usr/bin/env python3
"""
CI/CD integration tests for InvenTag BOM generation

Tests integration with CI/CD pipelines, GitHub Actions compatibility,
and automated workflow scenarios.
"""

import pytest
import tempfile
import json
import os
import subprocess
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from inventag.core.cicd_integration import CICDIntegration
from inventag.core.cloud_bom_generator import CloudBOMGenerator


class TestCICDIntegration:
    """Integration tests for CI/CD pipeline compatibility."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, 'output')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Mock environment variables for CI/CD
        self.ci_env = {
            'GITHUB_ACTIONS': 'true',
            'GITHUB_WORKSPACE': self.temp_dir,
            'GITHUB_REPOSITORY': 'test-org/test-repo',
            'GITHUB_SHA': 'abc123def456',
            'GITHUB_REF': 'refs/heads/main'
        }

    def test_github_actions_environment_detection(self):
        """Test detection of GitHub Actions environment."""
        with patch.dict(os.environ, self.ci_env):
            integration = CICDIntegration()
            
            assert integration.is_github_actions() is True
            assert integration.get_repository_info()['name'] == 'test-org/test-repo'
            assert integration.get_commit_sha() == 'abc123def456'
            assert integration.get_branch_name() == 'main'

    def test_cicd_artifact_generation(self):
        """Test generation of CI/CD artifacts."""
        sample_resources = [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
                'id': 'i-12345',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'compliance_status': 'compliant'
            }
        ]
        
        config = {
            'output_directory': self.output_dir,
            'output_formats': ['json'],
            'cicd': {
                'generate_artifacts': True,
                'artifact_formats': ['json', 'junit'],
                'upload_to_s3': False
            }
        }
        
        with patch.dict(os.environ, self.ci_env):
            integration = CICDIntegration(config)
            
            # Mock BOM generation
            with patch('inventag.core.cloud_bom_generator.CloudBOMGenerator') as mock_generator:
                mock_generator_instance = Mock()
                mock_generator_instance.generate_bom.return_value = {
                    'resources': sample_resources,
                    'compliance_summary': {
                        'total_resources': 1,
                        'compliant_resources': 1,
                        'compliance_percentage': 100.0
                    }
                }
                mock_generator.return_value = mock_generator_instance
                
                artifacts = integration.generate_cicd_artifacts(sample_resources)
                
                # Verify artifacts were generated
                assert 'json' in artifacts
                assert 'junit' in artifacts
                assert artifacts['json']['success'] is True

    def test_compliance_gate_checking(self):
        """Test compliance gate checking for CI/CD pipelines."""
        # Test passing compliance
        passing_summary = {
            'total_resources': 100,
            'compliant_resources': 95,
            'compliance_percentage': 95.0,
            'violations': []
        }
        
        config = {
            'compliance_gates': {
                'minimum_compliance_percentage': 90.0,
                'fail_on_critical_violations': True,
                'allowed_violation_types': ['missing_tag']
            }
        }
        
        integration = CICDIntegration(config)
        
        # Should pass
        gate_result = integration.check_compliance_gates(passing_summary)
        assert gate_result['passed'] is True
        assert gate_result['exit_code'] == 0
        
        # Test failing compliance
        failing_summary = {
            'total_resources': 100,
            'compliant_resources': 80,
            'compliance_percentage': 80.0,
            'violations': [
                {'type': 'critical', 'resource': 'i-12345', 'message': 'Critical violation'}
            ]
        }
        
        gate_result = integration.check_compliance_gates(failing_summary)
        assert gate_result['passed'] is False
        assert gate_result['exit_code'] == 1
        assert 'compliance percentage' in gate_result['failure_reason'].lower()

    def test_s3_upload_integration(self):
        """Test S3 upload integration for CI/CD artifacts."""
        config = {
            'cicd': {
                'upload_to_s3': True,
                's3_bucket': 'test-compliance-bucket',
                's3_key_prefix': 'bom-reports/',
                's3_region': 'us-east-1'
            }
        }
        
        # Mock S3 client
        with patch('boto3.client') as mock_boto3:
            mock_s3 = Mock()
            mock_boto3.return_value = mock_s3
            
            integration = CICDIntegration(config)
            
            # Test file upload
            test_file = os.path.join(self.temp_dir, 'test-report.json')
            with open(test_file, 'w') as f:
                json.dump({'test': 'data'}, f)
            
            result = integration.upload_to_s3(test_file, 'test-report.json')
            
            # Verify S3 upload was called
            mock_s3.upload_file.assert_called_once()
            assert result['success'] is True
            assert 'test-compliance-bucket' in result['s3_url']

    def test_notification_generation(self):
        """Test notification generation for CI/CD results."""
        compliance_summary = {
            'total_resources': 150,
            'compliant_resources': 140,
            'compliance_percentage': 93.3,
            'violations': [
                {'type': 'missing_tag', 'count': 10}
            ]
        }
        
        config = {
            'notifications': {
                'slack_webhook': 'https://hooks.slack.com/test',
                'teams_webhook': 'https://outlook.office.com/test',
                'include_metrics': True
            }
        }
        
        with patch.dict(os.environ, self.ci_env):
            integration = CICDIntegration(config)
            
            # Mock HTTP requests
            with patch('requests.post') as mock_post:
                mock_post.return_value.status_code = 200
                
                # Generate Slack notification
                slack_result = integration.send_slack_notification(compliance_summary)
                assert slack_result['success'] is True
                
                # Generate Teams notification
                teams_result = integration.send_teams_notification(compliance_summary)
                assert teams_result['success'] is True
                
                # Verify notifications were sent
                assert mock_post.call_count == 2

    def test_prometheus_metrics_export(self):
        """Test Prometheus metrics export for monitoring."""
        compliance_summary = {
            'total_resources': 200,
            'compliant_resources': 180,
            'compliance_percentage': 90.0,
            'violations': [
                {'type': 'missing_tag', 'count': 15},
                {'type': 'encryption_disabled', 'count': 5}
            ]
        }
        
        config = {
            'monitoring': {
                'prometheus_pushgateway': 'http://localhost:9091',
                'job_name': 'inventag-compliance',
                'instance': 'ci-pipeline'
            }
        }
        
        integration = CICDIntegration(config)
        
        # Mock Prometheus push gateway
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            
            result = integration.export_prometheus_metrics(compliance_summary)
            
            assert result['success'] is True
            mock_post.assert_called_once()
            
            # Verify metrics format
            call_args = mock_post.call_args
            metrics_data = call_args[1]['data']
            
            assert 'inventag_total_resources' in metrics_data
            assert 'inventag_compliant_resources' in metrics_data
            assert 'inventag_compliance_percentage' in metrics_data

    def test_junit_xml_generation(self):
        """Test JUnit XML generation for CI/CD test reporting."""
        compliance_results = {
            'total_resources': 50,
            'compliant_resources': 45,
            'violations': [
                {
                    'resource_id': 'i-12345',
                    'resource_type': 'EC2 Instance',
                    'violation_type': 'missing_tag',
                    'message': 'Missing required tag: CostCenter',
                    'severity': 'medium'
                },
                {
                    'resource_id': 's3-bucket-1',
                    'resource_type': 'S3 Bucket',
                    'violation_type': 'encryption_disabled',
                    'message': 'Bucket encryption is not enabled',
                    'severity': 'high'
                }
            ]
        }
        
        integration = CICDIntegration({})
        
        junit_xml = integration.generate_junit_xml(compliance_results)
        
        # Verify JUnit XML structure
        assert '<?xml version="1.0"' in junit_xml
        assert '<testsuite' in junit_xml
        assert '<testcase' in junit_xml
        assert 'missing_tag' in junit_xml
        assert 'encryption_disabled' in junit_xml
        
        # Parse and validate XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(junit_xml)
        
        assert root.tag == 'testsuite'
        assert root.get('tests') == '50'  # Total resources
        assert root.get('failures') == '5'  # Non-compliant resources
        
        # Check test cases
        testcases = root.findall('testcase')
        assert len(testcases) == 50
        
        # Check failures
        failures = root.findall('.//failure')
        assert len(failures) == 5

    def test_github_actions_workflow_simulation(self):
        """Test simulation of complete GitHub Actions workflow."""
        # Simulate GitHub Actions environment
        github_env = {
            **self.ci_env,
            'INPUT_AWS_REGION': 'us-east-1',
            'INPUT_OUTPUT_FORMATS': 'excel,csv',
            'INPUT_COMPLIANCE_THRESHOLD': '90',
            'INPUT_S3_BUCKET': 'test-bucket',
            'INPUT_SLACK_WEBHOOK': 'https://hooks.slack.com/test'
        }
        
        with patch.dict(os.environ, github_env):
            # Mock AWS session
            with patch('boto3.Session') as mock_session:
                mock_session_instance = Mock()
                mock_session.return_value = mock_session_instance
                
                # Mock resource discovery
                with patch('inventag.discovery.inventory.ResourceDiscovery') as mock_discovery:
                    mock_discovery_instance = Mock()
                    mock_discovery_instance.discover_all_resources.return_value = [
                        {
                            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-12345',
                            'id': 'i-12345',
                            'service': 'EC2',
                            'type': 'Instance',
                            'compliance_status': 'compliant'
                        }
                    ]
                    mock_discovery.return_value = mock_discovery_instance
                    
                    # Mock compliance checking
                    with patch('inventag.compliance.checker.ComplianceChecker') as mock_compliance:
                        mock_compliance_instance = Mock()
                        mock_compliance_instance.check_compliance.return_value = {
                            'total_resources': 1,
                            'compliant_resources': 1,
                            'compliance_percentage': 100.0,
                            'violations': []
                        }
                        mock_compliance.return_value = mock_compliance_instance
                        
                        # Mock document generation
                        with patch('inventag.reporting.document_generator.DocumentGenerator') as mock_doc_gen:
                            mock_doc_gen_instance = Mock()
                            mock_doc_gen_instance.generate_bom_documents.return_value = Mock(
                                successful_formats=2,
                                failed_formats=0
                            )
                            mock_doc_gen.return_value = mock_doc_gen_instance
                            
                            # Mock S3 upload
                            with patch('boto3.client') as mock_boto3:
                                mock_s3 = Mock()
                                mock_boto3.return_value = mock_s3
                                
                                # Mock notifications
                                with patch('requests.post') as mock_post:
                                    mock_post.return_value.status_code = 200
                                    
                                    # Run the workflow
                                    config = {
                                        'output_formats': ['excel', 'csv'],
                                        'compliance_gates': {
                                            'minimum_compliance_percentage': 90.0
                                        },
                                        'cicd': {
                                            'upload_to_s3': True,
                                            's3_bucket': 'test-bucket'
                                        },
                                        'notifications': {
                                            'slack_webhook': 'https://hooks.slack.com/test'
                                        }
                                    }
                                    
                                    integration = CICDIntegration(config)
                                    generator = CloudBOMGenerator(
                                        session=mock_session_instance,
                                        config=config
                                    )
                                    
                                    # Execute workflow steps
                                    bom_result = generator.generate_bom()
                                    compliance_gates = integration.check_compliance_gates(
                                        bom_result.get('compliance_summary', {})
                                    )
                                    
                                    # Verify workflow completed successfully
                                    assert bom_result is not None
                                    assert compliance_gates['passed'] is True
                                    
                                    # Verify all components were called
                                    mock_discovery_instance.discover_all_resources.assert_called_once()
                                    mock_compliance_instance.check_compliance.assert_called_once()
                                    mock_doc_gen_instance.generate_bom_documents.assert_called_once()

    def test_codebuild_integration(self):
        """Test AWS CodeBuild integration."""
        codebuild_env = {
            'CODEBUILD_BUILD_ID': 'test-project:12345',
            'CODEBUILD_BUILD_ARN': 'arn:aws:codebuild:us-east-1:123456789012:build/test-project:12345',
            'CODEBUILD_SOURCE_REPO_URL': 'https://github.com/test-org/test-repo.git',
            'CODEBUILD_SOURCE_VERSION': 'abc123def456'
        }
        
        with patch.dict(os.environ, codebuild_env):
            integration = CICDIntegration({})
            
            assert integration.is_codebuild() is True
            assert integration.get_build_id() == 'test-project:12345'
            
            # Test CodeBuild-specific artifact handling
            artifacts = integration.prepare_codebuild_artifacts({
                'compliance_summary': {
                    'total_resources': 100,
                    'compliant_resources': 95,
                    'compliance_percentage': 95.0
                }
            })
            
            assert 'buildspec_outputs' in artifacts
            assert 'compliance_report' in artifacts

    def test_error_handling_in_cicd(self):
        """Test error handling in CI/CD scenarios."""
        config = {
            'cicd': {
                'fail_on_errors': True,
                'retry_attempts': 3
            }
        }
        
        integration = CICDIntegration(config)
        
        # Test discovery failure
        with patch('inventag.discovery.inventory.ResourceDiscovery') as mock_discovery:
            mock_discovery_instance = Mock()
            mock_discovery_instance.discover_all_resources.side_effect = Exception("AWS API Error")
            mock_discovery.return_value = mock_discovery_instance
            
            # Should handle error gracefully in CI/CD mode
            result = integration.handle_discovery_error(Exception("AWS API Error"))
            
            assert result['success'] is False
            assert result['exit_code'] == 1
            assert 'AWS API Error' in result['error_message']

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


if __name__ == '__main__':
    pytest.main([__file__])