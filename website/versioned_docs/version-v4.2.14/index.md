---
title: InvenTag Documentation
description: Complete documentation for InvenTag AWS Cloud Governance Platform
sidebar_position: 1
---

# 🏷️ InvenTag

> **Professional AWS™ Cloud Governance Platform - Comprehensive resource inventory, compliance checking, and BOM generation**

[![Automated Release](https://github.com/habhabhabs/inventag-aws/workflows/Automated%20Release/badge.svg)](https://github.com/habhabhabs/inventag-aws/actions)
[![Documentation](https://img.shields.io/badge/docs-versioned-brightgreen.svg)](https://habhabhabs.github.io/inventag-aws/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![InvenTag Logo](/img/inventag-logo-placeholder.svg)

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
pip install -r requirements.txt

# Generate professional BOM reports with production safety
# The script automatically detects python3/python
./inventag.sh --create-excel --create-word \
  --enable-production-safety --security-validation
```

## ✨ Key Features

- 🛡️ **Production Safety & Security** - Enterprise-grade security validation with compliance standards (SOC 2, PCI, HIPAA, GDPR) and read-only enforcement
- 📊 **Professional BOM Generation** - Multi-format reports (Excel/Word/Google Docs) with logical column ordering and service-specific sheets
- 🔍 **Comprehensive Resource Discovery** - 22+ AWS services discovery with optimized patterns and 3-4x performance improvement
- 🌐 **Advanced Analysis Suite** - Network security analysis, cost optimization, and security posture assessment with detailed insights
- 🏷️ **Tag Compliance & Validation** - Automated validation against organizational tagging policies with customizable rules
- 🔄 **State Management & Change Tracking** - Delta detection with professional changelog generation and audit trails
- 🚀 **Multi-Account & CI/CD Ready** - Parallel processing across accounts with S3 upload, role assumption, and pipeline integration
- ⚡ **Flexible Deployment Options** - Cross-platform support, interactive setup, credential management, and enterprise scaling

## 🏛️ AWS Prescriptive Guidance Templates

**NEW**: Professional templates following [AWS Prescriptive Guidance for Cost Allocation Tagging](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/)

```bash
# Generate compliance reports using AWS Prescriptive Guidance templates
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --tag-mappings config/aws-prescriptive-guidance/tag-mappings.yaml \
  --service-descriptions config/aws-prescriptive-guidance/service-descriptions.yaml \
  --compliance-standard aws-prescriptive-guidance \
  --enable-cost-analysis --enable-governance-reporting

# Cost allocation focused reporting with financial governance
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --tag-mappings config/aws-prescriptive-guidance/tag-mappings.yaml \
  --cost-allocation-focus --financial-governance \
  --budget-tracking --chargeback-reporting
```

**📋 Available AWS Prescriptive Guidance Templates:**
- **[Tagging Dictionary](/files/tagging-dictionary.yaml)** - Comprehensive tag definitions with cost allocation focus
- **[Service Descriptions](/files/service-descriptions.yaml)** - Enhanced service descriptions with cost factors
- **[Tag Mappings](/files/tag-mappings.yaml)** - Financial governance optimized column mappings
- **Cost Allocation Hierarchy** - Multi-level business unit → cost center → project → application
- **Compliance Frameworks** - SOC 2, PCI, HIPAA, GDPR integration
- **Governance Automation** - SCP enforcement, tag policies, monitoring dashboards

## 💼 Enterprise Examples

```bash
# Multi-account BOM with comprehensive analysis and compliance
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --tag-mappings config/aws-prescriptive-guidance/tag-mappings.yaml \
  --service-descriptions config/aws-prescriptive-guidance/service-descriptions.yaml \
  --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
  --compliance-standard soc2 --audit-output compliance-report.json

# Interactive multi-account setup with state management
./inventag.sh --accounts-prompt \
  --create-excel --create-google-docs \
  --tag-mappings config/aws-prescriptive-guidance/tag-mappings.yaml \
  --enable-state-management --generate-changelog \
  --per-account-reports --verbose

# Cross-account role assumption with enhanced security
./inventag.sh --cross-account-role InvenTagRole \
  --create-excel --create-word \
  --enable-production-safety --security-validation \
  --risk-threshold HIGH --audit-output security-audit.json

# CI/CD pipeline integration with S3 upload
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --s3-bucket enterprise-reports --s3-key-prefix daily-reports/ \
  --s3-encryption aws:kms --s3-kms-key-id alias/report-encryption \
  --max-concurrent-accounts 8 --account-processing-timeout 3600

# Production validation and debugging
./inventag.sh --validate-credentials \
  --validate-config --debug \
  --log-file inventag-debug.log \
  --credential-timeout 60
```

## 🏗️ Project Structure

```text
inventag-aws/
├── inventag_cli.py              # Main CLI entry point
├── inventag.sh / inventag.bat   # Cross-platform wrapper scripts
├── inventag/                    # Core Python package
│   ├── cli/                     # Unified CLI interface & configuration validation
│   ├── core/                    # Multi-account orchestration & credential management
│   ├── discovery/               # 22+ AWS service discovery engines
│   ├── compliance/              # Security validation & production safety
│   ├── reporting/               # Multi-format BOM generation (Excel/Word/CSV)
│   └── state/                   # Change tracking & changelog generation
├── docs/                        # Complete documentation (dual GitHub/Docusaurus)
├── website/                     # Docusaurus documentation site
├── examples/                    # 15+ working configuration examples
├── config/                      # Default configurations & JSON schemas
├── templates/                   # Document generation templates
├── scripts/                     # Development & production tools
└── tests/                       # Comprehensive test suite (unit/integration/backward)
```

## 🛡️ Security & Compliance

InvenTag includes enterprise-grade security features:

- **Read-Only Enforcement** - All operations are strictly read-only by default
- **Compliance Standards** - Built-in support for SOC 2, PCI, HIPAA, GDPR
- **Audit Logging** - Comprehensive audit trails for all operations
- **Risk Assessment** - Automated security risk evaluation
- **Production Safety** - Real-time monitoring and validation

See [Production Safety Guide](/user-guides/production-safety) for complete details.

## 🚀 Getting Started

New to InvenTag? Start here to get up and running quickly.

- **[Introduction](/getting-started/introduction)** - Overview of InvenTag and its key features
- **[Installation](/getting-started/installation)** - How to install and set up InvenTag
- **[Quick Start Guide](/getting-started/quick-start)** - Get started in minutes with basic examples

## 📖 User Guides

Comprehensive guides for using InvenTag in different scenarios.

- **[CLI User Guide](./user-guides/cli-user-guide)** - Comprehensive CLI reference and usage examples
- **[Configuration Examples](./user-guides/configuration-examples)** - Setup and configuration guidance
- **[Production Safety Guide](./user-guides/production-safety)** - Security, compliance, and safety features
- **[Troubleshooting Guide](./user-guides/troubleshooting-guide)** - Common issues and solutions

## 🏗️ Architecture & Technical Design

Technical documentation for developers and system architects.

- **[Core Module Integration](./architecture/core-module-integration)** - System architecture overview
- **[Optimized Discovery System](./architecture/optimized-discovery-system)** - Enhanced discovery with 3-4x performance improvement
- **[State Management](./architecture/state-management)** - Change tracking and delta detection
- **[Template Framework](./architecture/template-framework)** - Document generation system
- **[Service Enrichment](./architecture/service-enrichment)** - AWS service attribute enhancement
- **[BOM Data Processor](./architecture/bom-data-processor)** - Data processing pipeline
- **[Network Analysis](./architecture/network-analysis)** - VPC and network analysis capabilities
- **[Cost Analysis](./architecture/cost-analysis)** - Cost estimation and optimization
- **[Tag Compliance](./architecture/tag-compliance)** - Compliance checking framework

## 🛠️ Development & Deployment

Resources for developers contributing to InvenTag or deploying it in production.

- **[Contributing Guide](./development/CONTRIBUTING)** - Development setup and guidelines
- **[Deployment Guide](./development/DEPLOYMENT)** - Production deployment instructions
- **[CI/CD Integration](./development/cicd-integration)** - Pipeline integration examples
- **[Security Guide](./development/SECURITY)** - Security best practices
- **[Backward Compatibility](./development/backward-compatibility)** - Version compatibility matrix
- **[Migration Guide](./development/bom-migration-guide)** - Upgrade and migration procedures

## 📖 Documentation

- **[📖 Complete User Guide](./user-guides/cli-user-guide)** - Comprehensive CLI reference and examples
- **[🚀 Quick Start Guide](./getting-started/quick-start)** - Get started in minutes
- **[📋 Configuration Examples](./examples/)** - Working configuration examples  
- **[🛡️ Production Safety Guide](./user-guides/production-safety)** - Security and compliance features
- **[⚙️ Configuration Guide](./user-guides/configuration-examples)** - Setup and customization
- **[🔧 Troubleshooting](./user-guides/troubleshooting-guide)** - Common issues and solutions

## 🚀 Quick Navigation

- **New User?** Start with [Introduction](./getting-started/introduction) and [Quick Start Guide](./getting-started/quick-start)
- **Setting Up?** Check [Installation](./getting-started/installation) and [Configuration Examples](./user-guides/configuration-examples)  
- **Production Deployment?** See [Production Safety Guide](./user-guides/production-safety) and [Deployment Guide](./development/DEPLOYMENT)
- **Having Issues?** Visit [Troubleshooting Guide](./user-guides/troubleshooting-guide)
- **Developer?** Read [Contributing Guide](./development/CONTRIBUTING)

## 🔗 Support & Community

- **[🐛 Issues](https://github.com/habhabhabs/inventag-aws/issues)** - Bug reports and feature requests
- **[💬 Discussions](https://github.com/habhabhabs/inventag-aws/discussions)** - Community Q&A
- **[📋 Wiki](https://github.com/habhabhabs/inventag-aws/wiki)** - Additional resources

## 📄 License

MIT License - see the [LICENSE](https://github.com/habhabhabs/inventag-aws/blob/main/LICENSE) file for details.

---

> **InvenTag** - Professional AWS™ cloud governance made simple
>
> *AWS™ is a trademark of Amazon Web Services, Inc. InvenTag is an independent tool and is not affiliated with, endorsed by, or sponsored by Amazon Web Services, Inc.*

## 📋 Documentation Standards

All documentation follows consistent formatting and includes:
- Clear examples with working code
- Step-by-step procedures
- Troubleshooting sections
- Cross-references to related topics
- Regular updates with each release
