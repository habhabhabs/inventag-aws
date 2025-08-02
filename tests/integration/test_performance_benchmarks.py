#!/usr/bin/env python3
"""
Performance benchmark tests for InvenTag BOM generation

Tests performance characteristics with large datasets and concurrent operations
to ensure the system can handle enterprise-scale workloads.
"""

import pytest
import time
import threading
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import gc

from inventag.reporting.bom_processor import BOMDataProcessor
from inventag.discovery.network_analyzer import NetworkAnalyzer
from inventag.discovery.security_analyzer import SecurityAnalyzer
from inventag.state.delta_detector import DeltaDetector
from inventag.reporting.document_generator import DocumentGenerator, DocumentConfig


class TestPerformanceBenchmarks:
    """Performance benchmark tests for BOM generation components."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'output_directory': self.temp_dir,
            'output_formats': ['csv'],  # Use fastest format for performance tests
            'service_descriptions': {},
            'tag_mappings': {}
        }

    def generate_large_dataset(self, size: int) -> list:
        """Generate large dataset for performance testing."""
        resources = []
        services = ['EC2', 'S3', 'RDS', 'Lambda', 'ECS', 'EKS']
        regions = ['us-east-1', 'us-west-2', 'eu-west-1']
        
        for i in range(size):
            service = services[i % len(services)]
            region = regions[i % len(regions)]
            
            resource = {
                'arn': f'arn:aws:{service.lower()}:{region}:123456789012:resource/resource-{i:06d}',
                'id': f'resource-{i:06d}',
                'service': service,
                'type': 'Resource',
                'region': region,
                'tags': {
                    'Name': f'resource-{i}',
                    'Environment': 'test',
                    'CostCenter': f'cc-{i % 10}',
                    'Owner': f'team-{i % 5}'
                },
                'compliance_status': 'compliant' if i % 10 != 0 else 'non-compliant',
                'vpc_id': f'vpc-{i % 100}',
                'subnet_id': f'subnet-{i % 500}',
                'security_groups': [f'sg-{i % 50}', f'sg-{(i + 1) % 50}']
            }
            resources.append(resource)
        
        return resources

    @pytest.mark.performance
    def test_bom_processor_performance_1k_resources(self):
        """Test BOM processor performance with 1,000 resources."""
        resources = self.generate_large_dataset(1000)
        
        processor = BOMDataProcessor(self.config)
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        result = processor.process_inventory_data(resources)
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        processing_time = end_time - start_time
        memory_usage = end_memory - start_memory
        
        # Performance assertions
        assert processing_time < 5.0, f"Processing took {processing_time:.2f}s, expected < 5.0s"
        assert memory_usage < 100, f"Memory usage {memory_usage:.2f}MB, expected < 100MB"
        assert len(result.resources) == 1000
        
        print(f"1K resources: {processing_time:.2f}s, {memory_usage:.2f}MB")

    @pytest.mark.performance
    def test_bom_processor_performance_10k_resources(self):
        """Test BOM processor performance with 10,000 resources."""
        resources = self.generate_large_dataset(10000)
        
        processor = BOMDataProcessor(self.config)
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        result = processor.process_inventory_data(resources)
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        processing_time = end_time - start_time
        memory_usage = end_memory - start_memory
        
        # Performance assertions (more lenient for larger dataset)
        assert processing_time < 30.0, f"Processing took {processing_time:.2f}s, expected < 30.0s"
        assert memory_usage < 500, f"Memory usage {memory_usage:.2f}MB, expected < 500MB"
        assert len(result.resources) == 10000
        
        print(f"10K resources: {processing_time:.2f}s, {memory_usage:.2f}MB")

    @pytest.mark.performance
    def test_network_analyzer_performance(self):
        """Test network analyzer performance with large VPC dataset."""
        # Generate VPC-heavy dataset
        resources = []
        for i in range(5000):  # 5K resources across 100 VPCs
            vpc_id = f'vpc-{i % 100}'
            subnet_id = f'subnet-{i % 500}'
            
            resource = {
                'arn': f'arn:aws:ec2:us-east-1:123456789012:instance/i-{i:06d}',
                'id': f'i-{i:06d}',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'vpc_id': vpc_id,
                'subnet_id': subnet_id,
                'private_ip': f'10.{i % 256}.{(i // 256) % 256}.{i % 254 + 1}',
                'security_groups': [f'sg-{i % 50}']
            }
            resources.append(resource)
        
        # Mock session for network analyzer
        mock_session = Mock()
        analyzer = NetworkAnalyzer(session=mock_session)
        
        # Mock the network info caching to avoid actual AWS calls
        with patch.object(analyzer, '_cache_network_info'):
            start_time = time.time()
            
            # This would normally call AWS APIs, but we're testing the analysis logic
            with patch.object(analyzer, 'vpc_cache', {}):
                with patch.object(analyzer, 'subnet_cache', {}):
                    enriched_resources = analyzer.map_resources_to_network(resources)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Performance assertion
            assert processing_time < 10.0, f"Network analysis took {processing_time:.2f}s, expected < 10.0s"
            assert len(enriched_resources) == 5000
            
            print(f"Network analysis (5K resources): {processing_time:.2f}s")

    @pytest.mark.performance
    def test_security_analyzer_performance(self):
        """Test security analyzer performance with large security group dataset."""
        # Generate security-heavy dataset
        resources = []
        for i in range(3000):  # 3K resources across 100 security groups
            sg_ids = [f'sg-{i % 100}', f'sg-{(i + 1) % 100}']
            
            resource = {
                'arn': f'arn:aws:ec2:us-east-1:123456789012:instance/i-{i:06d}',
                'id': f'i-{i:06d}',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'security_groups': [{'GroupId': sg_id} for sg_id in sg_ids]
            }
            resources.append(resource)
        
        # Mock session for security analyzer
        mock_session = Mock()
        analyzer = SecurityAnalyzer(session=mock_session)
        
        # Mock the security group caching to avoid actual AWS calls
        with patch.object(analyzer, '_cache_security_group_info'):
            start_time = time.time()
            
            # This would normally call AWS APIs, but we're testing the analysis logic
            with patch.object(analyzer, 'sg_cache', {}):
                enriched_resources = analyzer.map_resources_to_security_groups(resources)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Performance assertion
            assert processing_time < 8.0, f"Security analysis took {processing_time:.2f}s, expected < 8.0s"
            assert len(enriched_resources) == 3000
            
            print(f"Security analysis (3K resources): {processing_time:.2f}s")

    @pytest.mark.performance
    def test_delta_detector_performance(self):
        """Test delta detector performance with large state comparison."""
        # Generate old and new states
        old_resources = self.generate_large_dataset(2000)
        
        # Create new state with modifications
        new_resources = old_resources.copy()
        
        # Modify 10% of resources
        for i in range(0, len(new_resources), 10):
            new_resources[i]['tags']['Environment'] = 'modified'
            new_resources[i]['compliance_status'] = 'non-compliant'
        
        # Add 200 new resources
        new_resources.extend(self.generate_large_dataset(200))
        
        # Remove 100 resources
        new_resources = new_resources[100:]
        
        detector = DeltaDetector()
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        delta_report = detector.detect_changes(
            old_resources=old_resources,
            new_resources=new_resources,
            state1_id='old_state',
            state2_id='new_state'
        )
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        processing_time = end_time - start_time
        memory_usage = end_memory - start_memory
        
        # Performance assertions
        assert processing_time < 15.0, f"Delta detection took {processing_time:.2f}s, expected < 15.0s"
        assert memory_usage < 200, f"Memory usage {memory_usage:.2f}MB, expected < 200MB"
        
        # Verify results
        assert delta_report.summary['added_count'] == 200
        assert delta_report.summary['removed_count'] == 100
        assert delta_report.summary['modified_count'] > 0
        
        print(f"Delta detection (2K resources): {processing_time:.2f}s, {memory_usage:.2f}MB")

    @pytest.mark.performance
    def test_concurrent_document_generation(self):
        """Test concurrent document generation performance."""
        resources = self.generate_large_dataset(1000)
        
        # Create multiple BOM processors
        processors = [BOMDataProcessor(self.config) for _ in range(3)]
        
        def generate_bom(processor, resource_subset):
            """Generate BOM for a subset of resources."""
            return processor.process_inventory_data(resource_subset)
        
        # Split resources into chunks
        chunk_size = len(resources) // 3
        resource_chunks = [
            resources[i:i + chunk_size] 
            for i in range(0, len(resources), chunk_size)
        ]
        
        start_time = time.time()
        
        # Process chunks concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(generate_bom, processors[i], resource_chunks[i])
                for i in range(len(resource_chunks))
            ]
            
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance assertion
        assert processing_time < 10.0, f"Concurrent processing took {processing_time:.2f}s, expected < 10.0s"
        assert len(results) == 3
        
        # Verify all chunks were processed
        total_processed = sum(len(result.resources) for result in results)
        assert total_processed == len(resources)
        
        print(f"Concurrent processing (3 threads, 1K resources): {processing_time:.2f}s")

    @pytest.mark.performance
    def test_memory_usage_scaling(self):
        """Test memory usage scaling with increasing dataset sizes."""
        sizes = [100, 500, 1000, 2000]
        memory_usage = []
        
        for size in sizes:
            # Force garbage collection before test
            gc.collect()
            
            resources = self.generate_large_dataset(size)
            processor = BOMDataProcessor(self.config)
            
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            result = processor.process_inventory_data(resources)
            
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_used = end_memory - start_memory
            memory_usage.append(memory_used)
            
            # Clean up
            del result
            del resources
            gc.collect()
            
            print(f"Dataset size {size}: {memory_used:.2f}MB")
        
        # Verify memory usage scales reasonably (not exponentially)
        # Memory usage should be roughly linear with dataset size
        for i in range(1, len(memory_usage)):
            ratio = memory_usage[i] / memory_usage[i-1]
            size_ratio = sizes[i] / sizes[i-1]
            
            # Memory usage should not grow faster than 2x the data size ratio
            assert ratio < size_ratio * 2, f"Memory usage growing too fast: {ratio:.2f}x vs {size_ratio:.2f}x data"

    @pytest.mark.performance
    def test_document_generation_performance(self):
        """Test document generation performance with large datasets."""
        resources = self.generate_large_dataset(5000)
        
        # Mock BOM data
        mock_bom_data = Mock()
        mock_bom_data.resources = resources
        mock_bom_data.generation_metadata = {
            'timestamp': datetime.now().isoformat(),
            'total_resources': len(resources)
        }
        
        # Configure for CSV only (fastest format)
        doc_config = DocumentConfig(
            output_formats=['csv'],
            output_directory=self.temp_dir,
            enable_parallel_generation=False
        )
        
        # Mock the actual file writing to focus on data processing
        with patch('inventag.reporting.csv_builder.CSVBuilder.create_bom_csv') as mock_csv:
            mock_csv.return_value = 'test.csv'
            
            generator = DocumentGenerator(doc_config)
            
            start_time = time.time()
            
            result = generator.generate_bom_documents(mock_bom_data)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Performance assertion
            assert processing_time < 5.0, f"Document generation took {processing_time:.2f}s, expected < 5.0s"
            assert result.successful_formats == 1
            
            print(f"Document generation (5K resources): {processing_time:.2f}s")

    @pytest.mark.performance
    def test_stress_test_continuous_processing(self):
        """Stress test with continuous processing for extended period."""
        duration_seconds = 30  # Run for 30 seconds
        batch_size = 500
        
        start_time = time.time()
        iterations = 0
        total_resources_processed = 0
        
        processor = BOMDataProcessor(self.config)
        
        while time.time() - start_time < duration_seconds:
            resources = self.generate_large_dataset(batch_size)
            
            batch_start = time.time()
            result = processor.process_inventory_data(resources)
            batch_end = time.time()
            
            batch_time = batch_end - batch_start
            
            # Ensure each batch processes within reasonable time
            assert batch_time < 3.0, f"Batch {iterations} took {batch_time:.2f}s, expected < 3.0s"
            
            iterations += 1
            total_resources_processed += len(result.resources)
            
            # Clean up to prevent memory accumulation
            del resources
            del result
            gc.collect()
        
        total_time = time.time() - start_time
        throughput = total_resources_processed / total_time
        
        # Performance assertions
        assert iterations >= 5, f"Only completed {iterations} iterations in {duration_seconds}s"
        assert throughput > 100, f"Throughput {throughput:.2f} resources/sec, expected > 100"
        
        print(f"Stress test: {iterations} iterations, {total_resources_processed} resources, "
              f"{throughput:.2f} resources/sec")

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # Force garbage collection
        gc.collect()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'performance'])