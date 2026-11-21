---
title: FinOps 检查
description: 对扫描找到的资源运行六项固定的 FinOps 检查（未挂载的卷、未关联的地址、旧快照、已停止的实例、没有目标的负载均衡器、缺少的成本分配标签），不再发出任何 AWS 调用。
sidebar_position: 10
---

# FinOps 检查

**适合谁读：** 你负责云支出，想根据已有的清单得到一份值得查看的资源列表。

**读完后你能做到：** 运行六项 FinOps 检查，读懂 `FinOps` 工作表，并知道这些检查看不到什么。

## 运行检查 {#run-the-checks}

```bash
inventag --create-excel --finops-checks
```

该参数默认关闭。使用它时，InvenTag 对扫描找到的资源运行六项固定检查，并在 Excel 报告末尾添加一个名为 `FinOps` 的工作表。

- 这些检查只读取扫描已有的行。它们不再发出任何 AWS 调用，也不需要额外的权限。无论是否使用该参数，只读防护看到的调用都相同。
- 这些检查不会更改任何账户中的任何内容。
- 该参数不改变退出码。
- 不使用该参数的运行写出的报告与之前相同。

## 六项检查 {#the-six-checks}

| 检查 ID | 资源 | 结果为 `fail` 的条件 |
|---|---|---|
| `FIN-001` | EBS 卷 | 卷的 `State` 为 `available`（未挂载） |
| `FIN-002` | 弹性 IP 地址 | 地址没有 `AssociationId` |
| `FIN-003` | 被扫描账户拥有的 EBS 快照 | 快照的 `StartTime` 早于运行开始时间 90 天以上 |
| `FIN-004` | EC2 实例 | 实例状态为 `stopped` |
| `FIN-005` | 负载均衡器 | 同一账户和区域中没有任何目标组指向它（`ELBV2` 工作表），或它没有列出任何实例（经典负载均衡器，`ELB` 工作表） |
| `FIN-006` | 内置标签策略 `finops-cost-allocation` 范围内的每个资源 | 缺少该策略的某个键：`CostCenter`、`Owner`、`Project` 或 `Environment` |

`FIN-003` 的 90 天是固定的，没有参数可以修改。

`FIN-006` 使用与 `finops-cost-allocation` 标签策略相同的检查（见[用策略检查标签](check-tag-compliance.md)），但只查找缺少的键。值不被策略允许的键不算 `FIN-006` 的结果。标签键区分大小写：`owner` 不算作 `Owner`。只来自 Cost Explorer 的行（来源为 `billing`）不检查。

## 结果 {#results}

每项检查对每个资源给出三种结果之一：

- `fail`：检查观察到了表中所说的情况。该资源会列出。
- `not_evaluated`：缺少检查需要的数据。该资源会列出，并附上原因。
- `pass`：该资源只计数，不列出。

数据中的空缺从不算作 pass。原因有：

| 原因 | 含义 |
|---|---|
| `identity_only` | 该资源只通过 Resource Groups Tagging API 得知，所以检查读取的字段不在它的行上。 |
| `field_missing` | 检查读取的字段不在该行上。 |
| `tags_not_read` | 仅 `FIN-006`：缺少某个键，并且该区域的 Tagging API 列表在本次运行中失败。对于全局资源，该账户任何一次失败的 Tagging API 列表都算。 |
| `units_not_read` | 检查需要的某个列表在本次运行中失败。工作表中每个列表和区域各有一行。 |

## FinOps 工作表 {#the-finops-sheet}

工作表的第一行写着："These are observations from the inventory. A resource listed here may be intended."（这些是来自清单的观察结果；这里列出的资源可能是有意为之。）

然后是列出的结果，列为：`Check ID`、`Check`、`Result`、`Reason`、`Account`、`Region`、`Service`、`Resource Type`、`Resource ID`、`Name`、`Observed`。各行按检查 ID、账户、区域和资源 ID 排序。`Observed` 说明检查看到了什么，例如 "no attachment"、"started 2026-05-02"、"state stopped" 或 "missing: CostCenter, Owner"。API 应答中的其他内容都不会复制到工作表中。

列出的结果之后是一张表，每项检查一行，列出 `Fail`、`Not evaluated` 和 `Pass` 的计数。

以下示例由文档生成器根据模拟的 AWS 账户生成：

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `FinOps`

`FinOps` sheet:

> These are observations from the inventory. A ...  

| Check ID | Check | Result | Reason | Account | Region | Service | Resource Type | Resource ID | Name | Observed |
|---|---|---|---|---|---|---|---|---|---|---|
| FIN-001 | EBS volume with no attachment | fail |  | 123456789012 | us-east-1 | EC2 | Volume | vol-57d5df4cfc9884b48 | acme-build-cache | no attachment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | global | IAM | Role | acme-orders-api-role |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | VPC | NetworkAcl | acl-3118daa9d5cc099a7 |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | missing: Project |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-inventory-reports | acme-inventory-reports | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-new-bucket | acme-new-bucket | missing: CostCenter, Owner, Project, Environment |

使用 `--per-account-reports` 时，每个账户的报告只列出该账户的结果。

使用 `--template` 时，这些检查不运行：InvenTag 显示一条警告，不写 `FinOps` 工作表。

## `finops_checks` 结果 {#the-finops_checks-result}

命令行只以 `FinOps` 工作表的形式写出结果。在 Python 中，`CloudBOMGenerator.generate_multi_account_bom()` 在 `finops_checks` 键下返回结果，用 `json` 输出格式写出的 JSON 报告的 `metadata` 中也有同一个键。该键包含：

- `schema_version`：`1`。
- `summary`：每项检查一个条目，包括 `policy`（检查 ID）、`check`、`fail`、`not_evaluated` 和 `pass`。
- `findings`：列出的结果，包括 `policy`、`result`、`reason`、`account`、`region`、`service`、`resource_type`、`resource`、`name` 和 `message`（即 `Observed` 的文字）。

不使用该参数时没有这个键。

## 检查看不到的内容 {#what-the-checks-cannot-see}

- `FIN-004` 不给出时长。实例列表中没有可靠的停止时间，所以已停止的实例不论停止多久都会列出。
- `FIN-005` 不读取目标的健康状态。目标全部不健康的负载均衡器结果为 pass。读取目标健康状态需要新的 AWS 调用。
- 这里列出的资源可能是有意为之：例如故意停止的实例，或按保留规则保存的快照。
- 这些检查不显示任何金额。
- 未针对真实的 AWS 验证：在每种账户类型上，列表都带有每项检查需要的字段。
