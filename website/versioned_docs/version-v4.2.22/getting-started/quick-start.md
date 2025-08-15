---
title: Quick Start Guide
description: Get up and running with InvenTag in minutes
sidebar_position: 1
---

# 🚀 InvenTag Quick Start Guide

Get up and running with InvenTag in minutes!

## Prerequisites

- Python 3.8+
- AWS CLI configured with appropriate permissions
- Required Python packages (install with `pip install -r requirements.txt`)

## Basic Usage

### 1. Simple BOM Generation

Generate a basic Excel BOM for your default AWS account with optimized discovery:

```bash
# Unix/Linux/macOS (auto-detects python3/python)
./inventag.sh --create-excel

# Windows (auto-detects python3/python/py)
inventag.bat --create-excel

# Direct Python (use python3 if available)
python3 -m inventag_cli --create-excel
```

**✨ Enhanced Performance**: InvenTag automatically uses the optimized discovery system for 3-4x faster resource discovery with better service coverage.

### 2. Multi-Format Output

Generate Excel, Word, and Google Docs reports:

```bash
# Excel and Word documents (scripts auto-detect Python)
./inventag.sh --create-excel --create-word --verbose

# All formats including Google Docs (requires Google API credentials)
./inventag.sh --create-excel --create-word --create-google-docs --verbose
```

### 3. Multi-Account Setup

Create an accounts configuration file:

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Global Production",
      "profile_name": "prod-profile",
      "regions": ["us-east-1", "us-west-2", "ap-southeast-1", "eu-west-1"]
    },
    {
      "account_id": "123456789013", 
      "account_name": "APAC Development",
      "profile_name": "dev-profile",
      "regions": ["ap-southeast-1", "ap-north-1", "ap-south-1"]
    },
    {
      "account_id": "123456789014",
      "account_name": "All Regions Account",
      "profile_name": "global-profile",
      "regions": []
    }
  ]
}
```

**Note:** Empty `regions` array means scan all available AWS regions (default behavior).

Then run:

```bash
./inventag.sh --accounts-file accounts.json --create-excel
```

### 4. Multi-Region Selection

Specify regions to scan across all accounts:

```bash
# Scan specific regions globally
./inventag.sh --create-excel \
  --account-regions us-east-1,us-west-2,ap-southeast-1,ap-north-1

# Asia-Pacific regions only
./inventag.sh --create-excel \
  --account-regions ap-southeast-1,ap-southeast-2,ap-north-1,ap-south-1

# European regions with GDPR compliance
./inventag.sh --create-excel \
  --account-regions eu-west-1,eu-west-2,eu-central-1 \
  --compliance-standard gdpr

# All regions (default behavior)
./inventag.sh --create-excel --verbose
```

### 5. Advanced Analysis

Enable comprehensive analysis features:

```bash
./inventag.sh \
  --create-excel \
  --enable-network-analysis \
  --enable-security-analysis \
  --enable-cost-analysis \
  --verbose
```

### 6. Production Deployment

For production use with S3 upload and security features:

```bash
./inventag.sh \
  --accounts-file accounts.json \
  --create-excel --create-word \
  --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
  --s3-bucket my-reports-bucket \
  --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
  --compliance-standard soc2 \
  --enable-production-safety --security-validation \
  --audit-output security-audit.json \
  --verbose
```

## Configuration Examples

### Service Descriptions

Customize service descriptions in your BOM:

```yaml
# service-descriptions.yaml
EC2:
  default_description: "Amazon Elastic Compute Cloud - Virtual servers"
  resource_types:
    Instance: "Virtual machine instances"
    Volume: "Block storage volumes"

S3:
  default_description: "Amazon Simple Storage Service - Object storage"
  resource_types:
    Bucket: "Storage containers"
```

Use with:
```bash
# Using the provided example
./inventag.sh --create-excel --service-descriptions config/defaults/services/service_descriptions_example.yaml

# Or create your own
./inventag.sh --create-excel --service-descriptions service-descriptions.yaml
```

### Tag Mappings

Map AWS tags to custom BOM columns:

```yaml
# tag-mappings.yaml
"Environment":
  column_name: "Environment"
  default_value: "Unknown"

"inventag:owner":
  column_name: "Resource Owner"
  default_value: "Unassigned"
```

Use with:
```bash
# Using the provided example
./inventag.sh --create-excel --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml

# Or create your own
./inventag.sh --create-excel --tag-mappings tag-mappings.yaml
```

## Common Commands

```bash
# Validate configuration
./inventag.sh --accounts-file accounts.json --validate-config

# Validate credentials
./inventag.sh --accounts-file accounts.json --validate-credentials

# Debug mode
./inventag.sh --create-excel --debug --log-file debug.log

# Interactive account setup with Google Docs
./inventag.sh --accounts-prompt --create-excel --create-google-docs

# Cross-account role assumption
./inventag.sh --cross-account-role InvenTagRole --create-excel

# CI/CD integration with security validation
./inventag.sh \
  --accounts-file $ACCOUNTS_CONFIG \
  --create-excel \
  --s3-bucket $REPORTS_BUCKET \
  --max-concurrent-accounts 8 \
  --security-validation --compliance-standard soc2
```

## Output Files

InvenTag generates files in the `bom_output` directory (or your specified output directory):

- `AWS_BOM_YYYYMMDD_HHMMSS.xlsx` - Excel workbook with multiple sheets
- `AWS_BOM_YYYYMMDD_HHMMSS.docx` - Professional Word document
- `state_YYYYMMDD_HHMMSS.json` - State file for change tracking

## Performance Features

InvenTag includes an **Optimized Discovery System** that provides significant performance improvements:

### Key Performance Benefits

| Feature | Benefit |
|---------|---------|
| **3-4x Faster Discovery** | Parallel processing and service-specific patterns |
| **Enhanced Service Coverage** | Better detection of CloudFront, IAM, Route53, S3, Lambda |
| **Higher Quality Results** | 98% of resources achieve high confidence scores |
| **Intelligent Field Mapping** | Service-specific extraction for better accuracy |

### Performance Tips

```bash
# Maximum performance with parallel processing
./inventag.sh --create-excel --max-concurrent-accounts 6

# Focus on specific services for faster processing
./inventag.sh --create-excel --service-filters ec2,s3,rds,lambda

# Single region for fastest discovery
./inventag.sh --create-excel --account-regions us-east-1
```

The optimized discovery system is enabled by default and requires no additional configuration.

## Next Steps

- Read the [Complete CLI User Guide](../user-guides/cli-user-guide)
- Check out [Configuration Examples](../user-guides/configuration-examples)
- Learn about [Production Safety](../user-guides/production-safety)
- See [Troubleshooting Guide](../user-guides/troubleshooting-guide)
- Explore [Optimized Discovery System](../architecture/optimized-discovery-system)

## Need Help?

- Use `./inventag.sh --help` for command-line help
- Enable `--debug` for detailed logging
- Check the [documentation](/) for comprehensive guides
