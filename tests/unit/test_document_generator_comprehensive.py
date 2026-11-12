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
    DocumentGenerationError,
    DocumentValidationError,
)
from inventag.reporting.bom_processor import BOMData


def _bom_data(resources=None):
    return BOMData(
        resources=(
            resources
            if resources is not None
            else [
                {
                    "id": "i-12345",
                    "service": "EC2",
                    "type": "Instance",
                    "region": "us-east-1",
                    "tags": {"Name": "test-instance"},
                }
            ]
        ),
        network_analysis={},
        security_analysis={},
        compliance_summary={},
        generation_metadata={"timestamp": "2026-01-01T12:00:00Z", "total_resources": 1},
    )


class TestDocumentGenerator:
    """Test cases for DocumentGenerator (real builders, real files)."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.output_dir = tmp_path / "out"
        self.config = DocumentConfig(
            output_formats=["excel", "word"], output_directory=str(self.output_dir)
        )
        self.generator = DocumentGenerator(self.config)

    def test_init(self):
        assert self.generator.config == self.config
        assert set(self.generator.builders) == {"csv", "excel", "word"}
        assert hasattr(self.generator, "_lock")

    def test_validate_document_structure_valid(self):
        # Does not raise for well-formed data
        self.generator._validate_document_structure(_bom_data())

    @pytest.mark.parametrize(
        "mutate, message",
        [
            (lambda d: setattr(d, "resources", []), "No resources"),
            (lambda d: setattr(d, "resources", ["not-a-dict"]), "not a dictionary"),
            (lambda d: setattr(d, "generation_metadata", "x"), "metadata must be"),
            (lambda d: setattr(d, "network_analysis", ["x"]), "Network analysis"),
            (lambda d: setattr(d, "security_analysis", ["x"]), "Security analysis"),
        ],
    )
    def test_validate_document_structure_invalid(self, mutate, message):
        data = _bom_data()
        mutate(data)
        with pytest.raises(DocumentValidationError, match=message):
            self.generator._validate_document_structure(data)

    def test_get_file_extension(self):
        ext = self.generator._get_file_extension
        assert (ext("excel"), ext("word"), ext("csv"), ext("json")) == (
            "xlsx",
            "docx",
            "csv",
            "json",
        )
        assert ext("custom") == "custom"

    def test_apply_branding_delegates_to_builder(self):
        builder = Mock()
        builder.apply_branding.return_value = "branded"
        self.generator.builders["excel"] = builder
        assert self.generator.apply_branding("doc", "excel") == "branded"
        builder.apply_branding.assert_called_once_with("doc")
        assert self.generator.apply_branding("doc", "nope") == "doc"
        builder.apply_branding.side_effect = RuntimeError("boom")
        assert self.generator.apply_branding("doc", "excel") == "doc"

    @pytest.mark.parametrize(
        "fmt, ext", [("excel", "xlsx"), ("word", "docx"), ("csv", "csv")]
    )
    def test_generate_single_document_writes_private_file(self, fmt, ext):
        self.output_dir.mkdir()
        result = self.generator._generate_single_document(_bom_data(), fmt)
        assert result.success, result.error_message
        assert result.format_type == fmt
        files = list(self.output_dir.glob(f"bom_report_*.{ext}"))
        assert len(files) == 1
        assert result.file_size_bytes == files[0].stat().st_size > 0
        if os.name == "posix":
            assert files[0].stat().st_mode & 0o777 == 0o600

    def test_generate_single_document_builder_failure(self):
        builder = Mock()
        builder.generate_document.side_effect = RuntimeError("disk full")
        self.generator.builders["excel"] = builder
        result = self.generator._generate_single_document(_bom_data(), "excel")
        assert result.success is False
        assert "disk full" in result.error_message

    def test_generate_single_document_unsupported(self):
        result = self.generator._generate_single_document(_bom_data(), "pdf")
        assert result.success is False
        assert "No builder available for format: pdf" in result.error_message

    def test_generate_bom_documents_sequential(self):
        self.config.enable_parallel_generation = False
        summary = self.generator.generate_bom_documents(_bom_data(), ["csv", "excel"])
        assert (summary.total_formats, summary.successful_formats) == (2, 2)
        assert summary.failed_formats == 0 and summary.errors == []
        if os.name == "posix":
            assert self.output_dir.stat().st_mode & 0o777 == 0o700

    def test_generate_bom_documents_parallel(self):
        summary = self.generator.generate_bom_documents(
            _bom_data(), ["csv", "excel", "word"]
        )
        assert summary.successful_formats == 3
        assert sorted(r.format_type for r in summary.results) == [
            "csv",
            "excel",
            "word",
        ]

    def test_generate_bom_documents_with_failures(self):
        summary = self.generator.generate_bom_documents(_bom_data(), ["csv", "pdf"])
        assert (summary.successful_formats, summary.failed_formats) == (1, 1)
        assert any(e.startswith("pdf:") for e in summary.errors)

    def test_generate_bom_documents_validation_failure(self):
        with pytest.raises(DocumentGenerationError, match="No resources"):
            self.generator.generate_bom_documents(_bom_data(resources=[]), ["csv"])

    def test_generate_bom_documents_without_validation(self):
        self.config.validate_before_generation = False
        summary = self.generator.generate_bom_documents(
            _bom_data(resources=[]), ["csv"]
        )
        assert summary.total_formats == 1

    def test_available_formats_and_capabilities(self):
        assert sorted(self.generator.get_available_formats()) == [
            "csv",
            "excel",
            "word",
        ]
        caps = self.generator.get_format_capabilities()
        assert caps["excel"]["dependencies_met"] is True
        assert self.generator.validate_format_dependencies("pdf") == [
            "No builder available for format: pdf"
        ]

    def test_load_template(self, tmp_path):
        path = tmp_path / "t.yaml"
        path.write_text("name: Corp\nsections: [summary]\nformatting_options: {x: 1}\n")
        template = self.generator.load_template(str(path), "excel")
        assert (template.name, template.sections, template.formatting_options) == (
            "Corp",
            ["summary"],
            {"x": 1},
        )
        assert self.generator.load_template(str(tmp_path / "t.txt"), "excel") is None

    def test_save_generation_report(self, tmp_path):
        summary = DocumentGenerationSummary(
            total_formats=1,
            successful_formats=1,
            failed_formats=0,
            results=[
                DocumentGenerationResult("csv", "a.csv", True, file_size_bytes=10)
            ],
        )
        target = tmp_path / "report.json"
        self.generator.save_generation_report(summary, str(target))
        report = json.loads(target.read_text())
        assert report["generation_summary"]["successful_formats"] == 1
        assert report["results"][0]["filename"] == "a.csv"
        if os.name == "posix":
            assert target.stat().st_mode & 0o777 == 0o600


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
