---
title: 配置文件
description: InvenTag 读取的文件格式（账户文件、标签映射和服务描述），以及加载器实际接受的字段。
sidebar_position: 2
slug: /user-guides/configuration-examples
---

# 配置文件

**适合谁阅读：** 你要手工编写或检查 InvenTag 的配置文件。

**读完后你可以：** 写出加载器能接受的账户文件、标签映射文件和服务描述文件。

关于模板（报告版式、标签策略、运行设置），见[模板参考](../templates/reference.md)。
配置模板能做账户文件能做的一切，只是不能存放访问密钥，而且校验更严格，因此新的配置请优先使用它。

所有文件都可以是 YAML（`.yaml`、`.yml`）或 JSON（`.json`）。不扫描也可以检查它们：

```bash
inventag --accounts-file accounts.yaml --tag-mappings tags.yaml \
  --validate-config-only --skip-credential-validation
```

这条命令只读取文件，不调用 AWS。

## 账户文件 {#accounts-file}

与 `--accounts-file` 一起使用。

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

每个账户需要**一种**获取凭证的方式：

| 字段 | 用途 |
|---|---|
| `profile_name` | 一个 AWS CLI 配置文件，例如 IAM Identity Center 配置文件。 |
| `role_arn` | InvenTag 使用你当前的凭证 assume 的角色。 |
| `access_key_id` 和 `secret_access_key`（以及可选的 `session_token`） | 写在文件中的密钥。应避免使用：任何能读取该文件的人都拿到了密钥。 |

`settings` 中的值会覆盖对应的命令行参数。

要在每个账户中使用同一个角色名称，请省略 `role_arn`，并在命令中加上
`--cross-account-role InvenTagReadOnly`。

损坏的账户文件会在扫描之前就让运行停止。例如，没有加引号的账户 ID（示例数据）：

```text title="Terminal"
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
inventag - ERROR - ❌ Accounts configuration is invalid:
inventag - ERROR -    - Account 1: 'account_id' must be a non-empty string
inventag - ERROR - ❌ Some configuration files have validation errors
$ echo $?
1
```

现成的示例在仓库的
[`examples/`](https://github.com/habhabhabs/inventag-aws/tree/main/examples)
文件夹中，例如 `accounts_cross_account_roles.json` 和
`accounts_with_profiles.json`。

## 标签映射 {#tag-mappings}

与 `--tag-mappings` 一起使用。每个条目会在报告中添加一个命名列。
该列显示标签的值；如果资源没有这个标签，则显示默认值。

```yaml
tag_mappings:
  - tag: CostCenter          # required: the tag key
    name: Cost Center        # required: the column name
    default_value: Unknown   # optional: shown when the tag is missing
    description: Budget that pays for the resource
    required: false
    case_sensitive: false
```

该列出现在默认工作簿中（不使用 `--template` 时）。使用 `--template` 时它不会出现：请改用报告模板中的 `tag_columns`。
使用版式文件（`--excel-template`、`--word-template`）时，把列名添加到 `extra_fields`。

请使用顶层键 `tag_mappings`，其值是条目的**列表**。InvenTag 也接受较早的写法，即把每个标签键作为顶层键，并给出 `column_name` 值。

上面这个条目在 EC2 工作表上的示例结果：

| service | type | id | Cost Center |
|---|---|---|---|
| EC2 | Instance | i-0abc1234def567890 | CC-1042 |
| EC2 | Volume | vol-0abc1234def567890 | Unknown |

## 服务描述 {#service-descriptions}

与 `--service-descriptions` 一起使用。它会在报告中添加 `service_description` 列。
没有文件时，InvenTag 会写入内置描述，例如
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

顶层键 `service_descriptions` 是必需的。在每个服务之下，每种资源类型（或 `default`）都需要一个 `description`。

**对某些服务，内置描述优先。** InvenTag 为 S3、EC2、RDS、Lambda 和 VPC 内置了描述模板。
对这些服务，单独写一个自定义 `description` 会被忽略，使用的仍是内置文本。
要替换它，请给条目加上 `template`，并在 `templates` 下定义该模板。
模板可以使用 `{resource_id}`、`{resource_type}`、`{service}`、`{region}` 和 `{account_id}`。
对其他所有服务，普通的 `description` 会按原样使用（示例中 DynamoDB 表使用的是 `Application data table`）。

如果模板无法填充，InvenTag 会记录一条警告，例如
`Failed to render template vpc_vpc: 'cidr_block'`，并使用备用文本。

## BOM 处理配置 {#bom-processing-configuration}

与 `--bom-config` 一起使用。它是一个 YAML 或 JSON 映射，其键是 BOM 处理配置的字段，例如：

```yaml
enable_network_analysis: false
enable_parallel_processing: true
max_worker_threads: 4
```

未知的键会被忽略，并记录一条列出这些键的警告，所以请在日志中查找拼错的键。
例如，`enable_network_analysis: true` 添加的工作表与 `--enable-network-analysis` 相同。
这个文件用于高级调优；大多数人从来不需要它。

## 下一步 {#next-steps}

- [模板参考](../templates/reference.md)
- [扫描多个账户](../guides/scan-multiple-accounts.md)
