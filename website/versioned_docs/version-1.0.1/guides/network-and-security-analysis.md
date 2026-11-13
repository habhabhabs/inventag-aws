---
title: Network and security analysis
description: What InvenTag's network and security-group analysis flags add to the Excel report, what they leave out, and how to review VPCs and security groups.
sidebar_position: 5
slug: /architecture/network-analysis
---

# Network and security analysis

**Who this is for:** you want to review VPCs, subnets and security groups with
InvenTag.

**What you will know after reading:** what the analysis flags add to a report.

## What the flags add

InvenTag has two flags for this:

- `--enable-network-analysis`: VPCs, subnets and how they are used.
- `--enable-security-analysis`: security groups.

Each flag adds one sheet to the Excel report:

- `--enable-network-analysis` adds the `Network Analysis` sheet. It lists each
  VPC with its CIDR block, total and available IP addresses, utilisation and
  subnet count, then a table of subnets.
- `--enable-security-analysis` adds the `Security Analysis` sheet. It lists
  each security group with its rule counts, a risk level and whether it has
  permissive rules, then a table of each rule.

Limits:

- A sheet is written only if the scan finds VPCs or security groups.
- The Word report has no network or security sections.
- Network ACLs are not part of the Security Analysis sheet. They appear on the
  `VPC` sheet.
- With `--template`, the flags add **no sheets**: the built-in report
  templates have no such sheets (we checked with `--template standard-bom`).
  Use the default layout, or a layout file (`--excel-template`), which keeps
  the `network_analysis` and `security_analysis` sections.
- The risk level is a simple rule in InvenTag, not a security assessment.

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

What a run prints, and the first rows of each sheet, from an offline run
against mocked AWS (sample data):

<!-- BEGIN EXAMPLE OUTPUT: analysis-console -->

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: analysis-console -->

<!-- BEGIN EXAMPLE OUTPUT: analysis-network -->

**Sheets:** `Summary`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

`Network Analysis` sheet, first rows:

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

<!-- END EXAMPLE OUTPUT: analysis-network -->

<!-- BEGIN EXAMPLE OUTPUT: analysis-security -->

**Sheets:** `Summary`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

`Security Analysis` sheet, first rows:

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | medium | 0 | 1 | 0 | No |  |

<!-- END EXAMPLE OUTPUT: analysis-security -->

## More detail on network resources

Network resources are part of every normal scan. With the `standard-bom`
template they appear on the **VPC** sheet: VPCs, subnets, route tables,
network ACLs and security groups, each with its tags.

To see their configuration as well, add every field the AWS API returned:

```yaml
# .inventag/templates/network-review.yaml
format_version: 1
kind: report
name: network-review
description: Every field, for a network review
extends: standard-bom
spec:
  title: Network review
  excel:
    include_all_fields: true
```

```bash
inventag --template network-review --create-excel --account-regions us-east-1
```

The VPC sheet then has a column for every field the AWS API returned. They
are detailed but not summarised. In an offline run (sample data):

<!-- BEGIN EXAMPLE OUTPUT: network-columns -->

The VPC sheet has 54 columns. The `raw_data.*` columns in this sample are:

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

<!-- END EXAMPLE OUTPUT: network-columns -->

## Next steps

- [Feature status and known limitations](../getting-started/status.md)
- [Adapt a template](../templates/adapt-a-template.md)
