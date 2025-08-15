# ⚙️ InvenTag Configuration

Configuration files and examples for customizing InvenTag behavior.

## 📁 Directory Structure

```
config/
├── README.md                           # This file
├── defaults/                           # Default configuration examples
│   ├── complete_configuration_example.yaml  # Comprehensive BOM settings
│   ├── iam-policy-read-only.json          # Required IAM permissions
│   ├── compliance/                     # Tag compliance configurations
│   │   ├── tag_compliance_policy_example.yaml  # Tag rules (YAML)
│   │   └── tag_compliance_policy_example.json  # Tag rules (JSON)
│   ├── mappings/                       # BOM column mappings
│   │   └── tag_to_column_mappings_example.yaml # Tag-to-column mappings
│   └── services/                       # Service descriptions
│       └── service_descriptions_example.yaml   # AWS service descriptions
└── schemas/                           # JSON schemas for validation
    └── account-config.schema.json
```

## 🚀 Quick Start

1. **Copy default configurations:**
```bash
# Basic BOM configuration
cp config/defaults/complete_configuration_example.yaml config/my_config.yaml

# Tag compliance policy (for compliance rules)
cp config/defaults/compliance/tag_compliance_policy_example.yaml config/my_tag_policy.yaml

# Tag mappings (for BOM column mappings)
cp config/defaults/mappings/tag_to_column_mappings_example.yaml config/my_tag_mappings.yaml

# Service descriptions
cp config/defaults/services/service_descriptions_example.yaml config/my_service_descriptions.yaml

# Multi-account setup
cp examples/accounts_basic.json config/my_accounts.json
```

2. **Use with InvenTag CLI:**
```bash
# Basic BOM generation with default credentials
python -m inventag.cli.main --create-excel --create-word

# With custom tag mappings and service descriptions
python -m inventag.cli.main \
  --create-excel --create-word \
  --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml \
  --service-descriptions config/defaults/services/service_descriptions_example.yaml

# With multi-account setup
python -m inventag.cli.main --accounts-file config/my_accounts.json --create-excel

# Validate configuration files before running
python -m inventag.cli.main \
  --tag-mappings config/defaults/mappings/tag_to_column_mappings_example.yaml \
  --service-descriptions config/defaults/services/service_descriptions_example.yaml \
  --validate-config-only
```

## 📋 Configuration Files

### 🔧 **Configuration Types**

**🏢 BOM Generation:**
- **`mappings/tag_to_column_mappings_example.yaml`** - Maps AWS tags to BOM column names
- **`services/service_descriptions_example.yaml`** - Custom AWS service descriptions
- **`complete_configuration_example.yaml`** - Comprehensive BOM generation settings

**🛡️ Compliance Checking:**
- **`compliance/tag_compliance_policy_example.yaml`** - Tag compliance rules (YAML)
- **`compliance/tag_compliance_policy_example.json`** - Tag compliance rules (JSON)

**🔐 Security:**
- **`iam-policy-read-only.json`** - Minimum required IAM permissions

### 🔍 **Validation Schemas** (`schemas/`)

- **`account-config.schema.json`** - JSON schema for multi-account configuration validation

## 🛡️ Security Configuration

### IAM Permissions
InvenTag requires minimal read-only access. Use the provided IAM policy:

```bash
# Review the policy
cat config/defaults/iam-policy-read-only.json

# Apply to your IAM user/role
aws iam put-user-policy --user-name inventag-user \
  --policy-name InvenTagReadOnly \
  --policy-document file://config/defaults/iam-policy-read-only.json
```

### Multi-Account Authentication
Supports multiple authentication methods:

- **AWS CLI Profiles** - Recommended for local development
- **Cross-Account Roles** - Recommended for production/CI-CD
- **Access Keys** - For specific use cases (not recommended)

## 📖 Configuration Examples

See the [examples/](../examples/) directory for complete working configurations:

- **Basic Setup**: `examples/accounts_basic.json`
- **AWS Profiles**: `examples/accounts_with_profiles.json`
- **Cross-Account Roles**: `examples/accounts_cross_account_roles.json`
- **CI/CD Environment**: `examples/accounts_cicd_environment.json`

## 🔗 Documentation Links

- **[Configuration Examples Guide](../docs/user-guides/CONFIGURATION_EXAMPLES.md)** - Detailed setup instructions
- **[CLI User Guide](../docs/user-guides/CLI_USER_GUIDE.md)** - Command-line usage
- **[Production Safety Guide](../docs/user-guides/PRODUCTION_SAFETY.md)** - Security best practices