---
title: BOM Data Processor
description: Data processing pipeline and BOM generation architecture
sidebar_position: 5
---

# 📊 InvenTag BOM Data Processor

The BOM Data Processor is InvenTag's central orchestrator for processing raw inventory data and coordinating with specialized analyzers to produce enriched, analysis-ready datasets. It serves as the unified processing pipeline that transforms raw AWS resource data into comprehensive Bill of Materials (BOM) reports with deep analysis and insights.

## 📋 Overview

The BOM Data Processor consists of three main components:

- **BOMDataProcessor**: Central orchestrator that coordinates all processing activities
- **BOMProcessingConfig**: Configuration dataclass for customizing processing behavior
- **BOMData**: Structured output containing enriched resources and analysis results

## 🏗️ Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   BOMDataProcessor  │    │  Analysis Components │    │    BOMData Output   │
│                     │    │                     │    │                     │
│ • Data Extraction   │───▶│ • NetworkAnalyzer   │───▶│ • Enriched Resources│
│ • Resource Cleanup  │    │ • SecurityAnalyzer  │    │ • Network Analysis  │
│ • Orchestration     │    │ • ServiceEnricher   │    │ • Security Analysis │
│ • Error Handling    │    │ • DescriptionMgr    │    │ • Compliance Summary│
│ • Statistics        │    │ • TagMappingEngine  │    │ • Processing Stats  │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## 🔧 Core Components

### BOMProcessingConfig

Configuration dataclass that controls all aspects of the processing pipeline:

```python
from inventag.reporting.bom_processor import BOMProcessingConfig

# Default configuration with all features enabled
config = BOMProcessingConfig()

# Custom configuration for specific use cases
config = BOMProcessingConfig(
    enable_network_analysis=True,
    enable_security_analysis=True,
    enable_service_enrichment=True,
    enable_service_descriptions=True,
    enable_tag_mapping=True,
    enable_parallel_processing=True,
    max_worker_threads=4,
    cache_results=True,
    processing_timeout=300,
    service_descriptions_config='config/service_descriptions.yaml',
    tag_mappings_config='config/tag_mappings.yaml'
)
```

#### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_network_analysis` | bool | True | Enable VPC/subnet network analysis |
| `enable_security_analysis` | bool | True | Enable security posture assessment |
| `enable_service_enrichment` | bool | True | Enable deep service attribute extraction |
| `enable_service_descriptions` | bool | True | Enable intelligent resource descriptions |
| `enable_tag_mapping` | bool | True | Enable tag transformation and mapping |
| `enable_parallel_processing` | bool | True | Enable multi-threaded processing |
| `max_worker_threads` | int | 4 | Maximum number of worker threads |
| `cache_results` | bool | True | Enable result caching for performance |
| `service_descriptions_config` | str | None | Path to service descriptions config file |
| `tag_mappings_config` | str | None | Path to tag mappings config file |
| `processing_timeout` | int | 300 | Processing timeout in seconds |

### BOMData

Structured output containing all processed data and analysis results:

```python
from inventag.reporting.bom_processor import BOMData

# Access processed data
bom_data = processor.process_inventory_data(resources)

# Enriched resources with all analysis applied
enriched_resources = bom_data.resources

# Network analysis results
network_summary = bom_data.network_analysis
print(f"Total VPCs: {network_summary.get('total_vpcs', 0)}")
print(f"Total Subnets: {network_summary.get('total_subnets', 0)}")

# Security analysis results
security_summary = bom_data.security_analysis
print(f"Security Groups: {security_summary.get('total_security_groups', 0)}")
print(f"High Risk Rules: {security_summary.get('high_risk_rules', 0)}")

# Compliance summary
compliance = bom_data.compliance_summary
print(f"Compliance Rate: {compliance.get('compliance_percentage', 0):.1f}%")

# Processing metadata
metadata = bom_data.generation_metadata
print(f"Generated at: {metadata.get('generated_at')}")
print(f"Processing time: {metadata.get('processing_time_seconds', 0):.2f}s")
```

#### BOMData Structure

