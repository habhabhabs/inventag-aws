# 📋 InvenTag Configuration Examples

This directory contains example configuration files to help you get started with InvenTag.

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

## Demo Scripts

### `demo_document_generation.py`
Comprehensive demonstration of the InvenTag document generation system, showing:
- DocumentGenerator orchestration layer
- ExcelWorkbookBuilder for Excel BOM generation  
- WordDocumentBuilder for Word document generation
- Professional formatting and branding configuration
- Complete workflow from data creation to document output

**Usage:**
```bash
cd examples
python demo_document_generation.py
```

### `demo_integration_workflow.py`
End-to-end demonstration of the integrated compliance checking and BOM generation workflow:
- Tag compliance analysis with policy validation
- Resource compliance status assessment
- Automated BOM document generation from compliance results
- Enhanced reporting with service-specific analysis

**Usage:**
```bash
cd examples  
python demo_integration_workflow.py
```

### Other Demo Scripts
The examples directory also contains specialized demo scripts for specific features:
- `bom_processor_demo.py` - BOM data processing
- `changelog_generator_demo.py` - Change tracking
- `cost_analysis_demo.py` - Cost analysis features
- `network_security_analysis_demo.py` - Network security analysis
- `production_safety_demo.py` - Production safety features
- `service_enrichment_demo.py` - Service enrichment capabilities
- `state_manager_demo.py` - State management

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

Copy these example files and modify them for your environment:

```bash
# Copy examples to your config directory
cp examples/accounts-example.json config/accounts.json
cp examples/service-descriptions-example.yaml config/service-descriptions.yaml
cp examples/tag-mappings-example.yaml config/tag-mappings.yaml

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

- [Quick Start Guide](../QUICKSTART.md)
- [Complete CLI User Guide](../docs/user-guides/CLI_USER_GUIDE.md)
- [Configuration Guide](../docs/user-guides/CONFIGURATION_EXAMPLES.md)