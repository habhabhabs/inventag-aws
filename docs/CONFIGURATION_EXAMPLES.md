# InvenTag Configuration Examples

## Overview

This document provides comprehensive examples of InvenTag configuration files for various use cases and environments. All configuration files support both JSON and YAML formats.

## Accounts Configuration

### Basic Single Account

#### JSON Format
```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "My AWS Account",
      "profile_name": "default",
      "regions": ["us-east-1"],
      "services": [],
      "tags": {}
    }
  ],
  "settings": {
    "max_concurrent_accounts": 1,
    "account_processing_timeout": 1800,
    "output_directory": "bom_output"
  }
}
```

#### YAML Format
```yaml
accounts:
  - account_id: "123456789012"
    account_name: "My AWS Account"
    profile_name: "default"
    regions:
      - "us-east-1"
    services: []
    tags: {}

settings:
  max_concurrent_accounts: 1
  account_processing_timeout: 1800
  output_directory: "bom_output"
```

### Multi-Account with Different Credential Types

```json
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "Production Account",
      "profile_name": "prod-profile",
      "regions": ["us-east-1", "us-west-2", "eu-west-1"],
      "services": ["EC2", "S3", "RDS", "Lambda", "VPC"],
      "tags": {
        "Environment": "production",
        "Team": "platform",
        "CostCenter": "engineering"
      }
    },
    {
      "account_id": "123456789013",
      "account_name": "Development Account",
      "access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
      "regions": ["us-east-1"],
      "services": ["EC2", "S3", "Lambda"],
      "tags": {
        "Environment": "development",
        "Team": "development"
      }
    },
    {
      "account_id": "123456789014",
      "account_name": "Security Account",
      "role_arn": "arn:aws:iam::123456789014:role/InvenTagCrossAccountRole",
      "external_id": "unique-external-id-123",
      "regions": ["us-east-1", "us-west-2"],
      "services": ["IAM", "CloudTrail", "Config", "GuardDuty"],
      "tags": {
        "Environment": "security",
        "Team": "security"
      }
    },
    {
      "account_id": "123456789015",
      "account_name": "Staging Account",
      "access_key_id": "AKIAIOSFODNN7STAGING",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYSTAGING",
      "session_token": "FwoGZXIvYXdzEBQaDH...",
      "regions": ["us-east-1", "us-west-1"],
      "services": [],
      "tags": {
        "Environment": "staging",
        "Team": "qa"
      }
    }
  ],
  "settings": {
    "max_concurrent_accounts": 4,
    "account_processing_timeout": 3600,
    "output_directory": "multi_account_bom",
    "enable_state_management": true,
    "enable_delta_detection": true,
    "generate_per_account_reports": true
  }
}
```

### Enterprise Multi-Region Configuration

```yaml
accounts:
  # US Production Accounts
  - account_id: "111111111111"
    account_name: "US-East Production"
    role_arn: "arn:aws:iam::111111111111:role/InvenTagRole"
    regions:
      - "us-east-1"
      - "us-east-2"
    services:
      - "EC2"
      - "S3"
      - "RDS"
      - "Lambda"
      - "ELB"
      - "VPC"
      - "IAM"
    tags:
      Environment: "production"
      Region: "us-east"
      BusinessUnit: "core-services"
      CostCenter: "12345"

  - account_id: "222222222222"
    account_name: "US-West Production"
    role_arn: "arn:aws:iam::222222222222:role/InvenTagRole"
    regions:
      - "us-west-1"
      - "us-west-2"
    services:
      - "EC2"
      - "S3"
      - "RDS"
      - "Lambda"
      - "ELB"
      - "VPC"
    tags:
      Environment: "production"
      Region: "us-west"
      BusinessUnit: "core-services"
      CostCenter: "12345"

  # European Accounts
  - account_id: "333333333333"
    account_name: "EU Production"
    role_arn: "arn:aws:iam::333333333333:role/InvenTagRole"
    regions:
      - "eu-west-1"
      - "eu-west-2"
      - "eu-central-1"
    services:
      - "EC2"
      - "S3"
      - "RDS"
      - "Lambda"
      - "VPC"
    tags:
      Environment: "production"
      Region: "europe"
      BusinessUnit: "european-ops"
      CostCenter: "67890"
      DataResidency: "eu"

  # Development and Testing
  - account_id: "444444444444"
    account_name: "Development Sandbox"
    profile_name: "dev-sandbox"
    regions:
      - "us-east-1"
    services: []  # All services
    tags:
      Environment: "development"
      Team: "all-teams"
      AutoShutdown: "enabled"

settings:
  max_concurrent_accounts: 6
  account_processing_timeout: 7200  # 2 hours for large accounts
  output_directory: "enterprise_bom_reports"
  enable_state_management: true
  enable_delta_detection: true
  generate_per_account_reports: true
```