| Field | Type | Description |
|-------|------|-------------|
| `resources` | List[Dict] | Enriched and processed resources |
| `network_analysis` | Dict | Network analysis results and summaries |
| `security_analysis` | Dict | Security analysis results and findings |
| `compliance_summary` | Dict | Compliance statistics and violations |
| `generation_metadata` | Dict | Processing metadata and timestamps |
| `custom_attributes` | List[str] | List of discovered custom attributes |
| `processing_statistics` | Dict | Detailed processing statistics |
| `error_summary` | Dict | Error and warning summaries |

### ProcessingStatistics

Detailed statistics about the processing operation:

```python
from inventag.reporting.bom_processor import ProcessingStatistics

# Get processing statistics
stats = processor.get_processing_statistics()

print(f"Total Resources: {stats.total_resources}")
print(f"Successfully Processed: {stats.processed_resources}")
print(f"Failed Processing: {stats.failed_resources}")
print(f"Network Enriched: {stats.network_enriched}")
print(f"Security Enriched: {stats.security_enriched}")
print(f"Service Enriched: {stats.service_enriched}")
print(f"Description Enriched: {stats.description_enriched}")
print(f"Tag Mapped: {stats.tag_mapped}")
print(f"Processing Time: {stats.processing_time_seconds:.2f} seconds")

# Handle errors and warnings
if stats.errors:
    print(f"Errors: {len(stats.errors)}")
    for error in stats.errors:
        print(f"  - {error}")

if stats.warnings:
    print(f"Warnings: {len(stats.warnings)}")
    for warning in stats.warnings:
        print(f"  - {warning}")
```

## 🔄 Data Processing Pipeline

The BOM Data Processor follows a comprehensive 8-stage processing pipeline:

### Stage 1: Data Extraction
Intelligently extracts resources from various input formats:

- **Direct Resource Lists**: Simple list of resource dictionaries
- **Container Formats**: Inventory data with `all_discovered_resources` wrapper
- **Compliance Formats**: Compliance checker output with separate resource categories
- **Custom Formats**: Flexible extraction from unknown data structures

```python
# Handles multiple input formats automatically
inventory_format = {"all_discovered_resources": resources}
compliance_format = {
    "compliant_resources": compliant_resources,
    "non_compliant_resources": non_compliant_resources
}
direct_format = resources  # Direct list

# All formats processed seamlessly
bom_data = processor.process_inventory_data(any_format)
```

### Stage 2: Resource Standardization
Normalizes resource data structure and attributes:

- **Service Name Standardization**: Converts service names to consistent format
- **Resource Type Fixes**: Standardizes resource type naming conventions
- **ID Extraction**: Extracts resource IDs from ARNs when missing
- **Account ID Population**: Extracts account IDs from ARNs
- **Field Normalization**: Ensures consistent field naming and structure

```python
# Before standardization
resource = {
    "service": "CloudFormation",  # Inconsistent naming
    "type": "LoadBalancer",       # Needs hyphenation
    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
    # Missing id and account_id fields
}

# After standardization
resource = {
    "service": "CLOUDFORMATION",  # Standardized
    "type": "Load-Balancer",      # Fixed naming
    "id": "i-1234567890abcdef0",  # Extracted from ARN
    "account_id": "123456789012", # Extracted from ARN
    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
}
```

### Stage 3: Service Reclassification
Intelligently reclassifies VPC-related resources for better organization:

```python
# VPC-related resources are reclassified from EC2 to VPC service
vpc_resources = ["VPC", "Subnet", "SecurityGroup", "NetworkAcl", "InternetGateway", "NatGateway"]

# Before reclassification
ec2_resources = [
    {"service": "EC2", "type": "VPC", "id": "vpc-123"},
    {"service": "EC2", "type": "Subnet", "id": "subnet-123"},
    {"service": "EC2", "type": "SecurityGroup", "id": "sg-123"}
]

# After reclassification
vpc_service_resources = [
    {"service": "VPC", "type": "VPC", "id": "vpc-123"},
    {"service": "VPC", "type": "Subnet", "id": "subnet-123"},
    {"service": "VPC", "type": "SecurityGroup", "id": "sg-123"}
]
```

