# InvenTag Examples

This directory contains comprehensive examples and templates for using InvenTag in various environments and scenarios.

## Quick Start

### 1. Basic Setup

Run the quick start script to get up and running quickly:

```bash
# Run the complete setup
./examples/quick_start.sh

# Or run with specific options
./examples/quick_start.sh --skip-deps --skip-validate
```

### 2. Manual Setup

If you prefer manual setup:

```bash
# Install dependencies
pip install -r requirements.txt

# Generate BOM with default settings
python inventag_cli.py --create-excel --verbose

# Generate BOM with custom configuration
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --service-descriptions config/service_descriptions_example.yaml \
  --tag-mappings config/tag_mappings_example.yaml \
  --create-excel --create-word
```

## Configuration Examples

### Account Configuration Files

| File | Description | Use Case |
|------|-------------|----------|
| `accounts_basic.json` | Single account with profile | Development/testing |
| `accounts_cli_example.json` | Multi-account with different credential types | Production multi-account |
| `accounts_cli_example.yaml` | Same as above in YAML format | YAML preference |
| `accounts_with_profiles.json` | Multiple accounts using AWS profiles | Profile-based authentication |
| `accounts_cross_account_roles.json` | Cross-account role assumption | Enterprise cross-account access |
| `accounts_flexible_credentials.json` | Mixed credential types | Complex environments |
| `accounts_local_with_credentials.json` | Local development with explicit keys | Local development |
| `accounts_github_secrets.json` | GitHub Actions integration | CI/CD with GitHub |
| `accounts_aws_secrets_manager.json` | AWS Secrets Manager integration | Secure credential storage |
| `accounts_cicd_environment.json` | CI/CD optimized configuration | Automated pipelines |

### Service and Tag Configuration

| File | Description |
|------|-------------|
| `config/service_descriptions_example.yaml` | Custom service descriptions |
| `config/tag_mappings_example.yaml` | Custom tag attribute mappings |
| `config/complete_configuration_example.yaml` | Comprehensive configuration example |

## CI/CD Integration Examples

### GitHub Actions

| File | Description |
|------|-------------|
| `github_actions_cicd_example.yml` | Complete GitHub Actions workflow |
| `github_actions_with_secrets.yml` | GitHub Actions with secrets management |

### AWS CodeBuild

| File | Description |
|------|-------------|
| `aws_codebuild_buildspec.yml` | CodeBuild buildspec with comprehensive features |
| `aws_codebuild_with_secrets_manager.yml` | CodeBuild with Secrets Manager integration |

### Jenkins

| File | Description |
|------|-------------|
| `jenkins_pipeline.groovy` | Jenkins declarative pipeline |

### Docker

| File | Description |
|------|-------------|
| `docker_compose_cicd.yml` | Docker Compose for CI/CD environments |

## Compliance-BOM Integration Examples

### Tag Compliance with BOM Generation

```bash
# Generate compliance BOM with tag policy validation
python -m inventag.cli.main \
  --create-excel --create-word \
  --tag-mappings config/tag_policy_example.yaml \
  --service-descriptions config/service_descriptions_example.yaml \
  --enable-compliance-analysis \
  --output-directory compliance_reports

# Multi-account compliance BOM
python -m inventag.cli.main \
  --accounts-file examples/accounts_cli_example.json \
  --create-excel \
  --tag-mappings config/tag_policy_example.yaml \
  --enable-compliance-analysis \
  --s3-bucket compliance-reports
```

### Programmatic Compliance-BOM Integration

```python
from inventag.compliance import ComprehensiveTagComplianceChecker

# Initialize checker with configuration
checker = ComprehensiveTagComplianceChecker(
    regions=['us-east-1', 'us-west-2'],
    config_file='config/tag_policy_example.yaml'
)

# Run compliance check
results = checker.check_compliance()
print(f"Compliance: {results['summary']['compliance_percentage']:.1f}%")

# Generate professional BOM documents
bom_results = checker.generate_bom_documents(
    output_formats=['excel', 'word'],
    output_directory='compliance_reports',
    enable_security_analysis=True,
    enable_network_analysis=True
)

print(f"Generated {len(bom_results['generated_files'])} BOM documents")
```

