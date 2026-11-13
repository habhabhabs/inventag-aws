#!/usr/bin/env python3
"""
InvenTag - Tag Compliance Checker
Checks AWS resource tags against a list of required tag keys.

This is the engine behind ``scripts/legacy/tag_compliance_checker.py``. The
``inventag --template`` tag-policy check uses ``inventag.templating`` instead,
which also supports allowed values, patterns and scope rules.

What it checks: a resource is compliant when it has at least one user tag and
every required tag key is present. Tag keys are compared case-sensitively, as
AWS does. Values are not checked. Tags whose key starts with ``aws:`` are
created by AWS and are not counted as user tags.

It does not assess or certify compliance with any security or regulatory
framework.
"""

import json
import yaml
import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set, Tuple
from botocore.exceptions import ClientError, NoCredentialsError
import time

from ..security.read_only_guard import ReadOnlyGuard
from ..security.safe_output import open_private

# AWS reserves this tag-key prefix for tags it creates itself; users cannot
# set them (for example, S3 rejects them with "System tags cannot be added").
SYSTEM_TAG_PREFIX = "aws:"


def user_tags(resource: Any) -> Dict[str, str]:
    """Return the user tags of a resource as ``{key: value}``.

    Accepts ``{"k": "v"}`` or ``[{"Key": "k", "Value": "v"}]``. Tags whose key
    starts with ``aws:`` (any case) are dropped: AWS creates them, so they say
    nothing about whether a person tagged the resource. ``None`` values become
    empty strings. Keys are left exactly as given (tag keys are case-sensitive).
    """
    raw = resource.get("tags") if isinstance(resource, dict) else None
    pairs: List[Tuple[Any, Any]] = []
    if isinstance(raw, dict):
        pairs = list(raw.items())
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                key = item.get("Key", item.get("key"))
                pairs.append((key, item.get("Value", item.get("value"))))
    tags: Dict[str, str] = {}
    for key, value in pairs:
        if key is None:
            continue
        key = str(key)
        if key.lower().startswith(SYSTEM_TAG_PREFIX):
            continue
        tags[key] = "" if value is None else str(value)
    return tags


def _resource_key(resource: Dict[str, Any]):
    """Identity used to match a resource to its compliance status."""
    return resource.get("arn") or (
        resource.get("service"),
        resource.get("type"),
        resource.get("id"),
        resource.get("region"),
    )


