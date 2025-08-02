# BOM Generation Migration Guide

This guide helps existing InvenTag users migrate to the new enhanced BOM generation capabilities while maintaining backward compatibility.

## Overview

The InvenTag BOM generation system has been significantly enhanced with new capabilities:

- **Integrated Compliance Workflow**: Generate BOM documents directly from compliance checking results
- **Advanced Network Analysis**: VPC/subnet utilization analysis with capacity planning
- **Security Analysis**: Security group risk assessment and permissive rule detection
- **Service-Specific Enrichment**: Automatic discovery and enrichment of AWS service attributes
- **Professional Document Generation**: Enhanced Excel reports with dedicated analysis sheets

## Migration Paths

### 1. Existing Compliance Checker Users

If you currently use `tag_compliance_checker.py`, you can now generate BOM documents as an optional step:

**Before (compliance only):**
```bash
python tag_compliance_checker.py --config tag_policy.yaml --output compliance_report.json
```

**After (compliance + BOM generation):**
```bash
python tag_compliance_checker.py --config tag_policy.yaml --output compliance_report.json --generate-bom --bom-formats excel word
```

**New Options:**
- `--generate-bom`: Enable BOM document generation after compliance analysis
- `--bom-formats`: Choose output formats (excel, word, csv)
- `--bom-output-dir`: Specify output directory for BOM documents
- `--service-descriptions`: Path to service descriptions configuration
- `--tag-mappings`: Path to tag mappings configuration
- `--disable-vpc-enrichment`: Disable VPC/subnet name enrichment
- `--disable-security-analysis`: Disable security group analysis
- `--disable-network-analysis`: Disable network capacity analysis

### 2. Existing BOM Converter Users

If you currently use `bom_converter.py`, you can enable advanced analysis features:

**Before (basic BOM conversion):**
```bash
python bom_converter.py --input inventory.json --output report.xlsx
```

**After (enhanced BOM with analysis):**
```bash
python bom_converter.py --input inventory.json --output report.xlsx --enable-advanced-analysis
```

**New Options:**
- `--enable-advanced-analysis`: Enable network and security analysis
- `--service-descriptions`: Path to service descriptions configuration
- `--tag-mappings`: Path to tag mappings configuration

### 3. New Unified CLI Users

For new workflows, use the unified `inventag` CLI:

```bash
# Generate comprehensive BOM with multi-account support
inventag --create-excel --create-word --accounts-file accounts.json

# Generate BOM with advanced analysis
inventag --create-excel --service-descriptions services.yaml --tag-mappings tags.yaml
```

## Backward Compatibility

### Existing Scripts Continue to Work

All existing scripts maintain their original interfaces and behavior:

- `tag_compliance_checker.py` - Works exactly as before
- `bom_converter.py` - Works exactly as before
- All CLI arguments and output formats remain unchanged

### Output Format Compatibility

- JSON/YAML compliance reports maintain the same structure
- Excel BOM reports maintain the same basic structure
- CSV exports maintain the same column structure

### Configuration File Compatibility

- Existing tag policy files work without changes
- Existing service description files work without changes
- Existing tag mapping files work without changes

## New Features Available

### 1. Integrated Compliance-to-BOM Workflow

Generate professional BOM documents directly from compliance results:

```bash
python tag_compliance_checker.py \
  --config tag_policy.yaml \
  --generate-bom \
  --bom-formats excel word \
  --service-descriptions services.yaml \
  --tag-mappings tags.yaml
```

### 2. Advanced Network Analysis

New Excel sheets with network insights:
- **Network Analysis Sheet**: VPC utilization, subnet capacity, IP allocation
- **Subnet Details**: Per-subnet utilization and availability zone mapping

### 3. Security Analysis

New Excel sheets with security insights:
- **Security Analysis Sheet**: Security group risk assessment
- **Detailed Security Rules**: Rule-by-rule analysis with risk ratings

### 4. Service-Specific Enrichment

Automatic enrichment with service-specific attributes:
- S3 bucket encryption, versioning, lifecycle policies
- RDS database configuration, backup settings
- Lambda function configuration, VPC settings
- And more...

## Configuration Examples

### Service Descriptions Configuration

Create `services.yaml`:
```yaml
EC2:
  default: "Amazon Elastic Compute Cloud - Virtual servers in the cloud"
  Instance: "Virtual machine instances providing scalable compute capacity"
  Volume: "Block storage volumes attached to EC2 instances"

S3:
  default: "Amazon Simple Storage Service - Object storage service"
  Bucket: "Container for objects stored in Amazon S3"

RDS:
  default: "Amazon Relational Database Service - Managed database service"
  DBInstance: "Managed database instance"
```

### Tag Mappings Configuration

Create `tags.yaml`:
```yaml
inventag:remarks:
  column_name: "Remarks"
  default_value: ""
  description: "Additional remarks about the resource"

inventag:costcenter:
  column_name: "Cost Center"
  default_value: "Unknown"
  description: "Cost center responsible for the resource"

inventag:owner:
  column_name: "Resource Owner"
  default_value: "Unassigned"
  description: "Person or team responsible for the resource"
```

## Best Practices for Migration

### 1. Gradual Migration

Start by adding BOM generation to your existing compliance workflow:

```bash
# Step 1: Test BOM generation alongside existing workflow
python tag_compliance_checker.py --config tag_policy.yaml --generate-bom --bom-formats excel

# Step 2: Add custom configurations
python tag_compliance_checker.py --config tag_policy.yaml --generate-bom --service-descriptions services.yaml

# Step 3: Enable advanced analysis
python tag_compliance_checker.py --config tag_policy.yaml --generate-bom --bom-formats excel word
```

### 2. Configuration Management

Organize your configuration files:
```
config/
├── tag_policy.yaml          # Compliance policy
├── service_descriptions.yaml # Service descriptions
├── tag_mappings.yaml        # Custom tag mappings
└── accounts.json           # Multi-account configuration
```

### 3. CI/CD Integration

Update your CI/CD pipelines to include BOM generation:

```yaml
# GitHub Actions example
- name: Run Compliance Check and Generate BOM
  run: |
    python tag_compliance_checker.py \
      --config config/tag_policy.yaml \
      --generate-bom \
      --bom-formats excel \
      --bom-output-dir reports/ \
      --service-descriptions config/service_descriptions.yaml
```

### 4. Testing Migration

Test the migration with a subset of your resources:

```bash
# Test with limited regions
python tag_compliance_checker.py \
  --config tag_policy.yaml \
  --regions us-east-1 \
  --generate-bom \
  --bom-formats excel

# Compare outputs
diff old_report.xlsx new_report.xlsx
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the unified `inventag` package is properly installed
2. **Missing Dependencies**: Install `openpyxl` for Excel generation
3. **Permission Issues**: Ensure AWS credentials have necessary read permissions
4. **Configuration Errors**: Validate YAML/JSON configuration files

### Getting Help

- Check the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
- Review [Configuration Examples](CONFIGURATION_EXAMPLES.md)
- See [CLI User Guide](CLI_USER_GUIDE.md) for detailed command reference

## Summary

The enhanced BOM generation system provides:

✅ **Full Backward Compatibility** - All existing scripts work unchanged
✅ **Seamless Integration** - Add BOM generation to existing workflows
✅ **Advanced Analysis** - Network and security insights
✅ **Professional Reports** - Enhanced Excel documents with multiple analysis sheets
✅ **Flexible Configuration** - Custom service descriptions and tag mappings
✅ **Migration Support** - Gradual migration path with comprehensive documentation

Start by adding `--generate-bom` to your existing compliance checker commands to begin using the new capabilities immediately.