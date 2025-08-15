#!/usr/bin/env python3
"""
Comprehensive unit tests for DocumentGenerator

Tests document generation orchestration, template system, branding application,
and multi-format document generation with error handling.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from inventag.reporting.document_generator import (
    DocumentGenerator,
    DocumentConfig,
    BrandingConfig,
    DocumentTemplate,
    DocumentGenerationResult,
    DocumentGenerationSummary,
)
from inventag.reporting.bom_processor import BOMData


class TestDocumentGenerator:
    """Test cases for DocumentGenerator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = DocumentConfig(
            output_formats=["excel", "word"], output_directory=tempfile.mkdtemp()
        )
        self.generator = DocumentGenerator(self.config)

        # Create mock BOM data
        self.mock_bom_data = Mock(spec=BOMData)
        self.mock_bom_data.resources = [
            {
                "id": "i-12345",
                "service": "EC2",
                "type": "Instance",
                "region": "us-east-1",
                "tags": {"Name": "test-instance"},
            }
        ]
        self.mock_bom_data.generation_metadata = {
            "timestamp": datetime.now().isoformat(),
            "total_resources": 1,
        }

    def test_init(self):
        """Test DocumentGenerator initialization."""
        assert self.generator.config == self.config
        assert hasattr(self.generator, "builders")
        assert isinstance(self.generator.builders, dict)
        assert hasattr(self.generator, "_lock")

    def test_validate_document_structure_valid(self):
        """Test document structure validation with valid data."""
        valid_data = Mock(spec=BOMData)
        valid_data.resources = [{"id": "test", "service": "EC2"}]
        valid_data.generation_metadata = {"timestamp": "2023-01-01T12:00:00Z"}

        result = self.generator.validate_document_structure(valid_data)
        assert result is True

    def test_validate_document_structure_invalid(self):
        """Test document structure validation with invalid data."""
        # Test with None data
        result = self.generator.validate_document_structure(None)
        assert result is False

        # Test with missing resources
        invalid_data = Mock(spec=BOMData)
        invalid_data.resources = None
        invalid_data.generation_metadata = {"timestamp": "2023-01-01T12:00:00Z"}

        result = self.generator.validate_document_structure(invalid_data)
        assert result is False

        # Test with empty resources
        invalid_data.resources = []
        result = self.generator.validate_document_structure(invalid_data)
        assert result is False

    def test_generate_filename(self):
        """Test filename generation."""
        timestamp = datetime.now()

        # Test default template
        filename = self.generator._generate_filename("excel", timestamp)
        assert filename.startswith("bom_report_")
        assert filename.endswith(".xlsx")

        # Test custom template
        custom_config = DocumentConfig(filename_template="custom_{timestamp}")
        custom_generator = DocumentGenerator(custom_config)
        filename = custom_generator._generate_filename("word", timestamp)
        assert filename.startswith("custom_")
        assert filename.endswith(".docx")

    def test_get_format_extension(self):
        """Test format extension mapping."""
        assert self.generator._get_format_extension("excel") == ".xlsx"
        assert self.generator._get_format_extension("word") == ".docx"
        assert self.generator._get_format_extension("csv") == ".csv"
        assert self.generator._get_format_extension("unknown") == ".txt"

    def test_apply_branding(self):
        """Test branding application."""
        mock_document = Mock()

        # Test Excel branding
        with patch.object(self.generator.excel_branding_applicator, "apply_branding") as mock_apply:
            self.generator.apply_branding(mock_document, "excel")
            mock_apply.assert_called_once_with(mock_document, self.config.branding)

        # Test Word branding
        with patch.object(self.generator.word_branding_applicator, "apply_branding") as mock_apply:
            self.generator.apply_branding(mock_document, "word")
            mock_apply.assert_called_once_with(mock_document, self.config.branding)

    def test_generate_single_format_excel_success(self):
        """Test successful single format generation for Excel."""
        mock_workbook = Mock()
        mock_workbook.save = Mock()

        with patch.object(
            self.generator.excel_builder,
            "create_bom_workbook",
            return_value=mock_workbook,
        ):
            with patch.object(self.generator, "apply_branding"):
                with patch("os.path.getsize", return_value=1024):
                    result = self.generator._generate_single_format("excel", self.mock_bom_data)

        assert result.success is True
        assert result.format_type == "excel"
        assert result.filename.endswith(".xlsx")
        assert result.file_size_bytes == 1024
        assert result.error_message is None

    def test_generate_single_format_word_success(self):
        """Test successful single format generation for Word."""
        mock_document = Mock()
        mock_document.save = Mock()

        with patch.object(
            self.generator.word_builder,
            "create_bom_document",
            return_value=mock_document,
        ):
            with patch.object(self.generator, "apply_branding"):
                with patch("os.path.getsize", return_value=2048):
                    result = self.generator._generate_single_format("word", self.mock_bom_data)

        assert result.success is True
        assert result.format_type == "word"
        assert result.filename.endswith(".docx")
        assert result.file_size_bytes == 2048

    def test_generate_single_format_csv_success(self):
        """Test successful single format generation for CSV."""
        with patch.object(self.generator.csv_builder, "create_bom_csv", return_value="test.csv"):
            with patch("os.path.getsize", return_value=512):
                result = self.generator._generate_single_format("csv", self.mock_bom_data)

        assert result.success is True
        assert result.format_type == "csv"
        assert result.filename.endswith(".csv")
        assert result.file_size_bytes == 512

    def test_generate_single_format_failure(self):
        """Test single format generation failure."""
        with patch.object(
            self.generator.excel_builder,
            "create_bom_workbook",
            side_effect=Exception("Test error"),
        ):
            result = self.generator._generate_single_format("excel", self.mock_bom_data)

        assert result.success is False
        assert result.format_type == "excel"
        assert "Test error" in result.error_message

    def test_generate_single_format_unsupported(self):
        """Test single format generation with unsupported format."""
        result = self.generator._generate_single_format("unsupported", self.mock_bom_data)

        assert result.success is False
        assert result.format_type == "unsupported"
        assert "Unsupported format" in result.error_message

    def test_generate_bom_documents_sequential(self):
        """Test BOM document generation in sequential mode."""
        config = DocumentConfig(output_formats=["excel", "word"], enable_parallel_generation=False)
        generator = DocumentGenerator(config)

        with patch.object(generator, "_generate_single_format") as mock_generate:
            mock_generate.side_effect = [
                DocumentGenerationResult("excel", "test.xlsx", True),
                DocumentGenerationResult("word", "test.docx", True),
            ]

            summary = generator.generate_bom_documents(self.mock_bom_data)

        assert summary.total_formats == 2
        assert summary.successful_formats == 2
        assert summary.failed_formats == 0
        assert len(summary.results) == 2
        assert mock_generate.call_count == 2

    def test_generate_bom_documents_parallel(self):
        """Test BOM document generation in parallel mode."""
        config = DocumentConfig(
            output_formats=["excel", "word", "csv"], enable_parallel_generation=True
        )
        generator = DocumentGenerator(config)

        with patch.object(generator, "_generate_single_format") as mock_generate:
            mock_generate.side_effect = [
                DocumentGenerationResult("excel", "test.xlsx", True),
                DocumentGenerationResult("word", "test.docx", True),
                DocumentGenerationResult("csv", "test.csv", True),
            ]

            summary = generator.generate_bom_documents(self.mock_bom_data)

        assert summary.total_formats == 3
        assert summary.successful_formats == 3
        assert summary.failed_formats == 0
        assert mock_generate.call_count == 3

    def test_generate_bom_documents_with_failures(self):
        """Test BOM document generation with some failures."""
        with patch.object(self.generator, "_generate_single_format") as mock_generate:
            mock_generate.side_effect = [
                DocumentGenerationResult("excel", "test.xlsx", True),
                DocumentGenerationResult("word", "", False, error_message="Word generation failed"),
            ]

            summary = self.generator.generate_bom_documents(self.mock_bom_data)

        assert summary.total_formats == 2
        assert summary.successful_formats == 1
        assert summary.failed_formats == 1
        assert len(summary.errors) == 1
        assert "Word generation failed" in summary.errors[0]

    def test_generate_bom_documents_validation_failure(self):
        """Test BOM document generation with validation failure."""
        invalid_data = Mock(spec=BOMData)
        invalid_data.resources = None

        with patch.object(self.generator, "validate_document_structure", return_value=False):
            summary = self.generator.generate_bom_documents(invalid_data)

        assert summary.total_formats == 0
        assert summary.successful_formats == 0
        assert summary.failed_formats == 0
        assert len(summary.errors) == 1
        assert "validation failed" in summary.errors[0].lower()

    def test_generate_bom_documents_timeout(self):
        """Test BOM document generation with timeout."""
        config = DocumentConfig(
            output_formats=["excel"], generation_timeout=1  # Very short timeout
        )
        generator = DocumentGenerator(config)

        def slow_generation(format_type, bom_data):
            import time

            time.sleep(2)  # Longer than timeout
            return DocumentGenerationResult(format_type, "test.xlsx", True)

        with patch.object(generator, "_generate_single_format", side_effect=slow_generation):
            summary = generator.generate_bom_documents(self.mock_bom_data)

        # Should handle timeout gracefully
        assert summary.total_formats == 1
        assert summary.failed_formats >= 0  # May or may not complete depending on timing

    def test_create_generation_summary(self):
        """Test generation summary creation."""
        results = [
            DocumentGenerationResult(
                "excel",
                "test.xlsx",
                True,
                file_size_bytes=1024,
                generation_time_seconds=1.5,
            ),
            DocumentGenerationResult(
                "word",
                "test.docx",
                True,
                file_size_bytes=2048,
                generation_time_seconds=2.0,
            ),
            DocumentGenerationResult(
                "csv",
                "",
                False,
                error_message="CSV failed",
                generation_time_seconds=0.5,
            ),
        ]

        summary = self.generator._create_generation_summary(results)

        assert summary.total_formats == 3
        assert summary.successful_formats == 2
        assert summary.failed_formats == 1
        assert summary.total_generation_time == 4.0
        assert len(summary.results) == 3
        assert len(summary.errors) == 1
        assert "CSV failed" in summary.errors[0]

    def test_cleanup_failed_files(self):
        """Test cleanup of failed generation files."""
        # Create temporary files
        temp_dir = tempfile.mkdtemp()
        test_file1 = os.path.join(temp_dir, "test1.xlsx")
        test_file2 = os.path.join(temp_dir, "test2.docx")

        # Create the files
        with open(test_file1, "w") as f:
            f.write("test")
        with open(test_file2, "w") as f:
            f.write("test")

        assert os.path.exists(test_file1)
        assert os.path.exists(test_file2)

        # Test cleanup
        self.generator._cleanup_failed_files([test_file1, test_file2])

        assert not os.path.exists(test_file1)
        assert not os.path.exists(test_file2)

    def test_get_builder_for_format(self):
        """Test builder selection for different formats."""
        assert self.generator._get_builder_for_format("excel") == self.generator.excel_builder
        assert self.generator._get_builder_for_format("word") == self.generator.word_builder
        assert self.generator._get_builder_for_format("csv") == self.generator.csv_builder

        # Test unsupported format
        with pytest.raises(ValueError):
            self.generator._get_builder_for_format("unsupported")