### CI/CD Environment Configuration

```json
{
  "accounts": [
    {
      "account_id": "555555555555",
      "account_name": "CI/CD Production",
      "role_arn": "arn:aws:iam::555555555555:role/GitHubActionsRole",
      "regions": ["us-east-1", "us-west-2"],
      "services": ["EC2", "S3", "RDS", "Lambda", "ECS", "EKS"],
      "tags": {
        "Environment": "production",
        "ManagedBy": "github-actions",
        "Project": "main-application"
      }
    },
    {
      "account_id": "666666666666",
      "account_name": "CI/CD Staging",
      "role_arn": "arn:aws:iam::666666666666:role/GitHubActionsRole",
      "regions": ["us-east-1"],
      "services": ["EC2", "S3", "Lambda", "ECS"],
      "tags": {
        "Environment": "staging",
        "ManagedBy": "github-actions",
        "Project": "main-application"
      }
    }
  ],
  "settings": {
    "max_concurrent_accounts": 8,
    "account_processing_timeout": 1800,
    "output_directory": "cicd_bom_output",
    "enable_state_management": true,
    "enable_delta_detection": true,
    "generate_per_account_reports": false
  }
}
```

## Service Descriptions Configuration

### Basic Service Descriptions

```yaml
# Basic service descriptions for common AWS services
EC2:
  default_description: "Amazon Elastic Compute Cloud - Virtual servers in the cloud providing scalable compute capacity"
  resource_types:
    Instance: "Virtual machine instances with various compute, memory, and networking capacity"
    Volume: "Elastic Block Store (EBS) volumes providing persistent block storage"
    SecurityGroup: "Virtual firewall controlling inbound and outbound traffic"
    KeyPair: "Key pairs for secure SSH access to EC2 instances"
    NetworkInterface: "Virtual network interface attachable to instances"
    Snapshot: "Point-in-time backup of EBS volumes"

S3:
  default_description: "Amazon Simple Storage Service - Highly scalable object storage service"
  resource_types:
    Bucket: "Container for objects with global namespace and configurable access controls"

RDS:
  default_description: "Amazon Relational Database Service - Managed relational database service"
  resource_types:
    DBInstance: "Managed database instance with automated backups and maintenance"
    DBCluster: "Aurora database cluster with multiple instances for high availability"
    DBSubnetGroup: "Collection of subnets for database deployment"
    DBParameterGroup: "Configuration parameters for database engines"

Lambda:
  default_description: "AWS Lambda - Serverless compute service for running code without managing servers"
  resource_types:
    Function: "Serverless function that runs code in response to events"

VPC:
  default_description: "Amazon Virtual Private Cloud - Isolated virtual network environment"
  resource_types:
    VPC: "Virtual private cloud providing isolated network environment"
    Subnet: "Subdivision of VPC IP address range in specific availability zone"
    InternetGateway: "Gateway enabling internet access for VPC resources"
    NatGateway: "Network Address Translation gateway for outbound internet access"
    RouteTable: "Rules determining where network traffic is directed"
    NetworkAcl: "Network-level access control list for subnet traffic filtering"
```

### Comprehensive Enterprise Service Descriptions

