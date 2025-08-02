# Network Analysis & Capacity Planning

InvenTag's NetworkAnalyzer provides comprehensive VPC and subnet analysis for network visibility, capacity planning, and optimization recommendations. This module extracts and enhances the VPC enrichment functionality from the original BOM converter into a dedicated, powerful network analysis framework.

## 🌐 Overview

The NetworkAnalyzer module offers deep insights into your AWS network infrastructure by:

- **Analyzing VPC and subnet utilization** with real-time IP address tracking
- **Mapping resources to network context** for comprehensive visibility
- **Providing capacity planning insights** with utilization thresholds and warnings
- **Generating optimization recommendations** for cost savings and efficiency
- **Supporting multi-CIDR VPCs** with comprehensive IP calculations

## 🔧 Core Features

### VPC Analysis
- **Multi-CIDR Support**: Handles VPCs with multiple CIDR blocks
- **IP Utilization Tracking**: Real-time calculation of used vs. available IPs
- **Network Component Discovery**: Internet gateways, NAT gateways, VPC endpoints
- **Connectivity Mapping**: VPC peering connections and Transit Gateway attachments
- **Resource Association**: Automatic mapping of EC2, RDS, Lambda resources to VPCs

### Subnet Analysis
- **Detailed IP Utilization**: Per-subnet IP usage with percentage calculations
- **Availability Zone Distribution**: Multi-AZ subnet analysis
- **Public/Private Classification**: Route table analysis for subnet types
- **Capacity Planning**: Configurable utilization thresholds and alerts
- **Resource Mapping**: Direct association of resources to specific subnets

### Network Optimization
- **Capacity Warnings**: Configurable high-utilization alerts (default: 80% and 90%)
- **Unused Resource Detection**: Identification of VPCs and subnets with no associated resources
- **Consolidation Recommendations**: Suggestions for optimizing underutilized subnets
- **Cost Optimization**: NAT gateway and VPC endpoint recommendations

## 🛠️ Usage Examples

### Basic Network Analysis

```python
from inventag.discovery.network_analyzer import NetworkAnalyzer

# Initialize network analyzer
analyzer = NetworkAnalyzer()

# Analyze VPC resources from inventory
vpc_analysis = analyzer.analyze_vpc_resources(resources)

# Generate comprehensive network summary
network_summary = analyzer.generate_network_summary(vpc_analysis)

print(f"Total VPCs: {network_summary.total_vpcs}")
print(f"Total Subnets: {network_summary.total_subnets}")
print(f"Total Available IPs: {network_summary.total_available_ips}")
print(f"Highest Utilization: {network_summary.highest_utilization_percentage:.1f}%")
```

### Resource-to-Network Mapping

```python
# Map resources to their network context
enriched_resources = analyzer.map_resources_to_network(resources)

# Each resource now includes network context
for resource in enriched_resources:
    if 'vpc_name' in resource:
        print(f"Resource {resource['name']} is in VPC {resource['vpc_name']}")
        print(f"  VPC CIDR: {resource['vpc_cidr_block']}")
        print(f"  VPC Utilization: {resource['vpc_utilization_percentage']:.1f}%")
    
    if 'subnet_name' in resource:
        print(f"  Subnet: {resource['subnet_name']}")
        print(f"  Subnet CIDR: {resource['subnet_cidr_block']}")
        print(f"  Subnet Utilization: {resource['subnet_utilization_percentage']:.1f}%")
        print(f"  Public Subnet: {resource['subnet_is_public']}")
```

### Capacity Planning and Monitoring

```python
# Identify high-utilization subnets for capacity planning
for vpc_id, vpc in vpc_analysis.items():
    print(f"\nVPC: {vpc.vpc_name} ({vpc.vpc_id})")
    print(f"Overall Utilization: {vpc.utilization_percentage:.1f}%")
    
    for subnet in vpc.subnets:
        if subnet.utilization_percentage > 80:
            print(f"  ⚠️  HIGH UTILIZATION: {subnet.subnet_name}")
            print(f"      {subnet.utilization_percentage:.1f}% utilized")
            print(f"      {subnet.available_ips} IPs remaining")
            print(f"      Associated resources: {len(subnet.associated_resources)}")

# Check capacity warnings from network summary
if network_summary.capacity_warnings:
    print("\n🚨 CAPACITY WARNINGS:")
    for warning in network_summary.capacity_warnings:
        print(f"  • {warning}")

# Review optimization recommendations
if network_summary.optimization_recommendations:
    print("\n💡 OPTIMIZATION RECOMMENDATIONS:")
    for recommendation in network_summary.optimization_recommendations:
        print(f"  • {recommendation}")
```

