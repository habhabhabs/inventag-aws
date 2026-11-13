---
title: 網路與安全分析
description: InvenTag 的網路和安全組分析引數會向 Excel 報告增加什麼、不包含什麼，以及如何審查 VPC 和安全組。
sidebar_position: 5
slug: /architecture/network-analysis
---

# 網路與安全分析

**適合誰閱讀：** 你想用 InvenTag 審查 VPC、子網和安全組。

**讀完後你會了解：** 這些分析引數會向報告增加什麼內容。

## 這些引數增加什麼 {#what-the-flags-add}

InvenTag 為此提供兩個引數：

- `--enable-network-analysis`：VPC、子網及其使用情況。
- `--enable-security-analysis`：安全組。

每個引數會向 Excel 報告增加一個工作表：

- `--enable-network-analysis` 增加 `Network Analysis` 工作表。它列出每個 VPC 及其 CIDR 塊、
  IP 地址總數和可用數量、利用率和子網數量，然後是一張子網表。
- `--enable-security-analysis` 增加 `Security Analysis` 工作表。它列出每個安全組及其規則數量、
  風險級別以及是否有寬鬆規則，然後是一張列出每條規則的表。

限制：

- 只有當掃描發現了 VPC 或安全組時，才會寫入相應的工作表。
- Word 報告沒有網路或安全章節。
- 網路 ACL 不屬於 Security Analysis 工作表，它們出現在 `VPC` 工作表中。
- 使用 `--template` 時，這些引數**不會增加任何工作表**：內建的報告範本沒有這類工作表
  （我們用 `--template standard-bom` 檢查過）。請使用預設版面配置，或使用保留了
  `network_analysis` 和 `security_analysis` 部分的版面配置檔案（`--excel-template`）。
- 風險級別是 InvenTag 中的一條簡單規則，不是安全評估。

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

下面是針對模擬 AWS 離線執行時列印的內容，以及每個工作表的前幾列（範例資料）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Network Analysis` 工作表的前幾列：

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Security Analysis` 工作表的前幾列：

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | low | 0 | 1 | 1 | No |  |

## 網路資源的更多細節 {#more-detail-on-network-resources}

網路資源是每次普通掃描的一部分。使用 `standard-bom` 範本時，它們出現在 **VPC** 工作表中：
VPC、子網、路由表、網路 ACL 和安全組，每個都帶有其標籤。

如果還想看到它們的設定，請加入 AWS API 返回的所有欄位：

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

這樣 VPC 工作表中，AWS API 返回的每個欄位都有一欄。它們很詳細，但沒有經過彙總。
在一次離線執行中（範例資料）：

VPC 工作表有 57 欄。此範例中的 `raw_data.*` 欄是：

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

## 下一步 {#next-steps}

- [功能狀態與已知限制](../getting-started/status.md)
- [調整範本](../templates/adapt-a-template.md)