```yaml
# Comprehensive service descriptions for enterprise environments
EC2:
  default_description: "Amazon Elastic Compute Cloud - Virtual servers providing scalable compute capacity with enterprise-grade security and compliance features"
  display_name: "EC2 (Elastic Compute Cloud)"
  category: "Compute"
  documentation_url: "https://docs.aws.amazon.com/ec2/"
  compliance_notes: "All EC2 instances must comply with company security baseline and be properly tagged"
  resource_types:
    Instance: "Virtual machine instances providing scalable compute capacity. Must follow company AMI standards and security configurations"
    Volume: "Elastic Block Store volumes providing persistent storage. Encryption required for production workloads"
    SecurityGroup: "Virtual firewall controlling traffic. Must follow least-privilege access principles"
    KeyPair: "SSH key pairs for secure instance access. Regular rotation required"
    NetworkInterface: "Virtual network interface for advanced networking configurations"
    Snapshot: "Point-in-time EBS volume backups. Automated backup policies required"
    Image: "Amazon Machine Images for instance deployment. Must use approved corporate AMIs"
    LaunchTemplate: "Template for consistent instance configuration and deployment"

S3:
  default_description: "Amazon Simple Storage Service - Enterprise object storage with advanced security and compliance features"
  display_name: "S3 (Simple Storage Service)"
  category: "Storage"
  documentation_url: "https://docs.aws.amazon.com/s3/"
  compliance_notes: "All S3 buckets must have encryption enabled and follow data classification policies"
  resource_types:
    Bucket: "Object storage container with enterprise security controls and lifecycle management"

RDS:
  default_description: "Amazon Relational Database Service - Managed database service with enterprise features"
  display_name: "RDS (Relational Database Service)"
  category: "Database"
  documentation_url: "https://docs.aws.amazon.com/rds/"
  compliance_notes: "All RDS instances must have encryption at rest and automated backups enabled"
  resource_types:
    DBInstance: "Managed database instance with automated maintenance and enterprise security"
    DBCluster: "Aurora cluster providing high availability and automatic failover"
    DBSubnetGroup: "Subnet group for database network isolation and security"
    DBParameterGroup: "Database configuration parameters following enterprise standards"
    DBSnapshot: "Database backup snapshot for disaster recovery"

Lambda:
  default_description: "AWS Lambda - Serverless compute platform for event-driven applications"
  display_name: "Lambda"
  category: "Compute"
  documentation_url: "https://docs.aws.amazon.com/lambda/"
  compliance_notes: "Lambda functions must follow secure coding practices and have appropriate IAM permissions"
  resource_types:
    Function: "Serverless function with enterprise monitoring and security controls"

VPC:
  default_description: "Amazon Virtual Private Cloud - Enterprise network infrastructure with advanced security"
  display_name: "VPC (Virtual Private Cloud)"
  category: "Networking"
  documentation_url: "https://docs.aws.amazon.com/vpc/"
  compliance_notes: "VPC configurations must follow enterprise network security standards"
  resource_types:
    VPC: "Isolated virtual network environment with enterprise security controls"
    Subnet: "Network subdivision with appropriate security group and NACL configurations"
    InternetGateway: "Internet access gateway with controlled routing"
    NatGateway: "Managed NAT service for secure outbound internet access"
    RouteTable: "Network routing configuration following security best practices"
    NetworkAcl: "Network-level access control for additional security layer"
    VPCEndpoint: "Private connectivity to AWS services without internet routing"

IAM:
  default_description: "AWS Identity and Access Management - Enterprise identity and access control service"
  display_name: "IAM (Identity and Access Management)"
  category: "Security"
  documentation_url: "https://docs.aws.amazon.com/iam/"
  compliance_notes: "All IAM resources must follow least-privilege principles and regular access reviews"
  resource_types:
    User: "IAM user account with appropriate permissions and MFA requirements"
    Role: "IAM role for service-to-service authentication and cross-account access"
    Policy: "Permission policy defining allowed actions and resources"
    Group: "User group for simplified permission management"

ELB:
  default_description: "Elastic Load Balancing - Managed load balancing service for high availability"
  display_name: "ELB (Elastic Load Balancing)"
  category: "Networking"
  documentation_url: "https://docs.aws.amazon.com/elasticloadbalancing/"
  compliance_notes: "Load balancers must have appropriate security groups and SSL/TLS configuration"
  resource_types:
    LoadBalancer: "Load balancer distributing traffic across multiple targets"
    TargetGroup: "Group of targets for load balancer routing"

ECS:
  default_description: "Amazon Elastic Container Service - Managed container orchestration service"
  display_name: "ECS (Elastic Container Service)"
  category: "Containers"
  documentation_url: "https://docs.aws.amazon.com/ecs/"
  compliance_notes: "Container images must be scanned for vulnerabilities and follow security best practices"
  resource_types:
    Cluster: "Container cluster for running containerized applications"
    Service: "Container service ensuring desired number of running tasks"
    TaskDefinition: "Blueprint for running containers with resource requirements"

EKS:
  default_description: "Amazon Elastic Kubernetes Service - Managed Kubernetes service"
  display_name: "EKS (Elastic Kubernetes Service)"
  category: "Containers"
  documentation_url: "https://docs.aws.amazon.com/eks/"
  compliance_notes: "EKS clusters must have appropriate RBAC and network policies configured"
  resource_types:
    Cluster: "Managed Kubernetes cluster with enterprise security features"
    NodeGroup: "Group of worker nodes for running Kubernetes workloads"
```

