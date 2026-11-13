---
title: Google Sheets 和 Docs 输出
description: 如何把 InvenTag 清单写入 Google Sheets 电子表格和 Google Docs 文档、如何登录、谁能打开这些文件，以及哪些部分尚未对真实的 Google 验证过。
sidebar_position: 9
---

# Google Sheets 和 Docs 输出

**适合谁阅读：** 你希望把清单放在 Google Drive 中，替代或补充 Excel、Word 文件。

**读完后你会了解：** 如何安装 Google 库、如何登录、该用哪些参数、谁能打开这些文件，以及哪些部分尚未验证。

## 你会得到什么 {#what-you-get}

- `--create-google-sheets` 把与 `--create-excel` 相同的工作簿（相同的工作表、相同的行顺序、相同的模板）写成 Google Sheets 电子表格。
- `--create-google-docs` 把与 `--create-word` 相同的报告写成 Google Docs 文档。
- InvenTag 先生成 Excel 和 Word 报告，再复制它们，因此 `--template` 对 Google 文件的影响与对本地文件完全一样。
- 运行时会打印每个文件的 URL。

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

- Google Sheets 的单元格最多容纳 50,000 个字符，一个电子表格最多 1,000 万个单元格。
  非常大的清单可能超出限制；此时运行会因 Google 的错误而失败。
- Word 报告的表格默认每个服务最多显示 50 个资源（`max_rows`），Google Docs 文档也是如此。
- 单元格的值以文本形式写入，因此以 `=` 开头的标签值不会被当作公式执行。

## 尚未验证的部分 {#what-is-not-verified}

所有测试都使用模拟的 Google 客户端。**没有任何测试针对真实的 Google API 运行过**，
因为那需要一个 Google 账号。特别是，InvenTag 填充 Google Docs 文档中表格时计算的位置，
是按我们对 Docs API 规则的理解来检查的，而不是对真实服务检查的。请先用一个小账户试一试，
如果 Google Docs 文档的版式有问题，请提交 issue 反馈。

## 接下来 {#where-to-next}

- [选择要扫描什么、生成什么](./run-a-scan.md)
- [CLI 参考](../reference/cli.md#output)
- [报告模板](../templates/index.md)