### Stage 4: Data Cleaning
Fixes common data issues and inconsistencies:

- **Missing ID Fields**: Extracts IDs from ARNs using intelligent parsing
- **Account ID Population**: Ensures all resources have account_id field
- **Name Field Generation**: Creates name fields from tags or IDs when missing
- **Region Validation**: Validates and standardizes region information

### Stage 5: Deduplication
Advanced deduplication with preference for more complete resource records:

```python
# Duplicate resources with different completeness levels
resources = [
    {
        "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
        "id": "i-123",
        "name": "instance-1"
    },
    {
        "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
        "id": "i-123",
        "name": "instance-1",
        "service_attributes": {...},  # More complete record
        "tags": {...}
    }
]

# Deduplication keeps the more complete record
deduplicated = [
    {
        "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-123",
        "id": "i-123",
        "name": "instance-1",
        "service_attributes": {...},  # Preserved
        "tags": {...}
    }
]
```

### Stage 6: Analysis Coordination
Orchestrates multiple analysis components based on configuration:

#### Network Analysis
```python
if config.enable_network_analysis:
    # Enrich resources with network information
    for resource in resources:
        enriched_resource = network_analyzer.enrich_resource_with_network_info(resource)
    
    # Generate network summary
    network_summary = network_analyzer.generate_network_summary(resources)
```

#### Security Analysis
```python
if config.enable_security_analysis:
    # Enrich resources with security information
    for resource in resources:
        enriched_resource = security_analyzer.enrich_resource_with_security_info(resource)
    
    # Generate security summary
    security_summary = security_analyzer.generate_security_summary(resources)
```

#### Service Enrichment
```python
if config.enable_service_enrichment:
    # Deep attribute extraction for each resource
    for resource in resources:
        enriched_resource = service_enricher.enrich_resource(resource)
```

#### Service Descriptions
```python
if config.enable_service_descriptions:
    # Apply intelligent descriptions
    for resource in resources:
        described_resource = service_desc_manager.apply_description_to_resource(resource)
```

#### Tag Mapping
```python
if config.enable_tag_mapping:
    # Apply tag transformations and mappings
    for resource in resources:
        mapped_resource = tag_mapping_engine.apply_mappings_to_resource(resource)
```

### Stage 7: Result Aggregation
Combines analysis results into comprehensive BOM data:

```python
# Aggregate all analysis results
bom_data = BOMData(
    resources=processed_resources,
    network_analysis=network_summary,
    security_analysis=security_summary,
    compliance_summary=compliance_summary,
    generation_metadata=processing_metadata,
    custom_attributes=extracted_attributes,
    processing_statistics=processing_stats,
    error_summary=error_summary
)
```

### Stage 8: Metadata Generation
Creates comprehensive processing metadata and statistics:

```python
# Processing metadata includes
metadata = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "processing_version": "1.0",
    "total_resources": len(resources),
    "processing_time_seconds": processing_time,
    "configuration": config_summary,
    "processing_statistics": detailed_stats
}
```

## 🛠️ Usage Patterns

### Basic Processing

```python
from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig
import boto3

# Initialize with default configuration
config = BOMProcessingConfig()
processor = BOMDataProcessor(config, boto3.Session())

# Process inventory data
bom_data = processor.process_inventory_data(resources)

# Access results
print(f"Processed {len(bom_data.resources)} resources")
print(f"Network Analysis: {bom_data.network_analysis}")
print(f"Security Analysis: {bom_data.security_analysis}")
```

### Selective Analysis

```python
# Network-focused analysis only
network_config = BOMProcessingConfig(
    enable_network_analysis=True,
    enable_security_analysis=False,
    enable_service_enrichment=False,
    enable_service_descriptions=False,
    enable_tag_mapping=False
)

processor = BOMDataProcessor(network_config, session)
bom_data = processor.process_inventory_data(resources)

# Only network analysis will be performed
network_summary = bom_data.network_analysis
print(f"VPC Count: {network_summary.get('total_vpcs', 0)}")
print(f"Subnet Utilization: {network_summary.get('average_utilization', 0):.1f}%")
```