### Industry-Specific Service Descriptions

```yaml
# Healthcare/HIPAA-compliant descriptions
EC2:
  default_description: "HIPAA-eligible compute service for healthcare workloads with encryption and audit capabilities"
  compliance_notes: "Must be configured for HIPAA compliance with encryption at rest and in transit"
  resource_types:
    Instance: "HIPAA-eligible virtual machines with required security configurations for PHI processing"

S3:
  default_description: "HIPAA-eligible object storage with encryption and access logging for healthcare data"
  compliance_notes: "Must have server-side encryption, access logging, and appropriate bucket policies for PHI"
  resource_types:
    Bucket: "HIPAA-compliant storage bucket with encryption and audit trail for healthcare data"

# Financial Services descriptions
EC2:
  default_description: "SOC 2 Type II compliant compute service for financial services workloads"
  compliance_notes: "Must meet PCI DSS requirements and financial services regulatory standards"
  resource_types:
    Instance: "SOC 2 compliant virtual machines for processing financial data with required security controls"

RDS:
  default_description: "SOC 2 compliant managed database service for financial data with encryption and audit"
  compliance_notes: "Must have encryption at rest, automated backups, and meet financial regulatory requirements"
  resource_types:
    DBInstance: "PCI DSS compliant database instance for financial data processing"
```

## Tag Mappings Configuration

### Basic Tag Mappings

```yaml
# Basic custom tag mappings
"inventag:remarks":
  column_name: "Remarks"
  default_value: ""
  description: "Additional remarks or notes about the resource"

"inventag:costcenter":
  column_name: "Cost Center"
  default_value: "Unknown"
  description: "Cost center responsible for the resource"

"inventag:owner":
  column_name: "Resource Owner"
  default_value: "Unassigned"
  description: "Person or team responsible for the resource"

"inventag:project":
  column_name: "Project"
  default_value: ""
  description: "Project or application the resource belongs to"
```

### Enterprise Tag Mappings

```yaml
# Comprehensive enterprise tag mappings
"company:cost-center":
  column_name: "Cost Center"
  default_value: "UNASSIGNED"
  description: "Financial cost center for chargeback and budgeting"

"company:business-unit":
  column_name: "Business Unit"
  default_value: "UNKNOWN"
  description: "Business unit or division owning the resource"

"company:environment":
  column_name: "Environment"
  default_value: "UNDEFINED"
  description: "Environment classification (prod, staging, dev, test)"

"company:application":
  column_name: "Application"
  default_value: "UNTAGGED"
  description: "Application or service name"

"company:owner":
  column_name: "Technical Owner"
  default_value: "UNASSIGNED"
  description: "Technical owner or responsible team"

"company:data-classification":
  column_name: "Data Classification"
  default_value: "UNCLASSIFIED"
  description: "Data sensitivity classification (public, internal, confidential, restricted)"

"company:backup-required":
  column_name: "Backup Required"
  default_value: "UNKNOWN"
  description: "Whether resource requires backup (yes, no, n/a)"

"company:monitoring-level":
  column_name: "Monitoring Level"
  default_value: "STANDARD"
  description: "Required monitoring level (basic, standard, enhanced, critical)"

"company:compliance-scope":
  column_name: "Compliance Scope"
  default_value: "NONE"
  description: "Compliance frameworks applicable (sox, pci, hipaa, gdpr)"

"company:auto-shutdown":
  column_name: "Auto Shutdown"
  default_value: "DISABLED"
  description: "Automatic shutdown configuration for cost optimization"

"company:patch-group":
  column_name: "Patch Group"
  default_value: "DEFAULT"
  description: "Patching group for maintenance scheduling"

"company:disaster-recovery":
  column_name: "DR Tier"
  default_value: "TIER3"
  description: "Disaster recovery tier (tier1, tier2, tier3, tier4)"
```

### Compliance-Focused Tag Mappings

