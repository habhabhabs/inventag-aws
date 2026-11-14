#!/usr/bin/env python3
"""
InvenTag - Network Analyzer
Comprehensive VPC and subnet analysis for network visibility and capacity planning.

Extracted and enhanced from bom_converter.py VPC enrichment functionality.
"""

import ipaddress
import boto3
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

# NAT gateway and peering states that mean the resource is gone or never worked.
_DEAD_NAT_STATES = {"deleted", "deleting", "failed"}
_DEAD_PEERING_STATES = {"deleted", "deleting", "rejected", "failed", "expired"}
_DEAD_TGW_STATES = {"deleted", "deleting", "failed", "rejected", "rejecting"}


def _collect(client, operation: str, key: str, **kwargs) -> List[Dict[str, Any]]:
    """All items of a List/Describe call, following ``NextToken`` to the end."""
    items: List[Dict[str, Any]] = []
    token = None
    while True:
        params = dict(kwargs)
        if token:
            params["NextToken"] = token
        response = getattr(client, operation)(**params)
        items.extend(response[key])
        token = response.get("NextToken")
        if not isinstance(token, str) or not token:
            return items


@dataclass
class SubnetAnalysis:
    """Analysis data for a single subnet."""

    subnet_id: str
    subnet_name: str
    cidr_block: str
    availability_zone: str
    vpc_id: str
    total_ips: int
    available_ips: int
    utilization_percentage: float
    associated_resources: List[str] = field(default_factory=list)
    route_table_id: Optional[str] = None
    is_public: bool = False
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class VPCAnalysis:
    """Analysis data for a single VPC."""

    vpc_id: str
    vpc_name: str
    cidr_block: str
    cidr_blocks: List[str] = field(default_factory=list)  # Multiple CIDR blocks
    total_ips: int = 0
    available_ips: int = 0
    utilization_percentage: float = 0.0
    subnets: List[SubnetAnalysis] = field(default_factory=list)
    associated_resources: List[str] = field(default_factory=list)
    internet_gateway_id: Optional[str] = None
    nat_gateways: List[str] = field(default_factory=list)
    vpc_endpoints: List[str] = field(default_factory=list)
    peering_connections: List[str] = field(default_factory=list)
    transit_gateway_attachments: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    # Elastic network interfaces in the VPC; None when they could not be read.
    region: str = ""
    network_interface_count: Optional[int] = None
    # Route tables as returned by DescribeRouteTables; None when not read.
    route_tables: Optional[List[Dict[str, Any]]] = None


@dataclass
class NetworkSummary:
    """Overall network analysis summary."""

    total_vpcs: int
    total_subnets: int
    total_available_ips: int
    highest_utilization_subnet: Optional[str]
    highest_utilization_percentage: float
    vpc_utilization_stats: Dict[str, float] = field(default_factory=dict)
    capacity_warnings: List[str] = field(default_factory=list)
    optimization_recommendations: List[str] = field(default_factory=list)


