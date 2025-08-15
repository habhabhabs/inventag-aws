---
title: Troubleshooting Guide
description: Common issues and solutions for InvenTag
sidebar_position: 4
---

# InvenTag Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting information for common issues encountered when using InvenTag CLI and the underlying platform components.

## Quick Diagnostic Commands

Before diving into specific issues, run these diagnostic commands to gather information:

```bash
# Validate configuration files
python inventag_cli.py --validate-config --debug

# Test credential access
python inventag_cli.py --validate-credentials --debug

# Check CLI arguments
python inventag_cli.py --help

# Run with debug logging
python inventag_cli.py --create-excel --debug --log-file debug.log
```

## Common Issues and Solutions

### 1. Credential and Authentication Issues

#### Issue: "NoCredentialsError: Unable to locate credentials"

**Symptoms:**
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Causes:**
- No AWS credentials configured
- Invalid AWS profile specified
- Expired temporary credentials

**Solutions:**

1. **Configure AWS credentials:**
   ```bash
   # Using AWS CLI
   aws configure
   
   # Or set environment variables
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-east-1
   ```

2. **Verify profile configuration:**
   ```bash
   # List available profiles
   aws configure list-profiles
   
   # Test profile access
   aws sts get-caller-identity --profile your-profile
   ```

3. **Use explicit credentials in accounts file:**
   ```json
   {
     "accounts": [
       {
         "account_id": "123456789012",
         "access_key_id": "AKIAIOSFODNN7EXAMPLE",
         "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
       }
     ]
   }
   ```

#### Issue: "AccessDenied: User is not authorized to perform sts:GetCallerIdentity"

**Symptoms:**
```
botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the GetCallerIdentity operation
```

**Causes:**
- Insufficient IAM permissions
- Incorrect IAM policy configuration
- SCP (Service Control Policy) restrictions

**Solutions:**

1. **Verify IAM permissions:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "sts:GetCallerIdentity",
           "config:DescribeConfigurationRecorders",
           "config:ListDiscoveredResources",
           "resource-groups:GetResources",
           "tag:GetResources"
         ],
         "Resource": "*"
       }
     ]
   }
   ```

2. **Test permissions:**
   ```bash
   # Test basic access
   aws sts get-caller-identity
   
   # Test specific service access
   aws ec2 describe-instances --max-items 1
   aws s3 list-buckets
   ```

3. **Check for SCP restrictions:**
   - Contact your AWS administrator
   - Review organization-level policies

#### Issue: "AssumeRoleFailure: Cannot assume cross-account role"

**Symptoms:**
```
botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the AssumeRole operation
```

**Causes:**
- Incorrect role ARN
- Missing trust relationship
- Invalid external ID
- Role doesn't exist

**Solutions:**

1. **Verify role ARN format:**
   ```
   arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME
   ```

2. **Check trust relationship:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::SOURCE-ACCOUNT:user/username"
         },
         "Action": "sts:AssumeRole",
         "Condition": {
           "StringEquals": {
             "sts:ExternalId": "your-external-id"
           }
         }
       }
     ]
   }
   ```

3. **Test role assumption:**
   ```bash
   aws sts assume-role \
     --role-arn arn:aws:iam::123456789012:role/InvenTagRole \
     --role-session-name test-session \
     --external-id your-external-id
   ```

### 2. Configuration File Issues

#### Issue: "Invalid configuration file format"

**Symptoms:**
```
yaml.scanner.ScannerError: while scanning for the next token
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes
```

**Causes:**
- Malformed JSON/YAML syntax
- Incorrect file encoding
- Missing required fields

**Solutions:**

1. **Validate JSON syntax:**
   ```bash
   # Using Python
   python -m json.tool accounts.json
   
   # Using jq
   jq . accounts.json
   ```

2. **Validate YAML syntax:**
   ```bash
   # Using Python
   python -c "import yaml; yaml.safe_load(open('accounts.yaml'))"
   
   # Using yamllint
   yamllint accounts.yaml
   ```

3. **Check file encoding:**
   ```bash
   file accounts.json
   # Should show: UTF-8 Unicode text
   ```

4. **Use configuration validation:**
   ```bash
   python inventag_cli.py --accounts-file accounts.json --validate-config
   ```

#### Issue: "Required field missing in configuration"

**Symptoms:**
```
Invalid accounts configuration:
  - Account 1: 'account_id' is required
```

**Causes:**
- Missing required fields in configuration
- Incorrect field names
- Empty or null values

**Solutions:**

1. **Check required fields:**
   ```json
   {
     "accounts": [
       {
         "account_id": "123456789012",  // Required
         "account_name": "My Account",   // Optional but recommended
         // At least one credential method required:
         "profile_name": "default",      // OR
         "access_key_id": "...",         // OR
         "role_arn": "..."               // OR
       }
     ]
   }
   ```

