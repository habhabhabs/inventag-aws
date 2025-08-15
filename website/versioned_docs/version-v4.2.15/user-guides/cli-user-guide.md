---
title: CLI User Guide
description: Comprehensive CLI reference and usage examples for InvenTag
sidebar_position: 1
---

# InvenTag CLI User Guide

## Overview

The InvenTag CLI provides a comprehensive command-line interface for AWS cloud governance, BOM (Bill of Materials) generation, compliance checking, and advanced reporting across single or multiple AWS accounts. The unified CLI interface (`inventag.cli.main`) replaces the legacy script-based approach with a modern, feature-rich command-line tool.

### Key Features

- **🏢 Multi-Account Support**: Process multiple AWS accounts concurrently with flexible credential management
- **📊 Multiple Output Formats**: Generate Excel, Word, and Google Docs reports with professional branding
- **🚀 CI/CD Integration**: Built-in S3 upload, configuration validation, and credential management
- **⚡ Parallel Processing**: Configurable concurrent account processing with timeout management
- **🔧 Advanced Configuration**: Support for service descriptions, tag mappings, and BOM processing configs
- **📝 Comprehensive Logging**: Account-specific logging with debug capabilities and file output
- **✅ Validation Framework**: Built-in validation for credentials, configurations, and CLI arguments
- **🔄 State Management**: Integrated state tracking, delta detection, and change analysis with professional changelog generation
- **🛡️ Production Safety**: Enterprise-grade security validation and compliance standards
- **🌐 Advanced Analysis**: Network security analysis, cost optimization, and security posture assessment
- **🔐 Security Features**: Read-only enforcement, audit logging, and risk assessment capabilities

### CLI Architecture

The CLI is built on three core components:

1. **`main.py`**: Primary CLI interface with argument parsing and orchestration
2. **`config_validator.py`**: Comprehensive validation framework for all configuration types
3. **`logging_setup.py`**: Advanced logging system with account-specific context

## Installation

The InvenTag CLI is included with the InvenTag package. Run it using:

```bash
# On Unix/Linux/macOS
./inventag.sh [options]

# On Windows
inventag.bat [options]

# Or directly with Python
python inventag_cli.py [options]
```

For convenience, you can add the script to your PATH or create an alias:

```bash
# Unix/Linux/macOS
alias inventag="./inventag.sh"
inventag [options]

# Windows
doskey inventag=inventag.bat $*
inventag [options]
```

## Quick Start

### Single Account BOM Generation

Generate a BOM for your default AWS account:

```bash
# Generate Excel BOM using default AWS credentials
./inventag.sh --create-excel

# Generate both Word and Excel BOM with verbose logging
./inventag.sh --create-word --create-excel --verbose

# Generate BOM with custom output directory
./inventag.sh --create-excel --output-directory my-bom-reports
```

### Multi-Region Configuration

#### Region Selection Examples

**Default Behavior:** If no regions are specified in account configuration or CLI arguments, InvenTag scans all available AWS regions for comprehensive coverage.

```bash
# Scan specific regions across all accounts
./inventag.sh --create-excel \
  --account-regions us-east-1,us-west-2,ap-southeast-1,ap-north-1

# Asia-Pacific regions only
./inventag.sh --create-excel \
  --account-regions ap-southeast-1,ap-southeast-2,ap-north-1,ap-south-1

# US regions with comprehensive analysis
./inventag.sh --create-excel \
  --account-regions us-east-1,us-east-2,us-west-1,us-west-2 \
  --enable-network-analysis --enable-security-analysis

# European regions with GDPR compliance
./inventag.sh --create-excel \
  --account-regions eu-west-1,eu-west-2,eu-central-1 \
  --compliance-standard gdpr

# Global multi-region scan (default behavior - all regions)
./inventag.sh --create-excel --verbose

# Mixed regional strategy with cost optimization
./inventag.sh --create-excel \
  --account-regions us-east-1,ap-southeast-1,eu-west-1 \
  --enable-cost-analysis --enable-network-analysis
```

#### Region Configuration in Account Files

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

#### Common AWS Regions Reference

