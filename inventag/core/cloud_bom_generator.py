#!/usr/bin/env python3
"""
CloudBOMGenerator - Main Multi-Account Orchestrator

Main orchestrator that coordinates comprehensive resource discovery, compliance checking,
and BOM document generation across multiple AWS accounts with parallel processing
and centralized credential management.

Features:
- Account context detection using aws sts get-caller-identity for each account
- Multi-account credential management with file-based and prompt-based input
- Cross-account role assumption support for centralized scanning
- Comprehensive resource discovery across multiple AWS accounts in parallel
- Account-specific error handling and graceful failure recovery
- Account consolidation logic for unified BOM document generation
"""

import logging
import boto3
import json
import yaml
import getpass
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

# Import InvenTag components
from ..discovery import AWSResourceInventory
from ..compliance import ComprehensiveTagComplianceChecker
from ..reporting import BOMConverter, BOMDataProcessor, BOMProcessingConfig
from ..state import StateManager, DeltaDetector, ChangelogGenerator


@dataclass
class AccountCredentials:
    """Credentials for a single AWS account."""
    account_id: str
    account_name: str = ""
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    profile_name: Optional[str] = None
    role_arn: Optional[str] = None
    external_id: Optional[str] = None
    regions: List[str] = field(default_factory=lambda: ["us-east-1"])
    services: List[str] = field(default_factory=list)  # Empty means all services
    tags: Dict[str, str] = field(default_factory=dict)  # Account-specific tag filters


@dataclass
class AccountContext:
    """Runtime context for an AWS account during processing."""
    credentials: AccountCredentials
    session: boto3.Session
    caller_identity: Dict[str, Any]
    accessible_regions: List[str] = field(default_factory=list)
    discovered_services: List[str] = field(default_factory=list)
    processing_errors: List[str] = field(default_factory=list)
    processing_warnings: List[str] = field(default_factory=list)
    resource_count: int = 0
    processing_time_seconds: float = 0.0


@dataclass
class MultiAccountConfig:
    """Configuration for multi-account BOM generation."""
    accounts: List[AccountCredentials] = field(default_factory=list)
    cross_account_role_name: str = "InvenTagCrossAccountRole"
    parallel_account_processing: bool = True
    max_concurrent_accounts: int = 4
    account_processing_timeout: int = 1800  # 30 minutes per account
    consolidate_accounts: bool = True
    generate_per_account_reports: bool = False
    enable_state_management: bool = True
    enable_delta_detection: bool = True
    enable_changelog_generation: bool = True
    bom_processing_config: BOMProcessingConfig = field(default_factory=BOMProcessingConfig)
    output_directory: str = "bom_output"
    credential_validation_timeout: int = 30


