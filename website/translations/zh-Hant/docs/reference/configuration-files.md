---
title: 配置檔案
description: InvenTag 讀取的檔案格式（賬戶檔案、標籤對映和服務描述），以及載入器實際接受的欄位。
sidebar_position: 2
slug: /user-guides/configuration-examples
---

# 配置檔案

**適合誰閱讀：** 你要手工編寫或檢查 InvenTag 的配置檔案。

**讀完後你可以：** 寫出載入器能接受的賬戶檔案、標籤對映檔案和服務描述檔案。

關於模板（報告版式、標籤策略、執行設定），見[模板參考](../templates/reference.md)。
配置模板能做賬戶檔案能做的一切，只是不能存放訪問金鑰，而且校驗更嚴格，因此新的配置請優先使用它。

所有檔案都可以是 YAML（`.yaml`、`.yml`）或 JSON（`.json`）。不掃描也可以檢查它們：

```bash
inventag --accounts-file accounts.yaml --tag-mappings tags.yaml \
  --validate-config-only --skip-credential-validation
```

這條命令只讀取檔案，不掃描任何內容。它仍會呼叫一次 `ec2:DescribeRegions` 來列出區域，如果呼叫失敗，會記錄一條警告。

## 賬戶檔案 {#accounts-file}

與 `--accounts-file` 一起使用。

```yaml
accounts:
  - account_id: "123456789012"         # required, in quotes
    account_name: Production           # optional, shown in reports
    role_arn: arn:aws:iam::123456789012:role/InvenTagReadOnly
    external_id: optional-external-id  # only if the trust policy needs it
    regions: [us-east-1, eu-west-1]    # optional; empty = every enabled region
    services: []                       # optional; empty = all services
  - account_id: "210987654321"
    account_name: Development
    profile_name: dev-readonly         # an AWS CLI profile instead of a role
settings:                              # optional
  max_concurrent_accounts: 4
  account_processing_timeout: 1800     # seconds, at least 60
  output_directory: bom_output
```

每個賬戶需要**一種**獲取憑證的方式：

| 欄位 | 用途 |
|---|---|
| `profile_name` | 一個 AWS CLI 配置檔案，例如 IAM Identity Center 配置檔案。 |
| `role_arn` | InvenTag 使用你當前的憑證 assume 的角色。 |
| `access_key_id` 和 `secret_access_key`（以及可選的 `session_token`） | 寫在檔案中的金鑰。應避免使用：任何能讀取該檔案的人都拿到了金鑰。 |

`settings` 中的值會覆蓋對應的命令列引數。

要在每個賬戶中使用同一個角色名稱，請省略 `role_arn`，並在命令中加上
`--cross-account-role InvenTagReadOnly`。

損壞的賬戶檔案會在掃描之前就讓執行停止。例如，沒有加引號的賬戶 ID（示例資料）：

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

現成的示例在倉庫的
[`examples/`](https://github.com/habhabhabs/inventag-aws/tree/main/examples)
資料夾中，例如 `accounts_cross_account_roles.json` 和
`accounts_with_profiles.json`。

## 標籤對映 {#tag-mappings}

與 `--tag-mappings` 一起使用。每個條目會在報告中新增一個命名列。
該列顯示標籤的值；如果資源沒有這個標籤，則顯示預設值。

```yaml
tag_mappings:
  - tag: CostCenter          # required: the tag key
    name: Cost Center        # required: the column name
    default_value: Unknown   # optional: shown when the tag is missing
    description: Budget that pays for the resource
    required: false
    case_sensitive: false
```

該列出現在預設工作簿中（不使用 `--template` 時）。使用 `--template` 時它不會出現：請改用報告模板中的 `tag_columns`。
使用版式檔案（`--excel-template`、`--word-template`）時，把列名新增到 `extra_fields`。

請使用頂層鍵 `tag_mappings`，其值是條目的**列表**。InvenTag 也接受較早的寫法，即把每個標籤鍵作為頂層鍵，並給出 `column_name` 值。

上面這個條目在 EC2 工作表上的示例結果：

| service | type | id | Cost Center |
|---|---|---|---|
| EC2 | Instance | i-0abc1234def567890 | CC-1042 |
| EC2 | Volume | vol-0abc1234def567890 | Unknown |

## 服務描述 {#service-descriptions}

與 `--service-descriptions` 一起使用。它會在報告中新增 `service_description` 列。
沒有檔案時，InvenTag 會寫入內建描述，例如
`Amazon EC2 Instance (i-0abc1234def567890) in us-east-1`。

```yaml
service_descriptions:
  DYNAMODB:
    default:
      description: Application data table
  EC2:
    Volume:
      description: Block storage
      template: volume_text       # needed for EC2, S3, RDS, Lambda and VPC
templates:
  volume_text:
    template: "Disk {resource_id} in {region}"
```

頂層鍵 `service_descriptions` 是必需的。在每個服務之下，每種資源型別（或 `default`）都需要一個 `description`。

**對某些服務，內建描述優先。** InvenTag 為 S3、EC2、RDS、Lambda 和 VPC 內建了描述模板。
對這些服務，單獨寫一個自定義 `description` 會被忽略，使用的仍是內建文字。
要替換它，請給條目加上 `template`，並在 `templates` 下定義該模板。
模板可以使用 `{resource_id}`、`{resource_type}`、`{service}`、`{region}` 和 `{account_id}`。
對其他所有服務，普通的 `description` 會按原樣使用（示例中 DynamoDB 表使用的是 `Application data table`）。

如果模板無法填充，InvenTag 會記錄一條警告，例如
`Failed to render template vpc_vpc: 'cidr_block'`，並使用備用文字。

## BOM 處理配置 {#bom-processing-configuration}

與 `--bom-config` 一起使用。它是一個 YAML 或 JSON 對映，其鍵是 BOM 處理配置的欄位，例如：

```yaml
enable_network_analysis: false
enable_parallel_processing: true
max_worker_threads: 4
```

未知的鍵會被忽略且不給任何提示，所以拼錯的鍵不會有任何作用。
例如，`enable_network_analysis: true` 新增的工作表與 `--enable-network-analysis` 相同。
這個檔案用於高階調優；大多數人從來不需要它。

## 下一步 {#next-steps}

- [模板參考](../templates/reference.md)
- [掃描多個賬戶](../guides/scan-multiple-accounts.md)
