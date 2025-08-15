---
title: Tag Compliance
description: Compliance checking framework and tag validation
sidebar_position: 8
---

# InvenTag Tag Compliance Checker

## Overview

The `ComprehensiveTagComplianceChecker` is InvenTag's enterprise-grade AWS resource tag compliance validation tool. It provides comprehensive resource discovery, tag policy validation, and integrated BOM (Bill of Materials) document generation capabilities.

## Key Features

- 🔍 **Comprehensive Resource Discovery** - Uses multiple discovery methods (Resource Groups Tagging API, AWS Config, service-specific APIs)
- 🏷️ **Tag Policy Validation** - Validates resources against organizational tagging policies
- 📊 **Integrated BOM Generation** - Seamlessly generates professional BOM documents from compliance results
- 📈 **Compliance Reporting** - Detailed compliance metrics and summaries
- ☁️ **Multi-Region Support** - Discovers resources across all AWS regions
- 🔄 **Multiple Output Formats** - Supports JSON, YAML, Excel, Word, and CSV outputs
- 📤 **S3 Integration** - Direct upload of compliance results to S3

## Basic Usage

### Initialize the Checker

```python
from inventag.compliance import ComprehensiveTagComplianceChecker

# Basic initialization
checker = ComprehensiveTagComplianceChecker()

# With specific regions and configuration
checker = ComprehensiveTagComplianceChecker(
    regions=['us-east-1', 'us-west-2', 'eu-west-1'],
    config_file='config/tag_policy_example.yaml'
)
```

### Run Compliance Check

```python
# Discover resources and check compliance
results = checker.check_compliance()

# View compliance summary
summary = results['summary']
print(f"Total Resources: {summary['total_resources']}")
print(f"Compliant: {summary['compliant_resources']}")
print(f"Non-Compliant: {summary['non_compliant_resources']}")
print(f"Untagged: {summary['untagged_resources']}")
print(f"Compliance Rate: {summary['compliance_percentage']:.1f}%")
```

### Generate BOM Documents

```python
# Generate BOM documents from compliance results
bom_results = checker.generate_bom_documents(
    output_formats=['excel', 'word', 'csv'],
    output_directory='compliance_reports',
    enable_security_analysis=True,
    enable_network_analysis=True
)

print(f"Generated {len(bom_results['generated_files'])} BOM documents:")
for file_path in bom_results['generated_files']:
    print(f"  - {file_path}")
```

## Configuration

### Tag Policy Configuration

Create a YAML or JSON configuration file defining your required tags:

```yaml
# tag_policy_example.yaml
required_tags:
  - key: "Environment"
    description: "Environment designation (dev, staging, prod)"
    required: true
  - key: "Owner"
    description: "Resource owner or team"
    required: true
  - key: "CostCenter"
    description: "Cost center for billing"
    required: true
  - key: "Project"
    description: "Project or application name"
    required: false

# Optional: Define allowed values for specific tags
tag_values:
  Environment:
    - "development"
    - "staging"
    - "production"
  
# Optional: Service-specific requirements
service_requirements:
  EC2:
    additional_required_tags:
      - "Backup"
      - "MaintenanceWindow"
  RDS:
    additional_required_tags:
      - "BackupRetention"
      - "MaintenanceWindow"
```

### JSON Configuration Format

```json
{
  "required_tags": [
    {
      "key": "Environment",
      "description": "Environment designation",
      "required": true
    },
    {
      "key": "Owner", 
      "description": "Resource owner",
      "required": true
    }
  ],
  "tag_values": {
    "Environment": ["dev", "staging", "prod"]
  }
}
```

## Advanced Usage

### Custom Resource Discovery

```python
# Discover resources first, then check compliance
resources = checker.discover_all_resources()
print(f"Discovered {len(resources)} resources")

# Check compliance on discovered resources
results = checker.check_compliance(resources)
```

### Detailed Compliance Analysis

