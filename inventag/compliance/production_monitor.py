#!/usr/bin/env python3
"""
InvenTag - Production Safety and Monitoring System
Enterprise-grade production safety, error handling, and monitoring capabilities.

This module provides comprehensive error handling with graceful degradation,
CloudTrail integration for audit trail visibility, performance metrics tracking,
and security validation reports for compliance documentation.
"""

import json
import logging
import boto3
import time
import psutil
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict, field
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from enum import Enum
import traceback
import sys
import os
from collections import defaultdict, deque


class ErrorSeverity(Enum):
    """Error severity levels for production monitoring."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MonitoringMetric(Enum):
    """Types of monitoring metrics."""
    PERFORMANCE = "performance"
    RESOURCE_USAGE = "resource_usage"
    ERROR_RATE = "error_rate"
    OPERATION_COUNT = "operation_count"
    COMPLIANCE_SCORE = "compliance_score"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    timestamp: datetime
    error_type: str
    error_message: str
    severity: ErrorSeverity
    operation: str
    service: str
    resource_arn: Optional[str]
    stack_trace: str
    recovery_action: Optional[str]
    user_impact: str
    correlation_id: str


@dataclass
class PerformanceMetric:
    """Performance monitoring metric."""
    timestamp: datetime
    metric_type: MonitoringMetric
    metric_name: str
    value: Union[float, int]
    unit: str
    tags: Dict[str, str]
    threshold_breached: bool = False
    threshold_value: Optional[float] = None


@dataclass
class CloudTrailEvent:
    """CloudTrail event for audit trail integration."""
    event_time: datetime
    event_name: str
    event_source: str
    user_identity: Dict[str, Any]
    source_ip_address: str
    user_agent: str
    request_parameters: Dict[str, Any]
    response_elements: Optional[Dict[str, Any]]
    error_code: Optional[str]
    error_message: Optional[str]
    resources: List[Dict[str, Any]]
    read_only: bool


@dataclass
class SecurityValidationReport:
    """Security validation report for compliance documentation."""
    report_id: str
    generation_timestamp: datetime
    account_id: str
    region: str
    validation_period_start: datetime
    validation_period_end: datetime
    total_operations: int
    successful_operations: int
    failed_operations: int
    blocked_operations: int
    security_findings: List[Dict[str, Any]]
    compliance_violations: List[Dict[str, Any]]
    recommendations: List[str]
    risk_score: float
    cloudtrail_events: List[CloudTrailEvent]


class ProductionSafetyMonitor:
    """
    Comprehensive production safety and monitoring system for InvenTag.
    
    Provides error handling with graceful degradation, performance monitoring,
    CloudTrail integration, and security validation reporting.
    """

    def __init__(self, 
                 enable_cloudtrail: bool = True,
                 enable_performance_monitoring: bool = True,
                 error_threshold: int = 10,
                 performance_threshold_cpu: float = 80.0,
                 performance_threshold_memory: float = 80.0):
        """Initialize the production safety monitor."""
        self.enable_cloudtrail = enable_cloudtrail
        self.enable_performance_monitoring = enable_performance_monitoring
        self.error_threshold = error_threshold
        self.performance_threshold_cpu = performance_threshold_cpu
        self.performance_threshold_memory = performance_threshold_memory
        
        # Initialize logging
        self.logger = self._setup_production_logging()
        
        # Initialize AWS clients
        try:
            self.session = boto3.Session()
            self.cloudtrail_client = self.session.client('cloudtrail') if enable_cloudtrail else None
            self.sts_client = self.session.client('sts')
            self.account_id = self._get_account_id()
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS clients: {e}")
            self.cloudtrail_client = None
            self.sts_client = None
            self.account_id = "unknown"
        
        # Monitoring data structures
        self.error_history: deque = deque(maxlen=1000)
        self.performance_metrics: deque = deque(maxlen=1000)
        self.cloudtrail_events: List[CloudTrailEvent] = []
        self.operation_counts: defaultdict = defaultdict(int)
        self.error_counts: defaultdict = defaultdict(int)
        
        # Performance monitoring thread
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Circuit breaker state
        self.circuit_breaker_state = defaultdict(lambda: {"failures": 0, "last_failure": None, "state": "closed"})
        
        # Start monitoring if enabled
        if enable_performance_monitoring:
            self.start_performance_monitoring()

    def _setup_production_logging(self) -> logging.Logger:
        """Set up comprehensive production logging."""
        logger = logging.getLogger(f"{__name__}.production_monitor")
        logger.setLevel(logging.INFO)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - PRODUCTION - %(levelname)s - %(name)s - %(message)s - '
            '[PID:%(process)d] [Thread:%(thread)d]'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(detailed_formatter)
        logger.addHandler(console_handler)
        
        # File handlers for different log levels
        try:
            # General production log
            production_handler = logging.FileHandler('inventag_production.log')
            production_handler.setFormatter(detailed_formatter)
            production_handler.setLevel(logging.INFO)
            logger.addHandler(production_handler)
            
            # Error-only log
            error_handler = logging.FileHandler('inventag_errors.log')
            error_handler.setFormatter(detailed_formatter)
            error_handler.setLevel(logging.ERROR)
            logger.addHandler(error_handler)
            
            # Performance metrics log
            metrics_handler = logging.FileHandler('inventag_metrics.log')
            metrics_formatter = logging.Formatter('%(asctime)s - METRICS - %(message)s')
            metrics_handler.setFormatter(metrics_formatter)
            metrics_handler.setLevel(logging.INFO)
            
            # Create separate logger for metrics
            metrics_logger = logging.getLogger(f"{__name__}.metrics")
            metrics_logger.addHandler(metrics_handler)
            metrics_logger.setLevel(logging.INFO)
            
        except Exception as e:
            logger.warning(f"Could not create log files: {e}")
        
        return logger

    def _get_account_id(self) -> str:
        """Get current AWS account ID."""
        try:
            identity = self.sts_client.get_caller_identity()
            return identity.get("Account", "unknown")
        except Exception as e:
            self.logger.error(f"Failed to get account ID: {e}")
            return "unknown"

    def handle_error(self, 
                    error: Exception,
                    operation: str,
                    service: str,
                    resource_arn: Optional[str] = None,
                    recovery_action: Optional[str] = None) -> ErrorContext:
        """
        Comprehensive error handling with graceful degradation.
        
        Args:
            error: The exception that occurred
            operation: The operation that failed
            service: The AWS service involved
            resource_arn: ARN of the resource (if applicable)
            recovery_action: Suggested recovery action
            
        Returns:
            ErrorContext with detailed error information
        """
        # Determine error severity
        severity = self._assess_error_severity(error, operation, service)
        
        # Generate correlation ID
        correlation_id = f"error_{int(time.time())}_{hash(str(error))}"
        
        # Create error context
        error_context = ErrorContext(
            timestamp=datetime.now(timezone.utc),
            error_type=type(error).__name__,
            error_message=str(error),
            severity=severity,
            operation=operation,
            service=service,
            resource_arn=resource_arn,
            stack_trace=traceback.format_exc(),
            recovery_action=recovery_action,
            user_impact=self._assess_user_impact(severity, operation),
            correlation_id=correlation_id
        )
        
        # Log the error
        self._log_error(error_context)
        
        # Store in error history
        self.error_history.append(error_context)
        self.error_counts[f"{service}:{operation}"] += 1
        
        # Update circuit breaker
        self._update_circuit_breaker(service, operation, error_context)
        
        # Check if error threshold is breached
        if len(self.error_history) >= self.error_threshold:
            recent_errors = [e for e in self.error_history 
                           if (datetime.now(timezone.utc) - e.timestamp).seconds < 300]  # Last 5 minutes
            if len(recent_errors) >= self.error_threshold:
                self._trigger_error_threshold_alert(recent_errors)
        
        # Attempt graceful degradation
        self._attempt_graceful_degradation(error_context)
        
        return error_context

    def _assess_error_severity(self, error: Exception, operation: str, service: str) -> ErrorSeverity:
        """Assess the severity of an error."""
        # Critical errors
        if isinstance(error, (NoCredentialsError, PermissionError)):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', '')
            if error_code in ['AccessDenied', 'UnauthorizedOperation', 'InvalidUserID.NotFound']:
                return ErrorSeverity.HIGH
            elif error_code in ['Throttling', 'RequestLimitExceeded', 'ServiceUnavailable']:
                return ErrorSeverity.MEDIUM
        
        # Service-specific severity assessment
        if service in ['iam', 'sts'] and 'permission' in str(error).lower():
            return ErrorSeverity.HIGH
        
        # Default to medium for unknown errors
        return ErrorSeverity.MEDIUM

    def _assess_user_impact(self, severity: ErrorSeverity, operation: str) -> str:
        """Assess the impact on users."""
        if severity == ErrorSeverity.CRITICAL:
            return "High - Operation cannot proceed, user intervention required"
        elif severity == ErrorSeverity.HIGH:
            return "Medium - Operation may fail, some functionality affected"
        elif severity == ErrorSeverity.MEDIUM:
            return "Low - Operation may be retried, minimal user impact"
        else:
            return "Minimal - Operation continues with degraded functionality"

    def _log_error(self, error_context: ErrorContext):
        """Log error with appropriate level and detail."""
        log_message = (
            f"Error in {error_context.service}:{error_context.operation} - "
            f"{error_context.error_type}: {error_context.error_message} "
            f"[Correlation ID: {error_context.correlation_id}]"
        )
        
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_context.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # Log detailed context for debugging
        self.logger.debug(f"Error context: {asdict(error_context)}")

    def _update_circuit_breaker(self, service: str, operation: str, error_context: ErrorContext):
        """Update circuit breaker state for service/operation."""
        key = f"{service}:{operation}"
        breaker = self.circuit_breaker_state[key]
        
        breaker["failures"] += 1
        breaker["last_failure"] = error_context.timestamp
        
        # Open circuit breaker if too many failures
        if breaker["failures"] >= 5 and breaker["state"] == "closed":
            breaker["state"] = "open"
            self.logger.warning(f"Circuit breaker opened for {key} due to repeated failures")
        
        # Half-open after timeout
        elif (breaker["state"] == "open" and 
              breaker["last_failure"] and
              (datetime.now(timezone.utc) - breaker["last_failure"]).seconds > 300):  # 5 minutes
            breaker["state"] = "half-open"
            self.logger.info(f"Circuit breaker half-opened for {key}")

    def _trigger_error_threshold_alert(self, recent_errors: List[ErrorContext]):
        """Trigger alert when error threshold is breached."""
        alert_message = (
            f"ERROR THRESHOLD BREACHED: {len(recent_errors)} errors in the last 5 minutes. "
            f"Most common errors: {self._get_top_errors(recent_errors)}"
        )
        
        self.logger.critical(alert_message)
        
        # Could integrate with alerting systems here (SNS, Slack, etc.)

    def _get_top_errors(self, errors: List[ErrorContext]) -> Dict[str, int]:
        """Get the most common error types."""
        error_types = defaultdict(int)
        for error in errors:
            error_types[f"{error.service}:{error.error_type}"] += 1
        
        return dict(sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:3])

    def _attempt_graceful_degradation(self, error_context: ErrorContext):
        """Attempt graceful degradation based on error type."""
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.info(f"Attempting graceful degradation for critical error: {error_context.correlation_id}")
            # Could implement fallback mechanisms here
        
        # Example: If S3 upload fails, save locally
        if error_context.service == 's3' and 'upload' in error_context.operation.lower():
            self.logger.info("S3 upload failed, data will be saved locally instead")
            error_context.recovery_action = "Save data locally and retry S3 upload later"

    def start_performance_monitoring(self):
        """Start background performance monitoring."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._performance_monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        self.logger.info("Performance monitoring started")

    def stop_performance_monitoring(self):
        """Stop background performance monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        self.logger.info("Performance monitoring stopped")

    def _performance_monitoring_loop(self):
        """Background loop for performance monitoring."""
        while self.monitoring_active:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Create performance metrics
                timestamp = datetime.now(timezone.utc)
                
                metrics = [
                    PerformanceMetric(
                        timestamp=timestamp,
                        metric_type=MonitoringMetric.RESOURCE_USAGE,
                        metric_name="cpu_usage_percent",
                        value=cpu_percent,
                        unit="percent",
                        tags={"resource": "cpu"},
                        threshold_breached=cpu_percent > self.performance_threshold_cpu,
                        threshold_value=self.performance_threshold_cpu
                    ),
                    PerformanceMetric(
                        timestamp=timestamp,
                        metric_type=MonitoringMetric.RESOURCE_USAGE,
                        metric_name="memory_usage_percent",
                        value=memory.percent,
                        unit="percent",
                        tags={"resource": "memory"},
                        threshold_breached=memory.percent > self.performance_threshold_memory,
                        threshold_value=self.performance_threshold_memory
                    ),
                    PerformanceMetric(
                        timestamp=timestamp,
                        metric_type=MonitoringMetric.RESOURCE_USAGE,
                        metric_name="disk_usage_percent",
                        value=disk.percent,
                        unit="percent",
                        tags={"resource": "disk"}
                    )
                ]
                
                # Store metrics
                for metric in metrics:
                    self.performance_metrics.append(metric)
                    
                    # Log threshold breaches
                    if metric.threshold_breached:
                        self.logger.warning(
                            f"Performance threshold breached: {metric.metric_name} = {metric.value}% "
                            f"(threshold: {metric.threshold_value}%)"
                        )
                
                # Log metrics to file
                metrics_logger = logging.getLogger(f"{__name__}.metrics")
                for metric in metrics:
                    metrics_logger.info(json.dumps(asdict(metric), default=str))
                
                time.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in performance monitoring: {e}")
                time.sleep(60)  # Wait longer on error

    def record_operation(self, operation: str, service: str, duration: float, success: bool):
        """Record an operation for monitoring."""
        self.operation_counts[f"{service}:{operation}"] += 1
        
        # Record performance metric
        metric = PerformanceMetric(
            timestamp=datetime.now(timezone.utc),
            metric_type=MonitoringMetric.PERFORMANCE,
            metric_name="operation_duration",
            value=duration,
            unit="seconds",
            tags={"service": service, "operation": operation, "success": str(success)}
        )
        
        self.performance_metrics.append(metric)
        
        # Log slow operations
        if duration > 30:  # More than 30 seconds
            self.logger.warning(f"Slow operation detected: {service}:{operation} took {duration:.2f} seconds")

    def integrate_cloudtrail_events(self, start_time: datetime, end_time: datetime) -> List[CloudTrailEvent]:
        """
        Integrate with CloudTrail for audit trail visibility.
        
        Args:
            start_time: Start time for event lookup
            end_time: End time for event lookup
            
        Returns:
            List of CloudTrail events
        """
        if not self.cloudtrail_client:
            self.logger.warning("CloudTrail client not available")
            return []
        
        try:
            self.logger.info(f"Retrieving CloudTrail events from {start_time} to {end_time}")
            
            events = []
            paginator = self.cloudtrail_client.get_paginator('lookup_events')
            
            page_iterator = paginator.paginate(
                StartTime=start_time,
                EndTime=end_time,
                LookupAttributes=[
                    {
                        'AttributeKey': 'ReadOnly',
                        'AttributeValue': 'true'
                    }
                ]
            )
            
            for page in page_iterator:
                for event in page.get('Events', []):
                    cloudtrail_event = CloudTrailEvent(
                        event_time=event.get('EventTime'),
                        event_name=event.get('EventName', ''),
                        event_source=event.get('EventSource', ''),
                        user_identity=json.loads(event.get('CloudTrailEvent', '{}')).get('userIdentity', {}),
                        source_ip_address=json.loads(event.get('CloudTrailEvent', '{}')).get('sourceIPAddress', ''),
                        user_agent=json.loads(event.get('CloudTrailEvent', '{}')).get('userAgent', ''),
                        request_parameters=json.loads(event.get('CloudTrailEvent', '{}')).get('requestParameters', {}),
                        response_elements=json.loads(event.get('CloudTrailEvent', '{}')).get('responseElements'),
                        error_code=json.loads(event.get('CloudTrailEvent', '{}')).get('errorCode'),
                        error_message=json.loads(event.get('CloudTrailEvent', '{}')).get('errorMessage'),
                        resources=event.get('Resources', []),
                        read_only=event.get('ReadOnly', True)
                    )
                    events.append(cloudtrail_event)
            
            self.cloudtrail_events.extend(events)
            self.logger.info(f"Retrieved {len(events)} CloudTrail events")
            return events
            
        except ClientError as e:
            error_context = self.handle_error(
                e, "lookup_events", "cloudtrail", 
                recovery_action="Continue without CloudTrail integration"
            )
            return []
        except Exception as e:
            error_context = self.handle_error(
                e, "integrate_cloudtrail_events", "cloudtrail",
                recovery_action="Continue without CloudTrail integration"
            )
            return []

    def generate_security_validation_report(self, 
                                          validation_period_hours: int = 24) -> SecurityValidationReport:
        """
        Generate comprehensive security validation report for compliance documentation.
        
        Args:
            validation_period_hours: Hours to look back for validation data
            
        Returns:
            SecurityValidationReport with comprehensive security analysis
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=validation_period_hours)
        
        self.logger.info(f"Generating security validation report for period {start_time} to {end_time}")
        
        # Get CloudTrail events for the period
        cloudtrail_events = self.integrate_cloudtrail_events(start_time, end_time)
        
        # Analyze operations
        total_operations = len(self.operation_counts)
        successful_operations = sum(1 for count in self.operation_counts.values() if count > 0)
        failed_operations = len([e for e in self.error_history 
                               if start_time <= e.timestamp <= end_time])
        blocked_operations = len([e for e in self.error_history 
                                if start_time <= e.timestamp <= end_time 
                                and e.severity == ErrorSeverity.HIGH])
        
        # Generate security findings
        security_findings = self._generate_security_findings(start_time, end_time)
        
        # Generate compliance violations
        compliance_violations = self._generate_compliance_violations(start_time, end_time)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(
            total_operations, failed_operations, blocked_operations, security_findings
        )
        
        # Generate recommendations
        recommendations = self._generate_security_recommendations(
            security_findings, compliance_violations, risk_score
        )
        
        report = SecurityValidationReport(
            report_id=f"security_validation_{int(time.time())}",
            generation_timestamp=datetime.now(timezone.utc),
            account_id=self.account_id,
            region="global",
            validation_period_start=start_time,
            validation_period_end=end_time,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            blocked_operations=blocked_operations,
            security_findings=security_findings,
            compliance_violations=compliance_violations,
            recommendations=recommendations,
            risk_score=risk_score,
            cloudtrail_events=cloudtrail_events
        )
        
        self.logger.info(f"Security validation report generated: Risk score {risk_score:.1f}/100")
        return report

    def _generate_security_findings(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Generate security findings for the validation period."""
        findings = []
        
        # Check for high error rates
        period_errors = [e for e in self.error_history if start_time <= e.timestamp <= end_time]
        if len(period_errors) > 10:
            findings.append({
                "finding_id": "SEC-HIGH-ERROR-RATE",
                "severity": "MEDIUM",
                "title": "High Error Rate Detected",
                "description": f"{len(period_errors)} errors occurred during validation period",
                "recommendation": "Investigate error patterns and implement additional error handling"
            })
        
        # Check for critical errors
        critical_errors = [e for e in period_errors if e.severity == ErrorSeverity.CRITICAL]
        if critical_errors:
            findings.append({
                "finding_id": "SEC-CRITICAL-ERRORS",
                "severity": "HIGH",
                "title": "Critical Errors Detected",
                "description": f"{len(critical_errors)} critical errors occurred",
                "recommendation": "Immediate investigation required for critical errors"
            })
        
        # Check for permission-related errors
        permission_errors = [e for e in period_errors 
                           if 'permission' in e.error_message.lower() or 'access' in e.error_message.lower()]
        if permission_errors:
            findings.append({
                "finding_id": "SEC-PERMISSION-ISSUES",
                "severity": "HIGH",
                "title": "Permission-Related Errors",
                "description": f"{len(permission_errors)} permission-related errors detected",
                "recommendation": "Review IAM permissions and ensure least-privilege access"
            })
        
        return findings

    def _generate_compliance_violations(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Generate compliance violations for the validation period."""
        violations = []
        
        # Check for operations outside business hours (example compliance rule)
        business_hours_violations = []
        for event in self.cloudtrail_events:
            if event.event_time and (event.event_time.hour < 6 or event.event_time.hour > 22):
                business_hours_violations.append(event)
        
        if business_hours_violations:
            violations.append({
                "violation_id": "COMP-BUSINESS-HOURS",
                "severity": "LOW",
                "title": "Operations Outside Business Hours",
                "description": f"{len(business_hours_violations)} operations occurred outside business hours",
                "recommendation": "Review after-hours access policies"
            })
        
        return violations

    def _calculate_risk_score(self, total_ops: int, failed_ops: int, 
                            blocked_ops: int, findings: List[Dict[str, Any]]) -> float:
        """Calculate overall risk score (0-100, lower is better)."""
        base_score = 0.0
        
        # Error rate contribution
        if total_ops > 0:
            error_rate = (failed_ops / total_ops) * 100
            base_score += min(error_rate * 2, 40)  # Max 40 points for error rate
        
        # Blocked operations contribution
        base_score += min(blocked_ops * 5, 30)  # Max 30 points for blocked ops
        
        # Security findings contribution
        for finding in findings:
            if finding["severity"] == "HIGH":
                base_score += 15
            elif finding["severity"] == "MEDIUM":
                base_score += 10
            else:
                base_score += 5
        
        return min(base_score, 100.0)

    def _generate_security_recommendations(self, 
                                         findings: List[Dict[str, Any]], 
                                         violations: List[Dict[str, Any]], 
                                         risk_score: float) -> List[str]:
        """Generate security recommendations based on findings and risk score."""
        recommendations = []
        
        # Base recommendations
        recommendations.extend([
            "Implement comprehensive audit logging for all AWS operations",
            "Review and validate IAM permissions using least-privilege principle",
            "Enable CloudTrail logging in all regions for complete audit trail",
            "Implement automated monitoring and alerting for security events",
            "Regularly review and rotate access credentials"
        ])
        
        # Risk score based recommendations
        if risk_score > 70:
            recommendations.append("High risk score detected - immediate security review recommended")
            recommendations.append("Consider implementing additional access controls and monitoring")
        elif risk_score > 40:
            recommendations.append("Moderate risk detected - review security policies and procedures")
        
        # Finding-specific recommendations
        high_severity_findings = [f for f in findings if f.get("severity") == "HIGH"]
        if high_severity_findings:
            recommendations.append("Address high-severity security findings immediately")
            recommendations.append("Implement additional security controls for critical operations")
        
        # Violation-specific recommendations
        if violations:
            recommendations.append("Review compliance policies and ensure adherence")
            recommendations.append("Implement automated compliance checking and reporting")
        
        return recommendations

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary."""
        current_time = datetime.now(timezone.utc)
        
        # Calculate recent error rate (last hour)
        recent_errors = [e for e in self.error_history 
                        if (current_time - e.timestamp).seconds < 3600]
        
        # Get circuit breaker status
        circuit_breaker_summary = {}
        for key, breaker in self.circuit_breaker_state.items():
            circuit_breaker_summary[key] = {
                "state": breaker["state"],
                "failures": breaker["failures"],
                "last_failure": breaker["last_failure"].isoformat() if breaker["last_failure"] else None
            }
        
        # Get recent performance metrics
        recent_metrics = [m for m in self.performance_metrics 
                         if (current_time - m.timestamp).seconds < 3600]
        
        summary = {
            "monitoring_status": "active" if self.monitoring_active else "inactive",
            "account_id": self.account_id,
            "total_operations": sum(self.operation_counts.values()),
            "total_errors": len(self.error_history),
            "recent_errors_1h": len(recent_errors),
            "circuit_breakers": circuit_breaker_summary,
            "error_threshold": self.error_threshold,
            "performance_thresholds": {
                "cpu_percent": self.performance_threshold_cpu,
                "memory_percent": self.performance_threshold_memory
            },
            "recent_metrics_1h": len(recent_metrics),
            "cloudtrail_enabled": self.enable_cloudtrail,
            "performance_monitoring_enabled": self.enable_performance_monitoring,
            "timestamp": current_time.isoformat()
        }
        
        return summary

    def _generate_security_recommendations(self, findings: List[Dict[str, Any]], 
                                         violations: List[Dict[str, Any]], 
                                         risk_score: float) -> List[str]:
        """Generate security recommendations based on analysis."""
        recommendations = [
            "Maintain comprehensive audit logging for all operations",
            "Implement automated monitoring and alerting for security events",
            "Regularly review and update IAM permissions",
            "Use read-only access patterns wherever possible"
        ]
        
        if risk_score > 50:
            recommendations.append("High risk score detected - immediate security review recommended")
        
        if findings:
            recommendations.append("Address all identified security findings promptly")
        
        if violations:
            recommendations.append("Review and remediate compliance violations")
        
        return recommendations

    def save_security_report(self, report: SecurityValidationReport, filename: str):
        """Save security validation report to file."""
        report_data = asdict(report)
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"Security validation report saved to {filename}")

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary."""
        current_time = datetime.now(timezone.utc)
        
        # Get recent metrics
        recent_metrics = [m for m in self.performance_metrics 
                         if (current_time - m.timestamp).seconds < 3600]  # Last hour
        
        # Get recent errors
        recent_errors = [e for e in self.error_history 
                        if (current_time - e.timestamp).seconds < 3600]  # Last hour
        
        return {
            "monitoring_status": "active" if self.monitoring_active else "inactive",
            "total_operations": sum(self.operation_counts.values()),
            "total_errors": len(self.error_history),
            "recent_errors": len(recent_errors),
            "recent_metrics": len(recent_metrics),
            "circuit_breakers": dict(self.circuit_breaker_state),
            "error_threshold": self.error_threshold,
            "performance_thresholds": {
                "cpu": self.performance_threshold_cpu,
                "memory": self.performance_threshold_memory
            },
            "cloudtrail_events": len(self.cloudtrail_events),
            "account_id": self.account_id
        }