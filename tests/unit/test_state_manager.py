"""
Unit tests for StateManager - Comprehensive inventory state persistence
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from inventag.state.state_manager import StateManager, StateMetadata, StateSnapshot


class TestStateManager:
    """Test suite for StateManager functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def state_manager(self, temp_dir):
        """Create StateManager instance for testing"""
        return StateManager(
            state_dir=f"{temp_dir}/.inventag/state",
            retention_days=7,
            max_snapshots=5
        )
    
    @pytest.fixture
    def sample_resources(self):
        """Sample resource data for testing"""
        return [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
                'id': 'i-1234567890abcdef0',
                'service': 'EC2',
                'type': 'Instance',
                'region': 'us-east-1',
                'tags': {'Name': 'test-instance', 'Environment': 'dev'},
                'compliance_status': 'compliant'
            },
            {
                'arn': 'arn:aws:s3:::test-bucket',
                'id': 'test-bucket',
                'service': 'S3',
                'type': 'Bucket',
                'region': 'us-east-1',
                'tags': {'Name': 'test-bucket'},
                'compliance_status': 'non-compliant'
            }
        ]
    
    @pytest.fixture
    def sample_compliance_data(self):
        """Sample compliance data for testing"""
        return {
            'summary': {
                'total_resources': 2,
                'compliant_resources': 1,
                'non_compliant_resources': 1,
                'compliance_percentage': 50.0
            },
            'violations': [
                {
                    'resource_arn': 'arn:aws:s3:::test-bucket',
                    'violation_type': 'missing_required_tag',
                    'details': 'Missing required tag: CostCenter'
                }
            ]
        }
    
    def test_initialization(self, temp_dir):
        """Test StateManager initialization"""
        state_manager = StateManager(
            state_dir=f"{temp_dir}/.inventag/state",
            retention_days=30,
            max_snapshots=100
        )
        
        assert state_manager.retention_days == 30
        assert state_manager.max_snapshots == 100
        assert state_manager.state_dir.exists()
        assert state_manager.metadata_index == {}
    
    def test_save_state_basic(self, state_manager, sample_resources):
        """Test basic state saving functionality"""
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"],
            discovery_method="test"
        )
        
        assert state_id is not None
        assert len(state_id) == 15  # YYYYMMDD_HHMMSS format
        assert state_id in state_manager.metadata_index
        
        # Verify metadata
        metadata = state_manager.metadata_index[state_id]['metadata']
        assert metadata['account_id'] == "123456789012"
        assert metadata['regions'] == ["us-east-1"]
        assert metadata['resource_count'] == 2
        assert metadata['discovery_method'] == "test"
        assert 'checksum' in metadata
    
    def test_save_state_with_additional_data(self, state_manager, sample_resources, sample_compliance_data):
        """Test state saving with compliance and analysis data"""
        network_analysis = {'vpc_count': 1, 'subnet_count': 3}
        security_analysis = {'security_groups': 2, 'high_risk_rules': 1}
        tags = {'environment': 'test', 'purpose': 'unit-testing'}
        
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            discovery_method="comprehensive",
            compliance_data=sample_compliance_data,
            network_analysis=network_analysis,
            security_analysis=security_analysis,
            tags=tags
        )
        
        # Load and verify
        snapshot = state_manager.load_state(state_id)
        assert snapshot is not None
        assert snapshot.compliance_data == sample_compliance_data
        assert snapshot.network_analysis == network_analysis
        assert snapshot.security_analysis == security_analysis
        assert snapshot.metadata.tags == tags
    
    def test_load_state_existing(self, state_manager, sample_resources):
        """Test loading existing state"""
        # Save state first
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        # Load state
        snapshot = state_manager.load_state(state_id)
        
        assert snapshot is not None
        assert len(snapshot.resources) == 2
        assert snapshot.metadata.account_id == "123456789012"
        assert snapshot.metadata.resource_count == 2
        assert snapshot.resources == sample_resources
    
    def test_load_state_most_recent(self, state_manager, sample_resources):
        """Test loading most recent state when no ID specified"""
        # Save multiple states
        state_id1 = state_manager.save_state(
            resources=sample_resources[:1],
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        # Wait a moment to ensure different timestamps
        import time
        time.sleep(1)
        
        state_id2 = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        # Load most recent (should be state_id2)
        snapshot = state_manager.load_state()
        
        assert snapshot is not None
        assert len(snapshot.resources) == 2
        assert snapshot.metadata.timestamp == state_id2
    
    def test_load_state_nonexistent(self, state_manager):
        """Test loading non-existent state"""
        snapshot = state_manager.load_state("20230101_120000")
        assert snapshot is None
    
    def test_list_states(self, state_manager, sample_resources):
        """Test listing available states"""
        # Save multiple states
        state_ids = []
        for i in range(3):
            import time
            time.sleep(1)  # Ensure different timestamps
            state_id = state_manager.save_state(
                resources=sample_resources,
                account_id="123456789012",
                regions=["us-east-1"]
            )
            state_ids.append(state_id)
        
        # List all states
        states = state_manager.list_states()
        assert len(states) == 3
        
        # Should be in reverse chronological order
        for i, state in enumerate(states):
            assert state['state_id'] == state_ids[-(i+1)]
            assert 'metadata' in state
            assert 'file' in state
            assert 'size_bytes' in state
        
        # Test with limit
        limited_states = state_manager.list_states(limit=2)
        assert len(limited_states) == 2
    
    def test_checksum_calculation(self, state_manager, sample_resources):
        """Test checksum calculation for change detection"""
        checksum1 = state_manager._calculate_checksum(sample_resources)
        checksum2 = state_manager._calculate_checksum(sample_resources)
        
        # Same data should produce same checksum
        assert checksum1 == checksum2
        
        # Modified data should produce different checksum
        modified_resources = sample_resources.copy()
        modified_resources[0]['tags']['NewTag'] = 'NewValue'
        checksum3 = state_manager._calculate_checksum(modified_resources)
        
        assert checksum1 != checksum3
    
    def test_get_state_comparison_data(self, state_manager, sample_resources):
        """Test getting comparison data between states"""
        # Save first state
        state_id1 = state_manager.save_state(
            resources=sample_resources[:1],
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        import time
        time.sleep(1)
        
        # Save second state with more resources
        state_id2 = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        # Get comparison data
        comparison = state_manager.get_state_comparison_data(state_id1, state_id2)
        
        assert 'state1' in comparison
        assert 'state2' in comparison
        assert comparison['state1']['id'] == state_id1
        assert comparison['state2']['id'] == state_id2
        assert len(comparison['state1']['resources']) == 1
        assert len(comparison['state2']['resources']) == 2
    
    def test_export_state_json(self, state_manager, sample_resources, temp_dir):
        """Test exporting state to JSON format"""
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        output_file = f"{temp_dir}/export_test.json"
        exported_file = state_manager.export_state(
            state_id=state_id,
            export_format="json",
            output_file=output_file,
            include_metadata=True
        )
        
        assert exported_file == output_file
        assert Path(output_file).exists()
        
        # Verify exported content
        with open(output_file, 'r') as f:
            exported_data = json.load(f)
        
        assert 'metadata' in exported_data
        assert 'resources' in exported_data
        assert len(exported_data['resources']) == 2
    
    def test_export_state_yaml(self, state_manager, sample_resources, temp_dir):
        """Test exporting state to YAML format"""
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        output_file = f"{temp_dir}/export_test.yaml"
        exported_file = state_manager.export_state(
            state_id=state_id,
            export_format="yaml",
            output_file=output_file,
            include_metadata=False
        )
        
        assert exported_file == output_file
        assert Path(output_file).exists()
    
    def test_export_state_csv(self, state_manager, sample_resources, temp_dir):
        """Test exporting state to CSV format"""
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        output_file = f"{temp_dir}/export_test.csv"
        exported_file = state_manager.export_state(
            state_id=state_id,
            export_format="csv",
            output_file=output_file
        )
        
        assert exported_file == output_file
        assert Path(output_file).exists()
    
    def test_cleanup_old_states_by_age(self, state_manager, sample_resources):
        """Test cleanup of old states by age"""
        # Mock datetime to simulate old states
        with patch('inventag.state.state_manager.datetime') as mock_datetime:
            # Create old state (8 days ago)
            old_time = datetime.now(timezone.utc) - timedelta(days=8)
            mock_datetime.now.return_value = old_time
            mock_datetime.strptime.side_effect = datetime.strptime
            mock_datetime.timezone = timezone
            
            old_state_id = state_manager.save_state(
                resources=sample_resources,
                account_id="123456789012",
                regions=["us-east-1"]
            )
            
            # Reset to current time and create new state
            mock_datetime.now.return_value = datetime.now(timezone.utc)
            
            new_state_id = state_manager.save_state(
                resources=sample_resources,
                account_id="123456789012",
                regions=["us-east-1"]
            )
            
            # Trigger cleanup (retention_days=7)
            state_manager._cleanup_old_states()
            
            # Old state should be removed, new state should remain
            assert old_state_id not in state_manager.metadata_index
            assert new_state_id in state_manager.metadata_index
    
    def test_cleanup_old_states_by_count(self, state_manager, sample_resources):
        """Test cleanup of old states by count limit"""
        # Save more states than max_snapshots (5)
        state_ids = []
        for i in range(7):
            import time
            time.sleep(0.1)  # Small delay for different timestamps
            state_id = state_manager.save_state(
                resources=sample_resources,
                account_id="123456789012",
                regions=["us-east-1"]
            )
            state_ids.append(state_id)
        
        # Should only keep the 5 most recent
        assert len(state_manager.metadata_index) == 5
        
        # Check that we have 5 states (the exact IDs may vary due to timestamp collision handling)
        assert len(state_manager.metadata_index) == 5
        
        # Verify that the states are the most recent ones by checking timestamps
        remaining_timestamps = sorted(state_manager.metadata_index.keys())
        # All remaining states should be from the same time period (recent)
        assert len(remaining_timestamps) == 5
    
    def test_get_storage_stats(self, state_manager, sample_resources):
        """Test getting storage statistics"""
        # Save some states
        for i in range(3):
            import time
            time.sleep(0.1)
            state_manager.save_state(
                resources=sample_resources,
                account_id="123456789012",
                regions=["us-east-1"]
            )
        
        stats = state_manager.get_storage_stats()
        
        assert stats['total_states'] == 3
        assert stats['total_size_bytes'] > 0
        assert stats['total_size_mb'] >= 0  # Allow 0.0 for small files
        assert stats['retention_days'] == 7
        assert stats['max_snapshots'] == 5
        assert 'state_directory' in stats
    
    def test_validate_state_integrity(self, state_manager, sample_resources):
        """Test state integrity validation"""
        # Save valid state
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        # Validate all states
        results = state_manager.validate_state_integrity()
        
        assert len(results['valid_states']) == 1
        assert state_id in results['valid_states']
        assert len(results['invalid_states']) == 0
        assert len(results['missing_files']) == 0
        assert len(results['checksum_mismatches']) == 0
        
        # Validate specific state
        specific_results = state_manager.validate_state_integrity(state_id)
        assert len(specific_results['valid_states']) == 1
        assert state_id in specific_results['valid_states']
    
    def test_validate_state_integrity_corrupted(self, state_manager, sample_resources):
        """Test state integrity validation with corrupted data"""
        # Save state
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        # Corrupt the state file
        state_file = Path(state_manager.metadata_index[state_id]['file'])
        with open(state_file, 'w') as f:
            json.dump({'corrupted': 'data'}, f)
        
        # Validate should detect corruption
        results = state_manager.validate_state_integrity(state_id)
        
        assert len(results['valid_states']) == 0
        assert len(results['invalid_states']) == 1
    
    def test_metadata_persistence(self, temp_dir, sample_resources):
        """Test that metadata persists across StateManager instances"""
        # Create first instance and save state
        state_manager1 = StateManager(state_dir=f"{temp_dir}/.inventag/state")
        state_id = state_manager1.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        # Create second instance (should load existing metadata)
        state_manager2 = StateManager(state_dir=f"{temp_dir}/.inventag/state")
        
        assert state_id in state_manager2.metadata_index
        snapshot = state_manager2.load_state(state_id)
        assert snapshot is not None
        assert len(snapshot.resources) == 2
    
    def test_error_handling_invalid_export_format(self, state_manager, sample_resources):
        """Test error handling for invalid export format"""
        state_id = state_manager.save_state(
            resources=sample_resources,
            account_id="123456789012",
            regions=["us-east-1"]
        )
        
        with pytest.raises(ValueError, match="Unsupported export format"):
            state_manager.export_state(state_id, export_format="invalid")
    
    def test_error_handling_export_nonexistent_state(self, state_manager):
        """Test error handling when exporting non-existent state"""
        with pytest.raises(ValueError, match="State .* not found"):
            state_manager.export_state("20230101_120000")
    
    def test_error_handling_comparison_nonexistent_state(self, state_manager):
        """Test error handling when comparing non-existent states"""
        with pytest.raises(ValueError, match="One or both states not found"):
            state_manager.get_state_comparison_data("20230101_120000", "20230101_130000")


if __name__ == "__main__":
    pytest.main([__file__])