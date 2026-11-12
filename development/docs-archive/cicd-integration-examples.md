---
title: CI/CD Integration Examples
description: Automated deployment and integration patterns for InvenTag
sidebar_position: 2
---

# CI/CD Integration Examples

This guide provides examples for integrating InvenTag into your CI/CD pipelines for automated AWS governance and compliance reporting.

## GitHub Actions Examples

### Basic BOM Generation

```yaml
name: Generate AWS BOM
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC
  workflow_dispatch:

jobs:
  generate-bom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
          
      - name: Install dependencies
        run: pip install -r requirements.txt
        
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
          
      - name: Generate BOM
        run: |
          ./inventag.sh \
            --accounts-file accounts.json \
            --create-excel --create-word \
            --s3-bucket ${{ secrets.REPORTS_BUCKET }} \
            --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
            --verbose
```

### Enterprise Security Validation

```yaml
name: Enterprise BOM with Security Validation
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:

jobs:
  security-bom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
          
      - name: Install dependencies
        run: pip install -r requirements.txt
        
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1
          
      - name: Validate configuration
        run: ./inventag.sh --accounts-file accounts.json --validate-config
        
      - name: Validate credentials
        run: ./inventag.sh --accounts-file accounts.json --validate-credentials
        
      - name: Generate secure BOM
        run: |
          ./inventag.sh \
            --accounts-file accounts.json \
            --create-excel --create-word \
            --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
            --compliance-standard soc2 \
            --enable-production-safety --security-validation \
            --s3-bucket ${{ secrets.REPORTS_BUCKET }} \
            --s3-key-prefix secure-reports/$(date +%Y-%m-%d)/ \
            --audit-output security-audit.json \
            --max-concurrent-accounts 8
            
      - name: Upload audit logs
        uses: actions/upload-artifact@v3
        with:
          name: security-audit
          path: security-audit.json
```

## AWS CodeBuild Examples

### Basic buildspec.yml

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
      - echo "Validating configuration..."
      - ./inventag.sh --accounts-file accounts.json --validate-config
      - ./inventag.sh --accounts-file accounts.json --validate-credentials
      
  build:
    commands:
      - echo "Generating BOM reports..."
      - |
        ./inventag.sh \
          --accounts-file accounts.json \
          --create-excel --create-word \
          --s3-bucket $REPORTS_BUCKET \
          --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
          --verbose
          
  post_build:
    commands:
      - echo "BOM generation completed"
      
artifacts:
  files:
    - 'bom_output/**/*'
```

### Advanced buildspec with Security

```yaml
version: 0.2

env:
  variables:
    PYTHONPATH: "/codebuild/output/src"
  parameter-store:
    REPORTS_BUCKET: "/inventag/reports-bucket"
    COMPLIANCE_STANDARD: "/inventag/compliance-standard"

phases:
  install:
    runtime-versions:
      python: 3.9
    commands:
      - pip install -r requirements.txt
      
  pre_build:
    commands:
      - echo "Starting security validation..."
      - ./inventag.sh --accounts-file accounts.json --validate-config
      - ./inventag.sh --accounts-file accounts.json --validate-credentials
      
  build:
    commands:
      - echo "Generating comprehensive BOM with security analysis..."
      - |
        ./inventag.sh \
          --accounts-file accounts.json \
          --service-descriptions service-descriptions.yaml \
          --tag-mappings tag-mappings.yaml \
          --create-excel --create-word \
          --enable-network-analysis --enable-security-analysis --enable-cost-analysis \
          --compliance-standard $COMPLIANCE_STANDARD \
          --enable-production-safety --security-validation \
          --s3-bucket $REPORTS_BUCKET \
          --s3-key-prefix secure-reports/$(date +%Y-%m-%d)/ \
          --audit-output security-audit.json \
          --max-concurrent-accounts 8 \
          --verbose
          
  post_build:
    commands:
      - echo "Uploading audit logs..."
      - aws s3 cp security-audit.json s3://$REPORTS_BUCKET/audit-logs/$(date +%Y-%m-%d)/
      
artifacts:
  files:
    - 'bom_output/**/*'
    - 'security-audit.json'
```

## GitLab CI Examples

### Basic .gitlab-ci.yml

```yaml
stages:
  - validate
  - generate
  - upload

variables:
  PYTHON_VERSION: "3.9"

before_script:
  - pip install -r requirements.txt

validate_config:
  stage: validate
  script:
    - ./inventag.sh --accounts-file accounts.json --validate-config
    - ./inventag.sh --accounts-file accounts.json --validate-credentials

