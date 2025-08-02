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

### CLI Architecture

The CLI is built on three core components:

1. **`main.py`**: Primary CLI interface with argument parsing and orchestration
2. **`config_validator.py`**: Comprehensive validation framework for all configuration types
3. **`logging_setup.py`**: Advanced logging system with account-specific context

## Installation

The InvenTag CLI is included with the InvenTag package. Run it using:

```bash
python -m inventag.cli.main [options]
```

Or create an alias for convenience:

```bash
alias inventag="python -m inventag.cli.main"
inventag [options]
```

## Quick Start

### Single Account BOM Generation

Generate a BOM for your default AWS account:

```bash
# Generate Excel BOM using default AWS credentials
python -m inventag.cli.main --create-excel

# Generate both Word and Excel BOM with verbose logging
python -m inventag.cli.main --create-word --create-excel --verbose

# Generate BOM with custom output directory
python -m inventag.cli.main --create-excel --output-directory my-bom-reports
```

### Multi-Account BOM Generation

#### Using Configuration File

Create an accounts configuration file (JSON or YAML):

```bash
# Generate BOM for multiple accounts from configuration file
python -m inventag.cli.main --accounts-file accounts.json --create-excel --create-word

# With S3 upload for CI/CD integration
python -m inventag.cli.main --accounts-file accounts.yaml --create-excel --s3-bucket my-reports-bucket
```

#### Interactive Account Setup

```bash
# Interactively configure multiple accounts
python -m inventag.cli.main --accounts-prompt --create-excel --verbose
```

#### Cross-Account Role Assumption

```bash
# Use cross-account role for multi-account scanning
python -m inventag.cli.main --cross-account-role InvenTagRole --create-excel
```

### State Management and Change Tracking

```bash
# Enable state tracking for change detection
python -m inventag.cli.main --accounts-file accounts.json --create-excel \
  --enable-state-tracking --state-dir inventory_states

# Generate changelog from state changes
python -m inventag.cli.main --accounts-file accounts.json --create-excel \
  --enable-state-tracking --generate-changelog --changelog-format markdown

# State management with custom retention
python -m inventag.cli.main --create-excel --enable-state-tracking \
  --state-retention-days 90 --max-state-snapshots 50
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

### State Management Options

| Option | Description | Example |
|--------|-------------|---------|
| `--enable-state-tracking` | Enable state management and change tracking | `--enable-state-tracking` |
| `--state-dir` | Directory for storing state snapshots | `--state-dir inventory_states` |
| `--generate-changelog` | Generate changelog from state changes | `--generate-changelog` |
| `--changelog-format` | Changelog format (markdown, html, json) | `--changelog-format markdown` |
| `--state-retention-days` | Days to retain state snapshots | `--state-retention-days 90` |
| `--max-state-snapshots` | Maximum number of state snapshots to keep | `--max-state-snapshots 50` |
| `--create-excel` | Generate comprehensive Excel workbook BOM | `--create-excel` |
| `--create-google-docs` | Generate Google Docs/Sheets BOM | `--create-google-docs` |

### S3 Upload Options (CI/CD Integration)

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--s3-bucket` | S3 bucket name for uploading documents | None | `--s3-bucket my-reports-bucket` |
| `--s3-key-prefix` | S3 key prefix for organizing documents | `bom-reports/` | `--s3-key-prefix reports/2024/` |
| `--s3-encryption` | S3 server-side encryption method | `AES256` | `--s3-encryption aws:kms` |
| `--s3-kms-key-id` | KMS key ID for S3 encryption | None | `--s3-kms-key-id alias/my-key` |

### Account-Specific Configuration Overrides

| Option | Description | Example |
|--------|-------------|---------|
| `--account-regions` | Comma-separated list of AWS regions | `--account-regions us-east-1,us-west-2` |
| `--account-services` | Comma-separated list of AWS services | `--account-services EC2,S3,RDS` |
| `--account-tags` | JSON string of tag filters | `--account-tags '{"Environment":"prod"}'` |

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
python -m inventag.cli.main --create-excel --verbose

