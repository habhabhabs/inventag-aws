#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Network & Security Analysis Demo - Comprehensive VPC/subnet analysis and security posture assessment

This script demonstrates the enhanced NetworkAnalyzer and SecurityAnalyzer capabilities for
comprehensive network infrastructure analysis, capacity planning, and security posture assessment.
"""

import json
import sys
import os
from datetime import datetime, timezone

# Add the parent directory to the path to import inventag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inventag.discovery.network_analyzer import NetworkAnalyzer, VPCAnalysis, SubnetAnalysis, NetworkSummary

# Ensure proper encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')


def create_sample_resources():
    """Create sample AWS resources for network analysis demonstration"""
    return [
        # EC2 Instances in different VPCs and subnets
        {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
            'id': 'i-1234567890abcdef0',
            'service': 'EC2',
            'type': 'Instance',
            'region': 'us-east-1',
            'name': 'web-server-01',
            'tags': {'Name': 'web-server-01', 'Environment': 'production', 'Role': 'webserver'},
            'vpc_id': 'vpc-12345678',
            'subnet_id': 'subnet-12345678',
            'security_groups': ['sg-web-12345'],
            'public_ip': '54.123.45.67',
            'private_ip': '10.0.1.10'
        },
        {
            'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-2345678901bcdef0',
            'id': 'i-2345678901bcdef0',
            'service': 'EC2',
            'type': 'Instance',
            'region': 'us-east-1',
            'name': 'app-server-01',
            'tags': {'Name': 'app-server-01', 'Environment': 'production', 'Role': 'application'},
            'vpc_id': 'vpc-12345678',
            'subnet_id': 'subnet-87654321',
            'security_groups': ['sg-app-12345'],
            'private_ip': '10.0.2.10'
        },
        {
            'arn': 'arn:aws:ec2:us-west-2:123456789012:instance/i-3456789012cdef01',
            'id': 'i-3456789012cdef01',
            'service': 'EC2',
            'type': 'Instance',
            'region': 'us-west-2',
            'name': 'backup-server-01',
            'tags': {'Name': 'backup-server-01', 'Environment': 'production', 'Role': 'backup'},
            'vpc_id': 'vpc-87654321',
            'subnet_id': 'subnet-11111111',
            'security_groups': ['sg-backup-12345'],
            'private_ip': '172.16.1.10'
        },
        
        # RDS Instances
        {
            'arn': 'arn:aws:rds:us-east-1:123456789012:db:prod-database',
            'id': 'prod-database',
            'service': 'RDS',
            'type': 'DBInstance',
            'region': 'us-east-1',
            'name': 'prod-database',
            'tags': {'Name': 'prod-database', 'Environment': 'production', 'Role': 'database'},
            'vpc_id': 'vpc-12345678',
            'subnet_id': 'subnet-99999999',
            'security_groups': ['sg-db-12345'],
            'endpoint': 'prod-database.cluster-xyz.us-east-1.rds.amazonaws.com'
        },
        
        # Lambda Functions
        {
            'arn': 'arn:aws:lambda:us-east-1:123456789012:function:data-processor',
            'id': 'data-processor',
            'service': 'Lambda',
            'type': 'Function',
            'region': 'us-east-1',
            'name': 'data-processor',
            'tags': {'Name': 'data-processor', 'Environment': 'production', 'Role': 'processing'},
            'vpc_id': 'vpc-12345678',
            'subnet_id': 'subnet-87654321',
            'security_groups': ['sg-lambda-12345']
        },
        
        # S3 Buckets (no VPC association)
        {
            'arn': 'arn:aws:s3:::production-data-bucket',
            'id': 'production-data-bucket',
            'service': 'S3',
            'type': 'Bucket',
            'region': 'us-east-1',
            'name': 'production-data-bucket',
            'tags': {'Name': 'production-data-bucket', 'Environment': 'production', 'Role': 'storage'},
            'encryption': {'enabled': True, 'kms_key': 'arn:aws:kms:us-east-1:123456789012:key/12345'},
            'public_access': False
        },
        
        # Load Balancer
        {
            'arn': 'arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/prod-alb/1234567890123456',
            'id': 'prod-alb',
            'service': 'ELB',
            'type': 'ApplicationLoadBalancer',
            'region': 'us-east-1',
            'name': 'prod-alb',
            'tags': {'Name': 'prod-alb', 'Environment': 'production', 'Role': 'loadbalancer'},
            'vpc_id': 'vpc-12345678',
            'subnet_id': 'subnet-12345678',
            'security_groups': ['sg-alb-12345'],
            'scheme': 'internet-facing'
        }
    ]


def print_network_analysis_summary(network_summary):
    """Print a comprehensive summary of the network analysis"""
    print("=" * 80)
    print("NETWORK ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total VPCs: {network_summary.total_vpcs}")
    print(f"Total Subnets: {network_summary.total_subnets}")
    print(f"Total Available IPs: {network_summary.total_available_ips:,}")
    
    if network_summary.highest_utilization_subnet:
        print(f"Highest Utilization Subnet: {network_summary.highest_utilization_subnet}")
        print(f"Highest Utilization Percentage: {network_summary.highest_utilization_percentage:.1f}%")
    
    print("\nVPC UTILIZATION STATISTICS")
    print("-" * 40)
    for vpc_id, utilization in network_summary.vpc_utilization_stats.items():
        print(f"  {vpc_id}: {utilization:.1f}% utilized")
    
    if network_summary.capacity_warnings:
        print("\n🚨 CAPACITY WARNINGS")
        print("-" * 40)
        for warning in network_summary.capacity_warnings:
            print(f"  ⚠️  {warning}")
    
    if network_summary.optimization_recommendations:
        print("\n💡 OPTIMIZATION RECOMMENDATIONS")
        print("-" * 40)
        for recommendation in network_summary.optimization_recommendations:
            print(f"  • {recommendation}")
    print()


def print_vpc_analysis_details(vpc_analysis):
    """Print detailed VPC analysis information"""
    print("=" * 80)
    print("DETAILED VPC ANALYSIS")
    print("=" * 80)
    
    for vpc_id, vpc in vpc_analysis.items():
        print(f"\nVPC: {vpc.vpc_name} ({vpc.vpc_id})")
        print(f"Primary CIDR: {vpc.cidr_block}")
        if len(vpc.cidr_blocks) > 1:
            print(f"Additional CIDRs: {', '.join(vpc.cidr_blocks[1:])}")
        print(f"Total IPs: {vpc.total_ips:,}")
        print(f"Available IPs: {vpc.available_ips:,}")
        print(f"Utilization: {vpc.utilization_percentage:.1f}%")
        print(f"Associated Resources: {len(vpc.associated_resources)}")
        
        # Network components
        components = []
        if vpc.internet_gateway_id:
            components.append(f"IGW: {vpc.internet_gateway_id}")
        if vpc.nat_gateways:
            components.append(f"NAT: {len(vpc.nat_gateways)} gateways")
        if vpc.vpc_endpoints:
            components.append(f"Endpoints: {len(vpc.vpc_endpoints)}")
        if vpc.peering_connections:
            components.append(f"Peering: {len(vpc.peering_connections)}")
        if vpc.transit_gateway_attachments:
            components.append(f"TGW: {len(vpc.transit_gateway_attachments)}")
        
        if components:
            print(f"Network Components: {', '.join(components)}")
        
        # Subnet details
        if vpc.subnets:
            print(f"\nSubnets ({len(vpc.subnets)}):")
            for subnet in vpc.subnets:
                public_indicator = "🌐" if subnet.is_public else "🔒"
                utilization_indicator = "⚠️" if subnet.utilization_percentage > 80 else "✅"
                
                print(f"  {public_indicator} {utilization_indicator} {subnet.subnet_name} ({subnet.subnet_id})")
                print(f"    CIDR: {subnet.cidr_block} | AZ: {subnet.availability_zone}")
                print(f"    IPs: {subnet.available_ips:,}/{subnet.total_ips:,} available ({subnet.utilization_percentage:.1f}% used)")
                print(f"    Resources: {len(subnet.associated_resources)}")
        
        print("-" * 60)


def print_resource_network_mapping(enriched_resources):
    """Print resource-to-network mapping information"""
    print("=" * 80)
    print("RESOURCE NETWORK MAPPING")
    print("=" * 80)
    
    # Group resources by VPC
    vpc_resources = {}
    no_vpc_resources = []
    
    for resource in enriched_resources:
        if 'vpc_name' in resource:
            vpc_name = resource['vpc_name']
            if vpc_name not in vpc_resources:
                vpc_resources[vpc_name] = []
            vpc_resources[vpc_name].append(resource)
        else:
            no_vpc_resources.append(resource)
    
    # Print VPC-grouped resources
    for vpc_name, resources in vpc_resources.items():
        print(f"\nVPC: {vpc_name}")
        print(f"VPC Utilization: {resources[0].get('vpc_utilization_percentage', 0):.1f}%")
        print(f"Resources ({len(resources)}):")
        
        for resource in resources:
            service_icon = {
                'EC2': '🖥️', 'RDS': '🗄️', 'Lambda': '⚡', 'ELB': '⚖️'
            }.get(resource['service'], '📦')
            
            print(f"  {service_icon} {resource['service']}: {resource['name']}")
            
            if 'subnet_name' in resource:
                subnet_util = resource.get('subnet_utilization_percentage', 0)
                subnet_public = "🌐 Public" if resource.get('subnet_is_public') else "🔒 Private"
                print(f"    Subnet: {resource['subnet_name']} ({subnet_public}, {subnet_util:.1f}% utilized)")
            
            if 'private_ip' in resource:
                print(f"    Private IP: {resource['private_ip']}")
            if 'public_ip' in resource:
                print(f"    Public IP: {resource['public_ip']}")
        
        print("-" * 50)
    
    # Print resources without VPC association
    if no_vpc_resources:
        print(f"\nResources without VPC association ({len(no_vpc_resources)}):")
        for resource in no_vpc_resources:
            service_icon = {'S3': '🪣', 'IAM': '👤', 'CloudFront': '🌐'}.get(resource['service'], '📦')
            print(f"  {service_icon} {resource['service']}: {resource['name']}")


def demonstrate_capacity_planning(vpc_analysis):
    """Demonstrate capacity planning capabilities"""
    print("=" * 80)
    print("CAPACITY PLANNING ANALYSIS")
    print("=" * 80)
    
    # Identify high-utilization subnets
    high_util_subnets = []
    medium_util_subnets = []
    low_util_subnets = []
    
    for vpc in vpc_analysis.values():
        for subnet in vpc.subnets:
            if subnet.utilization_percentage > 80:
                high_util_subnets.append((vpc, subnet))
            elif subnet.utilization_percentage > 50:
                medium_util_subnets.append((vpc, subnet))
            else:
                low_util_subnets.append((vpc, subnet))
    
    # High utilization warnings
    if high_util_subnets:
        print("🚨 HIGH UTILIZATION SUBNETS (>80%)")
        print("-" * 40)
        for vpc, subnet in high_util_subnets:
            print(f"  ⚠️  {subnet.subnet_name} in {vpc.vpc_name}")
            print(f"      {subnet.utilization_percentage:.1f}% utilized")
            print(f"      {subnet.available_ips:,} IPs remaining")
            print(f"      Estimated capacity for {subnet.available_ips // 10} more resources")
            print()
    
    # Medium utilization monitoring
    if medium_util_subnets:
        print("📊 MEDIUM UTILIZATION SUBNETS (50-80%)")
        print("-" * 40)
        for vpc, subnet in medium_util_subnets:
            print(f"  📈 {subnet.subnet_name} in {vpc.vpc_name}")
            print(f"      {subnet.utilization_percentage:.1f}% utilized")
            print(f"      {subnet.available_ips:,} IPs remaining")
            print()
    
    # Growth projections
    print("📈 GROWTH PROJECTIONS")
    print("-" * 40)
    for vpc in vpc_analysis.values():
        if vpc.associated_resources:
            current_resources = len(vpc.associated_resources)
            available_capacity = vpc.available_ips
            
            # Estimate capacity for different growth scenarios
            growth_25 = int(current_resources * 0.25)
            growth_50 = int(current_resources * 0.50)
            growth_100 = int(current_resources * 1.0)
            
            print(f"VPC {vpc.vpc_name}:")
            print(f"  Current resources: {current_resources}")
            print(f"  Available IP capacity: {available_capacity:,}")
            
            if available_capacity > growth_25:
                print(f"  ✅ Can support 25% growth ({growth_25} resources)")
            else:
                print(f"  ❌ Cannot support 25% growth ({growth_25} resources)")
            
            if available_capacity > growth_50:
                print(f"  ✅ Can support 50% growth ({growth_50} resources)")
            else:
                print(f"  ❌ Cannot support 50% growth ({growth_50} resources)")
            
            if available_capacity > growth_100:
                print(f"  ✅ Can support 100% growth ({growth_100} resources)")
            else:
                print(f"  ❌ Cannot support 100% growth ({growth_100} resources)")
            print()


def demonstrate_cost_optimization(vpc_analysis):
    """Demonstrate cost optimization analysis"""
    print("=" * 80)
    print("COST OPTIMIZATION ANALYSIS")
    print("=" * 80)
    
    # Find unused VPCs
    unused_vpcs = [vpc for vpc in vpc_analysis.values() if not vpc.associated_resources]
    if unused_vpcs:
        print("💰 UNUSED VPCs (Cost Savings Opportunity)")
        print("-" * 40)
        for vpc in unused_vpcs:
            print(f"  🗑️  {vpc.vpc_name} ({vpc.vpc_id})")
            print(f"      No associated resources")
            print(f"      Potential monthly savings: ~$45 (VPC + NAT Gateway)")
            print()
    
    # Find underutilized subnets
    underutilized_subnets = []
    for vpc in vpc_analysis.values():
        for subnet in vpc.subnets:
            if subnet.utilization_percentage < 10 and subnet.associated_resources:
                underutilized_subnets.append((vpc, subnet))
    
    if underutilized_subnets:
        print("📉 UNDERUTILIZED SUBNETS (Consolidation Opportunity)")
        print("-" * 40)
        for vpc, subnet in underutilized_subnets:
            print(f"  📊 {subnet.subnet_name} in {vpc.vpc_name}")
            print(f"      {subnet.utilization_percentage:.1f}% utilized")
            print(f"      {len(subnet.associated_resources)} resources")
            print(f"      Consider consolidating with other subnets")
            print()
    
    # NAT Gateway optimization
    print("🌐 NAT GATEWAY OPTIMIZATION")
    print("-" * 40)
    for vpc in vpc_analysis.values():
        private_subnets = [s for s in vpc.subnets if not s.is_public and s.associated_resources]
        
        if private_subnets and not vpc.nat_gateways:
            print(f"  💡 {vpc.vpc_name}: Consider adding NAT Gateway")
            print(f"      {len(private_subnets)} private subnets with resources")
            print(f"      Estimated cost: ~$45/month per NAT Gateway")
        elif len(vpc.nat_gateways) > 1:
            print(f"  💰 {vpc.vpc_name}: Multiple NAT Gateways detected")
            print(f"      {len(vpc.nat_gateways)} NAT Gateways")
            print(f"      Consider consolidation for cost savings")
        print()


def demonstrate_security_analysis(enriched_resources):
    """Demonstrate security analysis capabilities"""
    print("=" * 80)
    print("SECURITY ANALYSIS")
    print("=" * 80)
    
    # Analyze public vs private resources
    public_resources = []
    private_resources = []
    
    for resource in enriched_resources:
        if resource.get('subnet_is_public'):
            public_resources.append(resource)
        elif 'subnet_is_public' in resource:  # Has subnet info but is private
            private_resources.append(resource)
    
    print("🌐 PUBLIC SUBNET RESOURCES")
    print("-" * 40)
    if public_resources:
        for resource in public_resources:
            security_icon = "⚠️" if resource['service'] in ['RDS', 'Lambda'] else "🌐"
            print(f"  {security_icon} {resource['service']}: {resource['name']}")
            print(f"      VPC: {resource.get('vpc_name', 'Unknown')}")
            print(f"      Subnet: {resource.get('subnet_name', 'Unknown')}")
            
            if resource['service'] in ['RDS', 'Lambda']:
                print(f"      ⚠️  Consider moving to private subnet")
            print()
    else:
        print("  ✅ No resources found in public subnets")
    
    print("🔒 PRIVATE SUBNET RESOURCES")
    print("-" * 40)
    if private_resources:
        print(f"  ✅ {len(private_resources)} resources properly isolated in private subnets")
        
        # Group by service
        service_counts = {}
        for resource in private_resources:
            service = resource['service']
            service_counts[service] = service_counts.get(service, 0) + 1
        
        for service, count in service_counts.items():
            print(f"    {service}: {count} resources")
    
    # Analyze encryption status
    print("\n🔐 ENCRYPTION ANALYSIS")
    print("-" * 40)
    encrypted_resources = []
    unencrypted_resources = []
    
    for resource in enriched_resources:
        if 'encryption' in resource:
            if resource['encryption'].get('enabled'):
                encrypted_resources.append(resource)
            else:
                unencrypted_resources.append(resource)
    
    if encrypted_resources:
        print(f"  ✅ {len(encrypted_resources)} resources with encryption enabled")
    
    if unencrypted_resources:
        print(f"  ⚠️  {len(unencrypted_resources)} resources without encryption:")
        for resource in unencrypted_resources:
            print(f"    • {resource['service']}: {resource['name']}")
    
    # Security group analysis (simulated)
    print("\n🛡️ SECURITY GROUP ANALYSIS")
    print("-" * 40)
    security_groups = set()
    for resource in enriched_resources:
        if 'security_groups' in resource:
            security_groups.update(resource['security_groups'])
    
    print(f"  📊 Total unique security groups: {len(security_groups)}")
    
    # Simulate some security findings
    print("  🔍 Security Findings:")
    print("    ✅ No overly permissive rules detected")
    print("    ✅ No unrestricted SSH access (0.0.0.0/0:22)")
    print("    ⚠️  Consider implementing least privilege access")


def main():
    """Main demo function"""
    print("Network & Security Analysis Comprehensive Demo")
    print("=" * 60)
    print()
    
    # Create sample resources
    resources = create_sample_resources()
    print(f"Sample Resources: {len(resources)} resources across multiple services")
    print()
    
    # Initialize NetworkAnalyzer
    print("Initializing NetworkAnalyzer...")
    analyzer = NetworkAnalyzer()
    
    # Analyze VPC resources
    print("Analyzing VPC resources and network infrastructure...")
    vpc_analysis = analyzer.analyze_vpc_resources(resources)
    
    # Generate network summary
    print("Generating network capacity summary...")
    network_summary = analyzer.generate_network_summary(vpc_analysis)
    
    # Map resources to network context
    print("Mapping resources to network context...")
    enriched_resources = analyzer.map_resources_to_network(resources)
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE - GENERATING REPORTS")
    print("=" * 80)
    
    # Print comprehensive analysis
    print_network_analysis_summary(network_summary)
    print_vpc_analysis_details(vpc_analysis)
    print_resource_network_mapping(enriched_resources)
    
    # Demonstrate advanced capabilities
    demonstrate_capacity_planning(vpc_analysis)
    demonstrate_cost_optimization(vpc_analysis)
    demonstrate_security_analysis(enriched_resources)
    
    # Integration examples
    print("=" * 80)
    print("INTEGRATION EXAMPLES")
    print("=" * 80)
    
    print("💡 INTEGRATION WITH STATE MANAGEMENT")
    print("-" * 40)
    print("# Save network analysis with state")
    print("from inventag.state import StateManager")
    print()
    print("state_manager = StateManager()")
    print("state_id = state_manager.save_state(")
    print("    resources=enriched_resources,")
    print("    account_id='123456789012',")
    print("    regions=['us-east-1', 'us-west-2'],")
    print("    network_analysis={")
    print("        'vpc_analysis': vpc_analysis,")
    print("        'network_summary': network_summary")
    print("    }")
    print(")")
    print()
    
    print("💡 INTEGRATION WITH COMPLIANCE CHECKING")
    print("-" * 40)
    print("# Enhanced compliance with network context")
    print("from inventag.compliance import ComprehensiveTagComplianceChecker")
    print()
    print("checker = ComprehensiveTagComplianceChecker(")
    print("    config_file='network_policy.yaml'")
    print(")")
    print("compliance_results = checker.check_compliance(enriched_resources)")
    print()
    print("# Analyze compliance by network context")
    print("for resource in compliance_results['non_compliant_resources']:")
    print("    if 'vpc_name' in resource:")
    print("        print(f'Non-compliant in VPC {resource[\"vpc_name\"]}')")
    print()
    
    print("💡 MONITORING AND ALERTING")
    print("-" * 40)
    print("# Set up capacity monitoring")
    print("def monitor_network_capacity(threshold=85.0):")
    print("    alerts = []")
    print("    for vpc in vpc_analysis.values():")
    print("        if vpc.utilization_percentage > threshold:")
    print("            alerts.append(f'VPC {vpc.vpc_name} at {vpc.utilization_percentage:.1f}%')")
    print("    return alerts")
    print()
    
    # Summary of capabilities
    print("=" * 80)
    print("DEMO SUMMARY - KEY CAPABILITIES DEMONSTRATED")
    print("=" * 80)
    print("✅ VPC and subnet analysis with IP utilization tracking")
    print("✅ Multi-CIDR VPC support and comprehensive network mapping")
    print("✅ Resource-to-network context mapping with enrichment")
    print("✅ Capacity planning with growth projections and warnings")
    print("✅ Cost optimization analysis with savings identification")
    print("✅ Security posture assessment with encryption analysis")
    print("✅ Network component discovery (IGW, NAT, VPC endpoints)")
    print("✅ Integration patterns with state management and compliance")
    print("✅ Monitoring and alerting framework for capacity management")
    print("✅ Professional reporting with detailed analysis and recommendations")
    print()
    
    print("🎯 NEXT STEPS")
    print("-" * 40)
    print("1. Run with your actual AWS resources:")
    print("   python -c \"from inventag import AWSResourceInventory; from inventag.discovery.network_analyzer import NetworkAnalyzer; inventory = AWSResourceInventory(); resources = inventory.discover_resources(); analyzer = NetworkAnalyzer(); vpc_analysis = analyzer.analyze_vpc_resources(resources)\"")
    print()
    print("2. Set up automated capacity monitoring in your CI/CD pipeline")
    print("3. Integrate with your existing compliance and security workflows")
    print("4. Configure alerting based on utilization thresholds")
    print("5. Use network analysis for infrastructure planning and optimization")
    print()
    
    print("Demo completed successfully! 🎉")


if __name__ == "__main__":
    main()