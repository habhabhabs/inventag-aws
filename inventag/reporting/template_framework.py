#!/usr/bin/env python3
"""
Document Template Framework

Comprehensive document template system with company logo integration,
customizable document structure, and automatic table of contents generation.

Features:
- Document template system with company logo integration
- Customizable document structure with markdown-like header definitions
- Table of contents generation with automatic page/section references
- Custom header and footer templates with company branding
- Template variables for company name, document title, generation date
"""

import logging
import os
import json
import yaml
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from abc import ABC, abstractmethod
import re
from collections import OrderedDict

from .document_generator import BrandingConfig


@dataclass
class TemplateVariable:
    """Template variable definition."""
    name: str
    value: Any
    description: str = ""
    format_type: str = "string"  # string, date, number, boolean
    default_value: Any = None


@dataclass
class DocumentSection:
    """Document section definition."""
    id: str
    title: str
    level: int = 1  # Heading level (1-6)
    content_type: str = "text"  # text, table, chart, image
    template: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    subsections: List['DocumentSection'] = field(default_factory=list)
    include_in_toc: bool = True
    page_break_before: bool = False
    page_break_after: bool = False


@dataclass
class HeaderFooterTemplate:
    """Header and footer template configuration."""
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    include_logo: bool = False
    logo_position: str = "left"  # left, center, right
    logo_size: Tuple[float, float] = (1.0, 0.5)  # width, height in inches
    include_page_numbers: bool = True
    page_number_position: str = "right"  # left, center, right
    include_date: bool = True
    date_format: str = "%Y-%m-%d"
    custom_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class TableOfContentsConfig:
    """Table of contents configuration."""
    enabled: bool = True
    title: str = "Table of Contents"
    max_depth: int = 3
    include_page_numbers: bool = True
    dot_leader: bool = True
    custom_styles: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentTemplate:
    """Comprehensive document template definition."""
    name: str
    description: str = ""
    format_type: str = "word"  # word, excel, pdf
    template_version: str = "1.0"
    
    # Document structure
    sections: List[DocumentSection] = field(default_factory=list)
    variables: Dict[str, TemplateVariable] = field(default_factory=dict)
    
    # Layout and styling
    branding: Optional[BrandingConfig] = None
    header_footer: Optional[HeaderFooterTemplate] = None
    table_of_contents: Optional[TableOfContentsConfig] = None
    
    # Page layout
    page_margins: Dict[str, float] = field(default_factory=lambda: {
        "top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0
    })
    page_orientation: str = "portrait"  # portrait, landscape
    page_size: str = "letter"  # letter, a4, legal
    
    # Template metadata
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    template_path: Optional[str] = None


class TemplateVariableResolver:
    """Resolves template variables with values."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.TemplateVariableResolver")
        self._built_in_variables = self._initialize_built_in_variables()
        
    def _initialize_built_in_variables(self) -> Dict[str, TemplateVariable]:
        """Initialize built-in template variables."""
        return {
            "current_date": TemplateVariable(
                name="current_date",
                value=datetime.now().strftime("%Y-%m-%d"),
                description="Current date in YYYY-MM-DD format",
                format_type="date"
            ),
            "current_datetime": TemplateVariable(
                name="current_datetime", 
                value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                description="Current date and time",
                format_type="date"
            ),
            "current_year": TemplateVariable(
                name="current_year",
                value=datetime.now().year,
                description="Current year",
                format_type="number"
            ),
            "generation_timestamp": TemplateVariable(
                name="generation_timestamp",
                value=datetime.now(timezone.utc).isoformat(),
                description="Document generation timestamp in ISO format",
                format_type="date"
            )
        }
        
    def resolve_variables(
        self, 
        template: DocumentTemplate, 
        context_variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resolve all template variables with actual values."""
        resolved = {}
        
        # Start with built-in variables
        for name, var in self._built_in_variables.items():
            resolved[name] = var.value
            
        # Add template-defined variables
        for name, var in template.variables.items():
            resolved[name] = var.value if var.value is not None else var.default_value
            
        # Override with context variables
        if context_variables:
            resolved.update(context_variables)
            
        self.logger.debug(f"Resolved {len(resolved)} template variables")
        return resolved
        
    def substitute_text(self, text: str, variables: Dict[str, Any]) -> str:
        """Substitute template variables in text using {{variable}} syntax."""
        if not text:
            return text
            
        # Pattern to match {{variable_name}} or {{variable_name|format}}
        pattern = r'\{\{([^}|]+)(?:\|([^}]+))?\}\}'
        
        def replace_variable(match):
            var_name = match.group(1).strip()
            format_spec = match.group(2).strip() if match.group(2) else None
            
            if var_name in variables:
                value = variables[var_name]
                
                # Apply formatting if specified
                if format_spec and value is not None:
                    try:
                        if format_spec.startswith('date:'):
                            date_format = format_spec[5:]
                            if isinstance(value, datetime):
                                return value.strftime(date_format)
                            elif isinstance(value, str):
                                # Try to parse as ISO date
                                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                return dt.strftime(date_format)
                        elif format_spec.startswith('number:'):
                            number_format = format_spec[7:]
                            return f"{float(value):{number_format}}"
                        elif format_spec == 'upper':
                            return str(value).upper()
                        elif format_spec == 'lower':
                            return str(value).lower()
                        elif format_spec == 'title':
                            return str(value).title()
                    except Exception as e:
                        self.logger.warning(f"Failed to format variable {var_name}: {e}")
                        
                return str(value) if value is not None else ""
            else:
                self.logger.warning(f"Template variable not found: {var_name}")
                return match.group(0)  # Return original if not found
                
        return re.sub(pattern, replace_variable, text)


