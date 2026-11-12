---
title: SBOM Overview
description: Understanding InvenTag's Software Bill of Materials
sidebar_position: 2
---

# Software Bill of Materials (SBOM) Overview

A Software Bill of Materials (SBOM) is a comprehensive inventory of all components, libraries, and dependencies that make up InvenTag. This transparency is crucial for security, compliance, and supply chain management.

## What is an SBOM?

An SBOM provides:
- **Complete inventory** of all software components
- **Dependency relationships** between components  
- **License information** for compliance
- **Vulnerability tracking** for security
- **Supply chain transparency** for risk management

## SBOM Generation Process

InvenTag automatically generates SBOMs:

### During Documentation Builds
- **Fresh SBOM** generated with each documentation deployment
- **Multiple formats** created for different use cases
- **Integrated into docs** for easy access and transparency

### During Version Creation
- **Version-specific SBOM** captured at release time
- **Historical tracking** of component changes
- **Compliance documentation** for specific releases

## SBOM Formats

We generate SBOMs in multiple industry-standard formats:

| Format | Use Case | Description |
|--------|----------|-------------|
| **Syft JSON** | Automated analysis | Comprehensive format with detailed metadata |
| **CycloneDX** | Industry standard | OWASP standard for supply chain security |
| **SPDX** | Compliance | Software Package Data Exchange format |
| **XML** | Human readable | Structured format for manual review |

## Component Categories

Our SBOM includes:

### Python Dependencies
- **Direct dependencies** from requirements.txt
- **Transitive dependencies** automatically resolved
- **Development dependencies** for complete transparency

### Node.js Dependencies (Website)
- **Website build dependencies** for documentation
- **Runtime dependencies** for the documentation system
- **Development dependencies** for the build process

### System Components
- **Operating system packages** detected in containers
- **Language runtimes** and interpreters
- **System libraries** and tools

## Using the SBOM

### Security Analysis
- **Vulnerability scanning** with tools like Grype, Trivy
- **Risk assessment** for known vulnerabilities
- **Impact analysis** for security updates

### Compliance Management
- **License tracking** for legal compliance
- **Component approval** workflows
- **Audit documentation** for regulatory requirements

### Supply Chain Security
- **Component provenance** tracking
- **Supply chain risk** assessment
- **Third-party dependency** monitoring

## SBOM Automation

The SBOM generation is fully automated:

1. **Triggered automatically** during documentation builds
2. **Version-specific generation** when creating releases  
3. **Multiple format output** for different tools and use cases
4. **Documentation integration** for transparency and access

## Accessing SBOM Data

When the documentation builds, SBOM files will be available:
- In the security section of the documentation
- As downloadable artifacts from GitHub Actions
- In version-specific directories for historical tracking
- In multiple formats for different analysis tools

---

*The SBOM is a critical component of InvenTag's security and compliance posture, providing complete transparency into all software components and dependencies.*