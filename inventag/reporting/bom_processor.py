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
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, wait
import threading
from collections import defaultdict

# Import analyzers and enrichers
from ..discovery.network_analyzer import NetworkAnalyzer, NetworkSummary
from ..discovery.security_analyzer import SecurityAnalyzer, SecuritySummary
from ..discovery.service_enrichment import ServiceAttributeEnricher
from ..discovery.service_descriptions import ServiceDescriptionManager
from ..discovery.arn_utils import id_tail, parse_arn
from ..discovery.tag_mapping import TagMappingEngine
from ..security.secret_values import mask_resource, mask_resources
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

    def __post_init__(self) -> None:
        # From here on, a later assignment to enable_service_enrichment is the
        # user's (the --bom-config file is applied that way); the default and
        # the constructor argument are not.
        object.__setattr__(self, "_enrichment_key_set_by_user", False)

    def __setattr__(self, name: str, value: Any) -> None:
        if (
            name == "enable_service_enrichment"
            and "_enrichment_key_set_by_user" in self.__dict__
        ):
            object.__setattr__(self, "_enrichment_key_set_by_user", bool(value))
        object.__setattr__(self, name, value)


def analysis_resource_key(resource: Dict[str, Any]) -> tuple:
    """What identifies a row when asking if two reports hold the same rows."""
    return (
        resource.get("service"),
        resource.get("type"),
        resource.get("id"),
        resource.get("region"),
        resource.get("source_account_id"),
    )


