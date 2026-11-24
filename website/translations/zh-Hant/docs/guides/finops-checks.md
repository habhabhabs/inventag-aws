---
title: FinOps 檢查
description: 對掃描找到的資源執行六項固定的 FinOps 檢查（未掛載的卷、未關聯的地址、舊快照、已停止的例項、沒有目標的負載均衡器、缺少的成本分配標籤），不再發出任何 AWS 呼叫。
sidebar_position: 10
---

# FinOps 檢查

**適合誰讀：** 你負責雲支出，想根據已有的清單得到一份值得檢視的資源列表。

**讀完後你能做到：** 執行六項 FinOps 檢查，讀懂 `FinOps` 工作表，並知道這些檢檢視不到什麼。

## 執行檢查 {#run-the-checks}

```bash
inventag --create-excel --finops-checks
```

該引數預設關閉。使用它時，InvenTag 對掃描找到的資源執行六項固定檢查，並在 Excel 報告末尾新增一個名為 `FinOps` 的工作表。

- 這些檢查唯讀取掃描已有的行。它們不再發出任何 AWS 呼叫，也不需要額外的權限。無論是否使用該引數，唯讀防護看到的呼叫都相同。
- 這些檢查不會更改任何帳戶中的任何內容。
- 檢查結果不改變結束代碼：有 `fail` 結果的執行與沒有這些結果時以相同方式結束。
- 不使用該引數時，這些檢查不執行：報告中沒有 `FinOps` 工作表，其他工作表和控制檯文字與使用該引數時相同。

## 六項檢查 {#the-six-checks}

| 檢查 ID | 資源 | 結果為 `fail` 的條件 |
|---|---|---|
| `FIN-001` | EBS 卷 | 卷的 `State` 為 `available`（未掛載） |
| `FIN-002` | 彈性 IP 地址 | 地址沒有 `AssociationId` |
| `FIN-003` | 被掃描帳戶擁有的 EBS 快照 | 快照的 `StartTime` 早於執行開始時間 90 天以上 |
| `FIN-004` | EC2 例項 | 例項狀態為 `stopped` |
| `FIN-005` | 負載均衡器 | 同一帳戶和區域中沒有任何目標組指向它（`ELBV2` 工作表），或它沒有列出任何例項（經典負載均衡器，`ELB` 工作表） |
| `FIN-006` | 內建標籤策略 `finops-cost-allocation` 範圍內的每個資源 | 缺少該策略的某個鍵：`CostCenter`、`Owner`、`Project` 或 `Environment` |

`FIN-003` 的 90 天是固定的，沒有引數可以修改。

`FIN-006` 使用與 `finops-cost-allocation` 標籤策略相同的檢查（見[用策略檢查標籤](check-tag-compliance.md)），但只查詢缺少的鍵。值不被策略允許的鍵不算 `FIN-006` 的結果。標籤鍵區分大小寫：`owner` 不算作 `Owner`。只來自 Cost Explorer 的行（來源為 `billing`）不檢查。

## 結果 {#results}

每項檢查對每個資源給出三種結果之一：

- `fail`：檢查觀察到了表中所說的情況。該資源會列出。
- `not_evaluated`：缺少檢查需要的資料。該資源會列出，並附上原因。
- `pass`：該資源只計數，不列出。

資料中的空缺從不算作 pass。原因有：

| 原因 | 含義 |
|---|---|
| `identity_only` | 該資源只透過 Resource Groups Tagging API 得知，所以檢查讀取的欄位不在它的行上。 |
| `field_missing` | 檢查讀取的欄位不在該行上。對於 `FIN-003`，執行沒有開始時間時也是如此。 |
| `tags_not_read` | 僅 `FIN-006`：缺少某個鍵，並且該區域的 Tagging API 列表在本次執行中失敗。對於全域性資源，該帳戶任何一次失敗的 Tagging API 列表都算。 |
| `listing_not_read` | 檢查需要的某個列表在本次執行中失敗。需要該列表的每項檢查各為該列表及其區域寫一行：一個失敗的 `ec2` 列表會產生四行（`FIN-001`、`FIN-003`、`FIN-004`、`FIN-006`）。 |

## FinOps 工作表 {#the-finops-sheet}

工作表的第一行寫著："These are observations from the inventory. A resource listed here may be intended."（這些是來自清單的觀察結果；這裡列出的資源可能是有意為之。）

然後是列出的結果，列為：`Check ID`、`Check`、`Result`、`Reason`、`Account`、`Region`、`Service`、`Resource Type`、`Resource ID`、`Name`、`Observed`。各行按檢查 ID、帳戶、區域和資源 ID 排序。`Observed` 說明檢檢視到了什麼，例如 "no attachment"、"started 2026-05-02"、"state stopped" 或 "missing: CostCenter, Owner"。API 應答中的其他內容都不會複製到工作表中。

列出的結果之後是一張表，每項檢查一行，列出 `Fail`、`Not evaluated` 和 `Pass` 的計數。

以下範例由文件生成器根據模擬的 AWS 帳戶生成：

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

使用 `--per-account-reports` 時，每個帳戶的報告只列出該帳戶的結果。

使用 `--template` 時，這些檢查不執行：InvenTag 顯示一條警告，不寫 `FinOps` 工作表。

## `finops_checks` 結果 {#the-finops_checks-result}

命令列只以 `FinOps` 工作表的形式寫出結果。在 Python 中，`CloudBOMGenerator.generate_multi_account_bom()` 在 `finops_checks` 鍵下返回結果，用 `json` 輸出格式寫出的 JSON 報告的 `metadata` 中也有同一個鍵。該鍵包含：

- `schema_version`：`1`。
- `summary`：每項檢查一個條目，包括 `policy`（檢查 ID）、`check`、`fail`、`not_evaluated` 和 `pass`。
- `findings`：列出的結果，包括 `policy`、`result`、`reason`、`account`、`region`、`service`、`resource_type`、`resource`、`name` 和 `message`（即 `Observed` 的文字）。

不使用該引數時沒有這個鍵。

## 檢檢視不到的內容 {#what-the-checks-cannot-see}

- `FIN-004` 不給出時長。例項列表中沒有可靠的停止時間，所以已停止的例項不論停止多久都會列出。
- `FIN-005` 不讀取目標的健康狀態。目標全部不健康的負載均衡器結果為 pass。讀取目標健康狀態需要新的 AWS 呼叫。
- 這裡列出的資源可能是有意為之：例如故意停止的例項，或按保留規則儲存的快照。
- 這些檢查不顯示任何金額。
- 未針對真實的 AWS 驗證：在每種帳戶型別上，列表都帶有每項檢查需要的欄位。
