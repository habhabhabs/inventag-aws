#!/usr/bin/env python3
"""
Fine-tuning script for AWS managed resource filtering
Analyzes discovered resources and suggests improvements to filtering patterns
"""

import sys
import os
import json
import re
from collections import defaultdict, Counter
from datetime import datetime

# Add the inventag package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

try:
    from inventag.discovery.optimized_discovery import (
        OptimizedAWSDiscovery,
        OptimizedFieldMapper,
    )
    import boto3
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class FilteringTuner:
    """Fine-tuning system for AWS managed resource filtering"""

    def __init__(self):
        self.session = boto3.Session()
        self.discovery = OptimizedAWSDiscovery(session=self.session)
        self.field_mapper = OptimizedFieldMapper()

        # Analysis results
        self.resource_analysis = defaultdict(list)
        self.pattern_suggestions = defaultdict(list)
        self.false_positives = []  # User resources incorrectly filtered
        self.false_negatives = []  # AWS managed resources not filtered

    def analyze_discovered_resources(self, services=None):
        """Analyze discovered resources to identify filtering issues"""

        if services is None:
            services = ["iam", "ec2", "s3", "lambda", "rds", "ecs", "eks"]

        print("🔍 Analyzing discovered resources for filtering patterns...")

        all_resources = []

        for service in services:
            try:
                print(f"  📊 Analyzing {service.upper()}...")
                resources = self.discovery.discover_service(service)

                for resource in resources:
                    # Analyze resource patterns
                    self._analyze_resource_patterns(resource)
                    all_resources.append(resource)

                print(f"    Found {len(resources)} resources")

            except Exception as e:
                print(f"    ❌ Error analyzing {service}: {e}")

        print(f"\n📊 Analysis complete: {len(all_resources)} total resources analyzed")
        return all_resources

    def _analyze_resource_patterns(self, resource):
        """Analyze individual resource patterns"""

        service = resource.service_name.lower()
        resource_id = resource.resource_id
        resource_type = resource.resource_type

        # Store resource info for analysis
        self.resource_analysis[service].append(
            {
                "id": resource_id,
                "type": resource_type,
                "name": resource.resource_name,
                "arn": resource.arn,
                "confidence": resource.confidence_score,
                "tags": resource.tags,
            }
        )

        # Check for potential AWS managed patterns
        self._check_aws_managed_patterns(service, resource_id, resource_type)

        # Check for potential user-created patterns
        self._check_user_created_patterns(service, resource_id, resource_type)

    def _check_aws_managed_patterns(self, service, resource_id, resource_type):
        """Check for potential AWS managed resource patterns"""

        # Common AWS managed patterns across services
        aws_indicators = [
            r"^aws-",
            r"^AWS",
            r"^amazon-",
            r"^Amazon",
            r"ServiceRole",
            r"service-role",
            r"^default",
            r"^Default",
            r"-aws-",
            r"StackSet-",
            r"CloudFormation-",
            r"^ecs-optimized",
            r"^eks-",
            r"^rds-",
            r"^elasticache-",
            r"^lambda-",
            r"Reserved",
            r"Managed",
        ]

        for pattern in aws_indicators:
            if re.search(pattern, resource_id, re.IGNORECASE):
                # Check if this pattern is already covered
                current_patterns = self.field_mapper.aws_managed_patterns.get(service, [])

                if not any(
                    re.search(existing, resource_id, re.IGNORECASE) for existing in current_patterns
                ):
                    self.pattern_suggestions[service].append(
                        {
                            "type": "aws_managed",
                            "pattern": pattern,
                            "resource_id": resource_id,
                            "resource_type": resource_type,
                            "reason": f"Matches AWS managed pattern: {pattern}",
                        }
                    )
                break

    def _check_user_created_patterns(self, service, resource_id, resource_type):
        """Check for potential user-created resource patterns"""

        # Patterns that typically indicate user-created resources
        user_indicators = [
            r"^my-",
            r"^dev-",
            r"^prod-",
            r"^test-",
            r"^staging-",
            r"^demo-",
            r"^app-",
            r"^web-",
            r"^api-",
            r"^db-",
            r"^cache-",
            r"^queue-",
            r"^topic-",
            r"^bucket-",
            r"^function-",
            r"^cluster-",
            r"^project-",
            r"^company-",
            r"^team-",
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}",  # Date patterns
            r"v[0-9]+\.[0-9]+",  # Version patterns
        ]

        for pattern in user_indicators:
            if re.search(pattern, resource_id, re.IGNORECASE):
                # This should NOT be filtered as AWS managed
                current_patterns = self.field_mapper.aws_managed_patterns.get(service, [])

                if any(
                    re.search(existing, resource_id, re.IGNORECASE) for existing in current_patterns
                ):
                    self.false_positives.append(
                        {
                            "service": service,
                            "resource_id": resource_id,
                            "resource_type": resource_type,
                            "pattern": pattern,
                            "reason": f"User-created resource incorrectly filtered by AWS managed pattern",
                        }
                    )
                break

    def generate_filtering_recommendations(self):
        """Generate recommendations for improving filtering patterns"""

        print("\n🔧 FILTERING RECOMMENDATIONS")
        print("=" * 50)

        # Analyze pattern frequency
        pattern_frequency = defaultdict(int)

        for service, suggestions in self.pattern_suggestions.items():
            print(f"\n📊 {service.upper()} Service Recommendations:")

            if not suggestions:
                print("  ✅ No new patterns suggested")
                continue

            # Group by pattern type
            aws_managed_suggestions = [s for s in suggestions if s["type"] == "aws_managed"]

            if aws_managed_suggestions:
                print(f"  🔒 AWS Managed Pattern Suggestions ({len(aws_managed_suggestions)}):")

                # Count pattern frequency
                pattern_counts = Counter(s["pattern"] for s in aws_managed_suggestions)

                for pattern, count in pattern_counts.most_common():
                    print(f"    📈 {pattern} (matches {count} resources)")
                    pattern_frequency[pattern] += count

                    # Show example resources
                    examples = [s for s in aws_managed_suggestions if s["pattern"] == pattern][:3]
                    for example in examples:
                        print(
                            f"      💡 Example: {example['resource_type']}:{example['resource_id']}"
                        )

        # Global pattern recommendations
        print(f"\n🌍 GLOBAL PATTERN RECOMMENDATIONS:")
        if pattern_frequency:
            print("  📈 Most common patterns across all services:")
            for pattern, count in Counter(pattern_frequency).most_common(10):
                print(f"    {pattern}: {count} matches")
        else:
            print("  ✅ No global patterns identified")

        # False positive warnings
        if self.false_positives:
            print(f"\n⚠️  FALSE POSITIVE WARNINGS ({len(self.false_positives)}):")
            print("  These user-created resources may be incorrectly filtered:")

            for fp in self.false_positives[:10]:  # Show first 10
                print(f"    🚨 {fp['service']}:{fp['resource_type']}:{fp['resource_id']}")
                print(f"       Reason: {fp['reason']}")
        else:
            print(f"\n✅ No false positives detected")

        return {
            "pattern_suggestions": dict(self.pattern_suggestions),
            "pattern_frequency": dict(pattern_frequency),
            "false_positives": self.false_positives,
        }

    def apply_recommended_patterns(self, recommendations, dry_run=True):
        """Apply recommended filtering patterns"""

        if dry_run:
            print("\n🔍 DRY RUN: Showing what would be applied...")
        else:
            print("\n✅ APPLYING RECOMMENDATIONS...")

        applied_count = 0

        for service, suggestions in recommendations["pattern_suggestions"].items():
            aws_managed_suggestions = [s for s in suggestions if s["type"] == "aws_managed"]

            if aws_managed_suggestions:
                # Get unique patterns with high frequency
                pattern_counts = Counter(s["pattern"] for s in aws_managed_suggestions)
                high_frequency_patterns = [p for p, c in pattern_counts.items() if c >= 2]

                if high_frequency_patterns:
                    print(f"\n📊 {service.upper()}: Adding {len(high_frequency_patterns)} patterns")

                    for pattern in high_frequency_patterns:
                        print(f"  ➕ Adding pattern: {pattern}")

                        if not dry_run:
                            # Add pattern to the service configuration
                            if service not in self.field_mapper.aws_managed_patterns:
                                self.field_mapper.aws_managed_patterns[service] = []

                            if pattern not in self.field_mapper.aws_managed_patterns[service]:
                                self.field_mapper.aws_managed_patterns[service].append(pattern)
                                applied_count += 1

        if dry_run:
            print(f"\n🔍 Dry run complete. {applied_count} patterns would be applied.")
            print("Run with dry_run=False to apply changes.")
        else:
            print(f"\n✅ Applied {applied_count} new filtering patterns.")

        return applied_count

    def export_patterns_to_file(self, filename=None):
        """Export current filtering patterns to a file"""

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"aws_managed_patterns_{timestamp}.json"

        patterns_data = {
            "timestamp": datetime.now().isoformat(),
            "aws_managed_patterns": dict(self.field_mapper.aws_managed_patterns),
            "service_patterns": dict(self.field_mapper.optimized_service_patterns),
        }

        with open(filename, "w") as f:
            json.dump(patterns_data, f, indent=2)

        print(f"💾 Patterns exported to: {filename}")
        return filename

    def run_comprehensive_analysis(self, services=None):
        """Run comprehensive filtering analysis"""

        print("🚀 Starting Comprehensive Filtering Analysis")
        print("=" * 50)

        # Step 1: Analyze resources
        resources = self.analyze_discovered_resources(services)

        # Step 2: Generate recommendations
        recommendations = self.generate_filtering_recommendations()

        # Step 3: Show dry run of applying recommendations
        self.apply_recommended_patterns(recommendations, dry_run=True)

        # Step 4: Export current patterns
        patterns_file = self.export_patterns_to_file()

        print(f"\n🎯 ANALYSIS SUMMARY:")
        print(f"  📊 Resources analyzed: {len(resources)}")
        print(f"  🔧 Services with suggestions: {len(recommendations['pattern_suggestions'])}")
        print(f"  ⚠️  False positives detected: {len(recommendations['false_positives'])}")
        print(f"  📄 Patterns exported to: {patterns_file}")

        return recommendations


def main():
    """Main function for filtering fine-tuning"""

    print("🔧 AWS Managed Resource Filtering - Fine-Tuning System")
    print("=" * 60)

    try:
        tuner = FilteringTuner()

        # Run comprehensive analysis
        recommendations = tuner.run_comprehensive_analysis()

        # Ask user if they want to apply recommendations
        print(f"\n❓ Apply recommended filtering patterns?")
        response = input("Enter 'yes' to apply, anything else to skip: ").lower().strip()

        if response == "yes":
            applied = tuner.apply_recommended_patterns(recommendations, dry_run=False)
            print(f"✅ Applied {applied} new filtering patterns")

            # Export updated patterns
            tuner.export_patterns_to_file("updated_aws_managed_patterns.json")
        else:
            print("⏭️  Skipping pattern application")

        print(f"\n🎉 Fine-tuning analysis complete!")

    except KeyboardInterrupt:
        print("\n⚠️  Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
