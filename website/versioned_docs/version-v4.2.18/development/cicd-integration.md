---
title: CI/CD Integration
description: Pipeline integration examples and automation setup
sidebar_position: 3
---

# InvenTag CI/CD Integration Guide

## Overview

InvenTag provides comprehensive CI/CD integration capabilities for automated cloud governance and BOM generation. This guide covers integration with popular CI/CD platforms including GitHub Actions, AWS CodeBuild, Jenkins, and GitLab CI.

## Key Features

- **Automated BOM Generation**: Generate compliance reports on schedule or trigger
- **Multi-Account Support**: Process multiple AWS accounts in parallel
- **S3 Integration**: Automatically upload reports to S3 buckets
- **Compliance Gates**: Fail builds based on compliance thresholds
- **Notification Integration**: Send alerts to Slack, Teams, or email
- **Artifact Management**: Store and version BOM documents
- **Metrics Export**: Export metrics to monitoring systems

## GitHub Actions Integration

### Basic Workflow

Create `.github/workflows/inventag-bom.yml`:

```yaml
name: InvenTag BOM Generation

on:
  schedule:
    # Run daily at 6 AM UTC
    - cron: '0 6 * * *'
  workflow_dispatch:
    inputs:
      accounts_config:
        description: 'Accounts configuration file'
        required: false
        default: 'config/accounts.json'
      output_formats:
        description: 'Output formats (comma-separated)'
        required: false
        default: 'excel,word'

jobs:
  generate-bom:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1
    
    - name: Generate BOM Reports
      run: |
        python inventag_cli.py \
          --accounts-file ${{ github.event.inputs.accounts_config || 'config/accounts.json' }} \
          --create-excel \
          --create-word \
          --s3-bucket ${{ secrets.BOM_REPORTS_BUCKET }} \
          --s3-key-prefix "bom-reports/${{ github.run_number }}/" \
          --verbose \
          --log-file inventag-github.log
    
    - name: Upload logs as artifact
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: inventag-logs
        path: inventag-github.log
    
    - name: Upload local reports as artifact
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: bom-reports
        path: bom_output/
```

### Advanced Workflow with Compliance Gates

```yaml
name: InvenTag Compliance Check

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  compliance-check:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
        aws-region: us-east-1
    
    - name: Validate configuration
      run: |
        python inventag_cli.py \
          --accounts-file config/accounts.json \
          --service-descriptions config/service_descriptions.yaml \
          --tag-mappings config/tag_mappings.yaml \
          --validate-config
    
    - name: Validate credentials
      run: |
        python inventag_cli.py \
          --accounts-file config/accounts.json \
          --validate-credentials
    
    - name: Generate compliance report
      run: |
        python inventag_cli.py \
          --accounts-file config/accounts.json \
          --create-excel \
          --enable-state-management \
          --enable-delta-detection \
          --generate-changelog \
          --s3-bucket ${{ secrets.COMPLIANCE_BUCKET }} \
          --s3-key-prefix "compliance-reports/pr-${{ github.event.number }}/" \
          --verbose
    
    - name: Check compliance threshold
      run: |
        # Custom script to check compliance percentage
        python scripts/check_compliance_threshold.py --threshold 85
    
    - name: Notify Slack on failure
      if: failure()
      uses: 8398a7/action-slack@v3
      with:
        status: failure
        channel: '#compliance-alerts'
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Multi-Environment Workflow

```yaml
name: Multi-Environment BOM Generation

on:
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday at 2 AM

jobs:
  generate-bom:
    strategy:
      matrix:
        environment: [dev, staging, prod]
    
    runs-on: ubuntu-latest
    environment: ${{ matrix.environment }}
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ secrets[format('AWS_ROLE_ARN_{0}', upper(matrix.environment))] }}
        aws-region: us-east-1
    
    - name: Generate BOM for ${{ matrix.environment }}
      run: |
        python inventag_cli.py \
          --accounts-file config/accounts-${{ matrix.environment }}.json \
          --create-excel \
          --create-word \
          --s3-bucket ${{ secrets[format('BOM_BUCKET_{0}', upper(matrix.environment))] }} \
          --s3-key-prefix "bom-reports/${{ matrix.environment }}/$(date +%Y-%m-%d)/" \
          --max-concurrent-accounts 6 \
          --verbose
