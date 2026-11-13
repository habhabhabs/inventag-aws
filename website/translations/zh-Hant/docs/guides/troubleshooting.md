---
title: 解決常見問題
description: 人們最常遇到的 InvenTag 錯誤（憑證、權限、區域、限流、範本和設定檔），附真實訊息和解決辦法。
sidebar_position: 8
---

# 解決常見問題

**適合誰閱讀：** 出了問題，你想要最快的解決辦法。

**讀完後你可以：** 認出你看到的訊息，並修復其原因。

下面的訊息是 InvenTag 離線執行的真實輸出（範例資料）。
對於離線無法產生的 AWS 錯誤，例如權杖過期，我們模擬了確切的 AWS 錯誤回應，並記錄了 InvenTag 如何報告它。
這些程式碼塊標註為“simulated AWS error response”。

加上 `--verbose` 可以看到每一步，加上 `--debug` 可以看到每個 AWS 呼叫。除錯日誌會遮蔽金鑰，但仍應把它當作敏感資訊對待。

## 憑證 {#credentials}

### 找不到憑證 {#no-credentials-found}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ No AWS credentials found!
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Set AWS environment variables:
inventag.cli.main - ERROR -       export AWS_ACCESS_KEY_ID=your-key
inventag.cli.main - ERROR -       export AWS_SECRET_ACCESS_KEY=your-secret
inventag.cli.main - ERROR -    3. Use IAM roles if running on EC2/ECS/Lambda
inventag.cli.main - ERROR -    4. Use --accounts-prompt for interactive setup
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**解決辦法：** 登入，例如執行 `aws sso login --profile my-readonly` 和
`export AWS_PROFILE=my-readonly`，然後用 `aws sts get-caller-identity` 檢查。

### 憑證已過期或無效 {#expired-or-invalid-credentials}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.cli.main - ERROR - ❌ AWS credential validation failed!
inventag.cli.main - ERROR -    Issue: Invalid or expired security token
inventag.cli.main - ERROR -    Solutions:
inventag.cli.main - ERROR -    1. Run 'aws configure' to set up credentials
inventag.cli.main - ERROR -    2. Check if your access keys are correct
inventag.cli.main - ERROR -    3. If using temporary credentials, they may have expired
inventag.cli.main - ERROR -    4. If using AWS SSO, run 'aws sso login'
inventag.cli.main - ERROR -
inventag.cli.main - ERROR - 💡 Quick diagnostic commands:
inventag.cli.main - ERROR -    aws configure list          # Show current config
inventag.cli.main - ERROR -    aws sts get-caller-identity # Test credentials
inventag.cli.main - ERROR -    aws configure               # Set up new credentials
inventag - ERROR - ❌ Cannot proceed with invalid AWS credentials
inventag - ERROR - 💡 Use --accounts-prompt for interactive credential setup
inventag - ERROR - 💡 Or use --skip-credential-validation to bypass this check
$ echo $?
1
```

**解決辦法：** 重新登入（`aws sso login --profile <name>`），或重新整理你的臨時金鑰。
如果你使用存取金鑰，請用 `aws configure list` 檢查它們。

### 無法 assume 角色 {#a-role-cannot-be-assumed}

**你會看到：** 日誌中出現如下內容，並且報告中缺少該帳戶：

```text
inventag.core.cloud_bom_generator.CloudBOMGenerator - ERROR - Failed to establish context for account 999999999999: Role assumption failed for account 999999999999: An error occurred (AccessDenied) when calling the AssumeRole operation: ...
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Skipping account 999999999999 due to invalid session
```

如果其他帳戶正常，InvenTag 仍會寫出它們的報告，並以**結束代碼 0** 結束。
如果每個帳戶都失敗，則以結束代碼 1 結束。（訊息文字來自帶有模擬 AWS 錯誤的離線執行。）

**解決辦法：** 檢查角色 ARN，並檢查該角色的信任策略是否允許你的身份。
InvenTag 不會回退到其他憑證，因此在問題解決之前，該帳戶會被跳過。

### 給了角色名稱但沒有帳戶檔案 {#a-role-name-without-an-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag.cli.main - ERROR - --cross-account-role was given a role name without --accounts-file. Pass a full role ARN (arn:aws:iam::<account-id>:role/<name>), or list the target account IDs in --accounts-file.
$ echo $?
2
```