## Demo Scripts

### Basic Demos

| File | Description |
|------|-------------|
| `quick_start.sh` | Interactive setup and first BOM generation |
| `bom_processor_demo.py` | BOM processing demonstration |
| `service_description_demo.py` | Service description customization |
| `tag_mapping_demo.py` | Tag mapping configuration |
| `network_security_analysis_demo.py` | Network and security analysis |

### Advanced Demos

| File | Description |
|------|-------------|
| `state_manager_demo.py` | State management and delta detection |
| `delta_detector_demo.py` | Change tracking demonstration |
| `changelog_generator_demo.py` | Changelog generation |
| `service_enrichment_demo.py` | Service attribute enrichment |
| `cost_analysis_demo.py` | Cost analysis features |
| `production_safety_demo.py` | Production safety and monitoring |

## Usage Examples

### Single Account BOM Generation

```bash
# Basic Excel report
python inventag_cli.py --create-excel

# Excel and Word reports with verbose logging
python inventag_cli.py --create-excel --create-word --verbose

# With custom service descriptions
python inventag_cli.py \
  --create-excel \
  --service-descriptions examples/service_descriptions_custom.yaml \
  --verbose
```

### Multi-Account BOM Generation

```bash
# From configuration file
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --create-excel --create-word

# Interactive account setup
python inventag_cli.py --accounts-prompt --create-excel

# Cross-account role assumption
python inventag_cli.py \
  --cross-account-role InvenTagCrossAccountRole \
  --create-excel
```

### Advanced Features

```bash
# With state management and change tracking
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --create-excel \
  --enable-state-management \
  --enable-delta-detection \
  --generate-changelog

# With S3 upload for CI/CD
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --create-excel \
  --s3-bucket my-bom-reports \
  --s3-key-prefix reports/$(date +%Y-%m-%d)/

# High-performance multi-account processing
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --create-excel \
  --max-concurrent-accounts 8 \
  --account-processing-timeout 7200
```

### Configuration Validation

```bash
# Validate configuration files
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --service-descriptions config/service_descriptions_example.yaml \
  --tag-mappings config/tag_mappings_example.yaml \
  --validate-config

# Validate credentials
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --validate-credentials
```

### Debug and Troubleshooting

```bash
# Debug mode with detailed logging
python inventag_cli.py \
  --create-excel \
  --debug \
  --log-file inventag-debug.log

# Account-specific logging
python inventag_cli.py \
  --accounts-file examples/accounts_cli_example.json \
  --create-excel \
  --verbose

# Minimal test run
python inventag_cli.py \
  --create-excel \
  --account-regions us-east-1 \
  --account-services EC2,S3 \
  --debug
```

## Environment-Specific Examples

### Development Environment

```bash
# Quick development BOM
python inventag_cli.py \
  --create-excel \
  --account-regions us-east-1 \
  --disable-state-management \
  --verbose
```

### Staging Environment

```bash
# Staging with state management
python inventag_cli.py \
  --accounts-file examples/accounts_staging.json \
  --create-excel \
  --enable-state-management \
  --enable-delta-detection \
  --verbose
```

### Production Environment

```bash
# Production with full features
python inventag_cli.py \
  --accounts-file examples/accounts_production.json \
  --create-excel --create-word \
  --enable-state-management \
  --enable-delta-detection \
  --generate-changelog \
  --s3-bucket production-bom-reports \
  --max-concurrent-accounts 10 \
  --verbose
```

## CI/CD Pipeline Examples

### GitHub Actions

```yaml
# .github/workflows/inventag.yml
name: InvenTag BOM Generation
on:
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:

jobs:
  generate-bom:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - run: pip install -r requirements.txt
    - run: |
        python inventag_cli.py \
          --accounts-file examples/accounts_github_secrets.json \
          --create-excel \
          --s3-bucket ${{ secrets.BOM_BUCKET }} \
          --verbose
```

### AWS CodeBuild

```yaml
# buildspec.yml
version: 0.2
phases:
  install:
    runtime-versions:
      python: 3.9
    commands:
      - pip install -r requirements.txt
  build:
    commands:
      - python inventag_cli.py --accounts-file $ACCOUNTS_CONFIG --create-excel --s3-bucket $BOM_BUCKET
```

