#!/usr/bin/env python3
"""
InvenTag Production Safety and Monitoring Demo

This example demonstrates how to use the comprehensive production safety
and monitoring features for secure AWS operations with audit trail generation.
"""

import json
import time
from datetime import datetime, timezone

from inventag.compliance import (
    ComplianceManager,
    ComplianceConfiguration,
    ComplianceStandard
)


def demo_basic_compliance_monitoring():
    """Demonstrate basic compliance monitoring setup."""
    print("=== InvenTag Production Safety and Monitoring Demo ===\n")
    
    # Configure compliance management
    config = ComplianceConfiguration(
        compliance_standard=ComplianceStandard.GENERAL,
        enable_security_validation=True,
        enable_production_monitoring=True,
        enable_cloudtrail_integration=False,  # Disable for demo
        error_threshold=5,
        performance_threshold_cpu=80.0,
        performance_threshold_memory=80.0
    )
    
    print("1. Initializing Compliance Manager...")
    manager = ComplianceManager(config)
    print("   ✓ Security validation enabled")
    print("   ✓ Production monitoring enabled")
    print("   ✓ General compliance standard configured\n")
    
    return manager


def demo_operation_validation(manager):
    """Demonstrate operation validation and monitoring."""
    print("2. Testing Operation Validation and Monitoring...\n")
    
    # Test valid read-only operations
    print("   Testing valid read-only operations:")
    
    valid_operations = [
        ("ec2", "describe_instances"),
        ("s3", "list_buckets"),
        ("iam", "list_users"),
        ("rds", "describe_db_instances")
    ]
    
    for service, operation in valid_operations:
        result = manager.validate_and_monitor_operation(
            service=service,
            operation=operation,
            resource_arn=f"arn:aws:{service}:us-east-1:123456789012:*"
        )
        
        status = "✓ ALLOWED" if result["validation_passed"] else "✗ BLOCKED"
        print(f"     {service}:{operation} - {status}")
    
    print("\n   Testing blocked mutating operations:")
    
    # Test blocked mutating operations
    blocked_operations = [
        ("ec2", "create_instance"),
        ("s3", "delete_bucket"),
        ("iam", "create_user"),
        ("rds", "delete_db_instance")
    ]
    
    for service, operation in blocked_operations:
        result = manager.validate_and_monitor_operation(
            service=service,
            operation=operation
        )
        
        status = "✓ ALLOWED" if result["validation_passed"] else "✗ BLOCKED"
        print(f"     {service}:{operation} - {status}")
    
    print()


def demo_error_handling(manager):
    """Demonstrate error handling and monitoring."""
    print("3. Testing Error Handling and Monitoring...\n")
    
    # Simulate operations with errors
    def failing_operation():
        raise ValueError("Simulated operation failure")
    
    def permission_error_operation():
        from botocore.exceptions import ClientError
        raise ClientError(
            error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            operation_name='DescribeInstances'
        )
    
    print("   Simulating operation failures:")
    
    # Test error handling
    result1 = manager.validate_and_monitor_operation(
        service="ec2",
        operation="describe_instances",
        operation_func=failing_operation
    )
    
    print(f"     ValueError handling - Error captured: {'✓' if result1.get('error_context') else '✗'}")
    
    result2 = manager.validate_and_monitor_operation(
        service="ec2",
        operation="describe_instances", 
        operation_func=permission_error_operation
    )
    
    print(f"     Permission error handling - Error captured: {'✓' if result2.get('error_context') else '✗'}")
    print()


def demo_compliance_assessment(manager):
    """Demonstrate compliance status assessment."""
    print("4. Compliance Status Assessment...\n")
    
    # Get compliance status
    status = manager.assess_compliance_status()
    
    print(f"   Overall Compliance: {'✓ COMPLIANT' if status.is_compliant else '✗ NON-COMPLIANT'}")
    print(f"   Compliance Score: {status.compliance_score:.1f}%")
    print(f"   Risk Score: {status.risk_score:.1f}/100")
    print(f"   Total Operations: {status.total_operations}")
    print(f"   Blocked Operations: {status.blocked_operations}")
    print(f"   Error Count: {status.error_count}")
    print(f"   Security Validation: {'✓ ACTIVE' if status.security_validation_passed else '✗ ISSUES'}")
    print(f"   Production Monitoring: {'✓ ACTIVE' if status.production_monitoring_active else '✗ INACTIVE'}")
    
    if status.recommendations:
        print("\n   Recommendations:")
        for i, rec in enumerate(status.recommendations[:3], 1):
            print(f"     {i}. {rec}")
    
    print()


