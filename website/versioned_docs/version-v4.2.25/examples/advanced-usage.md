---
title: Advanced Usage Examples
description: Complex scenarios and advanced configuration patterns
sidebar_position: 3
---

# Advanced Usage Examples

This guide covers advanced InvenTag usage patterns for complex enterprise environments and specialized use cases.

## Enterprise Multi-Account Scenarios

### Global Organization with Regional Compliance

```json
{
  "accounts": [
    {
      "account_id": "111111111111",
      "account_name": "US Production",
      "profile_name": "us-prod",
      "regions": ["us-east-1", "us-west-2"],
      "compliance_standard": "soc2"
    },
    {
      "account_id": "222222222222",
      "account_name": "EU Production",
      "profile_name": "eu-prod",
      "regions": ["eu-west-1", "eu-central-1"],
      "compliance_standard": "gdpr"
    },
    {
      "account_id": "333333333333",
      "account_name": "APAC Production",
      "profile_name": "apac-prod",
      "regions": ["ap-southeast-1", "ap-northeast-1"],
      "compliance_standard": "iso27001"
    }
  ]
}
```

**Usage with regional compliance:**
```bash
./inventag.sh \
  --accounts-file global-accounts.json \
  --create-excel --create-word \
  --enable-security-analysis --enable-cost-analysis \
  --enable-production-safety --security-validation \
  --s3-bucket global-compliance-reports \
  --s3-key-prefix compliance/$(date +%Y-%m-%d)/ \
  --per-account-reports \
  --max-concurrent-accounts 6 \
  --verbose
```

### Cross-Account Role with MFA

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production",
      "cross_account_role": "arn:aws:iam::123456789012:role/InvenTagRole",
      "external_id": "unique-external-id-123",
      "mfa_serial": "arn:aws:iam::999999999999:mfa/inventag-user",
      "regions": ["us-east-1", "us-west-2"]
    }
  ]
}
```

## Advanced Service Configuration

### Comprehensive Service Descriptions

```yaml
# advanced-service-descriptions.yaml
EC2:
  default_description: "Amazon Elastic Compute Cloud - Scalable virtual servers"
  resource_types:
    Instance: "Virtual machine instances with compute, memory, and storage"
    Volume: "Elastic Block Store volumes for persistent storage"
    SecurityGroup: "Virtual firewalls controlling network access"
    NetworkInterface: "Virtual network interfaces for EC2 instances"
    Snapshot: "Point-in-time backups of EBS volumes"
    Image: "Amazon Machine Images for launching instances"
    KeyPair: "SSH key pairs for secure instance access"

S3:
  default_description: "Amazon Simple Storage Service - Scalable object storage"
  resource_types:
    Bucket: "Storage containers with global namespace"

RDS:
  default_description: "Amazon Relational Database Service - Managed databases"
  resource_types:
    DBInstance: "Managed database instances"
    DBCluster: "Aurora database clusters"
    DBSnapshot: "Database backups and snapshots"
    DBSubnetGroup: "Database subnet groups for VPC deployment"
    DBParameterGroup: "Database configuration parameters"

Lambda:
  default_description: "AWS Lambda - Serverless compute service"
  resource_types:
    Function: "Serverless functions triggered by events"
    Layer: "Shared code and libraries for Lambda functions"

VPC:
  default_description: "Amazon Virtual Private Cloud - Isolated network environments"
  resource_types:
    VPC: "Virtual private clouds providing network isolation"
    Subnet: "Network segments within VPCs"
    RouteTable: "Routing rules for network traffic"
    InternetGateway: "Gateways providing internet access"
    NatGateway: "Network Address Translation gateways"
    VPCEndpoint: "Private connections to AWS services"

ELB:
  default_description: "Elastic Load Balancing - Distribute traffic across targets"
  resource_types:
    LoadBalancer: "Load balancers distributing incoming traffic"
    TargetGroup: "Groups of targets for load balancer routing"

CloudFormation:
  default_description: "AWS CloudFormation - Infrastructure as Code"
  resource_types:
    Stack: "Collections of AWS resources managed as a unit"

IAM:
  default_description: "AWS Identity and Access Management - Security and access control"
  resource_types:
    User: "IAM users with programmatic or console access"
    Role: "IAM roles for cross-service access"
    Policy: "Permission policies defining access rights"
    Group: "Groups of IAM users with shared permissions"

CloudWatch:
  default_description: "Amazon CloudWatch - Monitoring and observability"
  resource_types:
    Alarm: "Monitoring alarms for metrics and thresholds"
    LogGroup: "Log groups for centralized logging"
```

### Advanced Tag Mappings

```yaml
# enterprise-tag-mappings.yaml
"Environment":
  column_name: "Environment"
  default_value: "Unknown"
  validation_rules:
    - allowed_values: ["prod", "staging", "dev", "test"]

"inventag:owner":
  column_name: "Resource Owner"
  default_value: "Unassigned"
  validation_rules:
    - required: true
    - format: "email"