### Jenkins

```groovy
// Jenkinsfile
pipeline {
    agent any
    stages {
        stage('Generate BOM') {
            steps {
                sh '''
                    python inventag_cli.py \
                      --accounts-file examples/accounts_jenkins.json \
                      --create-excel \
                      --verbose
                '''
            }
        }
    }
}
```

## Monitoring and Alerting Examples

### Prometheus Metrics

```bash
# Export metrics to Prometheus
python inventag_cli.py \
  --create-excel \
  --enable-prometheus-metrics \
  --prometheus-pushgateway http://prometheus:9091
```

### CloudWatch Integration

```bash
# Export metrics to CloudWatch
python inventag_cli.py \
  --create-excel \
  --enable-cloudwatch-metrics \
  --cloudwatch-namespace "InvenTag/BOM"
```

### Slack Notifications

```bash
# With Slack notifications (configured via environment variables)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python inventag_cli.py \
  --create-excel \
  --enable-notifications \
  --verbose
```

## Best Practices Examples

### Security Best Practices

```bash
# Use IAM roles instead of access keys
python inventag_cli.py \
  --cross-account-role InvenTagRole \
  --create-excel

# Validate credentials before processing
python inventag_cli.py \
  --accounts-file accounts.json \
  --validate-credentials \
  --create-excel
```

### Performance Optimization

```bash
# Optimize for large environments
python inventag_cli.py \
  --accounts-file accounts.json \
  --max-concurrent-accounts 8 \
  --account-processing-timeout 7200 \
  --create-excel

# Filter for specific services and regions
python inventag_cli.py \
  --account-services EC2,S3,RDS,Lambda \
  --account-regions us-east-1,us-west-2 \
  --create-excel
```

### Reliability Patterns

```bash
# With retry and error handling
python inventag_cli.py \
  --accounts-file accounts.json \
  --create-excel \
  --account-processing-timeout 3600 \
  --verbose \
  --log-file production.log
```

## Testing Examples

### Unit Testing

```python
# test_inventag_cli.py
import unittest
from inventag.cli.main import create_parser, create_multi_account_config

class TestInvenTagCLI(unittest.TestCase):
    def test_parser_creation(self):
        parser = create_parser()
        self.assertIsNotNone(parser)
    
    def test_config_validation(self):
        # Test configuration validation
        pass
```

### Integration Testing

```bash
# Integration test script
#!/bin/bash
set -e

echo "Running integration tests..."

# Test configuration validation
python inventag_cli.py --accounts-file examples/accounts_basic.json --validate-config

# Test credential validation
python inventag_cli.py --accounts-file examples/accounts_basic.json --validate-credentials

# Test BOM generation
python inventag_cli.py --accounts-file examples/accounts_basic.json --create-excel --output-directory test_output

echo "Integration tests completed successfully"
```

## Troubleshooting Examples

### Common Issues

```bash
# Debug credential issues
python inventag_cli.py --validate-credentials --debug

# Debug configuration issues
python inventag_cli.py --validate-config --debug

# Debug with minimal scope
python inventag_cli.py \
  --create-excel \
  --account-regions us-east-1 \
  --account-services EC2 \
  --debug \
  --log-file debug.log
```

### Performance Issues

```bash
# Reduce concurrency for memory-constrained environments
python inventag_cli.py \
  --disable-parallel-processing \
  --account-processing-timeout 7200 \
  --create-excel

# Process accounts sequentially
python inventag_cli.py \
  --max-concurrent-accounts 1 \
  --create-excel
```

## Getting Help

For additional help and documentation:

1. **CLI Help**: `python inventag_cli.py --help`
2. **Configuration Validation**: `python inventag_cli.py --validate-config`
3. **Credential Testing**: `python inventag_cli.py --validate-credentials`
4. **Debug Mode**: `python inventag_cli.py --debug --log-file debug.log`
5. **Documentation**: Check the `docs/` directory for comprehensive guides

## Contributing

When adding new examples:

1. Follow the existing naming conventions
2. Include comprehensive comments
3. Test examples before committing
4. Update this README with new examples
5. Add appropriate error handling