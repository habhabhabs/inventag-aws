# Configuration Files

This directory contains configuration files and policies for the AWS Cloud BOM Automation tools.

## Files

### `iam-policy-read-only.json`
**Complete IAM policy** with minimal read-only permissions required by all tools.

**Usage:**
```bash
aws iam create-policy --policy-name AWSResourceInventoryReadOnly --policy-document file://config/iam-policy-read-only.json
aws iam attach-user-policy --user-name YOUR_USER --policy-arn arn:aws:iam::ACCOUNT:policy/AWSResourceInventoryReadOnly
```

**Important:** Replace `YOUR-REPORTS-BUCKET-NAME` with your actual S3 bucket name if using S3 upload features.

### `tag_policy_example.yaml`
**Example tag policy** in YAML format showing all supported features.

**Usage:**
```bash
# Copy and customize for your organization
cp config/tag_policy_example.yaml my_tag_policy.yaml
# Edit my_tag_policy.yaml with your requirements
python scripts/tag_compliance_checker.py --config my_tag_policy.yaml
```

### `tag_policy_example.json`
**Same tag policy** in JSON format for organizations preferring JSON.

### `service_descriptions_example.yaml`
**Example service description configuration** showing how to customize resource descriptions and templates.

**Usage:**
```bash
# Copy and customize for your organization
cp config/service_descriptions_example.yaml my_service_descriptions.yaml
# Edit my_service_descriptions.yaml with your custom descriptions
python scripts/aws_resource_inventory.py --service-descriptions my_service_descriptions.yaml
```

**Features:**
- **Custom service descriptions**: Override default descriptions for AWS services
- **Template system**: Dynamic description generation using resource attributes
- **Fallback mechanisms**: Intelligent fallbacks when templates fail
- **Service hierarchies**: Service-level and resource-type-level descriptions
- **Metadata tracking**: Track configuration sources and update timestamps

## Tag Policy Features

Your tag policy can include:

- **Simple required tags**: Keys that must exist with any value
- **Allowed values**: Keys that must have specific values
- **Required values**: Keys that must have one of the required values  
- **Service-specific rules**: Different requirements per AWS service
- **Exemptions**: Resources that don't need to follow the policy

## Customization Tips

1. **Start simple**: Begin with just a few required tags like "Environment", "Owner", "Project"
2. **Add gradually**: Introduce more complex rules over time
3. **Use exemptions**: Skip tagging for AWS-managed resources
4. **Test first**: Run with `--verbose` to see what would be flagged
5. **Iterate**: Refine your policy based on compliance reports