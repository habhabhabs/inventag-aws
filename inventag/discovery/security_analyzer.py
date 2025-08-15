#!/usr/bin/env python3
"""
InvenTag - Security Analyzer
Comprehensive security group and NACL analysis for security assessment.

Provides detailed analysis of network security configurations including:
- Security group rule extraction and analysis
- Overly permissive rule detection with risk assessment
- Security group relationship mapping and dependency analysis
- NACL analysis and unused rule identification
- Security group reference resolution and circular dependency detection
- Port and protocol analysis with common service identification
"""

import boto3
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


@dataclass
class SecurityRule:
    """Analysis data for a single security rule."""

    protocol: str
    port_range: str
    source_destination: str
    description: str
    rule_type: str  # 'inbound' or 'outbound'
    risk_assessment: str  # 'low', 'medium', 'high', 'critical'
    is_permissive: bool = False
    references_security_group: bool = False
    referenced_sg_id: Optional[str] = None
    common_service: Optional[str] = None


@dataclass
class SecurityGroupAnalysis:
    """Analysis data for a single security group."""

    group_id: str
    group_name: str
    description: str
    vpc_id: str
    inbound_rules: List[SecurityRule] = field(default_factory=list)
    outbound_rules: List[SecurityRule] = field(default_factory=list)
    associated_resources: List[str] = field(default_factory=list)
    risk_level: str = "low"  # 'low', 'medium', 'high', 'critical'
    is_unused: bool = False
    references_other_sgs: List[str] = field(default_factory=list)
    referenced_by_sgs: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class NACLRule:
    """Analysis data for a single NACL rule."""

    rule_number: int
    protocol: str
    rule_action: str  # 'allow' or 'deny'
    port_range: str
    cidr_block: str
    rule_type: str  # 'inbound' or 'outbound'
    is_redundant: bool = False
    common_service: Optional[str] = None


@dataclass
class NACLAnalysis:
    """Analysis data for a single Network ACL."""

    nacl_id: str
    nacl_name: str
    vpc_id: str
    is_default: bool
    inbound_rules: List[NACLRule] = field(default_factory=list)
    outbound_rules: List[NACLRule] = field(default_factory=list)
    associated_subnets: List[str] = field(default_factory=list)
    unused_rules: List[int] = field(default_factory=list)
    optimization_recommendations: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SecuritySummary:
    """Overall security analysis summary."""

    total_security_groups: int
    overly_permissive_rules: int
    unused_security_groups: int
    high_risk_resources: List[str] = field(default_factory=list)
    security_recommendations: List[str] = field(default_factory=list)
    total_nacls: int = 0
    nacl_optimization_opportunities: int = 0
    circular_dependencies: List[Tuple[str, str]] = field(default_factory=list)


