---
title: CLI User Guide
description: Every InvenTag CLI flag, what it does today, and usage examples
sidebar_position: 1
---

# InvenTag CLI User Guide

## Overview

The `inventag` CLI (`./inventag.sh`, `inventag.bat` or `python3 inventag_cli.py`)
discovers resources in one or more AWS accounts and writes a bill of materials
(BOM) as Excel and/or Word. `./inventag.sh --help` is the authoritative list of
flags; this page explains them.

:::warning Flags that stop with an error
These flags are not implemented: `--create-google-docs`,
`--per-account-reports`, `--compliance-standard`, `--risk-threshold` and
`--disable-production-safety`. If you use one of them, the CLI stops with exit
code `2`. See [Current status and known limitations](../getting-started/status.md).
:::

### What it does

- **Several accounts** in parallel (`--accounts-file`, `--accounts-prompt`, `--cross-account-role`)
- **Excel and Word** reports (`--create-excel`, `--create-word`)
- **Your own columns and descriptions** (`--tag-mappings`, `--service-descriptions`)
- **Change tracking** between runs (on by default)
- **Upload to Amazon S3** with server-side encryption (`--s3-bucket`)
- **Read-only guard** on each AWS API call (always on), with an audit file (`--audit-output`)
- **Validation** of credentials and config files (`--validate-credentials`, `--validate-config`)
- **Logging** per account, to the console or a file (`--verbose`, `--log-file`)

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
  --account-regions us-east-1,us-west-2,ap-southeast-1,ap-northeast-1

# Asia-Pacific regions only
./inventag.sh --create-excel \
  --account-regions ap-southeast-1,ap-southeast-2,ap-northeast-1,ap-south-1

# US regions with comprehensive analysis
./inventag.sh --create-excel \
  --account-regions us-east-1,us-east-2,us-west-1,us-west-2 \
  --enable-network-analysis --enable-security-analysis

# European regions
./inventag.sh --create-excel \
  --account-regions eu-west-1,eu-west-2,eu-central-1

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
      "regions": ["ap-southeast-1", "ap-northeast-1", "ap-south-1"]
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

# With cost analysis
./inventag.sh --accounts-file accounts.json --create-excel \
  --enable-network-analysis --enable-security-analysis \
  --enable-cost-analysis
```

#### Interactive Account Setup

```bash
# Interactively configure multiple accounts
./inventag.sh --accounts-prompt --create-excel --verbose
```

#### Cross-Account Role Assumption

```bash
# Assume one role. Give the full role ARN.
./inventag.sh --cross-account-role arn:aws:iam::123456789012:role/InvenTagRole --create-excel

# Assume the same role name in each account of the accounts file
./inventag.sh --accounts-file accounts.json --cross-account-role InvenTagRole --create-excel

# Write an audit of each AWS API call
./inventag.sh --cross-account-role arn:aws:iam::123456789012:role/InvenTagRole --create-excel \
  --audit-output security-audit.json
```

If you give a role name without `--accounts-file`, the CLI stops with exit
code `2`.

### State Management and Change Tracking

```bash
# Enable state tracking for change detection
./inventag.sh --accounts-file accounts.json --create-excel \
  --enable-state-management --output-directory inventory_states

# Snapshots, change detection and the changelog are on by default
./inventag.sh --accounts-file accounts.json --create-excel

