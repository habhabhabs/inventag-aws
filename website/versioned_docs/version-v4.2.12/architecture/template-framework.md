---
title: Template Framework
description: Document generation system and template architecture
sidebar_position: 3
---

# InvenTag Template Framework

## Overview

The InvenTag Template Framework provides a comprehensive document template system with company logo integration, customizable document structure, and automatic table of contents generation. This enterprise-grade system enables professional document customization for Cloud Bill of Materials (BOM) reports.

## 🎯 Key Features

- **Document Template System**: Complete template definitions with sections, variables, and layout
- **Variable Substitution**: Dynamic content with `{{variable}}` syntax and formatting options
- **Table of Contents**: Automatic generation with page/section references
- **Header/Footer Templates**: Custom branding with logo placement
- **Multi-Format Support**: Templates for Word, Excel, and other document formats
- **Configuration Management**: YAML/JSON template loading with validation
- **Branding Integration**: Seamless integration with the advanced branding system

## 📁 Core Components

### DocumentTemplate
Complete template definition with all customization options:

```python
from inventag.reporting.template_framework import DocumentTemplate, DocumentSection

template = DocumentTemplate(
    name="Professional BOM Report",
    description="Enterprise BOM report template",
    format_type="word",
    template_version="1.0"
)
```

### TemplateVariableResolver
Resolves template variables with values and formatting:

```python
from inventag.reporting.template_framework import TemplateVariableResolver

resolver = TemplateVariableResolver()
variables = resolver.resolve_variables(template, {
    "company_name": "Acme Corporation",
    "document_title": "Cloud Infrastructure BOM"
})

# Substitute variables in text
formatted_text = resolver.substitute_text(
    "{{company_name}} - {{document_title}} ({{current_date|date:%B %Y}})",
    variables
)
```

### DocumentStructureBuilder
Builds document structure from template definitions:

```python
from inventag.reporting.template_framework import DocumentStructureBuilder

builder = DocumentStructureBuilder()
structure = builder.build_structure(template, context_data)
toc_entries = builder.generate_table_of_contents(structure, toc_config)
```

### TemplateManager
Central management for templates with caching and validation:

```python
from inventag.reporting.template_framework import create_template_manager

# Create template manager
template_manager = create_template_manager("templates")

# Load template
template = template_manager.load_template("professional_word")

# Create default template
default_template = template_manager.create_default_template("word")

# List available templates
templates = template_manager.list_available_templates()
```

## 🔧 Template Variables

### Built-in Variables

The framework provides several built-in variables:

- `current_date`: Current date in YYYY-MM-DD format
- `current_datetime`: Current date and time
- `current_year`: Current year
- `generation_timestamp`: Document generation timestamp in ISO format

### Custom Variables

Define custom variables with type validation:

```python
from inventag.reporting.template_framework import TemplateVariable

template.variables = {
    "company_name": TemplateVariable(
        name="company_name",
        value="Acme Corporation",
        description="Company name",
        format_type="string",
        default_value="Organization"
    ),
    "report_date": TemplateVariable(
        name="report_date",
        value="{{current_date}}",
        description="Report generation date",
        format_type="date"
    )
}
```

### Variable Formatting

Variables support formatting options:

```python
# Date formatting
"{{current_date|date:%B %d, %Y}}"  # January 15, 2024

# Number formatting
"{{compliance_score|number:.1f}}%"  # 95.5%

# Text formatting
"{{company_name|upper}}"  # ACME CORPORATION
"{{document_title|title}}"  # Cloud Infrastructure Bom
```

## 📄 Document Structure

### Document Sections

Define document structure with hierarchical sections:

```python
from inventag.reporting.template_framework import DocumentSection

sections = [
    DocumentSection(
        id="title_page",
        title="Title Page",
        level=0,
        content_type="title",
        include_in_toc=False,
        page_break_after=True
    ),
    DocumentSection(
        id="executive_summary",
        title="Executive Summary",
        level=1,
        content_type="text",
        include_in_toc=True,
        variables={"summary_type": "executive"}
    ),
    DocumentSection(
        id="service_resources",
        title="Service Resources",
        level=1,
        content_type="table",
        include_in_toc=True,
        subsections=[
            DocumentSection(
                id="ec2_resources",
                title="EC2 Instances",
                level=2,
                content_type="table"
            ),
            DocumentSection(
                id="s3_resources", 
                title="S3 Buckets",
                level=2,
                content_type="table"
            )
        ]
    )
]
```

### Table of Contents Configuration

Configure automatic table of contents generation:

```python
from inventag.reporting.template_framework import TableOfContentsConfig

toc_config = TableOfContentsConfig(
    enabled=True,
    title="Table of Contents",
    max_depth=3,
    include_page_numbers=True,
    dot_leader=True,
    custom_styles={
        "font_size": 12,
        "spacing": 1.15
    }
)
```

## 🎨 Header and Footer Templates

### Header/Footer Configuration

Define custom headers and footers with branding:

