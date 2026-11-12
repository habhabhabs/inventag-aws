---
title: AWS Prescriptive Guidance Templates
description: Reference tagging templates based on the AWS Prescriptive Guidance for cost allocation tagging
sidebar_position: 2
---

# 🏛️ AWS Prescriptive Guidance Templates

Reference templates written by the InvenTag project, based on the public
[AWS Prescriptive Guidance for cost allocation tagging](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/).
They are a starting point for your own tagging standard. They are not published
or reviewed by AWS, and today they are reference material rather than CLI input
(see [Quick start](#-quick-start) below).

## 📚 AWS Documentation References

### Core AWS Prescriptive Guidance
- **[Cost Allocation Tagging Guide](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/)** - Complete AWS methodology
- **[Tagging Strategy](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/tagging-strategy.html)** - Strategic framework
- **[Implementation Steps](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/implementation.html)** - 5-step methodology

### AWS Service Documentation
- **[AWS Organizations Tag Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_tag-policies.html)** - Centralized tag governance
- **[Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)** - Preventive controls
- **[AWS Config Rules](https://docs.aws.amazon.com/config/latest/developerguide/required-tags.html)** - Compliance monitoring
- **[Cost Allocation Tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)** - Financial reporting
- **[Resource Groups Tagging API](https://docs.aws.amazon.com/resourcegroupstaggingapi/latest/APIReference/Welcome.html)** - Programmatic tagging

### Best Practices Documentation
- **[AWS Tagging Best Practices](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html)** - General guidelines
- **[Well-Architected Cost Optimization](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html)** - Cost optimization framework
- **[CloudFormation Resource Tags](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-resource-tags.html)** - Infrastructure as Code tagging

## 🎯 Overview

These templates implement the complete [AWS Prescriptive Guidance 5-Step Methodology](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/tagging-strategy.html):

1. **[Define tagging dictionary](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step1.html)** - Comprehensive tag dictionary with validation rules
2. **[Publish tagging dictionary](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step2.html)** - Organization-wide distribution and awareness
3. **[Define rules for applying tags](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step3.html)** - Automated governance via SCPs and tag policies
4. **[Apply tags](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step4.html)** - Implementation using AWS native tools
5. **[Measure, enforce, and evolve](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step5.html)** - Continuous monitoring and optimization

**Key AWS Requirements Addressed:**
- **[Three-Dimensional Organization](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/dimensions.html)** - Technical, business, and security dimensions
- **[Multi-Stakeholder Approach](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/stakeholders.html)** - Finance, IT, Engineering, Security, and Operations alignment
- **[Standardized Naming](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html)** - AWS hyphen-separated naming conventions
- **[FinOps Integration](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html)** - Cost optimization and financial operations

## 📋 Available Templates

### 1. Tagging Dictionary Template
**File**: [tagging-dictionary.yaml](/files/tagging-dictionary.yaml)

Comprehensive tag definitions following AWS prescriptive guidance:

```yaml
# Required Tags (Financial Management)
- CostCenter: "CC-1001" 
- Project: "PROJ-2024-WEBAPP"
- BusinessUnit: "Engineering"
- Environment: "prod"
- Application: "user-authentication-service"

# Recommended Tags
- TeamName: "Platform Engineering"
- ContactEmail: "platform-team@company.com"
- DataClassification: "confidential"
- BackupRequired: "true"

# Conditional Tags (Environment-Specific)
- MaintenanceWindow: "Sunday-0200-0400" (Production only)
- SLALevel: "gold" (Production only)
- ComplianceFramework: "soc2" (Production only)
```

**Key Features (AWS Compliant):**
- ✅ [AWS standard naming conventions](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html) (hyphen-separated)
- ✅ [Three-dimensional organization](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/dimensions.html) (technical, business, security)
- ✅ [5-step methodology compliance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/tagging-strategy.html)
- ✅ [Service Control Policy integration](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- ✅ [Tag policy enforcement](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_tag-policies.html)
- ✅ [AWS Config rule templates](https://docs.aws.amazon.com/config/latest/developerguide/required-tags.html)

### 2. Service Descriptions Template  
**File**: [service-descriptions.yaml](/files/service-descriptions.yaml)

Enhanced service descriptions with cost allocation focus:

```yaml
services:
  ec2:
    cost_allocation_priority: "high"
    required_tags: ["CostCenter", "Project", "Environment", "BusinessUnit", "Application"]
    cost_factors:
      - "Instance type and size"
      - "Reserved vs On-Demand pricing"
      - "EBS storage attached"
    governance_notes: "Critical for cost optimization - enable detailed monitoring"
    
  s3:
    cost_allocation_priority: "high" 
    cost_factors:
      - "Storage class (Standard, IA, Glacier)"
      - "Data transfer costs"
      - "Request costs (GET, PUT, DELETE)"
    governance_notes: "Implement lifecycle policies for optimal spend visibility"
```

**Key Features (AWS Aligned):**
- 🎯 [Cost allocation priorities](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html) per service
- 💰 [AWS Cost Explorer integration](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ce-what-is.html) ready
- 🏷️ [Service-specific tagging requirements](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html)
- 📊 [Multi-dimensional cost analysis](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/dimensions.html)
- 🔧 [AWS native tool integration](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step4.html)

### 3. Tag Mappings Template
**File**: [tag-mappings.yaml](/files/tag-mappings.yaml)

Financial governance optimized column mappings:

```yaml
financial_governance:
  cost_center:
    tag_key: "CostCenter"
    column_name: "Cost Center"
    column_order: 1
    required: true
    validation_pattern: "^CC-[0-9]{4}$"
    report_grouping: "primary"
    
organizational:
  business_unit:
    tag_key: "BusinessUnit" 
    column_name: "Business Unit"
    column_order: 5
    required: true
    report_grouping: "primary"
```

**Key Features (AWS Standards):**
- 📈 [AWS-recommended cost allocation hierarchy](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
- 📊 [AWS QuickSight integration](https://docs.aws.amazon.com/quicksight/latest/user/cost-analysis.html) ready
- ✅ [Tag policy validation rules](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_tag-policies.html)
- 🎨 [Cost Explorer compatible formatting](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ce-what-is.html)
- 📋 [AWS Config compliance templates](https://docs.aws.amazon.com/config/latest/developerguide/required-tags.html)

## 🚀 Quick Start

### 1. Download Templates

```bash
# Download all AWS Prescriptive Guidance templates
curl -O https://habhabhabs.github.io/inventag-aws/files/tagging-dictionary.yaml
curl -O https://habhabhabs.github.io/inventag-aws/files/service-descriptions.yaml  
curl -O https://habhabhabs.github.io/inventag-aws/files/tag-mappings.yaml
```

### 2. Use them as a reference (not as CLI input, yet)

:::caution These files do not load in the CLI today
`config/aws-prescriptive-guidance/tag-mappings.yaml` and
`service-descriptions.yaml` use a richer layout than the CLI's loaders accept.
Passed to `--tag-mappings` / `--service-descriptions`, they are rejected (an
error in the log) and the report falls back to defaults. The
`tagging-dictionary.yaml` file has no CLI flag at all. Earlier versions of this
page showed flags such as `--enable-governance-reporting`,
`--cost-allocation-focus` and `--compliance-standard aws-prescriptive-guidance`;
those do not exist.
:::

Use the dictionary as a checklist for your tagging standard, then express it in
the formats InvenTag does load:

```yaml
# tag-mappings.yaml: report columns for your cost-allocation tags
tag_mappings:
  - tag: "CostCenter"
    name: "Cost Center"
  - tag: "BusinessUnit"
    name: "Business Unit"
  - tag: "Environment"
    name: "Environment"
  - tag: "Owner"
    name: "Owner"
```

```bash
./inventag.sh --accounts-file accounts.json --create-excel \
  --tag-mappings tag-mappings.yaml
```

### 3. Check tag compliance

Write the required tags and allowed values as a tag policy (layout:
`config/defaults/compliance/tag_compliance_policy_example.yaml`) and run the
tag-policy checker:

```bash
python3 scripts/legacy/tag_compliance_checker.py \
  --config my-tag-policy.yaml --format excel --output compliance_report
```

## 📊 Cost Allocation Hierarchy

The templates implement a 4-level cost allocation hierarchy following AWS best practices:

```text
Level 1: Business Unit
├── Level 2: Cost Center  
│   ├── Level 3: Project
│   │   └── Level 4: Application
│   └── Level 3: Project
│       └── Level 4: Application
└── Level 2: Cost Center
    └── Level 3: Project
        └── Level 4: Application
```

**Example Hierarchy:**
- **Business Unit**: Engineering
  - **Cost Center**: CC-1001 (Platform Team)
    - **Project**: PROJ-2024-WEBAPP
      - **Application**: user-authentication-service
      - **Application**: payment-processing-api
    - **Project**: PROJ-2024-MOBILE
      - **Application**: mobile-app-backend

## 🎯 Compliance Frameworks

### Financial Governance
- **Cost Center Attribution** - Mandatory for all resources
- **Project-Based Allocation** - Detailed project cost tracking
- **Budget Category Mapping** - Infrastructure, Development, Operations, Security
- **Chargeback Integration** - Internal billing and cost recovery

### Security and Compliance
- **SOC 2** - System and Organization Controls
- **PCI DSS** - Payment Card Industry Data Security Standard  
- **HIPAA** - Health Insurance Portability and Accountability Act
- **GDPR** - General Data Protection Regulation

### Operational Excellence
- **SLA-Based Classifications** - Gold, Silver, Bronze service levels
- **Automated Governance** - Tag policies and Service Control Policies
- **Monitoring and Alerting** - Cost anomaly detection and compliance dashboards
- **Lifecycle Management** - Data retention and backup policies

## 🏭 Industry Templates

### Financial Services
```yaml
additional_tags: 
  - "ComplianceFramework"
  - "DataClassification" 
  - "RegulatoryConcern"
enhanced_governance: true
retention_requirements: "7 years"
```

### Healthcare
```yaml
additional_tags:
  - "PHI_Status"
  - "HIPAA_Applicable"
  - "PatientData"
enhanced_security: true
encryption_required: true
```

### Government  
```yaml
additional_tags:
  - "SecurityLevel"
  - "AuthorityToOperate"
  - "FISMA_Level"
enhanced_compliance: true
audit_trail_required: true
```

## 🔧 Implementation Roadmap

### Phase 1: [Dictionary Development](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step1.html) (2 weeks)
- ✅ [Define tagging dictionary](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step1.html) with stakeholder engagement
- ✅ Establish [three-dimensional framework](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/dimensions.html)
- ✅ Create [AWS-compliant naming conventions](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html)
- 🎯 **Target**: Complete dictionary with stakeholder approval

### Phase 2: [Publication](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step2.html) (1 week)
- ✅ [Publish dictionary organization-wide](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step2.html)
- ✅ Conduct all-hands meetings and training
- ✅ Create internal documentation and wikis
- 🎯 **Target**: 100% stakeholder awareness and formal approval

### Phase 3: [Rule Definition](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step3.html) (1 week)
- ✅ [Deploy Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- ✅ [Configure Tag Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_tag-policies.html)
- ✅ [Setup AWS Config Rules](https://docs.aws.amazon.com/config/latest/developerguide/required-tags.html)
- 🎯 **Target**: Automated enforcement policies active

### Phase 4: [Tag Application](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step4.html) (4-6 weeks)
- ✅ [Use Tag Editor for existing resources](https://docs.aws.amazon.com/resourcegroupstaggingapi/latest/userguide/resource-groups-tagging-api-overview.html)
- ✅ [Update CloudFormation templates](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-resource-tags.html)
- ✅ [Enable cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
- 🎯 **Target**: 90% compliance on required tags

### Phase 5: [Measure and Evolve](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step5.html) (Ongoing)
- ✅ [Monitor KPIs](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/kpis.html) and compliance metrics
- ✅ [Use Cost Explorer](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ce-what-is.html) for cost analysis
- ✅ Quarterly strategy reviews and optimization
- 🎯 **Target**: 95% compliance maintained with continuous improvement

## 📈 Expected Outcomes

### Cost Visibility
- **Granular Cost Tracking** - Project and application level visibility
- **Budget Accountability** - Clear cost center responsibility
- **Trend Analysis** - Historical cost patterns and forecasting
- **Optimization Opportunities** - Right-sizing and scheduling recommendations

### Governance Benefits
- **Automated Compliance** - Continuous policy enforcement
- **Audit Readiness** - Complete resource attribution and tracking
- **Risk Mitigation** - Data classification and security controls
- **Operational Excellence** - Standardized resource management

### Financial Impact
- **15-30% Cost Reduction** - Through better visibility and optimization
- **Accurate Chargeback** - Fair cost allocation across business units
- **Budget Planning** - Data-driven financial planning
- **ROI Tracking** - Project-level return on investment analysis

## 🛠️ Tools and Automation

### [AWS Native Tools](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/step4.html)
- **[AWS Cost Explorer](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ce-what-is.html)** - Cost analysis and reporting
- **[AWS Budgets](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-managing-costs.html)** - Budget alerts and controls
- **[AWS Tag Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_tag-policies.html)** - Centralized tag governance
- **[Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)** - Preventive controls
- **[AWS Config Rules](https://docs.aws.amazon.com/config/latest/developerguide/required-tags.html)** - Compliance monitoring
- **[Resource Groups Tag Editor](https://docs.aws.amazon.com/resourcegroupstaggingapi/latest/userguide/resource-groups-tagging-api-overview.html)** - Bulk tagging operations

### Third-Party Integration
- **CloudHealth** - Advanced cost management
- **CloudCheckr** - Governance and optimization
- **Terraform** - Infrastructure as Code with tags
- **InvenTag AWS** - Comprehensive discovery and reporting

## 📚 Additional Resources

### AWS Documentation
- **[AWS Prescriptive Guidance: Cost Allocation Tagging](https://docs.aws.amazon.com/prescriptive-guidance/latest/cost-allocation-tagging/)** - Complete methodology
- **[AWS Tagging Best Practices](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html)** - General tagging guidelines
- **[AWS Cost Management User Guide](https://docs.aws.amazon.com/cost-management/)** - Financial operations
- **[AWS Organizations User Guide](https://docs.aws.amazon.com/organizations/latest/userguide/)** - Multi-account governance
- **[AWS Config Developer Guide](https://docs.aws.amazon.com/config/latest/developerguide/)** - Compliance monitoring
- **[AWS CloudFormation User Guide](https://docs.aws.amazon.com/cloudformation/)** - Infrastructure as Code
- **[Resource Groups and Tags User Guide](https://docs.aws.amazon.com/resourcegroupstaggingapi/latest/userguide/)** - Programmatic tagging

### InvenTag Resources
- [Getting Started Guide](./getting-started/quick-start.md)
- [CLI User Guide](./user-guides/cli-user-guide.md)
- [Configuration Examples](./examples/index.md)
- [Production Safety Guide](./user-guides/production-safety.md)

## 🤝 Support and Community

Need help implementing AWS Prescriptive Guidance templates?

- **📖 Documentation**: Complete guides and examples
- **🐛 Issues**: [GitHub Issues](https://github.com/habhabhabs/inventag-aws/issues)
- **💬 Discussions**: [Community Q&A](https://github.com/habhabhabs/inventag-aws/discussions)
- **📧 Enterprise Support**: Contact your AWS Solutions Architect

---

**Ready to transform your AWS cost allocation and governance?** Start with our [Quick Start Guide](./getting-started/quick-start.md) and download the professional templates above.