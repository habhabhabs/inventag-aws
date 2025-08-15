"""
DeltaDetector - Comprehensive change tracking

Provides delta detection algorithms for new, removed, and modified resources
with ARN-based matching, attribute diffing, compliance change detection,
and change impact analysis.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes that can be detected"""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class ChangeSeverity(Enum):
    """Severity levels for changes"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ChangeCategory(Enum):
    """Categories of changes"""

    CONFIGURATION = "configuration"
    TAGS = "tags"
    SECURITY = "security"
    NETWORK = "network"
    COMPLIANCE = "compliance"
    METADATA = "metadata"


@dataclass
class AttributeChange:
    """Represents a change to a specific attribute"""

    attribute_path: str
    old_value: Any
    new_value: Any
    change_type: ChangeType
    category: ChangeCategory
    severity: ChangeSeverity
    description: str = ""


@dataclass
class ResourceChange:
    """Represents changes to a single resource"""

    resource_arn: str
    resource_id: str
    service: str
    resource_type: str
    region: str
    change_type: ChangeType
    attribute_changes: List[AttributeChange] = field(default_factory=list)
    compliance_changes: List[AttributeChange] = field(default_factory=list)
    security_impact: Optional[str] = None
    network_impact: Optional[str] = None
    related_resources: List[str] = field(default_factory=list)
    severity: ChangeSeverity = ChangeSeverity.INFO
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class DeltaReport:
    """Comprehensive delta report between two states"""

    state1_id: str
    state2_id: str
    timestamp: str
    summary: Dict[str, int]
    added_resources: List[ResourceChange]
    removed_resources: List[ResourceChange]
    modified_resources: List[ResourceChange]
    unchanged_resources: List[ResourceChange]
    compliance_changes: Dict[str, Any]
    security_changes: Dict[str, Any]
    network_changes: Dict[str, Any]
    impact_analysis: Dict[str, Any]
    change_statistics: Dict[str, Any]


class DeltaDetector:
    """
    Enhanced delta detector for comprehensive change tracking between
    AWS resource inventory states with detailed analysis and categorization.
    """

    def __init__(
        self,
        ignore_metadata_fields: Optional[List[str]] = None,
        severity_rules: Optional[Dict[str, ChangeSeverity]] = None,
    ):
        """
        Initialize DeltaDetector with configuration options.

        Args:
            ignore_metadata_fields: List of fields to ignore during comparison
            severity_rules: Custom rules for determining change severity
        """
        self.ignore_metadata_fields = ignore_metadata_fields or [
            "last_seen",
            "discovery_timestamp",
            "scan_time",
            "metadata",
        ]

        # Default severity rules based on attribute patterns
        self.severity_rules = severity_rules or {
            # Critical changes
            "security_groups": ChangeSeverity.CRITICAL,
            "iam_roles": ChangeSeverity.CRITICAL,
            "encryption": ChangeSeverity.CRITICAL,
            "public_access": ChangeSeverity.CRITICAL,
            "vpc_id": ChangeSeverity.CRITICAL,
            "subnet_id": ChangeSeverity.HIGH,
            # High severity changes
            "compliance_status": ChangeSeverity.HIGH,
            "policy": ChangeSeverity.HIGH,
            "permissions": ChangeSeverity.HIGH,
            "network_acls": ChangeSeverity.HIGH,
            # Medium severity changes
            "tags": ChangeSeverity.MEDIUM,
            "configuration": ChangeSeverity.MEDIUM,
            "state": ChangeSeverity.MEDIUM,
            # Low severity changes
            "description": ChangeSeverity.LOW,
            "name": ChangeSeverity.LOW,
            "labels": ChangeSeverity.LOW,
        }

        # Resource dependency patterns for impact analysis
        self.dependency_patterns = {
            "EC2": {
                "depends_on": ["VPC", "Subnet", "SecurityGroup", "KeyPair", "IAMRole"],
                "affects": ["ELB", "AutoScalingGroup", "EBS"],
            },
            "RDS": {
                "depends_on": ["VPC", "Subnet", "SecurityGroup", "DBSubnetGroup"],
                "affects": ["Lambda", "EC2"],
            },
            "Lambda": {
                "depends_on": ["IAMRole", "VPC", "Subnet", "SecurityGroup"],
                "affects": ["APIGateway", "EventBridge", "S3"],
            },
            "S3": {
                "depends_on": ["IAMRole", "KMSKey"],
                "affects": ["Lambda", "CloudFront", "EC2"],
            },
            "VPC": {
                "depends_on": [],
                "affects": ["EC2", "RDS", "Lambda", "ELB", "NAT"],
            },
            "SecurityGroup": {
                "depends_on": ["VPC"],
                "affects": ["EC2", "RDS", "Lambda", "ELB"],
            },
        }

    def detect_changes(
        self,
        old_resources: List[Dict],
        new_resources: List[Dict],
        state1_id: str,
        state2_id: str,
    ) -> DeltaReport:
        """
        Detect comprehensive changes between two resource states.

        Args:
            old_resources: Resources from the previous state
            new_resources: Resources from the current state
            state1_id: ID of the previous state
            state2_id: ID of the current state

        Returns:
            DeltaReport with comprehensive change analysis
        """
        logger.info(f"Detecting changes between states {state1_id} and {state2_id}")

        # Create resource lookup maps by ARN
        old_resources_map = self._create_resource_map(old_resources)
        new_resources_map = self._create_resource_map(new_resources)

        # Detect different types of changes
        added_resources = self._detect_added_resources(
            old_resources_map, new_resources_map
        )
        removed_resources = self._detect_removed_resources(
            old_resources_map, new_resources_map
        )
        modified_resources, unchanged_resources = self._detect_modified_resources(
            old_resources_map, new_resources_map
        )

        # Analyze compliance changes
        compliance_changes = self._analyze_compliance_changes(
            old_resources, new_resources, modified_resources
        )

        # Analyze security changes
        security_changes = self._analyze_security_changes(
            added_resources + removed_resources + modified_resources
        )

        # Analyze network changes
        network_changes = self._analyze_network_changes(
            added_resources + removed_resources + modified_resources
        )

        # Perform impact analysis
        impact_analysis = self._analyze_change_impact(
            added_resources + removed_resources + modified_resources,
            old_resources_map,
            new_resources_map,
        )

        # Calculate change statistics
        change_statistics = {
            "added_count": len(added_resources),
            "removed_count": len(removed_resources),
            "modified_count": len(modified_resources),
            "unchanged_count": len(unchanged_resources),
            "total_changes": len(added_resources)
            + len(removed_resources)
            + len(modified_resources),
        }

        return DeltaReport(
            state1_id=state1_id,
            state2_id=state2_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary=change_statistics,
            added_resources=added_resources,
            removed_resources=removed_resources,
            modified_resources=modified_resources,
            unchanged_resources=unchanged_resources,
            compliance_changes=compliance_changes,
            security_changes=security_changes,
            network_changes=network_changes,
            impact_analysis=impact_analysis,
            change_statistics=change_statistics,
        )

    def detect_changes_by_state_id(
        self, state_manager, previous_state_id: str, current_state_id: str
    ) -> DeltaReport:
        """
        Detect changes between two states using state IDs.

        Args:
            state_manager: StateManager instance to load states
            previous_state_id: ID of the previous state
            current_state_id: ID of the current state

        Returns:
            DeltaReport with comprehensive change analysis
        """
        # Load the states
        previous_state = state_manager.load_state(previous_state_id)
        current_state = state_manager.load_state(current_state_id)

        if not previous_state or not current_state:
            logger.warning(
                f"Could not load states {previous_state_id} or {current_state_id}"
            )
            # Return empty delta report
            return DeltaReport(
                state1_id=previous_state_id,
                state2_id=current_state_id,
                comparison_timestamp=datetime.now(timezone.utc).isoformat(),
                changes_detected=False,
                change_summary={
                    "total_changes": 0,
                    "added": 0,
                    "removed": 0,
                    "modified": 0,
                    "unchanged": 0,
                },
                added_resources=[],
                removed_resources=[],
                modified_resources=[],
                unchanged_resources=[],
                change_impact={},
                recommendations=[],
            )

        # Extract resources and call the main detect_changes method
        old_resources = previous_state.resources
        new_resources = current_state.resources

        return self.detect_changes(
            old_resources=old_resources,
            new_resources=new_resources,
            state1_id=previous_state_id,
            state2_id=current_state_id,
        )

    def _create_resource_map(self, resources: List[Dict]) -> Dict[str, Dict]:
        """Create a map of resources keyed by ARN for efficient lookup"""
        resource_map = {}
        for resource in resources:
            # Use ARN as primary key, fallback to ID if ARN not available
            key = resource.get("arn") or resource.get("id", "")
            if key:
                resource_map[key] = resource
            else:
                # Generate a synthetic key for resources without ARN or ID
                synthetic_key = f"{resource.get('service', 'unknown')}:{resource.get('type', 'unknown')}:{resource.get('region', 'unknown')}:{hash(json.dumps(resource, sort_keys=True))}"
                resource_map[synthetic_key] = resource
        return resource_map

    def _detect_added_resources(
        self, old_resources_map: Dict[str, Dict], new_resources_map: Dict[str, Dict]
    ) -> List[ResourceChange]:
        """Detect resources that were added in the new state"""
        added_resources = []

        for arn, resource in new_resources_map.items():
            if arn not in old_resources_map:
                change = ResourceChange(
                    resource_arn=arn,
                    resource_id=resource.get("id", ""),
                    service=resource.get("service", ""),
                    resource_type=resource.get("type", ""),
                    region=resource.get("region", ""),
                    change_type=ChangeType.ADDED,
                    severity=self._determine_resource_severity(
                        resource, ChangeType.ADDED
                    ),
                )

                # Add security and network impact for new resources
                change.security_impact = self._assess_security_impact(
                    resource, ChangeType.ADDED
                )
                change.network_impact = self._assess_network_impact(
                    resource, ChangeType.ADDED
                )

                added_resources.append(change)

        logger.info(f"Detected {len(added_resources)} added resources")
        return added_resources

    def _detect_removed_resources(
        self, old_resources_map: Dict[str, Dict], new_resources_map: Dict[str, Dict]
    ) -> List[ResourceChange]:
        """Detect resources that were removed from the new state"""
        removed_resources = []

        for arn, resource in old_resources_map.items():
            if arn not in new_resources_map:
                change = ResourceChange(
                    resource_arn=arn,
                    resource_id=resource.get("id", ""),
                    service=resource.get("service", ""),
                    resource_type=resource.get("type", ""),
                    region=resource.get("region", ""),
                    change_type=ChangeType.REMOVED,
                    severity=self._determine_resource_severity(
                        resource, ChangeType.REMOVED
                    ),
                )

                # Add security and network impact for removed resources
                change.security_impact = self._assess_security_impact(
                    resource, ChangeType.REMOVED
                )
                change.network_impact = self._assess_network_impact(
                    resource, ChangeType.REMOVED
                )

                removed_resources.append(change)

        logger.info(f"Detected {len(removed_resources)} removed resources")
        return removed_resources

    def _detect_modified_resources(
        self, old_resources_map: Dict[str, Dict], new_resources_map: Dict[str, Dict]
    ) -> Tuple[List[ResourceChange], List[ResourceChange]]:
        """Detect resources that were modified between states"""
        modified_resources = []
        unchanged_resources = []

        for arn in old_resources_map:
            if arn in new_resources_map:
                old_resource = old_resources_map[arn]
                new_resource = new_resources_map[arn]

                # Compare resources and detect changes
                attribute_changes = self._compare_resources(old_resource, new_resource)

                if attribute_changes:
                    change = ResourceChange(
                        resource_arn=arn,
                        resource_id=new_resource.get("id", ""),
                        service=new_resource.get("service", ""),
                        resource_type=new_resource.get("type", ""),
                        region=new_resource.get("region", ""),
                        change_type=ChangeType.MODIFIED,
                        attribute_changes=attribute_changes,
                        severity=self._determine_change_severity(attribute_changes),
                    )

                    # Analyze compliance changes for this resource
                    compliance_changes = self._detect_compliance_changes(
                        old_resource, new_resource
                    )
                    change.compliance_changes = compliance_changes

                    # Add security and network impact
                    change.security_impact = self._assess_security_impact(
                        new_resource, ChangeType.MODIFIED, old_resource
                    )
                    change.network_impact = self._assess_network_impact(
                        new_resource, ChangeType.MODIFIED, old_resource
                    )

                    modified_resources.append(change)
                else:
                    # Resource unchanged
                    unchanged_change = ResourceChange(
                        resource_arn=arn,
                        resource_id=new_resource.get("id", ""),
                        service=new_resource.get("service", ""),
                        resource_type=new_resource.get("type", ""),
                        region=new_resource.get("region", ""),
                        change_type=ChangeType.UNCHANGED,
                        severity=ChangeSeverity.INFO,
                    )
                    unchanged_resources.append(unchanged_change)

        logger.info(
            f"Detected {len(modified_resources)} modified resources and {len(unchanged_resources)} unchanged resources"
        )
        return modified_resources, unchanged_resources

    def _compare_resources(
        self, old_resource: Dict, new_resource: Dict
    ) -> List[AttributeChange]:
        """Compare two resources and return list of attribute changes"""
        changes = []

        # Get all unique keys from both resources
        all_keys = set(old_resource.keys()) | set(new_resource.keys())

        for key in all_keys:
            # Skip ignored metadata fields
            if key in self.ignore_metadata_fields:
                continue

            old_value = old_resource.get(key)
            new_value = new_resource.get(key)

            # Detect changes at this level
            if old_value != new_value:
                change_type = self._determine_attribute_change_type(
                    old_value, new_value
                )
                category = self._categorize_attribute_change(key, old_value, new_value)
                severity = self._determine_attribute_severity(key, old_value, new_value)

                change = AttributeChange(
                    attribute_path=key,
                    old_value=old_value,
                    new_value=new_value,
                    change_type=change_type,
                    category=category,
                    severity=severity,
                    description=self._generate_change_description(
                        key, old_value, new_value
                    ),
                )
                changes.append(change)

                # For complex objects, do deep comparison
                if isinstance(old_value, dict) and isinstance(new_value, dict):
                    nested_changes = self._compare_nested_objects(
                        old_value, new_value, key
                    )
                    changes.extend(nested_changes)
                elif isinstance(old_value, list) and isinstance(new_value, list):
                    nested_changes = self._compare_lists(old_value, new_value, key)
                    changes.extend(nested_changes)

        return changes

    def _compare_nested_objects(
        self, old_obj: Dict, new_obj: Dict, parent_path: str
    ) -> List[AttributeChange]:
        """Compare nested dictionary objects"""
        changes = []
        all_keys = set(old_obj.keys()) | set(new_obj.keys())

        for key in all_keys:
            if key in self.ignore_metadata_fields:
                continue

            full_path = f"{parent_path}.{key}"
            old_value = old_obj.get(key)
            new_value = new_obj.get(key)

            if old_value != new_value:
                change_type = self._determine_attribute_change_type(
                    old_value, new_value
                )
                category = self._categorize_attribute_change(
                    full_path, old_value, new_value
                )
                severity = self._determine_attribute_severity(
                    full_path, old_value, new_value
                )

                change = AttributeChange(
                    attribute_path=full_path,
                    old_value=old_value,
                    new_value=new_value,
                    change_type=change_type,
                    category=category,
                    severity=severity,
                    description=self._generate_change_description(
                        key, old_value, new_value
                    ),
                )
                changes.append(change)

        return changes

    def _compare_lists(
        self, old_list: List, new_list: List, parent_path: str
    ) -> List[AttributeChange]:
        """Compare list attributes"""
        changes = []

        # Convert lists to sets for comparison if they contain simple types
        try:
            old_set = (
                set(old_list)
                if all(isinstance(x, (str, int, float, bool)) for x in old_list)
                else None
            )
            new_set = (
                set(new_list)
                if all(isinstance(x, (str, int, float, bool)) for x in new_list)
                else None
            )

            if old_set is not None and new_set is not None:
                # Handle as sets
                added_items = new_set - old_set
                removed_items = old_set - new_set

                if added_items:
                    change = AttributeChange(
                        attribute_path=f"{parent_path}[added]",
                        old_value=None,
                        new_value=list(added_items),
                        change_type=ChangeType.ADDED,
                        category=self._categorize_attribute_change(
                            parent_path, None, added_items
                        ),
                        severity=self._determine_attribute_severity(
                            parent_path, None, added_items
                        ),
                        description=f"Added items to {parent_path}: {added_items}",
                    )
                    changes.append(change)

                if removed_items:
                    change = AttributeChange(
                        attribute_path=f"{parent_path}[removed]",
                        old_value=list(removed_items),
                        new_value=None,
                        change_type=ChangeType.REMOVED,
                        category=self._categorize_attribute_change(
                            parent_path, removed_items, None
                        ),
                        severity=self._determine_attribute_severity(
                            parent_path, removed_items, None
                        ),
                        description=f"Removed items from {parent_path}: {removed_items}",
                    )
                    changes.append(change)
            else:
                # Handle as ordered lists (for complex objects)
                if len(old_list) != len(new_list) or old_list != new_list:
                    change = AttributeChange(
                        attribute_path=parent_path,
                        old_value=old_list,
                        new_value=new_list,
                        change_type=ChangeType.MODIFIED,
                        category=self._categorize_attribute_change(
                            parent_path, old_list, new_list
                        ),
                        severity=self._determine_attribute_severity(
                            parent_path, old_list, new_list
                        ),
                        description=f"List {parent_path} modified",
                    )
                    changes.append(change)
        except (TypeError, ValueError):
            # Fallback to simple comparison
            if old_list != new_list:
                change = AttributeChange(
                    attribute_path=parent_path,
                    old_value=old_list,
                    new_value=new_list,
                    change_type=ChangeType.MODIFIED,
                    category=self._categorize_attribute_change(
                        parent_path, old_list, new_list
                    ),
                    severity=self._determine_attribute_severity(
                        parent_path, old_list, new_list
                    ),
                    description=f"List {parent_path} modified",
                )
                changes.append(change)

        return changes

    def _determine_attribute_change_type(
        self, old_value: Any, new_value: Any
    ) -> ChangeType:
        """Determine the type of change for an attribute"""
        if old_value is None and new_value is not None:
            return ChangeType.ADDED
        elif old_value is not None and new_value is None:
            return ChangeType.REMOVED
        else:
            return ChangeType.MODIFIED

    def _categorize_attribute_change(
        self, attribute_path: str, old_value: Any, new_value: Any
    ) -> ChangeCategory:
        """Categorize the type of attribute change"""
        path_lower = attribute_path.lower()

        # Security-related changes - check both the path and parent path for encryption
        if any(
            keyword in path_lower
            for keyword in [
                "security",
                "iam",
                "policy",
                "permission",
                "role",
                "encryption",
                "public",
                "private",
                "acl",
                "firewall",
                "ssl",
                "tls",
                "certificate",
            ]
        ) or path_lower.startswith("encryption."):
            return ChangeCategory.SECURITY

        # Network-related changes
        elif any(
            keyword in path_lower
            for keyword in [
                "vpc",
                "subnet",
                "network",
                "ip",
                "cidr",
                "route",
                "gateway",
                "dns",
                "port",
                "protocol",
                "endpoint",
                "load_balancer",
            ]
        ):
            return ChangeCategory.NETWORK

        # Tag-related changes
        elif "tag" in path_lower or path_lower == "tags":
            return ChangeCategory.TAGS

        # Compliance-related changes
        elif any(
            keyword in path_lower
            for keyword in ["compliance", "compliant", "violation", "policy_status"]
        ):
            return ChangeCategory.COMPLIANCE

        # Configuration changes (default)
        else:
            return ChangeCategory.CONFIGURATION

    def _determine_attribute_severity(
        self, attribute_path: str, old_value: Any, new_value: Any
    ) -> ChangeSeverity:
        """Determine the severity of an attribute change"""
        path_lower = attribute_path.lower()

        # Check custom severity rules
        for pattern, severity in self.severity_rules.items():
            if pattern in path_lower:
                return severity

        # Default severity based on change type
        if old_value is None or new_value is None:
            # Addition or removal is generally more significant
            return ChangeSeverity.MEDIUM
        else:
            # Modification severity depends on the attribute
            if any(
                keyword in path_lower
                for keyword in ["security", "encryption", "public"]
            ):
                return ChangeSeverity.HIGH
            elif any(keyword in path_lower for keyword in ["compliance", "policy"]):
                return ChangeSeverity.HIGH
            elif "tag" in path_lower:
                return ChangeSeverity.MEDIUM
            else:
                return ChangeSeverity.LOW

    def _generate_change_description(
        self, attribute_path: str, old_value: Any, new_value: Any
    ) -> str:
        """Generate a human-readable description of the change"""
        if old_value is None:
            return f"Added {attribute_path}: {new_value}"
        elif new_value is None:
            return f"Removed {attribute_path}: {old_value}"
        else:
            return f"Changed {attribute_path}: {old_value} -> {new_value}"

    def _detect_compliance_changes(
        self, old_resource: Dict, new_resource: Dict
    ) -> List[AttributeChange]:
        """Detect compliance-specific changes"""
        compliance_changes = []

        old_compliance = old_resource.get("compliance_status")
        new_compliance = new_resource.get("compliance_status")

        if old_compliance != new_compliance:
            severity = (
                ChangeSeverity.HIGH
                if new_compliance == "non-compliant"
                else ChangeSeverity.MEDIUM
            )

            change = AttributeChange(
                attribute_path="compliance_status",
                old_value=old_compliance,
                new_value=new_compliance,
                change_type=ChangeType.MODIFIED,
                category=ChangeCategory.COMPLIANCE,
                severity=severity,
                description=f"Compliance status changed: {old_compliance} -> {new_compliance}",
            )
            compliance_changes.append(change)

        # Check for changes in compliance violations
        old_violations = old_resource.get("compliance_violations", [])
        new_violations = new_resource.get("compliance_violations", [])

        if old_violations != new_violations:
            change = AttributeChange(
                attribute_path="compliance_violations",
                old_value=old_violations,
                new_value=new_violations,
                change_type=ChangeType.MODIFIED,
                category=ChangeCategory.COMPLIANCE,
                severity=ChangeSeverity.HIGH,
                description="Compliance violations changed",
            )
            compliance_changes.append(change)

        return compliance_changes

    def _determine_resource_severity(
        self, resource: Dict, change_type: ChangeType
    ) -> ChangeSeverity:
        """Determine the severity of a resource-level change"""
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "").lower()

        # Critical services/resources
        if service in ["IAM", "KMS", "SECRETS_MANAGER"] or "security" in resource_type:
            return ChangeSeverity.CRITICAL

        # High impact services
        elif service in ["EC2", "RDS", "VPC", "ELB", "LAMBDA"]:
            return ChangeSeverity.HIGH

        # Medium impact services
        elif service in ["S3", "CLOUDFRONT", "ROUTE53"]:
            return ChangeSeverity.MEDIUM

        # Default severity
        else:
            return ChangeSeverity.LOW

    def _determine_change_severity(
        self, attribute_changes: List[AttributeChange]
    ) -> ChangeSeverity:
        """Determine overall severity for a resource based on its attribute changes"""
        if not attribute_changes:
            return ChangeSeverity.INFO

        # Return the highest severity among all changes
        severities = [change.severity for change in attribute_changes]
        severity_order = [
            ChangeSeverity.CRITICAL,
            ChangeSeverity.HIGH,
            ChangeSeverity.MEDIUM,
            ChangeSeverity.LOW,
            ChangeSeverity.INFO,
        ]

        for severity in severity_order:
            if severity in severities:
                return severity

        return ChangeSeverity.INFO

    def _get_highest_severity(self, severities: List[ChangeSeverity]) -> ChangeSeverity:
        """Get the highest severity from a list of severities"""
        if not severities:
            return ChangeSeverity.INFO

        severity_order = [
            ChangeSeverity.CRITICAL,
            ChangeSeverity.HIGH,
            ChangeSeverity.MEDIUM,
            ChangeSeverity.LOW,
            ChangeSeverity.INFO,
        ]

        for severity in severity_order:
            if severity in severities:
                return severity

        return ChangeSeverity.INFO

    def _assess_security_impact(
        self,
        resource: Dict,
        change_type: ChangeType,
        old_resource: Optional[Dict] = None,
    ) -> Optional[str]:
        """Assess the security impact of a resource change"""
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "").lower()

        security_impacts = []

        # Security-critical services
        if service in ["IAM", "KMS", "SECRETS_MANAGER"]:
            if change_type == ChangeType.ADDED:
                security_impacts.append(
                    f"New {service} resource may affect access controls"
                )
            elif change_type == ChangeType.REMOVED:
                security_impacts.append(
                    f"Removed {service} resource may break access controls"
                )
            elif change_type == ChangeType.MODIFIED and old_resource:
                security_impacts.append(
                    f"Modified {service} resource may change access patterns"
                )

        # Security groups
        if "security" in resource_type and "group" in resource_type:
            if change_type == ChangeType.ADDED:
                security_impacts.append(
                    "New security group may introduce network access changes"
                )
            elif change_type == ChangeType.REMOVED:
                security_impacts.append(
                    "Removed security group may affect network access"
                )
            elif change_type == ChangeType.MODIFIED:
                security_impacts.append(
                    "Modified security group rules may change network access"
                )

        # Public access changes
        if old_resource and change_type == ChangeType.MODIFIED:
            old_public = self._is_publicly_accessible(old_resource)
            new_public = self._is_publicly_accessible(resource)

            if old_public != new_public:
                if new_public:
                    security_impacts.append("Resource became publicly accessible")
                else:
                    security_impacts.append("Resource is no longer publicly accessible")

        return "; ".join(security_impacts) if security_impacts else None

    def _assess_network_impact(
        self,
        resource: Dict,
        change_type: ChangeType,
        old_resource: Optional[Dict] = None,
    ) -> Optional[str]:
        """Assess the network impact of a resource change"""
        service = resource.get("service", "").upper()
        resource_type = resource.get("type", "").lower()

        network_impacts = []

        # Network-critical resources
        if service in ["VPC", "EC2"] or any(
            keyword in resource_type
            for keyword in ["vpc", "subnet", "gateway", "route"]
        ):
            if change_type == ChangeType.ADDED:
                network_impacts.append(
                    f"New {service} resource may affect network topology"
                )
            elif change_type == ChangeType.REMOVED:
                network_impacts.append(
                    f"Removed {service} resource may disrupt network connectivity"
                )
            elif change_type == ChangeType.MODIFIED:
                network_impacts.append(
                    f"Modified {service} resource may change network behavior"
                )

        # VPC/Subnet changes
        if old_resource and change_type == ChangeType.MODIFIED:
            old_vpc = old_resource.get("vpc_id")
            new_vpc = resource.get("vpc_id")
            old_subnet = old_resource.get("subnet_id")
            new_subnet = resource.get("subnet_id")

            if old_vpc != new_vpc:
                network_impacts.append(f"VPC changed from {old_vpc} to {new_vpc}")
            if old_subnet != new_subnet:
                network_impacts.append(
                    f"Subnet changed from {old_subnet} to {new_subnet}"
                )

        return "; ".join(network_impacts) if network_impacts else None

    def _is_publicly_accessible(self, resource: Dict) -> bool:
        """Check if a resource is publicly accessible"""
        # Check various indicators of public access
        public_indicators = [
            resource.get("public_access", False),
            resource.get("publicly_accessible", False),
            "0.0.0.0/0" in str(resource.get("security_groups", [])),
            resource.get("public_ip") is not None,
            resource.get("public_dns_name") is not None,
        ]

        return any(public_indicators)

    def _analyze_compliance_changes(
        self,
        old_resources: List[Dict],
        new_resources: List[Dict],
        modified_resources: List[ResourceChange],
    ) -> Dict[str, Any]:
        """Analyze compliance changes across all resources"""
        # Calculate compliance statistics for old and new states
        old_compliance_stats = self._calculate_compliance_stats(old_resources)
        new_compliance_stats = self._calculate_compliance_stats(new_resources)

        # Identify resources with compliance status changes
        compliance_status_changes = []
        for change in modified_resources:
            compliance_changes = [
                c
                for c in change.compliance_changes
                if c.attribute_path == "compliance_status"
            ]
            if compliance_changes:
                compliance_status_changes.append(
                    {
                        "resource_arn": change.resource_arn,
                        "old_status": compliance_changes[0].old_value,
                        "new_status": compliance_changes[0].new_value,
                        "severity": compliance_changes[0].severity.value,
                    }
                )

        return {
            "old_compliance_stats": old_compliance_stats,
            "new_compliance_stats": new_compliance_stats,
            "compliance_trend": {
                "compliance_percentage_change": new_compliance_stats[
                    "compliance_percentage"
                ]
                - old_compliance_stats["compliance_percentage"],
                "newly_compliant": len(
                    [
                        c
                        for c in compliance_status_changes
                        if c["new_status"] == "compliant"
                    ]
                ),
                "newly_non_compliant": len(
                    [
                        c
                        for c in compliance_status_changes
                        if c["new_status"] == "non-compliant"
                    ]
                ),
            },
            "compliance_status_changes": compliance_status_changes,
        }

    def _analyze_security_changes(
        self, all_changes: List[ResourceChange]
    ) -> Dict[str, Any]:
        """Analyze security-related changes"""
        security_changes = []
        high_risk_changes = []

        for change in all_changes:
            # Check for security-related attribute changes
            security_attrs = [
                c
                for c in change.attribute_changes
                if c.category == ChangeCategory.SECURITY
            ]
            if security_attrs:
                security_changes.append(
                    {
                        "resource_arn": change.resource_arn,
                        "service": change.service,
                        "change_type": change.change_type.value,
                        "security_changes": len(security_attrs),
                        "highest_severity": self._get_highest_severity(
                            [c.severity for c in security_attrs]
                        ).value,
                    }
                )

                # Track high-risk changes
                if any(
                    c.severity in [ChangeSeverity.CRITICAL, ChangeSeverity.HIGH]
                    for c in security_attrs
                ):
                    high_risk_changes.append(change.resource_arn)

        return {
            "total_security_changes": len(security_changes),
            "high_risk_resources": high_risk_changes,
            "security_change_details": security_changes,
            "security_summary": {
                "critical_changes": len(
                    [c for c in security_changes if c["highest_severity"] == "critical"]
                ),
                "high_changes": len(
                    [c for c in security_changes if c["highest_severity"] == "high"]
                ),
                "medium_changes": len(
                    [c for c in security_changes if c["highest_severity"] == "medium"]
                ),
                "low_changes": len(
                    [c for c in security_changes if c["highest_severity"] == "low"]
                ),
            },
        }

    def _analyze_network_changes(
        self, all_changes: List[ResourceChange]
    ) -> Dict[str, Any]:
        """Analyze network-related changes"""
        network_changes = []
        vpc_changes = []
        subnet_changes = []

        for change in all_changes:
            # Check for network-related attribute changes
            network_attrs = [
                c
                for c in change.attribute_changes
                if c.category == ChangeCategory.NETWORK
            ]
            if network_attrs:
                network_changes.append(
                    {
                        "resource_arn": change.resource_arn,
                        "service": change.service,
                        "change_type": change.change_type.value,
                        "network_changes": len(network_attrs),
                        "network_impact": change.network_impact,
                    }
                )

            # Track VPC and subnet specific changes
            vpc_attrs = [
                c for c in change.attribute_changes if "vpc" in c.attribute_path.lower()
            ]
            subnet_attrs = [
                c
                for c in change.attribute_changes
                if "subnet" in c.attribute_path.lower()
            ]

            if vpc_attrs:
                vpc_changes.append(change.resource_arn)
            if subnet_attrs:
                subnet_changes.append(change.resource_arn)

        return {
            "total_network_changes": len(network_changes),
            "vpc_affected_resources": vpc_changes,
            "subnet_affected_resources": subnet_changes,
            "network_change_details": network_changes,
        }

    def _analyze_change_impact(
        self,
        all_changes: List[ResourceChange],
        old_resources_map: Dict[str, Dict],
        new_resources_map: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """Analyze the impact of changes on related resources"""
        impact_analysis = {
            "high_impact_changes": [],
            "dependency_impacts": {},
            "cascade_risks": [],
        }

        for change in all_changes:
            service = change.service.upper()

            # Check if this service has dependency patterns
            if service in self.dependency_patterns:
                patterns = self.dependency_patterns[service]

                # Find related resources that might be affected
                related_resources = self._find_related_resources(
                    change, patterns, old_resources_map, new_resources_map
                )

                if related_resources:
                    change.related_resources = related_resources

                    # Assess impact severity
                    if change.severity in [
                        ChangeSeverity.CRITICAL,
                        ChangeSeverity.HIGH,
                    ]:
                        impact_analysis["high_impact_changes"].append(
                            {
                                "resource_arn": change.resource_arn,
                                "service": change.service,
                                "change_type": change.change_type.value,
                                "severity": change.severity.value,
                                "related_resources": related_resources,
                                "potential_impact": f"Changes to {service} may affect {len(related_resources)} related resources",
                            }
                        )

                    # Track dependency impacts
                    if service not in impact_analysis["dependency_impacts"]:
                        impact_analysis["dependency_impacts"][service] = []
                    impact_analysis["dependency_impacts"][service].append(
                        {
                            "changed_resource": change.resource_arn,
                            "affected_resources": related_resources,
                        }
                    )

        # Identify cascade risks (resources that depend on multiple changed resources)
        cascade_risks = self._identify_cascade_risks(
            all_changes, old_resources_map, new_resources_map
        )
        impact_analysis["cascade_risks"] = cascade_risks

        return impact_analysis

    def _find_related_resources(
        self,
        change: ResourceChange,
        dependency_patterns: Dict[str, List[str]],
        old_resources_map: Dict[str, Dict],
        new_resources_map: Dict[str, Dict],
    ) -> List[str]:
        """Find resources that might be affected by this change"""
        related_resources = []

        # Get the resource data
        resource_data = new_resources_map.get(
            change.resource_arn
        ) or old_resources_map.get(change.resource_arn)
        if not resource_data:
            return related_resources

        # Check resources that depend on this one
        for arn, resource in new_resources_map.items():
            if arn == change.resource_arn:
                continue

            resource_service = resource.get("service", "").upper()

            # Check if this resource type depends on the changed resource type
            if resource_service in self.dependency_patterns:
                depends_on = self.dependency_patterns[resource_service].get(
                    "depends_on", []
                )
                if change.service.upper() in depends_on:
                    # Check for actual relationships (VPC, subnet, security groups, etc.)
                    if self._resources_are_related(resource_data, resource):
                        related_resources.append(arn)

        # Check resources that this one affects
        affects = dependency_patterns.get("affects", [])
        for arn, resource in new_resources_map.items():
            if arn == change.resource_arn:
                continue

            resource_service = resource.get("service", "").upper()
            if resource_service in affects:
                if self._resources_are_related(resource_data, resource):
                    related_resources.append(arn)

        return related_resources

    def _resources_are_related(self, resource1: Dict, resource2: Dict) -> bool:
        """Check if two resources are actually related"""
        # Check common relationship indicators
        relationship_fields = [
            "vpc_id",
            "subnet_id",
            "security_groups",
            "iam_role",
            "kms_key_id",
        ]

        for field in relationship_fields:
            value1 = resource1.get(field)
            value2 = resource2.get(field)

            if value1 and value2:
                # Handle both single values and lists
                if isinstance(value1, list) and isinstance(value2, list):
                    if set(value1) & set(value2):  # Intersection
                        return True
                elif isinstance(value1, list):
                    if value2 in value1:
                        return True
                elif isinstance(value2, list):
                    if value1 in value2:
                        return True
                elif value1 == value2:
                    return True

        return False

    def _identify_cascade_risks(
        self,
        all_changes: List[ResourceChange],
        old_resources_map: Dict[str, Dict],
        new_resources_map: Dict[str, Dict],
    ) -> List[Dict]:
        """Identify resources at risk of cascade failures"""
        cascade_risks = []

        # Group changes by related resources
        resource_change_count = {}
        for change in all_changes:
            for related_arn in change.related_resources:
                if related_arn not in resource_change_count:
                    resource_change_count[related_arn] = []
                resource_change_count[related_arn].append(change.resource_arn)

        # Identify resources affected by multiple changes
        for resource_arn, affecting_changes in resource_change_count.items():
            if len(affecting_changes) > 1:  # Multiple dependencies changed
                resource_data = new_resources_map.get(
                    resource_arn
                ) or old_resources_map.get(resource_arn)
                if resource_data:
                    cascade_risks.append(
                        {
                            "resource_arn": resource_arn,
                            "service": resource_data.get("service", ""),
                            "type": resource_data.get("type", ""),
                            "affecting_changes": affecting_changes,
                            "risk_level": (
                                "high" if len(affecting_changes) > 2 else "medium"
                            ),
                            "description": f"Resource depends on {len(affecting_changes)} resources that have changed",
                        }
                    )

        return cascade_risks

    def _calculate_compliance_stats(self, resources: List[Dict]) -> Dict[str, Any]:
        """Calculate compliance statistics for a set of resources"""
        total_resources = len(resources)
        if total_resources == 0:
            return {
                "total_resources": 0,
                "compliant_resources": 0,
                "non_compliant_resources": 0,
                "compliance_percentage": 0.0,
            }

        compliant_count = len(
            [r for r in resources if r.get("compliance_status") == "compliant"]
        )
        non_compliant_count = len(
            [r for r in resources if r.get("compliance_status") == "non-compliant"]
        )

        return {
            "total_resources": total_resources,
            "compliant_resources": compliant_count,
            "non_compliant_resources": non_compliant_count,
            "compliance_percentage": (compliant_count / total_resources) * 100.0,
        }

    def _generate_change_statistics(
        self,
        added_resources: List[ResourceChange],
        removed_resources: List[ResourceChange],
        modified_resources: List[ResourceChange],
        unchanged_resources: List[ResourceChange],
    ) -> Dict[str, Any]:
        """Generate comprehensive change statistics"""
        all_changes = added_resources + removed_resources + modified_resources

        # Statistics by service
        service_stats = {}
        for change in all_changes:
            service = change.service
            if service not in service_stats:
                service_stats[service] = {"added": 0, "removed": 0, "modified": 0}
            service_stats[service][change.change_type.value] += 1

        # Statistics by severity
        severity_stats = {}
        for change in all_changes:
            severity = change.severity.value
            if severity not in severity_stats:
                severity_stats[severity] = 0
            severity_stats[severity] += 1

        # Statistics by category
        category_stats = {}
        for change in modified_resources:
            for attr_change in change.attribute_changes:
                category = attr_change.category.value
                if category not in category_stats:
                    category_stats[category] = 0
                category_stats[category] += 1

        return {
            "total_changes": len(all_changes),
            "change_percentage": (
                (len(all_changes) / (len(all_changes) + len(unchanged_resources)))
                * 100.0
                if (len(all_changes) + len(unchanged_resources)) > 0
                else 0.0
            ),
            "service_statistics": service_stats,
            "severity_statistics": severity_stats,
            "category_statistics": category_stats,
            "most_changed_service": (
                max(service_stats.keys(), key=lambda k: sum(service_stats[k].values()))
                if service_stats
                else None
            ),
        }