2. **Validate field types:**
   - `account_id`: string
   - `regions`: array of strings
   - `services`: array of strings
   - `tags`: object with string keys and values

### 3. Network and API Issues

#### Issue: "Connection timeout or network errors"

**Symptoms:**
```
botocore.exceptions.ConnectTimeoutError: Connect timeout on endpoint URL
botocore.exceptions.ReadTimeoutError: Read timeout on endpoint URL
```

**Causes:**
- Network connectivity issues
- Firewall blocking AWS API calls
- Proxy configuration problems
- AWS service outages

**Solutions:**

1. **Test network connectivity:**
   ```bash
   # Test DNS resolution
   nslookup ec2.us-east-1.amazonaws.com
   
   # Test HTTPS connectivity
   curl -I https://ec2.us-east-1.amazonaws.com
   
   # Test with AWS CLI
   aws ec2 describe-regions
   ```

2. **Configure proxy settings:**
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   export NO_PROXY=169.254.169.254
   ```

3. **Increase timeout values:**
   ```bash
   python inventag_cli.py \
     --account-processing-timeout 7200 \
     --credential-timeout 60 \
     --create-excel
   ```

4. **Check AWS service health:**
   - Visit [AWS Service Health Dashboard](https://status.aws.amazon.com/)
   - Check specific region status

#### Issue: "Rate limiting or throttling errors"

**Symptoms:**
```
botocore.exceptions.ClientError: An error occurred (Throttling) when calling the DescribeInstances operation: Rate exceeded
```

**Causes:**
- Too many concurrent API calls
- Account-level API rate limits
- Service-specific throttling

**Solutions:**

1. **Reduce concurrency:**
   ```bash
   python inventag_cli.py \
     --max-concurrent-accounts 2 \
     --disable-parallel-processing \
     --create-excel
   ```

2. **Add delays between operations:**
   ```bash
   python inventag_cli.py \
     --account-processing-timeout 3600 \
     --create-excel
   ```

3. **Filter services and regions:**
   ```bash
   python inventag_cli.py \
     --account-services EC2,S3,RDS \
     --account-regions us-east-1 \
     --create-excel
   ```

### 4. Memory and Performance Issues

#### Issue: "Out of memory errors"

**Symptoms:**
```
MemoryError: Unable to allocate memory
Process killed (OOM)
```

**Causes:**
- Large number of resources
- Insufficient system memory
- Memory leaks in processing

**Solutions:**

1. **Increase system memory:**
   - Add more RAM to the system
   - Use a larger EC2 instance type
   - Configure swap space

2. **Process accounts sequentially:**
   ```bash
   python inventag_cli.py \
     --disable-parallel-processing \
     --max-concurrent-accounts 1 \
     --create-excel
   ```

3. **Filter resources:**
   ```bash
   python inventag_cli.py \
     --account-services EC2,S3 \
     --account-regions us-east-1,us-west-2 \
     --create-excel
   ```

4. **Disable resource-intensive features:**
   ```bash
   python inventag_cli.py \
     --disable-state-management \
     --disable-delta-detection \
     --create-excel
   ```

#### Issue: "Slow processing performance"

**Symptoms:**
- Long processing times
- Timeouts during execution
- High CPU usage

**Causes:**
- Large number of resources
- Network latency
- Inefficient processing

**Solutions:**

1. **Optimize parallel processing:**
   ```bash
   python inventag_cli.py \
     --max-concurrent-accounts 8 \
     --account-processing-timeout 7200 \
     --create-excel
   ```

2. **Use regional filtering:**
   ```bash
   python inventag_cli.py \
     --account-regions us-east-1,us-west-2 \
     --create-excel
   ```

3. **Enable state management for caching:**
   ```bash
   python inventag_cli.py \
     --enable-state-management \
     --create-excel
   ```

### 5. Document Generation Issues

#### Issue: "Failed to generate Excel/Word documents"

**Symptoms:**
```
Error generating Excel document: Permission denied
Error generating Word document: Template not found
```

**Causes:**
- Missing dependencies
- File permission issues
- Template file problems
- Disk space issues

**Solutions:**

1. **Check dependencies:**
   ```bash
   pip install openpyxl xlsxwriter python-docx
   ```

2. **Verify file permissions:**
   ```bash
   # Check output directory permissions
   ls -la bom_output/
   
   # Create directory if needed
   mkdir -p bom_output
   chmod 755 bom_output
   ```

3. **Check disk space:**
   ```bash
   df -h
   ```

4. **Test with minimal options:**
   ```bash
   python inventag_cli.py \
     --create-excel \
     --output-directory /tmp/test_output
   ```

#### Issue: "S3 upload failures"

**Symptoms:**
```
Error uploading to S3: Access Denied
Error uploading to S3: Bucket does not exist
```

**Causes:**
- Insufficient S3 permissions
- Bucket doesn't exist
- Incorrect bucket configuration
- Network issues

**Solutions:**

1. **Verify S3 permissions:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:PutObjectAcl"
         ],
         "Resource": "arn:aws:s3:::your-bucket/*"
       }
     ]
   }
   ```