# Keep the snapshots, but write no changelog file
./inventag.sh --accounts-file accounts.json --create-excel --no-generate-changelog
```

## Command Line Options

### Account Configuration

| Option | Description | Example |
|--------|-------------|---------|
| `--accounts-file` | Path to accounts configuration file (JSON/YAML) | `--accounts-file accounts.json` |
| `--accounts-prompt` | Interactively prompt for account credentials | `--accounts-prompt` |
| `--cross-account-role` | Role to assume. Give a full role ARN, or give a role name together with `--accounts-file`. With a role name, the CLI makes one role ARN for each account ID in the file. | `--cross-account-role arn:aws:iam::123456789012:role/InvenTagRole` |

### Output Format Options

| Option | Description | Example |
|--------|-------------|---------|
| `--create-word` | Word document BOM (`multi_account_bom_<timestamp>.docx`) | `--create-word` |
| `--create-excel` | Excel workbook BOM (`multi_account_bom_<timestamp>.xlsx`); the default if no format is given | `--create-excel` |
| `--create-google-docs` | **Not implemented.** The CLI stops with exit code `2`. | n/a |

### Analysis Options

| Option | Description | Example |
|--------|-------------|---------|
| `--enable-network-analysis` | Sets the network analysis option. In an offline test run, this flag added no sheets or columns to the report. | `--enable-network-analysis` |
| `--enable-security-analysis` | Sets the security analysis option. In an offline test run, this flag added no sheets or columns to the report. | `--enable-security-analysis` |
| `--enable-cost-analysis` | Starts the cost analyzer. The cost analyzer makes its own Cost Explorer requests, also with `--no-billing-validation`. | `--enable-cost-analysis` |
| `--fallback-display` | Control fallback resource display: `auto` (recommended), `always`, `never` | `--fallback-display=auto` |
| `--hide-fallback-resources` | Legacy option: equivalent to `--fallback-display=never` (deprecated) | `--hide-fallback-resources` |

### State Management Options

| Option | Description | Example |
|--------|-------------|---------|
| `--enable-state-management` / `--disable-state-management` | Snapshots are on by default and stored in `<output-directory>/state/` (kept 30 days) | `--disable-state-management` |
| `--enable-delta-detection` / `--disable-delta-detection` | Compare with the previous snapshot (on by default) | `--disable-delta-detection` |
| `--generate-changelog` / `--no-generate-changelog` | Changelog of detected changes, written to `<output-directory>/changelog_<timestamp>.md`. On by default. Use `--no-generate-changelog` to write no changelog. | `--no-generate-changelog` |

Earlier versions of this page listed `--enable-state-tracking`, `--state-dir`,
`--changelog-format`, `--state-retention-days` and `--max-state-snapshots`.
Those flags do not exist.

### S3 Upload Options (CI/CD Integration)

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--s3-bucket` | Uploads each generated report to this bucket with server-side encryption. The upload uses the default AWS credentials and needs `s3:PutObject`. If an upload fails, the run stops with exit code `1`. | None | `--s3-bucket my-reports-bucket` |
| `--s3-key-prefix` | Key prefix. The object key is `<prefix>/<UTC timestamp>/<file name>`. | `bom-reports/` | `--s3-key-prefix reports/2026/` |
| `--s3-encryption` | Server-side encryption method: `AES256` or `aws:kms` | `AES256` | `--s3-encryption aws:kms` |
| `--s3-kms-key-id` | KMS key for `aws:kms`. If you give no key, Amazon S3 uses the AWS managed key. | None | `--s3-kms-key-id alias/my-key` |

The CLI refuses public ACLs and does not change the bucket lifecycle
configuration.

### Account-Specific Configuration Overrides

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--account-regions` | Comma-separated list of AWS regions to scan (overrides account-specific settings) | All enabled regions | `--account-regions us-east-1,us-west-2,ap-southeast-1,ap-northeast-1` |
| `--account-services` | Comma-separated list of services to keep in the report. The CLI compares each name with the `Service` column. The comparison ignores case, spaces, and the prefixes `Amazon` and `AWS`. | All services | `--account-services EC2,S3,RDS,Lambda` |
| `--account-tags` | JSON object of tag filters. The report keeps a resource only if it has each tag with the given value. | None | `--account-tags '{"Environment":"prod","Team":"platform"}'` |
| `--billing-validation` / `--no-billing-validation` | Cost Explorer lookups during discovery. On by default: two `GetCostAndUsage` requests for each account in each run. AWS bills each request. With `--no-billing-validation`, discovery makes no Cost Explorer request. | On | `--no-billing-validation` |

The service filter and the tag filter apply to the final resource list. The
CLI continues to make most discovery API calls, thus a filter does not make a
run much faster.

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
| `--validate-config` | Validate the configuration files and exit. This flag also examines the AWS credentials unless you add `--skip-credential-validation`. | `--validate-config` |
| `--validate-config-only` | Validate only the files that you give on the command line, then exit | `--validate-config-only` |

### Output and State Management

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--output-directory` | Directory for output files | `bom_output` | `--output-directory reports` |
| `--enable-state-management` | Enable state management | True | `--enable-state-management` |
| `--disable-state-management` | Disable state management | False | `--disable-state-management` |
| `--enable-delta-detection` | Enable delta detection | True | `--enable-delta-detection` |
| `--disable-delta-detection` | Disable delta detection | False | `--disable-delta-detection` |
| `--generate-changelog` / `--no-generate-changelog` | Write a changelog of detected changes | True | `--no-generate-changelog` |
| `--per-account-reports` | **Not implemented.** The CLI stops with exit code `2`. | n/a | n/a |

### Logging and Debug Options