### Performance Optimization

```python
# High-performance configuration for large datasets
performance_config = BOMProcessingConfig(
    enable_parallel_processing=True,
    max_worker_threads=8,
    cache_results=True,
    processing_timeout=600
)

processor = BOMDataProcessor(performance_config, session)

# Monitor processing performance
import time
start_time = time.time()
bom_data = processor.process_inventory_data(large_dataset)
processing_time = time.time() - start_time

stats = processor.get_processing_statistics()
print(f"Processing completed in {processing_time:.2f} seconds")
print(f"Throughput: {stats.processed_resources / processing_time:.1f} resources/second")
```

### Custom Configuration Files

```python
# Use custom configuration files
config = BOMProcessingConfig(
    enable_service_descriptions=True,
    enable_tag_mapping=True,
    service_descriptions_config='config/custom_descriptions.yaml',
    tag_mappings_config='config/custom_tag_mappings.yaml'
)

processor = BOMDataProcessor(config, session)
bom_data = processor.process_inventory_data(resources)

# Resources will have custom descriptions and tag mappings applied
for resource in bom_data.resources:
    if 'service_description' in resource:
        print(f"{resource['id']}: {resource['service_description']}")
```

## 🎯 Integration Patterns

### With Resource Discovery

```python
from inventag import AWSResourceInventory
from inventag.reporting.bom_processor import BOMDataProcessor, BOMProcessingConfig

# Discover resources
inventory = AWSResourceInventory(regions=['us-east-1', 'us-west-2'])
raw_resources = inventory.discover_resources()

# Process with comprehensive analysis
config = BOMProcessingConfig(
    enable_network_analysis=True,
    enable_security_analysis=True,
    enable_service_enrichment=True,
    enable_service_descriptions=True,
    enable_tag_mapping=True
)

processor = BOMDataProcessor(config, inventory.session)
bom_data = processor.process_inventory_data(raw_resources)

# Access comprehensive analysis results
print(f"Discovered and processed {len(bom_data.resources)} resources")
print(f"Network Summary: {bom_data.network_analysis}")
print(f"Security Summary: {bom_data.security_analysis}")
```

### With State Management

```python
from inventag.state import StateManager

# Process and save enriched state
state_manager = StateManager()
bom_data = processor.process_inventory_data(resources)

# Save comprehensive state with all analysis
state_id = state_manager.save_state(
    resources=bom_data.resources,
    account_id='123456789012',
    regions=['us-east-1', 'us-west-2'],
    network_analysis=bom_data.network_analysis,
    security_analysis=bom_data.security_analysis,
    compliance_data=bom_data.compliance_summary,
    tags={'processing': 'bom_processor', 'version': '1.0'}
)

print(f"Saved enriched state: {state_id}")
```

### With Compliance Checking

```python
from inventag.compliance import ComprehensiveTagComplianceChecker

# Process resources first
bom_data = processor.process_inventory_data(resources)

# Enhanced compliance checking with enriched data
checker = ComprehensiveTagComplianceChecker(
    regions=['us-east-1', 'us-west-2'],
    config_file='config/tag_policy.yaml'
)

compliance_results = checker.check_compliance(bom_data.resources)

# Combine with BOM analysis for comprehensive reporting
enhanced_bom = BOMData(
    resources=bom_data.resources,
    network_analysis=bom_data.network_analysis,
    security_analysis=bom_data.security_analysis,
    compliance_summary=compliance_results['summary'],
    generation_metadata=bom_data.generation_metadata
)
```

### With BOM Converter

```python
from inventag.reporting import BOMConverter

# Process data with BOM processor
bom_data = processor.process_inventory_data(resources)

# Convert to Excel with enriched data
converter = BOMConverter(enrich_vpc_info=False)  # VPC info already enriched
converter.data = bom_data.resources

# Export with comprehensive analysis
converter.export_to_excel('comprehensive_bom_report.xlsx')

# Include analysis summaries in metadata sheet
analysis_summary = {
    'Network Analysis': bom_data.network_analysis,
    'Security Analysis': bom_data.security_analysis,
    'Compliance Summary': bom_data.compliance_summary,
    'Processing Statistics': bom_data.processing_statistics
}
```

