#!/usr/bin/env python3
"""
DocumentGenerator - Document Generation Orchestration Layer

Central orchestrator for multi-format document generation with template system.
Extracted and enhanced from existing bom_converter.py document generation patterns.

Features:
- Multi-format document generation coordination with template system
- Document structure validation before generation with schema checking
- Branding application for organization customization with logo support
- Format-specific builder coordination with parallel generation
- Comprehensive error handling and recovery for document generation failures
"""

import logging
import os
import re
import json
import uuid
import yaml
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import dataclass, field, replace as dataclass_replace
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading
from abc import ABC, abstractmethod

from .bom_processor import BOMData
from ..security.safe_output import (
    ensure_private_dir,
    open_private,
    precreate_private,
)

# Excel allows 32,767 characters in a cell and 16,384 columns on a sheet.
# Word has no hard cell limit, but one huge tag value would make the file
# unusable, so the same cap is used there.
MAX_CELL_CHARS = 32767
MAX_EXCEL_COLUMNS = 16384
MAX_SHEET_NAME_CHARS = 31

# Characters XML 1.0 cannot hold (control characters, lone surrogates, U+FFFE
# and U+FFFF). openpyxl and python-docx refuse to write them.
_ILLEGAL_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\\x00-\x1f]")
# Excel reserves this sheet name.
_RESERVED_SHEET_NAMES = {"history"}


def clean_text(value: str) -> str:
    """Replace characters that cannot be stored in an Office XML file with U+FFFD."""
    return _ILLEGAL_XML_CHARS.sub("\ufffd", value)


def limit_text(text: str, limit: int = MAX_CELL_CHARS) -> str:
    """Cut text to ``limit`` characters and say so, so nobody mistakes it for the full value."""
    if len(text) <= limit:
        return text
    marker = f"... [truncated, {len(text)} characters in total]"
    return text[: limit - len(marker)] + marker


def clean_structure(value: Any) -> Any:
    """Return ``value`` with illegal XML characters removed from every string and key.

    Nothing is copied when the data is already clean, so this is cheap to call
    on a large inventory.
    """
    if isinstance(value, str):
        return clean_text(value) if _ILLEGAL_XML_CHARS.search(value) else value
    if isinstance(value, dict):
        changed = False
        out = {}
        for key, item in value.items():
            new_key = clean_structure(key)
            new_item = clean_structure(item)
            changed = changed or new_key is not key or new_item is not item
            out[new_key] = new_item
        return out if changed else value
    if isinstance(value, (list, tuple)):
        items = [clean_structure(item) for item in value]
        if any(new is not old for new, old in zip(items, value)):
            return items if isinstance(value, list) else tuple(items)
        return value
    return value


def clean_bom_data(bom_data: "BOMData") -> "BOMData":
    """A BOMData whose text can be written to Excel and Word (same object if already clean)."""
    changes = {}
    for name in (
        "resources",
        "network_analysis",
        "security_analysis",
        "compliance_summary",
        "generation_metadata",
        "custom_attributes",
    ):
        original = getattr(bom_data, name)
        cleaned = clean_structure(original)
        if cleaned is not original:
            changes[name] = cleaned
    return dataclass_replace(bom_data, **changes) if changes else bom_data


def safe_sheet_name(name: Any, taken: Set[str]) -> str:
    """An Excel sheet name made from ``name`` that is valid and not in ``taken``.

    ``taken`` holds lower-case names already used (Excel compares names without
    regard to case). The caller adds the result to it. Characters Excel
    forbids (``[ ] : * ? / \\``) become ``_``; a name longer than 31 characters
    is cut, and a name that is already used gets `` (2)``, `` (3)`` ... inside
    the 31 characters.
    """
    text = _INVALID_SHEET_CHARS.sub("_", "" if name is None else str(name))
    text = text.strip().strip("'").strip() or "Sheet"
    base = text[:MAX_SHEET_NAME_CHARS]
    candidate = base
    number = 1
    while candidate.lower() in taken or candidate.lower() in _RESERVED_SHEET_NAMES:
        number += 1
        suffix = f" ({number})"
        candidate = base[: MAX_SHEET_NAME_CHARS - len(suffix)] + suffix
    taken.add(candidate.lower())
    return candidate


