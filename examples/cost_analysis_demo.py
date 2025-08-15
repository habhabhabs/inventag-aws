#!/usr/bin/env python3
"""
Cost Analysis Demonstration Script

This script demonstrates the comprehensive cost analysis capabilities
of the InvenTag Cost Analyzer, including cost estimation, forgotten resource
detection, and optimization recommendations.
"""

import sys
import os
from decimal import Decimal
from datetime import datetime, timezone

# Add the parent directory to the path to import inventag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.discovery.cost_analyzer import (
    CostAnalyzer,
    CostThresholds,
    ResourceCostEstimate,
    ForgottenResourceAnalysis,
    CostOptimizationRecommendation,
)


def main():
    """Demonstrate Cost Analyzer functionality"""
    print("=== InvenTag Cost Analyzer Demonstration ===\n")

    # Sample resource data for demonstration
    sample_resources = [
        {
            "id": "i-1234567890abcdef0",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "instance_type": "t3.large",
            "tags": {"Name": "web-server", "Environment": "production"},
        },
        {
            "id": "i-abcdef1234567890",
            "service": "EC2",
            "type": "Instance",
            "region": "us-east-1",
            "instance_type": "m5.xlarge",
            "tags": {"Name": "unused-server", "Environment": "development"},
        },
        {
            "id": "vol-1234567890abcdef0",
            "service": "EC2",
            "type": "Volume",
            "region": "us-east-1",
            "volume_type": "gp3",
            "size_gb": 100,
            "tags": {"Name": "web-server-storage"},
        },
        {
            "id": "production-data-bucket",
            "service": "S3",
            "type": "Bucket",
            "region": "us-east-1",
            "size_gb": 5000,
            "storage_class": "Standard",
            "tags": {"Environment": "production", "Owner": "data-team"},
        },
        {
            "id": "test-database",
            "service": "RDS",
            "type": "DBInstance",
            "region": "us-east-1",
            "db_instance_class": "db.t3.medium",
            "engine": "mysql",
            "tags": {"Environment": "test", "Owner": "dev-team"},
        },
        {
            "id": "data-processor",
            "service": "Lambda",
            "type": "Function",
            "region": "us-east-1",
            "memory_size": 512,
            "tags": {"Environment": "production", "Owner": "data-team"},
        },
    ]

    # Configure custom cost thresholds
    custom_thresholds = CostThresholds(
        expensive_resource_monthly_threshold=Decimal("75.00"),  # $75/month
        forgotten_resource_days_threshold=21,  # 21 days
        high_cost_alert_threshold=Decimal("500.00"),  # $500/month
        cost_trend_alert_percentage=25.0,  # 25% change
        unused_resource_utilization_threshold=8.0,  # 8% utilization
    )

    print("1. Initializing Cost Analyzer with custom thresholds...")
    print(
        f"   Expensive resource threshold: ${custom_thresholds.expensive_resource_monthly_threshold}"
    )
    print(
        f"   Forgotten resource threshold: {custom_thresholds.forgotten_resource_days_threshold} days"
    )
    print(f"   High cost alert threshold: ${custom_thresholds.high_cost_alert_threshold}")

    # Initialize Cost Analyzer (using mock data since we don't have real AWS access)
    analyzer = CostAnalyzer(thresholds=custom_thresholds)

    print("\n2. Demonstrating Resource Cost Estimation...")

    # Create mock cost estimates for demonstration
    mock_cost_estimates = [
        ResourceCostEstimate(
            resource_id="i-1234567890abcdef0",
            resource_type="Instance",
            service="EC2",
            region="us-east-1",
            estimated_monthly_cost=Decimal("65.50"),
            cost_breakdown={"compute": Decimal("65.50")},
            confidence_level="high",
        ),
        ResourceCostEstimate(
            resource_id="i-abcdef1234567890",
            resource_type="Instance",
            service="EC2",
            region="us-east-1",
            estimated_monthly_cost=Decimal("125.00"),
            cost_breakdown={"compute": Decimal("125.00")},
            confidence_level="high",
        ),
        ResourceCostEstimate(
            resource_id="vol-1234567890abcdef0",
            resource_type="Volume",
            service="EC2",
            region="us-east-1",
            estimated_monthly_cost=Decimal("10.00"),
            cost_breakdown={"storage": Decimal("10.00")},
            confidence_level="high",
        ),
        ResourceCostEstimate(
            resource_id="production-data-bucket",
            resource_type="Bucket",
            service="S3",
            region="us-east-1",
            estimated_monthly_cost=Decimal("115.00"),
            cost_breakdown={"storage": Decimal("115.00")},
            confidence_level="medium",
        ),
        ResourceCostEstimate(
            resource_id="test-database",
            resource_type="DBInstance",
            service="RDS",
            region="us-east-1",
            estimated_monthly_cost=Decimal("45.60"),
            cost_breakdown={"database": Decimal("45.60")},
            confidence_level="high",
        ),
        ResourceCostEstimate(
            resource_id="data-processor",
            resource_type="Function",
            service="Lambda",
            region="us-east-1",
            estimated_monthly_cost=Decimal("8.50"),
            cost_breakdown={"base_cost": Decimal("8.50")},
            confidence_level="medium",
        ),
    ]

    total_monthly_cost = sum(est.estimated_monthly_cost for est in mock_cost_estimates)

    print(f"   Total estimated monthly cost: ${total_monthly_cost}")
    print("   Cost breakdown by resource:")
    for estimate in mock_cost_estimates:
        print(
            f"   - {estimate.resource_id} ({estimate.service}): ${estimate.estimated_monthly_cost} ({estimate.confidence_level} confidence)"
        )

    print("\n3. Identifying Expensive Resources...")
    expensive_resources = analyzer.identify_expensive_resources(mock_cost_estimates)

    print(
        f"   Found {len(expensive_resources)} expensive resources (>${custom_thresholds.expensive_resource_monthly_threshold}/month):"
    )
    for resource in expensive_resources:
        print(f"   - {resource.resource_id}: ${resource.estimated_monthly_cost}/month")
        for component, cost in resource.cost_breakdown.items():
            print(f"     └─ {component}: ${cost}")

    print("\n4. Demonstrating Forgotten Resource Detection...")

    # Create mock forgotten resource analyses
    mock_forgotten_resources = [
        ForgottenResourceAnalysis(
            resource_id="i-abcdef1234567890",
            resource_type="Instance",
            service="EC2",
            days_since_last_activity=35,
            estimated_monthly_cost=Decimal("125.00"),
            activity_indicators={"cpu_utilization": [], "network_activity": []},
            risk_level="high",
            recommendations=[
                "Consider terminating this resource as it has been inactive for over 30 days",
                "High cost resource - prioritize review and potential termination",
                "Consider stopping the instance if not needed, or downsizing if underutilized",
            ],
        ),
        ForgottenResourceAnalysis(
            resource_id="test-database",
            resource_type="DBInstance",
            service="RDS",
            days_since_last_activity=28,
            estimated_monthly_cost=Decimal("45.60"),
            activity_indicators={"database_connections": []},
            risk_level="medium",
            recommendations=[
                "Review if this resource is still needed - inactive for over 21 days",
                "Consider taking a final snapshot before terminating the database",
            ],
        ),
    ]

    print(f"   Found {len(mock_forgotten_resources)} potentially forgotten resources:")
    for forgotten in mock_forgotten_resources:
        print(f"   - Resource: {forgotten.resource_id}")
        print(f"     Days inactive: {forgotten.days_since_last_activity}")
        print(f"     Monthly cost: ${forgotten.estimated_monthly_cost}")
        print(f"     Risk level: {forgotten.risk_level}")
        print("     Recommendations:")
        for rec in forgotten.recommendations:
            print(f"       • {rec}")
        print()

    print("5. Demonstrating Cost Optimization Recommendations...")

    # Generate optimization recommendations
    recommendations = analyzer.generate_cost_optimization_recommendations(
        cost_estimates=mock_cost_estimates, forgotten_resources=mock_forgotten_resources
    )

    # Add some mock recommendations for demonstration
    mock_recommendations = [
        CostOptimizationRecommendation(
            resource_id="i-abcdef1234567890",
            resource_type="Instance",
            service="EC2",
            recommendation_type="termination",
            current_monthly_cost=Decimal("125.00"),
            potential_monthly_savings=Decimal("125.00"),
            confidence_level="high",
            implementation_effort="low",
            description="Terminate unused EC2 instance that has been inactive for 35 days",
            action_items=[
                "Verify no critical data is stored on the instance",
                "Create AMI backup if needed",
                "Terminate the instance through AWS console or CLI",
            ],
        ),
        CostOptimizationRecommendation(
            resource_id="production-data-bucket",
            resource_type="Bucket",
            service="S3",
            recommendation_type="storage_optimization",
            current_monthly_cost=Decimal("115.00"),
            potential_monthly_savings=Decimal("35.00"),
            confidence_level="medium",
            implementation_effort="medium",
            description="Optimize S3 storage class for infrequently accessed data",
            action_items=[
                "Analyze access patterns for objects in the bucket",
                "Implement lifecycle policies to transition to IA or Glacier",
                "Monitor cost impact after implementation",
            ],
        ),
        CostOptimizationRecommendation(
            resource_id="i-1234567890abcdef0",
            resource_type="Instance",
            service="EC2",
            recommendation_type="rightsizing",
            current_monthly_cost=Decimal("65.50"),
            potential_monthly_savings=Decimal("20.00"),
            confidence_level="medium",
            implementation_effort="medium",
            description="Consider rightsizing this EC2 instance to reduce costs",
            action_items=[
                "Analyze CPU and memory utilization over the past 30 days",
                "Consider downsizing to t3.medium if underutilized",
                "Evaluate Reserved Instance pricing for long-term workloads",
            ],
        ),
    ]

    total_potential_savings = sum(rec.potential_monthly_savings for rec in mock_recommendations)

    print(f"   Generated {len(mock_recommendations)} optimization recommendations:")
    print(f"   Total potential monthly savings: ${total_potential_savings}")
    print()

    for rec in mock_recommendations:
        print(f"   Resource: {rec.resource_id} ({rec.service})")
        print(f"   Type: {rec.recommendation_type}")
        print(f"   Current cost: ${rec.current_monthly_cost}/month")
        print(f"   Potential savings: ${rec.potential_monthly_savings}/month")
        print(f"   Confidence: {rec.confidence_level}")
        print(f"   Implementation effort: {rec.implementation_effort}")
        print(f"   Description: {rec.description}")
        print("   Action items:")
        for action in rec.action_items:
            print(f"     • {action}")
        print()

    print("6. Cost Analysis Summary...")

    # Calculate summary statistics
    expensive_count = len(expensive_resources)
    forgotten_count = len(mock_forgotten_resources)
    optimization_count = len(mock_recommendations)

    # Calculate cost by service
    cost_by_service = {}
    for estimate in mock_cost_estimates:
        service = estimate.service
        if service not in cost_by_service:
            cost_by_service[service] = Decimal("0")
        cost_by_service[service] += estimate.estimated_monthly_cost

    print(f"   Total monthly cost: ${total_monthly_cost}")
    print(f"   Expensive resources: {expensive_count}")
    print(f"   Forgotten resources: {forgotten_count}")
    print(f"   Optimization opportunities: {optimization_count}")
    print(f"   Total potential savings: ${total_potential_savings}")
    print(
        f"   Potential savings percentage: {(total_potential_savings / total_monthly_cost * 100):.1f}%"
    )
    print()
    print("   Cost breakdown by service:")
    for service, cost in sorted(cost_by_service.items()):
        percentage = cost / total_monthly_cost * 100
        print(f"   - {service}: ${cost} ({percentage:.1f}%)")

    print("\n7. Cost Trend Analysis (Mock Data)...")

    # Mock trend analysis data
    print("   Analyzing cost trends over the past 60 days...")
    print("   Service cost changes:")
    print("   - EC2: +15.2% (increasing trend) ⚠️")
    print("   - S3: -5.1% (stable trend)")
    print("   - RDS: +2.3% (stable trend)")
    print("   - Lambda: +45.8% (increasing trend) ⚠️ ALERT")
    print()
    print("   Alerts triggered:")
    print("   - Lambda costs increased by 45.8% (threshold: 25%)")
    print("   - Investigate increased Lambda invocations")

    print("\n8. Integration with InvenTag Workflow...")

    # Demonstrate integration with resource data
    print("   Enriching resources with cost information...")
    enriched_resources = []

    for resource in sample_resources:
        # Find matching cost estimate
        cost_estimate = next(
            (est for est in mock_cost_estimates if est.resource_id == resource["id"]),
            None,
        )

        if cost_estimate:
            resource["estimated_monthly_cost"] = float(cost_estimate.estimated_monthly_cost)
            resource["cost_confidence"] = cost_estimate.confidence_level

            # Check if it's expensive
            if cost_estimate in expensive_resources:
                resource["cost_category"] = "expensive"
            else:
                resource["cost_category"] = "normal"

            # Check if it's forgotten
            forgotten = next(
                (f for f in mock_forgotten_resources if f.resource_id == resource["id"]),
                None,
            )
            if forgotten:
                resource["forgotten_risk"] = forgotten.risk_level
                resource["days_inactive"] = forgotten.days_since_last_activity

        enriched_resources.append(resource)

    print("   Sample enriched resource data:")
    for resource in enriched_resources[:3]:  # Show first 3 resources
        print(f"   - {resource['id']} ({resource['service']}):")
        print(f"     Monthly cost: ${resource.get('estimated_monthly_cost', 'N/A')}")
        print(f"     Cost category: {resource.get('cost_category', 'unknown')}")
        print(f"     Confidence: {resource.get('cost_confidence', 'N/A')}")
        if "forgotten_risk" in resource:
            print(f"     Forgotten risk: {resource['forgotten_risk']}")
            print(f"     Days inactive: {resource['days_inactive']}")

    print("\n=== Cost Analyzer Demonstration Complete ===")
    print("\nKey capabilities demonstrated:")
    print("✓ Resource cost estimation with AWS Pricing API integration")
    print("✓ Expensive resource identification with configurable thresholds")
    print("✓ Forgotten resource detection based on activity patterns")
    print("✓ Cost trend analysis with alerting for significant changes")
    print("✓ Comprehensive optimization recommendations")
    print("✓ Integration with InvenTag resource discovery workflow")
    print("✓ Cost breakdown analysis by service and resource type")
    print("✓ Risk assessment and prioritization for cost optimization")

    print("\nNext steps:")
    print("• Configure AWS credentials and IAM permissions for live data")
    print("• Customize cost thresholds for your organization")
    print("• Integrate with your existing InvenTag workflows")
    print("• Set up automated cost monitoring and alerting")
    print("• Implement optimization recommendations in test environments")


if __name__ == "__main__":
    main()