```python
# Get detailed compliance results
results = checker.check_compliance()

# Analyze compliant resources
compliant_resources = results['compliant']
print(f"Compliant resources: {len(compliant_resources)}")

# Analyze non-compliant resources
non_compliant_resources = results['non_compliant']
for resource in non_compliant_resources:
    print(f"Resource: {resource['arn']}")
    print(f"Missing tags: {', '.join(resource['missing_tags'])}")

# Analyze untagged resources
untagged_resources = results['untagged']
print(f"Completely untagged resources: {len(untagged_resources)}")
```

### BOM Generation with Custom Configuration

```python
# Generate BOM with custom configurations
bom_results = checker.generate_bom_documents(
    output_formats=['excel', 'word'],
    output_directory='compliance_reports',
    service_descriptions_file='config/service_descriptions.yaml',
    tag_mappings_file='config/tag_mappings.yaml',
    enable_vpc_enrichment=True,
    enable_security_analysis=True,
    enable_network_analysis=True
)

# Check generation results
for format_type, result in bom_results['generation_results'].items():
    if result['success']:
        print(f"✅ {format_type.upper()}: {result['file']}")
    else:
        print(f"❌ {format_type.upper()}: {result['error']}")
```

## Resource Discovery Methods

The checker uses multiple discovery methods to ensure comprehensive coverage:

### 1. Resource Groups Tagging API
- Primary discovery method
- Discovers all taggable resources across services
- Provides tag information directly
- Supports pagination for large environments

### 2. AWS Config (when available)
- Supplementary discovery method
- Provides additional resource metadata
- Useful for resources not covered by RGT API

### 3. Service-Specific APIs
- Targeted discovery for specific services
- Provides detailed resource attributes
- Covers edge cases and special resource types

## Output Formats

### Compliance Results (JSON/YAML)

```json
{
  "compliant": [...],
  "non_compliant": [...],
  "untagged": [...],
  "summary": {
    "total_resources": 1250,
    "compliant_resources": 980,
    "non_compliant_resources": 200,
    "untagged_resources": 70,
    "compliance_percentage": 78.4,
    "check_timestamp": "2024-01-15T10:30:00Z"
  },
  "all_discovered_resources": [...]
}
```

### BOM Documents

#### Excel Format
- **Summary Dashboard**: Executive overview with charts and metrics
- **Compliance Overview**: Detailed compliance status by service
- **Service Sheets**: Separate sheets for each AWS service
- **Non-Compliant Resources**: Detailed view of compliance violations
- **Untagged Resources**: Resources without any tags

#### Word Format
- **Executive Summary**: High-level compliance overview
- **Detailed Analysis**: Service-by-service compliance breakdown
- **Recommendations**: Actionable compliance improvement suggestions
- **Appendices**: Technical details and resource listings

#### CSV Format
- **Flat Structure**: All resources in a single CSV file
- **Compliance Status**: Compliance status for each resource
- **Missing Tags**: List of missing required tags
- **Resource Details**: Complete resource metadata

## Integration Examples

### CI/CD Pipeline Integration

```python
#!/usr/bin/env python3
"""
CI/CD Compliance Check
"""
import sys
from inventag.compliance import ComprehensiveTagComplianceChecker

def main():
    # Initialize checker
    checker = ComprehensiveTagComplianceChecker(
        config_file='config/tag_policy.yaml'
    )
    
    # Run compliance check
    results = checker.check_compliance()
    
    # Check compliance threshold
    compliance_rate = results['summary']['compliance_percentage']
    threshold = 80.0  # Minimum 80% compliance required
    
    if compliance_rate < threshold:
        print(f"❌ Compliance check failed: {compliance_rate:.1f}% < {threshold}%")
        
        # Generate detailed report for investigation
        checker.generate_bom_documents(
            output_formats=['excel'],
            output_directory='compliance_reports'
        )
        
        sys.exit(1)
    else:
        print(f"✅ Compliance check passed: {compliance_rate:.1f}%")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

### Automated Reporting

```python
#!/usr/bin/env python3
"""
Daily Compliance Report Generation
"""
from inventag.compliance import ComprehensiveTagComplianceChecker
from datetime import datetime

