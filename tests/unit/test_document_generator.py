#!/usr/bin/env python3
"""
Unit tests for DocumentGenerator orchestration layer.

Tests the document generation orchestration and template rendering functionality.
"""

import unittest
import tempfile
import os
import json
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Import the modules to test
from inventag.reporting.document_generator import (
    DocumentGenerator,
    DocumentConfig,
    BrandingConfig,
    DocumentTemplate,
    DocumentGenerationResult,
    DocumentGenerationSummary,
    DocumentValidationError,
    DocumentGenerationError,
    create_document_generator,
)
from inventag.reporting.bom_processor import BOMData


class TestDocumentGenerator(unittest.TestCase):
    """Test cases for DocumentGenerator orchestration layer."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create test BOM data
        self.test_bom_data = BOMData(
            resources=[
                {
                    "service": "EC2",
                    "type": "Instance",
                    "id": "i-1234567890abcdef0",
                    "region": "us-east-1",
                    "compliance_status": "compliant",
                },
                {
                    "service": "S3",
                    "type": "Bucket",
                    "id": "test-bucket",
                    "region": "us-east-1",
                    "compliance_status": "non_compliant",
                },
            ],
            network_analysis={"total_vpcs": 2, "total_subnets": 4},
            security_analysis={"total_security_groups": 5, "high_risk_rules": 1},
            compliance_summary={"total_resources": 2, "compliant_resources": 1},
            generation_metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_resources": 2,
            },
            custom_attributes=["inventag:remarks", "inventag:costcenter"],
        )

        # Create test configuration
        self.test_config = DocumentConfig(
            output_formats=["csv"],
            output_directory=self.temp_dir,
            enable_parallel_generation=False,
            validate_before_generation=True,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_document_generator_initialization(self):
        """Test DocumentGenerator initialization."""
        generator = DocumentGenerator(self.test_config)

        self.assertIsInstance(generator, DocumentGenerator)
        self.assertEqual(generator.config, self.test_config)
        self.assertIsInstance(generator.builders, dict)

    def test_document_config_defaults(self):
        """Test DocumentConfig default values."""
        config = DocumentConfig()

        self.assertEqual(config.output_formats, ["excel"])
        self.assertIsInstance(config.branding, BrandingConfig)
        self.assertTrue(config.enable_parallel_generation)
        self.assertEqual(config.max_worker_threads, 3)
        self.assertTrue(config.validate_before_generation)

    def test_branding_config_defaults(self):
        """Test BrandingConfig default values."""
        branding = BrandingConfig()

        self.assertEqual(branding.company_name, "Organization")
        self.assertIsNone(branding.logo_path)
        self.assertIsInstance(branding.color_scheme, dict)
        self.assertIn("primary", branding.color_scheme)
        self.assertEqual(branding.font_family, "Calibri")

    def test_document_template_creation(self):
        """Test DocumentTemplate creation."""
        template = DocumentTemplate(
            name="Test Template",
            format_type="excel",
            sections=["summary", "resources"],
            custom_fields={"title": "Test Report"},
        )

        self.assertEqual(template.name, "Test Template")
        self.assertEqual(template.format_type, "excel")
        self.assertEqual(template.sections, ["summary", "resources"])
        self.assertEqual(template.custom_fields["title"], "Test Report")

    @patch("inventag.reporting.csv_builder.CSVBuilder")
    def test_csv_builder_initialization(self, mock_csv_builder):
        """Test CSV builder initialization."""
        mock_builder = Mock()
        mock_builder.validate_dependencies.return_value = []
        mock_csv_builder.return_value = mock_builder

        generator = DocumentGenerator(self.test_config)

        # Should have initialized CSV builder
        mock_csv_builder.assert_called_once()

    def test_document_structure_validation_success(self):
        """Test successful document structure validation."""
        generator = DocumentGenerator(self.test_config)

        # Should not raise exception
        try:
            generator._validate_document_structure(self.test_bom_data)
        except DocumentValidationError:
            self.fail("Document validation should have passed")

    def test_document_structure_validation_empty_resources(self):
        """Test document structure validation with empty resources."""
        generator = DocumentGenerator(self.test_config)

        # Create BOM data with empty resources
        empty_bom_data = BOMData(resources=[], generation_metadata={})

        with self.assertRaises(DocumentValidationError) as context:
            generator._validate_document_structure(empty_bom_data)

        self.assertIn("No resources found", str(context.exception))

    def test_document_structure_validation_invalid_resources(self):
        """Test document structure validation with invalid resources."""
        generator = DocumentGenerator(self.test_config)

        # Create BOM data with invalid resources
        invalid_bom_data = BOMData(resources="not a list", generation_metadata={})

        with self.assertRaises(DocumentValidationError) as context:
            generator._validate_document_structure(invalid_bom_data)

        self.assertIn("Resources must be a list", str(context.exception))

    def test_prepare_output_directory(self):
        """Test output directory preparation."""
        # Use a subdirectory that doesn't exist
        subdir = os.path.join(self.temp_dir, "output", "reports")
        config = DocumentConfig(output_directory=subdir)
        generator = DocumentGenerator(config)

        # Should create the directory
        generator._prepare_output_directory()
        self.assertTrue(os.path.exists(subdir))

    def test_get_file_extension(self):
        """Test file extension mapping."""
        generator = DocumentGenerator(self.test_config)

        self.assertEqual(generator._get_file_extension("excel"), "xlsx")
        self.assertEqual(generator._get_file_extension("word"), "docx")
        self.assertEqual(generator._get_file_extension("csv"), "csv")
        self.assertEqual(generator._get_file_extension("unknown"), "unknown")

    def test_get_available_formats(self):
        """Test getting available formats."""
        generator = DocumentGenerator(self.test_config)

        formats = generator.get_available_formats()
        self.assertIsInstance(formats, list)
        # Should at least have CSV as fallback
        self.assertIn("csv", formats)

    def test_get_format_capabilities(self):
        """Test getting format capabilities."""
        generator = DocumentGenerator(self.test_config)

        capabilities = generator.get_format_capabilities()
        self.assertIsInstance(capabilities, dict)

        # Should have CSV capabilities
        if "csv" in capabilities:
            csv_caps = capabilities["csv"]
            self.assertTrue(csv_caps["available"])
            self.assertTrue(csv_caps["dependencies_met"])

    @patch("inventag.reporting.csv_builder.CSVBuilder")
    def test_sequential_document_generation(self, mock_csv_builder):
        """Test sequential document generation."""
        # Mock CSV builder
        mock_builder = Mock()
        mock_builder.validate_dependencies.return_value = []
        mock_builder.generate_document.return_value = DocumentGenerationResult(
            format_type="csv", filename="test.csv", success=True
        )
        mock_csv_builder.return_value = mock_builder

        generator = DocumentGenerator(self.test_config)

        results = generator._sequential_document_generation(self.test_bom_data, ["csv"])

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)
        self.assertEqual(results[0].format_type, "csv")

    @patch("inventag.reporting.csv_builder.CSVBuilder")
    def test_parallel_document_generation(self, mock_csv_builder):
        """Test parallel document generation."""
        # Mock CSV builder
        mock_builder = Mock()
        mock_builder.validate_dependencies.return_value = []
        mock_builder.generate_document.return_value = DocumentGenerationResult(
            format_type="csv", filename="test.csv", success=True
        )
        mock_csv_builder.return_value = mock_builder

        config = DocumentConfig(
            output_formats=["csv"],
            output_directory=self.temp_dir,
            enable_parallel_generation=True,
            max_worker_threads=2,
        )
        generator = DocumentGenerator(config)

        results = generator._parallel_document_generation(self.test_bom_data, ["csv"])

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)

    @patch("inventag.reporting.csv_builder.CSVBuilder")
    def test_generate_bom_documents_success(self, mock_csv_builder):
        """Test successful BOM document generation."""
        # Mock CSV builder
        mock_builder = Mock()
        mock_builder.validate_dependencies.return_value = []
        mock_builder.generate_document.return_value = DocumentGenerationResult(
            format_type="csv",
            filename="test.csv",
            success=True,
            file_size_bytes=1024,
            generation_time_seconds=0.5,
        )
        mock_csv_builder.return_value = mock_builder

        generator = DocumentGenerator(self.test_config)

        summary = generator.generate_bom_documents(self.test_bom_data)

        self.assertIsInstance(summary, DocumentGenerationSummary)
        self.assertEqual(summary.total_formats, 1)
        self.assertEqual(summary.successful_formats, 1)
        self.assertEqual(summary.failed_formats, 0)
        self.assertEqual(len(summary.results), 1)
        self.assertTrue(summary.results[0].success)

    def test_generate_bom_documents_validation_failure(self):
        """Test BOM document generation with validation failure."""
        # Create invalid BOM data
        invalid_bom_data = BOMData(resources=[])

        generator = DocumentGenerator(self.test_config)

        with self.assertRaises(DocumentGenerationError):
            generator.generate_bom_documents(invalid_bom_data)

    @patch("inventag.reporting.csv_builder.CSVBuilder")
    def test_generate_bom_documents_builder_failure(self, mock_csv_builder):
        """Test BOM document generation with builder failure."""
        # Mock CSV builder to fail
        mock_builder = Mock()
        mock_builder.validate_dependencies.return_value = []
        mock_builder.generate_document.side_effect = Exception("Builder failed")
        mock_csv_builder.return_value = mock_builder

        generator = DocumentGenerator(self.test_config)

        summary = generator.generate_bom_documents(self.test_bom_data)

        self.assertEqual(summary.successful_formats, 0)
        self.assertEqual(summary.failed_formats, 1)
        self.assertFalse(summary.results[0].success)
        self.assertIn("Builder failed", summary.results[0].error_message)

    def test_load_template_json(self):
        """Test loading JSON template."""
        # Create test template file
        template_data = {
            "name": "Test Template",
            "sections": ["summary", "resources"],
            "custom_fields": {"title": "Test Report"},
            "formatting_options": {"font_size": 12},
        }

        template_path = os.path.join(self.temp_dir, "template.json")
        with open(template_path, "w") as f:
            json.dump(template_data, f)

        generator = DocumentGenerator(self.test_config)
        template = generator.load_template(template_path, "excel")

        self.assertIsNotNone(template)
        self.assertEqual(template.name, "Test Template")
        self.assertEqual(template.format_type, "excel")
        self.assertEqual(template.sections, ["summary", "resources"])

    def test_load_template_invalid_file(self):
        """Test loading invalid template file."""
        generator = DocumentGenerator(self.test_config)
        template = generator.load_template("nonexistent.json", "excel")

        self.assertIsNone(template)

    def test_save_generation_report(self):
        """Test saving generation report."""
        generator = DocumentGenerator(self.test_config)

        # Create test summary
        summary = DocumentGenerationSummary(
            total_formats=1,
            successful_formats=1,
            failed_formats=0,
            results=[
                DocumentGenerationResult(
                    format_type="csv",
                    filename="test.csv",
                    success=True,
                    file_size_bytes=1024,
                    generation_time_seconds=0.5,
                )
            ],
            total_generation_time=1.0,
        )

        report_path = os.path.join(self.temp_dir, "report.json")
        generator.save_generation_report(summary, report_path)

        # Verify report was saved
        self.assertTrue(os.path.exists(report_path))

        # Verify report content
        with open(report_path, "r") as f:
            report_data = json.load(f)

        self.assertEqual(report_data["generation_summary"]["total_formats"], 1)
        self.assertEqual(report_data["generation_summary"]["successful_formats"], 1)
        self.assertEqual(len(report_data["results"]), 1)

    def test_create_document_generator_factory(self):
        """Test create_document_generator factory function."""
        generator = create_document_generator(
            output_formats=["csv", "excel"],
            branding_config=BrandingConfig(company_name="Test Corp"),
            output_directory=self.temp_dir,
        )

        self.assertIsInstance(generator, DocumentGenerator)
        self.assertEqual(generator.config.output_formats, ["csv", "excel"])
        self.assertEqual(generator.config.branding.company_name, "Test Corp")
        self.assertEqual(generator.config.output_directory, self.temp_dir)


class TestDocumentGenerationResult(unittest.TestCase):
    """Test cases for DocumentGenerationResult."""

    def test_document_generation_result_creation(self):
        """Test DocumentGenerationResult creation."""
        result = DocumentGenerationResult(
            format_type="excel",
            filename="test.xlsx",
            success=True,
            file_size_bytes=2048,
            generation_time_seconds=1.5,
            warnings=["Minor formatting issue"],
        )

        self.assertEqual(result.format_type, "excel")
        self.assertEqual(result.filename, "test.xlsx")
        self.assertTrue(result.success)
        self.assertEqual(result.file_size_bytes, 2048)
        self.assertEqual(result.generation_time_seconds, 1.5)
        self.assertEqual(len(result.warnings), 1)
        self.assertIsNone(result.error_message)

    def test_document_generation_result_failure(self):
        """Test DocumentGenerationResult for failure case."""
        result = DocumentGenerationResult(
            format_type="word",
            filename="",
            success=False,
            error_message="Template not found",
        )

        self.assertEqual(result.format_type, "word")
        self.assertEqual(result.filename, "")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Template not found")


class TestDocumentGenerationSummary(unittest.TestCase):
    """Test cases for DocumentGenerationSummary."""

    def test_document_generation_summary_creation(self):
        """Test DocumentGenerationSummary creation."""
        results = [
            DocumentGenerationResult("excel", "test.xlsx", True),
            DocumentGenerationResult("word", "test.docx", False, error_message="Failed"),
        ]

        summary = DocumentGenerationSummary(
            total_formats=2,
            successful_formats=1,
            failed_formats=1,
            results=results,
            total_generation_time=3.5,
            errors=["Word generation failed"],
            warnings=["Excel formatting issue"],
        )

        self.assertEqual(summary.total_formats, 2)
        self.assertEqual(summary.successful_formats, 1)
        self.assertEqual(summary.failed_formats, 1)
        self.assertEqual(len(summary.results), 2)
        self.assertEqual(summary.total_generation_time, 3.5)
        self.assertEqual(len(summary.errors), 1)
        self.assertEqual(len(summary.warnings), 1)


if __name__ == "__main__":
    unittest.main()
