# InvenTag Core Module Integration

## Overview

The InvenTag core module (`inventag.core`) provides unified access to all major components including multi-account BOM generation, credential management, CI/CD integration, and state management. This integration simplifies imports and provides a cohesive API for enterprise-grade cloud governance.

## Core Components

The core module exposes the following components:

### Multi-Account BOM Generation
- **`CloudBOMGenerator`**: Multi-account orchestrator for comprehensive BOM generation
- **`MultiAccountConfig`**: Configuration management for multi-account setups
- **`AccountContext`**: Individual account processing context
- **`AccountCredentials`**: Secure credential management for accounts

### Credential Management
- **`CredentialManager`**: Secure credential validation and management
- **`CredentialValidationResult`**: Credential validation results
- **`SecureCredentialFile`**: Encrypted credential file handling

### CI/CD Integration
- **`CICDIntegration`**: Comprehensive CI/CD pipeline integration
- **`S3UploadConfig`**: S3 upload configuration and management
- **`ComplianceGateConfig`**: Compliance gate configuration
- **`NotificationConfig`**: Multi-channel notification configuration
- **`PrometheusConfig`**: Prometheus metrics configuration
- **`PrometheusMetrics`**: Metrics collection and export
- **`CICDResult`**: CI/CD execution results

### State Management (New Integration)
- **`StateManager`**: Persistent storage and versioning of inventory states
- **`DeltaDetector`**: Advanced change detection and analysis
- **`ChangelogGenerator`**: Professional change documentation and reporting

## Usage Examples

### Basic Multi-Account BOM Generation with State Management

```python
from inventag.core import (
    CloudBOMGenerator, 
    StateManager, 
    DeltaDetector, 
    ChangelogGenerator
)

# Initialize components
generator = CloudBOMGenerator.from_credentials_file('accounts.json')
state_manager = StateManager(state_dir="inventory_states")
delta_detector = DeltaDetector()
changelog_generator = ChangelogGenerator()

# Generate comprehensive BOM
result = generator.generate_comprehensive_bom(
    output_formats=['excel', 'word'],
    enable_compliance_checking=True,
    enable_network_analysis=True,
    enable_security_analysis=True
)

# Save state for change tracking
state_id = state_manager.save_state(
    resources=result.all_resources,
    account_id=result.primary_account_id,
    regions=result.regions_processed,
    discovery_method="comprehensive",
    compliance_data=result.compliance_summary,
    network_analysis=result.network_analysis,
    security_analysis=result.security_analysis,
    tags={
        "purpose": "monthly_audit",
        "environment": "production",
        "generated_by": "inventag_core"
    }
)

print(f"BOM generated successfully. State saved as: {state_id}")
print(f"Total resources discovered: {len(result.all_resources)}")
print(f"Accounts processed: {len(result.account_results)}")
```

### Change Detection and Changelog Generation

```python
from inventag.core import StateManager, DeltaDetector, ChangelogGenerator

# Initialize state management
state_manager = StateManager(state_dir="inventory_states")
delta_detector = DeltaDetector()
changelog_generator = ChangelogGenerator()

# Get the two most recent states for comparison
states = state_manager.list_states(limit=2)

if len(states) >= 2:
    # Get comparison data
    comparison = state_manager.get_state_comparison_data(
        state_id1=states[1]['state_id'],  # Older state
        state_id2=states[0]['state_id']   # Newer state
    )
    
    # Detect changes
    delta_report = delta_detector.detect_changes(
        old_resources=comparison['state1']['resources'],
        new_resources=comparison['state2']['resources'],
        state1_id=states[1]['state_id'],
        state2_id=states[0]['state_id']
    )
    
    # Generate changelog if changes detected
    if delta_report.summary['total_changes'] > 0:
        changelog = changelog_generator.generate_changelog(
            delta_report=delta_report,
            format='markdown',
            include_details=True,
            include_executive_summary=True
        )
        
        # Export changelog
        changelog_generator.export_changelog(
            changelog, 
            f'infrastructure_changes_{states[0]["state_id"]}.md'
        )
        
        print(f"Changelog generated with {delta_report.summary['total_changes']} changes")
        print(f"Added: {delta_report.summary['added_count']}")
        print(f"Removed: {delta_report.summary['removed_count']}")
        print(f"Modified: {delta_report.summary['modified_count']}")
        
        # Check for critical changes
        critical_changes = [
            r for r in (delta_report.added_resources + 
                       delta_report.removed_resources + 
                       delta_report.modified_resources)
            if hasattr(r, 'severity') and r.severity.value == 'critical'
        ]
        
        if critical_changes:
            print(f"⚠️  {len(critical_changes)} critical changes detected!")
    else:
        print("No changes detected between states")
else:
    print("Need at least 2 states for comparison")
```