**US Regions:**
- `us-east-1` (N. Virginia)
- `us-east-2` (Ohio)
- `us-west-1` (N. California)
- `us-west-2` (Oregon)

**Asia Pacific:**
- `ap-southeast-1` (Singapore)
- `ap-southeast-2` (Sydney)
- `ap-north-1` (Mumbai)
- `ap-south-1` (Mumbai)
- `ap-northeast-1` (Tokyo)
- `ap-northeast-2` (Seoul)

**Europe:**
- `eu-west-1` (Ireland)
- `eu-west-2` (London)
- `eu-central-1` (Frankfurt)
- `eu-north-1` (Stockholm)

**Other Regions:**
- `ca-central-1` (Canada Central)
- `sa-east-1` (São Paulo)
- `af-south-1` (Cape Town)
- `me-south-1` (Bahrain)

### Multi-Account BOM Generation

#### Using Configuration File

Create an accounts configuration file (JSON or YAML):

```bash
# Generate BOM for multiple accounts from configuration file
./inventag.sh --accounts-file accounts.json --create-excel --create-word

# With S3 upload for CI/CD integration
./inventag.sh --accounts-file accounts.yaml --create-excel --s3-bucket my-reports-bucket

# With comprehensive analysis and security validation
./inventag.sh --accounts-file accounts.json --create-excel \
  --enable-network-analysis --enable-security-analysis \
  --enable-cost-analysis --compliance-standard soc2
```

#### Interactive Account Setup

```bash
# Interactively configure multiple accounts
./inventag.sh --accounts-prompt --create-excel --verbose

# Interactive setup with Google Docs output
./inventag.sh --accounts-prompt --create-google-docs --create-excel
```

#### Cross-Account Role Assumption

```bash
# Use cross-account role for multi-account scanning
./inventag.sh --cross-account-role InvenTagRole --create-excel

# Cross-account with production safety and audit logging
./inventag.sh --cross-account-role InvenTagRole --create-excel \
  --enable-production-safety --audit-output security-audit.json
```

### State Management and Change Tracking

```bash
# Enable state tracking for change detection
./inventag.sh --accounts-file accounts.json --create-excel \
  --enable-state-management --output-directory inventory_states

# Generate changelog from state changes
./inventag.sh --accounts-file accounts.json --create-excel \
  --enable-state-management --generate-changelog

# State management with custom retention
./inventag.sh --create-excel --enable-state-management \
  --enable-delta-detection --generate-changelog
```

## Command Line Options

### Account Configuration

| Option | Description | Example |
|--------|-------------|---------|
| `--accounts-file` | Path to accounts configuration file (JSON/YAML) | `--accounts-file accounts.json` |
| `--accounts-prompt` | Interactively prompt for account credentials | `--accounts-prompt` |
| `--cross-account-role` | Cross-account role name for multi-account scanning | `--cross-account-role InvenTagRole` |

### Output Format Options

| Option | Description | Example |
|--------|-------------|---------|
| `--create-word` | Generate professional Word document BOM | `--create-word` |
| `--create-excel` | Generate professional Excel workbook BOM | `--create-excel` |
| `--create-google-docs` | Generate Google Docs/Sheets BOM | `--create-google-docs` |

### Analysis Options

| Option | Description | Example |
|--------|-------------|---------|
| `--enable-network-analysis` | Enable network analysis for VPC, subnets, and network security | `--enable-network-analysis` |
| `--enable-security-analysis` | Enable security analysis for security groups, NACLs, and security posture | `--enable-security-analysis` |
| `--enable-cost-analysis` | Enable cost analysis and optimization recommendations | `--enable-cost-analysis` |
| `--fallback-display` | Control fallback resource display: `auto` (recommended), `always`, `never` | `--fallback-display=auto` |
| `--hide-fallback-resources` | Legacy option: equivalent to `--fallback-display=never` (deprecated) | `--hide-fallback-resources` |

### State Management Options

