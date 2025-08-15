---
title: Account Setup Examples
description: Multi-account configuration examples and patterns
sidebar_position: 1
---

# Account Setup Examples

This guide provides comprehensive examples for configuring InvenTag with multiple AWS accounts using different credential methods, regions, and services.

## Basic Multi-Account Configuration

### Example 1: Profile-Based Accounts

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production",
      "profile_name": "prod-profile",
      "regions": ["us-east-1", "us-west-2"]
    },
    {
      "account_id": "123456789013",
      "account_name": "Development",
      "profile_name": "dev-profile",
      "regions": ["us-east-1"]
    }
  ]
}
```

**Usage:**
```bash
./inventag.sh --accounts-file accounts.json --create-excel
```

### Example 2: Cross-Account Role Configuration

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production",
      "cross_account_role": "arn:aws:iam::123456789012:role/InvenTagRole",
      "regions": ["us-east-1", "us-west-2", "eu-west-1"]
    },
    {
      "account_id": "123456789013",
      "account_name": "Staging",
      "cross_account_role": "arn:aws:iam::123456789013:role/InvenTagRole",
      "regions": ["us-east-1"]
    }
  ]
}
```

### Example 3: Mixed Credential Methods

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production",
      "profile_name": "prod-profile",
      "regions": ["us-east-1", "us-west-2"]
    },
    {
      "account_id": "123456789013",
      "account_name": "Development",
      "cross_account_role": "arn:aws:iam::123456789013:role/InvenTagRole",
      "regions": ["us-east-1"]
    },
    {
      "account_id": "123456789014",
      "account_name": "Sandbox",
      "regions": []
    }
  ]
}
```

## Advanced Configuration Examples

### Global Region Configuration

Override regions for all accounts:

```bash
# Scan specific regions globally
./inventag.sh --accounts-file accounts.json --create-excel \
  --account-regions us-east-1,us-west-2,eu-west-1

# Asia-Pacific regions only
./inventag.sh --accounts-file accounts.json --create-excel \
  --account-regions ap-southeast-1,ap-southeast-2,ap-north-1,ap-south-1
```

### Service Descriptions Configuration

Create a `service-descriptions.yaml` file:

```yaml
EC2:
  default_description: "Amazon Elastic Compute Cloud - Virtual servers"
  resource_types:
    Instance: "Virtual machine instances"
    Volume: "Block storage volumes"
    SecurityGroup: "Network security groups"

S3:
  default_description: "Amazon Simple Storage Service - Object storage"
  resource_types:
    Bucket: "Storage containers"

RDS:
  default_description: "Amazon Relational Database Service"
  resource_types:
    DBInstance: "Database instances"
    DBCluster: "Database clusters"
```

**Usage:**
```bash
./inventag.sh --accounts-file accounts.json --create-excel \
  --service-descriptions service-descriptions.yaml
```

### Tag Mappings Configuration

Create a `tag-mappings.yaml` file:

```yaml
"Environment":
  column_name: "Environment"
  default_value: "Unknown"

"inventag:owner":
  column_name: "Resource Owner"
  default_value: "Unassigned"

"CostCenter":
  column_name: "Cost Center"
  default_value: "Not Specified"

"Project":
  column_name: "Project Name"
  default_value: "General"
```

**Usage:**
```bash
./inventag.sh --accounts-file accounts.json --create-excel \
  --tag-mappings tag-mappings.yaml
```

## Production Examples

### Enterprise Multi-Account with Full Analysis

```bash
./inventag.sh \
  --accounts-file accounts.json \
  --service-descriptions service-descriptions.yaml \
  --tag-mappings tag-mappings.yaml \
  --create-excel --create-word \
  --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
  --compliance-standard soc2 --security-validation \
  --s3-bucket enterprise-reports \
  --s3-key-prefix daily-reports/$(date +%Y-%m-%d)/ \
  --max-concurrent-accounts 8 \
  --verbose
```

### CI/CD Integration Example

```bash
#!/bin/bash
# CI/CD script for automated BOM generation

# Validate configuration
./inventag.sh --accounts-file $ACCOUNTS_CONFIG --validate-config

# Validate credentials
./inventag.sh --accounts-file $ACCOUNTS_CONFIG --validate-credentials

# Generate reports with security validation
./inventag.sh \
  --accounts-file $ACCOUNTS_CONFIG \
  --create-excel --create-word \
  --enable-production-safety --security-validation \
  --compliance-standard soc2 \
  --s3-bucket $REPORTS_BUCKET \
  --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
  --audit-output security-audit.json \
  --max-concurrent-accounts 8
```

## Interactive Setup

For interactive account configuration:

```bash
# Interactive multi-account setup
./inventag.sh --accounts-prompt --create-excel --verbose

# Interactive with Google Docs
./inventag.sh --accounts-prompt --create-excel --create-google-docs
```

## Validation Commands

```bash
# Validate configuration file
./inventag.sh --accounts-file accounts.json --validate-config

# Validate credentials for all accounts
./inventag.sh --accounts-file accounts.json --validate-credentials

# Test with debug output
./inventag.sh --accounts-file accounts.json --create-excel --debug
```

## See Also

- [CLI User Guide](../user-guides/cli-user-guide) - Complete CLI reference
- [Configuration Examples](../user-guides/configuration-examples) - Additional configuration patterns
- [Production Safety Guide](../user-guides/production-safety) - Security and compliance features