class CloudBOMGenerator:
    """
    Main orchestrator that coordinates comprehensive resource discovery, compliance checking,
    and BOM document generation across multiple AWS accounts.
    
    Features:
    - Account context detection using aws sts get-caller-identity for each account
    - Multi-account credential management with file-based and prompt-based input
    - Cross-account role assumption support for centralized scanning
    - Comprehensive resource discovery across multiple AWS accounts in parallel
    - Account-specific error handling and graceful failure recovery
    - Account consolidation logic for unified BOM document generation
    """

    def __init__(self, config: MultiAccountConfig):
        """Initialize the CloudBOMGenerator."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.CloudBOMGenerator")
        
        # Account contexts
        self.account_contexts: Dict[str, AccountContext] = {}
        self.consolidated_resources: List[Dict[str, Any]] = []
        
        # Processing state
        self._processing_lock = threading.Lock()
        self._processing_stats = {
            "total_accounts": 0,
            "successful_accounts": 0,
            "failed_accounts": 0,
            "total_resources": 0,
            "processing_start_time": None,
            "processing_end_time": None
        }
        
        # Initialize output directory
        self.output_dir = Path(self.config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Initialized CloudBOMGenerator with {len(self.config.accounts)} accounts")

    def generate_multi_account_bom(
        self, 
        output_formats: List[str] = None,
        compliance_policies: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive BOM documents across multiple AWS accounts.
        
        Args:
            output_formats: List of output formats (word, excel, csv, json)
            compliance_policies: Tag compliance policies to apply
            
        Returns:
            Dictionary containing generation results and metadata
        """
        self.logger.info("Starting multi-account BOM generation")
        self._processing_stats["processing_start_time"] = datetime.now(timezone.utc)
        self._processing_stats["total_accounts"] = len(self.config.accounts)
        
        try:
            # Step 1: Validate and establish account contexts
            self.logger.info("Validating account credentials and establishing contexts")
            account_contexts = self._establish_account_contexts()
            
            # Step 2: Discover resources across all accounts
            self.logger.info("Starting resource discovery across all accounts")
            if self.config.parallel_account_processing:
                all_resources = self._parallel_account_discovery(account_contexts)
            else:
                all_resources = self._sequential_account_discovery(account_contexts)
            
            # Step 3: Consolidate resources if configured
            if self.config.consolidate_accounts:
                self.logger.info("Consolidating resources from all accounts")
                consolidated_resources = self._consolidate_account_resources(all_resources)
            else:
                consolidated_resources = all_resources
                
            # Step 4: Process compliance checking if policies provided
            compliance_results = {}
            if compliance_policies:
                self.logger.info("Running compliance analysis across all resources")
                compliance_results = self._run_compliance_analysis(consolidated_resources, compliance_policies)
                
            # Step 5: Generate BOM documents
            self.logger.info("Generating BOM documents")
            bom_results = self._generate_bom_documents(
                consolidated_resources, 
                compliance_results,
                output_formats or ["excel", "word"]
            )
            
            # Step 6: Generate state management artifacts if enabled
            state_results = {}
            if self.config.enable_state_management:
                self.logger.info("Generating state management artifacts")
                state_results = self._generate_state_artifacts(consolidated_resources)
                
            # Step 7: Compile final results
            self._processing_stats["processing_end_time"] = datetime.now(timezone.utc)
            processing_time = (
                self._processing_stats["processing_end_time"] - 
                self._processing_stats["processing_start_time"]
            ).total_seconds()
            
            results = {
                "success": True,
                "processing_statistics": {
                    **self._processing_stats,
                    "processing_time_seconds": processing_time,
                    "total_resources": len(consolidated_resources)
                },
                "account_contexts": {
                    acc_id: {
                        "account_name": ctx.credentials.account_name,
                        "resource_count": ctx.resource_count,
                        "processing_time_seconds": ctx.processing_time_seconds,
                        "accessible_regions": ctx.accessible_regions,
                        "discovered_services": ctx.discovered_services,
                        "error_count": len(ctx.processing_errors),
                        "warning_count": len(ctx.processing_warnings)
                    }
                    for acc_id, ctx in self.account_contexts.items()
                },
                "bom_generation": bom_results,
                "compliance_analysis": compliance_results,
                "state_management": state_results,
                "output_directory": str(self.output_dir)
            }
            
            self.logger.info(
                f"Multi-account BOM generation completed successfully in {processing_time:.2f}s. "
                f"Processed {len(consolidated_resources)} resources across "
                f"{self._processing_stats['successful_accounts']} accounts"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Multi-account BOM generation failed: {e}")
            self._processing_stats["processing_end_time"] = datetime.now(timezone.utc)
            
            return {
                "success": False,
                "error": str(e),
                "processing_statistics": self._processing_stats,
                "account_contexts": {
                    acc_id: {
                        "account_name": ctx.credentials.account_name,
                        "error_count": len(ctx.processing_errors),
                        "errors": ctx.processing_errors
                    }
                    for acc_id, ctx in self.account_contexts.items()
                }
            }

    def _establish_account_contexts(self) -> Dict[str, AccountContext]:
        """Validate credentials and establish account contexts."""
        account_contexts = {}
        
        for credentials in self.config.accounts:
            try:
                self.logger.info(f"Establishing context for account {credentials.account_id}")
                
                # Create session
                session = self._create_account_session(credentials)
                
                # Get caller identity to validate credentials
                caller_identity = self._get_caller_identity(session)
                
                # Validate account ID matches
                actual_account_id = caller_identity.get("Account", "")
                if credentials.account_id != actual_account_id:
                    self.logger.warning(
                        f"Account ID mismatch for {credentials.account_id}. "
                        f"Actual: {actual_account_id}"
                    )
                
                # Test accessible regions
                accessible_regions = self._test_accessible_regions(session, credentials.regions)
                
                # Create account context
                context = AccountContext(
                    credentials=credentials,
                    session=session,
                    caller_identity=caller_identity,
                    accessible_regions=accessible_regions
                )
                
                account_contexts[credentials.account_id] = context
                self.account_contexts[credentials.account_id] = context
                
                self.logger.info(
                    f"Successfully established context for account {credentials.account_id} "
                    f"({credentials.account_name}) with {len(accessible_regions)} accessible regions"
                )
                
            except Exception as e:
                self.logger.error(f"Failed to establish context for account {credentials.account_id}: {e}")
                # Create a failed context for tracking
                context = AccountContext(
                    credentials=credentials,
                    session=None,
                    caller_identity={},
                    processing_errors=[f"Context establishment failed: {e}"]
                )
                account_contexts[credentials.account_id] = context
                self.account_contexts[credentials.account_id] = context
                
        return account_contexts

    def _create_account_session(self, credentials: AccountCredentials) -> boto3.Session:
        """Create a boto3 session for the given account credentials."""
        
        # Try profile-based authentication first
        if credentials.profile_name:
            try:
                session = boto3.Session(profile_name=credentials.profile_name)
                # Test the session
                sts = session.client('sts')
                sts.get_caller_identity()
                return session
            except (ProfileNotFound, NoCredentialsError, ClientError) as e:
                self.logger.warning(f"Profile {credentials.profile_name} failed: {e}")
        
        # Try role assumption if role_arn is provided
        if credentials.role_arn:
            try:
                # Use default session to assume role
                default_session = boto3.Session()
                sts = default_session.client('sts')
                
                assume_role_kwargs = {
                    'RoleArn': credentials.role_arn,
                    'RoleSessionName': f'InvenTag-{credentials.account_id}-{int(datetime.now().timestamp())}'
                }
                
                if credentials.external_id:
                    assume_role_kwargs['ExternalId'] = credentials.external_id
                    
                response = sts.assume_role(**assume_role_kwargs)
                
                temp_credentials = response['Credentials']
                session = boto3.Session(
                    aws_access_key_id=temp_credentials['AccessKeyId'],
                    aws_secret_access_key=temp_credentials['SecretAccessKey'],
                    aws_session_token=temp_credentials['SessionToken']
                )
                
                return session
                
            except ClientError as e:
                self.logger.warning(f"Role assumption failed for {credentials.role_arn}: {e}")
        
        # Try direct credentials
        if credentials.access_key_id and credentials.secret_access_key:
            session = boto3.Session(
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                aws_session_token=credentials.session_token
            )
            return session
        
        # Try cross-account role assumption with configured role name
        if self.config.cross_account_role_name:
            try:
                default_session = boto3.Session()
                sts = default_session.client('sts')
                
                role_arn = f"arn:aws:iam::{credentials.account_id}:role/{self.config.cross_account_role_name}"
                
                response = sts.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName=f'InvenTag-CrossAccount-{int(datetime.now().timestamp())}'
                )
                
                temp_credentials = response['Credentials']
                session = boto3.Session(
                    aws_access_key_id=temp_credentials['AccessKeyId'],
                    aws_secret_access_key=temp_credentials['SecretAccessKey'],
                    aws_session_token=temp_credentials['SessionToken']
                )
                
                return session
                
            except ClientError as e:
                self.logger.warning(f"Cross-account role assumption failed for {role_arn}: {e}")
        
        # Fallback to default session
        try:
            session = boto3.Session()
            # Test the session
            sts = session.client('sts')
            sts.get_caller_identity()
            return session
        except Exception as e:
            raise Exception(f"Failed to create valid session for account {credentials.account_id}: {e}")

    def _get_caller_identity(self, session: boto3.Session) -> Dict[str, Any]:
        """Get caller identity for account context detection."""
        try:
            sts = session.client('sts')
            response = sts.get_caller_identity()
            
            return {
                "UserId": response.get("UserId", ""),
                "Account": response.get("Account", ""),
                "Arn": response.get("Arn", ""),
                "retrieved_at": datetime.now(timezone.utc).isoformat()
            }
            
        except ClientError as e:
            raise Exception(f"Failed to get caller identity: {e}")

    def _test_accessible_regions(self, session: boto3.Session, target_regions: List[str]) -> List[str]:
        """Test which regions are accessible for the account."""
        accessible_regions = []
        
        for region in target_regions:
            try:
                # Test region accessibility with a simple EC2 describe call
                ec2 = session.client('ec2', region_name=region)
                ec2.describe_regions(RegionNames=[region])
                accessible_regions.append(region)
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                    self.logger.warning(f"No access to region {region}")
                else:
                    self.logger.warning(f"Region {region} test failed: {e}")
            except Exception as e:
                self.logger.warning(f"Region {region} test failed: {e}")
                
        return accessible_regions

    def _parallel_account_discovery(self, account_contexts: Dict[str, AccountContext]) -> List[Dict[str, Any]]:
        """Discover resources across accounts in parallel."""
        self.logger.info(f"Starting parallel discovery across {len(account_contexts)} accounts")
        
        all_resources = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_accounts) as executor:
            # Submit discovery tasks
            future_to_account = {
                executor.submit(self._discover_account_resources, account_id, context): account_id
                for account_id, context in account_contexts.items()
                if context.session is not None  # Only process accounts with valid sessions
            }
            
            # Collect results
            for future in as_completed(future_to_account, timeout=self.config.account_processing_timeout):
                account_id = future_to_account[future]
                try:
                    account_resources = future.result()
                    all_resources.extend(account_resources)
                    self._processing_stats["successful_accounts"] += 1
                    
                    self.logger.info(
                        f"Successfully discovered {len(account_resources)} resources "
                        f"from account {account_id}"
                    )
                    
                except Exception as e:
                    self.logger.error(f"Resource discovery failed for account {account_id}: {e}")
                    self._processing_stats["failed_accounts"] += 1
                    
                    # Update account context with error
                    if account_id in self.account_contexts:
                        self.account_contexts[account_id].processing_errors.append(
                            f"Resource discovery failed: {e}"
                        )
        
        self.logger.info(f"Parallel discovery completed. Total resources: {len(all_resources)}")
        return all_resources

    def _sequential_account_discovery(self, account_contexts: Dict[str, AccountContext]) -> List[Dict[str, Any]]:
        """Discover resources across accounts sequentially."""
        self.logger.info(f"Starting sequential discovery across {len(account_contexts)} accounts")
        
        all_resources = []
        
        for account_id, context in account_contexts.items():
            if context.session is None:
                self.logger.warning(f"Skipping account {account_id} due to invalid session")
                self._processing_stats["failed_accounts"] += 1
                continue
                
            try:
                self.logger.info(f"Discovering resources for account {account_id}")
                account_resources = self._discover_account_resources(account_id, context)
                all_resources.extend(account_resources)
                self._processing_stats["successful_accounts"] += 1
                
                self.logger.info(
                    f"Successfully discovered {len(account_resources)} resources "
                    f"from account {account_id}"
                )
                
            except Exception as e:
                self.logger.error(f"Resource discovery failed for account {account_id}: {e}")
                self._processing_stats["failed_accounts"] += 1
                
                # Update account context with error
                context.processing_errors.append(f"Resource discovery failed: {e}")
        
        self.logger.info(f"Sequential discovery completed. Total resources: {len(all_resources)}")
        return all_resources

    def _discover_account_resources(self, account_id: str, context: AccountContext) -> List[Dict[str, Any]]:
        """Discover resources for a single account."""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Initialize resource inventory for this account
            inventory = AWSResourceInventory(
                session=context.session,
                regions=context.accessible_regions,
                services=context.credentials.services or None,  # None means all services
                tag_filters=context.credentials.tags
            )
            
            # Discover resources
            resources = inventory.discover_all_resources()
            
            # Add account context to each resource
            for resource in resources:
                resource["source_account_id"] = account_id
                resource["source_account_name"] = context.credentials.account_name
                resource["discovery_timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Update context statistics
            context.resource_count = len(resources)
            context.processing_time_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            context.discovered_services = list(set(r.get("service", "") for r in resources))
            
            self.logger.info(
                f"Account {account_id} discovery completed in {context.processing_time_seconds:.2f}s. "
                f"Found {len(resources)} resources across {len(context.discovered_services)} services"
            )
            
            return resources
            
        except Exception as e:
            context.processing_errors.append(f"Resource discovery failed: {e}")
            context.processing_time_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            raise

    def _consolidate_account_resources(self, all_resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Consolidate resources from multiple accounts into unified format."""
        self.logger.info(f"Consolidating {len(all_resources)} resources from multiple accounts")
        
        # Group resources by account for analysis
        resources_by_account = {}
        for resource in all_resources:
            account_id = resource.get("source_account_id", "unknown")
            if account_id not in resources_by_account:
                resources_by_account[account_id] = []
            resources_by_account[account_id].append(resource)
        
        # Log consolidation statistics
        for account_id, resources in resources_by_account.items():
            account_name = resources[0].get("source_account_name", "Unknown") if resources else "Unknown"
            self.logger.info(f"Account {account_id} ({account_name}): {len(resources)} resources")
        
        # Add consolidation metadata
        for resource in all_resources:
            resource["consolidation_timestamp"] = datetime.now(timezone.utc).isoformat()
            resource["total_accounts_in_consolidation"] = len(resources_by_account)
        
        self.consolidated_resources = all_resources
        return all_resources

    def _run_compliance_analysis(
        self, 
        resources: List[Dict[str, Any]], 
        compliance_policies: Dict
    ) -> Dict[str, Any]:
        """Run compliance analysis across all consolidated resources."""
        self.logger.info("Running compliance analysis across consolidated resources")
        
        try:
            # Use the first available session for compliance checking
            session = None
            for context in self.account_contexts.values():
                if context.session:
                    session = context.session
                    break
            
            if not session:
                raise Exception("No valid session available for compliance analysis")
            
            # Initialize compliance checker
            compliance_checker = ComprehensiveTagComplianceChecker(
                session=session,
                policies=compliance_policies
            )
            
            # Run compliance analysis
            compliance_results = compliance_checker.check_resources_compliance(resources)
            
            # Add multi-account context to results
            compliance_results["multi_account_analysis"] = {
                "total_accounts": len(self.account_contexts),
                "accounts_analyzed": [
                    {
                        "account_id": acc_id,
                        "account_name": ctx.credentials.account_name,
                        "resource_count": ctx.resource_count
                    }
                    for acc_id, ctx in self.account_contexts.items()
                ],
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return compliance_results
            
        except Exception as e:
            self.logger.error(f"Compliance analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _generate_bom_documents(
        self, 
        resources: List[Dict[str, Any]], 
        compliance_results: Dict[str, Any],
        output_formats: List[str]
    ) -> Dict[str, Any]:
        """Generate BOM documents from consolidated resources."""
        self.logger.info(f"Generating BOM documents in formats: {output_formats}")
        
        try:
            # Use the first available session for BOM generation
            session = None
            for context in self.account_contexts.values():
                if context.session:
                    session = context.session
                    break
            
            if not session:
                raise Exception("No valid session available for BOM generation")
            
            # Initialize BOM processor
            bom_processor = BOMDataProcessor(
                config=self.config.bom_processing_config,
                session=session
            )
            
            # Process inventory data into BOM format
            bom_data = bom_processor.process_inventory_data(resources)
            
            # Add multi-account metadata
            bom_data.generation_metadata.update({
                "multi_account_generation": True,
                "total_accounts": len(self.account_contexts),
                "successful_accounts": self._processing_stats["successful_accounts"],
                "failed_accounts": self._processing_stats["failed_accounts"],
                "account_summary": [
                    {
                        "account_id": acc_id,
                        "account_name": ctx.credentials.account_name,
                        "resource_count": ctx.resource_count,
                        "processing_time_seconds": ctx.processing_time_seconds,
                        "error_count": len(ctx.processing_errors)
                    }
                    for acc_id, ctx in self.account_contexts.items()
                ]
            })
            
            # Add compliance results to BOM data
            if compliance_results:
                bom_data.compliance_summary = compliance_results
            
            # Initialize BOM converter
            bom_converter = BOMConverter(session=session)
            
            # Generate documents in requested formats
            generated_files = []
            
            for format_type in output_formats:
                try:
                    if format_type.lower() == "excel":
                        output_file = self.output_dir / f"multi_account_bom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        bom_converter.generate_excel_bom(bom_data, str(output_file))
                        generated_files.append(str(output_file))
                        
                    elif format_type.lower() == "word":
                        output_file = self.output_dir / f"multi_account_bom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                        bom_converter.generate_word_bom(bom_data, str(output_file))
                        generated_files.append(str(output_file))
                        
                    elif format_type.lower() == "csv":
                        output_file = self.output_dir / f"multi_account_bom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        bom_converter.generate_csv_bom(bom_data, str(output_file))
                        generated_files.append(str(output_file))
                        
                    elif format_type.lower() == "json":
                        output_file = self.output_dir / f"multi_account_bom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(output_file, 'w') as f:
                            json.dump({
                                "resources": bom_data.resources,
                                "metadata": bom_data.generation_metadata,
                                "compliance_summary": bom_data.compliance_summary,
                                "network_analysis": bom_data.network_analysis,
                                "security_analysis": bom_data.security_analysis
                            }, f, indent=2, default=str)
                        generated_files.append(str(output_file))
                        
                except Exception as e:
                    self.logger.error(f"Failed to generate {format_type} format: {e}")
            
            return {
                "success": True,
                "generated_files": generated_files,
                "total_resources": len(resources),
                "processing_statistics": bom_data.processing_statistics,
                "generation_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"BOM document generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "generation_timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _generate_state_artifacts(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate state management artifacts for change tracking."""
        if not self.config.enable_state_management:
            return {}
            
        self.logger.info("Generating state management artifacts")
        
        try:
            # Initialize state manager
            state_manager = StateManager(
                state_directory=str(self.output_dir / "state"),
                retention_days=30
            )
            
            # Save current state
            state_id = state_manager.save_state(resources, {
                "multi_account": True,
                "total_accounts": len(self.account_contexts),
                "generation_type": "multi_account_bom"
            })
            
            results = {
                "state_saved": True,
                "state_id": state_id,
                "state_directory": str(self.output_dir / "state")
            }
            
            # Generate delta detection if enabled
            if self.config.enable_delta_detection:
                try:
                    delta_detector = DeltaDetector(state_manager)
                    previous_states = state_manager.list_states()
                    
                    if len(previous_states) > 1:
                        # Compare with previous state
                        previous_state_id = previous_states[-2]["state_id"]  # Second to last
                        delta_results = delta_detector.detect_changes(previous_state_id, state_id)
                        
                        results["delta_detection"] = {
                            "changes_detected": True,
                            "previous_state_id": previous_state_id,
                            "current_state_id": state_id,
                            "summary": delta_results
                        }
                        
                        # Generate changelog if enabled
                        if self.config.enable_changelog_generation:
                            changelog_generator = ChangelogGenerator(delta_detector)
                            changelog_file = self.output_dir / f"changelog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                            
                            changelog_generator.generate_changelog(
                                delta_results,
                                str(changelog_file),
                                title="Multi-Account Infrastructure Changes"
                            )
                            
                            results["changelog_generated"] = True
                            results["changelog_file"] = str(changelog_file)
                    else:
                        results["delta_detection"] = {
                            "changes_detected": False,
                            "reason": "No previous state available for comparison"
                        }
                        
                except Exception as e:
                    self.logger.warning(f"Delta detection failed: {e}")
                    results["delta_detection"] = {
                        "changes_detected": False,
                        "error": str(e)
                    }
            
            return results
            
        except Exception as e:
            self.logger.error(f"State artifact generation failed: {e}")
            return {
                "state_saved": False,
                "error": str(e)
            }

    @classmethod
    def from_credentials_file(cls, credentials_file: str, **kwargs) -> 'CloudBOMGenerator':
        """Create CloudBOMGenerator from a credentials file."""
        credentials_path = Path(credentials_file)
        
        if not credentials_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {credentials_file}")
        
        # Load credentials based on file extension
        if credentials_path.suffix.lower() in ['.yaml', '.yml']:
            with open(credentials_path, 'r') as f:
                data = yaml.safe_load(f)
        elif credentials_path.suffix.lower() == '.json':
            with open(credentials_path, 'r') as f:
                data = json.load(f)
        else:
            raise ValueError(f"Unsupported credentials file format: {credentials_path.suffix}")
        
        # Parse accounts
        accounts = []
        for account_data in data.get('accounts', []):
            accounts.append(AccountCredentials(**account_data))
        
        # Create config
        config_data = data.get('config', {})
        config_data.update(kwargs)
        config_data['accounts'] = accounts
        
        config = MultiAccountConfig(**config_data)
        
        return cls(config)

    @classmethod
    def from_interactive_prompt(cls, **kwargs) -> 'CloudBOMGenerator':
        """Create CloudBOMGenerator from interactive credential prompts."""
        print("InvenTag Multi-Account BOM Generator Setup")
        print("=" * 50)
        
        accounts = []
        
        while True:
            print(f"\nConfiguring Account #{len(accounts) + 1}")
            print("-" * 30)
            
            account_id = input("Account ID: ").strip()
            if not account_id:
                break
                
            account_name = input("Account Name (optional): ").strip()
            
            # Authentication method
            print("\nAuthentication method:")
            print("1. AWS Profile")
            print("2. Access Keys")
            print("3. Role ARN")
            print("4. Cross-account role (will use configured role name)")
            
            auth_method = input("Select method (1-4): ").strip()
            
            credentials = AccountCredentials(
                account_id=account_id,
                account_name=account_name or f"Account-{account_id}"
            )
            
            if auth_method == "1":
                credentials.profile_name = input("AWS Profile Name: ").strip()
            elif auth_method == "2":
                credentials.access_key_id = input("Access Key ID: ").strip()
                credentials.secret_access_key = getpass.getpass("Secret Access Key: ")
                session_token = getpass.getpass("Session Token (optional): ")
                if session_token:
                    credentials.session_token = session_token
            elif auth_method == "3":
                credentials.role_arn = input("Role ARN: ").strip()
                external_id = input("External ID (optional): ").strip()
                if external_id:
                    credentials.external_id = external_id
            # Method 4 uses default cross-account role
            
            # Regions
            regions_input = input("Regions (comma-separated, default: us-east-1): ").strip()
            if regions_input:
                credentials.regions = [r.strip() for r in regions_input.split(",")]
            
            accounts.append(credentials)
            
            continue_prompt = input("\nAdd another account? (y/N): ").strip().lower()
            if continue_prompt not in ['y', 'yes']:
                break
        
        if not accounts:
            raise ValueError("No accounts configured")
        
        # Create config
        config = MultiAccountConfig(accounts=accounts, **kwargs)
        
        return cls(config)