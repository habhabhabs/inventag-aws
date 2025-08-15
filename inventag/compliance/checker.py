#!/usr/bin/env python3
"""
InvenTag - Tag Compliance Checker
Enterprise-grade AWS™ resource tag compliance validation tool.

Extracted from scripts/tag_compliance_checker.py and enhanced for the unified inventag package.
"""

import json
import yaml
import boto3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from botocore.exceptions import ClientError, NoCredentialsError
import time


class ComprehensiveTagComplianceChecker:
    def __init__(
        self, regions: Optional[List[str]] = None, config_file: Optional[str] = None
    ):
        """Initialize the Comprehensive Tag Compliance Checker."""
        self.session = boto3.Session()
        self.logger = self._setup_logging()
        self.regions = regions or self._get_available_regions()
        self.config_file = config_file
        self.tag_policy = self._load_tag_policy()
        self.all_resources = []
        self.compliance_results = {
            "compliant": [],
            "non_compliant": [],
            "untagged": [],
            "summary": {},
        }

    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
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

            # Validate configuration structure
            if "required_tags" not in config:
                raise ValueError("Configuration must contain 'required_tags' section")

            if not isinstance(config["required_tags"], list):
                raise ValueError("'required_tags' must be a list")

            if len(config["required_tags"]) == 0:
                print(
                    "WARNING: Configuration file contains no required tags. Consider adding at least 1 required tag key."
                )

            self.logger.info(f"Loaded tag policy from {self.config_file}")
            self.logger.info(f"Required tags: {len(config['required_tags'])}")

            return config

        except FileNotFoundError:
            self.logger.error(f"Configuration file {self.config_file} not found")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def discover_all_resources(self) -> List[Dict[str, Any]]:
        """Discover ALL AWS resources using Resource Groups Tagging API and other comprehensive methods."""
        self.logger.info(
            "Starting comprehensive AWS resource discovery across ALL services..."
        )

        # Method 1: Use Resource Groups Tagging API for comprehensive discovery
        self._discover_via_resource_groups_tagging_api()

        # Method 2: Use AWS Config (if available) for additional resources
        self._discover_via_config_service()

        # Method 3: Service-specific discovery for resources that might not appear in RGT API
        self._discover_additional_resources()

        # Remove duplicates based on ARN
        self._deduplicate_resources()

        self.logger.info(
            f"Comprehensive discovery complete. Found {len(self.all_resources)} unique resources."
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
                            arn_parts = arn.split(":")

                            if len(arn_parts) >= 6:
                                service = arn_parts[2]
                                region_from_arn = arn_parts[3]
                                account_id = arn_parts[4]
                                resource_part = arn_parts[5]

                                # Extract resource type and ID
                                if "/" in resource_part:
                                    resource_type, resource_id = resource_part.split(
                                        "/", 1
                                    )
                                else:
                                    resource_type = resource_part
                                    resource_id = resource_part

                                # Convert tag list to dictionary
                                tags = {
                                    tag["Key"]: tag["Value"]
                                    for tag in resource.get("Tags", [])
                                }

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
                                    "discovered_at": datetime.utcnow().isoformat(),
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
        self.logger.info("Discovering resources via AWS Config...")
        # Simplified implementation - full implementation would be more comprehensive
        pass

    def _discover_additional_resources(self):
        """Discover additional resources that might not appear in RGT API."""
        self.logger.info(
            "Discovering additional resources via service-specific APIs..."
        )
        # Simplified implementation - full implementation would include more services
        pass

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

        required_tags = self.tag_policy.get("required_tags", [])

        for resource in resources:
            tags = resource.get("tags", {}) or {}

            if not tags:
                untagged.append(resource)
                continue

            # Check if all required tags are present
            missing_tags = []
            for required_tag in required_tags:
                if isinstance(required_tag, str):
                    tag_key = required_tag
                elif isinstance(required_tag, dict):
                    tag_key = required_tag.get("key", "")
                else:
                    continue

                if tag_key not in tags:
                    missing_tags.append(tag_key)

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

        compliance_percentage = (
            (compliant_count / total_resources * 100) if total_resources > 0 else 0
        )

        summary = {
            "total_resources": total_resources,
            "compliant_resources": compliant_count,
            "non_compliant_resources": non_compliant_count,
            "untagged_resources": untagged_count,
            "compliance_percentage": round(compliance_percentage, 2),
            "check_timestamp": datetime.utcnow().isoformat(),
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

    def save_results(self, filename: str, format_type: str = "json"):
        """Save compliance results to file."""
        if format_type.lower() == "json":
            with open(filename, "w") as f:
                json.dump(self.compliance_results, f, indent=2, default=str)
        elif format_type.lower() == "yaml":
            with open(filename, "w") as f:
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
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

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

    def _generate_excel_bom(self, bom_data, filename: str):
        """Generate Excel BOM document."""
        from ..reporting import BOMConverter

        # Create a temporary JSON file with the processed data
        temp_data = []
        for resource in bom_data.resources:
            # Add compliance status to each resource
            resource_copy = resource.copy()

            # Determine compliance status
            if resource in self.compliance_results["compliant"]:
                resource_copy["compliance_status"] = "Compliant"
            elif resource in self.compliance_results["non_compliant"]:
                resource_copy["compliance_status"] = "Non-Compliant"
                # Add missing tags info if available
                for nc_resource in self.compliance_results["non_compliant"]:
                    if nc_resource.get("arn") == resource.get("arn"):
                        resource_copy["missing_tags"] = ", ".join(
                            nc_resource.get("missing_tags", [])
                        )
                        break
            elif resource in self.compliance_results["untagged"]:
                resource_copy["compliance_status"] = "Untagged"
            else:
                resource_copy["compliance_status"] = "Unknown"

            temp_data.append(resource_copy)

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
                f.write("InvenTag Compliance BOM Report\n")
                f.write("=" * 40 + "\n\n")
                f.write(f"Generated: {datetime.utcnow().isoformat()}\n")
                f.write(f"Total Resources: {len(bom_data.resources)}\n")
                f.write(
                    f"Compliance Rate: {bom_data.compliance_details['compliance_percentage']}%\n\n"
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

        # Prepare data with compliance status
        temp_data = []
        for resource in bom_data.resources:
            resource_copy = resource.copy()

            # Add compliance status
            if resource in self.compliance_results["compliant"]:
                resource_copy["compliance_status"] = "Compliant"
            elif resource in self.compliance_results["non_compliant"]:
                resource_copy["compliance_status"] = "Non-Compliant"
            elif resource in self.compliance_results["untagged"]:
                resource_copy["compliance_status"] = "Untagged"
            else:
                resource_copy["compliance_status"] = "Unknown"

            temp_data.append(resource_copy)

        # Use BOM converter to generate CSV
        converter = BOMConverter(enrich_vpc_info=False)
        converter.data = temp_data
        converter.export_to_csv(filename)

    def upload_to_s3(self, bucket_name: str, key: str, format_type: str = "json"):
        """Upload compliance results to S3."""
        try:
            s3 = self.session.client("s3")

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
                Bucket=bucket_name, Key=key, Body=content, ContentType=content_type
            )

            self.logger.info(f"Compliance results uploaded to s3://{bucket_name}/{key}")

        except ClientError as e:
            self.logger.error(f"Failed to upload to S3: {e}")
            raise