### Cost Optimization Analysis

```python
# Find unused VPCs for potential cost savings
unused_vpcs = []
underutilized_subnets = []

for vpc in vpc_analysis.values():
    # Check for completely unused VPCs
    if not vpc.associated_resources:
        unused_vpcs.append(vpc)
    
    # Check for underutilized subnets
    for subnet in vpc.subnets:
        if subnet.utilization_percentage < 10 and subnet.associated_resources:
            underutilized_subnets.append(subnet)

print(f"Found {len(unused_vpcs)} unused VPCs")
print(f"Found {len(underutilized_subnets)} underutilized subnets")

# Analyze NAT gateway usage
for vpc in vpc_analysis.values():
    if not vpc.nat_gateways and len(vpc.subnets) > 1:
        private_subnets = [s for s in vpc.subnets if not s.is_public]
        if private_subnets:
            print(f"VPC {vpc.vpc_name} may benefit from NAT gateways")
```

### Network Security Assessment

```python
# Identify public subnets and their security implications
for vpc in vpc_analysis.values():
    public_subnets = [s for s in vpc.subnets if s.is_public]
    
    if public_subnets:
        print(f"\nVPC {vpc.vpc_name} has {len(public_subnets)} public subnets:")
        
        for subnet in public_subnets:
            print(f"  • {subnet.subnet_name} ({subnet.availability_zone})")
            print(f"    Resources: {len(subnet.associated_resources)}")
            
            # Check if public subnet has resources (potential security concern)
            if subnet.associated_resources:
                print(f"    ⚠️  Public subnet contains resources!")

# Check for internet gateway presence
vpcs_with_igw = [vpc for vpc in vpc_analysis.values() if vpc.internet_gateway_id]
print(f"\n{len(vpcs_with_igw)} VPCs have internet gateways")

# Analyze VPC connectivity
for vpc in vpc_analysis.values():
    connectivity = []
    if vpc.internet_gateway_id:
        connectivity.append("Internet Gateway")
    if vpc.nat_gateways:
        connectivity.append(f"{len(vpc.nat_gateways)} NAT Gateways")
    if vpc.vpc_endpoints:
        connectivity.append(f"{len(vpc.vpc_endpoints)} VPC Endpoints")
    if vpc.peering_connections:
        connectivity.append(f"{len(vpc.peering_connections)} Peering Connections")
    if vpc.transit_gateway_attachments:
        connectivity.append(f"{len(vpc.transit_gateway_attachments)} Transit Gateway Attachments")
    
    if connectivity:
        print(f"VPC {vpc.vpc_name}: {', '.join(connectivity)}")
```

## 📊 Data Structures

### VPCAnalysis
```python
@dataclass
class VPCAnalysis:
    vpc_id: str                           # VPC identifier
    vpc_name: str                         # VPC name from tags
    cidr_block: str                       # Primary CIDR block
    cidr_blocks: List[str]                # All CIDR blocks (multi-CIDR support)
    total_ips: int                        # Total IP addresses across all CIDRs
    available_ips: int                    # Available IP addresses
    utilization_percentage: float         # IP utilization percentage
    subnets: List[SubnetAnalysis]         # Associated subnets
    associated_resources: List[str]       # Resource IDs in this VPC
    internet_gateway_id: Optional[str]    # Internet gateway ID
    nat_gateways: List[str]              # NAT gateway IDs
    vpc_endpoints: List[str]             # VPC endpoint IDs
    peering_connections: List[str]       # VPC peering connection IDs
    transit_gateway_attachments: List[str] # Transit gateway attachment IDs
    tags: Dict[str, str]                 # VPC tags
```