class SecurityAnalyzer:
    """
    Analyzes security groups, NACLs, and access patterns to provide
    comprehensive security documentation and risk assessment.

    Features:
    - Comprehensive security group rule extraction and analysis
    - Overly permissive rule detection (0.0.0.0/0 access) with risk assessment
    - Security group relationship mapping and dependency analysis across resources
    - NACL analysis and unused rule identification with optimization recommendations
    - Security group reference resolution and circular dependency detection
    - Port and protocol analysis with common service identification
    """

    def __init__(self, session: Optional[boto3.Session] = None):
        """Initialize the SecurityAnalyzer."""
        self.session = session or boto3.Session()
        self.sg_cache: Dict[str, SecurityGroupAnalysis] = {}
        self.nacl_cache: Dict[str, NACLAnalysis] = {}
        self.region_clients: Dict[str, Any] = {}

        # Common service port mappings
        self.common_services = {
            22: "SSH",
            23: "Telnet",
            25: "SMTP",
            53: "DNS",
            80: "HTTP",
            110: "POP3",
            143: "IMAP",
            443: "HTTPS",
            993: "IMAPS",
            995: "POP3S",
            1433: "SQL Server",
            1521: "Oracle",
            3306: "MySQL",
            3389: "RDP",
            5432: "PostgreSQL",
            5984: "CouchDB",
            6379: "Redis",
            8080: "HTTP Alt",
            8443: "HTTPS Alt",
            9200: "Elasticsearch",
            27017: "MongoDB",
        }

        # Risk assessment thresholds
        self.permissive_sources = ["0.0.0.0/0", "::/0"]
        self.high_risk_ports = [
            22,
            23,
            3389,
            1433,
            3306,
            5432,
        ]  # SSH, Telnet, RDP, DB ports

    def analyze_security_groups(
        self, sg_resources: List[Dict[str, Any]]
    ) -> Dict[str, SecurityGroupAnalysis]:
        """
        Analyze security group rules and relationships.

        Args:
            sg_resources: List of security group resource dictionaries

        Returns:
            Dictionary mapping security group IDs to SecurityGroupAnalysis objects
        """
        logger.info("Starting security group analysis...")

        # Get unique regions from resources
        regions = self._extract_regions(sg_resources)

        # Cache security group information for each region
        for region in regions:
            self._cache_security_group_info(region)

        # Map resources to security groups
        self._map_resources_to_security_groups(sg_resources)

        # Analyze security group relationships and dependencies
        self._analyze_security_group_relationships()

        # Assess risk levels
        self._assess_security_group_risks()

        logger.info(
            f"Analyzed {len(self.sg_cache)} security groups across {len(regions)} regions"
        )
        return self.sg_cache

    def identify_overly_permissive_rules(
        self, sg_analysis: Dict[str, SecurityGroupAnalysis]
    ) -> List[Dict[str, Any]]:
        """
        Identify security risks like 0.0.0.0/0 access.

        Args:
            sg_analysis: Dictionary of security group analysis results

        Returns:
            List of security risk dictionaries
        """
        logger.info("Identifying overly permissive rules...")

        risks = []

        for sg_id, sg in sg_analysis.items():
            # Check inbound rules
            for rule in sg.inbound_rules:
                if rule.is_permissive:
                    risk = {
                        "security_group_id": sg_id,
                        "security_group_name": sg.group_name,
                        "rule_type": "inbound",
                        "protocol": rule.protocol,
                        "port_range": rule.port_range,
                        "source": rule.source_destination,
                        "risk_level": rule.risk_assessment,
                        "description": rule.description,
                        "common_service": rule.common_service,
                    }
                    risks.append(risk)

            # Check outbound rules
            for rule in sg.outbound_rules:
                if rule.is_permissive:
                    risk = {
                        "security_group_id": sg_id,
                        "security_group_name": sg.group_name,
                        "rule_type": "outbound",
                        "protocol": rule.protocol,
                        "port_range": rule.port_range,
                        "destination": rule.source_destination,
                        "risk_level": rule.risk_assessment,
                        "description": rule.description,
                        "common_service": rule.common_service,
                    }
                    risks.append(risk)

        logger.info(f"Identified {len(risks)} overly permissive rules")
        return risks

    def analyze_nacls(
        self, nacl_resources: List[Dict[str, Any]]
    ) -> Dict[str, NACLAnalysis]:
        """
        Analyze Network ACL configurations.

        Args:
            nacl_resources: List of NACL resource dictionaries

        Returns:
            Dictionary mapping NACL IDs to NACLAnalysis objects
        """
        logger.info("Starting NACL analysis...")

        # Get unique regions from resources
        regions = self._extract_regions(nacl_resources)

        # Cache NACL information for each region
        for region in regions:
            self._cache_nacl_info(region)

        # Analyze NACL rules for optimization opportunities
        self._analyze_nacl_optimization()

        logger.info(
            f"Analyzed {len(self.nacl_cache)} NACLs across {len(regions)} regions"
        )
        return self.nacl_cache

    def map_resources_to_security_groups(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Map resources to their security group associations.

        Args:
            resources: List of resource dictionaries to enrich

        Returns:
            List of enriched resource dictionaries with security group context
        """
        logger.info("Mapping resources to security groups...")

        enriched_resources = []
        enriched_count = 0

        for resource in resources:
            enriched_resource = resource.copy()

            # Extract security group IDs
            sg_ids = self._extract_security_group_ids(resource)

            if sg_ids:
                sg_info = []
                for sg_id in sg_ids:
                    if sg_id in self.sg_cache:
                        sg_analysis = self.sg_cache[sg_id]
                        sg_info.append(
                            {
                                "id": sg_id,
                                "name": sg_analysis.group_name,
                                "risk_level": sg_analysis.risk_level,
                                "is_unused": sg_analysis.is_unused,
                            }
                        )

                if sg_info:
                    enriched_resource["security_groups"] = sg_info
                    enriched_resource["security_group_count"] = len(sg_info)
                    enriched_resource["max_security_risk"] = max(
                        sg["risk_level"] for sg in sg_info
                    )
                    enriched_count += 1

            enriched_resources.append(enriched_resource)

        logger.info(f"Enriched {enriched_count} resources with security group context")
        return enriched_resources

    def generate_security_summary(self, analysis: Dict[str, Any]) -> SecuritySummary:
        """
        Generate security overview for BOM.

        Args:
            analysis: Dictionary containing security analysis results

        Returns:
            SecuritySummary object with overall statistics
        """
        logger.info("Generating security summary...")

        sg_analysis = analysis.get("security_groups", {})
        nacl_analysis = analysis.get("nacls", {})

        total_security_groups = len(sg_analysis)
        unused_security_groups = sum(1 for sg in sg_analysis.values() if sg.is_unused)

        # Count overly permissive rules
        overly_permissive_rules = 0
        high_risk_resources = []

        for sg in sg_analysis.values():
            for rule in sg.inbound_rules + sg.outbound_rules:
                if rule.is_permissive:
                    overly_permissive_rules += 1

            if sg.risk_level in ["high", "critical"]:
                high_risk_resources.extend(sg.associated_resources)

        # Generate security recommendations
        security_recommendations = self._generate_security_recommendations(
            sg_analysis, nacl_analysis
        )

        # Find circular dependencies
        circular_dependencies = self._find_circular_dependencies(sg_analysis)

        # Count NACL optimization opportunities
        nacl_optimization_opportunities = sum(
            len(nacl.optimization_recommendations) for nacl in nacl_analysis.values()
        )

        return SecuritySummary(
            total_security_groups=total_security_groups,
            overly_permissive_rules=overly_permissive_rules,
            unused_security_groups=unused_security_groups,
            high_risk_resources=list(set(high_risk_resources)),
            security_recommendations=security_recommendations,
            total_nacls=len(nacl_analysis),
            nacl_optimization_opportunities=nacl_optimization_opportunities,
            circular_dependencies=circular_dependencies,
        )

    def _extract_regions(self, resources: List[Dict[str, Any]]) -> Set[str]:
        """Extract unique regions from resources."""
        regions = set()
        for resource in resources:
            region = resource.get("region", "")
            if region and region != "global":
                regions.add(region)
        return regions

    def _cache_security_group_info(self, region: str):
        """Cache security group information for a region."""
        try:
            logger.info(f"Caching security group information for region: {region}")
            ec2 = self.session.client("ec2", region_name=region)
            self.region_clients[region] = ec2

            # Get security groups
            sg_response = ec2.describe_security_groups()

            for sg in sg_response["SecurityGroups"]:
                sg_id = sg["GroupId"]
                sg_name = sg["GroupName"]
                description = sg["Description"]
                vpc_id = sg.get("VpcId", "default")

                # Extract tags
                tags = {tag["Key"]: tag["Value"] for tag in sg.get("Tags", [])}

                # Analyze inbound rules
                inbound_rules = []
                for rule in sg.get("IpPermissions", []):
                    inbound_rules.extend(self._parse_security_rule(rule, "inbound"))

                # Analyze outbound rules
                outbound_rules = []
                for rule in sg.get("IpPermissionsEgress", []):
                    outbound_rules.extend(self._parse_security_rule(rule, "outbound"))

                sg_analysis = SecurityGroupAnalysis(
                    group_id=sg_id,
                    group_name=sg_name,
                    description=description,
                    vpc_id=vpc_id,
                    inbound_rules=inbound_rules,
                    outbound_rules=outbound_rules,
                    tags=tags,
                )

                self.sg_cache[sg_id] = sg_analysis

        except Exception as e:
            logger.warning(f"Could not cache security group info for {region}: {e}")

    def _parse_security_rule(
        self, rule: Dict[str, Any], rule_type: str
    ) -> List[SecurityRule]:
        """Parse a security group rule into SecurityRule objects."""
        parsed_rules = []

        protocol = rule.get("IpProtocol", "")
        if protocol == "-1":
            protocol = "All"

        # Determine port range
        from_port = rule.get("FromPort")
        to_port = rule.get("ToPort")

        if from_port is None or to_port is None:
            port_range = "All"
        elif from_port == to_port:
            port_range = str(from_port)
        else:
            port_range = f"{from_port}-{to_port}"

        # Process IP ranges
        for ip_range in rule.get("IpRanges", []):
            cidr = ip_range.get("CidrIp", "")
            description = ip_range.get("Description", "")

            security_rule = SecurityRule(
                protocol=protocol,
                port_range=port_range,
                source_destination=cidr,
                description=description,
                rule_type=rule_type,
                risk_assessment=self._assess_rule_risk(cidr, from_port, protocol),
                is_permissive=cidr in self.permissive_sources,
                common_service=self._identify_common_service(from_port),
            )

            parsed_rules.append(security_rule)

        # Process IPv6 ranges
        for ipv6_range in rule.get("Ipv6Ranges", []):
            cidr = ipv6_range.get("CidrIpv6", "")
            description = ipv6_range.get("Description", "")

            security_rule = SecurityRule(
                protocol=protocol,
                port_range=port_range,
                source_destination=cidr,
                description=description,
                rule_type=rule_type,
                risk_assessment=self._assess_rule_risk(cidr, from_port, protocol),
                is_permissive=cidr in self.permissive_sources,
                common_service=self._identify_common_service(from_port),
            )

            parsed_rules.append(security_rule)

        # Process security group references
        for sg_ref in rule.get("UserIdGroupPairs", []):
            referenced_sg_id = sg_ref.get("GroupId", "")
            description = sg_ref.get("Description", "")

            security_rule = SecurityRule(
                protocol=protocol,
                port_range=port_range,
                source_destination=f"sg-{referenced_sg_id}",
                description=description,
                rule_type=rule_type,
                risk_assessment="low",  # SG references are generally lower risk
                references_security_group=True,
                referenced_sg_id=referenced_sg_id,
                common_service=self._identify_common_service(from_port),
            )

            parsed_rules.append(security_rule)

        return parsed_rules

    def _assess_rule_risk(self, cidr: str, port: Optional[int], protocol: str) -> str:
        """Assess the risk level of a security rule."""
        # Critical risk: permissive source with high-risk ports
        if cidr in self.permissive_sources:
            if port in self.high_risk_ports:
                return "critical"
            elif port and port < 1024:  # Well-known ports
                return "high"
            else:
                return "medium"

        # Medium risk: broad CIDR ranges
        if "/" in cidr:
            try:
                prefix_length = int(cidr.split("/")[-1])
                if prefix_length < 16:  # Very broad ranges
                    return "medium"
            except ValueError:
                pass

        return "low"

    def _identify_common_service(self, port: Optional[int]) -> Optional[str]:
        """Identify common service by port number."""
        if port in self.common_services:
            return self.common_services[port]
        return None

    def _cache_nacl_info(self, region: str):
        """Cache NACL information for a region."""
        try:
            logger.info(f"Caching NACL information for region: {region}")
            ec2 = self.session.client("ec2", region_name=region)

            # Get NACLs
            nacl_response = ec2.describe_network_acls()

            for nacl in nacl_response["NetworkAcls"]:
                nacl_id = nacl["NetworkAclId"]
                is_default = nacl["IsDefault"]
                vpc_id = nacl["VpcId"]

                # Get NACL name from tags
                tags = {tag["Key"]: tag["Value"] for tag in nacl.get("Tags", [])}
                nacl_name = tags.get("Name", nacl_id)

                # Get associated subnets
                associated_subnets = [
                    assoc["SubnetId"] for assoc in nacl.get("Associations", [])
                ]

                # Parse rules
                inbound_rules = []
                outbound_rules = []

                for entry in nacl.get("Entries", []):
                    rule = self._parse_nacl_rule(entry)
                    if entry.get("Egress", False):
                        outbound_rules.append(rule)
                    else:
                        inbound_rules.append(rule)

                nacl_analysis = NACLAnalysis(
                    nacl_id=nacl_id,
                    nacl_name=nacl_name,
                    vpc_id=vpc_id,
                    is_default=is_default,
                    inbound_rules=inbound_rules,
                    outbound_rules=outbound_rules,
                    associated_subnets=associated_subnets,
                    tags=tags,
                )

                self.nacl_cache[nacl_id] = nacl_analysis

        except Exception as e:
            logger.warning(f"Could not cache NACL info for {region}: {e}")

    def _parse_nacl_rule(self, entry: Dict[str, Any]) -> NACLRule:
        """Parse a NACL rule entry."""
        rule_number = entry.get("RuleNumber", 0)
        protocol = entry.get("Protocol", "")
        rule_action = entry.get("RuleAction", "")
        cidr_block = entry.get("CidrBlock", "")

        # Handle protocol numbers
        if protocol == "-1":
            protocol = "All"
        elif protocol == "6":
            protocol = "TCP"
        elif protocol == "17":
            protocol = "UDP"
        elif protocol == "1":
            protocol = "ICMP"

        # Determine port range
        port_range = "All"
        if "PortRange" in entry:
            from_port = entry["PortRange"].get("From")
            to_port = entry["PortRange"].get("To")
            if from_port == to_port:
                port_range = str(from_port)
            else:
                port_range = f"{from_port}-{to_port}"

        rule_type = "outbound" if entry.get("Egress", False) else "inbound"

        return NACLRule(
            rule_number=rule_number,
            protocol=protocol,
            rule_action=rule_action,
            port_range=port_range,
            cidr_block=cidr_block,
            rule_type=rule_type,
            common_service=self._identify_common_service(
                entry.get("PortRange", {}).get("From") if "PortRange" in entry else None
            ),
        )

    def _map_resources_to_security_groups(self, resources: List[Dict[str, Any]]):
        """Map resources to their security group associations."""
        for resource in resources:
            sg_ids = self._extract_security_group_ids(resource)
            resource_id = resource.get("id", "unknown")

            for sg_id in sg_ids:
                if sg_id in self.sg_cache:
                    if resource_id not in self.sg_cache[sg_id].associated_resources:
                        self.sg_cache[sg_id].associated_resources.append(resource_id)

    def _extract_security_group_ids(self, resource: Dict[str, Any]) -> List[str]:
        """Extract security group IDs from a resource."""
        sg_ids = []

        # Try multiple possible fields
        sg_fields = ["security_groups", "SecurityGroups", "security_group_ids"]
        for field in sg_fields:
            if field in resource:
                value = resource[field]
                if isinstance(value, list):
                    for sg in value:
                        if isinstance(sg, dict):
                            sg_id = sg.get("GroupId") or sg.get("group_id")
                            if sg_id:
                                sg_ids.append(sg_id)
                        elif isinstance(sg, str):
                            sg_ids.append(sg)
                elif isinstance(value, str):
                    sg_ids.append(value)

        return sg_ids

    def _analyze_security_group_relationships(self):
        """Analyze security group relationships and dependencies."""
        for sg_id, sg in self.sg_cache.items():
            # Find security groups that this SG references
            for rule in sg.inbound_rules + sg.outbound_rules:
                if rule.references_security_group and rule.referenced_sg_id:
                    if rule.referenced_sg_id not in sg.references_other_sgs:
                        sg.references_other_sgs.append(rule.referenced_sg_id)

                    # Add reverse reference
                    if rule.referenced_sg_id in self.sg_cache:
                        referenced_sg = self.sg_cache[rule.referenced_sg_id]
                        if sg_id not in referenced_sg.referenced_by_sgs:
                            referenced_sg.referenced_by_sgs.append(sg_id)

    def _assess_security_group_risks(self):
        """Assess risk levels for security groups."""
        for sg in self.sg_cache.values():
            risk_levels = []

            # Check all rules for risk levels
            for rule in sg.inbound_rules + sg.outbound_rules:
                risk_levels.append(rule.risk_assessment)

            # Determine overall risk level
            if "critical" in risk_levels:
                sg.risk_level = "critical"
            elif "high" in risk_levels:
                sg.risk_level = "high"
            elif "medium" in risk_levels:
                sg.risk_level = "medium"
            else:
                sg.risk_level = "low"

            # Check if unused
            sg.is_unused = len(sg.associated_resources) == 0

    def _analyze_nacl_optimization(self):
        """Analyze NACLs for optimization opportunities."""
        for nacl in self.nacl_cache.values():
            recommendations = []

            # Check for redundant rules
            all_rules = nacl.inbound_rules + nacl.outbound_rules
            rule_numbers = [rule.rule_number for rule in all_rules]

            # Check for gaps in rule numbers (potential cleanup opportunity)
            if rule_numbers:
                max_rule = max(rule_numbers)
                if max_rule > len(rule_numbers) * 10:  # Arbitrary threshold
                    recommendations.append(
                        "Consider renumbering rules to eliminate gaps"
                    )

            # Check for overly broad rules
            for rule in all_rules:
                if (
                    rule.cidr_block in ["0.0.0.0/0", "::/0"]
                    and rule.rule_action == "allow"
                ):
                    recommendations.append(
                        f"Rule {rule.rule_number} allows all traffic - consider restricting"
                    )

            nacl.optimization_recommendations = recommendations

    def _generate_security_recommendations(
        self,
        sg_analysis: Dict[str, SecurityGroupAnalysis],
        nacl_analysis: Dict[str, NACLAnalysis],
    ) -> List[str]:
        """Generate security optimization recommendations."""
        recommendations = []

        # Security group recommendations
        unused_sgs = [sg.group_name for sg in sg_analysis.values() if sg.is_unused]
        if unused_sgs:
            recommendations.append(
                f"Remove {len(unused_sgs)} unused security groups: {', '.join(unused_sgs[:5])}"
            )

        # High-risk rule recommendations
        high_risk_sgs = [
            sg.group_name
            for sg in sg_analysis.values()
            if sg.risk_level in ["high", "critical"]
        ]
        if high_risk_sgs:
            recommendations.append(
                f"Review {len(high_risk_sgs)} high-risk security groups for overly permissive rules"
            )

        # NACL recommendations
        nacl_recommendations = sum(
            len(nacl.optimization_recommendations) for nacl in nacl_analysis.values()
        )
        if nacl_recommendations > 0:
            recommendations.append(
                f"Optimize {nacl_recommendations} NACL rules for better performance"
            )

        return recommendations

    def _find_circular_dependencies(
        self, sg_analysis: Dict[str, SecurityGroupAnalysis]
    ) -> List[Tuple[str, str]]:
        """Find circular dependencies between security groups."""
        circular_deps = []

        for sg_id, sg in sg_analysis.items():
            for referenced_sg_id in sg.references_other_sgs:
                if referenced_sg_id in sg_analysis:
                    referenced_sg = sg_analysis[referenced_sg_id]
                    if sg_id in referenced_sg.references_other_sgs:
                        # Found circular dependency
                        dep_pair = tuple(sorted([sg_id, referenced_sg_id]))
                        if dep_pair not in circular_deps:
                            circular_deps.append(dep_pair)

        return circular_deps