| Option | Description | Example |
|--------|-------------|---------|
| `--enable-state-tracking` | Enable state management and change tracking | `--enable-state-tracking` |
| `--state-dir` | Directory for storing state snapshots | `--state-dir inventory_states` |
| `--generate-changelog` | Generate changelog from state changes | `--generate-changelog` |
| `--changelog-format` | Changelog format (markdown, html, json) | `--changelog-format markdown` |
| `--state-retention-days` | Days to retain state snapshots | `--state-retention-days 90` |
| `--max-state-snapshots` | Maximum number of state snapshots to keep | `--max-state-snapshots 50` |

### S3 Upload Options (CI/CD Integration)

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--s3-bucket` | S3 bucket name for uploading documents | None | `--s3-bucket my-reports-bucket` |
| `--s3-key-prefix` | S3 key prefix for organizing documents | `bom-reports/` | `--s3-key-prefix reports/2024/` |
| `--s3-encryption` | S3 server-side encryption method | `AES256` | `--s3-encryption aws:kms` |
| `--s3-kms-key-id` | KMS key ID for S3 encryption | None | `--s3-kms-key-id alias/my-key` |

### Account-Specific Configuration Overrides

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--account-regions` | Comma-separated list of AWS regions to scan (overrides account-specific settings) | All available regions | `--account-regions us-east-1,us-west-2,ap-southeast-1,ap-north-1` |
| `--account-services` | Comma-separated list of AWS services to include (empty means all services) | All services | `--account-services EC2,S3,RDS,Lambda` |
| `--account-tags` | JSON string of tag filters to apply across all accounts | None | `--account-tags '{"Environment":"prod","Team":"platform"}'` |

### Parallel Processing Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--max-concurrent-accounts` | Maximum concurrent account processing | 4 | `--max-concurrent-accounts 8` |
| `--account-processing-timeout` | Timeout per account (seconds) | 1800 | `--account-processing-timeout 3600` |
| `--disable-parallel-processing` | Process accounts sequentially | False | `--disable-parallel-processing` |

### Configuration Files

| Option | Description | Example |
|--------|-------------|---------|
| `--service-descriptions` | Path to service descriptions config | `--service-descriptions services.yaml` |
| `--tag-mappings` | Path to tag mappings config | `--tag-mappings tags.yaml` |
| `--bom-config` | Path to BOM processing config | `--bom-config bom.yaml` |
| `--validate-config` | Validate configuration files and exit | `--validate-config` |

### Output and State Management

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--output-directory` | Directory for output files | `bom_output` | `--output-directory reports` |
| `--enable-state-management` | Enable state management | True | `--enable-state-management` |
| `--disable-state-management` | Disable state management | False | `--disable-state-management` |
| `--enable-delta-detection` | Enable delta detection | True | `--enable-delta-detection` |
| `--disable-delta-detection` | Disable delta detection | False | `--disable-delta-detection` |
| `--generate-changelog` | Generate changelog | True | `--generate-changelog` |
| `--per-account-reports` | Generate per-account reports | False | `--per-account-reports` |

### Logging and Debug Options

| Option | Description | Example |
|--------|-------------|---------|
| `--verbose`, `-v` | Enable verbose logging (INFO level) | `--verbose` |
| `--debug`, `-d` | Enable debug logging (DEBUG level) | `--debug` |
| `--log-file` | Path to log file | `--log-file inventag.log` |
| `--disable-account-logging` | Disable account-specific logging | `--disable-account-logging` |

### Credential Validation

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--validate-credentials` | Validate credentials and exit | False | `--validate-credentials` |
| `--credential-timeout` | Credential validation timeout (seconds) | 30 | `--credential-timeout 60` |

### Production Safety and Security Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--enable-production-safety` | Enable production safety monitoring and validation | True | `--enable-production-safety` |
| `--disable-production-safety` | Disable production safety monitoring (not recommended for production use) | False | `--disable-production-safety` |
| `--enforce-read-only` | Enforce read-only operations only for security | True | `--enforce-read-only` |
| `--security-validation` | Enable security validation for all AWS operations | True | `--security-validation` |
| `--compliance-standard` | Compliance standard to enforce (general, soc2, pci, hipaa, gdpr) | general | `--compliance-standard soc2` |
| `--risk-threshold` | Risk threshold for operation blocking (LOW, MEDIUM, HIGH, CRITICAL) | MEDIUM | `--risk-threshold HIGH` |
| `--audit-output` | Path to security audit report output file | None | `--audit-output security-audit.json` |
| `--validate-operations` | Validate specific AWS operations (format: service:operation) | None | `--validate-operations ec2:describe_instances s3:list_buckets` |

