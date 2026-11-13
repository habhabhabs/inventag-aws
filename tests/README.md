# InvenTag Test Suite

This directory contains comprehensive test suites for the InvenTag unified platform, ensuring backward compatibility and validating the architectural transformation from standalone scripts to a unified package.

## Test Structure

### Backward Compatibility Tests (`backward_compatibility/`)

These tests ensure that the transformation to the unified `inventag` package maintains complete backward compatibility with existing script interfaces and outputs.

#### `test_script_interfaces.py`
- **Purpose**: Validates that existing script interfaces produce identical outputs
- **Coverage**: 
  - CLI argument parsing compatibility for all scripts
  - Help command functionality
  - Import compatibility and fallback mechanisms
  - Output format preservation
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_output_format_validation.py`
- **Purpose**: Creates test fixtures and validates output format preservation
- **Coverage**:
  - JSON/YAML output structure validation
  - CSV/Excel format compatibility
  - Automated comparison of legacy vs new package outputs
  - Regression validation against reference fixtures
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_github_actions_compatibility.py`
- **Purpose**: Ensures all existing GitHub Actions checks pass
- **Coverage**:
  - Workflow file structure validation
  - CI job compatibility testing
  - Security scan compatibility
  - Dependency and version compatibility
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `fixtures/`
Reference output files for regression testing:
- `reference_inventory.json`: Standard inventory output format
- `reference_compliance.json`: Standard compliance report format

### Unit Tests (`unit/`)

Comprehensive unit testing for all extracted `inventag` modules with mock AWS responses and error handling scenarios.

#### `test_dynamic_service_handler.py`
- **Purpose**: Unit tests for `DynamicServiceHandler` pattern-based discovery system
- **Coverage**:
  - Pattern generation for unknown AWS services
  - Parameter pattern matching and validation
  - Successful resource enrichment with mock responses
  - Error handling for unknown services and API failures
  - Response data extraction from various formats
  - Caching functionality and performance optimization
  - Read-only operation validation
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_discovery_module.py`
- **Purpose**: Unit tests for `inventag.discovery` module
- **Coverage**:
  - AWS resource discovery with mock responses
  - Error handling and graceful degradation
  - Performance testing with large datasets (1000+ resources)
  - Security validation (read-only operations only)
  - Utility method testing
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_compliance_manager.py`
- **Purpose**: Unit tests for `ComplianceManager` unified compliance orchestration
- **Coverage**:
  - Comprehensive compliance management functionality
  - Security validation and production monitoring integration
  - Error handling and graceful degradation
  - Compliance status assessment and reporting
  - Dashboard data generation and audit log management
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_production_monitor.py`
- **Purpose**: Unit tests for `ProductionSafetyMonitor` enterprise-grade monitoring
- **Coverage**:
  - Error handling with graceful degradation
  - Circuit breaker pattern implementation
  - Performance monitoring and metrics collection
  - CloudTrail integration for audit trails
  - Security validation reporting
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_security_validator.py`
- **Purpose**: Unit tests for `ReadOnlyAccessValidator` security validation
- **Coverage**:
  - Read-only operation classification and validation
  - AWS permissions validation
  - Compliance reporting and audit logging
  - Security findings generation
  - Identity type determination and validation
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_compliance_module.py`
- **Purpose**: Unit tests for `inventag.compliance` module
- **Coverage**:
  - Tag policy validation with various scenarios
  - Advanced policy features (exemptions, patterns, service-specific rules)
  - Error handling for malformed data and configs
  - Performance testing with large datasets
  - Security validation (no sensitive data in logs)
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_template_framework_comprehensive.py`
- **Purpose**: Unit tests for comprehensive document template framework
- **Coverage**:
  - Template variable resolution and substitution
  - Document structure building and validation
  - Table of contents generation
  - Template loading from JSON/YAML files
  - Custom template creation and management
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_document_generator_comprehensive.py`
- **Purpose**: Unit tests for multi-format document generation
- **Coverage**:
  - Excel, Word, and CSV document generation
  - Professional branding and styling application
  - Template framework integration
  - Parallel document generation
  - Error handling and recovery
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

#### `test_reporting_module.py`
- **Purpose**: Unit tests for `inventag.reporting` module
- **Coverage**:
  - Data processing and transformation
  - CSV/Excel export functionality
  - VPC enrichment capabilities
  - Error handling scenarios
  - Performance testing with large datasets
  - Multi-format data compatibility
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

### Regression Tests (`regression/`)

These two files are scripts, not pytest tests: their classes are not named `Test*`,
so `pytest` collects nothing from them, and no CI workflow runs them. Run them by
hand as shown under "Run Specific Test Categories".

Comprehensive regression test suites to validate full InvenTag functionality and prevent regressions.

#### `test_quick_regression.py`
- **Purpose**: Rapid validation of core functionality without AWS credentials
- **Coverage**:
  - CLI help and validation systems
  - Fallback display options (auto/always/never)
  - Configuration file validation
  - Core module imports and initialization
  - Intelligent fallback logic implementation
  - AWS Prescriptive Guidance templates
  - Documentation completeness
- **Execution Time**: < 30 seconds
- **Requirements**: No AWS credentials required

#### `test_full_regression.py`
- **Purpose**: Comprehensive end-to-end functionality validation
- **Coverage**:
  - Complete BOM generation workflows (Excel, Word, combined)
  - Fallback display mode testing (auto/always/never)
  - AWS Prescriptive Guidance template integration
  - Analysis features (network, security, cost)
  - Production safety features and security validation
  - State management and change detection
  - Service-specific and multi-region discovery
  - Error handling and edge cases
  - Output file verification
- **Execution Time**: 30-45 minutes
- **Requirements**: Valid AWS credentials for full testing

### Integration Tests (`integration/`)

End-to-end integration testing for complete workflows and CI/CD pipeline integration.

#### `test_end_to_end_workflows.py`
- **Purpose**: End-to-end workflow testing
- **Coverage**:
  - Complete discovery → compliance → BOM generation workflows
  - Multi-format output validation (Excel, CSV, JSON, YAML)
  - Configuration file loading and validation
  - Mock AWS environment testing
  - CI/CD pipeline integration simulation
  - Performance benchmarks to ensure no regression
- **Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

## What Every Test Gets for Free (`conftest.py`)

These fixtures are `autouse`, so no test has to ask for them:

- **Fake credentials.** `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are always
  replaced with fakes, even if your shell has real ones. Session tokens, profiles,
  web-identity and container credential variables are removed.
