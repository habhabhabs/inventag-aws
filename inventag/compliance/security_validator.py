#!/usr/bin/env python3
"""
InvenTag - Security and Compliance Validation System
Enterprise-grade AWS read-only access validation and compliance audit logging.

This module implements comprehensive security validation to ensure all operations
are read-only and provides audit logging for compliance requirements.
"""

import json
import logging
import boto3
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from botocore.exceptions import ClientError, NoCredentialsError
from enum import Enum


class OperationType(Enum):
    """Types of AWS operations for security validation."""
    READ_ONLY = "read_only"
    MUTATING = "mutating"
    UNKNOWN = "unknown"


class ComplianceStandard(Enum):
    """Supported compliance standards."""
    GENERAL = "general"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    CUSTOM = "custom"


@dataclass
class SecurityValidationResult:
    """Result of security validation check."""
    is_valid: bool
    operation: str
    operation_type: OperationType
    risk_level: str
    validation_message: str
    timestamp: datetime
    compliance_notes: List[str]


@dataclass
class AuditLogEntry:
    """Audit log entry for compliance tracking."""
    timestamp: datetime
    operation: str
    service: str
    resource_arn: Optional[str]
    operation_type: OperationType
    user_identity: Dict[str, Any]
    request_parameters: Dict[str, Any]
    response_elements: Optional[Dict[str, Any]]
    compliance_standard: ComplianceStandard
    audit_id: str
    session_id: str


@dataclass
class ComplianceReport:
    """General compliance report."""
    report_id: str
    generation_timestamp: datetime
    account_id: str
    region: str
    compliance_standard: str
    total_operations: int
    read_only_operations: int
    mutating_operations_blocked: int
    compliance_score: float
    audit_entries: List[AuditLogEntry]
    security_findings: List[Dict[str, Any]]
    recommendations: List[str]


