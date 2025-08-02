# Cost Analysis & Optimization

The InvenTag Cost Analyzer provides comprehensive cost estimation, forgotten resource detection, and optimization recommendations for AWS resources using the AWS Pricing API and CloudWatch metrics.

## Overview

The Cost Analyzer helps organizations:
- **Estimate Resource Costs**: Calculate monthly costs using AWS Pricing API
- **Identify Expensive Resources**: Find resources exceeding cost thresholds
- **Detect Forgotten Resources**: Identify unused resources based on activity patterns
- **Analyze Cost Trends**: Track cost changes over time with alerting
- **Generate Optimization Recommendations**: Provide actionable cost reduction strategies

## Key Features

### 🔍 **Resource Cost Estimation**
- **AWS Pricing API Integration**: Real-time pricing data for accurate estimates
- **Service-Specific Calculations**: Tailored cost models for EC2, RDS, S3, Lambda, and more
- **Multi-Pricing Model Support**: On-demand, reserved, and spot pricing considerations
- **Confidence Levels**: Reliability indicators for cost estimates
- **Cost Breakdown Analysis**: Detailed component-level cost attribution

### 💰 **Expensive Resource Identification**
- **Configurable Thresholds**: Customizable cost thresholds per organization
- **Service-Specific Analysis**: Different thresholds for different AWS services
- **Cost Ranking**: Resources sorted by estimated monthly cost
- **Impact Assessment**: Potential savings from optimization actions

### 🔍 **Forgotten Resource Detection**
- **Activity Pattern Analysis**: CloudWatch metrics-based activity detection
- **Multi-Metric Evaluation**: CPU, network, database connections, S3 requests
- **Configurable Inactivity Periods**: Customizable thresholds for "forgotten" classification
- **Risk Level Assessment**: High, medium, low risk categorization
- **Automated Recommendations**: Specific actions for each forgotten resource

### 📈 **Cost Trend Analysis**
- **Historical Cost Tracking**: Integration with AWS Cost Explorer
- **Trend Direction Detection**: Increasing, decreasing, or stable cost patterns
- **Alert Generation**: Notifications for significant cost changes
- **Service-Level Trends**: Cost analysis grouped by AWS service
- **Percentage Change Calculations**: Quantified cost impact analysis

### 🎯 **Optimization Recommendations**
- **Rightsizing Suggestions**: Instance type optimization recommendations
- **Underutilization Detection**: Resources with low utilization patterns
- **Reserved Instance Analysis**: Opportunities for reserved pricing
- **Storage Class Optimization**: S3 storage class recommendations
- **Implementation Effort Assessment**: Easy, medium, hard implementation categories

## Configuration

### Cost Thresholds

Configure cost analysis thresholds to match your organization's requirements:

```python
from inventag.discovery.cost_analyzer import CostThresholds

# Custom thresholds
thresholds = CostThresholds(
    expensive_resource_monthly_threshold=Decimal('200.00'),  # $200/month
    forgotten_resource_days_threshold=45,                    # 45 days inactive
    high_cost_alert_threshold=Decimal('2000.00'),           # $2000/month
    cost_trend_alert_percentage=30.0,                       # 30% change
    unused_resource_utilization_threshold=10.0              # 10% utilization
)
```

### Threshold Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `expensive_resource_monthly_threshold` | $100.00 | Monthly cost threshold for "expensive" classification |
| `forgotten_resource_days_threshold` | 30 days | Days of inactivity before "forgotten" classification |
| `high_cost_alert_threshold` | $1000.00 | Monthly cost threshold for high-priority alerts |
| `cost_trend_alert_percentage` | 50.0% | Percentage change threshold for trend alerts |
| `unused_resource_utilization_threshold` | 5.0% | Utilization threshold for "unused" classification |

## Usage Examples

### Basic Cost Analysis

