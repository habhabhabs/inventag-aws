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

# The classes below are not used by the ``inventag`` command. Their modules
# (``psutil``, a monitor thread) load on first use, so ``inventag --version``
# and every scan start without them. ``from inventag.compliance import X`` works
# for every name in ``__all__`` as before.
_LAZY = {
    "ReadOnlyAccessValidator": "security_validator",
    "OperationType": "security_validator",
    "ComplianceStandard": "security_validator",
    "SecurityValidationResult": "security_validator",
    "AuditLogEntry": "security_validator",
    "ComplianceReport": "security_validator",
    "ProductionSafetyMonitor": "production_monitor",
    "ErrorSeverity": "production_monitor",
    "MonitoringMetric": "production_monitor",
    "ErrorContext": "production_monitor",
    "PerformanceMetric": "production_monitor",
    "CloudTrailEvent": "production_monitor",
    "SecurityValidationReport": "production_monitor",
    "ComplianceManager": "compliance_manager",
    "ComplianceConfiguration": "compliance_manager",
    "ComplianceStatus": "compliance_manager",
}


def __getattr__(name):
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(f".{module_name}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY))


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
