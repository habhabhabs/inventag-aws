# InvenTag Credential Security Guide

This guide provides comprehensive security best practices for managing AWS credentials across different environments when using InvenTag for multi-account BOM generation.

## 🔐 Security Principles

### Core Security Principles
1. **Never store credentials in code or configuration files committed to version control**
2. **Use environment-appropriate credential management systems**
3. **Apply principle of least privilege for all AWS access**
4. **Rotate credentials regularly**
5. **Audit credential access and usage**
6. **Use temporary credentials when possible**
7. **Enable security validation** for all AWS operations
8. **Monitor and log all credential usage** with comprehensive audit trails

### InvenTag Security Validation

InvenTag includes comprehensive security validation that automatically enforces secure credential usage:

```python
from inventag.compliance import ReadOnlyAccessValidator, ComplianceStandard

# Initialize security validator
validator = ReadOnlyAccessValidator(ComplianceStandard.GENERAL)

# All AWS operations are automatically validated
result = validator.validate_operation("ec2", "describe_instances")
if not result.is_valid:
    print(f"Operation blocked: {result.validation_message}")
    # Operation is prevented from executing

# Generate compliance report for credential usage
compliance_report = validator.generate_gcc20_compliance_report()
print(f"Credential usage compliance: {compliance_report.compliance_score}%")
```

## 🏗️ Environment-Specific Credential Management

### 1. Local Development Environment

**✅ Recommended Approaches:**

#### Option A: AWS CLI Profiles (Most Secure for Local)
```bash
# Configure profiles for each account
aws configure --profile production-account
aws configure --profile staging-account
aws configure --profile development-account
```

**Configuration file:** `examples/accounts_with_profiles.json`
```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production Account",
      "profile_name": "production-account",
      "regions": ["us-east-1", "us-west-2"]
    }
  ]
}
```

#### Option B: Environment Variables (For Testing)
```bash
# Set global credentials
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_SESSION_TOKEN="optional-session-token"

# Use with any account configuration
python scripts/cicd_bom_generation.py --accounts-file examples/accounts_cicd_environment.json
```

#### Option C: Direct Credentials in File (⚠️ Use with Caution)
**Configuration file:** `examples/accounts_local_with_credentials.json`
```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production Account",
      "access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
      "session_token": "optional-session-token"
    }
  ]
}
```

**⚠️ Security Requirements for Direct Credentials:**
```bash
# Set restrictive file permissions
chmod 600 examples/accounts_local_with_credentials.json

# Add to .gitignore
echo "examples/accounts_local_with_credentials.json" >> .gitignore

# Never commit this file to version control
git add .gitignore
git commit -m "Add credential file to gitignore"
```

### 2. GitHub Actions Environment

**✅ Recommended Approach: GitHub Secrets**

#### Setup GitHub Secrets
1. Go to repository **Settings** → **Secrets and variables** → **Actions**
2. Add secrets for each account using one of these naming patterns:

**Option 1: By Account ID (Recommended)**
- `AWS_ACCESS_KEY_ID_123456789012`
- `AWS_SECRET_ACCESS_KEY_123456789012`
- `AWS_SESSION_TOKEN_123456789012` (optional)

**Option 2: By Account Name**
- `AWS_ACCESS_KEY_ID_PRODUCTION_ACCOUNT`
- `AWS_SECRET_ACCESS_KEY_PRODUCTION_ACCOUNT`
- `AWS_SESSION_TOKEN_PRODUCTION_ACCOUNT` (optional)

**Option 3: Reverse Pattern**
- `PRODUCTION_ACCOUNT_AWS_ACCESS_KEY_ID`
- `PRODUCTION_ACCOUNT_AWS_SECRET_ACCESS_KEY`

**Option 4: Short Account ID**
- `AWS_ACCESS_KEY_ID_9012` (last 4 digits)
- `AWS_SECRET_ACCESS_KEY_9012`

The system will automatically try multiple patterns to find your credentials.

#### GitHub Actions Workflow
**File:** `examples/github_actions_with_secrets.yml`