```python
from inventag.discovery.cost_analyzer import CostAnalyzer, CostThresholds
import boto3

# Initialize cost analyzer
session = boto3.Session()
thresholds = CostThresholds(expensive_resource_monthly_threshold=Decimal('150.00'))
analyzer = CostAnalyzer(session=session, thresholds=thresholds)

# Estimate costs for resources
resources = [
    {
        'id': 'i-1234567890abcdef0',
        'service': 'EC2',
        'type': 'Instance',
        'region': 'us-east-1',
        'instance_type': 't3.large'
    },
    {
        'id': 'my-bucket',
        'service': 'S3',
        'type': 'Bucket',
        'region': 'us-east-1',
        'size_gb': 1000
    }
]

# Generate cost estimates
cost_estimates = analyzer.estimate_resource_costs(resources)

for estimate in cost_estimates:
    print(f"Resource: {estimate.resource_id}")
    print(f"Service: {estimate.service}")
    print(f"Monthly Cost: ${estimate.estimated_monthly_cost}")
    print(f"Confidence: {estimate.confidence_level}")
    print("---")
```

### Expensive Resource Analysis

```python
# Identify expensive resources
expensive_resources = analyzer.identify_expensive_resources(cost_estimates)

print(f"Found {len(expensive_resources)} expensive resources:")
for resource in expensive_resources:
    print(f"- {resource.resource_id}: ${resource.estimated_monthly_cost}/month")
    
    # Show cost breakdown
    for component, cost in resource.cost_breakdown.items():
        print(f"  {component}: ${cost}")
```

### Forgotten Resource Detection

```python
# Detect forgotten resources
forgotten_resources = analyzer.detect_forgotten_resources(resources)

print(f"Found {len(forgotten_resources)} potentially forgotten resources:")
for forgotten in forgotten_resources:
    print(f"Resource: {forgotten.resource_id}")
    print(f"Days Inactive: {forgotten.days_since_last_activity}")
    print(f"Monthly Cost: ${forgotten.estimated_monthly_cost}")
    print(f"Risk Level: {forgotten.risk_level}")
    print("Recommendations:")
    for rec in forgotten.recommendations:
        print(f"  - {rec}")
    print("---")
```

### Cost Trend Analysis

```python
# Analyze cost trends (requires Cost Explorer access)
trend_analyses = analyzer.analyze_cost_trends(resources)

for trend in trend_analyses:
    if trend.alert_triggered:
        print(f"ALERT: {trend.resource_id}")
        print(f"Cost Change: {trend.cost_change_percentage:.1f}%")
        print(f"Direction: {trend.trend_direction}")
        print(f"Current: ${trend.current_monthly_cost}")
        print(f"Previous: ${trend.previous_monthly_cost}")
```

### Optimization Recommendations

```python
# Generate optimization recommendations
recommendations = analyzer.generate_cost_optimization_recommendations(
    cost_estimates=cost_estimates,
    forgotten_resources=forgotten_resources
)

print(f"Generated {len(recommendations)} optimization recommendations:")
for rec in recommendations:
    print(f"Resource: {rec.resource_id}")
    print(f"Type: {rec.recommendation_type}")
    print(f"Current Cost: ${rec.current_monthly_cost}")
    print(f"Potential Savings: ${rec.potential_monthly_savings}")
    print(f"Confidence: {rec.confidence_level}")
    print(f"Effort: {rec.implementation_effort}")
    print(f"Description: {rec.description}")
    print("Action Items:")
    for action in rec.action_items:
        print(f"  - {action}")
    print("---")
```

### Complete Cost Analysis Workflow

