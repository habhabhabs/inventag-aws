#!/usr/bin/env python3
"""
CSV Document Builder

Basic CSV document builder that provides fallback functionality.
Always available as it uses only standard library components.
"""

import csv
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from .document_generator import DocumentBuilder, DocumentGenerationResult, BOMData


class CSVBuilder(DocumentBuilder):
    """CSV document builder using standard library."""
    
    def __init__(self, config):
        super().__init__(config)
        
    def can_handle_format(self, format_type: str) -> bool:
        """Check if this builder can handle CSV format."""
        return format_type.lower() == "csv"
        
    def validate_dependencies(self) -> List[str]:
        """Validate CSV dependencies (always available)."""
        return []  # No external dependencies
        
    def generate_document(self, bom_data: BOMData, output_path: str) -> DocumentGenerationResult:
        """Generate CSV document."""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Flatten the data for CSV export
            flattened_data = []
            for resource in bom_data.resources:
                flattened_resource = self._flatten_dict(resource)
                flattened_data.append(flattened_resource)
                
            # Get all unique headers
            all_headers = set()
            for item in flattened_data:
                all_headers.update(item.keys())
                
            # Sort headers for consistent output
            sorted_headers = sorted(all_headers)
            
            # Write CSV
            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=sorted_headers)
                writer.writeheader()
                for item in flattened_data:
                    writer.writerow(item)
                    
            end_time = datetime.now(timezone.utc)
            
            return DocumentGenerationResult(
                format_type="csv",
                filename=os.path.basename(output_path),
                success=True,
                generation_time_seconds=(end_time - start_time).total_seconds()
            )
            
        except Exception as e:
            self.logger.error(f"CSV generation failed: {e}")
            return DocumentGenerationResult(
                format_type="csv",
                filename=os.path.basename(output_path) if output_path else "",
                success=False,
                error_message=str(e)
            )
            
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
        """Flatten a nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to comma-separated strings
                items.append((new_key, ", ".join(str(item) for item in v)))
            else:
                items.append((new_key, v))
        return dict(items)