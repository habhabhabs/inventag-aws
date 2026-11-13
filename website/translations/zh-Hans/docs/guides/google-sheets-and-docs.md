---
title: Google Sheets 和 Docs 输出
description: 如何把 InvenTag 清单写入 Google Sheets 电子表格和 Google Docs 文档、如何登录、谁能打开这些文件、如何用你自己的 Google 账号测试，以及哪些部分尚未对真实的 Google 验证过。
sidebar_position: 9
---

# Google Sheets 和 Docs 输出

**适合谁阅读：** 你希望把清单放在 Google Drive 中，替代或补充 Excel、Word 文件。

**读完后你会了解：** 如何安装 Google 库、如何登录、该用哪些参数、谁能打开这些文件、如何用你自己的 Google 账号测试输出，以及哪些部分尚未验证。

## 你会得到什么 {#what-you-get}

- `--create-google-sheets` 把与 `--create-excel` 相同的工作簿（相同的工作表、相同的行顺序、相同的模板）写成 Google Sheets 电子表格。
- `--create-google-docs` 把与 `--create-word` 相同的报告写成 Google Docs 文档。
- InvenTag 先生成 Excel 和 Word 报告，再复制它们，因此 `--template` 对 Google 文件的影响与对本地文件完全一样。
- 运行时会打印每个文件的 URL，例如 `Google Sheet: https://docs.google.com/spreadsheets/d/...` 和 `Google Doc: https://docs.google.com/document/d/...`。
- 使用 `--per-account-reports` 时，InvenTag 为每个账户生成一对文件。标题以 ` - ` 和账户 ID 结尾，每一行 URL 以 `[123456789012]` 开头。
- 如果运行没有找到任何资源，就不会生成 Google 文件。

## 安装 Google 附加包 {#install-the-google-add-on}

写入 Google 需要几个额外的 Python 包（Google 的登录和 API 库）。大多数人从不使用 Google 输出，
所以这些包默认不随 InvenTag 一起安装。你只需用下面这条命令添加一次：

```bash title="Terminal"
pip install "inventag-aws[google]"
```

可以把它理解为“安装 InvenTag，外加它的 Google 附加包”。方括号里的部分是附加包的名称，
不是占位符，所以请按原样输入，包括引号（macOS 默认的 shell zsh 需要引号）。

- **你已经安装了 InvenTag。** 运行同一条命令。pip 会保留你现有的 InvenTag，只添加 Google 包。
- **你是用 pipx 安装的。** 运行 `pipx install "inventag-aws[google]"`，或者运行
  `pipx inject inventag-aws google-api-python-client google-auth google-auth-oauthlib`
  把这些包添加到你已有的 InvenTag 中。
- **你使用虚拟环境。** 先激活它，这样这些包就会装在 InvenTag 旁边。

Excel、Word 或其他功能都不需要这个附加包。如果在没有它的情况下使用 Google 参数，
InvenTag 会以退出码 2 停止，说明缺少哪个包，并打印这条命令。

## 登录 {#sign-in}

任选一种：

| 方式 | 参数 | 适用场景 |
|---|---|---|
| 服务账号密钥 | `--google-credentials key.json` | 定时运行和 CI |
| 你自己的 Google 账号 | `--google-oauth-client client_secret.json` | 在笔记本电脑上运行。浏览器只会打开一次，令牌保存在 `~/.config/inventag/google-token.json`，只有你本人可读。 |
| 应用默认凭证 | 无 | 你运行过 `gcloud auth application-default login` |

在凭证所属的 Google Cloud 项目中启用 Google Sheets、Google Docs 和 Google Drive API。

InvenTag 会在扫描 AWS 之前读取密钥文件或 OAuth 客户端文件，因此文件有误时，运行会立即以退出码 2 停止，并给出以 `inventag: error: Google:` 开头的消息。

权限范围是 `drive.file`：InvenTag 只能访问它自己创建的文件。使用
`--google-folder-id` 时，它会请求完整的 Drive 权限范围，因为它必须把文件放进一个已有的文件夹。

## 谁能打开这些文件 {#who-can-open-the-files}

文件对创建它们的账号**私有**。除非你提出要求，否则不会共享任何内容。

```bash title="Terminal"
inventag --create-google-sheets --create-google-docs \
  --google-credentials key.json \
  --google-share-with you@example.com \
  --google-share-with team@example.com --google-share-role commenter \
  --google-folder-id 1AbCdEfGh \
  --google-title "AWS inventory, May"
```

- `--google-share-with EMAIL` 可以重复使用。`--google-share-role` 为所有这些人统一设置
  `reader`（默认）、`commenter` 或 `writer`。
- `--google-share-anyone` 让任何拿到链接的人都能读取这些文件。仅用于你会公开发布的数据。
- 服务账号拥有它所创建的文件，这些文件在它自己的 Drive 中，你无法打开。如果你用服务账号登录，
  又既没有给出 `--google-share-with` 也没有给出 `--google-folder-id`，InvenTag 会对此发出警告。
- 如果在没有 `--create-google-sheets` 或 `--create-google-docs` 的情况下使用
  `--google-share-with`、`--google-share-role`、`--google-share-anyone`、
  `--google-folder-id` 和 `--google-title`，会以退出码 2 停止。

## 凭证绝不会写入日志 {#credentials-are-never-logged}

密钥文件的路径不会被打印；看起来像 Google 私钥、访问令牌、刷新令牌或客户端密钥的机密，
在每一行日志中都会被遮蔽，包括 `--debug`。Google 库的错误信息会被缩短为错误类型，
因为它们可能引用密钥文件。