### CI/CD Integration with State Management

```python
from inventag.core import (
    CloudBOMGenerator,
    CICDIntegration,
    S3UploadConfig,
    ComplianceGateConfig,
    NotificationConfig,
    StateManager,
    DeltaDetector,
    ChangelogGenerator
)

# Configure CI/CD integration
s3_config = S3UploadConfig(
    bucket_name="compliance-reports",
    key_prefix="inventag-bom",
    region="us-east-1",
    encryption="AES256",
    lifecycle_days=90
)

compliance_config = ComplianceGateConfig(
    minimum_compliance_percentage=85.0,
    critical_violations_threshold=0,
    required_tags=["Environment", "Owner", "CostCenter"],
    fail_on_security_issues=True
)

notification_config = NotificationConfig(
    slack_webhook_url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    include_summary=True,
    include_document_links=True,
    notify_on_success=True,
    notify_on_failure=True
)

# Initialize components
generator = CloudBOMGenerator.from_credentials_file('accounts.json')
cicd = CICDIntegration(s3_config, compliance_config, notification_config)
state_manager = StateManager(state_dir="ci_states")
delta_detector = DeltaDetector()
changelog_generator = ChangelogGenerator()

# Execute CI/CD pipeline with state management
result = cicd.execute_pipeline_integration(
    bom_generator=generator,
    output_formats=["excel", "word", "json"],
    upload_to_s3=True,
    send_notifications=True,
    export_metrics=True
)

# Save state after successful BOM generation
if result.success:
    state_id = state_manager.save_state(
        resources=result.bom_data.get('all_resources', []),
        account_id=result.bom_data.get('primary_account_id', 'unknown'),
        regions=result.bom_data.get('regions_processed', []),
        tags={
            "ci_run": "true",
            "pipeline_id": result.pipeline_id,
            "compliance_gate": "passed" if result.compliance_gate_passed else "failed"
        }
    )
    
    # Generate change report for CI/CD
    states = state_manager.list_states(limit=2)
    if len(states) >= 2:
        comparison = state_manager.get_state_comparison_data(
            states[1]['state_id'], states[0]['state_id']
        )
        
        delta_report = delta_detector.detect_changes(
            old_resources=comparison['state1']['resources'],
            new_resources=comparison['state2']['resources'],
            state1_id=states[1]['state_id'],
            state2_id=states[0]['state_id']
        )
        
        if delta_report.summary['total_changes'] > 0:
            # Generate executive summary for CI/CD
            executive_summary = changelog_generator.generate_executive_summary(
                delta_report
            )
            
            # Upload change report to S3
            import boto3
            s3_client = boto3.client('s3')
            s3_client.put_object(
                Bucket=s3_config.bucket_name,
                Key=f"{s3_config.key_prefix}/changes/change_report_{state_id}.md",
                Body=executive_summary.encode('utf-8'),
                ContentType='text/markdown'
            )
            
            print(f"Change report uploaded: s3://{s3_config.bucket_name}/{s3_config.key_prefix}/changes/change_report_{state_id}.md")

print(f"CI/CD Pipeline: {'SUCCESS' if result.success else 'FAILED'}")
print(f"Compliance Gate: {'PASSED' if result.compliance_gate_passed else 'FAILED'}")
print(f"Documents Generated: {len(result.generated_documents)}")
print(f"S3 Uploads: {len(result.s3_uploads)}")
```

### Advanced Credential Management