def save_atomically(output_path: str, save) -> None:
    """Write a report so a failure never leaves a half-written file at ``output_path``.

    ``save`` is called with a temporary path in the same directory (created
    owner-only); the file is renamed to ``output_path`` only when ``save``
    finished. On any error the temporary file is removed and an existing file
    at ``output_path`` is left as it was.
    """
    directory, name = os.path.split(os.fspath(output_path))
    temporary = os.path.join(directory, f".{name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        precreate_private(temporary)
        save(temporary)
        os.replace(temporary, output_path)
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


@dataclass
class BrandingConfig:
    """Configuration for document branding and customization."""

    company_name: str = "Organization"
    logo_path: Optional[str] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    color_scheme: Dict[str, str] = field(
        default_factory=lambda: {
            "primary": "#366092",
            "secondary": "#4472C4",
            "accent": "#70AD47",
            "warning": "#FFC000",
            "danger": "#C5504B",
        }
    )
    font_family: str = "Calibri"
    font_size: int = 11
    enable_watermark: bool = False
    watermark_text: str = "CONFIDENTIAL"


@dataclass
class DocumentTemplate:
    """Document template configuration."""

    name: str
    format_type: str  # excel, word, csv, etc.
    template_path: Optional[str] = None
    sections: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    formatting_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentConfig:
    """Configuration for document generation."""

    output_formats: List[str] = field(default_factory=lambda: ["excel"])
    branding: BrandingConfig = field(default_factory=BrandingConfig)
    templates: Dict[str, DocumentTemplate] = field(default_factory=dict)
    field_visibility: Dict[str, bool] = field(default_factory=dict)
    enable_parallel_generation: bool = True
    max_worker_threads: int = 3
    # Word only: show at most this many resources per service and say how many
    # were left out. None (the default) shows every resource.
    max_rows_per_service: Optional[int] = None
    generation_timeout: int = 300  # seconds
    output_directory: str = "."
    filename_template: str = "bom_report_{timestamp}"
    include_metadata: bool = True
    include_error_summary: bool = True
    validate_before_generation: bool = True


@dataclass
class DocumentGenerationResult:
    """Result of document generation operation."""

    format_type: str
    filename: str
    success: bool
    file_size_bytes: int = 0
    generation_time_seconds: float = 0.0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class DocumentGenerationSummary:
    """Summary of all document generation operations."""

    total_formats: int
    successful_formats: int
    failed_formats: int
    results: List[DocumentGenerationResult] = field(default_factory=list)
    total_generation_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DocumentValidationError(Exception):
    """Exception raised when document validation fails."""

    pass


class DocumentGenerationError(Exception):
    """Exception raised when document generation fails."""

    pass


class DocumentBuilder(ABC):
    """Abstract base class for format-specific document builders."""

    def __init__(self, config: DocumentConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def can_handle_format(self, format_type: str) -> bool:
        """Check if this builder can handle the specified format."""
        pass

    @abstractmethod
    def generate_document(
        self, bom_data: BOMData, output_path: str
    ) -> DocumentGenerationResult:
        """Generate document in the specific format."""
        pass

    @abstractmethod
    def validate_dependencies(self) -> List[str]:
        """Validate that required dependencies are available."""
        pass

    def apply_branding(self, document_object: Any) -> Any:
        """Apply branding configuration to document object."""
        # Default implementation - override in specific builders
        return document_object


class DocumentGenerator:
    """
    Central orchestrator for multi-format document generation.

    Enhanced from bom_converter.py document generation patterns with:
    - Multi-format document generation coordination with template system
    - Document structure validation before generation with schema checking
    - Branding application for organization customization with logo support
    - Format-specific builder coordination with parallel generation
    - Comprehensive error handling and recovery for document generation failures
    """

    def __init__(self, config: DocumentConfig):
        """Initialize the document generator."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.DocumentGenerator")

        # Initialize document builders
        self.builders: Dict[str, DocumentBuilder] = {}
        self._initialize_builders()

        # Generation state
        self._generation_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def _initialize_builders(self):
        """Initialize format-specific document builders."""
        try:
            # Import and initialize builders
            from .excel_builder import ExcelWorkbookBuilder
            from .word_builder import WordDocumentBuilder
            from .csv_builder import CSVBuilder

            # Register CSV builder first (always available)
            try:
                csv_builder = CSVBuilder(self.config)
                dependencies = csv_builder.validate_dependencies()
                if not dependencies:  # Empty list means no missing dependencies
                    self.builders["csv"] = csv_builder
                    self.logger.info("Initialized CSVBuilder")
                else:
                    self.logger.warning(
                        f"CSVBuilder dependencies not available: {dependencies}"
                    )
            except Exception as e:
                self.logger.error(f"Failed to initialize CSVBuilder: {e}")

            # Register Excel builder
            try:
                excel_builder = ExcelWorkbookBuilder(self.config)
                dependencies = excel_builder.validate_dependencies()
                if not dependencies:  # Empty list means no missing dependencies
                    self.builders["excel"] = excel_builder
                    self.logger.info("Initialized ExcelWorkbookBuilder")
                else:
                    self.logger.warning(
                        f"ExcelWorkbookBuilder dependencies not available: {dependencies}"
                    )
            except Exception as e:
                self.logger.error(f"Failed to initialize ExcelWorkbookBuilder: {e}")

            # Register Word builder
            try:
                word_builder = WordDocumentBuilder(self.config)
                dependencies = word_builder.validate_dependencies()
                if not dependencies:  # Empty list means no missing dependencies
                    self.builders["word"] = word_builder
                    self.logger.info("Initialized WordDocumentBuilder")
                else:
                    self.logger.warning(
                        f"WordDocumentBuilder dependencies not available: {dependencies}"
                    )
            except Exception as e:
                self.logger.error(f"Failed to initialize WordDocumentBuilder: {e}")

        except ImportError as e:
            self.logger.error(f"Failed to import document builders: {e}")
            # Create minimal CSV builder as fallback
            self._create_fallback_csv_builder()

    def _create_fallback_csv_builder(self):
        """Create a minimal CSV builder as fallback."""
        try:
            from .csv_builder import CSVBuilder

            csv_builder = CSVBuilder(self.config)
            self.builders["csv"] = csv_builder
            self.logger.info("Created fallback CSVBuilder")
        except Exception as e:
            self.logger.error(f"Failed to create fallback CSV builder: {e}")

    def generate_bom_documents(
        self, bom_data: BOMData, output_formats: Optional[List[str]] = None
    ) -> DocumentGenerationSummary:
        """
        Generate BOM documents in specified formats.

        Enhanced from bom_converter.py export methods with:
        - Multi-format document generation coordination with template system
        - Document structure validation before generation with schema checking
        - Branding application for organization customization with logo support
        - Format-specific builder coordination with parallel generation
        - Comprehensive error handling and recovery for document generation failures
        """
        start_time = datetime.now(timezone.utc)

        # Use provided formats or default from config
        formats = output_formats or self.config.output_formats

        self.logger.info(f"Starting document generation for formats: {formats}")

        # Initialize summary
        summary = DocumentGenerationSummary(
            total_formats=len(formats), successful_formats=0, failed_formats=0
        )

        try:
            # Step 1: Validate document structure
            if self.config.validate_before_generation:
                self._validate_document_structure(bom_data)

            # Step 2: Prepare output directory
            self._prepare_output_directory()

            # Step 3: Generate documents
            if self.config.enable_parallel_generation and len(formats) > 1:
                results = self._parallel_document_generation(bom_data, formats)
            else:
                results = self._sequential_document_generation(bom_data, formats)

            # Step 4: Process results
            summary.results = results
            summary.successful_formats = sum(1 for r in results if r.success)
            summary.failed_formats = len(results) - summary.successful_formats

            # Collect errors and warnings
            for result in results:
                if result.error_message:
                    summary.errors.append(
                        f"{result.format_type}: {result.error_message}"
                    )
                summary.warnings.extend(result.warnings)

            # Calculate total time
            end_time = datetime.now(timezone.utc)
            summary.total_generation_time = (end_time - start_time).total_seconds()

            self.logger.info(
                f"Document generation completed in {summary.total_generation_time:.2f}s. "
                f"Success: {summary.successful_formats}/{summary.total_formats}"
            )

            return summary

        except Exception as e:
            self.logger.error(f"Document generation failed: {e}")
            summary.errors.append(str(e))
            summary.failed_formats = summary.total_formats
            raise DocumentGenerationError(f"Document generation failed: {e}")

    def _validate_document_structure(self, bom_data: BOMData):
        """
        Validate BOM data structure before document generation.

        Enhanced validation with schema checking to ensure data integrity.
        """
        self.logger.info("Validating document structure")

        try:
            # Validate required fields
            if not bom_data.resources:
                raise DocumentValidationError("No resources found in BOM data")

            if not isinstance(bom_data.resources, list):
                raise DocumentValidationError("Resources must be a list")

            # Validate resource structure
            required_resource_fields = ["service", "type", "id"]
            for i, resource in enumerate(
                bom_data.resources[:10]
            ):  # Check first 10 resources
                if not isinstance(resource, dict):
                    raise DocumentValidationError(f"Resource {i} is not a dictionary")

                missing_fields = [
                    field for field in required_resource_fields if field not in resource
                ]
                if missing_fields:
                    self.logger.warning(
                        f"Resource {i} missing fields: {missing_fields}"
                    )

            # Validate metadata structure
            if not isinstance(bom_data.generation_metadata, dict):
                raise DocumentValidationError(
                    "Generation metadata must be a dictionary"
                )

            # Validate analysis data
            if bom_data.network_analysis and not isinstance(
                bom_data.network_analysis, dict
            ):
                raise DocumentValidationError("Network analysis must be a dictionary")

            if bom_data.security_analysis and not isinstance(
                bom_data.security_analysis, dict
            ):
                raise DocumentValidationError("Security analysis must be a dictionary")

            self.logger.info("Document structure validation passed")

        except Exception as e:
            self.logger.error(f"Document structure validation failed: {e}")
            raise DocumentValidationError(f"Validation failed: {e}")

    def _prepare_output_directory(self):
        """Prepare output directory for document generation."""
        try:
            output_dir = ensure_private_dir(self.config.output_directory)
            self.logger.debug(f"Output directory prepared: {output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to prepare output directory: {e}")
            raise DocumentGenerationError(f"Output directory preparation failed: {e}")

    def _parallel_document_generation(
        self, bom_data: BOMData, formats: List[str]
    ) -> List[DocumentGenerationResult]:
        """Generate documents in parallel for better performance."""
        self.logger.info(
            f"Starting parallel document generation with {self.config.max_worker_threads} threads"
        )

        results = []

        with ThreadPoolExecutor(max_workers=self.config.max_worker_threads) as executor:
            # Submit generation tasks
            future_to_format = {
                executor.submit(self._generate_single_document, bom_data, fmt): fmt
                for fmt in formats
            }

            # Collect results
            for future in as_completed(
                future_to_format, timeout=self.config.generation_timeout
            ):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    format_type = future_to_format[future]
                    self.logger.error(f"Failed to generate {format_type} document: {e}")
                    results.append(
                        DocumentGenerationResult(
                            format_type=format_type,
                            filename="",
                            success=False,
                            error_message=str(e),
                        )
                    )

        self.logger.info(
            f"Parallel document generation completed. Generated {len(results)} documents"
        )
        return results

    def _sequential_document_generation(
        self, bom_data: BOMData, formats: List[str]
    ) -> List[DocumentGenerationResult]:
        """Generate documents sequentially."""
        self.logger.info("Starting sequential document generation")

        results = []

        for fmt in formats:
            try:
                result = self._generate_single_document(bom_data, fmt)
                results.append(result)
                self.logger.info(f"Generated {fmt} document: {result.filename}")
            except Exception as e:
                self.logger.error(f"Failed to generate {fmt} document: {e}")
                results.append(
                    DocumentGenerationResult(
                        format_type=fmt,
                        filename="",
                        success=False,
                        error_message=str(e),
                    )
                )

        self.logger.info(
            f"Sequential document generation completed. Generated {len(results)} documents"
        )
        return results

    def _generate_single_document(
        self, bom_data: BOMData, format_type: str
    ) -> DocumentGenerationResult:
        """Generate a single document in the specified format."""
        start_time = datetime.now(timezone.utc)

        try:
            # Check if we have a builder for this format
            if format_type not in self.builders:
                raise DocumentGenerationError(
                    f"No builder available for format: {format_type}"
                )

            builder = self.builders[format_type]

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_base = self.config.filename_template.format(timestamp=timestamp)

            # Get file extension from builder
            extension = self._get_file_extension(format_type)
            filename = f"{filename_base}.{extension}"
            output_path = os.path.join(self.config.output_directory, filename)

            # Generate document
            result = builder.generate_document(bom_data, output_path)

            # Calculate generation time
            end_time = datetime.now(timezone.utc)
            result.generation_time_seconds = (end_time - start_time).total_seconds()

            # Get file size if successful
            if result.success and os.path.exists(output_path):
                result.file_size_bytes = os.path.getsize(output_path)

            return result

        except Exception as e:
            self.logger.error(
                f"Single document generation failed for {format_type}: {e}"
            )
            return DocumentGenerationResult(
                format_type=format_type,
                filename="",
                success=False,
                error_message=str(e),
                generation_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
            )

    def _get_file_extension(self, format_type: str) -> str:
        """Get file extension for format type."""
        extensions = {
            "excel": "xlsx",
            "word": "docx",
            "csv": "csv",
            "json": "json",
            "yaml": "yaml",
        }
        return extensions.get(format_type, format_type)

    def apply_branding(self, document_object: Any, format_type: str) -> Any:
        """
        Apply organization branding to documents.

        Enhanced branding application with logo support and customization.
        """
        try:
            if format_type in self.builders:
                builder = self.builders[format_type]
                return builder.apply_branding(document_object)
            else:
                self.logger.warning(
                    f"No builder available for branding application: {format_type}"
                )
                return document_object
        except Exception as e:
            self.logger.error(f"Branding application failed for {format_type}: {e}")
            return document_object

    def get_available_formats(self) -> List[str]:
        """Get list of available document formats."""
        return list(self.builders.keys())

    def validate_format_dependencies(self, format_type: str) -> List[str]:
        """Validate dependencies for a specific format."""
        if format_type in self.builders:
            return self.builders[format_type].validate_dependencies()
        else:
            return [f"No builder available for format: {format_type}"]

    def get_format_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Get capabilities information for all available formats."""
        capabilities = {}

        for format_type, builder in self.builders.items():
            capabilities[format_type] = {
                "available": True,
                "dependencies_met": len(builder.validate_dependencies()) == 0,
                "supports_branding": hasattr(builder, "apply_branding"),
                "supports_templates": hasattr(builder, "load_template"),
                "builder_class": builder.__class__.__name__,
            }

        return capabilities

    def load_template(
        self, template_path: str, format_type: str
    ) -> Optional[DocumentTemplate]:
        """Load document template from file."""
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                if template_path.endswith(".json"):
                    template_data = json.load(f)
                elif template_path.endswith((".yaml", ".yml")):
                    template_data = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported template format: {template_path}")

            template = DocumentTemplate(
                name=template_data.get("name", "Custom Template"),
                format_type=format_type,
                template_path=template_path,
                sections=template_data.get("sections", []),
                custom_fields=template_data.get("custom_fields", {}),
                formatting_options=template_data.get("formatting_options", {}),
            )

            self.logger.info(f"Loaded template: {template.name}")
            return template

        except Exception as e:
            self.logger.error(f"Failed to load template {template_path}: {e}")
            return None

    def save_generation_report(
        self, summary: DocumentGenerationSummary, output_path: str
    ):
        """Save document generation report to file."""
        try:
            report = {
                "generation_summary": {
                    "total_formats": summary.total_formats,
                    "successful_formats": summary.successful_formats,
                    "failed_formats": summary.failed_formats,
                    "total_generation_time": summary.total_generation_time,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                "results": [
                    {
                        "format_type": result.format_type,
                        "filename": result.filename,
                        "success": result.success,
                        "file_size_bytes": result.file_size_bytes,
                        "generation_time_seconds": result.generation_time_seconds,
                        "error_message": result.error_message,
                        "warnings": result.warnings,
                    }
                    for result in summary.results
                ],
                "errors": summary.errors,
                "warnings": summary.warnings,
            }

            with open_private(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Generation report saved: {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to save generation report: {e}")


# Factory function for easy initialization
def create_document_generator(
    output_formats: Optional[List[str]] = None,
    branding_config: Optional[BrandingConfig] = None,
    **kwargs,
) -> DocumentGenerator:
    """Create a DocumentGenerator with common configuration."""

    config = DocumentConfig(
        output_formats=output_formats or ["excel"],
        branding=branding_config or BrandingConfig(),
        **kwargs,
    )

    return DocumentGenerator(config)