class DocumentStructureBuilder:
    """Builds document structure from template definition."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DocumentStructureBuilder")
        
    def build_structure(
        self, 
        template: DocumentTemplate,
        context_data: Optional[Dict[str, Any]] = None
    ) -> List[DocumentSection]:
        """Build complete document structure from template."""
        self.logger.info(f"Building document structure for template: {template.name}")
        
        structure = []
        
        # Process each section in the template
        for section in template.sections:
            built_section = self._build_section(section, template, context_data)
            structure.append(built_section)
            
        self.logger.info(f"Built document structure with {len(structure)} sections")
        return structure
        
    def _build_section(
        self, 
        section: DocumentSection, 
        template: DocumentTemplate,
        context_data: Optional[Dict[str, Any]] = None
    ) -> DocumentSection:
        """Build a single document section."""
        # Create a copy of the section
        built_section = DocumentSection(
            id=section.id,
            title=section.title,
            level=section.level,
            content_type=section.content_type,
            template=section.template,
            variables=section.variables.copy(),
            include_in_toc=section.include_in_toc,
            page_break_before=section.page_break_before,
            page_break_after=section.page_break_after
        )
        
        # Build subsections recursively
        for subsection in section.subsections:
            built_subsection = self._build_section(subsection, template, context_data)
            built_section.subsections.append(built_subsection)
            
        return built_section
        
    def generate_table_of_contents(
        self, 
        sections: List[DocumentSection],
        config: Optional[TableOfContentsConfig] = None
    ) -> List[Dict[str, Any]]:
        """Generate table of contents from document sections."""
        if not config or not config.enabled:
            return []
            
        toc_entries = []
        
        def process_section(section: DocumentSection, level: int = 1):
            if section.include_in_toc and level <= config.max_depth:
                toc_entries.append({
                    "id": section.id,
                    "title": section.title,
                    "level": level,
                    "page_number": None  # Will be filled during document generation
                })
                
            # Process subsections
            for subsection in section.subsections:
                process_section(subsection, level + 1)
                
        for section in sections:
            process_section(section)
            
        self.logger.info(f"Generated table of contents with {len(toc_entries)} entries")
        return toc_entries


class TemplateLoader:
    """Loads document templates from various sources."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.TemplateLoader")
        
    def load_from_file(self, template_path: str) -> DocumentTemplate:
        """Load template from JSON or YAML file."""
        self.logger.info(f"Loading template from: {template_path}")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                if template_path.endswith('.json'):
                    template_data = json.load(f)
                elif template_path.endswith(('.yaml', '.yml')):
                    template_data = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported template format: {template_path}")
                    
            template = self._parse_template_data(template_data)
            template.template_path = template_path
            
            self.logger.info(f"Successfully loaded template: {template.name}")
            return template
            
        except Exception as e:
            self.logger.error(f"Failed to load template from {template_path}: {e}")
            raise
            
    def load_from_dict(self, template_data: Dict[str, Any]) -> DocumentTemplate:
        """Load template from dictionary data."""
        return self._parse_template_data(template_data)
        
    def _parse_template_data(self, data: Dict[str, Any]) -> DocumentTemplate:
        """Parse template data into DocumentTemplate object."""
        # Parse basic template info
        template = DocumentTemplate(
            name=data.get("name", "Untitled Template"),
            description=data.get("description", ""),
            format_type=data.get("format_type", "word"),
            template_version=data.get("template_version", "1.0")
        )
        
        # Parse variables
        variables_data = data.get("variables", {})
        for name, var_data in variables_data.items():
            if isinstance(var_data, dict):
                template.variables[name] = TemplateVariable(
                    name=name,
                    value=var_data.get("value"),
                    description=var_data.get("description", ""),
                    format_type=var_data.get("format_type", "string"),
                    default_value=var_data.get("default_value")
                )
            else:
                # Simple value
                template.variables[name] = TemplateVariable(
                    name=name,
                    value=var_data,
                    format_type="string"
                )
                
        # Parse sections
        sections_data = data.get("sections", [])
        template.sections = self._parse_sections(sections_data)
        
        # Parse branding
        branding_data = data.get("branding")
        if branding_data:
            template.branding = BrandingConfig(
                company_name=branding_data.get("company_name", "Organization"),
                logo_path=branding_data.get("logo_path"),
                header_text=branding_data.get("header_text"),
                footer_text=branding_data.get("footer_text"),
                color_scheme=branding_data.get("color_scheme", {}),
                font_family=branding_data.get("font_family", "Calibri"),
                font_size=branding_data.get("font_size", 11),
                enable_watermark=branding_data.get("enable_watermark", False),
                watermark_text=branding_data.get("watermark_text", "CONFIDENTIAL")
            )
            
        # Parse header/footer
        header_footer_data = data.get("header_footer")
        if header_footer_data:
            template.header_footer = HeaderFooterTemplate(
                header_text=header_footer_data.get("header_text"),
                footer_text=header_footer_data.get("footer_text"),
                include_logo=header_footer_data.get("include_logo", False),
                logo_position=header_footer_data.get("logo_position", "left"),
                logo_size=tuple(header_footer_data.get("logo_size", [1.0, 0.5])),
                include_page_numbers=header_footer_data.get("include_page_numbers", True),
                page_number_position=header_footer_data.get("page_number_position", "right"),
                include_date=header_footer_data.get("include_date", True),
                date_format=header_footer_data.get("date_format", "%Y-%m-%d"),
                custom_fields=header_footer_data.get("custom_fields", {})
            )
            
        # Parse table of contents
        toc_data = data.get("table_of_contents")
        if toc_data:
            template.table_of_contents = TableOfContentsConfig(
                enabled=toc_data.get("enabled", True),
                title=toc_data.get("title", "Table of Contents"),
                max_depth=toc_data.get("max_depth", 3),
                include_page_numbers=toc_data.get("include_page_numbers", True),
                dot_leader=toc_data.get("dot_leader", True),
                custom_styles=toc_data.get("custom_styles", {})
            )
            
        # Parse page layout
        template.page_margins = data.get("page_margins", {
            "top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0
        })
        template.page_orientation = data.get("page_orientation", "portrait")
        template.page_size = data.get("page_size", "letter")
        
        return template
        
    def _parse_sections(self, sections_data: List[Dict[str, Any]]) -> List[DocumentSection]:
        """Parse sections data into DocumentSection objects."""
        sections = []
        
        for section_data in sections_data:
            section = DocumentSection(
                id=section_data.get("id", ""),
                title=section_data.get("title", ""),
                level=section_data.get("level", 1),
                content_type=section_data.get("content_type", "text"),
                template=section_data.get("template"),
                variables=section_data.get("variables", {}),
                include_in_toc=section_data.get("include_in_toc", True),
                page_break_before=section_data.get("page_break_before", False),
                page_break_after=section_data.get("page_break_after", False)
            )
            
            # Parse subsections recursively
            subsections_data = section_data.get("subsections", [])
            section.subsections = self._parse_sections(subsections_data)
            
            sections.append(section)
            
        return sections