```yaml
jobs:
  production-bom:
    runs-on: ubuntu-latest
    environment: production  # Use GitHub Environments for additional protection
    steps:
    - name: Generate Production BOM
      env:
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID_PROD }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY_PROD }}
        AWS_SESSION_TOKEN: ${{ secrets.AWS_SESSION_TOKEN_PROD }}
      run: |
        python scripts/cicd_bom_generation.py \
          --accounts-file examples/accounts_github_secrets.json \
          --formats excel word json
```

#### Account Configuration for GitHub Actions
**File:** `examples/accounts_github_secrets.json`
```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production Account",
      "regions": ["us-east-1", "us-west-2"]
    }
  ],
  "metadata": {
    "credential_management": {
      "method": "github_secrets",
      "description": "Credentials injected via GitHub Secrets as environment variables"
    }
  }
}
```

### 3. AWS CodeBuild Environment

**✅ Recommended Approach: AWS Secrets Manager**

#### Setup AWS Secrets Manager
1. Create secrets for each account using flexible naming:

```bash
# Option 1: By Account ID (Recommended)
aws secretsmanager create-secret \
  --name "inventag/credentials/123456789012" \
  --description "InvenTag credentials for account 123456789012" \
  --secret-string '{
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "aws_session_token": "optional-session-token"
  }'

# Option 2: By Account Name
aws secretsmanager create-secret \
  --name "inventag/credentials/production-account" \
  --description "InvenTag production account credentials" \
  --secret-string '{
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }'

# Option 3: Environment Variable Override (Highest Priority)
export INVENTAG_SECRET_PRODUCTION_ACCOUNT="my-custom-secret-name"
```

**Automatic Secret Discovery Patterns:**
- `inventag/credentials/{account_id}`
- `inventag/credentials/{account_name}`
- `inventag/{account_id}/credentials`
- `inventag-{account_id}`
- Environment variable: `INVENTAG_SECRET_{ACCOUNT_NAME}`

#### CodeBuild IAM Role Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:inventag/credentials/*"
      ]
    }
  ]
}
```

#### CodeBuild Buildspec
**File:** `examples/aws_codebuild_with_secrets_manager.yml`

```yaml
env:
  secrets-manager:
    PROD_AWS_ACCESS_KEY_ID: "inventag/credentials/production:aws_access_key_id"
    PROD_AWS_SECRET_ACCESS_KEY: "inventag/credentials/production:aws_secret_access_key"
    STAGING_AWS_ACCESS_KEY_ID: "inventag/credentials/staging:aws_access_key_id"
    STAGING_AWS_SECRET_ACCESS_KEY: "inventag/credentials/staging:aws_secret_access_key"
```

### 4. Jenkins Environment

**✅ Recommended Approach: Jenkins Credentials Store**

#### Setup Jenkins Credentials
1. Go to **Manage Jenkins** → **Manage Credentials**
2. Add **AWS Credentials** for each account:
   - ID: `aws-credentials-prod`
   - Access Key ID: `AKIAIOSFODNN7EXAMPLE`
   - Secret Access Key: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`

#### Jenkins Pipeline
```groovy
pipeline {
    agent any
    
    stages {
        stage('Generate Production BOM') {
            steps {
                withCredentials([
                    aws(credentialsId: 'aws-credentials-prod', 
                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh '''
                        python scripts/cicd_bom_generation.py \
                          --accounts-file examples/accounts_cicd_environment.json \
                          --formats excel word
                    '''
                }
            }
        }
    }
}
```

## 🔒 Advanced Security Configurations

### Cross-Account Role Assumption

**Most Secure Approach for Enterprise Environments**

#### Setup Cross-Account Roles
1. **Create IAM Role in Target Account:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::MANAGEMENT-ACCOUNT-ID:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "unique-external-id-12345"
        }
      }
    }
  ]
}
```

2. **Attach ReadOnly Policy:**
```bash
aws iam attach-role-policy \
  --role-name InvenTagCrossAccountRole \
  --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