generate_bom:
  stage: generate
  script:
    - |
      ./inventag.sh \
        --accounts-file accounts.json \
        --create-excel --create-word \
        --verbose
  artifacts:
    paths:
      - bom_output/
    expire_in: 7 days

upload_reports:
  stage: upload
  script:
    - |
      ./inventag.sh \
        --accounts-file accounts.json \
        --create-excel --create-word \
        --s3-bucket $REPORTS_BUCKET \
        --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
        --verbose
  only:
    - main
```

## Jenkins Pipeline Examples

### Declarative Pipeline

```groovy
pipeline {
    agent any
    
    environment {
        REPORTS_BUCKET = credentials('reports-bucket')
        AWS_DEFAULT_REGION = 'us-east-1'
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        
        stage('Validate') {
            steps {
                sh './inventag.sh --accounts-file accounts.json --validate-config'
                sh './inventag.sh --accounts-file accounts.json --validate-credentials'
            }
        }
        
        stage('Generate BOM') {
            steps {
                sh '''
                    ./inventag.sh \
                        --accounts-file accounts.json \
                        --create-excel --create-word \
                        --enable-network-analysis --enable-security-analysis \
                        --s3-bucket $REPORTS_BUCKET \
                        --s3-key-prefix bom-reports/$(date +%Y-%m-%d)/ \
                        --verbose
                '''
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'bom_output/**/*', fingerprint: true
        }
        failure {
            emailext (
                subject: "InvenTag BOM Generation Failed",
                body: "The BOM generation pipeline failed. Please check the logs.",
                to: "${env.CHANGE_AUTHOR_EMAIL}"
            )
        }
    }
}
```

## Docker Integration

### Dockerfile for CI/CD

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws/

# Copy application files
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Make scripts executable
RUN chmod +x inventag.sh

# Default command
CMD ["./inventag.sh", "--help"]
```

### Docker Compose for Development

```yaml
version: '3.8'

services:
  inventag:
    build: .
    environment:
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
    volumes:
      - ./accounts.json:/app/accounts.json:ro
      - ./bom_output:/app/bom_output
    command: >
      ./inventag.sh
      --accounts-file accounts.json
      --create-excel
      --verbose
```

## Monitoring and Alerting

### CloudWatch Integration

```bash
#!/bin/bash
# Script with CloudWatch metrics

# Generate BOM with error handling
if ./inventag.sh --accounts-file accounts.json --create-excel --verbose; then
    # Success metric
    aws cloudwatch put-metric-data \
        --namespace "InvenTag/BOM" \
        --metric-data MetricName=GenerationSuccess,Value=1,Unit=Count
else
    # Failure metric
    aws cloudwatch put-metric-data \
        --namespace "InvenTag/BOM" \
        --metric-data MetricName=GenerationFailure,Value=1,Unit=Count
    
    # Send SNS notification
    aws sns publish \
        --topic-arn $SNS_TOPIC_ARN \
        --message "InvenTag BOM generation failed"
fi
```

### Slack Notifications

```bash
#!/bin/bash
# Script with Slack notifications

SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

send_slack_notification() {
    local message=$1
    local color=$2
    
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"attachments\":[{\"color\":\"$color\",\"text\":\"$message\"}]}" \
        $SLACK_WEBHOOK_URL
}

# Generate BOM
if ./inventag.sh --accounts-file accounts.json --create-excel --verbose; then
    send_slack_notification "✅ InvenTag BOM generation completed successfully" "good"
else
    send_slack_notification "❌ InvenTag BOM generation failed" "danger"
fi
```

## Best Practices

### Security Considerations

1. **Use IAM Roles**: Prefer IAM roles over access keys in CI/CD
2. **Least Privilege**: Grant minimal required permissions
3. **Secrets Management**: Store sensitive data in secure secret stores
4. **Audit Logging**: Enable comprehensive audit logging
5. **Network Security**: Use private subnets and VPC endpoints when possible

### Performance Optimization

1. **Parallel Processing**: Use `--max-concurrent-accounts` for faster execution
2. **Region Filtering**: Limit regions to reduce scan time
3. **Caching**: Cache dependencies in CI/CD pipelines
4. **Resource Limits**: Set appropriate timeout and resource limits

### Reliability

1. **Validation Steps**: Always validate configuration and credentials
2. **Error Handling**: Implement proper error handling and notifications
3. **Retry Logic**: Add retry mechanisms for transient failures
4. **Monitoring**: Set up comprehensive monitoring and alerting

## See Also

- [CLI User Guide](../user-guides/cli-user-guide) - Complete CLI reference
- [Production Safety Guide](../user-guides/production-safety) - Security and compliance
- [Deployment Guide](../development/DEPLOYMENT) - Production deployment instructions