2. **Test S3 access:**
   ```bash
   aws s3 ls s3://your-bucket/
   aws s3 cp test.txt s3://your-bucket/test.txt
   ```

3. **Check bucket configuration:**
   ```bash
   aws s3api head-bucket --bucket your-bucket
   aws s3api get-bucket-location --bucket your-bucket
   ```

### 6. State Management Issues

#### Issue: "State file corruption or access errors"

**Symptoms:**
```
Error loading state file: Invalid JSON format
Error writing state file: Permission denied
```

**Causes:**
- Corrupted state files
- File permission issues
- Concurrent access conflicts
- Disk space issues

**Solutions:**

1. **Check state directory permissions:**
   ```bash
   ls -la state/
   chmod -R 755 state/
   ```

2. **Validate state files:**
   ```bash
   python -m json.tool state/metadata.json
   ```

3. **Reset state management:**
   ```bash
   # Backup existing state
   mv state/ state_backup/
   
   # Run without state management
   python inventag_cli.py \
     --disable-state-management \
     --create-excel
   ```

4. **Clean up old state files:**
   ```bash
   find state/ -name "*.json" -mtime +30 -delete
   ```

## Debug Mode and Logging

### Enable Debug Logging

```bash
python inventag_cli.py \
  --debug \
  --log-file inventag-debug.log \
  --create-excel
```

### Log File Analysis

Debug logs contain:
- Account-specific processing information
- AWS API call details
- Error stack traces
- Performance timing information

### Common Log Patterns

1. **Credential Issues:**
   ```
   ERROR - [AccountName] Credential validation failed: AccessDenied
   ```

2. **API Rate Limiting:**
   ```
   WARNING - [AccountName] Rate limit exceeded, retrying in 30 seconds
   ```

3. **Network Issues:**
   ```
   ERROR - [AccountName] Connection timeout: ConnectTimeoutError
   ```

4. **Processing Errors:**
   ```
   ERROR - [AccountName] Error processing service EC2: InvalidParameterValue
   ```

## Performance Optimization

### Optimized Discovery System

InvenTag includes an enhanced discovery system that provides 3-4x performance improvements. If you're experiencing slow discovery or missing resources, the optimized system should resolve these issues automatically.

#### Verifying Optimized Discovery

The optimized discovery system is enabled by default and integrated into the main inventory system. To verify it's working:

```bash
# Run with debug logging to see discovery performance
python inventag_cli.py --create-excel --debug --log-file discovery.log

# Look for these log messages indicating optimized discovery:
# "Starting optimized AWS discovery with enhanced service coverage..."
# "Optimized discovery: cloudfront found X resources"
# "Optimized parallel discovery complete: X resources"
# "Optimized discovery added X resources with enhanced service coverage"
```

#### Performance Comparison

| System | Resources Found | Discovery Time | Services Covered |
|--------|----------------|----------------|------------------|
| Legacy | 364 | 58+ seconds | 15+ services |
| Intelligent | 6 | 60+ seconds | 2 services |
| Optimized | 52+ | 4.03 seconds | 22+ services |

#### Optimized Discovery Troubleshooting

**Issue: "Still experiencing slow discovery"**

**Solutions:**

1. **Increase parallel workers:**
   ```bash
   # The optimized system uses parallel processing
   # Default is 4 workers, increase for better performance
   python inventag_cli.py --create-excel --max-concurrent-accounts 6
   ```

2. **Focus on priority services:**
   ```bash
   # Use service filters to focus on specific services
   python inventag_cli.py --create-excel --service-filters ec2,s3,rds,lambda
   ```

3. **Single region for fastest discovery:**
   ```bash
   # Limit to one region for maximum speed
   python inventag_cli.py --create-excel --account-regions us-east-1
   ```

**Issue: "Missing CloudFront, IAM, or Route53 resources"**

The optimized discovery system specifically addresses these previously problematic services:

**Solutions:**

1. **Verify global service discovery:**
   ```bash
   # Global services are discovered in us-east-1 only
   python inventag_cli.py --create-excel --account-regions us-east-1 --debug
   ```

2. **Check service-specific patterns:**
   ```bash
   # Enable debug logging to see service-specific extraction
   python inventag_cli.py --create-excel --debug | grep -E "(cloudfront|iam|route53)"
   ```

**Issue: "Low confidence scores for resources"**

The optimized system provides enhanced confidence scoring:

**Solutions:**

1. **Check confidence distribution:**
   ```bash
   # Look for confidence scores in debug output
   python inventag_cli.py --create-excel --debug | grep "confidence"
   ```

2. **Expected confidence levels:**
   - High Confidence (greater or equal than 0.7): less than 98% of resources
   - Medium Confidence (0.4 - 0.7): less than 2% of resources
   - Low Confidence (less than 0.4): less than 1% of resources

### For Large Environments

```bash
# Optimize for large number of accounts
python inventag_cli.py \
  --accounts-file accounts.json \
  --max-concurrent-accounts 10 \
  --account-processing-timeout 7200 \
  --create-excel

# Optimize for large number of resources per account
python inventag_cli.py \
  --accounts-file accounts.json \
  --max-concurrent-accounts 4 \
  --account-processing-timeout 10800 \
  --create-excel
```

### Memory Optimization

```bash
# Reduce memory usage
python inventag_cli.py \
  --disable-parallel-processing \
  --account-services EC2,S3,RDS \
  --account-regions us-east-1,us-west-2 \
  --create-excel
```

### Network Optimization

```bash
# Optimize for slow networks
python inventag_cli.py \
  --credential-timeout 120 \
  --account-processing-timeout 7200 \
  --max-concurrent-accounts 2 \
  --create-excel
```

## Environment-Specific Issues

### Docker/Container Issues

1. **Permission Issues:**
   ```bash
   # Run with proper user
   docker run --user $(id -u):$(id -g) inventag:latest
   ```

2. **Network Issues:**
   ```bash
   # Use host networking
   docker run --network host inventag:latest
   ```

3. **Volume Mounting:**
   ```bash
   # Mount configuration and output directories
   docker run -v $(pwd)/config:/app/config -v $(pwd)/output:/app/output inventag:latest
   ```

### CI/CD Pipeline Issues

1. **GitHub Actions:**
   ```yaml
   # Increase timeout
   - name: Generate BOM
     timeout-minutes: 120
     run: python inventag_cli.py --create-excel
   ```

2. **AWS CodeBuild:**
   ```yaml
   # Use larger compute type
   environment:
     compute-type: BUILD_GENERAL1_LARGE
   ```

3. **Jenkins:**
   ```groovy
   // Increase timeout
   timeout(time: 2, unit: 'HOURS') {
       sh 'python inventag_cli.py --create-excel'
   }
   ```

## Getting Help

### Self-Service Options

1. **Configuration Validation:**
   ```bash
   python inventag_cli.py --validate-config --debug
   ```

2. **Credential Testing:**
   ```bash
   python inventag_cli.py --validate-credentials --debug
   ```

3. **Minimal Test Run:**
   ```bash
   python inventag_cli.py \
     --create-excel \
     --account-regions us-east-1 \
     --account-services EC2 \
     --debug
   ```

### Information to Collect

When reporting issues, include:

1. **Command used:**
   ```bash
   python inventag_cli.py --create-excel --verbose
   ```

2. **Error messages:**
   - Full error output
   - Stack traces from debug logs

3. **Environment information:**
   ```bash
   python --version
   pip list | grep -E "(boto3|botocore|openpyxl|python-docx)"
   aws --version
   ```

4. **Configuration files:**
   - Sanitized accounts configuration
   - Service descriptions and tag mappings
   - Any custom templates

5. **System information:**
   ```bash
   uname -a
   free -h
   df -h
   ```

### Debug Information Script

```bash
#!/bin/bash
# collect_debug_info.sh - Collect debug information for support

echo "=== InvenTag Debug Information ==="
echo "Date: $(date)"
echo "User: $(whoami)"
echo "Working Directory: $(pwd)"
echo

echo "=== Python Environment ==="
python --version
echo

echo "=== Installed Packages ==="
pip list | grep -E "(boto3|botocore|openpyxl|python-docx|pyyaml)"
echo

echo "=== AWS CLI ==="
aws --version
echo

echo "=== System Information ==="
uname -a
echo

echo "=== Memory Information ==="
free -h
echo

echo "=== Disk Space ==="
df -h
echo

echo "=== Network Connectivity ==="
curl -I https://ec2.us-east-1.amazonaws.com 2>&1 | head -1
echo

echo "=== AWS Credentials Test ==="
aws sts get-caller-identity 2>&1 | head -5
echo

echo "=== InvenTag Configuration Validation ==="
python inventag_cli.py --validate-config 2>&1 | head -10
echo

echo "=== Recent Log Entries ==="
if [ -f "inventag-debug.log" ]; then
    tail -20 inventag-debug.log
else
    echo "No debug log file found"
fi
```

This troubleshooting guide covers the most common issues and provides systematic approaches to diagnosing and resolving problems with InvenTag CLI.