```

## AWS CodeBuild Integration

### Basic BuildSpec

Create `buildspec.yml`:

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.9
    commands:
      - pip install -r requirements.txt
  
  pre_build:
    commands:
      - echo "Validating InvenTag configuration..."
      - python inventag_cli.py --accounts-file $ACCOUNTS_CONFIG --validate-config
      - python inventag_cli.py --accounts-file $ACCOUNTS_CONFIG --validate-credentials
  
  build:
    commands:
      - echo "Generating BOM reports..."
      - python inventag_cli.py 
          --accounts-file $ACCOUNTS_CONFIG 
          --create-excel 
          --create-word 
          --s3-bucket $BOM_REPORTS_BUCKET 
          --s3-key-prefix "bom-reports/$CODEBUILD_BUILD_NUMBER/" 
          --max-concurrent-accounts 8 
          --account-processing-timeout 3600 
          --verbose 
          --log-file inventag-codebuild.log
  
  post_build:
    commands:
      - echo "BOM generation completed"
      - aws s3 cp inventag-codebuild.log s3://$BOM_REPORTS_BUCKET/logs/

artifacts:
  files:
    - bom_output/**/*
    - inventag-codebuild.log
  name: inventag-bom-$CODEBUILD_BUILD_NUMBER

cache:
  paths:
    - '/root/.cache/pip/**/*'
```

### Advanced BuildSpec with Secrets Manager

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.9
    commands:
      - pip install -r requirements.txt
      - pip install boto3
  
  pre_build:
    commands:
      - echo "Retrieving accounts configuration from Secrets Manager..."
      - aws secretsmanager get-secret-value --secret-id inventag/accounts --query SecretString --output text > accounts.json
      - echo "Validating configuration..."
      - python inventag_cli.py --accounts-file accounts.json --validate-config
  
  build:
    commands:
      - echo "Starting multi-account BOM generation..."
      - python inventag_cli.py 
          --accounts-file accounts.json 
          --service-descriptions config/service_descriptions.yaml 
          --tag-mappings config/tag_mappings.yaml 
          --create-excel 
          --create-word 
          --s3-bucket $BOM_REPORTS_BUCKET 
          --s3-key-prefix "automated-reports/$(date +%Y/%m/%d)/" 
          --enable-state-management 
          --enable-delta-detection 
          --generate-changelog 
          --max-concurrent-accounts 10 
          --verbose
  
  post_build:
    commands:
      - echo "Cleaning up sensitive files..."
      - rm -f accounts.json
      - echo "BOM generation completed successfully"

artifacts:
  files:
    - bom_output/**/*
  name: inventag-bom-$(date +%Y%m%d-%H%M%S)
