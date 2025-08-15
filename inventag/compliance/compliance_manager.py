#!/usr/bin/env python3
"""
InvenTag - Compliance Manager
Unified interface for production safety monitoring and security validation.

This module provides a comprehensive compliance management system that integrates
security validation, production monitoring, and audit trail generation for
enterprise-grade AWS operations.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict

from .security_validator import (
    ReadOnlyAccessValidator,
    ComplianceStandard,
    SecurityValidationResult,
    ComplianceReport,
)
from .production_monitor import (
    ProductionSafetyMonitor,
    ErrorSeverity,
    ErrorContext,
    SecurityValidationReport,
)


@dataclass
class ComplianceConfiguration:
    """Configuration for compliance management."""

    compliance_standard: ComplianceStandard
    enable_security_validation: bool = True
    enable_production_monitoring: bool = True
    enable_cloudtrail_integration: bool = True
    error_threshold: int = 10
    performance_threshold_cpu: float = 80.0
    performance_threshold_memory: float = 80.0
    audit_log_retention_days: int = 90


@dataclass
class ComplianceStatus:
    """Overall compliance status."""

    is_compliant: bool
    compliance_score: float
    security_validation_passed: bool
    production_monitoring_active: bool
    total_operations: int
    blocked_operations: int
    error_count: int
    risk_score: float
    last_assessment: datetime
    recommendations: List[str]


class ComplianceManager:
    """
    Unified compliance management system that integrates security validation
    and production monitoring for comprehensive AWS operations oversight.
    """

    def __init__(self, config: ComplianceConfiguration):
        """Initialize the compliance manager."""
        self.config = config
        self.logger = self._setup_logging()

        # Initialize components
        self.security_validator = None
        self.production_monitor = None

        if config.enable_security_validation:
            self.security_validator = ReadOnlyAccessValidator(
                compliance_standard=config.compliance_standard
            )

        if config.enable_production_monitoring:
            self.production_monitor = ProductionSafetyMonitor(
                enable_cloudtrail=config.enable_cloudtrail_integration,
                enable_performance_monitoring=True,
                error_threshold=config.error_threshold,
                performance_threshold_cpu=config.performance_threshold_cpu,
                performance_threshold_memory=config.performance_threshold_memory,
            )

        self.logger.info("Compliance manager initialized with comprehensive monitoring")

    def _setup_logging(self) -> logging.Logger:
        """Set up compliance management logging."""
        logger = logging.getLogger(f"{__name__}.compliance_manager")
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - COMPLIANCE - %(levelname)s - %(message)s"
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def validate_and_monitor_operation(
        self,
        service: str,
        operation: str,
        resource_arn: Optional[str] = None,
        request_parameters: Optional[Dict[str, Any]] = None,
        operation_func: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive validation and monitoring of AWS operations.

        Args:
            service: AWS service name
            operation: Operation name
            resource_arn: Resource ARN (optional)
            request_parameters: Request parameters (optional)
            operation_func: Function to execute if validation passes (optional)

        Returns:
            Dictionary with validation results, monitoring data, and operation outcome
        """
        start_time = datetime.now(timezone.utc)

        result = {
            "timestamp": start_time.isoformat(),
            "service": service,
            "operation": operation,
            "resource_arn": resource_arn,
            "validation_passed": False,
            "operation_executed": False,
            "operation_successful": False,
            "duration_seconds": 0,
            "security_validation": None,
            "error_context": None,
            "monitoring_data": {},
        }

        try:
            # Security validation
            if self.security_validator:
                security_result = self.security_validator.validate_operation(
                    service, operation, resource_arn, request_parameters
                )
                result["security_validation"] = asdict(security_result)
                result["validation_passed"] = security_result.is_valid

                if not security_result.is_valid:
                    self.logger.warning(
                        f"Operation blocked by security validation: {service}:{operation}"
                    )
                    return result
            else:
                result["validation_passed"] = True

            # Execute operation if provided and validation passed
            if operation_func and result["validation_passed"]:
                try:
                    operation_result = operation_func()
                    result["operation_executed"] = True
                    result["operation_successful"] = True
                    result["operation_result"] = operation_result

                except Exception as e:
                    result["operation_executed"] = True
                    result["operation_successful"] = False

                    # Handle error with production monitor
                    if self.production_monitor:
                        error_context = self.production_monitor.handle_error(
                            e, operation, service, resource_arn
                        )
                        result["error_context"] = asdict(error_context)

                    raise e

        except Exception as e:
            # Ensure error is handled by production monitor
            if self.production_monitor and "error_context" not in result:
                error_context = self.production_monitor.handle_error(
                    e, operation, service, resource_arn
                )
                result["error_context"] = asdict(error_context)

        finally:
            # Record operation metrics
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            result["duration_seconds"] = duration

            if self.production_monitor:
                self.production_monitor.record_operation(
                    operation, service, duration, result["operation_successful"]
                )

                # Get monitoring summary
                result["monitoring_data"] = (
                    self.production_monitor.get_monitoring_summary()
                )

        return result

    def assess_compliance_status(self) -> ComplianceStatus:
        """Assess overall compliance status across all components."""
        self.logger.info("Assessing overall compliance status...")

        # Initialize status values
        is_compliant = True
        compliance_score = 100.0
        security_validation_passed = True
        production_monitoring_active = False
        total_operations = 0
        blocked_operations = 0
        error_count = 0
        risk_score = 0.0
        recommendations = []

        # Security validation assessment
        if self.security_validator:
            audit_summary = self.security_validator.get_audit_summary()
            total_operations += audit_summary.get("total_operations", 0)
            blocked_operations += audit_summary.get("blocked_operations", 0)

            if blocked_operations > 0:
                security_validation_passed = False
                is_compliant = False
                recommendations.append("Review and resolve blocked operations")

        # Production monitoring assessment
        if self.production_monitor:
            monitoring_summary = self.production_monitor.get_monitoring_summary()
            production_monitoring_active = (
                monitoring_summary.get("monitoring_status") == "active"
            )
            error_count = monitoring_summary.get("total_errors", 0)

            # Generate security validation report for risk assessment
            security_report = (
                self.production_monitor.generate_security_validation_report()
            )
            risk_score = security_report.risk_score

            if risk_score > 50:
                is_compliant = False
                recommendations.append(
                    "High risk score detected - review security posture"
                )

            if error_count > self.config.error_threshold:
                is_compliant = False
                recommendations.append(
                    "Error threshold exceeded - investigate error patterns"
                )

        # Calculate overall compliance score
        if total_operations > 0:
            compliance_score = max(
                0,
                100 - (blocked_operations / total_operations * 50) - (risk_score * 0.5),
            )

        # Add general recommendations
        if is_compliant:
            recommendations.append("Maintain current security and monitoring practices")
        else:
            recommendations.append(
                "Immediate attention required for compliance violations"
            )

        status = ComplianceStatus(
            is_compliant=is_compliant,
            compliance_score=compliance_score,
            security_validation_passed=security_validation_passed,
            production_monitoring_active=production_monitoring_active,
            total_operations=total_operations,
            blocked_operations=blocked_operations,
            error_count=error_count,
            risk_score=risk_score,
            last_assessment=datetime.now(timezone.utc),
            recommendations=recommendations,
        )

        self.logger.info(
            f"Compliance assessment complete: {'COMPLIANT' if is_compliant else 'NON-COMPLIANT'}"
        )
        return status

    def generate_comprehensive_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive compliance report combining all components."""
        self.logger.info("Generating comprehensive compliance report...")

        report = {
            "report_id": f"compliance_report_{int(datetime.now(timezone.utc).timestamp())}",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "compliance_standard": self.config.compliance_standard.value,
            "configuration": asdict(self.config),
            "compliance_status": None,
            "security_validation_report": None,
            "production_monitoring_report": None,
            "security_compliance_report": None,
            "recommendations": [],
            "executive_summary": {},
        }

        # Overall compliance status
        compliance_status = self.assess_compliance_status()
        report["compliance_status"] = asdict(compliance_status)

        # Security validation report
        if self.security_validator:
            compliance_report = self.security_validator.generate_compliance_report()
            report["security_compliance_report"] = asdict(compliance_report)

        # Production monitoring report
        if self.production_monitor:
            security_report = (
                self.production_monitor.generate_security_validation_report()
            )
            report["production_monitoring_report"] = asdict(security_report)

        # Consolidate recommendations
        all_recommendations = set(compliance_status.recommendations)

        if report["security_compliance_report"]:
            all_recommendations.update(
                report["security_compliance_report"]["recommendations"]
            )

        if report["production_monitoring_report"]:
            all_recommendations.update(
                report["production_monitoring_report"]["recommendations"]
            )

        report["recommendations"] = list(all_recommendations)

        # Executive summary
        report["executive_summary"] = {
            "overall_compliance": (
                "COMPLIANT" if compliance_status.is_compliant else "NON-COMPLIANT"
            ),
            "compliance_score": f"{compliance_status.compliance_score:.1f}%",
            "risk_level": (
                "HIGH"
                if compliance_status.risk_score > 70
                else "MEDIUM" if compliance_status.risk_score > 30 else "LOW"
            ),
            "total_operations": compliance_status.total_operations,
            "blocked_operations": compliance_status.blocked_operations,
            "error_count": compliance_status.error_count,
            "monitoring_active": compliance_status.production_monitoring_active,
            "key_findings": self._extract_key_findings(report),
            "immediate_actions": self._extract_immediate_actions(report),
        }

        self.logger.info("Comprehensive compliance report generated successfully")
        return report

    def _extract_key_findings(self, report: Dict[str, Any]) -> List[str]:
        """Extract key findings from the comprehensive report."""
        findings = []

        compliance_status = report.get("compliance_status", {})

        if not compliance_status.get("is_compliant", True):
            findings.append("System is not fully compliant with security requirements")

        if compliance_status.get("blocked_operations", 0) > 0:
            findings.append(
                f"{compliance_status['blocked_operations']} operations were blocked for security reasons"
            )

        if compliance_status.get("risk_score", 0) > 50:
            findings.append("High risk score indicates potential security concerns")

        if compliance_status.get("error_count", 0) > self.config.error_threshold:
            findings.append(
                "Error threshold exceeded - system stability may be affected"
            )

        return findings

    def _extract_immediate_actions(self, report: Dict[str, Any]) -> List[str]:
        """Extract immediate actions from the comprehensive report."""
        actions = []

        compliance_status = report.get("compliance_status", {})

        if not compliance_status.get("security_validation_passed", True):
            actions.append("Review and resolve blocked security operations")

        if compliance_status.get("risk_score", 0) > 70:
            actions.append("Immediate security review required due to high risk score")

        if not compliance_status.get("production_monitoring_active", False):
            actions.append("Enable production monitoring for comprehensive oversight")

        return actions

    def save_compliance_report(self, report: Dict[str, Any], filename: str):
        """Save comprehensive compliance report to file."""
        with open(filename, "w") as f:
            json.dump(report, f, indent=2, default=str)

        self.logger.info(f"Comprehensive compliance report saved to {filename}")

    def cleanup_audit_logs(self, retention_days: Optional[int] = None):
        """Clean up old audit logs based on retention policy."""
        retention_days = retention_days or self.config.audit_log_retention_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        self.logger.info(f"Cleaning up audit logs older than {retention_days} days")

        # Clean up security validator audit entries
        if self.security_validator:
            original_count = len(self.security_validator.audit_entries)
            self.security_validator.audit_entries = [
                entry
                for entry in self.security_validator.audit_entries
                if entry.timestamp > cutoff_date
            ]
            cleaned_count = original_count - len(self.security_validator.audit_entries)
            self.logger.info(f"Cleaned {cleaned_count} security audit entries")

        # Clean up production monitor history
        if self.production_monitor:
            original_error_count = len(self.production_monitor.error_history)
            self.production_monitor.error_history = [
                error
                for error in self.production_monitor.error_history
                if error.timestamp > cutoff_date
            ]
            cleaned_error_count = original_error_count - len(
                self.production_monitor.error_history
            )

            original_metrics_count = len(self.production_monitor.performance_metrics)
            self.production_monitor.performance_metrics = [
                metric
                for metric in self.production_monitor.performance_metrics
                if metric.timestamp > cutoff_date
            ]
            cleaned_metrics_count = original_metrics_count - len(
                self.production_monitor.performance_metrics
            )

            self.logger.info(
                f"Cleaned {cleaned_error_count} error entries and {cleaned_metrics_count} performance metrics"
            )

    def get_compliance_dashboard_data(self) -> Dict[str, Any]:
        """Get data for compliance dashboard visualization."""
        compliance_status = self.assess_compliance_status()

        dashboard_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": (
                "COMPLIANT" if compliance_status.is_compliant else "NON-COMPLIANT"
            ),
            "compliance_score": compliance_status.compliance_score,
            "risk_score": compliance_status.risk_score,
            "metrics": {
                "total_operations": compliance_status.total_operations,
                "blocked_operations": compliance_status.blocked_operations,
                "error_count": compliance_status.error_count,
                "success_rate": (
                    (compliance_status.total_operations - compliance_status.error_count)
                    / max(compliance_status.total_operations, 1)
                )
                * 100,
            },
            "status_indicators": {
                "security_validation": (
                    "ACTIVE" if self.security_validator else "DISABLED"
                ),
                "production_monitoring": (
                    "ACTIVE"
                    if compliance_status.production_monitoring_active
                    else "INACTIVE"
                ),
                "cloudtrail_integration": (
                    "ENABLED"
                    if self.config.enable_cloudtrail_integration
                    else "DISABLED"
                ),
            },
            "recent_activity": self._get_recent_activity_summary(),
            "recommendations": compliance_status.recommendations[
                :5
            ],  # Top 5 recommendations
        }

        return dashboard_data

    def _get_recent_activity_summary(self) -> Dict[str, Any]:
        """Get summary of recent activity for dashboard."""
        summary = {
            "last_24h": {"operations": 0, "errors": 0, "blocked": 0},
            "last_hour": {"operations": 0, "errors": 0, "blocked": 0},
        }

        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_hour = now - timedelta(hours=1)

        # Count security validator activities
        if self.security_validator:
            for entry in self.security_validator.audit_entries:
                if entry.timestamp > last_24h:
                    summary["last_24h"]["operations"] += 1
                    if entry.timestamp > last_hour:
                        summary["last_hour"]["operations"] += 1

        # Count production monitor activities
        if self.production_monitor:
            for error in self.production_monitor.error_history:
                if error.timestamp > last_24h:
                    summary["last_24h"]["errors"] += 1
                    if error.timestamp > last_hour:
                        summary["last_hour"]["errors"] += 1

        return summary