```yaml
# HIPAA compliance tags
"hipaa:phi-data":
  column_name: "Contains PHI"
  default_value: "UNKNOWN"
  description: "Whether resource processes Protected Health Information"

"hipaa:encryption-required":
  column_name: "Encryption Required"
  default_value: "YES"
  description: "HIPAA encryption requirement status"

"hipaa:access-logging":
  column_name: "Access Logging"
  default_value: "REQUIRED"
  description: "HIPAA access logging requirement"

# PCI DSS compliance tags
"pci:cardholder-data":
  column_name: "Cardholder Data"
  default_value: "NO"
  description: "Whether resource processes cardholder data"

"pci:compliance-scope":
  column_name: "PCI Scope"
  default_value: "OUT_OF_SCOPE"
  description: "PCI DSS compliance scope (in_scope, out_of_scope, connected)"

# SOX compliance tags
"sox:financial-reporting":
  column_name: "Financial Reporting"
  default_value: "NO"
  description: "Whether resource supports financial reporting processes"

"sox:control-environment":
  column_name: "SOX Controls"
  default_value: "STANDARD"
  description: "SOX control environment classification"

# GDPR compliance tags
"gdpr:personal-data":
  column_name: "Personal Data"
  default_value: "UNKNOWN"
  description: "Whether resource processes EU personal data"

"gdpr:data-retention":
  column_name: "Data Retention"
  default_value: "STANDARD"
  description: "GDPR data retention classification"
```

### Multi-Cloud Tag Mappings

```yaml
# Multi-cloud standardized tags
"cloud:provider":
  column_name: "Cloud Provider"
  default_value: "AWS"
  description: "Cloud service provider (AWS, Azure, GCP)"

"cloud:region":
  column_name: "Cloud Region"
  default_value: ""
  description: "Cloud provider region"

"cloud:availability-zone":
  column_name: "Availability Zone"
  default_value: ""
  description: "Specific availability zone within region"

"cloud:instance-type":
  column_name: "Instance Type"
  default_value: ""
  description: "Cloud instance or resource type"

"cloud:pricing-model":
  column_name: "Pricing Model"
  default_value: "ON_DEMAND"
  description: "Pricing model (on_demand, reserved, spot, savings_plan)"

"cloud:auto-scaling":
  column_name: "Auto Scaling"
  default_value: "DISABLED"
  description: "Auto scaling configuration status"
```

## BOM Processing Configuration

### Basic BOM Configuration

```yaml
# Basic BOM processing configuration
document_generation:
  formats:
    - excel
    - word
  
  branding:
    company_name: "My Company"
    logo_path: "assets/company-logo.png"
    color_scheme:
      primary: "#1f4e79"
      secondary: "#70ad47"
      accent: "#c55a11"

  templates:
    excel_template: "templates/custom_excel_template.json"
    word_template: "templates/custom_word_template.yaml"

network_analysis:
  enabled: true
  include_vpc_flow_logs: false
  calculate_ip_utilization: true
  identify_unused_resources: true

security_analysis:
  enabled: true
  check_security_groups: true
  analyze_nacls: true
  identify_overly_permissive_rules: true
  security_risk_threshold: "medium"

compliance_analysis:
  enabled: true
  policy_files:
    - "config/tag_policy.yaml"
  compliance_threshold: 85
  generate_compliance_report: true

state_management:
  enabled: true
  state_directory: "state"
  retention_days: 90
  enable_delta_detection: true
  generate_changelog: true

output_configuration:
  directory: "bom_output"
  file_naming_pattern: "bom_report_{timestamp}_{account}"
  include_timestamp: true
  compress_output: false
```

### Enterprise BOM Configuration