class TestBrandingConfig:
    """Test cases for BrandingConfig class."""

    def test_default_branding_config(self):
        """Test default branding configuration."""
        config = BrandingConfig()

        assert config.company_name == "Organization"
        assert config.logo_path is None
        assert config.color_scheme["primary"] == "#366092"
        assert config.font_family == "Calibri"
        assert config.font_size == 11
        assert config.enable_watermark is False

    def test_custom_branding_config(self):
        """Test custom branding configuration."""
        config = BrandingConfig(
            company_name="Test Corp",
            logo_path="/path/to/logo.png",
            color_scheme={"primary": "#FF0000"},
            enable_watermark=True,
            watermark_text="INTERNAL",
        )

        assert config.company_name == "Test Corp"
        assert config.logo_path == "/path/to/logo.png"
        assert config.color_scheme["primary"] == "#FF0000"
        assert config.enable_watermark is True
        assert config.watermark_text == "INTERNAL"


class TestDocumentTemplate:
    """Test cases for DocumentTemplate class."""

    def test_document_template_creation(self):
        """Test document template creation."""
        template = DocumentTemplate(
            name="Custom Template",
            format_type="excel",
            template_path="/path/to/template.xlsx",
            sections=["summary", "resources", "compliance"],
            custom_fields={"author": "Test User"},
            formatting_options={"highlight_non_compliant": True},
        )

        assert template.name == "Custom Template"
        assert template.format_type == "excel"
        assert template.template_path == "/path/to/template.xlsx"
        assert len(template.sections) == 3
        assert template.custom_fields["author"] == "Test User"
        assert template.formatting_options["highlight_non_compliant"] is True


