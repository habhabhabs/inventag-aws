#!/usr/bin/env python3
"""
InvenTag compliance package.

``ComprehensiveTagComplianceChecker`` checks resource tags against a list of
required tag keys (used by ``scripts/legacy/tag_compliance_checker.py``).

The other classes exported here (``ReadOnlyAccessValidator``,
``ProductionSafetyMonitor``, ``ComplianceManager`` and their data classes) are
not used by the ``inventag`` command. The read-only guard in
``inventag.security.read_only_guard`` is what blocks non-read AWS calls.
Nothing in this package assesses or certifies compliance with SOC 2, PCI DSS,
HIPAA, GDPR, ISO 27001 or any other framework.
"""

from .checker import ComprehensiveTagComplianceChecker

from .security_validator import (
    ReadOnlyAccessValidator,
    OperationType,
    ComplianceStandard,
    SecurityValidationResult,
    AuditLogEntry,
    ComplianceReport,
)

from .production_monitor import (
    ProductionSafetyMonitor,
    ErrorSeverity,
    MonitoringMetric,
    ErrorContext,
    PerformanceMetric,
    CloudTrailEvent,
    SecurityValidationReport,
)

from .compliance_manager import (
    ComplianceManager,
    ComplianceConfiguration,
    ComplianceStatus,
)

__all__ = [
    "ComprehensiveTagComplianceChecker",
    "ReadOnlyAccessValidator",
    "ProductionSafetyMonitor",
    "ComplianceManager",
    "ComplianceConfiguration",
    "ComplianceStatus",
    "OperationType",
    "ComplianceStandard",
    "ErrorSeverity",
    "MonitoringMetric",
    "SecurityValidationResult",
    "AuditLogEntry",
    "ComplianceReport",
    "ErrorContext",
    "PerformanceMetric",
    "CloudTrailEvent",
    "SecurityValidationReport",
]
