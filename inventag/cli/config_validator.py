"""
Configuration validation for InvenTag CLI.
"""

import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field

from ..core import AccountCredentials, MultiAccountConfig
from ..reporting import BOMProcessingConfig


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    config: Optional[Dict[str, Any]] = None


class ConfigValidator:
    """Validates InvenTag configuration files and CLI arguments."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_accounts_file(self, file_path: str) -> ValidationResult:
        """
        Validate accounts configuration file.
        
        Args:
            file_path: Path to accounts configuration file
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        result = ValidationResult(is_valid=False)
        
        try:
            path = Path(file_path)
            if not path.exists():
                result.errors.append(f"Accounts file not found: {file_path}")
                return result
            
            # Load configuration based on file extension
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    config = json.load(f)
                else:
                    result.errors.append(f"Unsupported file format: {path.suffix}. Use .json, .yaml, or .yml")
                    return result
            
            result.config = config
            
            # Validate structure
            if not isinstance(config, dict):
                result.errors.append("Configuration must be a dictionary/object")
                return result
            
            if 'accounts' not in config:
                result.errors.append("Configuration must contain 'accounts' key")
                return result
            
            accounts = config['accounts']
            if not isinstance(accounts, list):
                result.errors.append("'accounts' must be a list")
                return result
            
            if not accounts:
                result.errors.append("At least one account must be specified")
                return result
            
            # Validate each account
            for i, account in enumerate(accounts):
                account_errors = self._validate_account_config(account, i)
                result.errors.extend(account_errors)
            
            # Validate global settings
            if 'settings' in config:
                settings_errors = self._validate_settings_config(config['settings'])
                result.errors.extend(settings_errors)
            
            result.is_valid = len(result.errors) == 0
            
        except yaml.YAMLError as e:
            result.errors.append(f"YAML parsing error: {e}")
        except json.JSONDecodeError as e:
            result.errors.append(f"JSON parsing error: {e}")
        except Exception as e:
            result.errors.append(f"Unexpected error validating accounts file: {e}")
        
        return result
    
    def _validate_account_config(self, account: Dict[str, Any], index: int) -> List[str]:
        """Validate individual account configuration."""
        errors = []
        prefix = f"Account {index + 1}"
        
        # Required fields
        if 'account_id' not in account:
            errors.append(f"{prefix}: 'account_id' is required")
        elif not isinstance(account['account_id'], str) or not account['account_id'].strip():
            errors.append(f"{prefix}: 'account_id' must be a non-empty string")
        
        # Optional fields validation
        if 'account_name' in account and not isinstance(account['account_name'], str):
            errors.append(f"{prefix}: 'account_name' must be a string")
        
        if 'regions' in account:
            if not isinstance(account['regions'], list):
                errors.append(f"{prefix}: 'regions' must be a list")
            elif not all(isinstance(r, str) for r in account['regions']):
                errors.append(f"{prefix}: all regions must be strings")
        
        if 'services' in account:
            if not isinstance(account['services'], list):
                errors.append(f"{prefix}: 'services' must be a list")
            elif not all(isinstance(s, str) for s in account['services']):
                errors.append(f"{prefix}: all services must be strings")
        
        if 'tags' in account:
            if not isinstance(account['tags'], dict):
                errors.append(f"{prefix}: 'tags' must be a dictionary")
            elif not all(isinstance(k, str) and isinstance(v, str) 
                        for k, v in account['tags'].items()):
                errors.append(f"{prefix}: all tag keys and values must be strings")
        
        # Credential validation
        has_keys = 'access_key_id' in account and 'secret_access_key' in account
        has_profile = 'profile_name' in account
        has_role = 'role_arn' in account
        
        if not (has_keys or has_profile or has_role):
            errors.append(f"{prefix}: must specify either access keys, profile_name, or role_arn")
        
        if has_keys:
            if not isinstance(account['access_key_id'], str) or not account['access_key_id'].strip():
                errors.append(f"{prefix}: 'access_key_id' must be a non-empty string")
            if not isinstance(account['secret_access_key'], str) or not account['secret_access_key'].strip():
                errors.append(f"{prefix}: 'secret_access_key' must be a non-empty string")
            
            if 'session_token' in account and not isinstance(account['session_token'], str):
                errors.append(f"{prefix}: 'session_token' must be a string")
        
        if has_profile and not isinstance(account['profile_name'], str):
            errors.append(f"{prefix}: 'profile_name' must be a string")
        
        if has_role:
            if not isinstance(account['role_arn'], str) or not account['role_arn'].strip():
                errors.append(f"{prefix}: 'role_arn' must be a non-empty string")
            if 'external_id' in account and not isinstance(account['external_id'], str):
                errors.append(f"{prefix}: 'external_id' must be a string")
        
        return errors
    
    def _validate_settings_config(self, settings: Dict[str, Any]) -> List[str]:
        """Validate global settings configuration."""
        errors = []
        
        if 'max_concurrent_accounts' in settings:
            max_concurrent = settings['max_concurrent_accounts']
            if not isinstance(max_concurrent, int) or max_concurrent < 1:
                errors.append("'max_concurrent_accounts' must be a positive integer")
        
        if 'account_processing_timeout' in settings:
            timeout = settings['account_processing_timeout']
            if not isinstance(timeout, int) or timeout < 60:
                errors.append("'account_processing_timeout' must be an integer >= 60 seconds")
        
        if 'output_directory' in settings:
            if not isinstance(settings['output_directory'], str):
                errors.append("'output_directory' must be a string")
        
        return errors
    
    def validate_service_descriptions_file(self, file_path: str) -> ValidationResult:
        """Validate service descriptions configuration file."""
        result = ValidationResult(is_valid=False)
        
        try:
            path = Path(file_path)
            if not path.exists():
                result.errors.append(f"Service descriptions file not found: {file_path}")
                return result
            
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    config = json.load(f)
                else:
                    result.errors.append(f"Unsupported file format: {path.suffix}")
                    return result
            
            result.config = config
            
            if not isinstance(config, dict):
                result.errors.append("Service descriptions must be a dictionary")
                return result
            
            # Validate structure
            for service, service_config in config.items():
                if not isinstance(service, str):
                    result.errors.append(f"Service name must be string: {service}")
                    continue
                
                if not isinstance(service_config, dict):
                    result.errors.append(f"Service '{service}' configuration must be a dictionary")
                    continue
                
                # Validate service-level fields
                if 'default_description' in service_config:
                    if not isinstance(service_config['default_description'], str):
                        result.errors.append(f"Service '{service}' default_description must be a string")
                
                # Validate resource_types if present
                if 'resource_types' in service_config:
                    resource_types = service_config['resource_types']
                    if not isinstance(resource_types, dict):
                        result.errors.append(f"Service '{service}' resource_types must be a dictionary")
                    else:
                        for resource_type, description in resource_types.items():
                            if not isinstance(resource_type, str):
                                result.errors.append(f"Resource type must be string in service '{service}': {resource_type}")
                            if not isinstance(description, str):
                                result.errors.append(f"Resource type description must be string in service '{service}', resource '{resource_type}'")
                
                # For backward compatibility, also support simple service -> resource -> description structure
                for key, value in service_config.items():
                    if key not in ['default_description', 'display_name', 'category', 'documentation_url', 'resource_types', 'custom_fields']:
                        # This might be a direct resource type mapping
                        if isinstance(value, str):
                            # This is fine - direct resource type to description mapping
                            pass
                        elif isinstance(value, dict):
                            # This might be a nested resource configuration
                            pass
            
            result.is_valid = len(result.errors) == 0
            
        except Exception as e:
            result.errors.append(f"Error validating service descriptions file: {e}")
        
        return result
    
    def validate_tag_mappings_file(self, file_path: str) -> ValidationResult:
        """Validate tag mappings configuration file."""
        result = ValidationResult(is_valid=False)
        
        try:
            path = Path(file_path)
            if not path.exists():
                result.errors.append(f"Tag mappings file not found: {file_path}")
                return result
            
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    config = json.load(f)
                else:
                    result.errors.append(f"Unsupported file format: {path.suffix}")
                    return result
            
            result.config = config
            
            if not isinstance(config, dict):
                result.errors.append("Tag mappings must be a dictionary")
                return result
            
            # Validate structure
            for tag_key, mapping in config.items():
                if not isinstance(tag_key, str):
                    result.errors.append(f"Tag key must be string: {tag_key}")
                    continue
                
                if not isinstance(mapping, dict):
                    result.errors.append(f"Tag mapping for '{tag_key}' must be a dictionary")
                    continue
                
                required_fields = ['column_name']
                for field in required_fields:
                    if field not in mapping:
                        result.errors.append(f"Tag mapping for '{tag_key}' missing required field: {field}")
                    elif not isinstance(mapping[field], str):
                        result.errors.append(f"Tag mapping for '{tag_key}' field '{field}' must be a string")
                
                optional_fields = ['default_value', 'description']
                for field in optional_fields:
                    if field in mapping and not isinstance(mapping[field], str):
                        result.errors.append(f"Tag mapping for '{tag_key}' field '{field}' must be a string")
            
            result.is_valid = len(result.errors) == 0
            
        except Exception as e:
            result.errors.append(f"Error validating tag mappings file: {e}")
        
        return result
    
    def validate_cli_arguments(self, args) -> ValidationResult:
        """Validate CLI arguments for consistency and completeness."""
        result = ValidationResult(is_valid=True)
        
        # Check format options
        format_options = [args.create_word, args.create_excel, args.create_google_docs]
        if not any(format_options):
            result.warnings.append("No output format specified. Use --create-word, --create-excel, or --create-google-docs")
        
        # Check account specification
        account_options = [
            bool(args.accounts_file),
            args.accounts_prompt,
            bool(args.cross_account_role)
        ]
        if not any(account_options):
            result.warnings.append("No account specification method provided. Using default AWS credentials.")
        
        # Validate S3 options
        if args.s3_bucket and not args.s3_key_prefix:
            result.warnings.append("S3 bucket specified without key prefix. Using default prefix.")
        
        if args.s3_key_prefix and not args.s3_bucket:
            result.errors.append("S3 key prefix specified without bucket. Both --s3-bucket and --s3-key-prefix are required for S3 upload.")
        
        # Validate parallel processing
        if args.max_concurrent_accounts and args.max_concurrent_accounts < 1:
            result.errors.append("--max-concurrent-accounts must be a positive integer")
        
        # Validate timeout
        if args.account_processing_timeout and args.account_processing_timeout < 60:
            result.errors.append("--account-processing-timeout must be at least 60 seconds")
        
        result.is_valid = len(result.errors) == 0
        
        return result