## 🔒 Error Handling and Recovery

### Comprehensive Error Handling

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

### Graceful Degradation

The processor is designed to handle component failures gracefully:

```python
# If network analysis fails, other components continue
try:
    bom_data = processor.process_inventory_data(resources)
    
    # Check which components succeeded
    if bom_data.network_analysis:
        print("Network analysis completed successfully")
    else:
        print("Network analysis failed - check error summary")
    
    if bom_data.security_analysis:
        print("Security analysis completed successfully")
    else:
        print("Security analysis failed - check error summary")
        
    # Resources are still processed even if some analysis fails
    print(f"Successfully processed {len(bom_data.resources)} resources")
    
except Exception as e:
    print(f"Critical processing failure: {e}")
```

### Partial Processing Recovery

```python
# Handle partial processing failures
def process_with_recovery(processor, resources, max_retries=3):
    for attempt in range(max_retries):
        try:
            bom_data = processor.process_inventory_data(resources)
            
            # Check processing success rate
            stats = processor.get_processing_statistics()
            success_rate = stats.processed_resources / stats.total_resources
            
            if success_rate >= 0.9:  # 90% success threshold
                print(f"Processing successful: {success_rate:.1%} success rate")
                return bom_data
            else:
                print(f"Low success rate: {success_rate:.1%}, retrying...")
                processor.clear_cache()  # Clear cache for retry
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
    
    return None
```

## 📊 Performance Optimization

### Caching System

```python
# Enable result caching for improved performance
config = BOMProcessingConfig(
    cache_results=True,
    enable_parallel_processing=True
)

processor = BOMDataProcessor(config, session)

# First processing run - builds cache
bom_data1 = processor.process_inventory_data(resources)

# Subsequent runs use cached results for better performance
bom_data2 = processor.process_inventory_data(similar_resources)

# Clear cache when needed
processor.clear_cache()
```

### Parallel Processing

```python
# Configure parallel processing for large datasets
config = BOMProcessingConfig(
    enable_parallel_processing=True,
    max_worker_threads=8  # Adjust based on system capabilities
)

processor = BOMDataProcessor(config, session)

# Process large dataset with parallel workers
large_dataset = load_large_resource_dataset()
bom_data = processor.process_inventory_data(large_dataset)

# Monitor parallel processing performance
stats = processor.get_processing_statistics()
print(f"Parallel processing completed in {stats.processing_time_seconds:.2f}s")
print(f"Average throughput: {stats.processed_resources / stats.processing_time_seconds:.1f} resources/second")
```

### Memory Management

```python
# Process large datasets in batches to manage memory
def process_large_dataset_in_batches(processor, large_dataset, batch_size=1000):
    all_results = []
    
    for i in range(0, len(large_dataset), batch_size):
        batch = large_dataset[i:i + batch_size]
        print(f"Processing batch {i // batch_size + 1}: {len(batch)} resources")
        
        # Process batch
        bom_data = processor.process_inventory_data(batch)
        all_results.extend(bom_data.resources)
        
        # Clear cache between batches to manage memory
        processor.clear_cache()
    
    return all_results
```

## 🚨 Troubleshooting

### Common Issues

**Component Initialization Failures**
```python
try:
    processor = BOMDataProcessor(config, session)
except Exception as e:
    print(f"Component initialization failed: {e}")
    
    # Check AWS credentials and permissions
    try:
        session.client('ec2').describe_regions()
        print("AWS credentials are valid")
    except Exception as cred_error:
        print(f"AWS credential issue: {cred_error}")
```

**Processing Timeouts**
```python
# Increase timeout for large datasets
config = BOMProcessingConfig(
    processing_timeout=900,  # 15 minutes
    max_worker_threads=2     # Reduce threads to avoid resource contention
)

processor = BOMDataProcessor(config, session)
```