**解決辦法：** 傳入完整的角色 ARN，或加上帶有帳戶 ID 的 `--accounts-file`。

## 權限 {#permissions}

### Cost Explorer 存取被拒絕 {#cost-explorer-access-denied}

InvenTag 會在沒有帳單資料的情況下繼續，執行也會成功，所以這個問題很容易被忽略。它只會在使用 `--debug` 時顯示：

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0

$ # the same run with --debug, lines that mention AccessDeniedException
Cost Explorer data is not available, so billing checks are skipped: An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage
```

**解決辦法：** 把 `ce:GetCostAndUsage` 新增到策略中，或者接受缺少帳單資料。

### 某個服務或某一列為空 {#a-service-or-column-is-empty}

**原因：** 該身份缺少該服務的某個 `List*`、`Describe*` 或 `Get*` 權限。
發現過程會在沒有它的情況下繼續，並且不列印任何訊息。AWS 錯誤只在除錯級別記錄，在很長的輸出中很難找到。
請用同一個身份執行對應的 AWS CLI 呼叫來檢查。

**解決辦法：** 使用 `config/defaults/iam-policy-read-only.json` 中的策略，它涵蓋了 InvenTag 發出的每個呼叫。
見 [IAM 權限](../reference/iam-permissions.md)。

### 被唯讀防護阻止 {#blocked-by-the-read-only-guard}

**你會看到：** 日誌中有 `Read-only guard blocked <service>:<Operation>`，
以及以 `Blocked AWS operation <service>:<Operation>` 開頭的錯誤。

**原因：** 一個不是讀取的呼叫到達了防護。InvenTag 自己不會發出這樣的呼叫，因此這通常意味著自定義程式碼或外掛。

**解決辦法：** 用 `inventag --validate-operations <service>:<Operation>` 檢查是哪個操作。防護無法關閉。

## 區域 {#regions}

### 區域未對該帳戶啟用 {#a-region-is-not-enabled-for-the-account}

```text title="Terminal (simulated AWS error response)"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag.core.cloud_bom_generator.CloudBOMGenerator - WARNING - Region ap-east-1 test failed: An error occurred (AuthFailure) when calling the DescribeRegions operation: AWS was not able to validate the provided access credentials
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
$ echo $?
0
```

執行會使用可用的區域繼續。

**解決辦法：** 從 `--account-regions` 中刪除該區域，或在 AWS 控制檯中為該帳戶啟用它（Account settings，AWS Regions）。

## 限流 {#throttling}

當同時到達的請求太多時，AWS 會放慢它們。AWS SDK（軟體開發工具包）會自動重試。
對於重試之後仍然持續的限流，InvenTag 會如何報告，我們還沒有測試過。

**解決辦法：** 減少同時掃描的帳戶數（`--max-concurrent-accounts 2`），掃描更少的區域，
或給大型帳戶更多時間（`--account-processing-timeout 3600`）。

## 範本和設定檔 {#templates-and-configuration-files}

### 無效的範本 {#invalid-template}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   bad.yaml:5: spec.colors.header_fill: must be a six-digit hex colour such as 1F3A5F (got 'blue')
$ echo $?
1
```

**解決辦法：** 更正所示行上的欄位。執行 `inventag templates validate <file>` 可以在不掃描的情況下檢查。

### 未知的範本名稱 {#unknown-template-name}

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   no template named 'acme-bomm'. Run 'inventag templates list' to see what is available (searched: ~/acme-infra/.inventag/templates, ~/.config/inventag/templates, ~/inventag-aws/inventag/templating/builtin)
$ echo $?
1
```

**解決辦法：** 用 `inventag templates list` 檢查拼寫。專案範本必須位於你執行命令的資料夾下的 `.inventag/templates/` 中。

### 無效的帳戶檔案 {#invalid-accounts-file}

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

**解決辦法：** 給帳戶 ID 加上引號（`account_id: "123456789012"`），並給每個帳戶提供 `profile_name`、`role_arn` 或存取金鑰。

### 其他範本訊息 {#other-template-messages}

| 訊息包含 | 解決辦法 |
|---|---|
| `did you mean '...'?` | 更正所示行上的拼寫。 |
| `Put account IDs in quotes` | 寫成 `account_id: "012345678901"`。 |
| `must stay inside the template's folder` | 把被引用的檔案移到範本旁邊，或移到子資料夾中。 |
| `templates must not contain credentials` | 刪除存取金鑰；改用 `profile_name` 或 `role_arn`。 |
| `--template given two report templates` | 每種型別最多隻給一個範本。 |