```python
from inventag.reporting.template_framework import HeaderFooterTemplate

header_footer = HeaderFooterTemplate(
    header_text="{{company_name}} - {{document_title}}",
    footer_text="Generated on {{current_date}} | Page {page} of {total_pages}",
    include_logo=True,
    logo_position="left",
    logo_size=(1.0, 0.5),  # width, height in inches
    include_page_numbers=True,
    page_number_position="right",
    include_date=True,
    date_format="%Y-%m-%d",
    custom_fields={
        "classification": "CONFIDENTIAL",
        "version": "v1.0"
    }
)
```

## 📋 Template File Formats

### YAML Template Example

```yaml
name: "Professional Word Template"
description: "Enterprise BOM report template for Word documents"
format_type: "word"
template_version: "1.0"

variables:
  company_name:
    value: "{{company_name}}"
    description: "Company name"
    default_value: "Organization"
  document_title:
    value: "{{document_title}}"
    description: "Document title"
    default_value: "Cloud Bill of Materials Report"

sections:
  - id: "title_page"
    title: "Title Page"
    level: 0
    content_type: "title"
    include_in_toc: false
    page_break_after: true
    
  - id: "table_of_contents"
    title: "Table of Contents"
    level: 0
    content_type: "toc"
    include_in_toc: false
    page_break_after: true
    
  - id: "executive_summary"
    title: "Executive Summary"
    level: 1
    content_type: "text"
    include_in_toc: true

branding:
  company_name: "{{company_name}}"
  font_family: "Calibri"
  font_size: 11
  color_scheme:
    primary: "#366092"
    secondary: "#4472C4"

header_footer:
  header_text: "{{company_name}} - {{document_title}}"
  footer_text: "Generated on {{current_date}}"
  include_logo: true
  include_page_numbers: true

table_of_contents:
  enabled: true
  title: "Table of Contents"
  max_depth: 3
  include_page_numbers: true

page_margins:
  top: 1.0
  bottom: 1.0
  left: 1.0
  right: 1.0
page_orientation: "portrait"
page_size: "letter"
```

### JSON Template Example

```json
{
  "name": "Professional Excel Template",
  "description": "Enterprise BOM report template for Excel workbooks",
  "format_type": "excel",
  "template_version": "1.0",
  "variables": {
    "company_name": {
      "value": "{{company_name}}",
      "description": "Company name",
      "default_value": "Organization"
    }
  },
  "sections": [
    {
      "id": "dashboard",
      "title": "Executive Dashboard",
      "level": 1,
      "content_type": "dashboard",
      "variables": {
        "chart_types": ["pie", "bar", "line"]
      }
    },
    {
      "id": "compliance_summary",
      "title": "Compliance Summary",
      "level": 1,
      "content_type": "table"
    }
  ],
  "branding": {
    "company_name": "{{company_name}}",
    "color_scheme": {
      "primary": "#366092",
      "secondary": "#4472C4",
      "success": "#70AD47",
      "warning": "#FFC000",
      "danger": "#C5504B"
    }
  }
}
```

## 🔄 Integration with Document Generation

### Using Templates in Document Generation

```python
from inventag.reporting.document_generator import DocumentGenerator, DocumentConfig
from inventag.reporting.template_framework import create_template_manager
from inventag.reporting.branding_system import create_branding_theme_manager

# Create managers
template_manager = create_template_manager("templates")
branding_manager = create_branding_theme_manager()

# Load template and theme
template = template_manager.load_template("professional_word")
branding_theme = branding_manager.get_theme("professional_blue")

# Configure document generation
config = DocumentConfig(
    output_formats=["word"],
    template=template,
    branding_theme=branding_theme,
    template_variables={
        "company_name": "Acme Corporation",
        "document_title": "Cloud Infrastructure BOM",
        "classification": "CONFIDENTIAL"
    }
)

# Generate document
generator = DocumentGenerator(config)
result = generator.generate_bom_documents(bom_data, ["word"])
```

### Template-Driven Word Document Generation

```python
from inventag.reporting.word_builder import WordDocumentBuilder

# Create Word builder with template
builder = WordDocumentBuilder(
    template=template,
    branding_config=branding_theme,
    output_path="reports/bom_report.docx"
)

# Generate document using template structure
builder.create_document_from_template(
    bom_data=bom_data,
    template_variables={
        "company_name": "Acme Corporation",
        "document_title": "Cloud Infrastructure BOM"
    }
)
```

## 🛠️ Template Validation

### Template Structure Validation

```python
# Validate template structure
issues = template_manager.validate_template(template)

if issues:
    print("Template validation issues:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("Template is valid")
```

### Common Validation Rules

- Template must have a name and format type
- All sections must have unique IDs and titles
- Variables must have valid names and types
- Branding configuration must be complete
- Page layout settings must be valid

## 📊 Advanced Features

### Conditional Sections

Create sections that appear based on data conditions:

```python
section = DocumentSection(
    id="security_analysis",
    title="Security Analysis",
    level=1,
    content_type="text",
    include_in_toc=True,
    variables={
        "condition": "has_security_findings",
        "min_findings": 1
    }
)
```

### Dynamic Section Generation

Generate sections based on data content:

```python
# Generate service-specific sections
for service in services:
    section = DocumentSection(
        id=f"{service}_resources",
        title=f"{service.upper()} Resources",
        level=2,
        content_type="table",
        variables={"service_name": service}
    )
    template.sections.append(section)
```

### Template Inheritance

Create templates that extend base templates:

```python
# Load base template
base_template = template_manager.load_template("base_word")

# Create extended template
extended_template = template_manager.create_extended_template(
    base_template,
    additional_sections=[custom_section],
    override_variables={"company_name": "Custom Corp"}
)
```

## 🔧 Configuration Management Integration

### Loading Templates with Configuration

```python
from inventag.reporting.configuration_manager import create_configuration_manager

# Create configuration manager
config_manager = create_configuration_manager("config")

# Load complete configuration including templates
config = config_manager.load_configuration("enterprise_config")

# Get template from configuration
template = config.document_template
branding = config.branding_configuration
```

### Template Configuration Files

Templates can reference external configuration files:

```yaml
# In template file
name: "Enterprise BOM Template"
configuration_references:
  service_descriptions: "config/service_descriptions.yaml"
  tag_mappings: "config/tag_mappings.yaml"
  branding_theme: "config/branding_professional.yaml"
```

## 🚀 Best Practices

### Template Organization

1. **Use descriptive names**: `professional_word_v2` instead of `template1`
2. **Version your templates**: Include version numbers in template metadata
3. **Organize by format**: Separate directories for Word, Excel, PDF templates
4. **Document variables**: Provide clear descriptions for all template variables

### Performance Optimization

1. **Cache templates**: Use TemplateManager caching for frequently used templates
2. **Lazy loading**: Load template sections only when needed
3. **Variable resolution**: Resolve variables once and reuse
4. **Template validation**: Validate templates at load time, not generation time

### Security Considerations

1. **Validate input**: Sanitize all template variables and user input
2. **Restrict file access**: Limit template loading to designated directories
3. **Audit template changes**: Log all template modifications
4. **Version control**: Store templates in version control systems

## 📈 Monitoring and Debugging

### Template Usage Metrics

```python
# Get template usage statistics
stats = template_manager.get_usage_statistics()
print(f"Most used template: {stats['most_used']}")
print(f"Template cache hit rate: {stats['cache_hit_rate']:.1f}%")
```

### Debug Mode

Enable debug logging for template operations:

```python
import logging
logging.getLogger('inventag.reporting.template_framework').setLevel(logging.DEBUG)

# Template operations will now log detailed information
template = template_manager.load_template("debug_template")
```

### Template Validation Reports

Generate detailed validation reports:

```python
validation_report = template_manager.generate_validation_report(template)
print(f"Validation status: {validation_report['status']}")
print(f"Issues found: {len(validation_report['issues'])}")
print(f"Warnings: {len(validation_report['warnings'])}")
```

## 🔄 Migration and Upgrades

### Template Version Migration

```python
# Migrate template to newer version
migrated_template = template_manager.migrate_template(
    old_template,
    target_version="2.0"
)
```

### Backward Compatibility

The framework maintains backward compatibility:

- Old template formats are automatically converted
- Deprecated features generate warnings but continue to work
- Migration utilities help upgrade to newer template versions

## 📚 Examples and Templates

### Available Template Examples

- [`assets/files/default_word_template.yaml`](/files/default_word_template.yaml): Professional Word document template
- [`assets/files/default_excel_template.json`](/files/default_excel_template.json): Excel workbook template with dashboards
- `templates/minimal_template.yaml`: Simple template for basic reports
- `templates/executive_template.yaml`: Executive summary focused template

### Creating Custom Templates

1. Start with a default template
2. Customize sections for your needs
3. Add organization-specific variables
4. Configure branding and styling
5. Validate and test the template
6. Deploy to your template directory

## 🆘 Troubleshooting

### Common Issues

**Template not found**
- Check template directory path
- Verify file extension (.yaml, .yml, .json)
- Ensure template name matches filename

**Variable substitution fails**
- Check variable syntax: `{{variable_name}}`
- Verify variable is defined in template or context
- Check for typos in variable names

**Template validation errors**
- Review validation error messages
- Check required fields (name, format_type)
- Ensure section IDs are unique

**Performance issues**
- Enable template caching
- Reduce template complexity
- Optimize variable resolution

### Debug Commands

```python
# List all available templates
templates = template_manager.list_available_templates()

# Validate specific template
issues = template_manager.validate_template(template)

# Check template cache status
cache_info = template_manager.get_cache_info()

# Clear template cache
template_manager.clear_cache()
```

## 🔗 Related Documentation

- [User Guides](../user-guides/cli-user-guide) - CLI usage and examples
- [Configuration Examples](../user-guides/configuration-examples) - Configuration management
- [Getting Started](../getting-started/quick-start) - Document generation workflow
- [Production Safety](../user-guides/production-safety) - Production safety guidelines

## 📞 Support

For template framework issues:

1. Check template validation output
2. Review debug logs
3. Verify template file syntax
4. Test with minimal template
5. Check integration with branding system

The template framework is designed to be flexible and extensible while maintaining enterprise-grade reliability and performance.
