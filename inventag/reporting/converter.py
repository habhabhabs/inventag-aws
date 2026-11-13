#!/usr/bin/env python3
"""
InvenTag - BOM Converter
Professional AWS™ resource inventory to Excel/CSV converter.

Extracted from scripts/bom_converter.py and enhanced for the unified inventag package.
"""

import json
import yaml
import boto3
from typing import Dict, List, Any, Union, Optional
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from ..security.safe_output import (
    neutralize_workbook_formulas,
    open_private,
    precreate_private,
    write_safe_csv,
)
from .report_template import (
    ReportTemplate,
    build_context,
    default_template,
    substitute,
)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    # Create a placeholder for type hints when openpyxl is not available
    Workbook = Any

try:
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False
    # Create placeholders for type hints when python-docx is not available
    Document = Any


def _group_by_service(resources: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """Group resources by service. Services and rows are sorted, so the same
    estate gives the same sheet order and row order on every run (discovery
    runs in parallel and finishes in a different order each time)."""

    def row_key(resource: Dict[str, Any]) -> tuple:
        return tuple(
            str(resource.get(k) or "").lower()
            for k in ("type", "name", "id", "arn", "source_account_id", "region")
        )

    groups: Dict[str, List[Dict]] = {}
    for resource in resources:
        groups.setdefault(resource.get("service", "Unknown"), []).append(resource)
    return {
        service: sorted(rows, key=row_key)
        for service, rows in sorted(groups.items(), key=lambda kv: str(kv[0]).lower())
    }


class BOMConverter:
    def __init__(
        self,
        enrich_vpc_info: bool = True,
        enable_advanced_analysis: bool = False,
        session: Optional[boto3.Session] = None,
    ):
        """Initialize the BOM converter."""
        self.data = []
        self.headers = set()
        self.enrich_vpc_info = enrich_vpc_info
        self.enable_advanced_analysis = enable_advanced_analysis
        # Set by the CLI from --enable-network-analysis / --enable-security-analysis
        self.analyze_network = False
        self.analyze_security = False
        self.vpc_cache = {}  # Cache for VPC/subnet name lookups
        self.session = session or (boto3.Session() if enrich_vpc_info else None)

        # Advanced analysis components
        self.network_analysis = {}
        self.security_analysis = {}
        self.service_attributes = {}

    def load_data(self, filename: str) -> List[Dict[str, Any]]:
        """Load data from JSON or YAML file."""
        try:
            with open(filename, "r") as f:
                if filename.lower().endswith(".json"):
                    raw_data = json.load(f)
                elif filename.lower().endswith((".yaml", ".yml")):
                    raw_data = yaml.safe_load(f)
                else:
                    # Try to detect format by content
                    content = f.read()
                    try:
                        raw_data = json.loads(content)
                    except json.JSONDecodeError:
                        try:
                            raw_data = yaml.safe_load(content)
                        except yaml.YAMLError:
                            raise ValueError("Unable to parse file as JSON or YAML")

            # Handle different data structures
            self.data = self._extract_resources(raw_data)

            # Reclassify VPC-related resources
            self._reclassify_vpc_resources()

            # Standardize service names and fix resource types
            self._standardize_service_names()
            self._fix_resource_types()
            self._fix_id_and_name_parsing()
            self._fix_account_id_from_arn()
            self._deduplicate_resources()

            # Enrich VPC/subnet information if enabled
            if self.enrich_vpc_info:
                self._enrich_vpc_subnet_info()

            # Perform advanced analysis if enabled
            if self.enable_advanced_analysis:
                self._perform_network_analysis()
                self._perform_security_analysis()
                self._enrich_service_attributes()

            # Collect all possible headers from the data
            for item in self.data:
                if isinstance(item, dict):
                    self._collect_headers(item)

            print(f"Loaded {len(self.data)} resources from {filename}")
            return self.data

        except FileNotFoundError:
            print(f"Error: File {filename} not found")
            raise
        except Exception as e:
            print(f"Error loading data: {e}")
            raise

    def _extract_resources(self, raw_data: Union[Dict, List]) -> List[Dict[str, Any]]:
        """Extract resources from different data structures."""
        resources = []

        # If it's already a list, assume it's a list of resources
        if isinstance(raw_data, list):
            return raw_data

        # If it's a dict, check for common resource array keys
        if isinstance(raw_data, dict):
            # Try to find resource arrays in common formats
            resource_keys = [
                "all_discovered_resources",  # Preferred - contains all resources
                "compliant_resources",
                "non_compliant_resources",
                "untagged_resources",
                "resources",  # Generic key
                "items",  # Another common key
            ]

            # First try to get all resources from a single comprehensive array
            if "all_discovered_resources" in raw_data and isinstance(
                raw_data["all_discovered_resources"], list
            ):
                resources.extend(raw_data["all_discovered_resources"])
                print(f"Found {len(resources)} resources in 'all_discovered_resources'")
                return resources

            # Otherwise, collect from multiple arrays
            for key in resource_keys:
                if key in raw_data and isinstance(raw_data[key], list):
                    resources.extend(raw_data[key])
                    print(f"Found {len(raw_data[key])} resources in '{key}'")

            # If we found resources in arrays, return them
            if resources:
                return resources

            # If no resource arrays found, maybe the whole dict is a single resource
            # Check if it has typical resource fields
            if any(
                field in raw_data
                for field in ["service", "type", "id", "arn", "region"]
            ):
                return [raw_data]

        # Fallback: return empty list
        print("Warning: No resources found in the input data")
        return []

    def _reclassify_vpc_resources(self):
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
        for resource in self.data:
            if isinstance(resource, dict) and resource.get("service") == "EC2":
                resource_type = resource.get("type", "")
                if resource_type in vpc_resource_types:
                    resource["service"] = "VPC"
                    reclassified_count += 1

        if reclassified_count > 0:
            print(
                f"Reclassified {reclassified_count} VPC-related resources from EC2 to VPC service"
            )

    def _standardize_service_names(self):
        """Standardize service names to avoid duplicates."""
        standardizations = {
            "CloudFormation": "CLOUDFORMATION",
            "Lambda": "LAMBDA",
            # Add more as needed
        }

        standardized_count = 0
        for resource in self.data:
            if isinstance(resource, dict):
                service = resource.get("service", "")
                if service in standardizations:
                    resource["service"] = standardizations[service]
                    standardized_count += 1

        if standardized_count > 0:
            print(f"Standardized {standardized_count} service names")

    def _fix_resource_types(self):
        """Fix resource type inconsistencies."""
        # Simplified implementation
        pass

    def _fix_id_and_name_parsing(self):
        """Fix ID and name parsing issues by extracting correct values from ARNs."""
        # Simplified implementation
        pass

    def _fix_account_id_from_arn(self):
        """Extract and set account_id from ARN for resources missing this field."""
        # Simplified implementation
        pass

    def _deduplicate_resources(self):
        """Remove duplicate resources keeping the one with more complete information."""
        seen_resources = {}
        deduplicated = []
        duplicate_count = 0

        for resource in self.data:
            if isinstance(resource, dict):
                # Create a unique key based on ARN (most reliable) or fallback to service+id+region
                arn = resource.get("arn", "")
                if arn:
                    key = arn
                else:
                    service = resource.get("service", "")
                    res_id = resource.get("id", "")
                    region = resource.get("region", "")
                    key = f"{service}:{res_id}:{region}"

                if key in seen_resources:
                    duplicate_count += 1
                else:
                    seen_resources[key] = resource
                    deduplicated.append(resource)

        if duplicate_count > 0:
            print(f"Removed {duplicate_count} duplicate resources")

        self.data = deduplicated

    def _enrich_vpc_subnet_info(self):
        """Enrich resources with VPC and subnet name information."""
        if not self.session:
            return

        print("Enriching VPC/subnet information...")

        # Get unique regions from the data
        regions = set()
        for resource in self.data:
            region = resource.get("region", "")
            if region and region != "global":
                regions.add(region)

        # Cache VPC and subnet information for each region
        for region in regions:
            self._cache_vpc_subnet_info(region)

        # Apply enrichment to resources
        enriched_count = 0
        for resource in self.data:
            if self._enrich_single_resource(resource):
                enriched_count += 1

        if enriched_count > 0:
            print(f"Enriched {enriched_count} resources with VPC/subnet names")

    def _cache_vpc_subnet_info(self, region: str):
        """Cache VPC and subnet information for a region."""
        try:
            ec2 = self.session.client("ec2", region_name=region)

            # Cache VPC information
            vpcs = ec2.describe_vpcs()
            for vpc in vpcs["Vpcs"]:
                vpc_id = vpc["VpcId"]
                vpc_name = self._get_tag_value(vpc.get("Tags", []), "Name") or vpc_id
                self.vpc_cache[vpc_id] = {
                    "name": vpc_name,
                    "cidr_block": vpc["CidrBlock"],
                }

            # Cache subnet information
            subnets = ec2.describe_subnets()
            for subnet in subnets["Subnets"]:
                subnet_id = subnet["SubnetId"]
                subnet_name = (
                    self._get_tag_value(subnet.get("Tags", []), "Name") or subnet_id
                )
                self.vpc_cache[subnet_id] = {
                    "name": subnet_name,
                    "vpc_id": subnet["VpcId"],
                    "cidr_block": subnet["CidrBlock"],
                    "availability_zone": subnet["AvailabilityZone"],
                }

        except ClientError as e:
            print(f"Warning: Could not cache VPC/subnet info for {region}: {e}")

    def _enrich_single_resource(self, resource: Dict[str, Any]) -> bool:
        """Enrich a single resource with VPC/subnet information."""
        enriched = False

        # Enrich VPC ID with name
        vpc_id = resource.get("vpc_id")
        if vpc_id and vpc_id in self.vpc_cache:
            resource["vpc_name"] = self.vpc_cache[vpc_id]["name"]
            enriched = True

        # Enrich subnet ID with name
        subnet_id = resource.get("subnet_id")
        if subnet_id and subnet_id in self.vpc_cache:
            resource["subnet_name"] = self.vpc_cache[subnet_id]["name"]
            enriched = True

        return enriched

    def _get_tag_value(self, tags: Optional[List[Dict]], key: str) -> Optional[str]:
        """Get tag value by key."""
        for tag in tags or []:
            if tag.get("Key") == key:
                return tag.get("Value")
        return None

    def _collect_headers(self, item: Dict[str, Any], prefix: str = ""):
        """Recursively collect all possible headers from the data."""
        for key, value in item.items():
            if prefix:
                header = f"{prefix}.{key}"
            else:
                header = key

            if isinstance(value, dict):
                self._collect_headers(value, header)
            else:
                self.headers.add(header)

    def export_to_csv(self, filename: str):
        """Export data to CSV format."""
        if not self.data:
            print("No data to export")
            return

        # Flatten the data for CSV export
        flattened_data = []
        for item in self.data:
            flattened_item = self._flatten_dict(item)
            flattened_data.append(flattened_item)

        # Get all unique headers
        all_headers = set()
        for item in flattened_data:
            all_headers.update(item.keys())

        # Apply logical column ordering instead of alphabetical
        sorted_headers = self._get_logical_column_order(all_headers)

        # Write CSV
        with open_private(filename, "w", newline="", encoding="utf-8") as csvfile:
            write_safe_csv(csvfile, sorted_headers, flattened_data)

        print(f"Data exported to {filename}")

    def export_to_excel(self, filename: str, template: Optional[ReportTemplate] = None):
        """Export data to Excel format.

        ``template`` selects the sheets, their order and their columns. Without
        a template the built-in default applies: a summary sheet, then one
        sheet for each service.
        """
        if not OPENPYXL_AVAILABLE:
            print(
                "Error: openpyxl library not available. Please install it to export to Excel."
            )
            return

        if not self.data:
            print("No data to export")
            return

        template = self._resolve_template(template, "excel")
        context = build_context(template, self.data)

        # Group resources by service (sorted, so repeated runs match)
        services = _group_by_service(self.data)

        # Create workbook
        wb = Workbook()

        # Remove default sheet
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        for section in template.sections:
            content_type = section["content_type"]
            if content_type == "service_summary":
                self._create_summary_sheet(
                    wb, services, section=section, template=template, context=context
                )
            elif content_type == "resources":
                selected = self._select_services(services, section.get("services"))
                if section["group_by_service"]:
                    for service, resources in selected:
                        self._create_service_sheet(
                            wb, service, resources, section=section, template=template
                        )
                else:
                    combined = [r for _, group in selected for r in group]
                    self._create_service_sheet(
                        wb,
                        section["sheet_name"],
                        combined,
                        section=section,
                        template=template,
                    )
            elif content_type == "network_analysis":
                if (
                    self.enable_advanced_analysis or self.analyze_network
                ) and self.network_analysis:
                    self._create_network_analysis_sheet(wb)
            elif content_type == "security_analysis":
                if (
                    self.enable_advanced_analysis or self.analyze_security
                ) and self.security_analysis:
                    self._create_security_analysis_sheet(wb)

        if not wb.sheetnames:
            raise ValueError(
                f"The Excel template {template.source} gives a workbook with no "
                "sheets for this data. Enable a service_summary section, or "
                "make sure that the 'services' list matches a service in the report."
            )

        self._apply_workbook_branding(wb, template, context)

        # Save workbook (no data value may become a live formula; owner-only file)
        neutralize_workbook_formulas(wb)
        precreate_private(filename)
        wb.save(filename)
        print(f"Data exported to {filename}")

    @staticmethod
    def _resolve_template(
        template: Optional[ReportTemplate], format_type: str
    ) -> ReportTemplate:
        """Return ``template`` or the built-in default for ``format_type``."""
        if template is None:
            return default_template(format_type)
        if template.format_type != format_type:
            raise ValueError(
                f"Template {template.source} has format_type "
                f"'{template.format_type}', but '{format_type}' is necessary"
            )
        return template

    @staticmethod
    def _select_services(
        services: Dict[str, List], wanted: Optional[List[str]]
    ) -> list:
        """(service, resources) pairs to show, in order.

        Without ``wanted`` every service is shown, sorted by name. With
        ``wanted`` only those services are shown, in the order of the list.
        """
        if not wanted:
            return list(services.items())
        from ..discovery.service_filter import canonical_service

        by_key = {}
        for name, resources in services.items():
            by_key.setdefault(canonical_service(name), []).append((name, resources))
        selected = []
        seen = set()
        for name in wanted:
            key = canonical_service(name)
            if key in seen:
                continue
            seen.add(key)
            selected.extend(by_key.get(key, []))
        return selected

    @staticmethod
    def _apply_workbook_branding(wb: Workbook, template: ReportTemplate, context: Dict):
        """Workbook properties and print header/footer from the template."""
        if context["document_title"]:
            wb.properties.title = context["document_title"]
        if context["document_subtitle"]:
            wb.properties.subject = context["document_subtitle"]
        if context["company_name"]:
            wb.properties.creator = context["company_name"]
        header_footer = template.data["header_footer"]
        # "&" starts a formatting code in an Excel header/footer; "&&" is a literal "&".
        header = substitute(header_footer["header_text"], context).replace("&", "&&")
        footer = substitute(header_footer["footer_text"], context).replace("&", "&&")
        if header or footer:
            for ws in wb.worksheets:
                if header:
                    ws.oddHeader.center.text = header
                if footer:
                    ws.oddFooter.center.text = footer

    @staticmethod
    def _auto_fit_columns(ws, fixed_widths: Optional[Dict[int, float]] = None):
        """Set column widths: template widths first, then the content length."""
        fixed_widths = fixed_widths or {}
        for column in ws.columns:
            max_length = 0
            index = column[0].column
            column_letter = get_column_letter(index)
            if index in fixed_widths:
                ws.column_dimensions[column_letter].width = fixed_widths[index]
                continue
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _create_summary_sheet(
        self,
        wb: Workbook,
        services: Dict[str, List],
        section: Optional[Dict[str, Any]] = None,
        template: Optional[ReportTemplate] = None,
        context: Optional[Dict[str, str]] = None,
    ):
        """Create a summary sheet with service statistics."""
        legacy_call = section is None
        if legacy_call:
            template = default_template("excel")
            section = next(
                s for s in template.sections if s["content_type"] == "service_summary"
            )
        header_color = template.data["branding"]["header_color"]
        if legacy_call:
            ws = wb.create_sheet(section["sheet_name"], 0)
        else:
            ws = wb.create_sheet(section["sheet_name"])

        columns = section["columns"]
        default_headings = {
            "service": "Service",
            "resource_count": "Resource Count",
            "percentage": "Percentage",
        }

        row = 1
        if section.get("show_title") and context:
            if context["document_title"]:
                ws.cell(row=row, column=1, value=context["document_title"]).font = Font(
                    bold=True, size=14
                )
                row += 1
            if context["document_subtitle"]:
                ws.cell(row=row, column=1, value=context["document_subtitle"])
                row += 1
            if row > 1:
                row += 1  # blank row between the title block and the table

        # Headers
        header_font = Font(bold=True)
        header_fill = PatternFill(
            start_color=header_color, end_color=header_color, fill_type="solid"
        )
        for col, column in enumerate(columns, 1):
            cell = ws.cell(
                row=row,
                column=col,
                value=column["heading"] or default_headings[column["field"]],
            )
            cell.font = header_font
            cell.fill = header_fill

        # Calculate totals
        total_resources = sum(len(resources) for resources in services.values())

        def values_for(service, count, percentage_text):
            values = {
                "service": service,
                "resource_count": count,
                "percentage": percentage_text,
            }
            return [values[column["field"]] for column in columns]

        # Add service data
        row += 1
        for service, resources in sorted(services.items()):
            count = len(resources)
            percentage = (count / total_resources * 100) if total_resources > 0 else 0
            for col, value in enumerate(
                values_for(service, count, f"{percentage:.1f}%"), 1
            ):
                ws.cell(row=row, column=col, value=value)
            row += 1

        # Add total row
        for col, value in enumerate(values_for("TOTAL", total_resources, "100.0%"), 1):
            ws.cell(row=row, column=col, value=value).font = Font(bold=True)

        self._auto_fit_columns(
            ws, {i: c["width"] for i, c in enumerate(columns, 1) if c["width"]}
        )

    def _create_service_sheet(
        self,
        wb: Workbook,
        service: str,
        resources: List[Dict],
        section: Optional[Dict[str, Any]] = None,
        template: Optional[ReportTemplate] = None,
    ):
        """Create a sheet of resources (one service, or all resources)."""
        header_color = (
            template.data["branding"]["header_color"] if template else "366092"
        )
        # Sanitize sheet name (Excel has restrictions)
        sheet_name = service[:31]  # Excel sheet names are limited to 31 characters

        ws = wb.create_sheet(sheet_name)
        flattened_rows = [self._flatten_dict(resource) for resource in resources]

        columns = section["columns"] if section else "auto"
        if columns == "auto":
            # Get all unique headers for this sheet, in logical order
            headers = set()
            for flattened in flattened_rows:
                headers.update(flattened.keys())
            fields = self._get_logical_column_order(headers)
            headings = list(fields)
            widths = {}
        else:
            fields = [c["field"] for c in columns]
            headings = [c["heading"] or c["field"] for c in columns]
            widths = {i: c["width"] for i, c in enumerate(columns, 1) if c["width"]}

        # Write headers
        for col, heading in enumerate(headings, 1):
            cell = ws.cell(row=1, column=col, value=heading)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color=header_color, end_color=header_color, fill_type="solid"
            )

        # Write data
        for row, (resource, flattened) in enumerate(zip(resources, flattened_rows), 2):
            for col, field_name in enumerate(fields, 1):
                if field_name in flattened:
                    value = flattened[field_name]
                else:
                    value = self._format_structured_value(resource.get(field_name, ""))
                ws.cell(
                    row=row, column=col, value=str(value) if value is not None else ""
                )

        self._auto_fit_columns(ws, widths)

    @staticmethod
    def _format_structured_value(value: Any) -> Any:
        """Text for a dict or list value that is shown in one cell."""
        if isinstance(value, dict):
            return ", ".join(f"{k}={v}" for k, v in value.items())
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(v) for v in value)
        return value

    def _perform_network_analysis(self):
        """Perform network analysis on VPC and subnet resources."""
        print("Performing network analysis...")

        try:
            from ..discovery import NetworkAnalyzer

            analyzer = NetworkAnalyzer()

            # Extract VPC and subnet resources
            vpc_resources = [
                r
                for r in self.data
                if r.get("service") == "VPC" and r.get("type") in ["VPC", "Subnet"]
            ]

            if vpc_resources:
                self.network_analysis = analyzer.analyze_vpc_resources(vpc_resources)

                # Enrich resources with network analysis data
                for resource in self.data:
                    vpc_id = resource.get("vpc_id")
                    subnet_id = resource.get("subnet_id")

                    if vpc_id and vpc_id in self.network_analysis:
                        vpc_analysis = self.network_analysis[vpc_id]
                        resource["vpc_cidr_block"] = vpc_analysis.cidr_block
                        resource["vpc_utilization"] = (
                            f"{vpc_analysis.utilization_percentage:.1f}%"
                        )
                        resource["vpc_available_ips"] = vpc_analysis.available_ips

                    if subnet_id:
                        # Find subnet analysis in VPC data
                        for vpc_analysis in self.network_analysis.values():
                            for subnet in vpc_analysis.subnets:
                                if subnet.subnet_id == subnet_id:
                                    resource["subnet_cidr_block"] = subnet.cidr_block
                                    resource["subnet_utilization"] = (
                                        f"{subnet.utilization_percentage:.1f}%"
                                    )
                                    resource["subnet_available_ips"] = (
                                        subnet.available_ips
                                    )
                                    resource["subnet_az"] = subnet.availability_zone
                                    break

                print(
                    f"Network analysis completed for {len(vpc_resources)} VPC resources"
                )

        except ImportError:
            print("Warning: NetworkAnalyzer not available, skipping network analysis")
        except Exception as e:
            print(f"Warning: Network analysis failed: {e}")

    def _perform_security_analysis(self):
        """Perform security analysis on security groups and NACLs."""
        print("Performing security analysis...")

        try:
            from ..discovery import SecurityAnalyzer

            analyzer = SecurityAnalyzer()

            # Extract security group resources
            sg_resources = [
                r
                for r in self.data
                if r.get("service") == "VPC" and r.get("type") == "SecurityGroup"
            ]

            if sg_resources:
                self.security_analysis = analyzer.analyze_security_groups(sg_resources)

                # Enrich resources with security analysis data
                for resource in self.data:
                    if (
                        resource.get("service") == "VPC"
                        and resource.get("type") == "SecurityGroup"
                    ):
                        sg_id = resource.get("id")
                        if sg_id and sg_id in self.security_analysis:
                            sg_analysis = self.security_analysis[sg_id]
                            resource["security_risk_level"] = sg_analysis.risk_level
                            resource["inbound_rules_count"] = len(
                                sg_analysis.inbound_rules
                            )
                            resource["outbound_rules_count"] = len(
                                sg_analysis.outbound_rules
                            )
                            resource["associated_resources_count"] = len(
                                sg_analysis.associated_resources
                            )

                            # Check for overly permissive rules
                            permissive_rules = []
                            for rule in sg_analysis.inbound_rules:
                                if "0.0.0.0/0" in rule.source_destination:
                                    permissive_rules.append(
                                        f"{rule.protocol}:{rule.port_range}"
                                    )

                            if permissive_rules:
                                resource["permissive_rules"] = ", ".join(
                                    permissive_rules
                                )
                                resource["has_permissive_rules"] = "Yes"
                            else:
                                resource["has_permissive_rules"] = "No"

                print(
                    f"Security analysis completed for {len(sg_resources)} security groups"
                )

        except ImportError:
            print("Warning: SecurityAnalyzer not available, skipping security analysis")
        except Exception as e:
            print(f"Warning: Security analysis failed: {e}")

    def _enrich_service_attributes(self):
        """Enrich resources with service-specific attributes."""
        print("Enriching service-specific attributes...")

        try:
            from ..discovery import ServiceAttributeEnricher

            enricher = ServiceAttributeEnricher()

            # Enrich resources with service-specific attributes
            enriched_count = 0
            for resource in self.data:
                try:
                    enriched_resources = enricher.enrich_resources_with_attributes(
                        [resource]
                    )
                    if enriched_resources:
                        enriched_resource = enriched_resources[0]
                    if enriched_resource != resource:
                        # Merge service attributes into the main resource
                        service_attrs = enriched_resource.get("service_attributes", {})
                        for key, value in service_attrs.items():
                            if isinstance(value, (str, int, float, bool)):
                                resource[f"service_{key}"] = value
                            elif isinstance(value, list):
                                resource[f"service_{key}"] = ", ".join(
                                    str(v) for v in value
                                )
                            elif isinstance(value, dict):
                                # Flatten nested attributes
                                for nested_key, nested_value in value.items():
                                    if isinstance(
                                        nested_value, (str, int, float, bool)
                                    ):
                                        resource[f"service_{key}_{nested_key}"] = (
                                            nested_value
                                        )

                        enriched_count += 1

                except Exception as e:
                    print(
                        f"Warning: Failed to enrich resource {resource.get('id', 'unknown')}: {e}"
                    )
                    continue

            if enriched_count > 0:
                print(
                    f"Service attribute enrichment completed for {enriched_count} resources"
                )

        except ImportError:
            print(
                "Warning: ServiceAttributeEnricher not available, skipping service enrichment"
            )
        except Exception as e:
            print(f"Warning: Service attribute enrichment failed: {e}")

    def _flatten_dict(
        self, d: Dict[str, Any], parent_key: str = "", sep: str = "."
    ) -> Dict[str, Any]:
        """Flatten a nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to comma-separated strings
                items.append((new_key, ", ".join(str(item) for item in v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _create_network_analysis_sheet(self, wb: Workbook):
        """Create a sheet with network analysis results."""
        ws = wb.create_sheet("Network Analysis")

        # Headers
        headers = [
            "VPC ID",
            "VPC Name",
            "CIDR Block",
            "Total IPs",
            "Available IPs",
            "Utilization %",
            "Subnet Count",
            "Associated Resources",
        ]

        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="366092", end_color="366092", fill_type="solid"
            )

        # Write VPC analysis data
        row = 2
        for vpc_id, analysis in self.network_analysis.items():
            ws.cell(row=row, column=1, value=vpc_id)
            ws.cell(row=row, column=2, value=analysis.vpc_name)
            ws.cell(row=row, column=3, value=analysis.cidr_block)
            ws.cell(row=row, column=4, value=analysis.total_ips)
            ws.cell(row=row, column=5, value=analysis.available_ips)
            ws.cell(row=row, column=6, value=f"{analysis.utilization_percentage:.1f}%")
            ws.cell(row=row, column=7, value=len(analysis.subnets))
            ws.cell(row=row, column=8, value=len(analysis.associated_resources))
            row += 1

        # Add subnet details section
        if any(analysis.subnets for analysis in self.network_analysis.values()):
            # Add separator row
            row += 1
            ws.cell(row=row, column=1, value="SUBNET DETAILS").font = Font(bold=True)
            row += 1

            # Subnet headers
            subnet_headers = [
                "Subnet ID",
                "Subnet Name",
                "VPC ID",
                "CIDR Block",
                "AZ",
                "Total IPs",
                "Available IPs",
                "Utilization %",
                "Associated Resources",
            ]

            for col, header in enumerate(subnet_headers, 1):
                cell = ws.cell(row=row, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(
                    start_color="4F81BD", end_color="4F81BD", fill_type="solid"
                )
            row += 1

            # Write subnet data
            for vpc_analysis in self.network_analysis.values():
                for subnet in vpc_analysis.subnets:
                    ws.cell(row=row, column=1, value=subnet.subnet_id)
                    ws.cell(row=row, column=2, value=subnet.subnet_name)
                    ws.cell(row=row, column=3, value=vpc_analysis.vpc_id)
                    ws.cell(row=row, column=4, value=subnet.cidr_block)
                    ws.cell(row=row, column=5, value=subnet.availability_zone)
                    ws.cell(row=row, column=6, value=subnet.total_ips)
                    ws.cell(row=row, column=7, value=subnet.available_ips)
                    ws.cell(
                        row=row, column=8, value=f"{subnet.utilization_percentage:.1f}%"
                    )
                    ws.cell(row=row, column=9, value=len(subnet.associated_resources))
                    row += 1

        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _create_security_analysis_sheet(self, wb: Workbook):
        """Create a sheet with security analysis results."""
        ws = wb.create_sheet("Security Analysis")

        # Headers
        headers = [
            "Security Group ID",
            "Group Name",
            "VPC ID",
            "Risk Level",
            "Inbound Rules",
            "Outbound Rules",
            "Associated Resources",
            "Has Permissive Rules",
            "Permissive Rule Details",
        ]

        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="366092", end_color="366092", fill_type="solid"
            )

        # Write security group analysis data
        row = 2
        for sg_id, analysis in self.security_analysis.items():
            ws.cell(row=row, column=1, value=sg_id)
            ws.cell(row=row, column=2, value=analysis.group_name)
            ws.cell(row=row, column=3, value=analysis.vpc_id)
            ws.cell(row=row, column=4, value=analysis.risk_level)
            ws.cell(row=row, column=5, value=len(analysis.inbound_rules))
            ws.cell(row=row, column=6, value=len(analysis.outbound_rules))
            ws.cell(row=row, column=7, value=len(analysis.associated_resources))

            # Check for permissive rules
            permissive_rules = []
            for rule in analysis.inbound_rules:
                if "0.0.0.0/0" in rule.source_destination:
                    permissive_rules.append(f"{rule.protocol}:{rule.port_range}")

            has_permissive = "Yes" if permissive_rules else "No"
            ws.cell(row=row, column=8, value=has_permissive)
            ws.cell(row=row, column=9, value=", ".join(permissive_rules))

            # Color code risk levels
            risk_cell = ws.cell(row=row, column=4)
            if analysis.risk_level == "HIGH":
                risk_cell.fill = PatternFill(
                    start_color="FF6B6B", end_color="FF6B6B", fill_type="solid"
                )
            elif analysis.risk_level == "MEDIUM":
                risk_cell.fill = PatternFill(
                    start_color="FFE66D", end_color="FFE66D", fill_type="solid"
                )
            elif analysis.risk_level == "LOW":
                risk_cell.fill = PatternFill(
                    start_color="4ECDC4", end_color="4ECDC4", fill_type="solid"
                )

            row += 1

        # Add detailed rules section
        if self.security_analysis:
            # Add separator row
            row += 1
            ws.cell(row=row, column=1, value="DETAILED SECURITY RULES").font = Font(
                bold=True
            )
            row += 1

            # Rule headers
            rule_headers = [
                "Security Group ID",
                "Rule Type",
                "Protocol",
                "Port Range",
                "Source/Destination",
                "Description",
                "Risk Assessment",
            ]

            for col, header in enumerate(rule_headers, 1):
                cell = ws.cell(row=row, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(
                    start_color="4F81BD", end_color="4F81BD", fill_type="solid"
                )
            row += 1

            # Write detailed rules
            for sg_id, analysis in self.security_analysis.items():
                # Inbound rules
                for rule in analysis.inbound_rules:
                    ws.cell(row=row, column=1, value=sg_id)
                    ws.cell(row=row, column=2, value="Inbound")
                    ws.cell(row=row, column=3, value=rule.protocol)
                    ws.cell(row=row, column=4, value=rule.port_range)
                    ws.cell(row=row, column=5, value=rule.source_destination)
                    ws.cell(row=row, column=6, value=rule.description)
                    ws.cell(row=row, column=7, value=rule.risk_assessment)
                    row += 1

                # Outbound rules
                for rule in analysis.outbound_rules:
                    ws.cell(row=row, column=1, value=sg_id)
                    ws.cell(row=row, column=2, value="Outbound")
                    ws.cell(row=row, column=3, value=rule.protocol)
                    ws.cell(row=row, column=4, value=rule.port_range)
                    ws.cell(row=row, column=5, value=rule.source_destination)
                    ws.cell(row=row, column=6, value=rule.description)
                    ws.cell(row=row, column=7, value=rule.risk_assessment)
                    row += 1

        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _get_logical_column_order(self, headers: set) -> list:
        """
        Return headers in a logical, methodical order instead of alphabetical.
        Order: Core Info -> Account Info -> Location -> Resource Details -> Analysis -> Tags
        """
        # Define the logical ordering categories
        core_columns = ["service", "type", "id", "name", "arn"]

        account_columns = [
            "account_id",
            "source_account_id",
            "source_account_name",
            "account_name",
            "region",
            "availability_zone",
        ]

        resource_details = [
            "status",
            "state",
            "creation_date",
            "created_time",
            "launch_time",
            "size",
            "instance_type",
            "storage_type",
            "engine",
            "engine_version",
            "allocated_storage",
            "storage_encrypted",
            "multi_az",
            "publicly_accessible",
            "vpc_id",
            "vpc_name",
            "subnet_id",
            "subnet_name",
            "security_groups",
            "security_group_ids",
        ]

        network_analysis = [
            "vpc_cidr_block",
            "vpc_total_ips",
            "vpc_utilization_percentage",
            "subnet_cidr_block",
            "subnet_total_ips",
            "subnet_utilization_percentage",
            "subnet_is_public",
            "subnet_availability_zone",
        ]

        security_analysis = [
            "security_risk_level",
            "security_groups",
            "security_group_count",
            "max_security_risk",
            "inbound_rules_count",
            "outbound_rules_count",
            "associated_resources_count",
            "has_permissive_rules",
            "permissive_rules",
        ]

        cost_analysis = [
            "estimated_monthly_cost",
            "cost_breakdown",
            "pricing_model",
            "confidence_level",
            "cost_optimization_opportunities",
        ]

        compliance_tracking = [
            "compliance_status",
            "compliance_score",
            "discovery_timestamp",
            "consolidation_timestamp",
            "total_accounts_in_consolidation",
            "processing_statistics",
        ]

        service_specific = [
            # These will be detected by prefixes
        ]

        # Headers that should come last (tags and custom attributes)
        tag_columns = []
        custom_columns = []

        # Categorize headers
        ordered_headers = []
        remaining_headers = set(headers)

        # 1. Core columns (service, type, id, name, arn)
        for col in core_columns:
            if col in remaining_headers:
                ordered_headers.append(col)
                remaining_headers.remove(col)

        # 2. Account and location columns
        for col in account_columns:
            if col in remaining_headers:
                ordered_headers.append(col)
                remaining_headers.remove(col)

        # 3. Resource details
        for col in resource_details:
            if col in remaining_headers:
                ordered_headers.append(col)
                remaining_headers.remove(col)

        # 4. Network analysis
        for col in network_analysis:
            if col in remaining_headers:
                ordered_headers.append(col)
                remaining_headers.remove(col)

        # 5. Security analysis
        for col in security_analysis:
            if col in remaining_headers:
                ordered_headers.append(col)
                remaining_headers.remove(col)

        # 6. Cost analysis
        for col in cost_analysis:
            if col in remaining_headers:
                ordered_headers.append(col)
                remaining_headers.remove(col)

        # 7. Compliance tracking
        for col in compliance_tracking:
            if col in remaining_headers:
                ordered_headers.append(col)
                remaining_headers.remove(col)

        # 8. Service-specific columns (columns starting with service_)
        service_cols = [col for col in remaining_headers if col.startswith("service_")]
        service_cols.sort()  # Alphabetical within service columns
        ordered_headers.extend(service_cols)
        remaining_headers -= set(service_cols)

        # 9. Other analysis columns (network_, security_, cost_, etc.)
        analysis_prefixes = ["network_", "security_", "cost_", "vpc_", "subnet_"]
        analysis_cols = []
        for col in remaining_headers:
            if any(col.startswith(prefix) for prefix in analysis_prefixes):
                analysis_cols.append(col)
        analysis_cols.sort()
        ordered_headers.extend(analysis_cols)
        remaining_headers -= set(analysis_cols)

        # 10. Tag columns (anything with 'tag' in the name or common tag patterns)
        tag_patterns = ["tag", "tags", "Tag", "Tags"]
        tag_cols = []
        for col in remaining_headers:
            if any(pattern in col for pattern in tag_patterns):
                tag_cols.append(col)
        tag_cols.sort()  # Alphabetical within tags
        remaining_headers -= set(tag_cols)

        # 11. Remaining columns (alphabetically sorted)
        other_cols = sorted(list(remaining_headers))

        # 12. Add tags at the very end
        ordered_headers.extend(other_cols)
        ordered_headers.extend(tag_cols)

        return ordered_headers

    def generate_excel_bom(
        self, bom_data, filename: str, template: Optional[ReportTemplate] = None
    ) -> str:
        """Generate Excel BOM document with provided data."""
        # Handle both BOMData objects and lists
        if hasattr(bom_data, "resources"):
            # It's a BOMData object
            resources = bom_data.resources
        elif isinstance(bom_data, list):
            # It's a list of resources
            resources = bom_data
        else:
            # Try to iterate over it
            resources = list(bom_data)

        # Load the data first
        self.data = resources
        self.headers = set()
        for item in resources:
            if isinstance(item, dict):
                self.headers.update(item.keys())

        # The analysis sheets need the analysis results. load_data() computes
        # them for the legacy script; this path did not, so the sheets were
        # never written from the CLI.
        if self.analyze_network and not self.network_analysis:
            self._perform_network_analysis()
        if self.analyze_security and not self.security_analysis:
            self._perform_security_analysis()

        self.export_to_excel(filename, template=template)
        return filename

    def generate_csv_bom(self, bom_data, filename: str) -> str:
        """Generate a CSV BOM (one row per resource) with provided data."""
        if hasattr(bom_data, "resources"):
            resources = bom_data.resources
        elif isinstance(bom_data, list):
            resources = bom_data
        else:
            resources = list(bom_data)

        self.data = resources
        self.headers = set()
        for item in resources:
            if isinstance(item, dict):
                self.headers.update(item.keys())

        self.export_to_csv(filename)
        return filename

    def generate_word_bom(
        self, bom_data, filename: str, template: Optional[ReportTemplate] = None
    ) -> str:
        """Generate Word BOM document with professional formatting."""
        # Handle both BOMData objects and lists
        if hasattr(bom_data, "resources"):
            # It's a BOMData object
            resources = bom_data.resources
        elif isinstance(bom_data, list):
            # It's a list of resources
            resources = bom_data
        else:
            # Try to iterate over it
            resources = list(bom_data)

        # Load the data first
        self.data = resources
        self.headers = set()
        for item in resources:
            if isinstance(item, dict):
                self.headers.update(item.keys())

        # Generate the Word document using our existing method
        self.export_to_word(filename, template=template)
        return filename

    def export_to_word(self, filename: str, template: Optional[ReportTemplate] = None):
        """Export data to Word format.

        ``template`` selects the sections, their order, the columns and the
        header and footer. Without a template the built-in default applies.
        """
        if not PYTHON_DOCX_AVAILABLE:
            print(
                "Error: python-docx library not available. Please install it to export to Word."
            )
            print("Run: pip install python-docx")
            return

        if not self.data:
            print("No data to export")
            return

        template = self._resolve_template(template, "word")
        context = build_context(template, self.data)

        # Group resources by service (sorted, so repeated runs match)
        services = _group_by_service(self.data)

        # Create Word document
        doc = Document()

        for section in template.sections:
            if section.get("page_break_before"):
                doc.add_page_break()
            content_type = section["content_type"]
            if content_type == "title":
                self._add_word_title(doc, template, context)
            elif content_type == "text":
                if section["title"]:
                    doc.add_heading(
                        substitute(section["title"], context), level=section["level"]
                    )
                for paragraph in section["paragraphs"]:
                    doc.add_paragraph(substitute(paragraph, context))
            elif content_type == "service_summary":
                self._add_word_service_summary(doc, section, services, context)
            elif content_type == "resources":
                self._add_word_resources(doc, section, services, context)

        self._apply_word_header_footer(doc, template, context)

        # Save the document (owner-only file)
        precreate_private(filename)
        doc.save(filename)
        print(f"Word document saved: {filename}")

    @staticmethod
    def _add_word_title(doc, template: ReportTemplate, context: Dict[str, str]):
        """Logo, title and subtitle."""
        if template.logo_file is not None:
            doc.add_picture(
                str(template.logo_file),
                width=Inches(template.data["branding"]["logo_width_inches"]),
            )
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        title = doc.add_heading(context["document_title"], 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if context["document_subtitle"]:
            subtitle = doc.add_paragraph(context["document_subtitle"], style="Subtitle")
            subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    @staticmethod
    def _set_word_column_widths(table, columns):
        """Apply the template column widths (inches) to a table."""
        if not any(column.get("width") for column in columns):
            return
        table.autofit = False
        for index, column in enumerate(columns):
            if column.get("width"):
                width = Inches(column["width"])
                for cell in table.columns[index].cells:
                    cell.width = width

    def _add_word_service_summary(self, doc, section, services, context):
        """Heading and one table row for each service."""
        if section["title"]:
            doc.add_heading(
                substitute(section["title"], context), level=section["level"]
            )
        columns = section["columns"]
        default_headings = {
            "service": "Service",
            "resource_count": "Resource Count",
            "percentage": "Percentage",
        }
        table = doc.add_table(rows=1, cols=len(columns))
        table.style = section["table_style"]
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Add headers
        hdr_cells = table.rows[0].cells
        for i, column in enumerate(columns):
            hdr_cells[i].text = column["heading"] or default_headings[column["field"]]

        # Add service data
        total_resources = sum(len(resources) for resources in services.values())
        for service, resources in sorted(services.items()):
            count = len(resources)
            percentage = (count / total_resources * 100) if total_resources > 0 else 0
            values = {
                "service": service,
                "resource_count": str(count),
                "percentage": f"{percentage:.1f}%",
            }
            row_cells = table.add_row().cells
            for i, column in enumerate(columns):
                row_cells[i].text = values[column["field"]]
        self._set_word_column_widths(table, columns)

    def _auto_word_columns(self, resources: List[Dict], max_cols: int) -> List[str]:
        """The most important fields of a service, for a narrow Word table."""
        service_headers = set()
        for resource in resources:
            service_headers.update(resource.keys())

        # Filter and order headers logically
        ordered_headers = self._get_logical_column_order(service_headers)

        # Limit to most important columns for Word format (to avoid very wide tables)
        important_headers = []
        priority_headers = [
            "name",
            "id",
            "type",
            "region",
            "compliance_status",
            "tags",
        ]

        for header in priority_headers:
            if header in ordered_headers and len(important_headers) < max_cols:
                important_headers.append(header)

        # Add other important headers up to the maximum number of columns
        for header in ordered_headers:
            if len(important_headers) >= max_cols:
                break
            if header not in important_headers and header not in [
                "arn",
                "account_id",
                "source_account_id",
            ]:
                important_headers.append(header)
        return important_headers

    @staticmethod
    def _format_word_value(header: str, value: Any) -> str:
        """Cell text for a Word table: long structured values are shortened."""
        if isinstance(value, dict):
            if header == "tags" and value:
                # Format tags nicely
                tag_str = ", ".join([f"{k}={v}" for k, v in value.items()])
                return tag_str[:100] + ("..." if len(tag_str) > 100 else "")
            return str(value)[:50] + ("..." if len(str(value)) > 50 else "")
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)[:100] + (
                "..." if len(str(value)) > 100 else ""
            )
        return str(value)

    def _add_word_resources(self, doc, section, services, context):
        """Heading, then one heading and one table for each service."""
        if section["title"]:
            doc.add_heading(
                substitute(section["title"], context), level=section["level"]
            )

        if section.get("services"):
            selected = self._select_services(services, section["services"])
        else:
            selected = sorted(services.items())

        max_resources = section["max_rows"]
        for service, resources in selected:
            if not resources:
                continue
            shown = resources[:max_resources]
            service_context = dict(context)
            service_context.update(
                {
                    "service": str(service),
                    "service_resource_count": str(len(resources)),
                    "shown_resource_count": str(len(shown)),
                }
            )

            # Service section
            doc.add_heading(
                substitute(section["service_title"], service_context),
                level=section["level"] + 1,
            )

            if section["columns"] == "auto":
                columns = [
                    {
                        "field": header,
                        "heading": header.replace("_", " ").title(),
                        "width": None,
                    }
                    for header in self._auto_word_columns(
                        resources, section["max_columns"]
                    )
                ]
            else:
                columns = [
                    {
                        "field": c["field"],
                        "heading": c["heading"] or c["field"].replace("_", " ").title(),
                        "width": c["width"],
                    }
                    for c in section["columns"]
                ]

            if columns:
                # Create service resource table
                resource_table = doc.add_table(rows=1, cols=len(columns))
                resource_table.style = section["table_style"]

                # Add headers
                hdr_cells = resource_table.rows[0].cells
                for i, column in enumerate(columns):
                    hdr_cells[i].text = column["heading"]

                # Add resource data (limited to max_rows resources per service)
                for resource in shown:
                    row_cells = resource_table.add_row().cells
                    flattened = None
                    for i, column in enumerate(columns):
                        header = column["field"]
                        if header in resource:
                            value = resource[header]
                        elif "." in header:
                            if flattened is None:
                                flattened = self._flatten_dict(resource)
                            value = flattened.get(header, "")
                        else:
                            value = ""
                        row_cells[i].text = self._format_word_value(header, value)
                self._set_word_column_widths(resource_table, columns)

                if len(resources) > max_resources and section["truncation_note"]:
                    doc.add_paragraph(
                        substitute(section["truncation_note"], service_context)
                    )

            if section["page_break_after_service"]:
                doc.add_page_break()

    @staticmethod
    def _apply_word_header_footer(
        doc, template: ReportTemplate, context: Dict[str, str]
    ):
        """Page header, page footer and the optional page number field."""
        header_footer = template.data["header_footer"]
        header = substitute(header_footer["header_text"], context)
        footer = substitute(header_footer["footer_text"], context)
        page_numbers = header_footer["include_page_numbers"]
        if not (header or footer or page_numbers):
            return
        word_section = doc.sections[0]
        if header:
            word_section.header.paragraphs[0].text = header
        if footer or page_numbers:
            paragraph = word_section.footer.paragraphs[0]
            paragraph.text = footer
            if page_numbers:
                from docx.oxml import OxmlElement
                from docx.oxml.ns import qn

                paragraph.add_run("  Page " if footer else "Page ")
                field = OxmlElement("w:fldSimple")
                field.set(qn("w:instr"), "PAGE")
                paragraph._p.append(field)
