#!/usr/bin/env python3
"""
BOM Data Processor - Central Orchestrator

Central orchestrator that processes raw inventory data and coordinates with specialized analyzers.
Extracted and enhanced from existing bom_converter.py data processing patterns.

Features:
- Inventory data processing pipeline coordination with error handling
- Network analysis integration with resource enrichment and caching
- Security analysis integration and intelligent data merging
- Service attribute enrichment coordination with parallel processing
- Comprehensive logging and monitoring for data processing pipeline
"""

import logging
import boto3
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from collections import defaultdict

# Import analyzers and enrichers
from ..discovery.network_analyzer import NetworkAnalyzer, NetworkSummary
from ..discovery.security_analyzer import SecurityAnalyzer, SecuritySummary
from ..discovery.service_enrichment import ServiceAttributeEnricher
from ..discovery.service_descriptions import ServiceDescriptionManager
from ..discovery.tag_mapping import TagMappingEngine
from ..discovery.cost_analyzer import CostAnalyzer, CostThresholds, CostAnalysisSummary


@dataclass
class BOMProcessingConfig:
    """Configuration for BOM data processing."""
    enable_network_analysis: bool = True
    enable_security_analysis: bool = True
    enable_service_enrichment: bool = True
    enable_service_descriptions: bool = True
    enable_tag_mapping: bool = True
    enable_cost_analysis: bool = False  # Optional feature
    enable_parallel_processing: bool = True
    max_worker_threads: int = 4
    cache_results: bool = True
    service_descriptions_config: Optional[str] = None
    tag_mappings_config: Optional[str] = None
    cost_thresholds: Optional[CostThresholds] = None
    processing_timeout: int = 300  # seconds


