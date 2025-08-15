---
title: Installation
description: How to install and set up InvenTag
sidebar_position: 2
---

# Installation Guide

## Prerequisites

- **Python 3.8+** - InvenTag requires Python 3.8 or higher
- **AWS CLI** - Configured with appropriate permissions
- **Git** - For cloning the repository

## Installation Methods

### Method 1: Clone from GitHub (Recommended)

```bash
# Clone the repository
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws

# Install Python dependencies
pip install -r requirements.txt

# Verify installation
python inventag_cli.py --help
```

### Method 2: Direct Download

1. Download the latest release from [GitHub Releases](https://github.com/habhabhabs/inventag-aws/releases)
2. Extract the archive
3. Navigate to the extracted directory
4. Install dependencies: `pip install -r requirements.txt`

## AWS Configuration

### Configure AWS CLI

InvenTag uses AWS CLI credentials. Configure them using:

```bash
aws configure
```

Or set environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### Required AWS Permissions

InvenTag supports two permission levels depending on your security requirements:

#### Option 1: Minimal IAM Policy (Basic Discovery)

For basic resource discovery with minimal permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "resourcegroupstaggingapi:GetResources",
                "ce:GetCostAndUsage",
                "ce:GetUsageReport",
                "pricing:GetProducts",
                "ec2:DescribeInstances",
                "ec2:DescribeVpcs",
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation",
                "rds:DescribeDBInstances",
                "lambda:ListFunctions"
            ],
            "Resource": "*"
        }
    ]
}
```

#### Option 2: Enhanced Discovery with ReadOnlyAccess Policy

For comprehensive resource discovery with detailed service-specific attributes, **add** the AWS ReadOnlyAccess policy **in addition to** the minimal policy above:

**For IAM Identity Center/SSO Users:**
- Keep the minimal policy above
- **Add** the AWS managed policy: `ReadOnlyAccess`

**For IAM Users:**
```bash
# First ensure the minimal policy is attached, then add ReadOnlyAccess
aws iam attach-user-policy \
    --user-name your-username \
    --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
```

**For IAM Roles:**
```bash
# First ensure the minimal policy is attached, then add ReadOnlyAccess
aws iam attach-role-policy \
    --role-name your-role-name \
    --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
```

> **Note**: ReadOnlyAccess **extends** the minimal policy's capabilities. Both policies work together to provide comprehensive discovery while maintaining the core billing and pricing access from the minimal policy.

#### Permission Level Comparison

| Feature | Minimal Policy Only | Minimal + ReadOnlyAccess |
|---------|---------------------|-------------------------|
| Basic resource discovery | ✅ | ✅ |
| Billing-based service identification | ✅ | ✅ |
| Cost Explorer access | ✅ | ✅ |
| Service-specific attributes | Limited | ✅ Full |
| KMS key details & rotation | ❌ | ✅ |
| S3 encryption/retention config | ❌ | ✅ |
| RDS parameter groups | ❌ | ✅ |
| Lambda VPC configurations | ❌ | ✅ |
| CloudWatch detailed metrics | ❌ | ✅ |
| ELB health check details | ❌ | ✅ |
| Global service support | ✅ | ✅ Enhanced |

#### Setting Up IAM Identity Center/SSO

If using AWS IAM Identity Center:

1. **Create Permission Set:**
   ```bash
   # Option 1: Use ReadOnlyAccess managed policy
   aws sso-admin create-permission-set \
       --instance-arn arn:aws:sso:::instance/ssoins-xxxxxxxxx \
       --name InvenTagReadOnly \
       --description "ReadOnly access for InvenTag"
   
   # Attach ReadOnlyAccess policy
   aws sso-admin attach-managed-policy-to-permission-set \
       --instance-arn arn:aws:sso:::instance/ssoins-xxxxxxxxx \
       --permission-set-arn arn:aws:sso:::permissionSet/ssoins-xxxxxxxxx/ps-xxxxxxxxx \
       --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
   ```

2. **Create Custom Permission Set (Minimal):**
   ```bash
   # Option 2: Use minimal custom policy
   aws sso-admin create-permission-set \
       --instance-arn arn:aws:sso:::instance/ssoins-xxxxxxxxx \
       --name InvenTagMinimal \
       --description "Minimal access for InvenTag"
   
   # Create and attach inline policy (use JSON from Option 1 above)
   ```

3. **Assign Permission Set:**
   ```bash
   aws sso-admin create-account-assignment \
       --instance-arn arn:aws:sso:::instance/ssoins-xxxxxxxxx \
       --target-id 123456789012 \
       --target-type AWS_ACCOUNT \
       --permission-set-arn arn:aws:sso:::permissionSet/ssoins-xxxxxxxxx/ps-xxxxxxxxx \
       --principal-type USER \
       --principal-id user-id-from-sso
   ```

## Verification

Test your installation:

```bash
# Test basic functionality
./inventag.sh --help

# Test AWS connectivity
./inventag.sh --validate-credentials

# Generate a test report
./inventag.sh --create-excel --verbose
```

## Optional Dependencies

### Google Docs Integration

For Google Docs output, install additional dependencies:

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Development Dependencies

For development and testing:

```bash
pip install -r requirements-dev.txt
```

## Troubleshooting

### Common Issues

**Python Version Error**
```bash
# Check Python version
python --version
# Should be 3.8 or higher
```

**AWS Credentials Error**
```bash
# Test AWS CLI
aws sts get-caller-identity
```

**Permission Denied**
```bash
# Make scripts executable (Unix/Linux/macOS)
chmod +x inventag.sh
```

**Module Import Errors**
```bash
# Ensure you're in the correct directory
cd inventag-aws
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## Next Steps

- Follow the [Quick Start Guide](/getting-started/quick-start) to generate your first BOM
- Read the [CLI User Guide](../user-guides/cli-user-guide) for comprehensive usage
- Check [Configuration Examples](../user-guides/configuration-examples) for advanced setups
