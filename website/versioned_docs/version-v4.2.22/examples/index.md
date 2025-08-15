---
title: Configuration Examples
description: Example configuration files to help you get started with InvenTag
sidebar_position: 0
---

# 📋 InvenTag Configuration Examples

This section contains example configuration files to help you get started with InvenTag.

## 🔧 Wrapper Scripts

InvenTag provides wrapper scripts that automatically detect the best Python command:

- **`inventag.sh`** (Unix/Linux/macOS) - Auto-detects `python3` or `python`
- **`inventag.bat`** (Windows) - Auto-detects `python3`, `python`, or `py -3`

Both scripts require Python 3.8+ and will show helpful error messages if no suitable Python is found.

## Configuration Files

### `accounts-example.json`
Example multi-account configuration file showing how to configure multiple AWS accounts with different credential methods, regions, and services.

**Usage:**
```bash
./inventag.sh --accounts-file examples/accounts-example.json --create-excel
```

### `service-descriptions-example.yaml`
Example service descriptions configuration that customizes how AWS services and resources are described in BOM reports.

**Usage:**
```bash
./inventag.sh --create-excel --service-descriptions examples/service-descriptions-example.yaml
```

### `tag-mappings-example.yaml`
Example tag mappings configuration that maps AWS resource tags to custom columns in BOM reports.

**Usage:**
```bash
./inventag.sh --create-excel --tag-mappings examples/tag-mappings-example.yaml
```

## Complete Example

Use all configuration files together with comprehensive analysis:

```bash
./inventag.sh \
  --accounts-file examples/accounts-example.json \
  --service-descriptions examples/service-descriptions-example.yaml \
  --tag-mappings examples/tag-mappings-example.yaml \
  --create-excel --create-word --create-google-docs \
  --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
  --compliance-standard soc2 --security-validation \
  --verbose
```

## Multi-Region Examples

Override regions for all accounts:

```bash
# Scan specific regions across all accounts
./inventag.sh \
  --accounts-file examples/accounts-example.json \
  --account-regions us-east-1,us-west-2,ap-southeast-1,ap-north-1 \
  --create-excel

# Asia-Pacific focus with cost analysis
./inventag.sh \
  --accounts-file examples/accounts-example.json \
  --account-regions ap-southeast-1,ap-southeast-2,ap-north-1,ap-south-1 \
  --enable-cost-analysis --create-excel

# Global scan (all regions - default behavior)
./inventag.sh \
  --accounts-file examples/accounts-example.json \
  --create-excel --verbose
```

## Customization

## Download Example Files

All example configuration files are available in the centralized assets directory:

- [Account Configuration Example](/files/accounts-example.json)
- [Service Descriptions Example](/files/service-descriptions-example.yaml)
- [Tag Mappings Example](/files/tag-mappings-example.yaml)
- [Excel Template](/files/default_excel_template.json)
- [Word Template](/files/default_word_template.yaml)

Copy these example files and modify them for your environment:

```bash
# Copy examples to your config directory
cp docs/assets/files/accounts-example.json config/accounts.json
cp docs/assets/files/service-descriptions-example.yaml config/service-descriptions.yaml
cp docs/assets/files/tag-mappings-example.yaml config/tag-mappings.yaml

# Edit the files for your environment
# Then use them with production safety:
./inventag.sh \
  --accounts-file config/accounts.json \
  --service-descriptions config/service-descriptions.yaml \
  --tag-mappings config/tag-mappings.yaml \
  --create-excel --create-word \
  --enable-production-safety --security-validation
```

## Validation

Always validate your configuration files before use:

```bash
./inventag.sh \
  --accounts-file examples/accounts-example.json \
  --service-descriptions examples/service-descriptions-example.yaml \
  --tag-mappings examples/tag-mappings-example.yaml \
  --validate-config
```

## More Information

- [Quick Start Guide](../getting-started/quick-start)
- [Complete CLI User Guide](../user-guides/cli-user-guide)
- [Configuration Guide](../user-guides/configuration-examples)