| Option | Description | Example |
|--------|-------------|---------|
| `--verbose`, `-v` | Enable verbose logging (INFO level) | `--verbose` |
| `--debug`, `-d` | DEBUG logging, which includes the AWS SDK. InvenTag replaces secret keys, session tokens and signatures with `***REDACTED***`. The log continues to show account IDs, ARNs, resource names and API responses. Do not publish it. | `--debug` |
| `--log-file` | Path to log file | `--log-file inventag.log` |
| `--disable-account-logging` | Disable account-specific logging | `--disable-account-logging` |

### Credential Validation

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--validate-credentials` | Validate credentials and exit | False | `--validate-credentials` |
| `--credential-timeout` | Credential validation timeout (seconds) | 30 | `--credential-timeout 60` |
| `--skip-credential-validation` | Do not examine the default AWS credentials before the run | False | `--skip-credential-validation` |

### Production Safety and Security Options

The read-only guard is always on. The guard blocks each AWS API operation
that is not a read operation before the request goes to AWS. For the rules of
the guard, see [Permissions and production safety](./production-safety.md).

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--enforce-read-only` | Accepted for compatibility. The guard is always on. | Always on | n/a |
| `--enable-production-safety` | Accepted for compatibility. This flag has no effect. | Always on | n/a |
| `--security-validation` | Accepted for compatibility. This flag has no effect. | Always on | n/a |
| `--audit-output` | Write a JSON audit of each AWS API operation that the run called. The file shows the call count of each operation and each blocked call. | None | `--audit-output security-audit.json` |
| `--validate-operations` | Compare `service:Operation` names with the rules of the guard, then exit. Exit code `0` if the guard allows all names, `1` if not. This flag makes no AWS call. | None | `--validate-operations ec2:DescribeInstances s3:PutObject` |
| `--disable-production-safety` | **Not supported.** The CLI stops with exit code `2`. | n/a | n/a |
| `--compliance-standard` | **Not implemented.** The CLI stops with exit code `2`. | n/a | n/a |
| `--risk-threshold` | **Not implemented.** The CLI stops with exit code `2`. | n/a | n/a |

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
  --verbose

# With an audit of each AWS API call
./inventag.sh \
  --accounts-file accounts.json \
  --create-excel \
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

InvenTag replaces secret keys, session tokens and signatures in the log with
`***REDACTED***`. The log continues to show account IDs, ARNs, resource names
and API responses. Do not publish a debug log.

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
3. **Service Filtering**: A service filter makes the report smaller. It does not make the run much faster.
4. **Timeout Configuration**: Set appropriate timeouts
5. **Optimized Discovery**: The CLI automatically uses the enhanced discovery system to speed up discovery

#### Optimized Discovery System

InvenTag includes an optimized discovery system that provides significant performance improvements:

- **Faster discovery**: Parallel processing and service-specific patterns
- **Enhanced Service Coverage**: Better detection of CloudFront, IAM, Route53, S3, and Lambda resources
- **Intelligent Field Mapping**: Service-specific extraction patterns for better accuracy

The optimized discovery is enabled by default and requires no additional configuration. For maximum performance:

```bash
# Use parallel processing with optimized discovery
./inventag.sh --create-excel --max-concurrent-accounts 6

# Keep only these services in the report
./inventag.sh --create-excel --account-services EC2,S3,RDS,Lambda

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
| 0 | Success. Also the result of `--validate-operations` if the guard allows all names. |
| 1 | Error: configuration file not valid, credentials not valid, processing failure, or S3 upload failure. Also the result of `--validate-operations` if the guard blocks a name. |
| 2 | Usage error: a flag that is not implemented, a `--cross-account-role` value that is not valid, or an unknown argument. |

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
./inventag.sh --create-excel --fallback-display=auto
```
- Shows fallback resources **only** when no primary resources are found for a service
- Perfect for debugging missing resources and discovering services like AWS RoboMaker
- Provides optimal balance between coverage and clean output

**Always Mode (Maximum Visibility)**
```bash
./inventag.sh --create-excel --fallback-display=always  
```
- Shows all fallback resources for comprehensive auditing
- Best for compliance scenarios requiring proof of complete discovery
- May show duplicate entries for validation

**Never Mode (Primary Only)**
```bash
./inventag.sh --create-excel --fallback-display=never
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
./inventag.sh --create-excel --fallback-display=auto --verbose
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
7. **Production Safety**: monitoring and compliance features

### Backward Compatibility

Legacy scripts are still available but marked as deprecated. They will be maintained for backward compatibility but new features will only be added to the unified CLI.