- **No network.** A socket connection to a non-loopback address raises `OSError`
  (it names the address). Proxy variables are removed so a stray call is refused
  at its real destination.
- **Scratch home.** `HOME`, `XDG_CONFIG_HOME` and the AWS shared config files point
  into a temporary directory, so no test reads or writes your real `~`.
- **No log files in the repository.** `production_monitor` and `security_validator`
  open `inventag_*.log` in the current directory; the fixture redirects those bare
  names to a temporary directory.
- **No leaked monitor threads.** `ProductionSafetyMonitor` loops that a test starts
  and forgets are stopped when the test ends.

`tests/unit/test_test_isolation.py` tests these fixtures.

## End-to-End Tests (`e2e/`)

Whole-CLI runs against moto's in-memory AWS. They read back the files the CLI wrote.

| File | What it covers |
|---|---|
| `test_cli_end_to_end.py` | `main()` in process: default run, Word, Excel, both, service filter, network/security/cost analysis, multi-account file, per-account reports, change tracking and changelog, `--audit-output`, exit codes 0, 1, 2, 3 and 4 |
| `test_cli_subprocess.py` | `python -m inventag` in a child process through `_moto_runner.py`: the real entry point, exit codes, stdout and stderr |
| `test_discovery_completeness.py` | paginated list calls; an `xfail(strict=True)` test for a known defect |
| `test_live_smoke_script.py` | `scripts/live_smoke_test.py` against moto, including one test per failing check |
| `test_benchmark_script.py` | `scripts/benchmark_scan.py` |

`estate.py` builds the fixed estate (VPC, subnet, open security group, bucket, queue,
topic, table; optionally an instance and a Lambda function). Each scan takes 5 to 15
seconds. moto's HTTP server mode is not used because it needs Flask, which is not a
dependency. moto's default AMIs are switched off (`MOTO_EC2_LOAD_DEFAULT_AMIS=false`):
they add about 1,300 snapshots to every scan.