## Configuration Files

### Accounts Configuration

The accounts configuration file defines multiple AWS accounts and their credentials. It supports both JSON and YAML formats.

#### JSON Format

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production Account",
      "profile_name": "prod-profile",
      "regions": ["us-east-1", "us-west-2"],
      "services": ["EC2", "S3", "RDS"],
      "tags": {
        "Environment": "production"
      }
    },
    {
      "account_id": "123456789013",
      "account_name": "Development Account",
      "access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
      "regions": ["us-east-1"],
      "services": [],
      "tags": {}
    }
  ],
  "settings": {
    "max_concurrent_accounts": 4,
    "account_processing_timeout": 1800,
    "output_directory": "multi_account_bom"
  }
}
```

#### YAML Format

```yaml
accounts:
  - account_id: "123456789012"
    account_name: "Production Account"
    profile_name: "prod-profile"
    regions:
      - "us-east-1"
      - "us-west-2"
    services:
      - "EC2"
      - "S3"
      - "RDS"
    tags:
      Environment: "production"

  - account_id: "123456789013"
    account_name: "Development Account"
    access_key_id: "AKIAIOSFODNN7EXAMPLE"
    secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    regions:
      - "us-east-1"
    services: []
    tags: {}

settings:
  max_concurrent_accounts: 4
  account_processing_timeout: 1800
  output_directory: "multi_account_bom"
```

### Service Descriptions Configuration

Customize service descriptions in BOM documents:

```yaml
EC2:
  default_description: "Amazon Elastic Compute Cloud - Virtual servers in the cloud"
  resource_types:
    Instance: "Virtual machine instances providing scalable compute capacity"
    Volume: "Block storage volumes attached to EC2 instances"
    SecurityGroup: "Virtual firewall controlling traffic to instances"

S3:
  default_description: "Amazon Simple Storage Service - Object storage service"
  resource_types:
    Bucket: "Container for objects stored in Amazon S3"
```

### Tag Mappings Configuration

Define custom tag attribute mappings:

```yaml
"inventag:remarks":
  column_name: "Remarks"
  default_value: ""
  description: "Additional remarks about the resource"

"inventag:costcenter":
  column_name: "Cost Center"
  default_value: "Unknown"
  description: "Cost center responsible for the resource"

"inventag:owner":
  column_name: "Resource Owner"
  default_value: "Unassigned"
  description: "Person or team responsible for the resource"
```

## Common Usage Patterns

### Local Development

```bash
# Quick BOM generation for development
./inventag.sh --create-excel --verbose

# With custom service descriptions
./inventag.sh --create-excel --service-descriptions my-services.yaml --verbose

# Debug mode with detailed logging
./inventag.sh --create-excel --debug --log-file debug.log
```

### Production Environment

```bash
# Multi-account production BOM with S3 upload and comprehensive analysis
./inventag.sh \
  --accounts-file prod-accounts.json \
  --create-excel --create-word \
  --enable-network-analysis --enable-security-analysis \
  --enable-cost-analysis \
  --s3-bucket company-compliance-reports \
  --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
  --compliance-standard soc2 \
  --verbose

# With state management, change tracking, and security validation
./inventag.sh \
  --accounts-file accounts.json \
  --create-excel \
  --enable-state-management \
  --enable-delta-detection \
  --generate-changelog \
  --security-validation \
  --audit-output security-audit.json \
  --verbose
```

### CI/CD Integration

```bash
# Automated BOM generation in CI/CD pipeline
./inventag.sh \
  --accounts-file $ACCOUNTS_CONFIG \
  --create-excel \
  --s3-bucket $REPORTS_BUCKET \
  --s3-key-prefix bom-reports/$BUILD_NUMBER/ \
  --max-concurrent-accounts 8 \
  --account-processing-timeout 3600 \
  --log-file inventag-cicd.log
