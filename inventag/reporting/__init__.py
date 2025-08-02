"""
InvenTag Reporting Module

Extracted and enhanced functionality from bom_converter.py
Provides professional AWS resource inventory to Excel/CSV conversion.
"""

from .converter import BOMConverter
from .bom_processor import BOMDataProcessor, BOMProcessingConfig, BOMData, ProcessingStatistics
from .document_generator import (
    DocumentGenerator, DocumentConfig, BrandingConfig, DocumentTemplate,
    DocumentGenerationResult, DocumentGenerationSummary, create_document_generator
)
from .template_framework import TemplateManager, TemplateVariableResolver, TemplateLoader

__all__ = [
    "BOMConverter", 
    "BOMDataProcessor", "BOMProcessingConfig", "BOMData", "ProcessingStatistics",
    "DocumentGenerator", "DocumentConfig", "BrandingConfig", "DocumentTemplate",
    "DocumentGenerationResult", "DocumentGenerationSummary", "create_document_generator",
    "TemplateManager", "TemplateVariableResolver", "TemplateLoader"
]