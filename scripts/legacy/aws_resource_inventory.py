#!/usr/bin/env python3
"""
AWS Resource Inventory Tool
Discovers and catalogs all AWS resources across services and regions.

BACKWARD COMPATIBILITY WRAPPER
This script now imports from the unified inventag package while maintaining
identical CLI interfaces and output formats.
"""

import argparse
import sys
import os
import logging
import shutil
from datetime import datetime
from botocore.exceptions import NoCredentialsError

# Import from the unified inventag package
try:
    from inventag.discovery import AWSResourceInventory
except ImportError:
    # Fallback for development/testing - add project root to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from inventag.discovery import AWSResourceInventory


def get_python_command():
    """Detect the correct Python command to use (python or python3)."""
    # Check if python3 is available
    if shutil.which("python3"):
        return "python3"
    # Fall back to python if available
    elif shutil.which("python"):
        return "python"
    else:
        raise RuntimeError("Neither 'python' nor 'python3' command found in PATH")


def main():
    parser = argparse.ArgumentParser(description="AWS Resource Inventory Tool")
    parser.add_argument(
        "--regions", nargs="+", help="AWS regions to scan (default: all regions)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="aws_resources",
        help="Output filename (without extension)",
    )
    parser.add_argument("--s3-bucket", help="S3 bucket to upload results")
    parser.add_argument("--s3-key", help="S3 key for uploaded file")
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Also export to Excel/CSV using the converter utility",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Initialize inventory tool
        inventory = AWSResourceInventory(regions=args.regions)

        # Discover resources
        resources = inventory.discover_resources()

        if not resources:
            print("No resources found.")
            return

        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{args.output}_{timestamp}.{args.format}"

        # Save to local file
        inventory.save_to_file(filename, args.format)
        print(f"Inventory saved to {filename}")
        print(f"Total resources discovered: {len(resources)}")

        # Upload to S3 if requested
        if args.s3_bucket:
            s3_key = args.s3_key or f"aws-inventory/{filename}"
            inventory.upload_to_s3(args.s3_bucket, s3_key, args.format)
            print(f"Inventory uploaded to s3://{args.s3_bucket}/{s3_key}")

        # Export to Excel/CSV if requested
        if args.export_excel:
            print("Exporting to Excel/CSV format...")
            excel_filename = f"{args.output}_{timestamp}.xlsx"
            python_cmd = get_python_command()

            # Get the correct path to bom_converter.py
            script_dir = os.path.dirname(os.path.abspath(__file__))
            bom_converter_path = os.path.join(script_dir, "bom_converter.py")

            # Execute the conversion command with proper path quoting
            exit_code = os.system(
                f'"{python_cmd}" "{bom_converter_path}" --input "{filename}" --output "{excel_filename}" --format excel'
            )

            if exit_code == 0:
                print(f"Excel export saved to {excel_filename}")
            else:
                print(f"Error: Excel export failed with exit code {exit_code}")
                sys.exit(1)

    except NoCredentialsError:
        print(
            "Error: AWS credentials not found. Please configure your AWS credentials."
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