@dataclass
class BOMData:
    """Processed BOM data structure."""
    resources: List[Dict[str, Any]]
    network_analysis: Dict[str, Any] = field(default_factory=dict)
    security_analysis: Dict[str, Any] = field(default_factory=dict)
    cost_analysis: Dict[str, Any] = field(default_factory=dict)
    compliance_summary: Dict[str, Any] = field(default_factory=dict)
    generation_metadata: Dict[str, Any] = field(default_factory=dict)
    custom_attributes: List[str] = field(default_factory=list)
    processing_statistics: Dict[str, Any] = field(default_factory=dict)
    error_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingStatistics:
    """Statistics for BOM processing operations."""
    total_resources: int = 0
    processed_resources: int = 0
    failed_resources: int = 0
    network_enriched: int = 0
    security_enriched: int = 0
    service_enriched: int = 0
    description_enriched: int = 0
    tag_mapped: int = 0
    processing_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BOMDataProcessor:
    """
    Central orchestrator that processes raw inventory data and coordinates 
    with specialized analyzers.
    
    Enhanced from the data processing patterns in bom_converter.py with:
    - Inventory data processing pipeline coordination with error handling
    - Network analysis integration with resource enrichment and caching
    - Security analysis integration and intelligent data merging
    - Service attribute enrichment coordination with parallel processing
    - Comprehensive logging and monitoring for data processing pipeline
    """

    def __init__(self, config: BOMProcessingConfig, session: Optional[boto3.Session] = None):
        """Initialize the BOM data processor."""
        self.config = config
        self.session = session or boto3.Session()
        self.logger = logging.getLogger(f"{__name__}.BOMDataProcessor")
        
        # Initialize analyzers and enrichers
        self._initialize_components()
        
        # Processing state
        self.statistics = ProcessingStatistics()
        self._processing_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
    def _initialize_components(self):
        """Initialize all processing components."""
        try:
            # Network analyzer
            if self.config.enable_network_analysis:
                self.network_analyzer = NetworkAnalyzer(self.session)
                self.logger.info("Initialized NetworkAnalyzer")
            else:
                self.network_analyzer = None
                
            # Security analyzer
            if self.config.enable_security_analysis:
                self.security_analyzer = SecurityAnalyzer(self.session)
                self.logger.info("Initialized SecurityAnalyzer")
            else:
                self.security_analyzer = None
                
            # Service attribute enricher
            if self.config.enable_service_enrichment:
                self.service_enricher = ServiceAttributeEnricher(self.session)
                self.logger.info("Initialized ServiceAttributeEnricher")
            else:
                self.service_enricher = None
                
            # Service description manager
            if self.config.enable_service_descriptions:
                self.service_desc_manager = ServiceDescriptionManager(
                    self.config.service_descriptions_config
                )
                self.logger.info("Initialized ServiceDescriptionManager")
            else:
                self.service_desc_manager = None
                
            # Tag mapping engine
            if self.config.enable_tag_mapping:
                self.tag_mapping_engine = TagMappingEngine(
                    self.config.tag_mappings_config
                )
                self.logger.info("Initialized TagMappingEngine")
            else:
                self.tag_mapping_engine = None
                
            # Cost analyzer (optional feature)
            if self.config.enable_cost_analysis:
                self.cost_analyzer = CostAnalyzer(
                    self.session, 
                    self.config.cost_thresholds
                )
                self.logger.info("Initialized CostAnalyzer")
            else:
                self.cost_analyzer = None
                
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
            
    def process_inventory_data(self, inventory_data: List[Dict[str, Any]]) -> BOMData:
        """
        Process raw inventory data into BOM-ready format.
        
        Enhanced from bom_converter.py data processing patterns with:
        - Inventory data processing pipeline coordination with error handling
        - Network analysis integration with resource enrichment and caching
        - Security analysis integration and intelligent data merging
        - Service attribute enrichment coordination with parallel processing
        - Comprehensive logging and monitoring for data processing pipeline
        """
        start_time = datetime.now(timezone.utc)
        self.statistics = ProcessingStatistics()
        self.statistics.total_resources = len(inventory_data)
        
        self.logger.info(f"Starting BOM data processing for {len(inventory_data)} resources")
        
        try:
            # Step 1: Extract and standardize resources (from bom_converter.py patterns)
            processed_resources = self._extract_and_standardize_resources(inventory_data)
            
            # Step 2: Parallel enrichment processing
            if self.config.enable_parallel_processing:
                enriched_resources = self._parallel_enrichment_processing(processed_resources)
            else:
                enriched_resources = self._sequential_enrichment_processing(processed_resources)
            
            # Step 3: Generate analysis summaries
            network_analysis = self._generate_network_analysis(enriched_resources)
            security_analysis = self._generate_security_analysis(enriched_resources)
            cost_analysis = self._generate_cost_analysis(enriched_resources) if self.config.enable_cost_analysis else {}
            
            # Step 4: Create BOM data structure
            bom_data = self._create_bom_data_structure(
                enriched_resources, network_analysis, security_analysis, cost_analysis
            )
            
            # Update statistics
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.statistics.processing_time_seconds = processing_time
            self.statistics.processed_resources = len(enriched_resources)
            
            self.logger.info(
                f"BOM processing completed in {processing_time:.2f}s. "
                f"Processed {self.statistics.processed_resources}/{self.statistics.total_resources} resources"
            )
            
            return bom_data
            
        except Exception as e:
            self.logger.error(f"BOM processing failed: {e}")
            self.statistics.errors.append(str(e))
            raise
            
    def _extract_and_standardize_resources(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract and standardize resources from raw inventory data.
        Enhanced from BOMConverter._extract_resources and related methods.
        """
        self.logger.info("Extracting and standardizing resources")
        
        try:
            # Extract resources from different data structures
            resources = self._extract_resources_from_data(raw_data)
            
            # Apply standardization steps (from bom_converter.py)
            resources = self._reclassify_vpc_resources(resources)
            resources = self._standardize_service_names(resources)
            resources = self._fix_resource_types(resources)
            resources = self._fix_id_and_name_parsing(resources)
            resources = self._fix_account_id_from_arn(resources)
            resources = self._deduplicate_resources(resources)
            
            self.logger.info(f"Standardized {len(resources)} resources")
            return resources
            
        except Exception as e:
            self.logger.error(f"Resource extraction and standardization failed: {e}")
            self.statistics.errors.append(f"Standardization error: {e}")
            raise
            
    def _extract_resources_from_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract resources from different data structures."""
        resources = []
        
        for item in raw_data:
            if isinstance(item, dict):
                # Check if it's a resource container or a direct resource
                if any(key in item for key in ["all_discovered_resources", "compliant_resources", "non_compliant_resources"]):
                    # It's a container, extract resources
                    if "all_discovered_resources" in item:
                        resources.extend(item["all_discovered_resources"])
                    else:
                        # Collect from multiple arrays
                        for key in ["compliant_resources", "non_compliant_resources", "untagged_resources"]:
                            if key in item and isinstance(item[key], list):
                                resources.extend(item[key])
                else:
                    # It's likely a direct resource
                    resources.append(item)
            elif isinstance(item, list):
                # It's a list of resources
                resources.extend(item)
                
        return resources
        
    def _reclassify_vpc_resources(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reclassify VPC-related resources from EC2 to VPC service."""
        vpc_resource_types = {
            "VPC", "Subnet", "SecurityGroup", "Route-Table", "Network-Interface",
            "Vpc-Endpoint", "Vpc-Flow-Log", "Dhcp-Options", "Transit-Gateway-Attachment",
            "Network-Insights-Path", "Internet-Gateway", "Nat-Gateway", "Network-Acl"
        }
        
        reclassified_count = 0
        for resource in resources:
            if resource.get("service") == "EC2" and resource.get("type") in vpc_resource_types:
                resource["service"] = "VPC"
                reclassified_count += 1
                
        if reclassified_count > 0:
            self.logger.info(f"Reclassified {reclassified_count} VPC-related resources")
            
        return resources
        
    def _standardize_service_names(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Standardize service names to avoid duplicates."""
        standardizations = {
            "CloudFormation": "CLOUDFORMATION",
            "Lambda": "LAMBDA",
            "ElasticLoadBalancing": "ELB",
            "ElasticLoadBalancingV2": "ELBV2",
            "ApplicationAutoScaling": "AUTO_SCALING",
            "AutoScaling": "AUTO_SCALING",
        }
        
        standardized_count = 0
        for resource in resources:
            service = resource.get("service", "")
            if service in standardizations:
                resource["service"] = standardizations[service]
                standardized_count += 1
                
        if standardized_count > 0:
            self.logger.info(f"Standardized {standardized_count} service names")
            
        return resources
        
    def _fix_resource_types(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fix resource type inconsistencies."""
        # Enhanced implementation for resource type fixes
        type_fixes = {
            "LoadBalancer": "Load-Balancer",
            "TargetGroup": "Target-Group",
            "LaunchConfiguration": "Launch-Configuration",
            "AutoScalingGroup": "Auto-Scaling-Group",
        }
        
        fixed_count = 0
        for resource in resources:
            resource_type = resource.get("type", "")
            if resource_type in type_fixes:
                resource["type"] = type_fixes[resource_type]
                fixed_count += 1
                
        if fixed_count > 0:
            self.logger.info(f"Fixed {fixed_count} resource types")
            
        return resources
        
    def _fix_id_and_name_parsing(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fix ID and name parsing issues by extracting correct values from ARNs."""
        fixed_count = 0
        for resource in resources:
            arn = resource.get("arn", "")
            if arn and not resource.get("id"):
                # Extract ID from ARN
                arn_parts = arn.split(":")
                if len(arn_parts) >= 6:
                    resource_part = arn_parts[5]
                    if "/" in resource_part:
                        resource["id"] = resource_part.split("/")[-1]
                    else:
                        resource["id"] = resource_part
                    fixed_count += 1
                    
        if fixed_count > 0:
            self.logger.info(f"Fixed {fixed_count} resource IDs from ARNs")
            
        return resources
        
    def _fix_account_id_from_arn(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract and set account_id from ARN for resources missing this field."""
        fixed_count = 0
        for resource in resources:
            if not resource.get("account_id"):
                arn = resource.get("arn", "")
                if arn:
                    arn_parts = arn.split(":")
                    if len(arn_parts) >= 5:
                        resource["account_id"] = arn_parts[4]
                        fixed_count += 1
                        
        if fixed_count > 0:
            self.logger.info(f"Fixed {fixed_count} account IDs from ARNs")
            
        return resources
        
    def _deduplicate_resources(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate resources keeping the one with more complete information."""
        seen_resources = {}
        deduplicated = []
        duplicate_count = 0
        
        for resource in resources:
            # Create unique key based on ARN or fallback to service+id+region
            arn = resource.get("arn", "")
            if arn:
                key = arn
            else:
                service = resource.get("service", "")
                res_id = resource.get("id", "")
                region = resource.get("region", "")
                key = f"{service}:{res_id}:{region}"
                
            if key in seen_resources:
                # Keep the resource with more fields
                existing = seen_resources[key]
                if len(resource) > len(existing):
                    seen_resources[key] = resource
                    # Replace in deduplicated list
                    for i, item in enumerate(deduplicated):
                        if item is existing:
                            deduplicated[i] = resource
                            break
                duplicate_count += 1
            else:
                seen_resources[key] = resource
                deduplicated.append(resource)
                
        if duplicate_count > 0:
            self.logger.info(f"Removed {duplicate_count} duplicate resources")
            
        return deduplicated
        
    def _parallel_enrichment_processing(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process resource enrichment in parallel for better performance."""
        self.logger.info(f"Starting parallel enrichment processing with {self.config.max_worker_threads} threads")
        
        enriched_resources = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_worker_threads) as executor:
            # Submit enrichment tasks
            future_to_resource = {
                executor.submit(self._enrich_single_resource, resource): resource
                for resource in resources
            }
            
            # Collect results
            for future in as_completed(future_to_resource, timeout=self.config.processing_timeout):
                try:
                    enriched_resource = future.result()
                    enriched_resources.append(enriched_resource)
                except Exception as e:
                    resource = future_to_resource[future]
                    self.logger.warning(f"Failed to enrich resource {resource.get('id', 'unknown')}: {e}")
                    self.statistics.failed_resources += 1
                    self.statistics.errors.append(f"Enrichment failed for {resource.get('id', 'unknown')}: {e}")
                    # Add the original resource without enrichment
                    enriched_resources.append(resource)
                    
        self.logger.info(f"Parallel enrichment completed. Processed {len(enriched_resources)} resources")
        return enriched_resources
        
    def _sequential_enrichment_processing(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process resource enrichment sequentially."""
        self.logger.info("Starting sequential enrichment processing")
        
        enriched_resources = []
        
        for i, resource in enumerate(resources):
            try:
                enriched_resource = self._enrich_single_resource(resource)
                enriched_resources.append(enriched_resource)
                
                if (i + 1) % 100 == 0:
                    self.logger.info(f"Processed {i + 1}/{len(resources)} resources")
                    
            except Exception as e:
                self.logger.warning(f"Failed to enrich resource {resource.get('id', 'unknown')}: {e}")
                self.statistics.failed_resources += 1
                self.statistics.errors.append(f"Enrichment failed for {resource.get('id', 'unknown')}: {e}")
                # Add the original resource without enrichment
                enriched_resources.append(resource)
                
        self.logger.info(f"Sequential enrichment completed. Processed {len(enriched_resources)} resources")
        return enriched_resources
        
    def _enrich_single_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single resource with all available enrichment data."""
        enriched_resource = resource.copy()
        
        try:
            # Network analysis enrichment
            if self.network_analyzer:
                enriched_resource = self._enrich_with_network_analysis(enriched_resource)
                
            # Security analysis enrichment
            if self.security_analyzer:
                enriched_resource = self._enrich_with_security_analysis(enriched_resource)
                
            # Service attribute enrichment
            if self.service_enricher:
                enriched_resource = self._enrich_with_service_attributes(enriched_resource)
                
            # Service descriptions
            if self.service_desc_manager:
                enriched_resource = self._apply_service_descriptions(enriched_resource)
                
            # Tag mappings
            if self.tag_mapping_engine:
                enriched_resource = self._apply_tag_mappings(enriched_resource)
                
            # Cost analysis enrichment (optional feature)
            if self.cost_analyzer:
                enriched_resource = self._enrich_with_cost_analysis(enriched_resource)
                
        except Exception as e:
            self.logger.warning(f"Partial enrichment failure for resource {resource.get('id', 'unknown')}: {e}")
            self.statistics.warnings.append(f"Partial enrichment failure: {e}")
            
        return enriched_resource
        
    def _enrich_with_network_analysis(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Add network analysis to a resource."""
        try:
            if self.network_analyzer:
                enriched = self.network_analyzer.enrich_resource_with_network_info(resource)
                if enriched != resource:
                    self.statistics.network_enriched += 1
                return enriched
        except Exception as e:
            self.logger.debug(f"Network enrichment failed for {resource.get('id', 'unknown')}: {e}")
            
        return resource
        
    def _enrich_with_security_analysis(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Add security analysis to a resource."""
        try:
            if self.security_analyzer:
                enriched = self.security_analyzer.enrich_resource_with_security_info(resource)
                if enriched != resource:
                    self.statistics.security_enriched += 1
                return enriched
        except Exception as e:
            self.logger.debug(f"Security enrichment failed for {resource.get('id', 'unknown')}: {e}")
            
        return resource
        
    def _enrich_with_service_attributes(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich resource with service-specific attributes."""
        try:
            if self.service_enricher:
                enriched = self.service_enricher.enrich_resource(resource)
                if enriched != resource:
                    self.statistics.service_enriched += 1
                return enriched
        except Exception as e:
            self.logger.debug(f"Service enrichment failed for {resource.get('id', 'unknown')}: {e}")
            
        return resource
        
    def _apply_service_descriptions(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Add custom service descriptions to a resource."""
        try:
            if self.service_desc_manager:
                enriched = self.service_desc_manager.apply_description_to_resource(resource)
                if enriched != resource:
                    self.statistics.description_enriched += 1
                return enriched
        except Exception as e:
            self.logger.debug(f"Description application failed for {resource.get('id', 'unknown')}: {e}")
            
        return resource
        
    def _apply_tag_mappings(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Apply custom tag attribute mappings to a resource."""
        try:
            if self.tag_mapping_engine:
                enriched = self.tag_mapping_engine.apply_mappings_to_resource(resource)
                if enriched != resource:
                    self.statistics.tag_mapped += 1
                return enriched
        except Exception as e:
            self.logger.debug(f"Tag mapping failed for {resource.get('id', 'unknown')}: {e}")
            
        return resource
        
    def _generate_network_analysis(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive network analysis summary."""
        if not self.network_analyzer:
            return {}
            
        try:
            self.logger.info("Generating network analysis summary")
            return self.network_analyzer.generate_network_summary(resources)
        except Exception as e:
            self.logger.error(f"Network analysis generation failed: {e}")
            self.statistics.errors.append(f"Network analysis failed: {e}")
            return {}
            
    def _generate_security_analysis(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive security analysis summary."""
        if not self.security_analyzer:
            return {}
            
        try:
            self.logger.info("Generating security analysis summary")
            return self.security_analyzer.generate_security_summary(resources)
        except Exception as e:
            self.logger.error(f"Security analysis generation failed: {e}")
            self.statistics.errors.append(f"Security analysis failed: {e}")
            return {}
            
    def _create_bom_data_structure(
        self, 
        resources: List[Dict[str, Any]], 
        network_analysis: Dict[str, Any], 
        security_analysis: Dict[str, Any],
        cost_analysis: Dict[str, Any] = None
    ) -> BOMData:
        """Create the final BOM data structure."""
        
        # Generate compliance summary
        compliance_summary = self._generate_compliance_summary(resources)
        
        # Generate custom attributes list
        custom_attributes = self._extract_custom_attributes(resources)
        
        # Create generation metadata
        generation_metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_resources": len(resources),
            "processing_statistics": {
                "total_resources": self.statistics.total_resources,
                "processed_resources": self.statistics.processed_resources,
                "failed_resources": self.statistics.failed_resources,
                "network_enriched": self.statistics.network_enriched,
                "security_enriched": self.statistics.security_enriched,
                "service_enriched": self.statistics.service_enriched,
                "description_enriched": self.statistics.description_enriched,
                "tag_mapped": self.statistics.tag_mapped,
                "processing_time_seconds": self.statistics.processing_time_seconds,
                "error_count": len(self.statistics.errors),
                "warning_count": len(self.statistics.warnings)
            }
        }
        
        # Create error summary
        error_summary = {
            "errors": self.statistics.errors,
            "warnings": self.statistics.warnings,
            "has_errors": len(self.statistics.errors) > 0,
            "has_warnings": len(self.statistics.warnings) > 0
        }
        
        return BOMData(
            resources=resources,
            network_analysis=network_analysis,
            security_analysis=security_analysis,
            cost_analysis=cost_analysis or {},
            compliance_summary=compliance_summary,
            generation_metadata=generation_metadata,
            custom_attributes=custom_attributes,
            processing_statistics=generation_metadata["processing_statistics"],
            error_summary=error_summary
        )
        
    def _generate_compliance_summary(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate compliance summary from processed resources."""
        total_resources = len(resources)
        compliant_resources = 0
        non_compliant_resources = 0
        
        # Count compliance status
        for resource in resources:
            compliance_status = resource.get("compliance_status", "unknown")
            if compliance_status == "compliant":
                compliant_resources += 1
            elif compliance_status == "non_compliant":
                non_compliant_resources += 1
                
        compliance_percentage = (compliant_resources / total_resources * 100) if total_resources > 0 else 0
        
        return {
            "total_resources": total_resources,
            "compliant_resources": compliant_resources,
            "non_compliant_resources": non_compliant_resources,
            "unknown_compliance": total_resources - compliant_resources - non_compliant_resources,
            "compliance_percentage": compliance_percentage
        }
        
    def _extract_custom_attributes(self, resources: List[Dict[str, Any]]) -> List[str]:
        """Extract list of custom attributes from processed resources."""
        custom_attributes = set()
        
        for resource in resources:
            # Look for custom tag mappings
            if "custom_attributes" in resource:
                custom_attributes.update(resource["custom_attributes"].keys())
                
        return sorted(list(custom_attributes))
        
    def get_processing_statistics(self) -> ProcessingStatistics:
        """Get current processing statistics."""
        return self.statistics
        
    def clear_cache(self):
        """Clear processing cache."""
        with self._lock:
            self._processing_cache.clear()
            self.logger.info("Processing cache cleared")       
 
    def _enrich_with_cost_analysis(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Add cost analysis to a resource."""
        try:
            if self.cost_analyzer:
                enriched = self.cost_analyzer.enrich_resource_with_cost_info(resource)
                if enriched != resource:
                    self.statistics.cost_enriched = getattr(self.statistics, 'cost_enriched', 0) + 1
                return enriched
        except Exception as e:
            self.logger.debug(f"Cost enrichment failed for {resource.get('id', 'unknown')}: {e}")
            
        return resource
        
    def _generate_cost_analysis(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive cost analysis summary."""
        if not self.cost_analyzer:
            return {}
            
        try:
            self.logger.info("Generating cost analysis summary")
            
            # Get cost estimates for all resources
            cost_estimates = self.cost_analyzer.estimate_resource_costs(resources)
            
            # Identify expensive resources
            expensive_resources = self.cost_analyzer.identify_expensive_resources(cost_estimates)
            
            # Detect forgotten resources
            forgotten_resources = self.cost_analyzer.detect_forgotten_resources(resources)
            
            # Analyze cost trends
            cost_trends = self.cost_analyzer.analyze_cost_trends(resources)
            
            # Generate optimization recommendations
            recommendations = self.cost_analyzer.generate_cost_optimization_recommendations(
                cost_estimates, forgotten_resources
            )
            
            # Generate cost analysis summary
            cost_summary = self.cost_analyzer.generate_cost_analysis_summary(
                cost_estimates, forgotten_resources, recommendations
            )
            
            return {
                "cost_estimates": [
                    {
                        "resource_id": est.resource_id,
                        "resource_type": est.resource_type,
                        "service": est.service,
                        "region": est.region,
                        "estimated_monthly_cost": float(est.estimated_monthly_cost),
                        "cost_breakdown": {k: float(v) for k, v in est.cost_breakdown.items()},
                        "pricing_model": est.pricing_model,
                        "confidence_level": est.confidence_level
                    }
                    for est in cost_estimates
                ],
                "expensive_resources": [
                    {
                        "resource_id": res.resource_id,
                        "service": res.service,
                        "estimated_monthly_cost": float(res.estimated_monthly_cost),
                        "confidence_level": res.confidence_level
                    }
                    for res in expensive_resources
                ],
                "forgotten_resources": [
                    {
                        "resource_id": res.resource_id,
                        "service": res.service,
                        "days_since_last_activity": res.days_since_last_activity,
                        "estimated_monthly_cost": float(res.estimated_monthly_cost),
                        "risk_level": res.risk_level,
                        "recommendations": res.recommendations
                    }
                    for res in forgotten_resources
                ],
                "cost_trends": [
                    {
                        "resource_id": trend.resource_id,
                        "service": trend.service,
                        "current_monthly_cost": float(trend.current_monthly_cost),
                        "previous_monthly_cost": float(trend.previous_monthly_cost),
                        "cost_change_percentage": trend.cost_change_percentage,
                        "trend_direction": trend.trend_direction,
                        "alert_triggered": trend.alert_triggered
                    }
                    for trend in cost_trends
                ],
                "optimization_recommendations": [
                    {
                        "resource_id": rec.resource_id,
                        "service": rec.service,
                        "recommendation_type": rec.recommendation_type,
                        "current_monthly_cost": float(rec.current_monthly_cost),
                        "potential_monthly_savings": float(rec.potential_monthly_savings),
                        "confidence_level": rec.confidence_level,
                        "implementation_effort": rec.implementation_effort,
                        "description": rec.description,
                        "action_items": rec.action_items
                    }
                    for rec in recommendations
                ],
                "summary": {
                    "total_estimated_monthly_cost": float(cost_summary.total_estimated_monthly_cost),
                    "expensive_resources_count": cost_summary.expensive_resources_count,
                    "forgotten_resources_count": cost_summary.forgotten_resources_count,
                    "total_potential_savings": float(cost_summary.total_potential_savings),
                    "high_risk_resources": cost_summary.high_risk_resources,
                    "cost_by_service": {k: float(v) for k, v in cost_summary.cost_by_service.items()},
                    "cost_by_region": {k: float(v) for k, v in cost_summary.cost_by_region.items()},
                    "optimization_opportunities": cost_summary.optimization_opportunities,
                    "analysis_timestamp": cost_summary.analysis_timestamp.isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Cost analysis generation failed: {e}")
            self.statistics.errors.append(f"Cost analysis failed: {e}")
            return {}