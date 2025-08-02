#!/usr/bin/env python3
"""
CI/CD Integration Components

CI/CD integration system for automated BOM generation and compliance checking with:
- CI/CD artifact generation for pipeline consumption
- S3 upload functionality with format-specific CLI options (--create-word, --create-excel)
- Configurable S3 bucket and key prefix support for document storage
- Compliance gate checking for pipeline control
- Notification generation for Slack/Teams integration with S3 document links
- Prometheus metrics export for monitoring systems
"""

import logging
import json
import boto3
import requests
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import tempfile
import os
from botocore.exceptions import ClientError

from .cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
from ..reporting.bom_processor import BOMData


@dataclass
class S3UploadConfig:
    """Configuration for S3 document upload."""
    bucket_name: str
    key_prefix: str = "inventag-bom"
    region: str = "us-east-1"
    encryption: str = "AES256"  # AES256 or aws:kms
    kms_key_id: Optional[str] = None
    public_read: bool = False
    lifecycle_days: int = 90
    storage_class: str = "STANDARD"  # STANDARD, STANDARD_IA, GLACIER, etc.


@dataclass
class ComplianceGateConfig:
    """Configuration for compliance gate checking."""
    minimum_compliance_percentage: float = 80.0
    critical_violations_threshold: int = 0
    required_tags: List[str] = field(default_factory=list)
    allowed_non_compliant_services: List[str] = field(default_factory=list)
    fail_on_security_issues: bool = True
    fail_on_network_issues: bool = False


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    slack_webhook_url: Optional[str] = None
    teams_webhook_url: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    include_summary: bool = True
    include_document_links: bool = True
    notify_on_success: bool = True
    notify_on_failure: bool = True


@dataclass
class PrometheusConfig:
    """Configuration for Prometheus metrics export."""
    push_gateway_url: Optional[str] = None
    job_name: str = "inventag-bom"
    instance_name: str = "default"
    push_on_success: bool = True
    push_on_failure: bool = True
    include_resource_counts: bool = True
    include_compliance_metrics: bool = True
    include_timing_metrics: bool = True


@dataclass
class PrometheusMetrics:
    """Prometheus metrics for monitoring."""
    total_resources: int = 0
    compliant_resources: int = 0
    non_compliant_resources: int = 0
    compliance_percentage: float = 0.0
    processing_time_seconds: float = 0.0
    successful_accounts: int = 0
    failed_accounts: int = 0
    total_accounts: int = 0
    security_issues: int = 0
    network_issues: int = 0
    document_generation_time: float = 0.0
    s3_upload_time: float = 0.0


@dataclass
class CICDResult:
    """Result of CI/CD integration execution."""
    success: bool
    compliance_gate_passed: bool = False
    generated_documents: List[str] = field(default_factory=list)
    s3_uploads: Dict[str, str] = field(default_factory=dict)  # format -> S3 URL
    notifications_sent: List[str] = field(default_factory=list)
    metrics: Optional[PrometheusMetrics] = None
    error_message: str = ""
    execution_time_seconds: float = 0.0
    artifacts: Dict[str, Any] = field(default_factory=dict)