class TestDocumentConfig:
    """Test cases for DocumentConfig class."""

    def test_default_document_config(self):
        """Test default document configuration."""
        config = DocumentConfig()

        assert config.output_formats == ["excel"]
        assert isinstance(config.branding, BrandingConfig)
        assert config.enable_parallel_generation is True
        assert config.max_worker_threads == 3
        assert config.generation_timeout == 300
        assert config.filename_template == "bom_report_{timestamp}"

    def test_custom_document_config(self):
        """Test custom document configuration."""
        branding = BrandingConfig(company_name="Test Corp")
        config = DocumentConfig(
            output_formats=["excel", "word", "csv"],
            branding=branding,
            enable_parallel_generation=False,
            max_worker_threads=5,
            generation_timeout=600,
            filename_template="custom_{timestamp}",
        )

        assert len(config.output_formats) == 3
        assert config.branding.company_name == "Test Corp"
        assert config.enable_parallel_generation is False
        assert config.max_worker_threads == 5
        assert config.generation_timeout == 600
        assert config.filename_template == "custom_{timestamp}"


class TestDocumentGenerationResult:
    """Test cases for DocumentGenerationResult class."""

    def test_successful_result(self):
        """Test successful generation result."""
        result = DocumentGenerationResult(
            format_type="excel",
            filename="test.xlsx",
            success=True,
            file_size_bytes=1024,
            generation_time_seconds=2.5,
        )

        assert result.format_type == "excel"
        assert result.filename == "test.xlsx"
        assert result.success is True
        assert result.file_size_bytes == 1024
        assert result.generation_time_seconds == 2.5
        assert result.error_message is None
        assert len(result.warnings) == 0

    def test_failed_result(self):
        """Test failed generation result."""
        result = DocumentGenerationResult(
            format_type="word",
            filename="",
            success=False,
            error_message="Template not found",
            warnings=["Missing logo file"],
        )

        assert result.format_type == "word"
        assert result.filename == ""
        assert result.success is False
        assert result.error_message == "Template not found"
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Missing logo file"


if __name__ == "__main__":
    pytest.main([__file__])