```python
from inventag.core import CredentialManager, CloudBOMGenerator

# Initialize credential manager
cred_manager = CredentialManager()

# Validate credentials from multiple sources
validation_results = []

# Validate environment credentials
env_result = cred_manager.validate_environment_credentials()
validation_results.append(("Environment", env_result))

# Validate profile credentials
profile_result = cred_manager.validate_profile_credentials("production")
validation_results.append(("Profile", profile_result))

# Validate credentials file
file_result = cred_manager.validate_credentials_file("accounts.json")
validation_results.append(("File", file_result))

# Report validation results
for source, result in validation_results:
    print(f"{source} Credentials: {'✓ VALID' if result.is_valid else '✗ INVALID'}")
    if not result.is_valid:
        print(f"  Error: {result.error_message}")
    else:
        print(f"  Account: {result.account_id}")
        print(f"  Permissions: {len(result.available_permissions)} validated")

# Use the best available credentials
if any(result.is_valid for _, result in validation_results):
    # Initialize BOM generator with validated credentials
    generator = CloudBOMGenerator.from_credentials_file('accounts.json')
    
    # Generate BOM with credential validation
    result = generator.generate_comprehensive_bom(
        output_formats=['excel'],
        validate_credentials=True,
        credential_validation_timeout=30
    )
    
    print(f"BOM generated with {len(result.account_results)} validated accounts")
else:
    print("No valid credentials found")
```

## Integration Patterns

### Enterprise CI/CD Pipeline

```python
"""
Complete enterprise CI/CD integration with state management,
change detection, and compliance reporting.
"""
from inventag.core import *
import os
import sys

def enterprise_pipeline():
    try:
        # Initialize all components
        generator = CloudBOMGenerator.from_credentials_file(
            os.environ.get('ACCOUNTS_CONFIG', 'accounts.json')
        )
        
        state_manager = StateManager(
            state_dir=os.environ.get('STATE_DIR', 'pipeline_states'),
            retention_days=int(os.environ.get('STATE_RETENTION_DAYS', '90'))
        )
        
        cicd = CICDIntegration(
            s3_config=S3UploadConfig(
                bucket_name=os.environ['S3_BUCKET'],
                key_prefix=os.environ.get('S3_PREFIX', 'inventag-reports'),
                region=os.environ.get('AWS_REGION', 'us-east-1')
            ),
            compliance_gate_config=ComplianceGateConfig(
                minimum_compliance_percentage=float(os.environ.get('MIN_COMPLIANCE', '85.0')),
                fail_on_security_issues=os.environ.get('FAIL_ON_SECURITY', 'true').lower() == 'true'
            ),
            notification_config=NotificationConfig(
                slack_webhook_url=os.environ.get('SLACK_WEBHOOK'),
                notify_on_success=True,
                notify_on_failure=True
            )
        )
        
        delta_detector = DeltaDetector()
        changelog_generator = ChangelogGenerator()
        
        # Execute pipeline
        result = cicd.execute_pipeline_integration(
            bom_generator=generator,
            output_formats=os.environ.get('OUTPUT_FORMATS', 'excel,word').split(','),
            upload_to_s3=True,
            send_notifications=True,
            export_metrics=True
        )
        
        # Handle state management
        if result.success:
            # Save current state
            state_id = state_manager.save_state(
                resources=result.bom_data.get('all_resources', []),
                account_id=result.bom_data.get('primary_account_id', 'pipeline'),
                regions=result.bom_data.get('regions_processed', []),
                tags={
                    "pipeline": "enterprise",
                    "build_id": os.environ.get('BUILD_ID', 'unknown'),
                    "commit_sha": os.environ.get('COMMIT_SHA', 'unknown')
                }
            )
            
            # Generate change report
            states = state_manager.list_states(limit=2)
            if len(states) >= 2:
                comparison = state_manager.get_state_comparison_data(
                    states[1]['state_id'], states[0]['state_id']
                )
                
                delta_report = delta_detector.detect_changes(
                    old_resources=comparison['state1']['resources'],
                    new_resources=comparison['state2']['resources'],
                    state1_id=states[1]['state_id'],
                    state2_id=states[0]['state_id']
                )
                
                # Generate and upload changelog
                if delta_report.summary['total_changes'] > 0:
                    changelog = changelog_generator.generate_changelog(
                        delta_report=delta_report,
                        format='markdown',
                        include_details=True,
                        include_executive_summary=True
                    )
                    
                    # Upload to S3
                    import boto3
                    s3_client = boto3.client('s3')
                    s3_client.put_object(
                        Bucket=os.environ['S3_BUCKET'],
                        Key=f"{os.environ.get('S3_PREFIX', 'inventag-reports')}/changes/changelog_{state_id}.md",
                        Body=changelog.encode('utf-8'),
                        ContentType='text/markdown'
                    )
                    
                    print(f"📝 Changelog generated with {delta_report.summary['total_changes']} changes")
                    
                    # Fail pipeline on critical changes if configured
                    critical_changes = [
                        r for r in (delta_report.added_resources + 
                                   delta_report.removed_resources + 
                                   delta_report.modified_resources)
                        if hasattr(r, 'severity') and r.severity.value == 'critical'
                    ]
                    
                    if critical_changes and os.environ.get('FAIL_ON_CRITICAL_CHANGES', 'false').lower() == 'true':
                        print(f"❌ Pipeline failed: {len(critical_changes)} critical changes detected")
                        sys.exit(1)
        
        # Report results
        print(f"🚀 Pipeline Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"🛡️  Compliance Gate: {'PASSED' if result.compliance_gate_passed else 'FAILED'}")
        print(f"📊 Documents Generated: {len(result.generated_documents)}")
        print(f"☁️  S3 Uploads: {len(result.s3_uploads)}")
        
        # Exit with appropriate code
        sys.exit(0 if result.success and result.compliance_gate_passed else 1)
        
    except Exception as e:
        print(f"❌ Pipeline failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    enterprise_pipeline()
```