def generate_daily_report():
    checker = ComprehensiveTagComplianceChecker(
        config_file='config/tag_policy.yaml'
    )
    
    # Run compliance check
    results = checker.check_compliance()
    
    # Generate comprehensive BOM reports
    timestamp = datetime.now().strftime("%Y%m%d")
    
    bom_results = checker.generate_bom_documents(
        output_formats=['excel', 'word'],
        output_directory=f'reports/{timestamp}',
        enable_security_analysis=True,
        enable_network_analysis=True
    )
    
    # Save compliance results
    checker.save_results(f'reports/{timestamp}/compliance_results.json')
    
    # Upload to S3 for archival
    checker.upload_to_s3(
        bucket_name='compliance-reports',
        key=f'daily-reports/{timestamp}/compliance_results.json'
    )
    
    print(f"Daily compliance report generated: {timestamp}")
    print(f"Compliance rate: {results['summary']['compliance_percentage']:.1f}%")

if __name__ == "__main__":
    generate_daily_report()
```

### Multi-Account Compliance

```python
#!/usr/bin/env python3
"""
Multi-Account Compliance Checking
"""
import boto3
from inventag.compliance import ComprehensiveTagComplianceChecker

def check_multi_account_compliance(account_configs):
    """
    Check compliance across multiple AWS accounts
    
    Args:
        account_configs: List of account configuration dictionaries
    """
    overall_results = {}
    
    for account_config in account_configs:
        account_id = account_config['account_id']
        role_arn = account_config['role_arn']
        
        print(f"Checking compliance for account: {account_id}")
        
        try:
            # Assume role for cross-account access
            sts = boto3.client('sts')
            assumed_role = sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName=f'InvenTagCompliance-{account_id}'
            )
            
            # Create session with assumed role credentials
            session = boto3.Session(
                aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
                aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
                aws_session_token=assumed_role['Credentials']['SessionToken']
            )
            
            # Initialize checker with assumed role session
            checker = ComprehensiveTagComplianceChecker(
                config_file='config/tag_policy.yaml'
            )
            checker.session = session
            
            # Run compliance check
            results = checker.check_compliance()
            overall_results[account_id] = results
            
            # Generate account-specific BOM
            checker.generate_bom_documents(
                output_formats=['excel'],
                output_directory=f'reports/account-{account_id}'
            )
            
            compliance_rate = results['summary']['compliance_percentage']
            print(f"  Account {account_id}: {compliance_rate:.1f}% compliant")
            
        except Exception as e:
            print(f"  Error checking account {account_id}: {e}")
            overall_results[account_id] = {'error': str(e)}
    
    return overall_results

# Example usage
account_configs = [
    {
        'account_id': '123456789012',
        'role_arn': 'arn:aws:iam::123456789012:role/InvenTagComplianceRole'
    },
    {
        'account_id': '123456789013', 
        'role_arn': 'arn:aws:iam::123456789013:role/InvenTagComplianceRole'
    }
]

results = check_multi_account_compliance(account_configs)
```

## Best Practices

### 1. Configuration Management
- **Version Control**: Store tag policies in version control
- **Environment-Specific**: Use different policies for dev/staging/prod
- **Regular Review**: Periodically review and update tag requirements

### 2. Compliance Monitoring
- **Regular Checks**: Run compliance checks daily or weekly
- **Threshold Alerts**: Set up alerts for compliance rate drops
- **Trend Analysis**: Monitor compliance trends over time

### 3. Resource Discovery
- **Region Coverage**: Ensure all relevant regions are included
- **Service Coverage**: Regularly review discovered services
- **Performance**: Monitor discovery performance and optimize as needed

### 4. BOM Generation
- **Format Selection**: Choose appropriate formats for different audiences
- **Customization**: Use service descriptions and tag mappings for clarity
- **Distribution**: Establish processes for report distribution and review

## Troubleshooting

### Common Issues

#### No Resources Discovered
```python
# Check if regions are accessible
checker = ComprehensiveTagComplianceChecker(regions=['us-east-1'])
resources = checker.discover_all_resources()

if not resources:
    print("No resources discovered. Check:")
    print("1. AWS credentials and permissions")
    print("2. Region accessibility")
    print("3. Resource Groups Tagging API permissions")