```yaml
# Enterprise-grade BOM processing configuration
document_generation:
  formats:
    - excel
    - word
    - pdf
  
  branding:
    company_name: "Enterprise Corp"
    logo_path: "assets/enterprise-logo.png"
    header_text: "AWS Cloud Infrastructure Bill of Materials"
    footer_text: "Confidential - Enterprise Corp Internal Use Only"
    color_scheme:
      primary: "#003366"
      secondary: "#0066cc"
      accent: "#ff6600"
      success: "#00cc66"
      warning: "#ffcc00"
      danger: "#cc0000"
    
    themes:
      default: "professional"
      compliance: "high-contrast"
      executive: "modern"

  templates:
    excel_template: "templates/enterprise_excel_template.json"
    word_template: "templates/enterprise_word_template.yaml"
    pdf_template: "templates/enterprise_pdf_template.yaml"

network_analysis:
  enabled: true
  include_vpc_flow_logs: true
  calculate_ip_utilization: true
  identify_unused_resources: true
  analyze_peering_connections: true
  check_transit_gateways: true
  generate_network_diagrams: true
  capacity_planning:
    enabled: true
    growth_projection_months: 12
    utilization_threshold: 80

security_analysis:
  enabled: true
  check_security_groups: true
  analyze_nacls: true
  identify_overly_permissive_rules: true
  security_risk_threshold: "low"
  analyze_iam_policies: true
  check_encryption_status: true
  scan_for_public_resources: true
  compliance_frameworks:
    - "CIS"
    - "NIST"
    - "SOC2"
  
  risk_scoring:
    enabled: true
    weight_factors:
      public_access: 0.4
      encryption: 0.3
      access_controls: 0.3

compliance_analysis:
  enabled: true
  policy_files:
    - "config/enterprise_tag_policy.yaml"
    - "config/security_policy.yaml"
    - "config/compliance_policy.yaml"
  compliance_threshold: 95
  generate_compliance_report: true
  compliance_frameworks:
    - name: "SOX"
      enabled: true
      policy_file: "config/sox_policy.yaml"
    - name: "PCI DSS"
      enabled: true
      policy_file: "config/pci_policy.yaml"
    - name: "HIPAA"
      enabled: false
      policy_file: "config/hipaa_policy.yaml"

cost_analysis:
  enabled: true
  include_pricing_estimates: true
  identify_cost_optimization_opportunities: true
  analyze_reserved_instances: true
  check_unused_resources: true
  cost_allocation_tags:
    - "company:cost-center"
    - "company:business-unit"
    - "company:project"

state_management:
  enabled: true
  state_directory: "enterprise_state"
  retention_days: 365
  enable_delta_detection: true
  generate_changelog: true
  backup_state: true
  backup_location: "s3://enterprise-inventag-state-backup"

change_tracking:
  enabled: true
  track_configuration_changes: true
  track_compliance_changes: true
  track_security_changes: true
  change_notification:
    enabled: true
    channels:
      - slack
      - email
    thresholds:
      major_changes: 10
      security_changes: 1

output_configuration:
  directory: "enterprise_bom_output"
  file_naming_pattern: "enterprise_bom_{environment}_{timestamp}"
  include_timestamp: true
  compress_output: true
  encryption:
    enabled: true
    kms_key_id: "alias/enterprise-inventag-key"
  
  s3_upload:
    enabled: true
    bucket: "enterprise-compliance-reports"
    key_prefix: "bom-reports/"
    encryption: "aws:kms"
    kms_key_id: "alias/enterprise-s3-key"

monitoring:
  enabled: true
  metrics_export:
    cloudwatch:
      enabled: true
      namespace: "Enterprise/InvenTag"
    prometheus:
      enabled: true
      pushgateway_url: "http://prometheus-pushgateway:9091"
  
  alerting:
    enabled: true
    compliance_threshold_alerts: true
    processing_failure_alerts: true
    security_finding_alerts: true

notification:
  channels:
    slack:
      enabled: true
      webhook_url: "${SLACK_WEBHOOK_URL}"
      channel: "#compliance-alerts"
    
    email:
      enabled: true
      smtp_server: "smtp.enterprise.com"
      recipients:
        - "compliance-team@enterprise.com"
        - "security-team@enterprise.com"
    
    teams:
      enabled: false
      webhook_url: "${TEAMS_WEBHOOK_URL}"

performance:
  parallel_processing:
    max_concurrent_accounts: 10
    max_concurrent_regions: 5
    max_concurrent_services: 20
  
  caching:
    enabled: true
    cache_duration_hours: 24
    cache_location: "cache/"
  
  optimization:
    batch_size: 1000
    api_retry_attempts: 3
    api_timeout_seconds: 30
```

## Environment-Specific Configurations

### Development Environment

```yaml
# Development environment configuration
accounts:
  - account_id: "111111111111"
    account_name: "Development"
    profile_name: "dev"
    regions: ["us-east-1"]
    services: ["EC2", "S3", "Lambda"]
    tags:
      Environment: "development"

settings:
  max_concurrent_accounts: 1
  account_processing_timeout: 900
  output_directory: "dev_bom"
  enable_state_management: false
  enable_delta_detection: false
```

### Production Environment

```yaml
# Production environment configuration
accounts:
  - account_id: "999999999999"
    account_name: "Production"
    role_arn: "arn:aws:iam::999999999999:role/InvenTagProdRole"
    regions: ["us-east-1", "us-west-2", "eu-west-1"]
    services: []  # All services
    tags:
      Environment: "production"

settings:
  max_concurrent_accounts: 8
  account_processing_timeout: 7200
  output_directory: "prod_bom"
  enable_state_management: true
  enable_delta_detection: true
  generate_per_account_reports: true
```

This comprehensive configuration guide provides templates and examples for various InvenTag deployment scenarios and use cases.