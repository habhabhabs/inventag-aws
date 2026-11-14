---
title: 功能狀態與已知限制
sidebar_label: 功能狀態
description: 目前發行版中哪些 InvenTag 功能可用、哪些只是部分可用、哪些引數會報錯停止，以及在依賴它之前需要了解的具體限制、費用和風險。
sidebar_position: 5
---

# 功能狀態與已知限制

**適合誰閱讀：** 打算把 InvenTag 用於真實工作的人。

**讀完後你會了解：** 哪些功能可用、它們在哪裡止步、哪些引數會報錯停止，
以及每項限制該怎麼應對。

這一頁刻意寫得直白。本頁描述的是目前發行版；[更新日誌](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md)列出了每個發行版的變化。下面每一項都有離線測試或針對模擬 AWS（moto）的執行作為證明。**沒有任何測試在真實的 AWS 帳戶上執行過。** 凡是某一項取決於真實 AWS 的行為，本頁都會明說。如果你修復或改動了其中一項，請在同一個提取要求中更新本頁。

## 測試了什麼 {#what-is-tested}

[測試](../security/tests.md)頁面列出了針對模擬 AWS（moto）的離線測試，以及每個測試檢查什麼。本文件中沒有任何測試證明的陳述，會帶有一條以「未針對」開頭的說明。

## 有限制的引數 {#flags-with-a-limit}

| 引數 | 實際會發生什麼 |
|---|---|
| `--enable-cost-analysis` | 增加一個 Cost Analysis 工作表和四個 `forgotten_analysis.*` 欄，其中的估算值來自 AWS Pricing API，不是你的帳單，並且會額外發出 Cost Explorer、Pricing 和 CloudWatch 呼叫（參見[費用](#costs)）。 |
| `--compliance-standard` | 以結束代碼 2 停止，因為像 SOC 2 這樣的標準無法從資源清單中檢查；請改用標籤策略範本。 |
| `--create-google-docs`、`--create-google-sheets` | 只針對模擬的 Google 客戶端驗證過。參見 [Google Sheets 和 Docs](../guides/google-sheets-and-docs.md#what-is-not-verified)。 |
| `--enable-production-safety`、`--security-validation`、`--enforce-read-only` | 保留下來，讓舊命令仍能執行。唯讀防護始終開啟。 |
| `--disable-production-safety` | 以結束代碼 2 停止，因為唯讀防護無法關閉。 |

```bash title="Terminal"
inventag --create-google-docs
```

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)
```

```bash title="Terminal"
inventag --risk-threshold HIGH
```

```text title="輸出"
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)
```

```bash title="Terminal"
inventag --compliance-standard soc2
```

```text title="輸出"
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="輸出"
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## InvenTag 能找到什麼，不能找到什麼 {#what-inventag-finds-and-what-it-does-not}

- **有自己發現程式碼的服務（46 個）：** VPC（VPC、子網、安全組、網際網路閘道器和 NAT 閘道器、路由表、網路 ACL、
  彈性 IP 地址）、EC2（例項、卷、快照、金鑰對）、S3、RDS、Lambda、ELB、ELBv2、IAM、CloudFront、
  Route 53、KMS、CloudWatch、ECS（叢集，以及每個叢集中的服務）、EKS、SNS、SQS、DynamoDB、
  API Gateway、Glue、WorkMail、CloudFormation、ACM、CloudTrail、EventBridge、ElastiCache、
  Redshift、Redshift Serverless、OpenSearch、EFS、ECR、Step Functions、Kinesis、Firehose、
  Secrets Manager（僅名稱）、Systems Manager 引數（僅名稱）、Auto Scaling 組、Backup 保管庫、
  Cognito 使用者池、CodeBuild、CodePipeline、Athena 工作組、EMR、MSK、AppSync、Elastic Beanstalk
  和 WAF Web ACL。