```

### Credential Validation

```bash
# Validate all account credentials before processing
./inventag.sh \
  --accounts-file accounts.json \
  --validate-credentials \
  --verbose

# Validate configuration files
./inventag.sh \
  --accounts-file accounts.json \
  --service-descriptions services.yaml \
  --tag-mappings tags.yaml \
  --validate-config
```

### Compliance-BOM Integration

The CLI integrates tag compliance checking with BOM generation for comprehensive governance reporting:

```bash
# Generate BOM with integrated compliance checking
./inventag.sh \
  --create-excel --create-word \
  --tag-mappings examples/tag-mappings-example.yaml \
  --service-descriptions examples/service-descriptions-example.yaml \
  --output-directory compliance_reports

# Multi-account compliance BOM generation with analysis
./inventag.sh \
  --accounts-file examples/accounts-example.json \
  --create-excel \
  --enable-network-analysis --enable-security-analysis \
  --tag-mappings examples/tag-mappings-example.yaml \
  --s3-bucket compliance-reports \
  --s3-key-prefix daily-compliance/$(date +%Y-%m-%d)/

# Comprehensive analysis with cost optimization
./inventag.sh \
  --create-excel \
  --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
  --tag-mappings examples/tag-mappings-example.yaml \
  --compliance-standard soc2 \
  --verbose
```

**Key Features:**
- **Integrated Workflow**: Seamless transition from compliance checking to BOM generation
- **Professional Reports**: Excel and Word documents with compliance status and metrics
- **Threshold Enforcement**: Configurable compliance thresholds for CI/CD gates
- **Multi-Format Output**: Compliance data included in all BOM formats
- **Detailed Analysis**: Resource-level compliance status with missing tag information

## Error Handling and Troubleshooting

### Common Issues

1. **Invalid Credentials**
   ```bash
   # Validate credentials first
   ./inventag.sh --accounts-file accounts.json --validate-credentials
   ```

2. **Configuration File Errors**
   ```bash
   # Validate configuration
   ./inventag.sh --accounts-file accounts.json --validate-config
   ```

3. **AWS API Rate Limiting**
   ```bash
   # Reduce concurrent processing
   ./inventag.sh --max-concurrent-accounts 2 --account-processing-timeout 3600
   ```

4. **Large Account Processing**
   ```bash
   # Increase timeout and enable detailed logging
   ./inventag.sh --account-processing-timeout 7200 --debug --log-file debug.log
   ```

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
./inventag.sh --debug --log-file inventag-debug.log --create-excel
```

This will provide:
- Detailed AWS API call logging
- Account-specific processing information
- Configuration validation details
- Error stack traces

### Log File Analysis

Log files contain structured information:
- Account-specific prefixes: `[AccountName]`
- Timestamp information
- Processing stages and timing
- Error details and stack traces

## Best Practices

### Security

1. **Use IAM Roles**: Prefer cross-account roles over access keys
2. **Least Privilege**: Grant only necessary permissions
3. **Credential Rotation**: Regularly rotate access keys
4. **Secure Storage**: Store credentials securely, never in code

### Performance

1. **Parallel Processing**: Use appropriate concurrency levels
2. **Region Filtering**: Limit to necessary regions
3. **Service Filtering**: Specify only required services
4. **Timeout Configuration**: Set appropriate timeouts
5. **Optimized Discovery**: The CLI automatically uses the enhanced discovery system for 3-4x performance improvement

#### Optimized Discovery System

InvenTag includes an optimized discovery system that provides significant performance improvements:

- **3-4x Faster Discovery**: Parallel processing and service-specific patterns
- **Enhanced Service Coverage**: Better detection of CloudFront, IAM, Route53, S3, and Lambda resources
- **Higher Quality Results**: 98% of resources achieve high confidence scores (≥0.7)
- **Intelligent Field Mapping**: Service-specific extraction patterns for better accuracy