## 限制 {#limits}

- Google Sheets 的单元格最多容纳 50,000 个字符。InvenTag 会把更长的文本在 49,000 个字符处截断。一个电子表格最多 1,000 万个单元格，一个工作表最多 18,278 列。
- InvenTag 会在调用 Google 之前先数单元格。如果报告太大，它不会创建任何内容并说明原因，运行以退出码 1 结束。Excel 和 Word 文件仍会写出。例如：
  `The report has 12,000,000 cells; a Google spreadsheet allows 10,000,000. No
  spreadsheet was created. Send fewer resources (filters or an account subset)
  or use the Excel report.`
- InvenTag 会把大的工作表分成多个请求发送，每个请求最多 2,000 行，约 100 万个字符。
- 如果 Google 返回“429 too many requests”，InvenTag 会记录 `Google rate limit
  reached; waiting 5 seconds` 并重试。在最后一次尝试之前，它依次等待 5、10、20、40 和 60 秒。
- 如果文件创建之后某个调用失败，运行会以退出码 1 结束，消息中会给出写到一半的文件的 URL：`The spreadsheet was already
  created and may be incomplete: <url> (delete it in Google Drive).` Google Docs 文档同理。请删除该文件，然后重新运行。
- Word 报告的表格默认每个服务最多显示 50 个资源（报告模板中是 `max_rows_per_service`，布局文件中是 `max_rows`），Google Docs 文档也是如此。
- 单元格的值以文本形式写入，因此以 `=` 开头的标签值不会被当作公式执行。

## 尚未验证的部分 {#what-is-not-verified}

大多数测试使用模拟的 Google 客户端。**我们没有记录过针对真实 Google API 的运行**，
因为那需要一个 Google 账号。特别是，InvenTag 填充 Google Docs 文档中表格时计算的位置，
是按我们对 Docs API 规则的理解来检查的，而不是对真实服务检查的。请先用一个小账户试一试，
如果 Google Docs 文档的版式有问题，请提交 issue 反馈。

## 用你自己的 Google 账号检查 {#check-it-against-your-own-google-account}

仓库里有一个脚本，可以替你做真实 Google 的测试。它用 moto（AWS 的模拟）构建一个虚构的资源环境，
因此不需要 AWS 账号，只会接触 Google。它用 `--create-google-sheets` 和
`--create-google-docs` 运行 InvenTag，从 Google 读回这些文件，并与同一次运行生成的 Excel 和 Word 文件比较。
它会打印一张 PASS 或 FAIL 表、两个 URL，以及 `RESULT: PASS` 或 `RESULT: FAIL`。通过时退出码为 0。

请在仓库的检出目录中运行它。

1. 安装 Google 库和 moto：

   ```bash title="Terminal"
   pip install "inventag-aws[google]"
   pip install moto
   ```

2. 在凭证所属的 Google Cloud 项目中，启用 Google Sheets API、Google Docs API 和 Google Drive API。
   如果其中一个没有启用，Google 会返回 HTTP 403，脚本会指出要启用哪个 API。
3. 创建一个类型为“Desktop app”的 OAuth 客户端，把它下载为 `client_secret.json`，然后运行：

   ```bash title="Terminal"
   python scripts/google_live_test.py --google-oauth-client client_secret.json --large
   ```

   浏览器会打开一次。如果应用处于“Testing”状态，请把你的账号添加到 OAuth consent screen 的 Test users 下。

如果要使用服务账号密钥，请传入 `--google-credentials key.json`。服务账号拥有它自己 Drive 中的文件，
所以如果你想打开它们，请加上 `--share-with you@example.com`。

| 参数 | 作用 |
|---|---|
| `--large` | 还会测试一个 20,000 行的工作表和一个 300 行的 Doc 表格。它会统计 API 调用次数，并注入两次“429”应答来证明重试有效。大约多花一分钟。 |
| `--share-with EMAIL` | 把文件共享（reader）给这个地址，并检查只有该地址和所有者能打开它们。可重复使用。 |
| `--keep` | 把文件留在 Drive 中。默认情况下，脚本会在最后把它创建的每个文件移到 Drive 的回收站。 |
| `--folder-id ID` | 还会在这个 Drive 文件夹中创建一对文件。这需要完整的 Drive 权限范围。使用 `--google-oauth-client` 时，请先删除 `~/.config/inventag/google-token.json`，这样它会重新询问。 |

不带登录参数时，脚本使用应用默认凭证。Google 会阻止 `gcloud` 自己的登录客户端使用 Drive、Docs 和 Sheets 的权限范围，
所以这里也需要你自己的 OAuth 客户端文件。运行 `python
scripts/google_live_test.py --help` 查看确切的 `gcloud` 命令。我们没有验证过这条途径。请优先使用 OAuth 客户端。

脚本会检查这些内容：

- 电子表格和 Doc 存在，并且与打印出的 URL 一致。
- 工作表名称和顺序、行和列，以及每个单元格都与 Excel 文件一致。
- 以 `=` 开头的文本回来时仍是文本，而不是公式。
- 长文本、带重音的文本、CJK 文本和空工作表都能保留。
- 标题行为粗体并带颜色，顶部几行被冻结。
- Doc 的标题和每个表格单元格都与 Word 文件一致。
- 两个文件对该账号私有（以及对 `--share-with` 地址）。

如果你运行了它，请把最后的表格发给我们。只有在真实账号上通过之后，我们才会修改本页。

## 接下来 {#where-to-next}

- [选择要扫描什么、生成什么](./run-a-scan.md)
- [CLI 参考](../reference/cli.md#output)
- [报告模板](../templates/index.md)