## 會讓執行停止的引數 {#flags-that-stop-the-run}

有兩個引數會被接受，但會讓執行以結束代碼 2 停止，並輸出以引數名開頭的訊息。`--compliance-standard` 的訊息是尚未實現；`--disable-production-safety` 的訊息是隻讀保護無法關閉。見[功能狀態與已知限制](../getting-started/status.md)。

## 結束代碼 3 {#exit-code-3}

這不是 InvenTag 的錯誤。標籤策略發現了違規，並且設定範本設定了 `fail_on_tag_violations: true`。
開啟 Tag Compliance 工作表或 JSON 檔案，檢視是哪些資源。

## 報告看起來不對 {#reports-look-wrong}

| 你看到的情況 | 原因和解決辦法 |
|---|---|
| 工作表很寬，帶有 `raw_data.*` 欄 | 這是預設版面配置。請使用 `--template standard-bom`。 |
| 缺少標籤對應欄 | 標籤對應只會向預設工作簿新增欄。使用 `--template` 時，請用 `tag_columns`。見[設定檔](../reference/configuration-files.md#tag-mappings)。 |
| 自定義服務描述被忽略 | S3、EC2、RDS、Lambda 和 VPC 有內建描述，除非你的條目指定了 `template`，否則內建描述優先。見[設定檔](../reference/configuration-files.md#service-descriptions)。 |
| 沒有網路或安全工作表 | 新增 `--enable-network-analysis` 或 `--enable-security-analysis`，並確認掃描找到了 VPC 或安全組。與 `--template` 一起使用時，這些引數不新增任何內容。見[網路與安全分析](./network-and-security-analysis.md)。 |
| 缺少 IAM、S3、CloudFront 或 Route 53 資源 | 它們被 `--account-services` 或 `--account-tags` 篩掉了，或者該身份缺少權限（在日誌中查詢每個服務一條的警告）。區域列表無關緊要：全域性服務始終從 `us-east-1` 讀取。 |
| 某個資源沒有顯示標籤，或出現了兩次 | 用 `--debug` 執行，並把 ARN 欄與 AWS 控制檯中的 ARN 對比。如果不一致，請作為 issue 報告，並附上服務和資源型別。 |
| 沒有報告檔案，且結束代碼為 0 | 掃描沒有找到任何內容，或者 `--account-services` 或 `--account-tags` 把所有內容都篩掉了。在日誌中查詢 `No resources to report`。 |
| 報告中缺少某個帳戶 | 它的憑證或角色失敗了。見[無法 assume 角色](#a-role-cannot-be-assumed)。 |
| 缺少變更報告 | 第一次執行不會寫出變更報告。它還要求狀態管理和差異檢測處於開啟狀態。見[跟蹤兩次執行之間的變更](./track-changes.md)。 |
| 其他使用者無法開啟 `bom_output/` | 輸出檔案只對執行 InvenTag 的使用者私有。請有意識地共享它們。 |

## 可以忽略的噪音 {#noise-you-can-ignore}

有些訊息看起來像錯誤，但不會改變你的報告。

| 訊息 | 為什麼可以忽略 |
|---|---|
| ``Failed to render template vpc_vpc: 'cidr_block'``（使用 `--service-descriptions` 時） | VPC 描述範本需要一個該資源沒有的欄位。報告不受影響。 |
| `No account specification method provided. Using default AWS credentials.` | 你沒有指定帳戶，所以 InvenTag 使用了你目前的憑證。這是正常情況。 |
| `Cross-account role ... not usable ... trying default credentials` | InvenTag 嘗試了預設的角色名稱，無法 assume 它，於是用你自己的憑證繼續。每個帳戶只記錄一次。 |

## 安裝問題 {#install-problems}

見[安裝 InvenTag](../getting-started/installation.md#fix-install-problems)。

## 還是解決不了？ {#still-stuck}

請提交一個 [issue](https://github.com/habhabhabs/inventag-aws/issues)，附上你執行的命令、版本（`python -m pip show inventag-aws`；如果是克隆的儲存庫，則用 `git describe --tags`）和訊息。
請刪除你不想分享的帳戶 ID 和名稱。切勿貼上憑證。
