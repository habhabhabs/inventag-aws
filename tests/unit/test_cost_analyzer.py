#!/usr/bin/env python3
"""
Unit tests for CostAnalyzer

Tests for cost analysis capabilities including:
- Resource cost estimation using AWS Pricing API
- Expensive resource identification with configurable thresholds
- Forgotten resource detection based on activity patterns
- Cost trend analysis and alerting functionality
- Cost optimization recommendations based on resource utilization
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import boto3

# Import the classes to test
from inventag.discovery.cost_analyzer import (
    CostAnalyzer,
    CostThresholds,
    ResourceCostEstimate,
    ForgottenResourceAnalysis,
    CostOptimizationRecommendation,
    CostTrendAnalysis,
    CostAnalysisSummary,
)


class TestCostThresholds(unittest.TestCase):
    """Test CostThresholds dataclass."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = CostThresholds()

        self.assertEqual(thresholds.expensive_resource_monthly_threshold, Decimal("100.00"))
        self.assertEqual(thresholds.forgotten_resource_days_threshold, 30)
        self.assertEqual(thresholds.high_cost_alert_threshold, Decimal("1000.00"))
        self.assertEqual(thresholds.cost_trend_alert_percentage, 50.0)
        self.assertEqual(thresholds.unused_resource_utilization_threshold, 5.0)

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = CostThresholds(
            expensive_resource_monthly_threshold=Decimal("200.00"),
            forgotten_resource_days_threshold=60,
            high_cost_alert_threshold=Decimal("2000.00"),
            cost_trend_alert_percentage=25.0,
            unused_resource_utilization_threshold=10.0,
        )

        self.assertEqual(thresholds.expensive_resource_monthly_threshold, Decimal("200.00"))
        self.assertEqual(thresholds.forgotten_resource_days_threshold, 60)
        self.assertEqual(thresholds.high_cost_alert_threshold, Decimal("2000.00"))
        self.assertEqual(thresholds.cost_trend_alert_percentage, 25.0)
        self.assertEqual(thresholds.unused_resource_utilization_threshold, 10.0)


class TestResourceCostEstimate(unittest.TestCase):
    """Test ResourceCostEstimate dataclass."""

    def test_resource_cost_estimate_creation(self):
        """Test creating a ResourceCostEstimate."""
        estimate = ResourceCostEstimate(
            resource_id="i-1234567890abcdef0",
            resource_type="Instance",
            service="EC2",
            region="us-east-1",
            estimated_monthly_cost=Decimal("75.50"),
            cost_breakdown={"compute": Decimal("75.50")},
            pricing_model="on-demand",
            confidence_level="high",
        )

        self.assertEqual(estimate.resource_id, "i-1234567890abcdef0")
        self.assertEqual(estimate.resource_type, "Instance")
        self.assertEqual(estimate.service, "EC2")
        self.assertEqual(estimate.region, "us-east-1")
        self.assertEqual(estimate.estimated_monthly_cost, Decimal("75.50"))
        self.assertEqual(estimate.cost_breakdown["compute"], Decimal("75.50"))
        self.assertEqual(estimate.pricing_model, "on-demand")
        self.assertEqual(estimate.confidence_level, "high")