- **其他所有服務**只有在 Resource Groups Tagging API 返回時才會出現，因此其他服務中沒有標籤的資源會缺失。使用 `--fallback-display auto`（預設值）時，這類資源只在其自身發現程式碼沒有結果的服務中顯示；`--fallback-display always` 會顯示全部。
- **不收集：** 機密值、引數值、物件內容或任何其他資料，因為唯讀防護會阻止返回這些內容的呼叫。
- **允許的回應中的機密值會被遮蓋。** 有些讀取呼叫會在設定旁邊返回機密。常用於存放機密的欄位，其值在報告、
  JSON 輸出、狀態快照、續掃檢查點和日誌中會被替換為 `***REDACTED***`：Lambda 和 App Runner 環境變數、
  ECS 和 CodeBuild 環境值、EC2 使用者資料、CloudFormation 引數值、堆疊輸出值和堆疊集範本正文、
  Glue 作業、觸發器和作業執行引數以及連線屬性、EMR on EKS 作業引數、WorkSpaces Thin Client 啟用碼、
  DMS 證書錢包、連線字串、簽名 URL、下載和上傳 URL、Splunk HEC、Grafana 和加入權杖，
  以及任何名稱類似 password、secret、token、access token 或 refresh token、private key 或 credentials 的欄位，
  在 JSON 文字中也是如此。名稱會保留。
- **其他欄位中的機密不會被發現：** 描述、標籤、其他自由文字欄位或 AWS 以後新增的欄位中的機密，會按原樣複製到報告中，因為遮蓋是按欄位名稱進行的。
- **標籤按原樣顯示**，即使標籤鍵看起來像機密，例如 `password`。
- **v1.2.0 之前的版本寫出的報告和快照可能包含機密值**，因此請刪除舊的 `bom_output/` 資料夾和共享副本，或限制其存取。
- **全域性服務**（IAM、S3 儲存貯體列表、CloudFront、Route 53、用於 CloudFront 的 WAF Web ACL，以及
  CloudFront 使用的 ACM 證書）每個帳戶只從 `us-east-1`（中國為 `cn-north-1`，GovCloud 為
  `us-gov-west-1`）讀取一次，無論你選擇哪些區域。它們的區域欄顯示 `global`；S3 儲存貯體保留自己的區域。
  參見[執行掃描](../guides/run-a-scan.md)。
- **區域。** 沒有 `--account-regions` 時，InvenTag 向 EC2 查詢帳戶中已啟用的區域。如果
  `ec2:DescribeRegions` 失敗，它會查詢 `account:ListRegions`；如果這也失敗，它會嘗試該分割槽的每個區域，
  並跳過未透過存取檢查的區域。未透過存取檢查的區域會被跳過並記錄警告，執行仍然成功。

## 執行出錯時 {#when-a-run-goes-wrong}