class CICDIntegration:
    """
    CI/CD integration system for automated BOM generation and compliance checking.
    
    Features:
    - CI/CD artifact generation for pipeline consumption
    - S3 upload functionality with format-specific CLI options
    - Configurable S3 bucket and key prefix support for document storage
    - Compliance gate checking for pipeline control
    - Notification generation for Slack/Teams integration with S3 document links
    - Prometheus metrics export for monitoring systems
    """

    def __init__(self, 
                 s3_config: Optional[S3UploadConfig] = None,
                 compliance_gate_config: Optional[ComplianceGateConfig] = None,
                 notification_config: Optional[NotificationConfig] = None,
                 prometheus_config: Optional[PrometheusConfig] = None):
        """Initialize the CI/CD integration system."""
        self.logger = logging.getLogger(f"{__name__}.CICDIntegration")
        
        self.s3_config = s3_config
        self.compliance_gate_config = compliance_gate_config or ComplianceGateConfig()
        self.notification_config = notification_config or NotificationConfig()
        self.prometheus_config = prometheus_config or PrometheusConfig()
        
        # Initialize AWS clients
        self.s3_client = None
        if s3_config:
            self.s3_client = boto3.client('s3', region_name=s3_config.region)
        
        self.logger.info("Initialized CICDIntegration")

    def execute_pipeline_integration(self,
                                   bom_generator: CloudBOMGenerator,
                                   output_formats: List[str] = None,
                                   compliance_policies: Optional[Dict] = None,
                                   upload_to_s3: bool = True,
                                   send_notifications: bool = True,
                                   export_metrics: bool = True) -> CICDResult:
        """
        Execute complete CI/CD pipeline integration.
        
        Args:
            bom_generator: Configured CloudBOMGenerator instance
            output_formats: List of document formats to generate
            compliance_policies: Compliance policies to apply
            upload_to_s3: Whether to upload documents to S3
            send_notifications: Whether to send notifications
            export_metrics: Whether to export Prometheus metrics
            
        Returns:
            CICDResult with execution details
        """
        start_time = datetime.now(timezone.utc)
        self.logger.info("Starting CI/CD pipeline integration")
        
        result = CICDResult(success=False)
        
        try:
            # Step 1: Generate multi-account BOM
            self.logger.info("Generating multi-account BOM")
            bom_results = bom_generator.generate_multi_account_bom(
                output_formats=output_formats or ["excel", "word", "json"],
                compliance_policies=compliance_policies
            )
            
            if not bom_results.get("success", False):
                result.error_message = f"BOM generation failed: {bom_results.get('error', 'Unknown error')}"
                return result
            
            result.generated_documents = bom_results.get("bom_generation", {}).get("generated_files", [])
            
            # Step 2: Check compliance gate
            self.logger.info("Checking compliance gate")
            compliance_results = bom_results.get("compliance_analysis", {})
            result.compliance_gate_passed = self._check_compliance_gate(compliance_results)
            
            # Step 3: Upload documents to S3 if configured
            if upload_to_s3 and self.s3_config and result.generated_documents:
                self.logger.info("Uploading documents to S3")
                s3_uploads = self._upload_documents_to_s3(result.generated_documents)
                result.s3_uploads = s3_uploads
            
            # Step 4: Generate CI/CD artifacts
            self.logger.info("Generating CI/CD artifacts")
            artifacts = self._generate_cicd_artifacts(bom_results, result)
            result.artifacts = artifacts
            
            # Step 5: Send notifications if configured
            if send_notifications and self.notification_config:
                self.logger.info("Sending notifications")
                notifications_sent = self._send_notifications(bom_results, result)
                result.notifications_sent = notifications_sent
            
            # Step 6: Export Prometheus metrics if configured
            if export_metrics:
                self.logger.info("Exporting Prometheus metrics")
                metrics = self._generate_prometheus_metrics(bom_results, result)
                result.metrics = metrics
                self._export_prometheus_metrics(metrics, self.prometheus_config.push_gateway_url)
            
            # Calculate execution time
            end_time = datetime.now(timezone.utc)
            result.execution_time_seconds = (end_time - start_time).total_seconds()
            
            result.success = True
            
            self.logger.info(
                f"CI/CD pipeline integration completed successfully in {result.execution_time_seconds:.2f}s. "
                f"Compliance gate: {'PASSED' if result.compliance_gate_passed else 'FAILED'}"
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            result.execution_time_seconds = (end_time - start_time).total_seconds()
            result.error_message = str(e)
            
            self.logger.error(f"CI/CD pipeline integration failed: {e}")
            
            # Send failure notification
            if send_notifications and self.notification_config and self.notification_config.notify_on_failure:
                try:
                    self._send_failure_notification(result)
                except Exception as notify_error:
                    self.logger.error(f"Failed to send failure notification: {notify_error}")
            
            return result

    def _check_compliance_gate(self, compliance_results: Dict[str, Any]) -> bool:
        """
        Check if compliance gate criteria are met.
        
        Args:
            compliance_results: Compliance analysis results
            
        Returns:
            True if compliance gate passes, False otherwise
        """
        if not compliance_results:
            self.logger.warning("No compliance results available for gate checking")
            return False
        
        try:
            # Check minimum compliance percentage
            total_resources = compliance_results.get("total_resources", 0)
            compliant_resources = compliance_results.get("compliant_resources", 0)
            
            if total_resources == 0:
                self.logger.warning("No resources found for compliance checking")
                return False
            
            compliance_percentage = (compliant_resources / total_resources) * 100
            
            if compliance_percentage < self.compliance_gate_config.minimum_compliance_percentage:
                self.logger.warning(
                    f"Compliance percentage {compliance_percentage:.1f}% below threshold "
                    f"{self.compliance_gate_config.minimum_compliance_percentage}%"
                )
                return False
            
            # Check critical violations threshold
            critical_violations = compliance_results.get("critical_violations", 0)
            if critical_violations > self.compliance_gate_config.critical_violations_threshold:
                self.logger.warning(
                    f"Critical violations {critical_violations} exceed threshold "
                    f"{self.compliance_gate_config.critical_violations_threshold}"
                )
                return False
            
            # Check required tags compliance
            if self.compliance_gate_config.required_tags:
                missing_required_tags = compliance_results.get("missing_required_tags", [])
                if missing_required_tags:
                    self.logger.warning(f"Missing required tags: {missing_required_tags}")
                    return False
            
            # Check security issues if configured
            if self.compliance_gate_config.fail_on_security_issues:
                security_issues = compliance_results.get("security_issues", 0)
                if security_issues > 0:
                    self.logger.warning(f"Security issues found: {security_issues}")
                    return False
            
            # Check network issues if configured
            if self.compliance_gate_config.fail_on_network_issues:
                network_issues = compliance_results.get("network_issues", 0)
                if network_issues > 0:
                    self.logger.warning(f"Network issues found: {network_issues}")
                    return False
            
            self.logger.info(f"Compliance gate passed: {compliance_percentage:.1f}% compliance")
            return True
            
        except Exception as e:
            self.logger.error(f"Compliance gate checking failed: {e}")
            return False

    def _upload_documents_to_s3(self, document_files: List[str]) -> Dict[str, str]:
        """
        Upload generated documents to S3.
        
        Args:
            document_files: List of local document file paths
            
        Returns:
            Dictionary mapping format to S3 URL
        """
        if not self.s3_client or not self.s3_config:
            self.logger.warning("S3 upload requested but not configured")
            return {}
        
        s3_uploads = {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        for file_path in document_files:
            try:
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    self.logger.warning(f"Document file not found: {file_path}")
                    continue
                
                # Determine format from file extension
                format_type = file_path_obj.suffix.lower().lstrip('.')
                
                # Generate S3 key
                s3_key = f"{self.s3_config.key_prefix}/{timestamp}/{file_path_obj.name}"
                
                # Prepare upload parameters
                upload_params = {
                    'Bucket': self.s3_config.bucket_name,
                    'Key': s3_key,
                    'ServerSideEncryption': self.s3_config.encryption
                }
                
                if self.s3_config.encryption == 'aws:kms' and self.s3_config.kms_key_id:
                    upload_params['SSEKMSKeyId'] = self.s3_config.kms_key_id
                
                if self.s3_config.public_read:
                    upload_params['ACL'] = 'public-read'
                
                if self.s3_config.storage_class != 'STANDARD':
                    upload_params['StorageClass'] = self.s3_config.storage_class
                
                # Upload file
                with open(file_path, 'rb') as f:
                    self.s3_client.upload_fileobj(f, **upload_params)
                
                # Generate S3 URL
                s3_url = f"https://{self.s3_config.bucket_name}.s3.{self.s3_config.region}.amazonaws.com/{s3_key}"
                s3_uploads[format_type] = s3_url
                
                self.logger.info(f"Uploaded {format_type} document to S3: {s3_url}")
                
                # Set lifecycle policy if configured
                if self.s3_config.lifecycle_days > 0:
                    self._set_s3_lifecycle_policy(s3_key)
                
            except Exception as e:
                self.logger.error(f"Failed to upload {file_path} to S3: {e}")
        
        return s3_uploads

    def _set_s3_lifecycle_policy(self, s3_key: str):
        """Set lifecycle policy for uploaded S3 object."""
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'InvenTagBOMLifecycle',
                        'Status': 'Enabled',
                        'Filter': {'Prefix': self.s3_config.key_prefix},
                        'Expiration': {'Days': self.s3_config.lifecycle_days}
                    }
                ]
            }
            
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.s3_config.bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            
        except ClientError as e:
            # Lifecycle policy might already exist or we might not have permissions
            self.logger.debug(f"Could not set lifecycle policy: {e}")

    def _generate_cicd_artifacts(self, bom_results: Dict[str, Any], cicd_result: CICDResult) -> Dict[str, Any]:
        """
        Generate CI/CD artifacts for pipeline consumption.
        
        Args:
            bom_results: BOM generation results
            cicd_result: CI/CD execution result
            
        Returns:
            Dictionary of CI/CD artifacts
        """
        artifacts = {}
        
        try:
            # Generate pipeline summary artifact
            pipeline_summary = {
                "execution_timestamp": datetime.now(timezone.utc).isoformat(),
                "success": cicd_result.success,
                "compliance_gate_passed": cicd_result.compliance_gate_passed,
                "execution_time_seconds": cicd_result.execution_time_seconds,
                "generated_documents": len(cicd_result.generated_documents),
                "s3_uploads": len(cicd_result.s3_uploads),
                "notifications_sent": len(cicd_result.notifications_sent)
            }
            
            # Add processing statistics
            processing_stats = bom_results.get("processing_statistics", {})
            pipeline_summary.update({
                "total_accounts": processing_stats.get("total_accounts", 0),
                "successful_accounts": processing_stats.get("successful_accounts", 0),
                "failed_accounts": processing_stats.get("failed_accounts", 0),
                "total_resources": processing_stats.get("total_resources", 0)
            })
            
            artifacts["pipeline_summary.json"] = pipeline_summary
            
            # Generate compliance gate artifact
            compliance_gate = {
                "passed": cicd_result.compliance_gate_passed,
                "configuration": {
                    "minimum_compliance_percentage": self.compliance_gate_config.minimum_compliance_percentage,
                    "critical_violations_threshold": self.compliance_gate_config.critical_violations_threshold,
                    "required_tags": self.compliance_gate_config.required_tags,
                    "fail_on_security_issues": self.compliance_gate_config.fail_on_security_issues,
                    "fail_on_network_issues": self.compliance_gate_config.fail_on_network_issues
                },
                "results": bom_results.get("compliance_analysis", {})
            }
            
            artifacts["compliance_gate.json"] = compliance_gate
            
            # Generate S3 links artifact if uploads were performed
            if cicd_result.s3_uploads:
                s3_links = {
                    "bucket": self.s3_config.bucket_name if self.s3_config else "",
                    "region": self.s3_config.region if self.s3_config else "",
                    "documents": cicd_result.s3_uploads,
                    "upload_timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                artifacts["s3_links.json"] = s3_links
            
            # Generate account summary artifact
            account_contexts = bom_results.get("account_contexts", {})
            account_summary = {
                "total_accounts": len(account_contexts),
                "accounts": [
                    {
                        "account_id": acc_id,
                        "account_name": ctx.get("account_name", ""),
                        "resource_count": ctx.get("resource_count", 0),
                        "processing_time_seconds": ctx.get("processing_time_seconds", 0),
                        "error_count": ctx.get("error_count", 0),
                        "accessible_regions": ctx.get("accessible_regions", []),
                        "discovered_services": ctx.get("discovered_services", [])
                    }
                    for acc_id, ctx in account_contexts.items()
                ]
            }
            
            artifacts["account_summary.json"] = account_summary
            
            # Write artifacts to files
            for artifact_name, artifact_data in artifacts.items():
                artifact_path = Path(tempfile.gettempdir()) / artifact_name
                with open(artifact_path, 'w') as f:
                    json.dump(artifact_data, f, indent=2, default=str)
                
                self.logger.info(f"Generated CI/CD artifact: {artifact_path}")
            
            return artifacts
            
        except Exception as e:
            self.logger.error(f"Failed to generate CI/CD artifacts: {e}")
            return {}

    def _send_notifications(self, bom_results: Dict[str, Any], cicd_result: CICDResult) -> List[str]:
        """
        Send notifications to configured channels.
        
        Args:
            bom_results: BOM generation results
            cicd_result: CI/CD execution result
            
        Returns:
            List of notification channels that were notified
        """
        notifications_sent = []
        
        if not self.notification_config.notify_on_success and cicd_result.success:
            return notifications_sent
        
        try:
            # Prepare notification content
            notification_content = self._prepare_notification_content(bom_results, cicd_result)
            
            # Send Slack notification
            if self.notification_config.slack_webhook_url:
                try:
                    self._send_slack_notification(notification_content)
                    notifications_sent.append("slack")
                except Exception as e:
                    self.logger.error(f"Failed to send Slack notification: {e}")
            
            # Send Teams notification
            if self.notification_config.teams_webhook_url:
                try:
                    self._send_teams_notification(notification_content)
                    notifications_sent.append("teams")
                except Exception as e:
                    self.logger.error(f"Failed to send Teams notification: {e}")
            
            # Send email notifications
            if self.notification_config.email_recipients:
                try:
                    self._send_email_notifications(notification_content)
                    notifications_sent.append("email")
                except Exception as e:
                    self.logger.error(f"Failed to send email notifications: {e}")
            
            return notifications_sent
            
        except Exception as e:
            self.logger.error(f"Failed to send notifications: {e}")
            return notifications_sent

    def _prepare_notification_content(self, bom_results: Dict[str, Any], cicd_result: CICDResult) -> Dict[str, Any]:
        """Prepare notification content."""
        processing_stats = bom_results.get("processing_statistics", {})
        compliance_results = bom_results.get("compliance_analysis", {})
        
        # Calculate compliance percentage
        total_resources = processing_stats.get("total_resources", 0)
        compliance_percentage = 0.0
        if total_resources > 0:
            compliant_resources = compliance_results.get("compliant_resources", 0)
            compliance_percentage = (compliant_resources / total_resources) * 100
        
        content = {
            "title": "InvenTag Multi-Account BOM Generation Complete",
            "status": "SUCCESS" if cicd_result.success else "FAILED",
            "compliance_gate": "PASSED" if cicd_result.compliance_gate_passed else "FAILED",
            "summary": {
                "total_accounts": processing_stats.get("total_accounts", 0),
                "successful_accounts": processing_stats.get("successful_accounts", 0),
                "failed_accounts": processing_stats.get("failed_accounts", 0),
                "total_resources": total_resources,
                "compliance_percentage": round(compliance_percentage, 1),
                "execution_time": round(cicd_result.execution_time_seconds, 1),
                "generated_documents": len(cicd_result.generated_documents),
                "s3_uploads": len(cicd_result.s3_uploads)
            },
            "document_links": cicd_result.s3_uploads if self.notification_config.include_document_links else {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if not cicd_result.success:
            content["error_message"] = cicd_result.error_message
        
        return content

    def _send_slack_notification(self, content: Dict[str, Any]):
        """Send Slack notification."""
        status_color = "good" if content["status"] == "SUCCESS" else "danger"
        gate_color = "good" if content["compliance_gate"] == "PASSED" else "warning"
        
        slack_payload = {
            "text": content["title"],
            "attachments": [
                {
                    "color": status_color,
                    "fields": [
                        {
                            "title": "Status",
                            "value": content["status"],
                            "short": True
                        },
                        {
                            "title": "Compliance Gate",
                            "value": content["compliance_gate"],
                            "short": True
                        },
                        {
                            "title": "Accounts",
                            "value": f"{content['summary']['successful_accounts']}/{content['summary']['total_accounts']} successful",
                            "short": True
                        },
                        {
                            "title": "Resources",
                            "value": f"{content['summary']['total_resources']} ({content['summary']['compliance_percentage']}% compliant)",
                            "short": True
                        },
                        {
                            "title": "Execution Time",
                            "value": f"{content['summary']['execution_time']}s",
                            "short": True
                        },
                        {
                            "title": "Documents Generated",
                            "value": str(content['summary']['generated_documents']),
                            "short": True
                        }
                    ],
                    "footer": "InvenTag CI/CD Integration",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }
        
        # Add document links if available
        if content["document_links"]:
            links_text = "\n".join([
                f"• {format_type.upper()}: <{url}|Download>"
                for format_type, url in content["document_links"].items()
            ])
            slack_payload["attachments"].append({
                "color": "good",
                "title": "Generated Documents",
                "text": links_text
            })
        
        # Add error message if failed
        if content["status"] == "FAILED" and content.get("error_message"):
            slack_payload["attachments"].append({
                "color": "danger",
                "title": "Error Details",
                "text": content["error_message"]
            })
        
        response = requests.post(
            self.notification_config.slack_webhook_url,
            json=slack_payload,
            timeout=30
        )
        response.raise_for_status()

    def _send_teams_notification(self, content: Dict[str, Any]):
        """Send Microsoft Teams notification."""
        status_color = "Good" if content["status"] == "SUCCESS" else "Attention"
        
        teams_payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "00FF00" if content["status"] == "SUCCESS" else "FF0000",
            "summary": content["title"],
            "sections": [
                {
                    "activityTitle": content["title"],
                    "activitySubtitle": f"Status: {content['status']} | Compliance Gate: {content['compliance_gate']}",
                    "facts": [
                        {
                            "name": "Total Accounts",
                            "value": str(content['summary']['total_accounts'])
                        },
                        {
                            "name": "Successful Accounts",
                            "value": str(content['summary']['successful_accounts'])
                        },
                        {
                            "name": "Total Resources",
                            "value": str(content['summary']['total_resources'])
                        },
                        {
                            "name": "Compliance Percentage",
                            "value": f"{content['summary']['compliance_percentage']}%"
                        },
                        {
                            "name": "Execution Time",
                            "value": f"{content['summary']['execution_time']}s"
                        },
                        {
                            "name": "Documents Generated",
                            "value": str(content['summary']['generated_documents'])
                        }
                    ],
                    "markdown": True
                }
            ]
        }
        
        # Add document links if available
        if content["document_links"]:
            actions = []
            for format_type, url in content["document_links"].items():
                actions.append({
                    "@type": "OpenUri",
                    "name": f"Download {format_type.upper()}",
                    "targets": [{"os": "default", "uri": url}]
                })
            
            teams_payload["potentialAction"] = actions
        
        response = requests.post(
            self.notification_config.teams_webhook_url,
            json=teams_payload,
            timeout=30
        )
        response.raise_for_status()

    def _send_email_notifications(self, content: Dict[str, Any]):
        """Send email notifications using SES."""
        # This would require SES configuration
        # For now, just log that email would be sent
        self.logger.info(f"Would send email notification to {len(self.notification_config.email_recipients)} recipients")

    def _send_failure_notification(self, cicd_result: CICDResult):
        """Send failure notification."""
        failure_content = {
            "title": "InvenTag CI/CD Pipeline Failed",
            "status": "FAILED",
            "compliance_gate": "N/A",
            "summary": {
                "execution_time": round(cicd_result.execution_time_seconds, 1),
                "error_message": cicd_result.error_message
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if self.notification_config.slack_webhook_url:
            try:
                self._send_slack_notification(failure_content)
            except Exception as e:
                self.logger.error(f"Failed to send Slack failure notification: {e}")

    def _generate_prometheus_metrics(self, bom_results: Dict[str, Any], cicd_result: CICDResult) -> PrometheusMetrics:
        """Generate Prometheus metrics."""
        processing_stats = bom_results.get("processing_statistics", {})
        compliance_results = bom_results.get("compliance_analysis", {})
        
        total_resources = processing_stats.get("total_resources", 0)
        compliant_resources = compliance_results.get("compliant_resources", 0)
        non_compliant_resources = compliance_results.get("non_compliant_resources", 0)
        
        compliance_percentage = 0.0
        if total_resources > 0:
            compliance_percentage = (compliant_resources / total_resources) * 100
        
        return PrometheusMetrics(
            total_resources=total_resources,
            compliant_resources=compliant_resources,
            non_compliant_resources=non_compliant_resources,
            compliance_percentage=compliance_percentage,
            processing_time_seconds=processing_stats.get("processing_time_seconds", 0),
            successful_accounts=processing_stats.get("successful_accounts", 0),
            failed_accounts=processing_stats.get("failed_accounts", 0),
            total_accounts=processing_stats.get("total_accounts", 0),
            security_issues=compliance_results.get("security_issues", 0),
            network_issues=compliance_results.get("network_issues", 0),
            document_generation_time=bom_results.get("bom_generation", {}).get("processing_time", 0),
            s3_upload_time=0.0  # Would be calculated during upload
        )

    def _export_prometheus_metrics(self, metrics: PrometheusMetrics, push_gateway_url: Optional[str] = None):
        """Export Prometheus metrics to file and optionally push to gateway."""
        try:
            metrics_content = f"""# HELP inventag_total_resources Total number of AWS resources discovered
# TYPE inventag_total_resources gauge
inventag_total_resources {metrics.total_resources}

# HELP inventag_compliant_resources Number of compliant AWS resources
# TYPE inventag_compliant_resources gauge
inventag_compliant_resources {metrics.compliant_resources}

# HELP inventag_non_compliant_resources Number of non-compliant AWS resources
# TYPE inventag_non_compliant_resources gauge
inventag_non_compliant_resources {metrics.non_compliant_resources}

# HELP inventag_compliance_percentage Compliance percentage
# TYPE inventag_compliance_percentage gauge
inventag_compliance_percentage {metrics.compliance_percentage}

# HELP inventag_processing_time_seconds Total processing time in seconds
# TYPE inventag_processing_time_seconds gauge
inventag_processing_time_seconds {metrics.processing_time_seconds}

# HELP inventag_successful_accounts Number of successfully processed accounts
# TYPE inventag_successful_accounts gauge
inventag_successful_accounts {metrics.successful_accounts}

# HELP inventag_failed_accounts Number of failed account processing attempts
# TYPE inventag_failed_accounts gauge
inventag_failed_accounts {metrics.failed_accounts}

# HELP inventag_total_accounts Total number of accounts processed
# TYPE inventag_total_accounts gauge
inventag_total_accounts {metrics.total_accounts}

# HELP inventag_security_issues Number of security issues found
# TYPE inventag_security_issues gauge
inventag_security_issues {metrics.security_issues}

# HELP inventag_network_issues Number of network issues found
# TYPE inventag_network_issues gauge
inventag_network_issues {metrics.network_issues}

# HELP inventag_document_generation_time_seconds Time spent generating documents
# TYPE inventag_document_generation_time_seconds gauge
inventag_document_generation_time_seconds {metrics.document_generation_time}

# HELP inventag_s3_upload_time_seconds Time spent uploading to S3
# TYPE inventag_s3_upload_time_seconds gauge
inventag_s3_upload_time_seconds {metrics.s3_upload_time}
"""
            
            # Export to file
            metrics_file = Path(tempfile.gettempdir()) / "inventag_metrics.prom"
            with open(metrics_file, 'w') as f:
                f.write(metrics_content)
            
            self.logger.info(f"Exported Prometheus metrics to: {metrics_file}")
            
            # Push to Prometheus Push Gateway if configured
            gateway_url = push_gateway_url or os.environ.get('PROMETHEUS_PUSH_GATEWAY_URL')
            if gateway_url:
                self._push_to_prometheus_gateway(metrics_content, gateway_url)
            
        except Exception as e:
            self.logger.error(f"Failed to export Prometheus metrics: {e}")

    def _push_to_prometheus_gateway(self, metrics_content: str, gateway_url: str):
        """Push metrics to Prometheus Push Gateway."""
        try:
            job_name = os.environ.get('PROMETHEUS_JOB_NAME', 'inventag-bom')
            instance_name = os.environ.get('PROMETHEUS_INSTANCE_NAME', 'default')
            
            # Construct push gateway URL
            push_url = f"{gateway_url.rstrip('/')}/metrics/job/{job_name}/instance/{instance_name}"
            
            # Push metrics
            response = requests.post(
                push_url,
                data=metrics_content,
                headers={'Content-Type': 'text/plain'},
                timeout=30
            )
            response.raise_for_status()
            
            self.logger.info(f"Successfully pushed metrics to Prometheus Push Gateway: {push_url}")
            
        except Exception as e:
            self.logger.error(f"Failed to push metrics to Prometheus Push Gateway: {e}")

    def create_github_actions_config(self, 
                                   workflow_name: str = "inventag-bom-generation",
                                   schedule_cron: str = "0 6 * * 1",  # Weekly on Monday at 6 AM
                                   output_formats: List[str] = None) -> str:
        """
        Create GitHub Actions workflow configuration.
        
        Args:
            workflow_name: Name of the workflow
            schedule_cron: Cron schedule for automated runs
            output_formats: Document formats to generate
            
        Returns:
            YAML workflow configuration
        """
        output_formats = output_formats or ["excel", "word", "json"]
        
        workflow_config = f"""name: {workflow_name}

on:
  schedule:
    - cron: '{schedule_cron}'
  workflow_dispatch:
    inputs:
      accounts_file:
        description: 'Path to accounts configuration file'
        required: false
        default: '.github/inventag-accounts.yaml'
      output_formats:
        description: 'Output formats (comma-separated)'
        required: false
        default: '{",".join(output_formats)}'
      upload_to_s3:
        description: 'Upload documents to S3'
        required: false
        default: 'true'
        type: boolean

jobs:
  inventag-bom-generation:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install inventag[cicd]
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{{{ secrets.AWS_ACCESS_KEY_ID }}}}
        aws-secret-access-key: ${{{{ secrets.AWS_SECRET_ACCESS_KEY }}}}
        aws-region: us-east-1
    
    - name: Generate multi-account BOM
      env:
        INVENTAG_ACCOUNTS_FILE: ${{{{ github.event.inputs.accounts_file || '.github/inventag-accounts.yaml' }}}}
        INVENTAG_OUTPUT_FORMATS: ${{{{ github.event.inputs.output_formats || '{",".join(output_formats)}' }}}}
        INVENTAG_S3_BUCKET: ${{{{ secrets.INVENTAG_S3_BUCKET }}}}
        INVENTAG_S3_KEY_PREFIX: ${{{{ secrets.INVENTAG_S3_KEY_PREFIX || 'inventag-bom' }}}}
        INVENTAG_SLACK_WEBHOOK: ${{{{ secrets.SLACK_WEBHOOK_URL }}}}
        INVENTAG_TEAMS_WEBHOOK: ${{{{ secrets.TEAMS_WEBHOOK_URL }}}}
        INVENTAG_UPLOAD_TO_S3: ${{{{ github.event.inputs.upload_to_s3 || 'true' }}}}
      run: |
        python -c "
        import os
        from inventag import CloudBOMGenerator, CredentialManager
        from inventag.core.cicd_integration import CICDIntegration, S3UploadConfig, NotificationConfig
        
        # Load accounts configuration
        credential_manager = CredentialManager()
        accounts = credential_manager.load_credential_file(os.environ['INVENTAG_ACCOUNTS_FILE'])
        
        # Create BOM generator
        from inventag import MultiAccountConfig
        config = MultiAccountConfig(accounts=accounts)
        generator = CloudBOMGenerator(config)
        
        # Configure CI/CD integration
        s3_config = None
        if os.environ.get('INVENTAG_S3_BUCKET') and os.environ.get('INVENTAG_UPLOAD_TO_S3') == 'true':
            s3_config = S3UploadConfig(
                bucket_name=os.environ['INVENTAG_S3_BUCKET'],
                key_prefix=os.environ.get('INVENTAG_S3_KEY_PREFIX', 'inventag-bom')
            )
        
        notification_config = NotificationConfig(
            slack_webhook_url=os.environ.get('INVENTAG_SLACK_WEBHOOK'),
            teams_webhook_url=os.environ.get('INVENTAG_TEAMS_WEBHOOK')
        )
        
        cicd = CICDIntegration(
            s3_config=s3_config,
            notification_config=notification_config
        )
        
        # Execute pipeline
        output_formats = os.environ['INVENTAG_OUTPUT_FORMATS'].split(',')
        result = cicd.execute_pipeline_integration(
            generator,
            output_formats=output_formats,
            upload_to_s3=bool(s3_config),
            send_notifications=True,
            export_metrics=True
        )
        
        # Set GitHub Actions outputs
        print(f'::set-output name=success::{result.success}')
        print(f'::set-output name=compliance_gate_passed::{result.compliance_gate_passed}')
        print(f'::set-output name=generated_documents::{len(result.generated_documents)}')
        
        # Fail the job if compliance gate failed
        if not result.compliance_gate_passed:
            print('::error::Compliance gate failed')
            exit(1)
        "
    
    - name: Upload artifacts
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: inventag-artifacts
        path: |
          /tmp/pipeline_summary.json
          /tmp/compliance_gate.json
          /tmp/account_summary.json
          /tmp/s3_links.json
          /tmp/inventag_metrics.prom
        retention-days: 30
"""
        
        return workflow_config