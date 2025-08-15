# 🏷️ InvenTag

> **Professional AWS™ Cloud Governance Platform - Comprehensive resource inventory, compliance checking, and BOM generation**

[![Automated Release](https://github.com/habhabhabs/inventag-aws/workflows/Automated%20Release/badge.svg)](https://github.com/habhabhabs/inventag-aws/actions)
[![Documentation](https://github.com/habhabhabs/inventag-aws/workflows/Documentation%20Deployment/badge.svg)](https://habhabhabs.github.io/inventag-aws/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📚 **[→ Visit Complete Documentation Site ←](https://habhabhabs.github.io/inventag-aws/)**

**Modern Documentation Platform** with advanced search, mobile-responsive design, and comprehensive guides.

[![Documentation Preview](https://img.shields.io/badge/📖_Documentation-Live_Site-blue?style=for-the-badge)](https://habhabhabs.github.io/inventag-aws/)

---

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

- 🛡️ **Production Safety & Security** - Enterprise-grade security validation and compliance standards (SOC 2, PCI, HIPAA, GDPR)
- 📊 **Professional BOM Generation** - Excel/Word/Google Docs reports with logical column ordering and service-specific sheets
- 🔍 **Comprehensive Discovery System** - Advanced service-specific API discovery that finds **ALL resources regardless of tags**, including untagged VPCs, subnets, security groups, and critical infrastructure
- 🧠 **Multi-Account Discovery** - Comprehensive resource scanning across multiple AWS accounts with parallel processing
- ⚡ **Optimized Performance** - Enhanced intelligent discovery with 22+ AWS service patterns, AWS managed resource filtering, and **8.4 resources/sec performance** (68% above targets)
- ⚡ **Production-Tested Reliability** - Comprehensive regression testing on real AWS accounts with 93-97% parallel efficiency and graceful error handling
- 🌐 **Advanced Analysis Suite** - Network security analysis, cost optimization, and security posture assessment
- 🏷️ **Tag Compliance Checking** - Automated validation against organizational tagging policies
- 🔄 **State Management** - Change tracking with delta detection and professional changelog generation
- 🚀 **CI/CD Ready** - Easy integration with automated workflows and S3 upload support
- ⚡ **Flexible Deployment** - Cross-account roles, interactive setup, and comprehensive credential management

## 📖 **Complete Documentation Portal**

### **🌟 [Interactive Documentation Site](https://habhabhabs.github.io/inventag-aws/)** 
**Powered by Docusaurus** - Professional documentation platform with:

- 🔍 **Advanced Search** - Instant results across all content
- 📱 **Mobile Responsive** - Perfect on any device  
- 🌙 **Dark/Light Themes** - Customizable viewing experience
- 📊 **Interactive Navigation** - Collapsible sidebar with breadcrumbs
- 🚀 **Fast Loading** - Optimized performance and caching
- 📝 **GitHub Integration** - Direct editing links for contributors

### **📋 Quick Access Links**

| Section | Description | Link |
|---------|-------------|------|
| 🚀 **Getting Started** | Installation and quick start guide | **[Start Here →](https://habhabhabs.github.io/inventag-aws/docs/getting-started/quick-start)** |
| 📖 **User Guides** | Comprehensive CLI reference | **[CLI Guide →](https://habhabhabs.github.io/inventag-aws/docs/user-guides/cli-user-guide)** |
| 📋 **Configuration** | Working configuration examples | **[Examples →](https://habhabhabs.github.io/inventag-aws/docs/user-guides/configuration-examples)** |
| 🛡️ **Production Safety** | Security and compliance features | **[Security →](https://habhabhabs.github.io/inventag-aws/docs/user-guides/production-safety)** |
| 🏗️ **Architecture** | System architecture and design | **[Architecture →](https://habhabhabs.github.io/inventag-aws/docs/architecture/core-module-integration)** |
| 🔧 **Development** | Contributing and development guide | **[Contribute →](https://habhabhabs.github.io/inventag-aws/docs/development/CONTRIBUTING)** |

### Legacy Documentation

For offline reference, documentation is also available in the `docs/` directory:

- **[CLI User Guide](docs/user-guides/cli-user-guide.md)** - Local CLI reference
- **[Quick Start Guide](docs/getting-started/quick-start.md)** - Local installation guide
- **[All Local Documentation](docs/)** - Complete documentation directory

## 💼 Enterprise Examples

```bash
# Multi-account BOM with comprehensive analysis
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml \
  --service-descriptions config/defaults/services/service_descriptions_example.yaml \
  --enable-network-analysis --enable-security-analysis \
  --compliance-standard soc2 --s3-bucket enterprise-reports

# Interactive multi-account setup with advanced features
./inventag.sh --accounts-prompt \
  --create-excel --create-google-docs \
  --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml \
  --enable-cost-analysis --generate-changelog

# Cross-account role with production safety
./inventag.sh --cross-account-role InvenTagRole \
  --create-excel --enable-production-safety \
  --security-validation --audit-output security-audit.json

# CI/CD integration with comprehensive reporting
./inventag.sh --accounts-file accounts.json \
  --create-excel --create-word \
  --s3-bucket reports-bucket --s3-key-prefix daily-reports/ \
  --max-concurrent-accounts 8 --per-account-reports
```

## 🏗️ Project Structure

```text
inventag-aws/
├── README.md                    # This overview
├── inventag/                    # Core Python package
│   ├── cli/                     # Unified CLI interface
│   ├── core/                    # Core orchestration
│   ├── discovery/               # Resource discovery
│   ├── compliance/              # Security & compliance
│   ├── reporting/               # BOM generation
│   └── state/                   # Change management
├── docs/                        # Complete documentation
├── examples/                    # Configuration examples
├── config/                      # Default configurations
├── scripts/                     # Standalone tools
└── tests/                       # Comprehensive test suite
```

## 🛡️ Security & Compliance

InvenTag includes enterprise-grade security features:

- **Read-Only Enforcement** - All operations are strictly read-only by default
- **Compliance Standards** - Built-in support for SOC 2, PCI, HIPAA, GDPR
- **Audit Logging** - Comprehensive audit trails for all operations
- **Risk Assessment** - Automated security risk evaluation
- **Production Safety** - Real-time monitoring and validation

See [Production Safety Guide](https://habhabhabs.github.io/inventag-aws/docs/user-guides/production-safety) for complete details.

## 🔗 Support & Community

- **[📖 Complete Documentation](https://habhabhabs.github.io/inventag-aws/)** - Comprehensive guides and references
- **[🐛 Issues](https://github.com/habhabhabs/inventag-aws/issues)** - Bug reports and feature requests
- **[💬 Discussions](https://github.com/habhabhabs/inventag-aws/discussions)** - Community Q&A
- **[📋 Additional Resources](https://habhabhabs.github.io/inventag-aws/docs/examples/)** - Configuration examples and tutorials

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🌐 **Documentation Platform**

This project uses **[Docusaurus](https://docusaurus.io/)** for its documentation site, providing:

- **Professional Documentation Experience** - Modern, fast, and user-friendly
- **Automated Deployment** - Documentation automatically deployed from `docs/` directory  
- **Developer-Friendly** - Easy to contribute with Markdown and GitHub integration
- **Mobile-First Design** - Responsive layout for all devices
- **Search-Optimized** - Full-text search across all documentation

**📖 Experience it yourself:** **[habhabhabs.github.io/inventag-aws](https://habhabhabs.github.io/inventag-aws/)**

---

> **InvenTag** - Professional AWS™ cloud governance made simple
>
> *AWS™ is a trademark of Amazon Web Services, Inc. InvenTag is an independent tool and is not affiliated with, endorsed by, or sponsored by Amazon Web Services, Inc.*