# Regression Testing Guide

## Overview

InvenTag AWS includes a comprehensive regression test suite to validate full functionality including BOM generation, discovery systems, compliance checking, and all advanced features. This ensures code changes don't break existing functionality.

## Running Regression Tests

### Quick Regression Test

For rapid validation of core functionality:

```bash
python3 tests/regression/test_quick_regression.py
```

**Test Coverage:**
- ✅ CLI Help and validation
- ✅ Fallback display options (auto/always/never)
- ✅ Configuration file validation
- ✅ Core module imports
- ✅ Intelligent fallback logic
- ✅ AWS Prescriptive Guidance templates
- ✅ Documentation completeness

### Comprehensive Regression Test

For thorough end-to-end testing (requires AWS credentials):

```bash
python3 tests/regression/test_full_regression.py
```

**Test Categories:**

#### 1. CLI Help and Validation
- CLI help display functionality
- Configuration file validation
- Credential validation checks

#### 2. Fallback Display Modes
Tests the intelligent fallback resource display system:
```bash
# Auto mode (recommended) - shows fallback only when no primary resources found
--fallback-display=auto

# Always mode - shows all fallback resources for maximum visibility  
--fallback-display=always

# Never mode - hides all fallback resources
--fallback-display=never

# Legacy compatibility
--hide-fallback-resources
```

#### 3. BOM Generation Formats
- Excel format generation (`.xlsx`)
- Word format generation (`.docx`)
- Combined format generation

#### 4. AWS Prescriptive Guidance Templates
- AWS compliant tagging dictionary integration
- Service descriptions with AWS standards
- 5-step methodology validation

#### 5. Analysis Features
- Network analysis (VPC, subnets, security groups)
- Security analysis (posture assessment, compliance)
- Cost analysis (optimization recommendations)
- Combined analysis workflows

#### 6. Production Safety Features
- Production safety monitoring
- Security validation frameworks
- Read-only operation enforcement
- Combined safety feature validation

#### 7. State Management
- Baseline state creation
- Delta detection between runs
- Changelog generation
- Change tracking validation

#### 8. Service-Specific Discovery
Testing discovery for key AWS services:
- Core services: `ec2,s3,iam`
- Compute services: `lambda,rds,vpc`
- Management services: `cloudformation,cloudtrail`

#### 9. Multi-Region Discovery
- Single region discovery (`us-east-1`)
- Dual region discovery (`us-east-1,us-west-2`)
- Multi-region discovery (`us-east-1,eu-west-1,ap-southeast-1`)

#### 10. Error Handling
- Invalid region handling
- Invalid service handling
- Invalid output directory handling

#### 11. Output File Verification
Validates generated files:
- BOM Excel files (`bom_*.xlsx`)
- BOM Word documents (`bom_*.docx`)
- Inventory JSON files (`inventory_*.json`)
- State tracking files (`state_*.json`)

## Test Reports

The regression test suite generates detailed reports:

```json
{
  "summary": {
    "total_tests": 45,
    "passed_tests": 43,
    "failed_tests": 2,
    "success_rate": 95.6,
    "total_time_seconds": 1847.3,
    "timestamp": "2025-08-08T10:30:00Z"
  },
  "test_results": [...]
}
```

## Continuous Integration

### GitHub Actions Integration

Add to `.github/workflows/regression.yml`:

```yaml
name: Regression Tests
on: [push, pull_request]

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .
      
      - name: Run quick regression tests
        run: python3 tests/regression/test_quick_regression.py
      
      - name: Run comprehensive tests (with credentials)
        if: env.AWS_ACCESS_KEY_ID
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: python3 tests/regression/test_full_regression.py
```

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: regression-test
        name: Quick regression test
        entry: python3 tests/regression/test_quick_regression.py
        language: system
        pass_filenames: false
        always_run: true
```

## Debugging Test Failures

### Common Issues

1. **Timeout Errors**
   ```
   ⏱️ TIMEOUT after 300s
   ```
   - **Solution**: Increase timeout values for complex operations
   - **Check**: Network connectivity and AWS API responsiveness

2. **Credential Errors**
   ```
   ❌ FAILED: Credential validation failed
   ```
   - **Solution**: Verify AWS credentials with `aws sts get-caller-identity`
   - **Check**: IAM permissions and credential expiration

3. **CLI Argument Errors**
   ```
   Exit code: 2
   Error: unrecognized arguments: --regions
   ```
   - **Solution**: Use correct argument format (`--account-regions` not `--regions`)
   - **Check**: CLI help with `python3 -m inventag.cli.main --help`

### Test Environment Cleanup

Failed tests preserve output directories for analysis:

```bash
⚠️ Keeping test outputs for analysis: /tmp/inventag_regression_20250808_103045
```

**Manual Cleanup:**
```bash
# List test output directories
ls /tmp/inventag_regression_*