"CostCenter":
  column_name: "Cost Center"
  default_value: "Not Specified"
  validation_rules:
    - pattern: "^CC-[0-9]{4}$"

"Project":
  column_name: "Project Name"
  default_value: "General"

"DataClassification":
  column_name: "Data Classification"
  default_value: "Internal"
  validation_rules:
    - allowed_values: ["public", "internal", "confidential", "restricted"]

"BackupRequired":
  column_name: "Backup Required"
  default_value: "Yes"
  validation_rules:
    - allowed_values: ["Yes", "No"]

"ComplianceScope":
  column_name: "Compliance Scope"
  default_value: "Standard"
  validation_rules:
    - allowed_values: ["SOC2", "PCI", "HIPAA", "GDPR", "Standard"]

"MaintenanceWindow":
  column_name: "Maintenance Window"
  default_value: "Standard"

"BusinessCriticality":
  column_name: "Business Criticality"
  default_value: "Medium"
  validation_rules:
    - allowed_values: ["Critical", "High", "Medium", "Low"]

"AutoShutdown":
  column_name: "Auto Shutdown"
  default_value: "Enabled"
  validation_rules:
    - allowed_values: ["Enabled", "Disabled"]
```

## Complex Analysis Scenarios

### Security-Focused Analysis

```bash
#!/bin/bash
# Comprehensive security analysis script

./inventag.sh \
  --accounts-file security-accounts.json \
  --service-descriptions security-service-descriptions.yaml \
  --tag-mappings security-tag-mappings.yaml \
  --create-excel --create-word \
  --enable-network-analysis --enable-security-analysis \
  --compliance-standard soc2 \
  --enable-production-safety --security-validation \
  --audit-output detailed-security-audit.json \
  --s3-bucket security-compliance-reports \
  --s3-key-prefix security-analysis/$(date +%Y-%m-%d)/ \
  --max-concurrent-accounts 4 \
  --verbose \
  --debug --log-file security-analysis.log
```

### Cost Optimization Analysis

```bash
#!/bin/bash
# Cost optimization focused analysis

./inventag.sh \
  --accounts-file cost-accounts.json \
  --create-excel --create-word \
  --enable-cost-analysis \
  --enable-network-analysis \
  --s3-bucket cost-optimization-reports \
  --s3-key-prefix cost-analysis/$(date +%Y-%m-%d)/ \
  --generate-changelog \
  --state-file previous-cost-state.json \
  --max-concurrent-accounts 8 \
  --verbose
```

### Compliance Audit Preparation

```bash
#!/bin/bash
# Comprehensive compliance audit preparation

# SOC 2 Compliance
./inventag.sh \
  --accounts-file soc2-accounts.json \
  --service-descriptions compliance-service-descriptions.yaml \
  --tag-mappings compliance-tag-mappings.yaml \
  --create-excel --create-word --create-google-docs \
  --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
  --compliance-standard soc2 \
  --enable-production-safety --security-validation \
  --audit-output soc2-audit-$(date +%Y-%m-%d).json \
  --s3-bucket compliance-audit-reports \
  --s3-key-prefix soc2/$(date +%Y-%m-%d)/ \
  --per-account-reports \
  --max-concurrent-accounts 6 \
  --verbose

# GDPR Compliance (EU accounts)
./inventag.sh \
  --accounts-file gdpr-accounts.json \
  --account-regions eu-west-1,eu-central-1,eu-west-2,eu-north-1 \
  --create-excel --create-word \
  --enable-security-analysis \
  --compliance-standard gdpr \
  --enable-production-safety --security-validation \
  --audit-output gdpr-audit-$(date +%Y-%m-%d).json \
  --s3-bucket compliance-audit-reports \
  --s3-key-prefix gdpr/$(date +%Y-%m-%d)/ \
  --verbose
```

## State Management and Change Tracking

### Delta Analysis with Historical Comparison

```bash
#!/bin/bash
# Advanced state management with change tracking

# Initial baseline
./inventag.sh \
  --accounts-file production-accounts.json \
  --create-excel \
  --state-file baseline-state.json \
  --verbose

# Weekly comparison
./inventag.sh \
  --accounts-file production-accounts.json \
  --create-excel \
  --state-file current-state.json \
  --previous-state baseline-state.json \
  --generate-changelog \
  --s3-bucket change-tracking-reports \
  --s3-key-prefix weekly-changes/$(date +%Y-%m-%d)/ \
  --verbose

# Move current to baseline for next comparison
cp current-state.json baseline-state.json
```

### Automated Change Detection

```bash
#!/bin/bash
# Automated change detection with notifications

PREVIOUS_STATE="states/previous-state.json"
CURRENT_STATE="states/current-state-$(date +%Y-%m-%d).json"
CHANGELOG="changelogs/changelog-$(date +%Y-%m-%d).json"

# Generate current state
./inventag.sh \
  --accounts-file monitoring-accounts.json \
  --create-excel \
  --state-file "$CURRENT_STATE" \
  --previous-state "$PREVIOUS_STATE" \
  --generate-changelog \
  --changelog-output "$CHANGELOG" \
  --verbose

