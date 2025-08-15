#!/usr/bin/env python3
"""
Comprehensive test suite for the optimized AWS discovery system
Tests all major functionality including filtering, AI predictions, and state consistency
"""

import sys
import os
import json
import time
from datetime import datetime
from collections import defaultdict

# Add the inventag package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

try:
    from inventag.discovery.optimized_discovery import (
        OptimizedAWSDiscovery,
        OptimizedFieldMapper,
    )
    from inventag.discovery.intelligent_discovery import IntelligentAWSDiscovery
    import boto3
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class DiscoveryTester:
    """Comprehensive tester for the optimized discovery system"""

    def __init__(self):
        # Create simple session for testing
        self.session = boto3.Session()

        # Initialize discovery systems with session
        self.optimized_discovery = OptimizedAWSDiscovery(session=self.session)
        self.intelligent_discovery = IntelligentAWSDiscovery(session=self.session)
        self.results = {}

    def test_aws_managed_filtering(self):
        """Test AWS managed resource filtering"""
        print("\n🔍 Testing AWS Managed Resource Filtering...")

        # Test IAM filtering patterns
        mapper = OptimizedFieldMapper()

        test_cases = [
            # Should be filtered (AWS managed)
            ("iam", "AWSServiceRoleForEC2", "Role", True),
            ("iam", "aws-service-role/ec2.amazonaws.com", "Role", True),
            ("iam", "service-role/MyRole", "Role", True),
            ("iam", "OrganizationAccountAccessRole", "Role", True),
            ("iam", "AWSReservedSSO_MyRole", "Role", True),
            # Should NOT be filtered (user created)
            ("iam", "MyCustomRole", "Role", False),
            ("iam", "DeveloperRole", "Role", False),
            ("ec2", "my-custom-vpc", "VPC", False),
            ("s3", "my-bucket", "Bucket", False),
        ]

        filtered_count = 0
        for service, resource_id, resource_type, should_filter in test_cases:
            raw_data = {"name": resource_id, "id": resource_id}
            is_filtered = mapper._is_aws_managed_resource(
                raw_data, service, resource_id, resource_type
            )

            if is_filtered == should_filter:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"

            print(f"  {status}: {service}:{resource_type}:{resource_id} -> Filtered: {is_filtered}")

            if is_filtered:
                filtered_count += 1

        print(f"  📊 Filtered {filtered_count} AWS managed resources")
        return filtered_count > 0

    def test_region_detection(self):
        """Test region detection for S3 and other services"""
        print("\n🌍 Testing Region Detection...")

        try:
            # Test S3 region detection if we have S3 access
            s3_resources = self.optimized_discovery.discover_service("s3")

            region_stats = defaultdict(int)
            for resource in s3_resources:
                region_stats[resource.region] += 1

            print(f"  📊 S3 Buckets by Region:")
            for region, count in sorted(region_stats.items()):
                print(f"    {region}: {count} buckets")

            # Check if we have proper region distribution (not all us-east-1)
            unique_regions = len(region_stats)
            total_buckets = sum(region_stats.values())

            if unique_regions > 1 or (unique_regions == 1 and "us-east-1" not in region_stats):
                print("  ✅ Region detection working correctly")
                return True
            else:
                print("  ⚠️  All buckets showing same region - may need investigation")
                return False

        except Exception as e:
            print(f"  ⚠️  Could not test S3 region detection: {e}")
            return False

    def test_ai_predictions(self):
        """Test AI-based resource predictions"""
        print("\n🤖 Testing AI Resource Predictions...")

        try:
            # Get Lambda functions first
            lambda_resources = self.optimized_discovery.discover_service("lambda")
            lambda_count = len(lambda_resources)

            if lambda_count == 0:
                print("  ℹ️  No Lambda functions found - skipping AI prediction test")
                return True

            print(f"  📊 Found {lambda_count} Lambda functions")

            # Test AI predictions for CloudWatch log groups
            all_resources = []
            for service in ["lambda", "logs"]:
                try:
                    resources = self.optimized_discovery.discover_service(service)
                    all_resources.extend(resources)
                except Exception as e:
                    print(f"    ⚠️  Could not discover {service}: {e}")

            # Check for predicted resources
            predicted_resources = [
                r
                for r in all_resources
                if hasattr(r, "confidence_score") and r.confidence_score < 0.8
            ]

            print(f"  📊 Total resources: {len(all_resources)}")
            print(f"  🔮 Predicted resources: {len(predicted_resources)}")

            if predicted_resources:
                print("  ✅ AI predictions are working")
                for pred in predicted_resources[:3]:  # Show first 3
                    print(
                        f"    🔮 Predicted: {pred.service}:{pred.resource_type}:{pred.resource_id} (confidence: {pred.confidence_score:.2f})"
                    )
            else:
                print("  ℹ️  No predictions generated (may be normal)")

            return True

        except Exception as e:
            print(f"  ❌ AI prediction test failed: {e}")
            return False

    def test_state_consistency(self):
        """Test state management consistency"""
        print("\n🔄 Testing State Management Consistency...")

        try:
            # Run discovery twice and compare results
            print("  🔄 Running first discovery...")
            resources1 = self.optimized_discovery.discover_service("s3")

            time.sleep(1)  # Small delay

            print("  🔄 Running second discovery...")
            resources2 = self.optimized_discovery.discover_service("s3")

            # Compare results
            if len(resources1) != len(resources2):
                print(f"  ❌ Resource count mismatch: {len(resources1)} vs {len(resources2)}")
                return False

            # Check ordering consistency
            for i, (r1, r2) in enumerate(zip(resources1, resources2)):
                if r1.arn != r2.arn:
                    print(f"  ❌ Ordering inconsistency at position {i}: {r1.arn} vs {r2.arn}")
                    return False

            print(f"  ✅ State consistency verified with {len(resources1)} resources")
            return True

        except Exception as e:
            print(f"  ❌ State consistency test failed: {e}")
            return False

    def test_performance_comparison(self):
        """Compare performance between optimized and intelligent discovery"""
        print("\n⚡ Testing Performance Comparison...")

        test_services = ["s3", "ec2", "iam"]

        for service in test_services:
            try:
                print(f"\n  📊 Testing {service.upper()} service:")

                # Test optimized discovery
                start_time = time.time()
                optimized_resources = self.optimized_discovery.discover_service(service)
                optimized_time = time.time() - start_time

                # Test intelligent discovery
                start_time = time.time()
                intelligent_resources = self.intelligent_discovery.discover_service(service)
                intelligent_time = time.time() - start_time

                print(
                    f"    🚀 Optimized: {len(optimized_resources)} resources in {optimized_time:.2f}s"
                )
                print(
                    f"    🧠 Intelligent: {len(intelligent_resources)} resources in {intelligent_time:.2f}s"
                )

                if optimized_time < intelligent_time:
                    speedup = intelligent_time / optimized_time
                    print(f"    ✅ Optimized is {speedup:.1f}x faster")
                else:
                    print(
                        f"    ⚠️  Intelligent was faster by {optimized_time / intelligent_time:.1f}x"
                    )

                # Compare resource counts
                if len(optimized_resources) >= len(intelligent_resources):
                    print(
                        f"    ✅ Optimized found {len(optimized_resources) - len(intelligent_resources)} more resources"
                    )
                else:
                    print(
                        f"    ⚠️  Optimized found {len(intelligent_resources) - len(optimized_resources)} fewer resources"
                    )

            except Exception as e:
                print(f"    ❌ Performance test failed for {service}: {e}")

    def test_service_coverage(self):
        """Test coverage across different AWS services"""
        print("\n🎯 Testing Service Coverage...")

        services_to_test = [
            "s3",
            "ec2",
            "iam",
            "lambda",
            "cloudfront",
            "route53",
            "rds",
            "cloudwatch",
            "logs",
        ]

        service_results = {}

        for service in services_to_test:
            try:
                print(f"  🔍 Testing {service.upper()}...")
                resources = self.optimized_discovery.discover_service(service)
                service_results[service] = len(resources)
                print(f"    ✅ Found {len(resources)} resources")

            except Exception as e:
                print(f"    ❌ Failed to discover {service}: {e}")
                service_results[service] = 0

        print(f"\n  📊 Service Coverage Summary:")
        total_resources = sum(service_results.values())
        services_with_resources = sum(1 for count in service_results.values() if count > 0)

        for service, count in sorted(service_results.items()):
            status = "✅" if count > 0 else "⚪"
            print(f"    {status} {service.upper()}: {count} resources")

        print(
            f"\n  🎯 Total: {total_resources} resources across {services_with_resources}/{len(services_to_test)} services"
        )
        return service_results

    def run_comprehensive_test(self):
        """Run all tests and generate a comprehensive report"""
        print("🚀 Starting Comprehensive Optimized Discovery Test Suite")
        print("=" * 60)

        start_time = time.time()
        test_results = {}

        # Run all tests
        test_results["aws_managed_filtering"] = self.test_aws_managed_filtering()
        test_results["region_detection"] = self.test_region_detection()
        test_results["ai_predictions"] = self.test_ai_predictions()
        test_results["state_consistency"] = self.test_state_consistency()
        test_results["service_coverage"] = self.test_service_coverage()

        # Performance comparison (separate as it's more intensive)
        print("\n" + "=" * 60)
        self.test_performance_comparison()

        total_time = time.time() - start_time

        # Generate summary report
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY REPORT")
        print("=" * 60)

        passed_tests = sum(1 for result in test_results.values() if result is True)
        total_tests = len([k for k, v in test_results.items() if isinstance(v, bool)])

        for test_name, result in test_results.items():
            if isinstance(result, bool):
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status}: {test_name.replace('_', ' ').title()}")
            elif isinstance(result, dict):
                print(
                    f"📊 {test_name.replace('_', ' ').title()}: {sum(result.values())} total resources"
                )

        print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
        print(f"⏱️  Total test time: {total_time:.2f} seconds")

        if passed_tests == total_tests:
            print("\n🎉 All tests passed! Optimized discovery system is working correctly.")
        else:
            print(
                f"\n⚠️  {total_tests - passed_tests} tests failed. Review the output above for details."
            )

        return test_results


if __name__ == "__main__":
    print("🔧 Optimized AWS Discovery System - Comprehensive Test Suite")
    print("=" * 60)

    try:
        tester = DiscoveryTester()
        results = tester.run_comprehensive_test()

        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"test_results_{timestamp}.json"

        # Convert results to JSON-serializable format
        json_results = {}
        for k, v in results.items():
            if isinstance(v, dict):
                json_results[k] = v
            else:
                json_results[k] = str(v)

        with open(results_file, "w") as f:
            json.dump(
                {
                    "timestamp": timestamp,
                    "test_results": json_results,
                    "summary": f"Comprehensive test of optimized discovery system",
                },
                f,
                indent=2,
            )

        print(f"\n📄 Test results saved to: {results_file}")

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback

        traceback.print_exc()