# Remove specific test directory
rm -rf /tmp/inventag_regression_20250808_103045

# Remove all test directories
rm -rf /tmp/inventag_regression_*
```

## Test Development Guidelines

### Adding New Tests

1. **Create test method** in `RegressionTestRunner` class:
```python
def test_new_feature(self):
    """Test new feature functionality."""
    print("\n" + "="*60)
    print("🧪 TESTING: New Feature")
    print("="*60)
    
    self.run_command(
        "command_to_test",
        "Test Description",
        timeout=300
    )
```

2. **Add to test suite** in `run_all_tests()`:
```python
def run_all_tests(self):
    try:
        self.setup()
        # ... existing tests
        self.test_new_feature()  # Add here
        # ... remaining tests
```

### Test Categories

Organize tests by functional area:
- **Core Functionality**: CLI, configuration, credentials
- **Feature Tests**: Analysis, safety, state management
- **Discovery Tests**: Service-specific, multi-region
- **Error Handling**: Invalid inputs, edge cases
- **Integration Tests**: AWS services, external dependencies

## Performance Benchmarks

Expected test completion times:

| Test Category | Quick Test | Full Test |
|---------------|------------|-----------|
| CLI & Config | < 30s | < 2min |
| Fallback Logic | N/A | < 10min |
| BOM Generation | N/A | < 15min |
| Analysis Features | N/A | < 20min |
| Multi-Region | N/A | < 25min |
| **Total** | **< 30s** | **< 45min** |

## Fallback Mechanism Validation

The regression tests specifically validate the intelligent fallback mechanism:

### Auto Mode Testing
```python
# Test that services with no primary resources show fallback resources
# Example: AWS RoboMaker typically has no primary resources but may have fallback
service_has_primary = check_primary_resources("robomaker")
service_has_fallback = check_fallback_resources("robomaker") 

# Validation: If no primary resources, fallback should be shown in auto mode
assert not service_has_primary and service_has_fallback
```

### Legacy Compatibility Testing
```python
# Verify --hide-fallback-resources equals --fallback-display=never
cmd1 = "./inventag.sh --hide-fallback-resources --create-excel"
cmd2 = "./inventag.sh --fallback-display=never --create-excel"
# Both should produce identical results
```

## Troubleshooting Guide

### Quick Diagnostics

Run these commands to diagnose issues:

```bash
# Test AWS credentials
aws sts get-caller-identity

# Verify CLI functionality
python3 -m inventag.cli.main --help

# Check configuration files
python3 -m inventag.cli.main --validate-config-only

# Test basic discovery
./inventag.sh --validate-config

# Test specific regions
./inventag.sh --account-regions us-east-1 --create-excel
```

### Log Analysis

Enable debug logging for detailed troubleshooting:

```bash
# Run with debug logging
python3 tests/regression/test_full_regression.py --debug

# Review specific test logs
tail -f inventag-debug.log

# Check AWS API calls
export AWS_SDK_LOAD_CONFIG=1
export BOTO_LOG_LEVEL=DEBUG
```

## Best Practices

1. **Run Quick Tests First**: Always run quick regression tests before comprehensive ones
2. **Test on Clean Environment**: Use fresh virtual environments for accurate results
3. **Monitor Resource Usage**: Watch CPU, memory, and network usage during tests
4. **Validate Outputs**: Check generated files for completeness and accuracy
5. **Document New Tests**: Update this guide when adding new test categories
6. **Use Appropriate Timeouts**: Scale timeouts based on operation complexity
7. **Clean Up Resources**: Ensure tests don't leave temporary resources in AWS
8. **Version Test Data**: Track test data versions to ensure reproducibility

## Integration with AWS Prescriptive Guidance

The regression tests validate compliance with AWS Prescriptive Guidance:

- ✅ **5-Step Methodology**: Define, Publish, Apply Rules, Apply Tags, Measure/Evolve
- ✅ **Three-Dimensional Tagging**: Technical, Business, Security dimensions
- ✅ **Hyphen-Separated Naming**: `cost-center-id`, `project-id`, `environment-id`
- ✅ **FinOps Integration**: Cost allocation and optimization features
- ✅ **2025 Advanced Capabilities**: Latest compliance and governance features

This ensures InvenTag maintains alignment with AWS official guidance and industry best practices.