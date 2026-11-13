---
title: 网络与安全分析
description: InvenTag 的网络和安全组分析参数会向 Excel 报告增加什么、不包含什么，以及如何审查 VPC 和安全组。
sidebar_position: 5
slug: /architecture/network-analysis
---

# 网络与安全分析

**适合谁阅读：** 你想用 InvenTag 审查 VPC、子网和安全组。

**读完后你会了解：** 这些分析参数会向报告增加什么内容。

## 这些参数增加什么 {#what-the-flags-add}

InvenTag 为此提供两个参数：

- `--enable-network-analysis`：VPC、子网及其使用情况。
- `--enable-security-analysis`：安全组。

每个参数会向 Excel 报告增加一个工作表：

- `--enable-network-analysis` 增加 `Network Analysis` 工作表。它列出每个 VPC 及其 CIDR 块、
  IP 地址总数和可用数量、利用率和子网数量，然后是一张子网表。
- `--enable-security-analysis` 增加 `Security Analysis` 工作表。它列出每个安全组及其规则数量、
  风险级别以及是否有宽松规则，然后是一张列出每条规则的表。

限制：

- 只有当扫描发现了 VPC 或安全组时，才会写入相应的工作表。
- Word 报告没有网络或安全章节。
- 网络 ACL 不属于 Security Analysis 工作表，它们出现在 `VPC` 工作表中。
- 使用 `--template` 时，这些参数**不会增加任何工作表**：内置的报告模板没有这类工作表
  （我们用 `--template standard-bom` 检查过）。请使用默认版式，或使用保留了
  `network_analysis` 和 `security_analysis` 部分的版式文件（`--excel-template`）。
- 风险级别是 InvenTag 中的一条简单规则，不是安全评估。

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

下面是针对模拟 AWS 离线运行时打印的内容，以及每个工作表的前几行（示例数据）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Network Analysis` 工作表的前几行：

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Security Analysis` 工作表的前几行：

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | low | 0 | 1 | 1 | No |  |

## 网络资源的更多细节 {#more-detail-on-network-resources}

网络资源是每次普通扫描的一部分。使用 `standard-bom` 模板时，它们出现在 **VPC** 工作表中：
VPC、子网、路由表、网络 ACL 和安全组，每个都带有其标签。

如果还想看到它们的配置，请加入 AWS API 返回的所有字段：

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

这样 VPC 工作表中，AWS API 返回的每个字段都有一列。它们很详细，但没有经过汇总。
在一次离线运行中（示例数据）：

VPC 工作表有 57 列。此示例中的 `raw_data.*` 列是：

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

## 下一步 {#next-steps}

- [功能状态与已知限制](../getting-started/status.md)
- [调整模板](../templates/adapt-a-template.md)
