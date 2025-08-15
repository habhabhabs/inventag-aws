---
title: Complete Readme Backup
---

# 🏷️ InvenTag

> **Python tool to check on AWS™ cloud inventory and tagging. Integrate into your CI/CD flow to meet your organization's stringent compliance requirements.**

[![Automated Release](https://github.com/habhabhabs/inventag-aws/workflows/Automated%20Release/badge.svg)](https://github.com/habhabhabs/inventag-aws/actions)
[![PR Checks](https://github.com/habhabhabs/inventag-aws/workflows/PR%20Checks/badge.svg)](https://github.com/habhabhabs/inventag-aws/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![AWS](https://img.shields.io/badge/AWS-Compatible-orange.svg)](https://aws.amazon.com/)
[![Version](https://img.shields.io/badge/dynamic/json?color=blue&label=version&query=version&url=https%3A//raw.githubusercontent.com/habhabhabs/inventag-aws/main/version.json)](https://github.com/habhabhabs/inventag-aws/releases/latest)

## 🎯 Overview

**InvenTag** is a comprehensive Python toolkit for AWS™ resource inventory management and tag compliance checking. Designed for enterprise environments, it automates the discovery, analysis, and reporting of AWS™ resources while ensuring adherence to organizational tagging policies.

> **Disclaimer**: AWS™ is a trademark of Amazon Web Services, Inc. InvenTag is an independent tool and is not affiliated with, endorsed by, or sponsored by Amazon Web Services, Inc.
>
> [AWS Trademark Guidelines & License Terms](https://aws.amazon.com/trademark-guidelines/)

### ✨ Key Features

- 🛡️ **Production Safety & Security** - Enterprise-grade security validation, read-only enforcement, and comprehensive audit logging
- 🔐 **Compliance Standards** - Built-in support for SOC 2, PCI, HIPAA, GDPR with automated compliance reporting
- 🔍 **Multi-Method Discovery** - Leverages ResourceGroupsTaggingAPI, AWSConfig, and service-specific APIs
- 📊 **Professional BOM Generation** - Creates detailed Excel/Word/CSV reports with service-specific sheets
- 🌐 **Network & Security Analysis** - Comprehensive VPC/subnet analysis with security posture assessment
- 💰 **Cost Analysis & Optimization** - Resource cost estimation, forgotten resource detection, and optimization recommendations
- 🎯 **Service-Specific Enrichment** - Deep attribute extraction for S3, RDS, EC2, Lambda, ECS, EKS and more
- 🏷️ **Tag Compliance Checking** - Validates resources against organizational tagging policies with integrated BOM generation
- 🔄 **State Management & Change Tracking** - Track changes over time with delta detection and professional changelog generation
- 🚀 **CI/CD Ready** - Easy integration into automated compliance workflows with S3 upload and GitHub Actions support
- 🧩 **Multi-Account Support** - Comprehensive multi-account scanning with cross-account role assumption
- 📋 **Template Framework** - Advanced document template system with variable substitution and professional branding
- 🔧 **Intelligent Data Enhancement** - Enriches resources with VPC names, account IDs, and inferred tags
- 📈 **Comprehensive Reporting** - Summary dashboards with compliance percentages and service breakdowns
- 🔗 **Integrated Compliance-BOM Workflow** - Seamless transition from compliance checking to professional BOM document generation
- 🧪 **Production-Grade Testing** - Full test coverage including dynamic service discovery, production safety, and template framework testing

## 🧪 Testing Framework

InvenTag includes a comprehensive test suite with full coverage of all major components:

### **Dynamic Service Discovery Testing**
- Pattern-based discovery validation for unknown AWS services
- Mock API response handling and error scenarios
- Caching system performance and optimization testing
- Read-only operation validation and security testing

### **Production Safety Testing**
- Enterprise-grade error handling and graceful degradation
- Circuit breaker pattern implementation testing
- Performance monitoring and metrics collection validation
- CloudTrail integration and audit trail testing

### **Template Framework Testing**
- Document template system with variable substitution
- Multi-format generation (Excel, Word, CSV) validation
- Professional branding and styling application testing
- Template loading and management system testing

### **Run Tests**
```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=inventag --cov-report=html

# Run specific test categories
python -m pytest tests/unit/test_dynamic_service_handler.py -v
python -m pytest tests/unit/test_production_monitor.py -v
python -m pytest tests/unit/test_template_framework_comprehensive.py -v
```

## 📁 Project Structure

```
inventag-aws/
├── README.md                    # This file - main documentation
├── requirements.txt             # Python dependencies
├── inventag/                    # Unified Python package
│   ├── __init__.py                    # Package initialization
│   ├── core/                          # Core orchestration module
│   │   ├── __init__.py                # Core module with state management integration
│   │   ├── cloud_bom_generator.py     # CloudBOMGenerator - multi-account orchestrator
│   │   ├── credential_manager.py      # CredentialManager - multi-account credential management
│   │   └── cicd_integration.py        # CICDIntegration - CI/CD pipeline integration
│   ├── discovery/                     # Resource discovery module
│   │   ├── __init__.py
│   │   ├── inventory.py               # AWSResourceInventory class
│   │   ├── service_enrichment.py      # Service attribute enrichment framework
│   │   ├── service_handlers.py        # Specific AWS service handlers
│   │   ├── service_descriptions.py    # Service description management framework
│   │   ├── tag_mapping.py             # Tag mapping and transformation utilities
│   │   ├── network_analyzer.py        # NetworkAnalyzer for VPC/subnet analysis
│   │   ├── security_analyzer.py       # SecurityAnalyzer for security posture
│   │   └── cost_analyzer.py           # CostAnalyzer for cost estimation and optimization
│   ├── compliance/                    # Tag compliance and security module
│   │   ├── __init__.py
│   │   ├── checker.py                 # ComprehensiveTagComplianceChecker with integrated BOM generation
│   │   ├── security_validator.py      # ReadOnlyAccessValidator - security validation and audit logging
│   │   ├── production_monitor.py      # ProductionSafetyMonitor - error handling and monitoring
│   │   └── compliance_manager.py      # ComplianceManager - unified compliance orchestration
│   ├── reporting/                     # BOM generation module
│   │   ├── __init__.py
│   │   ├── converter.py               # BOMConverter class
│   │   ├── bom_processor.py           # BOMDataProcessor - central orchestrator
│   │   ├── document_generator.py      # DocumentGenerator - multi-format document orchestration
│   │   ├── excel_builder.py           # ExcelWorkbookBuilder - Excel document generation
│   │   ├── word_builder.py            # WordDocumentBuilder - Word document generation
│   │   ├── csv_builder.py             # CSVBuilder - CSV document generation
│   │   ├── template_framework.py      # DocumentTemplate framework with variable substitution
│   │   ├── branding_system.py         # Advanced branding system with themes
│   │   ├── configuration_manager.py   # Configuration management framework
│   │   ├── excel_branding_applicator.py  # Excel-specific branding application
│   │   └── word_branding_applicator.py   # Word-specific branding application
│   └── state/                         # State management module
│       ├── __init__.py
│       ├── state_manager.py           # StateManager for persistence
│       ├── delta_detector.py          # DeltaDetector for change tracking
│       └── changelog_generator.py     # ChangelogGenerator for reports
├── inventag/                    # Unified Python package
│   ├── __init__.py                    # Package initialization
│   ├── cli/                           # Comprehensive CLI interface
│   │   ├── __init__.py                # CLI module initialization
│   │   ├── main.py                    # Main CLI entry point with multi-account support
│   │   ├── config_validator.py        # Configuration validation framework
│   │   └── logging_setup.py           # Advanced logging with account-specific context
├── scripts/                     # Legacy CLI wrapper scripts (deprecated)
│   ├── aws_resource_inventory.py      # Resource discovery CLI
│   ├── tag_compliance_checker.py      # Tag validation CLI
│   ├── bom_converter.py               # Excel/CSV generator CLI
│   └── README.md                      # Script documentation
├── config/                      # Configuration files
│   ├── iam-policy-read-only.json      # Required IAM permissions
│   ├── tag_policy_example.yaml        # Example tag policy
│   ├── tag_policy_example.json        # Example tag policy (JSON)
│   └── README.md                      # Config documentation
├── templates/                   # Document templates
│   ├── default_excel_template.json    # Professional Excel template with dashboards
│   └── default_word_template.yaml     # Professional Word template with branding
├── docs/                        # Detailed documentation
│   ├── BOM_DATA_PROCESSOR.md          # BOM Data Processor comprehensive guide
│   ├── CICD_INTEGRATION.md            # CI/CD integration and pipeline automation
│   ├── CORE_MODULE_INTEGRATION.md     # Core module integration with state management
│   ├── COST_ANALYSIS.md               # Cost analysis and optimization guide
│   ├── NETWORK_ANALYSIS.md            # Network analysis and capacity planning
│   ├── PRODUCTION_SAFETY.md           # Production safety and security validation guide
│   ├── SERVICE_ENRICHMENT.md          # Service enrichment framework and dynamic discovery
│   ├── SERVICE_DESCRIPTIONS.md        # Service description management
│   ├── STATE_MANAGEMENT.md            # State management and change tracking
│   ├── TAG_COMPLIANCE.md              # Tag compliance checking with integrated BOM generation
│   ├── TEMPLATE_FRAMEWORK.md          # Document template framework and customization
│   ├── SECURITY.md                    # Security guide & permissions
│   └── CREDENTIAL_SECURITY_GUIDE.md   # Comprehensive credential security guide
├── examples/                    # Examples and demo scripts
│   ├── quick_start.sh                 # Automated demo script
│   ├── state_manager_demo.py          # State management demo
│   ├── delta_detector_demo.py         # Change tracking demo
│   ├── changelog_generator_demo.py    # Changelog generation demo
│   ├── production_safety_demo.py      # Production safety and security validation demo
│   └── README.md                      # Usage examples
└── tests/                       # Comprehensive test suite
    ├── unit/                          # Unit tests for all modules
    │   ├── test_dynamic_service_handler.py    # Dynamic service discovery tests
    │   ├── test_template_framework_comprehensive.py  # Template system tests
    │   ├── test_document_generator_comprehensive.py  # Document generation tests
    │   ├── test_compliance_manager.py         # Compliance management tests
    │   ├── test_production_monitor.py         # Production safety tests
    │   └── test_security_validator.py         # Security validation tests
    ├── integration/                   # End-to-end workflow tests
    ├── backward_compatibility/        # Legacy compatibility tests
    └── README.md                      # Testing documentation
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure AWS Credentials
```bash
aws configure
# OR set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

### 3. Set Up Permissions
```bash
aws iam create-policy --policy-name AWSResourceInventoryReadOnly --policy-document file://config/iam-policy-read-only.json
aws iam attach-user-policy --user-name YOUR_USER --policy-arn arn:aws:iam::ACCOUNT:policy/AWSResourceInventoryReadOnly
```

### 4. Run the Demo
```bash
./examples/quick_start.sh
```

## 🚀 Core CLI Commands

### Basic BOM Generation
```bash
# Single account BOM with Excel and Word formats
python -m inventag.cli.main --create-excel --create-word

# BOM with comprehensive analysis enabled
python -m inventag.cli.main --create-excel --create-word \
  --enable-network-analysis --enable-security-analysis --enable-cost-analysis

# Multi-account BOM from configuration file
python -m inventag.cli.main --accounts-file examples/accounts_basic.json \
  --create-excel --create-word --verbose

# Interactive multi-account setup
python -m inventag.cli.main --accounts-prompt --create-excel --verbose
```

### 🛡️ Production Safety & Security Commands
```bash
# Production-safe BOM with security validation
python -m inventag.cli.main --create-excel \
  --enable-production-safety --security-validation \
  --enforce-read-only --risk-threshold HIGH

# SOC 2 compliance BOM with audit trail
python -m inventag.cli.main --create-excel \
  --compliance-standard soc2 --audit-output soc2-compliance.json

# Security validation for specific operations
python -m inventag.cli.main --create-excel \
  --validate-operations ec2:describe_instances s3:list_buckets iam:list_users

# Real-time production monitoring
python scripts/production_monitor.py \
  --operations ec2:describe_instances s3:list_buckets \
  --report-output production-monitor.json --verbose

# Security validation with audit report
python scripts/security_validator.py --validate-inventory \
  --enforce-read-only --risk-threshold HIGH \
  --audit-output security-validation.json
```

### 🌐 Multi-Account & Enterprise Commands
```bash
# Cross-account role assumption
python scripts/multi_account_scanner.py \
  --accounts-file examples/accounts_basic.json \
  --enable-security-analysis --enable-network-analysis \
  --output-format excel json --verbose

# Enterprise-scale multi-account BOM
python -m inventag.cli.main --accounts-file enterprise-accounts.json \
  --create-excel --create-word --enable-network-analysis \
  --enable-security-analysis --enable-cost-analysis \
  --max-concurrent-accounts 12 --per-account-reports

# CI/CD integration with S3 upload and security validation
python -m inventag.cli.main --accounts-file accounts.json \
  --create-excel --s3-bucket reports-bucket \
  --enable-production-safety --security-validation \
  --s3-key-prefix "secure-reports/$(date +%Y-%m-%d)/"
```

### 📊 Advanced Analysis Commands
```bash
# Comprehensive network and security analysis
python -m inventag.cli.main --create-excel \
  --enable-network-analysis --enable-security-analysis \
  --service-descriptions config/service_descriptions_example.yaml \
  --tag-mappings config/tag_mappings_example.yaml

# Cost optimization analysis
python -m inventag.cli.main --create-excel \
  --enable-cost-analysis --account-services ec2,rds,s3,lambda \
  --create-word --output-directory cost-optimization

# State management with change tracking
python -m inventag.cli.main --create-excel \
  --enable-state-management --enable-delta-detection \
  --generate-changelog --output-directory state-tracking
```

### 🔧 Debug & Troubleshooting Commands
```bash
# Debug mode with comprehensive logging
python -m inventag.cli.main --create-excel --debug \
  --log-file inventag-debug.log --verbose

# Credential validation before processing
python -m inventag.cli.main --validate-credentials \
  --accounts-file accounts.json --credential-timeout 60

# Configuration validation only
python -m inventag.cli.main --validate-config \
  --accounts-file accounts.json \
  --service-descriptions config/service_descriptions_example.yaml
```

> 📚 **For complete CLI documentation with all options and examples, see [CLI_USAGE_ENHANCED.md](/development/CLI_USAGE_ENHANCED)**

**Legacy script usage (deprecated):**
```bash
# Basic resource inventory
python scripts/aws_resource_inventory.py

# Tag compliance check
python scripts/tag_compliance_checker.py --config config/tag_policy_example.yaml

# Convert to Excel with service sheets
python scripts/bom_converter.py --input examples/basic_inventory_*.json --output examples/report.xlsx
```

## 🔄 CI/CD Integration & Automated Releases

### Automated Semantic Versioning

This repository uses **automated semantic versioning** with every merge to main:

- 🏷️ **Label your PRs** to control version bumps:
  - `release:patch` → v1.0.0 → v1.0.1 (bug fixes, minor updates)  
  - `release:minor` → v1.0.0 → v1.1.0 (new features, backwards compatible)
  - `release:major` → v1.0.0 → v2.0.0 (breaking changes)
- 🚀 **Automatic releases** created on every merge to main
- 📦 **Release assets** include source archives and comprehensive changelog
- ✅ **Quality gates** ensure tests pass before release

### CI/CD Integration Components

InvenTag now includes comprehensive CI/CD integration capabilities for automated BOM generation and compliance checking in your deployment pipelines.

#### **🚀 CICDIntegration Class**
Central orchestrator for pipeline integration with automated document generation, compliance gates, and notification systems.

```python
from inventag.core.cicd_integration import CICDIntegration, S3UploadConfig, ComplianceGateConfig

# Configure CI/CD integration
s3_config = S3UploadConfig(
    bucket_name="compliance-reports",
    key_prefix="inventag-bom",
    region="us-east-1",
    encryption="AES256",
    lifecycle_days=90
)

compliance_config = ComplianceGateConfig(
    minimum_compliance_percentage=80.0,
    critical_violations_threshold=0,
    required_tags=["Environment", "Owner"],
    fail_on_security_issues=True
)

# Initialize CI/CD integration
cicd = CICDIntegration(
    s3_config=s3_config,
    compliance_gate_config=compliance_config
)

# Execute pipeline integration
result = cicd.execute_pipeline_integration(
    bom_generator=generator,
    output_formats=["excel", "word", "json"],
    upload_to_s3=True,
    send_notifications=True,
    export_metrics=True
)

print(f"Pipeline success: {result.success}")
print(f"Compliance gate: {'PASSED' if result.compliance_gate_passed else 'FAILED'}")
print(f"Documents uploaded: {len(result.s3_uploads)}")
```

#### **📊 S3 Document Upload**
Automated upload of generated BOM documents to S3 with configurable storage options.

```python
from inventag.core.cicd_integration import S3UploadConfig

s3_config = S3UploadConfig(
    bucket_name="my-compliance-bucket",
    key_prefix="bom-reports",
    region="us-west-2",
    encryption="aws:kms",
    kms_key_id="arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012",
    public_read=False,
    lifecycle_days=30,
    storage_class="STANDARD_IA"
)
```

#### **🛡️ Compliance Gate Checking**
Automated compliance validation with configurable thresholds for pipeline control.

```python
from inventag.core.cicd_integration import ComplianceGateConfig

compliance_config = ComplianceGateConfig(
    minimum_compliance_percentage=85.0,
    critical_violations_threshold=0,
    required_tags=["Environment", "Owner", "CostCenter"],
    allowed_non_compliant_services=["CloudTrail"],
    fail_on_security_issues=True,
    fail_on_network_issues=False
)
```

#### **📢 Notification Integration**
Multi-channel notifications with Slack, Teams, and email support.

```python
from inventag.core.cicd_integration import NotificationConfig

notification_config = NotificationConfig(
    slack_webhook_url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    teams_webhook_url="https://outlook.office.com/webhook/YOUR/TEAMS/WEBHOOK",
    email_recipients=["compliance@company.com", "devops@company.com"],
    include_summary=True,
    include_document_links=True,
    notify_on_success=True,
    notify_on_failure=True
)
```

#### **📈 Prometheus Metrics Export**
Comprehensive metrics export for monitoring and alerting systems.

```python
# Metrics automatically exported include:
# - inventag_total_resources
# - inventag_compliant_resources  
# - inventag_compliance_percentage
# - inventag_processing_time_seconds
# - inventag_successful_accounts
# - inventag_security_issues
# - inventag_document_generation_time
# - inventag_s3_upload_time
```

### Contributing with Automated Releases

> **⚠️ IMPORTANT: This project strictly follows [Semantic Commit](https://www.conventionalcommits.org/) conventions. All commits must use semantic prefixes for automated versioning and release notes generation.**

1. **Create a feature branch with semantic commits:**
   ```bash
   git checkout -b feat/new-export-format
   
   # ✅ REQUIRED: Use semantic commit format
   git commit -m "feat: add JSON export format for compliance reports"
   
   # ❌ WRONG: Non-semantic commits will break automation
   git commit -m "added json stuff"
   ```

   **Semantic Commit Format:**
   ```
   <type>[optional scope]: <description>
   
   [optional body]
   
   [optional footer(s)]
   ```

   **Required Types:**
   - `feat:` - New features (triggers minor version bump)
   - `fix:` - Bug fixes (triggers patch version bump) 
   - `docs:` - Documentation changes
   - `style:` - Code style/formatting changes
   - `refactor:` - Code refactoring without feature changes
   - `test:` - Adding or updating tests
   - `chore:` - Maintenance tasks, dependency updates
   - `feat!:` or `fix!:` - Breaking changes (triggers major version bump)

2. **Create PR with appropriate release label:**
   ```bash
   # For new features (minor version bump)
   gh pr create --title "feat: add JSON export format" --label "release:minor"
   
   # For bug fixes (patch version bump - default)
   gh pr create --title "fix: resolve Excel formatting issue"
   
   # For breaking changes (major version bump)
   gh pr create --title "feat!: redesign CLI interface" --label "release:major"
   ```

3. **Merge to main** → Automatic release triggered! 🎉

### Manual Releases

**Via GitHub Actions UI:**
1. Go to Actions → "Automated Release"
2. Click "Run workflow" 
3. Select version bump type
4. Click "Run workflow"

**Via Command Line:**
```bash
# Trigger specific version bumps
gh workflow run "Automated Release" --field version_bump=patch
gh workflow run "Automated Release" --field version_bump=minor  
gh workflow run "Automated Release" --field version_bump=major
```

### CI/CD Pipeline Features

- ✅ **Automated Testing**: Python syntax, formatting, and functionality tests
- 🔍 **PR Validation**: Title format, description length, release labels
- 📝 **Semantic Commits (REQUIRED)**: Automated versioning and enhanced release notes from conventional commit messages
- 🏷️ **Breaking Change Detection**: Requires proper labeling for major releases
- 📊 **Release Analytics**: Track version history and change patterns
- 🚀 **CI/CD Integration**: Automated BOM generation with compliance gates
- 📊 **S3 Document Storage**: Automated upload with lifecycle management
- 📢 **Multi-Channel Notifications**: Slack, Teams, and email integration
- 📈 **Prometheus Metrics**: Comprehensive monitoring and alerting

### Integration Examples

**GitHub Actions Workflow with CI/CD Integration:**
```yaml
name: Multi-Account BOM Generation
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC
  workflow_dispatch:

jobs:
  generate-bom:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Generate Multi-Account BOM
      run: |
        python -c "
        from inventag.core.cloud_bom_generator import CloudBOMGenerator
        from inventag.core.cicd_integration import CICDIntegration, S3UploadConfig, ComplianceGateConfig, NotificationConfig
        
        # Configure CI/CD integration
        s3_config = S3UploadConfig(
            bucket_name='${{ secrets.S3_BUCKET }}',
            key_prefix='daily-bom-reports',
            region='us-east-1'
        )
        
        compliance_config = ComplianceGateConfig(
            minimum_compliance_percentage=80.0,
            fail_on_security_issues=True
        )
        
        notification_config = NotificationConfig(
            slack_webhook_url='${{ secrets.SLACK_WEBHOOK }}',
            notify_on_success=True,
            notify_on_failure=True
        )
        
        # Initialize and execute
        cicd = CICDIntegration(s3_config, compliance_config, notification_config)
        generator = CloudBOMGenerator.from_credentials_file('accounts.json')
        
        result = cicd.execute_pipeline_integration(
            bom_generator=generator,
            output_formats=['excel', 'word', 'json'],
            upload_to_s3=True,
            send_notifications=True,
            export_metrics=True
        )
        
        # Fail pipeline if compliance gate fails
        if not result.compliance_gate_passed:
            exit(1)
        "
      env:
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

**Compliance Gate Integration:**
```yaml
name: Compliance Gate Check
on: [push, pull_request]
jobs:
  compliance-gate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Run Compliance Gate
      run: |
        python -c "
        from inventag.core.cicd_integration import CICDIntegration, ComplianceGateConfig
        from inventag.core.cloud_bom_generator import CloudBOMGenerator
        
        # Configure strict compliance gate
        compliance_config = ComplianceGateConfig(
            minimum_compliance_percentage=90.0,
            critical_violations_threshold=0,
            required_tags=['Environment', 'Owner', 'CostCenter'],
            fail_on_security_issues=True,
            fail_on_network_issues=True
        )
        
        cicd = CICDIntegration(compliance_gate_config=compliance_config)
        generator = CloudBOMGenerator.from_credentials_file('accounts.json')
        
        result = cicd.execute_pipeline_integration(
            bom_generator=generator,
            upload_to_s3=False,
            send_notifications=False
        )
        
        print(f'Compliance Gate: {\"PASSED\" if result.compliance_gate_passed else \"FAILED\"}')
        
        # Fail build if compliance gate fails
        if not result.compliance_gate_passed:
            print('❌ Compliance gate failed - blocking deployment')
            exit(1)
        else:
            print('✅ Compliance gate passed - deployment approved')
        "
      env:
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### Version Management

**Current Version Tracking:**
- Version stored in `version.json` 
- Automatic updates on each release
- Semantic versioning (MAJOR.MINOR.PATCH)

**Release Documentation:**
- 📖 See [`RELEASE.md`](/development/RELEASE) for complete release management guide
- 🔗 [Latest Release](https://github.com/habhabhabs/inventag-aws/releases/latest)
- 📊 [All Releases](https://github.com/habhabhabs/inventag-aws/releases)

**Core Module Integration Documentation:**
- 🏗️ See [`docs/CORE_MODULE_INTEGRATION.md`](/development/docs/CORE_MODULE_INTEGRATION) for unified core module usage
- 🔄 Includes state management integration, change detection, and changelog generation
- 🚀 Enterprise CI/CD patterns with comprehensive state tracking
- 📊 Advanced credential management and multi-account orchestration

**CI/CD Integration Documentation:**
- 🚀 See [`docs/CICD_INTEGRATION.md`](/development/docs/CICD_INTEGRATION) for comprehensive CI/CD integration guide
- 📊 Includes S3 upload configuration, compliance gates, notifications, and monitoring
- 🔧 GitHub Actions and AWS CodeBuild integration examples
- 📈 Prometheus metrics and Grafana dashboard configurations

**Production Safety Documentation:**
- 🛡️ See [`docs/PRODUCTION_SAFETY.md`](/development/docs/PRODUCTION_SAFETY) for comprehensive production safety guide
- 🔐 Includes security validation, error handling, and compliance reporting
- 📋 SOC2, ISO27001 compliance framework support
- 🚨 Real-time monitoring, audit logging, and performance tracking

## 📋 Main Tools

### 🚀 **Unified CLI Interface** (`python -m inventag.cli.main`)
Comprehensive command-line interface for multi-account AWS cloud governance with BOM generation, compliance checking, and advanced reporting capabilities.

**Key Features:**
- 🏢 **Multi-Account Support**: Process multiple AWS accounts concurrently with flexible credential management
- 📊 **Multiple Output Formats**: Generate Excel, Word, and Google Docs reports with professional branding
- 🚀 **CI/CD Integration**: Built-in S3 upload, configuration validation, and credential management
- ⚡ **Parallel Processing**: Configurable concurrent account processing with timeout management
- 🔧 **Advanced Configuration**: Support for service descriptions, tag mappings, and BOM processing configs
- 📝 **Comprehensive Logging**: Account-specific logging with debug capabilities and file output
- ✅ **Validation Framework**: Built-in validation for credentials, configurations, and CLI arguments
- 🔄 **State Management**: Integrated state tracking, delta detection, and change analysis with professional changelog generation

**Usage Examples:**
```bash
# Single account BOM generation
python -m inventag.cli.main --create-excel --create-word

# Multi-account BOM from configuration file
python -m inventag.cli.main --accounts-file accounts.json --create-excel --s3-bucket reports-bucket

# Interactive multi-account setup
python -m inventag.cli.main --accounts-prompt --create-excel --verbose

# Cross-account role assumption
python -m inventag.cli.main --cross-account-role InvenTagRole --create-excel --account-regions us-east-1,us-west-2

# CI/CD integration with comprehensive options
python -m inventag.cli.main --accounts-file accounts.json --create-excel --create-word \
  --s3-bucket reports-bucket --s3-key-prefix bom-reports/ \
  --max-concurrent-accounts 8 --verbose

# State management and change tracking
python -m inventag.cli.main --accounts-file accounts.json --create-excel \
  --enable-state-tracking --state-dir inventory_states \
  --generate-changelog --changelog-format markdown
```

**CLI Architecture:**
The CLI is built on three core components:
- **`main.py`**: Primary CLI interface with argument parsing and orchestration
- **`config_validator.py`**: Comprehensive validation framework for all configuration types  
- **`logging_setup.py`**: Advanced logging system with account-specific context

**State Management Integration:**
The core module now includes direct access to state management components:
- **`StateManager`**: Persistent storage and versioning of inventory states
- **`DeltaDetector`**: Advanced change detection and analysis
- **`ChangelogGenerator`**: Professional change documentation and reporting

### 🔍 **Resource Inventory** (`scripts/aws_resource_inventory.py`) - *Legacy*
Discovers ALL AWS resources across your account with intelligent service enrichment.

```bash
# Discover all resources in all regions
python scripts/aws_resource_inventory.py

# Export to Excel automatically  
python scripts/aws_resource_inventory.py --export-excel

# Upload to S3
python scripts/aws_resource_inventory.py --s3-bucket my-reports-bucket
```

**Key Features:**
- 🎯 **Dynamic Service Discovery**: Automatically handles unknown AWS services using pattern-based API discovery
- 🔧 **Service-Specific Enrichment**: Deep attribute extraction for S3, RDS, EC2, Lambda, ECS, EKS and more
- 🧠 **Intelligent Pattern Matching**: Uses comprehensive operation and parameter patterns for unknown services
- 📊 **Caching System**: Optimized performance with pattern caching and failed operation tracking
- 🛡️ **Read-Only Validation**: All operations are validated as read-only before execution

**Dynamic Service Discovery:**
The `DynamicServiceHandler` provides intelligent pattern-based discovery for unknown AWS services:

```python
from inventag.discovery.service_enrichment import DynamicServiceHandler

# Initialize handler with AWS session
handler = DynamicServiceHandler(boto3.Session())

# Automatically discover and enrich unknown service resources
resource = {
    'service': 'TEXTRACT',
    'type': 'Document', 
    'id': 'document-123',
    'arn': 'arn:aws:textract:us-east-1:123456789012:document/document-123'
}

enriched_resource = handler.enrich_resource(resource)
print(f"Discovered attributes: {enriched_resource['service_attributes']}")

# Get cache statistics for performance monitoring
stats = handler.get_cache_statistics()
print(f"Cached results: {stats['cached_results']}, Failed patterns: {stats['failed_patterns']}")
```

**Pattern-Based Discovery Features:**
- 🔍 **Operation Pattern Generation**: Automatically generates `describe_*`, `get_*`, `list_*` patterns
- 📋 **Parameter Pattern Matching**: Tries multiple parameter combinations (`Name`, `Id`, `Arn`, etc.)
- 🚀 **Intelligent Caching**: Caches successful patterns and failed attempts to optimize performance
- 🛡️ **Read-Only Enforcement**: Only attempts operations validated as read-only
- 📊 **Response Data Extraction**: Intelligently extracts resource data from API responses

### 🏷️ **Tag Compliance** (`inventag.compliance.checker.ComprehensiveTagComplianceChecker`)
Validates ALL resources against your tagging policies with integrated BOM generation.

**State Management Integration:**
```python
from inventag.core import CloudBOMGenerator, StateManager, DeltaDetector, ChangelogGenerator

# Initialize BOM generator with state management
generator = CloudBOMGenerator.from_credentials_file('accounts.json')

# Initialize state management components
state_manager = StateManager(state_dir="inventory_states")
delta_detector = DeltaDetector()
changelog_generator = ChangelogGenerator()

# Generate BOM and save state
result = generator.generate_comprehensive_bom(
    output_formats=['excel', 'word'],
    enable_state_tracking=True
)

# Save current state for change tracking
state_id = state_manager.save_state(
    resources=result.all_resources,
    account_id="123456789012",
    regions=result.regions_processed,
    tags={"purpose": "monthly_audit", "environment": "production"}
)

# Compare with previous state for change detection
states = state_manager.list_states(limit=2)
if len(states) >= 2:
    comparison = state_manager.get_state_comparison_data(
        states[1]['state_id'], states[0]['state_id']
    )
    
    # Detect changes
    delta_report = delta_detector.detect_changes(
        old_resources=comparison['state1']['resources'],
        new_resources=comparison['state2']['resources'],
        state1_id=states[1]['state_id'],
        state2_id=states[0]['state_id']
    )
    
    # Generate professional changelog
    if delta_report.summary['total_changes'] > 0:
        changelog = changelog_generator.generate_changelog(
            delta_report=delta_report,
            format='markdown',
            include_details=True,
            include_executive_summary=True
        )
        changelog_generator.export_changelog(changelog, 'infrastructure_changes.md')
        print(f"Generated changelog with {delta_report.summary['total_changes']} changes")
```

**Unified Package Usage:**
```python
from inventag.compliance import ComprehensiveTagComplianceChecker

# Initialize checker with configuration
checker = ComprehensiveTagComplianceChecker(
    regions=['us-east-1', 'us-west-2'],
    config_file='config/tag_policy_example.yaml'
)

# Discover and check compliance
results = checker.check_compliance()
print(f"Compliance: {results['summary']['compliance_percentage']:.1f}%")

# Generate BOM documents directly from compliance results
bom_results = checker.generate_bom_documents(
    output_formats=['excel', 'word'],
    output_directory='compliance_reports',
    enable_security_analysis=True,
    enable_network_analysis=True
)

print(f"Generated {len(bom_results['generated_files'])} BOM documents:")
for file_path in bom_results['generated_files']:
    print(f"  - {file_path}")

# Save compliance results
checker.save_results('compliance_results.json')

# Upload to S3
checker.upload_to_s3('my-bucket', 'compliance/results.json')
```

**Legacy Script Usage (deprecated):**
```bash
# Check for untagged resources only
python scripts/tag_compliance_checker.py

# Use your tagging policy
python scripts/tag_compliance_checker.py --config config/tag_policy_example.yaml

# Get compliance report with S3 upload
python scripts/tag_compliance_checker.py --config my_policy.yaml --s3-bucket compliance-reports
```

### 📊 **BOM Converter** (`scripts/bom_converter.py`)
Converts JSON/YAML to professional Excel reports.

```bash
# Create Excel with service-specific sheets
python scripts/bom_converter.py --input inventory.json --output report.xlsx

# Create CSV with service column
python scripts/bom_converter.py --input inventory.json --output report.csv --format csv
```

### 📄 **Document Generation Framework**
Advanced multi-format document generation with professional templates and branding.

```python
from inventag.reporting.document_generator import DocumentGenerator, DocumentConfig, BrandingConfig
from inventag.reporting.template_framework import create_template_manager
from inventag.reporting.branding_system import create_branding_theme_manager

# Create template and branding managers
template_manager = create_template_manager("templates")
branding_manager = create_branding_theme_manager()

# Load professional template
template = template_manager.load_template("professional_word")

# Get predefined branding theme
branding_theme = branding_manager.get_theme("professional_blue")

# Configure document generation
config = DocumentConfig(
    output_formats=["excel", "word", "csv"],
    template=template,
    branding_theme=branding_theme,
    enable_parallel_generation=True,
    output_directory="reports"
)

# Generate professional documents
generator = DocumentGenerator(config)
summary = generator.generate_bom_documents(bom_data, ["excel", "word"])

print(f"Generated {summary.successful_formats} documents in {summary.total_generation_time:.2f}s")
```

**Key Features:**
- 🎨 **Professional Branding**: Company logos, color schemes, and custom styling with predefined themes
- 📊 **Multi-Format Support**: Excel, Word, CSV with format-specific optimizations
- ⚡ **Parallel Generation**: Concurrent document creation for better performance
- 🔧 **Advanced Template System**: Comprehensive template framework with variable substitution
- 📈 **Progress Tracking**: Detailed generation statistics and error reporting
- 🛡️ **Error Recovery**: Graceful handling of generation failures with partial results
- 🎯 **Template Variables**: Dynamic content with {{variable}} syntax and formatting
- 🏢 **Enterprise Themes**: Professional, corporate, modern, and high-contrast themes

### 📋 **Template Framework**
Comprehensive document template system with variable substitution and professional customization.

```python
from inventag.reporting.template_framework import create_template_manager

# Create template manager
template_manager = create_template_manager("templates")

# Load professional template
template = template_manager.load_template("professional_word")

# Create custom template with variables
template.variables = {
    "company_name": TemplateVariable(
        name="company_name",
        value="Acme Corporation",
        description="Company name",
        default_value="Organization"
    ),
    "document_title": TemplateVariable(
        name="document_title",
        value="Cloud Infrastructure BOM",
        description="Document title"
    )
}

# Resolve variables with formatting
resolver = TemplateVariableResolver()
variables = resolver.resolve_variables(template, {
    "classification": "CONFIDENTIAL"
})

# Apply variable substitution
formatted_text = resolver.substitute_text(
    "{{company_name}} - {{document_title}} ({{current_date|date:%B %Y}})",
    variables
)
```

**Template Features:**
- 📄 **Document Structure**: Hierarchical sections with table of contents
- 🔤 **Variable System**: Built-in and custom variables with type validation
- 🎨 **Header/Footer Templates**: Custom branding with logo placement
- 📊 **Multi-Format Templates**: YAML/JSON template definitions
- 🔧 **Template Management**: Caching, validation, and hot-reload
- 🎯 **Variable Formatting**: Date, number, and text formatting options

### 🚀 **CI/CD Integration**
Complete pipeline integration for automated compliance monitoring and BOM generation with comprehensive CLI script.

#### **Command-Line Interface**
The unified CLI (`python -m inventag.cli.main`) provides comprehensive CI/CD integration capabilities:

```bash
# Basic multi-account BOM generation
python -m inventag.cli.main \
  --accounts-file examples/accounts_basic.json \
  --create-excel --create-word

# Full CI/CD integration with S3 upload and monitoring
python -m inventag.cli.main \
  --accounts-file examples/accounts_cicd_environment.json \
  --create-excel --create-word \
  --s3-bucket my-compliance-bucket \
  --s3-key-prefix bom-reports/ \
  --max-concurrent-accounts 8 \
  --account-processing-timeout 3600 \
  --verbose

# Configuration and credential validation
python -m inventag.cli.main \
  --accounts-file examples/accounts_basic.json \
  --validate-config --validate-credentials \
  --verbose
```

**Legacy CI/CD Script (deprecated):**
```bash
# Basic multi-account BOM generation
python scripts/cicd_bom_generation.py \
  --accounts-file examples/accounts_basic.json \
  --formats excel word

# Full CI/CD integration with S3, notifications, and monitoring
python scripts/cicd_bom_generation.py \
  --accounts-file examples/accounts_cicd_environment.json \
  --formats excel word json \
  --s3-bucket my-compliance-bucket \
  --s3-key-prefix bom-reports \
  --compliance-threshold 80 \
  --fail-on-security-issues \
  --slack-webhook https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK \
  --prometheus-gateway http://prometheus-pushgateway:9091 \
  --verbose

# Dry run for configuration validation
python scripts/cicd_bom_generation.py \
  --accounts-file examples/accounts_basic.json \
  --formats excel \
  --dry-run \
  --verbose
```

#### **Programmatic Integration**
```python
from inventag.core.cicd_integration import CICDIntegration, S3UploadConfig, ComplianceGateConfig

# Configure CI/CD integration
s3_config = S3UploadConfig(
    bucket_name="compliance-reports",
    key_prefix="bom-reports",
    encryption="AES256",
    lifecycle_days=90
)

compliance_config = ComplianceGateConfig(
    minimum_compliance_percentage=80.0,
    fail_on_security_issues=True,
    required_tags=["Environment", "Owner"]
)

# Execute pipeline integration
cicd = CICDIntegration(s3_config=s3_config, compliance_gate_config=compliance_config)
result = cicd.execute_pipeline_integration(
    bom_generator=generator,
    output_formats=["excel", "word", "json"],
    upload_to_s3=True,
    send_notifications=True,
    export_metrics=True
)

# Check compliance gate
if not result.compliance_gate_passed:
    print("❌ Compliance gate failed - blocking deployment")
    exit(1)
```

**Key Features:**
- 🛡️ **Compliance Gates**: Configurable thresholds that can fail builds
- 📊 **S3 Document Storage**: Automated upload with lifecycle management
- 📢 **Multi-Channel Notifications**: Slack, Teams, and email integration
- 📈 **Prometheus Metrics**: Comprehensive monitoring and alerting
- 🔄 **Pipeline Artifacts**: JSON artifacts for downstream consumption
- 🏢 **Multi-Account Support**: Parallel processing across AWS accounts
- 🔧 **Environment Detection**: Automatic credential handling for GitHub Actions, AWS CodeBuild, Jenkins
- 🎯 **Flexible Configuration**: Support for environment variables and configuration files

#### **Environment Detection & Credential Management**
The CI/CD script automatically detects the execution environment and applies appropriate credential strategies:

- **GitHub Actions**: Uses GitHub Secrets with environment-specific variables (`AWS_ACCESS_KEY_ID_PROD`, `AWS_SECRET_ACCESS_KEY_STAGING`, etc.)
- **AWS CodeBuild**: Retrieves credentials from AWS Secrets Manager with configurable secret names
- **Jenkins**: Uses environment variables or Jenkins credential store
- **Local Development**: Falls back to AWS CLI profiles or global environment variables

```bash
# Environment-specific credential examples:

# GitHub Actions environment variables
AWS_ACCESS_KEY_ID_PROD=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY_PROD=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# AWS Secrets Manager secret names (CodeBuild)
INVENTAG_SECRET_PRODUCTION=inventag/credentials/production
INVENTAG_SECRET_STAGING=inventag/credentials/staging

# Global environment variables (local/generic CI)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

## 🔄 State Management & Change Tracking

InvenTag now includes powerful state management capabilities for tracking changes over time and generating comprehensive change reports.

### 📈 **State Manager**
Persistent storage and versioning of inventory states with comprehensive metadata tracking.

```python
from inventag.state import StateManager

# Initialize state manager
state_manager = StateManager(
    state_dir="inventory_states",
    retention_days=30,
    max_snapshots=10
)

# Save current state
state_id = state_manager.save_state(
    resources=discovered_resources,
    account_id="123456789012",
    regions=["us-east-1", "us-west-2"],
    discovery_method="comprehensive",
    compliance_data=compliance_results
)

# Load previous state for comparison
previous_state = state_manager.load_state(state_id)
```

### 🔍 **Delta Detection**
Advanced change detection with comprehensive analysis of resource modifications.

```python
from inventag.state import DeltaDetector

# Initialize delta detector
detector = DeltaDetector()

# Detect changes between states
delta_report = detector.detect_changes(
    old_resources=previous_resources,
    new_resources=current_resources,
    state1_id='20231201_120000',
    state2_id='20231201_130000'
)

# Analyze results
print(f"Added: {len(delta_report.added_resources)}")
print(f"Removed: {len(delta_report.removed_resources)}")
print(f"Modified: {len(delta_report.modified_resources)}")
```

### 📝 **Changelog Generation**
Professional change reports with detailed analysis and impact assessment.

```python
from inventag.state import ChangelogGenerator

# Generate comprehensive changelog
generator = ChangelogGenerator()
changelog = generator.generate_changelog(
    delta_report=delta_report,
    format='markdown',
    include_details=True
)

# Export changelog
generator.export_changelog(changelog, 'changes_report.md')
```

### 🎯 **Demo Scripts**
Explore the comprehensive capabilities with interactive demos:

```bash
# State management demonstration
python examples/state_manager_demo.py

# Change detection demonstration  
python examples/delta_detector_demo.py

# Changelog generation demonstration
python examples/changelog_generator_demo.py

# Service enrichment demonstration
python examples/service_enrichment_demo.py

# Service description management demonstration
python examples/service_description_demo.py

# Network analysis demonstration
python examples/network_security_analysis_demo.py

# Cost analysis demonstration
python examples/cost_analysis_demo.py

# Production safety and security validation demonstration
python examples/production_safety_demo.py
```

### 🔧 **Key State Management Features**

- **📊 Comprehensive Metadata**: Track discovery method, regions, compliance status, and custom tags
- **🔒 Data Integrity**: Checksum validation and state integrity verification
- **⏰ Retention Policies**: Configurable retention by age and count limits
- **📈 Change Analytics**: Detailed analysis of compliance, security, and network changes
- **🎯 Impact Assessment**: Identify high-impact changes and cascade risks
- **📋 Export Capabilities**: JSON, YAML, CSV export for CI/CD integration
- **🔍 Query Interface**: List, compare, and validate states programmatically

## 🛡️ Production Safety & Security Validation

InvenTag includes enterprise-grade production safety and security validation features designed for secure AWS operations with comprehensive audit trail generation.

### 🔐 **Security Validation Features**

#### **Read-Only Access Validation** - Comprehensive Operation Security
- **Operation Classification**: Automatic detection of read-only vs. mutating operations
- **Security Enforcement**: Blocks all non-read-only operations to ensure system integrity
- **Compliance Standards**: Built-in support for SOC2, ISO27001 compliance frameworks
- **Audit Trail Generation**: Detailed logging of all operations for compliance documentation
- **Risk Assessment**: Automatic risk level assessment for all AWS operations
- **Identity Validation**: AWS identity type detection and validation

#### **Production Safety Monitoring** - Enterprise-Grade Error Handling
- **Graceful Degradation**: Intelligent error handling with automatic recovery strategies
- **Circuit Breaker Pattern**: Prevents cascade failures with automatic service protection
- **Performance Monitoring**: Real-time CPU, memory, and disk utilization tracking
- **CloudTrail Integration**: Comprehensive audit trail visibility and event correlation
- **Error Categorization**: Severity-based error classification with user impact assessment
- **Threshold Monitoring**: Configurable alerting for error rates and performance metrics

### 🎯 **Compliance Management**

#### **Unified Compliance Orchestration**
```python
from inventag.compliance import ComplianceManager, ComplianceConfiguration, ComplianceStandard

# Configure comprehensive compliance management
config = ComplianceConfiguration(
    compliance_standard=ComplianceStandard.GENERAL,
    enable_security_validation=True,
    enable_production_monitoring=True,
    enable_cloudtrail_integration=True,
    error_threshold=10,
    performance_threshold_cpu=80.0
)

# Initialize compliance manager
manager = ComplianceManager(config)

# Validate and monitor operations
result = manager.validate_and_monitor_operation(
    service="ec2",
    operation="describe_instances",
    resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/*"
)

# Generate comprehensive compliance report
report = manager.generate_comprehensive_compliance_report()
print(f"Compliance Score: {report['executive_summary']['compliance_score']}")
```

#### **Security Validation**
```python
from inventag.compliance import ReadOnlyAccessValidator, ComplianceStandard

# Initialize security validator
validator = ReadOnlyAccessValidator(ComplianceStandard.GENERAL)

# Validate AWS operations
result = validator.validate_operation("ec2", "describe_instances")
print(f"Operation allowed: {result.is_valid}")
print(f"Risk level: {result.risk_level}")

# Generate compliance report
compliance_report = validator.generate_compliance_report()
print(f"Compliance score: {compliance_report.compliance_score}%")
```

#### **Production Monitoring**
```python
from inventag.compliance import ProductionSafetyMonitor

# Initialize production monitor
monitor = ProductionSafetyMonitor(
    enable_cloudtrail=True,
    enable_performance_monitoring=True,
    error_threshold=10
)

# Handle errors with graceful degradation
try:
    # Your AWS operation here
    pass
except Exception as e:
    error_context = monitor.handle_error(
        error=e,
        operation="describe_instances",
        service="ec2",
        resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
    )
    print(f"Error handled: {error_context.recovery_action}")

# Generate security validation report
security_report = monitor.generate_security_validation_report()
print(f"Risk score: {security_report.risk_score}/100")
```

### 🔧 **Key Security Features**

- **🛡️ Read-Only Enforcement**: Comprehensive validation ensures only safe operations are executed
- **📋 Audit Logging**: Detailed audit trails for all operations with compliance metadata
- **🚨 Error Handling**: Production-grade error handling with automatic recovery strategies
- **📊 Performance Monitoring**: Real-time system performance tracking and alerting
- **🔍 CloudTrail Integration**: Enhanced audit visibility with AWS CloudTrail event correlation
- **📈 Compliance Reporting**: Automated generation of compliance reports for various standards
- **🎯 Risk Assessment**: Automatic risk scoring and security finding generation
- **⚡ Circuit Breakers**: Automatic protection against cascade failures and service degradation

## 🌐 Network Analysis & Capacity Planning

InvenTag includes a comprehensive NetworkAnalyzer that provides deep VPC and subnet analysis for network visibility, capacity planning, and optimization recommendations.

### 🔧 **Network Analysis Features**

#### **VPC Analysis** - Comprehensive Virtual Private Cloud Assessment
- **CIDR Block Analysis**: Multi-CIDR support with total IP calculations
- **Utilization Metrics**: Real-time IP utilization across all subnets
- **Network Components**: Internet gateways, NAT gateways, VPC endpoints
- **Connectivity Mapping**: VPC peering and Transit Gateway attachments
- **Resource Association**: Automatic mapping of resources to VPCs

#### **Subnet Analysis** - Detailed Subnet Utilization and Planning
- **IP Utilization Tracking**: Available vs. used IP addresses with percentages
- **Availability Zone Distribution**: Multi-AZ subnet analysis
- **Public/Private Classification**: Route table analysis for subnet types
- **Capacity Planning**: Utilization thresholds and growth projections
- **Resource Mapping**: EC2, RDS, Lambda resource-to-subnet associations

#### **Network Optimization** - Intelligent Recommendations
- **Capacity Warnings**: High utilization alerts (configurable thresholds)
- **Underutilized Resources**: Identification of unused VPCs and subnets
- **Consolidation Opportunities**: Subnet optimization recommendations
- **Cost Optimization**: NAT gateway and VPC endpoint suggestions

### 🛠️ **Network Analysis Framework**

```python
from inventag.discovery.network_analyzer import NetworkAnalyzer

# Initialize network analyzer
analyzer = NetworkAnalyzer()

# Analyze VPC resources with comprehensive metrics
vpc_analysis = analyzer.analyze_vpc_resources(resources)

# Generate network capacity summary
network_summary = analyzer.generate_network_summary(vpc_analysis)

# Map resources to network context
enriched_resources = analyzer.map_resources_to_network(resources)

print(f"Total VPCs: {network_summary.total_vpcs}")
print(f"Total Available IPs: {network_summary.total_available_ips}")
print(f"Highest Utilization: {network_summary.highest_utilization_percentage:.1f}%")
```

### 🎯 **Network Analysis Use Cases**

#### **Capacity Planning**
```python
# Identify high-utilization subnets
for vpc_id, vpc in vpc_analysis.items():
    for subnet in vpc.subnets:
        if subnet.utilization_percentage > 80:
            print(f"WARNING: Subnet {subnet.subnet_name} is {subnet.utilization_percentage:.1f}% utilized")
```

#### **Cost Optimization**
```python
# Find unused VPCs for cost savings
unused_vpcs = [vpc for vpc in vpc_analysis.values() if not vpc.associated_resources]
print(f"Found {len(unused_vpcs)} unused VPCs that could be removed")
```

#### **Network Security Assessment**
```python
# Identify public subnets and their resources
for vpc in vpc_analysis.values():
    public_subnets = [s for s in vpc.subnets if s.is_public]
    if public_subnets:
        print(f"VPC {vpc.vpc_name} has {len(public_subnets)} public subnets")
```

## 📝 Service Description Management

InvenTag includes a comprehensive Service Description Management Framework that provides intelligent, customizable descriptions for AWS resources with template-based dynamic generation and configuration file support.

### 🔧 **Service Description Features**

#### **Dynamic Description Generation** - Template-Based Resource Descriptions
- **Template Engine**: Flexible template system with variable substitution
- **Fallback Mechanisms**: Intelligent fallback to default descriptions when templates fail
- **Attribute Mapping**: Automatic mapping of resource attributes to template variables
- **Nested Attribute Support**: Access nested resource attributes using dot notation
- **Service-Specific Templates**: Pre-built templates for major AWS services

#### **Configuration Management** - YAML/JSON Configuration Support
- **Schema Validation**: Comprehensive validation of configuration files
- **Hot Reloading**: Runtime configuration updates without restart
- **Template Registration**: Custom template registration and management
- **Service Hierarchies**: Service-level and resource-type-level descriptions
- **Metadata Tracking**: Track configuration sources and update timestamps

#### **Built-in Service Support** - Pre-configured AWS Service Descriptions
- **EC2**: Instances, volumes, security groups with detailed templates
- **S3**: Buckets with encryption and configuration details
- **RDS**: Database instances and clusters with engine information
- **Lambda**: Functions with runtime and memory specifications
- **VPC**: VPCs and subnets with network configuration details

### 🛠️ **Service Description Framework**

```python
from inventag.discovery.service_descriptions import ServiceDescriptionManager

# Initialize with configuration file
manager = ServiceDescriptionManager(config_path='config/service_descriptions.yaml')

# Apply descriptions to resources
enriched_resources = manager.apply_descriptions_to_resources(resources)

# Get dynamic descriptions with templates
for resource in resources:
    description = manager.get_dynamic_description(resource)
    print(f"{resource['id']}: {description}")

# Get configuration information
config_info = manager.get_configuration_info()
print(f"Loaded {config_info['total_custom_descriptions']} custom descriptions")
```

### 🎯 **Template System**

Create custom templates for dynamic description generation:

```yaml
# config/service_descriptions.yaml
service_descriptions:
  EC2:
    Instance:
      description: "Virtual machine instance providing compute capacity"
      template: "custom_ec2_instance"
    Volume:
      description: "Block storage volume for EC2 instances"
      template: "custom_ec2_volume"

templates:
  custom_ec2_instance:
    template: "EC2 Instance {resource_id} - {instance_type} in {availability_zone} ({state})"
    required_attributes:
      - "service_attributes.InstanceType"
      - "service_attributes.State.Name"
    optional_attributes:
      - "service_attributes.Placement.AvailabilityZone"
    fallback_template: "ec2_default"
  
  custom_ec2_volume:
    template: "EBS Volume {resource_id} - {size}GB {volume_type} ({state})"
    required_attributes:
      - "service_attributes.Size"
      - "service_attributes.VolumeType"
      - "service_attributes.State"
    fallback_template: "ec2_default"
```

### 🔄 **Advanced Template Features**

#### **Variable Mapping and Transformation**
```python
# Template variables are automatically mapped from resource attributes
# service_attributes.InstanceType -> instance_type
# service_attributes.Placement.AvailabilityZone -> availability_zone

# Example resource with service attributes:
resource = {
    'id': 'i-1234567890abcdef0',
    'service': 'EC2',
    'type': 'Instance',
    'service_attributes': {
        'InstanceType': 't3.micro',
        'State': {'Name': 'running'},
        'Placement': {'AvailabilityZone': 'us-east-1a'}
    }
}

# Results in description: "EC2 Instance i-1234567890abcdef0 - t3.micro in us-east-1a (running)"
```

#### **Fallback Strategy**
The system uses intelligent fallback mechanisms:
1. **Exact Match**: Service + resource type specific template
2. **Service Default**: Service-level default template
3. **Built-in Templates**: Pre-configured AWS service templates
4. **Generic Fallback**: Basic AWS service description

#### **Configuration Export**
```python
# Export configuration template for customization
manager.export_configuration_template(
    output_path='my_service_descriptions.yaml',
    format_type='yaml'
)
```

### 🎯 **Integration with Resource Discovery**

```python
from inventag.discovery.service_descriptions import ServiceDescriptionManager
from inventag.discovery.service_enrichment import ServiceAttributeEnricher

# Enrich resources with service attributes first
enricher = ServiceAttributeEnricher()
enriched_resources = enricher.enrich_resources_with_attributes(resources)

# Apply intelligent descriptions
desc_manager = ServiceDescriptionManager(config_path='config/descriptions.yaml')
final_resources = desc_manager.apply_descriptions_to_resources(enriched_resources)

# Each resource now has:
# - service_description: Human-readable description
# - description_metadata: Generation metadata and source tracking
```

## 🏢 Multi-Account Support & Credential Management

InvenTag provides comprehensive multi-account support for enterprise environments with centralized credential management and cross-account role assumption.

### 🔐 **Multi-Account Credential Management**

Secure credential management system for multiple AWS accounts with flexible authentication methods.

```python
from inventag.core.credential_manager import CredentialManager, AccountCredentials

# Create account credentials
accounts = [
    AccountCredentials(
        account_id="123456789012",
        account_name="Production Account",
        profile_name="prod-profile"
    ),
    AccountCredentials(
        account_id="123456789013", 
        account_name="Development Account",
        access_key_id="AKIATEST",
        secret_access_key="secret"
    ),
    AccountCredentials(
        account_id="123456789014",
        account_name="Staging Account",
        role_arn="arn:aws:iam::123456789014:role/InvenTagCrossAccountRole"
    )
]

# Initialize credential manager
credential_manager = CredentialManager()

# Create secure credential file
credential_manager.create_secure_credential_file(
    accounts=accounts,
    output_file="accounts.json",
    encrypt=True
)

# Interactive credential setup
accounts = credential_manager.interactive_credential_setup(
    save_to_file="accounts.yaml",
    encrypt_file=True
)
```

### 🌐 **Multi-Account BOM Generation**

Generate comprehensive BOMs across multiple AWS accounts with parallel processing.

```python
from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig

# Load from credential file
generator = CloudBOMGenerator.from_credentials_file("accounts.json")

# Generate multi-account BOM
result = generator.generate_multi_account_bom(
    output_formats=["excel", "word", "json"],
    compliance_policies=compliance_policies
)

print(f"Processed {result['processing_statistics']['total_accounts']} accounts")
print(f"Found {result['processing_statistics']['total_resources']} resources")
print(f"Success rate: {result['processing_statistics']['successful_accounts']}/{result['processing_statistics']['total_accounts']}")
```

### 🔄 **Cross-Account Role Setup**

Automated setup of cross-account roles for centralized scanning.

```python
from inventag.core.credential_manager import CredentialManager

credential_manager = CredentialManager()

# Setup cross-account roles across all accounts
setup_results = credential_manager.setup_cross_account_roles(
    accounts=accounts,
    role_name="InvenTagCrossAccountRole",
    trusted_account_id="123456789012",  # Central scanning account
    external_id="unique-external-id"
)

for account_id, result in setup_results.items():
    if result["success"]:
        print(f"✅ {account_id}: Role created successfully")
        print(f"   Role ARN: {result['role_arn']}")
    else:
        print(f"❌ {account_id}: {result['error']}")
```

### 🎯 **Multi-Account Configuration**

Flexible configuration for different account types and environments.

```python
from inventag.core.cloud_bom_generator import MultiAccountConfig

config = MultiAccountConfig(
    accounts=accounts,
    parallel_account_processing=True,
    max_concurrent_accounts=4,
    account_processing_timeout=1800,  # 30 minutes per account
    consolidate_accounts=True,
    generate_per_account_reports=False,
    enable_state_management=True,
    enable_delta_detection=True
)

generator = CloudBOMGenerator(config)
```

## 🎯 Service-Specific Enrichment

InvenTag includes a powerful service enrichment framework that provides deep attribute extraction for major AWS services, going beyond basic resource discovery to capture detailed configuration and operational data.

### 🔧 **Supported Services with Deep Enrichment**

#### **Amazon S3** - Comprehensive Bucket Analysis
- **Encryption Configuration**: Server-side encryption settings, KMS key details
- **Versioning Status**: Bucket versioning configuration
- **Lifecycle Management**: Lifecycle rules and policies
- **Public Access Controls**: Public access block configuration
- **Object Lock**: Object lock configuration and retention policies
- **Location Constraints**: Bucket region and location details

#### **Amazon RDS** - Database Configuration Deep Dive
- **Engine Details**: Database engine, version, and class information
- **Storage Configuration**: Allocated storage, type, and encryption settings
- **High Availability**: Multi-AZ deployment and backup configuration
- **Security Settings**: VPC security groups, subnet groups, and parameter groups
- **Performance Insights**: Monitoring and performance configuration
- **Maintenance Windows**: Backup and maintenance scheduling

#### **Amazon EC2** - Instance and Volume Analysis
- **Instance Configuration**: Type, state, platform, and architecture details
- **Network Configuration**: VPC, subnet, security groups, and IP addresses
- **Storage Details**: EBS optimization, block device mappings, and root device info
- **Security Features**: IAM instance profiles, key pairs, and monitoring state
- **Advanced Features**: CPU options, hibernation, metadata options, and enclave settings
- **Volume Attributes**: Size, type, IOPS, throughput, encryption, and attachment details

#### **AWS Lambda** - Function Configuration Analysis
- **Runtime Environment**: Runtime version, handler, and execution role
- **Resource Configuration**: Memory size, timeout, and ephemeral storage
- **Network Configuration**: VPC settings and security groups
- **Code Configuration**: Code size, SHA256, deployment package details
- **Advanced Features**: Layers, environment variables, dead letter queues
- **Monitoring**: Tracing configuration and logging settings

#### **Amazon ECS** - Container Service Details
- **Cluster Configuration**: Status, capacity providers, and service counts
- **Service Configuration**: Task definitions, desired count, and deployment settings
- **Network Configuration**: Load balancers, service registries, and VPC settings
- **Scaling Configuration**: Auto scaling and capacity provider strategies

#### **Amazon EKS** - Kubernetes Cluster Analysis
- **Cluster Configuration**: Version, endpoint, and platform details
- **Network Configuration**: VPC settings and Kubernetes network config
- **Security Configuration**: Encryption, identity providers, and access controls
- **Node Group Details**: Instance types, scaling configuration, and launch templates
- **Add-on Configuration**: Installed add-ons and their versions

### 🔄 **Dynamic Service Discovery**

For services not explicitly supported, InvenTag includes an intelligent dynamic discovery system:

- **Pattern-Based API Discovery**: Automatically discovers and tests read-only API operations
- **Intelligent Parameter Mapping**: Maps resource identifiers to appropriate API parameters
- **Response Analysis**: Extracts meaningful attributes from API responses
- **Caching System**: Optimizes performance by caching successful patterns
- **Comprehensive Coverage**: Attempts multiple API patterns for maximum data extraction

### 🛠️ **Service Enrichment Framework**

The enrichment system is built on a flexible, extensible framework:

```python
from inventag.discovery.service_enrichment import ServiceAttributeEnricher

# Initialize enricher
enricher = ServiceAttributeEnricher()

# Enrich all resources with service-specific attributes
enriched_resources = enricher.enrich_resources_with_attributes(resources)

# Get enrichment statistics
stats = enricher.get_enrichment_statistics()
print(f"Enriched: {stats['statistics']['enriched_resources']}")
print(f"Discovered services: {stats['discovered_services']}")
```

### 🎯 **Custom Service Handlers**

Extend InvenTag with custom service handlers for proprietary or specialized services:

```python
from inventag.discovery.service_enrichment import ServiceHandler

class CustomServiceHandler(ServiceHandler):
    def can_handle(self, service: str, resource_type: str) -> bool:
        return service.upper() == 'CUSTOM_SERVICE'
    
    def _define_read_only_operations(self) -> List[str]:
        return ['describe_custom_resource', 'get_custom_configuration']
    
    def enrich_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        # Custom enrichment logic
        attributes = {}
        # ... implementation details
        return {**resource, 'service_attributes': attributes}

# Register custom handler
enricher.register_custom_handler('CUSTOM_SERVICE', CustomServiceHandler)
```

## 💰 Cost Analysis & Optimization

InvenTag includes a comprehensive Cost Analyzer that provides resource cost estimation, forgotten resource detection, and optimization recommendations using the AWS Pricing API and CloudWatch metrics.

### 🔧 **Cost Analysis Features**

#### **Resource Cost Estimation** - AWS Pricing API Integration
- **Real-Time Pricing Data**: Accurate cost estimates using current AWS pricing
- **Service-Specific Calculations**: Tailored cost models for EC2, RDS, S3, Lambda, and more
- **Multi-Pricing Model Support**: On-demand, reserved, and spot pricing considerations
- **Confidence Levels**: Reliability indicators for cost estimates (high, medium, low)
- **Cost Breakdown Analysis**: Detailed component-level cost attribution

#### **Expensive Resource Identification** - Configurable Cost Thresholds
- **Customizable Thresholds**: Organization-specific cost thresholds
- **Service-Specific Analysis**: Different thresholds for different AWS services
- **Cost Ranking**: Resources sorted by estimated monthly cost
- **Impact Assessment**: Potential savings from optimization actions

#### **Forgotten Resource Detection** - Activity Pattern Analysis
- **CloudWatch Metrics Integration**: CPU, network, database connections, S3 requests
- **Configurable Inactivity Periods**: Customizable thresholds for "forgotten" classification
- **Risk Level Assessment**: High, medium, low risk categorization
- **Automated Recommendations**: Specific actions for each forgotten resource

#### **Cost Trend Analysis** - Historical Cost Tracking
- **AWS Cost Explorer Integration**: Historical cost data and trend analysis
- **Trend Direction Detection**: Increasing, decreasing, or stable cost patterns
- **Alert Generation**: Notifications for significant cost changes
- **Service-Level Trends**: Cost analysis grouped by AWS service

#### **Optimization Recommendations** - Actionable Cost Reduction
- **Rightsizing Suggestions**: Instance type optimization recommendations
- **Underutilization Detection**: Resources with low utilization patterns
- **Reserved Instance Analysis**: Opportunities for reserved pricing
- **Storage Class Optimization**: S3 storage class recommendations
- **Implementation Effort Assessment**: Easy, medium, hard implementation categories

### 🛠️ **Cost Analysis Framework**

```python
from inventag.discovery.cost_analyzer import CostAnalyzer, CostThresholds
from decimal import Decimal

# Configure custom thresholds
thresholds = CostThresholds(
    expensive_resource_monthly_threshold=Decimal('200.00'),  # $200/month
    forgotten_resource_days_threshold=45,                    # 45 days inactive
    high_cost_alert_threshold=Decimal('2000.00'),           # $2000/month
    cost_trend_alert_percentage=30.0,                       # 30% change
    unused_resource_utilization_threshold=10.0              # 10% utilization
)

# Initialize cost analyzer
analyzer = CostAnalyzer(thresholds=thresholds)

# Estimate costs for resources
cost_estimates = analyzer.estimate_resource_costs(resources)

# Identify expensive resources
expensive_resources = analyzer.identify_expensive_resources(cost_estimates)

# Detect forgotten resources
forgotten_resources = analyzer.detect_forgotten_resources(resources)

# Generate optimization recommendations
recommendations = analyzer.generate_cost_optimization_recommendations(
    cost_estimates=cost_estimates,
    forgotten_resources=forgotten_resources
)

print(f"Total monthly cost: ${sum(est.estimated_monthly_cost for est in cost_estimates)}")
print(f"Expensive resources: {len(expensive_resources)}")
print(f"Forgotten resources: {len(forgotten_resources)}")
print(f"Optimization opportunities: {len(recommendations)}")
```

### 🎯 **Cost Analysis Use Cases**

#### **Monthly Cost Estimation**
```python
# Get detailed cost breakdown for resources
for estimate in cost_estimates:
    print(f"Resource: {estimate.resource_id}")
    print(f"Service: {estimate.service}")
    print(f"Monthly Cost: ${estimate.estimated_monthly_cost}")
    print(f"Confidence: {estimate.confidence_level}")
    
    # Show cost breakdown by component
    for component, cost in estimate.cost_breakdown.items():
        print(f"  {component}: ${cost}")
```

#### **Forgotten Resource Management**
```python
# Identify and manage forgotten resources
for forgotten in forgotten_resources:
    if forgotten.risk_level == 'high':
        print(f"HIGH RISK: {forgotten.resource_id}")
        print(f"Inactive for {forgotten.days_since_last_activity} days")
        print(f"Monthly cost: ${forgotten.estimated_monthly_cost}")
        print("Recommendations:")
        for rec in forgotten.recommendations:
            print(f"  - {rec}")
```

#### **Cost Optimization Planning**
```python
# Prioritize optimization recommendations
high_impact_recs = [r for r in recommendations if r.potential_monthly_savings > Decimal('50.00')]
total_savings = sum(r.potential_monthly_savings for r in high_impact_recs)

print(f"High-impact recommendations: {len(high_impact_recs)}")
print(f"Potential monthly savings: ${total_savings}")

for rec in sorted(high_impact_recs, key=lambda x: x.potential_monthly_savings, reverse=True):
    print(f"- {rec.resource_id}: ${rec.potential_monthly_savings}/month savings")
    print(f"  Type: {rec.recommendation_type}")
    print(f"  Effort: {rec.implementation_effort}")
```

### 🔄 **Integration with InvenTag Workflow**

```python
from inventag.discovery import AWSResourceInventory
from inventag.discovery.cost_analyzer import CostAnalyzer
from inventag.reporting import BOMConverter

# Discover resources
inventory = AWSResourceInventory(regions=['us-east-1', 'us-west-2'])
resources = inventory.discover_resources()

# Analyze costs
analyzer = CostAnalyzer()
cost_estimates = analyzer.estimate_resource_costs(resources)

# Enrich resources with cost data
for resource in resources:
    cost_estimate = next(
        (est for est in cost_estimates if est.resource_id == resource['id']), 
        None
    )
    if cost_estimate:
        resource['estimated_monthly_cost'] = float(cost_estimate.estimated_monthly_cost)
        resource['cost_confidence'] = cost_estimate.confidence_level

# Generate BOM with cost information
converter = BOMConverter()
converter.data = resources
converter.export_to_excel('cost_analysis_bom.xlsx')
```

### 📊 **Supported AWS Services for Cost Analysis**

| Service | Resource Types | Pricing Factors | Activity Metrics |
|---------|----------------|-----------------|------------------|
| **EC2** | Instances, Volumes | Instance type, volume type, size | CPU utilization, network traffic |
| **RDS** | DB Instances, Clusters | Instance class, engine, storage | Database connections, CPU usage |
| **S3** | Buckets | Storage class, region, data transfer | Request count, data access |
| **Lambda** | Functions | Memory, execution time, requests | Function invocations |
| **ELB/ALB** | Load Balancers | Load balancer type, data processing | Request count, response time |
| **CloudFront** | Distributions | Data transfer, requests | Request metrics |
| **VPC** | NAT Gateways, Endpoints | Data processing, hours | Data transfer |
| **DynamoDB** | Tables | Read/write capacity, storage | Request metrics |

## 📊 BOM Data Processing & Orchestration

InvenTag includes a comprehensive BOM Data Processor that serves as the central orchestrator for processing raw inventory data and coordinating with specialized analyzers to produce enriched, analysis-ready datasets.

### 🔧 **BOM Data Processor Features**

#### **Central Orchestration** - Unified Data Processing Pipeline
- **Multi-Format Input Support**: Handles inventory, compliance, and custom data formats
- **Intelligent Data Extraction**: Automatically detects and extracts resources from various container formats
- **Resource Standardization**: Normalizes resource data across different discovery methods
- **Service Reclassification**: Intelligently reclassifies VPC-related resources for better organization
- **Deduplication**: Advanced deduplication with preference for more complete resource records

#### **Comprehensive Analysis Integration** - Coordinated Enrichment Pipeline
- **Network Analysis**: VPC/subnet analysis with IP utilization and capacity planning
- **Security Analysis**: Security posture assessment with vulnerability detection
- **Service Enrichment**: Deep attribute extraction for AWS services
- **Service Descriptions**: Intelligent, template-based resource descriptions
- **Tag Mapping**: Advanced tag transformation and standardization

#### **Configurable Processing** - Flexible Processing Options
- **Selective Analysis**: Enable/disable specific analysis components
- **Parallel Processing**: Multi-threaded processing for large datasets
- **Caching System**: Result caching for improved performance
- **Timeout Management**: Configurable processing timeouts
- **Error Handling**: Comprehensive error tracking and recovery

### 🛠️ **BOM Data Processing Framework**

```python
from inventag.reporting.bom_processor import (
    BOMDataProcessor, 
    BOMProcessingConfig, 
    BOMData
)

# Configure processing options
config = BOMProcessingConfig(
    enable_network_analysis=True,
    enable_security_analysis=True,
    enable_service_enrichment=True,
    enable_service_descriptions=True,
    enable_tag_mapping=True,
    enable_parallel_processing=True,
    max_worker_threads=4,
    processing_timeout=300,
    service_descriptions_config='config/service_descriptions.yaml',
    tag_mappings_config='config/tag_mappings.yaml'
)

# Initialize processor
processor = BOMDataProcessor(config, boto3.Session())

# Process inventory data
bom_data = processor.process_inventory_data(raw_inventory_data)

# Access enriched results
print(f"Processed {len(bom_data.resources)} resources")
print(f"Network Analysis: {bom_data.network_analysis}")
print(f"Security Analysis: {bom_data.security_analysis}")
print(f"Compliance Summary: {bom_data.compliance_summary}")
```

### 🎯 **Advanced Processing Configuration**

#### **Selective Analysis Configuration**
```python
# Configure for network-focused analysis only
network_config = BOMProcessingConfig(
    enable_network_analysis=True,
    enable_security_analysis=False,
    enable_service_enrichment=False,
    enable_service_descriptions=False,
    enable_tag_mapping=False
)

# Configure for compliance-focused analysis
compliance_config = BOMProcessingConfig(
    enable_network_analysis=False,
    enable_security_analysis=True,
    enable_service_enrichment=True,
    enable_service_descriptions=True,
    enable_tag_mapping=True,
    service_descriptions_config='config/compliance_descriptions.yaml'
)
```

#### **Performance Optimization**
```python
# High-performance configuration for large datasets
performance_config = BOMProcessingConfig(
    enable_parallel_processing=True,
    max_worker_threads=8,
    cache_results=True,
    processing_timeout=600
)

processor = BOMDataProcessor(performance_config, session)

# Process with performance monitoring
import time
start_time = time.time()
bom_data = processor.process_inventory_data(large_dataset)
processing_time = time.time() - start_time

stats = processor.get_processing_statistics()
print(f"Processing completed in {processing_time:.2f} seconds")
print(f"Resources processed: {stats.processed_resources}")
print(f"Failed resources: {stats.failed_resources}")
```

### 🔄 **Data Processing Pipeline**

The BOM Data Processor follows a comprehensive processing pipeline:

1. **Data Extraction**: Intelligently extracts resources from various input formats
2. **Resource Standardization**: Normalizes resource data structure and attributes
3. **Service Reclassification**: Reclassifies VPC-related resources for better organization
4. **Data Cleaning**: Fixes common data issues (missing IDs, account IDs, etc.)
5. **Deduplication**: Removes duplicate resources while preserving complete records
6. **Analysis Coordination**: Orchestrates multiple analysis components
7. **Result Aggregation**: Combines analysis results into comprehensive BOM data
8. **Metadata Generation**: Creates processing metadata and statistics

### 🎯 **Integration Patterns**

#### **With Resource Discovery**
```python
from inventag import AWSResourceInventory
from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig

# Discover resources
inventory = AWSResourceInventory(regions=['us-east-1', 'us-west-2'])
raw_resources = inventory.discover_resources()

# Process with BOM processor
config = BOMProcessingConfig(enable_all_analysis=True)
processor = BOMDataProcessor(config, inventory.session)
bom_data = processor.process_inventory_data(raw_resources)

# Access comprehensive analysis
print(f"Network Summary: {bom_data.network_analysis}")
print(f"Security Summary: {bom_data.security_analysis}")
print(f"Custom Attributes: {bom_data.custom_attributes}")
```

#### **With State Management**
```python
from inventag.state import StateManager

# Process and save enriched state
state_manager = StateManager()
bom_data = processor.process_inventory_data(resources)

state_id = state_manager.save_state(
    resources=bom_data.resources,
    account_id='123456789012',
    regions=['us-east-1', 'us-west-2'],
    network_analysis=bom_data.network_analysis,
    security_analysis=bom_data.security_analysis,
    compliance_data=bom_data.compliance_summary,
    tags={'processing': 'bom_processor', 'version': '1.0'}
)
```

#### **With Compliance Checking**
```python
from inventag.compliance import ComprehensiveTagComplianceChecker

# Process resources and check compliance
bom_data = processor.process_inventory_data(resources)

# Enhanced compliance checking with enriched data
checker = ComprehensiveTagComplianceChecker(
    regions=['us-east-1', 'us-west-2'],
    config_file='config/tag_policy.yaml'
)

compliance_results = checker.check_compliance(bom_data.resources)

# Combine with BOM analysis
enhanced_bom = BOMData(
    resources=bom_data.resources,
    network_analysis=bom_data.network_analysis,
    security_analysis=bom_data.security_analysis,
    compliance_summary=compliance_results['summary'],
    generation_metadata=bom_data.generation_metadata
)
```

### 📊 **Processing Statistics and Monitoring**

```python
# Get detailed processing statistics
stats = processor.get_processing_statistics()

print(f"Processing Statistics:")
print(f"  Total Resources: {stats.total_resources}")
print(f"  Successfully Processed: {stats.processed_resources}")
print(f"  Failed Processing: {stats.failed_resources}")
print(f"  Network Enriched: {stats.network_enriched}")
print(f"  Security Enriched: {stats.security_enriched}")
print(f"  Service Enriched: {stats.service_enriched}")
print(f"  Description Enriched: {stats.description_enriched}")
print(f"  Tag Mapped: {stats.tag_mapped}")
print(f"  Processing Time: {stats.processing_time_seconds:.2f} seconds")

# Handle errors and warnings
if stats.errors:
    print(f"Errors encountered: {len(stats.errors)}")
    for error in stats.errors:
        print(f"  - {error}")

if stats.warnings:
    print(f"Warnings: {len(stats.warnings)}")
    for warning in stats.warnings:
        print(f"  - {warning}")
```

### 🔧 **Error Handling and Recovery**

```python
# Configure error handling
config = BOMProcessingConfig(
    enable_network_analysis=True,
    enable_security_analysis=True,
    processing_timeout=300
)

processor = BOMDataProcessor(config, session)

try:
    bom_data = processor.process_inventory_data(resources)
    
    # Check for processing errors
    if bom_data.error_summary.get('has_errors', False):
        print("Processing completed with errors:")
        for error in bom_data.error_summary.get('errors', []):
            print(f"  - {error}")
    
    # Check for warnings
    if bom_data.error_summary.get('has_warnings', False):
        print("Processing completed with warnings:")
        for warning in bom_data.error_summary.get('warnings', []):
            print(f"  - {warning}")
            
except Exception as e:
    print(f"Processing failed: {e}")
    
    # Get partial results if available
    stats = processor.get_processing_statistics()
    if stats.processed_resources > 0:
        print(f"Partial processing completed: {stats.processed_resources} resources")
```

## 🐍 Programmatic Usage (Python Package)

InvenTag is now available as a unified Python package for programmatic integration into your applications and workflows.

### Basic Usage

```python
from inventag import AWSResourceInventory, ComprehensiveTagComplianceChecker, BOMConverter
from inventag.state import StateManager, DeltaDetector, ChangelogGenerator
from inventag.discovery.service_enrichment import ServiceAttributeEnricher
from inventag.discovery.service_descriptions import ServiceDescriptionManager
from inventag.discovery.network_analyzer import NetworkAnalyzer
from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig

# Resource Discovery with Service Enrichment
inventory = AWSResourceInventory(regions=['us-east-1', 'us-west-2'])
resources = inventory.discover_resources()

# Comprehensive BOM Processing
config = BOMProcessingConfig(
    enable_network_analysis=True,
    enable_security_analysis=True,
    enable_service_enrichment=True,
    enable_service_descriptions=True,
    enable_tag_mapping=True
)

processor = BOMDataProcessor(config, inventory.session)
bom_data = processor.process_inventory_data(resources)

# Access enriched and analyzed data
enriched_resources = bom_data.resources
network_analysis = bom_data.network_analysis
security_analysis = bom_data.security_analysis
compliance_summary = bom_data.compliance_summarywork_analyzer.analyze_vpc_resources(described_resources)
network_enriched_resources = network_analyzer.map_resources_to_network(described_resources)

# Tag Compliance Checking
checker = ComprehensiveTagComplianceChecker(
    regions=['us-east-1', 'us-west-2'],
    config_file='config/tag_policy_example.yaml'
)
compliance_results = checker.check_compliance(network_enriched_resources)

# Professional Reporting with enriched data and descriptions
converter = BOMConverter(enrich_vpc_info=True)
converter.data = network_enriched_resources
converter.export_to_excel('comprehensive_report.xlsx')

# State Management
state_manager = StateManager(state_dir='inventory_states')
state_id = state_manager.save_state(
    resources=network_enriched_resources,
    account_id='123456789012',
    regions=['us-east-1', 'us-west-2'],
    compliance_data=compliance_results
)
```

### Advanced Workflows with Service Enrichment

```python
# Service-specific analysis
enricher = ServiceAttributeEnricher()

# Get detailed S3 bucket configurations
s3_resources = [r for r in resources if r.get('service') == 'S3']
enriched_s3 = enricher.enrich_resources_with_attributes(s3_resources)

for bucket in enriched_s3:
    if 'service_attributes' in bucket:
        attrs = bucket['service_attributes']
        print(f"Bucket: {bucket['name']}")
        print(f"  Encryption: {attrs.get('encryption', {}).get('enabled', 'Unknown')}")
        print(f"  Versioning: {attrs.get('versioning_status', 'Unknown')}")
        print(f"  Public Access Block: {bool(attrs.get('public_access_block'))}")

# RDS database analysis
rds_resources = [r for r in resources if r.get('service') == 'RDS']
enriched_rds = enricher.enrich_resources_with_attributes(rds_resources)

for db in enriched_rds:
    if 'service_attributes' in db:
        attrs = db['service_attributes']
        print(f"Database: {db['name']}")
        print(f"  Engine: {attrs.get('engine')} {attrs.get('engine_version')}")
        print(f"  Multi-AZ: {attrs.get('multi_az', False)}")
        print(f"  Encrypted: {attrs.get('storage_encrypted', False)}")
        print(f"  Backup Retention: {attrs.get('backup_retention_period', 0)} days")

# Change Detection and Analysis
detector = DeltaDetector()
delta_report = detector.detect_changes(
    old_resources=previous_resources,
    new_resources=current_resources,
    state1_id='previous_state',
    state2_id='current_state'
)

# Generate Professional Changelogs
changelog_gen = ChangelogGenerator()
changelog = changelog_gen.generate_changelog(
    delta_report=delta_report,
    format='markdown',
    include_details=True
)
changelog_gen.export_changelog(changelog, 'infrastructure_changes.md')

# Get enrichment statistics
stats = enricher.get_enrichment_statistics()
print(f"Total resources processed: {stats['statistics']['total_resources']}")
print(f"Successfully enriched: {stats['statistics']['enriched_resources']}")
print(f"Services discovered: {', '.join(stats['discovered_services'])}")
print(f"Unknown services: {', '.join(stats['unknown_services'])}")
```

## 🏷️ Tag Policy Configuration

Create your own tag policy by copying and editing the example:

```bash
cp config/tag_policy_example.yaml my_tag_policy.yaml
# Edit my_tag_policy.yaml with your requirements
```

**Example policy structure:**
```yaml
required_tags:
  - "Environment"      # Any value allowed
  - "Owner"
  - "Project" 
  
  # Specific allowed values
  - key: "Environment"
    allowed_values: ["production", "staging", "development"]
  
  - key: "CostCenter"
    required_values: ["engineering", "marketing", "finance"]
```

## 📊 Excel Output Features

- **Service-Specific Sheets**: Each AWS service gets its own sheet (EC2, S3, RDS, etc.)
- **VPC/Subnet Names**: Automatic lookup and inclusion from resource tags
- **Professional Formatting**: Color-coded headers, auto-sized columns
- **Summary Dashboard**: Overview with service breakdown and statistics

## 🔐 Security

**✅ 100% READ-ONLY**: Cannot modify your AWS infrastructure  
**✅ MINIMAL PERMISSIONS**: Only requires read access to AWS services  
**✅ PRODUCTION SAFE**: Designed for safe execution in production environments

See [`docs/SECURITY.md`](/development/docs/SECURITY) for detailed security information.

## 🌍 Region Handling

- **Default**: Scans ALL AWS regions automatically
- **Fallback**: Uses us-east-1 and ap-southeast-1 if region discovery fails
- **Custom**: Specify specific regions with `--regions us-east-1 eu-west-1`

## ⚡ Common Use Cases

### Monthly Resource Audit
```bash
# Using unified CLI
python -m inventag.cli.main --create-excel --s3-bucket monthly-reports --verbose

# Legacy script (deprecated)
python scripts/aws_resource_inventory.py --export-excel --s3-bucket monthly-reports
```

### Multi-Account Compliance Monitoring
```bash
# Using unified CLI with multi-account support
python -m inventag.cli.main --accounts-file accounts.json --create-excel --create-word \
  --s3-bucket compliance-reports --s3-key-prefix monthly-audit/

# Legacy script (deprecated)
python scripts/tag_compliance_checker.py --config config/production_tags.yaml --s3-bucket compliance-reports
```

### Cost Center Reporting
```bash
# Using unified CLI with custom tag mappings
python -m inventag.cli.main --create-excel --tag-mappings config/cost_center_tags.yaml \
  --output-directory cost-reports

# Legacy approach (deprecated)
python scripts/aws_resource_inventory.py
python scripts/bom_converter.py --input aws_resources_*.json --output cost_center_report.xlsx
```

### Security Audit Preparation
```bash
# Using unified CLI with production safety features
python -m inventag.cli.main --accounts-file security-accounts.json --create-excel --create-word \
  --service-descriptions config/security_services.yaml --verbose --debug

# Legacy script (deprecated)
python scripts/tag_compliance_checker.py --config config/security_tags.yaml --verbose
```

## 🛠️ Advanced Options

### Resource Inventory
- `--regions us-east-1 eu-west-1` - Scan specific regions only
- `--format yaml` - Output in YAML format
- `--s3-bucket BUCKET --s3-key path/file.json` - Custom S3 upload
- `--export-excel` - Auto-generate Excel report
- `--verbose` - Detailed logging

### Tag Compliance
- `--config FILE` - Use custom tag policy
- `--regions LIST` - Check specific regions
- `--format yaml` - YAML output format
- `--s3-bucket BUCKET` - Upload compliance report
- `--verbose` - Show detailed progress

### BOM Converter
- `--format csv` - Export as CSV instead of Excel
- `--no-vpc-enrichment` - Skip VPC/subnet name lookup (faster)

## 📦 Dependencies

- **boto3** - AWS SDK
- **PyYAML** - YAML support
- **openpyxl** - Excel generation
- **colorama** - Colored output

## 🆘 Troubleshooting

**"No credentials found"**  
→ Run `aws configure` or set environment variables

**"Access denied for service X"**  
→ Update IAM policy with permissions for that service

**"No resources found"**  
→ Check if you have any resources in the scanned regions

**Excel export fails**  
→ Install openpyxl: `pip install openpyxl`

## 📁 Output Files

All files include timestamps for easy tracking:
- `aws_resources_YYYYMMDD_HHMMSS.json` - Complete inventory
- `aws_resources_YYYYMMDD_HHMMSS.xlsx` - Excel with service sheets
- `tag_compliance_report_YYYYMMDD_HHMMSS.json` - Compliance results

## 🏢 Enterprise Features

- **Multi-account support** via cross-account roles
- **Automated scheduling** via AWS Lambda or cron
- **Integration** with CMDB/ITSM systems via S3 uploads
- **Compliance reporting** for SOC2, PCI-DSS, HIPAA audits
- **Cost optimization** through resource discovery and tagging

---

## 📚 Documentation

- **[Release Management Guide](/development/RELEASE)** - Complete CI/CD and versioning documentation
- **[Security Guide](/development/docs/SECURITY)** - Detailed permissions and security info
- **[Tag Compliance Guide](/development/docs/TAG_COMPLIANCE)** - Comprehensive tag compliance checking with integrated BOM generation
- **[Network Analysis Guide](/development/docs/NETWORK_ANALYSIS)** - Comprehensive VPC/subnet analysis and capacity planning
- **[Service Enrichment Guide](/development/docs/SERVICE_ENRICHMENT)** - Deep service attribute extraction and custom handlers
- **[CLI User Guide](/development/docs/CLI_USER_GUIDE)** - Comprehensive CLI interface documentation
- **[State Management Guide](/development/docs/STATE_MANAGEMENT)** - Comprehensive state tracking and change detection
- **[Configuration Guide](/development/config/README)** - Tag policies and IAM setup
- **[Script Documentation](/development/scripts/README)** - Legacy script usage (deprecated)
- **[Examples](/development/examples/README)** - Usage patterns and outputs
- **[Testing Guide](/development/tests/README)** - Comprehensive test suite documentation

## 🚀 DevOps & Production Integration

### Enterprise CI/CD Pipeline

This repository demonstrates modern DevOps practices:

```mermaid
graph LR
    A[Developer] --> B[Feature Branch]
    B --> C[Pull Request]
    C --> D[PR Checks]
    D --> E[Code Review]
    E --> F[Merge to Main]
    F --> G[Automated Release]
    G --> H[GitHub Release]
    H --> I[Production Deploy]
```

### Monitoring & Observability

**Compliance Metrics:**
- Track compliance percentage over time
- Service-specific compliance trends  
- Tag policy violation alerts
- Resource growth patterns

**Integration with Monitoring:**
```bash
# Export compliance metrics to monitoring system using unified CLI
python -m inventag.cli.main --accounts-file accounts.json --create-excel \
  --s3-bucket monitoring-reports --verbose

# Legacy approach (deprecated)
python scripts/tag_compliance_checker.py \
  --config production_tags.yaml \
  --format json | \
  jq '.summary.compliance_percentage' | \
  curl -X POST monitoring-endpoint
```

### Production Deployment Patterns

**1. Scheduled Compliance Auditing:**
```yaml
# Deploy as AWS Lambda for automated daily reports
name: Deploy Compliance Lambda
on:
  release:
    types: [published]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Deploy to AWS Lambda
      run: |
        zip -r inventag-aws.zip scripts/ config/ requirements.txt
        aws lambda update-function-code \
          --function-name compliance-checker \
          --zip-file fileb://inventag-aws.zip
```

**2. Multi-Account Scanning:**
```bash
# Cross-account compliance checking
for account in prod staging dev; do
  aws sts assume-role --role-arn arn:aws:iam::${account}:role/ComplianceRole \
    --role-session-name compliance-scan \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text | read key secret token
  
  AWS_ACCESS_KEY_ID=$key \
  AWS_SECRET_ACCESS_KEY=$secret \
  AWS_SESSION_TOKEN=$token \
  # Using unified CLI (recommended)
  python -m inventag.cli.main --accounts-file config/${account}_accounts.json --create-excel \
  # Legacy script (deprecated)
  python scripts/tag_compliance_checker.py \
    --config config/${account}_tags.yaml \
    --output ${account}_compliance.json
done
```

**3. Integration with ITSM/CMDB:**
```bash
# Upload to ServiceNow/JIRA for ticket creation
# Using unified CLI (recommended)
python -m inventag.cli.main --accounts-file accounts.json --create-excel \
  --s3-bucket integration-reports

# Legacy script (deprecated)
python scripts/tag_compliance_checker.py \
  --config production_tags.yaml | \
  jq '.non_compliant_resources[] | select(.resource.service=="EC2")' | \
  curl -X POST -H "Content-Type: application/json" \
    -d @- https://company.service-now.com/api/compliance-violations
```

### Cost Optimization Integration

**Resource Cost Analysis:**
```bash
# Combine with AWS Cost Explorer
# Using unified CLI (recommended)
python -m inventag.cli.main --create-excel --output-directory cost-analysis

# Legacy script (deprecated)
python scripts/aws_resource_inventory.py --export-excel
# Import into cost analysis tools for optimization recommendations
```

**Tag-Based Cost Allocation:**
```bash
# Generate cost center reports
# Using unified CLI (recommended)
python -m inventag.cli.main --create-excel --tag-mappings cost_center_tags.yaml

# Legacy script (deprecated)
python scripts/tag_compliance_checker.py \
  --config cost_center_tags.yaml \
  --output cost_allocation_report.json
```

### Security & Compliance

**SOC2/ISO27001 Integration:**
- Automated evidence collection
- Continuous compliance monitoring  
- Audit trail generation
- Policy violation alerts

**Zero-Trust Security Model:**
- Read-only permissions only
- Cross-account role assumption
- Temporary credential usage
- Audit logging enabled

**Quick help:** Run `./examples/quick_start.sh` for an automated demo of all features!