```python
from inventag.discovery.cost_analyzer import CostAnalyzer, CostAnalysisSummary
from decimal import Decimal

def perform_complete_cost_analysis(resources):
    """Perform comprehensive cost analysis workflow."""
    
    # Initialize analyzer
    analyzer = CostAnalyzer()
    
    # Step 1: Estimate costs
    print("Estimating resource costs...")
    cost_estimates = analyzer.estimate_resource_costs(resources)
    
    # Step 2: Identify expensive resources
    print("Identifying expensive resources...")
    expensive_resources = analyzer.identify_expensive_resources(cost_estimates)
    
    # Step 3: Detect forgotten resources
    print("Detecting forgotten resources...")
    forgotten_resources = analyzer.detect_forgotten_resources(resources)
    
    # Step 4: Analyze cost trends
    print("Analyzing cost trends...")
    trend_analyses = analyzer.analyze_cost_trends(resources)
    
    # Step 5: Generate recommendations
    print("Generating optimization recommendations...")
    recommendations = analyzer.generate_cost_optimization_recommendations(
        cost_estimates=cost_estimates,
        forgotten_resources=forgotten_resources
    )
    
    # Step 6: Create summary
    total_cost = sum(est.estimated_monthly_cost for est in cost_estimates)
    total_savings = sum(rec.potential_monthly_savings for rec in recommendations)
    
    summary = CostAnalysisSummary(
        total_estimated_monthly_cost=total_cost,
        expensive_resources_count=len(expensive_resources),
        forgotten_resources_count=len(forgotten_resources),
        total_potential_savings=total_savings,
        optimization_opportunities=len(recommendations)
    )
    
    return {
        'summary': summary,
        'cost_estimates': cost_estimates,
        'expensive_resources': expensive_resources,
        'forgotten_resources': forgotten_resources,
        'trend_analyses': trend_analyses,
        'recommendations': recommendations
    }

# Run complete analysis
results = perform_complete_cost_analysis(discovered_resources)

# Print summary
summary = results['summary']
print(f"=== Cost Analysis Summary ===")
print(f"Total Monthly Cost: ${summary.total_estimated_monthly_cost}")
print(f"Expensive Resources: {summary.expensive_resources_count}")
print(f"Forgotten Resources: {summary.forgotten_resources_count}")
print(f"Potential Savings: ${summary.total_potential_savings}")
print(f"Optimization Opportunities: {summary.optimization_opportunities}")
```

## Supported AWS Services

### Pricing API Support

The Cost Analyzer supports pricing estimation for the following AWS services:

| Service | Resource Types | Pricing Factors |
|---------|----------------|-----------------|
| **EC2** | Instances, Volumes | Instance type, volume type, size, region |
| **RDS** | DB Instances, Clusters | Instance class, engine, storage, region |
| **S3** | Buckets | Storage class, region, data transfer |
| **Lambda** | Functions | Memory, execution time, requests |
| **ELB/ALB** | Load Balancers | Load balancer type, data processing |
| **CloudFront** | Distributions | Data transfer, requests |
| **Route53** | Hosted Zones | Queries, health checks |
| **VPC** | NAT Gateways, Endpoints | Data processing, hours |
| **ECS/EKS** | Clusters, Services | Compute resources, data transfer |
| **DynamoDB** | Tables | Read/write capacity, storage |

### Activity Metrics Support

Forgotten resource detection uses CloudWatch metrics:

| Service | Metrics Used | Activity Indicators |
|---------|--------------|-------------------|
| **EC2** | CPUUtilization, NetworkIn/Out | CPU usage, network traffic |
| **RDS** | DatabaseConnections, CPUUtilization | Active connections, CPU usage |
| **S3** | AllRequests, DataRetrieved | Request count, data access |
| **Lambda** | Invocations, Duration | Function executions |
| **ELB** | RequestCount, TargetResponseTime | Load balancer traffic |

## Integration with InvenTag Workflow

### With Resource Discovery

```python
from inventag.discovery import AWSResourceInventory
from inventag.discovery.cost_analyzer import CostAnalyzer

# Discover resources
inventory = AWSResourceInventory(regions=['us-east-1', 'us-west-2'])
resources = inventory.discover_resources()

# Analyze costs
analyzer = CostAnalyzer()
cost_estimates = analyzer.estimate_resource_costs(resources)

# Add cost information to resources
for resource in resources:
    cost_estimate = next(
        (est for est in cost_estimates if est.resource_id == resource['id']), 
        None
    )
    if cost_estimate:
        resource['estimated_monthly_cost'] = float(cost_estimate.estimated_monthly_cost)
        resource['cost_confidence'] = cost_estimate.confidence_level
```

### With State Management

```python
from inventag.state import StateManager
from inventag.discovery.cost_analyzer import CostAnalyzer

# Load previous state
state_manager = StateManager()
previous_state = state_manager.load_state()

# Analyze cost trends between states
if previous_state:
    analyzer = CostAnalyzer()
    trend_analyses = analyzer.analyze_cost_trends(current_resources)
    
    # Save cost analysis with state
    state_manager.save_state(
        resources=current_resources,
        account_id="123456789012",
        regions=["us-east-1"],
        cost_analysis={
            'total_monthly_cost': float(total_cost),
            'expensive_resources': len(expensive_resources),
            'optimization_opportunities': len(recommendations)
        }
    )
```