# With custom service descriptions
python -m inventag.cli.main --create-excel --service-descriptions my-services.yaml --verbose

# Debug mode with detailed logging
python -m inventag.cli.main --create-excel --debug --log-file debug.log
```

### Production Environment

```bash
# Multi-account production BOM with S3 upload
python -m inventag.cli.main \
  --accounts-file prod-accounts.json \
  --create-excel --create-word \
  --s3-bucket company-compliance-reports \
  --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
  --verbose

# With state management and change tracking
python -m inventag.cli.main \
  --accounts-file accounts.json \
  --create-excel \
  --enable-state-management \
  --enable-delta-detection \
  --generate-changelog \
  --verbose
```

### CI/CD Integration

```bash
# Automated BOM generation in CI/CD pipeline
python -m inventag.cli.main \
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
python -m inventag.cli.main \
  --accounts-file accounts.json \
  --validate-credentials \
  --verbose

# Validate configuration files
python -m inventag.cli.main \
  --accounts-file accounts.json \
  --service-descriptions services.yaml \
  --tag-mappings tags.yaml \
  --validate-config
```

### Compliance-BOM Integration

The CLI integrates tag compliance checking with BOM generation for comprehensive governance reporting:

```bash
# Generate BOM with integrated compliance checking
python -m inventag.cli.main \
  --create-excel --create-word \
  --tag-mappings config/tag_policy.yaml \
  --service-descriptions config/service_descriptions.yaml \
  --enable-compliance-analysis \
  --output-directory compliance_reports

# Multi-account compliance BOM generation
python -m inventag.cli.main \
  --accounts-file accounts.json \
  --create-excel \
  --tag-mappings config/tag_policy.yaml \
  --enable-compliance-analysis \
  --s3-bucket compliance-reports \
  --s3-key-prefix daily-compliance/$(date +%Y-%m-%d)/

# Compliance-focused reporting with thresholds
python -m inventag.cli.main \
  --create-excel \
  --tag-mappings config/tag_policy.yaml \
  --enable-compliance-analysis \
  --compliance-threshold 80 \
  --fail-on-low-compliance \
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
   python -m inventag.cli.main --accounts-file accounts.json --validate-credentials
   ```

2. **Configuration File Errors**
   ```bash
   # Validate configuration
   python -m inventag.cli.main --accounts-file accounts.json --validate-config
   ```

3. **AWS API Rate Limiting**
   ```bash
   # Reduce concurrent processing
   python -m inventag.cli.main --max-concurrent-accounts 2 --account-processing-timeout 3600
   ```

4. **Large Account Processing**
   ```bash
   # Increase timeout and enable detailed logging
   python -m inventag.cli.main --account-processing-timeout 7200 --debug --log-file debug.log
   ```

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
python -m inventag.cli.main --debug --log-file inventag-debug.log --create-excel
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

## Migration from Legacy Scripts

The unified CLI interface replaces the legacy script-based approach. Here's how to migrate:

### Script Migration Guide

| Legacy Script | New CLI Command | Notes |
|---------------|-----------------|-------|
| `python scripts/aws_resource_inventory.py --export-excel` | `python -m inventag.cli.main --create-excel` | Unified interface with multi-account support |
| `python scripts/tag_compliance_checker.py --config tags.yaml` | `python -m inventag.cli.main --create-excel --tag-mappings tags.yaml --enable-compliance-analysis` | Integrated compliance checking with BOM generation |
| `python scripts/bom_converter.py --input data.json --output report.xlsx` | `python -m inventag.cli.main --create-excel` | Direct Excel generation |
| `python scripts/cicd_bom_generation.py --accounts-file accounts.json` | `python -m inventag.cli.main --accounts-file accounts.json --create-excel` | Enhanced CI/CD integration |

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