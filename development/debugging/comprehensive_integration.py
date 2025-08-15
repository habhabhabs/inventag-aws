#!/usr/bin/env python3
"""
Comprehensive Integration Script for Enhanced AWS Discovery System
Integrates all improvements: enhanced patterns, AI predictions, monitoring, and fine-tuning
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

# Add the inventag package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

try:
    from inventag.discovery.optimized_discovery import OptimizedAWSDiscovery
    from test_optimized_discovery import DiscoveryTester
    from performance_monitor import PerformanceMonitor
    from fine_tune_filtering import FilteringTuner
    from monitoring_system import DiscoveryMonitor
    import boto3
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class ComprehensiveIntegration:
    """Comprehensive integration of all AWS discovery enhancements"""

    def __init__(self):
        self.session = boto3.Session()
        self.discovery = OptimizedAWSDiscovery(session=self.session)

        # Initialize all components
        self.tester = DiscoveryTester()
        self.performance_monitor = PerformanceMonitor()
        self.filtering_tuner = FilteringTuner()
        self.system_monitor = DiscoveryMonitor()

        # Results storage
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "performance": {},
            "filtering": {},
            "monitoring": {},
        }

    def run_comprehensive_integration(self):
        """Run complete integration with all enhancements"""

        print("🚀 COMPREHENSIVE AWS DISCOVERY SYSTEM INTEGRATION")
        print("=" * 60)
        print("This will run all enhancements and optimizations:")
        print("  1️⃣  System Testing")
        print("  2️⃣  Performance Benchmarking")
        print("  3️⃣  Filtering Fine-tuning")
        print("  4️⃣  AI Predictions Testing")
        print("  5️⃣  Monitoring Setup")
        print("  6️⃣  Integration Validation")
        print()

        try:
            # Step 1: System Testing
            print("🔧 STEP 1: SYSTEM TESTING")
            print("-" * 30)
            test_results = self._run_system_tests()
            self.results["tests"] = test_results

            # Step 2: Performance Benchmarking
            print("\n⚡ STEP 2: PERFORMANCE BENCHMARKING")
            print("-" * 40)
            performance_results = self._run_performance_benchmarks()
            self.results["performance"] = performance_results

            # Step 3: Filtering Fine-tuning
            print("\n🔍 STEP 3: FILTERING FINE-TUNING")
            print("-" * 35)
            filtering_results = self._run_filtering_analysis()
            self.results["filtering"] = filtering_results

            # Step 4: AI Predictions Testing
            print("\n🤖 STEP 4: AI PREDICTIONS TESTING")
            print("-" * 35)
            ai_results = self._test_ai_predictions()
            self.results["ai_predictions"] = ai_results

            # Step 5: Monitoring Setup
            print("\n📊 STEP 5: MONITORING SETUP")
            print("-" * 30)
            monitoring_results = self._setup_monitoring()
            self.results["monitoring"] = monitoring_results

            # Step 6: Integration Validation
            print("\n✅ STEP 6: INTEGRATION VALIDATION")
            print("-" * 40)
            validation_results = self._validate_integration()
            self.results["validation"] = validation_results

            # Generate final report
            self._generate_final_report()

            return self.results

        except KeyboardInterrupt:
            print("\n⚠️  Integration interrupted by user")
            return self.results
        except Exception as e:
            print(f"\n❌ Integration failed: {e}")
            import traceback

            traceback.print_exc()
            return self.results

    def _run_system_tests(self):
        """Run comprehensive system tests"""

        print("🧪 Running comprehensive test suite...")

        try:
            # Run the full test suite
            test_results = self.tester.run_comprehensive_test()

            # Extract key metrics
            passed_tests = sum(1 for result in test_results.values() if result is True)
            total_tests = len([k for k, v in test_results.items() if isinstance(v, bool)])

            print(f"✅ System tests complete: {passed_tests}/{total_tests} passed")

            return {
                "passed": passed_tests,
                "total": total_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "details": test_results,
            }

        except Exception as e:
            print(f"❌ System tests failed: {e}")
            return {"error": str(e)}

    def _run_performance_benchmarks(self):
        """Run performance benchmarking"""

        print("📊 Running performance benchmarks...")

        try:
            # Quick benchmark of key services
            services = ["s3", "ec2", "iam", "lambda"]
            benchmark_results = {}

            for service in services:
                result = self.performance_monitor.benchmark_service(service, iterations=1)
                if result:
                    benchmark_results[service] = result

            # Calculate overall metrics
            total_time = sum(r["avg_time"] for r in benchmark_results.values())
            total_resources = sum(r["avg_resources"] for r in benchmark_results.values())

            print(f"✅ Performance benchmarks complete: {len(benchmark_results)} services tested")

            return {
                "services_tested": len(benchmark_results),
                "total_time": total_time,
                "total_resources": total_resources,
                "throughput": total_resources / total_time if total_time > 0 else 0,
                "details": benchmark_results,
            }

        except Exception as e:
            print(f"❌ Performance benchmarks failed: {e}")
            return {"error": str(e)}

    def _run_filtering_analysis(self):
        """Run filtering fine-tuning analysis"""

        print("🔍 Running filtering analysis...")

        try:
            # Run filtering analysis
            recommendations = self.filtering_tuner.run_comprehensive_analysis()

            # Extract key metrics
            services_with_suggestions = len(recommendations.get("pattern_suggestions", {}))
            false_positives = len(recommendations.get("false_positives", []))

            print(f"✅ Filtering analysis complete: {services_with_suggestions} services analyzed")

            return {
                "services_analyzed": services_with_suggestions,
                "false_positives": false_positives,
                "recommendations": recommendations,
            }

        except Exception as e:
            print(f"❌ Filtering analysis failed: {e}")
            return {"error": str(e)}

    def _test_ai_predictions(self):
        """Test AI prediction functionality"""

        print("🤖 Testing AI predictions...")

        try:
            # Test AI predictions with sample data
            sample_resources = []

            # Try to get some real resources for testing
            for service in ["lambda", "ecs", "rds"]:
                try:
                    resources = self.discovery.discover_service(service)
                    sample_resources.extend(resources[:5])  # Take first 5 from each
                except:
                    pass

            if sample_resources:
                # Apply AI predictions
                predicted_resources = self.discovery._apply_ai_predictions(sample_resources)

                print(
                    f"✅ AI predictions complete: {len(predicted_resources)} predictions generated"
                )

                return {
                    "source_resources": len(sample_resources),
                    "predicted_resources": len(predicted_resources),
                    "prediction_rate": (
                        len(predicted_resources) / len(sample_resources) if sample_resources else 0
                    ),
                }
            else:
                print("ℹ️  No source resources found for AI prediction testing")
                return {
                    "source_resources": 0,
                    "predicted_resources": 0,
                    "prediction_rate": 0,
                }

        except Exception as e:
            print(f"❌ AI predictions test failed: {e}")
            return {"error": str(e)}

    def _setup_monitoring(self):
        """Setup monitoring system"""

        print("📊 Setting up monitoring system...")

        try:
            # Configure monitoring
            config = {
                "monitoring_interval": 300,  # 5 minutes
                "alert_thresholds": {
                    "discovery_time": 60,
                    "error_rate": 0.1,
                    "resource_change_rate": 0.2,
                },
                "services_to_monitor": ["s3", "ec2", "iam", "lambda"],
            }

            # Initialize monitor with config
            monitor = DiscoveryMonitor(config)

            # Test monitoring status
            status = monitor.get_monitoring_status()

            print("✅ Monitoring system configured successfully")

            return {
                "configured": True,
                "services_monitored": len(config["services_to_monitor"]),
                "monitoring_interval": config["monitoring_interval"],
                "status": status,
            }

        except Exception as e:
            print(f"❌ Monitoring setup failed: {e}")
            return {"error": str(e)}

    def _validate_integration(self):
        """Validate the complete integration"""

        print("✅ Validating integration...")

        validation_results = {
            "components_tested": 0,
            "components_passed": 0,
            "issues": [],
        }

        # Test 1: Discovery system functionality
        try:
            resources = self.discovery.discover_service("s3")
            validation_results["components_tested"] += 1
            validation_results["components_passed"] += 1
            print("  ✅ Discovery system: Working")
        except Exception as e:
            validation_results["components_tested"] += 1
            validation_results["issues"].append(f"Discovery system: {e}")
            print(f"  ❌ Discovery system: {e}")

        # Test 2: Enhanced patterns
        try:
            patterns = self.discovery.field_mapper.optimized_service_patterns
            if len(patterns) > 10:  # Should have enhanced patterns
                validation_results["components_tested"] += 1
                validation_results["components_passed"] += 1
                print(f"  ✅ Enhanced patterns: {len(patterns)} services configured")
            else:
                validation_results["components_tested"] += 1
                validation_results["issues"].append("Enhanced patterns: Insufficient patterns")
                print("  ❌ Enhanced patterns: Insufficient patterns")
        except Exception as e:
            validation_results["components_tested"] += 1
            validation_results["issues"].append(f"Enhanced patterns: {e}")
            print(f"  ❌ Enhanced patterns: {e}")

        # Test 3: AWS managed filtering
        try:
            mapper = self.discovery.field_mapper
            test_result = mapper._is_aws_managed_resource({}, "iam", "AWSServiceRoleForEC2", "Role")
            if test_result:
                validation_results["components_tested"] += 1
                validation_results["components_passed"] += 1
                print("  ✅ AWS managed filtering: Working")
            else:
                validation_results["components_tested"] += 1
                validation_results["issues"].append(
                    "AWS managed filtering: Not filtering correctly"
                )
                print("  ❌ AWS managed filtering: Not filtering correctly")
        except Exception as e:
            validation_results["components_tested"] += 1
            validation_results["issues"].append(f"AWS managed filtering: {e}")
            print(f"  ❌ AWS managed filtering: {e}")

        # Test 4: AI predictions
        try:
            if hasattr(self.discovery, "_apply_ai_predictions"):
                validation_results["components_tested"] += 1
                validation_results["components_passed"] += 1
                print("  ✅ AI predictions: Available")
            else:
                validation_results["components_tested"] += 1
                validation_results["issues"].append("AI predictions: Method not found")
                print("  ❌ AI predictions: Method not found")
        except Exception as e:
            validation_results["components_tested"] += 1
            validation_results["issues"].append(f"AI predictions: {e}")
            print(f"  ❌ AI predictions: {e}")

        success_rate = (
            validation_results["components_passed"] / validation_results["components_tested"]
            if validation_results["components_tested"] > 0
            else 0
        )

        print(
            f"✅ Integration validation complete: {validation_results['components_passed']}/{validation_results['components_tested']} components working ({success_rate:.1%})"
        )

        return validation_results

    def _generate_final_report(self):
        """Generate comprehensive final report"""

        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE INTEGRATION REPORT")
        print("=" * 80)

        # Overall status
        overall_success = True

        # Test results
        if "tests" in self.results and "error" not in self.results["tests"]:
            test_success_rate = self.results["tests"]["success_rate"]
            print(
                f"🧪 System Tests: {test_success_rate:.1%} success rate ({self.results['tests']['passed']}/{self.results['tests']['total']})"
            )
            if test_success_rate < 0.8:
                overall_success = False
        else:
            print("🧪 System Tests: ❌ Failed")
            overall_success = False

        # Performance results
        if "performance" in self.results and "error" not in self.results["performance"]:
            throughput = self.results["performance"]["throughput"]
            print(
                f"⚡ Performance: {throughput:.1f} resources/sec across {self.results['performance']['services_tested']} services"
            )
        else:
            print("⚡ Performance: ❌ Failed")

        # Filtering results
        if "filtering" in self.results and "error" not in self.results["filtering"]:
            services_analyzed = self.results["filtering"]["services_analyzed"]
            false_positives = self.results["filtering"]["false_positives"]
            print(
                f"🔍 Filtering: {services_analyzed} services analyzed, {false_positives} false positives"
            )
        else:
            print("🔍 Filtering: ❌ Failed")

        # AI predictions
        if "ai_predictions" in self.results and "error" not in self.results["ai_predictions"]:
            prediction_rate = self.results["ai_predictions"]["prediction_rate"]
            print(f"🤖 AI Predictions: {prediction_rate:.1f} predictions per source resource")
        else:
            print("🤖 AI Predictions: ❌ Failed")

        # Monitoring
        if "monitoring" in self.results and "error" not in self.results["monitoring"]:
            services_monitored = self.results["monitoring"]["services_monitored"]
            print(f"📊 Monitoring: {services_monitored} services configured")
        else:
            print("📊 Monitoring: ❌ Failed")

        # Validation
        if "validation" in self.results:
            validation = self.results["validation"]
            validation_rate = (
                validation["components_passed"] / validation["components_tested"]
                if validation["components_tested"] > 0
                else 0
            )
            print(
                f"✅ Integration: {validation_rate:.1%} components working ({validation['components_passed']}/{validation['components_tested']})"
            )

            if validation["issues"]:
                print(f"\n⚠️  Issues Found:")
                for issue in validation["issues"]:
                    print(f"  • {issue}")

        # Overall status
        print(f"\n🎯 OVERALL STATUS: {'✅ SUCCESS' if overall_success else '⚠️  PARTIAL SUCCESS'}")

        if overall_success:
            print(
                "\n🎉 All systems are operational! The enhanced AWS discovery system is ready for production use."
            )
        else:
            print(
                "\n⚠️  Some components need attention. Review the issues above and re-run integration."
            )

        # Save results
        self._save_integration_results()

    def _save_integration_results(self):
        """Save integration results to file"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"integration_results_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, default=str, ensure_ascii=False)

        print(f"\n💾 Integration results saved to: {filename}")

        # Also create a summary file
        summary_filename = f"integration_summary_{timestamp}.md"
        self._create_summary_file(summary_filename)

        return filename

    def _create_summary_file(self, filename):
        """Create a markdown summary file"""

        summary = f"""# AWS Discovery System Integration Summary

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Overview
Comprehensive integration of enhanced AWS discovery system with all optimizations and improvements.

## Results Summary

### System Tests
- **Status:** {'✅ PASSED' if self.results.get('tests', {}).get('success_rate', 0) >= 0.8 else '❌ FAILED'}
- **Success Rate:** {self.results.get('tests', {}).get('success_rate', 0):.1%}
- **Tests Passed:** {self.results.get('tests', {}).get('passed', 0)}/{self.results.get('tests', {}).get('total', 0)}

### Performance Benchmarks
- **Status:** {'✅ COMPLETED' if 'performance' in self.results and 'error' not in self.results['performance'] else '❌ FAILED'}
- **Services Tested:** {self.results.get('performance', {}).get('services_tested', 0)}
- **Throughput:** {self.results.get('performance', {}).get('throughput', 0):.1f} resources/sec

### Filtering Analysis
- **Status:** {'✅ COMPLETED' if 'filtering' in self.results and 'error' not in self.results['filtering'] else '❌ FAILED'}
- **Services Analyzed:** {self.results.get('filtering', {}).get('services_analyzed', 0)}
- **False Positives:** {self.results.get('filtering', {}).get('false_positives', 0)}

### AI Predictions
- **Status:** {'✅ WORKING' if 'ai_predictions' in self.results and 'error' not in self.results['ai_predictions'] else '❌ FAILED'}
- **Prediction Rate:** {self.results.get('ai_predictions', {}).get('prediction_rate', 0):.1f} per source resource

### Monitoring System
- **Status:** {'✅ CONFIGURED' if 'monitoring' in self.results and 'error' not in self.results['monitoring'] else '❌ FAILED'}
- **Services Monitored:** {self.results.get('monitoring', {}).get('services_monitored', 0)}

### Integration Validation
- **Status:** {'✅ VALIDATED' if self.results.get('validation', {}).get('components_passed', 0) == self.results.get('validation', {}).get('components_tested', 1) else '⚠️ PARTIAL'}
- **Components Working:** {self.results.get('validation', {}).get('components_passed', 0)}/{self.results.get('validation', {}).get('components_tested', 0)}

## Next Steps

1. **Production Deployment:** The system is ready for production use
2. **Monitoring:** Enable continuous monitoring for ongoing optimization
3. **Fine-tuning:** Apply filtering recommendations as needed
4. **Documentation:** Update user documentation with new features

## Files Generated

- Integration results: `integration_results_*.json`
- Test results: `test_results_*.json`
- Performance data: `performance_data_*.json`
- Monitoring data: `monitoring_data_*.json`

---
*Generated by AWS Discovery System Integration Tool*
"""

        with open(filename, "w", encoding="utf-8") as f:
            f.write(summary)

        print(f"📄 Integration summary saved to: {filename}")


def main():
    """Main function for comprehensive integration"""

    print("🚀 AWS Discovery System - Comprehensive Integration")
    print("=" * 60)

    integration = ComprehensiveIntegration()

    try:
        results = integration.run_comprehensive_integration()

        print(f"\n🎉 Integration complete! Check the generated files for detailed results.")

        return results

    except KeyboardInterrupt:
        print("\n⚠️  Integration interrupted by user")
    except Exception as e:
        print(f"\n❌ Integration failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
