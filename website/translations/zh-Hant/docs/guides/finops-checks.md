---
title: FinOps 檢查
description: 對掃描找到的資源執行六項固定的 FinOps 檢查，不再發出任何 AWS 呼叫；並可選擇從 Cost Explorer 讀取上個月按服務、關聯帳戶和成本分配標籤劃分的支出。
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

## 從 Cost Explorer 讀取成本分配 {#cost-allocation-from-cost-explorer}

`--finops-cost-allocation` 是第二個引數，預設關閉，與 `--finops-checks` 和 `--enable-cost-analysis` 相互獨立。它用每個帳戶自己的憑證，從 Cost Explorer 讀取該帳戶上個月的支出，並在 Excel 報告末尾新增一個名為 `FinOps costs` 的工作表。

```bash
inventag --create-excel --finops-cost-allocation
```

### 請求 {#requests}

對每個帳戶，按以下順序：

| 請求 | 數量 |
|---|---|
| 針對 `CostCenter`、`Owner`、`Project` 和 `Environment`（內建標籤策略 `finops-cost-allocation` 的鍵）的 `ListCostAllocationTags` | 1 |
| 按服務分組的 `GetCostAndUsage` | 1 |
| 按關聯帳戶分組的 `GetCostAndUsage` | 1 |
| 按這些鍵中每個已作為成本分配標籤啟用的鍵分組的 `GetCostAndUsage` | 0 到 4 |

即每個帳戶最多 7 個請求。`ListCostAllocationTags` 顯示為未啟用或未列出的鍵不會被查詢；它的表格顯示 "not active as a cost allocation tag" 或 "not found as a cost allocation tag"。如果 `ListCostAllocationTags` 本身失敗，四個鍵都會被查詢。

應答的後續頁面（`NextPageToken`）也是一個請求。它從同樣的 7 箇中扣除，每個分組最多 3 頁。需要更多頁面的表格標記為 "incomplete"。

在發現開始之前，執行會顯示一行警告，給出最多的請求數，例如：`Cost Explorer: up to 7 request(s) in this run (billing validation: 0; cost trend: 0; cost allocation: 7). AWS charges for each.` 唯讀防護的審計（`--audit-output`）統計到的該功能請求數從不超過這一行所說的數。

SDK 會重試被限流的請求，每次重試都是一個新請求。AWS 對每個 Cost Explorer 請求收費：見 [Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。未針對真實的 AWS 驗證：AWS 對這些請求（包括重試和 `ListCostAllocationTags`）如何收費。

### FinOps costs 工作表 {#the-finops-costs-sheet}

工作表以一條說明開頭：金額是 Cost Explorer 為每個帳戶返回的數值，用該帳戶自己的憑證讀取，屬於上一個完整的月份，並不是單個資源的成本。然後每個帳戶、分組和值各佔一列，列為 `Account`、`Grouping`、`Value`、`Amount`、`Currency`、`Metric`、`Period start`、`Period end` 和 `Status`。

- 時間段是執行開始所在月份的前一個自然月。`Period end` 是執行所在月份的第一天。
- 指標是 `UnblendedCost`。金額是 AWS 返回的文字；InvenTag 不對其求和、拆分或取整。
- 在按標籤的分組中，值 `(no value)` 表示沒有該標籤鍵的支出。
- 無法讀取的表格有一行顯示其狀態，例如 "not read: access denied"。執行說明中也會寫出它，被拒絕的請求會有一行 `Permissions:`。掃描結果和結束代碼與不使用該引數時相同。

使用 `--per-account-reports` 時，每個帳戶的報告只包含該帳戶的表格。使用 `--template` 時不發出任何請求：InvenTag 顯示一條警告，不寫 `FinOps costs` 工作表。

### `finops_costs` 鍵、快照和變更報告 {#the-finops_costs-key-the-snapshot-and-the-change-report}

- 在 Python 中，`CloudBOMGenerator.generate_multi_account_bom()` 的結果和 JSON 報告的 `metadata` 帶有 `finops_costs` 鍵：`schema_version`、`metric`，以及每個帳戶的時間段、請求數、每個標籤鍵的狀態和表格。
- 狀態快照帶有 `metadata.tags.cost_allocation`：只有表格（按服務、關聯帳戶和標籤值的合計；沒有資源 ID）。快照仍然只有所有者可讀（模式 0600）。`--no-cost-in-snapshot` 不把這些數字寫入快照；工作表照常寫出。不使用 `--finops-cost-allocation` 時，該引數不改變任何內容，並會顯示一條警告說明這一點。
- 從管理（付費）帳戶讀取時，按關聯帳戶的表格可能列出組織中的每個成員帳戶及其支出，包括本次執行沒有掃描的帳戶；按標籤的表格包含這些帳戶的標籤值（例如 `Owner` 的姓名或電子郵件地址），與 AWS 返回的一致。這些內容會寫入工作表、快照和變更報告。使用 `--no-cost-in-snapshot` 可以不把它們寫入快照。未針對真實的 AWS 驗證：付費帳戶的應答包含哪些內容。
- 當本次執行讀取了成本分配時，變更報告會有一個 "Cost, previous run to this run" 區塊。兩個快照的月份不同時，它把上一次執行和本次執行的每個值並排列出。否則用一行說明為什麼沒有比較：上一個快照沒有這些數字、兩次執行讀取的是同一個月，或者使用了 `--no-cost-in-snapshot`。

### 需要什麼，以及未驗證的內容 {#what-it-needs-and-what-is-not-verified}

該引數需要 `ce:GetCostAndUsage` 和 `ce:ListCostAllocationTags`。兩者都在儲存庫策略中（見 [IAM 權限](../reference/iam-permissions.md)）。

未針對真實的 AWS 驗證：

- 標籤鍵只有在付費（payer）帳戶中被啟用為成本分配標籤之後，才會顯示支出。
- 組織中的成員帳戶看到的可能比付費帳戶少，並且 `ListCostAllocationTags` 可能無法從成員帳戶應答。
- 應答的形式與測試使用的一致。測試使用的應答與 Cost Explorer 應答的形式相同，並已對照 botocore 服務模型檢查。

## 檢檢視不到的內容 {#what-the-checks-cannot-see}

- `FIN-004` 不給出時長。例項列表中沒有可靠的停止時間，所以已停止的例項不論停止多久都會列出。
- `FIN-005` 不讀取目標的健康狀態。目標全部不健康的負載均衡器結果為 pass。讀取目標健康狀態需要新的 AWS 呼叫。
- 這裡列出的資源可能是有意為之：例如故意停止的例項，或按保留規則儲存的快照。
- 這些檢查不顯示任何金額。
- 未針對真實的 AWS 驗證：在每種帳戶型別上，列表都帶有每項檢查需要的欄位。