# Check for significant changes
if [ -f "$CHANGELOG" ]; then
    CHANGE_COUNT=$(jq '.changes | length' "$CHANGELOG")
    if [ "$CHANGE_COUNT" -gt 10 ]; then
        # Send alert for significant changes
        aws sns publish \
            --topic-arn "$SNS_TOPIC_ARN" \
            --message "Significant infrastructure changes detected: $CHANGE_COUNT changes"
    fi
fi

# Update previous state
cp "$CURRENT_STATE" "$PREVIOUS_STATE"
```

## Custom Output and Reporting

### Multi-Format Enterprise Reporting

```bash
#!/bin/bash
# Generate reports in multiple formats for different audiences

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUTPUT_DIR="enterprise-reports-$TIMESTAMP"

# Executive Summary (Excel only)
./inventag.sh \
  --accounts-file executive-accounts.json \
  --create-excel \
  --output-dir "$OUTPUT_DIR/executive" \
  --enable-cost-analysis \
  --verbose

# Technical Team (Excel + Word)
./inventag.sh \
  --accounts-file technical-accounts.json \
  --service-descriptions technical-service-descriptions.yaml \
  --create-excel --create-word \
  --enable-network-analysis --enable-security-analysis \
  --output-dir "$OUTPUT_DIR/technical" \
  --verbose

# Compliance Team (All formats)
./inventag.sh \
  --accounts-file compliance-accounts.json \
  --service-descriptions compliance-service-descriptions.yaml \
  --tag-mappings compliance-tag-mappings.yaml \
  --create-excel --create-word --create-google-docs \
  --enable-security-analysis \
  --compliance-standard soc2 \
  --enable-production-safety --security-validation \
  --audit-output "$OUTPUT_DIR/compliance/audit-report.json" \
  --output-dir "$OUTPUT_DIR/compliance" \
  --verbose

# Upload all reports
aws s3 sync "$OUTPUT_DIR" s3://enterprise-reports-bucket/reports/$TIMESTAMP/
```

### Custom Template Integration

```bash
#!/bin/bash
# Using custom templates for branded reports

./inventag.sh \
  --accounts-file branded-accounts.json \
  --create-excel --create-word \
  --excel-template templates/custom-excel-template.json \
  --word-template templates/custom-word-template.yaml \
  --enable-network-analysis --enable-security-analysis \
  --s3-bucket branded-reports \
  --s3-key-prefix custom-branded/$(date +%Y-%m-%d)/ \
  --verbose
```

## Performance Optimization

### Large-Scale Multi-Account Processing

```bash
#!/bin/bash
# Optimized for large-scale environments

./inventag.sh \
  --accounts-file large-scale-accounts.json \
  --create-excel \
  --max-concurrent-accounts 12 \
  --account-timeout 1800 \
  --per-account-reports \
  --s3-bucket large-scale-reports \
  --s3-key-prefix bulk-processing/$(date +%Y-%m-%d)/ \
  --verbose \
  --log-file large-scale-processing.log
```

### Region-Specific Processing

```bash
#!/bin/bash
# Process different regions separately for performance

# US Regions
./inventag.sh \
  --accounts-file us-accounts.json \
  --account-regions us-east-1,us-west-1,us-west-2 \
  --create-excel \
  --output-dir "reports/us-regions" \
  --max-concurrent-accounts 8 \
  --verbose

# EU Regions
./inventag.sh \
  --accounts-file eu-accounts.json \
  --account-regions eu-west-1,eu-central-1,eu-west-2 \
  --create-excel \
  --output-dir "reports/eu-regions" \
  --max-concurrent-accounts 8 \
  --verbose

# APAC Regions
./inventag.sh \
  --accounts-file apac-accounts.json \
  --account-regions ap-southeast-1,ap-northeast-1,ap-south-1 \
  --create-excel \
  --output-dir "reports/apac-regions" \
  --max-concurrent-accounts 8 \
  --verbose
```

## Troubleshooting and Debugging

### Comprehensive Debug Mode

```bash
#!/bin/bash
# Full debugging for troubleshooting

./inventag.sh \
  --accounts-file debug-accounts.json \
  --create-excel \
  --debug \
  --log-file debug-$(date +%Y-%m-%d_%H-%M-%S).log \
  --validate-config \
  --validate-credentials \
  --verbose
```

### Selective Account Processing

```bash
#!/bin/bash
# Process specific accounts for testing

# Test single account
./inventag.sh \
  --accounts-file single-account-test.json \
  --create-excel \
  --debug \
  --verbose

# Test with minimal regions
./inventag.sh \
  --accounts-file test-accounts.json \
  --account-regions us-east-1 \
  --create-excel \
  --debug \
  --verbose
```

## See Also

- [CLI User Guide](../user-guides/cli-user-guide) - Complete CLI reference
- [Configuration Examples](../user-guides/configuration-examples) - Basic configuration patterns
- [Production Safety Guide](../user-guides/production-safety) - Security and compliance features
- [CI/CD Integration](/examples/cicd-integration) - Automated deployment patterns