class TestCostAnalyzer(unittest.TestCase):
    """Test CostAnalyzer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=boto3.Session)
        self.thresholds = CostThresholds(
            expensive_resource_monthly_threshold=Decimal("50.00"),
            forgotten_resource_days_threshold=15,
        )

        # Mock AWS clients
        self.mock_pricing_client = Mock()
        self.mock_cloudwatch_client = Mock()
        self.mock_cost_explorer_client = Mock()

        with patch("boto3.client") as mock_client:
            mock_client.side_effect = self._mock_client_factory
            self.cost_analyzer = CostAnalyzer(self.mock_session, self.thresholds)

    def _mock_client_factory(self, service_name, **kwargs):
        """Factory for creating mock clients."""
        if service_name == "pricing":
            return self.mock_pricing_client
        elif service_name == "cloudwatch":
            return self.mock_cloudwatch_client
        elif service_name == "ce":
            return self.mock_cost_explorer_client
        else:
            return Mock()

    def test_initialization(self):
        """Test CostAnalyzer initialization."""
        self.assertIsNotNone(self.cost_analyzer)
        self.assertEqual(self.cost_analyzer.thresholds, self.thresholds)
        self.assertEqual(self.cost_analyzer.session, self.mock_session)

    def test_map_service_to_pricing_code(self):
        """Test service name to pricing code mapping."""
        test_cases = [
            ("EC2", "AmazonEC2"),
            ("S3", "AmazonS3"),
            ("RDS", "AmazonRDS"),
            ("LAMBDA", "AWSLambda"),
            ("UNKNOWN", None),
        ]

        for service, expected_code in test_cases:
            with self.subTest(service=service):
                result = self.cost_analyzer._map_service_to_pricing_code(service)
                self.assertEqual(result, expected_code)

    def test_map_region_to_location(self):
        """Test region code to location name mapping."""
        test_cases = [
            ("us-east-1", "US East (N. Virginia)"),
            ("us-west-2", "US West (Oregon)"),
            ("eu-west-1", "Europe (Ireland)"),
            ("unknown-region", "unknown-region"),
        ]

        for region, expected_location in test_cases:
            with self.subTest(region=region):
                result = self.cost_analyzer._map_region_to_location(region)
                self.assertEqual(result, expected_location)

    def test_build_ec2_filters(self):
        """Test building EC2-specific pricing filters."""
        resource = {"instance_type": "t3.medium", "volume_type": "gp3"}

        # Test instance filters
        filters = self.cost_analyzer._build_ec2_filters("Instance", resource)

        expected_filters = [
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": "t3.medium"},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "operating-system", "Value": "Linux"},
        ]

        self.assertEqual(filters, expected_filters)

        # Test volume filters
        filters = self.cost_analyzer._build_ec2_filters("Volume", resource)
        expected_filters = [{"Type": "TERM_MATCH", "Field": "volumeType", "Value": "gp3"}]

        self.assertEqual(filters, expected_filters)

    def test_calculate_monthly_cost(self):
        """Test monthly cost calculation."""
        # Test hourly pricing
        pricing_info = {"price_per_unit": Decimal("0.0464"), "unit": "Hrs"}
        resource = {}

        monthly_cost = self.cost_analyzer._calculate_monthly_cost(pricing_info, resource)
        expected_cost = Decimal("0.0464") * Decimal("730")  # 730 hours per month
        self.assertEqual(monthly_cost, expected_cost)

        # Test storage pricing
        pricing_info = {"price_per_unit": Decimal("0.10"), "unit": "GB-Mo"}
        resource = {"size_gb": 100}

        monthly_cost = self.cost_analyzer._calculate_monthly_cost(pricing_info, resource)
        expected_cost = Decimal("0.10") * Decimal("100")
        self.assertEqual(monthly_cost, expected_cost)

    def test_estimate_monthly_requests(self):
        """Test monthly request estimation."""
        test_cases = [
            ({"service": "LAMBDA"}, Decimal("100000")),
            ({"service": "S3"}, Decimal("10000")),
            ({"service": "OTHER"}, Decimal("1000")),
        ]

        for resource, expected_requests in test_cases:
            with self.subTest(resource=resource):
                result = self.cost_analyzer._estimate_monthly_requests(resource)
                self.assertEqual(result, expected_requests)

    def test_determine_confidence_level(self):
        """Test confidence level determination."""
        test_cases = [
            ("EC2", "Instance", {"price_per_unit": Decimal("0.05")}, "high"),
            ("UNKNOWN", "Resource", {"price_per_unit": Decimal("0.05")}, "medium"),
            ("UNKNOWN", "Resource", {"price_per_unit": Decimal("0")}, "low"),
        ]

        for service, resource_type, pricing_info, expected_confidence in test_cases:
            with self.subTest(service=service):
                result = self.cost_analyzer._determine_confidence_level(
                    service, resource_type, pricing_info
                )
                self.assertEqual(result, expected_confidence)

    def test_identify_expensive_resources(self):
        """Test expensive resource identification."""
        cost_estimates = [
            ResourceCostEstimate(
                resource_id="expensive-1",
                resource_type="Instance",
                service="EC2",
                region="us-east-1",
                estimated_monthly_cost=Decimal("100.00"),
            ),
            ResourceCostEstimate(
                resource_id="cheap-1",
                resource_type="Instance",
                service="EC2",
                region="us-east-1",
                estimated_monthly_cost=Decimal("25.00"),
            ),
        ]

        expensive_resources = self.cost_analyzer.identify_expensive_resources(cost_estimates)

        # With threshold of 50.00, only the first resource should be expensive
        self.assertEqual(len(expensive_resources), 1)
        self.assertEqual(expensive_resources[0].resource_id, "expensive-1")

    def test_get_activity_threshold(self):
        """Test activity threshold retrieval."""
        test_cases = [
            ("cpu_utilization", 5.0),
            ("network_activity", 1000000),
            ("database_connections", 1),
            ("s3_requests", 10),
            ("unknown_metric", 0),
        ]

        for metric_name, expected_threshold in test_cases:
            with self.subTest(metric_name=metric_name):
                result = self.cost_analyzer._get_activity_threshold(metric_name)
                self.assertEqual(result, expected_threshold)

    def test_estimate_resource_cost_simple(self):
        """Test simple resource cost estimation."""
        test_cases = [
            ({"service": "EC2", "type": "Instance"}, Decimal("50.00")),
            ({"service": "RDS", "type": "DBInstance"}, Decimal("100.00")),
            ({"service": "S3", "type": "Bucket"}, Decimal("10.00")),
            ({"service": "UNKNOWN", "type": "Unknown"}, Decimal("20.00")),
        ]

        for resource, expected_cost in test_cases:
            with self.subTest(resource=resource):
                result = self.cost_analyzer._estimate_resource_cost_simple(resource)
                self.assertEqual(result, expected_cost)

    def test_determine_forgotten_resource_risk(self):
        """Test forgotten resource risk determination."""
        test_cases = [
            (100, Decimal("150.00"), "high"),
            (70, Decimal("75.00"), "medium"),
            (40, Decimal("25.00"), "low"),
        ]

        for days, cost, expected_risk in test_cases:
            with self.subTest(days=days, cost=cost):
                result = self.cost_analyzer._determine_forgotten_resource_risk(days, cost)
                self.assertEqual(result, expected_risk)

    def test_generate_forgotten_resource_recommendations(self):
        """Test forgotten resource recommendation generation."""
        recommendations = self.cost_analyzer._generate_forgotten_resource_recommendations(
            "EC2", "Instance", 95, Decimal("120.00")
        )

        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)

        # Check for specific recommendations
        rec_text = " ".join(recommendations)
        self.assertIn("90 days", rec_text)
        self.assertIn("High cost", rec_text)
        self.assertIn("stopping", rec_text)  # EC2-specific recommendation

    @patch("inventag.discovery.cost_analyzer.CostAnalyzer._get_pricing_info")
    def test_estimate_single_resource_cost(self, mock_get_pricing):
        """Test single resource cost estimation."""
        # Mock pricing info
        mock_get_pricing.return_value = {
            "price_per_unit": Decimal("0.0464"),
            "unit": "Hrs",
            "pricing_model": "on-demand",
            "cost_factors": {},
        }

        resource = {
            "service": "EC2",
            "type": "Instance",
            "id": "i-1234567890abcdef0",
            "region": "us-east-1",
        }

        result = self.cost_analyzer._estimate_single_resource_cost(resource)

        self.assertIsNotNone(result)
        self.assertEqual(result.resource_id, "i-1234567890abcdef0")
        self.assertEqual(result.service, "EC2")
        self.assertEqual(result.confidence_level, "high")

    def test_calculate_days_since_activity(self):
        """Test days since activity calculation."""
        # Mock activity indicators with recent activity
        recent_timestamp = datetime.now(timezone.utc) - timedelta(days=5)
        activity_indicators = {
            "cpu_utilization": [{"Timestamp": recent_timestamp, "Average": 10.0}]
        }

        days = self.cost_analyzer._calculate_days_since_activity(activity_indicators)
        self.assertEqual(days, 5)

        # Test with no significant activity
        activity_indicators = {
            "cpu_utilization": [{"Timestamp": recent_timestamp, "Average": 1.0}]  # Below threshold
        }

        days = self.cost_analyzer._calculate_days_since_activity(activity_indicators)
        self.assertGreater(days, self.thresholds.forgotten_resource_days_threshold)

    def test_generate_cost_analysis_summary(self):
        """Test cost analysis summary generation."""
        cost_estimates = [
            ResourceCostEstimate(
                resource_id="resource-1",
                resource_type="Instance",
                service="EC2",
                region="us-east-1",
                estimated_monthly_cost=Decimal("100.00"),
            ),
            ResourceCostEstimate(
                resource_id="resource-2",
                resource_type="Bucket",
                service="S3",
                region="us-east-1",
                estimated_monthly_cost=Decimal("25.00"),
            ),
        ]

        forgotten_resources = [
            ForgottenResourceAnalysis(
                resource_id="forgotten-1",
                resource_type="Instance",
                service="EC2",
                days_since_last_activity=45,
                estimated_monthly_cost=Decimal("75.00"),
                risk_level="high",
            )
        ]

        recommendations = [
            CostOptimizationRecommendation(
                resource_id="resource-1",
                resource_type="Instance",
                service="EC2",
                recommendation_type="rightsizing",
                current_monthly_cost=Decimal("100.00"),
                potential_monthly_savings=Decimal("30.00"),
                confidence_level="medium",
                implementation_effort="medium",
                description="Consider rightsizing",
            )
        ]

        summary = self.cost_analyzer.generate_cost_analysis_summary(
            cost_estimates, forgotten_resources, recommendations
        )

        self.assertEqual(summary.total_estimated_monthly_cost, Decimal("125.00"))
        self.assertEqual(
            summary.expensive_resources_count, 1
        )  # Only resource-1 is expensive (>50.00)
        self.assertEqual(summary.forgotten_resources_count, 1)
        self.assertEqual(summary.total_potential_savings, Decimal("30.00"))
        self.assertEqual(len(summary.high_risk_resources), 1)
        self.assertEqual(summary.cost_by_service["EC2"], Decimal("100.00"))
        self.assertEqual(summary.cost_by_service["S3"], Decimal("25.00"))
        self.assertEqual(summary.optimization_opportunities, 1)

    def test_enrich_resource_with_cost_info(self):
        """Test resource enrichment with cost information."""
        with patch.object(self.cost_analyzer, "_estimate_single_resource_cost") as mock_estimate:
            mock_estimate.return_value = ResourceCostEstimate(
                resource_id="test-resource",
                resource_type="Instance",
                service="EC2",
                region="us-east-1",
                estimated_monthly_cost=Decimal("75.00"),
                confidence_level="high",
            )

            with patch.object(self.cost_analyzer, "_analyze_resource_activity") as mock_activity:
                mock_activity.return_value = ForgottenResourceAnalysis(
                    resource_id="test-resource",
                    resource_type="Instance",
                    service="EC2",
                    days_since_last_activity=20,
                    estimated_monthly_cost=Decimal("75.00"),
                    risk_level="medium",
                    recommendations=["Review usage"],
                )

                resource = {
                    "id": "test-resource",
                    "service": "EC2",
                    "type": "Instance",
                    "region": "us-east-1",
                }

                enriched = self.cost_analyzer.enrich_resource_with_cost_info(resource)

                self.assertIn("cost_analysis", enriched)
                self.assertIn("forgotten_analysis", enriched)

                cost_info = enriched["cost_analysis"]
                self.assertEqual(cost_info["estimated_monthly_cost"], 75.00)
                self.assertEqual(cost_info["confidence_level"], "high")
                self.assertTrue(cost_info["is_expensive"])  # 75.00 > 50.00 threshold

                forgotten_info = enriched["forgotten_analysis"]
                self.assertEqual(forgotten_info["days_since_last_activity"], 20)
                self.assertEqual(forgotten_info["risk_level"], "medium")
                self.assertTrue(forgotten_info["is_potentially_forgotten"])  # 20 > 15 threshold


if __name__ == "__main__":
    unittest.main()