The optimized discovery is enabled by default and requires no additional configuration. For maximum performance:

```bash
# Use parallel processing with optimized discovery
./inventag.sh --create-excel --max-concurrent-accounts 6

# Focus on specific services for faster processing
./inventag.sh --create-excel --service-filters ec2,s3,rds,lambda

# Single region for fastest discovery
./inventag.sh --create-excel --account-regions us-east-1
```

### Reliability

1. **Credential Validation**: Always validate before processing
2. **Configuration Validation**: Validate config files
3. **Error Handling**: Monitor logs for errors
4. **State Management**: Enable for change tracking

### CI/CD Integration

1. **Environment Variables**: Use for sensitive configuration
2. **Artifact Storage**: Upload to S3 for persistence
3. **Notification Integration**: Configure alerts
4. **Monitoring**: Track processing metrics

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error (invalid arguments, configuration errors, processing failures) |

## Support

For additional help:
1. Use `--help` for command-line help
2. Enable `--debug` for detailed logging
3. Check configuration with `--validate-config`
4. Validate credentials with `--validate-credentials`

## Advanced Features

### Intelligent Fallback Resource Discovery

InvenTag AWS uses a sophisticated dual-tier discovery system to ensure comprehensive AWS resource detection:

#### Discovery Modes

**Auto Mode (Recommended Default)**
```bash
inventag-aws --fallback-display=auto
```
- Shows fallback resources **only** when no primary resources are found for a service
- Perfect for debugging missing resources and discovering services like AWS RoboMaker
- Provides optimal balance between coverage and clean output

**Always Mode (Maximum Visibility)**
```bash
inventag-aws --fallback-display=always  
```
- Shows all fallback resources for comprehensive auditing
- Best for compliance scenarios requiring proof of complete discovery
- May show duplicate entries for validation

**Never Mode (Primary Only)**
```bash
inventag-aws --fallback-display=never
```
- Only shows resources discovered via direct service APIs
- Cleanest output with no duplicates
- May miss resources not discoverable via service APIs

#### When Fallback Resources Appear

**Services with Primary Resources Found**:
- EC2, S3, RDS, Lambda (fallback hidden in auto mode)

**Services Relying on Fallback Discovery**:
- AWS RoboMaker: Simulation jobs, applications
- AWS AppStream: Fleets, stacks, images
- AWS WorkSpaces: Workspaces, directories

**Debug Example**:
```bash
# See which services have primary vs fallback resources
inventag-aws --fallback-display=auto --verbose
```

For complete technical details, see: [Advanced Fallback Mechanism Guide](../advanced/fallback-mechanism.md)

## Migration from Legacy Scripts

The unified CLI interface replaces the legacy script-based approach. Here's how to migrate:

### Script Migration Guide

| Legacy Script | New CLI Command | Notes |
|---------------|-----------------|-------|
| `python scripts/aws_resource_inventory.py --export-excel` | `./inventag.sh --create-excel` | Unified interface with multi-account support |
| `python scripts/tag_compliance_checker.py --config tags.yaml` | `./inventag.sh --create-excel --tag-mappings tags.yaml` | Integrated compliance checking with BOM generation |
| `python scripts/bom_converter.py --input data.json --output report.xlsx` | `./inventag.sh --create-excel` | Direct Excel generation |
| `python scripts/cicd_bom_generation.py --accounts-file accounts.json` | `./inventag.sh --accounts-file accounts.json --create-excel` | Enhanced CI/CD integration |

### Key Advantages of the Unified CLI

1. **Simplified Interface**: Single command for all operations
2. **Multi-Account Support**: Built-in support for multiple AWS accounts
3. **Advanced Configuration**: Comprehensive validation and configuration management
4. **Better Error Handling**: Enhanced error reporting and debugging
5. **CI/CD Integration**: Native S3 upload and pipeline integration
6. **State Management**: Built-in change tracking and delta detection
7. **Production Safety**: Enterprise-grade monitoring and compliance features

### Backward Compatibility

Legacy scripts are still available but marked as deprecated. They will be maintained for backward compatibility but new features will only be added to the unified CLI.
