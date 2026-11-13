---
title: 功能狀態與已知限制
description: v1.0.2 中哪些 InvenTag 功能可用、哪些只是部分可用、哪些引數會報錯停止，以及在依賴它之前需要了解的具體限制、費用和風險。
sidebar_position: 5
---

# 功能狀態與已知限制

**適合誰閱讀：** 打算把 InvenTag 用於真實工作的人。

**讀完後你會了解：** 哪些功能可用、它們在哪裡止步、哪些引數會報錯停止，
以及每項限制該怎麼應對。

這一頁刻意寫得直白。本頁描述的是 InvenTag v1.0.2。我們逐項檢查過：
要麼對模擬的 AWS（moto）離線執行程式碼，要麼閱讀程式碼路徑。
**沒有任何測試在真實的 AWS 賬戶上執行過。** 凡是下面某一點取決於真實 AWS 的行為，
本頁都會明說。如果你修復或改動了其中一項，請在同一個拉取請求中更新本頁。

## 測試了什麼 {#what-is-tested}

每項功能都有針對模擬 AWS（moto）的離線測試。測試清單以及每個測試檢查什麼，
見[測試](../security/tests.md)頁面。

## 有限制的引數 {#flags-with-a-limit}

| 引數 | 實際會發生什麼 |
|---|---|
| `--service-descriptions` | 自定義描述對 InvenTag 沒有內建描述的服務有效。對於 S3、EC2、RDS、Lambda 和 VPC 資源，內建描述優先，除非你的條目同時指定了 `template`。參見[配置檔案](../reference/configuration-files.md#service-descriptions)。 |
| `--enable-cost-analysis` | 增加一個 Cost Analysis 工作表和四個 `forgotten_analysis.*` 列。它會額外發出許多 Cost Explorer、Pricing 和 CloudWatch 呼叫。參見[費用](#costs)。 |
| `--compliance-standard` | 以退出碼 2 停止。像 SOC 2 這樣的標準無法從資源清單中檢查，而一個只列印標籤的引數會誤導你。請使用標籤策略模板。 |
| `--create-google-docs`、`--create-google-sheets` | 只針對模擬的 Google 客戶端驗證過。參見 [Google Sheets 和 Docs](../guides/google-sheets-and-docs.md#what-is-not-verified)。 |
| `--enable-production-safety`、`--security-validation`、`--enforce-read-only` | 保留下來，讓舊命令仍能執行。只讀防護始終開啟。 |
| `--disable-production-safety` | 以退出碼 2 停止。防護無法關閉。 |

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)

$ inventag --risk-threshold HIGH
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## InvenTag 能找到什麼，不能找到什麼 {#what-inventag-finds-and-what-it-does-not}

- **有自己發現程式碼的服務（24 種）：** VPC（VPC、子網、安全組、網際網路閘道器和 NAT 閘道器、
  路由表、網路 ACL、彈性 IP 地址）、EC2（例項、卷、快照、金鑰對）、S3、RDS、Lambda、
  ELB、ELBv2、IAM、CloudFront、Route 53、KMS、CloudWatch、ECS、EKS、SNS、SQS、
  DynamoDB、API Gateway、Glue、WorkMail、CloudFormation、ACM、CloudTrail 和 EventBridge。
- **其他一切**只有在 Resource Groups Tagging API 返回時才會出現。該 API 列出的是
  現有標籤或曾經有過標籤的資源，因此其他服務中沒有標籤的資源會缺失。
  在 `--fallback-display auto`（預設值）下，這類資源只會針對自己的發現程式碼沒有結果的服務顯示。
  使用 `--fallback-display always` 可顯示全部。
- **不會收集：** 金鑰、引數、物件內容或任何其他資料。只讀防護會攔截這些呼叫。
- **全域性服務**（IAM、S3 儲存桶列表、CloudFront、Route 53，以及 CloudFront 使用的 ACM 證書）
  無論你選擇哪些區域，都會針對每個賬戶從 `us-east-1` 讀取一次。它們的區域列顯示 `global`；
  S3 儲存桶則保留它自己的區域。參見[執行掃描](../guides/run-a-scan.md)。
- **區域。** 不指定 `--account-regions` 時，InvenTag 會向 EC2 詢問賬戶中啟用的區域。
  如果該呼叫失敗，它會記錄一條警告，並且只掃描 `us-east-1`、`us-west-2`、`eu-west-1`
  和 `ap-southeast-1`。訪問檢查失敗的區域會被跳過並給出警告，執行仍然成功。

## 執行出錯時 {#when-a-run-goes-wrong}

- **一個賬戶失敗，其他賬戶正常：** 執行以退出碼 0 結束。執行摘要和報告會列出每個失敗的賬戶及原因。
  如果所有賬戶都失敗，執行以退出碼 1 結束。
- **沒有找到資源，或過濾器把它們全部去掉了：** InvenTag 不會寫出報告，記錄一條警告，
  並以退出碼 0 結束。請在指令碼中檢查檔案是否存在。
- **你缺少某個服務的許可權：** InvenTag 跳過該呼叫，為該服務記錄一條帶原因的警告，然後繼續。
  如果 Resource Groups Tagging API 返回了該服務的資源，它們仍可能出現。
- **Cost Explorer 訪問被拒絕：** 執行在沒有計費資料的情況下繼續，並記錄一條警告。
- **被只讀防護攔截的呼叫**會引發一個指明具體操作的錯誤。命令列本身不會發出這類呼叫。
- **S3 上傳失敗**會讓整個執行以退出碼 1 結束，此時報告已經寫入本地。
- **某種報告格式生成失敗**會讓執行以退出碼 1 結束。

## 費用 {#costs}

預設情況下，發現過程會呼叫 Cost Explorer 的 `GetCostAndUsage` API。
在我們的離線測試中，它為每個賬戶發出兩次請求。AWS 對每次 Cost Explorer 請求收費。
請參閱最新的
[Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。

- `--no-billing-validation` 會停止這些呼叫。此時報告裡沒有可供對比的計費資料。
- `--enable-cost-analysis` 即使加上 `--no-billing-validation` 也會發出更多 Cost Explorer 呼叫
  （在我們的離線測試中多出八次），此外還有 Pricing 和 CloudWatch 呼叫。

其他呼叫是免費的，但大型賬戶意味著請求很多，並可能遇到限流（AWS 放慢你的請求）。

## 效能與限制 {#performance-and-limits}

- InvenTag 沒有針對真實賬戶的基準資料。掃描大型賬戶的所有區域很慢：
  每個服務在每個區域各有一組呼叫。
- 預設同時掃描四個賬戶。每個賬戶有 1800 秒（30 分鐘）。執行不會續跑；如果中途停止，請重新開始。
- Excel 工作表名稱會被截斷為 31 個字元。Word 表格預設每個服務最多顯示 50 條資源（`max_rows`）。
- 執行儲存快照時，InvenTag 會刪除 `bom_output/state/` 中超過 30 天或超出最新 100 個的快照。
  如果需要更長的歷史，請自行保留副本。

## 安全說明 {#security-notes}

- **無論如何都要使用只讀 IAM 身份。** 防護會攔截寫入呼叫，而你的 IAM（身份與訪問管理）策略是第二道獨立的保險。
  參見[設定只讀訪問](../guides/read-only-access.md)。
- **除錯日誌預設經過脫敏：** 會話令牌、金鑰和簽名會被遮蔽。但仍應把除錯日誌視為敏感資訊。
- **有兩個庫函式在你自己的 Python 程式碼中呼叫時會寫入 AWS**（命令列不會呼叫它們）：
  `CredentialManager.setup_cross_account_roles()` 會建立 IAM 角色，
  S3 輔助工具可以修改儲存桶的生命週期規則（預設關閉，並且會與現有規則合併）。

## 測試與軟體物料清單 {#tests-and-the-software-bill-of-materials}

測試套件和依賴清單有各自的頁面：
[測試](../security/tests.md)和
[軟體物料清單](../security/sbom.md)。
