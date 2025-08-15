#!/usr/bin/env python3
"""
Multi-Account Resource Scanner
Comprehensive scanning across multiple AWS accounts with advanced filtering and analysis.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add the project root to the Python path to import inventag
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

from inventag.core import CloudBOMGenerator, MultiAccountConfig
from inventag.reporting import BOMProcessingConfig


def main():
    parser = argparse.ArgumentParser(
        description="InvenTag Multi-Account Resource Scanner"
    )
    parser.add_argument(
        "--accounts-file",
        type=str,
        required=True,
        help="Path to accounts configuration file (JSON/YAML)",
    )
    parser.add_argument(
        "--regions", type=str, help="Comma-separated list of regions to scan"
    )
    parser.add_argument(
        "--services", type=str, help="Comma-separated list of services to include"
    )
    parser.add_argument(
        "--output-format",
        choices=["excel", "word", "json", "csv"],
        nargs="+",
        default=["excel"],
        help="Output formats to generate",
    )
    parser.add_argument(
        "--enable-network-analysis",
        action="store_true",
        help="Enable comprehensive network analysis",
    )
    parser.add_argument(
        "--enable-security-analysis",
        action="store_true",
        help="Enable comprehensive security analysis",
    )
    parser.add_argument(
        "--enable-cost-analysis",
        action="store_true",
        help="Enable cost analysis and optimization recommendations",
    )
    parser.add_argument(
        "--parallel-accounts",
        type=int,
        default=4,
        help="Maximum concurrent accounts to process",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="multi_account_scan_output",
        help="Output directory for generated reports",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    print("🌐 InvenTag Multi-Account Resource Scanner")
    print("=" * 60)

    # Load accounts configuration
    print(f"📋 Loading accounts from: {args.accounts_file}")

    # Configure BOM processing
    bom_config = BOMProcessingConfig(
        enable_network_analysis=args.enable_network_analysis,
        enable_security_analysis=args.enable_security_analysis,
        enable_cost_analysis=args.enable_cost_analysis,
        enable_parallel_processing=True,
        max_worker_threads=args.parallel_accounts,
    )

    # Create multi-account configuration
    multi_config = MultiAccountConfig(
        parallel_account_processing=True,
        max_concurrent_accounts=args.parallel_accounts,
        bom_processing_config=bom_config,
        output_directory=args.output_dir,
    )

    # Initialize generator
    generator = CloudBOMGenerator.from_credentials_file(
        args.accounts_file, **multi_config.__dict__
    )

    print(f"🔍 Starting scan across {len(generator.config.accounts)} accounts...")

    # Start scanning
    start_time = datetime.now()

    results = generator.generate_multi_account_bom(output_formats=args.output_format)

    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()

    # Display results
    print(f"\n📊 Scan Results:")
    print(f"  ⏱️  Processing Time: {processing_time:.2f} seconds")
    print(
        f"  📈 Total Resources: {results['processing_statistics']['total_resources']}"
    )
    print(
        f"  ✅ Successful Accounts: {results['processing_statistics']['successful_accounts']}"
    )
    print(
        f"  ❌ Failed Accounts: {results['processing_statistics']['failed_accounts']}"
    )

    if results["success"]:
        print(f"  📁 Output Directory: {results['output_directory']}")

        if "bom_generation" in results and results["bom_generation"].get(
            "generated_files"
        ):
            print(f"  📄 Generated Files:")
            for file_path in results["bom_generation"]["generated_files"]:
                print(f"    • {file_path}")

    # Account-specific summary
    print(f"\n📋 Account Summary:")
    for account_id, context in results["account_contexts"].items():
        status = "✅" if context["error_count"] == 0 else "❌"
        print(
            f"  {status} {account_id} ({context['account_name']}): {context['resource_count']} resources"
        )
        if context["error_count"] > 0:
            print(f"    ⚠️  {context['error_count']} errors encountered")

    # Recommendations
    print(f"\n💡 Recommendations:")
    failed_accounts = results["processing_statistics"]["failed_accounts"]
    if failed_accounts > 0:
        print(f"  • Review failed accounts for credential or permission issues")

    if args.enable_network_analysis:
        print(
            f"  • Review network analysis for security and optimization opportunities"
        )

    if args.enable_security_analysis:
        print(f"  • Review security analysis for compliance and risk assessment")

    print(f"\n✅ Multi-account scan completed successfully!")


if __name__ == "__main__":
    main()