## Best Practices

### State Management Integration

1. **Regular State Snapshots**: Save states after each BOM generation for comprehensive change tracking
2. **Meaningful Tags**: Use descriptive tags to identify state context and purpose
3. **Retention Policies**: Configure appropriate retention based on compliance and audit requirements
4. **Change Thresholds**: Set up alerting for significant infrastructure changes

### CI/CD Integration

1. **Credential Security**: Use IAM roles and temporary credentials in CI/CD environments
2. **Parallel Processing**: Configure appropriate concurrency limits for multi-account processing
3. **Error Handling**: Implement comprehensive error handling and retry logic
4. **Artifact Management**: Store and version all generated documents and reports

### Performance Optimization

1. **Resource Filtering**: Use service and region filters for large environments
2. **Caching**: Leverage state caching for repeated operations
3. **Parallel Execution**: Use multi-threading for independent operations
4. **Memory Management**: Monitor memory usage in large-scale deployments

## Migration Guide

### From Individual Imports

**Before:**
```python
from inventag.core.cloud_bom_generator import CloudBOMGenerator
from inventag.state.state_manager import StateManager
from inventag.state.delta_detector import DeltaDetector
from inventag.state.changelog_generator import ChangelogGenerator
```

**After:**
```python
from inventag.core import (
    CloudBOMGenerator,
    StateManager,
    DeltaDetector,
    ChangelogGenerator
)
```

### From Legacy CLI Usage

**Before:**
```bash
python scripts/aws_resource_inventory.py
python scripts/tag_compliance_checker.py
python scripts/bom_converter.py
```

**After:**
```bash
python -m inventag.cli.main --create-excel --create-word --enable-state-tracking
```

## Troubleshooting

### Common Issues

**Import Errors**
```python
# Ensure you're importing from the core module
from inventag.core import StateManager  # ✓ Correct
from inventag.state import StateManager  # ✗ Direct import still works but not recommended
```

**State Management Issues**
```python
# Check state directory permissions
import os
state_dir = "inventory_states"
if not os.path.exists(state_dir):
    os.makedirs(state_dir, mode=0o755)
```

**Memory Issues with Large States**
```python
# Use resource filtering for large environments
generator = CloudBOMGenerator.from_credentials_file('accounts.json')
result = generator.generate_comprehensive_bom(
    service_filters=['ec2', 's3', 'rds'],  # Limit services
    region_filters=['us-east-1', 'us-west-2'],  # Limit regions
    output_formats=['json']  # Use lightweight format for state storage
)
```

For more detailed information, see:
- [State Management Documentation](STATE_MANAGEMENT.md)
- [CI/CD Integration Guide](CICD_INTEGRATION.md)
- [CLI User Guide](CLI_USER_GUIDE.md)