```

#### Configuration
**File:** `examples/accounts_cross_account_roles.json`
```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production Account",
      "role_arn": "arn:aws:iam::123456789012:role/InvenTagCrossAccountRole",
      "external_id": "unique-external-id-12345",
      "regions": ["us-east-1", "us-west-2"]
    }
  ]
}
```

### Temporary Credentials with STS

**For Enhanced Security**

```bash
# Generate temporary credentials
aws sts get-session-token \
  --duration-seconds 3600 \
  --output json > temp_credentials.json

# Extract credentials
export AWS_ACCESS_KEY_ID=$(cat temp_credentials.json | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(cat temp_credentials.json | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(cat temp_credentials.json | jq -r '.Credentials.SessionToken')

# Use with InvenTag
python scripts/cicd_bom_generation.py --accounts-file examples/accounts_cicd_environment.json
```

## 🛡️ Security Best Practices

### 1. IAM Permissions (Principle of Least Privilege)

**Minimum Required Permissions for InvenTag:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning",
        "s3:GetBucketEncryption",
        "s3:GetBucketPublicAccessBlock",
        "s3:ListBucket",
        "rds:Describe*",
        "lambda:List*",
        "lambda:Get*",
        "ecs:Describe*",
        "ecs:List*",
        "eks:Describe*",
        "eks:List*",
        "iam:List*",
        "iam:Get*",
        "cloudtrail:Describe*",
        "config:Describe*",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. Credential Rotation

**Automated Rotation with AWS Secrets Manager:**
```bash
# Enable automatic rotation
aws secretsmanager rotate-secret \
  --secret-id "inventag/credentials/production" \
  --rotation-lambda-arn "arn:aws:lambda:us-east-1:123456789012:function:SecretsManagerRotationFunction"
```

**Manual Rotation Schedule:**
- **Production:** Every 30 days
- **Staging:** Every 60 days  
- **Development:** Every 90 days

### 3. Audit and Monitoring

**CloudTrail Monitoring:**
```json
{
  "eventVersion": "1.05",
  "userIdentity": {
    "type": "IAMUser",
    "principalId": "AIDACKCEVSQ6C2EXAMPLE",
    "arn": "arn:aws:iam::123456789012:user/inventag-service",
    "accountId": "123456789012",
    "userName": "inventag-service"
  },
  "eventTime": "2024-01-15T10:30:00Z",
  "eventSource": "ec2.amazonaws.com",
  "eventName": "DescribeInstances"
}
```

**Set up CloudWatch Alarms:**
```bash
# Monitor for unusual API activity
aws cloudwatch put-metric-alarm \
  --alarm-name "InvenTag-Unusual-API-Activity" \
  --alarm-description "Monitor for unusual InvenTag API activity" \
  --metric-name "CallCount" \
  --namespace "AWS/CloudTrail" \
  --statistic "Sum" \
  --period 300 \
  --threshold 1000 \
  --comparison-operator "GreaterThanThreshold"
```

### 4. Network Security

**VPC Endpoints for Enhanced Security:**
```bash
# Create VPC endpoint for S3
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-12345678 \
  --service-name com.amazonaws.us-east-1.s3 \
  --vpc-endpoint-type Gateway

# Create VPC endpoint for Secrets Manager
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-12345678 \
  --service-name com.amazonaws.us-east-1.secretsmanager \
  --vpc-endpoint-type Interface
```

## 🚨 Security Incident Response

### Credential Compromise Response

**Immediate Actions:**
1. **Disable compromised credentials:**
```bash
aws iam update-access-key \
  --access-key-id AKIAIOSFODNN7EXAMPLE \
  --status Inactive \
  --user-name inventag-service
```

2. **Rotate all related credentials:**
```bash
aws secretsmanager rotate-secret \
  --secret-id "inventag/credentials/production" \
  --force-rotate-immediately
```

3. **Review CloudTrail logs:**
```bash
aws logs filter-log-events \
  --log-group-name CloudTrail/InvenTagActivity \
  --start-time 1642204800000 \
  --filter-pattern "{ $.userIdentity.userName = \"inventag-service\" }"
```

4. **Update all CI/CD systems with new credentials**

### Security Checklist

**Pre-Deployment Security Checklist:**
- [ ] Credentials stored in appropriate secret management system
- [ ] IAM permissions follow principle of least privilege
- [ ] Cross-account roles configured with external IDs
- [ ] CloudTrail logging enabled for all accounts
- [ ] Credential rotation schedule established
- [ ] Security incident response plan documented
- [ ] Network access restricted via VPC endpoints (if applicable)
- [ ] Multi-factor authentication enabled for human users
- [ ] Regular security audits scheduled

**Runtime Security Monitoring:**
- [ ] CloudWatch alarms for unusual API activity
- [ ] Regular credential rotation
- [ ] Access pattern analysis
- [ ] Compliance gate monitoring
- [ ] Failed authentication alerts

## 📋 Quick Reference

### Environment Detection
The InvenTag CLI automatically detects the execution environment and applies appropriate credential handling:

- **GitHub Actions:** Uses GitHub Secrets via environment variables
- **AWS CodeBuild:** Uses AWS Secrets Manager integration
- **Jenkins:** Uses Jenkins credential store
- **Local:** Uses AWS CLI profiles or environment variables

### Configuration Files by Environment

| Environment | Configuration File | Credential Method |
|-------------|-------------------|-------------------|
| Local Development | `accounts_with_profiles.json` | AWS CLI Profiles |
| Local Testing | `accounts_local_with_credentials.json` | Direct credentials (⚠️) |
| GitHub Actions | `accounts_github_secrets.json` | GitHub Secrets |
| AWS CodeBuild | `accounts_aws_secrets_manager.json` | AWS Secrets Manager |
| Enterprise | `accounts_cross_account_roles.json` | Cross-account roles |

### Emergency Contacts

**Security Incident Response:**
- Security Team: security@company.com
- DevOps Team: devops@company.com
- AWS Support: [AWS Support Center](https://console.aws.amazon.com/support/)

## 🔍 Security Monitoring and Validation

### Automated Security Monitoring

InvenTag provides comprehensive security monitoring for credential usage:

```python
from inventag.compliance import ProductionSafetyMonitor

# Initialize production monitor with security features
monitor = ProductionSafetyMonitor(
    enable_cloudtrail=True,
    enable_performance_monitoring=True,
    error_threshold=10
)

# Monitor credential usage and operations
try:
    # Your AWS operations
    result = aws_operation()
except Exception as e:
    # Automatic error handling with security context
    error_context = monitor.handle_error(
        error=e,
        operation="aws_operation",
        service="ec2"
    )
    print(f"Security impact: {error_context.user_impact}")
    print(f"Recovery action: {error_context.recovery_action}")

# Generate security validation report
security_report = monitor.generate_security_validation_report()
print(f"Credential security score: {security_report.risk_score}/100")
```

### Compliance Integration

```python
from inventag.compliance import ComplianceManager, ComplianceConfiguration

# Configure comprehensive compliance monitoring
config = ComplianceConfiguration(
    enable_security_validation=True,
    enable_production_monitoring=True,
    enable_cloudtrail_integration=True
)

manager = ComplianceManager(config)

# Validate and monitor all credential usage
result = manager.validate_and_monitor_operation(
    service="ec2",
    operation="describe_instances"
)

# Generate comprehensive compliance report
report = manager.generate_comprehensive_compliance_report()
print(f"Overall credential compliance: {report['executive_summary']['compliance_score']}%")
```

### Security Features

- **🛡️ Real-time Validation**: Every AWS operation is validated before execution
- **📋 Comprehensive Audit Logging**: All credential usage is logged with compliance metadata
- **🚨 Automatic Error Handling**: Graceful degradation with security context
- **📊 Performance Monitoring**: Real-time monitoring of credential usage patterns
- **🔍 CloudTrail Integration**: Enhanced audit visibility with AWS CloudTrail correlation
- **📈 Compliance Reporting**: Automated generation of security compliance reports
- **🎯 Risk Assessment**: Automatic risk scoring for credential usage patterns
- **⚡ Circuit Breakers**: Protection against credential abuse and cascade failures

**Remember: Security is everyone's responsibility. When in doubt, choose the more secure option.**