### SubnetAnalysis
```python
@dataclass
class SubnetAnalysis:
    subnet_id: str                        # Subnet identifier
    subnet_name: str                      # Subnet name from tags
    cidr_block: str                       # Subnet CIDR block
    availability_zone: str                # Availability zone
    vpc_id: str                          # Parent VPC ID
    total_ips: int                       # Total IP addresses (minus AWS reserved)
    available_ips: int                   # Available IP addresses
    utilization_percentage: float        # IP utilization percentage
    associated_resources: List[str]      # Resource IDs in this subnet
    route_table_id: Optional[str]        # Associated route table
    is_public: bool                      # Public/private classification
    tags: Dict[str, str]                 # Subnet tags
```

### NetworkSummary
```python
@dataclass
class NetworkSummary:
    total_vpcs: int                           # Total number of VPCs
    total_subnets: int                        # Total number of subnets
    total_available_ips: int                  # Total available IP addresses
    highest_utilization_subnet: Optional[str] # Most utilized subnet
    highest_utilization_percentage: float     # Highest utilization percentage
    vpc_utilization_stats: Dict[str, float]   # Per-VPC utilization statistics
    capacity_warnings: List[str]              # Capacity warning messages
    optimization_recommendations: List[str]   # Optimization recommendations
```

## ⚙️ Configuration Options

### Utilization Thresholds

```python
# Initialize with custom thresholds
analyzer = NetworkAnalyzer()
analyzer.high_utilization_threshold = 75.0    # High utilization warning at 75%
analyzer.capacity_warning_threshold = 85.0    # Capacity warning at 85%
```

### Custom Session

```python
# Use custom boto3 session
import boto3
session = boto3.Session(profile_name='production')
analyzer = NetworkAnalyzer(session=session)
```

## 🔍 Advanced Features

### Multi-Region Analysis

```python
# Analyze resources across multiple regions
regions = ['us-east-1', 'us-west-2', 'eu-west-1']
all_vpc_analysis = {}

for region in regions:
    regional_resources = [r for r in resources if r.get('region') == region]
    regional_analysis = analyzer.analyze_vpc_resources(regional_resources)
    all_vpc_analysis[region] = regional_analysis

# Generate cross-region summary
total_vpcs = sum(len(analysis) for analysis in all_vpc_analysis.values())
print(f"Total VPCs across all regions: {total_vpcs}")
```

### Integration with State Management

```python
from inventag.state import StateManager

# Save network analysis with state
state_manager = StateManager()
state_id = state_manager.save_state(
    resources=enriched_resources,
    account_id='123456789012',
    regions=['us-east-1', 'us-west-2'],
    network_analysis={
        'vpc_analysis': {vpc_id: vpc.__dict__ for vpc_id, vpc in vpc_analysis.items()},
        'network_summary': network_summary.__dict__
    }
)
```

### Custom Resource Extraction

```python
# Override VPC/subnet ID extraction for custom resource formats
class CustomNetworkAnalyzer(NetworkAnalyzer):
    def _extract_vpc_id(self, resource):
        # Custom logic for extracting VPC ID
        if 'custom_vpc_field' in resource:
            return resource['custom_vpc_field']
        return super()._extract_vpc_id(resource)
    
    def _extract_subnet_id(self, resource):
        # Custom logic for extracting subnet ID
        if 'custom_subnet_field' in resource:
            return resource['custom_subnet_field']
        return super()._extract_subnet_id(resource)
```

## 🚀 Performance Considerations

### Caching
The NetworkAnalyzer caches VPC and subnet information to avoid repeated API calls:

```python
# Cache is automatically managed, but you can access it
print(f"Cached VPCs: {len(analyzer.vpc_cache)}")
print(f"Cached Subnets: {len(analyzer.subnet_cache)}")
```

### Batch Processing
For large inventories, process resources in batches:

```python
batch_size = 1000
for i in range(0, len(resources), batch_size):
    batch = resources[i:i + batch_size]
    batch_analysis = analyzer.analyze_vpc_resources(batch)
    # Process batch results
```

## 🔗 Integration Examples

### With Service Enrichment

```python
from inventag.discovery.service_enrichment import ServiceAttributeEnricher

# Combine service enrichment with network analysis
enricher = ServiceAttributeEnricher()
service_enriched = enricher.enrich_resources_with_attributes(resources)

analyzer = NetworkAnalyzer()
network_enriched = analyzer.map_resources_to_network(service_enriched)

# Now resources have both service attributes and network context
```

### With BOM Converter