@dataclass
class AnalysisResults:
    """What the network and security analyzers found for one set of resources.

    Kept on the BOM data so the workbook writer does not read the account a
    second time. ``resource_keys`` names the rows analysed: a report of other
    rows (one account of several) must analyse its own.
    """

    resource_keys: tuple
    vpcs: Optional[Dict[str, Any]] = None
    security_groups: Optional[Dict[str, Any]] = None


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
    # The analyzers' own results for ``resources`` (None when none was made).
    analysis_results: Optional[AnalysisResults] = field(
        default=None, repr=False, compare=False
    )


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
    masked_values: int = 0
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

    def __init__(
        self, config: BOMProcessingConfig, session: Optional[boto3.Session] = None
    ):
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
        # What the analyzers found in the last run (see AnalysisResults)
        self._analysis_found: Dict[str, Any] = {}

    def _count(self, name: str) -> None:
        """Add one to a statistics counter (enrichment runs in several threads)."""
        with self._lock:
            setattr(self.statistics, name, getattr(self.statistics, name, 0) + 1)

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

            # Service attribute enricher. It is built, but no step calls it:
            # it has no per-resource method, so enrichment never ran. Whether
            # to make it run is the owner's decision. Tell a user who
            # switched it on that it has no effect.
            if self.config.enable_service_enrichment:
                self.service_enricher = ServiceAttributeEnricher(self.session)
                self.logger.info("Initialized ServiceAttributeEnricher")
            else:
                self.service_enricher = None
            if getattr(self.config, "_enrichment_key_set_by_user", False):
                self.logger.warning(
                    "enable_service_enrichment is set to true, but service "
                    "attribute enrichment is not available in this version: "
                    "the setting has no effect and the report is unchanged"
                )

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
                    self.session, self.config.cost_thresholds
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
        self._analysis_found = {}
        self.statistics.total_resources = len(inventory_data)

        self.logger.info(
            f"Starting BOM data processing for {len(inventory_data)} resources"
        )

        try:
            # Step 1: Extract and standardize resources (from bom_converter.py patterns)
            processed_resources = self._extract_and_standardize_resources(
                inventory_data
            )

            # Step 2: Network and security analysis. These read the account once
            # (read-only calls) and fill the analyzers' caches.
            network_analysis = self._generate_network_analysis(processed_resources)
            security_analysis = self._generate_security_analysis(processed_resources)

            # Step 3: Tell every resource which VPC, subnet and security groups it
            # uses, from those caches (no further AWS calls)
            processed_resources = self._map_network_and_security(processed_resources)

            # Step 4: Per-resource enrichment (service attributes, descriptions,
            # tag mappings, cost)
            if self.config.enable_parallel_processing:
                enriched_resources = self._parallel_enrichment_processing(
                    processed_resources
                )
            else:
                enriched_resources = self._sequential_enrichment_processing(
                    processed_resources
                )
            # Enrichment may copy more of a Describe response into the
            # resource (service attributes): hide secret values again.
            enriched_resources = mask_resources(enriched_resources)

            cost_analysis = (
                self._generate_cost_analysis(enriched_resources)
                if self.config.enable_cost_analysis
                else {}
            )

            # Update statistics before they are copied into the BOM metadata
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.statistics.processing_time_seconds = processing_time
            self.statistics.processed_resources = len(enriched_resources)

            # Step 4: Create BOM data structure
            bom_data = self._create_bom_data_structure(
                enriched_resources, network_analysis, security_analysis, cost_analysis
            )

            if self._analysis_found:
                bom_data.analysis_results = AnalysisResults(
                    resource_keys=tuple(
                        analysis_resource_key(r) for r in bom_data.resources
                    ),
                    vpcs=self._analysis_found.get("vpcs"),
                    security_groups=self._analysis_found.get("security_groups"),
                )

            self.logger.info(
                f"BOM processing completed in {processing_time:.2f}s. "
                f"Processed {self.statistics.processed_resources}/{self.statistics.total_resources} resources"
            )

            return bom_data

        except Exception as e:
            self.logger.error(f"BOM processing failed: {e}")
            self.statistics.errors.append(str(e))
            raise

    def _extract_and_standardize_resources(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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

            # Secret values never go into a report (names stay, values are hidden)
            masked = sum(mask_resource(r)[1] for r in resources)
            if masked:
                resources = mask_resources(resources)
                self.statistics.masked_values = masked
                self.logger.info(
                    f"Hid {masked} secret value(s) (such as environment variable "
                    "values and user data) before writing reports"
                )

            self.logger.info(f"Standardized {len(resources)} resources")
            return resources

        except Exception as e:
            self.logger.error(f"Resource extraction and standardization failed: {e}")
            self.statistics.errors.append(f"Standardization error: {e}")
            raise

    def _extract_resources_from_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract resources from different data structures."""
        resources = []

        for item in raw_data:
            if isinstance(item, dict):
                # Check if it's a resource container or a direct resource
                if any(
                    key in item
                    for key in [
                        "all_discovered_resources",
                        "compliant_resources",
                        "non_compliant_resources",
                    ]
                ):
                    # It's a container, extract resources
                    if "all_discovered_resources" in item:
                        resources.extend(item["all_discovered_resources"])
                    else:
                        # Collect from multiple arrays
                        for key in [
                            "compliant_resources",
                            "non_compliant_resources",
                            "untagged_resources",
                        ]:
                            if key in item and isinstance(item[key], list):
                                resources.extend(item[key])
                else:
                    # It's likely a direct resource
                    resources.append(item)
            elif isinstance(item, list):
                # It's a list of resources
                resources.extend(item)

        return resources

    def _reclassify_vpc_resources(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Reclassify VPC-related resources from EC2 to VPC service."""
        vpc_resource_types = {
            "VPC",
            "Subnet",
            "SecurityGroup",
            "Route-Table",
            "Network-Interface",
            "Vpc-Endpoint",
            "Vpc-Flow-Log",
            "Dhcp-Options",
            "Transit-Gateway-Attachment",
            "Network-Insights-Path",
            "Internet-Gateway",
            "Nat-Gateway",
            "Network-Acl",
        }

        reclassified_count = 0
        for resource in resources:
            if (
                resource.get("service") == "EC2"
                and resource.get("type") in vpc_resource_types
            ):
                resource["service"] = "VPC"
                reclassified_count += 1

        if reclassified_count > 0:
            self.logger.info(f"Reclassified {reclassified_count} VPC-related resources")

        return resources

    def _standardize_service_names(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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

    def _fix_resource_types(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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

    def _fix_id_and_name_parsing(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fix ID and name parsing issues by extracting correct values from ARNs."""
        fixed_count = 0
        for resource in resources:
            arn = resource.get("arn", "")
            if arn and not resource.get("id"):
                # The last segment of the resource part ("function:name" and
                # "type/name" both give the name)
                tail = id_tail(arn)
                if tail:
                    resource["id"] = tail
                    fixed_count += 1

        if fixed_count > 0:
            self.logger.info(f"Fixed {fixed_count} resource IDs from ARNs")

        return resources

    def _fix_account_id_from_arn(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract and set account_id from ARN for resources missing this field."""
        fixed_count = 0
        source_account_fixed = 0

        for resource in resources:
            arn = resource.get("arn", "")
            account_from_arn = None

            # Extract account ID from ARN if available
            parsed = parse_arn(arn) if arn else None
            if parsed:
                account_from_arn = parsed["account"] or None

            # Fix account_id field if missing
            if not resource.get("account_id") and account_from_arn:
                resource["account_id"] = account_from_arn
                fixed_count += 1

            # Fix source_account_id if it's still "default" but we have real account ID from ARN
            if (
                resource.get("source_account_id") == "default"
                and account_from_arn
                and account_from_arn != "default"
            ):
                resource["source_account_id"] = account_from_arn
                source_account_fixed += 1

        if fixed_count > 0:
            self.logger.info(f"Fixed {fixed_count} account IDs from ARNs")
        if source_account_fixed > 0:
            self.logger.info(
                f"Fixed {source_account_fixed} source_account_id fields from 'default' to actual account ID"
            )

        return resources

    @staticmethod
    def _dedup_key(resource: Dict[str, Any]) -> Optional[tuple]:
        """Identity of a resource, or None when it has no identity to compare.

        The ARN says everything (it holds the account, region, type and ID).
        Without one, the key is account + service + type + ID + region, so the
        same ID in two accounts is two resources. A resource with neither ARN
        nor ID cannot be matched to another one and is never merged.
        """
        arn = resource.get("arn") or ""
        if arn:
            return ("arn", arn)
        res_id = resource.get("id") or resource.get("resource_id") or ""
        if not res_id:
            return None
        return (
            "id",
            resource.get("source_account_id") or resource.get("account_id") or "",
            resource.get("service") or "",
            resource.get("type") or resource.get("resource_type") or "",
            res_id,
            resource.get("region") or "",
        )

    @staticmethod
    def _is_blank(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    def _deduplicate_resources(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate resources, keeping the one with more fields.

        Fields that only the discarded copy has (for example tags that came
        from the other discovery path) are copied onto the kept one. Order of
        first appearance is kept.
        """
        seen_resources: Dict[tuple, int] = {}
        deduplicated: List[Dict[str, Any]] = []
        duplicate_count = 0

        for resource in resources:
            key = self._dedup_key(resource)
            if key is None:
                deduplicated.append(resource)
                continue

            if key in seen_resources:
                index = seen_resources[key]
                existing = deduplicated[index]
                if len(resource) > len(existing):
                    winner, loser = dict(resource), existing
                else:
                    winner, loser = existing, resource
                for name, value in loser.items():
                    if name not in winner or (
                        self._is_blank(winner[name]) and not self._is_blank(value)
                    ):
                        if winner is existing:
                            winner = dict(existing)
                        winner[name] = value
                deduplicated[index] = winner
                duplicate_count += 1
            else:
                seen_resources[key] = len(deduplicated)
                deduplicated.append(resource)

        if duplicate_count > 0:
            self.logger.info(f"Removed {duplicate_count} duplicate resources")

        return deduplicated

    def _parallel_enrichment_processing(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process resource enrichment in parallel for better performance."""
        self.logger.info(
            f"Starting parallel enrichment processing with {self.config.max_worker_threads} threads"
        )

        # Results go back in the order of the input, so the same inventory gives
        # the same resource order on every run whatever thread finishes first.
        enriched_resources: List[Optional[Dict[str, Any]]] = [None] * len(resources)

        executor = ThreadPoolExecutor(max_workers=self.config.max_worker_threads)
        try:
            futures = [
                executor.submit(self._enrich_single_resource, resource)
                for resource in resources
            ]
            done, not_done = wait(futures, timeout=self.config.processing_timeout)
            for index, future in enumerate(futures):
                resource = resources[index]
                if future in not_done:
                    future.cancel()
                    # Not enriched in time: keep the resource as it was found.
                    enriched_resources[index] = resource
                    continue
                try:
                    enriched_resources[index] = future.result()
                except Exception as e:
                    self.logger.warning(
                        f"Failed to enrich resource {resource.get('id', 'unknown')}: {e}"
                    )
                    self.statistics.failed_resources += 1
                    self.statistics.errors.append(
                        f"Enrichment failed for {resource.get('id', 'unknown')}: {e}"
                    )
                    # Add the original resource without enrichment
                    enriched_resources[index] = resource
            if not_done:
                message = (
                    f"Enrichment did not finish within {self.config.processing_timeout}s "
                    f"for {len(not_done)} of {len(resources)} resources; they are "
                    "in the report without enrichment"
                )
                self.logger.warning(message)
                self.statistics.warnings.append(message)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        self.logger.info(
            f"Parallel enrichment completed. Processed {len(enriched_resources)} resources"
        )
        return enriched_resources

    def _sequential_enrichment_processing(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                self.logger.warning(
                    f"Failed to enrich resource {resource.get('id', 'unknown')}: {e}"
                )
                self.statistics.failed_resources += 1
                self.statistics.errors.append(
                    f"Enrichment failed for {resource.get('id', 'unknown')}: {e}"
                )
                # Add the original resource without enrichment
                enriched_resources.append(resource)

        self.logger.info(
            f"Sequential enrichment completed. Processed {len(enriched_resources)} resources"
        )
        return enriched_resources

    def _enrich_single_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single resource with all available enrichment data."""
        enriched_resource = resource.copy()

        try:
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
            self.logger.warning(
                f"Partial enrichment failure for resource {resource.get('id', 'unknown')}: {e}"
            )
            self.statistics.warnings.append(f"Partial enrichment failure: {e}")

        return enriched_resource

    def _map_network_and_security(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Add VPC, subnet and security group context to all resources.

        Uses the analyzers' own mapping methods on the whole list, after the
        analysis filled their caches. A failure leaves the resources as they
        were and is recorded as a warning.
        """
        for analyzer, method, counter in (
            (self.network_analyzer, "map_resources_to_network", "network_enriched"),
            (
                self.security_analyzer,
                "map_resources_to_security_groups",
                "security_enriched",
            ),
        ):
            if analyzer is None:
                continue
            try:
                mapped = getattr(analyzer, method)(resources)
            except Exception as e:
                message = f"{method} failed: {e}"
                self.logger.warning(message)
                self.statistics.warnings.append(message)
                continue
            if not isinstance(mapped, list) or len(mapped) != len(resources):
                message = f"{method} did not return one result per resource; ignored"
                self.logger.warning(message)
                self.statistics.warnings.append(message)
                continue
            changed = sum(
                1 for before, after in zip(resources, mapped) if before != after
            )
            with self._lock:
                setattr(
                    self.statistics,
                    counter,
                    getattr(self.statistics, counter, 0) + changed,
                )
            resources = mapped
        return resources

    def _apply_service_descriptions(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Add the service description from --service-descriptions to a resource.

        The column appears only if the user gave a descriptions file, so the
        default report keeps its columns.
        """
        if not self.service_desc_manager or not self.config.service_descriptions_config:
            return resource
        try:
            description = self.service_desc_manager.get_dynamic_description(resource)
            if description:
                enriched = dict(resource)
                enriched["service_description"] = description
                self._count("description_enriched")
                return enriched
        except Exception as e:
            self.logger.warning(
                f"Description application failed for {resource.get('id', 'unknown')}: {e}"
            )

        return resource

    def _apply_tag_mappings(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Add one column for each mapping in the --tag-mappings file.

        The column name is the mapping's column name. The value is the tag
        value, or the mapping's default value if the resource has no such tag.
        """
        if not self.tag_mapping_engine or not self.config.tag_mappings_config:
            return resource
        try:
            result = self.tag_mapping_engine.extract_custom_attributes(resource)
            if result.mapped_attributes:
                enriched = dict(resource)
                for column, value in result.mapped_attributes.items():
                    # Never replace a discovered field with a mapped value
                    enriched.setdefault(column, value)
                self._count("tag_mapped")
                return enriched
        except Exception as e:
            self.logger.warning(
                f"Tag mapping failed for {resource.get('id', 'unknown')}: {e}"
            )

        return resource

    def _generate_network_analysis(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate comprehensive network analysis summary."""
        if not self.network_analyzer:
            return {}

        try:
            self.logger.info("Generating network analysis summary")
            # First analyze VPC resources, then generate summary
            vpc_resources = [
                r
                for r in resources
                if r.get("service") == "VPC" and r.get("type") in ["VPC", "Subnet"]
            ]
            if vpc_resources:
                # All resources go in: the analyzer uses them to list which
                # resources sit in each VPC and subnet.
                vpc_analysis = self.network_analyzer.analyze_vpc_resources(resources)
                summary = self.network_analyzer.generate_network_summary(vpc_analysis)
                result = self._network_summary_to_dict(summary, vpc_analysis)
                self._analysis_found["vpcs"] = vpc_analysis
                return result
            return {}
        except Exception as e:
            self.logger.error(f"Network analysis generation failed: {e}")
            self.statistics.errors.append(f"Network analysis failed: {e}")
            return {}

    def _generate_security_analysis(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate comprehensive security analysis summary."""
        if not self.security_analyzer:
            return {}

        try:
            self.logger.info("Generating security analysis summary")
            # First analyze security groups, then generate summary
            sg_resources = [
                r
                for r in resources
                if r.get("service") == "VPC" and r.get("type") == "SecurityGroup"
            ]
            if sg_resources:
                sg_analysis = self.security_analyzer.analyze_security_groups(resources)
                # generate_security_summary expects the analysis keyed by kind
                summary = self.security_analyzer.generate_security_summary(
                    {"security_groups": sg_analysis}
                )
                result = self._security_summary_to_dict(summary, sg_analysis)
                self._analysis_found["security_groups"] = sg_analysis
                return result
            return {}
        except Exception as e:
            self.logger.error(f"Security analysis generation failed: {e}")
            self.statistics.errors.append(f"Security analysis failed: {e}")
            return {}

    @staticmethod
    def _summary_as_dict(summary: Any) -> Dict[str, Any]:
        """Return an analyzer summary (dataclass or mapping) as a plain dict."""
        if is_dataclass(summary) and not isinstance(summary, type):
            return asdict(summary)
        if isinstance(summary, dict):
            return dict(summary)
        raise TypeError(f"Unsupported analysis summary type: {type(summary).__name__}")

    def _network_summary_to_dict(
        self, summary: Any, vpc_analysis: Any
    ) -> Dict[str, Any]:
        """
        Convert the NetworkSummary dataclass into the dictionary that BOMData,
        the document validator and the Excel/Word builders expect.
        """
        data = self._summary_as_dict(summary)
        if isinstance(vpc_analysis, dict) and "vpc_utilization" not in data:
            data["vpc_utilization"] = {
                vpc_id: {
                    "name": vpc.vpc_name,
                    "cidr_block": vpc.cidr_block,
                    "utilization_percentage": vpc.utilization_percentage,
                    "available_ips": vpc.available_ips,
                }
                for vpc_id, vpc in vpc_analysis.items()
            }
        return data

    def _security_summary_to_dict(
        self, summary: Any, sg_analysis: Any
    ) -> Dict[str, Any]:
        """
        Convert the SecuritySummary dataclass into the dictionary that BOMData,
        the document validator and the Excel/Word builders expect.

        The builders read ``overly_permissive_rules`` as a list of rule
        dictionaries and ``high_risk_rules`` as a count, so the summary's
        integer count moves to ``overly_permissive_rule_count``.
        """
        data = self._summary_as_dict(summary)
        if not isinstance(sg_analysis, dict):
            return data

        if isinstance(data.get("overly_permissive_rules"), int):
            data["overly_permissive_rule_count"] = data["overly_permissive_rules"]

        rules = []
        for risk in self.security_analyzer.identify_overly_permissive_rules(
            sg_analysis
        ):
            peer = risk.get("source") or risk.get("destination") or ""
            rules.append(
                {
                    **risk,
                    "group_id": risk.get("security_group_id", ""),
                    "rule": (
                        f"{risk.get('rule_type', '')} {risk.get('protocol', '')} "
                        f"{risk.get('port_range', '')} {peer}"
                    ).strip(),
                }
            )
        data["overly_permissive_rules"] = rules
        data["high_risk_rules"] = sum(
            1 for rule in rules if rule.get("risk_level") in ("high", "critical")
        )
        return data

    def _create_bom_data_structure(
        self,
        resources: List[Dict[str, Any]],
        network_analysis: Dict[str, Any],
        security_analysis: Dict[str, Any],
        cost_analysis: Dict[str, Any] = None,
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
                "warning_count": len(self.statistics.warnings),
            },
        }

        # Create error summary
        error_summary = {
            "errors": self.statistics.errors,
            "warnings": self.statistics.warnings,
            "has_errors": len(self.statistics.errors) > 0,
            "has_warnings": len(self.statistics.warnings) > 0,
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
            error_summary=error_summary,
        )

    def _generate_compliance_summary(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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

        compliance_percentage = (
            (compliant_resources / total_resources * 100) if total_resources > 0 else 0
        )

        return {
            "total_resources": total_resources,
            "compliant_resources": compliant_resources,
            "non_compliant_resources": non_compliant_resources,
            "unknown_compliance": total_resources
            - compliant_resources
            - non_compliant_resources,
            "compliance_percentage": compliance_percentage,
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
                    self._count("cost_enriched")
                return enriched
        except Exception as e:
            self.logger.debug(
                f"Cost enrichment failed for {resource.get('id', 'unknown')}: {e}"
            )

        return resource

    def _generate_cost_analysis(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate comprehensive cost analysis summary."""
        if not self.cost_analyzer:
            return {}

        try:
            self.logger.info("Generating cost analysis summary")

            # Get cost estimates for all resources
            cost_estimates = self.cost_analyzer.estimate_resource_costs(resources)

            # Identify expensive resources
            expensive_resources = self.cost_analyzer.identify_expensive_resources(
                cost_estimates
            )

            # Detect forgotten resources
            forgotten_resources = self.cost_analyzer.detect_forgotten_resources(
                resources
            )

            # Analyze cost trends
            cost_trends = self.cost_analyzer.analyze_cost_trends(resources)

            # Generate optimization recommendations
            recommendations = (
                self.cost_analyzer.generate_cost_optimization_recommendations(
                    cost_estimates, forgotten_resources
                )
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
                        "cost_breakdown": {
                            k: float(v) for k, v in est.cost_breakdown.items()
                        },
                        "pricing_model": est.pricing_model,
                        "confidence_level": est.confidence_level,
                    }
                    for est in cost_estimates
                ],
                "expensive_resources": [
                    {
                        "resource_id": res.resource_id,
                        "service": res.service,
                        "estimated_monthly_cost": float(res.estimated_monthly_cost),
                        "confidence_level": res.confidence_level,
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
                        "recommendations": res.recommendations,
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
                        "alert_triggered": trend.alert_triggered,
                    }
                    for trend in cost_trends
                ],
                "optimization_recommendations": [
                    {
                        "resource_id": rec.resource_id,
                        "service": rec.service,
                        "recommendation_type": rec.recommendation_type,
                        "current_monthly_cost": float(rec.current_monthly_cost),
                        "potential_monthly_savings": float(
                            rec.potential_monthly_savings
                        ),
                        "confidence_level": rec.confidence_level,
                        "implementation_effort": rec.implementation_effort,
                        "description": rec.description,
                        "action_items": rec.action_items,
                    }
                    for rec in recommendations
                ],
                "summary": {
                    "total_estimated_monthly_cost": float(
                        cost_summary.total_estimated_monthly_cost
                    ),
                    "expensive_resources_count": cost_summary.expensive_resources_count,
                    "forgotten_resources_count": cost_summary.forgotten_resources_count,
                    "total_potential_savings": float(
                        cost_summary.total_potential_savings
                    ),
                    "high_risk_resources": cost_summary.high_risk_resources,
                    "cost_by_service": {
                        k: float(v) for k, v in cost_summary.cost_by_service.items()
                    },
                    "cost_by_region": {
                        k: float(v) for k, v in cost_summary.cost_by_region.items()
                    },
                    "optimization_opportunities": cost_summary.optimization_opportunities,
                    "analysis_timestamp": cost_summary.analysis_timestamp.isoformat(),
                },
            }

        except Exception as e:
            self.logger.error(f"Cost analysis generation failed: {e}")
            self.statistics.errors.append(f"Cost analysis failed: {e}")
            return {}