### With BOM Generation

```python
from inventag.reporting import BOMConverter
from inventag.discovery.cost_analyzer import CostAnalyzer

# Enrich resources with cost data
analyzer = CostAnalyzer()
cost_estimates = analyzer.estimate_resource_costs(resources)

# Add cost columns to BOM
for resource in resources:
    cost_estimate = next(
        (est for est in cost_estimates if est.resource_id == resource['id']), 
        None
    )
    if cost_estimate:
        resource['monthly_cost'] = f"${cost_estimate.estimated_monthly_cost}"
        resource['cost_confidence'] = cost_estimate.confidence_level

# Generate BOM with cost information
converter = BOMConverter()
converter.data = resources
converter.export_to_excel('cost_analysis_bom.xlsx')
```

## Best Practices

### 1. **Pricing Data Caching**
- Cost Analyzer caches pricing data to improve performance
- Cache is thread-safe and automatically managed
- Consider cache warming for large-scale analysis

### 2. **Parallel Processing**
- Cost estimation uses ThreadPoolExecutor for parallel processing
- Default max_workers=10, adjust based on API rate limits
- Monitor AWS API throttling and adjust accordingly

### 3. **Activity Threshold Tuning**
- Adjust activity thresholds based on your workload patterns
- Different services have different "normal" activity levels
- Consider seasonal or cyclical usage patterns

### 4. **Cost Trend Analysis**
- Requires AWS Cost Explorer API access
- Cost Explorer has additional charges for API usage
- Consider batching trend analysis for cost efficiency

### 5. **Recommendation Implementation**
- Start with high-confidence, low-effort recommendations
- Test recommendations in non-production environments first
- Monitor impact of optimization changes

## Limitations and Considerations

### AWS Pricing API Limitations
- Pricing API only available in us-east-1 region
- Not all services have complete pricing data
- Spot pricing and reserved instance pricing require additional logic

### CloudWatch Metrics Limitations
- Some metrics require explicit enablement (e.g., S3 request metrics)
- Metrics retention varies by metric type
- Custom metrics may incur additional charges

### Cost Explorer Limitations
- Cost Explorer API has usage charges
- Historical data availability varies
- Granularity limitations for detailed resource-level analysis

### Accuracy Considerations
- Cost estimates are approximations based on current pricing
- Actual costs may vary due to usage patterns, discounts, and credits
- Reserved instance and savings plan discounts not automatically applied

## Troubleshooting

### Common Issues

**1. Pricing API Access Denied**
```
Error: Access denied to pricing API
Solution: Ensure IAM permissions include pricing:GetProducts
```

**2. CloudWatch Metrics Not Found**
```
Error: No metrics found for resource
Solution: Check if CloudWatch monitoring is enabled for the resource
```

**3. Cost Explorer API Errors**
```
Error: Cost Explorer API access denied
Solution: Ensure IAM permissions include ce:GetCostAndUsage
```

**4. High Memory Usage**
```
Issue: Memory usage increases with large resource sets
Solution: Process resources in batches or increase available memory
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('inventag.discovery.cost_analyzer')
logger.setLevel(logging.DEBUG)

# Run cost analysis with debug output
analyzer = CostAnalyzer()
cost_estimates = analyzer.estimate_resource_costs(resources)
```

## Required IAM Permissions

Add these permissions to your IAM policy for full Cost Analyzer functionality:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "pricing:GetProducts",
                "pricing:DescribeServices",
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:ListMetrics",
                "ce:GetCostAndUsage",
                "ce:GetUsageReport"
            ],
            "Resource": "*"
        }
    ]
}
```

## Demo Script

Run the cost analysis demonstration:

```bash
python examples/cost_analysis_demo.py
```

This demo script shows:
- Resource cost estimation
- Expensive resource identification
- Forgotten resource detection
- Cost trend analysis
- Optimization recommendations
- Complete workflow integration

The Cost Analyzer provides powerful insights into your AWS spending patterns and helps identify concrete opportunities for cost optimization while maintaining operational efficiency.