---
title: Network and security analysis
description: The current state of InvenTag's network and security-group analysis flags, and how to review VPCs and security groups with the reports today.
sidebar_position: 5
slug: /architecture/network-analysis
---

# Network and security analysis

**Who this is for:** you want to review VPCs, subnets and security groups with
InvenTag.

**What you will know after reading:** what the analysis flags add to a report.

## Current state

InvenTag has two flags for this:

- `--enable-network-analysis`: VPCs, subnets and how they are used.
- `--enable-security-analysis`: security groups and network ACLs.

Each flag adds one sheet to the Excel report:

- `--enable-network-analysis` adds the `Network Analysis` sheet. It lists each
  VPC with its CIDR block, total and available IP addresses, and subnets.
- `--enable-security-analysis` adds the `Security Analysis` sheet. It lists
  each security group with its rules, its risk level and the resources that
  use it.

InvenTag writes a sheet only if the scan finds VPCs or security groups. The
Word report does not have these sections.

```bash
./inventag.sh --create-excel --enable-network-analysis --enable-security-analysis
```

Example of the `Security Analysis` sheet:

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Has Permissive Rules |
|---|---|---|---|---|---|
| sg-0bf7019da40cb75c1 | web | vpc-d242bc5ced0c09235 | High | 1 | Yes |

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
./inventag.sh --template network-review --create-excel --account-regions us-east-1
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