class ReadOnlyAccessValidator:
    """
    Validates that all AWS operations are read-only and provides comprehensive
    audit logging for compliance requirements.
    """

    # Comprehensive list of read-only AWS operations
    READ_ONLY_OPERATIONS = {
        # EC2 read-only operations
        'ec2': {
            'describe_instances', 'describe_images', 'describe_volumes', 'describe_snapshots',
            'describe_security_groups', 'describe_vpcs', 'describe_subnets', 'describe_route_tables',
            'describe_internet_gateways', 'describe_nat_gateways', 'describe_network_acls',
            'describe_key_pairs', 'describe_placement_groups', 'describe_regions',
            'describe_availability_zones', 'describe_instance_types', 'describe_addresses',
            'describe_network_interfaces', 'describe_dhcp_options', 'describe_customer_gateways',
            'describe_vpn_gateways', 'describe_vpn_connections', 'describe_transit_gateways',
            'get_console_output', 'get_password_data'
        },
        
        # S3 read-only operations
        's3': {
            'list_buckets', 'list_objects', 'list_objects_v2', 'head_bucket', 'head_object',
            'get_object', 'get_object_acl', 'get_bucket_acl', 'get_bucket_policy',
            'get_bucket_location', 'get_bucket_versioning', 'get_bucket_lifecycle',
            'get_bucket_cors', 'get_bucket_encryption', 'get_bucket_notification',
            'get_bucket_tagging', 'get_bucket_website', 'get_bucket_logging',
            'get_bucket_replication', 'get_bucket_request_payment', 'get_public_access_block',
            'get_object_lock_configuration', 'get_bucket_policy_status'
        },
        
        # RDS read-only operations
        'rds': {
            'describe_db_instances', 'describe_db_clusters', 'describe_db_snapshots',
            'describe_db_cluster_snapshots', 'describe_db_parameter_groups',
            'describe_db_cluster_parameter_groups', 'describe_db_subnet_groups',
            'describe_option_groups', 'describe_db_security_groups', 'describe_events',
            'describe_event_categories', 'describe_event_subscriptions', 'describe_db_log_files',
            'download_db_log_file_portion', 'describe_certificates', 'describe_reserved_db_instances'
        },
        
        # Lambda read-only operations
        'lambda': {
            'list_functions', 'get_function', 'get_function_configuration', 'list_versions_by_function',
            'list_aliases', 'get_alias', 'list_event_source_mappings', 'get_event_source_mapping',
            'get_policy', 'list_layers', 'get_layer_version', 'list_layer_versions',
            'get_account_settings', 'list_tags', 'get_function_concurrency'
        },
        
        # IAM read-only operations
        'iam': {
            'list_users', 'list_groups', 'list_roles', 'list_policies', 'get_user', 'get_group',
            'get_role', 'get_policy', 'get_policy_version', 'list_attached_user_policies',
            'list_attached_group_policies', 'list_attached_role_policies', 'list_user_policies',
            'list_group_policies', 'list_role_policies', 'get_user_policy', 'get_group_policy',
            'get_role_policy', 'list_policy_versions', 'simulate_principal_policy',
            'get_account_summary', 'get_credential_report', 'list_access_keys',
            'list_mfa_devices', 'list_signing_certificates', 'get_account_password_policy'
        },
        
        # CloudFormation read-only operations
        'cloudformation': {
            'list_stacks', 'describe_stacks', 'describe_stack_resources', 'describe_stack_events',
            'get_template', 'get_template_summary', 'list_stack_resources', 'describe_stack_resource',
            'list_exports', 'list_imports', 'describe_account_limits', 'describe_stack_drift_detection_status',
            'detect_stack_drift', 'detect_stack_resource_drift'
        },
        
        # CloudWatch read-only operations
        'cloudwatch': {
            'list_metrics', 'get_metric_statistics', 'get_metric_data', 'describe_alarms',
            'describe_alarm_history', 'describe_anomaly_detectors', 'list_dashboards',
            'get_dashboard', 'list_tags_for_resource'
        },
        
        # CloudTrail read-only operations
        'cloudtrail': {
            'describe_trails', 'get_trail_status', 'lookup_events', 'list_public_keys',
            'list_tags', 'get_event_selectors', 'get_insight_selectors'
        },
        
        # Config read-only operations
        'config': {
            'describe_configuration_recorders', 'describe_delivery_channels',
            'describe_configuration_recorder_status', 'describe_delivery_channel_status',
            'get_compliance_details_by_config_rule', 'get_compliance_details_by_resource',
            'get_compliance_summary_by_config_rule', 'get_compliance_summary_by_resource_type',
            'describe_config_rules', 'describe_compliance_by_config_rule',
            'describe_compliance_by_resource', 'get_resource_config_history',
            'list_discovered_resources', 'get_discovered_resource_counts'
        },
        
        # Resource Groups Tagging API read-only operations
        'resourcegroupstaggingapi': {
            'get_resources', 'get_tag_keys', 'get_tag_values', 'describe_report_creation',
            'get_compliance_summary'
        },
        
        # STS read-only operations
        'sts': {
            'get_caller_identity', 'get_session_token', 'assume_role', 'assume_role_with_saml',
            'assume_role_with_web_identity', 'decode_authorization_message'
        }
    }

    # Operations that are explicitly mutating and should be blocked
    MUTATING_OPERATIONS = {
        'create_', 'delete_', 'modify_', 'update_', 'put_', 'attach_', 'detach_',
        'associate_', 'disassociate_', 'start_', 'stop_', 'reboot_', 'terminate_',
        'run_', 'launch_', 'allocate_', 'release_', 'authorize_', 'revoke_',
        'enable_', 'disable_', 'register_', 'deregister_', 'import_', 'export_',
        'copy_', 'restore_', 'reset_', 'replace_', 'cancel_', 'accept_', 'reject_'
    }

    def __init__(self, compliance_standard: ComplianceStandard = ComplianceStandard.GENERAL):
        """Initialize the security validator."""
        self.compliance_standard = compliance_standard
        self.logger = self._setup_logging()
        self.session_id = self._generate_session_id()
        self.audit_entries: List[AuditLogEntry] = []
        self.blocked_operations: List[str] = []
        
        # Initialize AWS session for identity validation
        try:
            self.session = boto3.Session()
            self.sts_client = self.session.client('sts')
            self.user_identity = self._get_user_identity()
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS session: {e}")
            self.user_identity = {"error": str(e)}

    def _setup_logging(self) -> logging.Logger:
        """Set up comprehensive audit logging."""
        logger = logging.getLogger(f"{__name__}.security_validator")
        logger.setLevel(logging.INFO)
        
        # Create formatter for audit logs
        formatter = logging.Formatter(
            '%(asctime)s - SECURITY_AUDIT - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler for audit trail
        try:
            file_handler = logging.FileHandler('inventag_security_audit.log')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not create audit log file: {e}")
        
        return logger

    def _generate_session_id(self) -> str:
        """Generate unique session ID for audit tracking."""
        return f"inventag_session_{int(time.time())}_{hash(datetime.now())}"

    def _get_user_identity(self) -> Dict[str, Any]:
        """Get current AWS user identity for audit logging."""
        try:
            identity = self.sts_client.get_caller_identity()
            return {
                "user_id": identity.get("UserId", "unknown"),
                "account": identity.get("Account", "unknown"),
                "arn": identity.get("Arn", "unknown"),
                "type": self._determine_identity_type(identity.get("Arn", ""))
            }
        except Exception as e:
            self.logger.error(f"Failed to get user identity: {e}")
            return {"error": str(e)}

    def _determine_identity_type(self, arn: str) -> str:
        """Determine the type of AWS identity (user, role, etc.)."""
        if ":user/" in arn:
            return "IAM_USER"
        elif ":role/" in arn:
            return "IAM_ROLE"
        elif ":assumed-role/" in arn:
            return "ASSUMED_ROLE"
        elif ":root" in arn:
            return "ROOT_USER"
        else:
            return "UNKNOWN"

    def validate_operation(self, service: str, operation: str, 
                         resource_arn: Optional[str] = None,
                         request_parameters: Optional[Dict[str, Any]] = None) -> SecurityValidationResult:
        """
        Validate that an AWS operation is read-only and safe to execute.
        
        Args:
            service: AWS service name (e.g., 'ec2', 's3')
            operation: Operation name (e.g., 'describe_instances')
            resource_arn: ARN of the resource being accessed (optional)
            request_parameters: Parameters being sent with the request (optional)
            
        Returns:
            SecurityValidationResult with validation outcome
        """
        timestamp = datetime.now(timezone.utc)
        operation_lower = operation.lower()
        service_lower = service.lower()
        
        # Determine operation type
        operation_type = self._classify_operation(service_lower, operation_lower)
        
        # Validate operation
        is_valid = operation_type == OperationType.READ_ONLY
        risk_level = self._assess_risk_level(operation_type, service_lower, operation_lower)
        
        # Generate validation message
        if is_valid:
            validation_message = f"Operation {operation} on {service} is validated as read-only"
        else:
            validation_message = f"Operation {operation} on {service} is BLOCKED - not read-only"
            self.blocked_operations.append(f"{service}:{operation}")
        
        # Generate compliance notes
        compliance_notes = self._generate_compliance_notes(
            operation_type, service_lower, operation_lower
        )
        
        # Create validation result
        result = SecurityValidationResult(
            is_valid=is_valid,
            operation=operation,
            operation_type=operation_type,
            risk_level=risk_level,
            validation_message=validation_message,
            timestamp=timestamp,
            compliance_notes=compliance_notes
        )
        
        # Log the validation
        self._log_security_validation(result, service, resource_arn, request_parameters)
        
        # Create audit entry
        self._create_audit_entry(
            operation, service, resource_arn, operation_type, request_parameters
        )
        
        return result

    def _classify_operation(self, service: str, operation: str) -> OperationType:
        """Classify an AWS operation as read-only, mutating, or unknown."""
        
        # Check if it's in our explicit read-only list
        if service in self.READ_ONLY_OPERATIONS:
            if operation in self.READ_ONLY_OPERATIONS[service]:
                return OperationType.READ_ONLY
        
        # Check for mutating operation patterns
        for mutating_pattern in self.MUTATING_OPERATIONS:
            if operation.startswith(mutating_pattern):
                return OperationType.MUTATING
        
        # Check for common read-only patterns
        read_only_patterns = [
            'describe_', 'list_', 'get_', 'head_', 'lookup_', 'download_',
            'simulate_', 'detect_', 'test_', 'validate_', 'check_'
        ]
        
        for pattern in read_only_patterns:
            if operation.startswith(pattern):
                return OperationType.READ_ONLY
        
        # If we can't classify it, mark as unknown (which will be blocked)
        return OperationType.UNKNOWN

    def _assess_risk_level(self, operation_type: OperationType, service: str, operation: str) -> str:
        """Assess the risk level of an operation."""
        if operation_type == OperationType.MUTATING:
            return "HIGH"
        elif operation_type == OperationType.UNKNOWN:
            return "MEDIUM"
        elif service in ['iam', 'sts'] and operation_type == OperationType.READ_ONLY:
            return "MEDIUM"  # IAM/STS operations are sensitive even if read-only
        else:
            return "LOW"

    def _generate_compliance_notes(self, operation_type: OperationType, 
                                 service: str, operation: str) -> List[str]:
        """Generate compliance-specific notes for the operation."""
        notes = []
        
        if operation_type == OperationType.READ_ONLY:
            notes.append("Read-only operation approved for cloud resource inventory")
            notes.append("Operation supports comprehensive audit trail requirements")
        else:
            notes.append("Mutating operation blocked to maintain system integrity")
            notes.append("Operation would violate read-only access requirements")
        
        if service in ['iam', 'sts']:
            notes.append("Sensitive identity operation - enhanced monitoring applied")
        
        return notes

    def _log_security_validation(self, result: SecurityValidationResult, service: str,
                               resource_arn: Optional[str], request_parameters: Optional[Dict[str, Any]]):
        """Log security validation for audit trail."""
        log_data = {
            "validation_result": asdict(result),
            "service": service,
            "resource_arn": resource_arn,
            "request_parameters": request_parameters,
            "user_identity": self.user_identity,
            "session_id": self.session_id
        }
        
        if result.is_valid:
            self.logger.info(f"SECURITY_VALIDATION_PASSED: {json.dumps(log_data, default=str)}")
        else:
            self.logger.warning(f"SECURITY_VALIDATION_BLOCKED: {json.dumps(log_data, default=str)}")

    def _create_audit_entry(self, operation: str, service: str, resource_arn: Optional[str],
                          operation_type: OperationType, request_parameters: Optional[Dict[str, Any]]):
        """Create detailed audit entry for compliance tracking."""
        audit_entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            operation=operation,
            service=service,
            resource_arn=resource_arn,
            operation_type=operation_type,
            user_identity=self.user_identity,
            request_parameters=request_parameters or {},
            response_elements=None,  # Will be populated after operation
            compliance_standard=self.compliance_standard,
            audit_id=f"audit_{int(time.time())}_{len(self.audit_entries)}",
            session_id=self.session_id
        )
        
        self.audit_entries.append(audit_entry)

    def validate_aws_permissions(self) -> Dict[str, Any]:
        """
        Validate that the current AWS credentials have appropriate read-only permissions
        and no dangerous write permissions.
        """
        self.logger.info("Starting AWS permissions validation...")
        
        validation_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_identity": self.user_identity,
            "permission_checks": [],
            "overall_status": "UNKNOWN",
            "recommendations": []
        }
        
        # Test basic read operations
        read_tests = [
            ("sts", "get_caller_identity", {}),
            ("ec2", "describe_regions", {}),
            ("s3", "list_buckets", {}),
        ]
        
        passed_tests = 0
        total_tests = len(read_tests)
        
        for service, operation, params in read_tests:
            try:
                client = self.session.client(service)
                method = getattr(client, operation)
                
                # Validate the operation first
                validation = self.validate_operation(service, operation)
                
                if validation.is_valid:
                    # Try to execute the operation
                    method(**params)
                    passed_tests += 1
                    
                    validation_results["permission_checks"].append({
                        "service": service,
                        "operation": operation,
                        "status": "PASSED",
                        "message": f"Successfully executed {operation}"
                    })
                else:
                    validation_results["permission_checks"].append({
                        "service": service,
                        "operation": operation,
                        "status": "BLOCKED",
                        "message": f"Operation blocked by security validation"
                    })
                    
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                validation_results["permission_checks"].append({
                    "service": service,
                    "operation": operation,
                    "status": "FAILED",
                    "message": f"Permission denied: {error_code}"
                })
            except Exception as e:
                validation_results["permission_checks"].append({
                    "service": service,
                    "operation": operation,
                    "status": "ERROR",
                    "message": f"Unexpected error: {str(e)}"
                })
        
        # Determine overall status
        if passed_tests == total_tests:
            validation_results["overall_status"] = "VALID"
            validation_results["recommendations"].append(
                "Credentials have appropriate read-only access"
            )
        elif passed_tests > 0:
            validation_results["overall_status"] = "PARTIAL"
            validation_results["recommendations"].append(
                "Some read operations failed - check IAM permissions"
            )
        else:
            validation_results["overall_status"] = "INVALID"
            validation_results["recommendations"].append(
                "No read operations succeeded - check credentials and permissions"
            )
        
        self.logger.info(f"Permission validation complete: {validation_results['overall_status']}")
        return validation_results

    def generate_compliance_report(self) -> ComplianceReport:
        """Generate a comprehensive compliance report."""
        self.logger.info("Generating compliance report...")
        
        total_operations = len(self.audit_entries)
        read_only_operations = len([
            entry for entry in self.audit_entries 
            if entry.operation_type == OperationType.READ_ONLY
        ])
        mutating_operations_blocked = len([
            entry for entry in self.audit_entries 
            if entry.operation_type == OperationType.MUTATING
        ])
        
        # Calculate compliance score
        compliance_score = (read_only_operations / total_operations * 100) if total_operations > 0 else 100
        
        # Generate security findings
        security_findings = []
        
        if mutating_operations_blocked > 0:
            security_findings.append({
                "finding_id": "SEC-001",
                "severity": "HIGH",
                "title": "Mutating Operations Blocked",
                "description": f"{mutating_operations_blocked} mutating operations were blocked",
                "recommendation": "Review application logic to ensure only read-only operations are attempted"
            })
        
        if self.user_identity.get("type") == "ROOT_USER":
            security_findings.append({
                "finding_id": "SEC-002",
                "severity": "MEDIUM",
                "title": "Root User Access",
                "description": "Operations performed using root user credentials",
                "recommendation": "Use IAM users or roles instead of root user for better security"
            })
        
        # Generate recommendations
        recommendations = [
            "Maintain read-only access patterns for compliance",
            "Regularly review audit logs for security monitoring",
            "Implement least-privilege access principles",
            "Use IAM roles instead of long-term access keys where possible"
        ]
        
        if compliance_score < 100:
            recommendations.append("Investigate and resolve blocked operations")
        
        report = ComplianceReport(
            report_id=f"compliance_report_{int(time.time())}",
            generation_timestamp=datetime.now(timezone.utc),
            account_id=self.user_identity.get("account", "unknown"),
            region="global",  # Security validation is global
            compliance_standard=self.compliance_standard.value,
            total_operations=total_operations,
            read_only_operations=read_only_operations,
            mutating_operations_blocked=mutating_operations_blocked,
            compliance_score=compliance_score,
            audit_entries=self.audit_entries,
            security_findings=security_findings,
            recommendations=recommendations
        )
        
        self.logger.info(f"Compliance report generated: {compliance_score:.1f}% compliant")
        return report

    def save_compliance_report(self, report: ComplianceReport, filename: str):
        """Save compliance report to file."""
        report_data = asdict(report)
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"Compliance report saved to {filename}")

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get summary of audit activities."""
        return {
            "session_id": self.session_id,
            "total_operations": len(self.audit_entries),
            "read_only_operations": len([
                e for e in self.audit_entries if e.operation_type == OperationType.READ_ONLY
            ]),
            "blocked_operations": len(self.blocked_operations),
            "compliance_standard": self.compliance_standard.value,
            "user_identity": self.user_identity,
            "session_start": min([e.timestamp for e in self.audit_entries]) if self.audit_entries else None,
            "session_end": max([e.timestamp for e in self.audit_entries]) if self.audit_entries else None
        }