def demo_comprehensive_reporting(manager):
    """Demonstrate comprehensive compliance reporting."""
    print("5. Comprehensive Compliance Reporting...\n")
    
    # Generate comprehensive report
    report = manager.generate_comprehensive_compliance_report()
    
    print("   Generated comprehensive compliance report:")
    print(f"     Report ID: {report['report_id']}")
    print(f"     Compliance Standard: {report['compliance_standard']}")
    print(f"     Generation Time: {report['generation_timestamp']}")
    
    # Show executive summary
    exec_summary = report['executive_summary']
    print(f"\n   Executive Summary:")
    print(f"     Overall Status: {exec_summary['overall_compliance']}")
    print(f"     Compliance Score: {exec_summary['compliance_score']}")
    print(f"     Risk Level: {exec_summary['risk_level']}")
    print(f"     Total Operations: {exec_summary['total_operations']}")
    print(f"     Blocked Operations: {exec_summary['blocked_operations']}")
    
    if exec_summary.get('key_findings'):
        print(f"\n   Key Findings:")
        for finding in exec_summary['key_findings'][:2]:
            print(f"     • {finding}")
    
    if exec_summary.get('immediate_actions'):
        print(f"\n   Immediate Actions:")
        for action in exec_summary['immediate_actions'][:2]:
            print(f"     • {action}")
    
    # Save report to file
    report_filename = f"compliance_report_{int(time.time())}.json"
    manager.save_compliance_report(report, report_filename)
    print(f"\n   ✓ Report saved to: {report_filename}")
    
    print()


def demo_dashboard_data(manager):
    """Demonstrate dashboard data generation."""
    print("6. Compliance Dashboard Data...\n")
    
    dashboard_data = manager.get_compliance_dashboard_data()
    
    print("   Dashboard Metrics:")
    print(f"     Overall Status: {dashboard_data['overall_status']}")
    print(f"     Compliance Score: {dashboard_data['compliance_score']:.1f}%")
    print(f"     Risk Score: {dashboard_data['risk_score']:.1f}/100")
    
    metrics = dashboard_data['metrics']
    print(f"     Success Rate: {metrics['success_rate']:.1f}%")
    print(f"     Total Operations: {metrics['total_operations']}")
    print(f"     Blocked Operations: {metrics['blocked_operations']}")
    
    status_indicators = dashboard_data['status_indicators']
    print(f"\n   System Status:")
    print(f"     Security Validation: {status_indicators['security_validation']}")
    print(f"     Production Monitoring: {status_indicators['production_monitoring']}")
    print(f"     CloudTrail Integration: {status_indicators['cloudtrail_integration']}")
    
    print()


def demo_audit_cleanup(manager):
    """Demonstrate audit log cleanup."""
    print("7. Audit Log Management...\n")
    
    print("   Performing audit log cleanup (retention: 30 days)...")
    manager.cleanup_audit_logs(retention_days=30)
    print("   ✓ Audit logs cleaned up")
    
    print()


def main():
    """Run the complete production safety and monitoring demo."""
    try:
        # Initialize compliance manager
        manager = demo_basic_compliance_monitoring()
        
        # Demonstrate various features
        demo_operation_validation(manager)
        demo_error_handling(manager)
        demo_compliance_assessment(manager)
        demo_comprehensive_reporting(manager)
        demo_dashboard_data(manager)
        demo_audit_cleanup(manager)
        
        print("=== Demo Complete ===")
        print("\nKey Features Demonstrated:")
        print("✓ Comprehensive security validation with read-only enforcement")
        print("✓ Production-grade error handling with graceful degradation")
        print("✓ Real-time performance monitoring and metrics collection")
        print("✓ Comprehensive compliance reporting and audit trail generation")
        print("✓ Executive dashboard data for compliance visualization")
        print("✓ Automated audit log management and cleanup")
        
        print("\nNext Steps:")
        print("• Integrate with your AWS operations for comprehensive monitoring")
        print("• Configure CloudTrail integration for enhanced audit trails")
        print("• Set up automated compliance reporting for regular assessments")
        print("• Customize thresholds and policies for your organization")
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()