**Memory Issues**
```python
# Monitor memory usage during processing
import psutil
import os

def monitor_memory_usage():
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Current memory usage: {memory_mb:.1f} MB")

# Process with memory monitoring
monitor_memory_usage()
bom_data = processor.process_inventory_data(resources)
monitor_memory_usage()

# Clear cache if memory usage is high
if psutil.virtual_memory().percent > 80:
    processor.clear_cache()
```

**Analysis Component Failures**
```python
# Check which components are failing
bom_data = processor.process_inventory_data(resources)

if not bom_data.network_analysis:
    print("Network analysis failed - check network analyzer configuration")

if not bom_data.security_analysis:
    print("Security analysis failed - check security analyzer permissions")

if bom_data.error_summary.get('has_errors'):
    for error in bom_data.error_summary.get('errors', []):
        print(f"Error: {error}")
```

### Performance Issues

**Slow Processing**
```python
# Profile processing performance
import time

start_time = time.time()
bom_data = processor.process_inventory_data(resources)
total_time = time.time() - start_time

stats = processor.get_processing_statistics()
print(f"Processing Statistics:")
print(f"  Total time: {total_time:.2f}s")
print(f"  Resources processed: {stats.processed_resources}")
print(f"  Throughput: {stats.processed_resources / total_time:.1f} resources/second")

# Identify bottlenecks
if stats.network_enriched < stats.processed_resources:
    print("Network analysis may be a bottleneck")

if stats.service_enriched < stats.processed_resources:
    print("Service enrichment may be a bottleneck")
```

**High Memory Usage**
```python
# Optimize for memory usage
memory_optimized_config = BOMProcessingConfig(
    enable_parallel_processing=False,  # Reduce memory overhead
    cache_results=False,               # Disable caching
    max_worker_threads=1               # Single-threaded processing
)

processor = BOMDataProcessor(memory_optimized_config, session)
```

## 📈 Best Practices

### Configuration Management

1. **Use Environment-Specific Configs**: Create different configurations for development, staging, and production
2. **Enable Selective Analysis**: Only enable analysis components you need for better performance
3. **Configure Timeouts Appropriately**: Set realistic timeouts based on dataset size
4. **Use Configuration Files**: Store service descriptions and tag mappings in external files
5. **Monitor Resource Usage**: Track memory and CPU usage during processing

### Performance Optimization

1. **Enable Caching**: Use result caching for repeated processing operations
2. **Parallel Processing**: Enable parallel processing for large datasets
3. **Batch Processing**: Process large datasets in batches to manage memory
4. **Clear Caches**: Periodically clear caches to prevent memory issues
5. **Monitor Statistics**: Track processing statistics to identify bottlenecks

### Error Handling

1. **Graceful Degradation**: Design workflows to handle component failures gracefully
2. **Comprehensive Logging**: Log all errors and warnings for troubleshooting
3. **Retry Logic**: Implement retry logic for transient failures
4. **Partial Results**: Use partial results when complete processing fails
5. **Validation**: Validate input data before processing

### Integration Patterns

1. **Modular Design**: Use the processor as part of larger workflows
2. **State Management**: Combine with state management for change tracking
3. **Compliance Integration**: Enhance compliance checking with enriched data
4. **Export Integration**: Use processed data with BOM converters
5. **CI/CD Integration**: Integrate into automated compliance workflows

## 🎯 Interactive Demo

Explore the BOM Data Processor with a comprehensive interactive demo:

```bash
# Run the BOM processor demonstration
python examples/bom_processor_demo.py
```

The demo script provides:

- **Configuration Examples**: Different configuration patterns for various use cases
- **Processing Pipeline Walkthrough**: Step-by-step explanation of the processing stages
- **Analysis Component Integration**: How different analyzers work together
- **Performance Monitoring**: Real-time processing statistics and performance metrics
- **Error Handling Demonstration**: How the processor handles various error conditions
- **Integration Patterns**: Examples of using the processor with other InvenTag components

---

For more examples and advanced usage patterns, see the comprehensive test suite in `tests/unit/test_bom_processor.py` and the integration examples in the main documentation.