- **一個帳戶失敗，其他帳戶正常：** 執行以結束代碼 0 結束；傳入 `--fail-on-account-error` 時以結束代碼 5 結束。
- **用 `--template` 生成的報告**不會列出失敗的帳戶；執行摘要和預設報告會列出。
- **所有帳戶都失敗：** 執行以結束代碼 1 結束，使用 `--fail-on-account-error` 時也是如此；除非這些帳戶是因超時而失敗，否則不寫報告，超時時報告會列出已找到的資源。
- **帳戶超時：** 它算作失敗，超時前找到的資源保留在報告中。
- **沒有找到資源，或篩選條件把它們全部去掉了：** 不使用 `--template` 時 InvenTag 不寫報告，使用 `--template` 時寫出一份空報告；除非你傳入 `--fail-if-empty`（結束代碼 6），否則執行以結束代碼 0 結束。
- **範圍內沒有任何資源的標籤策略**會報告 `0 of 0 resources compliant (100.0%)`，儘管什麼都沒有檢查。
- **你沒有權限的服務**會被跳過並記錄一條警告；只有 Resource Groups Tagging API 返回時，它的資源才會出現。
- **因其他原因失敗的列出呼叫**（重試後仍被限流，或出現錯誤）會記為一條警告，並計入快照（`metadata.tags.coverage_summary`），沒有任何報告會提到它。
- **帳戶中的所有呼叫都被拒絕：** 該帳戶不算失敗，執行以結束代碼 0 結束，下一份變更報告會把該帳戶的所有資源列為已刪除。
- **某個服務的列出呼叫被限流或失敗**，在下一份變更報告中，該服務的資源會顯示為已刪除。
- **與上一次執行相比，區域或服務不同的執行**，會在變更報告中把新範圍之外的資源顯示為已刪除。
- **從 v1.1.4 升級後的第一份變更報告**會把新覆蓋服務的資源列為新增，儘管它們之前就存在。
- **掃描過程中會話過期**時，報告只包含會話過期前讀取到的內容，沒有任何說明，執行以結束代碼 0 結束，使用 `--fail-on-account-error` 時也是如此。
- **掃描開始時會話已經過期**時，不會生成報告檔案，結束代碼為 0。
- **使用 `--resume` 時**，第一次執行中會話中途過期的帳戶，可能會被當作已完整掃描而複用。
- **IAM Identity Center（SSO）權杖過期**時，執行會以結束代碼 1 和 Python 回溯停止，並且訊息不會告訴你執行 `aws sso login`。
- **Cost Explorer 存取被拒絕：** 執行在沒有帳單資料的情況下繼續，關於它的兩條警告只在使用 `--debug` 時顯示。
- **被唯讀防護阻止的呼叫**如果發生在列出呼叫中，該列出會被跳過並輸出一行錯誤，執行仍以結束代碼 0 結束。
- **S3 上傳失敗**會讓整個執行以結束代碼 1 結束，此時報告已寫到本地。
- **某個報告格式寫入失敗**會讓執行以結束代碼 1 結束，並且不會向 S3 上傳任何檔案，已寫出的格式也不會上傳。
- **無法儲存的快照**只會輸出一行錯誤，執行仍以結束代碼 0 結束。
- **與 `--template` 一起使用的 Google 輸出**會被跳過，執行以結束代碼 0 結束。
- **有些無效值以結束代碼 1 而不是 2 停止，** 例如 `--max-concurrent-accounts 0` 或
  `--account-processing-timeout 0`。
- **帳戶檔案 `settings` 塊中的值會覆蓋對應的命令列引數，** 例如 `max_concurrent_accounts`。
- **使用 `--s3-bucket` 時結果為空**會讓執行以結束代碼 1 結束（`S3 upload of reports failed: no files`），使用 `--fail-if-empty` 時也是如此。
- **`--account-regions` 中輸入錯誤的區域名稱**會讓執行以結束代碼 0 結束，輸出原始的 `KeyError` 文字，並且不寫報告。
- **需要 MFA 的設定檔在沒有終端的情況下執行**時，會以 Python 回溯和空訊息停止，或者在輸入保持開啟時一直等待。
- **無法寫入的 `--audit-output` 或 `--log-file` 路徑**會讓執行以 Python 回溯結束，而無法使用的輸出資料夾要到整個掃描結束後才會發現。
- **Ctrl-C** 會讓執行停止且沒有可見訊息，SIGTERM 會讓它停止且沒有任何訊息。
- **帳戶檔案中帳戶 ID 相同的第二個條目**會被丟棄且沒有任何訊息，因此它的區域不會被掃描。
- **兩個同時使用同一輸出資料夾的執行**不會被阻止。

## 費用 {#costs}