```python
from inventag.reporting import BOMConverter

# Use network-enriched resources in BOM generation
converter = BOMConverter(enrich_vpc_info=True)
converter.data = network_enriched_resources
converter.export_to_excel('network_enriched_bom.xlsx')
```

### With Compliance Checking

```python
from inventag.compliance import ComprehensiveTagComplianceChecker

# Check compliance on network-enriched resources
checker = ComprehensiveTagComplianceChecker(config_file='network_policy.yaml')
compliance_results = checker.check_compliance(network_enriched_resources)

# Analyze compliance by network context
for resource in compliance_results['non_compliant_resources']:
    if 'vpc_name' in resource:
        print(f"Non-compliant resource in VPC {resource['vpc_name']}")
```

## 📈 Monitoring and Alerting

### Capacity Monitoring

```python
def monitor_network_capacity(resources, alert_threshold=85.0):
    analyzer = NetworkAnalyzer()
    vpc_analysis = analyzer.analyze_vpc_resources(resources)
    
    alerts = []
    for vpc in vpc_analysis.values():
        if vpc.utilization_percentage > alert_threshold:
            alerts.append(f"VPC {vpc.vpc_name} at {vpc.utilization_percentage:.1f}% capacity")
        
        for subnet in vpc.subnets:
            if subnet.utilization_percentage > alert_threshold:
                alerts.append(f"Subnet {subnet.subnet_name} at {subnet.utilization_percentage:.1f}% capacity")
    
    return alerts

# Use in monitoring system
alerts = monitor_network_capacity(resources)
if alerts:
    # Send to monitoring system
    for alert in alerts:
        print(f"ALERT: {alert}")
```

### Cost Optimization Tracking

```python
def track_optimization_opportunities(resources):
    analyzer = NetworkAnalyzer()
    vpc_analysis = analyzer.analyze_vpc_resources(resources)
    network_summary = analyzer.generate_network_summary(vpc_analysis)
    
    opportunities = {
        'unused_vpcs': len([vpc for vpc in vpc_analysis.values() if not vpc.associated_resources]),
        'underutilized_subnets': len([
            subnet for vpc in vpc_analysis.values() 
            for subnet in vpc.subnets 
            if subnet.utilization_percentage < 10 and subnet.associated_resources
        ]),
        'optimization_recommendations': len(network_summary.optimization_recommendations)
    }
    
    return opportunities

# Track over time
opportunities = track_optimization_opportunities(resources)
print(f"Cost optimization opportunities: {opportunities}")
```

## 🛡️ Security Considerations

The NetworkAnalyzer follows the same security principles as the rest of InvenTag:

- **Read-Only Operations**: Only uses describe/list AWS API operations
- **No Resource Modification**: Cannot modify any AWS resources
- **Minimal Permissions**: Requires only EC2 read permissions
- **Safe for Production**: Designed for safe execution in production environments

### Required IAM Permissions

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeInternetGateways",
                "ec2:DescribeNatGateways",
                "ec2:DescribeVpcEndpoints",
                "ec2:DescribeVpcPeeringConnections",
                "ec2:DescribeTransitGatewayAttachments",
                "ec2:DescribeRouteTables"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🔧 Troubleshooting

### Common Issues

**No VPC information found**
- Ensure resources contain VPC ID fields (`vpc_id`, `VpcId`, or in ARN)
- Check that EC2 permissions are properly configured
- Verify resources are from regions where VPCs exist

**Incorrect utilization calculations**
- AWS reserves 5 IP addresses per subnet (first 4 and last 1)
- Utilization is calculated as: `(total_ips - available_ips) / total_ips * 100`
- Multi-CIDR VPCs sum IP addresses across all CIDR blocks

**Missing network components**
- Some components (Transit Gateway) may not be available in all regions
- VPC endpoints and peering connections require appropriate permissions
- Route table analysis for public/private classification may be simplified

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug logging for detailed analysis
analyzer = NetworkAnalyzer()
vpc_analysis = analyzer.analyze_vpc_resources(resources)
```

## 📚 Related Documentation

- [Service Enrichment Guide](SERVICE_ENRICHMENT.md) - Deep service attribute extraction
- [State Management Guide](STATE_MANAGEMENT.md) - Tracking changes over time
- [Security Guide](SECURITY.md) - Security considerations and permissions
- [BOM Converter Documentation](../scripts/README.md) - Professional reporting integration