```

## Jenkins Integration

### Declarative Pipeline

Create `Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['dev', 'staging', 'prod', 'all'],
            description: 'Environment to generate BOM for'
        )
        booleanParam(
            name: 'UPLOAD_TO_S3',
            defaultValue: true,
            description: 'Upload reports to S3'
        )
        string(
            name: 'COMPLIANCE_THRESHOLD',
            defaultValue: '85',
            description: 'Minimum compliance percentage'
        )
    }
    
    environment {
        AWS_DEFAULT_REGION = 'us-east-1'
        BOM_REPORTS_BUCKET = credentials('bom-reports-bucket')
        ACCOUNTS_CONFIG = credentials('inventag-accounts-config')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install -r requirements.txt
                '''
            }
        }
        
        stage('Validate Configuration') {
            steps {
                sh '''
                    . venv/bin/activate
                    python inventag_cli.py --accounts-file $ACCOUNTS_CONFIG --validate-config
                    python inventag_cli.py --accounts-file $ACCOUNTS_CONFIG --validate-credentials
                '''
            }
        }
        
        stage('Generate BOM') {
            steps {
                script {
                    def s3Options = params.UPLOAD_TO_S3 ? 
                        "--s3-bucket ${env.BOM_REPORTS_BUCKET} --s3-key-prefix bom-reports/${env.BUILD_NUMBER}/" : ""
                    
                    sh """
                        . venv/bin/activate
                        python inventag_cli.py \\
                            --accounts-file \$ACCOUNTS_CONFIG \\
                            --create-excel \\
                            --create-word \\
                            ${s3Options} \\
                            --max-concurrent-accounts 6 \\
                            --verbose \\
                            --log-file inventag-jenkins.log
                    """
                }
            }
        }
        
        stage('Compliance Check') {
            steps {
                sh '''
                    . venv/bin/activate
                    python scripts/check_compliance.py --threshold ${COMPLIANCE_THRESHOLD}
                '''
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'bom_output/**/*,inventag-jenkins.log', allowEmptyArchive: true
            publishHTML([
                allowMissing: false,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'bom_output',
                reportFiles: '*.html',
                reportName: 'BOM Report'
            ])
        }
        
        failure {
            emailext (
                subject: "InvenTag BOM Generation Failed - Build ${env.BUILD_NUMBER}",
                body: "The InvenTag BOM generation failed. Check the build logs for details.",
                to: "${env.CHANGE_AUTHOR_EMAIL}"
            )
        }
        
        success {
            slackSend (
                channel: '#compliance',
                color: 'good',
                message: "InvenTag BOM generation completed successfully for build ${env.BUILD_NUMBER}"
            )
        }
    }
}
```

## GitLab CI Integration

Create `.gitlab-ci.yml`:

```yaml
stages:
  - validate
  - generate
  - deploy

variables:
  PYTHON_VERSION: "3.9"
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

cache:
  paths:
    - .cache/pip/
    - venv/

before_script:
  - python -m venv venv
  - source venv/bin/activate
  - pip install -r requirements.txt

validate_config:
  stage: validate
  script:
    - python inventag_cli.py --accounts-file $ACCOUNTS_CONFIG --validate-config
    - python inventag_cli.py --accounts-file $ACCOUNTS_CONFIG --validate-credentials
  only:
    - merge_requests
    - main

generate_bom:
  stage: generate
  script:
    - python inventag_cli.py 
        --accounts-file $ACCOUNTS_CONFIG 
        --create-excel 
        --create-word 
        --s3-bucket $BOM_REPORTS_BUCKET 
        --s3-key-prefix "bom-reports/$CI_PIPELINE_ID/" 
        --verbose 
        --log-file inventag-gitlab.log
  artifacts:
    paths:
      - bom_output/
      - inventag-gitlab.log
    expire_in: 30 days
  only:
    - main
    - schedules

deploy_reports:
  stage: deploy
  script:
    - aws s3 sync bom_output/ s3://$REPORTS_ARCHIVE_BUCKET/reports/$CI_PIPELINE_ID/
  dependencies:
    - generate_bom
  only:
    - main

# Scheduled job for regular BOM generation
scheduled_bom:
  extends: generate_bom
  script:
    - python inventag_cli.py 
        --accounts-file $ACCOUNTS_CONFIG 
        --create-excel 
        --create-word 
        --enable-state-management 
        --enable-delta-detection 
        --generate-changelog 
        --s3-bucket $BOM_REPORTS_BUCKET 
        --s3-key-prefix "scheduled-reports/$(date +%Y-%m-%d)/" 
        --max-concurrent-accounts 8 
        --verbose
  only:
    - schedules
```

## Docker Integration

### Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 inventag
USER inventag

# Set entrypoint
ENTRYPOINT ["python", "inventag_cli.py"]
```

### Docker Compose for CI/CD

```yaml
version: '3.8'

services:
  inventag:
    build: .
    environment:
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_DEFAULT_REGION=us-east-1
    volumes:
      - ./config:/app/config:ro
      - ./output:/app/bom_output
    command: >
      --accounts-file config/accounts.json
      --create-excel
      --create-word
      --verbose
      --log-file bom_output/inventag-docker.log
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_DEFAULT_REGION` | Default AWS region | `us-east-1` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ACCOUNTS_CONFIG` | Path to accounts config | None | `config/accounts.json` |
| `BOM_REPORTS_BUCKET` | S3 bucket for reports | None | `my-bom-reports` |
| `SERVICE_DESCRIPTIONS_CONFIG` | Service descriptions file | None | `config/services.yaml` |
| `TAG_MAPPINGS_CONFIG` | Tag mappings file | None | `config/tags.yaml` |
| `MAX_CONCURRENT_ACCOUNTS` | Max parallel accounts | `4` | `8` |
| `ACCOUNT_PROCESSING_TIMEOUT` | Timeout per account | `1800` | `3600` |
| `COMPLIANCE_THRESHOLD` | Min compliance % | `80` | `90` |

## Security Best Practices

### Credential Management

1. **Use IAM Roles**: Prefer IAM roles over access keys
2. **Least Privilege**: Grant minimal required permissions
3. **Secrets Management**: Store credentials in secure vaults
4. **Rotation**: Regularly rotate access keys
5. **Audit**: Monitor credential usage

### Example IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "sts:AssumeRole"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "config:DescribeConfigurationRecorders",
        "config:DescribeDeliveryChannels",
        "config:GetResourceConfigHistory",
        "config:ListDiscoveredResources",
        "resource-groups:GetGroupQuery",
        "resource-groups:GetResources",
        "resource-groups:ListGroups",
        "tag:GetResources",
        "tag:GetTagKeys",
        "tag:GetTagValues"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::your-bom-bucket/*"
    }
  ]
}
```

## Monitoring and Alerting

### CloudWatch Integration

```bash
# Export metrics to CloudWatch
python inventag_cli.py \
  --accounts-file accounts.json \
  --create-excel \
  --enable-cloudwatch-metrics \
  --cloudwatch-namespace "InvenTag/BOM"
```

### Prometheus Integration

```bash
# Export metrics to Prometheus
python inventag_cli.py \
  --accounts-file accounts.json \
  --create-excel \
  --enable-prometheus-metrics \
  --prometheus-pushgateway http://prometheus:9091
```

### Custom Alerting Script

```python
#!/usr/bin/env python3
"""
Custom alerting script for InvenTag CI/CD integration
"""

import json
import sys
import requests
from pathlib import Path

def check_compliance_threshold(report_path, threshold=85):
    """Check if compliance meets threshold"""
    try:
        with open(report_path) as f:
            report = json.load(f)
        
        compliance_pct = report.get('compliance_percentage', 0)
        
        if compliance_pct < threshold:
            send_alert(f"Compliance below threshold: {compliance_pct}% < {threshold}%")
            return False
        
        return True
    
    except Exception as e:
        send_alert(f"Error checking compliance: {e}")
        return False

def send_alert(message):
    """Send alert to Slack/Teams"""
    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if webhook_url:
        requests.post(webhook_url, json={'text': message})

if __name__ == '__main__':
    report_path = sys.argv[1] if len(sys.argv) > 1 else 'bom_output/compliance_summary.json'
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 85
    
    if not check_compliance_threshold(report_path, threshold):
        sys.exit(1)
```

## Troubleshooting

### Common Issues

1. **Credential Errors**
   - Validate credentials before processing
   - Check IAM permissions
   - Verify role trust relationships

2. **Timeout Issues**
   - Increase `account_processing_timeout`
   - Reduce `max_concurrent_accounts`
   - Filter regions and services

3. **S3 Upload Failures**
   - Check S3 bucket permissions
   - Verify bucket exists and is accessible
   - Check network connectivity

4. **Memory Issues**
   - Increase container/runner memory
   - Process accounts sequentially
   - Filter services to reduce data volume

### Debug Commands

```bash
# Validate configuration
python inventag_cli.py --validate-config --debug

# Test credentials
python inventag_cli.py --validate-credentials --debug

# Dry run with debug logging
python inventag_cli.py --create-excel --debug --log-file debug.log
```

## Performance Optimization

### Parallel Processing

```bash
# Optimize for large environments
python inventag_cli.py \
  --max-concurrent-accounts 10 \
  --account-processing-timeout 7200 \
  --disable-delta-detection \
  --account-services EC2,S3,RDS
```

### Resource Filtering

```bash
# Filter by regions and services
python inventag_cli.py \
  --account-regions us-east-1,us-west-2 \
  --account-services EC2,S3,RDS,Lambda \
  --account-tags '{"Environment":"production"}'
```

### Caching

```bash
# Enable state management for caching
python inventag_cli.py \
  --enable-state-management \
  --enable-delta-detection
```

This comprehensive CI/CD integration guide provides everything needed to implement automated InvenTag BOM generation across different platforms and environments.