預設情況下，發現過程會呼叫 Cost Explorer 的 `GetCostAndUsage` API。
在我們的離線測試中，它為每個帳戶發出兩次請求。AWS 對每次 Cost Explorer 請求收費：
請參閱最新的
[Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。

- `--no-billing-validation` 會停止這些呼叫，此時報告裡沒有可供對比的計費資料。
- `--enable-cost-analysis` 會發出更多 Cost Explorer、Pricing 和 CloudWatch 呼叫，即使加上 `--no-billing-validation` 也是如此，呼叫次數取決於你的資源。每個不同的價格查詢只發出一次，之後重複使用，因此 Pricing 呼叫次數隨不同資源型別和規格的數量增長，而不是隨資源數量增長。

未針對真實的 AWS 驗證：`--enable-cost-analysis` 的成本估算。

InvenTag 會把被限流的呼叫最多重試 10 次（standard 重試模式）；`AWS_RETRY_MODE` 和 `AWS_MAX_ATTEMPTS` 可以覆蓋這一設定。

## 效能與限制 {#performance-and-limits}

- InvenTag 沒有針對真實帳戶的基準資料，掃描會為每個服務在每個區域發出一組呼叫。
- 針對 moto（在程序內執行，因此沒有網路時間），`scripts/benchmark_scan.py --scale 60` 在一個區域中掃描了 10,948 個資源，發出了 2,053 次 API 呼叫：1,200 次 `s3:GetBucketLocation` 呼叫（每個儲存貯體一次）、600 次 `lambda:GetFunctionConfiguration` 呼叫（每個函式一次）、150 次 Resource Groups Tagging API 呼叫，以及 103 次其他呼叫。對真實帳戶有用的是呼叫次數。
- 預設同時掃描四個帳戶（`--max-concurrent-accounts`）。每個帳戶從開始掃描起有 1800 秒
  （`--account-processing-timeout`）。
- 當有些帳戶失敗時，已完成帳戶的結果會被儲存。在 24 小時內（`--resume-max-age-hours`）用 `--resume`
  執行同一條命令，只掃描其他帳戶。
- Excel 工作表名稱會被截斷為 31 個字元，Excel 不允許的字元會變成 `-`，重複的名稱會加上 ` (2)`，日誌會列出每個被改名的工作表。
- Word 表格預設每個服務最多顯示 50 個資源（`max_rows`）。
- 當執行儲存快照時，InvenTag 會刪除 `bom_output/state/` 中超過 30 天或超出最新 100 個的快照。
  剛寫入的快照和與之比較的快照永遠不會被刪除。用 `--state-retention-days` 和 `--state-max-snapshots`
  修改這些限制，或用 `none` 保留全部。
- 使用 `--enable-network-analysis` 或 `--enable-security-analysis` 時，分析呼叫在一次執行中會發出兩次。
- 網路分析把位於多個子網中的資源只計入第一個子網，並且只把負載均衡器計入其 VPC，而不計入任何子網。
- 服務屬性補充（BOM 設定中的 `enable_service_enrichment`）不會執行；報告包含發現過程返回的欄位。
- 在範本報告中，如果 AWS 沒有為資源返回 `Name` 欄位或 `Name` 標籤，Name 列為空；ID 欄用於識別該資源。
  對於 Lambda 函式、IAM 角色和 KMS 別名，範本報告會把 ID 顯示為名稱。

## 安全說明 {#security-notes}

- **仍然使用唯讀 IAM 身份。** 防護會阻止寫入呼叫，而你的 IAM（身份和存取管理）策略是第二道獨立的安全網。
  參見[設定唯讀存取](../guides/read-only-access.md)。
- **除錯日誌預設經過脫敏：** 會話權杖、金鑰、簽名以及上面列出的機密值都會被遮蓋。仍請把除錯日誌當作敏感資訊。
- **兩個庫函式可以寫入 AWS**，前提是從你自己的 Python 程式碼中呼叫（CLI 不會呼叫它們）：
  `CredentialManager.setup_cross_account_roles()` 只在 `allow_iam_writes=True` 時執行，S3 生命週期輔助函式
  只在 `allow_bucket_writes=True` 時執行。在 CLI 執行中，唯讀防護會阻止這兩者。
- **從你自己的 Python 程式碼中使用 `CloudBOMGenerator`** 不會安裝唯讀防護。只有 `inventag` 命令會安裝。
- **設定範本可以設定輸出資料夾以及要掃描的帳戶和角色。** 只使用你信任的範本。
- **擔任角色的會話不會重新整理**，因此持續時間超過會話的帳戶掃描會遇到權杖過期。

  未針對真實的 AWS 驗證：擔任角色的會話持續一小時。
- **MFA 只能透過 AWS 設定檔（`mfa_serial`）使用**，不支援帳戶檔案中的 `role_arn` 條目。

  未針對真實的 MFA 裝置驗證：透過帶 `mfa_serial` 的 AWS 設定檔使用 MFA。

## 測試與軟體物料清單 {#tests-and-the-software-bill-of-materials}

測試套件和依賴清單有各自的頁面：
[測試](../security/tests.md)和
[軟體物料清單](../security/sbom.md)。