class ComprehensiveTagComplianceChecker:
    def __init__(
        self,
        regions: Optional[List[str]] = None,
        config_file: Optional[str] = None,
        session: Optional[boto3.Session] = None,
        policy: Optional[Dict[str, Any]] = None,
        strict_policy: bool = False,
    ):
        """Initialize the Comprehensive Tag Compliance Checker.

        Args:
            regions: regions to scan when discovering resources itself
            config_file: tag policy file (YAML/JSON)
            session: boto3 session to use (default: default credentials)
            policy: tag policy as a dict (instead of config_file)
            strict_policy: raise ValueError when the policy has fields this
                checker does not enforce (such as ``allowed_values``). By
                default they are ignored with a warning and listed in
                ``summary["ignored_policy_fields"]``.
        """
        self.strict_policy = strict_policy
        self.ignored_policy_fields: List[str] = []
        self.session = session or boto3.Session()
        self.logger = self._setup_logging()
        self.regions = regions or self._get_available_regions()
        self.config_file = config_file
        self.tag_policy = (
            self._validate_tag_policy(policy)
            if policy is not None
            else self._load_tag_policy()
        )
        self.all_resources = []
        self.compliance_results = {
            "compliant": [],
            "non_compliant": [],
            "untagged": [],
            "summary": {},
        }

    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        # Not under the CLI, whose "inventag" logger already has handlers:
        # a root handler would print every message a second time.
        if not logging.getLogger("inventag").handlers:
            logging.basicConfig(
                level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
            )
        return logging.getLogger(__name__)

    def _get_available_regions(self) -> List[str]:
        """Get all available AWS regions with fallback."""
        try:
            ec2 = self.session.client("ec2", region_name="us-east-1")
            regions = ec2.describe_regions()["Regions"]
            region_list = [region["RegionName"] for region in regions]
            self.logger.info(f"Successfully retrieved {len(region_list)} AWS regions")
            return region_list
        except Exception as e:
            self.logger.warning(f"Failed to get all regions: {e}")
            self.logger.info(
                "Falling back to default regions: us-east-1, ap-southeast-1"
            )
            return ["us-east-1", "ap-southeast-1"]  # Fallback to key regions

    def _load_tag_policy(self) -> Dict[str, Any]:
        """Load tag policy from configuration file."""
        if not self.config_file:
            print(
                "WARNING: No configuration file specified. Only checking for completely untagged resources."
            )
            print(
                "It is recommended to provide a configuration file with at least 1 required tag key."
            )
            return {"required_tags": []}

        try:
            with open(self.config_file, "r") as f:
                if self.config_file.lower().endswith(".json"):
                    config = json.load(f)
                elif self.config_file.lower().endswith((".yaml", ".yml")):
                    config = yaml.safe_load(f)
                else:
                    # Try to detect format
                    content = f.read()
                    try:
                        config = json.loads(content)
                    except json.JSONDecodeError:
                        config = yaml.safe_load(content)

            config = self._validate_tag_policy(config)
            self.logger.info(f"Loaded tag policy from {self.config_file}")
            return config

        except FileNotFoundError:
            self.logger.error(f"Configuration file {self.config_file} not found")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def _validate_tag_policy(self, config: Any) -> Dict[str, Any]:
        """Check a tag policy has a valid list of required tags.

        Only required tag keys are enforced. Every other field (for example
        ``allowed_values``, ``pattern``, ``service_specific``) is recorded in
        ``self.ignored_policy_fields`` and logged, never silently dropped.
        """
        if not isinstance(config, dict):
            raise ValueError("Tag policy must be a mapping")
        if "required_tags" not in config:
            raise ValueError("Configuration must contain 'required_tags' section")
        if not isinstance(config["required_tags"], list):
            raise ValueError("'required_tags' must be a list")
        ignored: List[str] = []
        for index, entry in enumerate(config["required_tags"]):
            if isinstance(entry, str):
                key = entry
            elif isinstance(entry, dict):
                key = entry.get("key")
            else:
                raise ValueError(
                    f"required_tags[{index}] must be a tag key or a mapping with 'key'"
                )
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    f"required_tags[{index}] needs a non-empty string 'key'"
                )
            if key.lower().startswith(SYSTEM_TAG_PREFIX):
                raise ValueError(
                    f"required_tags[{index}]: '{key}' uses the reserved aws: prefix; "
                    "AWS-created tags are not counted as user tags"
                )
            if isinstance(entry, dict):
                ignored.extend(
                    f"required_tags[{key}].{name}" for name in entry if name != "key"
                )
        ignored.extend(name for name in config if name != "required_tags")
        if ignored:
            message = (
                "This checker only enforces that required tag keys are present. "
                "Not enforced: " + ", ".join(ignored)
            )
            if self.strict_policy:
                raise ValueError(message)
            self.logger.warning(message)
        self.ignored_policy_fields = ignored
        if len(config["required_tags"]) == 0:
            self.logger.warning(
                "Tag policy contains no required tags; only untagged resources "
                "will be reported. Consider adding at least 1 required tag key."
            )
        self.logger.info(f"Required tags: {len(config['required_tags'])}")
        return config

    def discover_all_resources(self) -> List[Dict[str, Any]]:
        """Discover resources with the Resource Groups Tagging API.

        That API lists resources of supported services that have tags (or had
        tags before). A resource that never had a tag is usually not returned,
        so the ``untagged`` result of a self-discovered run undercounts. Pass
        resources from a full inventory to ``check_compliance`` to count them.
        """
        self.logger.info("Starting resource discovery via the Tagging API...")

        # Method 1: Resource Groups Tagging API
        self._discover_via_resource_groups_tagging_api()

        # Methods 2 and 3 are placeholders and add nothing today.
        self._discover_via_config_service()
        self._discover_additional_resources()

        # Remove duplicates based on ARN
        self._deduplicate_resources()

        self.logger.info(
            f"Discovery complete. Found {len(self.all_resources)} unique resources."
        )
        return self.all_resources

    def _discover_via_resource_groups_tagging_api(self):
        """Use Resource Groups Tagging API to discover all taggable resources."""
        self.logger.info("Discovering resources via Resource Groups Tagging API...")

        for region in self.regions:
            try:
                rgt_client = self.session.client(
                    "resourcegroupstaggingapi", region_name=region
                )

                # Get all resources (paginated)
                paginator = rgt_client.get_paginator("get_resources")

                for page in paginator.paginate():
                    for resource in page.get("ResourceTagMappingList", []):
                        try:
                            # Parse ARN to extract service and resource type
                            arn = resource["ResourceARN"]
                            arn_parts = arn.split(":", 5)

                            if len(arn_parts) >= 6:
                                service = arn_parts[2]
                                region_from_arn = arn_parts[3]
                                account_id = arn_parts[4]
                                resource_part = arn_parts[5]

                                # Extract resource type and ID. The part after
                                # the account is "type/id", "type:id" or just an
                                # id (S3 buckets).
                                slash = resource_part.find("/")
                                colon = resource_part.find(":")
                                cut = (
                                    min(i for i in (slash, colon) if i >= 0)
                                    if (slash >= 0 or colon >= 0)
                                    else -1
                                )
                                if cut >= 0:
                                    resource_type = resource_part[:cut]
                                    resource_id = resource_part[cut + 1 :]
                                elif service == "s3":
                                    resource_type = "bucket"
                                    resource_id = resource_part
                                else:
                                    resource_type = resource_part
                                    resource_id = resource_part

                                # Convert tag list to dictionary
                                tags = {
                                    tag["Key"]: tag["Value"]
                                    for tag in resource.get("Tags", [])
                                }  # all tags, including aws:* (filtered when checking)

                                # Get additional resource details if possible
                                additional_info = self._get_additional_resource_info(
                                    service, resource_type, resource_id, region, arn
                                )

                                resource_info = {
                                    "service": service.upper(),
                                    "type": self._normalize_resource_type(
                                        service, resource_type
                                    ),
                                    "region": region_from_arn or region,
                                    "id": resource_id,
                                    "name": self._extract_resource_name(
                                        tags, additional_info
                                    ),
                                    "arn": arn,
                                    "tags": tags,
                                    "account_id": account_id,
                                    "discovered_via": "ResourceGroupsTaggingAPI",
                                    "discovered_at": datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                }

                                # Add additional info if available
                                if additional_info:
                                    resource_info.update(additional_info)

                                self.all_resources.append(resource_info)

                        except Exception as e:
                            self.logger.warning(
                                f"Error processing resource {resource.get('ResourceARN', 'unknown')}: {e}"
                            )
                            continue

                # Add small delay to avoid rate limiting
                time.sleep(0.1)

            except ClientError as e:
                if e.response["Error"]["Code"] == "UnauthorizedOperation":
                    self.logger.warning(
                        f"No permission for Resource Groups Tagging API in {region}"
                    )
                else:
                    self.logger.warning(
                        f"Failed to discover resources via RGT API in {region}: {e}"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Unexpected error in RGT API discovery for {region}: {e}"
                )

    def _discover_via_config_service(self):
        """Use AWS Config to discover additional resources."""
        # Not implemented: adds no resources.
        self.logger.debug("AWS Config discovery is not implemented; skipped")

    def _discover_additional_resources(self):
        """Discover additional resources that might not appear in RGT API."""
        # Not implemented: adds no resources.
        self.logger.debug("Service-specific discovery is not implemented; skipped")

    def _get_additional_resource_info(
        self, service: str, resource_type: str, resource_id: str, region: str, arn: str
    ) -> Dict:
        """Get additional resource information if possible."""
        # Simplified implementation
        return {}

    def _normalize_resource_type(self, service: str, resource_type: str) -> str:
        """Normalize resource type names."""
        # Basic normalization
        return resource_type.title()

    def _extract_resource_name(self, tags: Dict, additional_info: Dict) -> str:
        """Extract resource name from tags or additional info."""
        # Try to get name from tags first
        if tags and "Name" in tags:
            return tags["Name"]

        # Try additional info
        if additional_info and "name" in additional_info:
            return additional_info["name"]

        return ""

    def _deduplicate_resources(self):
        """Remove duplicate resources based on ARN."""
        seen_arns = set()
        deduplicated = []

        for resource in self.all_resources:
            arn = resource.get("arn", "")
            if arn not in seen_arns:
                seen_arns.add(arn)
                deduplicated.append(resource)

        removed_count = len(self.all_resources) - len(deduplicated)
        if removed_count > 0:
            self.logger.info(f"Removed {removed_count} duplicate resources")

        self.all_resources = deduplicated

    def check_compliance(
        self, resources: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Check tag compliance for all resources."""
        if resources is None:
            resources = self.discover_all_resources()

        self.logger.info(f"Checking compliance for {len(resources)} resources...")

        compliant = []
        non_compliant = []
        untagged = []

        skipped = [r for r in resources if not isinstance(r, dict)]
        if skipped:
            self.logger.warning(f"Skipping {len(skipped)} malformed resource entries")
            resources = [r for r in resources if isinstance(r, dict)]

        for resource in resources:
            # "aws:" system tags do not count: a resource that only has those
            # is untagged as far as a person is concerned.
            if not user_tags(resource):
                untagged.append(resource)
                continue

            _, missing_tags = self._check_resource_compliance(resource)

            if missing_tags:
                resource_copy = resource.copy()
                resource_copy["missing_tags"] = missing_tags
                non_compliant.append(resource_copy)
            else:
                compliant.append(resource)

        # Generate summary
        total_resources = len(resources)
        compliant_count = len(compliant)
        non_compliant_count = len(non_compliant)
        untagged_count = len(untagged)

        # Percentage = compliant / all resources given (untagged ones count in
        # the denominator and as not compliant), rounded to 2 decimals; 0 when
        # there are no resources.
        compliance_percentage = (
            (compliant_count / total_resources * 100) if total_resources > 0 else 0
        )

        summary = {
            "total_resources": total_resources,
            "compliant_resources": compliant_count,
            "non_compliant_resources": non_compliant_count,
            "untagged_resources": untagged_count,
            "compliance_percentage": round(compliance_percentage, 2),
            "ignored_policy_fields": list(self.ignored_policy_fields),
            "check_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.compliance_results = {
            "compliant": compliant,
            "non_compliant": non_compliant,
            "untagged": untagged,
            "summary": summary,
            "all_discovered_resources": resources,  # Include all resources for BOM generation
        }

        self.logger.info(
            f"Compliance check complete. {compliance_percentage:.1f}% compliant"
        )

        return self.compliance_results

    def _check_resource_compliance(
        self, resource: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Return (is_compliant, missing required tag keys) for one resource.

        Keys match exactly (case-sensitive). A key with an empty value counts as
        present. ``aws:`` tags are ignored.
        """
        tags = user_tags(resource)
        missing_tags: List[str] = []
        for required_tag in self.tag_policy.get("required_tags", []):
            if isinstance(required_tag, str):
                tag_key = required_tag
            elif isinstance(required_tag, dict):
                tag_key = required_tag.get("key", "")
            else:
                continue
            if tag_key not in tags and tag_key not in missing_tags:
                missing_tags.append(tag_key)
        return (bool(tags) and not missing_tags), missing_tags

    def save_results(self, filename: str, format_type: str = "json"):
        """Save compliance results to file (owner-only permissions)."""
        if format_type.lower() not in ("json", "yaml"):
            raise ValueError("Format must be 'json' or 'yaml'")
        if format_type.lower() == "json":
            with open_private(filename, "w") as f:
                json.dump(self.compliance_results, f, indent=2, default=str)
        elif format_type.lower() == "yaml":
            with open_private(filename, "w") as f:
                yaml.dump(
                    self.compliance_results,
                    f,
                    default_flow_style=False,
                    default_style="",
                    allow_unicode=True,
                )
        else:
            raise ValueError("Format must be 'json' or 'yaml'")

        self.logger.info(f"Compliance results saved to {filename}")

    def generate_bom_documents(
        self,
        output_formats: List[str] = None,
        output_directory: str = "bom_output",
        service_descriptions_file: str = None,
        tag_mappings_file: str = None,
        enable_vpc_enrichment: bool = True,
        enable_security_analysis: bool = True,
        enable_network_analysis: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate BOM documents from compliance results.

        This method provides seamless integration between compliance checking
        and BOM generation, allowing users to generate professional reports
        as an optional step after compliance analysis.

        Args:
            output_formats: List of formats to generate ('excel', 'word', 'csv')
            output_directory: Directory to save BOM documents
            service_descriptions_file: Path to service descriptions config
            tag_mappings_file: Path to tag mappings config
            enable_vpc_enrichment: Enable VPC/subnet name enrichment
            enable_security_analysis: Enable security group analysis
            enable_network_analysis: Enable network capacity analysis

        Returns:
            Dictionary with generation results and file paths
        """
        if not self.compliance_results or not self.compliance_results.get(
            "all_discovered_resources"
        ):
            raise ValueError(
                "No compliance results available. Run check_compliance() first."
            )

        self.logger.info("Starting BOM document generation from compliance results...")

        # Import BOM generation components
        try:
            from ..reporting import (
                BOMDataProcessor,
                BOMProcessingConfig,
                DocumentGenerator,
            )
            from ..discovery import NetworkAnalyzer, SecurityAnalyzer
            import os
            from pathlib import Path
        except ImportError as e:
            self.logger.error(f"Failed to import BOM generation components: {e}")
            raise

        # Set default formats if none specified
        if output_formats is None:
            output_formats = ["excel"]

        # Create output directory
        Path(output_directory).mkdir(parents=True, exist_ok=True)

        # Load configuration files
        bom_config = BOMProcessingConfig()

        if service_descriptions_file:
            try:
                with open(service_descriptions_file, "r") as f:
                    if service_descriptions_file.lower().endswith(".json"):
                        bom_config.service_descriptions = json.load(f)
                    else:
                        bom_config.service_descriptions = yaml.safe_load(f)
                self.logger.info(
                    f"Loaded service descriptions from {service_descriptions_file}"
                )
            except Exception as e:
                self.logger.warning(f"Could not load service descriptions: {e}")

        if tag_mappings_file:
            try:
                with open(tag_mappings_file, "r") as f:
                    if tag_mappings_file.lower().endswith(".json"):
                        bom_config.tag_mappings = json.load(f)
                    else:
                        bom_config.tag_mappings = yaml.safe_load(f)
                self.logger.info(f"Loaded tag mappings from {tag_mappings_file}")
            except Exception as e:
                self.logger.warning(f"Could not load tag mappings: {e}")

        # Configure BOM processing options
        bom_config.enable_vpc_enrichment = enable_vpc_enrichment
        bom_config.enable_security_analysis = enable_security_analysis
        bom_config.enable_network_analysis = enable_network_analysis

        # Get all discovered resources
        all_resources = self.compliance_results["all_discovered_resources"]

        # Initialize BOM processor
        processor = BOMDataProcessor(bom_config)

        # Process inventory data into BOM format
        self.logger.info(
            f"Processing {len(all_resources)} resources for BOM generation..."
        )
        bom_data = processor.process_inventory_data(all_resources)

        # Add compliance information to BOM data
        bom_data.compliance_summary = self.compliance_results["summary"]
        bom_data.compliance_details = {
            "compliant_resources": len(self.compliance_results["compliant"]),
            "non_compliant_resources": len(self.compliance_results["non_compliant"]),
            "untagged_resources": len(self.compliance_results["untagged"]),
            "compliance_percentage": self.compliance_results["summary"][
                "compliance_percentage"
            ],
        }

        # Generate timestamp for filenames
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Generate documents
        generated_files = []
        generation_results = {}

        for format_type in output_formats:
            try:
                if format_type.lower() == "excel":
                    filename = os.path.join(
                        output_directory, f"compliance_bom_{timestamp}.xlsx"
                    )
                    self._generate_excel_bom(bom_data, filename)
                    generated_files.append(filename)
                    generation_results[format_type] = {
                        "success": True,
                        "file": filename,
                    }

                elif format_type.lower() == "word":
                    filename = os.path.join(
                        output_directory, f"compliance_bom_{timestamp}.docx"
                    )
                    self._generate_word_bom(bom_data, filename)
                    generated_files.append(filename)
                    generation_results[format_type] = {
                        "success": True,
                        "file": filename,
                    }

                elif format_type.lower() == "csv":
                    filename = os.path.join(
                        output_directory, f"compliance_bom_{timestamp}.csv"
                    )
                    self._generate_csv_bom(bom_data, filename)
                    generated_files.append(filename)
                    generation_results[format_type] = {
                        "success": True,
                        "file": filename,
                    }

                else:
                    self.logger.warning(f"Unsupported format: {format_type}")
                    generation_results[format_type] = {
                        "success": False,
                        "error": f"Unsupported format: {format_type}",
                    }

            except Exception as e:
                self.logger.error(f"Failed to generate {format_type} BOM: {e}")
                generation_results[format_type] = {"success": False, "error": str(e)}

        # Return results
        result = {
            "success": len(generated_files) > 0,
            "generated_files": generated_files,
            "generation_results": generation_results,
            "total_resources": len(all_resources),
            "compliance_summary": self.compliance_results["summary"],
            "timestamp": timestamp,
        }

        if generated_files:
            self.logger.info(
                f"Successfully generated {len(generated_files)} BOM document(s)"
            )
            for file_path in generated_files:
                self.logger.info(f"  - {file_path}")
        else:
            self.logger.error("No BOM documents were generated successfully")

        return result

    def _rows_with_status(self, bom_data, include_missing: bool = False):
        """Copy BOM rows and add ``compliance_status`` (matched by ARN)."""
        status_by_key = {}
        for label, bucket in (
            ("Compliant", "compliant"),
            ("Non-Compliant", "non_compliant"),
            ("Untagged", "untagged"),
        ):
            for item in self.compliance_results[bucket]:
                status_by_key[_resource_key(item)] = (
                    label,
                    ", ".join(item.get("missing_tags", [])),
                )
        rows = []
        for resource in bom_data.resources:
            row = resource.copy()
            label, missing = status_by_key.get(_resource_key(resource), ("Unknown", ""))
            row["compliance_status"] = label
            if include_missing and label == "Non-Compliant":
                row["missing_tags"] = missing
            rows.append(row)
        return rows

    def _generate_excel_bom(self, bom_data, filename: str):
        """Generate Excel BOM document."""
        from ..reporting import BOMConverter

        temp_data = self._rows_with_status(bom_data, include_missing=True)

        # Use BOM converter to generate Excel
        converter = BOMConverter(enrich_vpc_info=False)  # Already enriched by processor
        converter.data = temp_data
        converter.export_to_excel(filename)

    def _generate_word_bom(self, bom_data, filename: str):
        """Generate Word BOM document."""
        try:
            from ..reporting import DocumentGenerator, DocumentConfig

            # Create document config
            doc_config = DocumentConfig()
            doc_config.include_compliance_section = True
            doc_config.include_executive_summary = True

            # Generate document
            generator = DocumentGenerator(doc_config)
            generator.generate_word_document(bom_data, filename)

        except ImportError:
            # Fallback: create a simple text-based report
            self.logger.warning(
                "Word document generation not available, creating text report"
            )
            with open(filename.replace(".docx", ".txt"), "w") as f:
                f.write("InvenTag Tag Check BOM Report\n")
                f.write("=" * 40 + "\n\n")
                f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"Total Resources: {len(bom_data.resources)}\n")
                f.write(
                    f"Resources with all required tags: {bom_data.compliance_details['compliance_percentage']}%\n\n"
                )

                # Write summary by service
                services = {}
                for resource in bom_data.resources:
                    service = resource.get("service", "Unknown")
                    services[service] = services.get(service, 0) + 1

                f.write("Resources by Service:\n")
                for service, count in sorted(services.items()):
                    f.write(f"  {service}: {count}\n")

    def _generate_csv_bom(self, bom_data, filename: str):
        """Generate CSV BOM document."""
        from ..reporting import BOMConverter

        temp_data = self._rows_with_status(bom_data)

        # Use BOM converter to generate CSV
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = temp_data
        converter.export_to_csv(filename)

    def upload_to_s3(
        self,
        bucket_name: str,
        key: str,
        format_type: str = "json",
        allow_write: bool = False,
    ):
        """Upload the results file to S3 (a write: ``s3:PutObject``).

        InvenTag is read-only by default, so this refuses unless the caller
        passes ``allow_write=True``. Even then the read-only guard, if
        installed, only lets ``PutObject`` through on this one client.
        """
        if not allow_write:
            raise PermissionError(
                "upload_to_s3 writes an object to S3 and is disabled by default; "
                "call it with allow_write=True to upload to a bucket you choose"
            )
        try:
            s3 = self.session.client("s3")
            ReadOnlyGuard.allow_on_client(s3, {"PutObject"})

            if format_type.lower() == "json":
                content = json.dumps(self.compliance_results, indent=2, default=str)
                content_type = "application/json"
            elif format_type.lower() == "yaml":
                content = yaml.dump(
                    self.compliance_results,
                    default_flow_style=False,
                    default_style="",
                    allow_unicode=True,
                )
                content_type = "text/yaml"
            else:
                raise ValueError("Format must be 'json' or 'yaml'")

            s3.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )

            self.logger.info(f"Compliance results uploaded to s3://{bucket_name}/{key}")

        except ClientError as e:
            self.logger.error(f"Failed to upload to S3: {e}")
            raise
