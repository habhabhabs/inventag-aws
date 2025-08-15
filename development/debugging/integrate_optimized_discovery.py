#!/usr/bin/env python3
"""
Integration Script for Optimized Discovery System
This script integrates the optimized discovery system into the existing inventag package.
"""

import sys
import os
import shutil
from pathlib import Path


def integrate_optimized_discovery():
    """
    Integrate the optimized discovery system into the existing inventag package.
    """

    print("🔧 Integrating Optimized Discovery System")
    print("=" * 50)

    # Check if inventag directory exists
    inventag_path = Path("inventag")
    if not inventag_path.exists():
        print("❌ Error: inventag directory not found!")
        return False

    discovery_path = inventag_path / "discovery"
    if not discovery_path.exists():
        print("❌ Error: inventag/discovery directory not found!")
        return False

    # 1. Backup existing intelligent_discovery.py
    intelligent_discovery_path = discovery_path / "intelligent_discovery.py"
    if intelligent_discovery_path.exists():
        backup_path = discovery_path / "intelligent_discovery_backup.py"
        shutil.copy2(intelligent_discovery_path, backup_path)
        print(f"✅ Backed up existing intelligent_discovery.py to {backup_path}")

    # 2. Create enhanced intelligent discovery
    enhanced_content = '''#!/usr/bin/env python3
"""
Enhanced Intelligent AWS Resource Discovery System
Optimized version with better service coverage and field mapping.
"""

import json
import re
import logging
import concurrent.futures
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Import the original classes
from .intelligent_discovery import StandardResource, IntelligentFieldMapper, IntelligentAWSDiscovery

class EnhancedFieldMapper(IntelligentFieldMapper):
    """Enhanced field mapper with better detection patterns."""
    
    def __init__(self):
        super().__init__()
        
        # Enhanced service-specific patterns
        self.enhanced_service_patterns = {
            "cloudfront": {
                "resource_types": ["Distribution"],
                "id_patterns": [r"E[A-Z0-9]+"],
                "operations": ["ListDistributions"],
                "name_fields": ["DomainName", "Id"],
                "region_dependent": False,
                "global_service": True,
            },
            "iam": {
                "resource_types": ["Role", "User", "Policy", "Group"],
                "operations": ["ListRoles", "ListUsers", "ListPolicies"],
                "name_fields": ["RoleName", "UserName", "PolicyName"],
                "region_dependent": False,
                "global_service": True,
            },
            "route53": {
                "resource_types": ["HostedZone"],
                "id_patterns": [r"Z[0-9A-Z]+"],
                "operations": ["ListHostedZones"],
                "name_fields": ["Name", "Id"],
                "region_dependent": False,
                "global_service": True,
            },
            "s3": {
                "resource_types": ["Bucket"],
                "operations": ["ListBuckets"],
                "name_fields": ["Name"],
                "region_dependent": False,
                "global_service": True,
            },
            "lambda": {
                "resource_types": ["Function"],
                "operations": ["ListFunctions"],
                "name_fields": ["FunctionName"],
                "region_dependent": True,
            }
        }
    
    def analyze_and_map_resource(
        self,
        raw_data: Dict[str, Any],
        service_name: str,
        operation_name: str,
        region: str,
        account_id: str = None,
    ) -> StandardResource:
        """Enhanced resource analysis with better field detection."""
        
        try:
            # Enhanced resource ID extraction
            resource_id = self._enhanced_extract_resource_id(raw_data, service_name)
            resource_type = self._enhanced_determine_resource_type(
                raw_data, operation_name, service_name
            )
            
            # Initialize with enhanced detection
            resource = StandardResource(
                service_name=self._normalize_service_name(service_name),
                resource_type=resource_type,
                resource_id=resource_id,
                region=region,
                account_id=account_id or self._extract_account_from_data(raw_data),
                api_operation=operation_name,
                raw_data=raw_data,
            )
            
            # Enhanced field extraction
            resource.resource_name = self._enhanced_extract_resource_name(raw_data, service_name)
            resource.resource_arn = self._extract_arn(raw_data)
            
            # Status and lifecycle with fallbacks
            resource.status = self._extract_status(raw_data) or self._extract_state(raw_data)
            resource.state = self._extract_state(raw_data) or self._extract_status(raw_data)
            resource.created_date = self._extract_creation_date(raw_data)
            resource.last_modified = self._extract_modification_date(raw_data)
            
            # Enhanced tag extraction
            raw_tags = self._enhanced_extract_tags(raw_data)
            resource.tags = raw_tags
            resource.name_from_tags = raw_tags.get("Name")
            resource.environment = (
                raw_tags.get("Environment") or 
                raw_tags.get("Env") or 
                raw_tags.get("Stage")
            )
            resource.project = (
                raw_tags.get("Project") or 
                raw_tags.get("ProjectName") or 
                raw_tags.get("Application")
            )
            resource.cost_center = (
                raw_tags.get("CostCenter") or 
                raw_tags.get("BillingCode") or 
                raw_tags.get("Department")
            )
            
            # Enhanced security and network detection
            resource.vpc_id = self._extract_vpc_info(raw_data)
            resource.subnet_ids = self._extract_subnet_info(raw_data)
            resource.security_groups = self._extract_security_groups(raw_data)
            resource.public_access = self._determine_public_access(raw_data, service_name)
            resource.encrypted = self._determine_encryption_status(raw_data)
            
            # Resource relationships
            resource.dependencies = self._identify_dependencies(raw_data)
            resource.parent_resource = self._identify_parent_resource(raw_data)
            
            # Enhanced confidence calculation
            resource.confidence_score = self._enhanced_calculate_confidence_score(resource)
            
            return resource
            
        except Exception as e:
            self.logger.error(f"Enhanced mapping failed for {service_name}: {e}")
            # Return basic resource with minimal info
            return StandardResource(
                service_name=service_name,
                resource_type="Unknown",
                resource_id=str(raw_data.get("Id", raw_data.get("Name", "unknown"))),
                region=region,
                confidence_score=0.1,
                raw_data=raw_data,
            )
    
    def _enhanced_extract_resource_id(self, data: Dict[str, Any], service_name: str) -> str:
        """Enhanced resource ID extraction with service-specific logic."""
        
        # Service-specific ID extraction
        service_lower = service_name.lower()
        if service_lower in self.enhanced_service_patterns:
            patterns = self.enhanced_service_patterns[service_lower]
            
            # Try service-specific name fields first
            for field in patterns.get("name_fields", []):
                if field in data and data[field]:
                    return str(data[field])
        
        # Fall back to parent method
        return super()._extract_resource_id(data)
    
    def _enhanced_extract_resource_name(self, data: Dict[str, Any], service_name: str) -> Optional[str]:
        """Enhanced resource name extraction with service-specific logic."""
        
        # Service-specific name extraction
        service_lower = service_name.lower()
        if service_lower in self.enhanced_service_patterns:
            patterns = self.enhanced_service_patterns[service_lower]
            
            # Try service-specific name fields
            for field in patterns.get("name_fields", []):
                if field in data and data[field]:
                    return str(data[field])
        
        # CloudFront specific logic
        if service_lower == "cloudfront":
            if "DomainName" in data:
                return data["DomainName"]
            if "Aliases" in data and data["Aliases"].get("Items"):
                return data["Aliases"]["Items"][0]
        
        # Fall back to parent method
        return super()._extract_resource_name(data)
    
    def _enhanced_determine_resource_type(
        self, data: Dict[str, Any], operation_name: str, service_name: str
    ) -> str:
        """Enhanced resource type determination."""
        
        # Service-specific type detection
        service_lower = service_name.lower()
        if service_lower in self.enhanced_service_patterns:
            patterns = self.enhanced_service_patterns[service_lower]
            resource_types = patterns.get("resource_types", [])
            
            # Match operation to resource type
            if "Distribution" in operation_name and "Distribution" in resource_types:
                return "Distribution"
            elif "HostedZone" in operation_name and "HostedZone" in resource_types:
                return "HostedZone"
            elif "Bucket" in operation_name and "Bucket" in resource_types:
                return "Bucket"
            elif "Function" in operation_name and "Function" in resource_types:
                return "Function"
            elif "Role" in operation_name and "Role" in resource_types:
                return "Role"
            elif "User" in operation_name and "User" in resource_types:
                return "User"
        
        # Fall back to parent method
        return super()._determine_resource_type(data, operation_name, service_name)
    
    def _enhanced_extract_tags(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Enhanced tag extraction with multiple fallback methods."""
        
        tags = super()._extract_tags(data)
        
        # Additional tag extraction patterns
        if not tags:
            # Try nested tag structures
            for key, value in data.items():
                if isinstance(value, dict) and "Tags" in value:
                    nested_tags = value["Tags"]
                    if isinstance(nested_tags, list):
                        for tag in nested_tags:
                            if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                                tags[tag["Key"]] = tag["Value"]
                    elif isinstance(nested_tags, dict):
                        tags.update(nested_tags)
        
        return tags
    
    def _enhanced_calculate_confidence_score(self, resource: StandardResource) -> float:
        """Enhanced confidence scoring with weighted factors."""
        
        score = 0.0
        max_score = 10.0
        
        # Core identification (high weight)
        if resource.resource_id and resource.resource_id != "unknown":
            score += 2.0
        if resource.resource_name:
            score += 1.5
        if resource.resource_arn:
            score += 1.5
        if resource.resource_type and resource.resource_type != "Unknown":
            score += 1.0
        
        # Metadata (medium weight)
        if resource.tags:
            score += 1.0
        if resource.status:
            score += 0.5
        if resource.created_date:
            score += 0.5
        
        # Extended fields (low weight)
        if resource.vpc_id:
            score += 0.5
        if resource.security_groups:
            score += 0.5
        if resource.account_id:
            score += 0.5
        
        return min(score / max_score, 1.0)


class EnhancedAWSDiscovery(IntelligentAWSDiscovery):
    """Enhanced discovery system with better service coverage."""
    
    def __init__(self, session: boto3.Session = None, regions: List[str] = None):
        super().__init__(session, regions)
        self.field_mapper = EnhancedFieldMapper()
        
        # Priority services for better coverage
        self.priority_services = [
            'cloudfront', 'iam', 'route53', 's3', 'lambda', 
            'ec2', 'rds', 'cloudformation', 'cloudwatch'
        ]
    
    def discover_all_services(self) -> List[StandardResource]:
        """Enhanced discovery with better service coverage."""
        
        self.logger.info("Starting enhanced AWS discovery...")
        
        all_resources = []
        
        # Process priority services
        for service in self.priority_services:
            try:
                resources = self.discover_service(service)
                all_resources.extend(resources)
                self.logger.info(f"Enhanced discovery: {service} found {len(resources)} resources")
            except Exception as e:
                self.logger.warning(f"Enhanced discovery failed for {service}: {e}")
        
        # Deduplicate and enhance
        all_resources = self._intelligent_deduplication(all_resources)
        self.discovered_resources.extend(all_resources)
        
        self.logger.info(f"Enhanced discovery complete: {len(all_resources)} resources")
        return all_resources
    
    def discover_service(self, service_name: str) -> List[StandardResource]:
        """Enhanced service discovery with better operation selection."""
        
        service_resources = []
        
        for region in self.regions:
            try:
                # Skip global services for non-primary regions
                if self._is_global_service(service_name) and region != 'us-east-1':
                    continue
                
                # Get service client
                client = self.session.client(service_name, region_name=region)
                
                # Get enhanced operations for this service
                operations = self._get_enhanced_discovery_operations(service_name, client)
                
                # Try each discovery operation
                for operation_name in operations:
                    try:
                        resources = self._discover_via_operation(
                            client, operation_name, service_name, region
                        )
                        service_resources.extend(resources)
                        
                        # Limit operations per service to avoid too many API calls
                        if len(service_resources) > 0:
                            break
                            
                    except Exception as e:
                        self.logger.debug(f"Operation {operation_name} failed for {service_name}: {e}")
                        continue
                        
            except Exception as e:
                self.logger.warning(f"Failed to create {service_name} client in {region}: {e}")
        
        # Enhanced deduplication for this service
        service_resources = self._intelligent_deduplication(service_resources)
        
        return service_resources
    
    def _get_enhanced_discovery_operations(self, service_name: str, client) -> List[str]:
        """Get prioritized discovery operations for a service."""
        
        # Get all available operations
        all_operations = client._service_model.operation_names
        
        # Service-specific operation priorities
        service_lower = service_name.lower()
        if service_lower in self.field_mapper.enhanced_service_patterns:
            preferred_ops = self.field_mapper.enhanced_service_patterns[service_lower].get("operations", [])
            # Prioritize preferred operations
            operations = [op for op in preferred_ops if op in all_operations]
            if operations:
                return operations
        
        # Fall back to generic discovery operations
        discovery_ops = [
            op for op in all_operations
            if op.startswith(("List", "Describe", "Get"))
            and not any(skip in op for skip in ["Policy", "Version", "Status", "Health", "Metrics"])
        ]
        
        # Prioritize List operations over Describe operations
        list_ops = [op for op in discovery_ops if op.startswith("List")]
        describe_ops = [op for op in discovery_ops if op.startswith("Describe")]
        
        return list_ops[:2] + describe_ops[:1]  # Limit to avoid too many calls
    
    def _is_global_service(self, service_name: str) -> bool:
        """Check if a service is global (not region-specific)."""
        
        global_services = {
            'cloudfront', 'iam', 'route53', 'waf', 'cloudformation',
            'organizations', 'support', 'trustedadvisor'
        }
        
        return service_name.lower() in global_services
'''

    # Write the enhanced content
    with open(intelligent_discovery_path, "w") as f:
        f.write(enhanced_content)

    print(f"✅ Created enhanced intelligent_discovery.py")

    # 3. Update the inventory.py to use enhanced discovery
    inventory_path = discovery_path / "inventory.py"
    if inventory_path.exists():
        # Read the current content
        with open(inventory_path, "r") as f:
            content = f.read()

        # Replace the import to use enhanced classes
        updated_content = content.replace(
            "from .intelligent_discovery import IntelligentAWSDiscovery, StandardResource",
            "from .intelligent_discovery import IntelligentAWSDiscovery, StandardResource, EnhancedAWSDiscovery, EnhancedFieldMapper",
        )

        # Replace the initialization to use enhanced discovery
        updated_content = updated_content.replace(
            "self.intelligent_discovery = IntelligentAWSDiscovery(",
            "self.intelligent_discovery = EnhancedAWSDiscovery(",
        )

        # Write back the updated content
        with open(inventory_path, "w") as f:
            f.write(updated_content)

        print(f"✅ Updated inventory.py to use enhanced discovery")

    # 4. Create a configuration file for easy switching
    config_content = """# Optimized Discovery Configuration
# This file controls the behavior of the optimized discovery system

[discovery]
# Enable enhanced intelligent discovery
use_enhanced_discovery = true

# Enable parallel processing for faster discovery
enable_parallel_processing = true

# Maximum number of parallel workers
max_workers = 4

# Priority services to discover first
priority_services = cloudfront,iam,route53,s3,lambda,ec2,rds,cloudformation,cloudwatch

# Confidence score thresholds
high_confidence_threshold = 0.7
medium_confidence_threshold = 0.4

[field_mapping]
# Enhanced field mapping settings
enable_service_specific_patterns = true
enable_enhanced_tag_extraction = true
enable_confidence_scoring = true

[performance]
# Performance optimization settings
operation_timeout = 30
max_operations_per_service = 3
enable_caching = true
"""

    config_path = discovery_path / "optimized_config.ini"
    with open(config_path, "w") as f:
        f.write(config_content)

    print(f"✅ Created configuration file: {config_path}")

    # 5. Create a test script
    test_script_content = '''#!/usr/bin/env python3
"""
Test script for the optimized discovery system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inventag.discovery import AWSResourceInventory
from datetime import datetime

def test_optimized_discovery():
    """Test the optimized discovery system."""
    
    print("🧪 Testing Optimized Discovery System")
    print("=" * 50)
    
    # Test with enhanced intelligent discovery
    inventory = AWSResourceInventory(regions=['us-east-1'])
    inventory.configure_discovery_mode(use_intelligent=True, standardized_output=True)
    
    start_time = datetime.now()
    resources = inventory.discover_resources()
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    
    print(f"\\n✅ Test Results:")
    print(f"  - Total Resources: {len(resources)}")
    print(f"  - Discovery Time: {duration:.2f} seconds")
    print(f"  - Resources/Second: {len(resources)/duration:.2f}")
    
    # Analyze services
    services = {}
    for resource in resources:
        service = resource.get('service', 'Unknown')
        services[service] = services.get(service, 0) + 1
    
    print(f"\\n📊 Service Breakdown:")
    for service, count in sorted(services.items()):
        print(f"  - {service}: {count} resources")
    
    # Analyze confidence scores
    high_conf = [r for r in resources if r.get('confidence_score', 0) >= 0.7]
    medium_conf = [r for r in resources if 0.4 <= r.get('confidence_score', 0) < 0.7]
    low_conf = [r for r in resources if r.get('confidence_score', 0) < 0.4]
    
    print(f"\\n🎯 Confidence Analysis:")
    print(f"  - High (≥0.7): {len(high_conf)} resources")
    print(f"  - Medium (0.4-0.7): {len(medium_conf)} resources")
    print(f"  - Low (<0.4): {len(low_conf)} resources")
    
    return resources

if __name__ == "__main__":
    test_optimized_discovery()
'''

    test_script_path = discovery_path / "test_optimized.py"
    with open(test_script_path, "w") as f:
        f.write(test_script_content)

    print(f"✅ Created test script: {test_script_path}")

    print(f"\n🎉 Integration Complete!")
    print(f"=" * 50)
    print(f"The optimized discovery system has been integrated into your inventag package.")
    print(f"")
    print(f"📋 What was done:")
    print(f"  1. ✅ Backed up original intelligent_discovery.py")
    print(f"  2. ✅ Created enhanced intelligent discovery with better service coverage")
    print(f"  3. ✅ Updated inventory.py to use enhanced discovery")
    print(f"  4. ✅ Created configuration file for easy customization")
    print(f"  5. ✅ Created test script for validation")
    print(f"")
    print(f"🚀 Next Steps:")
    print(f"  1. Run the test script: python inventag/discovery/test_optimized.py")
    print(f"  2. Customize settings in: inventag/discovery/optimized_config.ini")
    print(f"  3. Use your existing scripts - they will automatically use the enhanced system")
    print(f"")
    print(f"🔧 Key Improvements:")
    print(f"  - Better service coverage (CloudFront, IAM, Route53, S3, Lambda)")
    print(f"  - Enhanced field mapping with service-specific patterns")
    print(f"  - Improved confidence scoring")
    print(f"  - Better resource name and type detection")
    print(f"  - Parallel processing support for faster discovery")

    return True


if __name__ == "__main__":
    integrate_optimized_discovery()