A test marked `xfail(strict=True)` documents a defect in `inventag/`. When the defect
is fixed the test fails with XPASS; delete the marker then.

## Scripts That Use This Setup

- `scripts/live_smoke_test.py`: for the owner, against a real AWS account with a
  read-only profile. See the header of the file.
- `scripts/benchmark_scan.py`: builds a synthetic estate in moto and reports scan
  time, API call counts and peak memory.

## Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Backward compatibility tests
python -m pytest tests/backward_compatibility/ -v

# Unit tests
python -m pytest tests/unit/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Regression tests (quick validation)
python3 tests/regression/test_quick_regression.py

# Regression tests (comprehensive with AWS)
python3 tests/regression/test_full_regression.py

# Dynamic service handler tests
python -m pytest tests/unit/test_dynamic_service_handler.py -v

# Production safety and compliance tests
python -m pytest tests/unit/test_compliance_manager.py tests/unit/test_production_monitor.py tests/unit/test_security_validator.py -v

# Template framework and document generation tests
python -m pytest tests/unit/test_template_framework_comprehensive.py tests/unit/test_document_generator_comprehensive.py -v
```

### Run Tests with Coverage
```bash
python -m pytest tests/ -v --cov=inventag --cov=scripts --cov-report=html
```

### Run Performance Tests
The nine tests in `integration/test_performance_benchmarks.py` are marked
`performance` and skipped by default (`addopts` in `pytest.ini` has
`-m "not performance"`). They use wall-clock limits, so run them on a quiet
machine. `-k performance` does not select them; use the marker:
```bash
python -m pytest -m performance -o addopts= tests/integration/test_performance_benchmarks.py -v
```

### Run the End-to-End Tests Only
```bash
python -m pytest -m e2e tests/e2e -v
```

### Run Security Tests
```bash
python -m pytest tests/ -v -k "security"
```

## Test Features

### Mock AWS Responses
All tests use comprehensive AWS service mocks to avoid requiring actual AWS credentials or making real API calls.

### Error Handling Validation
Tests validate graceful degradation when:
- AWS credentials are missing
- Services are unavailable
- API responses are malformed
- Configuration files are invalid

### Performance Testing
Tests validate performance with large datasets (1000+ resources) and ensure:
- Processing completes within reasonable time limits
- Memory usage remains within acceptable bounds
- No performance regression from the original scripts

### Security Validation
Tests ensure:
- Only read-only AWS operations are used
- No sensitive data appears in logs
- Configuration validation prevents injection attacks

### GitHub Actions Compatibility
Tests simulate the existing CI/CD pipeline to ensure:
- All workflow files are valid
- Required jobs and steps are present
- Python version compatibility is maintained
- Dependencies can be installed successfully

## Test Data

### Sample Resources
Tests use realistic AWS resource data covering:
- EC2 (Instances, Volumes, Security Groups, VPCs, Subnets)
- S3 (Buckets)
- RDS (DB Instances, DB Clusters)
- Lambda (Functions)
- IAM (Roles, Users, Policies)
- CloudFormation (Stacks)
- ECS (Clusters)
- EKS (Clusters)
- Unknown Services (TEXTRACT, COMPREHEND, etc.) for dynamic discovery testing

### Tag Policies
Tests include various tag policy configurations:
- Basic required/optional tags
- Advanced patterns and exemptions
- Service-specific rules
- Invalid configurations for error testing

## Continuous Integration

These tests are designed to run in GitHub Actions and validate:
- Backward compatibility is maintained
- All existing functionality continues to work
- New features don't break existing workflows
- Performance doesn't regress
- Security standards are maintained

## Requirements Traceability

All tests are mapped to specific requirements (13.1-13.6) ensuring complete coverage of:
- GitHub Actions compatibility (13.1)
- Backward compatibility maintenance (13.2)
- Test suite integration with CI/CD (13.3)
- Comprehensive test coverage (13.4)
- Quality check integration (13.5)
- Deployment compatibility (13.6)