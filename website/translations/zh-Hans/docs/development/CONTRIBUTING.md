---
title: 参与贡献 InvenTag
description: 搭建 InvenTag 的开发环境，运行测试和代码检查工具，构建文档站点，并提交拉取请求。
sidebar_position: 1
---

# 参与贡献 InvenTag

**适合谁阅读：** 你想修复一个缺陷、添加一项功能或改进文档。

**读完后你可以：** 搭建好代码环境，运行项目使用的检查，并提交一个便于审查的拉取请求。

## 开始之前 {#before-you-start}

1. 先查找已有的 [issue](https://github.com/habhabhabs/inventag-aws/issues)。
   如果没有，就新建一个并描述这项更改。
2. 对于较大的更改，请在编写大量代码之前，等待维护者的回复。

## 搭建环境 {#set-up}

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # includes moto
pip install -e .          # optional: gives you the `inventag` command
git checkout -b fix/short-description
```

分支前缀：`feat/`、`fix/`、`docs/`、`refactor/`、`test/`。

## 运行检查 {#run-the-checks}

```bash
black --check scripts/ inventag/
flake8 scripts/ inventag/ --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

CI 会运行相同的 `black --check` 和 `flake8` 命令，然后在 Python 3.11、3.12、3.13、3.14 和 3.15 上运行测试。
完整的测试套件（`python -m pytest -q`）需要几分钟，在 `main` 上全部通过（9 个性能基准测试被取消选中），
并且不需要 AWS 账户：测试使用 moto 或模拟客户端，并使用假凭证。你的更改必须保持它全部通过。
只有在需要时才运行基准测试：`python -m pytest -m performance`。
更改依赖项时请运行 `pip-audit -r requirements.txt`；出现新的安全公告时，CI 会失败。

未针对 GitHub Actions Runner 验证：CI 作业；它们读自工作流文件。

**千万不要不小心对真实的 AWS 账户运行测试。** 请取消设置 `AWS_PROFILE` 和真实密钥，或者使用 moto。

## 处理模板 {#work-on-templates}

- 内置模板位于 `inventag/templating/builtin/`。每个模板都需要在
  `tests/integration/templating/` 中有一个渲染它的测试。
- 模板格式只在 `inventag/templating/schema.py` 中描述一次。修改它之后，请重新生成文档参考：
  `python -m inventag.templating.reference --write`。如果你忘了，会有一个单元测试失败。
- 文档页面上的示例输出来自 `scripts/docs/generate_example_outputs.py`，
  它会针对 moto 运行真实的 CLI。行为发生变化后，请运行 `pip install pillow` 和
  `python scripts/docs/generate_example_outputs.py`，并提交结果。
  `--check` 会告诉你页面是否已经过时。生成图片需要 LibreOffice（`soffice`）和 `pdftoppm`。

## 处理文档 {#work-on-the-docs}

文档是 `docs/` 中的 Markdown 文件，通过 Docusaurus 从 `website/` 发布。

```bash
cd website
npm ci
npm run build          # fails on broken links and missing SEO metadata
npm run check:links    # checks links in the built site
npm run start          # local preview at http://localhost:3000/inventag-aws/
```

写作规则：

- 每个页面的 front matter 中都有唯一的 `title` 和 `description`，并且恰好有一个 `#` 标题。
- 开头先说明页面适合谁阅读，以及读者读完后能做什么。
- 句子简短，使用主动语态，用词平实。解释所有行话。
- 每条命令、每个标志和每份输出都必须与代码一致。写下之前先运行一遍，并把示例输出标注为示例数据。
- 不要编造数字，不用最高级，不声称合规或认证。
- 标题按顺序排列，表格带有表头行，图片带有替代文本，不要仅靠表情符号或颜色来传达含义。

侧边栏由各文件夹以及每个文件夹的 `_category_.json` 生成。

## 提交并创建拉取请求 {#commit-and-open-a-pull-request}

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```text
feat(templates): add landscape option for Word reports
fix(discovery): include EC2 instances in comprehensive discovery
docs: explain tag policy scopes
```

在拉取请求中，说明改了什么、如何测试的，以及更新了哪些文档。
修复或添加功能时，请更新[功能状态](../getting-started/status.md)。

## 下一步 {#next-steps}

- [代码如何组合在一起](./architecture.md)
- [安全](../security/index.md)