class TemplateManager:
    """Manages document templates and provides template operations."""
    
    def __init__(self, template_directory: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.TemplateManager")
        self.template_directory = template_directory or "templates"
        self.loader = TemplateLoader()
        self.variable_resolver = TemplateVariableResolver()
        self.structure_builder = DocumentStructureBuilder()
        
        # Template cache
        self._template_cache: Dict[str, DocumentTemplate] = {}
        
    def load_template(self, template_name: str) -> DocumentTemplate:
        """Load template by name."""
        if template_name in self._template_cache:
            return self._template_cache[template_name]
            
        # Try to find template file
        template_path = self._find_template_file(template_name)
        if not template_path:
            raise FileNotFoundError(f"Template not found: {template_name}")
            
        template = self.loader.load_from_file(template_path)
        self._template_cache[template_name] = template
        
        return template
        
    def _find_template_file(self, template_name: str) -> Optional[str]:
        """Find template file by name."""
        template_dir = Path(self.template_directory)
        
        # Try different extensions
        for ext in ['.json', '.yaml', '.yml']:
            template_path = template_dir / f"{template_name}{ext}"
            if template_path.exists():
                return str(template_path)
                
        return None
        
    def create_default_template(self, format_type: str = "word") -> DocumentTemplate:
        """Create a default template for the specified format."""
        self.logger.info(f"Creating default template for format: {format_type}")
        
        template = DocumentTemplate(
            name=f"Default {format_type.title()} Template",
            description=f"Default template for {format_type} documents",
            format_type=format_type,
            template_version="1.0"
        )
        
        # Add default variables
        template.variables = {
            "company_name": TemplateVariable(
                name="company_name",
                value="{{company_name}}",
                description="Company name",
                default_value="Organization"
            ),
            "document_title": TemplateVariable(
                name="document_title", 
                value="{{document_title}}",
                description="Document title",
                default_value="Cloud Bill of Materials Report"
            ),
            "report_date": TemplateVariable(
                name="report_date",
                value="{{current_date}}",
                description="Report generation date",
                format_type="date"
            )
        }
        
        # Add default sections
        template.sections = [
            DocumentSection(
                id="title_page",
                title="Title Page",
                level=0,
                content_type="title",
                include_in_toc=False,
                page_break_after=True
            ),
            DocumentSection(
                id="table_of_contents",
                title="Table of Contents",
                level=0,
                content_type="toc",
                include_in_toc=False,
                page_break_after=True
            ),
            DocumentSection(
                id="executive_summary",
                title="Executive Summary",
                level=1,
                content_type="text",
                include_in_toc=True
            ),
            DocumentSection(
                id="service_resources",
                title="Service Resources",
                level=1,
                content_type="table",
                include_in_toc=True
            ),
            DocumentSection(
                id="network_analysis",
                title="Network Analysis",
                level=1,
                content_type="text",
                include_in_toc=True,
                page_break_before=True
            ),
            DocumentSection(
                id="security_analysis",
                title="Security Analysis", 
                level=1,
                content_type="text",
                include_in_toc=True,
                page_break_before=True
            ),
            DocumentSection(
                id="compliance_details",
                title="Compliance Details",
                level=1,
                content_type="table",
                include_in_toc=True,
                page_break_before=True
            )
        ]
        
        # Add default branding
        template.branding = BrandingConfig()
        
        # Add default header/footer
        template.header_footer = HeaderFooterTemplate(
            header_text="{{company_name}} - {{document_title}}",
            footer_text="Generated on {{current_date}}",
            include_logo=True,
            include_page_numbers=True,
            include_date=True
        )
        
        # Add default table of contents
        template.table_of_contents = TableOfContentsConfig(
            enabled=True,
            title="Table of Contents",
            max_depth=3
        )
        
        return template
        
    def save_template(self, template: DocumentTemplate, output_path: str):
        """Save template to file."""
        self.logger.info(f"Saving template to: {output_path}")
        
        try:
            # Convert template to dictionary
            template_data = self._template_to_dict(template)
            
            # Save based on file extension
            with open(output_path, 'w', encoding='utf-8') as f:
                if output_path.endswith('.json'):
                    json.dump(template_data, f, indent=2, ensure_ascii=False, default=str)
                elif output_path.endswith(('.yaml', '.yml')):
                    yaml.dump(template_data, f, default_flow_style=False, allow_unicode=True)
                else:
                    raise ValueError(f"Unsupported output format: {output_path}")
                    
            self.logger.info(f"Template saved successfully: {output_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save template: {e}")
            raise
            
    def _template_to_dict(self, template: DocumentTemplate) -> Dict[str, Any]:
        """Convert DocumentTemplate to dictionary."""
        data = {
            "name": template.name,
            "description": template.description,
            "format_type": template.format_type,
            "template_version": template.template_version,
            "variables": {},
            "sections": [],
            "page_margins": template.page_margins,
            "page_orientation": template.page_orientation,
            "page_size": template.page_size
        }
        
        # Convert variables
        for name, var in template.variables.items():
            data["variables"][name] = {
                "value": var.value,
                "description": var.description,
                "format_type": var.format_type,
                "default_value": var.default_value
            }
            
        # Convert sections
        data["sections"] = self._sections_to_dict(template.sections)
        
        # Convert branding
        if template.branding:
            data["branding"] = {
                "company_name": template.branding.company_name,
                "logo_path": template.branding.logo_path,
                "header_text": template.branding.header_text,
                "footer_text": template.branding.footer_text,
                "color_scheme": template.branding.color_scheme,
                "font_family": template.branding.font_family,
                "font_size": template.branding.font_size,
                "enable_watermark": template.branding.enable_watermark,
                "watermark_text": template.branding.watermark_text
            }
            
        # Convert header/footer
        if template.header_footer:
            data["header_footer"] = {
                "header_text": template.header_footer.header_text,
                "footer_text": template.header_footer.footer_text,
                "include_logo": template.header_footer.include_logo,
                "logo_position": template.header_footer.logo_position,
                "logo_size": list(template.header_footer.logo_size),
                "include_page_numbers": template.header_footer.include_page_numbers,
                "page_number_position": template.header_footer.page_number_position,
                "include_date": template.header_footer.include_date,
                "date_format": template.header_footer.date_format,
                "custom_fields": template.header_footer.custom_fields
            }
            
        # Convert table of contents
        if template.table_of_contents:
            data["table_of_contents"] = {
                "enabled": template.table_of_contents.enabled,
                "title": template.table_of_contents.title,
                "max_depth": template.table_of_contents.max_depth,
                "include_page_numbers": template.table_of_contents.include_page_numbers,
                "dot_leader": template.table_of_contents.dot_leader,
                "custom_styles": template.table_of_contents.custom_styles
            }
            
        return data
        
    def _sections_to_dict(self, sections: List[DocumentSection]) -> List[Dict[str, Any]]:
        """Convert sections to dictionary format."""
        sections_data = []
        
        for section in sections:
            section_data = {
                "id": section.id,
                "title": section.title,
                "level": section.level,
                "content_type": section.content_type,
                "template": section.template,
                "variables": section.variables,
                "include_in_toc": section.include_in_toc,
                "page_break_before": section.page_break_before,
                "page_break_after": section.page_break_after
            }
            
            # Add subsections recursively
            if section.subsections:
                section_data["subsections"] = self._sections_to_dict(section.subsections)
                
            sections_data.append(section_data)
            
        return sections_data
        
    def list_available_templates(self) -> List[str]:
        """List all available templates in the template directory."""
        template_dir = Path(self.template_directory)
        
        if not template_dir.exists():
            return []
            
        templates = []
        for file_path in template_dir.glob("*"):
            if file_path.suffix in ['.json', '.yaml', '.yml']:
                templates.append(file_path.stem)
                
        return sorted(templates)
        
    def validate_template(self, template: DocumentTemplate) -> List[str]:
        """Validate template structure and return list of issues."""
        issues = []
        
        # Check required fields
        if not template.name:
            issues.append("Template name is required")
            
        if not template.format_type:
            issues.append("Template format_type is required")
            
        # Validate sections
        if not template.sections:
            issues.append("Template must have at least one section")
        else:
            section_ids = set()
            for section in template.sections:
                if not section.id:
                    issues.append("All sections must have an ID")
                elif section.id in section_ids:
                    issues.append(f"Duplicate section ID: {section.id}")
                else:
                    section_ids.add(section.id)
                    
                if not section.title:
                    issues.append(f"Section {section.id} must have a title")
                    
        # Validate variables
        for name, var in template.variables.items():
            if not var.name:
                issues.append(f"Variable {name} must have a name")
                
        return issues


# Factory function for easy template manager creation
def create_template_manager(template_directory: Optional[str] = None) -> TemplateManager:
    """Create a TemplateManager with the specified template directory."""
    return TemplateManager(template_directory)