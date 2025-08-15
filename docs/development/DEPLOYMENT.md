---
title: Deployment Guide
description: Production deployment instructions for InvenTag
sidebar_position: 2
---

# 🚀 Deployment Guide: GitLab CI/CD & GitHub Actions

This guide shows how to deploy InvenTag in your own repository using GitLab CI/CD or GitHub Actions for automated AWS™ compliance monitoring.

> **Disclaimer**: AWS™ is a trademark of Amazon Web Services, Inc. InvenTag is an independent tool and is not affiliated with, endorsed by, or sponsored by Amazon Web Services, Inc.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [GitHub Actions Deployment](#github-actions-deployment)
- [GitLab CI/CD Deployment](#gitlab-cicd-deployment)
- [Configuration Options](#configuration-options)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

## 🔧 Prerequisites

### AWS Setup
1. **AWS Account** with resources to scan
2. **IAM User/Role** with read-only permissions
3. **AWS Credentials** (Access Key + Secret or IAM Role)

### Repository Setup
1. **Copy InvenTag files** to your repository:
   ```bash
   # Copy essential files
   mkdir aws-compliance
   cp -r scripts/ aws-compliance/
   cp -r config/ aws-compliance/
   cp requirements.txt aws-compliance/
   cp version.json aws-compliance/
   ```

2. **Create your tag policy** (optional):
   ```bash
   cp aws-compliance/config/tag_policy_example.yaml aws-compliance/config/my_tag_policy.yaml
   # Edit my_tag_policy.yaml with your requirements
   ```

---

## 🐙 GitHub Actions Deployment

### 1. Basic Compliance Check Workflow

Create `.github/workflows/aws-compliance.yml`:

```yaml
name: AWS Compliance Check

on:
  # Run on pull requests
  pull_request:
    branches: [ main, develop ]
  
  # Run on push to main
  push:
    branches: [ main ]
  
  # Run daily at 8 AM UTC
  schedule:
    - cron: '0 8 * * *'
  
  # Manual trigger
  workflow_dispatch:
    inputs:
      scan_regions:
        description: 'AWS regions to scan (comma-separated)'
        required: false
        default: 'us-east-1,eu-west-1'

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  compliance-check:
    name: AWS Tag Compliance Check
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        cd aws-compliance
        pip install -r requirements.txt

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1

    - name: Run AWS resource inventory
      run: |
        cd aws-compliance
        python scripts/aws_resource_inventory.py \
          --output ../aws_inventory \
          --format json \
          $(if [ -n "${{ github.event.inputs.scan_regions }}" ]; then echo "--regions ${{ github.event.inputs.scan_regions }}"; fi)

    - name: Check tag compliance
      run: |
        cd aws-compliance
        python scripts/tag_compliance_checker.py \
          --config config/my_tag_policy.yaml \
          --output ../compliance_report \
          --format json \
          $(if [ -n "${{ github.event.inputs.scan_regions }}" ]; then echo "--regions ${{ github.event.inputs.scan_regions }}"; fi)

    - name: Generate Excel report
      run: |
        cd aws-compliance
        python scripts/bom_converter.py \
          --input ../aws_inventory_*.json \
          --output ../aws_compliance_report.xlsx

    - name: Upload compliance reports
      uses: actions/upload-artifact@v4
      with:
        name: compliance-reports-${{ github.run_number }}
        path: |
          aws_inventory_*.json
          compliance_report_*.json
          aws_compliance_report.xlsx
        retention-days: 30

    - name: Check compliance status
      run: |
        cd aws-compliance
        # Extract compliance percentage
        COMPLIANCE_PCT=$(python -c "
        import json
        import sys
        try:
            with open('../compliance_report_$(date +%Y%m%d_*)*.json', 'r') as f:
                data = json.load(f)
            pct = data['summary']['compliance_percentage']
            print(f'{pct:.1f}')
        except:
            print('0')
        ")
        
        echo "Compliance Rate: ${COMPLIANCE_PCT}%"
        
        # Fail if compliance is below threshold
        if (( $(echo "$COMPLIANCE_PCT < 80" | bc -l) )); then
          echo "❌ Compliance rate ${COMPLIANCE_PCT}% is below 80% threshold"
          exit 1
        else
          echo "✅ Compliance rate ${COMPLIANCE_PCT}% meets requirements"
        fi

    - name: Comment on PR (if applicable)
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v7
      with:
        script: |
          const fs = require('fs');
          const path = require('path');
          
          // Find compliance report file
          const files = fs.readdirSync('.');
          const reportFile = files.find(f => f.startsWith('compliance_report_') && f.endsWith('.json'));
          
          if (reportFile) {
            const report = JSON.parse(fs.readFileSync(reportFile, 'utf8'));
            const summary = report.summary;
            
            const comment = `## 🏷️ AWS Compliance Report
            
**Compliance Rate:** ${summary.compliance_percentage.toFixed(1)}%
**Total Resources:** ${summary.total_resources}
**Compliant:** ${summary.compliant_count} ✅
**Non-Compliant:** ${summary.non_compliant_count} ❌
**Untagged:** ${summary.untagged_count} 🏷️

${summary.compliance_percentage >= 80 ? '✅ Compliance requirements met' : '❌ Compliance below 80% threshold'}

<details>
<summary>View detailed compliance breakdown</summary>

${Object.entries(summary.service_breakdown || {}).map(([service, stats]) => 
  `**${service}:** ${stats.compliant}/${stats.total} compliant (${(stats.compliant/stats.total*100).toFixed(1)}%)`
).join('\n')}

</details>`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
          }
```

### 2. Advanced Workflow with S3 Upload

Create `.github/workflows/aws-compliance-advanced.yml`:

```yaml
name: AWS Compliance - Advanced

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Mondays at 6 AM UTC
  workflow_dispatch:
    inputs:
      upload_to_s3:
        description: 'Upload results to S3'
        type: boolean
        default: true
      compliance_threshold:
        description: 'Minimum compliance percentage'
        required: false
        default: '80'

env:
  S3_BUCKET: ${{ secrets.COMPLIANCE_S3_BUCKET }}
  COMPLIANCE_THRESHOLD: ${{ github.event.inputs.compliance_threshold || '80' }}

jobs:
  comprehensive-compliance:
    name: Comprehensive AWS Compliance Scan
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        environment: [production, staging]
        include:
          - environment: production
            aws_role: ${{ secrets.PROD_AWS_ROLE_ARN }}
            tag_policy: config/production_tags.yaml
          - environment: staging
            aws_role: ${{ secrets.STAGING_AWS_ROLE_ARN }}
            tag_policy: config/staging_tags.yaml

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        cd aws-compliance
        pip install -r requirements.txt

    - name: Assume AWS Role
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ matrix.aws_role }}
        role-session-name: compliance-scan-${{ matrix.environment }}
        aws-region: us-east-1

    - name: Comprehensive resource discovery
      run: |
        cd aws-compliance
        python scripts/tag_compliance_checker.py \
          --config ${{ matrix.tag_policy }} \
          --output ../compliance_${{ matrix.environment }} \
          --format json \
          --verbose

    - name: Generate Excel reports
      run: |
        cd aws-compliance
        python scripts/bom_converter.py \
          --input ../compliance_${{ matrix.environment }}_*.json \
          --output ../compliance_${{ matrix.environment }}.xlsx

    - name: Upload to S3 (if enabled)
      if: github.event.inputs.upload_to_s3 == 'true' && env.S3_BUCKET != ''
      run: |
        DATE=$(date +%Y/%m/%d)
        aws s3 cp compliance_${{ matrix.environment }}_*.json \
          s3://$S3_BUCKET/compliance-reports/$DATE/${{ matrix.environment }}/
        aws s3 cp compliance_${{ matrix.environment }}.xlsx \
          s3://$S3_BUCKET/compliance-reports/$DATE/${{ matrix.environment }}/

    - name: Create compliance summary
      run: |
        cd aws-compliance
        python -c "
        import json
        import glob
        
        files = glob.glob('../compliance_${{ matrix.environment }}_*.json')
        if files:
            with open(files[0], 'r') as f:
                data = json.load(f)
            
            summary = data['summary']
            with open('../compliance_summary_${{ matrix.environment }}.txt', 'w') as f:
                f.write(f'Environment: ${{ matrix.environment }}\n')
                f.write(f'Compliance Rate: {summary[\"compliance_percentage\"]:.1f}%\n')
                f.write(f'Total Resources: {summary[\"total_resources\"]}\n')
                f.write(f'Compliant: {summary[\"compliant_count\"]}\n')
                f.write(f'Non-Compliant: {summary[\"non_compliant_count\"]}\n')
                f.write(f'Untagged: {summary[\"untagged_count\"]}\n')
        "

    - name: Upload artifacts
      uses: actions/upload-artifact@v4
      with:
        name: compliance-${{ matrix.environment }}-${{ github.run_number }}
        path: |
          compliance_${{ matrix.environment }}_*.json
          compliance_${{ matrix.environment }}.xlsx
          compliance_summary_${{ matrix.environment }}.txt

  notify-teams:
    name: Notify Teams
    runs-on: ubuntu-latest
    needs: comprehensive-compliance
    if: always()
    
    steps:
    - name: Download artifacts
      uses: actions/download-artifact@v4
      with:
        pattern: compliance-*-${{ github.run_number }}
        merge-multiple: true

    - name: Send Teams notification
      if: env.TEAMS_WEBHOOK_URL != ''
      env:
        TEAMS_WEBHOOK_URL: ${{ secrets.TEAMS_WEBHOOK_URL }}
      run: |
        # Create Teams notification with compliance summary
        curl -H "Content-Type: application/json" -d '{
          "@type": "MessageCard",
          "@context": "https://schema.org/extensions",
          "summary": "AWS Compliance Report",
          "themeColor": "0078D4",
          "title": "🏷️ AWS Tag Compliance Report",
          "text": "Weekly compliance scan completed",
          "sections": [{
            "facts": [
              {"name": "Repository", "value": "${{ github.repository }}"},
              {"name": "Workflow", "value": "${{ github.workflow }}"},
              {"name": "Run Number", "value": "${{ github.run_number }}"}
            ]
          }],
          "potentialAction": [{
            "@type": "OpenUri",
            "name": "View Report",
            "targets": [{"os": "default", "uri": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"}]
          }]
        }' $TEAMS_WEBHOOK_URL
```

### 3. Secrets Configuration

In your GitHub repository, go to **Settings > Secrets and variables > Actions** and add:

```bash
# Required secrets
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Optional secrets for advanced workflow
PROD_AWS_ROLE_ARN=arn:aws:iam::123456789012:role/ComplianceRole
STAGING_AWS_ROLE_ARN=arn:aws:iam::123456789013:role/ComplianceRole
COMPLIANCE_S3_BUCKET=your-compliance-bucket
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

---

## 🦊 GitLab CI/CD Deployment

### 1. Basic Compliance Pipeline

Create `.gitlab-ci.yml`:

```yaml
stages:
  - validate
  - compliance
  - report
  - notify

variables:
  PYTHON_VERSION: "3.10"
  COMPLIANCE_THRESHOLD: "80"

# Cache pip dependencies
cache:
  paths:
    - .cache/pip

before_script:
  - python --version
  - pip install --cache-dir .cache/pip --upgrade pip
  - cd aws-compliance && pip install --cache-dir ../.cache/pip -r requirements.txt

# Validate AWS credentials
validate_aws:
  stage: validate
  image: python:$PYTHON_VERSION
  script:
    - aws sts get-caller-identity
  only:
    - merge_requests
    - main
    - schedules

# Basic compliance check
compliance_check:
  stage: compliance
  image: python:$PYTHON_VERSION
  script:
    - cd aws-compliance
    
    # Run resource inventory
    - |
      python scripts/aws_resource_inventory.py \
        --output ../aws_inventory \
        --format json \
        ${SCAN_REGIONS:+--regions $SCAN_REGIONS}
    
    # Check tag compliance
    - |
      python scripts/tag_compliance_checker.py \
        --config config/my_tag_policy.yaml \
        --output ../compliance_report \
        --format json \
        ${SCAN_REGIONS:+--regions $SCAN_REGIONS}
    
    # Generate Excel report
    - |
      python scripts/bom_converter.py \
        --input ../aws_inventory_*.json \
        --output ../aws_compliance_report.xlsx
    
    # Check compliance threshold
    - |
      cd ..
      COMPLIANCE_PCT=$(python -c "
      import json
      import glob
      files = glob.glob('compliance_report_*.json')
      if files:
          with open(files[0], 'r') as f:
              data = json.load(f)
          print(f'{data[\"summary\"][\"compliance_percentage\"]:.1f}')
      else:
          print('0')
      ")
      
      echo "Compliance Rate: ${COMPLIANCE_PCT}%"
      
      if [ $(echo "$COMPLIANCE_PCT < $COMPLIANCE_THRESHOLD" | bc -l) -eq 1 ]; then
        echo "❌ Compliance rate ${COMPLIANCE_PCT}% is below ${COMPLIANCE_THRESHOLD}% threshold"
        exit 1
      else
        echo "✅ Compliance rate ${COMPLIANCE_PCT}% meets requirements"
      fi

  artifacts:
    name: "compliance-reports-$CI_COMMIT_SHORT_SHA"
    paths:
      - aws_inventory_*.json
      - compliance_report_*.json
      - aws_compliance_report.xlsx
    expire_in: 30 days
    reports:
      junit: compliance_report.xml  # If you generate JUnit format
    
  only:
    - merge_requests
    - main
    - schedules

# Generate compliance report
generate_report:
  stage: report
  image: python:$PYTHON_VERSION
  script:
    - cd aws-compliance
    
    # Create summary report
    - |
      python -c "
      import json
      import glob
      import os
      
      files = glob.glob('../compliance_report_*.json')
      if files:
          with open(files[0], 'r') as f:
              data = json.load(f)
          
          summary = data['summary']
          
          # Create GitLab-style report
          with open('../compliance_summary.txt', 'w') as f:
              f.write(f'## 🏷️ AWS Compliance Report\\n\\n')
              f.write(f'**Pipeline:** {os.environ.get(\"CI_PIPELINE_URL\", \"N/A\")}\\n')
              f.write(f'**Commit:** {os.environ.get(\"CI_COMMIT_SHORT_SHA\", \"N/A\")}\\n')
              f.write(f'**Branch:** {os.environ.get(\"CI_COMMIT_REF_NAME\", \"N/A\")}\\n\\n')
              f.write(f'**Compliance Rate:** {summary[\"compliance_percentage\"]:.1f}%\\n')
              f.write(f'**Total Resources:** {summary[\"total_resources\"]}\\n')
              f.write(f'**Compliant:** {summary[\"compliant_count\"]} ✅\\n')
              f.write(f'**Non-Compliant:** {summary[\"non_compliant_count\"]} ❌\\n')
              f.write(f'**Untagged:** {summary[\"untagged_count\"]} 🏷️\\n\\n')
              
              if summary['compliance_percentage'] >= 80:
                  f.write('✅ Compliance requirements met\\n')
              else:
                  f.write('❌ Compliance below threshold\\n')
      "
    
    - cat ../compliance_summary.txt

  artifacts:
    name: "compliance-summary-$CI_COMMIT_SHORT_SHA"
    paths:
      - compliance_summary.txt
    expire_in: 30 days
  
  dependencies:
    - compliance_check
  
  only:
    - merge_requests
    - main
    - schedules

# Upload to S3 (production only)
upload_s3:
  stage: report
  image: python:$PYTHON_VERSION
  script:
    - |
      if [ -n "$S3_BUCKET" ]; then
        DATE=$(date +%Y/%m/%d)
        aws s3 cp compliance_report_*.json s3://$S3_BUCKET/compliance-reports/$DATE/
        aws s3 cp aws_compliance_report.xlsx s3://$S3_BUCKET/compliance-reports/$DATE/
        echo "Reports uploaded to s3://$S3_BUCKET/compliance-reports/$DATE/"
      else
        echo "S3_BUCKET not configured, skipping upload"
      fi
  
  dependencies:
    - compliance_check
  
  only:
    - main
    - schedules
  
  when: manual

# Notify teams (optional)
notify_slack:
  stage: notify
  image: alpine:latest
  before_script:
    - apk add --no-cache curl jq
  script:
    - |
      if [ -n "$SLACK_WEBHOOK_URL" ] && [ -f compliance_summary.txt ]; then
        MESSAGE=$(cat compliance_summary.txt | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
        
        curl -X POST -H 'Content-type: application/json' \
          --data "{\"text\":\"$MESSAGE\"}" \
          $SLACK_WEBHOOK_URL
      fi
  
  dependencies:
    - generate_report
  
  only:
    - main
    - schedules
  
  when: on_failure

# Scheduled compliance check
scheduled_compliance:
  extends: compliance_check
  variables:
    SCAN_REGIONS: "us-east-1,eu-west-1,ap-southeast-1"
  only:
    - schedules
```

### 2. Multi-Environment Pipeline

Create `.gitlab-ci-multi-env.yml`:

```yaml
stages:
  - validate
  - compliance_dev
  - compliance_staging
  - compliance_prod
  - report
  - deploy

variables:
  PYTHON_VERSION: "3.10"

# Template for compliance jobs
.compliance_template: &compliance_template
  image: python:$PYTHON_VERSION
  before_script:
    - pip install --upgrade pip
    - cd aws-compliance && pip install -r requirements.txt
  script:
    - cd aws-compliance
    
    # Assume role for environment
    - |
      CREDS=$(aws sts assume-role \
        --role-arn $AWS_ROLE_ARN \
        --role-session-name compliance-$ENVIRONMENT \
        --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
        --output text)
      
      export AWS_ACCESS_KEY_ID=$(echo $CREDS | cut -d' ' -f1)
      export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | cut -d' ' -f2)
      export AWS_SESSION_TOKEN=$(echo $CREDS | cut -d' ' -f3)
    
    # Run comprehensive compliance check
    - |
      python scripts/tag_compliance_checker.py \
        --config config/${ENVIRONMENT}_tags.yaml \
        --output ../compliance_${ENVIRONMENT} \
        --format json \
        --verbose
    
    # Generate Excel report
    - |
      python scripts/bom_converter.py \
        --input ../compliance_${ENVIRONMENT}_*.json \
        --output ../compliance_${ENVIRONMENT}.xlsx
  
  artifacts:
    name: "compliance-$ENVIRONMENT-$CI_COMMIT_SHORT_SHA"
    paths:
      - compliance_${ENVIRONMENT}_*.json
      - compliance_${ENVIRONMENT}.xlsx
    expire_in: 30 days

# Development environment
compliance_dev:
  <<: *compliance_template
  stage: compliance_dev
  variables:
    ENVIRONMENT: "dev"
    AWS_ROLE_ARN: $DEV_AWS_ROLE_ARN
  only:
    - merge_requests
    - develop

# Staging environment
compliance_staging:
  <<: *compliance_template
  stage: compliance_staging
  variables:
    ENVIRONMENT: "staging"
    AWS_ROLE_ARN: $STAGING_AWS_ROLE_ARN
  only:
    - main
    - schedules

# Production environment
compliance_prod:
  <<: *compliance_template
  stage: compliance_prod
  variables:
    ENVIRONMENT: "prod"
    AWS_ROLE_ARN: $PROD_AWS_ROLE_ARN
  only:
    - main
    - schedules
  when: manual

# Generate comprehensive report
generate_comprehensive_report:
  stage: report
  image: python:$PYTHON_VERSION
  script:
    - |
      python -c "
      import json
      import glob
      import os
      
      environments = ['dev', 'staging', 'prod']
      report = {
          'pipeline_id': os.environ.get('CI_PIPELINE_ID', 'N/A'),
          'commit': os.environ.get('CI_COMMIT_SHORT_SHA', 'N/A'),
          'branch': os.environ.get('CI_COMMIT_REF_NAME', 'N/A'),
          'environments': {}
      }
      
      for env in environments:
          files = glob.glob(f'compliance_{env}_*.json')
          if files:
              with open(files[0], 'r') as f:
                  data = json.load(f)
              report['environments'][env] = data['summary']
      
      with open('comprehensive_report.json', 'w') as f:
          json.dump(report, f, indent=2)
      
      # Create markdown summary
      with open('compliance_summary.md', 'w') as f:
          f.write('# 🏷️ Multi-Environment Compliance Report\\n\\n')
          f.write(f'**Pipeline:** {report[\"pipeline_id\"]}\\n')
          f.write(f'**Commit:** {report[\"commit\"]}\\n')
          f.write(f'**Branch:** {report[\"branch\"]}\\n\\n')
          
          for env, summary in report['environments'].items():
              f.write(f'## {env.title()} Environment\\n\\n')
              f.write(f'- **Compliance Rate:** {summary[\"compliance_percentage\"]:.1f}%\\n')
              f.write(f'- **Total Resources:** {summary[\"total_resources\"]}\\n')
              f.write(f'- **Compliant:** {summary[\"compliant_count\"]} ✅\\n')
              f.write(f'- **Non-Compliant:** {summary[\"non_compliant_count\"]} ❌\\n')
              f.write(f'- **Untagged:** {summary[\"untagged_count\"]} 🏷️\\n\\n')
      "
    
    - cat compliance_summary.md

  artifacts:
    name: "comprehensive-report-$CI_COMMIT_SHORT_SHA"
    paths:
      - comprehensive_report.json
      - compliance_summary.md
    expire_in: 30 days
  
  dependencies:
    - compliance_dev
    - compliance_staging
    - compliance_prod
```

### 3. GitLab Variables Configuration

In your GitLab project, go to **Settings > CI/CD > Variables** and add:

```bash
# Required variables
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# Optional variables for multi-environment
DEV_AWS_ROLE_ARN=arn:aws:iam::123456789012:role/ComplianceRole
STAGING_AWS_ROLE_ARN=arn:aws:iam::123456789013:role/ComplianceRole
PROD_AWS_ROLE_ARN=arn:aws:iam::123456789014:role/ComplianceRole

S3_BUCKET=your-compliance-bucket
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# For scheduled scans
SCAN_REGIONS=us-east-1,eu-west-1,ap-southeast-1
COMPLIANCE_THRESHOLD=80
```

### 4. Schedule Configuration

In GitLab, go to **CI/CD > Schedules** and create:

- **Daily Compliance Check**: `0 8 * * *`
- **Weekly Comprehensive Scan**: `0 6 * * 1`

---

## ⚙️ Configuration Options

### Tag Policy Customization

Create environment-specific tag policies:

```bash
# Production tags (strict)
aws-compliance/config/production_tags.yaml

# Staging tags (moderate)
aws-compliance/config/staging_tags.yaml

# Development tags (minimal)
aws-compliance/config/dev_tags.yaml
```

### Regional Scanning

Control which regions to scan:

```yaml
# GitHub Actions
env:
  SCAN_REGIONS: "us-east-1,eu-west-1,ap-southeast-1"

# GitLab CI/CD
variables:
  SCAN_REGIONS: "us-east-1,eu-west-1,ap-southeast-1"
```

### Compliance Thresholds

Set different thresholds per environment:

```yaml
# Strict for production
PROD_COMPLIANCE_THRESHOLD: "95"

# Moderate for staging
STAGING_COMPLIANCE_THRESHOLD: "80"

# Relaxed for development
DEV_COMPLIANCE_THRESHOLD: "60"
```

---

## 🔒 Security Best Practices

### 1. IAM Permissions

Use least-privilege IAM policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "resource-groups:GetResources",
        "config:ListDiscoveredResources",
        "config:GetResourceConfigHistory",
        "ec2:Describe*",
        "s3:ListBucket",
        "s3:GetBucketTagging",
        "rds:ListTagsForResource",
        "lambda:ListTags"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. Cross-Account Roles

For multi-account scanning, use assumable roles:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::CICD-ACCOUNT:role/ComplianceScannerRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "unique-external-id"
        }
      }
    }
  ]
}
```

### 3. Secrets Management

- **GitHub**: Use GitHub Secrets
- **GitLab**: Use GitLab CI/CD Variables (masked)
- **AWS**: Use IAM Roles for CI/CD when possible
- **Rotation**: Regularly rotate access keys

### 4. Network Security

For enhanced security:

```yaml
# Run in private runners/agents
runs-on: [self-hosted, private]

# Use VPC endpoints for AWS API calls
env:
  AWS_ENDPOINT_URL_S3: https://s3.region.amazonaws.com
```

---

## 🛠️ Troubleshooting

### Common Issues

1. **"AWS credentials not found"**
   ```bash
   # Check secrets/variables are set
   echo "Checking AWS credentials..."
   aws sts get-caller-identity
   ```

2. **"Permission denied for service X"**
   ```bash
   # Test specific service permissions
   aws ec2 describe-instances --max-items 1
   aws s3api list-buckets --max-items 1
   ```

3. **"No resources found"**
   ```bash
   # Check region configuration
   echo "Scanning regions: $SCAN_REGIONS"
   aws ec2 describe-regions
   ```

4. **"Compliance threshold not met"**
   ```bash
   # Review compliance details
   python -c "
   import json
   with open('compliance_report_*.json', 'r') as f:
       data = json.load(f)
   print('Non-compliant services:')
   for service, stats in data['summary']['service_breakdown'].items():
       if stats['non_compliant'] > 0:
           print(f'  {service}: {stats[\"non_compliant\"]} resources')
   "
   ```

### Debugging

Add debugging to your workflows:

```yaml
# GitHub Actions
- name: Debug AWS credentials
  run: |
    aws sts get-caller-identity
    aws configure list

# GitLab CI/CD
debug_aws:
  stage: validate
  script:
    - aws sts get-caller-identity
    - aws configure list
    - env | grep AWS
```

### Performance Optimization

For large AWS accounts:

```yaml
# Limit regions for faster scanning
SCAN_REGIONS: "us-east-1,eu-west-1"

# Use parallel jobs for multiple environments
strategy:
  matrix:
    region: [us-east-1, eu-west-1, ap-southeast-1]
```

---

## 📞 Support

- **Issues**: Create GitHub/GitLab issues in your repository
- **Documentation**: Refer to the [Project Repository](https://github.com/habhabhabs/inventag-aws) and [Release Guide](RELEASE)
- **Security**: See [Security Guide](SECURITY) for security guidelines

---

**Happy Compliance Monitoring! 🏷️✅**