class NetworkAnalyzer:
    """
    Analyzes VPC, subnet, and CIDR information to provide network visibility
    and capacity planning data.

    Enhanced from the VPC enrichment functionality in bom_converter.py with:
    - Comprehensive CIDR block analysis and IP utilization calculations
    - Subnet utilization tracking with available IP counting
    - Resource-to-VPC/subnet mapping with intelligent name resolution
    - Network capacity planning and utilization reporting
    - VPC peering and transit gateway relationship mapping
    """

    def __init__(self, session: Optional[boto3.Session] = None):
        """Initialize the NetworkAnalyzer."""
        self.session = session or boto3.Session()
        self.vpc_cache: Dict[str, VPCAnalysis] = {}
        self.subnet_cache: Dict[str, SubnetAnalysis] = {}
        self.region_clients: Dict[str, Any] = {}

        # Thresholds for warnings and recommendations
        self.high_utilization_threshold = 80.0  # Percentage
        self.capacity_warning_threshold = 90.0  # Percentage

    def analyze_vpc_resources(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, VPCAnalysis]:
        """
        Analyze VPC resources and calculate CIDR utilization.

        Args:
            resources: List of resource dictionaries from inventory

        Returns:
            Dictionary mapping VPC IDs to VPCAnalysis objects
        """
        logger.info("Starting VPC resource analysis...")

        # Get unique regions from resources
        regions = self._extract_regions(resources)

        # Cache VPC and subnet information for each region
        for region in regions:
            self._cache_network_info(region)

        # Map resources to their network context
        self._map_resources_to_network(resources)

        # Calculate utilization metrics
        self._calculate_utilization_metrics()

        logger.info(
            f"Analyzed {len(self.vpc_cache)} VPCs across {len(regions)} regions"
        )
        return self.vpc_cache

    def calculate_subnet_utilization(
        self, subnet_resources: List[Dict[str, Any]]
    ) -> Dict[str, SubnetAnalysis]:
        """
        Calculate IP utilization per subnet.

        Args:
            subnet_resources: List of subnet resource dictionaries

        Returns:
            Dictionary mapping subnet IDs to SubnetAnalysis objects
        """
        logger.info("Calculating subnet utilization...")

        for subnet_resource in subnet_resources:
            subnet_id = subnet_resource.get("id") or subnet_resource.get("subnet_id")
            if subnet_id and subnet_id in self.subnet_cache:
                subnet_analysis = self.subnet_cache[subnet_id]

                # Update with additional resource information
                if "tags" in subnet_resource:
                    subnet_analysis.tags.update(subnet_resource["tags"])

        return self.subnet_cache

    def map_resources_to_network(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Map EC2/RDS resources to their VPC/subnet context.

        Args:
            resources: List of resource dictionaries to enrich

        Returns:
            List of enriched resource dictionaries with network context
        """
        logger.info("Mapping resources to network context...")

        enriched_resources = []
        enriched_count = 0

        for resource in resources:
            enriched_resource = resource.copy()

            # Extract network identifiers
            vpc_id = self._extract_vpc_id(resource)
            subnet_id = self._extract_subnet_id(resource)

            # Enrich with VPC information
            if vpc_id and vpc_id in self.vpc_cache:
                vpc_analysis = self.vpc_cache[vpc_id]
                enriched_resource.update(
                    {
                        "vpc_id": vpc_id,
                        "vpc_name": vpc_analysis.vpc_name,
                        "vpc_cidr_block": vpc_analysis.cidr_block,
                        "vpc_total_ips": vpc_analysis.total_ips,
                        "vpc_utilization_percentage": vpc_analysis.utilization_percentage,
                    }
                )
                enriched_count += 1

            # Enrich with subnet information
            if subnet_id and subnet_id in self.subnet_cache:
                subnet_analysis = self.subnet_cache[subnet_id]
                enriched_resource.update(
                    {
                        "subnet_id": subnet_id,
                        "subnet_name": subnet_analysis.subnet_name,
                        "subnet_cidr_block": subnet_analysis.cidr_block,
                        "subnet_availability_zone": subnet_analysis.availability_zone,
                        "subnet_total_ips": subnet_analysis.total_ips,
                        "subnet_utilization_percentage": subnet_analysis.utilization_percentage,
                        "subnet_is_public": subnet_analysis.is_public,
                    }
                )
                enriched_count += 1

            enriched_resources.append(enriched_resource)

        logger.info(f"Enriched {enriched_count} resources with network context")
        return enriched_resources

    def generate_network_summary(
        self, vpc_analysis: Dict[str, VPCAnalysis]
    ) -> NetworkSummary:
        """
        Generate network capacity summary for BOM.

        Args:
            vpc_analysis: Dictionary of VPC analysis results

        Returns:
            NetworkSummary object with overall statistics
        """
        logger.info("Generating network summary...")

        total_vpcs = len(vpc_analysis)
        total_subnets = sum(len(vpc.subnets) for vpc in vpc_analysis.values())
        total_available_ips = sum(vpc.available_ips for vpc in vpc_analysis.values())

        # Find highest utilization subnet
        highest_utilization_subnet = None
        highest_utilization_percentage = 0.0

        for vpc in vpc_analysis.values():
            for subnet in vpc.subnets:
                if subnet.utilization_percentage > highest_utilization_percentage:
                    highest_utilization_percentage = subnet.utilization_percentage
                    highest_utilization_subnet = (
                        f"{subnet.subnet_name} ({subnet.subnet_id})"
                    )

        # Calculate VPC utilization stats
        vpc_utilization_stats = {
            vpc_id: vpc.utilization_percentage for vpc_id, vpc in vpc_analysis.items()
        }

        # Generate capacity warnings and recommendations
        capacity_warnings = self._generate_capacity_warnings(vpc_analysis)
        optimization_recommendations = self._generate_optimization_recommendations(
            vpc_analysis
        )

        return NetworkSummary(
            total_vpcs=total_vpcs,
            total_subnets=total_subnets,
            total_available_ips=total_available_ips,
            highest_utilization_subnet=highest_utilization_subnet,
            highest_utilization_percentage=highest_utilization_percentage,
            vpc_utilization_stats=vpc_utilization_stats,
            capacity_warnings=capacity_warnings,
            optimization_recommendations=optimization_recommendations,
        )

    def _extract_regions(self, resources: List[Dict[str, Any]]) -> Set[str]:
        """Extract unique regions from resources."""
        regions = set()
        for resource in resources:
            region = resource.get("region", "")
            if region and region != "global":
                regions.add(region)
        return regions

    def _cache_network_info(self, region: str):
        """Cache VPC and subnet information for a region."""
        try:
            logger.info(f"Caching network information for region: {region}")
            ec2 = self.session.client("ec2", region_name=region)
            self.region_clients[region] = ec2

            # Cache VPC information
            self._cache_vpc_info(ec2, region)

            # Cache subnet information
            self._cache_subnet_info(ec2, region)

            # Cache additional network components
            self._cache_network_components(ec2, region)

        except ClientError as e:
            logger.warning(f"Could not cache network info for {region}: {e}")

    def _cache_vpc_info(self, ec2_client, region: str):
        """Cache VPC information."""
        try:
            for vpc in _collect(ec2_client, "describe_vpcs", "Vpcs"):
                vpc_id = vpc["VpcId"]
                vpc_name = self._get_tag_value(vpc.get("Tags", []), "Name") or vpc_id

                # Handle multiple CIDR blocks
                cidr_blocks = [vpc["CidrBlock"]] if vpc.get("CidrBlock") else []
                if "CidrBlockAssociationSet" in vpc:
                    for cidr_assoc in vpc["CidrBlockAssociationSet"]:
                        if cidr_assoc["CidrBlockState"]["State"] == "associated":
                            cidr_block = cidr_assoc["CidrBlock"]
                            if cidr_block not in cidr_blocks:
                                cidr_blocks.append(cidr_block)

                # Calculate total IPs across all CIDR blocks
                total_ips = sum(self._calculate_cidr_ips(cidr) for cidr in cidr_blocks)

                # Extract tags
                tags = {tag["Key"]: tag["Value"] for tag in vpc.get("Tags", [])}

                vpc_analysis = VPCAnalysis(
                    vpc_id=vpc_id,
                    vpc_name=vpc_name,
                    cidr_block=vpc.get("CidrBlock", ""),  # Primary CIDR
                    cidr_blocks=cidr_blocks,
                    total_ips=total_ips,
                    tags=tags,
                    region=region,
                )

                self.vpc_cache[vpc_id] = vpc_analysis

        except Exception as e:
            logger.warning(f"Could not cache VPC info for {region}: {e}")

    def _cache_subnet_info(self, ec2_client, region: str):
        """Cache subnet information."""
        try:
            for subnet in _collect(ec2_client, "describe_subnets", "Subnets"):
                subnet_id = subnet["SubnetId"]
                subnet_name = (
                    self._get_tag_value(subnet.get("Tags", []), "Name") or subnet_id
                )
                vpc_id = subnet["VpcId"]

                # Calculate IP utilization. An IPv6-only subnet has no IPv4 CIDR
                # and no IPv4 addresses to count.
                cidr_block = subnet.get("CidrBlock", "")
                total_ips = self._calculate_cidr_ips(cidr_block) if cidr_block else 0
                available_ips = subnet.get("AvailableIpAddressCount", 0)
                utilization_percentage = (
                    ((total_ips - available_ips) / total_ips * 100)
                    if total_ips > 0
                    else 0
                )

                # Extract tags
                tags = {tag["Key"]: tag["Value"] for tag in subnet.get("Tags", [])}

                subnet_analysis = SubnetAnalysis(
                    subnet_id=subnet_id,
                    subnet_name=subnet_name,
                    cidr_block=cidr_block,
                    availability_zone=subnet["AvailabilityZone"],
                    vpc_id=vpc_id,
                    total_ips=total_ips,
                    available_ips=available_ips,
                    utilization_percentage=utilization_percentage,
                    tags=tags,
                )

                self.subnet_cache[subnet_id] = subnet_analysis

                # Add subnet to VPC analysis
                if vpc_id in self.vpc_cache:
                    self.vpc_cache[vpc_id].subnets.append(subnet_analysis)

        except Exception as e:
            logger.warning(f"Could not cache subnet info for {region}: {e}")

    def _cache_network_components(self, ec2_client, region: str):
        """Cache additional network components like IGW, NAT, VPC endpoints."""
        try:
            # Internet Gateways
            for igw in _collect(
                ec2_client, "describe_internet_gateways", "InternetGateways"
            ):
                for attachment in igw.get("Attachments", []):
                    vpc_id = attachment.get("VpcId")
                    if vpc_id and vpc_id in self.vpc_cache:
                        self.vpc_cache[vpc_id].internet_gateway_id = igw[
                            "InternetGatewayId"
                        ]

            # NAT Gateways (deleted ones stay listed for about an hour)
            for nat in _collect(ec2_client, "describe_nat_gateways", "NatGateways"):
                if nat.get("State") in _DEAD_NAT_STATES:
                    continue
                vpc_id = nat.get("VpcId")
                if vpc_id and vpc_id in self.vpc_cache:
                    self.vpc_cache[vpc_id].nat_gateways.append(nat["NatGatewayId"])

            # VPC Endpoints
            for endpoint in _collect(
                ec2_client, "describe_vpc_endpoints", "VpcEndpoints"
            ):
                vpc_id = endpoint.get("VpcId")
                if vpc_id and vpc_id in self.vpc_cache:
                    self.vpc_cache[vpc_id].vpc_endpoints.append(
                        endpoint["VpcEndpointId"]
                    )

            # VPC Peering Connections. A cross-region connection is listed in
            # both regions, so add each one to a VPC only once.
            for peering in _collect(
                ec2_client, "describe_vpc_peering_connections", "VpcPeeringConnections"
            ):
                state = peering.get("Status", {}).get("Code")
                if state in _DEAD_PEERING_STATES:
                    continue
                pcx_id = peering["VpcPeeringConnectionId"]
                for side in ("AccepterVpcInfo", "RequesterVpcInfo"):
                    vpc_id = peering.get(side, {}).get("VpcId")
                    if vpc_id and vpc_id in self.vpc_cache:
                        connections = self.vpc_cache[vpc_id].peering_connections
                        if pcx_id not in connections:
                            connections.append(pcx_id)

            # Transit Gateway Attachments
            try:
                for attachment in _collect(
                    ec2_client,
                    "describe_transit_gateway_attachments",
                    "TransitGatewayAttachments",
                ):
                    if attachment.get("State") in _DEAD_TGW_STATES:
                        continue
                    if attachment.get("ResourceType") == "vpc":
                        vpc_id = attachment.get("ResourceId")
                        if vpc_id and vpc_id in self.vpc_cache:
                            self.vpc_cache[vpc_id].transit_gateway_attachments.append(
                                attachment["TransitGatewayAttachmentId"]
                            )
            except ClientError:
                # Transit Gateway might not be available in all regions
                pass

        except Exception as e:
            logger.warning(f"Could not cache network components for {region}: {e}")

        self._cache_route_tables(ec2_client, region)
        self._cache_network_interface_counts(ec2_client, region)

    def _cache_route_tables(self, ec2_client, region: str):
        """Read the route tables of every cached VPC (needed to tell public subnets)."""
        try:
            tables = _collect(ec2_client, "describe_route_tables", "RouteTables")
        except Exception as e:
            logger.warning(
                f"Could not read route tables for {region}: {e}. "
                "Subnets are reported as not public."
            )
            return
        by_vpc: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for table in tables:
            by_vpc[table.get("VpcId", "")].append(table)
        for vpc_id, vpc in self.vpc_cache.items():
            if vpc.region == region:
                vpc.route_tables = by_vpc.get(vpc_id, [])

    def _cache_network_interface_counts(self, ec2_client, region: str):
        """Count the network interfaces in each cached VPC of a region."""
        try:
            interfaces = _collect(
                ec2_client, "describe_network_interfaces", "NetworkInterfaces"
            )
        except Exception as e:
            logger.warning(
                f"Could not read network interfaces for {region}: {e}. "
                "Empty VPCs are not reported."
            )
            return
        counts: Dict[str, int] = defaultdict(int)
        for interface in interfaces:
            counts[interface.get("VpcId", "")] += 1
        for vpc_id, vpc in self.vpc_cache.items():
            if vpc.region == region:
                vpc.network_interface_count = counts.get(vpc_id, 0)

    def _map_resources_to_network(self, resources: List[Dict[str, Any]]):
        """Map resources to their VPC and subnet context."""
        for resource in resources:
            vpc_id = self._extract_vpc_id(resource)
            resource_id = resource.get("id", "unknown")
            if resource_id in self.vpc_cache or resource_id in self.subnet_cache:
                continue  # a VPC or subnet is not a resource inside itself
            if self._is_plumbing(resource):
                continue

            # Add resource to VPC
            if vpc_id and vpc_id in self.vpc_cache:
                if resource_id not in self.vpc_cache[vpc_id].associated_resources:
                    self.vpc_cache[vpc_id].associated_resources.append(resource_id)

            # Add resource to every subnet it names
            for subnet_id in self._extract_subnet_ids(resource):
                if subnet_id in self.subnet_cache:
                    members = self.subnet_cache[subnet_id].associated_resources
                    if resource_id not in members:
                        members.append(resource_id)

    def _calculate_utilization_metrics(self):
        """Calculate utilization metrics for VPCs."""
        for vpc_analysis in self.vpc_cache.values():
            if vpc_analysis.subnets:
                # Calculate VPC utilization based on subnet utilization
                total_subnet_ips = sum(
                    subnet.total_ips for subnet in vpc_analysis.subnets
                )
                total_available_ips = sum(
                    subnet.available_ips for subnet in vpc_analysis.subnets
                )

                vpc_analysis.available_ips = total_available_ips
                if total_subnet_ips > 0:
                    vpc_analysis.utilization_percentage = (
                        (total_subnet_ips - total_available_ips)
                        / total_subnet_ips
                        * 100
                    )

                # Determine if subnets are public (have route to IGW)
                self._determine_subnet_publicity(vpc_analysis)

    @staticmethod
    def _has_internet_route(route_table: Dict[str, Any]) -> bool:
        """True if the table has an active default route to an internet gateway."""
        for route in route_table.get("Routes", []):
            default = (
                route.get("DestinationCidrBlock") == "0.0.0.0/0"
                or route.get("DestinationIpv6CidrBlock") == "::/0"
            )
            gateway = route.get("GatewayId") or ""
            if (
                default
                and gateway.startswith("igw-")
                and route.get("State", "active") == "active"
            ):
                return True
        return False

    def _determine_subnet_publicity(self, vpc_analysis: VPCAnalysis):
        """Mark subnets whose route table has a default route to an internet gateway.

        A subnet uses the route table it is associated with, or the VPC's main
        route table if it has no association of its own. A subnet is public
        only if that table routes 0.0.0.0/0 or ::/0 to an ``igw-`` gateway. A
        VPC that has an internet gateway but no such route does not make its
        subnets public. If the route tables could not be read, every subnet is
        left as not public.
        """
        tables = vpc_analysis.route_tables
        if not tables:
            return
        main_table = None
        explicit: Dict[str, Dict[str, Any]] = {}
        for table in tables:
            for assoc in table.get("Associations", []):
                if assoc.get("Main"):
                    main_table = table
                elif assoc.get("SubnetId"):
                    explicit[assoc["SubnetId"]] = table
        for subnet in vpc_analysis.subnets:
            table = explicit.get(subnet.subnet_id, main_table)
            if table is None:
                continue
            subnet.route_table_id = table.get("RouteTableId")
            subnet.is_public = self._has_internet_route(table)

    # Network plumbing of a VPC: not "resources in" it (every VPC has a
    # default security group, NACL and route table).
    _PLUMBING_TYPES = frozenset(
        {
            "securitygroup",
            "networkacl",
            "routetable",
            "internetgateway",
            "egressonlyinternetgateway",
            "dhcpoptions",
            "prefixlist",
            "managedprefixlist",
        }
    )

    @staticmethod
    def _raw_sources(resource: Dict[str, Any]) -> List[Dict[str, Any]]:
        """The resource itself, its raw API data and the nested VPC configs
        where AWS puts network IDs (EC2 VpcId/SubnetId, Lambda VpcConfig,
        RDS DBSubnetGroup, ...)."""
        sources = [resource]
        for key in ("raw_data", "service_attributes"):
            raw = resource.get(key)
            if isinstance(raw, dict):
                sources.append(raw)
                for nested in ("VpcConfig", "DBSubnetGroup", "vpcConfig", "Placement"):
                    if isinstance(raw.get(nested), dict):
                        sources.append(raw[nested])
                boto3_config = raw.get("boto3_config")
                if isinstance(boto3_config, dict):
                    sources.append(boto3_config)
                    if isinstance(boto3_config.get("VpcConfig"), dict):
                        sources.append(boto3_config["VpcConfig"])
        return sources

    def _is_plumbing(self, resource: Dict[str, Any]) -> bool:
        kind = str(resource.get("type") or resource.get("resource_type") or "")
        return kind.replace("_", "").replace(" ", "").lower() in self._PLUMBING_TYPES

    def _extract_vpc_id(self, resource: Dict[str, Any]) -> Optional[str]:
        """Extract VPC ID from resource (top level or its raw API data)."""
        for source in self._raw_sources(resource):
            for field in ("vpc_id", "VpcId", "vpc", "vpcId"):
                value = source.get(field)
                if isinstance(value, str) and value.startswith("vpc-"):
                    return value

        # Try to extract from ARN or other fields
        arn = resource.get("arn", "")
        if "vpc-" in arn:
            # Simple extraction - would need more sophisticated parsing
            parts = arn.split("/")
            for part in parts:
                if part.startswith("vpc-"):
                    return part

        return None

    def _extract_subnet_ids(self, resource: Dict[str, Any]) -> List[str]:
        """Every subnet ID the resource's data names, once each, in order.

        Reads the single-subnet fields (EC2), the lists of IDs (Lambda
        VpcConfig.SubnetIds, classic load balancer Subnets), the RDS subnet
        group (DBSubnetGroup.Subnets) and the load balancer zones
        (AvailabilityZones[].SubnetId).
        """
        found: List[str] = []

        def add(value: Any) -> None:
            if (
                isinstance(value, str)
                and value.startswith("subnet-")
                and value not in found
            ):
                found.append(value)

        for source in self._raw_sources(resource):
            for field in ("subnet_id", "SubnetId", "subnet", "subnetId"):
                add(source.get(field))
            for field in ("SubnetIds", "subnetIds", "Subnets", "AvailabilityZones"):
                values = source.get(field)
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, dict):
                            item = item.get("SubnetIdentifier") or item.get("SubnetId")
                        add(item)

        # Try to extract from ARN or other fields
        arn = resource.get("arn", "")
        if "subnet-" in arn:
            # Simple extraction - would need more sophisticated parsing
            for part in arn.split("/"):
                add(part)

        return found

    def _extract_subnet_id(self, resource: Dict[str, Any]) -> Optional[str]:
        """The first subnet ID of the resource (the per-resource row columns).

        A resource in several subnets has one set of subnet columns, for the
        first subnet it names. The analysis counts it in every subnet
        (``_extract_subnet_ids``).
        """
        for source in self._raw_sources(resource):
            for field in ("subnet_id", "SubnetId", "subnet", "subnetId"):
                value = source.get(field)
                if isinstance(value, str) and value.startswith("subnet-"):
                    return value
            for field in ("SubnetIds", "subnetIds", "Subnets"):
                values = source.get(field)
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, dict):
                            item = item.get("SubnetIdentifier") or item.get("SubnetId")
                        if isinstance(item, str) and item.startswith("subnet-"):
                            return item

        # Try to extract from ARN or other fields
        arn = resource.get("arn", "")
        if "subnet-" in arn:
            # Simple extraction - would need more sophisticated parsing
            parts = arn.split("/")
            for part in parts:
                if part.startswith("subnet-"):
                    return part

        return None

    def _calculate_cidr_ips(self, cidr_block: str) -> int:
        """Calculate total IP addresses in a CIDR block."""
        try:
            network = ipaddress.IPv4Network(cidr_block, strict=False)
            # Subtract AWS reserved IPs (first 4 and last 1 in each subnet)
            return max(0, network.num_addresses - 5)
        except ValueError:
            logger.warning(f"Invalid CIDR block: {cidr_block}")
            return 0

    def _get_tag_value(self, tags: List[Dict[str, str]], key: str) -> Optional[str]:
        """Get tag value by key."""
        for tag in tags:
            if tag.get("Key") == key:
                return tag.get("Value")
        return None

    def _generate_capacity_warnings(
        self, vpc_analysis: Dict[str, VPCAnalysis]
    ) -> List[str]:
        """Generate capacity warnings for high utilization."""
        warnings = []

        for vpc in vpc_analysis.values():
            # VPC-level warnings
            if vpc.utilization_percentage > self.capacity_warning_threshold:
                warnings.append(
                    f"VPC {vpc.vpc_name} ({vpc.vpc_id}) is {vpc.utilization_percentage:.1f}% utilized"
                )

            # Subnet-level warnings
            for subnet in vpc.subnets:
                if subnet.utilization_percentage > self.capacity_warning_threshold:
                    warnings.append(
                        f"Subnet {subnet.subnet_name} ({subnet.subnet_id}) is "
                        f"{subnet.utilization_percentage:.1f}% utilized"
                    )

        return warnings

    def _generate_optimization_recommendations(
        self, vpc_analysis: Dict[str, VPCAnalysis]
    ) -> List[str]:
        """Generate network optimization recommendations."""
        recommendations = []

        for vpc in vpc_analysis.values():
            # A VPC is unused when nothing in the inventory points at it and it
            # has no network interface. If the interfaces could not be read,
            # the VPC is not reported.
            if not vpc.associated_resources and vpc.network_interface_count == 0:
                recommendations.append(
                    f"VPC {vpc.vpc_name} ({vpc.vpc_id}) has no associated resources - consider removal"
                )

            # Check for underutilized subnets
            underutilized_subnets = [
                subnet
                for subnet in vpc.subnets
                if subnet.utilization_percentage < 10 and subnet.associated_resources
            ]

            if underutilized_subnets:
                recommendations.append(
                    f"VPC {vpc.vpc_name} has {len(underutilized_subnets)} underutilized subnets - "
                    "consider consolidation"
                )

            # Private subnets reach the internet only through a NAT gateway
            private_subnets = [subnet for subnet in vpc.subnets if not subnet.is_public]
            if private_subnets and not vpc.nat_gateways:
                recommendations.append(
                    f"VPC {vpc.vpc_name} has {len(private_subnets)} private subnet(s) and no NAT gateway - "
                    "resources there may benefit from NAT gateways for internet access"
                )

        return recommendations