```

#### Low Compliance Rates
```python
# Analyze non-compliant resources
results = checker.check_compliance()
non_compliant = results['non_compliant']

# Group by missing tags
missing_tags_summary = {}
for resource in non_compliant:
    for tag in resource.get('missing_tags', []):
        missing_tags_summary[tag] = missing_tags_summary.get(tag, 0) + 1

print("Most commonly missing tags:")
for tag, count in sorted(missing_tags_summary.items(), key=lambda x: x[1], reverse=True):
    print(f"  {tag}: {count} resources")
```

#### BOM Generation Failures
```python
# Check BOM generation results
bom_results = checker.generate_bom_documents(['excel'])

for format_type, result in bom_results['generation_results'].items():
    if not result['success']:
        print(f"BOM generation failed for {format_type}: {result['error']}")
        
        # Common solutions:
        print("Possible solutions:")
        print("1. Check output directory permissions")
        print("2. Ensure required libraries are installed")
        print("3. Verify sufficient disk space")
```

### Performance Optimization

#### Large Environments
```python
# For large environments, consider region-specific checks
regions = ['us-east-1', 'us-west-2']  # Limit to active regions

checker = ComprehensiveTagComplianceChecker(regions=regions)

# Or process regions separately
for region in regions:
    regional_checker = ComprehensiveTagComplianceChecker(regions=[region])
    results = regional_checker.check_compliance()
    print(f"Region {region}: {results['summary']['compliance_percentage']:.1f}% compliant")
```

#### Memory Management
```python
# For very large resource sets, process in batches
checker = ComprehensiveTagComplianceChecker()

# Discover resources first
all_resources = checker.discover_all_resources()
print(f"Discovered {len(all_resources)} resources")

# Process in batches of 1000
batch_size = 1000
for i in range(0, len(all_resources), batch_size):
    batch = all_resources[i:i+batch_size]
    batch_results = checker.check_compliance(batch)
    print(f"Batch {i//batch_size + 1}: {batch_results['summary']['compliance_percentage']:.1f}% compliant")
```

## API Reference

### ComprehensiveTagComplianceChecker

#### Constructor
```python
ComprehensiveTagComplianceChecker(
    regions: Optional[List[str]] = None,
    config_file: Optional[str] = None
)
```

#### Methods

##### discover_all_resources()
```python
def discover_all_resources() -> List[Dict[str, Any]]
```
Discovers all AWS resources using multiple discovery methods.

##### check_compliance(resources=None)
```python
def check_compliance(resources: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]
```
Checks tag compliance for discovered resources.

##### generate_bom_documents()
```python
def generate_bom_documents(
    output_formats: List[str] = None,
    output_directory: str = "bom_output",
    service_descriptions_file: str = None,
    tag_mappings_file: str = None,
    enable_vpc_enrichment: bool = True,
    enable_security_analysis: bool = True,
    enable_network_analysis: bool = True
) -> Dict[str, Any]
```
Generates BOM documents from compliance results.

##### save_results()
```python
def save_results(filename: str, format_type: str = "json")
```
Saves compliance results to file.

##### upload_to_s3()
```python
def upload_to_s3(bucket_name: str, key: str, format_type: str = "json")
```
Uploads compliance results to S3.

## Migration from Legacy Scripts

If you're migrating from the legacy `scripts/tag_compliance_checker.py`, here's how to update your code:

### Before (Legacy Script)
```bash
python scripts/tag_compliance_checker.py --config config/tag_policy.yaml --s3-bucket my-bucket
```

### After (Unified Package)
```python
from inventag.compliance import ComprehensiveTagComplianceChecker

checker = ComprehensiveTagComplianceChecker(config_file='config/tag_policy.yaml')
results = checker.check_compliance()
checker.save_results('compliance_results.json')
checker.upload_to_s3('my-bucket', 'compliance/results.json')

# Bonus: Generate professional BOM documents
checker.generate_bom_documents(
    output_formats=['excel', 'word'],
    output_directory='reports'
)
```

The unified package provides the same functionality with additional features like integrated BOM generation, better error handling, and more flexible configuration options.
